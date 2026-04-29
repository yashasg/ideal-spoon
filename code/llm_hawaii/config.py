"""Training/eval configuration.

Start here after `metrics.py`.

What to implement/learn in this file:
1. Read every `TrainConfig` field and match it to a training concept.
2. Add new fields only when another file needs them; keep this dataclass
   boring and explicit.
3. Keep smoke defaults small so an accidental run never downloads an 8B model.
4. Put serious choices like Llama-3.1-8B or A100/L40S in JSON configs, not
   hardcoded Python constants.

Deliberately not Hydra/pydantic — the point is for a learner to see every
field in one place.
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class TrainConfig:
    # --- Model / tokenizer ---
    # Smoke-tier default. Swap up to a 7B/8B base only after the
    # tokenizer audit gate (see docs/training-pipeline.md).
    base_model: str = "Qwen/Qwen2.5-0.5B"
    tokenizer_name: Optional[str] = None  # None -> use base_model's tokenizer
    # Unicode normalization is load-bearing for Hawaiian. Pin it.
    unicode_normalization: str = "NFC"

    # --- Data ---
    train_path: str = "examples/train.jsonl.example"
    eval_path: Optional[str] = None
    text_field: str = "text"
    max_seq_len: int = 1024

    # --- LoRA / QLoRA ---
    use_qlora: bool = True              # 4-bit base via bitsandbytes
    lora_rank: int = 32
    lora_alpha: int = 64
    lora_dropout: float = 0.05
    # "all-linear" is a reasonable default for LoRA; narrow it once you
    # know which modules actually matter for your base.
    lora_target_modules: str = "all-linear"

    # --- Optimization ---
    learning_rate: float = 2e-4
    num_train_epochs: float = 1.0
    per_device_train_batch_size: int = 1
    gradient_accumulation_steps: int = 8
    warmup_ratio: float = 0.03
    weight_decay: float = 0.0
    lr_scheduler_type: str = "cosine"
    gradient_checkpointing: bool = True
    bf16: bool = False  # set True on Ampere+; fp16 elsewhere
    fp16: bool = False
    seed: int = 7

    # --- Logging / checkpointing ---
    output_dir: str = "runs/smoke"
    logging_steps: int = 10
    save_steps: int = 200
    eval_steps: Optional[int] = None
    save_total_limit: int = 2

    # --- Stage tagging (see two-stage ADR) ---
    # "stage1-cpt" | "stage2-sft" | "smoke" — purely informational here.
    stage: str = "smoke"

    # --- Run / hardware metadata (informational; config-driven) ---
    # Free-text label for this run, e.g. "llama31-8b-a100-prototype".
    # Used for output dir naming and the run report; no code dispatches on it.
    run_name: Optional[str] = None
    # Free-text label for the target hardware profile, e.g.
    # "a100-40gb-single", "rtx4090-x2", "cpu-smoke". This is NOT enforced
    # in code — it's a hint for humans and the run report. See the
    # generic capability check in `model.py` for the runtime story.
    hardware_profile: Optional[str] = None

    # --- Free-form notes; populated by the run, not by the user ---
    notes: dict = field(default_factory=dict)

    # ---------------- JSON load/save ----------------

    @classmethod
    def from_json(cls, path: str | Path) -> "TrainConfig":
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        # Filter unknown keys with an explicit error rather than silent drop —
        # config typos are a leading cause of "why didn't my flag take effect".
        known = {f.name for f in dataclasses.fields(cls)}
        unknown = set(raw) - known
        if unknown:
            raise ValueError(f"Unknown config keys: {sorted(unknown)}")
        return cls(**raw)

    def to_json(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(dataclasses.asdict(self), f, indent=2, sort_keys=True)


def load_config(path: str | Path) -> TrainConfig:
    """Convenience wrapper used by the CLIs."""
    return TrainConfig.from_json(path)
