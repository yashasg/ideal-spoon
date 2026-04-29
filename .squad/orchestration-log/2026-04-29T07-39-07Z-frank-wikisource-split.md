# Orchestration: Frank — Hawaiian Wikisource split

**Time:** 2026-04-29T07:39:07Z  
**Agent:** frank-wikisource-split (background, claude-opus-4.7)  
**Directive:** Extract Hawaiian Wikisource fetch into dedicated `scripts/202_fetch_hawwikisource_raw.py`

## Outcome

✅ **COMPLETE**

- Created `scripts/002b_fetch_hawwikisource_raw.py` with paginated MediaWiki API enumeration and per-page wikitext fetches
- Updated `scripts/101_collect_rightslight.py` references to point at `scripts/202_*` (post-renumber)
- Validated script syntax and dry-run behavior without real network fetch
- Documented behavioral contract (dry-run by default, namespace allow-list, provenance schema parity with 201)

## Handoff

- **To Linus (builder):** Wikisource pages written to `data/raw/hawwikisource/fetch.jsonl` in ProvenanceRecord schema
- **Storage contract:** Per-page JSON via MediaWiki API; NFC, ʻokina, and apostrophe canonicalization applied downstream
- **Open points:** Bulk run blocked pending Linus's extracted-text contract refinement; Rusty to tokenizer-fragmentation audit

## Decision inbox

- `frank-wikisource-split.md` — formal contract and trade-offs documented
