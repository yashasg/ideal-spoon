"""Eval-ledger contamination helpers for Stage-2 candidate filtering.

The canonical ledger key is ``content_sha256`` over normalized text. Hawaiian
normalization maps apostrophe-like ʻokina variants to U+02BB; English maps them
to ASCII apostrophe. All text is NFC-normalized and whitespace-collapsed.

End-to-end use:
1. Ingest eval-only sources with their gated ``--execute`` command so rows append
   to ``data/evals/eval_hashes.jsonl``.
2. Build the Stage-2 train manifest with
   ``python scripts/320_build_stage2_manifest.py --execute --eval-hashes data/evals/eval_hashes.jsonl``;
   matching train candidates are dropped before dedup and reported in
   ``data/stage2/contamination_report.json``.
3. Audit candidate inputs with
   ``python scripts/340_audit_stage2_candidate_normalization.py --strict --eval-hashes data/evals/eval_hashes.jsonl``;
   strict mode confirms zero remaining candidate contamination before rebuild.
"""
from __future__ import annotations

import hashlib
import json
import unicodedata
from collections import Counter
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


def _candidate_full_hashes(text_pair: Any) -> set[str]:
    hashes = {canonical_content_sha256(text_pair)}
    if isinstance(text_pair, Mapping):
        for k in ("sha256_pair", "content_sha256"):
            v = text_pair.get(k)
            if isinstance(v, str) and v:
                hashes.add(v)
    return hashes


def _candidate_hashes(text_pair: Any) -> set[str]:
    hashes = set(_candidate_full_hashes(text_pair))
    if isinstance(text_pair, Mapping):
        side_hashes = _side_hashes_by_lang(text_pair)
        hashes.update(side_hashes["haw"])
        hashes.update(side_hashes["en"])
        for k in ("sha256_en_clean", "sha256_haw_clean"):
            v = text_pair.get(k)
            if isinstance(v, str) and v:
                hashes.add(v)
    return hashes


class EvalHashSet(set[str]):
    """Set of eval hashes plus flagged Bible-overlap side hashes."""

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


def _side_hashes_by_lang(text_pair: Any) -> dict[str, set[str]]:
    hashes: dict[str, set[str]] = {"haw": set(), "en": set()}
    if isinstance(text_pair, Mapping):
        haw = text_pair.get("text_haw") or text_pair.get("haw") or text_pair.get("target_text")
        en = text_pair.get("text_en") or text_pair.get("en") or text_pair.get("source_text")
        if haw:
            hashes["haw"].add(canonical_content_sha256(str(haw)))
            v = text_pair.get("sha256_haw_clean")
            if isinstance(v, str) and v:
                hashes["haw"].add(v)
        if en:
            hashes["en"].add(sha256_text(normalize_en(str(en))))
            v = text_pair.get("sha256_en_clean")
            if isinstance(v, str) and v:
                hashes["en"].add(v)
    return hashes


def _side_hashes(text_pair: Any) -> set[str]:
    side_hashes = _side_hashes_by_lang(text_pair)
    return side_hashes["haw"] | side_hashes["en"]


def contamination_match_type(text_pair: Any, eval_hashes: set[str]) -> str | None:
    if _candidate_full_hashes(text_pair) & eval_hashes:
        return "full_pair"
    if not hasattr(eval_hashes, "bible_overlap_side_hashes") and (_candidate_hashes(text_pair) & eval_hashes):
        return "full_pair"
    bible_side_hashes = getattr(eval_hashes, "bible_overlap_side_hashes", set())
    if bible_side_hashes:
        side_hashes = _side_hashes_by_lang(text_pair)
        if side_hashes["haw"] & bible_side_hashes:
            return "single_side_haw"
        if side_hashes["en"] & bible_side_hashes:
            return "single_side_en"
    return None


def is_contaminated(text_pair: Any, eval_hashes: set[str]) -> bool:
    return contamination_match_type(text_pair, eval_hashes) is not None


def contamination_report(rows_iter: Iterable[dict[str, Any]], eval_hashes: set[str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    per_source: Counter[str] = Counter()
    per_match_type: Counter[str] = Counter({"full_pair": 0, "single_side_haw": 0, "single_side_en": 0})
    dropped_rows: list[dict[str, Any]] = []
    for row in rows_iter:
        match_type = contamination_match_type(row, eval_hashes)
        if match_type is None:
            kept.append(row)
            continue
        source = str(row.get("source") or "<unknown>")
        per_source[source] += 1
        per_match_type[match_type] += 1
        dropped_rows.append({
            "pair_id": row.get("pair_id") or row.get("source_pair_id"),
            "source": source,
            "match_type": match_type,
        })
    report = {
        "total_dropped": len(dropped_rows),
        "per_source_dropped": dict(per_source),
        "per_match_type": dict(per_match_type),
        "drop_reasons": {f"contamination:{source}": count for source, count in per_source.items()},
        "dropped_rows": dropped_rows,
    }
    return kept, report


def filter_candidates(rows_iter: Iterable[dict[str, Any]], eval_hashes: set[str]) -> tuple[Iterator[dict[str, Any]], int]:
    kept, report = contamination_report(rows_iter, eval_hashes)
    return iter(kept), int(report["total_dropped"])
