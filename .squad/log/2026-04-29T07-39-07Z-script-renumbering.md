# Session: Script renumbering and Wikisource split (2026-04-29)

**Timeline:** 2026-04-29 00:29–07:39 UTC

## Summary

User directive (yashasg): Corrected script numbering from flat `001/002/003` to phase hundreds: collect `1xx`, fetch `2xx`, build `3xx`. Three agents executed in sequence:

1. **Frank** (`frank-wikisource-split`): Split Hawaiian Wikisource fetch into dedicated `002b_fetch_hawwikisource_raw.py`; updated 101 references.
2. **Linus** (`linus-wikisource-handoff`): Added Stage-1 builder support for Wikisource page-text records; extraction contract finalized.
3. **Linus** (`linus-renumber-scripts`): Renamed active scripts to `101`, `201`, `202`, `301`; reconciled all path references; validated without rewriting historical records.

## Decisions finalized

- **Phase-hundreds convention:** collect→fetch→build phases at hundreds granularity; ~99 slots per phase
- **Wikisource handoff:** Stage-1 builder dispatches on content shape (wiki-xml-stream vs wikisource-pagetext), eliminating source-specific branching
- **Storage:** Per-page JSON via MediaWiki API → `data/raw/hawwikisource/fetch.jsonl` (ProvenanceRecord schema)

## Validation

- All four scripts compile (`py_compile`) and execute dry-run modes
- No stale references in active code
- Existing hawwiki output unchanged

## Blockers resolved

- Wikisource bulk run gated pending Linus's extracted-text contract refinement (ʻokina, NFC, apostrophe)
- Rusty to tokenizer-fragmentation audit on de-wiki template handling
