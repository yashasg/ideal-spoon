# Orchestration Log: Rusty — Stage 1 Corpus-Size Sufficiency (2026-04-29T06:13:58Z)

**Agent:** Rusty (NLP Researcher)  
**Outcome:** Approved (advisory, no new ADR)  
**Request:** Whether 2.5M–7M cleaned Hawaiian tokens (right-clearable, open-license sources) are sufficient for Stage 1 without rights-review-heavy work.

## Headline

2.5–7M cleaned Hawaiian tokens is **sufficient for a meaningful Stage 1 smoke/prototype** on a 7B–8B multilingual base via QLoRA. It is **not** sufficient to expect strong DAPT adaptation across registers.

- 2.5M = smoke-only territory (≤2 epochs).
- 7M + 2–3 epochs ≈ 20M training tokens = reasonable QLoRA Stage-1 budget without overfitting.
- Published rule-of-thumb floor for robust DAPT: ~100M tokens; meaningful partial gains observable from ~10M; below ~10M frames as *pipeline + tokenizer + adapter validation*, not quality claim.

## Risks: Stage 1 Mostly hawwiki + Wikisource (+ small long tail)

1. **Register skew:** Wiki/Wikisource = encyclopedic + literary/PD-archaic. No news, conversational, contemporary. Stage 2 eval will underestimate model capability on held-out contemporary text. **Mandatory:** per-source/per-register slicing in eval.

2. **Memorization risk:** hawwiki globally available; 7B base may have partial coverage. Causal-LM loss drops fast while model partly recognizes, not learns. **Mandatory:** train↔eval n-gram overlap check + held-out *contemporary* slice not on open web.

3. **Tokenizer-audit signal narrow:** Wiki text cleaner than nūpepa; ʻokina/kahakō coverage in hawwiki inconsistent. Audits on wiki-only will *underestimate* real-world fragmentation and *overestimate* base tokenizer competence. **Mandatory:** audit must include small representative non-wiki sample even if not trained on.

4. **Eval uncertainty:** Single-number Hawaiian PPL near-meaningless at this scale/register. **Mandatory:** slices (source, register, diacritic density, length) and dual chrF (as-is + normalized).

5. **Catastrophic forgetting:** Stage 1 can degrade English even at 2.5–7M tokens. **Mandatory:** keep 1–5% English retention mix + monitor English PPL regression.

6. **Audit/provenance is cleaner:** hawwiki (CC-BY-SA) + Wikisource (PD/CC) + reviewed long tail = cleanest releasable-license posture. Matters for publication-guard story even in prototype-only context.

## Minimum Recommended Path (Avoids Rights-Review-Heavy nūpepa)

### Train
- Stage 1 QLoRA on the **full 7M-token tier** (use 2.5M tier only for 0.5B smoke).
- 2–3 epochs max; freeze tokenizer; record base+tokenizer SHA.
- Keep 1–5% English mix.
- Run Stage 0 smoke on Qwen2.5-0.5B end-to-end first.

### Measure (Load-bearing metrics)
- Tokens/word, byte-fallback rate, ʻokina U+02BB survival, kahakō retention (pre/post).
- Hawaiian held-out PPL on a **non-wiki held-out slice** (this is the anchor number).
- English PPL regression vs. base (forgetting check).
- Train↔eval n-gram overlap → recompute PPL after stripping overlapping n-grams (memorization check).
- Per-source / per-register PPL slices (encyclopedic vs. PD-archaic vs. long-tail).
- Stage-2 chrF (both directions, dual as-is/normalized) even if Stage-2 is smoke-only.

### Trigger Conditions to Add More Data (i.e., bite rights-review bullet on nūpepa)
Any **one** of these → Stage 1 is corpus-bound; next move is more Hawaiian text, not more compute:
- Non-wiki held-out PPL fails to improve materially over base.
- Stage-2 chrF gain dominated by encyclopedic-register slice; collapses on news/contemporary.
- Memorization check: large PPL drop after n-gram strip (gain was recognition, not learning).
- Tokenizer audit on non-wiki sample shows fragmentation unfixable with adapter-only training (would require embedding/lm_head unfreeze + more diverse pretraining text).

## Decision

**Approved operationally.** This advisory operationalizes the existing two-stage ADR and eval-pipeline docs; no durable team-wide decision is being changed. Frame Stage 1 as *pipeline + tokenizer + adapter validation* with honest slices, not "we trained a Hawaiian model." Plan the trigger conditions now so the decision to add nūpepa later is data-driven, not vibes-driven.

## References

- `.squad/agents/rusty/history.md` § 2026-04-29 — Stage 1 corpus-size sufficiency (lines 153–188)
- `.squad/decisions.md` § Two-stage training plan (ADR)
- `.squad/decisions.md` § Eval-pipeline specification (ADR)
