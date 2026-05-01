# Training Pipeline

> Status: **PROTOTYPE — learning project, not for redistribution.**
> **No public release of weights, adapters, tokenizers, generations, eval scores, derived data, API, or demo is planned.** The "release-candidate" scope referenced throughout this document describes *hypothetical* gates that would apply if the project ever changed posture from learning prototype to public release — it is not a roadmap toward shipping. See the prototype-vs-release ADR in `.squad/decisions.md`.

This document describes the training pipeline for the Hawaiian-language LLM adaptation. It consolidates the accepted ADRs (two-stage training plan, base-model recommendation, prototype-vs-release split) into an operational sequence: what runs where, in what order, and what must be true before each step costs time or money.

It is not training code; it is the contract the training code is expected to satisfy.

**Companion doc:** [`data-pipeline.md`](./data-pipeline.md) describes how the corpora, manifests, and `eval_hashes.jsonl` consumed here are produced. The split is: data pipeline = what goes *into* the model (ingest, normalization, license/cultural tagging, contamination guards); training pipeline (this doc) = what the model *does* with that data (Stage 1 CPT → fp16 merge → Stage 2 SFT, gates, artifact lineage).

---

## 0. Pipeline at a Glance

```
[Stage 0]  Readiness gates  ──►  [Smoke]  Qwen2.5-0.5B end-to-end (both stages, tiny slice)
                                    │
                                    ▼
[Stage 1]  Monolingual Hawaiian CPT / DAPT  ──►  Stage 1 LoRA
                                    │
                                    ▼
                         Merge Stage 1 LoRA into fp16 base
                                    │  (internal artifact: base+haw-cpt, not released)
                                    ▼
[Stage 2]  Bidirectional en↔haw translation SFT  ──►  Stage 2 LoRA (fresh, on merged base)
                                    │
                                    ▼
[Eval]    Stage-specific gates  ──►  Run report + (private) artifact
                                    │
                                    ▼
[Release-scope gate]  Hypothetical separate clearance pass.  Prototype-tainted artifacts never ship.
```

The two-stage shape (Stage 1 CPT → merge → fresh Stage 2 SFT LoRA) is fixed. The base model and the gates around each stage are what change between prototype and release runs.

---

## 1. Stage 0 — Readiness Gates (no GPU spend until these pass)

Stage 0 is the cheap stage. It catches the failures that would otherwise burn the paid Provider 2 block.

### 1.1 Tokenizer audit (Rusty)

The main-target base model is **not** chosen until the audit passes. Smoke runs may proceed on `Qwen2.5-0.5B` (Apache-2.0) regardless, because the smoke's job is to validate plumbing, not model quality.

Audit deliverable:

- ~10k tokens of representative Hawaiian text (ʻokina, kahakō vowels, code-switching, proper nouns; include a representative nūpepa sample and a *Baibala Hemolele* sample).
- Unicode pinned to **NFC**, ʻokina canonicalized to **U+02BB**.
- Per-candidate metrics: tokens/word, byte-fallback rate, ʻokina survival, kahakō unitarity.

Implementation path:

The audit is run locally and writes its report under the ignored
`data/tokenizer_audit/` tree. Audited text must be NFC-normalized with likely
Hawaiian ʻokina stand-ins canonicalized to U+02BB before tokenization. If
`transformers` is missing or gated Llama tokenizer access is unavailable, the
audit must fail loudly with install/login instructions instead of emitting
placeholder numbers. Current status: there is no standalone audit script in
the repo; a tokenizer-audit test is planned. The gated Llama audit/go-no-go
remains the #8 spend gate and is still blocked on Hugging Face
access/dependencies plus an actual run.

Inspect these report fields before any serious Stage-1 spend:

- `model.model_id`, `model.model_repo_sha`, and `model.tokenizer_sha256`
  (`tokenizer_fingerprint_sha256` alias) — freeze these in the Stage-1 manifest.
- `input.sources` / `input.paths` — confirm representative sample coverage.
- `overall.tokens_per_word`, `overall.explicit_byte_fallback_rate`, and
  `overall.byte_fallback_or_proxy_rate`.
- `high_diacritic.tokens_per_word` plus the same byte-fallback/proxy fields for
  the high-diacritic slice.
- `diacritic_char_tokenization` — standalone ʻokina/kahakō token counts.
- `recommendation.decision` and `recommendation.blocking_reasons`.

Default gate policy for the Llama-3.1-8B spend gate: require at least 1,500
sample words and 10 high-diacritic samples (`ʻokina+kahakō >= 3` and
`diacritics/word >= 0.25`). Go only if overall tokens/word ≤ 2.50,
high-diacritic tokens/word ≤ 3.25, explicit `<0x..>` byte fallback is 0,
combined byte-fallback/proxy rate ≤ 1%, and each standalone Hawaiian diacritic
character tokenizes to ≤2 tokens. Any miss is **no-go** for serious 8B Stage-1
spend until a fallback tokenizer is audited or a vocab/embedding policy is
chosen.

Outcome → main target:

- **Primary:** `Llama-3.1-8B` if the audit passes (best Polynesian-adjacent pretraining signal).
- **Fallback:** `Qwen2.5-7B` (cleanest license: Apache-2.0).
- **Held option:** `Gemma-2-9B` (license flow-down clauses; only if both above fail).
- **Excluded as public-release base:** Aya-23 / Aya-Expanse (CC-BY-NC), Mistral-7B (weak multilingual coverage).

The chosen base-model SHA and tokenizer SHA are **frozen at Stage 1 start** and recorded in the run manifest. Stage 2 must load the identical tokenizer files (CI hash check).

### 1.2 Data foundation (Linus)

Hard prereq before any Stage 1 GPU launch (see two-stage ADR §"Hard data gates"):

1. Corpus inventory + per-document or (prototype-scope) per-source manifest populated.
2. License posture applied:
   - Release-candidate runs: CC0 / CC-BY / CC-BY-SA / explicit permissive only; loader rejects `prototype_private`, `unclear`, `unreviewed*`.
   - Prototype-private runs: relaxed per the prototype ADR, but `intended_use=prototype_private` set on every row, manifest still required, contamination guard still on.
3. Normalization end-to-end: UTF-8 → NFC → ʻokina U+02BB → whitespace/control clean → langID `haw` → boilerplate strip → exact SHA / repeated-paragraph dedup now, with MinHash/LSH near-dup dedup still planned. `sha256_raw` and `sha256_normalized` populated. For FineWeb-2 specifically, `205` only fetches raw LID-classified rows; `301_build_stage1_dataset.py` performs the prototype cleaning gate and records raw vs cleaned token counts plus rejection reasons before any Stage-1 trainer JSONL is emitted.
4. Cluster-aware train/dev/test/holdout splits assigned at corpus-build time. Held-out splits live in a read-only path; loaders forbidden from touching it.
5. Cultural-sensitivity tagging at ingest. Hard-escalate categories (mele/oli/pule, moʻolelo from named tradition-bearers, moʻokūʻauhau, place-name lore tied to specific ʻohana/ahupuaʻa, restricted-archive material, **bulk pre-1925 nūpepa**) tagged even at prototype scope.
6. `eval_hashes.jsonl` exists; build/check tools import it and assert empty intersection with training shards. Runtime dataloader enforcement remains the human-owned #4 guard.

Local Stage-1 artifacts exist under ignored `data/stage1/` (`stage1_manifest.jsonl`,
`stage1.jsonl.gz`, `token_target_report.json`, plus FineWeb cleaning stats). The
FineWeb-2 local run saw 95,507 rows, rejected 6,528, and reduced raw vs cleaned
Stage-1 train-token estimates from 59,534,611 to 44,067,289. The builder's
strict undersized-slice path exits **2**; that token-volume check does not
replace the real tokenizer audit gate above.

**No data → no train.** The contamination guard and cultural tagging do not relax under prototype scope; only the release-eligibility flag does.

### 1.3 Eval harness ready (Rusty / Basher / Livingston)

Both stages' eval probes must exist **before** the first 7B Stage 1 run launches:

- Stage 1 probes: held-out Hawaiian PPL, English PPL probe, ʻokina/kahakō retention check, hallucination probe, qualitative spot-eval form for the human reviewer.
- Stage 2 probes: chrF / chrF++ both directions reported separately, COMET if a multilingual COMET model covers Hawaiian adequately, no-translation-leakage check, generalization probe, human Likert form.

### 1.4 Pipeline smoke — Qwen2.5-0.5B, both stages, end-to-end

The 0.5B smoke is **not** a quality run. Its job:

- Exercise tokenizer freeze + hash check across stages.
- Validate Stage 1 → fp16 merge → Stage 2 fresh-LoRA path on a tiny slice.
- Confirm checkpoint resume works (otherwise a Kaggle session interruption eats a real run).
- Confirm contamination-guard CI assertion fires when forced and stays green when not.

Smoke runs locally on RTX 2080 first; then a Kaggle dry-run repeats it to validate cloud checkpoint sync and resume. **Both must be green before any 7B-class job is queued.**

**Stage 0 exit criterion:** tokenizer audit decided, base model frozen, data foundation green, eval harness wired, 0.5B smoke passes locally and on Kaggle, resume-from-checkpoint demonstrated. Only then does a 7B-class GPU get scheduled.

---

## 2. Stage 1 — Monolingual Hawaiian CPT / DAPT

### 2.1 Goal

Continued pretraining on Hawaiian monolingual text. Causal-LM objective, **no instruction templates**, full-token loss. Output: `stage1-haw-cpt` LoRA over the chosen base model.

### 2.2 Recipe (starting points)

- **Targets:** all linear layers (`q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj`).
- **LoRA:** r=64, α=128, dropout 0.05. Embeddings / `lm_head` trainable only if the tokenizer audit shows ʻokina/kahakō tokens are rare or split — audit-driven.
- **Sequence length:** 2048 (drop to 1024 only if Kaggle OOMs; never below 1024 for CPT).
- **Batch:** per-device 1 (T4) / 2 (A100 40GB), grad-accum to ~64k–128k effective tokens per step.
- **Optimizer / LR:** paged AdamW 8-bit, LR 2e-4 cosine, warmup 3%, min LR 2e-5. **One epoch** over the curated corpus; ≤2× repeats; ≥1–2 epochs preferred when corpus permits.
- **Quantization:** 4-bit NF4 + double-quant, bf16 compute (fp16 on Turing / RTX 2080), gradient checkpointing on, flash-attn 2 where supported.
- **Anti-forgetting:** mix in **5–10% English** rehearsal (clean general corpus, e.g. small FineWeb-Edu slice). English-PPL probe on a fixed held-out set every eval.

### 2.3 Compute placement

| Work | Where |
|---|---|
| Pipeline plumbing, NFC checks, eval scaffolding | Local RTX 2080 |
| 0.5B smoke (both stages) | Local RTX 2080 |
| 0.5B Kaggle dry-run | Kaggle |
| **7B/8B Stage 1 CPT** | **Provider 2 paid stable block** — one vendor/GPU class, L4 / A10 / A100 / 4090-class (SM ≥80). T4/P100 free tiers are smoke-only, not gate-number environments. |
| Stage 1 → fp16 merge sanity-check | Same Provider 2 environment; CPU merge is acceptable only with matching env lock, base SHA, and tokenizer SHA. |

The repo also includes
`code/configs/stage1_fineweb2_haw_kaggle_t4x2.json` for free-tier Kaggle
prototype iteration when the goal is to shake out the real 8B QLoRA mechanics
before paying for a stable GPU block. It trains on the cleaned multi-source
Stage 1 JSONL (`data/stage1/stage1.jsonl.gz`: FineWeb-2 + hawwiki +
hawwikisource) with the FineWeb-2 Hawaiian dev split for eval. It is
intentionally T4x2-tuned
(`fp16=true`, `bf16=false`, `max_seq_len=2048`,
`gradient_accumulation_steps=16`, per-device batch 1, gradient checkpointing
on, frequent checkpoints). If Kaggle OOMs, fall back to `max_seq_len=1024`
and `gradient_accumulation_steps=32`. Treat metrics from that profile as debug
signals; they do not replace the Provider-2-class gate numbers above.

> **Kaggle T4x2 — `device_map="auto"` is model placement, not data parallel.**
> The current Kaggle command (`python -m llm_hawaii.train`) runs a single
> process with `device_map="auto"`, which is Hugging Face big-model inference
> sharding across the two T4s. Only one process runs; you do **not** get
> data-parallel throughput from the second GPU. True DDP would require
> removing `device_map="auto"`, loading the model per-rank, and launching with
> `torchrun --nproc_per_node=2` or `accelerate launch`. That is a separate
> experiment and not wired here.

Stage 1 dominates wallclock. If only one stage fits in budget, **Stage 1 must run on the 7B**.

### 2.4 Stage 1 evaluation gate (go / no-go)

All must hold to proceed to merge + Stage 2:

1. **Orthography preservation.** Generated Hawaiian retains ʻokina at U+02BB (not U+2018 / U+0027) and kahakō at expected rates vs a held-out reference distribution. **Hard fail** if ʻokina collapses to apostrophe.
2. **Hawaiian held-out PPL** lower than the base by a clearly visible margin (ballpark ≥20% relative reduction; exact threshold locked once base PPL is observed).
3. **English held-out PPL** has not blown up (≤20% relative *increase* vs base). If it has, forgetting is too severe; rerun with more English rehearsal.
4. **Fluency / native-speaker spot eval** on N=50–100 short Hawaiian continuation prompts (20-prompt minimum if reviewer time is scarce).
5. **Hallucination probe** on prompts about non-existent Hawaiian places/people; track fabrication rate.
6. **Tokenizer audit metrics** did not regress on the trained model's outputs.

Under **prototype scope**, gates 4–5 are *encouraged but not blocking*; gates 1–3 and 6 still apply. Under **release-candidate** scope, all six are blocking.

If any blocking gate fails → no Stage 2. Diagnose data or recipe first.

---

## 3. Merge step — Stage 1 LoRA into fp16 base

This step is non-optional and is the reason the pipeline avoids stacked-adapter pathologies.

- Save the Stage 1 LoRA + checkpoints.
- Merge Stage 1 LoRA into the base in **fp16** (not back into 4-bit). Output: `base+haw-cpt`, an internal artifact.
- Same base-model SHA used for the merge step **must** be used for Stage 2 init. Recorded in the run manifest.
- The merged artifact is **kept internally, not released** — even at release scope, the released chain is rebuilt from the cleared corpus, not relabeled from a prototype merge.

**Why this shape (recap):** stacked adapters at different ranks / target-modules cause merge headaches, double-quantization noise on QLoRA, and ambiguous "which adapter is active" inference bugs. Stacking is allowed **only for short A/B experiments** by Rusty (e.g., ablating Stage 1's contribution cheaply) and **never as a release artifact**.

Quantization rule: **one quant boundary per stage.** Stage 1 merges into fp16; Stage 2 reloads in 4-bit fresh from the fp16 merged model.

---

## 4. Stage 2 — Bidirectional en↔haw Translation SFT

### 4.1 Goal

Supervised fine-tuning for translation, **bidirectional (en→haw and haw→en) in the same run**, instruction-formatted, on the merged Stage 1 base. Output: `stage2-haw-sft` LoRA — a **fresh** LoRA on the merged model, not a continuation of the Stage 1 adapter.

### 4.2 Recipe (starting points)

- **Instruction template:** the base model's native chat template (Llama-3.1 chat template if Llama; ChatML if Qwen). Two minimum prompt variants per direction, plus Hawaiian-language prompt variants ("Unuhi i kēia …") so the model handles haw-side instructions, not just English-side.
- **Loss:** **target-only.** `labels=-100` on prompt tokens. **Non-negotiable.**
- **Sequence length:** 1024.
- **Batch:** per-device 2–4, grad-accum to effective 32.
- **LoRA:** r=32, α=64, dropout 0.05.
- **Optimizer / LR:** LR 1e-4 cosine, warmup 3% (≈⅓–½ of Stage 1 LoRA LR). 2–3 epochs max; early-stop on dev BLEU/chrF.
- **Direction balance:** 50/50 unless data forces otherwise; report eval per direction, never averaged.
- **Retention slice:** **10–20% Stage-1-style monolingual Hawaiian CLM examples** mixed into every batch mix to prevent catastrophic forgetting of Stage 1 fluency.

### 4.3 Compute placement

| Work | Where |
|---|---|
| **7B/8B Stage 2 SFT** | Same **Provider 2 paid stable block** as Stage 1 + merge; no provider/GPU-class switch mid-run. |
| Final eval / baselines | Provider 3 eval-only environment after same-checkpoint reproducibility passes. |

Provider 2 is a bounded paid window, not an open-ended training account. If Azure is selected, use spot only with auto-shutdown, checkpoint to blob/object storage, budget alerts at 50% / 80%, and short sessions; if another provider is selected, the same cost and checkpoint discipline applies.

### 4.3.1 Stage 2 SFT JSONL emitter (`scripts/330_emit_stage2_sft_jsonl.py`)

The bridge from canonical `stage2_manifest.jsonl` to trainer-facing JSONL is a small, stdlib-only script. One canonical pair → up to two directional rows per the [Stage 2 output JSONL](./data-pipeline.md#stage-2-output-jsonl) contract; row shape is fixed there and the trainer reads `direction` / `loss_mask` rather than inferring.

- **Inputs.** A Stage-2 manifest JSONL (one row per canonical pair). Each row carries either inline `text_en` / `text_haw` or `text_en_path` / `text_haw_path` refs (absolute or repo-relative). Sha-addressed text refs are a TODO once the Stage-2 ingest emits a `sha256_*_clean → blob` map.
- **Output.** `data/stage2/stage2_sft.jsonl` by default (under the gitignored `data/` tree). The script never writes tracked training data into the repo.
- **Filters (fail-conservative, all configurable).** `--splits` (default `train`), `--directions` (`both` | `en2haw` | `haw2en`), `--min-alignment-score` (only gates rows with a non-null embedding score; deterministic alignments — `verse-id`, `tmx-line`, etc. — pass through), and opt-in flags `--allow-review-required` / `--allow-synthetic`. Rows with `alignment_review_required=true` or unrecognised `alignment_type` are skipped by default with a counted reason.
- **Provenance carried per emitted row.** `pair_id`, `source`, `register`, `alignment_type`, `alignment_method`, `alignment_score`, `synthetic`, `synthetic_source_model`, `edition_or_version`, `prototype_only`, `release_eligible`, `dedup_cluster_id`, `crosslink_stage1_overlap`, plus `split`. Heavier fields stay in the manifest, queryable by `pair_id`.
- **Out of scope here.** Retention-slice (`haw-mono`) rows — those come from the Stage-1 builder and are merged in by a separate step. Contamination guard against `eval_hashes.jsonl` is a separate pass before any training read; this emitter must not pretend to gate.
- **Splits are pass-through.** Re-splitting at emit time would silently break the cluster-aware split isolation already baked into the manifest.

The emitter is a skeleton: it validates the contract end-to-end on a small fixture and stays NFC-clean, but real instruction-template rotation (~5 paraphrases per direction loaded from `data/stage2/templates.json`) is wired as a TODO.

### 4.4 Stage 2 evaluation gate (go / no-go)

1. **chrF / chrF++** (primary; BLEU is unreliable for morphologically rich, low-resource languages — report both, weight chrF) on a held-out en↔haw dev/test set, **beating both** (a) base zero-shot and (b) Stage-1-only zero-shot, **in both directions, reported separately, never averaged**.
2. **COMET** if a multilingual COMET model covers Hawaiian adequately; otherwise document the limitation.
3. **No-translation-leakage check:** model output on the test set is not a near-duplicate of any training pair (bigram-overlap threshold).
4. **Adequacy + fluency human eval** by a Hawaiian speaker, N=100 ideal / N=30 minimum per direction, 5-point Likert. Mean **≥3.5** to promote as an internal candidate; **≥4.0** to call it the internally recommended checkpoint.
5. **Orthography retention re-check.** SFT didn't kill the ʻokina/kahakō behavior installed by Stage 1. If it did, retention slice was too small; reweight and rerun.
6. **Generalization probe:** behavior on non-translation prompts hasn't collapsed into "always translate." Refusal/safety/register sanity probe included.

Under **prototype scope**, gate 4 is *encouraged but not blocking*; gates 1–3 and 5–6 apply. Under **release-candidate** scope, all six are blocking, plus the release gate in §6.

---

## 5. Artifact lineage and run manifest

Every run, prototype or release, produces a run manifest recording the chain. A trained artifact without a complete manifest is treated as garbage and not promoted.

**Recorded per run (implemented in `code/llm_hawaii/train.py` `write_run_report`):**

- `base_model`, `base_model_sha` — frozen at Stage 1 start; Stage 2 must match.
- `tokenizer_sha` — SHA-256 over canonical tokenizer files (`tokenizer.json`, `tokenizer_config.json`, etc.); frozen at Stage 1 start; Stage 2 CI asserts identical. **Implemented:** `compute_tokenizer_sha()` in `train.py`; `run_stage2_lineage_preflight()` enforces equality before GPU work.
- `artifact_sha` — SHA-256 of the saved LoRA adapter (`adapter_model.safetensors`); written by each stage so the next stage can reference it as `parent_artifact_sha`.
- `stage` — `0-smoke` | `1-cpt` | `merge` | `2-sft`.
- `parent_artifact_sha` — the prior stage's artifact_sha; resolved from `parent_run_dir/run_report.json` at Stage 2 train time.
- `corpus_manifest_sha` — SHA-256 of the training JSONL actually used (convenience top-level field; also in `train.sha256`).
- `eval_hashes_sha` — hash of `eval_hashes.jsonl` at run time.
- `intended_use` — `prototype_private` | `release_candidate`. Loader enforces.
- `seed`, training config, LoRA config, quantization config.
- Eval-suite version and full per-gate results.

**Stage 2 lineage preflight (`--preflight` on a `stage2-sft` config):**

Set `parent_run_dir` in the config to the Stage 1 / merged-base output dir.  The preflight will:
1. Load `parent_run_dir/run_report.json` to read the expected `tokenizer_sha`.
2. Re-hash the tokenizer files in `parent_run_dir` and assert they match.  A single-byte flip in `tokenizer.json` → hard fail before any GPU time is spent.
3. Record `parent_artifact_sha` from the parent run report into the Stage 2 run manifest.

```bash
# Stage 2 lineage preflight (no GPU, no model download):
PYTHONPATH=code python -m llm_hawaii.train \
  --config code/configs/stage2_prototype.json --preflight
```

**Lineage chain (hypothetical release-scope run):**

```
base_model_sha
   └─► stage1_lora_sha   (trained on cleared corpus, intended_use=release_candidate)
         └─► merged_fp16_sha   (Stage 1 → fp16 merge)
                └─► stage2_lora_sha   (fresh LoRA on merged base, cleared parallel + retention)
                       └─► cleared_artifact_candidate   (subject to release gate, §6; not planned here)
```

**Prototype runs share the same shape but carry `intended_use=prototype_private` end-to-end.** A prototype merged-base or prototype Stage 2 LoRA **never** flows into a release-candidate chain. To produce a release artifact, Stage 1 is re-run on the cleared corpus from scratch — the merge convention is reused, but the inputs are the cleared corpus, not the prototype corpus.

---

## 6. Compute sequencing and explicit gates before GPU spend

The three-provider plan is the budget reality: local/free tiers for Stage 0, one bounded paid Provider 2 block for Stage 1 + merge + Stage 2, and a separate Provider 3 eval-only pass. Translation: one real run, maybe one retry. Sequencing matters.

| Step | Where | Gate that must be green before this step starts |
|---|---|---|
| Pipeline scaffolding, manifest validators, eval harness | Local RTX 2080 | none |
| 0.5B end-to-end smoke (both stages) | Local RTX 2080 | tokenizer audit decided; data foundation green; eval harness wired |
| 0.5B Kaggle dry-run | Kaggle | local smoke green; checkpoint resume demonstrated |
| **7B/8B Stage 1 CPT** | **Provider 2 paid stable block** | base model frozen; tokenizer SHA frozen; corpus manifest generated locally and hashed; eval ledger loaded; contamination artifact checks green; English rehearsal slice prepared; Provider-2-class resume probe green |
| Stage 1 → fp16 merge sanity-check | Same Provider 2 environment | Stage 1 eval gate green (or, prototype scope, blocking subset green) |
| **7B/8B Stage 2 SFT** | Same Provider 2 paid stable block | merged base validated; Stage 2 manifest green; tokenizer hash CI check green; retention slice prepared; eval probes loaded |
| Final eval / baselines | Provider 3 eval-only environment | Stage 2 run completed; checkpoints synced; same-checkpoint reproducibility gate passes |

**Paid-provider guardrails are non-negotiable** any time credits are spent: auto-shutdown on idle, checkpoint to the artifact bus (not ephemeral VM disk), budget alerts at 50% / 80%, and no launch before the local/free pipeline is green. Azure, if chosen, is spot-only.

**No 7B-class GPU spend** until Stage 0 is green. **No Stage 2 spend** until the Stage 1 gate is green for the run's `intended_use` tier.

---

## 7. Go / no-go criteria summary

Compact form, for the run report's TL;DR.

### Stage 0 → Stage 1
- [ ] Tokenizer audit complete; main-target base model decided (Llama-3.1-8B primary; Qwen2.5-7B fallback).
- [ ] Data foundation green for the run's `intended_use` tier.
- [ ] Eval harness wired (both stages' probes loadable).
- [ ] 0.5B smoke green locally and on Kaggle; resume-from-checkpoint demonstrated.

### Stage 1 → merge (release-candidate; prototype relaxes 4–5)
- [ ] ʻokina U+02BB and kahakō preserved in generations.
- [ ] Hawaiian held-out PPL meaningfully below base (≥~20% relative).
- [ ] English held-out PPL ≤20% relative increase vs base.
- [ ] Native-speaker spot eval N≥20–50 acceptable. *(prototype: encouraged)*
- [ ] Hallucination-probe fabrication rate not catastrophic. *(prototype: encouraged)*
- [ ] Tokenizer-audit metrics not regressed on outputs.

### Merge → Stage 2
- [ ] Stage 1 LoRA merged into fp16 successfully; sanity generations match Stage 1 LoRA inference within tolerance.
- [ ] Same base SHA + tokenizer SHA carried forward.

### Stage 2 → internal candidate (release-candidate; prototype relaxes 4)
- [ ] chrF / chrF++ beats base and Stage-1-only zero-shot in both directions, reported separately.
- [ ] No-translation-leakage check green.
- [ ] Orthography retention not killed by SFT.
- [ ] Human Likert ≥3.5 mean (≥4.0 to call it recommended). *(prototype: encouraged)*
- [ ] Generalization probe green ("does not always translate").
- [ ] COMET reported if applicable, else limitation documented.

### Release gate (separate clearance pass; **does not happen in this pipeline run**)
- [ ] Per-source cultural review by a named Hawaiian-speaking reviewer; only `cleared` sources in the training mix. **Cultural-review owner is currently unassigned — this gate cannot be cleared until that gap is filled.**
- [ ] Per-source training-rights review distinct from copyright.
- [ ] License whitelist re-applied; zero `unreviewed_prototype` rows.
- [ ] Contamination + cluster-aware split isolation re-verified; tokenizer audit locked.
- [ ] Stage 1 + Stage 2 release-tier human eval per the two-stage ADR.
- [ ] Model card with provenance, register skew, known failure modes, explicit not-fit-for statements (ceremonial / cultural / official translation use).
- [ ] **No prototype-tainted weights in the released chain.** Stage 1 is re-run on the cleared corpus; the released chain is built from scratch using the merge convention.

Until the release gate is cleared, every artifact directory carries the markers from the prototype-vs-release ADR (`Status: PROTOTYPE — learning project, not for redistribution.`, etc.) and the repo-level `prototype-data` / `do-not-release` labels apply to commits that touch training data.

---

## 8. References

- `.squad/decisions.md` — ADR "Two-stage training plan — Hawaiian fluency (Stage 1 CPT) → bidirectional en↔haw SFT (Stage 2)".
- `.squad/decisions.md` — ADR "Prototype-vs-release split for data gates and release artifacts".
- `.squad/decisions.md` — Decision Note "Base-model recommendation for Hawaiian adaptation".
- `.squad/decisions.md` — Decision Notes on Azure credit fit and training-work fit.
- [`data-pipeline.md`](./data-pipeline.md) — Stage 1 + Stage 2 data ingest, manifests, and contamination guards that feed this training pipeline.
- [`eval_pipeline.md`](./eval_pipeline.md) — metrics, cadence, diagnostic slicing, attribution matrix, and run-report schema that backs the gates in this doc.
- [`implementation_plan.md`](./implementation_plan.md) — three-provider execution sequencing, Stage 0 prereqs, model-choice rationale, and open decisions that wrap this pipeline.
- `README.md` — project goals, non-goals, and overall planning posture.
