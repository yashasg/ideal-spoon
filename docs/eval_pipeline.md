# Evaluation Pipeline

> **Status:** Prototype design for a learning project. **No public release** of weights, adapters, tokenizer, generations, or eval scores is planned. The gates and metrics below describe what an honest internal eval loop looks like for a low-resource Hawaiian adaptation; they are not a release certification process. See the prototype-vs-release ADR in [`.squad/decisions.md`](../.squad/decisions.md).
>
> **Owner:** Rusty (NLP Researcher), with input from Basher (training) and Livingston (compute/budget) where eval cadence collides with free-tier reality.
>
> **Companion docs:**
> - [`data-pipeline.md`](./data-pipeline.md) — what goes *into* the model (ingest, normalization, manifests, contamination guards, `eval_hashes.parquet`).
> - [`training-pipeline.md`](./training-pipeline.md) — what the model *does* with that data (Stage 1 CPT → fp16 merge → Stage 2 SFT, with stage gates).
>
> This doc covers what we measure, when we measure it, how we slice it, and how we attribute regressions to a cause rather than a vibe.

---

## 1. Why this document exists (assessment basis)

The working prior is that **4-bit QLoRA quantization loss is real but small** relative to the bottlenecks that actually constrain a Hawaiian adaptation at this scale. Published QLoRA NF4 deltas land around ~0.1–0.4 PPL and ~0–1 chrF on English-style benchmarks. That is not the dominant error term for ʻŌlelo Hawaiʻi.

The **active bottleneck must be measured, not assumed.** Likely candidates, in rough order of expected impact:

1. **Tokenizer fragmentation** on ʻokina (U+02BB) and kahakō vowels (ā ē ī ō ū) — high tokens/word and frequent byte-fallback waste context and gradient signal.
2. **Unicode / orthography drift** — NFC vs NFD mixing, ʻokina collapsing to U+2018 / U+0027, kahakō stripped or decomposed.
3. **Corpus size and register skew** — heavy weighting toward 19th-century nūpepa or *Baibala Hemolele* yields a model that sounds period/biblical, not contemporary; conversely a thin contemporary slice generalizes poorly.
4. **OCR and source-quality noise** — nūpepa scans introduce systematic substitutions (e.g., long-s, broken diacritics) that propagate as learned errors.
5. **Catastrophic forgetting** — Stage 1 CPT erodes English; Stage 2 SFT erodes Stage 1 fluency; either failure mode is invisible without explicit probes.
6. **Eval leakage / contamination** — train↔eval n-gram overlap, near-duplicate pairs, or cluster-leak across splits inflate every score.
7. **Weak eval** — a single global metric (BLEU, average PPL) is near-useless on a morphologically rich low-resource target.
8. **Quantization loss** — present, bounded, and the cheapest to falsify (see §8).

The job of the eval pipeline is to make the *currently dominant* bottleneck legible after every meaningful checkpoint, so the next experiment is targeted instead of speculative.

---

## 2. Evaluation cadence

| When | What runs | Cost target | Purpose |
|---|---|---|---|
| **Pre-training baseline** | Full eval suite on the un-finetuned base model + tokenizer | One-time, local or Kaggle | Anchor every later delta. No "better" claim is allowed without this number. |
| **Stage 0 smoke** | Reduced eval on Qwen2.5-0.5B end-to-end (both stages, tiny slice) | Local RTX 2080, then Kaggle | Validates plumbing: harness loads, metrics emit, contamination guard fires. Quality numbers are not interpreted. |
| **Per-checkpoint Stage 1 eval** | Small fixed eval set (see §3) on each saved checkpoint | ~30–60 min wallclock or every meaningful step interval (see §4) | Detect divergence, orthography collapse, English regression *during* the run, not after. |
| **Stage 1 gate** | Full Stage 1 eval suite on candidate checkpoint | At checkpoint promotion | Go/no-go for fp16 merge → Stage 2. Defined in `training-pipeline.md` §2.4. |
| **Per-checkpoint Stage 2 eval** | Small fixed translation eval (chrF both directions, leakage check, retention probe) | Cadence matched to Stage 2 step count; checkpoint-aligned | Catch direction collapse, "always translate" regression, retention loss. |
| **Stage 2 gate** | Full Stage 2 eval suite on candidate checkpoint | At checkpoint promotion | Go/no-go for ship-as-candidate. Defined in `training-pipeline.md` §4.4. |
| **Post-run error analysis** | Slice-by-slice diagnostic pass (see §6) on the gated checkpoint | After gate, before next iteration | Identify the dominant bottleneck for the next experiment. Output feeds the run report's "next experiment" field. |

The cadence is deliberately tilted toward **cheap, frequent, checkpoint-aligned** probes during training and **expensive, careful, gated** probes at stage boundaries. The expensive probes are not run on every checkpoint; the cheap ones are.

---

## 3. Metrics

Metrics fall into four buckets. Every metric is reported with the eval-suite SHA so cross-run comparisons are honest.

### 3.1 Tokenizer / orthography (cheap, run on every eval)

| Metric | What it catches |
|---|---|
| **Tokens/word on Hawaiian text** | Tokenizer fragmentation. Dropping by extending vocab should show here. |
| **Byte-fallback rate** | Tokenizer routing Hawaiian through bytes — a strong "wrong base/tokenizer" signal. |
| **ʻokina survival rate** | ʻokina present at U+02BB in generations vs reference distribution. **Hard fail at Stage 1 gate** if it collapses to U+2018 / U+0027. |
| **Kahakō retention rate** | ā/ē/ī/ō/ū present at expected frequency vs reference; catches NFC/NFD drift and silent stripping. |

These metrics are computed on both the eval set's references *and* the model's generations. Divergence between the two is the diagnostic.

### 3.2 Language modeling (Stage 1 primary, Stage 2 monitor)

| Metric | What it catches |
|---|---|
| **Hawaiian held-out PPL** | Stage 1 progress against the un-finetuned base. Reported per source/register slice as well as overall. |
| **English PPL regression** | Forgetting. Tracked vs base; a >20% relative increase is the threshold for "rerun with more rehearsal" at Stage 1. |

Held-out splits are cluster-aware (see `data-pipeline.md`); PPL is computed only on the read-only held-out path that the loaders are forbidden from touching.

### 3.3 Translation (Stage 2)

| Metric | Notes |
|---|---|
| **chrF / chrF++ by direction** | Primary. Reported separately for en→haw and haw→en. **Never averaged.** BLEU is reported alongside but not weighted — it is unreliable on morphologically rich low-resource targets. |
| **chrF as-is vs diacritic-normalized** | Dual-report. If the gap collapses under normalization, the regression is orthography handling, not translation quality. (Currently advisory; promotion to formal gate is an open team question.) |
| **COMET (if applicable)** | Only if a multilingual COMET model has demonstrable Hawaiian coverage. Otherwise the limitation is documented in the run report. |

### 3.4 Integrity and behavior probes

| Probe | What it catches |
|---|---|
| **Leakage / contamination check** | Test outputs vs training shards — bigram-overlap and exact-SHA. CI-asserted at load time; recomputed on outputs as a generation-time check. |
| **Hallucination probe** | Prompts about non-existent Hawaiian places/people; track fabrication rate. Stage 1 signal for "model is confabulating fluent-sounding nonsense." |
| **Generalization probe** | Non-translation prompts at Stage 2; catches "always translate" collapse and refusal/register sanity. |
| **Human spot eval** | N=20–50 minimum, N=50–100 ideal, by a Hawaiian speaker/learner. 5-point Likert for adequacy + fluency. Required for release scope; encouraged for prototype scope. **Automatic metrics alone are not trusted.** |

---

## 4. Checkpoint-aligned eval frequency (Kaggle / free-tier reality)

Free-tier sessions are interruptible. Eval frequency must respect that.

- **Cheap eval at every checkpoint save**, where "every checkpoint" is the training pipeline's chosen save cadence (typically every ~30–60 minutes wallclock, or every N optimizer steps tuned so a session interruption never loses more than one checkpoint's worth of work).
- **Cheap eval set is fixed and small**: a few hundred Hawaiian held-out items for PPL + orthography metrics; for Stage 2, a small fixed parallel slice (≤500 pairs per direction) for chrF + leakage. The same eval set is used across all checkpoints in a run so deltas are comparable.
- **Full eval only at stage boundaries and candidate checkpoints.** Full eval includes the human spot eval, full translation suite, COMET (if applicable), and the diagnostic slicing pass.
- **Never re-tune the eval set mid-run.** Eval-set changes bump the eval-suite SHA and break comparability with prior checkpoints.
- **Eval runs are checkpoint-aligned, not wallclock-aligned.** If a Kaggle session dies mid-eval, the next session resumes from the last fully-evaluated checkpoint, not from a partial eval.

The principle: cheap probes catch divergence early; expensive probes confirm gate decisions.

---

## 5. Diagnostic slicing

A single global metric tells you almost nothing. Every gate-level eval and every post-run analysis pass slices the same generations along these axes:

| Slice axis | What it isolates |
|---|---|
| **Source / register** | Period/biblical vs contemporary vs governmental vs educational. Catches register skew (e.g., model only sounds like 1860s nūpepa). |
| **Direction** (Stage 2) | en→haw vs haw→en. Always reported separately. Asymmetric collapse is a common Stage 2 failure mode. |
| **Length** | Short / medium / long. Catches truncation-driven artifacts and attention-budget effects. |
| **Diacritic density** | Items binned by ʻokina + kahakō count. Performance drop on high-density slices is the orthography-handling fingerprint. |
| **OCR confidence** | Where source-level OCR confidence is available (nūpepa pipeline). Isolates OCR noise from model behavior. |
| **Tokenizer behavior** | Items binned by tokens/word and byte-fallback rate at the input. Identifies whether quality drops correlate with fragmentation. |
| **Data split** | Train vs dev vs test vs holdout. Gap between train and dev is the overfitting signal; gap between dev and holdout is the cluster-leak signal. |
| **Provider / environment handoff** | Local vs Kaggle vs Azure runs of the same eval. Catches harness drift, dtype/quantization differences, and environment-specific silent failures. |

Slicing is not optional. The "headline number went up" framing is rejected at code review.

---

## 6. Attribution matrix (symptom → likely cause → next experiment)

Used during post-run error analysis. The matrix is not exhaustive; it is the first-pass triage.

| Symptom | Likely cause | Next experiment / fix |
|---|---|---|
| chrF gap collapses under diacritic normalization | Orthography handling, not translation | Re-audit tokenizer on outputs; check ʻokina U+02BB vs U+2018 in generations; verify NFC pinning end-to-end. |
| ʻokina absent or apostrophe in Hawaiian generations | Tokenizer collapsed it, or training data wasn't normalized | Tokenizer audit on outputs; verify `sha256_normalized` equals expected NFC form on training shards; consider unfreezing embeddings/lm_head. |
| English PPL blew up after Stage 1 | Catastrophic forgetting — rehearsal too thin | Increase English rehearsal slice (5% → 10%); verify rehearsal corpus didn't drift. |
| Stage 1 fluency lost after Stage 2 | Retention slice too small or off-distribution | Increase Stage 2 retention slice (10% → 20%); verify retention examples are Stage-1-style monolingual CLM, not SFT-formatted. |
| One direction's chrF collapses (en→haw or haw→en) | Direction imbalance or asymmetric data quality | Rebalance batches 50/50; audit parallel-pair quality per direction; check instruction templates cover both haw-side and en-side prompts. |
| Test chrF improbably high | Eval leakage | Recompute after n-gram strip; re-run cluster-aware split builder; verify `eval_hashes.parquet` was actually loaded by the dataloader. |
| Hallucination rate high on real-world Hawaiian entities | Corpus gap or overfitting to register | Slice by source; check whether hallucinations cluster on contemporary topics absent from the corpus. |
| Quality drop correlates with high tokens/word slices | Tokenizer fragmentation is the bottleneck | Vocab extension experiment; consider Hawaiian-specific BPE/Unigram piece set; weigh embedding-table cost. |
| Train↔dev gap large, dev↔holdout small | Overfitting on a specific source | Reweight data mix; cap per-source repeats. |
| Dev↔holdout gap large | Cluster leak across splits | Rebuild splits with stricter clustering; re-run contamination guard. |
| Numbers differ between Kaggle and Azure runs of same checkpoint | Environment drift (dtype, quantization, harness version) | Pin eval-suite SHA; pin dtype; run a same-checkpoint reproducibility eval as the harness sanity check. |
| Stage 2 model "always translates" non-translation prompts | SFT register collapse | Generalization probe; expand non-translation examples in retention slice; verify target-only loss masking. |

The matrix is consulted **before** opening a new training experiment. A run report without an attribution-matrix entry pointing at the next experiment is incomplete.

---

## 7. QLoRA falsification plan

The "quantization loss is small" prior is a **prior, not a fact**, for our specific corpus, tokenizer, and base model. The falsification plan is cheap and runs on the smoke-tier model so it can't blow the budget.

**Setup:**

- **Model:** Qwen2.5-0.5B (and Qwen2.5-1B if local memory permits).
- **Variants:**
  - QLoRA (4-bit NF4 + double-quant, bf16/fp16 compute) — the project default.
  - fp16 LoRA (no 4-bit base) — controls for quantization.
  - **Full FT** — only if hardware allows on 0.5B/1B; otherwise documented as out-of-scope and the QLoRA-vs-fp16-LoRA delta is the primary signal.
- **Rank sweep:** r ∈ {16, 32, 64, 128} on the QLoRA arm; ablates whether rank, not quantization, is the constraint.
- **Controls:** identical seed, identical data shards (tiny Hawaiian slice + matched English rehearsal), identical tokenizer SHA, identical eval harness SHA.
- **Eval:** the same metrics defined in §3 — Hawaiian held-out PPL, English PPL, ʻokina survival, kahakō retention, plus a small Stage-2-style chrF probe if the smoke runs both stages.

**Decision rule:**

- If QLoRA-vs-fp16-LoRA delta is within published ranges (~0.1–0.4 PPL, low single-digit chrF), the prior holds; spend effort on tokenizer / data / forgetting instead.
- If the delta is materially larger on Hawaiian than on English, quantization interacts with the orthography or tokenizer pathologically — re-prioritize.
- If the delta is dominated by rank, not quantization, surface that to the training-pipeline ADR.

The falsification plan is a **smoke-tier experiment**, not a 7B run. It is allowed to run before any 7B-class GPU is scheduled.

---

## 8. Run report schema

Every eval-emitting run writes a row to the run report. Incomplete rows are not promoted.

| Field | Notes |
|---|---|
| `checkpoint` | Path or ID of the evaluated checkpoint. |
| `base_model_sha` | Frozen at Stage 1 start; identical across stages within a run. |
| `tokenizer_sha` | Frozen at Stage 1 start; CI-asserted identical at Stage 2. |
| `corpus_manifest_sha` | Hash of the manifest actually loaded (Stage 1 / Stage 2 / prototype). |
| `eval_hashes_sha` | Hash of `eval_hashes.parquet` at run time. |
| `stage` | `0-smoke` \| `1-cpt` \| `merge` \| `2-sft`. |
| `train_loss` | Final or checkpoint train loss. |
| `hawaiian_ppl` | Held-out, overall + per-source-slice. |
| `english_ppl_delta` | Relative change vs base; positive = forgetting. |
| `orthography_metrics` | ʻokina survival, kahakō retention, tokens/word, byte-fallback. |
| `chrf_by_direction` | en→haw and haw→en, separately; as-is and diacritic-normalized. |
| `leakage_check` | Pass/fail + n-gram-overlap stats. |
| `hallucination_rate` | Stage 1 probe result (where run). |
| `human_eval` | Likert means + N (where run); explicitly null otherwise. |
| `slices` | Per-slice numbers per §5 (source/register, direction, length, diacritic density, OCR confidence, tokenizer-bin, split, provider). |
| `eval_suite_sha` | The eval harness version. Cross-run comparisons are only valid within the same SHA. |
| `notes` | Free text. **Required:** the attribution-matrix entry pointing at the next experiment. |

The run report is the artifact other agents read. A model checkpoint without one is not promoted to a gate decision.

---

## 9. Non-goals

- **Not a release certification process.** The release gate is separate, lives in `training-pipeline.md` §6 / §7, and adds cultural review, training-rights review, license whitelist re-application, and per-source review by a named Hawaiian-speaking reviewer. This document does not duplicate or replace any of that.
- **Not a claim of Hawaiian fluency or cultural authority.** Numbers in the run report describe model behavior on a held-out distribution; they do not certify that the model speaks ʻŌlelo Hawaiʻi correctly, respectfully, or appropriately. They especially do not certify fitness for ceremonial, official, educational, or cultural use.
- **Not a replacement for human review.** Automatic metrics — chrF, PPL, COMET, all of them — are diagnostic instruments. A Hawaiian speaker's reading of the outputs is the ground truth this pipeline triangulates toward, never away from.
- **Not a benchmarking exercise.** This eval suite exists to find the bottleneck and decide the next experiment, not to publish leaderboard numbers. No eval scores are planned for public release.

---

## 10. References

- [`training-pipeline.md`](./training-pipeline.md) — stage-level gates this eval pipeline feeds.
- [`data-pipeline.md`](./data-pipeline.md) — `eval_hashes.parquet`, cluster-aware splits, normalization invariants this eval pipeline depends on.
- [`.squad/decisions.md`](../.squad/decisions.md) — ADRs: two-stage training plan, prototype-vs-release split, base-model recommendation.
- `README.md` — project goals, non-goals, planning posture.
