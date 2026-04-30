"""Data loading + tokenization hooks for Stage-1 CPT.

What this file is responsible for right now:
1. Read JSONL safely (`iter_jsonl` / `load_jsonl`) and fail loudly on bad data.
2. Normalize text to NFC (`normalize_text`) before tokenization.
3. Tokenize each record for plain causal LM (`tokenize_example`), with
    `labels = input_ids`.
4. Build a simple train dataset (`build_train_dataset`) and collator
    (`make_collator`) that work on CPU for smoke tests.

What this file is *not* responsible for yet:
- Stage-2 prompt/response masking logic.
- Packing/chunking optimizations.
- Tokenizer-efficiency analytics.

Quick local validation flow:
- Load a small JSONL (for example `code/examples/train.jsonl.example`).
- Tokenize one sample and inspect `input_ids`, `attention_mask`, `labels`.
- Build the dataset and verify it is non-empty and each row has those keys.

Expected input format (current Stage-1 path):
- JSONL, one object per line.
- Each object has a text field (default `text`, configurable with `text_field`).

This module deliberately lazy-imports optional dependencies (for example
`transformers`) so this file can still be imported in environments that only
run data/Unicode unit tests.
"""

from __future__ import annotations

import gzip
import json
import unicodedata
from contextlib import contextmanager
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

@contextmanager
def _open_jsonl_text(path: Path):
    if path.name.endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            yield f
    else:
        with path.open("r", encoding="utf-8") as f:
            yield f


def iter_jsonl(path: str | Path) -> Iterator[dict]:
    """Yield one parsed JSON object per non-empty line.

    Bad lines raise — silent skips hide corpus problems.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Training file not found: {p}")
    with _open_jsonl_text(p) as f:
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


# ---------------- Next implementation steps ----------------
#
# DO-NOW checklist (keep these changes in Stage-1 scope):
# 1) Add unit tests for:
#    - `iter_jsonl`: missing file, bad JSON, empty-line handling.
#    - `normalize_text`: NFC behavior with combining macron input.
#    - `tokenize_example`: missing `text_field` and labels==input_ids.
# 2) Add a tiny smoke runner (or test) that:
#    - loads `code/examples/train.jsonl.example`,
#    - tokenizes with a small `max_length`,
#    - confirms `build_train_dataset` returns >0 rows.
#
# AFTER Stage-1 is stable, do these in order:
# TODO(packing): Pack many short docs into fixed-length chunks with EOS
#   separators to improve throughput. Keep this as an optional path first.
# TODO(sft-masking): Add Stage-2 prompt/response loss masking by setting
#   prompt label positions to -100.
# TODO(rehearsal): Add a two-source sampler for Hawaiian + English rehearsal
#   at a configured ratio (for example 90/10).
# TODO(contamination-guard): Hash normalized tokenized sequences (NFC SHA-256)
#   and reject collisions with eval ledgers under `data/evals/`.


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
    """Causal-LM collator that handles variable-length pre-tokenized labels.

    tokenize_example() stores labels=input_ids on each record for inspection
    and tests.  DataCollatorForLanguageModeling.pad() tries to tensorize every
    feature key — including labels — *before* creating padded labels, which
    raises ValueError when batch size > 1 and sequences have different lengths.

    Fix: strip pre-existing labels before passing to the HF CLM collator, which
    then creates correct labels (with -100 at padding positions) from the padded
    input_ids.
    """
    transformers = _require("transformers", "pip install transformers")
    _inner = transformers.DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False,
    )

    def _collate(features):
        # Strip pre-tokenized labels so HF CLM collator builds them from
        # padded input_ids (-100 at padding positions).
        stripped = [{k: v for k, v in f.items() if k != "labels"} for f in features]
        return _inner(stripped)

    return _collate
