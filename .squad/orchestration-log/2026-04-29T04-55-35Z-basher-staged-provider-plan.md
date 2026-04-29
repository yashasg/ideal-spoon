# Orchestration Log: Basher — Staged Provider Plan

**Timestamp:** 2026-04-29T04:55:35Z  
**Agent:** Basher (Training Engineer)  
**Outcome:** Plan approved in shape

## Mandate

Stage 1 + merge + Stage 2 must stay within one stable 60-hour provider window on L4/A10/A100/4090-class GPU, **not T4**.

Provider 1 must complete Stage 0 readiness gates plus a short 7B warmup before 60-hour clock starts.

**60-hour allocation:**
- ~40% Stage 1 (24h)
- ~20% Stage 2 (12h)
- ~25% retries (15h)
- Remainder: setup/gates/merge (9h)

## Status

✅ **Approved in shape** — Provider 1 validates readiness before paid/quota block. Provider 2 holds Stage 1 + Stage 2 on one stable GPU class. Provider 3 is eval-only and reproduces Provider 2 gates first.

## Decision Points

1. **GPU class lock:** A100 40GB or RTX 4090 (RunPod community at $1.19/hr or $0.34–0.44/hr respectively). No T4 during 60-hour window.
2. **Provider 1 (Stage 0):** Kaggle free tier, verify bnb/FA2 wheel cache, test 7B warmup load (6–10 min checkpoint save/push cycle).
3. **Provider 2 (Stage 1 + Stage 2):** RunPod community A100 or 4090 subscription (or Azure spot if credits available). **Single continuous session required.**
4. **Stage 0 → Provider 2 transition:** Checkpoint-bus (HF Hub private repo) must survive provider hop. Validate push/pull before clock starts.
5. **Retry budget:** 15h = ~3 full Stage 1 restarts + 2 Stage 2 retries if convergence wavers. If budget exhausted, call for Provider 3 early.
6. **Merge integration:** Copy trained adapter + tokenizer + normalization spec from Provider 2 to evaluation ground truth before Provider 3 reads.

## Readiness Gates (Provider 1)

- ✅ Tokenizer builds without error on Kaggle Python + PyTorch 2.4+.
- ✅ 7B model loads in NF4 + grad-ckpt + FA2 with <15 GB VRAM (test on T4).
- ✅ One 10-min micro-batch training step completes without CUDA OOM.
- ✅ HF Hub checkpoint push (adapter + optimizer state + RNG) succeeds in <2 min.
- ✅ HF Hub checkpoint pull from saved state restores loss curve continuity (1–2 step deviation acceptable).

## Next Actions

1. **Basher:** Execute Stage 0 on Kaggle + verify gates.
2. **Rusty:** Freeze eval suite and gate pass/fail spec (see sibiling log).
3. **All:** Await Provider 1 green light before committing to Provider 2 paid hours.
