# Linus — Stage-2 cross-source exact-pair dedup policy

**Date:** 2026-05-03
**Requested by:** yashasg
**Status:** Implemented in `code/llm_hawaii/stage2_dedup.py`; wired into `scripts/320_build_stage2_manifest.py`; audit-aware in `scripts/340_audit_stage2_candidate_normalization.py`.

## Problem

After legacy candidate normalization fixed canonical HAW hashing, 100 exact `sha256_pair` collisions surfaced across sources. These are not near-dupes; they are byte-identical canonical EN/HAW pair hashes and must collapse to one manifest row before cap math and SFT emission.

## Source-pair breakdown observed

- 90 groups: `opus-haw-subsets` OPUS-Tatoeba mirror vs canonical `tatoeba`.
- 9 groups: `gospel_john_1854` vs `baibala-hemolele-1868` exact John verse overlaps.
- 1 group: `opus-haw-subsets` OPUS-Wikimedia mirror vs canonical `wikimedia-cx-en-haw`.
- All groups were size 2, so 100 groups => 100 rows dropped.

## Preference rules

Ordered first-match policy for exact `sha256_pair` collision groups:

1. **Hoʻoilina over Bible** (`hooilina-over-bible`): keep Hoʻoilina if any Bible-family source exactly overlaps. Rationale: Hawaiian newspaper/periodical register is preferred over Bible register for diversity; Bible rows remain allowed when not exact duplicates.
2. **Wikimedia CX over OPUS-Wikimedia** (`wikimedia-cx-over-opus-wikimedia`): keep canonical `wikimedia-cx-en-haw`; drop OPUS mirror rows whose pair IDs classify as `opus-wikimedia-*`. Rationale: CX rows retain article/revision provenance while OPUS is derivative.
3. **Canonical Tatoeba over OPUS-Tatoeba** (`tatoeba-over-opus-tatoeba`): keep `tatoeba`; drop OPUS mirror rows whose pair IDs classify as `opus-tatoeba-*`. Rationale: canonical Tatoeba rows retain sentence/link IDs while OPUS is derivative.
4. **Baibala 1868 over other Bible editions on exact overlap** (`bible-1868-over-other-bible-editions`): keep `baibala-hemolele-1868`; drop exact duplicate Bible-family rows (`baibala-hemolele-1839`, `gospel_john_1854`, or other Bible-family IDs). Rationale: ADR allows multiple editions under the combined Bible cap, but an exact duplicate should retain the later, more standardized orthography.
5. **Fallback** (`deterministic_fallback_no_policy_rule`): only if an unexpected cross-source exact-pair group appears without a matching rule, keep the deterministic source/pair-id minimum and log the fallback for review.

## Verification

- `python3 scripts/320_build_stage2_manifest.py --dry-run`: 37,761 -> 37,661 rows; 100 duplicate groups collapsed; 0 schema violations.
- `python3 scripts/340_audit_stage2_candidate_normalization.py --strict`: raw groups 100; post-dedup exact pair groups 0; raw/post-policy schema violations 0; hash mismatches 0.
- `PYTHONPATH=code python3 -m unittest discover -s code/tests -p 'test_stage2_dedup.py'`: 5/5 pass.
- `python3 code/tests/test_stage2_manifest.py`: 45/45 pass.
- `python3 code/tests/test_stage2_candidate_normalization_audit.py`: 3/3 pass.
