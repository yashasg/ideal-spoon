# Linus — Raw to Training Data Pipeline Plan

**Agent:** Linus (Data Engineer)  
**Mode:** sync  
**Requested by:** yashasg  
**Timestamp:** 2026-04-29T06:43:21Z  

## Task

Plan the ordered workflow from raw fetch (Frank's responsibility: rights-light sources) through Stage 1 training dataset, including extraction, normalization, language identification (LID), deduplication, validation, and handoff to downstream consumers (tokenizer audit, Rusty's training pipeline, Basher's infrastructure).

## Outcome

✅ **Complete workflow documented.** No repo edits required.

### Pipeline stages (ordered):

1. **Raw Fetch** (Frank responsibility)
   - Sources: hawwiki dump, Hawaiian Wikisource, pinned Bible edition, Ulukau nūpepa (with OCR confidence thresholding), Awaiaulu/OHA/DOE/UH bilingual PDFs, Tatoeba, FLORES, OPUS haw subsets.
   - Fetch artifacts: WARC per source, source URL, fetch date, HTTP status, sha256_raw, ToS snapshot per source/date.
   - Volumes: **10–30M raw Hawaiian tokens realistic; 5M floor; ~50M aspirational.**

2. **Raw Registration & Manifest Bootstrap** (Linus responsibility)
   - Ingest raw files into `stage1_manifest.parquet` schema: `doc_id`, `source_id`, `fetch_date`, `source_url`, `sha256_raw`, `license_observed`, `tos_snapshot_id`, `cultural_flag`, `prototype_only=true`, `release_eligible=false` (defaults).
   - Register every document at fetch time; unrecoverable metadata fields are captured now.
   - No cleanup or filtering yet—manifest is a ledger, not a filter.

3. **Language Identification (LID)** (Linus + Rusty)
   - Run LID on all raw documents; flag non-Hawaiian or mixed-language items.
   - Score each doc: `lid_language`, `lid_confidence`, `lid_mixed=true/false`.
   - Append to manifest: `lid_language`, `lid_confidence`, `lid_mixed`.
   - Hard filter: `lid_language != 'haw'` → `status=excluded_non_hawaiian` (never trained).

4. **Text Extraction** (Linus)
   - HTML/PDF → plain text using `trafilatura` + fallbacks; preserve document boundaries.
   - Metadata fields: `extracted_token_count`, `extraction_method`, `extraction_quality_flag` (confidence score).
   - Append to manifest: `text_extracted`, `extracted_token_count`, `extraction_method`.

5. **Unicode Normalization** (Linus)
   - Normalize to **NFC**.
   - Canonicalize ʻokina to **U+02BB** (combining single quote mark).
   - Preserve kahakō (macron over vowels).
   - Flag any document where normalization fails: `status=excluded_normalization_fail`.

6. **Text Registration Tags** (Linus + Rusty)
   - Per-document register assessment: `register ∈ {archaic, religious, contemporary, formal, colloquial, mixed, unknown}`.
   - For Bible editions: `register=religious`, `edition` + `translator` + `year` stored.
   - For nūpepa: `register=mixed`, `paper_title` + `issue_date` stored.
   - Append to manifest: `register`, `register_source_id` (trace-back to evidence).

7. **Deduplication (MinHash + Cluster-Aware Split Isolation)** (Linus)
   - MinHash (Jaccard ~0.95 threshold) to group near-duplicate documents.
   - Within each cluster, deterministically assign to train/dev/test **before any split**.
   - **Cluster-aware rule:** if any doc in a cluster is held-out (eval), hold out the entire cluster.
   - Append to manifest: `dedup_cluster_id`, `dedup_confidence`, `dedup_is_primary` (0 or 1 per cluster).
   - Remove non-primary docs: `status=excluded_duplicate`.

8. **Tokenizer Audit Gate** (Rusty responsibility)
   - Audit: **ʻokina U+02BB byte-fallback survival, kahakō preservation, tokens-per-word on representative Hawaiian text.**
   - Input: ~5–10k deduplicated Hawaiian documents.
   - Output: `tokenizer_audit_report.json` — ʻokina recovery %, kahakō preservation %, tokens/word distribution, recommendation (proceed / fix tokenizer / choose fallback).
   - **Gate:** if audit fails, loop back to tokenizer fix or fallback model choice (blocking downstream).

9. **Packed Manifest & Validation** (Linus)
   - Finalize `stage1_manifest.parquet`: all fields populated, no nulls in critical columns (`doc_id`, `sha256_raw`, `sha256_clean`, `lid_language`, `split`).
   - Schema validation: run pydantic or similar; fail loudly if schema is violated.
   - Output: `stage1_manifest.parquet` (ready for evaluation contamination guard).

10. **Evaluation Hash Registry** (Linus + Rusty)
    - Extract **evaluation holdout docs** (dev/test split).
    - Compute `sha256_clean` (after dedup/norm/extraction).
    - Register into `eval_hashes.parquet`: `sha256_clean`, `doc_id`, `split ∈ {dev, test}`.
    - **This is the contamination guard:** no doc in `eval_hashes` can appear in any training set.

11. **Stage 1 JSONL Export** (Linus)
    - Convert `stage1_manifest.parquet` train-split docs to `stage1.jsonl.gz`.
    - Schema per row: `doc_id`, `text`, `sha256_clean`, `source_id`, `register`, `extraction_method`, metadata dict.
    - Compression: gzip.
    - Output: `stage1.jsonl.gz` + `stage1_manifest.parquet` (twin artifacts).

12. **CI Guard Setup** (Linus + Basher)
    - Dataloader-level assertion: before any training epoch, assert no row's `sha256_clean` appears in `eval_hashes.parquet`.
    - Stage-2 ingest also checks against Stage-1 eval hashes: `crosslink_stage1_overlap=true` → banned from Stage-2 training.
    - Assertion fires loudly if violated; training halts.

13. **Basher Handoff** (explicit dependency)
    - Linus delivers: `stage1_manifest.parquet`, `stage1.jsonl.gz`, `eval_hashes.parquet`, `tokenizer_audit_report.json`.
    - Basher consumes: loads JSONL for training, asserts CI contamination guard in dataloader, logs token counts to training-infrastructure manifest.

## Key Decisions

1. **Vertical-slice first:** Start with **Hawaiian Wikipedia only** (smallest, cleanest) before adding Wiktionary/Wikisource/Baibala/long tail. Validate entire pipeline on 1 source, then scale.

2. **Corpus payloads local:** All raw/extracted data stays on yashasg's machine (no git blobs, no HuggingFace uploads during prototype).

3. **Rights-heavy sources deferred:** Pre-1925 nūpepa bulk, Baibala/JW300, hard-escalate cultural categories stay off the critical path; optional add-ons with cultural reviewer sign-off.

4. **Manifest-first discipline:** Every field from Frank's fetch is registered immediately; unrecoverable metadata (ToS snapshot, fetch date, source URL) captured at ingest, not rederived later.

5. **Dedup before split:** MinHash clusters are formed, then split decision applied uniformly per cluster — no data leakage via similar-doc memorization.

6. **Tokenizer audit is a gate:** No Stage-1 export proceeds without Rusty's ʻokina/kahakō audit; if audit fails, loop to tokenizer fix or fallback model (blocks downstream).

## Open Gaps Flagged

- **Cultural reviewer:** unassigned. Escalate to Coordinator for Hawaiian-literate cultural-review owner.
- **Bible edition pinning:** which edition(s) to ingest? Rights + register alignment TBD.
- **Raw archive storage:** off-git + encrypted? Staging location TBD.

## Next Steps

1. Frank pulls hawwiki dump → Linus registers into manifest + runs LID.
2. Rusty audits tokenizer on sample.
3. Iterate extraction/norm/dedup pipeline on 1 source.
4. Export Stage-1 JSONL when manifest is complete.
5. Basher sets up CI guard in training loop.
6. Parallel: Stage-2 pipeline design (no ingest until Stage-1 eval hashes locked).

---

**No repo edits in this task.** Plan is a workflow, not code.
