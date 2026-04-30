"""Checkpoint evaluation CLI.

Implement this file in this order:
1. Load a checkpoint and tokenizer without generating anything.
2. Compute held-out perplexity on a tiny eval JSONL.
3. Add a few fixed prompts and save the generations.
4. Run `metrics.py` checks on each generation so orthography regressions are
   visible, not buried in average loss.
5. Keep checkpoint-dev and final-holdout separate: dev is for frequent
   diagnostics; final is for major milestone checks.

Two things this should report at minimum:

  1. Held-out perplexity on a Hawaiian eval JSONL.
  2. A small batch of generations + Hawaiian text-quality checks
     (ʻokina survival, kahakō retention, NFC integrity) from
     `metrics.py`.

The output dict is also designed as a checkpoint *drift bundle*: it
captures eval-run identity (eval-file SHA, decoding config, dtype/device,
tokenizer/model identity), an orthography aggregate + tripwires across a
fixed prompt suite, and a `prompt_suite_sha256` so future checkpoints can
be compared without leaking raw text into tracked summaries. See
`docs/eval_pipeline.md` §8.

Heavy ML deps are lazy-imported. The file parses without them.

Run:

    python -m llm_hawaii.evaluate \
        --checkpoint runs/smoke \
        --eval-file examples/eval.jsonl.example
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import unicodedata
from pathlib import Path
from typing import Any

from . import metrics as metrics_mod

# Bumped whenever the report shape changes in a way that would break
# cross-checkpoint summary diffing. Stage 0 drift bundle = v2.
EVAL_SCHEMA_VERSION = "stage0_eval.v2"

# Fixed prompt suite for checkpoint drift monitoring. Spans low/medium/high
# Hawaiian diacritic density per `metrics.diacritic_density_bin`, plus one
# English control to catch English-collapse regressions cheaply.
#
# DO NOT renumber or reword these in place: changing a prompt changes
# `prompt_suite_sha256` and breaks comparability with prior checkpoints.
# Add new prompts at the end and bump `PROMPT_SUITE_ID` instead.
PROMPT_SUITE_ID = "stage0.v1"
DEFAULT_PROMPT_SUITE: list[tuple[str, str]] = [
    (
        "en_control_1",
        "Write one short paragraph in English describing a typical morning.",
    ),
    (
        "haw_low_1",
        "Aloha mai kākou.",
    ),
    (
        "haw_low_2",
        "Aloha kāua i kēia kakahiaka.",
    ),
    (
        "haw_medium_1",
        "He aha ka mōʻaukala o Hawaiʻi?",
    ),
    (
        "haw_medium_2",
        "Pehea ʻoe i kēia lā?",
    ),
    (
        "haw_high_1",
        "E kākau i hoʻokahi paukū pōkole ma ka ʻōlelo Hawaiʻi e pili ana i ka ʻohana, "
        "e hoʻohana ana i nā kahakō a me nā ʻokina a pau.",
    ),
    (
        "haw_high_2",
        "E hōʻike mai i kekahi moʻolelo pōkole ma ka ʻōlelo Hawaiʻi e pili ana i ka "
        "lā mua o ka makahiki, me nā ʻokina a me nā kahakō a pau.",
    ),
]


def _require(pkg: str, install_hint: str) -> Any:
    try:
        return __import__(pkg)
    except ImportError as e:
        raise RuntimeError(
            f"Missing optional dependency '{pkg}'. Install with: {install_hint}"
        ) from e


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _length_bin_from_tokens(n_tokens: int) -> str:
    if n_tokens <= 128:
        return "short"
    if n_tokens <= 512:
        return "medium"
    return "long"


def compute_prompt_suite_descriptor(
    suite: list[tuple[str, str]] | None = None,
) -> dict:
    """Hash-only descriptor of a fixed prompt suite (no raw prompt text in
    tracked summaries). Used to confirm two checkpoints saw the same prompts.
    """
    items_in = suite if suite is not None else DEFAULT_PROMPT_SUITE
    items: list[dict] = []
    h = hashlib.sha256()
    h.update(PROMPT_SUITE_ID.encode("utf-8"))
    h.update(b"\n")
    for pid, ptext in items_in:
        ptext_nfc = unicodedata.normalize("NFC", ptext)
        psha = _sha256_text(ptext_nfc)
        diacritics = metrics_mod.count_hawaiian_diacritics(ptext_nfc)
        items.append(
            {
                "id": pid,
                "prompt_sha256": psha,
                "prompt_len_chars": len(ptext_nfc),
                "prompt_diacritics": diacritics,
                "diacritic_density_bin": metrics_mod.diacritic_density_bin(
                    diacritics
                ),
            }
        )
        h.update(pid.encode("utf-8"))
        h.update(b"\t")
        h.update(psha.encode("utf-8"))
        h.update(b"\n")
    return {
        "suite_id": PROMPT_SUITE_ID,
        "suite_sha256": h.hexdigest(),
        "items": items,
    }


def load_checkpoint(checkpoint_dir: str):
    """Load a (possibly LoRA-adapter) checkpoint + its tokenizer."""
    transformers = _require("transformers", "pip install transformers")
    peft = _require("peft", "pip install peft")
    torch = _require("torch", "pip install torch")

    tokenizer = transformers.AutoTokenizer.from_pretrained(checkpoint_dir, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model_kwargs = {"dtype": torch.float16}
    if torch.cuda.is_available():
        model_kwargs["device_map"] = "auto"

    # If the checkpoint contains a peft adapter, load it on top of its
    # recorded base model. Otherwise treat it as a plain causal LM.
    adapter_cfg_path = Path(checkpoint_dir) / "adapter_config.json"
    if adapter_cfg_path.exists():
        with adapter_cfg_path.open("r", encoding="utf-8") as f:
            adapter_cfg = json.load(f)
        base_id = adapter_cfg["base_model_name_or_path"]
        base = transformers.AutoModelForCausalLM.from_pretrained(base_id, **model_kwargs)
        model = peft.PeftModel.from_pretrained(base, checkpoint_dir)
    else:
        model = transformers.AutoModelForCausalLM.from_pretrained(
            checkpoint_dir, **model_kwargs
        )
    model.eval()
    return model, tokenizer


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_eval_set_metadata(
    tokenizer,
    eval_file: str,
    max_length: int = 1024,
) -> dict:
    """Tokenize-once pass over the eval JSONL to capture slice metadata
    for drift comparison: counts, token counts, length bins, diacritic
    density bins, and any source/register fields present on records.

    Raw record text is NOT returned; only counts and bins.
    """
    from .data import iter_jsonl, normalize_text

    record_count = 0
    scored_record_count = 0
    total_tokens = 0
    length_bin_counts: dict[str, int] = {"short": 0, "medium": 0, "long": 0}
    density_bin_counts: dict[str, int] = {
        "none": 0,
        "low": 0,
        "medium": 0,
        "high": 0,
    }
    source_counts: dict[str, int] = {}
    register_counts: dict[str, int] = {}
    total_chars = 0

    for ex in iter_jsonl(eval_file):
        record_count += 1
        text = normalize_text(ex.get("text", ""), form="NFC")
        if not text:
            continue
        scored_record_count += 1
        ids = tokenizer(text, truncation=True, max_length=max_length)["input_ids"]
        n_tokens = len(ids)
        total_tokens += n_tokens
        total_chars += len(text)
        length_bin_counts[_length_bin_from_tokens(n_tokens)] += 1
        bin_name = metrics_mod.diacritic_density_bin(
            metrics_mod.count_hawaiian_diacritics(text)
        )
        density_bin_counts[bin_name] = density_bin_counts.get(bin_name, 0) + 1
        src = ex.get("source")
        if src is not None:
            source_counts[str(src)] = source_counts.get(str(src), 0) + 1
        reg = ex.get("register")
        if reg is not None:
            register_counts[str(reg)] = register_counts.get(str(reg), 0) + 1

    meta: dict[str, Any] = {
        "path": str(eval_file),
        "sha256": _sha256_file(Path(eval_file)),
        "record_count": record_count,
        "scored_record_count": scored_record_count,
        "total_tokens": total_tokens,
        "total_chars": total_chars,
        "length_bin_counts_tokens": length_bin_counts,
        "diacritic_density_bin_counts": density_bin_counts,
        "max_length_used": max_length,
    }
    if source_counts:
        meta["source_counts"] = source_counts
    else:
        meta["source_counts"] = {"status": "field_absent"}
    if register_counts:
        meta["register_counts"] = register_counts
    else:
        meta["register_counts"] = {"status": "field_absent"}
    return meta


def perplexity(model, tokenizer, eval_file: str, max_length: int = 1024) -> float:
    """Token-weighted perplexity on a Hawaiian held-out JSONL.

    TODO(slicing): The eval pipeline doc requires per-source/register
    slicing (docs/eval_pipeline.md §5). Start with the global number,
    then add slices once the JSONL records carry a `source` field.
    """
    torch = _require("torch", "pip install torch")
    from .data import iter_jsonl, normalize_text

    total_loss = 0.0
    total_tokens = 0
    device = next(model.parameters()).device

    with torch.no_grad():
        for idx, ex in enumerate(iter_jsonl(eval_file), start=1):
            text = normalize_text(ex.get("text", ""), form="NFC")
            if not text:
                continue
            enc = tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=max_length,
            )
            input_ids = enc["input_ids"].to(device)
            labels = input_ids.clone()
            out = model(input_ids=input_ids, labels=labels)
            n_tokens = int(input_ids.numel())
            total_loss += float(out.loss) * n_tokens
            total_tokens += n_tokens
            if idx == 1 or idx % 25 == 0:
                print(
                    f"[eval] scored {idx} records ({total_tokens} tokens)",
                    file=sys.stderr,
                    flush=True,
                )

    if total_tokens == 0:
        raise ValueError(f"No eval tokens scored from {eval_file}")
    return math.exp(total_loss / total_tokens)


def sample_generations(
    model,
    tokenizer,
    prompts: list[str],
    max_new_tokens: int = 64,
) -> list[str]:
    """Greedy generations for a small list of prompts."""
    torch = _require("torch", "pip install torch")
    device = next(model.parameters()).device
    outputs: list[str] = []
    with torch.no_grad():
        for p in prompts:
            enc = tokenizer(p, return_tensors="pt").to(device)
            gen = model.generate(
                **enc,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id,
            )
            outputs.append(tokenizer.decode(gen[0], skip_special_tokens=True))
    return outputs


def _model_identity(model, tokenizer, checkpoint_dir: str) -> dict:
    """Best-effort identity capture for fair cross-checkpoint comparison.

    Pulls dtype, device, device_map, quantization-ish config, tokenizer
    name/class/vocab size, model class, and library versions. Failures
    inside this helper must never break eval — fall back to "unknown".
    """
    info: dict[str, Any] = {"checkpoint": checkpoint_dir}
    try:
        torch = __import__("torch")
        info["torch_version"] = getattr(torch, "__version__", "unknown")
        info["cuda_available"] = bool(torch.cuda.is_available())
    except Exception:
        info["torch_version"] = "unknown"
        info["cuda_available"] = False
    try:
        transformers = __import__("transformers")
        info["transformers_version"] = getattr(
            transformers, "__version__", "unknown"
        )
    except Exception:
        info["transformers_version"] = "unknown"

    try:
        info["model_class"] = type(model).__name__
    except Exception:
        info["model_class"] = "unknown"
    try:
        first_param = next(model.parameters())
        info["model_dtype"] = str(first_param.dtype)
        info["model_device"] = str(first_param.device)
    except Exception:
        info["model_dtype"] = "unknown"
        info["model_device"] = "unknown"

    # peft adapter detection
    adapter_cfg_path = Path(checkpoint_dir) / "adapter_config.json"
    if adapter_cfg_path.exists():
        info["is_adapter"] = True
        try:
            with adapter_cfg_path.open("r", encoding="utf-8") as f:
                ad = json.load(f)
            info["base_model"] = ad.get("base_model_name_or_path")
        except Exception:
            info["base_model"] = "unknown"
    else:
        info["is_adapter"] = False
        info["base_model"] = checkpoint_dir

    # device_map (if peft/transformers exposed it)
    base = getattr(model, "base_model", None)
    target = base if base is not None else model
    info["device_map"] = str(getattr(target, "hf_device_map", "single_device"))

    # quantization-ish config
    qc = None
    try:
        cfg = getattr(target, "config", None)
        qc_raw = getattr(cfg, "quantization_config", None)
        if qc_raw is not None:
            qc = (
                qc_raw.to_dict()
                if hasattr(qc_raw, "to_dict")
                else dict(getattr(qc_raw, "__dict__", {}))
            )
    except Exception:
        qc = None
    info["quantization_config"] = qc if qc is not None else {"status": "absent"}

    # tokenizer identity
    try:
        info["tokenizer_class"] = type(tokenizer).__name__
        info["tokenizer_name_or_path"] = getattr(
            tokenizer, "name_or_path", "unknown"
        )
        info["tokenizer_vocab_size"] = int(getattr(tokenizer, "vocab_size", 0))
    except Exception:
        info["tokenizer_class"] = "unknown"
        info["tokenizer_name_or_path"] = "unknown"
        info["tokenizer_vocab_size"] = 0

    return info


def _orthography_aggregate(
    orth_per_sample: dict[str, dict],
    suite_descriptor: dict | None,
) -> dict:
    """Aggregate orthography signals + tripwires across the prompt suite.

    No raw text consumed here — only the per-sample dicts produced by
    `metrics.orthography_report` plus the suite descriptor (for
    high-density prompt detection).
    """
    n = len(orth_per_sample)
    okina_total = 0
    wrong_okina_total = 0
    kahako_total = 0
    combining_macron_total = 0
    nfc_failures = 0
    bin_counts: dict[str, int] = {}
    for r in orth_per_sample.values():
        okina_total += int(r.get("okina", 0))
        wrong_okina_total += int(r.get("wrong_okina", 0))
        kahako_total += int(r.get("kahako", 0))
        combining_macron_total += int(r.get("combining_macron", 0))
        if not r.get("is_nfc", True):
            nfc_failures += 1
        b = r.get("diacritic_density_bin", "none")
        bin_counts[b] = bin_counts.get(b, 0) + 1

    # Kahakō collapse on high-diacritic prompts: prompt was high-density,
    # generation contains zero kahakō. Indexed by suite item position.
    kahako_collapse_high_density = 0
    if suite_descriptor is not None:
        items = suite_descriptor.get("items", [])
        for i, item in enumerate(items):
            if item.get("diacritic_density_bin") != "high":
                continue
            key = f"sample_{i}"
            r = orth_per_sample.get(key)
            if r is None:
                continue
            if int(r.get("kahako", 0)) == 0:
                kahako_collapse_high_density += 1

    return {
        "n": n,
        "okina_total": okina_total,
        "wrong_okina_total": wrong_okina_total,
        "kahako_total": kahako_total,
        "combining_macron_total": combining_macron_total,
        "nfc_failures": nfc_failures,
        "diacritic_density_bin_counts": bin_counts,
        "kahako_collapse_on_high_diacritic": kahako_collapse_high_density,
    }


def _tripwires(
    orth_aggregate: dict,
    suite_descriptor: dict,
    generation_count: int,
) -> dict:
    return {
        "wrong_okina_nonzero": orth_aggregate.get("wrong_okina_total", 0) > 0,
        "nfc_failures": orth_aggregate.get("nfc_failures", 0),
        "combining_macron_nonzero": orth_aggregate.get("combining_macron_total", 0)
        > 0,
        "kahako_collapse_on_high_diacritic": orth_aggregate.get(
            "kahako_collapse_on_high_diacritic", 0
        ),
        "generation_count": generation_count,
        "prompt_suite_sha256": suite_descriptor.get("suite_sha256"),
        "prompt_suite_id": suite_descriptor.get("suite_id"),
    }


def evaluate_checkpoint(
    checkpoint_dir: str,
    eval_file: str | None,
    prompts: list[str] | None = None,
    *,
    use_prompt_suite: bool = True,
    max_length: int = 1024,
    max_new_tokens: int = 64,
) -> dict:
    """Run PPL + generation + Hawaiian text checks. Returns a dict.

    The shape is intentionally compatible with (a subset of) the
    run-report schema in docs/eval_pipeline.md §8 *plus* the Stage 0
    drift bundle (eval-set slice metadata, prompt-suite descriptor,
    orthography aggregate, tripwires).
    """
    model, tokenizer = load_checkpoint(checkpoint_dir)
    report: dict = {
        "schema_version": EVAL_SCHEMA_VERSION,
        "checkpoint": checkpoint_dir,
    }
    report["identity"] = _model_identity(model, tokenizer, checkpoint_dir)
    report["decoding"] = {
        "do_sample": False,
        "max_new_tokens": max_new_tokens,
        "temperature": None,
        "top_p": None,
        "greedy": True,
    }
    report["ppl_config"] = {"max_length": max_length}

    # Probes that need their own harness — surface them as explicit
    # placeholders so summaries don't silently lose the field.
    report["english_ppl"] = {
        "status": "not_configured",
        "reason": "english held-out PPL harness not wired (eval_pipeline.md §3.2)",
    }
    report["manual_w1"] = {
        "status": "not_configured",
        "reason": "W1 manual micro-eval loader not wired (data-sources/manual-eval/README.md)",
    }

    if eval_file:
        try:
            report["eval_set"] = collect_eval_set_metadata(
                tokenizer, eval_file, max_length=max_length
            )
        except Exception as e:  # pragma: no cover - defensive
            report["eval_set"] = {
                "path": str(eval_file),
                "status": "metadata_failed",
                "error": str(e),
            }
        report["hawaiian_ppl"] = perplexity(
            model, tokenizer, eval_file, max_length=max_length
        )
        # Per-source slice PPL is still TODO (see perplexity()); record an
        # explicit placeholder so downstream summary diff doesn't break.
        report["hawaiian_ppl_by_source"] = {
            "status": "not_configured",
            "reason": "per-source slicing TODO (evaluate.py:perplexity)",
        }
    else:
        # Keep `hawaiian_ppl` shape consistent with the other probes: emit
        # an explicit status object instead of a bare null/absent value, so
        # summary diffs don't silently swallow a missing eval file.
        report["hawaiian_ppl"] = {
            "status": "not_configured",
            "reason": "no --eval-file provided; held-out PPL not run",
        }

    # Prompt assembly: prefer explicit --prompt(s); otherwise use the
    # built-in suite if enabled. Backwards compatible: if --prompt is
    # given, behavior matches the legacy CLI exactly.
    suite_used: list[tuple[str, str]] | None = None
    if prompts:
        prompts_to_run = list(prompts)
        prompt_ids = [f"user_{i}" for i in range(len(prompts_to_run))]
    elif use_prompt_suite:
        suite_used = list(DEFAULT_PROMPT_SUITE)
        prompt_ids = [pid for pid, _ in suite_used]
        prompts_to_run = [ptext for _, ptext in suite_used]
    else:
        prompts_to_run = []
        prompt_ids = []

    if prompts_to_run:
        # Always record a hash-only descriptor of *what was asked*, even
        # for ad-hoc --prompt invocations, so checkpoints can be compared
        # without leaking raw prompt text to tracked summaries.
        descriptor_input = (
            suite_used
            if suite_used is not None
            else list(zip(prompt_ids, prompts_to_run))
        )
        suite_descriptor = compute_prompt_suite_descriptor(descriptor_input)
        report["prompt_suite"] = suite_descriptor

        gens = sample_generations(
            model, tokenizer, prompts_to_run, max_new_tokens=max_new_tokens
        )
        report["generations"] = gens
        report["generation_sha256"] = {
            f"sample_{i}": _sha256_text(g) for i, g in enumerate(gens)
        }
        # Pure-Python checks — no ML deps needed.
        orth = {
            f"sample_{i}": metrics_mod.orthography_report(g)
            for i, g in enumerate(gens)
        }
        report["orthography_metrics"] = orth
        report["orthography_aggregate"] = _orthography_aggregate(
            orth, suite_descriptor
        )
        report["tripwires"] = _tripwires(
            report["orthography_aggregate"],
            suite_descriptor,
            generation_count=len(gens),
        )
    return report


# ---------------- TODOs for the learner ----------------
#
# TODO(stage2-chrf): For Stage 2 translation eval, add chrF/chrF++ by
#   direction (en→haw and haw→en, never averaged). Use sacrebleu.
#
# TODO(leakage-check): Recompute the SHA-256 of every eval reference in
#   NFC and assert none appear in the training shards. See
#   docs/eval_pipeline.md §3.4.
#
# TODO(run-report): Promote this dict to the full run-report schema and
#   write it next to the checkpoint as `run_report.json`.


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hawaiian LLM eval (skeleton).")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--eval-file", default=None, help="JSONL with a 'text' field.")
    parser.add_argument(
        "--prompt",
        action="append",
        default=None,
        help="Prompt(s) to generate from. Repeatable. Disables built-in suite.",
    )
    parser.add_argument(
        "--no-prompt-suite",
        action="store_true",
        help="Skip the built-in fixed prompt suite when no --prompt is given.",
    )
    parser.add_argument(
        "--max-length",
        type=int,
        default=1024,
        help="Max tokens for held-out PPL scoring.",
    )
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=64,
        help="Max new tokens for generation.",
    )
    ns = parser.parse_args(argv)

    report = evaluate_checkpoint(
        ns.checkpoint,
        eval_file=ns.eval_file,
        prompts=ns.prompt,
        use_prompt_suite=not ns.no_prompt_suite,
        max_length=ns.max_length,
        max_new_tokens=ns.max_new_tokens,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
