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

## 2026-04-29T03:58:26Z — Team sync: model-choice rationale captured

**Mode:** Sync (no new decision written)

Scribe requested explanation of base-model rationale for team memory. Confirmed:
- **Primary:** Llama-3.1-8B (contingent on Hawaiian tokenizer audit for ʻokina/kahakō diacritics).
- **Fallback:** Qwen2.5-7B (cleanest license, Apache-2.0).
- **Smoke only:** Qwen2.5-0.5B (catches pipeline bugs).
- **On-hold:** Gemma (pending release updates).
- **Not current fit:** Aya (CC-BY-NC contaminates release goal), Mistral (weak multilingual), from-scratch pretraining.

Rationale aligned with existing ADR in decisions.md. Orchestration log: 2026-04-29T03-58-26Z-rusty.md. Session: 2026-04-29T03-58-26Z-prototype-docs-and-model-choice.md.

## 2026-04-29 — Quantization-vs-bottlenecks framing + eval-loop diagnostics (advisory)

User asked how we're assessing "quantization loss probably smaller than other bottlenecks for Hawaiian," and how we eval / diagnose. Captured as explanation, not a new ADR.

- Framed quantization-loss prior as: published QLoRA NF4 deltas (~0.1–0.4 PPL, ~0–1 chrF on English) + structural argument that Hawaiian-specific bottlenecks (tokenizer fragmentation on ʻokina/kahakō, corpus size/register skew, NFC/orthography normalization, eval leakage) are order-of-magnitude larger + planned cheap empirical check on the 0.5B smoke (fp16 vs 4-bit NF4) before any 7B spend.
- Diagnostic discipline to apply on every regression: slice by orthography (recompute chrF with diacritics normalized on both sides — if gap collapses, it's diacritic handling, not translation), source/register, direction, tokenization (re-audit on outputs), forgetting (Stage 1 PPL after Stage 2), leakage (recompute after n-gram strip), OCR noise (nūpepa-specific patterns), overfitting (train vs dev gap per source), eval-suite drift (harness SHA).
- Headline rule: a single global metric is near-useless for a low-resource Hawaiian model; slices tell you what to fix.
- Open question for the team: should per-source slicing + as-is/normalized chrF dual-report be promoted from diagnostic to formal gate? Currently advisory.

## 2026-04-29 — Eval pipeline doc landed

Wrote `docs/eval_pipeline.md` capturing the durable eval methodology: assessment basis (quantization loss bounded; tokenizer/Unicode/corpus-skew/OCR/forgetting/leakage/weak-eval are the candidate dominant bottlenecks), cadence (pre-training baseline, Stage 0 smoke, per-checkpoint cheap eval, stage gates, post-run analysis), metrics (tokens/word, byte-fallback, ʻokina survival, kahakō retention, Hawaiian held-out PPL, English PPL regression, chrF/chrF++ by direction with as-is/normalized dual report, leakage, hallucination, generalization, human spot eval), Kaggle/free-tier checkpoint-aligned cadence (cheap fixed eval ~30–60 min; full eval at gates only), diagnostic slicing axes (source/register, direction, length, diacritic density, OCR confidence, tokenizer behavior, split, provider handoff), attribution matrix (symptom → likely cause → next experiment), QLoRA falsification plan on 0.5B/1B (QLoRA vs fp16 LoRA vs full FT where feasible, rank sweep, matched seed/data/tokenizer/eval), run-report schema (checkpoint, base/tokenizer/corpus/eval SHAs, stage, train loss, Hawaiian PPL, English PPL delta, orthography, chrF by direction, slices, notes), and explicit non-goals (not release certification, not fluency claim, not human-review replacement, not benchmarking).

Linked from README "Evaluation" section and `docs/training-pipeline.md` References section. No new ADR; the doc operationalizes existing decisions and the prior advisory framing — no decision-inbox file written.

## 2026-04-29 — Model-choice rationale (full capture, prior sync was thin)

User flagged that the earlier 03:58:26Z sync recorded the *picks* but not the *reasoning* — backfilling here so Danny's implementation plan and team memory have it.

**Working plan (unchanged from ADR, restated for clarity):**
- **Primary:** Llama-3.1-8B — contingent on tokenizer audit (ʻokina U+02BB + kahakō, NFC, byte-fallback rate, tokens/word). Best Polynesian-adjacent pretraining signal among open 7B–9B bases; multilingual prior reduces the amount of Stage-1 data needed to move the needle.
- **Fallback:** Qwen2.5-7B — Apache-2.0 (cleanest license posture for "publish weights+tokenizer openly"), strong multilingual coverage, used if Llama tokenizer audit fails or license posture becomes the deciding factor.
- **Smoke only:** Qwen2.5-0.5B — pipeline validator (data → tokenizer → QLoRA → eval) on RTX 2080 / Kaggle. Runs both Stage 1 and Stage 2 end-to-end. Not a release candidate.
- **Held option:** Gemma-2-9B — kept in reserve. License flow-down + no-competing-foundation-model clauses make it less attractive as the released base, but it's a real fallback if both Llama and Qwen audits regress.
- **Excluded as released base:** Aya / Aya-Expanse — CC-BY-NC contaminates the openly-licensed-release goal; usable only as private reference / silver-data generator.
- **Excluded:** Mistral-7B — clean Apache-2.0 but weak multilingual fit and no Polynesian signal; tokenizer expected to fragment Hawaiian harder than Llama/Qwen/Gemma.
- **Rejected:** From-scratch pretraining — incompatible with prototype budget and Hawaiian corpus size; no plausible path to a usable model under the available compute and data.

**Why this plan beats the alternatives for *this* prototype:**
1. **Multilingual prior matters more than English-only quality** at this scale. A base that has *seen* Polynesian/Austronesian-adjacent text during pretraining transfers faster on a small Hawaiian corpus than a stronger English-only base.
2. **7B–8B is the right capacity band.** Big enough to carry continued pretraining + bidirectional translation SFT without collapse; small enough to run QLoRA on a single A100 40GB / L4 / A10 within the Azure credit envelope. Jumping to 13B+ adds compute cost without a corresponding gain on a corpus this small.
3. **Tokenizer audit is the gate, not benchmark scores.** For Hawaiian, fragmentation on ʻokina/kahakō dominates downstream quality far more than a few points of MMLU. The audit is the deciding factor; English benchmark leaderboards are not.
4. **License posture is part of the decision, not a footnote.** "Openly licensed release" is a project goal, so CC-BY-NC bases are out as the released artifact, and Llama/Gemma flow-down clauses are tracked explicitly. Qwen's Apache-2.0 is the cleanest fallback precisely because the license risk is zero.
5. **Smoke-then-main keeps cloud spend honest.** Qwen2.5-0.5B catches pipeline bugs locally before any 7B-class A100 hour is spent; this is the cheap insurance that lets us commit the credits to a single focused 7B run.

**Important caveats — do not overclaim:**
- **Final selection is blocked on the tokenizer audit.** Until we measure tokens-per-word, byte-fallback rate, and ʻokina/kahakō survival on a representative Hawaiian sample (nūpepa + Baibala + contemporary), the "Llama primary, Qwen fallback" ordering is a working hypothesis, not a verdict.
- **None of these models is "objectively best" for Hawaiian.** They are the best *available open* candidates under our license + compute + data constraints. A different team with different constraints could rationally pick differently.
- **QLoRA is a falsifiable default, not dogma.** It's the recipe that fits the budget; if the 0.5B/1B QLoRA-vs-fp16-LoRA ablation shows meaningful quality loss for Hawaiian specifically, we revisit.

**Response to user skepticism on QLoRA quantization loss (carried over from the eval-pipeline framing):**
- Quantization loss is real — usually ~0.1–0.4 PPL and ~0–1 chrF in published QLoRA NF4 results on English. We are not waving that away.
- But the *relevant* comparison for a low-resource Hawaiian prototype is quantization loss vs. the other candidate dominant bottlenecks: tokenizer fragmentation on ʻokina/kahakō, corpus size and register skew, NFC/orthography normalization mistakes, eval leakage and weak metrics, catastrophic forgetting between stages. Those are structurally larger.
- We falsify this prior cheaply: on the 0.5B/1B smoke, run fp16 LoRA vs 4-bit NF4 QLoRA with matched seed/data/tokenizer/eval. If the gap is non-trivial on Hawaiian held-out PPL or chrF in either direction, we re-plan for the 7B run (e.g., bf16 LoRA on a larger card or accept a smaller base). If the gap is in the published-noise band, QLoRA stands.
- Net: skepticism is reasonable, but it gets resolved with an ablation, not an argument.

No new ADR written — this elaborates the existing `Base-model recommendation` and `Two-stage training plan` ADRs in `.squad/decisions.md`. Inbox advisory written to `.squad/decisions/inbox/rusty-model-choice-rationale.md` for Scribe to fold the elaboration into `decisions.md` if useful, and for Danny to cite from `docs/implementation_plan.md`.

## 2026-04-29 — Three-provider eval sequencing (advisory)

User proposed: Provider 1 (free tier) for prelim evals + data validation, Provider 2 (60 hr compute) for Stage 1 + Stage 2 training + evals, Provider 3 for final eval. Advisory captured (no new ADR; existing free-compute-sequencing ADR + eval_pipeline.md already cover the methodology):

- **Provider 1 must finish before any Provider 2 spend:** tokenizer audit on representative slices (nūpepa + Baibala + contemporary), base-model PPL baseline (anchors every later delta), eval-harness build + SHA pin, `eval_hashes.parquet` build + cluster-aware split build, leakage/contamination CI assertion, NFC normalization invariant check, ʻokina U+02BB / kahakō survival baselines on references, 0.5B end-to-end smoke (both stages), QLoRA-vs-fp16-LoRA falsification on 0.5B/1B. Output: a frozen "training-ready bundle" (base SHA, tokenizer SHA, corpus manifest SHA, eval suite SHA, eval-hashes SHA, normalization spec, decision on embedding/lm_head unfreeze).
- **Provider 2 (Stage 1 + Stage 2):** cheap per-checkpoint eval (Hawaiian held-out PPL, English regression, orthography metrics, leakage recheck) at every checkpoint save; full Stage 1 gate eval before fp16 merge; per-checkpoint Stage 2 eval (chrF both directions, retention probe, leakage); full Stage 2 gate eval. Same harness SHA + eval-hashes SHA as Provider 1. All checkpoints carry the bundle hashes in their run report.
- **Provider 3 (final eval):** full slicing pass per eval_pipeline §5, human spot eval (N≥50), generalization probe, hallucination probe, COMET if applicable, attribution-matrix triage. Plus a **same-checkpoint reproducibility eval** vs Provider 2's last gate numbers — this is the harness-drift sanity check.
- **Must run on the same env/checkpoint bundle:** anything that produces a *gate decision* number (Stage 1 gate, Stage 2 gate, final headline chrF/PPL). PPL especially is dtype/quantization sensitive.
- **Safe to run elsewhere:** tokenizer audit, leakage/n-gram checks, orthography survival, slicing analysis, human spot eval, COMET — these are deterministic-ish text ops or human work, not GPU-numeric.
- **Risks of switching providers for final eval:** dtype drift (bf16 vs fp16 vs 4-bit at inference), tokenizer/transformers version drift, sampler/decoding defaults, COMET model version, locale/Unicode normalization differences. Mitigations: ship a pinned eval container (or `requirements.txt` + harness SHA); pin inference dtype + decoding params in the run report; require Provider 3 to first reproduce Provider 2's last gate numbers within tolerance on the *same checkpoint* before any Provider-3-only number is reported as headline; reject any "Provider 3 score" that wasn't preceded by a passing reproducibility eval.
- **Sequencing constraint:** Provider 3 should not be the *first* environment a checkpoint sees. Reproducibility eval first, then the new evals. Without that gate, any Provider 3 number is uninterpretable.

## 2026-04-29 — Raw-data sizing guidance (advisory)

User asked what to gather and how much for the prototype. Captured as advice; no new ADR — refines `data-pipeline.md` (Stage 1 ceiling already says "<50M, possibly <10M tokens") and existing two-stage ADR.

**Stage 1 (Hawaiian monolingual, CPT/DAPT) — cleaned token targets:**
- **Floor (smoke / Qwen2.5-0.5B end-to-end):** ~0.5–1M cleaned Hawaiian tokens. Enough to run both stages, exercise the pipeline, catch tokenizer/orthography bugs. Not enough to claim DAPT quality gain.
- **Minimal viable prototype (7B QLoRA Stage 1):** ~3–10M cleaned tokens, register-balanced, with Bible/religious-archaic ≤10% per pipeline cap. Below ~3M, expect overfitting + register collapse on a 7B; PPL improvements will be largely memorization.
- **Better prototype:** ~15–40M cleaned tokens with real register diversity (news/nūpepa cleaned, contemporary, encyclopedic, Wikisource, dictionary examples). This is near the realistic ceiling per `data-pipeline.md`.
- **Diminishing returns:** above ~40–50M, additional Hawaiian tokens at this base size + LoRA rank give sub-linear gains; tokenizer fragmentation + register skew dominate.

**Stage 2 (bidirectional en↔haw SFT) — cleaned pair targets:**
- **Floor (smoke):** ~2–5k verified pairs, sentence-aligned, eval-set isolated.
- **Minimal viable prototype:** ~20–50k verified sentence-aligned pairs, with Bible ≤30% of train and 0% of dev/test (per pipeline cap), bidirectional weighted roughly symmetric.
- **Better prototype:** ~80–150k verified pairs across ≥3 source families (Bible, Wikipedia comparable, dictionary/curated, optional back-translation ≤25% train, 0% eval).
- Pair *quality* (alignment correctness, register coverage, no dev/test leakage from Bible reprints) dominates pair count by a wide margin. 30k clean > 100k noisy.

**Held-out eval needs (carve out *before* training, not after):**
- Stage 1: ≥200k cleaned Hawaiian tokens for held-out PPL, stratified by source/register, cluster-aware split (no near-dupes across train/dev/test).
- Stage 2: ≥1k pairs dev + ≥1k pairs test, **0% Bible**, balanced by direction and register; isolated by document cluster, not just by row.
- Eval-hash file (`eval_hashes.parquet`) built before any training run; CI assertion that no train doc shares an n-gram cluster with eval.

**What to gather first, ranked by quality leverage (not volume):**
1. **Hawaiian Wikipedia + Wikisource dump.** Cleanest license (CC BY-SA 4.0), low OCR noise, modern register. Runs the pipeline end-to-end and gives a clean tokenizer-audit substrate.
2. **A representative nūpepa slice (~50 docs across decades 1860–1940).** Manual-review batch for OCR-quality stats and orthography variance *before* bulk ingest. This is what the tokenizer audit + go/no-go gate runs on.
3. **Baibala Hemolele (one pinned edition) + English KJV/ASV verse-aligned.** Largest reliable Stage-2 parallel; cap ≤30% of Stage-2 train, 0% eval.
4. **Pukui-Elbert / Andrews dictionary examples.** Small-volume but high-coverage register for orthography and lexical diversity.
5. **Bulk nūpepa OCR.** Only after (1)–(4) prove the pipeline; OCR cleaning eats most of the engineering time and is the largest noise risk. Gather widely, expect aggressive filtering (mean-confidence + char-ratio + paragraph-level LID).

**Quality-over-volume cautions (for Linus + Basher):**
- **OCR noise dominates.** Pre-1900 nūpepa byte-fallback rate and ʻokina/kahakō survival on OCR are the binding quality constraint. A 30M-token corpus where 60% is sub-threshold OCR is *worse* than a 10M-token clean corpus — the model learns the noise distribution.
- **Register skew is silent failure.** If Bible + religious-archaic creep above the 10% Stage-1 cap, the model will output King-James-Hawaiian on contemporary prompts and ace held-out PPL anyway. Track register distribution per-checkpoint, not just per-corpus.
- **Tokenizer fragmentation gates everything.** A 40M-token corpus on a base whose tokenizer fragments ʻokina words will train slower and worse than 10M tokens on a base that handles diacritics cleanly. Final corpus-size target is downstream of the tokenizer audit verdict.
- **Dedup before counting.** Bible reprints, nūpepa article reprints, Wikipedia mirrors inflate raw counts 2–5×. Cluster-aware MinHash dedup is the *real* token count.
- **Final numbers are eval-baseline-anchored.** Once base-model PPL baseline + tokenizer audit land on Provider 1, re-cost the corpus targets against the measured fragmentation rate. The ranges above are priors, not contracts.

No new decision file written — this is operational sizing advice within the existing data-pipeline ceiling and two-stage ADR.

## 2026-04-29 — Stage 1 corpus-size sufficiency (advisory, no new ADR)

User asked whether the publishable / right-clearable Stage 1 budget — hawwiki + Hawaiian Wikisource + small reviewed long tail at ~2.5M / 4.5M / 7M cleaned tokens — is enough to skip the rights-review-heavy nūpepa for the prototype.

**Headline (modeling view):**
- 2.5–7M cleaned Hawaiian tokens is **sufficient for a meaningful Stage 1 smoke / prototype** on a multilingual 7B–8B base via QLoRA. It is **not** sufficient to expect strong DAPT adaptation, especially across registers.
- For DAPT/CPT on a base that already has Polynesian-adjacent prior, the published rule-of-thumb floor is roughly 100M+ tokens to expect robust adaptation; meaningful but partial gains are observable from ~10M; below ~10M the run is best framed as a *pipeline + tokenizer + adapter validation*, not a quality claim.
- 7M tokens × ~3 epochs ≈ 20M training tokens is a reasonable QLoRA Stage-1 budget without overfitting catastrophe, *if* dedup and eval-leakage guards hold. 2.5M is firmly smoke-only territory (≤2 epochs to avoid memorization).

**Risks if Stage 1 is mostly hawwiki + Wikisource (+ small long tail):**
1. **Register skew.** Wikipedia + Wikisource is encyclopedic + literary/PD-archaic. No news, no contemporary prose, almost no conversational. Stage 2 translation eval on contemporary or news-register text will look worse than the model "really" is, and vice versa. Per-source / per-register slicing in eval becomes mandatory, not advisory.
2. **Memorization risk.** hawwiki is small and globally available; a 7B base may already have seen most of it. Causal-LM loss will drop fast and look great while the model is partly recognizing, not learning. Mandatory: train↔eval n-gram overlap check, and a held-out *contemporary* slice that is not on the open web.
3. **Tokenizer-audit signal is narrow.** Wiki text is cleaner than nūpepa; ʻokina/kahakō coverage in hawwiki is inconsistent (many articles drop diacritics). Audits done only on hawwiki + Wikisource will *underestimate* fragmentation on real-world Hawaiian and *overestimate* the base tokenizer's competence. Audit must include a small representative non-wiki sample even if it isn't trained on.
4. **Eval uncertainty.** With a corpus this small and this register-narrow, single-number Hawaiian PPL is near-meaningless. Slices (source, register, diacritic density, length) and dual chrF (as-is + diacritic-normalized) are required to read the run at all.
5. **Catastrophic forgetting still applies.** Even at 2.5–7M tokens, a long-enough Stage 1 can degrade English. Keep the 1–5% English retention mix and monitor English PPL regression.
6. **Audit/provenance posture is *cleaner*, not weaker.** The upside: hawwiki (CC-BY-SA) + Wikisource (PD/CC) + reviewed long tail is the cleanest releasable-license posture available. That matters for the publication-guard story even though we are prototype-only.

**Minimum recommended path (avoids rights-review-heavy nūpepa):**
- **Train:** Stage 1 QLoRA on the 7M-token tier (use the full 7M; 2.5M tier is for the 0.5B smoke only). 2–3 epochs max; freeze tokenizer; record base+tokenizer SHA. Keep 1–5% English mix. Run the pre-existing Stage 0 smoke on Qwen2.5-0.5B end-to-end first.
- **Measure:**
  - Tokens/word, byte-fallback rate, ʻokina U+02BB survival, kahakō retention — pre and post.
  - Hawaiian held-out PPL on a *non-wiki* held-out slice (this is the load-bearing number; build it even if small).
  - English PPL regression vs base (forgetting check).
  - Train↔eval n-gram overlap (memorization check); recompute PPL after stripping overlapping n-grams.
  - Per-source / per-register PPL slices (encyclopedic vs PD-archaic vs long-tail).
  - Stage-2 chrF (both directions, dual as-is/normalized) on a small fixed dev set, even if Stage 2 is only a smoke — this is what tells us whether Stage 1 actually moved the needle.
- **Trigger to add more data (i.e., bite the nūpepa rights-review bullet, or add Awaiaulu/OHA/DOE long tail more aggressively):**
  - Non-wiki held-out PPL fails to improve materially over base, **or**
  - Stage-2 chrF gain is dominated by encyclopedic-register slice and collapses on news/contemporary slice, **or**
  - Memorization check shows large PPL drop after n-gram strip (i.e., the apparent gain was recognition), **or**
  - Tokenizer audit on the non-wiki sample shows fragmentation we can't fix with adapter-only training (would push toward embedding/lm_head unfreeze + more diverse pretraining text).
  - Any one of these → Stage 1 is corpus-bound, and the next move is more Hawaiian text (nūpepa being the only realistic large pool), not more compute or a bigger base.

**Net:** Stage 1 on the right-clearable tier is the right *first* run. Frame it as pipeline + tokenizer + adapter validation with honest slices, not as "we trained a Hawaiian model." Plan the trigger conditions now so the decision to add nūpepa later is data-driven, not vibes-driven.

No new ADR / no decision-inbox file: this operationalizes the existing two-stage ADR and the eval-pipeline doc; no durable team-wide decision is being changed.
