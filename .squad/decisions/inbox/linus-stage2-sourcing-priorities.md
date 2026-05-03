# Linus Stage-2 Sourcing Priorities

**Date:** 2026-05-03
**Status:** Round-8 handoff

## Current eligibility

Round-7 in-memory dry-run from `scripts/320_build_stage2_manifest.py` emits 37,084 clean manifest rows. Current train split contains 2,396 canonical pairs, or 4,792 bidirectional SFT rows via `scripts/330_emit_stage2_sft_jsonl.py` filters. Gap to 40,000 directional SFT rows: 35,208.

The large difference between clean rows and SFT rows is expected: 34,438 rows are `review-pending`, 250 are `dev`, and only 2,396 are `train`. The manifest builder forces review/reject quality tiers to `review-pending`; only accept-tier rows are assigned train/dev, with non-parallel rows forced train-only. The SFT emitter then emits only requested splits and skips synthetic rows by default.

## Prioritized next sources

1. **Hawaiian Kingdom statutes bilingual — remaining 1869/1859/1846 pairs.** Public IA / PD, no compute dependency, deterministic section-id alignment, and the 1897 adapter provides the clearest pattern. Plan: extend `scripts/325_build_hk_statutes_candidates.py` to parameterize edition pairs and reuse CHAPTER/MOKUNA/section matching; enforce combined legal-register cap downstream.
2. **Weblate EN↔HAW public translation memories.** Plain HTTP/Weblate API, no embedding dependency, existing localization/TMX-line adapter pattern from Weblate/software-l10n work. Plan: dry-run enumerate public Hawaiian projects, apply permissive-license filter first, then adapt `scripts/329_build_weblate_en_haw_candidates.py` style rows.
3. **Global-PIQA haw_Latn TSV.** Public static TSV, no auth/compute, simple row-id adapter pattern. Plan: HEAD/probe the TSV and verify license/register; if train-appropriate, emit parallel-sentence candidates; otherwise hash into eval ledger only.

Excluded for Round 8: NLLB and Wikisource endpoints are invalid; wiki-langlinks and Sanitary require LaBSE/compute; Bible-family additions are cap-saturated; Pukui/modern dictionary work needs rights review; synthetic BT needs model-quality and cap infrastructure.
