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
