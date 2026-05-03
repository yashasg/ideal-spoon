# Linus — Stage-2 candidate normalization audit (Round 2)

**Date:** 2026-05-03  
**Status:** Landed dry-run audit tooling; no `data/` mutation.

## Decision

Add a dry-run-only normalization/dedup/schema audit before doing further Stage-2 manifest/cap promotion work.

## Why

Current candidate pool has enough mixed-era adapters that cap math can hide source-shape problems. The audit found:

- 37,761 candidate rows across 15 JSONL files.
- 311 Hawaiian rows need canonical ʻokina folding before clean hash/pair hash computation.
- 2,119 English rows contain apostrophes/right quotes; EN apostrophes are intentionally preserved while HAW okina-like marks are folded.
- 91 cross-source exact pair-hash duplicate groups, including OPUS-Tatoeba duplicates of upstream Tatoeba.
- Near-duplicate examples where Andrews number entries duplicate Phrase Book number rows.
- Post-policy schema violations concentrated in older/probe adapters: Gospel John/HK constitution raw-hash/license fields, Phrase Book enum drift, and wiki-langlinks probe rows.

## Consequence

Round 3 should fix adapters and regenerate candidate JSONL via each adapter's `--execute` only where already cleared, then rebuild the manifest. Do not hand-edit files under `data/`.

## Verification

- `python3 -m py_compile scripts/340_audit_stage2_candidate_normalization.py`
- `python3 code/tests/test_stage2_candidate_normalization_audit.py`
- `python3 scripts/340_audit_stage2_candidate_normalization.py --max-examples 4`
- `python3 scripts/320_build_stage2_manifest.py --dry-run`
