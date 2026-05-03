# Linus Stage-2 Paraphrase Grouping Decision

**Date:** 2026-05-03
**Status:** Implemented

## Decision

Accept the remaining one-sided exact duplicate groups as legitimate lexical diversity and annotate them with `paraphrase_group_id`; do not drop more rows and do not move them to held-out.

## Evidence

Post-Round-6 dry-run still shows 161 exact-English groups and 32 exact-Hawaiian groups. Samples are mostly expected formulaic or lexical variants:

- Bible formulae with distinct Hawaiian renderings: “The grace of our Lord Jesus Christ be with you all. Amen.” maps to multiple verse endings.
- Bible narrative formulae: “And the LORD spake unto Moses, saying,” and “The word of the LORD came unto me, saying,” recur with small Hawaiian lexical/OCR/casing variation.
- Hawaiian-side lexical variants: Tatoeba keeps “ʻO Keoni koʻu inoa.” for “My name is John.” / “My name's John.” / “John is my name.”
- Dictionary variants are semantically legitimate: Andrews “Nothing” / “Nought” both map to “he ole, he mea ole.”

No obvious broken pattern justified another hard drop rule. Additional dedup would mostly erase useful paraphrase/lexical diversity.

## Implementation

`code/llm_hawaii/stage2_dedup.py` now annotates connected one-sided exact groups after exact-pair collapse, one-sided caps, and near-duplicate collapse. `scripts/320_build_stage2_manifest.py` records `paraphrase_grouping` stats in ingest provenance. The manifest row count remains unchanged.

## Metrics

- Manifest rows: 37,084 → 37,084 (delta 0)
- Exact-EN groups annotated: 161 groups / 341 row hits
- Exact-HAW groups annotated: 32 groups / 71 row hits
- Connected paraphrase components: 178
- Rows with `paraphrase_group_id`: 395
