# Linus — Stage-2 legacy candidate normalization

**Date:** 2026-05-03  
**Requested by:** yashasg  
**Round:** Stage-2 autonomous progress round 3

## Decision

Use a one-shot legacy candidate normalizer before further Stage-2 manifest/cap decisions. The normalizer rewrites generated candidate JSONLs under `data/stage2/candidates/` only, leaves sibling `.jsonl.bak` copies, and never touches `data/raw/`.

## Why

Round 2 audit showed the highest-leverage blockers were schema drift in older/probe adapters plus HAW ʻokina hash drift. These were mechanical generated-artifact issues, not raw-source issues. Re-emitting candidates through the canonical `320_build_stage2_manifest.py` contract removes schema noise before dedup/cap policy work and makes future manifest dry-runs trustworthy.

## Implemented behavior

`scripts/341_normalize_legacy_candidates.py` is dry-run by default and uses `--apply` (not `--execute`) for local artifact patching. It:

- folds HAW ASCII/right/left quote/backtick ʻokina variants to U+02BB before `sha256_haw_clean` and `sha256_pair`;
- preserves English apostrophes/right quotes;
- maps legacy enum values to schema-compatible values (`phrase-pair` → `parallel-sentence`, `section-id`/coordinate pairing → `manual`, phrase/legal registers → allowed generic registers) while preserving legacy detail in `notes`;
- renames probe fields (`source_id`, `source_pair_id`, `schema_version`) to canonical manifest fields;
- fills required provenance defaults for legacy generated rows;
- sets `license_inferred = null` and enforces `prototype_only=true => release_eligible=false`;
- recomputes clean and pair hashes and applies the Stage-2 quality policy fields.

## Verification

Before: audit found 311 HAW ʻokina-fold rows, 693 pair-hash mismatches under canonical HAW hashing, and 21,118 post-policy schema violations.

After applying locally: `scripts/340_audit_stage2_candidate_normalization.py --strict` reports 0 HAW ʻokina-fold rows, 0 hash mismatches, and 0 raw/post-policy schema violations. `scripts/320_build_stage2_manifest.py --dry-run` emits 37,761 rows with 0 skipped schema violations.

## Follow-up

Cross-source exact pair dup groups remain and rose from 91 to 100 after canonical hash recomputation. Round 4 should codify dedup preference policy, starting with OPUS-Tatoeba vs upstream Tatoeba (Tatoeba should remain canonical) and then Bible cross-edition overlaps.
