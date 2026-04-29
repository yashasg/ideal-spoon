# Orchestration Log — Linus (Data Engineer)

**Timestamp:** 2026-04-29T05:50:27Z  
**Agent:** Linus  
**Topic:** Hawaiian data-source URL inventory and storage format guidance  
**Status:** Completed  
**Outcome:** Success  

## Deliverables

1. **`docs/data-pipeline.md` — Storage formats subsection**
   - Added concise "Storage formats" subsection after Cross-stage invariants, before Stage 1
   - Per-layer format table covering all pipeline layers:
     - URL inventory (JSON, in git)
     - Raw web fetch (WARC `.warc.gz`)
     - Raw non-HTML originals (native bytes, sha256-named, `fetch.jsonl` sidecar)
     - Extraction/intermediate (gzipped JSONL, one per doc/page)
     - Stage 1 manifest (Parquet, zstd)
     - Stage 1 training text (gzipped JSONL)
     - Stage 1 packed/tokenized (`.bin`/`.npy` + `index.json`)
     - Stage 2 manifest (Parquet, zstd)
     - Stage 2 training text (gzipped JSONL, two directional rows + retention slice)
     - Eval/contamination ledger (Parquet, zstd)
     - Schemas (JSON Schema, in git)

2. **Format rules locked:**
   - Parquet for manifests/hashes, JSONL for trainer-facing text
   - Gzip (`.jsonl.gz`) for text >few MB; zstd for Parquet
   - One file per (source, fetch_date) at raw/extracted layers; re-fetches create new dirs
   - No CSV past bootstrap (quoting/encoding eats Hawaiian diacritics)
   - Hashes are cross-layer join keys, never paths
   - Manifest fields stay out of training JSONL lines
   - Nothing in `data/` is committed to git; only URL inventory and schemas in-repo

3. **`.squad/agents/linus/history.md`**
   - Updated with 2026-04-29 storage formats consolidation entry
   - Documented format table, rules, and integration with adapter contract

4. **`.squad/decisions/inbox/linus-storage-formats.md`**
   - Decision proposal with format table and non-decisions (deferred items)
   - Consequences: single adapter contract, tooling coverage check, promotion path

## Coordination Notes

- **For Frank:** URL inventory JSON is the manifest seed; every entry already has provenance fields adapters must capture, plus `tos_or_license_url` to snapshot at fetch time
- **For adapters:** Single contract: read URL inventory JSON → write WARC + `fetch.jsonl` → emit `extracted/*.jsonl.gz` → manifest validator writes Parquet row
- **Tooling:** `warcio`, `scrapy-warc`, `trafilatura`, `selectolax`, `datasketch` already in `requirements.txt`; `pyarrow` to be added when manifest validator lands

## Quality Checks

✓ Format table covers all pipeline layers  
✓ Format rules are hashable, enforceable at dataloader level  
✓ Adapter contract is single and clear  
✓ Tooling coverage verified against `requirements.txt`  
✓ No CSV after bootstrap (diacritics preserved via Parquet)  
✓ Promotion path supports release-eligible transition without re-encode  

## Known Non-Decisions (Deferred)

1. Raw archive storage location (local disk vs. cheap blob) — Livingston cost input pending
2. Parquet compression codec (zstd default; revisit only if tool incompatibility surfaces)
3. Sharding strategy for `stage1.jsonl.gz` / `stage2.jsonl.gz` — flat single file until size forces it
