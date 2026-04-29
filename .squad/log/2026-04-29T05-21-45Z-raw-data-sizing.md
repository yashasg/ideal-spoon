# Session Log: Raw Data Gathering & Training-Set Sizing

**Date:** 2026-04-29  
**Timestamp:** 2026-04-29T05:21:45Z  
**Topic:** Raw data gathering strategy and reasonable training-set size for Hawaiian LLM prototype  

## Summary

Two-agent advisory phase (Linus + Rusty) on Stage 1 monolingual + Stage 2 bidirectional data volumes, gathering order, and quality gates.

**Linus outcome:** Recommended source order (hawwiki/Wikisource → pinned Bible → Ulukau nūpepa pilot → bulk nūpepa). Stage 1 target roughly 10–30M cleaned Hawaiian tokens (5M floor, ~50M ceiling). Stage 2 target 10k–30k verified pairs minimum (20–50k better). Capture unrecoverable manifest metadata at fetch time; pilot ~5–10k nūpepa pages before bulk commit.

**Rusty outcome:** Stage 1 tiers: smoke 0.5–1M, minimal viable 3–10M, better 15–40M, diminishing returns >40–50M. Stage 2 tiers: smoke 2–5k pairs, minimal 20–50k, better 80–150k. Quality/diversity and tokenizer audit matter more than raw volume. Carve out held-out eval before training.

**Flagged for later:** Linus/Scribe add "raw-collection volume targets" subsection to docs/data-pipeline.md. Rusty: per-source slicing + normalized chrF dual-report as formal gate? Open team gaps: cultural-review owner, Hawaiian-literate alignment spot-checker, pinned Bible edition decision, raw archive storage.

## Next Actions

- Linus: Launch nūpepa pilot (~5–10k pages) + tokenizer audit + go/no-go report
- Rusty: Finalize tokenizer audit spec + QLoRA falsification plan for 0.5B/1B smoke  
- Scribe: Append volume-guidance subsection to docs/data-pipeline.md
- Coordinator: Escalate cultural-review owner + alignment spot-checker role assignment
