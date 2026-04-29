# Session Log: Staged Provider Plan — Three-Provider Validation Chain

**Timestamp:** 2026-04-29T04:55:35Z  
**Scribe:** Scribe (Session Logger)  
**Topic:** Three-provider staged plan for free-tier prelim validation, 60-hour training block, final eval provider

## TL;DR

**Approved.** Provider 1 (Kaggle free) validates Stage 0 gates + 7B warmup. Provider 2 (RunPod A100/4090) trains Stage 1 + Stage 2 in one 60-hour continuous block. Provider 3 (eval-only) reproduces Provider 2's final gate numbers before full eval. Frozen ground truth (base SHA, tokenizer, corpus, eval suite) set by Provider 1 before paid clock starts.

## Three-Provider Boundaries

| Provider | Role | GPU | Duration | Responsibility |
|---|---|---|---|---|
| **1 (Kaggle)** | Prelim + gates | T4×2 or P100 | ~6–10h | Stage 0 readiness, 7B warmup load test, freeze ground truth, validate checkpoint-bus |
| **2 (RunPod/Azure)** | Training | A100 40GB or 4090 | **60h continuous** | Stage 1 (24h) + merge (9h) + Stage 2 (12h) + retries (15h), gate eval every 30 min |
| **3 (Eval-only)** | Full eval + human | Any | ~20–30h | Reproduce Provider 2 final gate, then slicing + human + generalization |

## Gate Sequence

```
Provider 1 Stage 0 gates ✅
   ↓
Provider 1 freeze ground truth (SHAs: base, tokenizer, corpus, eval, hashes, normalization)
   ↓
Provider 2 Stage 1 start (clock begins)
   ├─ micro-gates every ~2h (loss slope, throughput, no NaN)
   ├─ Stage 1 → Stage 2 gate (loss within threshold, checkpoint saved)
   └─ Stage 2 finish gate (final loss within threshold, adapter merged)
      ↓
Provider 3 reproduce Stage 1 final eval (±2% tolerance)
   ├─ IF reproduces ✅ → proceed to full eval slicing + human + generalization
   └─ IF diverges ✗ → escalate to Basher + Rusty, do NOT proceed to full eval
```

## Budget Allocation (60 hours)

- Stage 1: 24h (40%)
- Stage 2: 12h (20%)
- Retries: 15h (25%)
- Setup + merge + gates: 9h (15%)

## Success Criteria

1. ✅ Provider 1 Stage 0 gates all green.
2. ✅ Provider 2 trains in one continuous session, no hard stops.
3. ✅ All Provider 2 micro-gates pass (loss trend, throughput, no divergence).
4. ✅ Provider 3 reproduces Provider 2 Stage 1 final eval within ±2%.
5. ✅ Provider 3 delivers full eval report + human preference judgments.

## Orchestration Notes

- **Checkpoint-bus reliability is critical:** HF Hub push/pull must survive provider hops. Validate in Provider 1 Stage 0.
- **Frozen ground truth is immutable:** No base-model refactor, no tokenizer tuning, no corpus rebuild during training.
- **Stage 1 → Stage 2 merge happens on Provider 2:** Adapter weights merged into base at the 24h mark; SFT stage trains the merged model.
- **Provider 3 reproducibility gate is mandatory:** If Provider 3 cannot reproduce Provider 2 numbers, the eval is suspect and must be re-run or escalated.

## Open Items

None. Plan is approved and ready for execution.

---
*Recorded by Scribe at 2026-04-29T04:55:35Z. Ground truth frozen by Rusty. Training plan approved by Basher. Eval contract approved by Rusty.*
