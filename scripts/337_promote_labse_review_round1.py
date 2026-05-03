#!/usr/bin/env python3
"""Promote high-quality LaBSE review-tier rows to Stage 2 manifest.

Applies a tightened promotion rule to the 124 review-tier rows from:
  - data/stage2/_scored/wikimedia_cx_en_haw.labse.jsonl (4 review rows)
  - data/stage2/_scored/opus_haw_subsets.labse.jsonl (120 review rows)

Promotion rule (ALL must pass):
  a. LaBSE score above review-band midpoint (≥ 0.65, given band 0.55–0.75)
  b. Length ratio sane: 0.5 ≤ len(en_tokens) / len(haw_tokens) ≤ 2.0
  c. Both sides ≥ 3 tokens (whitespace split)
  d. Not a duplicate by pair_hash of any row in reviewed_stage2_manifest_final_capped.jsonl
  e. Hawaiian orthography check: contains ʻokina OR vowel-cluster [aeioāēīōū]{2,}

Outputs:
  - data/stage2/_scored/labse_review_promotion_round1.jsonl (promoted rows with metadata)
  - Prints before/after counts and sample promoted rows

Usage::

    python scripts/337_promote_labse_review_round1.py --dry-run
    python scripts/337_promote_labse_review_round1.py --execute
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "code"))

# Promotion rule thresholds
LABSE_REVIEW_MIN = 0.55
LABSE_ACCEPT_MIN = 0.75
LABSE_MIDPOINT = (LABSE_REVIEW_MIN + LABSE_ACCEPT_MIN) / 2.0  # 0.65
LENGTH_RATIO_MIN = 0.5
LENGTH_RATIO_MAX = 2.0
MIN_TOKENS = 3

from llm_hawaii.stage2_canonical import canonical_en, canonical_haw, compute_pair_hash, sha256_text  # noqa: E402

# Hawaiian orthography pattern: ʻokina or vowel-cluster
OKINA_CHAR = "\u02bb"
VOWEL_CLUSTER_PATTERN = re.compile(r"[aeioāēīōū]{2,}", re.IGNORECASE)


def canonicalize_okina(text: str) -> str:
    return canonical_haw(text)


def normalize_nfc(text: str) -> str:
    return canonical_haw(text)


def compute_row_pair_hash(row: dict[str, Any]) -> str:
    """Compute pair_hash for a candidate row using 320's logic."""
    en_clean = canonical_en(row.get("text_en", ""))
    haw_clean = canonical_haw(row.get("text_haw", ""))
    sha_en = sha256_text(en_clean)
    sha_haw = sha256_text(haw_clean)
    return compute_pair_hash(sha_en, sha_haw)


def has_hawaiian_orthography(text: str) -> bool:
    """Check if text contains ʻokina OR a vowel cluster."""
    if OKINA_CHAR in text:
        return True
    if VOWEL_CLUSTER_PATTERN.search(text):
        return True
    return False


def check_promotion_rule(row: dict[str, Any], existing_hashes: set[str]) -> dict[str, Any]:
    """Apply promotion rule to a review-tier row.
    
    Returns dict with:
      - passed: bool (overall pass/fail)
      - checks: dict of individual check results
      - reason: str (first failing check or "all_pass")
    """
    result = {
        "passed": False,
        "checks": {},
        "reason": "",
    }
    
    score = row.get("labse_score", 0.0)
    en = row.get("text_en", "")
    haw = row.get("text_haw", "")
    
    # Check a: LaBSE score above midpoint
    check_a = score >= LABSE_MIDPOINT
    result["checks"]["score_above_midpoint"] = check_a
    if not check_a:
        result["reason"] = f"score_too_low:{score:.4f}<{LABSE_MIDPOINT}"
        return result
    
    # Check b: Length ratio sane
    en_tokens = en.split()
    haw_tokens = haw.split()
    if len(haw_tokens) == 0:
        check_b = False
        result["checks"]["length_ratio_sane"] = check_b
        result["reason"] = "haw_empty"
        return result
    
    length_ratio = len(en_tokens) / len(haw_tokens)
    check_b = LENGTH_RATIO_MIN <= length_ratio <= LENGTH_RATIO_MAX
    result["checks"]["length_ratio_sane"] = check_b
    if not check_b:
        result["reason"] = f"length_ratio:{length_ratio:.2f}"
        return result
    
    # Check c: Both sides ≥ 3 tokens
    check_c = len(en_tokens) >= MIN_TOKENS and len(haw_tokens) >= MIN_TOKENS
    result["checks"]["min_tokens"] = check_c
    if not check_c:
        result["reason"] = f"too_short:en={len(en_tokens)},haw={len(haw_tokens)}"
        return result
    
    # Check d: Not a duplicate
    pair_hash = compute_row_pair_hash(row)
    check_d = pair_hash not in existing_hashes
    result["checks"]["not_duplicate"] = check_d
    if not check_d:
        result["reason"] = "duplicate_pair_hash"
        return result
    
    # Check e: Hawaiian orthography
    check_e = has_hawaiian_orthography(haw)
    result["checks"]["hawaiian_orthography"] = check_e
    if not check_e:
        result["reason"] = "no_okina_or_vowel_cluster"
        return result
    
    # All checks passed
    result["passed"] = True
    result["reason"] = "all_pass"
    return result


def load_existing_hashes(manifest_path: Path) -> set[str]:
    """Load pair_hash values from existing manifest."""
    hashes = set()
    if not manifest_path.exists():
        return hashes
    
    with manifest_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                row = json.loads(line)
                # Check both pair_hash and sha256_pair for compatibility
                h = row.get("pair_hash") or row.get("sha256_pair")
                if h:
                    hashes.add(h)
    return hashes


def load_review_rows(scored_paths: list[Path]) -> list[dict[str, Any]]:
    """Load all review-tier rows from scored files."""
    rows = []
    for path in scored_paths:
        if not path.exists():
            print(f"⚠️  Skipping missing file: {path}", file=sys.stderr)
            continue
        
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    row = json.loads(line)
                    if row.get("labse_verdict") == "review":
                        rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Promote LaBSE review-tier rows using tightened rule.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Dry-run mode: show promotion stats, do not write output (default).",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute mode: apply rule, write promoted rows. Overrides --dry-run.",
    )
    args = parser.parse_args()
    
    is_dry_run = args.dry_run and not args.execute
    
    # Paths
    scored_dir = REPO_ROOT / "data" / "stage2" / "_scored"
    manifest_path = REPO_ROOT / "data" / "stage2" / "reviewed_stage2_manifest_final_capped.jsonl"
    output_path = scored_dir / "labse_review_promotion_round1.jsonl"
    
    scored_files = [
        scored_dir / "wikimedia_cx_en_haw.labse.jsonl",
        scored_dir / "opus_haw_subsets.labse.jsonl",
    ]
    
    print("=" * 80)
    print("LaBSE Review Promotion — Round 1")
    print("=" * 80)
    print()
    print("Promotion rule (ALL must pass):")
    print(f"  a. LaBSE score ≥ {LABSE_MIDPOINT} (review band midpoint)")
    print(f"  b. Length ratio: {LENGTH_RATIO_MIN} ≤ en/haw ≤ {LENGTH_RATIO_MAX}")
    print(f"  c. Both sides ≥ {MIN_TOKENS} tokens")
    print(f"  d. Not a duplicate (by pair_hash)")
    print(f"  e. Hawaiian orthography (ʻokina OR vowel cluster)")
    print()
    
    # Load existing manifest hashes
    print(f"Loading existing manifest: {manifest_path.name}")
    existing_hashes = load_existing_hashes(manifest_path)
    print(f"  Found {len(existing_hashes)} existing pair_hash values")
    print()
    
    # Load review rows
    print(f"Loading review-tier rows from {len(scored_files)} files...")
    review_rows = load_review_rows(scored_files)
    print(f"  Total review rows: {len(review_rows)}")
    print()
    
    # Apply promotion rule
    promoted = []
    failed_reasons = []
    
    for row in review_rows:
        check_result = check_promotion_rule(row, existing_hashes)
        
        if check_result["passed"]:
            # Annotate with promotion metadata
            row["promotion_round"] = 1
            row["promotion_checks"] = check_result["checks"]
            import datetime
            row["promotion_timestamp"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            promoted.append(row)
        else:
            failed_reasons.append(check_result["reason"])
    
    # Stats
    print("=" * 80)
    print("Promotion results:")
    print("=" * 80)
    print(f"  Total review rows: {len(review_rows)}")
    print(f"  Promoted: {len(promoted)}")
    print(f"  Rejected: {len(failed_reasons)}")
    print()
    
    # Breakdown of failed reasons
    from collections import Counter
    reason_counts = Counter(failed_reasons)
    print("Rejection reasons:")
    for reason, count in reason_counts.most_common():
        print(f"  {reason}: {count}")
    print()
    
    # Sample promoted rows
    if promoted:
        print("Sample promoted rows (showing 5):")
        print("-" * 80)
        for i, row in enumerate(promoted[:5]):
            score = row.get("labse_score", 0.0)
            en = row.get("text_en", "")[:80]
            haw = row.get("text_haw", "")[:80]
            print(f"[{i+1}] Score: {score:.4f}")
            print(f"    EN:  {en}")
            print(f"    HAW: {haw}")
            print()
    
    # Write output
    if not is_dry_run:
        with output_path.open("w", encoding="utf-8") as f:
            for row in promoted:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"✅ Wrote {len(promoted)} promoted rows to: {output_path}")
    else:
        print(f"🔬 [DRY-RUN] No output written. Use --execute to write to: {output_path.name}")
    
    print()
    print("✅ Promotion complete!")


if __name__ == "__main__":
    main()
