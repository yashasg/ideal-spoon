"""Data loading + tokenization hooks for Stage-1 CPT and Stage-2 SFT.

What this file is responsible for right now:
1. Read JSONL safely (`iter_jsonl` / `load_jsonl`) and fail loudly on bad data.
2. Normalize text to NFC (`normalize_text`) before tokenization.
3. Tokenize each record for plain causal LM (`tokenize_example`), with
    `labels = input_ids`.  Stage-1 CPT path.
4. Tokenize prompt+target SFT examples (`tokenize_sft_example`) with
    target-only loss masking: prompt and padding tokens get `labels=-100`;
    target tokens *including EOS* carry the real token-id loss.  Stage-2 path.
5. Build train datasets and collators for both stages.

Quick local validation flow:
- Load a small JSONL (for example `code/examples/train.jsonl.example`).
- Tokenize one sample and inspect `input_ids`, `attention_mask`, `labels`.
- Build the dataset and verify it is non-empty and each row has those keys.

Expected input format (Stage-1 CPT path):
- JSONL, one object per line.
- Each object has a text field (default `text`, configurable with `text_field`).

Expected input format (Stage-2 SFT path):
- JSONL emitted by `scripts/330_emit_stage2_sft_jsonl.py`.
- Each object has `instruction`, `source_text`, and `target_text` fields
  (field names configurable).  Field `loss_mask` must equal `"target_only"`.

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


# ---------------- Stage-2 SFT tokenization ----------------

def tokenize_sft_example(
    example: dict,
    tokenizer,
    instruction_field: str = "instruction",
    source_field: str = "source_text",
    target_field: str = "target_text",
    max_length: int = 1024,
    normalization: str = "NFC",
) -> dict:
    """Tokenize a Stage-2 SFT prompt+target record with target-only loss masking.

    Prompt  = ``{instruction}\\n\\n{source_text}\\n\\n``  (no loss)
    Target  = ``{target_text}<EOS>``                      (loss on every token)

    Labels rule — non-negotiable per Stage-2 ADR:
      * Prompt token positions  → ``-100``  (excluded from cross-entropy loss)
      * Target token positions  → real token id  (included in loss)
      * EOS token               → real token id  (included in loss)
      * Padding (added later)   → ``-100``  (handled by ``make_sft_collator``)

    Prompt and target are tokenized separately with ``add_special_tokens=False``
    to prevent BOS/EOS injection mid-sequence.  EOS is appended explicitly to
    the target.  Truncation is applied to the right of the combined sequence;
    in the extreme case where only prompt tokens fit, all labels are ``-100``
    — a config error (``max_seq_len`` too small) rather than a silent bug.

    Returns a dict with ``input_ids``, ``attention_mask``, ``labels``.
    """
    for f in (instruction_field, source_field, target_field):
        if f not in example:
            raise KeyError(
                f"SFT example missing field '{f}': keys={list(example)}"
            )

    instruction = normalize_text(example[instruction_field], form=normalization)
    source = normalize_text(example[source_field], form=normalization)
    target = normalize_text(example[target_field], form=normalization)

    prompt_text = f"{instruction}\n\n{source}\n\n"

    enc_prompt = tokenizer(
        prompt_text,
        max_length=max_length,
        truncation=True,
        padding=False,
        return_tensors=None,
        add_special_tokens=False,
    )
    enc_target = tokenizer(
        target,
        max_length=max_length,
        truncation=False,
        padding=False,
        return_tensors=None,
        add_special_tokens=False,
    )

    eos_id = getattr(tokenizer, "eos_token_id", None)
    if eos_id is None:
        raise RuntimeError(
            "Tokenizer has no eos_token_id; cannot build SFT target. "
            "Set tokenizer.eos_token_id before calling tokenize_sft_example."
        )

    prompt_ids: list[int] = list(enc_prompt["input_ids"])
    target_ids: list[int] = list(enc_target["input_ids"]) + [eos_id]

    all_ids = (prompt_ids + target_ids)[:max_length]

    # Labels: -100 on prompt/padding; target (incl. EOS) carries loss.
    n_prompt = min(len(prompt_ids), len(all_ids))
    labels = [-100] * n_prompt + all_ids[n_prompt:]

    return {
        "input_ids": all_ids,
        "attention_mask": [1] * len(all_ids),
        "labels": labels,
    }


def build_sft_dataset(
    path: str | Path,
    tokenizer,
    instruction_field: str = "instruction",
    source_field: str = "source_text",
    target_field: str = "target_text",
    max_length: int = 1024,
    normalization: str = "NFC",
) -> list[dict]:
    """Load and tokenize a Stage-2 SFT JSONL with target-only loss masking.

    Returns an eager list of tokenized records.  Replace with a streaming
    pipeline once the corpus outgrows memory.
    """
    out = []
    for ex in iter_jsonl(path):
        out.append(
            tokenize_sft_example(
                ex,
                tokenizer,
                instruction_field=instruction_field,
                source_field=source_field,
                target_field=target_field,
                max_length=max_length,
                normalization=normalization,
            )
        )
    if not out:
        raise ValueError(f"No SFT training records loaded from {path}")
    return out


def make_sft_collator(tokenizer) -> Callable:
    """SFT collator that pads input_ids/attention_mask and pads labels with -100.

    Unlike the Stage-1 CLM collator, SFT labels are pre-computed by
    ``tokenize_sft_example`` (prompt positions are already ``-100``).  This
    collator must *preserve* those labels and only pad new positions — it must
    NOT rebuild labels from input_ids (that would overwrite the prompt mask).

    Padding positions get:
      * ``input_ids``       → ``pad_token_id``
      * ``attention_mask``  → ``0``
      * ``labels``          → ``-100``

    Pure Python; no HF dependency so it is safe on CPU-only environments.
    """
    pad_id: int = getattr(tokenizer, "pad_token_id", None) or 0

    def _collate(features: list[dict]) -> dict:
        max_len = max(len(f["input_ids"]) for f in features)
        batch: dict[str, list] = {"input_ids": [], "attention_mask": [], "labels": []}
        for f in features:
            n = len(f["input_ids"])
            pad = max_len - n
            batch["input_ids"].append(list(f["input_ids"]) + [pad_id] * pad)
            batch["attention_mask"].append(list(f["attention_mask"]) + [0] * pad)
            batch["labels"].append(list(f["labels"]) + [-100] * pad)
        return batch

    return _collate
