# Session Log: Prototype docs reframe and model-choice rationale

**Date:** 2026-04-29T03:58:26Z  
**Topic:** Reframe docs as prototype/learning project; capture base-model and training rationale  
**Requested by:** yashasg  
**Coordinator:** Copilot

## Agents Spawned

1. **Danny (Lead / Architect)** — background  
   - Reframed `README.md`, `docs/training-pipeline.md`, `docs/data-pipeline.md` as learning-prototype only.
   - Decision inbox: `danny-prototype-scope-docs.md`.

2. **Rusty (NLP Researcher)** — sync  
   - Explained base-model choice: Llama-3.1-8B primary, Qwen2.5-7B fallback, Qwen2.5-0.5B smoke.
   - No new decision.

3. **Basher (Training Engineer)** — sync  
   - Explained training/compute: 7B/8B + QLoRA fits prototype budget; free-tier chaining acceptable per user directive.
   - Tokenizer hashes protect provider-switch safety.
   - No new decision.

## User Directives Captured

- **2026-04-29T03:53:18Z:** Free GPU provider chaining acceptable; provider API names may change when switching.
- **2026-04-29T03:54:03Z:** Document as prototype and learning project, not release effort.

## Outcomes

- **Files modified:** `README.md`, `docs/training-pipeline.md`, `docs/data-pipeline.md` (staged).
- **Decisions inbox:** `danny-prototype-scope-docs.md`, `copilot-directive-2026-04-29T03-53-18Z.md`, `copilot-directive-2026-04-29T03-54-03Z.md`.
- **Next:** Scribe merges inbox → decisions.md, commits, and appends team updates to agent histories.
