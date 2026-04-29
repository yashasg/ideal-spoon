# Provider-Switching Plan for Free-Tier Sequential QLoRA Training
## Orchestration Log · 2026-04-29T04:46:49Z

**Requested by:** yashasg  
**Agent:** Basher (Training Engineer)  
**Agent ID:** basher-provider-switch-plan  
**Mode:** Sync

---

## Outcome Summary

HF Hub is the right artifact/checkpoint bus, but pushing/pulling model files is not enough. Portable unit must include:

- adapter
- optimizer
- scheduler
- RNG (random number generator state)
- dataloader position
- trainer_state
- env.lock
- base model SHA
- tokenizer SHA

### Key Seams Identified

1. **CUDA/bitsandbytes kernel drift** — kernels differ across providers
2. **GPU dtype and FA2 differences** — flashy attention 2 compatibility
3. **Global batch preservation** — maintaining effective batch size across provider hops
4. **Eval harness drift** — evaluation metrics may shift with hardware
5. **Paths/secrets** — config files contain provider-specific credentials

### Provider-Hopping Classification

- **Acceptable:** Prototype/Stage 1 work (proof-of-concept)
- **Not recommended:** Release-candidate/gate-close runs (single stable provider required)

---

## Status

Manifest processed. All artifacts staged for team awareness.

**Related files may be touched:**
- `.squad/agents/basher/history.md`

---

**Scribe Entry Created:** 2026-04-29T04:46:49Z
