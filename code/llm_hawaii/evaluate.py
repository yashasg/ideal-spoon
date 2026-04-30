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

Heavy ML deps are lazy-imported. The file parses without them.

Run:

    python -m llm_hawaii.evaluate \
        --checkpoint runs/smoke \
        --eval-file examples/eval.jsonl.example
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

from . import metrics as metrics_mod


def _require(pkg: str, install_hint: str) -> Any:
    try:
        return __import__(pkg)
    except ImportError as e:
        raise RuntimeError(
            f"Missing optional dependency '{pkg}'. Install with: {install_hint}"
        ) from e


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


def evaluate_checkpoint(
    checkpoint_dir: str,
    eval_file: str | None,
    prompts: list[str] | None = None,
) -> dict:
    """Run PPL + generation + Hawaiian text checks. Returns a dict.

    The shape is intentionally compatible with (a subset of) the
    run-report schema in docs/eval_pipeline.md §8.
    """
    model, tokenizer = load_checkpoint(checkpoint_dir)
    report: dict = {"checkpoint": checkpoint_dir}

    if eval_file:
        report["hawaiian_ppl"] = perplexity(model, tokenizer, eval_file)

    if prompts:
        gens = sample_generations(model, tokenizer, prompts)
        report["generations"] = gens
        # Pure-Python checks — no ML deps needed.
        report["orthography_metrics"] = {
            f"sample_{i}": metrics_mod.orthography_report(g)
            for i, g in enumerate(gens)
        }
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
        help="Prompt(s) to generate from. Repeatable.",
    )
    ns = parser.parse_args(argv)

    report = evaluate_checkpoint(
        ns.checkpoint,
        eval_file=ns.eval_file,
        prompts=ns.prompt,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
