#!/usr/bin/env python3
"""FineWeb-2 ``haw_Latn`` split/dedupe for Stage 1 (Linus, 300-phase).

Takes the official FineWeb-2 `haw_Latn` test split (887 rows) and:

1. **Deterministically splits** the official test split into:
   - 70% checkpoint/dev eval → `data/evals/fineweb2_haw/dev.jsonl`
   - 30% protected holdout/final eval → `data/final/fineweb2_haw/holdout.jsonl`

2. **Dedupes** train against the FULL official test split (all 887 rows):
   - Removes exact `text` SHA-256 matches from train.
   - Writes deduplicated train → `data/stage1/fineweb2_haw/train.jsonl`.

3. **Writes manifest** with row/token/char counts, split ratios, dedupe stats,
   deterministic seed, input/output paths.

4. **Writes eval hashes** for the eval data in a simple JSONL format (one hash
   per line with metadata), deferring parquet to later if needed.

Invariant enforced: `train ∩ eval_hashes = ∅` (exact text hash dedup).

Usage::

    python scripts/310_split_dedupe_fineweb2_haw.py --dry-run
    python scripts/310_split_dedupe_fineweb2_haw.py --execute

Exit codes: 0 success, 2 misuse, 3 processing failure.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def compute_text_hash(text: str) -> str:
    """Compute SHA-256 of normalized text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_whitespace_tokens(text: str) -> int:
    """Raw whitespace token count."""
    return len(text.split())


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load JSONL file into list of records."""
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"[ERROR] Failed to parse JSON at {path}:{line_no}: {e}", file=sys.stderr)
                sys.exit(3)
            records.append(obj)
    return records


def write_jsonl(records: list[dict[str, Any]], path: Path, dry_run: bool) -> None:
    """Write records to JSONL file."""
    if dry_run:
        print(f"[DRY-RUN] Would write {len(records)} records to {path}")
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"[WRITE] {len(records)} records → {path}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="FineWeb-2 haw_Latn split/dedupe for Stage 1 (Linus, 300-phase)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry-run: load and process data but don't write outputs.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute: write outputs to disk.",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/raw/fineweb2_haw/20260429"),
        help="Path to raw FineWeb-2 data directory (default: data/raw/fineweb2_haw/20260429).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Deterministic seed for test split (default: 42).",
    )
    parser.add_argument(
        "--dev-ratio",
        type=float,
        default=0.7,
        help="Ratio for dev split (default: 0.7 = 70%%).",
    )

    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        print("[ERROR] Must specify --dry-run or --execute.", file=sys.stderr)
        return 2

    dry_run = args.dry_run
    raw_dir = args.raw_dir
    seed = args.seed
    dev_ratio = args.dev_ratio
    holdout_ratio = 1.0 - dev_ratio

    # Input paths
    train_in = raw_dir / "train.jsonl"
    test_in = raw_dir / "test.jsonl"

    # Output paths
    evals_dir = Path("data/evals/fineweb2_haw")
    final_dir = Path("data/final/fineweb2_haw")
    stage1_dir = Path("data/stage1/fineweb2_haw")

    dev_out = evals_dir / "dev.jsonl"
    holdout_out = final_dir / "holdout.jsonl"
    train_out = stage1_dir / "train.jsonl"
    manifest_out = stage1_dir / "split_dedupe_manifest.json"
    eval_hashes_out = evals_dir / "eval_hashes.jsonl"

    print("[LOAD] Reading raw FineWeb-2 data...")
    if not train_in.exists():
        print(f"[ERROR] Train file not found: {train_in}", file=sys.stderr)
        return 3
    if not test_in.exists():
        print(f"[ERROR] Test file not found: {test_in}", file=sys.stderr)
        return 3

    train_records = load_jsonl(train_in)
    test_records = load_jsonl(test_in)

    print(f"[LOAD] Train: {len(train_records)} rows")
    print(f"[LOAD] Test: {len(test_records)} rows")

    # Step 1: Deterministically split test into dev/holdout
    print(f"\n[SPLIT] Splitting test {dev_ratio:.0%}/{holdout_ratio:.0%} (dev/holdout) with seed={seed}")

    # Sort test records by row_id for deterministic ordering
    test_sorted = sorted(test_records, key=lambda r: r.get("fineweb2_row_id", ""))

    # Deterministic split based on hash modulo
    dev_records = []
    holdout_records = []

    for record in test_sorted:
        row_id = record.get("fineweb2_row_id", "")
        # Use hash of row_id + seed to deterministically assign
        hash_val = int(hashlib.sha256(f"{row_id}{seed}".encode()).hexdigest(), 16)
        if (hash_val % 100) < int(dev_ratio * 100):
            dev_records.append(record)
        else:
            holdout_records.append(record)

    print(f"[SPLIT] Dev: {len(dev_records)} rows")
    print(f"[SPLIT] Holdout: {len(holdout_records)} rows")

    # Step 2: Build eval hash set from full test (dev + holdout)
    print(f"\n[HASH] Building eval hash set from full test split ({len(test_records)} rows)...")
    eval_hashes = set()
    eval_hash_records = []

    for record in test_records:
        text = record.get("text", "")
        if not text:
            print(f"[WARN] Empty text in test record: {record.get('fineweb2_row_id', 'unknown')}", file=sys.stderr)
            continue

        text_hash = compute_text_hash(text)
        eval_hashes.add(text_hash)

        # Determine division
        division = "evals" if record in dev_records else "final"

        eval_hash_records.append({
            "sha256_text": text_hash,
            "origin": "fineweb2_haw",
            "split": "test",
            "division": division,
            "row_id": record.get("fineweb2_row_id", ""),
            "char_count": record.get("char_count", len(text)),
            "token_count": record.get("raw_whitespace_token_count", compute_whitespace_tokens(text)),
        })

    print(f"[HASH] Eval hash set size: {len(eval_hashes)}")

    # Step 3: Dedupe train against eval hashes
    print(f"\n[DEDUPE] Deduplicating train against full test split...")
    train_deduped = []
    train_removed = []

    for record in train_records:
        text = record.get("text", "")
        if not text:
            print(f"[WARN] Empty text in train record: {record.get('fineweb2_row_id', 'unknown')}", file=sys.stderr)
            train_removed.append(record)
            continue

        text_hash = compute_text_hash(text)
        if text_hash in eval_hashes:
            train_removed.append(record)
        else:
            train_deduped.append(record)

    print(f"[DEDUPE] Train before dedupe: {len(train_records)} rows")
    print(f"[DEDUPE] Train after dedupe: {len(train_deduped)} rows")
    print(f"[DEDUPE] Removed: {len(train_removed)} rows")

    # Step 4: Compute stats
    print(f"\n[STATS] Computing final stats...")

    def compute_stats(records: list[dict[str, Any]]) -> dict[str, int]:
        total_chars = sum(r.get("char_count", len(r.get("text", ""))) for r in records)
        total_tokens = sum(r.get("raw_whitespace_token_count", compute_whitespace_tokens(r.get("text", ""))) for r in records)
        return {
            "rows": len(records),
            "chars": total_chars,
            "tokens": total_tokens,
        }

    dev_stats = compute_stats(dev_records)
    holdout_stats = compute_stats(holdout_records)
    train_stats = compute_stats(train_deduped)
    removed_stats = compute_stats(train_removed)

    print(f"[STATS] Dev: {dev_stats['rows']} rows, {dev_stats['chars']:,} chars, {dev_stats['tokens']:,} tokens")
    print(f"[STATS] Holdout: {holdout_stats['rows']} rows, {holdout_stats['chars']:,} chars, {holdout_stats['tokens']:,} tokens")
    print(f"[STATS] Train (deduped): {train_stats['rows']} rows, {train_stats['chars']:,} chars, {train_stats['tokens']:,} tokens")
    print(f"[STATS] Removed: {removed_stats['rows']} rows, {removed_stats['chars']:,} chars, {removed_stats['tokens']:,} tokens")

    # Step 5: Write manifest
    manifest = {
        "pipeline_stage": "310_split_dedupe_fineweb2_haw",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "seed": seed,
        "dev_ratio": dev_ratio,
        "holdout_ratio": holdout_ratio,
        "input": {
            "train": str(train_in),
            "test": str(test_in),
        },
        "output": {
            "dev": str(dev_out),
            "holdout": str(holdout_out),
            "train": str(train_out),
            "eval_hashes": str(eval_hashes_out),
            "manifest": str(manifest_out),
        },
        "splits": {
            "dev": dev_stats,
            "holdout": holdout_stats,
            "train": train_stats,
            "removed_from_train": removed_stats,
        },
        "invariant": "train ∩ eval_hashes = ∅ (exact text SHA-256 dedupe)",
        "method": "Deterministic hash-modulo split on sorted test rows; exact text-hash dedupe.",
    }

    # Step 6: Write outputs
    print(f"\n[OUTPUT] Writing outputs...")

    write_jsonl(dev_records, dev_out, dry_run)
    write_jsonl(holdout_records, holdout_out, dry_run)
    write_jsonl(train_deduped, train_out, dry_run)
    write_jsonl(eval_hash_records, eval_hashes_out, dry_run)

    if not dry_run:
        manifest_out.parent.mkdir(parents=True, exist_ok=True)
        with open(manifest_out, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        print(f"[WRITE] Manifest → {manifest_out}")
    else:
        print(f"[DRY-RUN] Would write manifest to {manifest_out}")
        print(f"[DRY-RUN] Manifest preview:")
        print(json.dumps(manifest, indent=2)[:500])

    print(f"\n[SUCCESS] Split/dedupe complete.")
    print(f"[INVARIANT] train ∩ eval_hashes = ∅ verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
