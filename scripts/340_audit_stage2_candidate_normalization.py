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
INVISIBLE_FORMAT_CONTROLS = str.maketrans("", "", "\u00ad\u200b\u200c\u200d\ufeff")
NON_ASCII_WHITESPACE = {"\u00a0", "\u1680", "\u2000", "\u2001", "\u2002", "\u2003", "\u2004", "\u2005", "\u2006", "\u2007", "\u2008", "\u2009", "\u200a", "\u2028", "\u2029", "\u202f", "\u205f", "\u3000"}
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
from llm_hawaii import eval_contamination  # noqa: E402
from llm_hawaii.stage2_dedup import (  # noqa: E402
    EXACT_SIDE_MAX_PER_KEY,
    NEAR_DUPE_THRESHOLD,
    cap_exact_en,
    cap_exact_haw,
    collapse_near_dupes,
    collapse_pair_hash_duplicates,
    near_duplicate_groups,
)


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def normalize_haw(text: str) -> str:
    return nfc(text).translate(OKINA_FOLD)


def normalize_en_for_dedup_key(text: str) -> str:
    return nfc(text).translate(INVISIBLE_FORMAT_CONTROLS)


def normalize_haw_for_dedup_key(text: str) -> str:
    return normalize_haw(text).translate(INVISIBLE_FORMAT_CONTROLS)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def text_key(text: str, *, haw: bool) -> str:
    text = normalize_haw_for_dedup_key(text) if haw else normalize_en_for_dedup_key(text)
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
        paths = [Path(p).resolve() for p in args.candidates]
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


def _load_eval_contamination_hashes(paths: list[Path]) -> eval_contamination.EvalHashSet:
    hashes = eval_contamination.EvalHashSet()
    for path in paths:
        loaded = eval_contamination.load_eval_hashes(path)
        hashes.update(loaded)
        hashes.bible_overlap_side_hashes.update(getattr(loaded, "bible_overlap_side_hashes", set()))
    return hashes


def audit(
    paths: list[Path],
    *,
    max_examples: int = 8,
    eval_hashes: set[str] | None = None,
    eval_hash_paths: list[Path] | None = None,
) -> dict[str, Any]:
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
    invisible_format_control_rows = 0
    non_ascii_whitespace_rows = 0
    examples: dict[str, list[dict[str, Any]]] = defaultdict(list)

    raw_pair_index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    pair_index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    dedup_rows: list[dict[str, Any]] = []
    en_index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    haw_index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    en_text_index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    contamination_by_source: Counter[str] = Counter()
    contamination_by_match_type: Counter[str] = Counter({"full_pair": 0, "single_side_haw": 0, "single_side_en": 0})
    contamination_rows: list[dict[str, Any]] = []

    for path in paths:
        file_count = 0
        for line_no, row in read_jsonl(path):
            file_count += 1
            loc = {"file": str(path.relative_to(REPO_ROOT)), "line": line_no, "pair_id": row.get("pair_id") or row.get("source_pair_id")}
            source = row.get("source") or row.get("source_id") or "<missing>"
            counts_by_source[source] += 1

            if eval_hashes is not None:
                match_type = eval_contamination.contamination_match_type(row, eval_hashes)
                if match_type is not None:
                    contamination_by_source[str(source)] += 1
                    contamination_by_match_type[match_type] += 1
                    contamination_rows.append({
                        **loc,
                        "source": source,
                        "match_type": match_type,
                    })

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
            joined_text = "".join(x for x in (en, haw) if isinstance(x, str))
            if any(ch in joined_text for ch in "\u00ad\u200b\u200c\u200d\ufeff"):
                invisible_format_control_rows += 1
                if len(examples["invisible_format_control_rows"]) < max_examples:
                    examples["invisible_format_control_rows"].append(loc)
            if any(ch in joined_text for ch in NON_ASCII_WHITESPACE):
                non_ascii_whitespace_rows += 1
                if len(examples["non_ascii_whitespace_rows"]) < max_examples:
                    examples["non_ascii_whitespace_rows"].append(loc)
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
                row_for_dupes = {
                    **loc,
                    "source": source,
                    "sha256_en_clean": en_hash,
                    "sha256_haw_clean": haw_hash,
                    "sha256_pair": expected_pair,
                    "text_en": en,
                    "text_haw": haw,
                }
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

    def exact_side_report(candidate_rows: list[dict[str, Any]], *, key_name: str, other_key: str) -> dict[str, Any]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in candidate_rows:
            key = row.get(key_name)
            if isinstance(key, str) and key:
                grouped[key].append(row)
        dup_groups = [g for g in grouped.values() if len(g) > 1 and len({r.get(other_key) for r in g}) > 1]
        source_rows: Counter[str] = Counter()
        source_groups: Counter[str] = Counter()
        size_hist: Counter[str] = Counter()
        examples_out: list[dict[str, Any]] = []
        for group in dup_groups:
            size_hist[str(len(group))] += 1
            sources = {str(r.get("source") or "<missing>") for r in group}
            for source in sources:
                source_groups[source] += 1
            for row in group:
                source_rows[str(row.get("source") or "<missing>")] += 1
            if len(examples_out) < max_examples:
                examples_out.append({
                    "group_size": len(group),
                    "sources": sorted(sources),
                    "examples": [
                        {k: row.get(k) for k in ("file", "line", "pair_id", "source")}
                        for row in group[:max_examples]
                    ],
                })
        return {
            "groups": len(dup_groups),
            "rows_in_groups": sum(len(g) for g in dup_groups),
            "group_size_histogram": dict(size_hist),
            "top_sources_by_rows": dict(source_rows.most_common(12)),
            "top_sources_by_groups": dict(source_groups.most_common(12)),
            "examples": examples_out,
        }

    def near_report(candidate_rows: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
        idx_groups = near_duplicate_groups(candidate_rows, threshold=threshold)
        source_rows: Counter[str] = Counter()
        source_groups: Counter[str] = Counter()
        size_hist: Counter[str] = Counter()
        examples_out: list[dict[str, Any]] = []
        for group in idx_groups:
            size_hist[str(len(group))] += 1
            sources = {str(candidate_rows[idx].get("source") or "<missing>") for idx in group}
            for source in sources:
                source_groups[source] += 1
            for idx in group:
                source_rows[str(candidate_rows[idx].get("source") or "<missing>")] += 1
            if len(examples_out) < max_examples:
                examples_out.append({
                    "group_size": len(group),
                    "sources": sorted(sources),
                    "examples": [
                        {k: candidate_rows[idx].get(k) for k in ("file", "line", "pair_id", "source")}
                        for idx in group[:max_examples]
                    ],
                })
        return {
            "threshold": threshold,
            "groups": len(idx_groups),
            "rows_in_groups": sum(len(g) for g in idx_groups),
            "group_size_histogram": dict(size_hist),
            "top_sources_by_rows": dict(source_rows.most_common(12)),
            "top_sources_by_groups": dict(source_groups.most_common(12)),
            "examples": examples_out,
        }

    raw_exact_pair_groups = cross_source_groups(raw_pair_index)
    deduped_rows, cross_source_dedup = collapse_pair_hash_duplicates(dedup_rows)
    en_capped_rows, exact_en_cap = cap_exact_en(deduped_rows, max_per_key=EXACT_SIDE_MAX_PER_KEY)
    haw_capped_rows, exact_haw_cap = cap_exact_haw(en_capped_rows, max_per_key=EXACT_SIDE_MAX_PER_KEY)
    post_policy_rows, near_dupe_collapse = collapse_near_dupes(haw_capped_rows, threshold=NEAR_DUPE_THRESHOLD)
    for row in post_policy_rows:
        key = row.get("sha256_pair")
        if isinstance(key, str) and key:
            pair_index[key].append({k: row.get(k) for k in ("file", "line", "pair_id", "source")})

    exact_pair_groups = cross_source_groups(pair_index)
    exact_en_groups = cross_source_groups(en_index)
    exact_haw_groups = cross_source_groups(haw_index)
    exact_en_only = exact_side_report(deduped_rows, key_name="sha256_en_clean", other_key="sha256_haw_clean")
    exact_haw_only = exact_side_report(deduped_rows, key_name="sha256_haw_clean", other_key="sha256_en_clean")
    post_policy_exact_en_only = exact_side_report(post_policy_rows, key_name="sha256_en_clean", other_key="sha256_haw_clean")
    post_policy_exact_haw_only = exact_side_report(post_policy_rows, key_name="sha256_haw_clean", other_key="sha256_en_clean")
    near_duplicate_report = near_report(deduped_rows, NEAR_DUPE_THRESHOLD)
    post_policy_near_duplicate_report = near_report(post_policy_rows, NEAR_DUPE_THRESHOLD)

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

    contamination_report = {
        "enabled": eval_hashes is not None,
        "ledger_path": None if eval_hash_paths is None else ([str(p) for p in eval_hash_paths] if len(eval_hash_paths) != 1 else str(eval_hash_paths[0])),
        "ledger_size": 0 if eval_hashes is None else len(eval_hashes),
        "total_matches": len(contamination_rows),
        "by_source": dict(contamination_by_source),
        "by_match_type": dict(contamination_by_match_type),
        "row_ids": [r.get("pair_id") for r in contamination_rows],
        "rows": contamination_rows[:max_examples],
        "error": "candidate contamination found" if contamination_rows else None,
    }

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
            "invisible_format_control_rows": invisible_format_control_rows,
            "non_ascii_whitespace_rows": non_ascii_whitespace_rows,
        },
        "hash_mismatches_if_haw_okina_canonicalized": dict(hash_mismatches),
        "schema": {
            "raw_violation_count": sum(raw_schema_violations.values()),
            "raw_violation_types": dict(raw_schema_violations),
            "post_policy_violation_count": sum(post_policy_schema_violations.values()),
            "post_policy_violation_types": dict(post_policy_schema_violations),
        },
        "contamination": contamination_report,
        "duplicates": {
            "cross_source_exact_pair_hash_groups": len(exact_pair_groups),
            "raw_cross_source_exact_pair_hash_groups": len(raw_exact_pair_groups),
            "cross_source_pair_dedup": cross_source_dedup,
            "cross_source_exact_en_hash_groups": len(exact_en_groups),
            "cross_source_exact_haw_hash_groups": len(exact_haw_groups),
            "exact_en_only_duplicate_groups": exact_en_only,
            "exact_haw_only_duplicate_groups": exact_haw_only,
            "near_duplicate_groups": near_duplicate_report,
            "post_policy_exact_en_only_duplicate_groups": post_policy_exact_en_only,
            "post_policy_exact_haw_only_duplicate_groups": post_policy_exact_haw_only,
            "post_policy_near_duplicate_groups": post_policy_near_duplicate_report,
            "exact_en_cap": exact_en_cap,
            "exact_haw_cap": exact_haw_cap,
            "near_duplicate_collapse": near_dupe_collapse,
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
    parser.add_argument("--eval-hashes", type=Path, action="append", default=None, help="Eval-hashes JSONL ledger(s) to audit against without dropping rows")
    parser.add_argument("--strict", action="store_true", help="Exit 3 if post-policy schema violations, pair-hash mismatches, or eval contamination are found")
    args = parser.parse_args(argv)

    if args.eval_hashes:
        missing = [p for p in args.eval_hashes if not p.exists()]
        if missing:
            print(f"error: eval-hashes ledger not found: {missing[0]}", file=sys.stderr)
            return 2
        eval_hashes = _load_eval_contamination_hashes(args.eval_hashes)
    else:
        eval_hashes = None

    paths = candidate_paths(args)
    report = audit(paths, max_examples=args.max_examples, eval_hashes=eval_hashes, eval_hash_paths=args.eval_hashes)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))

    if args.strict:
        schema_bad = report["schema"]["post_policy_violation_count"]
        pair_bad = report["hash_mismatches_if_haw_okina_canonicalized"].get("sha256_pair", 0)
        contamination_bad = report["contamination"]["total_matches"]
        if schema_bad or pair_bad or contamination_bad:
            return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
