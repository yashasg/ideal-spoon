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
| URL inventory (input contract, in git) | JSON | `docs/hawaiian-data-sources.json` |
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
