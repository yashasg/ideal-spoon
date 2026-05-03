#!/usr/bin/env python3
"""Audit Stage-2 candidate JSONL normalization, schema, and cross-source dupes.

Dry-run only: reads candidate files and prints a compact JSON report. It does
not write under data/ and does not mutate rows.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CANDIDATES = REPO_ROOT / "data" / "stage2" / "candidates"
OKINA_FOLD = str.maketrans({"'": "ʻ", "‘": "ʻ", "’": "ʻ", "`": "ʻ"})
TOKEN_RE = re.compile(r"[\wʻ'-]+", re.UNICODE)


def _load_manifest_builder():
    path = REPO_ROOT / "scripts" / "320_build_stage2_manifest.py"
    spec = importlib.util.spec_from_file_location("stage2_manifest_builder_320", path)
    if not spec or not spec.loader:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


_manifest = _load_manifest_builder()
from llm_hawaii.stage2_dedup import collapse_pair_hash_duplicates  # noqa: E402


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def normalize_haw(text: str) -> str:
    return nfc(text).translate(OKINA_FOLD)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def text_key(text: str, *, haw: bool) -> str:
    text = normalize_haw(text) if haw else nfc(text)
    toks = TOKEN_RE.findall(text.casefold())
    return " ".join(toks)


def token_set(text: str, *, haw: bool) -> set[str]:
    return set(text_key(text, haw=haw).split())


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def candidate_paths(args: argparse.Namespace) -> list[Path]:
    if args.candidates:
        paths = [Path(p) for p in args.candidates]
    else:
        paths = sorted(DEFAULT_CANDIDATES.glob("*.jsonl"))
    return [p for p in paths if p.exists()]


def read_jsonl(path: Path) -> Iterable[tuple[int, dict[str, Any]]]:
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            yield line_no, json.loads(line)


def pair_hash(en_clean_hash: str, haw_clean_hash: str) -> str:
    return _manifest.compute_pair_hash(en_clean_hash, haw_clean_hash)


def audit(paths: list[Path], *, max_examples: int = 8) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    counts_by_file: dict[str, int] = {}
    counts_by_source: Counter[str] = Counter()
    raw_schema_violations: Counter[str] = Counter()
    post_policy_schema_violations: Counter[str] = Counter()
    hash_mismatches: Counter[str] = Counter()
    okina_needs_fold = 0
    haw_non_nfc = 0
    en_non_nfc = 0
    en_apostrophe_rows = 0
    examples: dict[str, list[dict[str, Any]]] = defaultdict(list)

    raw_pair_index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    pair_index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    dedup_rows: list[dict[str, Any]] = []
    en_index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    haw_index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    en_text_index: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for path in paths:
        file_count = 0
        for line_no, row in read_jsonl(path):
            file_count += 1
            loc = {"file": str(path.relative_to(REPO_ROOT)), "line": line_no, "pair_id": row.get("pair_id") or row.get("source_pair_id")}
            source = row.get("source") or row.get("source_id") or "<missing>"
            counts_by_source[source] += 1

            raw_viol = _manifest.validate_row(dict(row))
            for v in raw_viol:
                raw_schema_violations[v] += 1
            if raw_viol and len(examples["raw_schema_violations"]) < max_examples:
                examples["raw_schema_violations"].append({**loc, "violations": raw_viol[:6]})

            scored = dict(row)
            try:
                _manifest.apply_policy(scored)
                post_viol = _manifest.validate_row(scored)
            except Exception as exc:  # defensive: audit must finish all files
                post_viol = [f"policy_exception:{type(exc).__name__}"]
            for v in post_viol:
                post_policy_schema_violations[v] += 1
            if post_viol and len(examples["post_policy_schema_violations"]) < max_examples:
                examples["post_policy_schema_violations"].append({**loc, "violations": post_viol[:6]})

            en = row.get("text_en")
            haw = row.get("text_haw")
            if isinstance(en, str):
                if en != nfc(en):
                    en_non_nfc += 1
                if "'" in en or "’" in en:
                    en_apostrophe_rows += 1
                en_key = text_key(en, haw=False)
                if en_key:
                    en_text_index[en_key].append({**loc, "source": source, "text_en": en, "text_haw": haw})
            if isinstance(haw, str):
                if haw != nfc(haw):
                    haw_non_nfc += 1
                haw_norm = normalize_haw(haw)
                if haw_norm != nfc(haw):
                    okina_needs_fold += 1
                    if len(examples["haw_okina_fold_needed"]) < max_examples:
                        examples["haw_okina_fold_needed"].append(loc)

            if isinstance(en, str) and isinstance(haw, str):
                en_hash = sha256_text(nfc(en))
                haw_hash = sha256_text(normalize_haw(haw))
                expected_pair = pair_hash(en_hash, haw_hash)
                if row.get("sha256_en_clean") and row.get("sha256_en_clean") != en_hash:
                    hash_mismatches["sha256_en_clean"] += 1
                if row.get("sha256_haw_clean") and row.get("sha256_haw_clean") != haw_hash:
                    hash_mismatches["sha256_haw_clean"] += 1
                if row.get("sha256_pair") and row.get("sha256_pair") != expected_pair:
                    hash_mismatches["sha256_pair"] += 1
                    if len(examples["pair_hash_mismatch"]) < max_examples:
                        examples["pair_hash_mismatch"].append(loc)
                row_for_dupes = {**loc, "source": source, "sha256_pair": expected_pair, "text_en": en, "text_haw": haw}
                rows.append({**row_for_dupes, "en_tokens": token_set(en, haw=False), "haw_tokens": token_set(haw, haw=True)})
                dedup_rows.append(row_for_dupes)
                raw_pair_index[expected_pair].append({**loc, "source": source})

            for key, idx in ((row.get("sha256_en_clean"), en_index), (row.get("sha256_haw_clean"), haw_index)):
                if isinstance(key, str) and key:
                    idx[key].append({**loc, "source": source})
        counts_by_file[str(path.relative_to(REPO_ROOT))] = file_count

    def cross_source_groups(index: dict[str, list[dict[str, Any]]]) -> list[list[dict[str, Any]]]:
        groups = []
        for group in index.values():
            if len({g["source"] for g in group}) > 1:
                groups.append(group[:max_examples])
        return groups

    raw_exact_pair_groups = cross_source_groups(raw_pair_index)
    deduped_rows, cross_source_dedup = collapse_pair_hash_duplicates(dedup_rows)
    for row in deduped_rows:
        key = row.get("sha256_pair")
        if isinstance(key, str) and key:
            pair_index[key].append({k: row.get(k) for k in ("file", "line", "pair_id", "source")})

    exact_pair_groups = cross_source_groups(pair_index)
    exact_en_groups = cross_source_groups(en_index)
    exact_haw_groups = cross_source_groups(haw_index)

    near_dupes: list[dict[str, Any]] = []
    for group in en_text_index.values():
        sources = {g["source"] for g in group}
        if len(group) < 2 or len(sources) < 2:
            continue
        for i, a in enumerate(group):
            if len(near_dupes) >= max_examples:
                break
            for b in group[i + 1:]:
                if a["source"] == b["source"]:
                    continue
                haw_a = token_set(a.get("text_haw") or "", haw=True)
                haw_b = token_set(b.get("text_haw") or "", haw=True)
                score = jaccard(haw_a, haw_b)
                if score >= 0.70:
                    near_dupes.append({
                        "a": {k: a[k] for k in ("file", "line", "pair_id", "source")},
                        "b": {k: b[k] for k in ("file", "line", "pair_id", "source")},
                        "basis": "exact-normalized-en + haw-token-jaccard>=0.70",
                        "haw_jaccard": round(score, 3),
                    })
                    break
            if len(near_dupes) >= max_examples:
                break

    return {
        "files_audited": len(paths),
        "rows_audited": sum(counts_by_file.values()),
        "rows_by_file": counts_by_file,
        "rows_by_source": dict(counts_by_source),
        "normalization": {
            "haw_rows_requiring_okina_fold_for_canonical_hash": okina_needs_fold,
            "haw_non_nfc_rows": haw_non_nfc,
            "en_non_nfc_rows": en_non_nfc,
            "en_rows_with_apostrophe_or_right_quote_preserved": en_apostrophe_rows,
        },
        "hash_mismatches_if_haw_okina_canonicalized": dict(hash_mismatches),
        "schema": {
            "raw_violation_count": sum(raw_schema_violations.values()),
            "raw_violation_types": dict(raw_schema_violations),
            "post_policy_violation_count": sum(post_policy_schema_violations.values()),
            "post_policy_violation_types": dict(post_policy_schema_violations),
        },
        "duplicates": {
            "cross_source_exact_pair_hash_groups": len(exact_pair_groups),
            "raw_cross_source_exact_pair_hash_groups": len(raw_exact_pair_groups),
            "cross_source_pair_dedup": cross_source_dedup,
            "cross_source_exact_en_hash_groups": len(exact_en_groups),
            "cross_source_exact_haw_hash_groups": len(exact_haw_groups),
            "near_duplicate_examples": near_dupes,
            "exact_pair_examples": exact_pair_groups[:max_examples],
            "exact_en_examples": exact_en_groups[:max_examples],
            "exact_haw_examples": exact_haw_groups[:max_examples],
        },
        "examples": dict(examples),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", nargs="*", help="Candidate JSONL files; defaults to data/stage2/candidates/*.jsonl")
    parser.add_argument("--max-examples", type=int, default=8)
    parser.add_argument("--strict", action="store_true", help="Exit 3 if post-policy schema violations or pair-hash mismatches are found")
    args = parser.parse_args(argv)

    paths = candidate_paths(args)
    report = audit(paths, max_examples=args.max_examples)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))

    if args.strict:
        schema_bad = report["schema"]["post_policy_violation_count"]
        pair_bad = report["hash_mismatches_if_haw_okina_canonicalized"].get("sha256_pair", 0)
        if schema_bad or pair_bad:
            return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
