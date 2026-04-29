"""Data loading + tokenization hooks.

Implement this file in this order:
1. Make JSONL loading boring and strict: bad paths or bad JSON should fail.
2. Normalize text to NFC before tokenization; Hawaiian diacritics make this
   load-bearing, not cosmetic.
3. Tokenize one example and inspect `input_ids`, `attention_mask`, and labels.
4. Build the smallest Stage-1 causal-LM dataset first. Do not add Stage-2
   prompt/response masking until plain CLM works.
5. Only after the simple path works, add packing/chunking for efficiency.

Expected input format: JSONL, one example per line, each with at least a
`text` field (configurable). For Stage 2 SFT later, you'll add a parallel-pair
format with prompt/response — leave a TODO for that and focus on the Stage-1
CLM path first.

This module deliberately lazy-imports `transformers` / `datasets`. The file
parses cleanly without them installed; functions that need them will raise a
clear RuntimeError telling you what to install.
"""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator


def _require(pkg: str, install_hint: str) -> Any:
    """Import a package or fail loudly with an install hint.

    No silent fallbacks: if a learner hits this, they should know
    exactly what to install.
    """
    try:
        return __import__(pkg)
    except ImportError as e:
        raise RuntimeError(
            f"Missing optional dependency '{pkg}'. Install with: {install_hint}"
        ) from e


# ---------------- JSONL I/O ----------------

def iter_jsonl(path: str | Path) -> Iterator[dict]:
    """Yield one parsed JSON object per non-empty line.

    Bad lines raise — silent skips hide corpus problems.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Training file not found: {p}")
    with p.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"Bad JSON at {p}:{lineno}: {e}") from e


def load_jsonl(path: str | Path) -> list[dict]:
    return list(iter_jsonl(path))


# ---------------- Normalization ----------------

def normalize_text(text: str, form: str = "NFC") -> str:
    """Pin Unicode normalization. Mixing NFC/NFD silently corrupts training.

    For Hawaiian, NFC is the project default — kahakō are precomposed
    (ā = U+0101, not a + U+0304) and ʻokina is U+02BB. See
    docs/eval_pipeline.md §3.1.
    """
    if form not in {"NFC", "NFD", "NFKC", "NFKD"}:
        raise ValueError(f"Unknown normalization form: {form}")
    return unicodedata.normalize(form, text)


# ---------------- Tokenization ----------------

def load_tokenizer(name: str):
    """Load a HF tokenizer.

    Lazy import so this module parses without `transformers` installed.
    """
    transformers = _require(
        "transformers",
        "pip install transformers",
    )
    tok = transformers.AutoTokenizer.from_pretrained(name, use_fast=True)
    # Causal LMs commonly lack a pad token; reuse EOS so the collator
    # doesn't crash. Don't introduce a *new* token here — that resizes
    # embeddings and is a bigger decision than this skeleton implies.
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    return tok


def tokenize_example(
    example: dict,
    tokenizer,
    text_field: str = "text",
    max_length: int = 1024,
    normalization: str = "NFC",
) -> dict:
    """Tokenize a single record. Returns input_ids/attention_mask/labels.

    Labels are a copy of input_ids for plain causal LM (Stage 1 CPT).
    Stage 2 SFT will mask the prompt portion — that's a TODO below.
    """
    if text_field not in example:
        raise KeyError(f"Example missing field '{text_field}': keys={list(example)}")
    text = normalize_text(example[text_field], form=normalization)
    enc = tokenizer(
        text,
        max_length=max_length,
        truncation=True,
        padding=False,
        return_tensors=None,
    )
    enc["labels"] = list(enc["input_ids"])
    return enc


# ---------------- TODOs for the learner ----------------
#
# TODO(packing): For Stage 1 CPT, packing many short docs into a single
#   max_length sequence (with EOS separators) substantially improves
#   throughput. Look at `trl`'s ConstantLengthDataset or write a small
#   generator that buffers tokenized records and emits fixed-size chunks.
#
# TODO(sft-masking): For Stage 2 SFT (translation), the loss must be
#   masked to *target* tokens only. Tokenize prompt and response
#   separately, concatenate, and set labels for prompt positions to -100
#   so they don't contribute to the loss.
#
# TODO(rehearsal): Stage 1 needs ~5–10% English rehearsal to fight
#   catastrophic forgetting. Implement a simple two-source mixer that
#   samples from a Hawaiian shard and an English shard at a configured
#   ratio.
#
# TODO(contamination-guard): Before training, hash every tokenized
#   sequence (NFC SHA-256) and reject any that match
#   the eval hash ledger under data/evals/. See docs/eval_pipeline.md §3.4.


def build_train_dataset(
    path: str | Path,
    tokenizer,
    text_field: str = "text",
    max_length: int = 1024,
    normalization: str = "NFC",
) -> Iterable[dict]:
    """Eager list of tokenized records. Replace with `datasets.Dataset`
    or a streaming pipeline once the corpus outgrows memory.
    """
    out = []
    for ex in iter_jsonl(path):
        out.append(
            tokenize_example(
                ex,
                tokenizer,
                text_field=text_field,
                max_length=max_length,
                normalization=normalization,
            )
        )
    if not out:
        raise ValueError(f"No training records loaded from {path}")
    return out


def make_collator(tokenizer) -> Callable:
    """Standard causal-LM collator. Pads to the longest in the batch."""
    transformers = _require("transformers", "pip install transformers")
    return transformers.DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False,
    )
