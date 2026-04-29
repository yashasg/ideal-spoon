"""Training entrypoint.

Implement this file in this order:
1. Run `--print-config` until config parsing is boring.
2. Run the smoke config on one tiny JSONL file and make sure checkpoints save.
3. Add eval-during-train only after the train-only path works.
4. Add resume-from-checkpoint before using short-lived/free GPU providers.
5. Write a small run report at the end; if a run cannot be reproduced, it is
   not useful for the project.

Skeleton uses `transformers.Trainer` because it gives you checkpointing, LR
scheduling, logging, and resume-from-checkpoint for free. Roll your own loop
only after you've felt the pain of doing it the easy way.

Run:

    python -m llm_hawaii.train --config configs/smoke.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .config import TrainConfig, load_config


def _require(pkg: str, install_hint: str) -> Any:
    try:
        return __import__(pkg)
    except ImportError as e:
        raise RuntimeError(
            f"Missing optional dependency '{pkg}'. Install with: {install_hint}"
        ) from e


def build_training_args(cfg: TrainConfig):
    transformers = _require("transformers", "pip install transformers")
    return transformers.TrainingArguments(
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


def run_training(cfg: TrainConfig) -> str:
    """Wire the pieces together and call `Trainer.train()`.

    Returns the output checkpoint dir.
    """
    # Lazy imports — keeps the module importable without ML deps.
    transformers = _require("transformers", "pip install transformers")
    from . import data as data_mod
    from . import model as model_mod

    # 1. Tokenizer + model (LoRA-wrapped, optionally 4-bit).
    model, tokenizer = model_mod.build_model_and_tokenizer(cfg)

    # 2. Dataset + collator.
    train_records = data_mod.build_train_dataset(
        cfg.train_path,
        tokenizer,
        text_field=cfg.text_field,
        max_length=cfg.max_seq_len,
        normalization=cfg.unicode_normalization,
    )
    collator = data_mod.make_collator(tokenizer)

    # 3. TrainingArguments + Trainer.
    args = build_training_args(cfg)
    trainer = transformers.Trainer(
        model=model,
        args=args,
        train_dataset=train_records,
        data_collator=collator,
        tokenizer=tokenizer,
    )

    # 4. Persist the resolved config next to the checkpoints — every run
    #    must be reproducible from its output dir alone.
    out = Path(cfg.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    cfg.to_json(out / "resolved_config.json")

    # 5. Train.
    trainer.train()

    # 6. Save the LoRA adapter (small) + tokenizer.
    trainer.save_model(str(out))
    tokenizer.save_pretrained(str(out))
    return str(out)


# ---------------- TODOs for the learner ----------------
#
# TODO(eval-during-train): Add an eval split + `evaluation_strategy="steps"`
#   so you see Hawaiian held-out PPL during the run, not only after.
#
# TODO(stage2): Swap `Trainer` for `trl.SFTTrainer` (or write your own
#   target-masked collator) when you start the Stage 2 translation SFT.
#
# TODO(run-report): On train end, write a row matching the schema in
#   docs/eval_pipeline.md §8. Without that, the run is not promotable.


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hawaiian LLM training (skeleton).")
    parser.add_argument("--config", required=True, help="Path to a JSON TrainConfig.")
    parser.add_argument(
        "--print-config",
        action="store_true",
        help="Parse config and print it; do not train. Useful for smoke checks.",
    )
    ns = parser.parse_args(argv)

    cfg = load_config(ns.config)
    if ns.print_config:
        import dataclasses
        print(json.dumps(dataclasses.asdict(cfg), indent=2, sort_keys=True))
        return 0

    out = run_training(cfg)
    print(f"Training complete. Artifacts at: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
