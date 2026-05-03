# Stage-2 Near-Duplicate and One-Sided Exact Duplicate Policy

**Owner:** Linus  
**Date:** 2026-05-03  
**Status:** Implemented in manifest dry-run path

## Decision

Stage-2 post-policy dedup now runs in this order:

1. collapse exact cross-source `sha256_pair` duplicates;
2. cap exact-English-only groups at **3** variants per `sha256_en_clean`;
3. cap exact-Hawaiian-only groups at **3** variants per `sha256_haw_clean`;
4. collapse cross-source near-duplicate groups at **0.92** similarity on both sides.

Selection is deterministic: source priority (richer provenance first), then longer combined text, then stable `(source, pair_id, record_id_haw)`. Baibala 1839 historical-orthography exception groups are excluded from one-sided caps so the historical sub-cap math remains stable.

## Rationale

A cap of 3 keeps useful translation/paraphrase signal for common strings (e.g. greetings and short phrase-book rows) without letting one English or Hawaiian phrase dominate the manifest. Near-duplicate collapse is cross-source only to avoid deleting intentional within-source variants or test fixtures; current hits are mostly Bible-family overlap plus Andrews/Phrase Book-style short phrase duplication.

## Round-5 measurements

After Round-4 exact pair dedup baseline (37,661 rows):

| Pass | Groups | Rows dropped |
|---|---:|---:|
| Exact EN cap (N=3) | 15 capped groups | 128 |
| Exact HAW cap (N=3) | 2 capped groups | 4 |
| Near-dupe collapse (threshold 0.92) | 306 groups | 306 |

Manifest dry-run: **37,661 → 37,223** rows.

Audit before policy reported 262 exact-EN-only groups, 88 exact-HAW-only groups, and 306 near-dupe groups. After policy, near-dupe groups are 0; remaining one-sided exact groups are ≤3 variants each (207 EN groups, 70 HAW groups).

## Follow-up

Round 6 should sample the remaining one-sided exact groups by source (especially Andrews/Phrase Book and short dictionary rows) and decide whether source-specific caps or manual allowlists should supplement the global N=3 policy.
