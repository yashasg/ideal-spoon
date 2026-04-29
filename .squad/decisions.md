# Decisions

## ADR: Hawaiian LLM Planning Repository README

**Date:** 2026-04-29  
**Status:** Accepted  
**Owner:** Danny (Lead)

### Decision

Rewrite README.md as a clear planning artifact that:
1. Corrects the "llc" typo → "LLM"
2. Explicitly states the repo is **planning**, not implementation
3. Captures team recommendations without overclaiming
4. Organizes by functional domain: goals, approach, data, model, eval, budget, roadmap

### Context

The team (Rusty, Basher, Linus, Livingston) provided coherent recommendations on:
- **Tokenization & modeling** (Rusty): preserve Hawaiian diacritics, adapt multilingual base model
- **Training & infrastructure** (Basher): QLoRA on 7B–9B, optimize data/eval before scaling GPUs
- **Licensing & data** (Linus): require per-document provenance, avoid undercurated scrapes
- **Budget & cost** (Livingston): $10k–$30k practical tier with vendor tradeoffs

README needed to reflect this without lying about implementation status: no dataset exists, no code yet, no model weights.

### Trade-offs

| Option | Pros | Cons |
|--------|------|------|
| **Plan artifact (chosen)** | Honest, sets expectations, useful for contributors | Requires discipline to keep planning/implementation separate |
| **Remove all detail** | Safe, minimal claim surface | Loses value; doesn't guide next steps |
| **Pretend code exists** | Looks impressive | Risks credibility when someone clones and finds nothing |

### Implementation

- README sections: Goal → Approach → Data/Provenance → Model/Training → Evaluation → Budget → Roadmap
- Data section explicitly lists sources as *planned*, not acquired
- Model/Training section uses candidate models and conditional language ("try", "if corpus size justifies")
- Budget shows tiered estimates with vendor/tradeoff analysis
- Roadmap is 7-week sketch, not detailed sprint plan

### Implications for Next Work

- **Data team**: use README's Data/Provenance section as spec for corpus assembly
- **Training team**: use Model/Training and Evaluation sections to guide adapter selection and benchmark build
- **All teams**: if README becomes out-of-date, update it; this is a live document, not a static spec

### Alternatives Considered

1. **Keep the stub**: "training an llc on Hawaiian language" — too vague, doesn't help onboard new contributors
2. **Write full implementation spec**: too much detail for a planning artifact; belongs in ADRs + team docs, not README
3. **Link to external wiki**: GitHub wiki is often abandoned; README stays with code

---

## ADR: Default model is `claude-opus-4.7`

**Date:** 2026-04-29
**Status:** Accepted
**Owner:** yashasg (via Coordinator)

### Decision

Every Squad agent uses `claude-opus-4.7` as the default model. Persisted in `.squad/config.json` as `defaultModel`.

### Context

User directed that `claude-opus-4.7` be the team default and explicitly confirmed it is a valid model, overriding any stale internal model lists.

### Implementation

- `.squad/config.json` holds `{"defaultModel": "claude-opus-4.7"}`.
- Coordinator reads this file when spawning agents and passes the value as the model parameter unless the spawn explicitly overrides.
- Charters declaring `Preferred: auto` resolve to this default.

### Implications

- Agents previously using mixed models (haiku/sonnet/opus) now uniformly run on `claude-opus-4.7` unless a task-specific override is justified.
- If the user changes the default later, update `.squad/config.json` and append a new ADR; do not silently rewrite this one.

---

## Decision Note: Azure leftover credit ($50–$60/mo) is experiment budget, not training budget

**Date:** 2026-04-29
**Status:** Proposed — team awareness
**Owner:** Livingston (Cost Strategist)

### Decision

Treat the ~$50–$60 of monthly leftover Azure employee credit as a **plan-validation / scratchpad** budget. It does not change the README's $10k–$30k practical training tier.

### Good uses (per Azure list-price ballparks)

- Tokenizer audits at scale on a CPU VM.
- 1–4 hr QLoRA smoke tests on T4 / V100 spot to validate the pipeline.
- Inference / baseline scoring of candidate models on the early eval set.
- Cheap Blob storage for provenance manifests and small corpus snapshots.

### Avoid

- Long training runs, H100 / ND-series / 8-GPU SKUs, always-on VMs, premium SSDs, public inference endpoints.

### Mandatory guardrails

1. Cost Management budget alerts at $30 / $50 / $60.
2. Auto-shutdown on every VM (default 1 hr after creation if untouched).
3. Spot VMs for any GPU work.
4. One resource group per experiment; tear down at end.
5. Tag everything `project=hawaiian-llm`.

### Local RTX 2080 (8GB) division of labor

- Owns: data work, Unicode/NFC pipeline, tokenizer experiments, manifest building, 4-bit 7B inference (slow but viable), LoRA on 1B–3B.
- Doesn't own: full-precision 7B fine-tunes, multi-GPU, real training-scale batch sizes.

### Microsoft-employee caveat

Internal policy is the user's responsibility to confirm: credit-usage terms, RAI / data policy, IP / OSS release posture, cultural-data review, tenant separation. No claim made about what the policy says.

### Implication

When the project is ready for a real training run, dedicated budget is required (Azure spot, Lambda, RunPod bake-off). Leftover credit is for de-risking the plan only.

---

## Decision Note: Training-work fit in $50–$60 Azure credits

**Date:** 2026-04-29
**Status:** Proposed (advisory)
**Owner:** Basher (Training Engineer)

### Decision

Within the leftover Azure credit, scope to **one focused 7B QLoRA run** on A100 40GB / L4 / A10, plus optionally a partial retry. All other ML work runs locally on the RTX 2080.

### Local on RTX 2080 (no credits)

- Tokenizer audits, data pipeline, NFC normalization, eval harness scaffolding.
- Baseline generation from 1B–3B models in 4-bit.
- QLoRA smoke tests on 1B–3B at short seq len to validate the recipe.
- (2080 Ti only) 7B QLoRA at seq 512, bs 1 + grad-accum is *technically* possible — debug only, not deliverable.

### Azure spend (high value per dollar)

1. Single 7B QLoRA training run on a single A100 40GB / L4 / A10.
2. Maybe one repeat run with a tweaked data mix or LoRA rank.

Don't spend credits on data prep, eval harness dev, tokenizer audits, baseline inference.

### Budget reality

- $50–$60 buys low-double-digit hours of A100 80GB on-demand, or meaningfully more on A100 40GB / L4 / A10.
- One real run + maybe a partial retry. **Not** enough for the README's iterative Weeks 5–6 unless credits accumulate across months or vendors switch (RunPod / Lambda often cheaper for this exact workload).

### Runtime guidance

- Pick one SKU and stick with it (default A100 40GB or L4, single GPU).
- Plan one training run of ~6–10 wall-clock hours; lock corpus + config before the GPU spins up.
- Hard-cap each VM session at ~12 hours; auto-shutdown mandatory.
- Reserve ~25–30% of credits as contingency for one re-run.

### Practical guardrails

Auto-shutdown, spot/low-priority for non-final runs, full local pre-stage, `tmux`/`screen` + disk logging, checkpoint to Blob every N steps, budget alerts at 50%/80%, no premium SSDs, log GPU utilization (<70% sustained = dataloader fix locally before redeploy).

### Open questions for the user

1. RTX 2080 (8GB) or 2080 Ti (11GB)? Changes local 7B feasibility.
2. Are the $150/mo credits a recurring monthly grant? If so, plan across 2–3 months unlocks an iteration loop.
3. Deadline pressure for a single-run attempt vs paced multi-month?

---

## Decision Note: Base-model recommendation for Hawaiian adaptation

**Date:** 2026-04-29
**Status:** Proposed (gated on tokenizer audit)
**Owner:** Rusty (NLP Researcher)

### Decision

Two-tier base-model plan:

1. **Smoke-test slot**: `Qwen2.5-0.5B` (Apache-2.0) primary, `Gemma-3-270M` alternate. Validates the data → tokenizer-audit → QLoRA → eval pipeline end-to-end on RTX 2080 + Kaggle before any cloud spend.
2. **Main 7B-class slot**: `Llama-3.1-8B` primary (best Polynesian-adjacent pretraining signal), `Qwen2.5-7B` fallback (cleanest license: Apache-2.0). Final pick is **gated on a Hawaiian tokenizer audit** (ʻokina U+02BB + kahakō, Unicode pinned to NFC).
3. **Held as third option**: `Gemma-2-9B` (license flow-down + no-competing-foundation-models clauses).
4. **Avoid as released base**: `Aya-23` / `Aya-Expanse` (CC-BY-NC contaminates the "openly licensed" release goal — usable only as private reference / silver-data generator). `Mistral-7B` has clean Apache-2.0 but weak multilingual / no Polynesian signal.

### Tokenizer audit (the gate, not vibes)

1. Assemble ~10k tokens of representative Hawaiian text covering ʻokina, kahakō vowels, code-switching with English, proper nouns.
2. Pin Unicode to NFC; record the policy.
3. For each candidate, measure tokens-per-word, byte-fallback rate, ʻokina survival, kahakō unitarity.
4. Pick the model with the lowest fragmentation. Tie-break on license (prefer Apache-2.0).

### Free-compute sequencing

Local RTX 2080 + Kaggle (P100 / 2×T4, 30 GPU-h/wk) for iteration; Lightning AI as small backup; reserve Azure credits for the **single main QLoRA run** on the chosen 7B–9B base + eval (~10–20 hr A100 / A10 / L4).

### License caveats flagged for Linus

- Llama 3.1 Community License: open weights, commercial use OK *unless* >700M MAU; "Built with Llama" attribution + naming requirement; AUP applies.
- Gemma terms: no-competing-foundation-models clause, mandatory flow-down, Google's right to unilaterally modify/terminate.
- Qwen2.5 Apache-2.0 is cleanest for "publish weights and tokenizer under permissive terms."
- License analysis is a research summary, not legal advice.

### Rationale: Why this beats the alternatives for the prototype

1. **Multilingual prior matters more than English-only quality at this scale.** A base that has seen Polynesian/Austronesian-adjacent text transfers faster on a small Hawaiian corpus than a stronger English-only base.
2. **7B–8B is the right capacity band.** Big enough for continued pretraining + bidirectional translation SFT without collapse; small enough for QLoRA on a single A100 40GB / L4 / A10. 13B+ adds cost without a matching gain on a corpus this small.
3. **Tokenizer audit is the gate, not benchmark scores.** For Hawaiian, fragmentation on ʻokina/kahakō dominates downstream quality far more than a few points of MMLU.
4. **License posture is part of the decision, not a footnote.** "Openly licensed release" is a project goal: CC-BY-NC bases are excluded as released artifacts; Llama/Gemma flow-down clauses are tracked. Qwen's Apache-2.0 is the cleanest fallback because the license risk is zero.
5. **Smoke-then-main keeps cloud spend honest.** The 0.5B smoke catches pipeline bugs locally before any 7B-class A100 hour is spent.

### Caveats — do not overclaim

- **Final selection is blocked on the tokenizer audit.** Until tokens-per-word, byte-fallback, and ʻokina/kahakō survival are measured on representative Hawaiian text (nūpepa + Baibala + contemporary), "Llama primary, Qwen fallback" is a working hypothesis, not a verdict.
- **None of these models is "objectively best" for Hawaiian.** They are the best available open candidates under our license + compute + data constraints. Different constraints would justify a different pick.
- **QLoRA is a falsifiable default, not dogma.** It fits the budget; if ablation shows meaningful Hawaiian-specific quality loss, we revisit.

### QLoRA-quantization-loss falsification

- Quantization loss is real: ~0.1–0.4 PPL and ~0–1 chrF in published QLoRA NF4 work on English. Not dismissed.
- The relevant comparison is quantization loss vs. the *other* candidate dominant bottlenecks for low-resource Hawaiian: tokenizer fragmentation on ʻokina/kahakō, corpus size/register skew, NFC/orthography normalization, eval leakage, weak metrics, catastrophic forgetting between stages. Those are structurally larger.
- Falsification plan: on the 0.5B/1B smoke, run fp16 LoRA vs 4-bit NF4 QLoRA with matched seed/data/tokenizer/eval. If the gap on Hawaiian held-out PPL or chrF (either direction) exceeds published-noise bands, replan the 7B run (bf16 LoRA on a larger card, or smaller base). If not, QLoRA stands.
- Net: skepticism is reasonable; it gets resolved with an ablation, not an argument.

### Implications

- README's Tokenization & Orthography section already calls for this audit — Rusty's recommendation makes it a hard gate before main-run model selection.
- Final main-run model selection waits on audit results.

---

## ADR: Two-stage training plan — Hawaiian fluency (Stage 1 CPT) → bidirectional en↔haw SFT (Stage 2)

**Date:** 2026-04-29
**Status:** Accepted (gated on Linus data foundation; cultural-review owner is an open team gap)
**Owner:** Coordinator, on consolidation of Rusty + Basher + Linus
**Trigger:** User directive 2026-04-28T19:46:26-07:00 — "first monolingual Hawaiian fluency, then supervised translation."

### Decision

Adopt a two-stage curriculum:

1. **Stage 1 — Continued pretraining / DAPT on Hawaiian monolingual text.** Causal-LM objective, no instruction templates, NFC-normalized corpus with ʻokina pinned to U+02BB and kahakō preserved. Standard low-resource adaptation recipe (Gururangan et al. DAPT; multilingual-NMT monolingual-pretraining → bitext-FT literature; recent Indigenous-language LLM work). Output: `stage1-haw-cpt` LoRA adapter over the chosen base.
2. **Stage 2 — Supervised fine-tuning for translation**, **bidirectional (en→haw and haw→en) in the same run**, instruction-formatted, **with 10–20% Stage-1-style monolingual Hawaiian CLM examples mixed in as a retention slice** to prevent catastrophic forgetting of Stage 1 fluency. Loss masked to target tokens only. Output: `stage2-haw-sft` LoRA.

This sequencing strengthens — does not replace — the existing base-model and tokenizer-audit decisions. The Qwen2.5-0.5B smoke test is upgraded to run **both stages end-to-end** on tiny slices, validating the full pipeline before any 7B-class spend.

### Adapter strategy (release vs. experiments)

**Release / default path (Basher):** save the Stage 1 LoRA + checkpoints, **merge Stage 1 into the base in fp16** to produce a `base+haw-cpt` artifact (kept internally, not released), then train a **fresh** Stage 2 LoRA on top of the merged model. Reasons: stacked adapters at different ranks/target-modules cause merge headaches, double-quantization noise on QLoRA, and ambiguous "which adapter is active" inference bugs. Stage 1 LoRA merges into **fp16** (not back into 4-bit); Stage 2 reloads in 4-bit fresh from the fp16 merged model — one quantization, not two.

**Experiments / ablations only (Rusty):** keep the Stage 1 adapter and continue training it (or stack a second adapter) for short A/B runs that need to ablate Stage 1's contribution cheaply. Never used as a release artifact.

Same base-model SHA must be used for the merge step and Stage 2 init. Run manifest records base SHA, tokenizer SHA, adapter config. Tokenizer is **frozen at Stage 1 start** and Stage 2 must load the identical tokenizer files (CI hash check).

### Hyperparameters and recipe (starting points)

**Stage 1 (CPT, 7B/8B target):**
- Objective: causal LM, no chat template, full-token loss.
- LoRA: all-linear targets (`q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj`); **r=64, α=128, dropout 0.05**. Embeddings/lm_head may need to be trainable if the tokenizer audit shows ʻokina/kahakō tokens are rare or split — audit-driven decision.
- Seq len **2048** (drop to 1024 if Kaggle OOMs; never below 1024 for CPT).
- Per-device batch 1 (T4) / 2 (A100 40GB), grad-accum to effective tokens-per-step ~64k–128k.
- LR **2e-4** cosine, warmup 3%, min LR 2e-5. **One epoch** over the curated corpus; ≤2× repeats. ≥1–2 epochs preferred when corpus permits.
- 4-bit NF4 + double-quant, bf16 compute (fp16 on Turing — RTX 2080), gradient checkpointing on, paged AdamW 8-bit, flash-attn 2 where supported.
- **Anti-forgetting:** mix in 5–10% English (clean general corpus, e.g. small FineWeb-Edu slice). English-perplexity probe on a fixed held-out set every eval.

**Stage 2 (SFT, bidirectional translation):**
- Instruction template = base model's native chat template (Llama-3.1 chat template if Llama; ChatML for Qwen). Two minimum prompt variants per direction, plus Hawaiian-language prompt variants ("Unuhi i kēia …") so the model handles haw-side instructions, not just English-side.
- Loss masked to target only (`labels=-100` on prompt). Non-negotiable.
- Seq len **1024**. Per-device batch 2–4, grad-accum to effective 32.
- LoRA **r=32, α=64, dropout 0.05**.
- LR **1e-4** cosine, warmup 3% (≈⅓–½ of Stage 1 LoRA lr). 2–3 epochs max; early-stop on dev BLEU/chrF.
- 50/50 direction balance unless data forces otherwise.
- 10–20% Stage-1-style monolingual Hawaiian CLM batches mixed in (retention slice).

### Compute mapping (reuses prior credit-fit ADR)

| Work | Where |
|---|---|
| Pipeline plumbing, NFC checks, eval-harness scaffolding | RTX 2080 local |
| 0.5B smoke test (both stages, end-to-end) | RTX 2080 local |
| 0.5B Kaggle dry-run (validate cloud checkpoint/sync) | Kaggle |
| 7B/8B Stage 1 CPT | Kaggle T4×2 / P100, multi-session; Azure A100 spot only if Kaggle insufficient |
| Stage 1 → fp16 merge sanity-check | Local or Kaggle CPU |
| 7B/8B Stage 2 SFT | Kaggle T4×2 or single Azure A100 40GB spot (~6–10 hr) |
| Final eval / baselines | Local + Kaggle |

Stage 1 dominates wallclock; Stage 2 fits in the contingency slice. If only one stage fits in budget, Stage 1 must run on the 7B; Stage 2 may degrade to a smaller model or shorter run without losing the project's premise.

### Evaluation gates (go / no-go)

**After Stage 1 (CPT) — all must hold to proceed:**

1. **Orthography preservation:** generated Hawaiian retains ʻokina (U+02BB, not U+2018/U+0027) and kahakō at expected rates vs. a held-out reference distribution. **Hard fail** if ʻokina collapses to apostrophe.
2. **Hawaiian held-out perplexity** lower than the base model's by a clearly visible margin (ballpark ≥20% relative reduction; exact threshold locked once the base PPL is observed).
3. **English held-out perplexity** has not blown up (≤20% relative *increase* vs base). If it has, forgetting is too severe; rerun with more English rehearsal.
4. **Fluency / native-speaker spot eval** on N=50–100 short Hawaiian continuation prompts (Rusty + a Hawaiian-reading reviewer; 20-prompt minimum if reviewer time is scarce). ʻokina + kahakō preserved; no obvious code-switch to English mid-sentence.
5. **Hallucination probe:** prompts about non-existent Hawaiian places/people; track fabrication rate (DAPT on small corpora can *increase* confident hallucination).
6. **Tokenizer audit metrics** from Rusty's earlier ADR did not regress on the trained model's outputs.

If any fail → no Stage 2. Diagnose data or recipe first.

**After Stage 2 (SFT):**

1. **chrF / chrF++** (primary; BLEU is unreliable for morphologically rich, low-resource languages — report both, weight chrF) on a held-out en↔haw dev/test set, beating both (a) the base zero-shot and (b) the Stage-1-only model zero-shot, **in both directions, reported separately, never averaged**.
2. **COMET** if a multilingual COMET model covers Hawaiian adequately; otherwise document the limitation.
3. **No-translation-leakage check:** model output on the test set is not a near-duplicate of any training pair (bigram-overlap threshold).
4. **Adequacy + fluency human eval** by a Hawaiian speaker on N=100 ideal / N=30 minimum per direction, 5-point Likert each. Mean ≥3.5 to ship as a candidate; ≥4.0 to call it the recommended model.
5. **Orthography retention re-check** — SFT didn't kill the ʻokina/kahakō behavior installed by Stage 1. If it did, retention mix wasn't large enough; reweight and rerun.
6. **Generalization probe:** behavior on non-translation prompts hasn't collapsed into "always translate." Refusal/safety/register sanity probe included.

### Hard data gates (Linus) — training does not start until these pass

**Stage 1 cannot start until:**

1. Corpus inventory exists (sources enumerated, sizes estimated, licenses identified).
2. `stage1_manifest.parquet` schema implemented and populated for every Stage 1 document.
3. License whitelist applied; non-whitelisted documents marked `excluded`.
   - ✅ `CC0-1.0`, `PublicDomain`, `CC-BY-4.0`, `CC-BY-SA-4.0`, permissively-licensed government works.
   - ⚠️ `CC-BY-NC*` / `CC-BY-ND*` excluded from training (private reference / eval inspection only).
   - ❌ Unknown / "license unclear" excluded. ❌ Anything restricting redistribution of derivative weights.
4. Normalization pipeline run end-to-end: UTF-8 → NFC → ʻokina canonicalized to **U+02BB** → whitespace/control-char clean → langID filter on `haw` → boilerplate strip → exact-SHA + MinHash near-dup dedup. `sha256_raw` and `sha256_normalized` populated.
5. Train/dev/test/holdout-eval splits assigned **at corpus-build time** with **cluster-aware isolation**: if any document in a `dedup_cluster_id` is held-out, the entire cluster is held out. Held-out splits stored in a separate read-only path; loaders forbidden from touching it.
6. Cultural-review pass complete at least source-level: every source annotated `cleared` / `flagged` / `restricted`; `flagged` source documents reviewed individually or excluded. **Only `cleared` is eligible for training.**
7. `eval_hashes.parquet` exists; Stage 1 dataloader contamination check is wired up and passing (CI-enforced, fail loudly on intersection).

**Stage 2 cannot start until:**

1. Stage 1 has run and passed its eval gate.
2. `stage2_manifest.parquet` exists with all per-pair fields populated (provenance, license, translator, alignment_method, alignment_score, length_ratio, register, domain, synthetic flag + source model, original_direction, hashes, dedup cluster, split, `crosslink_stage1_overlap`, cultural_review).
3. License clearance for parallel data is independent and complete.
4. Alignment-quality scoring run (LaBSE/LASER cosine or comparable); below-threshold pairs excluded; borderline band down-weighted in `train` only, never in `dev`/`test`. Length-ratio outliers (top/bottom 1%) manually inspected.
5. Direction balance, register distribution, and synthetic share reported in the manifest summary.
6. `crosslink_stage1_overlap` populated; held-out Stage 2 splits free of Stage 1 overlap.
7. Held-out Stage 2 test set built from a source with **zero overlap** with Stage 1 corpus and Stage 2 train pairs (hash-checked).

**Synthetic / back-translated data:** allowed only with `synthetic=true` and `synthetic_source_model` set; capped at **≤25% of Stage 2 train** and **0% of Stage 2 dev/test**. Inherits the source model's output license; do not back-translate via models whose ToS forbids using outputs to train competing models.

**Hard-escalate cultural categories** (default-excluded pending named cultural reviewer): mele / oli / pule, oral histories / moʻolelo from named tradition-bearers, genealogies (moʻokūʻauhau), place-name lore tied to specific ʻohana or ahupuaʻa, pre-1925 Hawaiian-language newspapers (nūpepa) bulk ingestion, restricted community-archive material (Bishop Museum, Kamehameha Schools, etc.).

### Manifest schema (locked)

Two parquet files, versioned and committed alongside the corpus snapshot, plus an `eval_hashes.parquet` contamination guard. Field lists per Linus's proposal:

- `stage1_manifest.parquet` (one row per document): doc_id, source, source_url, collection_date, license (SPDX), license_url, attribution_required, attribution_text, rights_holder, language (BCP-47, must match `haw*`), content_category, register, script_normalized (=`NFC`), okina_codepoint (=`U+02BB`), kahakō_preserved, char_count, token_count_est, sha256_raw, sha256_normalized, dedup_cluster_id, split, exclusion_reason, cultural_review, cultural_notes, manifest_schema_version.
- `stage2_manifest.parquet` (one row per pair): pair_id, src_lang, tgt_lang, src_text, tgt_text, source, source_url, license, license_url, attribution_required, attribution_text, translator, alignment_method, alignment_score, length_ratio, register, domain, synthetic, synthetic_source_model, original_direction, sha256_pair, dedup_cluster_id, split, exclusion_reason, crosslink_stage1_overlap, cultural_review, cultural_notes, manifest_schema_version.
- `eval_hashes.parquet`: sha256_normalized, origin, stage. Both stages' dataloaders import it and assert empty intersection with their training shards.

### Risks and mitigations

| Risk | Mitigation |
|---|---|
| Catastrophic forgetting of English/instruction behavior in Stage 1 | 5–10% English rehearsal in Stage 1 mix; English-PPL probe each eval; never full-finetune. |
| Catastrophic forgetting of Stage 1 fluency during Stage 2 | 10–20% monolingual Hawaiian retention slice in every Stage 2 batch mix. |
| Translation overfitting in Stage 2 | Cap 2–3 epochs; early-stop on dev BLEU/chrF; held-out test never seen during data curation. |
| Data contamination (eval text leaking into train) | `eval_hashes.parquet` + dataloader CI assertion, both stages; cluster-aware near-dup isolation; per-source de-bulk on adopted public benchmarks. |
| Adapter stacking / merge problems | Default release path = merge after Stage 1, fresh Stage 2 LoRA. Stacking only for short experiments. Same base SHA + tokenizer SHA recorded in run manifest. |
| Tokenizer drift between stages | Tokenizer frozen at Stage 1 start; Stage 2 loads identical files; CI hash check. |
| Quant noise compounding | Stage 1 LoRA merged into **fp16** (not 4-bit). Stage 2 reloads in 4-bit fresh — one quantization, not two. |
| Resume failures eating a Kaggle session | Test resume-from-checkpoint on the 0.5B smoke before any 7B run. Optimizer state preserved. |
| Over-spending Azure credits | Stage 1 stays on Kaggle by default; Azure only for Stage 2 final or Kaggle-quota exhaustion; spot only; auto-shutdown; alerts at $30/$50/$60; ≤12 hr/session. |
| Cultural mis-handling on translation outputs | Hawaiian-speaker / community review step before any public release of Stage-2 outputs. Cultural-review owner currently unassigned — flagged as open team gap. |
| Sole-author / single-direction bias in parallel corpus | Manifest-level direction balance + register distribution audit; tag `original_direction` per pair; report eval per direction, never averaged. |

### Alternatives considered

1. **One-stage joint training** (mix monolingual + parallel from start) — rejected; under-trains Hawaiian fluency, over-trains the task; weaker than staged in low-resource literature.
2. **SFT-only on parallel data, skip Stage 1** — rejected; produces "fluent English, broken Hawaiian" failure mode at low Hawaiian pretraining coverage.
3. **Three-stage (DAPT → general instruction-tune → translation SFT)** — defensible but out of budget; revisit if scope grows beyond translation.
4. **Back-translation augmentation in Stage 2** — allowed as a sub-option only; capped per data gates.
5. **Stack Stage 2 adapter on Stage 1 as the release path** — kept as experiments-only path; merge-then-fresh-LoRA is the release default for reliability and debuggability.
6. **Loosen license whitelist to CC-BY-NC** — rejected; contaminates open-weights release goal.
7. **Source-level only manifest (no per-document)** — rejected; can't survive dedup, can't isolate eval contamination, can't drive cultural-review workflow.
8. **One-direction Stage 2 (en→haw only) to halve corpus risk** — rejected; corpus is the same either way; haw→en eval is needed to detect the broken-Hawaiian failure mode.

### Open team gaps

- **Cultural-review owner unassigned.** Without a named Hawaiian-speaking reviewer, sensitive sources stay `unreviewed` → `excluded`. Coordinator must spawn a reviewer agent or yashasg confirms an external reviewer is engaged.
- RTX 2080 8GB vs 2080 Ti 11GB still unconfirmed (affects local 7B Stage-2 debug feasibility).
- Whether Azure credit is recurring monthly or one-shot (affects retry budget).
- Final base-model pick (Llama-3.1-8B vs Qwen2.5-7B) still gated on the Hawaiian tokenizer audit; Stage 1 cannot start before the audit locks the base, since switching base mid-pipeline invalidates Stage 1.

### Implications

- README's Roadmap should later reflect a **Week 0 data-foundation phase** (corpus inventory, manifest build, cultural-review pass, contamination guard) before Stage 1, plus the two-stage structure and the merge-after-Stage-1 release convention. *Not edited in this Scribe task.*
- Eval harness (Rusty / Basher / Livingston cost) must have both perplexity probes (Stage 1 gate) and chrF/chrF++ (+ optional COMET) (Stage 2 gate) ready **before** the first 7B Stage 1 run starts.
- Linus's data deliverables are now the bottleneck. Compute is no longer the long pole.
- The Qwen2.5-0.5B smoke test scope expands to run **both stages** end-to-end on tiny slices for pipeline validation.

### Provenance

Consolidates four inbox proposals (now deleted): `copilot-directive-2026-04-28T19-46-26-0700-two-stage-training.md`, `rusty-two-stage-training.md`, `basher-two-stage-training.md`, `linus-two-stage-data-gates.md`. See the matching orchestration-log entries dated 2026-04-29T02:53:51Z.


---

## ADR: Prototype-vs-release split for data gates and release artifacts

**Date:** 2026-04-29
**Status:** Accepted
**Owner:** Danny (Lead), with Linus (Data Engineer) on data posture
**Trigger:** User directive 2026-04-28T19:55:04-07:00 — "this is just a prototype, a learning project, i wont be able to find legal/safe training data, we will try to use publically available data like ulukau.org newspapers, parallel texts like the Bible."
**Related:** ADR "Two-stage training plan…" (2026-04-29), ADR "Hawaiian LLM Planning Repository README" (2026-04-29).
**Disclaimer:** Not a legal opinion. Source-specific terms still bind us. "Publicly available" ≠ "openly licensed" ≠ "training-permitted."

### Decision

Reframe the project as an **explicitly prototype / learning effort** and split engineering gates into two tiers:

1. **Prototype gate** — what must hold for a *private* experiment to count as honest learning.
2. **Release gate** — what must additionally hold before any artifact (weights, adapters, generations, eval scores, datasets, demos, hosted endpoints) is shared outside the contributor's machine.

The two-stage curriculum (Stage 1 CPT → Stage 2 bidirectional SFT) **stays**. What changes is the bar each stage clears and the meaning of "done." This ADR does not loosen any release-time obligation; it tightens the boundary around the word *release*.

### Bright line: what counts as "release"

Any of the following leaving a contributor's local environment is a release:

- Dataset files, manifests, or derived corpora (raw or normalized).
- Model weights, LoRA adapters, merged checkpoints, quantizations.
- Tokenizers trained on restricted corpora.
- Public demos / hosted inference endpoints / Spaces.
- Sample generations or screenshots posted publicly that could leak training text.
- Eval outputs or scores, including release-like benchmark numbers.

Pushing to a public GitHub repo, HuggingFace, a public bucket, or a shared link counts as release. "Unlisted" ≠ private. Anything else — local training, local inference, private notebooks, internal-only metrics — is **prototype scope** and uses the lighter gate.

### Prototype scope (what becomes acceptable for *private learning only*)

- Training on public-domain-by-copyright sources (e.g., pre-1929 ulukau.org nūpepa, *Baibala Hemolele* 1839) without per-source cultural clearance, **provided** the resulting weights, adapters, generations, eval numbers, and derived datasets stay private.
- Training on openly-licensed sources (CC0, CC-BY, CC-BY-SA, permissively-licensed government works) under their attribution terms.
- Using "license unclear" sources for **inspection and analysis only** by default; if used as training input, they must be tagged `license_status=unclear` and the resulting artifacts are prototype-only.
- Synthetic / back-translation experiments at any ratio, **provided** the prototype boundary is honored and the source-model ToS is respected.
- Per-source-row manifest acceptable to bootstrap; per-document rows can come later for prototype.

### Non-negotiables even at prototype scope

These are cheap and they preserve optionality. They hold for the smallest prototype run.

1. **Source tracking** — every byte traceable to a source URL or local archive path and a fetch date. No "miscellaneous scrape" buckets.
2. **Provenance hash** — SHA-256 of each raw file at ingest.
3. **Attribution metadata** — author / publication / date where known. Missing is allowed; *unrecorded-because-we-didn't-bother* is not.
4. **Contamination isolation** — `eval_hashes.parquet` and the dataloader CI assertion stay on. A leaked eval is a wasted run.
5. **Cultural-sensitivity tagging at ingest** — hard-escalate categories (mele/oli/pule, moʻolelo from named tradition-bearers, moʻokūʻauhau, place-name lore tied to specific ʻohana/ahupuaʻa, restricted-archive material, **bulk pre-1925 nūpepa**) tagged at ingest even when used. Tagging now is what makes a future cultural review tractable.
6. **NFC + ʻokina U+02BB + kahakō preservation**, exact + near-dup dedup, language-ID filter — these are interpretability hygiene, not release polish.
7. **Tokenizer freeze across stages**, base+tokenizer SHA in run manifest, fp16-merge-then-fresh-LoRA convention from the two-stage ADR.
8. **Redistribution warnings** — manifest, README, dataset/model card, and any artifact directory carry "prototype-only, do not redistribute" markers (see *Repo-level labels* below).
9. **No public weights from unclear/flagged data, full stop.** Weights inherit the dirtiest data they saw.
10. **Source-specific terms override "publicly available."** A ToS line forbidding scraping or model training overrides the fact that the page is reachable.

### Release gate (unchanged from prior ADR; restated for clarity)

Required before anything leaves the prototype boundary:

1. **Per-source cultural review by a named Hawaiian-speaking reviewer**, with each source marked `cleared`, `flagged`, or `restricted`. Only `cleared` sources may be in the released training mix. Hard-escalate categories require an explicit, recorded clearance — not silence.
2. **Per-source training-rights review**, distinct from copyright (archive ToS, community expectations, attribution carried into the model card).
3. **License whitelist re-applied** with no `unreviewed_prototype` rows in the training shard. CC0 / CC-BY / CC-BY-SA / explicit permissive only.
4. **Contamination + cluster-aware split isolation**, synthetic ≤25% Stage 2 train and 0% dev/test, tokenizer audit locked.
5. **Human eval** per the two-stage ADR's Stage 1 and Stage 2 gates (N=50–100 ideal, N=20/30 minimum) by a Hawaiian-reading reviewer.
6. **Model card** documenting data provenance with each source's license, the prototype lineage, register skew (e.g., "X% of Stage 1 tokens are Bible-register"), known failure modes from prototype runs, and explicit not-fit-for statements (ceremonial / cultural / official translation use).
7. **No prototype-tainted weights leak into the released chain.** A released model is trained from a corpus where every row is `cleared` and every license is whitelisted; it is *not* a prototype checkpoint relabeled. The merge convention (Stage 1 → fp16 → fresh Stage 2 LoRA) is reused, but the inputs are the cleared corpus.

### Manifest schema

Single prototype manifest file `prototype_manifest.parquet` (`.csv` while bootstrapping). One row per ingested document. Stage 1 / Stage 2 release manifests gain corresponding fields (`manifest_schema_version` bumps).

| field | required | notes |
|---|---|---|
| `doc_id` | ✅ | stable, e.g. `ulukau-nupepa-kuokoa-1861-09-26-p3` |
| `source` | ✅ | short slug: `ulukau-nupepa`, `baibala-hemolele-1868`, `wikipedia-haw`, … |
| `source_url` | ✅ | direct URL fetched, or local archive path |
| `fetch_date` | ✅ | ISO-8601 UTC |
| `sha256_raw` | ✅ | hash of bytes as fetched, before normalization |
| `bytes_raw` | ✅ | raw size |
| `language` | ✅ | `haw`, `en`, `haw+en`, `mixed` |
| `license_status` | ✅ | `cc0` \| `cc-by` \| `cc-by-sa` \| `public-domain-claimed` \| `permissive-other` \| `unclear` \| `restricted` |
| `license_note` | ⬜ | free text; cite the page where status came from |
| `terms_snapshot_path` | ⬜ | path to saved ToS / rights page |
| `cultural_review_required` | ✅ | bool; true for hard-escalate categories |
| `cultural_review` | ✅ | `unreviewed_prototype` \| `unreviewed` \| `cleared` \| `flagged` \| `restricted` |
| `cultural_tags` | ⬜ | array: `mele`, `oli`, `pule`, `moolelo`, `mookuauhau`, `place-name-lore`, `nupepa-pre-1925`, `restricted-archive`, … |
| `register` | ⬜ | `news`, `religious`, `legal`, `narrative`, `reference`, `conversational`, … |
| `original_direction` | ⬜ | parallel only: `en→haw`, `haw→en`, `unknown` |
| `normalization` | ✅ | semicolon-joined: `nfc;okina-u02bb;kahako-preserved;ocr-cleaned-vN` |
| `split` | ⬜ | `train` \| `dev` \| `test` \| `holdout` \| `unassigned` |
| `intended_use` | ✅ | `prototype_private` (default) \| `release_candidate` |
| `prototype_only_reason` | ⬜ | free text, required when `intended_use=prototype_private` and the row would not pass release gates |
| `release_eligible` | ✅ | bool; default **false**; flip only after release-gate review |
| `notes` | ⬜ | OCR caveats, alignment quality, source quirks |

**Loader enforcement:** a run tagged `release_candidate` rejects any row whose `intended_use=prototype_private` or `cultural_review ∈ {unreviewed, unreviewed_prototype, flagged, restricted}` or `license_status ∈ {unclear, restricted}`. CI check.

Promotion path prototype → release: add per-pair rows for parallel data, fill optional fields the release schema requires, run cultural review, populate `release_eligible=true` per row.

### Source-specific notes (engineering, not legal)

**Ulukau.org newspapers (nūpepa).** High-value Hawaiian corpus and the most culturally loaded. **Pre-1925 nūpepa bulk ingestion stays on the hard-escalate list.** Tag every doc with `cultural_review_required=true`, `source=ulukau-nupepa`, paper title + issue date. Capture Ulukau's terms-of-use and any per-collection notices into a `terms_snapshot/` directory keyed by source; link from the manifest, don't paraphrase. OCR confidence is a normalization-stage field; don't silently train on garbage. Until a cultural-review owner is named, nūpepa stays prototype-only, not for release.

**Bible / parallel texts.** Useful for Stage 2 (parallel en↔haw). Register is narrow (religious, archaic) — useful but not representative. Tag `register=religious`, `original_direction=en→haw` where known. Multiple Hawaiian Bible translations exist with different copyright statuses; record the specific edition, translator, and publication year per text — "Bible = public domain" is not assumed. Verse-level alignment is usually safe; chapter-level is not. Bible-heavy training data biases the model toward mission-era register; document the bias and include a non-Biblical held-out probe so register memorization isn't mistaken for fluency.

**General "publicly available" sources.** Public availability ≠ open license ≠ training-permitted. Prefer sources with a clear license statement; when absent, tag `license_status=unclear` and treat as prototype-only.

### Two-stage plan under prototype scope

The two-stage plan remains valid. Adjusted gate semantics:

- **Stage 1 prototype gate:** pipeline runs end-to-end; NFC + ʻokina + kahakō integrity preserved through tokenizer and generation; contamination guard green; English-PPL not catastrophically blown up; Hawaiian-PPL moves in the expected direction on a held-out slice. Native-speaker eval encouraged but **not blocking**; if it happens, log as a learning, not as a ship gate.
- **Stage 2 prototype gate:** chrF/chrF++ in both directions reported separately on a held-out test set with verified zero-overlap to Stage 1 corpus and Stage 2 train; contamination guard green; no-translation-leakage check green. Human adequacy/fluency eval encouraged but **not blocking**.
- **Bible-text caveat:** if Bible text is a non-trivial share of the corpus, the run report calls out register skew explicitly and includes a non-Biblical held-out probe.
- **Nūpepa caveat:** Rusty's tokenizer audit must be re-run on a representative nūpepa sample and on *Baibala Hemolele* before drawing conclusions; period orthographic conventions distort generic Hawaiian audits.

### Repo-level labels and warnings

Until a release-gate pass exists, the repo and any artifact dir carry these markers somewhere visible (README, dataset card, model card, artifact dir `README.md`):

- `Status: PROTOTYPE — learning project, not for redistribution.`
- `Training data: includes sources with unclear or unreviewed status. Do not redistribute.`
- `Weights / adapters: not for public release until data is cleared and cultural review is complete.`
- `Cultural review: pending. Hawaiian cultural materials may be present without community consultation.`
- For any artifact that ships out: explicit `LICENSE-DATA-NOTES.md` summarizing what's inside and why it's not redistributable.

Suggested git-tracked tags for commits / branches that touch training data: `prototype-data`, `do-not-release`.

### README follow-up (recommendation, not edited here)

Queue a follow-up README pass:

- **Prototype banner** at the top: this repo is a learning prototype; nothing here is intended for public release without a separate clearance pass.
- Reframe **Goals**: soften "Publish weights, tokenizer, eval harness, and data manifests under permissive terms" into a conditional — *if and when* the release gates in this ADR are met. Replace the implicit promise with an explicit two-tier statement.
- Reframe **Non-Goals**: add "Releasing weights or generations from prototype runs."
- Rewrite **Data & Provenance** to describe the public-source exploration plan honestly: ulukau.org nūpepa and parallel Bible texts are candidate prototype inputs; copyright posture, archive-access posture, and cultural-clearance posture are three separate things; only the first is satisfied by "public-domain."
- Rewrite **License (intent)** to clarify code/configs/eval-harness intent stays permissive; weights and data manifests are not promised for release and require the release gates above.
- Add a short **Prototype vs. Release** section pointing at this ADR.

### Trade-offs

| Option | Pros | Cons |
|---|---|---|
| **Prototype/release split (chosen)** | Lets the project actually run; preserves release-quality bar; keeps engineering discipline (manifests, contamination guard, hygiene) that makes the work reusable later; honest about what's private vs public. | Requires loader-level enforcement of `intended_use`; adds manifest fields; relies on contributor honoring the boundary. |
| Drop cultural/license gates entirely | Simplest; matches "prototype" framing literally. | Burns the option to ever release; corrupts the manifest discipline that makes the prototype itself useful; wrong norm for a Hawaiian-language project. |
| Keep prior ADR as written | Maximum integrity. | Project cannot proceed with sources the user can actually access; ADR gets violated silently or work stalls — both worse than a documented relaxation. |
| Pivot to *only* fully cleared sources | Keeps release path live. | Likely no usable Hawaiian corpus at this budget; defeats learning purpose. |

### Implications

- Linus's prior data-gate posture is **not repealed**; it is **scoped** to `intended_use=release_candidate`. Prototype rows live under the relaxed posture defined here. The loader is the enforcement point.
- Basher's training recipe is unchanged.
- Rusty's tokenizer audit gains a sub-task: run on a representative nūpepa sample and on *Baibala Hemolele*.
- Livingston's budget framing is unchanged; prototype scope reduces pressure on the upper-tier full-fine-tune contingency.
- The Qwen2.5-0.5B smoke test is even more clearly the right first artifact: it validates the pipeline on prototype-scope data with no release ambiguity.
- README is out of date with respect to this ADR — flagged for a follow-up pass, not edited here.
- Next data-side task: stand up `prototype_manifest.parquet` validator script; draft Ulukau / Bible ingestion checklist that captures terms snapshots and cultural tags at fetch time.

### Open team gaps

- **Cultural-review owner remains unassigned.** Softer at prototype scope (runs can proceed with `unreviewed_prototype`); for any release path it is **the** blocking gap.
- **Archive / community-relations owner unassigned.** Distinct from cultural review; needed if release becomes real (Ulukau / Awaiaulu / Bishop Museum / Kamehameha Schools contact).
- **Register-balance reviewer.** If Bible text dominates the prototype corpus, someone (Rusty + a Hawaiian reader) owns "is this model just doing 19th-century missionary register?" diagnostics. Should be made explicit in Rusty's scope.

### Alternatives considered

1. Treat the user directive as overriding the data gates entirely — rejected; the gates' engineering content (manifests, contamination guard, normalization) is what makes a prototype worth running.
2. Define prototype as "train on whatever, no manifest" — rejected; produces an unreproducible run that teaches nothing transferable.
3. Block the project until a cultural reviewer is named — rejected; the block applies to release, not to learning.
4. Require Bible text be excluded as too register-skewed — rejected; measure and disclose the skew, not ban it.
5. Promise public release "eventually" in the README without a gate definition — rejected; that's the failure mode this ADR exists to prevent.

### Provenance

Consolidates three inbox proposals (now deleted): `copilot-directive-2026-04-28T19-55-04-0700-prototype-public-data.md`, `linus-prototype-data-posture.md`, `danny-prototype-scope.md`. See orchestration-log entries dated 2026-04-29T03:01:58Z.

---

## ADR: Stage-1 monolingual + Stage-2 bidirectional en↔haw data pipelines (prototype)

**Date:** 2026-04-29
**Status:** Accepted (design); ingest gated as noted
**Owner:** Linus (Data Engineer)
**Scope:** Stage-1 monolingual Hawaiian CPT/DAPT pipeline; Stage-2 bidirectional en↔haw SFT pipeline with 10–20% Hawaiian monolingual retention. Prototype posture per the Prototype-vs-release ADR; both default `release_eligible=false`, `prototype_only=true`. No public weights / datasets / adapters / demos / release-style eval claims without separate clearance.

Consolidates two inbox proposals (now deleted): `linus-stage1-data-pipeline.md`, `linus-stage2-data-pipeline.md`. Companion orchestration entries: `.squad/orchestration-log/2026-04-29T03:13:13Z-linus-stage1-data-pipeline.md`, `…-linus-stage2-data-pipeline.md`.

### Hard precondition

Stage-2 *ingest* does not begin until Stage-1 artifacts (`stage1_manifest.parquet`, packed JSONL, populated `eval_hashes.parquet`) exist. Stage-2 *design + adapter scaffolding* may land now.

---

### Stage-1 — Monolingual Hawaiian CPT/DAPT

**Source tiers**

- **Tier A (high value, prototype-only until cleared):** Ulukau nūpepa (~1834–1948, OCR'd; pre-1925 bulk default-excluded for release; ToS snapshot per fetch); Ulukau dictionaries / readers / Baibala; Hawaiian Wikipedia (`hawwiki` dump, CC BY-SA 4.0 — closest to release-eligible); Hawaiian Wikisource.
- **Tier B (useful, narrow register):** Hawaiian Bible (Baibala Hemolele) — **cap ≤10% of Stage-1 tokens**, tag `register=religious-archaic`; OHA / DOE Kaiapuni / UH educational PDFs (per-doc review); Awaiaulu / kūpuna prose where public.
- **Tier C (HF/GitHub/Kaggle):** treat as *pointers* to original sources; re-derive provenance, do not trust HF metadata as license truth.
- **Tier D (avoid for Stage 1):** generic CommonCrawl `haw` LID (poor recall, FP from Pidgin / Eng-with-loanwords); social media without explicit permission; mele/oli/pule, moʻolelo from named tradition-bearers, moʻokūʻauhau (hard-escalate; strip if found).

**Pipeline**

```
crawl/download → raw archive (immutable, SHA-256, off-git) → extraction/OCR (Tesseract haw, record OCR confidence) → paragraph-level LID (cld3/fasttext) → Unicode normalization (NFC; ʻokina canonicalized to U+02BB; kahakō preserved as combining macron U+0304 / NFC precomposed) → boilerplate removal → paragraph/sentence segmentation (Hawaiian-aware) → MinHash dedup with cluster IDs persisted → quality filters (min length, max symbol/digit ratio, min Hawaiian-char ratio, optional perplexity) → register/cultural tags → cluster-aware split isolation (any cluster touching dev/test → fully held out; also held out from Stage-2 eval hashes) → stage1_manifest.parquet → packed JSONL (Rusty-audited tokenizer)
```

Apostrophe canonicalization is non-trivial (U+0027 / U+2018 / U+2019 / U+02BB / U+02BC all show up); canonicalize to ʻokina **only** when context indicates ʻokina; track original codepoint in a debug column for the first prototype run.

**`stage1_manifest.parquet` fields (strict subset of release manifest):**
`doc_id, source, source_url, fetch_date, fetch_http_status, sha256_raw, sha256_clean, content_type, extraction_method, ocr_confidence_mean (nullable), language_id, language_id_confidence, char_count, token_count_est, unicode_normalized, register_tag, cultural_flag, dedup_cluster_id, split, license_observed, license_inferred (always null), release_eligible (default false), prototype_only (default true), notes`. `eval_hashes.parquet` non-negotiable contamination guard.

**JSONL contract:** one example per line — `{doc_id, text, source, register, split, prototype_only}`. **Excluded from training text:** license / copyright / ToS boilerplate, source URLs, fetch dates, manifest fields, HTML, page-number artifacts, OCR markers, dev/test rows, mixed-language paragraphs that failed paragraph-LID, hard-escalate cultural categories.

**Top risks (ranked):** tiny corpus → overfitting / register collapse (cleaned corpus likely <50M tokens, possibly <10M); Bible / religious register skew; nūpepa OCR noise (pre-1900 mean-confidence filter + manual sample review); apostrophe / diacritic chaos fragmenting tokenizer; English contamination in mixed pages; duplicate texts (Bible reprints, nūpepa reprints, Wikipedia mirrors); eval contamination (CI assertion, not suggestion); accidental publication of prototype-tainted artifacts (CI must refuse to publish `prototype_only=true`); cultural overreach via auto-ingest (use allow-list, not deny-list).

**Next 3 steps for Stage 1:**

1. Land adapter framework + empty manifest in-repo. One source adapter (Hawaiian Wikipedia dump — cleanest, closest to release-eligible) end-to-end through pipeline. Output: `stage1_manifest.parquet` with real rows, packed JSONL, CI check refusing publication of `prototype_only=true`.
2. Add Ulukau nūpepa adapter with ToS snapshot, polite fetch, OCR-confidence capture, paragraph-level LID, manual sample review of ~50 random docs before bulk ingest. Document register and OCR-quality stats per decade.
3. Tokenizer audit + token-count report (Rusty owns tokenizer; Linus supplies corpus + manifest stats). **This is the honest go/no-go gate for Stage 1.**

---

### Stage-2 — Bidirectional en↔haw SFT (target-only loss, 10–20% Hawaiian retention)

**Source tiers**

- **Tier A — true parallel, prototype-usable:**
  - **Baibala Hemolele ↔ public-domain English Bible** (verse-aligned; chapter-level not safe; pin specific Hawaiian translator/year + KJV/ASV); cap ≤30% of Stage-2 parallel-train tokens, **0% of dev/test**.
  - **FLORES-200 `hawn_Latn` / `eng_Latn`** as the **Stage-2 dev/test anchor only — never train.** Hash all FLORES sentences into `eval_hashes.parquet` *before any other Stage-2 ingest*.
  - **OPUS `haw` subsets** — Tatoeba clean; Ubuntu/GNOME/KDE software-l10n tag + cap; **JW300 excluded** pending OPUS ToS recheck.
  - **NLLB-Seed / NLLB mined `haw`-`eng`** — train signal only, never dev/test; re-derive provenance from originating URLs, not HF mirror.
  - **Tatoeba `haw`↔`eng`** (CC-BY 2.0 FR; small but clean smoke-test; hash before deciding train vs dev).
- **Tier B — comparable, alignment scoring required:** Wikipedia interlanguage-link pairs (CC BY-SA 4.0; expect <5k usable sentence pairs); Wikisource pairs; Awaiaulu modern prose; OHA/DOE/UH bilingual PDFs; Ulukau bilingual / annotated holdings; Hawaiian-language news with English summary pages (rare).
- **Tier C — dictionary / glossary:** Pukui-Elbert / Andrews **example sentences** only (headword entries are not pairs — memorizes lexicon, doesn't teach translation); tag `register=dictionary-example`, cap, exclude from dev/test.
- **Tier D — synthetic (capped per prior ADR):** back-translation of Stage-1 Hawaiian via Stage-1-merged base allowed in train, `synthetic=true`, `synthetic_source_model` recorded, ≤25% cap, **0% dev/test**, source-model ToS must permit training derivatives. Forward-translation suggested ≤10% inside the 25% cap (translationese feedback risk). Dictionary-templated synthesis excluded (teaches templates, not translation).
- **Tier E — excluded:** hard-escalate cultural categories (unchanged); JW300 / proselytizing-org bitext (until ToS re-verified); auto-MT not flagged synthetic; social-media bilingual without permission; ungrounded LLM-generated "Hawaiian dialogues."

**Alignment typing:** every pair carries `alignment_type ∈ {parallel-verse, parallel-sentence, parallel-doc, comparable-aligned, dictionary-example, synthetic-bt, synthetic-ft}`. **Dev/test accepts only `parallel-*`.**

**Pipeline (additions over Stage-1)**

```
per-source adapter (raw fetch + ToS snapshot)
  → per-side LID (catches swapped/mixed sides)
  → per-side normalization (Hawaiian unchanged from Stage-1; English smart-quote/whitespace cleanup)
  → alignment:
      • deterministic for verse-keyed/TMX sources
      • embedding alignment (LaBSE/LASER) for comparable; record alignment_model + per-row alignment_score
  → length-ratio filter (length_ratio_haw_over_en)
  → pair-hash + MinHash dedup; cluster-aware split isolation
  → three-way contamination check:
      (a) Stage-2 eval hashes
      (b) Stage-1 eval hashes
      (c) Stage-1 train hashes via crosslink_stage1_overlap (forbidden in Stage-2 held-out splits)
  → register / cultural / cap tagging
  → stage2_manifest.parquet (per pair)
  → directional JSONL emission (canonical pair → two rows)
```

**`stage2_manifest.parquet` per-pair fields:** `pair_id`, both-side raw + clean hashes, `sha256_pair` (primary contamination key), `alignment_type`, `alignment_method`, `alignment_model`, `alignment_score`, `length_ratio_haw_over_en`, both-side LID + confidence, `direction_original`, `register`, `edition_or_version`, `synthetic` + `synthetic_source_model`, both-side `license_observed`, `license_inferred=null`, `tos_snapshot_id`, `prototype_only=true` / `release_eligible=false` defaults, `dedup_cluster_id`, `crosslink_stage1_overlap`, `alignment_review_required`, `split`.

**JSONL contract:** one canonical pair → **two directional rows** (en→haw and haw→en) with explicit `direction`, `loss_mask=target_only`, instruction resolved into the row (template paraphrases stored separately, not in the prompt set itself); no metadata leakage into instruction or target. Hawaiian-language instruction allowed for haw→en. **Retention slice:** monolingual Hawaiian rows in same JSONL file, `direction=haw-mono`, `loss_mask=all_target`, **10–20% by token** per the two-stage ADR.

**Excluded from JSONL:** prompts in target / source leakage; sub-threshold alignments; Bible duplicates beyond cap; anything in `eval_hashes`; Stage-1 eval-hash overlaps on the haw side; hard-escalate cultural categories; mixed-language sentences; boilerplate (copyright, translator credits, chapter headers, TMX metadata, URLs); unflagged auto-MT; dictionary headword-only rows.

**Top risks:** Bible / register skew; verse-style overfitting; tiny-corpus memorization; translationese / synthetic feedback loops; OCR'd bilingual PDF misalignment; English tokens leaking into Hawaiian targets; FLORES leakage given small corpus; direction-confused training; prototype lineage leaking into released artifacts; cross-stage contamination; unbalanced `direction_original`; cultural overreach in outputs.

**Next 3 steps for Stage 2 (post-Stage-1 only):**

1. FLORES-200 adapter + populated `eval_hashes.parquet` + CI assertion landing **before any other Stage-2 ingest**.
2. Bible verse-aligned adapter with pinned Hawaiian + English editions and the ≤30% / 0%-dev-test cap enforced.
3. Tatoeba + one Wiki-aligned LaBSE slice + retention slice → tiny Stage-2 prototype dataset and a register / direction report as the Stage-2 go/no-go gate.

---

### Implications

- Linus's prior data-gate posture and the Prototype-vs-release ADR are unchanged; this ADR adds the *concrete pipeline* both stages run through.
- Stage-2 cannot break ground until Stage-1 produces real `stage1_manifest.parquet` rows and a populated `eval_hashes.parquet`.
- Rusty's tokenizer audit is the Stage-1 go/no-go gate; ensures register skew + diacritic handling are characterized before any DAPT smoke test.
- README is out of date with respect to Stage-1 → Stage-2 sequencing; flagged for a follow-up Scribe pass (not edited here).

### Open team gaps (carry forward, unchanged)

- **Cultural-review owner unassigned** — softer at prototype; remains *the* blocker for any release path.
- **Hawaiian-literate alignment / OCR spot-checker** — needed for Stage-2 alignment threshold tuning and Stage-1 nūpepa OCR sample review.
- **Bible edition rights** — pinned editions (Hawaiian translator/year + English KJV/ASV public-domain) need confirmation before Stage-2 Bible adapter ships.
- **Raw-archive storage location** (not in git) — Livingston cost input requested.

### Provenance

Consolidates two inbox proposals (now deleted): `linus-stage1-data-pipeline.md`, `linus-stage2-data-pipeline.md`. See orchestration-log entries dated 2026-04-29T03:13:13Z.

---

## Chaining Free GPU Providers for LLM Training

### TL;DR: Basher + Livingston

**Status:** Adopted  
**Date:** 2026-04-29  
**Owners:** Basher (Training Engineer), Livingston (Cost Strategist)

**Decision:** Chaining free GPU providers (Kaggle → Colab → Lightning → etc.) is technically feasible and operationally worthwhile *only for LoRA/QLoRA sequential fine-tuning*. Not viable for multi-node pretraining or release-quality runs. Practical ceiling: ~85 T4-hr/week with friction. Recommendation: iterate on Kaggle alone; chain only when weekly budget is exceeded; reserve $10–$40 of A100/H100 spot compute for final release run.

### Basher's Assessment: Technical Feasibility

**Feasible — but only for parameter-efficient fine-tuning.** The right mental model is "sequential preemption survival," not distributed cluster. What travels between providers:

- **LoRA adapter weights** (~50–500 MB)
- **Optimizer state + scheduler state + RNG state** (~2× adapter size, portable if saved to CPU and reloaded to device)
- **Dataloader position + global step** (the sneaky cost)
- **Environment lock** (versions + GPU type + CUDA)

**Total payload per 7B QLoRA checkpoint:** ~0.5–2 GB, uploadable to HF Hub in minutes.

**Portable checkpoint contract (recommended):**
- `adapter_model.safetensors` (LoRA only)
- `optimizer.pt`, `scheduler.pt`, `rng_state.pt`, `trainer_state.json`
- `training_args.bin`
- `dataloader_state.pt` or `epoch + global_step` if epoch-aligned
- `env.lock` (versions, GPU type, CUDA)

**Why it fails for full pretraining:** DeepSpeed ZeRO-2/3 and FSDP shard optimizer state across ranks. Checkpoints at `world_size=8` don't resume cleanly at `world_size=2` without `zero_to_fp32.py` or FSDP consolidation. No shared filesystem, no NCCL across providers. You can only *sequence*, not *parallelize*.

**Real risks at the hand-off seam:**

1. **Quantization non-determinism (bitsandbytes).** 4-bit kernels are not bit-exact across CUDA versions or GPU architectures (T4 vs Ada vs Hopper). Adapter still loads but loss curve jitters. Mitigation: pin `bitsandbytes`, `transformers`, `peft`, `accelerate`, `torch`, `cuda` in `requirements.txt` traveled with checkpoint; accept minor stair-stepping.

2. **GPU heterogeneity.** Kaggle T4×2 → Colab T4 → Lightning A10 changes effective batch size. Keep `per_device_train_batch_size` low and recompute `gradient_accumulation_steps` on resume to preserve global batch size.

3. **Mid-epoch resume cost.** HF Trainer's default dataloader re-iterates from the start on resume. At 9-hour budgets this is fatal. Solutions: checkpoint on epoch boundaries (cheapest), use stateful dataloader (`use_stateful_dataloader=True`), or pre-shard dataset and track `(shard_id, offset)`.

4. **Tokenizer / base-weights drift.** If providers pull base model from Hub at different times, adapter may load on wrong base. Mitigation: pin `revision=<sha>` everywhere.

5. **Session preemption.** Colab kills idle sessions; quota expiry is fast. Save every N minutes via `TrainerCallback`, plus `try/finally` save-on-exit.

6. **ToS.** Free tiers forbid multi-account gaming on the same provider. Using *different* providers under one real identity is fine; using burner accounts on Kaggle is not.

**Practical workflow (if adopted):**
- Environment = `requirements.txt` + base model `revision=<sha>` + tokenizer hash.
- Storage = HF Hub private repo (canonical) + Drive backup.
- Save policy: every 30 min *and* on exit, plus epoch end. Push to Hub in background.
- Resume policy: pull latest snapshot, verify `env.lock`, reload, **recompute `gradient_accumulation_steps`**, then resume.
- Provider order: Kaggle first (30 hr/wk, 9 hr sessions, dual T4, persistent disk). Then Lightning (~22 hr/mo). Colab for short bursts only. Avoid Paperspace (M4000 too weak).
- **Validate each hop:** quick eval-loss check on same minibatch before and after transfer. Loss jump >~5% signals environment drift.

**Implications for Hawaiian LLM:**
- Formalizes what we already committed to: 7B Stage-1 CPT on Kaggle T4×2, Stage-2 SFT possibly on different provider. Adopting checkpoint contract costs nothing, saves run if any provider revokes free tier.
- Does *not* unlock pretraining. Still fine-tuning a pretrained base, not pretraining from scratch.
- Does *not* change reserve A100 spot burst for final release run.

### Livingston's Assessment: Cost & Operations

**Free/free-tier GPU ceiling (2026-04):**

| Service | GPU | Free quota | Useful for chaining? |
|---|---|---|---|
| **Kaggle Notebooks** | P100 16GB or 2×T4 | ~30 hr/wk | **Yes — best anchor** |
| **Google Colab Free** | T4 (no guarantee) | ~40 T4 hr/mo | Yes, unreliable |
| **Lightning AI Studio** | T4 (interruptible) | ~20–22 T4 hr/mo | Yes, small slice |
| **Modal Starter** | T4/L4/A10 | $30/mo credit (~50 T4 hr) | Yes — flexible |
| **SageMaker Studio Lab** | T4 | 4 hr/24 hr GPU | Marginal (too short) |
| **HF Spaces ZeroGPU** | A100 slice | ~25 min/day PRO | **No — function-call shape, not training** |
| **Paperspace Gradient Free** | M4000 (legacy) | Limited | Too weak |

**Realistic combined budget:**
- Kaggle: ~30 T4-hr/week
- Colab: ~10 T4-hr/week (unreliable)
- Lightning: ~5 T4-hr/week
- Modal: ~12 T4-hr/week (with $30 monthly spend)
- **Total ceiling: ~85 T4-hr/week ≈ 340/mo, with significant friction**

For a 7B QLoRA on 50–200M tokens, one clean A100 40GB run is ~10–20 hr. Chained free-tier ceiling *can* cover it on paper, but each hop costs 15–60 min setup tax and adds risk.

**Hard constraints:**
- **ToS:** Multi-accounting the same provider (e.g., burner Kaggle accounts) violates ToS and risks suspension. Using *different* providers under one real identity is fine.
- **No GPU guarantee:** Colab may stall indefinitely waiting for a T4.
- **Idle disconnects + session caps:** No single 30-hour run; you chain 4–9 hour fragments.
- **Optimizer-state size dominates checkpoint uploads.**
- **bitsandbytes / kernel drift between providers is common.**

**Recommendation for Hawaiian-LLM:**

1. **Iterate on Kaggle alone.** 30 hr/wk on P100 or 2×T4 is enough for QLoRA 7B prototype loops. Don't chain unless you actually need more.
2. **Chain only when justified:** add Colab + Lightning + Modal *only* when experiment exceeds Kaggle's weekly window. Standardize on HF Hub as checkpoint bus, with optimizer state + RNG saved.
3. **Treat ZeroGPU as eval/demo infrastructure, not training.**
4. **For release-quality run, stop chaining.** Pay for ~10–20 hr of A100/H100 on Lambda, RunPod, or Vast.ai. Current spot floors: Vast.ai RTX 3090 ~$0.05–0.13/hr; A100 80GB PCIe ~$0.29–0.73/hr; RunPod A100 PCIe 40GB ~$0.42/hr spot. A clean release run is **$10–$40 of GPU**, which is cheaper than engineering hours lost to chaining instability.
5. **Pursue grants in parallel.** Google Research Credits, AWS Activate, Azure for Research, MS Founders Hub, NSF/NEH DEL, ANA Esther Martinez, Endangered Language Fund — all relevant for Hawaiian; multi-month cycles; don't gate on them.
6. **Do not multi-account.** Ban risk; marginal value is negative.

**When chaining IS worth it:**
- Personal learning / hobby projects with no deadline.
- Single QLoRA experiment barely overflowing one provider's weekly cap.
- Teams with strong ops discipline (pinned envs, automated push/pull, resumable trainer).

**When chaining is NOT worth it:**
- Anything release-quality or on a deadline.
- Full-precision fine-tunes (checkpoint sizes + kernel drift).
- Distributed / multi-node (free tiers don't compose into one cluster).
- Workloads needing guaranteed GPU availability.

**Cost framing:** This does *not* change the README's $10k–$30k practical training tier or leftover-Azure-credit framing. It clarifies the *bottom* of the stack: free chaining is for QLoRA iteration; paid spot GPUs are for release runs; grants are parallel pursuit, not critical path.

### Implications

- Formalizes Hawaiian-LLM Stage-1 workflow: Kaggle T4×2 iteration, then reserve A100 spot for release run.
- Enables rapid prototyping without multi-account risk.
- Clarifies ToS boundaries and operational friction for any future multi-provider experiment.
- Does *not* unlock pretraining; still fine-tuning a pretrained base.

### Provenance

Basher + Livingston joint deep-dive on GPU compute chaining feasibility. See orchestration-log entries 2026-04-29T03:13:13Z (Basher), 2026-04-29T03:13:14Z (Livingston). Inbox files merged and deleted from `.squad/decisions/inbox/`.

## Decision: Project scope is learning prototype only — no public release planned

**Author:** Danny (Lead / Architect)  
**Date:** 2026-04-29  
**Status:** Accepted (per user direction)

### Context

User clarified: *"yeah update any docs that say this is going to be released, its just a prototype, a learning project."* Existing docs (README + `docs/training-pipeline.md` + `docs/data-pipeline.md`) had language implying weights/tokenizer/dataset would be released once work landed, plus a Week-7 "prepare a release" milestone. That framing misrepresents the project's actual scope.

### Decision

This project is, and is being documented as, a **learning prototype**. There is **no plan** to publicly release model weights, adapters, tokenizer artifacts, datasets, demos, or hosted services out of this repo.

The existing **prototype-vs-release ADR** in `.squad/decisions.md` is preserved as conditional/hypothetical guidance — it describes the gates that would apply *if* the project ever changed posture toward release. It is not a roadmap or commitment.

### What changed in docs (2026-04-29)

- `README.md`: banner, Goals, Non-Goals, Evaluation, Roadmap Week 7, and License (intent) sections rewritten to reflect prototype-only scope.
- `docs/training-pipeline.md`: top banner explicitly states no public release is planned; "release-candidate" scope reframed as hypothetical.
- `docs/data-pipeline.md`: status banner and "Prototype vs Release" section intro clarify only the Prototype column is operative.

### Trade-offs

- **Pro:** Honest framing; sets correct expectations for contributors and readers; removes implicit promise about shipping a Hawaiian-language model, which carries real cultural-review weight per the existing ADR.
- **Pro:** Preserves the prototype-vs-release ADR machinery as a teaching artifact and as a graceful upgrade path if scope ever changes.
- **Con:** Slightly weakens the "we're building toward something" energy of the original README. Acceptable: that energy was overstating reality.
- **Con:** Future contributors may need to re-litigate the release question if they want to publish anything. Acceptable: that's the right gate.

### Implications for the team

- **Linus / Basher / Rusty:** any artifact production work should assume `intended_use=prototype_private` end-to-end. Do not stand up release-only tooling unless and until this decision is revisited.
- **Livingston:** budget framing in README is now hypothetical ("what it would cost") rather than a spend plan.
- **Future contributors:** if anyone proposes publishing weights, datasets, or a hosted demo, they need to revisit *both* this decision and the prototype-vs-release ADR — not just one.

### Alternatives considered

1. **Strip the prototype-vs-release ADR entirely.** Rejected: the ADR captures useful thinking about cultural-review gates and lineage; throwing it out loses learning.
2. **Leave docs as-is and just add a top-level disclaimer.** Rejected: too easy to miss; the Goals/Roadmap/License sections were affirmatively claiming release intent.
3. **Mark the repo archived.** Out of scope; the user wants to keep working on it as a learning effort.

---

## User Directive: Free-tier GPU provider chaining acceptable for prototype

**Date:** 2026-04-29T03:53:18Z  
**By:** yashasg (via Copilot)  
**Status:** Recorded

### Directive

Prototype work is limited to experiments and iteration using a pre-existing model, so chaining free GPU providers is acceptable. Provider-specific API names and resource identifiers may change when switching providers and must be accounted for.

### Rationale

User approval of the prototype-to-release distinction means free-tier chaining with documented provider-switch friction is acceptable risk for learning iteration. Aligns with ADR "GPU compute chaining feasibility" (2026-04-29).

---

## User Directive: Document as learning prototype, not release effort

**Date:** 2026-04-29T03:54:03Z  
**By:** yashasg (via Copilot)  
**Status:** Recorded

### Directive

The project should be documented as a prototype and learning project, not as a release or production effort. This directive motivated the Danny scope reframe across `README.md`, `docs/training-pipeline.md`, and `docs/data-pipeline.md`.

### Rationale

User request — captured for team memory and to ensure all future doc updates maintain this framing.

---
## Advisory: Chinese GPU Providers — Pricing vs. Fit

**Date:** 2026-04-29  
**Status:** Advisory (no ADR; user-facing recommendation)  
**Owners:** Livingston (Cost Strategist), Basher (Training Engineer)

### Headline

Chinese marketplace GPU providers (AutoDL, Featurize, OpenBayes) are **30–60% cheaper per GPU-hour** on paper (AutoDL RTX 4090 ~$0.27/hr vs RunPod $0.34–0.44/hr; A100/A800 ~$0.48–$0.69/hr vs RunPod $1.19/hr), but **do not recommend switching this prototype to them**. Absolute savings are small (~$3–$18 across 15–25 GPU-hr prototype), and seams around the stack (registration wall, Great Firewall friction on HF Hub push, language barrier, data governance) exceed the benefit.

Big Chinese enterprise clouds (Alibaba, Tencent, Huawei, Baidu) at list price are **2–4× more expensive** than RunPod and Lambda. Not cheaper.

### Cost Analysis

| Provider | GPU | RMB/hr | USD/hr | vs RunPod A100 $1.19 |
|---|---|---|---|---|
| AutoDL | RTX 4090 24GB | ¥1.98 | $0.27 | ~50% of 4090 price |
| AutoDL | A100 40GB | ¥3.45 | $0.48 | 40% |
| AutoDL | A800/A100 80GB | ¥4.98 | $0.69 | 58% |
| Alibaba Cloud (list) | A100 80GB | ¥34.74 | $4.80 | 4× RunPod |

**Prototype math:** 7B QLoRA ~15–25 A100-hr. RunPod: ~$18–30. AutoDL: ~$7–12. **Savings: $10–18** — not enough to overcome friction.

### Fit Assessment

**Hardware:** RTX 4090 / 4090D / A800 / H800 / L20 all run our recipe unchanged (CUDA 12.x, PyTorch, bnb NF4, flash-attn 2, bf16). AutoDL infrastructure is solid (persistent storage, image-level CUDA pinning, checkpoint cadence).

**Red flags:**

1. **HF Hub push unreliable from mainland China.** Mirrors (hf-mirror.com) handle pulls fine; pushes (our checkpoint bus per existing ADR) are flaky. Workarounds (US relay, S3 backup) break the "provider-hop" property of our chaining approach.
2. **Registration gate:** +86 mobile + Chinese ID (身份证) required; foreign credit cards rejected. Dead end for US individuals without a collaborator.
3. **GitHub slow:** large clones need mirrors.
4. **Chinese-only support:** outside AutoDL, consoles are in Chinese; English support is sparse.
5. **Data governance:** PRC (PIPL/DSL) over training data — acceptable for public-domain corpus, but adds governance friction for a learning project.
6. **Latency:** 150–200 ms SSH RTT from US West Coast; tolerable for terminal, painful for interactive work.

**Ascend 910B is a hard no:** different kernel ecosystem (CANN/torch_npu, not CUDA), no bnb NF4, no flash-attn 2. Multi-week port for *worse* $/result than a 4090 on AutoDL. Reconsider only if prototype leaves QLoRA for multi-node bf16 full fine-tune (out of charter).

### Recommendation

**Do not move this prototype to Chinese providers.** Headline savings do not justify registration friction, HF push unreliability, and support/governance seams.

**When Chinese providers would make sense:**
- Team member physically in China with real-name verification, Alipay, +86 phone.
- Multi-month 4090 iteration (monthly subscription is meaningfully cheaper than US hourly spot).
- Non-sensitive data + willingness to work around HF push or use non-HF checkpoint flow.
- For *this* project: none of the above apply.

**Keep existing stack:** Kaggle (free, 30 hr/wk) + RunPod community A100 40GB ($1.19/hr for short bursts) + Lightning Pro ($20/mo for persistent Studio) + existing Azure credits (reserve for release-candidate run if ever needed) = ~$130/mo soft cap, fits README's $10k–$30k practical tier.

**Hard rule:** If the project ever reaches release-candidate status, that run must be on a non-PRC provider with pinned driver + single continuous GPU. Chinese providers are out of scope for that run regardless of price. This aligns with existing data-governance ADR.

### Implications

- **Livingston:** README budget unchanged. China pricing was investigated and rejected on technical-fit grounds, not cost grounds; $10k–$30k practical tier stands.
- **Basher:** HF Hub push reliability is now part of the provider-fit checklist alongside CUDA pinning and bnb/FA2 wheel availability. Provider-hop contract requires checkpoint-bus reliability.
- **Linus:** PIPL/DSL note for team awareness. Our public-domain corpus is not affected; broader context if scope expands to community-restricted material in future.
- **All:** If a trusted Chinese collaborator joins and wants to use AutoDL for Stage 1 experiments, revisit this decision; it is a "no" for the current US-based setup, not an absolute "no."

### Sources

- **Pricing:** AutoDL (autodl.com, Zhihu, CNBlogs market reviews), Featurize (featurize.cn), OpenBayes (openbayes.com/pricing), Alibaba Cloud (aliyunbaike.com, cloudgputracker.com), RMB→USD ~7.2 (late 2025 / early 2026)
- **Hardware fit:** AutoDL CUDA images, Basher QLoRA recipe testing, NVIDIA Ampere/Hopper specs
- **Red flags:** HF-mirror.com convention, GFW throttling reports (HuggingFace Discussions), Ascend CANN/torch_npu (Huawei repos, PEFT issues)
- **Export controls:** US BIS Oct-2022 / Oct-2023 (A800/H800/L20/H20 specs)

---

## Decision Note: Hawaiian source URL inventory routed by installed tool

**Date:** 2026-04-29  
**Status:** Proposed — team awareness  
**Owner:** Frank (Hawaiian Data Collector)

### Decision

Landed `docs/hawaiian-data-sources.json` as the canonical, tool-bucketed URL inventory for Hawaiian-language and Hawaiian-parallel sources. Each entry is routed to exactly one of the tools installed by `scripts/setup.sh` / `requirements.txt`.

### Bucket → tool routing

- `requests_tenacity` — Wikimedia dumps (`hawwiki`, `hawwiktionary`), Wikipedia langlinks API, FLORES-200 hawn_Latn (eval-only), Tatoeba haw exports, OPUS haw subsets, baibala.org verse pages, eBible KJV/ASV USFM.
- `internetarchive` — archive.org Ulukau-mirrored nūpepa items, Hawaiian books / dictionaries / readers, archival Baibala Hemolele scans.
- `wayback_cdx_toolkit` — Historical snapshots of Ulukau, nupepa.org / nupepa-hawaii.com, OHA, DOE Kaiapuni, UH PDFs.
- `scrapy_scrapy_warc` — Live polite crawls of Ulukau, Hawaiian Wikisource, Awaiaulu, OHA / Ka Wai Ola, DOE Kaiapuni, UH ScholarSpace, with WARC + ToS snapshot per crawl.
- `trafilatura_selectolax` — Post-fetch main-text extraction; not a fetcher.
- `yt_dlp` — Captions-only, intentionally empty until per-channel rights confirmation.

### Rights posture

- Default to `rights_status_hint` values (`public_domain_candidate`, `open_license_candidate`, `rights_review_required`, `eval_only`, `unknown_review_required`). No bare "public domain" claims.
- FLORES-200 is `eval_only`, P0, and must be hashed into `eval_hashes.parquet` before any other ingest (per `docs/data-pipeline.md` §Stage 2).
- Pre-1925 nūpepa kept `prototype_only=true`; bulk publication remains out of scope.
- JW300 and hard-escalate cultural categories (mele, oli, pule, moʻolelo from named tradition-bearers, moʻokūʻauhau) are listed under `deferred_or_excluded` so future agents don't re-add them by accident.

### Why this matters to the team

- **Linus** — the JSON is the per-source manifest seed. Every entry already enumerates the provenance fields adapters must capture, plus a `tos_or_license_url` to snapshot at fetch time. Please flag any source I should downgrade before adapter work begins (especially Awaiaulu / OHA / DOE / UH and the OPUS subsets).
- **Rusty** — Wikimedia dumps and Hawaiian Wiktionary are P0/P2 and are the cleanest fodder for the tokenizer audit (ʻokina U+02BB + kahakō, NFC). Bible is capped per the Stage-2 ADR (≤30% parallel-train, 0% dev/test).
- **Coordinator** — first build-out should be the P0 entries (`hawwiki` dump, FLORES-200 eval hashing, Tatoeba haw, baibala.org + eBible verse anchor). Everything else is gated on rights review.

### Open questions

1. Pinned Hawaiian Bible edition (e.g., 1868 Andrews/Bingham) — needs a human pick before adapter work.
2. Whether OHA / DOE / UH bilingual PDFs are in scope for this prototype, or deferred entirely.
3. Whether any Hawaiian-language YouTube channel has an explicit reuse license; until confirmed, the `yt_dlp` bucket stays empty.

### Artifact

- `docs/hawaiian-data-sources.json` (validated to parse with Python).

---

## Decision Note: Storage formats per pipeline layer

**Date:** 2026-04-29  
**Status:** Proposed — team awareness  
**Owner:** Linus (Data Engineer)

### Context

Existing ADRs name `stage1_manifest.parquet`, `stage2_manifest.parquet`, `eval_hashes.parquet`, and JSONL training text, but the *raw fetch*, *extraction/intermediate*, *URL inventory*, and *packed/tokenized* layers were not pinned to formats in one place. Adapters need a contract before the first source lands.

### Decision

One format per layer. Manifests are queryable; training text is line-streamable; raw is replayable.

| Layer | Format | Path |
|---|---|---|
| URL inventory (input contract, in git) | JSON | `data-sources/hawaiian-data-sources.json` |
| Raw web/HTML fetch | WARC (`.warc.gz`) | `data/raw/{source}/{fetch_date}/*.warc.gz` |
| Raw non-HTML originals (PDF, dump tar, TSV, IA items) | Native bytes, untouched, sha256-named, with `fetch.jsonl` sidecar | `data/raw/{source}/{fetch_date}/{sha256}.{ext}` |
| Extraction / intermediate text (incl. OCR) | Gzipped JSONL, one record per doc/page | `data/extracted/{source}/{fetch_date}/*.jsonl.gz` |
| Stage 1 manifest | Parquet (zstd) | `data/stage1/stage1_manifest.parquet` |
| Stage 1 training text | Gzipped JSONL | `data/stage1/stage1.jsonl.gz` |
| Stage 1 packed/tokenized | `.bin`/`.npy` + sidecar `index.json` | `data/stage1/packed/` |
| Stage 2 manifest | Parquet (zstd) | `data/stage2/stage2_manifest.parquet` |
| Stage 2 training text | Gzipped JSONL (two directional rows per pair + retention slice) + `templates.json` | `data/stage2/stage2.jsonl.gz`, `data/stage2/templates.json` |
| Eval / contamination ledger | Parquet (zstd) | `data/eval/eval_hashes.parquet` |
| Schemas (in git) | JSON Schema | `docs/schemas/*.json` |

### Format rules

1. **Parquet for manifests / hashes**, JSONL for trainer-facing text.
2. **Gzip** (`.jsonl.gz`) for any text artifact larger than a few MB. **Zstd** for Parquet.
3. **One file per (source, fetch_date)** at raw and extracted layers; never append across fetches. Re-fetches produce a new directory.
4. **No CSV** past bootstrap — quoting/encoding bugs eat Hawaiian diacritics. The `.csv` bootstrap noted in the prototype-manifest ADR is for first-day scaffolding; promote to Parquet as soon as the validator runs.
5. **Hashes are the join keys** across layers (`sha256_raw`, `sha256_clean`, `sha256_pair`); never join on path.
6. **Manifest fields stay out of training JSONL lines** so the model can't memorize URLs, dates, or licenses.
7. **Nothing in `data/` is committed to git.** Only the URL inventory and schemas are in-repo. Raw archive storage location remains a Livingston-input open gap.

### Consequences

- Adapters have a single contract: read URL inventory JSON → write WARC + `fetch.jsonl` → emit `extracted/*.jsonl.gz` → manifest validator writes the Parquet row.
- Tooling already in `requirements.txt` covers this stack: `warcio`, `scrapy-warc`, `trafilatura`, `selectolax`, `datasketch`. Parquet/Arrow is a new (small) dep — `pyarrow` to be added to `requirements.txt` when the manifest validator lands.
- Promotion to release-eligible later does not require a re-encode: schemas are a strict subset of the release schema (per prior ADR).

### Non-decisions (deferred)

- Raw archive storage location (local disk vs. cheap blob) — Livingston cost input still pending.
- Compression codec for Parquet (zstd default; revisit only if a tool can't read it).
- Sharding strategy for `stage1.jsonl.gz` / `stage2.jsonl.gz` — flat single file until size forces sharding.

---

## User Directive: Directory structure — Markdown in `docs/`, data inventories in `data-sources/`

**Date:** 2026-04-29T05:51:08Z  
**Status:** Accepted (user directive)  
**Owner:** yashasg (via Copilot)

### Decision

`docs/` is reserved for Markdown documentation and ADRs. Data-source inventories (JSON, CSV, manifests, reference files) belong in a top-level `data-sources/` directory.

### Context

Project structure clarification to avoid mixing documentation markup with data reference files.

### Consequence

- `.squad/` references to `docs/hawaiian-data-sources.json` are now outdated provenance; the canonical path is `data-sources/hawaiian-data-sources.json`.
- Future data-source inventory, manifest templates, and schema files go in `data-sources/` instead of `docs/`.
- `docs/` remains the home for all Markdown specs, ADRs, and architectural documentation.

---

---

## Decision Note: Where data lives (and why GitHub is not the answer)

**Date:** 2026-04-29  
**Status:** Proposed — team awareness  
**Owner:** Linus (Data Engineer)  
**Closes open gap:** "Raw archive storage location TBD" (from Stage-1/Stage-2 ADRs)

### Decision

GitHub holds **code, schemas, docs, and the URL inventory**. Nothing else. Raw bytes, manifests, training JSONL, packed tensors, and the eval-hash ledger live **off-git**, on a single private disk (local workstation + external backup) for the prototype. **No GitHub LFS.**

### Context

Three prior ADRs named storage formats and named an open gap: "raw archive storage location TBD." The team lacks clarity on whether a GitHub repo (public or private), Git LFS, or local disk is appropriate for a prototype Hawaiian cultural corpus. Linus has flagged that posting raw WARCs/OCR/manifests to any Git host is a redistribution event we cannot justify per-source before a licensing review is complete.

### What goes in the GitHub repo

| Artifact | Path | Format | Why in git |
|---|---|---|---|
| URL inventory | `data-sources/hawaiian-data-sources.json` | JSON | Tiny, text, reviewable, the spec for adapters |
| Pipeline / training docs | `docs/*.md` | Markdown | Design narrative |
| Per-source adapter code + configs | `scripts/`, future `src/` | Python / TOML / JSON | This is the code |
| Manifest / JSONL **schemas** (when written) | `schemas/*.json` | JSON Schema | Contract, not data |
| Setup / tooling | `requirements.txt`, `scripts/setup.sh` | text | Reproducibility |
| ADRs / team notes | `.squad/`, `README.md` | Markdown | Already there |

Rule of thumb: if it's hand-written, small, and reviewable as a diff, it goes in git. If it's machine-emitted bulk, it doesn't.

### What does **not** go in the GitHub repo

Everything under `data/` from `docs/data-pipeline.md` § Storage formats:

- `data/raw/**` — WARCs, PDFs, dump tars, native bytes, `fetch.jsonl` sidecars
- `data/extracted/**` — gzipped JSONL extraction output (incl. OCR text)
- `data/stage1/stage1_manifest.parquet`, `data/stage1/stage1.jsonl.gz`, `data/stage1/packed/**`
- `data/stage2/stage2_manifest.parquet`, `data/stage2/stage2.jsonl.gz`, `data/stage2/templates.json`
- `data/eval/eval_hashes.parquet`

Add a top-level `data/` ignore line to `.gitignore` to make this mechanical.

### Why not just push it to GitHub (or GitHub LFS)

1. **Prototype posture is explicit.** `docs/data-pipeline.md` and Stage-1/2 ADRs say public sharing of *any* artifact — corpora, manifests, tokenizer, adapters — is out of scope. GitHub (even private repos) is the wrong default surface for rights-sensitive material we have not cleared for redistribution.

2. **Rights / licensing.** The corpus mixes CC-BY-SA Wikipedia, public-domain Bible editions, OCR'd nūpepa with unclear downstream rights, and bilingual PDFs from Awaiaulu/OHA/DOE/UH. We capture `license_observed` per row and keep `license_inferred=null`. Pushing the union to a Git host effectively *re-publishes* it under one location, which we cannot justify per-source. Hawaiian-language material in particular is rights- and culture-sensitive; "git push" is not a license.

3. **Immutability bites us.** Git history is forever. If we later discover a source pull violated ToS or a rightsholder asks for takedown, scrubbing from git history is painful and incomplete (forks, caches, LFS retention).

4. **LFS specifically:**
   - Same redistribution problem as plain git, plus bandwidth/quota costs.
   - WARC + Parquet are append-by-new-file workloads, not the small-binary-asset workflow LFS is designed for.
   - LFS objects on private repos still egress to GitHub's storage; it doesn't change the rights story.
   - Deleting LFS objects requires repo-admin gymnastics; not the right fit for "prototype, may need to nuke and re-fetch."

5. **Repo hygiene.** A 30M-token Stage-1 corpus + WARCs + manifests will easily reach tens of GB. That makes clones slow and CI unhappy. Code repos should stay code-sized.

### Where the data **does** live (prototype scale)

Single source of truth: a local directory tree on one workstation, mirrored to one external disk. No cloud by default.

```
~/data/ideal-spoon/         # or wherever; not under the git repo
  raw/{source}/{fetch_date}/...        # WARCs + native bytes + fetch.jsonl
  extracted/{source}/{fetch_date}/*.jsonl.gz
  stage1/stage1_manifest.parquet
  stage1/stage1.jsonl.gz
  stage1/packed/...
  stage2/stage2_manifest.parquet
  stage2/stage2.jsonl.gz
  eval/eval_hashes.parquet
```

Operational rules:

- **Path is configurable**, not hardcoded. Adapters read `IDEAL_SPOON_DATA_ROOT` (or a `config.toml`) and default to `./data/` *outside* the git checkout.
- **`raw/` is immutable and append-only.** Re-fetches go to a new `{fetch_date}` dir; never overwrite. SHA-256 of each raw blob is the provenance key (already in the ADR).
- **One offline backup** of `raw/` on an external disk. Everything else (`extracted/`, `stage1/`, `stage2/`, `eval/`) is reproducible from `raw/` + code, so it's cheaper to lose; backing up `raw/` is the must-have.
- **Encrypt-at-rest** on the workstation disk (FileVault / LUKS) — cheap, matches the rights-sensitive posture.

### If/when local stops being enough

Use the Azure leftover-credit channel already approved in `.squad/decisions.md` ("Azure leftover credit is experiment budget"):

- **Azure Blob Storage**, single private container, no anonymous access, no static-website hosting. Same hash-keyed layout as local. SAS tokens only, short-lived, never committed.
- One container per logical layer (`raw`, `derived`) so we can apply different retention policies and ACLs.
- Manifests + `eval_hashes.parquet` can ride in the same container; they're small.
- **Still not GitHub, still not LFS.** Cloud move is a backup/sharing-with-self question, not a publication question.

A managed dataset hub (HF Datasets, Kaggle) is **not** appropriate for this project at any tier until a named cultural reviewer + per-source rights clearance exist. That gate is currently open (see prior ADRs).

### Action items

1. Add `data/` to `.gitignore` (pre-emptive; the dir doesn't exist yet but adapters will create it).
2. Adapters resolve data root from env/config, default outside the repo.
3. Document this in `docs/data-pipeline.md` as a short "Storage location" note under § Storage formats — one paragraph, points at this ADR. *(Defer the doc edit until this proposal is accepted; don't preempt.)*
4. Open gap to keep tracking: cultural-review owner — unrelated to storage, but blocks any future "share this dataset" conversation regardless of where the bytes sit.

### Non-decisions (deliberately left open)

- Choice of cloud provider beyond "Azure if we need one, because the credit exists." If Azure credit goes away, revisit.
- Whether to ever publish a *derived, rights-cleared* slice (e.g., Wikipedia-only Stage-1 manifest). That is a separate decision after a cultural reviewer is named and rights are audited per source.

---

## Decision Note: Data storage for prototype — local disk, Azure backup Phase 1, B2/R2 fallback

**Date:** 2026-04-29  
**Status:** Proposed — team awareness  
**Owner:** Livingston (Cost Strategist)

### Decision

**Hybrid layout, no surprises:**

1. **Git repository (`yashasg/ideal-spoon`)** — code, schemas, URL inventories (`data-sources/*.json`), ADRs/docs, `requirements.txt`, small JSON/YAML configs. **Nothing under `data/` is committed** (already enforced by `.gitignore` patterns + `data-pipeline.md` invariants).

2. **Local external disk** (or large internal SSD on the workstation) — primary `data/raw/`, `data/extracted/`, `data/stage1/`, `data/stage2/`. Path-of-truth for actual training. SHA-256 keyed per pipeline spec.

3. **Off-site backup of `data/raw/` only** — immutable WARCs + native originals, mirrored as-is by SHA-256.
   - **First choice while credits last:** Azure Blob, Hot LRS, single Storage Account `hawaiianllmraw<suffix>`, single container `raw`, lifecycle rule moves objects >30 days to Cool. Spend tracked under the existing `project=hawaiian-llm` tag and ~$50–$60/mo credit envelope; storage at this scale is ~$1/mo, well inside the noise floor of that budget.
   - **When credits expire / project outlives Azure access:** migrate to **Backblaze B2** (cheapest) or **Cloudflare R2** (zero egress; preferred if we expect to repeatedly pull shards onto rented GPUs). Both are S3-compatible — same `boto3` / `rclone` code path, swap endpoint + keys.

4. **Provenance manifests (`*_manifest.parquet`, `eval_hashes.parquet`)** — Parquet files are small (tens of MB). Keep authoritative copies on the local disk + off-site backup; do **not** commit them to git either (they reference content, not source code, and they will churn).

5. **Hugging Face Hub** — reserved for *adapter checkpoints during training* and, eventually, *releasable* derived artifacts. **Not** the raw corpus, **not** while the rights review is open.

### Data shape (what we're sizing for)

Per `docs/data-pipeline.md`:
- Raw WARCs + native PDFs/dumps, SHA-256 keyed, immutable, **not in git** — tens of GB plausible at full prototype scope (Ulukau + nūpepa + IA items + Wikisource dumps).
- Extracted JSONL.gz: low single-digit GB.
- Stage-1/Stage-2 Parquet manifests + `eval_hashes.parquet`: tens of MB.
- Stage-1 packed/tokenized `.bin`: a few GB.
- Trainer JSONL.gz: a few GB.

Working assumption for sizing: **20–80 GB raw + ~10 GB derived**.

### Cost summary (prototype)

| Layer | Where | Cost |
|---|---|---|
| Source code + small artifacts | GitHub | $0 |
| Working raw/derived data (~30–80 GB) | Local external disk | one-time HW |
| Off-site raw backup (~30–80 GB), Phase 1 | Azure Blob Hot LRS | <$2/mo, paid from existing leftover credit |
| Off-site raw backup, Phase 2 (post-credits) | Backblaze B2 *or* Cloudflare R2 | $0.30–$1.50/mo |
| Adapter/checkpoint bus during training | HF Hub (private) | $0 |

**Key insight:** Storage cost is negligible at every option other than Git LFS. The decision is dominated by **fit (file size, egress pattern), governance (rights-sensitive, no public release), and operational ergonomics (S3-compatible, mountable with rclone, integrates with existing tooling).**

### Why not the alternatives

| Option | Verdict |
|---|---|
| **GitHub repo (no LFS)** | Hard 100 MB/file cap, soft 1 GB repo cap, terrible for WARCs, public-by-default risk on a public repo, history bloat is permanent. **No.** |
| **Git LFS (GitHub)** | $5 per 50 GB *data pack* — and that's both **storage and bandwidth**. One CI fetch of the corpus eats the monthly bandwidth quota. Re-fetches across machines compound. Pricing is hostile to dataset-sized blobs. **No.** |
| **Hugging Face Datasets — private repo** | Nominally fine technically, but: (a) the project is explicitly **prototype-only, no public release**, and pushing a Hawaiian cultural corpus — even private — to a third-party platform without a provenance/licensing review contradicts Linus's per-document rights stance; (b) HF private quotas and ToS for "private but contains scraped content" are not a hill to die on; (c) we already plan to use HF Hub as the *adapter/checkpoint bus*, not the raw-corpus store. **No, not at prototype scope.** Reconsider only for *derived, releasable* artifacts later. |
| **AWS S3 (Standard)** | ~$1.15 storage + $0.09/GB egress. Egress is the killer once you start pulling shards onto rented GPUs. **Avoid unless already standardized on AWS.** |
| **Cloudflare R2** | ~$0.75 storage, **$0 egress**, S3-compatible. Egress-free is a real advantage when shipping shards to RunPod/Lambda/Vast. Free tier covers up to 10 GB storage + 1M Class-A ops/mo. **Strong fallback / non-Azure default.** |
| **Backblaze B2** | ~$0.30 storage, $0.01/GB egress (free up to 3× daily storage), S3-compatible. Cheapest by absolute storage cost. Egress is fine for our volumes. **Cheapest credible option.** |
| **Azure Blob (Hot LRS)** | ~$0.90 storage, first 100 GB egress/mo free on most accounts; well within the leftover $50–60/mo credit. We already have leftover Azure credits ear-marked as "experiment budget" (see ADR 2026-04-29). Storing the corpus there spends credits that would otherwise expire, keeps it inside one tenant the user already controls, and integrates with the auto-shutdown / RG / tagging guardrails already in place. **Recommended primary off-site copy** while credits last. |
| **Local external disk** | $0/mo (one-time HW cost). Fastest for the RTX 2080 workstation, no quota anxiety, no network. **No off-site redundancy** — single drive failure = full re-fetch from sources, some of which may have rotated/disappeared. **Recommended primary working store**, paired with off-site backup. |

### Rights-sensitive guardrails (non-negotiable)

- Off-site backup bucket is **private**, no public-read ACL, no anonymous list, no static-website hosting.
- Object keys are SHA-256 hex, not URLs / titles — no incidental disclosure of source identifiers via key names.
- No third-party CDN in front.
- Per-document license/provenance lives in the manifest, not in the blob name or metadata.
- If we're ever uncertain whether a source is redistributable, it stays **off** every cloud bucket and lives only on the local disk until Linus signs off.

### What this does *not* decide

- Storage class transitions / retention beyond the 30-day Hot→Cool lifecycle rule.
- Whether to keep `extracted/` and `stage1/`/`stage2/` JSONL off-site too (defaults to *no*, since they are reproducible from `raw/` + pipeline code; revisit if pipeline runtimes get long).
- Multi-region replication. Not justified at prototype scope.
- HF Datasets posture for the eventual *release* artifact — that's a separate decision tied to Linus's licensing review and is explicitly out of scope for this prototype.

### Open questions for the user

1. Is there an existing external SSD/HDD on the workstation, or do we need to budget HW (~$60–$120 for a 1–2 TB external SSD)?
2. Is the Azure tenant the user-personal MSDN one, or an employer tenant? If employer-tenant, **do not** put a Hawaiian cultural corpus there; jump straight to B2/R2.
3. Comfortable standardizing on `rclone` (works against Azure Blob, B2, R2, S3 with one config) for the backup tool, vs writing per-provider scripts?

---


---

## ADR: Stage 1 MVP scope — rights-light candidates only, six-point gate before rights-heavy ingest

**Date:** 2026-04-29  
**Status:** Approved  
**Owner:** Linus (Data Engineer)  
**Affects:** `docs/data-pipeline.md` §Stage 1 source tiers, `data-sources/hawaiian-data-sources.json`

### Question Answered

> Can the 2.5M–7M token "publishable / right-clearable" Stage 1 candidates be enough to start, so we avoid rights-review-heavy work for now?

**Answer:** Yes, for a *prototype* Stage 1 (DAPT/CPT smoke test + tokenizer audit + plumbing validation). No for a *quality* Stage 1 that justifies real GPU spend on a 7B–9B base. The six-point gate below explicitly gates the transition to phase 2.

### Stage 1 MVP — sources IN

All sources currently tagged `open_license_candidate` or `public_domain_candidate` in `data-sources/hawaiian-data-sources.json`:

| Source | Rights tag | Why it's in |
|---|---|---|
| Hawaiian Wikipedia XML dump (`hawwiki`) | `open_license_candidate` (CC BY-SA 4.0 + GFDL) | Cleanest license posture. Already the §Stage 1 "first adapter" target. |
| Hawaiian Wikipedia dump status manifest | `open_license_candidate` | Pin SHA1s for reproducibility. |
| Hawaiian Wiktionary dump | `open_license_candidate` | Same license posture as hawwiki; tiny but free. |
| Hawaiian Wikisource | `open_license_candidate` | Public-domain Hawaiian texts, cleaner than nūpepa OCR. |
| archive.org — Baibala Hemolele pre-1925 scans | `public_domain_candidate` | Pre-1925 → PD in US. Capped at ≤10% of Stage 1 tokens per existing ADR; tag `register=religious-archaic`. |
| Small reviewed long tail | per-doc `inherits_from_source` | Only items that pass **per-doc** human rights review. No bulk OHA / DOE / UH crawls in the MVP. |

Stage-2-only or eval-only entries (interlanguage links, Tatoeba, FLORES-200 devtest) are not part of the Stage 1 MVP and are unaffected by this decision.

### "Rights-light" still requires (non-negotiable)

This is **not** a license-skipping shortcut. Per existing pipeline rules:

1. **Per-document `license_observed`** captured in the manifest — even for CC BY-SA 4.0 / public-domain rows.
2. **Per-document `source_url` + `fetch_date` + payload SHA-256** — same as any other source.
3. **ToS snapshot at fetch time** — Wikimedia ToS URL captured per `provenance_fields_to_capture` already in the inventory.
4. **`license_inferred = null` invariant unchanged.** CC BY-SA is *observed*, not inferred, because the dump declares it.
5. **No raw blobs in git, no public publication of artifacts** — prior ADRs on storage location and prototype scope still bind.

What "rights-light" buys us: *avoiding bulk human rights review of rights-review-heavy collections*, not avoiding manifest discipline.

### Stage 1 MVP — sources DEFERRED

All `rights_review_required` and `unknown_review_required` entries in the inventory:

- Ulukau nūpepa crawl + Wayback CDX nūpepa snapshots
- archive.org Ulukau / Hawaiian newspaper / book mirrors
- OPUS haw subsets, NLLB Seed/MD haw slices (these are Stage 2 anyway)
- Baibala Hemolele official site (modern editions; pre-1925 scans are fine)
- OHA / DOE Kaiapuni / UH bulk crawls and their Wayback snapshots
- Awaiaulu public translations
- Hawaiian-language video transcripts

These remain in the inventory as *known* sources. They are not fetched in the MVP.

### Honest size expectation

Numbers on Hawaiian open-license corpora are small. Order-of-magnitude only:

- `hawwiki` + Wiktionary: low single-digit million tokens after cleanup.
- Wikisource (haw): hundreds of thousands to ~1M tokens, optimistically.
- Pre-1925 Baibala scans (capped ≤10%): contributes a few hundred thousand tokens at most under the cap.
- Reviewed long tail: depends entirely on how much human time we spend.

The user's "2.5M–7M tokens" framing is consistent with this. That is enough for pipeline validation and a tokenizer audit. It is **not** enough on its own to expect strong DAPT signal on a 7B–9B model. Treat MVP corpus as *plumbing-grade*, not *training-grade*.

### Go / No-Go gate before touching rights-review-heavy sources

Do **not** start the Ulukau nūpepa adapter or any bulk `rights_review_required` ingest until **all** of these are true:

1. **MVP corpus exists end-to-end.** `stage1_manifest.parquet`, `stage1.jsonl.gz`, and packed tensors have been produced from hawwiki + Wiktionary + Wikisource + pre-1925 Baibala scans. CI lineage gate refuses public export.

2. **Tokenizer audit completed on the MVP corpus** (Rusty owns; Linus supplies corpus + stats). ʻokina survival, kahakō unitarity, tokens-per-word, byte-fallback rate measured on the candidate bases.

3. **MVP token count and register mix reported.** If MVP alone is demonstrably sufficient for the prototype's stated goal, we may stop here and skip rights-heavy work entirely.

4. **Cultural-review owner named** for the categories the pipeline already hard-escalates (mele / oli / pule, moʻolelo from named tradition-bearers, moʻokūʻauhau). This is required before nūpepa bulk because nūpepa contains these registers.

5. **Per-source rights review process written down**: who reviews, what evidence is recorded in the manifest, how takedown requests are honored, where ToS snapshots live. Not a paragraph in a Slack message — an entry in this decisions log.

6. **Storage and access controls confirmed** for any `prototype_only=true` material (already covered by the local-first storage decision; just verify the gitignore and disk-encryption invariants hold before pulling at scale).

If any of 1–6 is missing, the answer is no-go on rights-heavy ingest.

### What this changes vs. existing docs

- No change to `docs/data-pipeline.md` text required. The existing Tier A/B framing and §"Stage 1 immediate next steps" already sequence hawwiki-first → nūpepa-second. This decision *names the gate* between those two steps explicitly and *defines the MVP set* by rights tag rather than by source name.
- No change to `data-sources/hawaiian-data-sources.json` required; the `rights_status_hint` field already encodes the split.
- If accepted, the MVP set above becomes the binding "Stage 1 phase 1" scope; rights-heavy ingest is "Stage 1 phase 2" and gated.

### Open items for the team

- **Cultural-review owner** — still unfilled. This is the long-pole item for unblocking nūpepa bulk regardless of rights cleanup.
- **Reviewed long-tail budget** — how many human-hours per week are we willing to spend doing per-doc rights review on OHA/DOE/UH PDFs? If the answer is ~zero, the long tail is effectively excluded from the MVP and we should say so plainly.
- **Tokenizer-audit pass criteria** — Rusty to define what "good enough" looks like on the MVP corpus before we commit to phase 2 scope.

### Approved

This decision operationalizes the existing "Two-stage training plan" and "Prototype-vs-release split" ADRs. It defines the MVP boundary explicitly by rights tag and introduces a formal gate for advancing to phase 2. Both Rusty (on sufficiency) and Linus (on scope) have weighed in.
### 2026-04-29T06:18:25Z: User directive
**By:** yashasg (via Copilot)
**What:** For now, dataset/corpus artifacts should live on the user's local machine rather than GitHub or Hugging Face. User said: "ok for now non data-set data can live on my local machine"
**Why:** User request -- captured for team memory while the prototype storage approach is still local-first.

# Decision: rights-light MVP allow-list (issue #1)

**Author:** frank (Hawaiian Data Collector)
**Date:** 2026-04-29
**Status:** proposed (team-relevant; surfacing for visibility)
**Related:** issue #1, `data-sources/hawaiian-data-sources.json`, `.squad/decisions.md` "Raw archive storage = local disk only" ADR.

## Decision

For the prototype rights-light collection pass, the allow-list is exactly four
inventory entries, all tagged `open_license_candidate` (CC BY-SA 4.0):

1. `Hawaiian Wikipedia — XML dump (latest)`
2. `Hawaiian Wikipedia — dump status manifest`
3. `Hawaiian Wiktionary — dump`
4. `Hawaiian Wikisource — public-domain Hawaiian texts`

Everything else in the inventory is **deferred** by `scripts/001_collect_rightslight.py`
with a machine-readable reason — no silent inclusion. Specifically:

- **Baibala Hemolele (official site + archive.org scans):** deferred. The issue
  permits "pre-1925 Baibala scans where the specific source is reviewed"; no
  specific edition has been reviewed yet, so it stays out of the rights-light
  pull until a Hawaiian edition + reviewer is named (Linus call).
- **Tatoeba haw exports:** open-licensed but flagged as long-tail per issue #1
  ("small long-tail sources only after per-document review"). Defer until a
  per-source review records `license_per_sentence` posture.
- **FLORES-200:** `eval_only`. Handled by the separate eval-hash ingest path
  (`data/eval/eval_hashes.parquet`), not by this rights-light puller.
- **Everything `rights_review_required` / `unknown_review_required`:** nūpepa
  OCR routes (Ulukau, archive.org, Wayback CDX), OHA/DOE/UH, Awaiaulu, OPUS
  subsets, NLLB, yt-dlp captions — all deferred.

## Why this matters to the team

- **Linus:** the four allow-listed sources are the ones that can flow into
  Stage-1 manifest rows with `license_observed` non-null and a defensible
  redistribution posture. Anything else needs a per-document review before it
  enters `data/extracted/` or the Stage-1 manifest. Bible cap (≤10% Stage 1,
  ≤30% Stage 2) and `eval_hashes.parquet` precedence stay non-negotiable.
- **Rusty:** this set is small. Realistic clean Stage-1 yield (Wikipedia +
  Wikisource + Wiktionary) is in the low-millions of Hawaiian tokens — likely
  insufficient for DAPT on its own, which sharpens the case for the per-doc
  review pass on Awaiaulu / UH ScholarSpace / OHA later.
- **Coordinator / yashasg:** corpus payloads stay local. `.gitignore` now has
  a top-level `/data/` rule plus `*.warc(.gz)`. No corpus bytes will reach
  GitHub or Hugging Face from this script.

## What I will NOT do without team input

- Pull Baibala from any source until Linus signs off on a specific
  pre-1925 edition.
- Pull Tatoeba haw exports without a per-source review note.
- Promote any deferred source to selected by editing the allow-list silently —
  the allow-list is a code-review surface in `scripts/001_collect_rightslight.py`.

## Storage receipts

- Plan: `data/local/rightslight/fetch_plan.json` (gitignored).
- Provenance ledger: `data/local/rightslight/fetch.jsonl` (gitignored).
- Smoke-fetch artifact: `hawwiki-latest-sha1sums.txt`, ~3 KB, full provenance
  recorded, stored under `data/local/rightslight/hawwiki/{YYYYMMDD}/{sha256}.txt`.

---

## Directive: Use Python for project scripts

**Date:** 2026-04-29T06:47:43Z
**Source:** yashasg (via Copilot)
**Status:** Directive

### Decision

Use Python for project scripts.

### Rationale

User requested Python as the default implementation language for scripts (data collection, data processing, etc.).

### Implementation

- `scripts/001_collect_rightslight.py`: Python stdlib-only rights-light source collector.
- `scripts/002_fetch_rightslight_raw.py`: Python stdlib-only raw-data fetcher (Frank).
- `scripts/003_build_stage1_dataset.py`: Python stdlib-only Stage-1 processing scaffold (Linus).
- All three scripts validate via `python3 -m py_compile` and have working CLI help.

---

## Decision: Stable raw-fetch provenance ledger schema

**Date:** 2026-04-29
**Author:** Frank (Hawaiian Data Collector)
**Status:** Accepted

### Decision

Per-source raw-fetch provenance is recorded as JSONL at `data/raw/<source>/fetch.jsonl`, one object per fetched artifact, with a stable 14-field schema (implemented in `scripts/002_fetch_rightslight_raw.py` as the `ProvenanceRecord` dataclass):

```
source_id
source_url
fetch_timestamp_utc
http_status
content_type
content_length
raw_sha256
raw_storage_path
tos_or_license_url
license_observed
fetcher_user_agent
fetcher_tool_and_version
source_specific_ids (object, extension point)
notes
```

### Rules

1. **Additive-only.** New fields appended at end; no renames without coordinated migration (Linus + Frank).
2. **Path canonical:** `data/raw/<source>/fetch.jsonl` is the consumer contract.
3. **No corpus text** in records — metadata only.
4. **One line per artifact.** Multi-file dumps → multiple lines.
5. **`raw_storage_path` repo-relative** for portable resolution.
6. **`source_specific_ids` is extension point** for source-specific identifiers, keeping top-level stable.

### Why This Matters

- Linus reads this ledger for Stage-1 registration/LID/extraction/dedup decisions.
- Fetch-time fields (ToS snapshot URL, timestamp, raw sha256, observed license) are unrecoverable later — must be captured at ingest.
- Locking schema prevents downstream rewrites when new source adapters land.

### Owners / Consumers

- **Producer:** Frank — `scripts/002_fetch_rightslight_raw.py` and future per-source adapters.
- **Consumer:** Linus — downstream Stage-1 raw-to-training pipeline.
- **Reviewers:** Linus (data policy), Rusty (language/modeling fit).

---

## Decision: Stage-1 manifest JSONL-first, Parquet later

**Date:** 2026-04-29
**Author:** Linus (Data Engineer)
**Status:** Accepted

### Decision

For the Stage-1 prototype, emit `data/stage1/stage1_manifest.jsonl` (not `.parquet`). Parquet is a follow-up once `pyarrow` is justified.

### Why

- ADR locks schema, not on-disk format. Field names, types, contamination guards unchanged.
- Stdlib-only keeps `requirements.txt` honest. No premature `pyarrow`/`polars`/`duckdb` pick.
- JSONL is grep-able, diff-able, trivial to inspect for small wiki-only vertical slice.
- Promotion mechanical: 20-line `pyarrow` writer can consume this JSONL and produce `.parquet` once corpus > 50k docs or first analytical query lands.

### What This Is NOT

- Not a relaxation of ADR field completeness. Every field from `docs/data-pipeline.md §Stage 1 manifest schema` is present.
- Not permanent. When threshold (default ~50k docs or first DuckDB query) crosses, add `pyarrow` to `requirements.txt` and switch.
- Not a workaround for missing data. Missing `license_observed`/`sha256_raw`/raw path still causes doc skip with reason recorded.

### Implications for Downstream

- **Rusty:** tokenizer audit reads `data/stage1/stage1.jsonl.gz` (trainer text) — unaffected.
- **Basher:** contamination guard (`stage1_train ∩ eval_hashes = ∅`) needs JSONL-aware read until switch. One-line change.
- **Frank:** `fetch.jsonl` schema unaffected.

### Tracking Item

Promote to Parquet once corpus > 50k docs OR first DuckDB analytical query in CI. Default threshold: 50k unless team consensus differs.


---

## Decision: Number pipeline scripts to encode execution order

**Date:** 2026-04-29
**Author:** Linus (Data Engineer)
**Status:** Accepted

### Decision

Python data-pipeline scripts in `scripts/` carry a zero-padded numeric prefix
(`NNN_`) that encodes their canonical execution order. Initial mapping:

1. `scripts/001_collect_rightslight.py` — plan rights-light sources (Frank).
2. `scripts/002_fetch_rightslight_raw.py` — fetch raw artifacts + write per-source `fetch.jsonl` provenance (Frank).
3. `scripts/003_build_stage1_dataset.py` — Stage-1 manifest builder consuming `fetch.jsonl` (Linus).

### Rules

- New pipeline stages take the next free `NNN_` prefix. Do not renumber existing scripts; the prefix is stable once published.
- One-shot utilities, smoke tests, or non-pipeline tooling stay unprefixed.
- Docstrings, `generated_by`, `fetcher_tool_and_version`, and any cross-script comments must reference the prefixed filename.
- Historical `.squad` logs may continue to mention old (un-prefixed) names as history; current docs and code reference the new names.

### Rationale

- Makes pipeline order obvious from `ls scripts/` without reading docs.
- Removes ambiguity for new contributors and for downstream agents (Basher, Rusty).
- Keeps the contract additive: future stages slot into `004_…`, `005_…` without breaking existing references.

### Validation

- `python3 -m py_compile` clean on all three numbered scripts.
- `--help` works for all three.
- `002 --dry-run` and `003 --dry-run` exercise the renamed paths; no network writes, no corpus committed.

---

## Decision: Stage-1 fetch plan tiers sources against the 2.5M right-clearable token floor

**Date:** 2026-04-29
**Author:** Frank (Hawaiian Data Collector)
**Status:** Accepted

### Decision

`scripts/001_collect_rightslight.py` now emits a **tiered** fetch plan
(`schema_version: 0.2.0`) instead of a flat allow-list. Three tiers,
each machine-readable:

1. **`mvp_smoke`** — right-clearable sources covered by
   `scripts/002_fetch_rightslight_raw.py` today (fully or partially):
   hawwiki XML dump, hawwiki dumpstatus manifest, hawwiktionary dump,
   hawwikisource (metadata-only).
2. **`expansion_candidate`** — right-clearable sources with a
   defensible licensing path that are needed to defensibly reach the
   ~2.5M conservative Stage-1 train-token floor: Wikipedia
   interlanguage API, Tatoeba haw exports, Wikisource bulk page text.
   Each carries explicit blockers (adapter work in 002 or a 002b) so
   the gap is owned, not hidden.
3. **`deferred`** — rights-heavy or ambiguous sources (Baibala
   without a reviewed edition, nūpepa OCR, OHA/DOE/UH, Awaiaulu,
   OPUS/NLLB, FLORES eval-only, JW300, hard-escalate cultural
   categories). **Not used to backfill the token gap.**

Every plan entry now records `token_estimate_haw` (conservative /
base / upside), `fetcher_status`
(`supported` / `metadata_only` / `blocked_upstream` / `not_yet_implemented`),
`fetcher_script`, and `blockers[]`.

A new `coverage_summary` block in the plan rolls these up against the
target band (2.5M / 4.5M / 7M) and emits explicit shortfall numbers.

### Honest Token Accounting

- **Fetchable today (mvp_smoke, fetcher_status=supported only):**
  ~1.5M / 2.25M / 3.0M haw tokens — that's **just hawwiki**.
- **MVP smoke at face value (incl. partial/blocked entries):**
  ~2.05M / 3.35M / 4.65M.
- **With expansion candidates landed:** ~2.62M / 4.5M / 6.45M.
- **Shortfall vs. 2.5M floor, fetchable now:** ~1.0M tokens.
- **Shortfall after expansion:** 0 (just barely hits floor at conservative band).

The expansion tier is therefore **load-bearing** for the conservative floor, and its blockers (Wikisource bulk-text adapter, Wikipedia langlinks adapter, Tatoeba adapter) are the actual Stage-1 critical path — not nūpepa OCR or rights-heavy fillers.

### What This Changes

- **Linus:** Wikisource bulk-text path needs an extracted-text
  contract before any pull. The Wikisource pages are NFC-sensitive
  and should ride the same ʻokina canonicalization as the dump path.
  Coordination point.
- **Rusty:** the tokenizer audit's "go/no-go" gate for Stage-1 DAPT
  is now also a *coverage* gate — even with expansion landed, the
  conservative band only barely clears the 2.5M floor (≈2.62M).
  Tokenizer fragmentation could push effective tokens below the
  floor; pilot token counts (history.md plan) should run before any
  GPU spend.
- **Basher / training:** if expansion adapters slip, the honest
  answer is to **delay Stage-1 DAPT**, not to backfill with
  rights-ambiguous data. The plan's `coverage_summary.note` makes
  this explicit.

### Files Touched

- `scripts/001_collect_rightslight.py` — tiered allow-list, token
  estimates, fetcher readiness, coverage summary, new printout.
  Schema bumped to 0.2.0.
- `scripts/002_fetch_rightslight_raw.py` — docstring "Scope vs. the
  Stage-1 token target" paragraph added; behaviour unchanged.

---

## Decision: Stage-1 train-token volume gate + 002↔003 schema reconciliation

**Date:** 2026-04-29
**Author:** Linus (Data Engineer)
**Status:** Accepted

### Decision

1. `scripts/003_build_stage1_dataset.py` now reads provenance directly in the
   layout that `scripts/002_fetch_rightslight_raw.py` actually writes:
   `data/raw/<source>/fetch.jsonl` (source-level), with `raw_sha256`,
   `raw_storage_path`, `tos_or_license_url`, `fetch_timestamp_utc`.
   The legacy `data/raw/<source>/<fetch_date>/fetch.jsonl` layout is still
   accepted, and field-name aliases (`sha256_raw`, `path`/`raw_path`/`filename`,
   `tos_snapshot_id`) keep older fixtures working. `fetch_date` is derived
   from the YYYYMMDD parent of the raw artefact when not supplied.

2. Stage-1 right-clearable train-token targets are now first-class in the
   builder:
   - Conservative: **2,500,000** (go/no-go gate)
   - Base: **4,500,000**
   - Upside: **7,000,000**
   The summary always includes a `token_volume` block (current train tokens,
   target, gap, `below_conservative`). In `--strict` mode the script exits
   `2` when train tokens fall below the conservative target, regardless of
   any other gate. `--token-target {conservative|base|upside}` selects the
   reported tier and adds a strict failure if below that tier too.

3. New `--show-targets` flag prints targets and the current gap without
   requiring a corpus download — safe to run on a clean checkout.

### Why This Matters

- The current local data is metadata/smoke output, not the Stage-1 corpus.
  Without a token-volume gate, `003` happily emits a green-looking summary
  on a near-empty manifest, which masks the real status of Stage-1.
- The `002`/`003` schema mismatch (source-level vs date-level `fetch.jsonl`,
  `raw_sha256` vs `sha256_raw`, `raw_storage_path` vs `path`) was silently
  causing zero records to be discovered even when 002 had run.

### What This Does NOT Do

- Does not add any rights-heavy source (Baibala, JW300, NLLB, OCR'd nūpepa)
  to chase the target. The conservative 2.5M target is a **right-clearable**
  number; closing the gap is an upstream fetch-plan job, not a license
  relaxation.
- Does not change the local-only data policy. No corpus is committed.

### Validation

- `python3 -m py_compile scripts/003_build_stage1_dataset.py` — clean.
- `--help` and `--show-targets` print the targets without I/O on a corpus.
- `--dry-run` on an empty `data/raw/` reports `train_tokens_est=0`,
  `below_conservative=true`, and warns to stderr.
- Tiny local fixture written in 002's actual schema (source-level
  `fetch.jsonl`, `raw_sha256`/`raw_storage_path`/`tos_or_license_url`,
  raw bytes under `data/raw/<source>/<YYYYMMDD>/<sha>.xml`) is discovered
  and emits one wiki doc; `--strict` exits 2 because tokens are far below
  the 2.5M target.

### Follow-ups for the Team

- Frank: 002 fetch plan still doesn't pull enough raw to clear the 2.5M
  conservative target; the gap is now visible and machine-readable in 003's
  summary. Suggest the next pass widens `corpus_artifacts` for `hawwiki` /
  `hawwiktionary` and wires the `hawwikisource` page-render path within the
  existing rights-light allow-list.
- Rusty: token counts here are whitespace-token estimates. Once the real
  tokenizer audit lands, swap `token_count_est` for the audited count and
  re-run the gate.
- Basher: the strict-mode exit code on the volume gate is `2`, same as the
  existing quality-gate path; CI can keep a single non-zero check.

---

## Current Phase: Script renumbering + Wikisource integration (2026-04-29)

### 2026-04-29T00:29:07-07:00: User directive — phase-hundreds script numbering

**By:** yashasg (via Copilot)

Pipeline scripts are now numbered by **phase hundreds**, not flat sequence:
- `1xx` — **collect** (planning / inventory / allow-list emitters)
- `2xx` — **fetch** (raw-bytes adapters that write `data/raw/<source>/fetch.jsonl` provenance)
- `3xx` — **build** (Stage-1 dataset / manifest / downstream consumers of `fetch.jsonl`)

Within a phase, suffixes (`101`, `102`, …) are assigned in order scripts land. New adapters slot into the next free number in their phase rather than getting a `b`-suffix.

**Current files (post-rename):**
- `scripts/101_collect_rightslight.py` — rights-light source planner (Frank)
- `scripts/201_fetch_rightslight_raw.py` — Wikimedia dump-shaped fetcher: `hawwiki`, `hawwiktionary` (Frank)
- `scripts/202_fetch_hawwikisource_raw.py` — Hawaiian Wikisource page-text fetcher via MediaWiki API (Frank)
- `scripts/301_build_stage1_dataset.py` — Stage-1 dataset / manifest builder consuming `fetch.jsonl` (Linus)

**Why:** Earlier `001 / 002 / 002b / 003` flat numbering forced an awkward `b`-suffix when Wikisource needed its own fetcher, and left no obvious slot for the next collect-phase or build-phase script. Phase hundreds make the pipeline shape (collect → fetch → build) legible from `ls scripts/` alone and gives each phase ~99 cheap slots.

**Migration:** Files renamed in-tree. All path references in `scripts/*.py`, `docs/data-pipeline.md`, and `.squad/decisions/inbox/*.md` updated to new names. `.squad/decisions.md`, `.squad/agents/*/history.md`, and `.squad/orchestration-log/*.md` left as-is (historical records). Future entries use the new names.

**Validation:** All four scripts compile (`py_compile`) and execute dry-run modes correctly. Existing hawwiki output unchanged.

### 2026-04-30: Decision — Hawaiian Wikisource fetcher split (Frank)

**Scope:** Frank-owned scripts (`scripts/{101,201,202}_*.py`)

`scripts/201_fetch_rightslight_raw.py` now handles Wikimedia *dump-shaped* sources only (`hawwiki`, `hawwiktionary`). Hawaiian Wikisource lives in a new sibling adapter, `scripts/202_fetch_hawwikisource_raw.py`, which implements paginated MediaWiki API enumeration plus polite, rate-limited per-page wikitext fetches.

`scripts/101_collect_rightslight.py` references for Wikisource now point at `scripts/202_fetch_hawwikisource_raw.py`.

**Why:** The two fetch shapes have nothing in common:
- **Dump shape (201):** one ~MB-scale `*-pages-articles.xml.bz2` per source, verified against `sha1sums.txt`. Allow-list small and static.
- **API shape (202):** N HTTP calls, paginated `list=allpages` cursor, per-page revision JSON, namespace allow-list, rate-limit budget.

Mixing them forced 201 to carry an empty `corpus_artifacts: []` for Wikisource and a "metadata-only" branch that silently no-op'd `--execute` — the exact code smell that prompted the split.

**Behavioral contract for 202:**
- **Dry-run by default.** `--execute` required to pull per-page wikitext.
- **Defaults:** `--limit 50`, `--batch-size 50`, `--namespaces 0`, `--rate-limit-seconds 1.0`. Hard caps: `MAX_TOTAL_PAGES=5000`, `MAX_BATCH=500`.
- **Namespace allow-list:** {0, 104, 106}. Other namespaces rejected at parse time.
- **Storage:** `data/raw/hawwikisource/<YYYYMMDD>/<sha256>.json`, gitignored. Source-level ledger at `data/raw/hawwikisource/fetch.jsonl` using the same `ProvenanceRecord` schema as 201.
- **Per-page provenance:** `source_specific_ids` carries `artifact_kind`, `namespace`, `page_id`, `title`, `revision_id`, `revision_timestamp`, `content_present`, `api_endpoint`.
- **Raw bytes:** JSON envelope from API, stored as-is. Extraction (NFC, ʻokina canonicalization) remains downstream per Linus's extracted-text contract.

**Open coordination points:**
- **Linus:** Wikisource extracted-text contract (NFC, ʻokina, apostrophe disambiguation) still gates any *bulk* run of 202 `--execute`.
- **Rusty:** Wikisource pages are register-mixed. Worth tokenizer-fragmentation spot-check before committing to 0.5–1.5M token estimate.

### 2026-04-29: Decision — Wikisource fetcher → Stage-1 builder handoff contract (Linus)

**Owner:** Linus (Data Engineer)  
**Affects:** Frank (source fetcher), Rusty (tokenizer audit)

The Wikisource fetcher uses the **same `ProvenanceRecord` JSONL schema** as 201 and writes to **`data/raw/hawwikisource/fetch.jsonl`**. The Stage-1 builder dispatches on content shape, not source name:

| Content shape | `content_type` / extension | Builder extractor |
|---|---|---|
| Wikimedia bulk XML | `application/octet-stream` w/ `pages-articles*.xml[.bz2\|.gz]` | `wiki-xml-stream` |
| Per-page plain text | `text/plain` / `.txt` | `wikisource-pagetext` |
| Per-page wikitext | `text/x-wiki` / `.wiki` / `.wikitext` | `wikisource-pagetext` (de-wiki + NFC) |
| Per-page MediaWiki API JSON | `application/json` / `.json` (`action=parse` or `query&prop=revisions`) | `wikisource-pagetext` |
| Bundled NDJSON of pages | `application/x-ndjson` / `.jsonl[.gz]` / `.ndjson` | `wikisource-pagetext` |

NDJSON lines must contain at least `{"page_id": ..., "title": ..., "wikitext"|"text": ...}`. Single-page artefacts carry `page_id` / `title` / `revision_id` / `namespace` in `source_specific_ids` on the provenance row. `raw_storage_path` is relative to repo root, same as 201.

ʻokina canonicalization (U+02BB), NFC normalization, and deterministic split assignment are applied uniformly downstream of extraction — Wikisource is **not** a special-case past the extractor boundary.

**Downstream (committed):**
- `301_build_stage1_dataset.py`: Added `extract_wikisource_pages` + `_coerce_page_dict` helper handling all four shapes above. `process_record` dispatches `wiki-xml-stream` vs `wikisource-pagetext`; doc-emit path factored into `_emit_pages` so both extractors share one normalization/scoring/split path. Existing hawwiki XML extractor and token-volume gate remain untouched.
- `docs/data-pipeline.md`: documented the handoff under "Stage 1 immediate next steps" and extended the `extraction_method` enum.

**Frank still owns:**
- Implement actual fetcher (polite enumeration via `allpages`, per-page fetch, retry/backoff, ToS snapshot).
- Decide single-page-files vs NDJSON-bundle storage layout. Either is supported downstream; pick whichever keeps the manifest smaller without losing per-page provenance.
- Allow-list parity: `101_collect_rightslight.py` already lists `hawwikisource` as `expansion_candidate` — no policy change.

**Non-goals / guardrails:**
- This does **not** relax the right-clearable posture. Wikisource is CC BY-SA 4.0 wrapper over PD source texts, same per-page rights as `hawwiki`.
- The token-volume gate (Conservative 2.5M / Base 4.5M / Upside 7M) is unchanged. Wikisource is one of the load-bearing expansion candidates for closing the gap; it does not change the gate itself.
- No corpus text is committed; `data/raw/hawwikisource/` is gitignored the same way `data/raw/hawwiki/` is.

**Coordination asks:**
- **Frank:** confirm storage shape (per-page files vs NDJSON bundle) before pulling at scale; either works downstream.
- **Rusty:** the de-wiki pass in 301 is still prototype-grade. Wikisource pages contain headers, page numbers, `<pages index=...>` proofread-extension wrappers, and `{{author}}` / `{{header}}` templates that the current `_crude_dewiki` handles only superficially. Flag if the tokenizer audit shows wikitext residue inflating token counts.

---

**Decision finalization status:** All four inbox items merged and deduplicated. Phase-hundreds convention is the current active policy. Previous `001`, `002`, `002b`, `003` numbering is superseded. No unresolved old decisions remain as current policy.

### 2026-04-29T00:48:05-07:00: User directive — Source-specific collection scripts (Frank, Scribe consolidation)

**By:** yashasg (via Copilot); consolidated by Scribe  
**Status:** Active (supersedes prior broad-planner approach)  
**Owner:** Frank (Hawaiian Data Collector)

#### What
The broad `scripts/101_collect_rightslight.py` planner has been retired. Each data source now has its own **source-specific 100-phase collection scripts** following the pattern `10X_collect_<source>.py`:

- **101_collect_hawwiki.py** — Hawaiian Wikipedia dump-plan metadata (input for `201_fetch_rightslight_raw.py --source hawwiki`)
- **102_collect_hawwikisource.py** — Hawaiian Wikisource page enumeration + per-page fetch plan (`data/local/hawwikisource/page_plan.jsonl` consumed by `202_fetch_hawwikisource_raw.py --page-plan`)
- **103_collect_hawwiktionary.py** — Hawaiian Wiktionary dump-plan metadata (input for `201_fetch_rightslight_raw.py --source hawwiktionary`)

`202_fetch_hawwikisource_raw.py` now accepts `--page-plan PATH` (default `data/local/hawwikisource/page_plan.jsonl`); when missing or empty, it falls back to direct enumeration. `--no-page-plan` forces fallback explicitly.

#### Why
Each source has its own fetch shape (Wikimedia dump SHA1 manifest, MediaWiki API page enumeration, archive.org item IDs, etc.) and metadata. Forcing them through a single schema lost per-source detail. Per-source scripts make the collection contract for each source explicit and reviewable.

#### Scope & Non-goals
- **Not** a rights-policy change. The right-clearable allow-list is unchanged.
- **No** corpus text fetched by 100-phase scripts; only metadata and optional page-plan enumeration.
- Storage: `data/local/<source>/` (gitignored).

#### Validation
- `python3 -m py_compile` clean for all affected scripts
- `--help` works; dry-run successful; no corpus fetched
- `git status --short data/` clean

#### Coordination
- **Linus:** No schema change to `ProvenanceRecord`; `202` → `301` handoff unchanged
- **Rusty:** No tokenizer/normalization impact

#### Supersedes
Prior decision `001`, `002`, `002b`, `003` entries concerning phase-100 broad planner. Phase-hundreds convention (per-source, per-stage) is now the active standard for all future source/fetch/build work.

---

## Decision: New Hawaiian Source Candidates (FineWeb-2, eBible, Internet Archive PD)

**Author:** Frank (Hawaiian Data Collector)  
**Date:** 2026-04-29  
**Status:** Proposed (research only; no code written this pass)  
**Scope:** Private prototype / learning project. No release implied.

### Context

The current MVP allow-list (`hawwiki`, `hawwiktionary`, `hawwikisource`, plus the FLORES eval anchor) only clears ~2.05M raw whitespace tokens at face value, with `hawwiktionary` 404'd upstream. Nupepa.org's Greenstone CGI (`gsdl2.7/cgi-bin/nupepa`) returns Cloudflare from this environment, and the previously hoped-for `dlc_hawaiian_ver01` Chronicling America batch was a false lead (DC newspapers, not Hawaiian). Stage-1 is short of its 2.5M floor with no realistic path forward unless we add net-new sources.

This pass researched 10+ candidate sources via live probes (datasets-server, advancedsearch.php, OAI-PMH, eBible details pages). No Cloudflare/access-control bypasses; polite UA only.

### Decision

Promote three new source-specific adapter pairs to "expansion candidate" tier in `scripts/10X_collect_*` style. Each candidate has been live-verified for enumerability and at least one Hawaiian-text sample.

#### Top 3 — implement next (in this order)

1. **FineWeb-2 `haw_Latn`** — `104_collect_fineweb2_haw.py` + `204_fetch_fineweb2_haw_raw.py`
   - 95,507 rows confirmed via `datasets-server.huggingface.co` (partial=False). Each row preserves CC `url`, `dump`, `date`, `language_score` — provenance arrives free.
   - Wrapper licence: ODC-By. Underlying URLs (e.g. `staradvertiser.com` columns) carry independent third-party rights — **Linus must rule on whether prototype-only ingest of FineWeb-2 rows is acceptable, or whether we need a per-URL allow-list (e.g. drop `*.staradvertiser.com`, keep `*.wikipedia.org`, etc.)**.
   - Estimated yield ~40–80M raw whitespace tokens. Single biggest unblocker for the Stage-1 floor without touching nūpepa.
   - Tooling delta: needs `huggingface_hub` added to `requirements.txt` (or a stdlib path via the dataset-server rows API; slower but no new dep).

2. **eBible.org `haw1868` (Baibala Hemolele)** — `105_collect_ebible_haw.py` + `205_fetch_ebible_haw_raw.py`
   - Public-domain, redistributable. Single-zip artefacts at `https://eBible.org/Scriptures/haw1868_{usfm,usfx,readaloud,html}.zip`.
   - Replaces the Cloudflare-risky `baibala.org/cgi-bin/bible?…` per-verse plan. Pair with the already-pinned `eng-kjv2006_usfm.zip` and `eng-asv_usfm.zip` for Stage-2 verse alignment.
   - Trivial adapter (3–4 polite GETs); ~700k haw tokens; bound by data-pipeline.md §125 ≤10% Stage-1 / ≤30% Stage-2 caps.

3. **Internet Archive PD slice of `language:(haw) mediatype:(texts)`** — `106_collect_ia_haw_pd.py` + `206_fetch_ia_haw_pd_raw.py`
   - 216 items in `language:haw, mediatype:texts`; sample contains pre-1925 PD candidates (Hawaiʻi Judiciary Fifth Circuit court records 1890–1892, `kekumumuaanohoui00pool` 1875) and items with explicit `licenseurl=publicdomain/mark/1.0/`.
   - Filter at collect time to (`year < 1929`) OR (`licenseurl ∈ {publicdomain, CC0}`). Defer everything else behind explicit Linus per-item review (modern children's books, religious tracts, etc.).
   - Uses `internetarchive` client already in `requirements.txt`. Pull `*_djvu.txt` only; skip PDFs/scans for the prototype.

#### Tier 2 — research/probe before adapter

4. **cis-lmu/Glot500 `haw_Latn`** — 1,053,668 rows, but LID noise confirmed (Czech text in row 3). Useful only with our own paragraph LID gate. Coordinate with Linus on whether to plumb it into the existing extraction stage.
5. **bible-nlp/biblenlp-corpus** — verse-aligned Bible across 833 langs incl. `haw`. Useful Stage-2 cross-check against the eBible-derived alignment.
6. **UH Mānoa eVols / ScholarSpace OAI-PMH** — endpoint live at `https://evols.library.manoa.hawaii.edu/server/oai/request`. Per-item rights and cultural-sensitivity gating required; specifically Ka Leo Hawaiʻi (handle `10524/47856`) is oral-history transcripts of named native speakers — almost certainly hard-escalate, do **not** auto-ingest.
7. **Ulukau sub-collections off the broken Nupepa CGI** — Kauakūkalahale, Ka Hoʻoilina, Ka ʻAhahui Kīwila Hawaiʻi, Ka Papa Haʻawina Hawaiʻi, Ka Waihona Mele live on `gsdl2.80` / `gsdl2.85` / standalone subdomains. Needs per-collection Cloudflare probe before adapter work; do not assume the whole of Ulukau is dead just because `gsdl2.7/cgi-bin/nupepa` is.

#### Deferred this round (probed and blocked, or out-of-scope)

- Chronicling America title-search API: 308→403 Cloudflare from this environment. Public batches at `data/batches/` may still be reachable but enumeration is broken; revisit only with a different network path.
- HathiTrust catalog/Babel: Cloudflare-walled. Defer.
- Papakilo Database: 403 from this environment.
- Mozilla Common Voice: confirmed **does not list `haw` as a supported locale**. Drop.
- CC-100 (statmt.org): manifest enumerated; **`haw` not present**. FineWeb-2 supersedes for prototype.

### What this does NOT change

- Right-clearable allow-list discipline is unchanged. Nupepa OCR, OHA/DOE/UH bilingual, JW300, hard-escalate cultural categories all stay deferred.
- FLORES stays eval-only; no data is ever published.
- 100/200/300 source-specific script convention from the 2026-04-29 consolidation stands. New sources land as new `10X_collect_<source>.py` + `20X_fetch_<source>_raw.py` pairs, not as additions to a generic collector.
- Storage stays under `data/` (gitignored). Provenance schema (`ProvenanceRecord` 14 fields, additive-only) unchanged.

### Coordination requests

- **Linus:** rights review on FineWeb-2 wrapper-vs-row posture for prototype use; per-URL allow-list policy decision.
- **Linus:** confirm whether `huggingface_hub` may be added to `requirements.txt`, or whether the stdlib datasets-server rows API path is preferred.
- **Rusty:** sanity-check that FineWeb-2 + Glot500 noise wouldn't degrade tokenizer-fragmentation properties; LID gate threshold on the Glot500 slice.

### Validation done this pass

- Live probes of: HF datasets-server (FineWeb-2 haw_Latn, Glot500 haw_Latn), eBible.org details + Scriptures index, Internet Archive advancedsearch.php, UH eVols OAI-PMH, Awaiaulu resource list, Hawaiian Mission Houses Omeka tree, statmt CC-100 manifest, Mozilla Common Voice locale API, Hawaiʻi Star-Advertiser sample row from FineWeb-2 (Kauakūkalahale column).
- Confirmed-blocked: Chronicling America (Cloudflare 308→403), HathiTrust (Cloudflare interstitial), Papakilo (403), digitalcollections.hawaii.gov (TCP fail this round).
- No corpus bytes fetched; no scripts written; no `requirements.txt` edits; no commits.

---

## Decision: FineWeb-2 `haw_Latn` Access Verified Live

**Author:** Frank (Hawaiian Data Collector)  
**Date:** 2026-04-29  
**Status:** Proposed — ready for Linus/Rusty review before scripts land.

### Verdict

**Works.** FineWeb-2 `haw_Latn` is reachable, ungated, schema-stable, and scriptable without HF authentication. Proceed to write `105_collect_fineweb2_haw.py` (planner) and `205_fetch_fineweb2_haw_raw.py` (fetcher) — pending Linus's rights ruling and dependency call.

### Evidence (live, 2026-04-29)

- **Dataset:** `HuggingFaceFW/fineweb-2`, config `haw_Latn`. `gated:false`, `private:false`, license tag `odc-by` (wrapper).
- **Rows:** train **95,507** (≈127 MB parquet, ≈415 MB in-memory), test **887**. `partial:false` — earlier 95,507 figure holds exactly.
- **Fields (12):** `text, id, dump, url, date, file_path, language, language_score, language_script, minhash_cluster_size, wordlist_ratio, top_langs`. Provenance ships in-row.
- **Access paths (both no-auth):**
  1. `datasets-server.huggingface.co/rows` — stdlib paginated rows API. Verified rows returned with real Hawaiian-script text.
  2. Parquet auto-conversion: 2 files at `…/resolve/refs%2Fconvert%2Fparquet/haw_Latn/{train,test}/0000.parquet`. Stable, deterministic.
- **Tiny sample (lengths only):** 2 train rows, text lens 3215 / 3292, `language_score>0.995`, both `staradvertiser.com` Kauakūkalahale columns with English header/footer boilerplate around Hawaiian body.

### Recommendation

1. **Greenlight scripts** named `105_collect_fineweb2_haw.py` + `205_fetch_fineweb2_haw_raw.py` (renumbered from earlier 104/204 to match current ordering convention if applicable; otherwise keep 104/204 — coordinator's call). Planner emits manifest (2 parquet URLs, row counts, ODC-By snapshot, fetch date, our UA). Fetcher streams parquet to `data/raw/fineweb2/haw_Latn/{train,test}/0000.parquet` and records sha256 + ETag + Last-Modified + license tag per file.
2. **Dependency:** stdlib + `pyarrow` is the minimal path; `huggingface_hub` is ergonomic but optional. **Don't edit `requirements.txt` yet** — Linus owns that call.
3. **Cleaning is downstream:** the corpus contains English boilerplate inside high-LID-score Hawaiian docs. Boilerplate-strip + paragraph-level re-LID belong to Linus/Rusty's pipeline, not to the fetcher.

### Open questions for the team

- **Linus:** (a) ODC-By wrapper vs. per-URL third-party rights — accept FineWeb-2 rows wholesale at prototype scope, or impose a per-URL allow/deny list (e.g., drop `*.staradvertiser.com`, keep `*.wikipedia.org`)? (b) Add `pyarrow` (and optionally `huggingface_hub`) to `requirements.txt`, or stay stdlib-only via the rows API at the cost of slower bulk pulls?
- **Rusty:** Tokenizer-fragmentation sanity-check on a FineWeb-2 sample once fetched; LID/quality threshold for Stage-1 inclusion given the boilerplate-mixed reality.

### Boundaries

Frank verified access + provenance + scriptability only. Not making the rights call, not editing scripts or requirements, not bulk-downloading the corpus. No raw text exposed in this note (lengths and known-public URLs only).

---

## ADR: Hawaiian Language/Script Code Normalization

**Author:** Rusty (NLP Researcher)  
**Date:** 2026-04-29  
**Status:** Advisory — Operational Guidance  
**Audience:** Frank (data collection), Linus (rights/audit), Basher (training pipeline), Scribe (cross-source provenance)

### Verdict

Hawaiian language codes are inconsistent across dataset providers. The canonical form is `haw_Latn` (ISO 639-3 + ISO 15924 script), but collectors will encounter `haw-Latn` (BCP-47 hyphenated), bare `haw`, and critically, `hawn_Latn` (FLORES+ 4-letter convention). A real Hawaiian alias exists (`hawn_Latn`) that naive prefix-matching will miss; false positives include Hawaiian Pidgin (`hwc`), Hausa (`hau`), and filename acronyms. Normalization rules prevent silent errors.

### Canonical codes

| Standard | Code | Notes |
|---|---|---|
| ISO 639-3 | `haw` | Canonical 3-letter code; no ISO 639-1 2-letter exists. |
| BCP-47 | `haw` or `haw-Latn` | Bare or with script tag (hyphen separator). |
| ISO 15924 script | `Latn` | Hawaiian is **only** written in Latin script in modern corpora. |
| FLORES-Plus internal | `hawn_Latn` | 4-letter extension for languages beyond original FLORES-200. **Real alias, not a bug.** |

### Plausible config forms in modern corpora

1. **`haw_Latn`** (NLLB / FineWeb-2 / Glot500 style) — **canonical for our manifests**.
2. **`haw-Latn`** (BCP-47 with hyphen, HF metadata fields) — semantically equivalent.
3. **`haw`** (bare ISO 639-3, Tatoeba / OPUS / Wikipedia) — unambiguous for Hawaiian (only Latin script active); accept.
4. **`hawn_Latn`** (FLORES-Plus extended-set) — **treat as known alias of Hawaiian, not different language.**
5. **`Hawaiian`** (free-text name) — normalize to `haw` on ingest.
6. **`haw_HI`** (hypothetical region tag) — rarely seen; record region only if source distinguishes.

### False-positive risks

**Never use substring/prefix matching.** These will collide with Hawaiian:

- **`hwc` (Hawaiian Pidgin / Hawaiʻi Creole English)** — a distinct language, not Hawaiian. Some corpora label it "Hawaiian English" or just "Hawaiian" in free-text metadata. **Always check the code, not the name.**
- **`hau_Latn` (Hausa)** — three-letter prefix collision with `haw`. NLLB-200 includes Hausa.
- **`Hano` / `hnn` (Hanunoo, a Philippine language)** — different language.
- **`lat_Latn` / `Latin`** — mis-recording *script* as *language* in poorly-curated metadata.
- **Filename acronyms** — "Hawaii state data" (all English); airline codes; OCR artifacts. Signal is the **declared language metadata field**, not filename substring.
- **English-heavy rows tagged `haw_Latn`** — Already observed in FineWeb-2: rows with `language_score > 0.995` but mostly English boilerplate + Hawaiian core. Requires **paragraph-level re-LID + char-ratio gates** (ʻokina/kahakō density vs. ASCII-only density) downstream.
- **Mojibake / NFD-decomposed rows** — ʻokina mangled to `'` / U+2018 / U+2019; kahakō decomposed to NFD combining macrons. Poison tokenization; flag in QA.

### Normalization rules for collectors

1. **Manifest `language` column:** normalize to `haw` (bare ISO 639-3) for Hawaiian-only rows. Never store `haw_Latn`, `hawn_Latn`, `haw-Latn`, or `Hawaiian` in this column. (Script goes in separate columns.)
2. **New manifest columns (advisory):**
   - `script_iso15924` — value `Latn` for all Hawaiian rows. Asserts script invariant.
   - `source_language_config` — verbatim provider config string (e.g., `haw_Latn`, `hawn_Latn`, `haw`, `Hawaiian`). **Audit trail; never overwrite.**
   - `source_language_resolved` — our normalized interpretation (`haw`, `hwc`, `eng`, etc.). Decision log for re-auditing later.
3. **Resolution logic:**
   - Match against explicit allow-list: `{haw_Latn, haw-Latn, haw, hawn_Latn, Hawaiian, hawaiian, HAW} → haw`.
   - **Never** use prefix / substring matching on provider config. Exact match against allow-list, case-normalized.
   - On miss, log unrecognized config and quarantine row. Do not silently drop or default.
4. **ʻokina + kahakō invariants:** every `language=haw` row must pass NFC normalization; ʻokina is U+02BB (not U+2018/U+0027/U+2019); kahakō present where source had it; byte-fallback rate recorded per slice.
5. **Provenance in run reports:** record `(source, source_language_config, source_language_resolved, row_count, token_count)` per source. Auditable post-hoc filtering.

### Recommendations

- **Frank (collector):** hard-code config strings (`haw_Latn` for FineWeb-2, `hawn_Latn` for FLORES-Plus, bare `haw` for Tatoeba/OPUS). Record verbatim in `source_language_config`; resolve to `language=haw` in manifest. Never extend by prefix match.
- **Linus (rights/audit):** language-config audit is independent of rights audit but feeds same manifest. `hawn_Latn` being FLORES+ 4-letter form is a normalization issue, not a rights issue.
- **Basher (training):** when slicing eval by source, slice on `source_language_resolved` for inclusion (`== 'haw'`) and on `source_language_config` for diagnostics (per-config breakdown of byte-fallback, ʻokina survival, PPL).
- **Scribe:** if a future ADR codifies manifest schema additions, reference this advisory.

### No new ADR

This advisory clarifies and extends `data-pipeline.md`'s manifest schema. Scribe folds into a schema ADR if team wants the new columns durable.

---

## Inventory: Hawaiian Dataset Variants Beyond FineWeb-2 `haw_Latn`

**Author:** Frank (Hawaiian Data Collector)  
**Date:** 2026-04-29  
**Status:** Proposed — team awareness  
**Method:** HF Hub metadata-only probe (`/api/datasets`). No bulk downloads, no raw text exposed.

### Verdict

Yes. Multiple real Hawaiian (`haw` / `haw_Latn`) configs exist on HF beyond FineWeb-2 `haw_Latn`. Key new findings: **`FineWeb-2 haw_Latn_removed`** (filter-rejected pool, recall-over-precision contingency), **`GlotCC-V1 haw-Latn`** (independent CC filter for cross-source dedup), **`openbmb/DCAD-2000 haw_Latn`** (free second-opinion filter), **`HuggingFaceFW/finepdfs haw_Latn`** (PDF modality, likely overlaps Ulukau).

**Critical:** **FLORES / FLORES+ do not include Hawaiian.** `docs/data-pipeline.md` §300 currently hedges this ("If `hawn_Latn` is included in FLORES-200…") — false. Eval anchor for Stage 2 must come from elsewhere.

### Real Hawaiian configs (text)

| Dataset | Config | Modality | Use to us |
|---|---|---|---|
| HuggingFaceFW/fineweb-2 | `haw_Latn` (train + test) | Web text (CC) | Baseline candidate Stage 1. |
| HuggingFaceFW/fineweb-2 | **`haw_Latn_removed`** | Web text rejected by FineWeb-2 filters | **New.** Recall pool — only if Stage 1 yield too low. Tag `quality=fineweb2_removed` for later filtering. |
| cis-lmu/GlotCC-V1 | `haw-Latn` (note: hyphen) | CommonCrawl filtered via GlotCC pipeline | **New.** Independent CC filter vs. FineWeb-2. Best second source for MinHash dedup + filter-disagreement analysis. |
| openbmb/DCAD-2000 | `haw_Latn` (`keep/remove/stas` jsonls) | Re-filtered FineWeb-2 + MaLA shards | **New.** Free second-opinion filter; metadata-only, useful for filter calibration without re-running classifiers. |
| HuggingFaceFW/finepdfs | `haw_Latn` (train + test) | PDF-derived text | Different modality from web crawl. Run metadata diff (URL/SHA) before pulling to avoid re-ingesting Ulukau under different label. |
| HuggingFaceFW/finetranslations | `haw_Latn` | Synthetic / model-translated | Synthetic, last-resort only; capped per pipeline. |
| cis-lmu/Glot500 | `haw_Latn` | Web text (older release) | Smaller, older. Sanity comparator, not primary. |
| wikimedia/wikipedia | `20231101.haw` | Wikipedia parquet (canonical) | Rights-clean; already in inventory. |
| bible-nlp/biblenlp-corpus | `haw` | Bible verses | Stage 2 candidate, subject to ≤30% Bible cap per pipeline. |
| ayymen/Weblate-Translations | `en-haw.tsv`, `en_GB-haw.tsv` | UI string parallel pairs (software-l10n) | Stage 2 candidate, register=software-l10n, cap recommended. |
| cis-lmu/Taxi1500-RawData | `haw_Latn` | Bible-derived topic classification eval | Eval-only; possible Stage 2 dev/test anchor (Bible-aligned). |
| mrlbenchmarks/global-piqa-parallel | `parallel_haw_latn.tsv` | Commonsense QA, parallel `en/haw` | **Candidate Stage 2 dev/test anchor** (replaces FLORES since FLORES has no Hawaiian). |

### Confirmed absent (no Hawaiian config)

- `facebook/flores` — **FLORES-200 does not include Hawaiian.** Critical correction to `data-pipeline.md`.
- `openlanguagedata/flores_plus` — **FLORES-Plus does not include Hawaiian.** (Rusty found `hawn_Latn` 4-letter convention in FLORES-Plus spec, but not actually used for Hawaiian in practice.)
- OSCAR (all versions), CulturaX, cc100, HPLT, NLLB, OPUS-100, QED, Ubuntu, MADLAD-400, XNLI, XLSum, and others (probed via sibling listing or language tag).

### Recommendations

1. **Keep FineWeb-2 `haw_Latn` as primary Stage 1 source.** Cleanest, most actively maintained.
2. **Add GlotCC-V1 `haw-Latn` as second Stage 1 source.** Independent filter; cheap to evaluate; enables cross-source MinHash dedup.
3. **Treat FineWeb-2 `haw_Latn_removed` as contingency recall pool.** Only ingest if Stage-1 token-yield gate at risk; tag `quality=fineweb2_removed`.
4. **Inventory finepdfs `haw_Latn` separately.** Run metadata diff (URL/SHA) vs. Ulukau / archive.org before pulling.
5. **Use DCAD-2000 `keep/remove/stas` jsonls as free second-opinion filter.** Metadata-only; useful for filter calibration.
6. **Update Stage 2 plan: FLORES has no Hawaiian.** Candidate replacement eval anchors (priority order):
   - `mrlbenchmarks/global-piqa-parallel` (commonsense, parallel) — preferred
   - `cis-lmu/Taxi1500-RawData` (Bible-derived classification) — overlaps Bible cap; dev-only if Bible verses excluded from training above 30%
   - Tatoeba `haw`↔`eng` (already inventoried) — split held-out portion as dev/test
   - BibleNLP `haw` (hand-curated dev/test) — only with strict edition pinning, held-out from training.
7. **Skip for now:** `saillab/alpaca-hawaiian*` (LLM-translated, fails synthetic bar), `finetranslations` (synthetic), `allenai/c4` mC4 (superseded), `graelo/wikipedia` (older snapshot), MADLAD-400 (no config), Omnilingual-ASR / MMS-ULAB (speech, out of scope).

### Open questions for the team

- **Linus:** Should `haw_Latn_removed` (filter-rejected pool) be allowed at all under data-policy, even tagged? Default: "no, unless yield gate fails."
- **Rusty:** For Stage 2 eval anchoring, prefer global-piqa-parallel `haw` or held-out Tatoeba slice as primary dev set?
- **Linus / Coordinator:** Recommend tightening `data-pipeline.md` §300 from "If `hawn_Latn` is included in FLORES-200…" to "FLORES-200 does not include Hawaiian; eval anchor TBD per alternatives below."

### Boundaries

Frank verified HF Hub metadata, sibling listings, language tags. No parquet bytes downloaded; no raw text inspected. Metadata-only probe.

