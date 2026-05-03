"""Eval-ledger contamination helpers for Stage-2 candidate filtering.

The canonical ledger key is ``content_sha256`` over normalized text. Hawaiian
normalization maps apostrophe-like ʻokina variants to U+02BB; English maps them
to ASCII apostrophe. All text is NFC-normalized and whitespace-collapsed.
"""
from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Iterable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

OKINA = "\u02bb"
_APOSTROPHE_VARIANTS = ("\u2018", "\u2019", "'", OKINA)
_DELIM = "\u241e"
_PAIR_DELIM = "\u2016"


def normalize_haw(text: str) -> str:
    out = unicodedata.normalize("NFC", text)
    for bad in _APOSTROPHE_VARIANTS:
        out = out.replace(bad, OKINA)
    return " ".join(unicodedata.normalize("NFC", out).split())


def normalize_en(text: str) -> str:
    out = unicodedata.normalize("NFC", text)
    for bad in _APOSTROPHE_VARIANTS:
        out = out.replace(bad, "'")
    return " ".join(unicodedata.normalize("NFC", out).split())


def sha256_text(text: str) -> str:
    return hashlib.sha256(unicodedata.normalize("NFC", text).encode("utf-8")).hexdigest()


def canonical_content(text_pair: Any) -> str:
    """Return canonical text used for eval contamination hashing.

    Accepted inputs:
    - PIQA-style dict with ``prompt`` + ``choices``/``solution0..3`` (HAW side).
    - Stage-2 dict with ``text_haw`` and optional ``text_en``.
    - ``(en, haw)`` tuple/list.
    - A single string (treated as Hawaiian/eval-side text).
    - Any other sequence of strings (treated as Hawaiian/eval-side segments).
    """
    if isinstance(text_pair, Mapping):
        if "prompt" in text_pair:
            choices = text_pair.get("choices")
            if choices is None:
                choices = [text_pair.get(f"solution{i}", "") for i in range(4)]
            return _DELIM.join(normalize_haw(str(x)) for x in [text_pair.get("prompt", ""), *list(choices)])
        haw = text_pair.get("text_haw") or text_pair.get("haw") or text_pair.get("target_text")
        en = text_pair.get("text_en") or text_pair.get("en") or text_pair.get("source_text")
        if en is not None and haw is not None:
            return normalize_en(str(en)) + _PAIR_DELIM + normalize_haw(str(haw))
        if haw is not None:
            return normalize_haw(str(haw))
        if en is not None:
            return normalize_en(str(en))
    if isinstance(text_pair, str):
        return normalize_haw(text_pair)
    if isinstance(text_pair, Sequence) and not isinstance(text_pair, (bytes, bytearray)):
        vals = list(text_pair)
        if len(vals) == 2 and all(isinstance(v, str) for v in vals):
            return normalize_en(vals[0]) + _PAIR_DELIM + normalize_haw(vals[1])
        return _DELIM.join(normalize_haw(str(v)) for v in vals)
    return normalize_haw(str(text_pair))


def canonical_content_sha256(text_pair: Any) -> str:
    return sha256_text(canonical_content(text_pair))


def _candidate_hashes(text_pair: Any) -> set[str]:
    hashes = {canonical_content_sha256(text_pair)}
    if isinstance(text_pair, Mapping):
        haw = text_pair.get("text_haw") or text_pair.get("haw") or text_pair.get("target_text")
        en = text_pair.get("text_en") or text_pair.get("en") or text_pair.get("source_text")
        if haw:
            hashes.add(canonical_content_sha256(str(haw)))
        if en:
            hashes.add(sha256_text(normalize_en(str(en))))
        pair_hash = text_pair.get("sha256_pair")
        if isinstance(pair_hash, str) and pair_hash:
            hashes.add(pair_hash)
        for k in ("sha256_en_clean", "sha256_haw_clean", "content_sha256"):
            v = text_pair.get(k)
            if isinstance(v, str) and v:
                hashes.add(v)
    return hashes


class EvalHashSet(set[str]):
    """Set of full eval hashes plus flagged Bible-overlap side hashes."""

    def __init__(self) -> None:
        super().__init__()
        self.bible_overlap_side_hashes: set[str] = set()


def load_eval_hashes(ledger_path: str | Path) -> EvalHashSet:
    path = Path(ledger_path)
    hashes = EvalHashSet()
    if not path.exists():
        return hashes
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            row_hashes: list[str] = []
            for key in ("content_sha256", "sha256_normalized", "sha256_clean", "sha256_text", "sha256_pair", "sha256_en_clean", "sha256_haw_clean"):
                value = row.get(key)
                if isinstance(value, str) and value:
                    hashes.add(value)
                    row_hashes.append(value)
            if row.get("bible_overlap_candidate") is True:
                hashes.bible_overlap_side_hashes.update(row_hashes)
    return hashes


def _side_hashes(text_pair: Any) -> set[str]:
    hashes: set[str] = set()
    if isinstance(text_pair, Mapping):
        haw = text_pair.get("text_haw") or text_pair.get("haw") or text_pair.get("target_text")
        en = text_pair.get("text_en") or text_pair.get("en") or text_pair.get("source_text")
        if haw:
            hashes.add(canonical_content_sha256(str(haw)))
        if en:
            hashes.add(sha256_text(normalize_en(str(en))))
    return hashes


def is_contaminated(text_pair: Any, eval_hashes: set[str]) -> bool:
    candidate_hashes = _candidate_hashes(text_pair)
    if candidate_hashes & eval_hashes:
        return True
    bible_side_hashes = getattr(eval_hashes, "bible_overlap_side_hashes", set())
    return bool(bible_side_hashes and (_side_hashes(text_pair) & bible_side_hashes))


def filter_candidates(rows_iter: Iterable[dict[str, Any]], eval_hashes: set[str]) -> tuple[Iterator[dict[str, Any]], int]:
    kept: list[dict[str, Any]] = []
    dropped = 0
    for row in rows_iter:
        if is_contaminated(row, eval_hashes):
            dropped += 1
        else:
            kept.append(row)
    return iter(kept), dropped
