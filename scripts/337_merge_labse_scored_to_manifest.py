#!/usr/bin/env python3
"""
Merge LaBSE-scored rows into Stage 2 manifest.

Reads scored JSONLs from data/stage2/_scored/*.labse.jsonl and:
- Accept (≥0.75): Set verdict='accept', release_eligible=True, split='train', alignment_method='labse'
- Review (0.65-0.75): Set verdict='review-required', release_eligible=False, split='review-pending', alignment_method='labse'
- Reject (<0.65): Drop (do not merge)

OPUS-wikimedia mined rows: Correct alignment_method from 'tmx-line' to 'labse' per policy gap.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "data" / "stage2" / "stage2_manifest.jsonl"
SCORED_DIR = REPO_ROOT / "data" / "stage2" / "_scored"

# Threshold constants (from PolicyConfig in code/llm_hawaii/stage2_policy.py)
ACCEPT_THRESHOLD = 0.75
REVIEW_THRESHOLD = 0.65  # Updated from 0.55 based on Rusty's note; actually using 0.65 from the context


def load_manifest():
    """Load manifest as {pair_id: row} dict."""
    manifest = {}
    with open(MANIFEST_PATH) as f:
        for line in f:
            row = json.loads(line)
            manifest[row["pair_id"]] = row
    return manifest


def merge_scored_file(manifest, scored_path):
    """Merge scored JSONL into manifest."""
    updated = 0
    promoted_accept = 0
    promoted_review = 0
    dropped_reject = 0
    added_new = 0
    
    with open(scored_path) as f:
        for line in f:
            scored_row = json.loads(line)
            pair_id = scored_row["pair_id"]
            verdict = scored_row.get("labse_verdict")
            labse_score = scored_row.get("labse_score")
            
            # Skip reject rows entirely—don't add them to manifest
            if verdict == "reject":
                dropped_reject += 1
                updated += 1
                continue
            
            # Determine if this is an update or a new addition
            if pair_id in manifest:
                # Update existing row
                manifest_row = manifest[pair_id]
            else:
                # Add new row from scored JSONL
                manifest_row = scored_row.copy()
                manifest[pair_id] = manifest_row
                added_new += 1
            
            # Apply verdict-based updates
            if verdict == "accept":
                manifest_row["alignment_score"] = labse_score
                manifest_row["alignment_method"] = "labse"
                manifest_row["split"] = "train"
                manifest_row["release_eligible"] = True
                # Remove alignment_review_required if present
                if "alignment_review_required" in manifest_row:
                    del manifest_row["alignment_review_required"]
                # Remove labse_verdict and labse_scorer_version (scoring metadata, not manifest fields)
                manifest_row.pop("labse_verdict", None)
                manifest_row.pop("labse_scorer_version", None)
                promoted_accept += 1
                
            elif verdict in ["review", "review-required"]:
                manifest_row["alignment_score"] = labse_score
                manifest_row["alignment_method"] = "labse"
                manifest_row["split"] = "review-pending"
                manifest_row["release_eligible"] = False
                manifest_row["alignment_review_required"] = True
                # Remove labse_verdict and labse_scorer_version
                manifest_row.pop("labse_verdict", None)
                manifest_row.pop("labse_scorer_version", None)
                promoted_review += 1
                
            else:
                print(f"WARNING: Unknown verdict '{verdict}' for {pair_id}", file=sys.stderr)
            
            updated += 1
    
    return {
        "updated": updated,
        "promoted_accept": promoted_accept,
        "promoted_review": promoted_review,
        "dropped_reject": dropped_reject,
        "added_new": added_new,
    }


def main():
    print("=== LaBSE Scored Row Merge ===")
    print(f"Manifest: {MANIFEST_PATH}")
    print(f"Scored dir: {SCORED_DIR}")
    
    # Load manifest
    manifest = load_manifest()
    initial_count = len(manifest)
    print(f"\nInitial manifest rows: {initial_count}")
    
    # Find scored files
    scored_files = sorted(SCORED_DIR.glob("*.labse.jsonl"))
    if not scored_files:
        print("ERROR: No scored files found", file=sys.stderr)
        sys.exit(1)
    
    print(f"\nFound {len(scored_files)} scored files:")
    for sf in scored_files:
        print(f"  - {sf.name}")
    
    # Merge each scored file
    total_stats = {
        "updated": 0,
        "promoted_accept": 0,
        "promoted_review": 0,
        "dropped_reject": 0,
        "added_new": 0,
    }
    
    for scored_file in scored_files:
        print(f"\n--- Merging {scored_file.name} ---")
        stats = merge_scored_file(manifest, scored_file)
        for k in total_stats:
            total_stats[k] += stats[k]
        
        print(f"  Accept: {stats['promoted_accept']}")
        print(f"  Review: {stats['promoted_review']}")
        print(f"  Reject (dropped): {stats['dropped_reject']}")
        print(f"  New rows added: {stats['added_new']}")
    
    # Write updated manifest
    final_count = len(manifest)
    with open(MANIFEST_PATH, "w") as f:
        for row in manifest.values():
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    
    # Summary
    print(f"\n=== Merge Complete ===")
    print(f"Initial manifest: {initial_count}")
    print(f"New rows added: {total_stats['added_new']}")
    print(f"Total accept promoted: {total_stats['promoted_accept']}")
    print(f"Total review promoted: {total_stats['promoted_review']}")
    print(f"Total reject dropped: {total_stats['dropped_reject']}")
    print(f"Final manifest: {final_count}")
    print(f"Delta: {final_count - initial_count:+d}")
    
    # Verify math (accept + review are added, reject never added)
    expected_final = initial_count + total_stats["promoted_accept"] + total_stats["promoted_review"]
    if final_count != expected_final:
        print(f"WARNING: Math mismatch. Expected {expected_final}, got {final_count}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
