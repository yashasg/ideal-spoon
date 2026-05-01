"""Training entrypoint.

Implement this file in this order:
1. Run `--print-config` until config parsing is boring.
2. Run `--preflight` on the real data path before touching the GPU.
3. Run the smoke config on one tiny JSONL file and make sure checkpoints save.
4. Add eval-during-train only after the train-only path works.
5. Add resume-from-checkpoint before using short-lived/free GPU providers.
6. The run report is written automatically after every train run.

Skeleton uses `transformers.Trainer` because it gives you checkpointing, LR
scheduling, logging, and resume-from-checkpoint for free. Roll your own loop
only after you've felt the pain of doing it the easy way.

Run from repo root with ``PYTHONPATH=code`` — paths are config-relative, not
CWD-relative:

    # Smoke test — no GPU, no download of heavy base model:
    PYTHONPATH=code python -m llm_hawaii.train --config code/configs/smoke.json --preflight
    PYTHONPATH=code python -m llm_hawaii.train --config code/configs/smoke.json --print-config

    # Stage 1 preflight on the real local data (no model download):
    PYTHONPATH=code python -m llm_hawaii.train --config code/configs/stage1_fineweb2_haw.json --preflight

    # Stage 1 train (requires HF access + GPU):
    PYTHONPATH=code python -m llm_hawaii.train --config code/configs/stage1_fineweb2_haw.json

    # Resume after interrupted session:
    PYTHONPATH=code python -m llm_hawaii.train --config code/configs/stage1_fineweb2_haw.json \\
        --resume-from-checkpoint runs/llama31-8b-stage1-multisource/checkpoint-200

    # Train then eval immediately after:
    PYTHONPATH=code python -m llm_hawaii.train --config code/configs/stage1_fineweb2_haw.json \\
        --eval-after-train
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import inspect
import json
import subprocess
import time
import warnings
from pathlib import Path
from typing import Any, Optional

from .config import TrainConfig, load_config


def _signature_parameters(obj: Any) -> dict[str, inspect.Parameter]:
    """Return callable/class signature parameters across wrapped APIs."""
    try:
        return dict(inspect.signature(obj).parameters)
    except (TypeError, ValueError):
        return dict(inspect.signature(obj.__init__).parameters)


def _require(pkg: str, install_hint: str) -> Any:
    try:
        return __import__(pkg)
    except ImportError as e:
        raise RuntimeError(
            f"Missing optional dependency '{pkg}'. Install with: {install_hint}"
        ) from e


def _hash_file(path: Path, chunk_size: int = 1 << 20) -> str:
    """SHA-256 hex digest of a file; streams so large corpus files are safe."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


# Canonical tokenizer files that constitute the tokenizer identity.
# Sorted for determinism; only present files are included in the hash.
_TOKENIZER_SHA_FILES = [
    "added_tokens.json",
    "merges.txt",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.json",
]


def compute_tokenizer_sha(tokenizer_dir: Path) -> str:
    """SHA-256 over the canonical tokenizer files present in ``tokenizer_dir``.

    Files are hashed in sorted order so the digest is deterministic regardless
    of filesystem ordering.  Raises ``FileNotFoundError`` if no tokenizer files
    are found (mistyped path guard).
    """
    h = hashlib.sha256()
    found = False
    for fname in _TOKENIZER_SHA_FILES:
        fpath = tokenizer_dir / fname
        if fpath.exists():
            found = True
            h.update(fname.encode("utf-8"))
            h.update(_hash_file(fpath).encode("ascii"))
    if not found:
        raise FileNotFoundError(
            f"No tokenizer files found in '{tokenizer_dir}'. "
            "Expected at least one of: " + ", ".join(_TOKENIZER_SHA_FILES)
        )
    return h.hexdigest()


def _compute_artifact_sha(out_dir: Path) -> Optional[str]:
    """SHA-256 of the saved LoRA adapter file, or None if not found."""
    for candidate in ("adapter_model.safetensors", "adapter_model.bin"):
        fpath = out_dir / candidate
        if fpath.exists():
            return _hash_file(fpath)
    return None


def _git_commit(cwd: Optional[Path] = None) -> str:
    """Return current HEAD SHA, or 'unknown' — never raises."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            cwd=str(cwd) if cwd else None,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def run_preflight(cfg: TrainConfig) -> dict:
    """Pre-training checks that do NOT require downloading the base model.

    Validates config, data-path existence, text-field presence, output-dir
    creatability, and runtime capability.  Returns a dict; never raises on
    individual check failures — read ``report["issues"]`` to decide pass/fail.

    Keys returned:
      issues              list[str] — empty means all checks passed
      train_path          str (resolved absolute)
      train_path_exists   bool
      train_row_count     int | None
      train_field_ok      bool | None
      eval_path           str  (only if eval_path configured)
      eval_path_exists    bool (only if eval_path configured)
      output_dir          str
      output_dir_ok       bool
      capability          dict from model.check_runtime_capability (non-fatal)
    """
    from . import data as data_mod  # lazy — no torch needed

    issues: list[str] = []
    report: dict = {"issues": issues}

    # --- train_path ---
    train_path = Path(cfg.train_path)
    report["train_path"] = str(train_path)
    if not train_path.exists():
        issues.append(f"train_path not found: {train_path}")
        report["train_path_exists"] = False
        report["train_row_count"] = None
        report["train_field_ok"] = None
    else:
        report["train_path_exists"] = True
        first_row: Optional[dict] = None
        row_count = 0
        for row in data_mod.iter_jsonl(train_path):
            if first_row is None:
                first_row = row
            row_count += 1
        report["train_row_count"] = row_count
        if row_count == 0:
            issues.append(f"train_path has zero rows: {train_path}")
            report["train_field_ok"] = None
        else:
            # Stage-2 SFT records have instruction/source/target fields;
            # Stage-1 CPT records have a single text field.
            if cfg.stage == "stage2-sft":
                check_fields = [
                    cfg.sft_instruction_field,
                    cfg.sft_source_field,
                    cfg.sft_target_field,
                ]
            else:
                check_fields = [cfg.text_field]
            missing_fields = [f for f in check_fields if f not in (first_row or {})]
            field_ok = not missing_fields
            report["train_field_ok"] = field_ok
            if not field_ok:
                issues.append(
                    f"Required fields {missing_fields} missing from first row; "
                    f"found keys: {sorted((first_row or {}).keys())}"
                )

    # --- eval_path (optional) ---
    if cfg.eval_path:
        eval_path = Path(cfg.eval_path)
        report["eval_path"] = str(eval_path)
        if not eval_path.exists():
            issues.append(f"eval_path configured but not found: {eval_path}")
            report["eval_path_exists"] = False
        else:
            report["eval_path_exists"] = True

    # --- output dir ---
    out = Path(cfg.output_dir)
    try:
        out.mkdir(parents=True, exist_ok=True)
        report["output_dir"] = str(out.resolve())
        report["output_dir_ok"] = True
    except OSError as e:
        issues.append(f"Cannot create output_dir '{out}': {e}")
        report["output_dir_ok"] = False
        report["output_dir"] = str(out)

    # --- runtime capability (non-fatal; torch may be absent on laptop) ---
    try:
        from . import model as model_mod
        cap = model_mod.check_runtime_capability(cfg.use_qlora, cfg.bf16)
        report["capability"] = cap
    except RuntimeError as e:
        report["capability"] = {"error": str(e)}
        warnings.warn(
            f"Runtime capability check skipped (torch missing?): {e}",
            stacklevel=2,
        )

    # --- Stage 2 lineage checks (stage2-sft only; Stage 1 path unaffected) ---
    if cfg.stage == "stage2-sft":
        lineage = run_stage2_lineage_preflight(cfg)
        issues.extend(lineage.pop("issues", []))
        report.update(lineage)

    return report


def run_stage2_lineage_preflight(cfg: TrainConfig) -> dict:
    """Stage 2 lineage checks. Does NOT require ML deps or a GPU.

    Validates:
    1. ``parent_run_dir`` is configured, exists, and contains a ``run_report.json``
       with a ``tokenizer_sha`` recorded from Stage 1.
    2. Current tokenizer files in ``parent_run_dir`` hash to that same SHA —
       any single-byte tamper of ``tokenizer.json`` (or any canonical file)
       fails loudly here, before any GPU work starts.
    3. Records ``corpus_manifest_sha`` (hash of ``cfg.train_path``),
       ``parent_artifact_sha`` (from parent ``run_report.json``), and the
       verified ``tokenizer_sha``.

    Returns a dict with keys:
      issues                list[str] — empty means all checks passed
      tokenizer_sha         str | None
      parent_artifact_sha   str | None
      corpus_manifest_sha   str | None

    Stage 1 path: this function is only called for ``stage2-sft``; Stage 1
    ``run_preflight`` is unaffected.
    """
    issues: list[str] = []
    report: dict = {
        "issues": issues,
        "tokenizer_sha": None,
        "parent_artifact_sha": None,
        "corpus_manifest_sha": None,
    }

    # Corpus SHA — hash the training JSONL regardless of other checks.
    train_path = Path(cfg.train_path)
    if train_path.exists():
        report["corpus_manifest_sha"] = _hash_file(train_path)

    # parent_run_dir is required for Stage 2.
    if not cfg.parent_run_dir:
        issues.append(
            "stage2-sft lineage check requires 'parent_run_dir' in config "
            "(path to Stage 1 / merged-base output dir containing saved "
            "tokenizer files and run_report.json)"
        )
        return report

    parent_dir = Path(cfg.parent_run_dir)
    if not parent_dir.exists():
        issues.append(f"parent_run_dir not found: {parent_dir}")
        return report

    # Load parent run report for expected tokenizer SHA and artifact SHA.
    parent_report_path = parent_dir / "run_report.json"
    expected_tokenizer_sha: Optional[str] = None
    if not parent_report_path.exists():
        issues.append(
            f"No run_report.json found in parent_run_dir '{parent_dir}'; "
            "cannot verify tokenizer SHA or artifact lineage. "
            "Ensure Stage 1 completed and wrote its run report."
        )
    else:
        with open(parent_report_path, "r", encoding="utf-8") as f:
            parent_report = json.load(f)
        expected_tokenizer_sha = parent_report.get("tokenizer_sha")
        report["parent_artifact_sha"] = parent_report.get("artifact_sha")
        if not expected_tokenizer_sha:
            issues.append(
                "parent run_report.json has no 'tokenizer_sha' field — "
                "was it produced by an older trainer version? "
                "Re-run Stage 1 to regenerate a complete run report."
            )

    # Compute tokenizer SHA from files saved in parent_run_dir.
    try:
        tok_sha = compute_tokenizer_sha(parent_dir)
        report["tokenizer_sha"] = tok_sha
    except FileNotFoundError as e:
        issues.append(str(e))
        tok_sha = None

    # Equality gate: tampered tokenizer → hard fail.
    if expected_tokenizer_sha and tok_sha and tok_sha != expected_tokenizer_sha:
        issues.append(
            f"TOKENIZER SHA MISMATCH — Stage 1 run_report recorded "
            f"{expected_tokenizer_sha!r} but current tokenizer files in "
            f"parent_run_dir hash to {tok_sha!r}. "
            "Tokenizer files may have been tampered with or replaced. "
            "Restore the original files or re-run Stage 1."
        )

    return report


def _collect_path_stats(path: Path) -> dict:
    """File hash + row count for a JSONL path. Streams hash; counts rows."""
    from . import data as data_mod

    return {
        "path": str(path),
        "sha256": _hash_file(path),
        "row_count": sum(1 for _ in data_mod.iter_jsonl(path)),
    }


def write_run_report(
    out_dir: Path,
    cfg: TrainConfig,
    config_path: str,
    capability: dict,
    t_start: float,
    t_end: float,
    *,
    tokenizer_sha: Optional[str] = None,
    artifact_sha: Optional[str] = None,
    parent_artifact_sha: Optional[str] = None,
    corpus_manifest_sha: Optional[str] = None,
) -> Path:
    """Write a small JSON run report under ``out_dir/run_report.json``.

    Contains no raw training text — only hashes, counts, resolved config,
    git commit, runtime capability, and timing.  Enough to re-run or compare
    runs without committing data.

    Lineage fields (all optional; populated at training time):
      tokenizer_sha         SHA-256 of canonical tokenizer files in out_dir.
      artifact_sha          SHA-256 of the saved LoRA adapter (for Stage 2 to
                            read as parent_artifact_sha).
      parent_artifact_sha   artifact_sha from the parent (Stage 1) run report.
      corpus_manifest_sha   SHA-256 of the training JSONL (top-level convenience
                            field; also present in train.sha256).

    Schema version: ``training-run-report.v1``
    """
    train_stats: dict = {}
    eval_stats: Optional[dict] = None

    train_path = Path(cfg.train_path)
    if train_path.exists():
        train_stats = _collect_path_stats(train_path)
    if cfg.eval_path:
        eval_path = Path(cfg.eval_path)
        if eval_path.exists():
            eval_stats = _collect_path_stats(eval_path)

    report = {
        "schema_version": "training-run-report.v1",
        "stage": cfg.stage,
        "run_name": cfg.run_name,
        "config_path": str(Path(config_path).resolve()),
        "resolved_config": dataclasses.asdict(cfg),
        "output_dir": str(out_dir.resolve()),
        "train": train_stats,
        "eval": eval_stats,
        "git_commit": _git_commit(out_dir),
        "runtime_capability": capability,
        "wallclock_seconds": round(t_end - t_start, 2),
        "completed_at_utc": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(t_end)
        ),
        # Lineage fields — populated at training time; None for older/Stage-1
        # runs that don't supply them yet.
        "tokenizer_sha": tokenizer_sha,
        "artifact_sha": artifact_sha,
        "parent_artifact_sha": parent_artifact_sha,
        "corpus_manifest_sha": corpus_manifest_sha,
    }

    report_path = out_dir / "run_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
    print(f"Run report written: {report_path}")
    return report_path


def build_training_args(cfg: TrainConfig, has_eval: bool = False):
    transformers = _require("transformers", "pip install transformers")
    eval_strategy = "steps" if (has_eval and cfg.eval_steps) else "no"
    training_args_params = _signature_parameters(transformers.TrainingArguments)
    if "eval_strategy" in training_args_params:
        eval_strategy_key = "eval_strategy"
    elif "evaluation_strategy" in training_args_params:
        eval_strategy_key = "evaluation_strategy"
    else:
        raise RuntimeError(
            "Unsupported transformers.TrainingArguments signature: expected "
            "'eval_strategy' or 'evaluation_strategy'."
        )
    kwargs: dict = dict(
        output_dir=cfg.output_dir,
        num_train_epochs=cfg.num_train_epochs,
        per_device_train_batch_size=cfg.per_device_train_batch_size,
        gradient_accumulation_steps=cfg.gradient_accumulation_steps,
        learning_rate=cfg.learning_rate,
        warmup_ratio=cfg.warmup_ratio,
        weight_decay=cfg.weight_decay,
        lr_scheduler_type=cfg.lr_scheduler_type,
        logging_steps=cfg.logging_steps,
        save_steps=cfg.save_steps,
        save_total_limit=cfg.save_total_limit,
        bf16=cfg.bf16,
        fp16=cfg.fp16,
        gradient_checkpointing=cfg.gradient_checkpointing,
        seed=cfg.seed,
        report_to=[],  # add "wandb"/"tensorboard" later if you want
    )
    kwargs[eval_strategy_key] = eval_strategy
    if has_eval and cfg.eval_steps:
        kwargs["eval_steps"] = cfg.eval_steps
    # Eval memory controls — only passed when explicitly set in config so the
    # Trainer default is preserved for configs that don't need to constrain it.
    if cfg.per_device_eval_batch_size is not None:
        kwargs["per_device_eval_batch_size"] = cfg.per_device_eval_batch_size
    if cfg.eval_accumulation_steps is not None:
        kwargs["eval_accumulation_steps"] = cfg.eval_accumulation_steps
    if cfg.prediction_loss_only is not None:
        kwargs["prediction_loss_only"] = cfg.prediction_loss_only
    return transformers.TrainingArguments(**kwargs)


def build_trainer_kwargs(
    transformers: Any,
    *,
    model: Any,
    args: Any,
    train_dataset: Any,
    eval_dataset: Any,
    data_collator: Any,
    tokenizer: Any,
) -> dict[str, Any]:
    """Build Trainer kwargs across transformers tokenizer API changes."""
    trainer_params = _signature_parameters(transformers.Trainer)
    kwargs: dict[str, Any] = dict(
        model=model,
        args=args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        data_collator=data_collator,
    )
    if "processing_class" in trainer_params:
        kwargs["processing_class"] = tokenizer
    elif "tokenizer" in trainer_params:
        kwargs["tokenizer"] = tokenizer
    else:
        raise RuntimeError(
            "Unsupported transformers.Trainer signature: expected "
            "'processing_class' or 'tokenizer'."
        )
    return kwargs


def run_training(
    cfg: TrainConfig,
    config_path: str = "",
    resume_from_checkpoint: Optional[str] = None,
    eval_after_train: bool = False,
) -> str:
    """Wire the pieces together and call ``Trainer.train()``.

    Returns the output checkpoint dir.

    Args:
        cfg: Resolved TrainConfig (paths already absolute via load_config).
        config_path: Original config file path — stored in run report only.
        resume_from_checkpoint: If set, passed to ``Trainer.train()``.
            Use a checkpoint dir like ``runs/stage1/checkpoint-200``.
        eval_after_train: If True and ``cfg.eval_path`` is set, run
            ``trainer.evaluate()`` after training for a post-run metric snapshot.
    """
    t_start = time.time()

    # Lazy imports — keeps the module importable without ML deps.
    transformers = _require("transformers", "pip install transformers")
    from . import data as data_mod
    from . import model as model_mod

    # 0. Non-fatal capability snapshot (warns, never asserts GPU SKU).
    capability = model_mod.check_runtime_capability(cfg.use_qlora, cfg.bf16)

    # 1. Tokenizer + model (LoRA-wrapped, optionally 4-bit).
    model, tokenizer = model_mod.build_model_and_tokenizer(cfg)

    # 2. Train dataset + optional eval dataset + collator.
    if cfg.stage == "stage2-sft":
        train_records = data_mod.build_sft_dataset(
            cfg.train_path,
            tokenizer,
            instruction_field=cfg.sft_instruction_field,
            source_field=cfg.sft_source_field,
            target_field=cfg.sft_target_field,
            max_length=cfg.max_seq_len,
            normalization=cfg.unicode_normalization,
        )
        eval_records = None
        if cfg.eval_path:
            eval_records = data_mod.build_sft_dataset(
                cfg.eval_path,
                tokenizer,
                instruction_field=cfg.sft_instruction_field,
                source_field=cfg.sft_source_field,
                target_field=cfg.sft_target_field,
                max_length=cfg.max_seq_len,
                normalization=cfg.unicode_normalization,
            )
        collator = data_mod.make_sft_collator(tokenizer)
    else:
        train_records = data_mod.build_train_dataset(
            cfg.train_path,
            tokenizer,
            text_field=cfg.text_field,
            max_length=cfg.max_seq_len,
            normalization=cfg.unicode_normalization,
        )
        eval_records = None
        if cfg.eval_path:
            eval_records = data_mod.build_train_dataset(
                cfg.eval_path,
                tokenizer,
                text_field=cfg.text_field,
                max_length=cfg.max_seq_len,
                normalization=cfg.unicode_normalization,
            )
        collator = data_mod.make_collator(tokenizer)

    # 3. TrainingArguments + Trainer.
    args = build_training_args(cfg, has_eval=(eval_records is not None))
    trainer_kwargs = build_trainer_kwargs(
        transformers,
        model=model,
        args=args,
        train_dataset=train_records,
        eval_dataset=eval_records,
        data_collator=collator,
        tokenizer=tokenizer,
    )
    trainer = transformers.Trainer(**trainer_kwargs)

    # 4. Persist the resolved config next to the checkpoints — every run
    #    must be reproducible from its output dir alone.
    out = Path(cfg.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    cfg.to_json(out / "resolved_config.json")

    # 5. Train (with optional resume from a prior checkpoint).
    trainer.train(resume_from_checkpoint=resume_from_checkpoint)

    # 6. Save the LoRA adapter (small) + tokenizer.
    trainer.save_model(str(out))
    tokenizer.save_pretrained(str(out))

    # 7. Optional post-training eval pass.
    if eval_after_train and eval_records is not None:
        eval_result = trainer.evaluate()
        print(f"Post-training eval: {json.dumps(eval_result, indent=2)}")
    elif eval_after_train and eval_records is None:
        warnings.warn(
            "--eval-after-train requested but no eval_path in config; skipped.",
            stacklevel=2,
        )

    # 8. Run report (no raw text; hashes + config + git SHA + timing).
    #    Compute lineage fields from the just-saved artifacts.
    t_end = time.time()
    _tok_sha: Optional[str] = None
    try:
        _tok_sha = compute_tokenizer_sha(out)
    except FileNotFoundError:
        pass
    _art_sha = _compute_artifact_sha(out)
    _parent_art_sha: Optional[str] = None
    _corpus_sha: Optional[str] = None
    if cfg.parent_run_dir:
        parent_dir = Path(cfg.parent_run_dir)
        parent_rpt = parent_dir / "run_report.json"
        if parent_rpt.exists():
            with open(parent_rpt, "r", encoding="utf-8") as _f:
                _parent_art_sha = json.load(_f).get("artifact_sha")
    train_path = Path(cfg.train_path)
    if train_path.exists():
        _corpus_sha = _hash_file(train_path)

    write_run_report(
        out, cfg, config_path, capability, t_start, t_end,
        tokenizer_sha=_tok_sha,
        artifact_sha=_art_sha,
        parent_artifact_sha=_parent_art_sha,
        corpus_manifest_sha=_corpus_sha,
    )

    return str(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Hawaiian LLM training (prototype/learning code)."
    )
    parser.add_argument("--config", required=True, help="Path to a JSON TrainConfig.")
    parser.add_argument(
        "--print-config",
        action="store_true",
        help="Parse + resolve config and print it; do not train.",
    )
    parser.add_argument(
        "--preflight",
        action="store_true",
        help=(
            "Run preflight checks (config, data paths, runtime capability) "
            "without downloading the base model or training. "
            "Exits 0 on pass, 1 if any issues found."
        ),
    )
    parser.add_argument(
        "--resume-from-checkpoint",
        metavar="PATH",
        help=(
            "Resume training from a checkpoint directory "
            "(e.g. runs/llama31-8b-stage1-multisource/checkpoint-200). "
            "Passed directly to Trainer.train(resume_from_checkpoint=...)."
        ),
    )
    parser.add_argument(
        "--eval-after-train",
        action="store_true",
        help=(
            "Run trainer.evaluate() on eval_path after training completes. "
            "Requires eval_path to be set in the config."
        ),
    )
    ns = parser.parse_args(argv)

    cfg = load_config(ns.config)

    if ns.print_config:
        print(json.dumps(dataclasses.asdict(cfg), indent=2, sort_keys=True))
        return 0

    if ns.preflight:
        report = run_preflight(cfg)
        print(json.dumps(report, indent=2, sort_keys=True))
        issues = report.get("issues", [])
        if issues:
            print(f"\n{len(issues)} preflight issue(s) found.", flush=True)
            return 1
        print("\nPreflight passed.", flush=True)
        return 0

    out = run_training(
        cfg,
        config_path=ns.config,
        resume_from_checkpoint=ns.resume_from_checkpoint,
        eval_after_train=ns.eval_after_train,
    )
    print(f"Training complete. Artifacts at: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
