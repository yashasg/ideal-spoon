# Orchestration Log: Rusty (NLP Researcher) — Training Data Sizing & Quality Framework

**Agent ID:** rusty-training-data-sizing  
**Timestamp:** 2026-04-29T05:21:45Z  
**Requester:** yashasg  
**Status:** Complete  

## Task

Advisory on training data sizing, quality metrics, and stage gates for Hawaiian LLM prototype (Stage 1 monolingual + Stage 2 bidirectional SFT).

## Outcome Summary

**Stage 1 (monolingual Hawaiian CPT/DAPT) — token tiers by goal:**
- **Smoke tier (validation):** 0.5–1M cleaned tokens (Qwen2.5-0.5B end-to-end, catches pipeline bugs, exercises tokenizer/normalization)
- **Minimal viable prototype:** 3–10M cleaned tokens (7B QLoRA Stage 1, expect overfitting + register collapse below ~3M)
- **Better prototype:** 15–40M cleaned tokens (register diversity, real lexical spread, measurable DAPT signal)
- **Diminishing returns:** >40–50M tokens (tokenizer fragmentation + register skew dominate, sub-linear gains on 7B LoRA)

**Stage 2 (bidirectional en↔haw SFT) — pair tiers by goal:**
- **Smoke tier:** 2–5k verified sentence-aligned pairs (eval-isolated)
- **Minimal viable prototype:** 20–50k verified pairs (Bible ≤30% train, 0% eval; bidirectional symmetric)
- **Better prototype:** 80–150k pairs (≥3 source families, optional BT ≤25% train/0% eval)
- **Constraint:** Pair *quality* (alignment correctness, register coverage, no leakage) >> pair count

**Quality/diversity priorities (matter more than volume):**
1. **Tokenizer audit before everything:** ʻokina U+02BB survival, kahakō retention, byte-fallback rate, tokens/word on representative Hawaiian sample (nūpepa + Baibala + contemporary). Final corpus-size target depends on audit verdict.
2. **Register balance carving:** Track Bible/religious-archaic (cap ≤10% Stage 1, ≤30% Stage 2 train, 0% eval), news/nūpepa, contemporary, encyclopedic separately; recompute per-checkpoint register distribution.
3. **OCR quality dominance:** nūpepa pre-1900 byte-fallback + ʻokina/kahakō survival on raw OCR is the binding Stage-1 constraint. 30M tokens at 60% OCR quality < 10M tokens clean.
4. **Dedup + heldout carving before counting:** MinHash cluster-aware split isolation; Bible/nūpepa reprints inflate counts 2–5×; build eval_hashes.parquet before any training run.

**Held-out eval (build before training, not after):**
- **Stage 1:** ≥200k cleaned tokens, stratified by source/register, cluster-aware split (no near-dupes across train/dev/test)
- **Stage 2:** ≥1k pairs dev + ≥1k pairs test, 0% Bible, balanced by direction and register, document-cluster isolation

**Diagnostic slicing framework (applies to every regression):**
- By orthography (chrF as-is vs normalized — if gap collapses, it's diacritic handling, not translation)
- By source/register (Bible vs news vs contemporary vs encyclopedic)
- By direction (haw→en vs en→haw)
- By tokenization (output re-audit for ʻokina/kahakō fragmentation)
- By length and diacritic density
- By OCR confidence (nūpepa-specific patterns)
- By train vs dev gap (overfitting signal per source)
- Slicing > single global metric for low-resource Hawaiian

## Key Decisions Affirmed

- **Multilingual prior matters:** Llama-3.1-8B (Polynesian signal) primary over Llama-only bases; tokenizer audit is the deciding gate
- **QLoRA falsification plan:** 0.5B/1B smoke with fp16-LoRA vs 4-bit NF4, matched seed/data/tokenizer/eval; if gap is non-trivial on Hawaiian PPL/chrF, revisit 7B recipe
- **No single global metric:** Per-source + orthography dual-report (as-is/normalized chrF) mandatory; evaluation slicing axis audit before reporting headline numbers

## Flagged for Later Action

- **Per-source slicing + normalized chrF dual-report:** Should this be promoted from diagnostic to formal stage gate? Currently advisory.
- **Hawaiian-literate alignment spot-checker:** Needed for threshold tuning on embedding-alignment (LaBSE/LASER) during Stage-2 pipeline; culturally-grounded judgment of when "close enough" is actually close.

## References

- `.squad/decisions.md` — Two-stage training plan, base-model recommendation, model-choice rationale ADR
- `docs/eval_pipeline.md` — Durable eval methodology, cadence, metrics, diagnostic framework, attribution matrix, QLoRA falsification
- `docs/training-pipeline.md` — Stage 1 + Stage 2 training recipes (cross-linked with eval_pipeline)
- `.squad/agents/rusty/history.md` — Prior syncs on model choice, quantization-loss framing, eval-loop diagnostics, three-provider sequencing
