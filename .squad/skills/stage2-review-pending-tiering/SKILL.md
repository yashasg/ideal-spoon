---
name: "stage2-review-pending-tiering"
description: "Audit Stage-2 review-pending rows, promote already-approved Tier A content, and sample uncertain Tier C sources without mutating v1 manifests."
domain: "data-pipeline"
confidence: "high"
source: "earned (Stage-2 Tier A promotion, 2026-05-04)"
---

## Use when

A Stage-2 reviewed manifest has a large `split="review-pending"` pile and the task is to promote only rows already cleared by policy while preserving caps and dev split.

## Tier policy

- **Tier A / promote if caps allow:** rows whose `manual_review_reasons` contain policy-approval strings, plus explicit trusted source whitelists.
- **Tier B / count only:** high-quality rows evicted by corpus/register caps; do not promote without a cap-policy change.
- **Tier C / sample only:** plausible but not yet approved sources; write bounded samples for human review.
- **Tier D / terminal reject:** hard quality failures such as too short, extreme length ratio, or high non-Hawaiian-letter share.

## Promotion algorithm

1. Read the existing manifest; never rewrite v1.
2. Freeze existing `train` and `dev` rows.
3. Identify Tier A from `review-pending` only.
4. Skip exact `sha256_pair` duplicates already present in train.
5. Greedy-admit Tier A in `sha256_pair` ascending order.
6. Recompute train-side pair-token shares with whitespace tokens from `text_en + text_haw`.
7. If a cap is breached, evict only newly admitted rows from that cap group, highest `sha256_pair` first, until all caps pass.
8. Write an additive v2 manifest with the same schema; only flip `split` to `train` for promoted rows.
9. Re-read v2 and verify row count, dev identity, schema keys, and cap shares.

## Reporting contract

Report:

- split counts before/after
- train tokens before/after
- cap shares before/after
- Tier A identified/admitted/promoted/evicted counts
- Tier B count-only rows/tokens by blocker reason
- Tier C rows/tokens plus sample file paths
- Tier D terminal failure counts
- per-source identified/promoted/evicted deltas
- at least 5 promoted samples

## Example

`scripts/335_promote_tier_a_review_pending.py` promotes from `data/stage2/reviewed_stage2_manifest_final_capped.jsonl` to `data/stage2/reviewed_stage2_manifest_final_capped_v2.jsonl` and writes `data/stage2/reports/stage2_tier_a_promotion_20260504.json`.
