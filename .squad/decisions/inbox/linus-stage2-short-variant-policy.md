# Stage-2 Short-Variant Exact Duplicate Policy

**Owner:** Linus  
**Date:** 2026-05-03  
**Status:** Implemented (Round 6)

## Decision

Use a length-aware exact one-sided duplicate policy for Stage-2 candidate dedup. For exact-EN or exact-HAW groups whose duplicated side is at most 3 normalized tokens, keep at most 2 variants and require the opposite side to contain at least 4 normalized tokens. Rows failing the opposite-side minimum are dropped before cap ranking. Longer exact one-sided groups keep the Round 5 cap of 3. The Baibala 1839 historical-orthography exception remains exempt from these exact-side caps.

## Rationale

Round 6 sampling showed the short-variant problem is mostly phrase/dictionary material: exact-EN remaining groups had 124 short duplicated-side rows, concentrated in Phrase Book (61) and Andrews (52); exact-HAW remaining groups had 88 short rows, concentrated in Andrews (44) and Phrase Book (29). Bible/Hoʻoilina-style rows are generally sentence-length and should keep the generic cap. A source allowlist with N=5 would preserve more dictionary variants but also retain one-word/short-gloss rows that add little SFT value. The source-agnostic length rule is simpler, deterministic, and directly targets low-information short variants regardless of source.

## Verification

- `PYTHONPATH=code python3 code/tests/test_stage2_dedup.py`
- `PYTHONPATH=code python3 code/tests/test_stage2_candidate_normalization_audit.py`
- `PYTHONPATH=code python3 code/tests/test_stage2_manifest.py`
- `python3 scripts/320_build_stage2_manifest.py --dry-run` → 37,084 rows
- `python3 scripts/340_audit_stage2_candidate_normalization.py --strict --max-examples 3` → 0 post-policy schema violations, 0 hash mismatches, 0 post-policy near-dupe groups

## Alternative considered

Source-allowlisting Phrase Book and Andrews with N=5 plus a sentence heuristic was rejected for now. The data showed the problem is not that these sources were over-clipped; it is that many rows are very short on both sides. Raising their cap would increase low-signal lexicon-style variants in the SFT pool.
