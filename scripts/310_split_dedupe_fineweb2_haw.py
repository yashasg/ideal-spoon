#!/usr/bin/env python3
"""FineWeb-2 ``haw_Latn`` split/dedupe for Stage 1 (Linus, 300-phase).

Takes the official FineWeb-2 ``haw_Latn`` test split (887 rows) and:

1. **Deterministically splits** the official test split into count-exact
   70/30 partitions by seeded stable row ordering:
   - 621 checkpoint/dev eval rows → ``data/evals/fineweb2_haw/dev.jsonl``
   - 266 protected holdout/final rows → ``data/final/fineweb2_haw/holdout.jsonl``

2. **Dedupes** train against the FULL official test split (all 887 rows):
   - Removes exact NFC-normalized ``text`` SHA-256 matches from train.
   - Writes deduplicated train → ``data/stage1/fineweb2_haw/train.jsonl``.

3. **Writes manifest** with row/token/char counts, requested ratio, target
   counts, actual counts, split method, normalization method, seed, input/output
   paths, and invariant checks.

4. **Writes eval hashes** to the canonical prototype JSONL ledger
   ``data/evals/eval_hashes.jsonl`` (one hash per line with metadata). A
   Parquet mirror can be generated later, but JSONL is the source of truth now.

Invariant enforced: ``train ∩ eval_hashes = ∅`` using NFC-normalized SHA-256.

Usage::

    python scripts/310_split_dedupe_fineweb2_haw.py --dry-run
    python scripts/310_split_dedupe_fineweb2_haw.py --execute

Exit codes: 0 success, 2 misuse, 3 processing failure.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import math
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_ID = "fineweb2_haw"
OFFICIAL_TEST_ROWS = 887
DEFAULT_RAW_DIR = Path("data/raw/fineweb2_haw/20260429")
CANONICAL_EVAL_HASH_LEDGER = Path("data/evals/eval_hashes.jsonl")
NORMALIZATION_METHOD = "NFC"
EVAL_HASH_SCHEMA_VERSION = "eval-hashes-jsonl-v1"


def utcnow_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def normalize_for_hash(text: str) -> str:
    """Normalize text before contamination hashing."""
    return unicodedata.normalize(NORMALIZATION_METHOD, text)


def compute_text_hash(text: str) -> str:
    """Compute SHA-256 over UTF-8 bytes of NFC-normalized text."""
    normalized = normalize_for_hash(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def compute_whitespace_tokens(text: str) -> int:
    """Raw whitespace token count."""
    return len(text.split())


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load JSONL file into list of records."""
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"[ERROR] Failed to parse JSON at {display_path(path)}:{line_no}: {e}", file=sys.stderr)
                raise
            if not isinstance(obj, dict):
                raise ValueError(f"{display_path(path)}:{line_no}: expected JSON object")
            records.append(obj)
    return records


def write_jsonl(records: list[dict[str, Any]], path: Path, dry_run: bool) -> None:
    """Write records to JSONL file."""
    if dry_run:
        print(f"[DRY-RUN] Would write {len(records)} records to {display_path(path)}")
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"[WRITE] {len(records)} records → {display_path(path)}")


def write_eval_hash_ledger(
    records: list[dict[str, Any]],
    path: Path,
    *,
    origin: str,
    dry_run: bool,
) -> dict[str, int]:
    """Replace this origin's rows in the canonical ledger while preserving others."""
    existing: list[dict[str, Any]] = []
    if path.exists():
        existing = load_jsonl(path)
    kept = [r for r in existing if r.get("origin") != origin]
    combined = kept + records
    stats = {
        "existing_rows": len(existing),
        "preserved_rows": len(kept),
        "replaced_origin_rows": len(existing) - len(kept),
        "new_origin_rows": len(records),
        "combined_rows": len(combined),
    }
    if dry_run:
        print(
            "[DRY-RUN] Would update "
            f"{display_path(path)}: preserve {stats['preserved_rows']} non-{origin} rows, "
            f"replace {stats['replaced_origin_rows']} {origin} rows, "
            f"write {stats['combined_rows']} total rows"
        )
        return stats
    write_jsonl(combined, path, dry_run=False)
    return stats


def source_row_id(record: dict[str, Any]) -> str:
    """Best stable source row id from FineWeb-2 raw records."""
    for key in ("fineweb2_row_id", "id", "row_id", "doc_id"):
        value = record.get(key)
        if value is not None and str(value) != "":
            return str(value)
    text = record.get("text", "")
    return f"sha256:{compute_text_hash(text)[:16]}"


def enrich_records(records: list[dict[str, Any]], source_split: str) -> list[dict[str, Any]]:
    """Attach stable row ids and normalized text hashes without mutating input records."""
    base_ids = [source_row_id(record) for record in records]
    base_counts = Counter(base_ids)
    enriched: list[dict[str, Any]] = []
    for source_index, (record, base_id) in enumerate(zip(records, base_ids, strict=True)):
        text = record.get("text", "")
        if not isinstance(text, str):
            text = ""
        normalized = normalize_for_hash(text)
        text_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        if base_counts[base_id] == 1:
            stable_id = base_id
        else:
            stable_id = f"{base_id}#source_index={source_index}#sha256={text_hash[:16]}"
        enriched.append(
            {
                "record": record,
                "source_split": source_split,
                "source_index": source_index,
                "source_row_id": base_id,
                "stable_row_id": stable_id,
                "sha256_normalized": text_hash,
                "normalized_char_count": len(normalized),
                "token_count": record.get("raw_whitespace_token_count", compute_whitespace_tokens(text)),
                "has_text": bool(text),
            }
        )
    return enriched


def seeded_order_key(item: dict[str, Any], seed: int) -> str:
    material = f"{seed}:{item['stable_row_id']}:{item['sha256_normalized']}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def target_dev_count(total_rows: int, dev_ratio: float) -> int:
    """Count-exact half-up rounding: 887 * 0.70 = 621."""
    return math.floor((total_rows * dev_ratio) + 0.5)


def compute_stats(records: list[dict[str, Any]]) -> dict[str, int]:
    total_chars = sum(r.get("char_count", len(r.get("text", ""))) for r in records)
    total_tokens = sum(
        r.get("raw_whitespace_token_count", compute_whitespace_tokens(r.get("text", "")))
        for r in records
    )
    return {
        "rows": len(records),
        "chars": int(total_chars),
        "tokens": int(total_tokens),
    }


def build_eval_hash_record(
    item: dict[str, Any],
    *,
    division: str,
    split_name: str,
    order_key: str,
) -> dict[str, Any]:
    record = item["record"]
    return {
        "schema_version": EVAL_HASH_SCHEMA_VERSION,
        "sha256_normalized": item["sha256_normalized"],
        "hash_method": "sha256",
        "normalization_method": NORMALIZATION_METHOD,
        "origin": SOURCE_ID,
        "stage": "eval-only",
        "division": division,
        "split": split_name,
        "source_split": item["source_split"],
        "row_id": item["stable_row_id"],
        "source_row_id": item["source_row_id"],
        "source_index": item["source_index"],
        "stable_order_sha256": order_key,
        "char_count_normalized": item["normalized_char_count"],
        "token_count": item["token_count"],
        "source_url": record.get("source_url") or record.get("url"),
        "cc_dump": record.get("cc_dump") or record.get("dump"),
        "cc_date": record.get("cc_date") or record.get("date"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="FineWeb-2 haw_Latn split/dedupe for Stage 1 (Linus, 300-phase)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry-run: load and process data when present but don't write outputs.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute: write outputs to disk.",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=DEFAULT_RAW_DIR,
        help=f"Path to raw FineWeb-2 data directory (default: {DEFAULT_RAW_DIR}).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Deterministic seed for test split ordering (default: 42).",
    )
    parser.add_argument(
        "--dev-ratio",
        type=float,
        default=0.7,
        help="Requested ratio for dev split (default: 0.7 = 70%%).",
    )
    parser.add_argument(
        "--allow-partial-test",
        action="store_true",
        help=(
            "Allow --execute when test rows differ from the official 887. "
            "Default protects canonical outputs from partial fetches."
        ),
    )

    args = parser.parse_args(argv)

    if not args.dry_run and not args.execute:
        print("[ERROR] Must specify --dry-run or --execute.", file=sys.stderr)
        return 2
    if not (0.0 < args.dev_ratio < 1.0):
        print("[ERROR] --dev-ratio must be between 0 and 1.", file=sys.stderr)
        return 2

    dry_run = args.dry_run or not args.execute
    raw_dir = resolve_repo_path(args.raw_dir)
    seed = args.seed
    dev_ratio = args.dev_ratio
    holdout_ratio = 1.0 - dev_ratio

    train_in = raw_dir / "train.jsonl"
    test_in = raw_dir / "test.jsonl"

    evals_dir = REPO_ROOT / "data" / "evals" / SOURCE_ID
    final_dir = REPO_ROOT / "data" / "final" / SOURCE_ID
    stage1_dir = REPO_ROOT / "data" / "stage1" / SOURCE_ID

    dev_out = evals_dir / "dev.jsonl"
    holdout_out = final_dir / "holdout.jsonl"
    train_out = stage1_dir / "train.jsonl"
    manifest_out = stage1_dir / "split_dedupe_manifest.json"
    eval_hashes_out = resolve_repo_path(CANONICAL_EVAL_HASH_LEDGER)

    missing_inputs = [p for p in (train_in, test_in) if not p.exists()]
    if missing_inputs:
        if dry_run:
            print("[DRY-RUN] Raw FineWeb-2 inputs are not present; no outputs regenerated.")
            for path in missing_inputs:
                print(f"[DRY-RUN] Missing: {display_path(path)}")
            print(
                "[DRY-RUN] Fetch raw train/test first with scripts/205_fetch_fineweb2_haw_raw.py; "
                "then rerun this script with --execute."
            )
            return 0
        for path in missing_inputs:
            print(f"[ERROR] Input file not found: {display_path(path)}", file=sys.stderr)
        return 3

    print("[LOAD] Reading raw FineWeb-2 data...")
    try:
        train_records = load_jsonl(train_in)
        test_records = load_jsonl(test_in)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[ERROR] Failed to load raw data: {exc}", file=sys.stderr)
        return 3

    print(f"[LOAD] Train: {len(train_records)} rows")
    print(f"[LOAD] Test: {len(test_records)} rows")

    official_test_count_ok = len(test_records) == OFFICIAL_TEST_ROWS
    if not official_test_count_ok:
        msg = (
            f"[WARN] Test row count is {len(test_records)}, expected official "
            f"{OFFICIAL_TEST_ROWS}."
        )
        print(msg, file=sys.stderr)
        if args.execute and not args.allow_partial_test:
            print(
                "[ERROR] Refusing to write canonical outputs from a partial/non-official test split. "
                "Use --allow-partial-test only for scratch data.",
                file=sys.stderr,
            )
            return 3

    print(
        f"\n[SPLIT] Splitting test {dev_ratio:.0%}/{holdout_ratio:.0%} "
        f"(dev/holdout) with seed={seed}"
    )
    test_items = enrich_records(test_records, "test")
    for item in test_items:
        item["stable_order_sha256"] = seeded_order_key(item, seed)
    test_ordered = sorted(
        test_items,
        key=lambda item: (
            item["stable_order_sha256"],
            item["stable_row_id"],
            item["sha256_normalized"],
        ),
    )
    dev_target = target_dev_count(len(test_ordered), dev_ratio)
    holdout_target = len(test_ordered) - dev_target
    dev_items = test_ordered[:dev_target]
    holdout_items = test_ordered[dev_target:]
    dev_row_ids = {item["stable_row_id"] for item in dev_items}
    holdout_row_ids = {item["stable_row_id"] for item in holdout_items}
    dev_records = [item["record"] for item in dev_items]
    holdout_records = [item["record"] for item in holdout_items]

    print(f"[SPLIT] Requested dev_ratio: {dev_ratio:.6f}")
    print("[SPLIT] Rounding rule: floor(test_rows * dev_ratio + 0.5)")
    print(f"[SPLIT] Target dev/holdout: {dev_target}/{holdout_target}")
    print(f"[SPLIT] Actual dev/holdout: {len(dev_records)}/{len(holdout_records)}")

    print(f"\n[HASH] Building eval hash set from full test split ({len(test_records)} rows)...")
    eval_hashes: set[str] = set()
    eval_hash_records: list[dict[str, Any]] = []
    eval_empty_text_rows = 0

    for item in test_ordered:
        if not item["has_text"]:
            print(f"[WARN] Empty text in test record: {item['stable_row_id']}", file=sys.stderr)
            eval_empty_text_rows += 1
            continue
        text_hash = item["sha256_normalized"]
        eval_hashes.add(text_hash)
        row_id = item["stable_row_id"]
        if row_id in dev_row_ids:
            division = "evals"
            split_name = "dev"
        elif row_id in holdout_row_ids:
            division = "final"
            split_name = "holdout"
        else:
            print(f"[ERROR] Split membership missing for test row_id={row_id}", file=sys.stderr)
            return 3
        eval_hash_records.append(
            build_eval_hash_record(
                item,
                division=division,
                split_name=split_name,
                order_key=item["stable_order_sha256"],
            )
        )

    print(f"[HASH] Eval hash set size: {len(eval_hashes)}")
    print(f"[HASH] Eval hash records: {len(eval_hash_records)}")

    print("\n[DEDUPE] Deduplicating train against full test split...")
    train_items = enrich_records(train_records, "train")
    train_deduped_items: list[dict[str, Any]] = []
    train_removed_items: list[dict[str, Any]] = []
    train_empty_text_rows = 0

    for item in train_items:
        if not item["has_text"]:
            print(f"[WARN] Empty text in train record: {item['stable_row_id']}", file=sys.stderr)
            train_removed_items.append(item)
            train_empty_text_rows += 1
            continue
        if item["sha256_normalized"] in eval_hashes:
            train_removed_items.append(item)
        else:
            train_deduped_items.append(item)

    train_deduped = [item["record"] for item in train_deduped_items]
    train_removed = [item["record"] for item in train_removed_items]

    train_hashes = {item["sha256_normalized"] for item in train_deduped_items if item["has_text"]}
    train_eval_overlap = train_hashes & eval_hashes
    if train_eval_overlap:
        print(
            f"[ERROR] train ∩ eval_hashes invariant failed: {len(train_eval_overlap)} overlaps",
            file=sys.stderr,
        )
        return 3

    print(f"[DEDUPE] Train before dedupe: {len(train_records)} rows")
    print(f"[DEDUPE] Train after dedupe: {len(train_deduped)} rows")
    print(f"[DEDUPE] Removed: {len(train_removed)} rows")
    print("[DEDUPE] train ∩ eval_hashes = ∅ explicitly verified")

    print("\n[STATS] Computing final stats...")
    dev_stats = compute_stats(dev_records)
    holdout_stats = compute_stats(holdout_records)
    train_stats = compute_stats(train_deduped)
    removed_stats = compute_stats(train_removed)

    print(f"[STATS] Dev: {dev_stats['rows']} rows, {dev_stats['chars']:,} chars, {dev_stats['tokens']:,} tokens")
    print(f"[STATS] Holdout: {holdout_stats['rows']} rows, {holdout_stats['chars']:,} chars, {holdout_stats['tokens']:,} tokens")
    print(f"[STATS] Train (deduped): {train_stats['rows']} rows, {train_stats['chars']:,} chars, {train_stats['tokens']:,} tokens")
    print(f"[STATS] Removed: {removed_stats['rows']} rows, {removed_stats['chars']:,} chars, {removed_stats['tokens']:,} tokens")

    actual_counts = {
        "test": len(test_records),
        "dev": len(dev_records),
        "holdout": len(holdout_records),
        "train_before_dedupe": len(train_records),
        "train_after_dedupe": len(train_deduped),
        "train_removed": len(train_removed),
        "eval_hash_records": len(eval_hash_records),
        "eval_hashes_unique": len(eval_hashes),
    }
    target_counts = {"dev": dev_target, "holdout": holdout_target}
    invariant_checks = {
        "official_test_rows_expected": OFFICIAL_TEST_ROWS,
        "official_test_rows_actual": len(test_records),
        "official_test_rows_match": official_test_count_ok,
        "dev_plus_holdout_equals_test": len(dev_records) + len(holdout_records) == len(test_records),
        "dev_count_matches_target": len(dev_records) == dev_target,
        "holdout_count_matches_target": len(holdout_records) == holdout_target,
        "dev_holdout_row_id_disjoint": not (dev_row_ids & holdout_row_ids),
        "dev_holdout_row_id_union_size": len(dev_row_ids | holdout_row_ids),
        "eval_hash_records_cover_nonempty_test_rows": len(eval_hash_records) == len(test_records) - eval_empty_text_rows,
        "eval_hash_duplicate_count": len(eval_hash_records) - len(eval_hashes),
        "train_eval_hash_intersection_count": len(train_eval_overlap),
        "train_eval_hash_intersection_empty": len(train_eval_overlap) == 0,
        "train_empty_text_rows_removed": train_empty_text_rows,
        "eval_empty_text_rows_skipped": eval_empty_text_rows,
    }

    manifest = {
        "pipeline_stage": "310_split_dedupe_fineweb2_haw",
        "timestamp": utcnow_iso(),
        "source_id": SOURCE_ID,
        "seed": seed,
        "requested_ratio": {
            "dev": dev_ratio,
            "holdout": holdout_ratio,
        },
        "rounding_rule": "target_dev_count = floor(test_rows * dev_ratio + 0.5)",
        "target_counts": target_counts,
        "actual_counts": actual_counts,
        "split_method": (
            "Sort test rows by sha256(f'{seed}:{stable_row_id}:{sha256_normalized}') "
            "ascending; take the first target_dev_count rows for dev and the remainder for holdout. "
            "Division membership is recorded by stable row id, never Python object/list membership."
        ),
        "normalization_method": {
            "hash_text": NORMALIZATION_METHOD,
            "details": (
                "All contamination hashes are SHA-256 over UTF-8 bytes after "
                "unicodedata.normalize('NFC', text). Output JSONL text is preserved as loaded from raw."
            ),
            "hash_field": "sha256_normalized",
        },
        "eval_hash_ledger_contract": {
            "schema_version": EVAL_HASH_SCHEMA_VERSION,
            "canonical_path": display_path(eval_hashes_out),
            "format": "JSONL, one JSON object per held-out hash",
            "required_fields": [
                "schema_version",
                "sha256_normalized",
                "hash_method",
                "normalization_method",
                "origin",
                "stage",
                "division",
                "split",
                "row_id",
            ],
            "parquet_status": "future optional mirror; JSONL is canonical for this prototype",
        },
        "input": {
            "train": display_path(train_in),
            "test": display_path(test_in),
        },
        "output": {
            "dev": display_path(dev_out),
            "holdout": display_path(holdout_out),
            "train": display_path(train_out),
            "eval_hashes": display_path(eval_hashes_out),
            "manifest": display_path(manifest_out),
        },
        "splits": {
            "dev": dev_stats,
            "holdout": holdout_stats,
            "train": train_stats,
            "removed_from_train": removed_stats,
        },
        "invariant_checks": invariant_checks,
        "invariant": "train ∩ eval_hashes = ∅ (NFC-normalized text SHA-256 dedupe)",
    }

    print("\n[OUTPUT] Writing outputs...")
    write_jsonl(dev_records, dev_out, dry_run)
    write_jsonl(holdout_records, holdout_out, dry_run)
    write_jsonl(train_deduped, train_out, dry_run)
    ledger_stats = write_eval_hash_ledger(
        eval_hash_records,
        eval_hashes_out,
        origin=SOURCE_ID,
        dry_run=dry_run,
    )
    manifest["eval_hash_ledger_update"] = ledger_stats

    if not dry_run:
        manifest_out.parent.mkdir(parents=True, exist_ok=True)
        with manifest_out.open("w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False, sort_keys=True)
            f.write("\n")
        print(f"[WRITE] Manifest → {display_path(manifest_out)}")
    else:
        print(f"[DRY-RUN] Would write manifest to {display_path(manifest_out)}")
        print("[DRY-RUN] Manifest preview:")
        print(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True)[:1200])

    print("\n[SUCCESS] Split/dedupe complete.")
    print("[INVARIANT] train ∩ eval_hashes = ∅ verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
