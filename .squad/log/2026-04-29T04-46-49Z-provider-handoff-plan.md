# Session Log: Provider Handoff Plan
## 2026-04-29T04:46:49Z

**Agent:** Basher (Training Engineer)  
**Topic:** Practical provider-switching plan for free-tier sequential QLoRA training

### Key Outcome

HF Hub confirmed as checkpoint bus, but requires portable unit with full state:  
adapter, optimizer, scheduler, RNG, dataloader position, trainer_state, env.lock, base model SHA, tokenizer SHA.

### Critical Seams

- CUDA/bitsandbytes kernel drift
- GPU dtype & FA2 differences
- Global batch preservation
- Eval harness drift
- Paths/secrets management

### Decision

Provider hopping OK for Stage 1. Single stable provider for release-candidates.

### Status

Ready for implementation.
