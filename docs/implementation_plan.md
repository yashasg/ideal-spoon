# Implementation Plan

> **Status:** Prototype design for a learning project. **No public release** of weights, adapters, tokenizer, datasets, generations, eval scores, API, or demo is planned. This doc consolidates the team's current working plan into an executable sequence; it is **not** a release roadmap, **not** a benchmark claim, and **not** a commitment to ship a model, hosted service, or corpus. See the prototype-vs-release ADR in [`.squad/decisions.md`](../.squad/decisions.md).
>
> **Owner:** Danny (Lead), with inputs from Rusty (NLP), Basher (Training), Livingston (Cost), Linus (Data).
>
> **Companion docs:**
> - [`README.md`](../README.md) — project framing, goals, non-goals, license intent.
> - [`data-pipeline.md`](./data-pipeline.md) — sources, manifests, normalization, contamination guards.
> - [`training-pipeline.md`](./training-pipeline.md) — Stage 0 → Stage 1 CPT → fp16 merge → Stage 2 SFT, with stage gates.
> - [`eval_pipeline.md`](./eval_pipeline.md) — cadence, metrics, slicing, attribution matrix, run-report schema.
> - [`.squad/decisions.md`](../.squad/decisions.md) — accepted ADRs (two-stage plan, prototype-vs-release split, model recommendation, free-GPU chaining, checkpoint contract).

---

## 1. Plan overview

The plan operationalizes decisions already accepted in `.squad/decisions.md`. It does not introduce new policy. Three things must hold across the whole sequence:

1. **Prototype scope.** No weights, adapters, tokenizer artifacts, datasets, generations, eval scores, API, or demo are planned for public release. Cultural review, license whitelisting, and human-eval thresholds described in the release branch of `training-pipeline.md` are out of scope here and remain hypothetical.
2. **Adapt, don't pretrain.** From-scratch pretraining is rejected at this budget and corpus scale. The bottleneck is data quality, tokenizer fit, and eval discipline — not GPU spend.
3. **Gates are checkpoints, not vibes.** Every phase boundary has an artifact identifier (manifest hash, eval-suite SHA, run report) frozen and recorded before the next phase starts. Generated data and model artifacts stay under ignored/private storage; a run without a complete report does not promote.

### Phase boundaries

| Phase | Boundary artifact | Gate before next phase |
|---|---|---|
| **Stage 0 readiness** | Tokenizer audit report, data manifests, contamination guard CI green, eval harness SHA, 0.5B end-to-end smoke run report, short 7B resume test report | All Stage 0 prereqs in §4 pass |
| **Stage 1 CPT/DAPT** | Adapter checkpoint + run report on Provider 2 | Stage 1 gate in `training-pipeline.md` §2.4 |
| **fp16 merge** | Merged base + tokenizer SHA equality assertion | Loadable, sanity-eval matches pre-merge within tolerance |
| **Stage 2 SFT** | Fresh LoRA checkpoint + run report | Stage 2 gate in `training-pipeline.md` §4.4 |
| **Final eval** | Reproducibility eval pass + headline eval run report on Provider 3 | N/A — terminal phase for this prototype |

Phases run in order. Within Stage 0, prereqs may run in parallel.

---

## 2. Three-provider execution strategy

The compute plan is sequenced across three providers. The split exists because (a) free / preliminary work should not consume the limited paid window, (b) Stage 1 + merge + Stage 2 must stay pinned to one provider/GPU class to keep the loss curve interpretable, and (c) headline numbers must be reproduced on a different environment before they are trusted. This reaffirms the existing chaining-feasibility and checkpoint-contract ADRs.

### 2.1 Provider 1 — Free / preliminary validation (Stage 0)

**Purpose:** finish all Stage 0 readiness work without spending the paid window. Output is a frozen "training-ready bundle" that the paid window consumes.

**Candidates:** Kaggle (30 GPU-h/wk on P100 / 2×T4) is the strongest free tier; Lightning AI free studio and Colab free are usable for shorter dev tasks; local RTX 2080 (8 GB) handles tokenizer audits, normalization checks, manifest builds, and 0.5B QLoRA work. T4/P100 tiers are acceptable for plumbing checks but **not** for any number that will gate Stage 1 (no bf16, no FA2 on Turing/Pascal).

**Stage 0 readiness gates that must complete before the Provider 2 training block opens:**

- Tokenizer audit on representative slices (nūpepa, *Baibala Hemolele*, contemporary Hawaiian) per `training-pipeline.md` §1.1. The script path exists, but the real gated Llama-3.1-8B go/no-go remains blocked on Hugging Face access/dependencies plus an actual run; decision on embedding/lm_head unfreeze, vocab extension, or base swap is recorded only after that report exists.
- Data manifests built and CI-green per `data-pipeline.md`: provenance fields populated, prototype lineage fields enforced, NFC normalization invariant verified, ʻokina U+02BB and kahakō survival baselines computed on references. Current local Stage-1 outputs live under ignored `data/stage1/` and the FineWeb cleaner reports 95,507 rows seen / 6,528 rejected / train tokens `59,534,611 → 44,067,289`.
- Contamination guard inputs wired and asserted in available artifact checks; canonical `eval_hashes.jsonl` built as JSONL; FineWeb-2 dev/holdout split frozen at 621 / 266 rows; cluster-aware split path scoped; n-gram-overlap recheck path exercised.
- Eval harness built; eval-suite SHA pinned; pre-FT baseline computed on the chosen 7B/8B base for Hawaiian held-out PPL and English PPL anchors. Without this baseline no later "better" claim is admissible.
- Pipeline smoke on Qwen2.5-0.5B, both stages end-to-end on tiny slices, with all metrics emitting and contamination guard firing on a planted positive. This is plumbing validation; the numbers are not interpreted.
- Short 7B resume test (≤1 h) demonstrating QLoRA NF4 load + FA2 throughput + checkpoint-to-HF-private-repo + resume-from-HF on the candidate base. Confirms the checkpoint contract works before the 60 h window opens.

**Output bundle (frozen, hashed, recorded in the run-report row):** base SHA, tokenizer SHA, corpus manifest SHA (Stage 1 + Stage 2), eval-hashes SHA, eval-suite SHA, normalization spec, embedding/lm_head policy, env.lock.

**Hard rule:** none of the above may bleed into the Provider 2 paid training window, except an explicitly budgeted ≤1 h Provider-2-class resume probe.

### 2.2 Provider 2 — Paid 60-hour stable training block (Stage 1 + merge + Stage 2)

**Purpose:** run Stage 1 CPT/DAPT, the fp16 merge, and Stage 2 SFT on **one provider, one GPU class**, with one retry budgeted. Provider switching mid-stage is forbidden because bnb 4-bit kernels and fp16/bf16 dtype choices are not deterministic across CUDA archs and GPU classes; switching mid-stage poisons the loss curve.

**GPU class requirement:** L4 / A10 / A100 / 4090-class (SM ≥ 80, bf16 + FA2). T4 / P100 are excluded for Stage 1 numbers that gate progression.

**Candidate providers (decision pending):** RunPod community A100 hourly, Lambda on-demand A100, Lightning AI Pro studio with A100, or burning Azure credit on a single A100 spot. Final pick is an open decision; see §10.

**Indicative 60 h budget allocation** (per Basher's advisory; not a hard contract):

| Allocation | % of 60 h | Notes |
|---|---|---|
| Setup, env pin, sanity resume from Provider 1 bundle | ~3 % | First cheap-eval point on a known checkpoint must match Provider 1 within ±0.02 PPL. If it does not, stop — env is not really restored. |
| Smoke + warmup on real base | ~2 % | One short throughput + loss-shape check. |
| Stage 1 CPT/DAPT | ~40 % | QLoRA r=64/α=128, all linear layers, lr 2e-4, seq 2048, ~1 epoch on Stage 1 corpus, **5–10 % English rehearsal** to fight forgetting. Cheap eval (Hawaiian PPL, English PPL delta, ʻokina/kahakō survival, leakage recheck) at every checkpoint save (~30–60 min cadence). |
| Stage 1 gate eval | ~3 % | Full Stage 1 eval suite per `training-pipeline.md` §2.4 + `eval_pipeline.md` §3. Hard fails: ʻokina collapse to U+2018/U+0027, English PPL > +20 % vs base. |
| fp16 merge | ~2 % | Merge Stage 1 LoRA into fp16 base. Tokenizer SHA equality re-asserted. Sanity eval on merged model must match pre-merge within tolerance. |
| Stage 2 SFT | ~20 % | Fresh LoRA r=32/α=64 on the merged fp16 model, lr 1e-4, seq 1024, 2–3 epochs, **target-only loss masking**, **50/50 direction balance**, **10–20 % Stage-1-style monolingual retention slice**. Cheap eval (chrF both directions, retention probe, leakage) at every checkpoint save. |
| Stage 2 gate eval | ~3 % | Full Stage 2 eval suite per `training-pipeline.md` §4.4. |
| Retry / contingency | ~25 % | One retry budgeted. Two retries are out of scope inside the 60 h. |
| Buffer | ~2 % | |

**Adapter strategy:** **merge Stage 1 into fp16 base, train fresh Stage 2 LoRA on the merged model.** Stacked adapters are reserved for short A/B ablations only; they are not the release-shape path. One quantization boundary per stage; Stage 2 reloads in 4-bit from the merged fp16.

**Checkpoint contract (every save):** adapter, optimizer state, scheduler state, RNG, dataloader position, `trainer_state.json`, env.lock, base-model SHA pin, tokenizer SHA pin. Eval log stored alongside. Storage = HF Hub private repo (or equivalent S3-compatible object store) — this is the artifact bus across providers.

**Hard rule:** if any Stage 1 → merge → Stage 2 boundary falls back to Provider 1 or forward to Provider 3 mid-stage, the run is invalid.

### 2.3 Provider 3 — Final eval-only (reproducibility-gated)

**Purpose:** run the headline eval pass on a separate environment to falsify harness drift and silent dtype/quantization differences. **No training, no merging, no tweaks.**

**Reproducibility gate (mandatory before any Provider 3 number is reported as headline):** Provider 3 must first re-run Provider 2's last gate eval on the **same checkpoint**. The first eval point must match Provider 2 within ±0.02 PPL on Hawaiian held-out and within harness tolerance on chrF by direction. If it does not, headline eval is invalid until the env drift is resolved.

**Eval scope after the reproducibility gate passes:** full diagnostic slicing pass per `eval_pipeline.md` §5 (source/register, direction, length, diacritic density, OCR confidence, tokenizer behavior, split, provider), generalization probe, hallucination probe, COMET if applicable, attribution-matrix triage. Human spot eval is encouraged for the prototype, required only under release scope (which we are not in).

**Constraint:** dtype and quantization at inference must match Provider 2. Decoding params and sampler defaults are pinned in the run report. Eval-suite SHA and `eval_hashes.jsonl` SHA are identical to Provider 1 and Provider 2.

---

## 3. Stage 0 prerequisites (consolidated)

A single checklist that must be green before Provider 2 spend opens. Each item maps to an existing doc section.

- **Tokenizer audit** (Rusty) — `training-pipeline.md` §1.1, `eval_pipeline.md` §3.1. Required output: tokens/word and byte-fallback/proxy rate on representative Hawaiian slices; model/tokenizer SHA fields; go/no-go recommendation for Llama-3.1-8B; decision on embedding/lm_head unfreeze and any vocab extension. Current status: no standalone audit script in the repo; a tokenizer-audit test is planned. Final base-model selection remains blocked on gated HF access/dependencies plus a real run.
- **Data manifests** (Linus, with Rusty on register balance) — `data-pipeline.md` Stage 1 and Stage 2 manifest schemas. Required output: per-document and per-pair provenance, license posture recorded at load, NFC normalization invariant green, register-balance check on Bible-heavy mixes flagged, `prototype_only` / `release_eligible` lineage fields enforced (prototype-only rows are expected here; release scope is hypothetical).
- **Contamination guard** (Rusty / Basher) — `data-pipeline.md` Stage 1 §contamination + Stage 2 §contamination + `eval_hashes.jsonl`. Required output: cluster-aware splits, W1 manual rows hashed through `scripts/315_hash_manual_w1_eval.py` when accepted (or explicit local draft preflight), n-gram overlap artifact/CI assertion before any training read, planted-positive smoke firing the available guard path. The runtime loader guard remains human-owned under #4.
- **Eval harness** (Rusty / Basher / Livingston) — `eval_pipeline.md` §2–§4. Required output: harness loads, W1 categories/slices (`okina_survival`, `kahako_retention`, `unicode_nfc`, `tokenizer_survival`, `generation_sanity`, `diacritic_density_bin`) are schema-consumable, all metrics emit, eval-suite SHA pinned, pre-FT baseline on the candidate base committed. Current W1 rows are draft/`eval_consumable=false` until Hawaiian-literate review.
- **0.5B / 1B smoke** (Basher / Rusty) — Qwen2.5-0.5B end-to-end on tiny slices, both stages. Optionally Qwen2.5-1B if local memory permits. Includes the QLoRA-vs-fp16-LoRA falsification arm per `eval_pipeline.md` §7. This is plumbing + prior-falsification, not quality.
- **Short 7B resume test** (Basher) — ≤1 h on the chosen base, on the chosen Provider 2 GPU class, demonstrating QLoRA NF4 load, FA2, checkpoint push to HF private repo, and resume-from-HF on a fresh container. Confirms the checkpoint contract before the 60 h window opens.

A Stage 0 failure is a Stage 0 failure. It does not promote to Stage 1 with caveats.

**Current prototype status (2026-04-29):** Stage 1/2 scaffold issues #2, #3, #5, #6, and #9–#14 are prototype-ready. Remaining blockers before serious 7B/8B spend are #8 (real gated Llama tokenizer audit) and the human-owned #4 runtime loader guard; #7 still needs Hawaiian-literate W1 review before W1 rows are treated as accepted eval results. #1 remains backlog/stretch.

---

## 4. Model-choice rationale (current working plan)

This section captures the model-selection conversation already accepted in `.squad/decisions.md` (base-model ADR) and reaffirmed in Rusty's history. Detailed NLP-quality claims live with Rusty; the plan here is the team-facing summary.

| Model                        | Role in plan                                | Why                                                                                                                                                                                                                                   |
| ---------------------------- | ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Llama-3.1-8B**             | **Primary** — contingent on tokenizer audit | Best Polynesian-adjacent pretraining signal among the candidates Rusty surveyed. License is the Llama community license (>700 M MAU clause + naming requirement), which is acceptable at prototype scope where no release is planned. |
| **Qwen2.5-7B**               | **Fallback**                                | Cleanest license (Apache-2.0). Used if Llama-3.1-8B fails the tokenizer audit (e.g., pathological byte-fallback on ʻokina / kahakō) or if the license clauses become load-bearing later.                                              |
| **Qwen2.5-0.5B**             | **Smoke only**                              | Stage 0 plumbing validation and QLoRA-vs-fp16-LoRA falsification. Not a candidate base for Stage 1 numbers.                                                                                                                           |
| **Gemma-2-9B**               | **Held option**                             | Pending model-family updates. Gemma terms include flow-down + no-competing-foundation-model clauses; revisited only if Llama-3.1-8B and Qwen2.5-7B both miss.                                                                         |
| **Aya-23 / Aya-Expanse**     | **Excluded**                                | CC-BY-NC contaminates the openly-licensed posture. Useful only as a private reference, not as a base.                                                                                                                                 |
| **Mistral-7B**               | **Excluded**                                | Clean license, but weaker multilingual coverage and no meaningful Polynesian signal in pretraining. Wrong fit for ʻŌlelo Hawaiʻi.                                                                                                     |
| **From-scratch pretraining** | **Rejected**                                | Hawaiian is low-resource; from-scratch at our budget would underperform a careful adaptation. The team consensus is to spend effort on data, tokenizer, and eval, not on training a base from zero.                                   |

**Final base-model selection is blocked on the tokenizer audit.** No 7B/8B GPU spend opens before the real gated Llama audit reports on representative nūpepa, *Baibala Hemolele*, and contemporary slices, and before the embedding/lm_head policy is decided. The script path exists; access/run is the remaining blocker.

---

## 5. Training stages (summary)

Operational details — recipes, hyperparameters, exact gate metrics — live in [`docs/training-pipeline.md`](./training-pipeline.md). The summary here is the team-facing shape.

- **Stage 1 — Hawaiian CPT / DAPT (QLoRA).** Causal LM on Hawaiian monolingual text, **not** instruction tuning. QLoRA r=64/α=128 on all linear layers, lr 2e-4, seq 2048, ~1 epoch, 5–10 % English rehearsal to fight catastrophic forgetting. Tokenizer is the base's shipped tokenizer; embedding/lm_head unfreeze decision is the tokenizer audit's output.
- **fp16 merge.** Stage 1 LoRA is merged into the fp16 base. Tokenizer SHA equality is re-asserted. Sanity eval on the merged model must match pre-merge numbers within tolerance before Stage 2 loads it.
- **Stage 2 — Bidirectional en↔haw SFT (fresh LoRA on merged model).** Instruction-formatted, base's native chat template, target-only loss masking, 50/50 direction balance, 10–20 % Stage-1-style monolingual retention slice to prevent fluency loss. QLoRA r=32/α=64, lr 1e-4, seq 1024, 2–3 epochs.
- **Adapter discipline.** Merge → fresh LoRA is the working path. Stacked adapters across stages are allowed only for short A/B ablations and never for the candidate path; double-quantization noise and ambiguous active-adapter-at-inference bugs are not worth the optionality.

---

## 6. Evaluation cadence and gates

This plan defers all eval methodology to [`docs/eval_pipeline.md`](./eval_pipeline.md). Three things are load-bearing for the implementation sequence:

1. **Pre-FT baseline on the chosen base is mandatory** before Stage 1. No "better" claim is admissible without it.
2. **Cheap eval rides the checkpoint cadence** (~30–60 min) on Provider 2 — Hawaiian PPL, English PPL delta, ʻokina/kahakō survival, leakage recheck at Stage 1; chrF by direction, retention probe, leakage recheck at Stage 2. Cheap eval set is fixed and small; never re-tuned mid-run.
3. **Full eval is gate-only.** Stage 1 → merge, merge → Stage 2, Stage 2 → internal prototype-candidate promotion, and the final reproducibility-gated eval on Provider 3 are the only points where the full eval suite runs.

Hard fails worth restating here because they shape the implementation plan, not just the eval doc:

- ʻokina collapsing to U+2018 / U+0027 in Hawaiian generations is a Stage 1 hard fail.
- English PPL regression > +20 % vs the pre-FT baseline is a Stage 1 hard fail (rerun with more rehearsal, do not promote).
- Direction-asymmetric chrF collapse on Stage 2 is a Stage 2 hard fail (rebalance batches, audit per-direction parallel-pair quality, do not promote).
- Provider 3 headline eval is invalid until the same-checkpoint reproducibility eval passes ±0.02 PPL vs Provider 2.

---

## 7. Checkpoint / provider handoff contract

The artifact bus across providers is an **HF Hub private repo or an equivalent S3-compatible object store**. This is necessary but not sufficient. A checkpoint that pushes to HF and pulls on the next provider is **not** a portable training state on its own — HF carries artifacts, not env or loop state.

**Every checkpoint must include:**

- adapter weights
- optimizer state
- scheduler state
- RNG state (cpu, cuda, numpy, python)
- dataloader position (stateful dataloader; mid-epoch resume must not silently re-shuffle)
- `trainer_state.json` (global step, epoch, loss history, metric history)
- `env.lock` (torch, transformers, peft, bitsandbytes, accelerate, flash-attn, CUDA — exact versions)
- base-model SHA pin
- tokenizer SHA pin

**Plus, alongside the checkpoint:**

- corpus manifest SHA (Stage 1 / Stage 2 / prototype, whichever applies)
- `eval_hashes.jsonl` SHA
- eval log up to this checkpoint, with eval-suite SHA

**Save policy:** every ~30 min wallclock, on SIGTERM/exit, and at epoch boundaries. **Resume policy:** recompute grad-accum to preserve the global batch size if GPU count or class changes between providers; if the first cheap-eval point on the new provider does not match the previous provider within ±0.02 PPL, stop — the env is not really restored.

Storage choice rationale: HF Hub private repo is the most provider-agnostic option in our stack, **except** when push reliability is in question (e.g., behind GFW). PRC providers are excluded for this prototype on those grounds; see Livingston's and Basher's joint advisory in `.squad/decisions.md`.

---

## 8. Risks

Ranked by expected impact on the prototype, not on a release.

1. **Tokenizer fragmentation on ʻokina / kahakō** — pathological byte-fallback on the Hawaiian diacritics is the most likely "wrong base" signal. Mitigation: tokenizer audit is a Stage 0 hard gate; vocab extension or a base swap is preferable to grinding through a bad tokenizer.
2. **Catastrophic forgetting** — Stage 1 erodes English; Stage 2 erodes Stage 1 fluency. Mitigation: 5–10 % English rehearsal in Stage 1; 10–20 % Stage-1-style monolingual retention slice in Stage 2; English PPL regression and retention probes in cheap eval.
3. **Eval leakage / contamination** — train↔eval n-gram overlap, near-duplicates, cluster-leak across splits silently inflate every score. Mitigation: cluster-aware splits, `eval_hashes.jsonl`, artifact/CI assertion before training reads, n-gram strip recheck on outputs, planted-positive smoke that must fire the available guard path.
4. **OCR and source-register skew** — heavy weighting on 19th-century nūpepa or *Baibala Hemolele* yields a model that sounds period/biblical. Mitigation: per-source slicing in eval, register-balance check at manifest stage, contemporary slice tracked separately.
5. **Provider-switch drift mid-stage** — bnb 4-bit kernels are not deterministic across CUDA / GPU class; dtype toggles between fp16 (T4/P100) and bf16 (A10/A100/4090) silently change the loss curve. Mitigation: Stage 1 + merge + Stage 2 pinned to one provider/GPU class on Provider 2; reproducibility gate on Provider 3.
6. **Free-tier interruption** — Kaggle and Colab sessions die. Mitigation: checkpoint every 30 min, resume from HF, do nothing on Provider 1 that has to land in one continuous session.
7. **HF Hub push reliability on some networks** — relevant if a provider lives behind GFW. Mitigation: PRC providers excluded for this prototype; release-candidate work (hypothetical) would re-evaluate.
8. **Quantization loss interacting with Hawaiian orthography** — bounded prior, but specific to our corpus and tokenizer. Mitigation: smoke-tier QLoRA-vs-fp16-LoRA falsification on 0.5B / 1B per `eval_pipeline.md` §7, before any 7B spend.

---

## 9. Non-goals

Restated for the implementation plan specifically. These are the things this plan **does not** promise and will **not** quietly drift toward.

- **No public release** of weights, adapters, tokenizer artifacts, datasets, generations, eval scores, API, or demo out of this work. The release branch of `training-pipeline.md` and the cultural-review machinery in `data-pipeline.md` describe what a release would require; nothing in this plan triggers any of it.
- **No claim of Hawaiian fluency, cultural authority, or ceremonial / official / educational fitness.** Eval numbers describe held-out behavior; they do not certify the model speaks ʻŌlelo Hawaiʻi correctly or appropriately.
- **No benchmark leaderboard run.** Eval exists to find the bottleneck and choose the next experiment, not to publish numbers.
- **No frontier-scale training** and no full fine-tune of a 7B/8B base. QLoRA is the only training shape budgeted here.
- **No ad hoc web-scraped corpus.** Sources come through `data-pipeline.md` with provenance, observed license, ToS snapshot, and local-only lineage.
- **No production service**, hosted API, demo Space, or chat product out of this repo.
- **No multi-node / FSDP / ZeRO-sharded run.** Single-GPU QLoRA only at this scope.

---

## 10. Open decisions

Tracked here so they don't disappear into prose. Each is blocking for some downstream phase.

1. **Final base-model selection — pending tokenizer audit.** Llama-3.1-8B is the working primary; Qwen2.5-7B is the fallback. Audit decides. Blocks: any 7B/8B Stage 1 spend.
2. **Provider 2 vendor pick after free validation.** RunPod community A100 hourly vs Lambda on-demand A100 vs Lightning AI Pro studio (with A100 hourly bursts) vs Azure A100 spot from remaining credit. Cost, HF push reliability, CUDA pinning, and persistent-disk availability all weigh in; final pick is Livingston's call with Basher's technical sign-off. Blocks: opening the 60 h window.
3. **Embedding / lm_head unfreeze policy.** Output of the tokenizer audit. Affects Stage 1 recipe and gradient-memory budget. Blocks: Stage 1 launch.
4. **Per-source slicing + as-is/normalized chrF dual-report — promote to formal gate?** Currently advisory in `eval_pipeline.md` §3.3. Open team question (Rusty raised it). Does not block Stage 0; should resolve before Stage 2 gate.
5. **Cultural-review owner.** Soft-blocker for prototype, hard-blocker for any future release scope. Tracked as an open gap from the prototype-scope reframe; not blocking this plan's phases but needs an owner before any release-candidate conversation reopens.

---

## 11. References

- [`README.md`](../README.md)
- [`docs/data-pipeline.md`](./data-pipeline.md)
- [`docs/training-pipeline.md`](./training-pipeline.md)
- [`docs/eval_pipeline.md`](./eval_pipeline.md)
- [`.squad/decisions.md`](../.squad/decisions.md) — ADRs: two-stage training plan, prototype-vs-release split, base-model recommendation, free-GPU chaining feasibility, checkpoint contract.
