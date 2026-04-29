# Orchestration Log: Linus (Data Engineer) — Raw Data Sizing & Gathering Order

**Agent ID:** linus-raw-data-sizing  
**Timestamp:** 2026-04-29T05:21:45Z  
**Requester:** yashasg  
**Status:** Complete  

## Task

Advisory on raw data gathering strategy and volume targets for Hawaiian LLM prototype (both Stage 1 monolingual and Stage 2 bidirectional SFT).

## Outcome Summary

**Stage 1 (Hawaiian monolingual CPT/DAPT) — cleaned token targets:**
- **Floor:** ~0.5–1M tokens (smoke/Qwen2.5-0.5B end-to-end validation)
- **Minimal viable:** ~3–10M tokens (7B QLoRA Stage 1 baseline, register-balanced, Bible/religious-archaic ≤10%)
- **Better:** ~15–40M tokens (real register diversity, news/nūpepa/contemporary/encyclopedic/Wikisource/dictionary)
- **Diminishing returns:** >40–50M tokens

**Stage 2 (bidirectional en↔haw SFT) — cleaned pair targets:**
- **Floor:** ~2–5k verified pairs (smoke, sentence-aligned, eval-isolated)
- **Minimal viable:** ~20–50k verified pairs (Bible ≤30% train, 0% eval; bidirectional symmetric balance)
- **Better:** ~80–150k pairs (≥3 source families, optional BT ≤25% train/0% eval)

**Gathering order (quality-first ranking):**
1. Hawaiian Wikipedia + Wikisource dump (CC-BY-SA 4.0, low OCR noise, modern register, pipeline validator)
2. Representative nūpepa sample (~50 docs, 1860–1940) for OCR quality audit *before* bulk ingest
3. Baibala Hemolele (pinned edition) + English KJV/ASV verse-aligned (Stage-2 core, capped ≤30%)
4. Pukui-Elbert / Andrews dictionary examples (lexical diversity + orthography coverage)
5. **Bulk nūpepa OCR only after (1)–(4) prove pipeline** (largest noise risk, most engineering time)

**Critical constraints:**
- **Manifest metadata unrecoverable later:** ToS snapshot per source/date, source_url + fetch-resolved, fetch_date + http_status, sha256_raw, license_observed verbatim, source-specific IDs (Ulukau paper+issue+page, Bible edition+translator+year, OPUS subset+version, etc), cultural_flag pre-tagged, prototype_only=true default
- **Held-out eval (carve out before training):** ≥200k tokens Stage 1; ≥1k pairs dev + ≥1k pairs test Stage 2 (0% Bible, balanced direction/register, cluster-aware split)
- **Quality dominates volume:** 30k clean pairs >> 100k noisy; nūpepa OCR noise (byte-fallback, ʻokina/kahakō survival) is the binding Stage-1 quality constraint; register skew is silent failure
- **Dedup before counting:** Bible/nūpepa reprints inflate raw counts 2–5×; MinHash cluster-aware dedup is the *real* token count
- **Tokenizer fragmentation gates everything:** corpus targets are downstream of tokenizer audit verdict

**Stage-1 nūpepa go/no-go gate:** Pilot ~5–10k pages + run tokenizer audit + token-count report before bulk nūpepa commit. Realistic ceiling on cleaned tokens: 10–30M (5M floor, ~50M aspirational).

**Stage-2 sequencing is hard-gated:** FLORES-200 first → eval_hashes.parquet → Bible verse-aligned → Tatoeba + OPUS haw subsets → NLLB mined → Wiki interlanguage + LaBSE → Awaiaulu/OHA/DOE/UH bilingual. No Stage-2 ingest until Stage-1 artifacts + eval_hashes exist.

## Key Decisions Affirmed

- Data-pipeline.md ceiling (cleaned yield) already correct; raw collection must overshoot due to OCR/dedup/filtering/heldout splits
- Wikipedia (CC-BY-SA) + Wikisource + pinned Bible + Ulukau nūpepa pilot + Awaiaulu/OHA/DOE/UH as the source tier ranking (quality/licensing/engineering risk)
- Prototype lineage tracking (capture metadata at fetch, tag everything prototype_only=true, do not publish weights without data clearance)

## Flagged for Later Action

- **Linus/Scribe:** Add "raw-collection volume targets" subsection to docs/data-pipeline.md capturing gathering-order rule, volume ranges, Stage-1 nūpepa-pilot go/no-go gate
- **Open gaps:** Cultural-review owner (unassigned), Hawaiian-literate alignment spot-checker, pinned Bible edition decision, raw archive storage location

## References

- `.squad/decisions.md` — Stage 1 + Stage 2 ADRs, two-stage data gates, manifest schema, contamination guard
- `docs/data-pipeline.md` — Stage 1 monolingual + Stage 2 bidirectional schemas, normalization, dedup, risks, next steps
- `.squad/agents/linus/history.md` — Prior advisories (data-posture reframe, Stage-2 pipeline, volume targets)
