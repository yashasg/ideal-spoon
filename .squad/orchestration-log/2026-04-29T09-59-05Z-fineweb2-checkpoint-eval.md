# Orchestration: FineWeb-2 Checkpoint Eval Reuse Question — 2026-04-29T09:59:05Z

## Challenge Scope

**Topic:** Can FineWeb-2 `haw_Latn` test split (887 rows) be reused for checkpoint evals during Stage-1 DAPT training?

**Mode:** Sync (Rusty answered via cross-agent note; decision documented for team memory)

## Outcome Summary

**Yes.** FineWeb-2 test split is **safe for checkpoint monitoring/dev signal** with three hard constraints:

1. **Train-test dedupe:** Remove any FineWeb-2 train-set rows (95,507 rows) that overlap with the test split via exact hash match. This is mechanical (MinHash post-filter on ingest).

2. **Frozen dev/holdout split:** Split the 887 test rows deterministically (fixed seed, stratified if possible) into:
   - ~80% (≈710 rows) = checkpoint dev signal — can probe perplexity, orthography, fluency metrics during training
   - ~20% (≈177 rows) = final holdout — **never used for any hyperparameter tuning, metric tracking, or learning-rate decisions**

3. **Pair with independent Stage-0 sources:** FineWeb-2 checkpoint monitoring is **not a substitute for eval-set diversity**. Pair with FLORES-200 `hawn_Latn` (if/when available) and other Stage-0 sources (UDHR, Taxi1500 if available, etc.) to avoid FineWeb-specific overfitting signals.

## Rationale

- **Why test-split reuse is acceptable:** Checkpoint evals measure training diagnostics (learning curves, metric stability) and are not the final benchmark. The risk of implicit hyperparameter leakage (e.g., stopping training because checkpoint loss is "good enough") is managed by the frozen holdout split.

- **Why dedupe is critical:** FineWeb train and test come from the same source pool (deduplicated by FineWeb's pipeline, not separate collections). Without train-test dedupe, the checkpoint signal is contaminated by train-set memorization.

- **Why frozen split matters:** Once dev rows are used for *any* decision (learning rate, early stopping, model selection), they are tainted. The final holdout rows must never be touched until the final freeze.

- **Why Stage-0 diversity matters:** FineWeb alone may exhibit distribution shifts (CCNet filtering, language-model biased crawl, haw_Latn tokenization artifacts). Checkpoint monitoring on FineWeb alone can mask generalization failures.

## Implementation Checklist

- [ ] **Before Stage 1 start:** Load FineWeb-2 full test set (887 rows), dedupe against train hashes, split into dev (≈710) + holdout (≈177) with fixed seed.
- [ ] **During Stage 1 training:** Only probe checkpoint dev rows for metrics; do not update any training decision based on holdout rows.
- [ ] **Stage 1 final reporting:** Report both dev-set metrics (with caveat: "checkpoint monitoring only") and holdout-set metrics (unreleased during training). Report which rows appear in each split for reproducibility.
- [ ] **Stage 2 and beyond:** Holdout rows remain frozen; do not include in Stage-2 dev sets unless explicitly re-approved in a separate ADR.

## Decision Status

- **ADR:** None required (reuse decision is narrow and operationally locked).
- **History updated:** Appended to `.squad/agents/rusty/history.md` and `.squad/agents/linus/history.md`.
- **Next step:** Linus routes dedupe + split logic to Livingston or Basher for implementation in Stage-0 harness setup.

## Cross-Agent Context

- **For Rusty:** FineWeb-2 checkpoint reuse is approved *within these constraints*; do not use holdout rows for any Stage-1 learning-rate decisions.
- **For Linus:** Data-engineering task: implement dedupe + frozen split before Stage-1 harness start.
- **For Basher/Livingston:** Eval harness must track which FineWeb-2 rows are in dev vs. holdout; never leak holdout rows into training loop.
