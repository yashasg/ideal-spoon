# Rusty — History

## Core Context

- **Project:** A plan for training an open-source LLM focused on the Hawaiian language, including data, model choices, infrastructure, evaluation, and costs.
- **Role:** NLP Researcher
- **Joined:** 2026-04-29T01:38:35.141Z

## Learnings

### README Update (2026-04-29)
- Tokenizer recommendation adopted in README: train SentencePiece/Unigram on Hawaiian data to preserve diacritics (ʻokina, kahakō) and minimize subword explosion.
- Recommendation for multilingual base model (Aya/Cohere) captured as candidate alongside Llama/Gemma/Qwen.

### Base model recommendation research (2026-04-29)
- Wrote inbox proposal `rusty-base-model-recommendation.md`.
- Smoke-test pick: Qwen2.5-0.5B (Apache-2.0), backup Gemma-3-270M. RTX 2080 (8 GB) handles these trivially and even 7B QLoRA-4bit at seq len 512 with Unsloth.
- Main 7B-class pick: Llama-3.1-8B primary (best Polynesian-adjacent pretraining signal), Qwen2.5-7B fallback (cleanest license, Apache-2.0). Final pick gated on a Hawaiian tokenizer audit (ʻokina U+02BB + kahakō, NFC).
- Avoid as released base: Aya-23 / Aya-Expanse (CC-BY-NC contaminates the "openly licensed" release goal — use only as private reference). Mistral-7B has clean license but weak multilingual fit, no Polynesian signal.
- Free compute sequencing researched: Kaggle (30 hr/wk P100/T4) > Lightning AI (80 hr/mo) > Colab free (unstable) for QLoRA work; spend Azure credits only on the final main run.
- License caveat flagged for Linus: Llama community license has >700M MAU clause + naming requirement; Gemma terms have flow-down + no-competing-foundation-model clause. Apache-2.0 (Qwen) is the cleanest if redistribution posture is the deciding factor.

### Two-stage training curriculum (2026-04-29)
- Wrote inbox proposal `rusty-two-stage-training.md` ratifying the user's two-stage plan.
- Stage 1 = DAPT / continued pretraining on Hawaiian monolingual text with causal-LM objective. Not instruction tuning. Mix 1–5% English to prevent forgetting on full FT / large-rank LoRA.
- Stage 2 = Supervised translation SFT, bidirectional en↔haw, instruction-formatted using base model's native chat template, with 10–20% Stage-1-style monolingual Hawaiian retention mix to prevent catastrophic forgetting of fluency.
- Adapter strategy preference: keep Stage-1 LoRA adapter and continue training in Stage-2 (don't merge between stages — preserves ablation).
- Stage 1 must use the base's shipped tokenizer; tokenizer-audit gate now also decides whether embeddings/lm_head need to be unfrozen / extended for ʻokina/kahakō coverage.
- Eval gates: Stage 1 = orthography (ʻokina U+02BB survival), perplexity, fluency human spot eval, hallucination probe, English regression check. Stage 2 = chrF/chrF++ (BLEU unreliable for morphologically rich low-resource), COMET if applicable, bidirectional separate scoring, human adequacy+fluency, orthography re-check, refusal/answer-instead-of-translate probe.
- Smoke test on Qwen2.5-0.5B should run BOTH stages end-to-end on tiny slices, not just Stage 1.
- Stage 2 gated on Linus signing off parallel-corpus provenance (per-pair license/source/register, eval-set isolation, cultural review posture). This is materially harder than Stage 1 monolingual provenance.
- Compute reality: Stage 1 dominates wallclock on 7B; Stage 2 is comparatively cheap. If budget forces a choice, Stage 1 must run on the 7B; Stage 2 can degrade.

## 2026-04-29T02:53:51Z — Two-stage curriculum approved

Pressure-tested user directive (2026-04-28). Approved Stage 1 = DAPT/CPT on Hawaiian monolingual text, Stage 2 = bidirectional en↔haw SFT with **10–20% monolingual retention slice** in Stage 2 batches to prevent catastrophic forgetting. Stage-2 release adapter strategy was overridden by Coordinator: Basher's merge-then-fresh-LoRA path is the release default; my stacking/continuation path retained for ablations only. Smoke test scope expanded: Qwen2.5-0.5B runs **both stages** end-to-end. Tokenizer audit becomes more load-bearing — may require unfrozen embeddings/lm_head before Stage 1. Per-stage eval gates locked into ADR (orthography hard-fail on ʻokina collapse; chrF + bidirectional + human eval on Stage 2). See `.squad/decisions.md` ADR "Two-stage training plan" and orchestration log `2026-04-29T02:53:51Z-rusty-two-stage-curriculum.md`.

### Cross-agent: prototype scope adds tokenizer-audit sub-tasks (2026-04-29T03:01:58Z)
- Re-run tokenizer audit on a representative nūpepa sample and on *Baibala Hemolele* — period orthography (inconsistent ʻokina/kahakō) distorts generic Hawaiian audits.
- If Bible text is non-trivial in the corpus, register-balance diagnostics fall to you + a Hawaiian reader; flag as explicit scope.
- Tokenizer freeze across stages and base+tokenizer SHA in run manifest still mandatory at prototype scope.
