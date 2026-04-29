# Session Log: FineWeb-2 Checkpoint Eval Reuse Question

**Timestamp:** 2026-04-29T09:59:05Z

## Summary

Rusty answered the FineWeb-2 test-split reuse question. **Outcome: yes, with hard constraints.**

**Key decision:**
- FineWeb-2 test (887 rows) can be used for checkpoint monitoring/dev signal during Stage 1
- **Hard constraint 1:** Dedupe against FineWeb-2 train set (95k rows) via exact hash match
- **Hard constraint 2:** Frozen split: ~80% dev, ~20% holdout (never touched for tuning)
- **Hard constraint 3:** Pair with independent Stage-0 sources (FLORES, UDHR, Taxi1500) to avoid FineWeb-only overfitting

**Blocking resolved:** Linus can now proceed with dedupe + frozen-split logic in the Stage-0 harness.

Full decision in orchestration log: `.squad/orchestration-log/2026-04-29T09-59-05Z-fineweb2-checkpoint-eval.md`

**Cross-agent follow-up:** Notes appended to Rusty and Linus histories with FineWeb-2 train-test dedupe + frozen holdout requirement.
