# Orchestration: Linus — Wikisource builder handoff contract

**Time:** 2026-04-29T07:39:07Z  
**Agent:** linus-wikisource-handoff (background, claude-opus-4.7)  
**Directive:** Add Stage-1 dataset builder support for Wikisource page-text records

## Outcome

✅ **COMPLETE**

- Added `extract_wikisource_pages` + `_coerce_page_dict` helper to `scripts/301_build_stage1_dataset.py`
- Builder dispatches on content shape (`wiki-xml-stream` vs `wikisource-pagetext`) not source name
- Factored doc-emit path into `_emit_pages` so both extractors share normalization/scoring/split path
- Existing hawwiki XML extractor and token-volume gate remain untouched
- Updated `docs/data-pipeline.md` with extraction method enum and handoff details
- Validated existing hawwiki output unchanged; full integration gated pending extraction refinement

## Handoff

- **From Frank (fetcher):** per-page JSON via `data/raw/hawwikisource/fetch.jsonl`
- **Contract:** ProvenanceRecord schema identical to 201 (dump path); content-shape dispatch eliminates source-specific branching
- **Downstream refinement:** ʻokina, NFC, apostrophe canonicalization; de-wiki template handling needs tokenizer audit

## Decision inbox

- `linus-wikisource-handoff.md` — formal extraction contract and de-wiki caveats documented
