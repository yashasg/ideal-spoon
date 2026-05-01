#!/usr/bin/env python3
"""Stage 2 review-pending completion pass (Linus, 330-phase).

Runs the automated machine/data review pass over every review-pending row across:
  - Existing manifest: baibala-1839, andrews-1865, kaikki, tatoeba
  - New candidates: hooilina, hk_statutes_1897
  - Bible 1868 candidate file: applies hard ≤30% parallel-train cap

Policy decisions applied (documented below):
  1. dict-example-relaxed: alignment_type=dictionary-example rows use
       min_tokens_per_side=1, length_ratio_max=5.0.
     Rationale: dictionary entries are inherently single-word by design;
     the standard 3-token minimum was written for sentence-level pairs.
  2. manual-short-sentence: alignment_method=manual + alignment_type=parallel-sentence
       rows use min_tokens_per_side=2.
     Rationale: Tatoeba pairs are manually verified translations; two-token
     greetings/phrases ("Hello!" / "Aloha!") carry real instruction signal.
  3. hk-statutes-historical-orthography: hk_statutes_1897 rows whose ONLY soft
       flag is `haw_no_diacritics` are promoted to accept tier.
     Rationale: 1897 Hawaiian legal text predates Pukui-Elbert orthography; the
     absence of ʻokina/kahakō is historically expected (not an OCR failure).
     Section-ID alignment is deterministic (filename-pair).
  4. Bible-30pct-cap: Bible (1839+1868 combined) is hard-capped at ≤30% of
       total parallel-train rows (row-count proxy for token-share cap). This is
       enforced against the 80k SFT target. At target=80k: ceil = 24,000 Bible rows.
     Current 1839 train = 4,431 → 1868 rows capped at 19,569 of 20,852 available.

Outputs:
  data/stage2/reviewed_stage2_manifest.jsonl   — promoted manifest
  data/stage2/reports/stage2_review_pass_YYYYMMDD.json  — review report

Usage::
    python scripts/331_stage2_review_pass.py --dry-run
    python scripts/331_stage2_review_pass.py --execute
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_STAGE2 = REPO_ROOT / "data" / "stage2"
CANDIDATES_DIR = DATA_STAGE2 / "candidates"
REPORTS_DIR = DATA_STAGE2 / "reports"
MANIFEST_IN = DATA_STAGE2 / "stage2_manifest.jsonl"
MANIFEST_OUT = DATA_STAGE2 / "reviewed_stage2_manifest.jsonl"

_CODE_DIR = REPO_ROOT / "code"
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

from llm_hawaii.stage2_quality import score_pair, PolicyConfig, POLICY_VERSION  # noqa: E402

# ---------------------------------------------------------------------------
# Policy configs for this review pass
# ---------------------------------------------------------------------------

# Standard config (default thresholds)
CFG_STANDARD = PolicyConfig()

# Dict-example relaxed: single-word dictionary pairs are valid
CFG_DICT_EXAMPLE = PolicyConfig(
    min_tokens_per_side=1,
    length_ratio_min=0.2,
    length_ratio_max=5.0,
)

# Short sentence manual: Tatoeba 2-token pairs are valid
CFG_MANUAL_SHORT = PolicyConfig(min_tokens_per_side=2)

# Bible 30% cap (row-count proxy). Hard ceiling at 80k SFT target.
BIBLE_30PCT_TARGET = 80_000
BIBLE_30PCT_CEILING = int(BIBLE_30PCT_TARGET * 0.30)  # 24,000

# Bible 1868 cap: total 1839 train already = 4,431 → 1868 budget = 24,000 - 4,431
BIBLE_1839_EXISTING_TRAIN = 4_431
BIBLE_1868_BUDGET = BIBLE_30PCT_CEILING - BIBLE_1839_EXISTING_TRAIN  # 19,569

# Dedup set: verse keys already in 1839 manifest
BIBLE_1839_VERSE_KEYS: set[str] = set()
# sha256_pair already in existing manifest
EXISTING_PAIR_HASHES: set[str] = set()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(rows: list[dict], path: Path) -> None:
    with path.open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def assign_split(pair_id: str, dev_modulus: int = 10) -> str:
    h = int(hashlib.sha256(pair_id.encode()).hexdigest()[:8], 16)
    return "dev" if h % dev_modulus == 0 else "train"


def pick_config(row: dict) -> PolicyConfig:
    """Select the policy config appropriate for this row type."""
    atype = row.get("alignment_type", "")
    amethod = row.get("alignment_method", "")
    if atype == "dictionary-example":
        return CFG_DICT_EXAMPLE
    if amethod == "manual" and atype == "parallel-sentence":
        return CFG_MANUAL_SHORT
    return CFG_STANDARD


def hk_statutes_historical_orth_override(row: dict, ann: dict) -> dict:
    """Promote HK Statutes 1897 rows with ONLY haw_no_diacritics to accept.

    Policy: 1897 Hawaiian legal text predates modern orthography conventions.
    Absence of diacritics is historically expected, not an OCR/quality defect.
    Alignment is deterministic (section-ID). This is analogous to the
    baibala-1839 historical_orthography_exception for the religious register.
    """
    if (
        row.get("source") == "hk_statutes_1897"
        and ann.get("alignment_confidence_tier") == "review"
        and set(ann.get("quality_flags") or []) == {"haw_no_diacritics"}
    ):
        ann = dict(ann)
        ann["alignment_confidence_tier"] = "accept"
        reasons = list(ann.get("manual_review_reasons") or [])
        reasons.append(
            "Accepted under historical-legal-register policy: 1897 Hawaiian "
            "Kingdom Statutes predates Pukui-Elbert orthography convention. "
            "Section-ID alignment is deterministic."
        )
        ann["manual_review_reasons"] = reasons
        ann["historical_orthography_exception"] = True
        ann["orthography_era"] = "pre-pukui-elbert-legal"
    return ann


# ---------------------------------------------------------------------------
# Main review pass
# ---------------------------------------------------------------------------

def run_review_pass(dry_run: bool = True) -> dict[str, Any]:
    today = datetime.date.today().strftime("%Y%m%d")
    report: dict[str, Any] = {
        "report_id": f"stage2_review_pass_{today}",
        "generated_utc": datetime.datetime.utcnow().isoformat() + "Z",
        "policy_version": POLICY_VERSION,
        "policy_decisions_applied": [
            "dict-example-relaxed: min_tokens=1, length_ratio_max=5.0 for alignment_type=dictionary-example",
            "manual-short-sentence: min_tokens=2 for manual-method parallel-sentence pairs (Tatoeba)",
            "hk-statutes-historical-orthography: promote haw_no_diacritics-only HK Statutes review rows",
            f"bible-30pct-cap: Bible 1839+1868 ≤ {BIBLE_30PCT_CEILING} rows at {BIBLE_30PCT_TARGET} target; 1868 budget = {BIBLE_1868_BUDGET}",
        ],
        "sources": {},
        "totals": {},
    }

    # --- Phase 1: Load existing manifest ---
    manifest_rows = read_jsonl(MANIFEST_IN)
    print(f"Loaded existing manifest: {len(manifest_rows)} rows")

    # Build dedup sets from existing train rows
    for r in manifest_rows:
        if r.get("split") == "train":
            EXISTING_PAIR_HASHES.add(r["sha256_pair"])
        if r.get("source") == "baibala-hemolele-1839":
            BIBLE_1839_VERSE_KEYS.add(r.get("record_id_haw", ""))

    # Keep non-review-pending rows as-is
    kept_rows: list[dict] = [r for r in manifest_rows if r.get("split") != "review-pending"]
    review_pending = [r for r in manifest_rows if r.get("split") == "review-pending"]
    print(f"  Non-review-pending (kept as-is): {len(kept_rows)}")
    print(f"  Review-pending to process: {len(review_pending)}")

    # Track counts for report
    src_stats: dict[str, dict] = defaultdict(lambda: {
        "input": 0, "promoted_train": 0, "promoted_dev": 0,
        "excluded_review": 0, "excluded_reject": 0, "top_exclude_reasons": Counter(),
    })

    # --- Phase 2: Review existing manifest review-pending rows ---
    reviewed_manifest_rows: list[dict] = list(kept_rows)

    for row in review_pending:
        src = row.get("source", "?")
        src_stats[src]["input"] += 1

        # Preserve the historical_orthography_sub_cap_reached policy decision:
        # these baibala-1839 rows passed quality but were demoted by the 15%
        # hist-orth sub-cap. Re-promoting them here without re-applying the sub-cap
        # would violate policy. They stay review-pending until the sub-cap allows them.
        existing_reasons = row.get("manual_review_reasons") or []
        if (
            row.get("source") == "baibala-hemolele-1839"
            and "historical_orthography_sub_cap_reached" in existing_reasons
        ):
            row = dict(row)
            row["split"] = "review-pending"
            src_stats[src]["excluded_review"] += 1
            reviewed_manifest_rows.append(row)
            continue

        cfg = pick_config(row)
        ann = score_pair(row, cfg)

        # HK Statutes historical-orthography override (not applicable here —
        # these are manifest rows; only new candidates get this override)
        tier = ann["alignment_confidence_tier"]
        row = dict(row)
        row.update({k: v for k, v in ann.items() if k not in ("alignment_type", "alignment_method")})

        if tier == "accept":
            # Determine split
            pair_id = row.get("pair_id") or row.get("sha256_pair", "")
            atype = row.get("alignment_type", "")
            assigned = assign_split(pair_id)
            if assigned == "dev" and not str(atype).startswith("parallel-"):
                assigned = "train"
            if row.get("historical_orthography_exception") and assigned == "dev":
                assigned = "train"
            row["split"] = assigned
            if assigned == "train":
                src_stats[src]["promoted_train"] += 1
            else:
                src_stats[src]["promoted_dev"] += 1
        else:
            # Keep as review-pending, record reason
            row["split"] = "review-pending"
            for f in (ann.get("quality_flags") or []):
                src_stats[src]["top_exclude_reasons"][f] += 1
            if tier == "reject":
                src_stats[src]["excluded_reject"] += 1
            else:
                src_stats[src]["excluded_review"] += 1

        reviewed_manifest_rows.append(row)

    # --- Phase 3: New candidate files ---

    # Hooilina
    hooilina_rows = read_jsonl(CANDIDATES_DIR / "hooilina.jsonl")
    hoo_stats = {"input": len(hooilina_rows), "promoted_train": 0, "promoted_dev": 0,
                 "excluded_review": 0, "excluded_reject": 0, "top_exclude_reasons": Counter()}
    print(f"Hooilina: {len(hooilina_rows)} rows")
    for row in hooilina_rows:
        if row["sha256_pair"] in EXISTING_PAIR_HASHES:
            continue
        cfg = pick_config(row)
        ann = score_pair(row, cfg)
        tier = ann["alignment_confidence_tier"]
        row = dict(row)
        row.update({k: v for k, v in ann.items() if k not in ("alignment_type", "alignment_method")})

        if tier == "accept":
            pair_id = row.get("pair_id") or row.get("sha256_pair", "")
            atype = row.get("alignment_type", "")
            assigned = assign_split(pair_id)
            if assigned == "dev" and not str(atype).startswith("parallel-"):
                assigned = "train"
            row["split"] = assigned
            EXISTING_PAIR_HASHES.add(row["sha256_pair"])
            if assigned == "train":
                hoo_stats["promoted_train"] += 1
            else:
                hoo_stats["promoted_dev"] += 1
        else:
            row["split"] = "review-pending"
            for f in (ann.get("quality_flags") or []):
                hoo_stats["top_exclude_reasons"][f] += 1
            if tier == "reject":
                hoo_stats["excluded_reject"] += 1
            else:
                hoo_stats["excluded_review"] += 1

        reviewed_manifest_rows.append(row)

    src_stats["hooilina"] = hoo_stats

    # HK Statutes 1897
    hk_rows = read_jsonl(CANDIDATES_DIR / "hk_statutes_1897.jsonl")
    hk_stats = {"input": len(hk_rows), "promoted_train": 0, "promoted_dev": 0,
                "excluded_review": 0, "excluded_reject": 0, "top_exclude_reasons": Counter()}
    print(f"HK Statutes 1897: {len(hk_rows)} rows")
    for row in hk_rows:
        if row["sha256_pair"] in EXISTING_PAIR_HASHES:
            continue
        cfg = pick_config(row)
        ann = score_pair(row, cfg)
        # Apply historical-orthography override for this source
        ann = hk_statutes_historical_orth_override(row, ann)
        tier = ann["alignment_confidence_tier"]
        row = dict(row)
        row.update({k: v for k, v in ann.items() if k not in ("alignment_type", "alignment_method")})

        if tier == "accept":
            pair_id = row.get("pair_id") or row.get("sha256_pair", "")
            atype = row.get("alignment_type", "")
            assigned = assign_split(pair_id)
            if assigned == "dev" and not str(atype).startswith("parallel-"):
                assigned = "train"
            row["split"] = assigned
            EXISTING_PAIR_HASHES.add(row["sha256_pair"])
            if assigned == "train":
                hk_stats["promoted_train"] += 1
            else:
                hk_stats["promoted_dev"] += 1
        else:
            row["split"] = "review-pending"
            for f in (ann.get("quality_flags") or []):
                hk_stats["top_exclude_reasons"][f] += 1
            if tier == "reject":
                hk_stats["excluded_reject"] += 1
            else:
                hk_stats["excluded_review"] += 1

        reviewed_manifest_rows.append(row)

    src_stats["hk_statutes_1897"] = hk_stats

    # --- Phase 4: Bible 1868 — apply 30% cap ---
    bible_1868_rows = read_jsonl(CANDIDATES_DIR / "bible_haw1868_kjv.jsonl")
    b68_stats = {
        "input": len(bible_1868_rows), "unique_after_verse_dedup": 0,
        "quality_accept": 0, "quality_review": 0, "quality_reject": 0,
        "cap_budget": BIBLE_1868_BUDGET, "promoted_train": 0,
        "excluded_over_cap": 0, "excluded_quality": 0,
        "bible_1839_existing_train": BIBLE_1839_EXISTING_TRAIN,
        "bible_ceiling_30pct_at_80k_target": BIBLE_30PCT_CEILING,
    }
    print(f"Bible 1868: {len(bible_1868_rows)} rows (applying cap)")

    # Dedup against 1839 verse keys and existing pair hashes
    unique_1868: list[dict] = []
    for row in bible_1868_rows:
        verse_key = row.get("record_id_haw", "")
        if verse_key in BIBLE_1839_VERSE_KEYS:
            continue
        if row["sha256_pair"] in EXISTING_PAIR_HASHES:
            continue
        unique_1868.append(row)
    b68_stats["unique_after_verse_dedup"] = len(unique_1868)

    # Score each row
    scored_1868: list[tuple[str, dict]] = []
    for row in unique_1868:
        ann = score_pair(row, CFG_STANDARD)
        tier = ann["alignment_confidence_tier"]
        if tier == "accept":
            b68_stats["quality_accept"] += 1
            scored_1868.append(("accept", row))
        elif tier == "review":
            b68_stats["quality_review"] += 1
            scored_1868.append(("review", row))
        else:
            b68_stats["quality_reject"] += 1
            scored_1868.append(("reject", row))

    # Apply historical-orthography exception for 1868 (same as 1839)
    # The 1868 Baibala also predates Pukui-Elbert; rows with only haw_no_diacritics
    # should get the same exception as 1839.
    def apply_1868_hist_orth(row: dict, ann: dict) -> dict:
        # The 1868 candidate rows have source_url_en="" / source_url_haw="" (empty,
        # not null) because the USFM adapter didn't populate URL fields. The source IS
        # known: baibala.org and standard KJV USFM. Allow source_url_missing to co-
        # occur with haw_no_diacritics for this source.
        allowed_soft_flags = {"haw_no_diacritics", "source_url_missing"}
        actual_flags = set(ann.get("quality_flags") or [])
        if (
            ann.get("alignment_confidence_tier") == "review"
            and actual_flags.issubset(allowed_soft_flags)
            and actual_flags  # at least one flag fired
            and row.get("alignment_method") == "verse-id"
            and row.get("register") == "religious"
        ):
            ann = dict(ann)
            ann["alignment_confidence_tier"] = "accept"
            reasons = list(ann.get("manual_review_reasons") or [])
            reasons.append(
                "Accepted under historical-orthography policy: "
                "1868 Baibala Hemolele predates modern ʻokina/kahakō convention. "
                "source_url_missing waived: source is baibala.org (known, documented)."
            )
            ann["manual_review_reasons"] = reasons
            ann["historical_orthography_exception"] = True
            ann["orthography_era"] = "pre-pukui-elbert"
        return ann

    # Re-score with hist-orth exception
    qualified_1868: list[dict] = []
    for row in unique_1868:
        ann = score_pair(row, CFG_STANDARD)
        ann = apply_1868_hist_orth(row, ann)
        tier = ann["alignment_confidence_tier"]
        if tier == "accept":
            merged = dict(row)
            merged.update({k: v for k, v in ann.items() if k not in ("alignment_type", "alignment_method")})
            merged["split"] = "train"  # Bible rows are train-only
            qualified_1868.append(merged)

    # Sort deterministically for cap enforcement: lowest SHA-256(pair_id) first
    qualified_1868.sort(key=lambda r: hashlib.sha256(r.get("pair_id", "").encode()).hexdigest())

    # Apply cap: take at most BIBLE_1868_BUDGET rows
    cap_kept = qualified_1868[:BIBLE_1868_BUDGET]
    cap_overflow = qualified_1868[BIBLE_1868_BUDGET:]

    b68_stats["promoted_train"] = len(cap_kept)
    b68_stats["excluded_over_cap"] = len(cap_overflow)
    b68_stats["excluded_quality"] = len(unique_1868) - len(qualified_1868)

    for row in cap_kept:
        EXISTING_PAIR_HASHES.add(row["sha256_pair"])
        reviewed_manifest_rows.append(row)

    for row in cap_overflow:
        row["split"] = "review-pending"
        row["notes"] = (row.get("notes") or "") + " [bible_30pct_cap_overflow: see stage2_review_pass report]"
        reviewed_manifest_rows.append(row)

    src_stats["bible_haw1868_kjv"] = b68_stats

    # --- Phase 5: Final counts ---
    final_splits = Counter(r.get("split", "?") for r in reviewed_manifest_rows)
    final_by_source = defaultdict(Counter)
    for r in reviewed_manifest_rows:
        final_by_source[r.get("source", "?")][r.get("split", "?")] += 1

    # Bible share check
    bible_train = sum(
        final_by_source[s].get("train", 0)
        for s in final_by_source
        if "baibala" in s or "bible" in s.lower() or "1868" in s
    )
    total_train = final_splits.get("train", 0)
    bible_share = (bible_train / total_train * 100) if total_train else 0

    # Serialize src_stats for JSON (Counter → dict)
    serializable_src_stats = {}
    for src, stats in src_stats.items():
        s = dict(stats)
        s["top_exclude_reasons"] = dict(s.get("top_exclude_reasons", Counter()))
        serializable_src_stats[src] = s

    report["sources"] = serializable_src_stats
    report["totals"] = {
        "manifest_in_rows": len(manifest_rows),
        "reviewed_manifest_rows": len(reviewed_manifest_rows),
        "final_train": final_splits.get("train", 0),
        "final_dev": final_splits.get("dev", 0),
        "final_review_pending": final_splits.get("review-pending", 0),
        "bible_train_rows": bible_train,
        "non_bible_train_rows": total_train - bible_train,
        "bible_share_pct": round(bible_share, 1),
        "bible_30pct_cap_ceiling_at_80k_target": BIBLE_30PCT_CEILING,
        "note_bible_share": (
            "Bible share exceeds 30% cap because non-Bible training data is still "
            "growing. Cap is enforced against 80k target. With current non-Bible rows, "
            "the 30% cap cannot be satisfied until ~10k non-Bible rows are accumulated "
            "(NLLB-mined, wikimedia-cx, additional sources). Existing 1839 train rows "
            "are preserved; 1868 additions are hard-capped at BIBLE_1868_BUDGET="
            f"{BIBLE_1868_BUDGET} rows."
        ),
    }
    report["final_split_by_source"] = {s: dict(c) for s, c in final_by_source.items()}

    print(f"\n--- REVIEW PASS RESULTS ---")
    print(f"Total rows in reviewed manifest: {len(reviewed_manifest_rows)}")
    print(f"  train: {final_splits.get('train',0)}")
    print(f"  dev:   {final_splits.get('dev',0)}")
    print(f"  review-pending: {final_splits.get('review-pending',0)}")
    print(f"  Bible train: {bible_train} ({bible_share:.1f}% of train)")
    print(f"  Non-Bible train: {total_train - bible_train}")
    print(f"\nSource breakdown:")
    for src, counts in sorted(final_by_source.items()):
        print(f"  {src}: {dict(counts)}")

    # --- Write outputs ---
    report_path = REPORTS_DIR / f"stage2_review_pass_{today}.json"
    if not dry_run:
        write_jsonl(reviewed_manifest_rows, MANIFEST_OUT)
        print(f"\nWrote: {MANIFEST_OUT}")
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        with report_path.open("w") as fh:
            json.dump(report, fh, indent=2, ensure_ascii=False)
        print(f"Wrote: {report_path}")
    else:
        print(f"\n[DRY RUN] Would write {MANIFEST_OUT} and {report_path}")

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not (args.dry_run or args.execute):
        parser.error("Pass --dry-run or --execute")
    run_review_pass(dry_run=not args.execute)


if __name__ == "__main__":
    main()
