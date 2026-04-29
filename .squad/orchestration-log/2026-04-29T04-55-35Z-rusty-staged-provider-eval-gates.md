# Orchestration Log: Rusty — Staged Provider Eval Gates

**Timestamp:** 2026-04-29T04:55:35Z  
**Agent:** Rusty (NLP Researcher)  
**Outcome:** Provider 1 freeze + Provider 2 gate spec + Provider 3 reproducibility contract

## Mandate

Provider 1 must freeze training-ready bundle before paid clock starts:
- Base SHA (model)
- Tokenizer SHA
- Corpus manifest SHA
- Eval-suite SHA
- eval_hashes SHA
- Normalization spec

Provider 2 runs cheap per-checkpoint eval and stage gates.

Provider 3 runs full slicing/human/generalization eval after reproducing Provider 2 gate numbers within tolerance.

## Status

✅ **Spec approved** — Three-provider eval chain with freeze gates and reproducibility contract.

## Frozen Ground Truth (Provider 1)

**Must be set before Basher Stage 1 clock starts:**

- `BASE_MODEL_SHA`: Qwen2.5-7B (or chosen base). Immutable for entire 60-hour run.
- `TOKENIZER_SHA`: Committed to `.squad/tokenizer/` or HF Hub pinned revision.
- `CORPUS_MANIFEST_SHA`: `.squad/data/corpus-manifest.json` with train/val/test split SHAs.
- `EVAL_SUITE_SHA`: `.squad/eval/suite-*.py` (baseline, per-checkpoint, stage gates).
- `EVAL_HASHES_SHA`: `.squad/eval/eval-hashes.json` (known-good reference outputs for 0.5B/1B smokes, base model zero-shot).
- `NORMALIZATION_SPEC`: Loss scaling, grad clipping, learning rate schedule, LoRA rank. Locked in `training-config.json`.

**Responsibility:** Rusty commits these, Basher validates against it during Stage 0 warmup.

## Provider 2 Eval Gates (per-checkpoint)

Basher logs checkpoint eval metrics to HF Hub repo every 30 min:

1. **Stage 1 micro-gates (every ~2h):**
   - Loss trend: slope > -0.1 (loss is decreasing).
   - Throughput: >500 tokens/sec (sanity check for OOM creep).
   - No CUDA divergence (loss NaN / OOM).

2. **Stage 1 → Stage 2 gate:**
   - Final Stage 1 eval loss < baseline + 0.15 nats.
   - Adapter saved + checkpoint-bus push succeeds.

3. **Stage 2 micro-gates:**
   - Loss slope > -0.05 (SFT is still converging).
   - Throughput >800 tokens/sec (lighter batch).

4. **Stage 2 finish:**
   - Final loss < Stage 1 loss + 0.20 nats.
   - Adapter saved, merged checkpoints on HF Hub.

**Gate pass/fail:** Binary (green/red). If any gate fails, trigger 1h retry or call Provider 3 early.

## Provider 3 Reproducibility Contract

**Pre-eval requirement:**

1. **Reproduce Provider 2 Stage 1 finish eval** using frozen ground truth:
   - Same base SHA, tokenizer, corpus manifest, normalization spec.
   - Pull adapter from HF Hub (Provider 2 checkpoint).
   - Run eval-suite on the merged model.
   - **Tolerance:** ±2% eval metric variance (loss ±0.05 nats, accuracy ±1 pp).

2. **If reproducibility fails:**
   - Document which component changed (CUDA version? PyTorch minor version? HF transformers commit?).
   - Do NOT proceed to full slicing/human/generalization eval.
   - Escalate to Basher + Rusty for triage.

3. **If reproducibility passes:**
   - Run full eval slicing (by length, by domain, by task).
   - Collect human preference judgments (if budget allows).
   - Compute generalization metrics (OOD test sets).

## Next Actions

1. **Rusty:** Commit ground-truth SHAs to `.squad/eval/` and `training-config.json`.
2. **Basher:** Validate during Stage 0 warmup, confirm frozen bundle before Stage 1 starts.
3. **Provider 2 (during Stage 1):** Log eval metrics per 30-min checkpoint to HF Hub.
4. **Provider 3 (after Provider 2 finish):** Reproduce Stage 1 eval within tolerance, then proceed to full eval.

## Success Criteria

- ✅ All Provider 1 readiness gates pass (Basher log).
- ✅ Provider 2 trains both stages within 60h budget, all micro-gates green.
- ✅ Provider 3 reproduces Provider 2 Stage 1 final eval within ±2%.
- ✅ Provider 3 delivers full eval report with human preference + generalization metrics.
