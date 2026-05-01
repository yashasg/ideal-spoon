# Evaluation Pipeline

> **Status:** Prototype design for a learning project. **No public release** of weights, adapters, tokenizer, generations, eval scores, API, or demo is planned. The gates and metrics below describe what an honest internal eval loop looks like for a low-resource Hawaiian adaptation; they are not a release certification process. See the prototype-vs-release ADR in [`.squad/decisions.md`](../.squad/decisions.md).
>
> **Owner:** Rusty (NLP Researcher), with input from Basher (training) and Livingston (compute/budget) where eval cadence collides with free-tier reality.
>
> **Companion docs:**
> - [`data-pipeline.md`](./data-pipeline.md) — what goes *into* the model (ingest, normalization, manifests, contamination guards, `eval_hashes.jsonl`).
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
| **Stage 2 gate** | Full Stage 2 eval suite on candidate checkpoint | At checkpoint promotion | Go/no-go for internal prototype-candidate promotion. Defined in `training-pipeline.md` §4.4. |
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

**Stage-0 tokenizer audit gate.** Before the Llama-3.1-8B serious-run config
is allowed near real training data, a tokenizer audit must be run locally on
representative Hawaiian slices (e.g. `data/stage1/stage1.jsonl.gz` and
`data/evals/manual_w1/w1-haw-micro-eval.jsonl`).

Reports are written under ignored `data/tokenizer_audit/` and must not be
fabricated: missing Hugging Face/`transformers` dependencies or gated Llama
access are hard failures with install/login instructions. The gate reads
`overall.*` and `high_diacritic.*` for `tokens_per_word`,
`explicit_byte_fallback_rate`, and `byte_fallback_or_proxy_rate`, then records
`recommendation.decision` (`go` / `no_go`). The default no-spend thresholds are
overall tokens/word ≤2.50, high-diacritic tokens/word ≤3.25, explicit byte
fallback = 0, combined byte fallback/proxy ≤1%, and sufficient sample coverage
(≥1,500 words plus ≥10 high-diacritic samples).

Current status: there is no standalone audit script in the repo; a
tokenizer-audit test is planned. The real gated Llama-3.1-8B go/no-go remains
blocked until Hugging Face access/dependencies are available and the audit is
actually run. Do not substitute smoke-model or placeholder numbers for this
gate.

**W1 manual micro-eval (independent of FineWeb-2).** A small hand-authored Hawaiian probe set (~50–100 items) is maintained as a *separate* cheap-eval source so the orthography metrics above are not solely measured against an LID-classified web crawl. Rows become accepted eval rows only after Hawaiian-literate review; until #7 closes, local draft rows are wiring/preflight only and must not be reported as eval results. Schema, field semantics, and authoring rules live in [`data-sources/manual-eval/`](../data-sources/manual-eval/README.md); the eval-consumable artifact is the off-git **JSONL** at `data/evals/manual_w1/w1-haw-micro-eval.jsonl` (under the canonical `evals` division per `data-pipeline.md` "Dataset division taxonomy"). Stage 0 W1 input is JSONL-only per the user directive (`.squad/decisions/inbox/copilot-directive-20260430T081137Z.md`); the local TSV at `data/evals/manual_w1/w1-haw-micro-eval.tsv` is the authoring/source format, converted to JSONL via `python3 scripts/315_hash_manual_w1_eval.py --execute --jsonl-only`. Accepted rows are hashed into the eval-hashes ledger with `origin=manual_w1, stage=eval-only, division=evals, split=w1` only after acceptance. The local hash path is `scripts/315_hash_manual_w1_eval.py`, which defaults to `review_status=accepted` rows; current seeded/local rows are draft, and draft rows require `--include-draft-for-local-ledger` for contamination preflight with `eval_consumable=false` / `prototype_local=true`. W1 is **never used as training data**; only accepted rows run alongside the FineWeb-2 dev slice at the cheap-eval cadence (§4). It is sliced by `category` (`okina_survival`, `kahako_retention`, `unicode_nfc`, `tokenizer_survival`, `generation_sanity`), `diacritic_density`, and derived `diacritic_density_bin` (`none` = 0, `low` = 1–2, `medium` = 3–5, `high` ≥ 6) per §5.

**FineWeb-2 `haw_Latn` eval splits.** The official FineWeb-2 test split (887 rows) is deterministically split 70/30 by `scripts/310_split_dedupe_fineweb2_haw.py` using a seeded stable row-id/hash ordering and count-exact half-up rounding: 621 dev rows (→ `data/evals/fineweb2_haw/dev.jsonl`) and 266 holdout rows (→ `data/final/fineweb2_haw/holdout.jsonl`). All 887 rows are NFC-normalized before SHA-256 hashing and recorded in the canonical JSONL eval-hash ledger at `data/evals/eval_hashes.jsonl`; the train split is deduplicated against this hash set to enforce the invariant `train ∩ eval_hashes = ∅`. Dev is used for cheap per-checkpoint eval; holdout is protected for major-milestone gates only.

### 3.2 Language modeling (Stage 1 primary, Stage 2 monitor)

| Metric | What it catches |
|---|---|
| **Hawaiian held-out PPL** | Stage 1 progress against the un-finetuned base. Reported per source/register slice as well as overall. |
| **English PPL regression** | Forgetting. Tracked vs base; a >20% relative increase is the threshold for "rerun with more rehearsal" at Stage 1. |

Held-out splits are cluster-aware (see `data-pipeline.md`); PPL is computed only on the read-only held-out path that the loaders are forbidden from touching.

### 3.3 Translation (Stage 2)

| Metric | Notes |
|---|---|
| **chrF / chrF++ by direction** | Primary. Reported separately for en→haw and haw→en. **Never averaged.** Implemented at `code/llm_hawaii/stage2_eval.py` with CLI `scripts/410_stage2_eval.py` (issue #23): sacrebleu when available, deterministic pure-Python fallback for prototype tests. BLEU is reported alongside but not weighted — it is unreliable on morphologically rich low-resource targets. |
| **chrF as-is vs diacritic-normalized** | Dual-report. If the gap collapses under normalization, the regression is orthography handling, not translation quality. (Currently advisory; promotion to formal gate is an open team question.) |
| **COMET (if applicable)** | Only if a multilingual COMET model has demonstrable Hawaiian coverage. Otherwise the limitation is documented in the run report. |

### 3.4 Integrity and behavior probes

| Probe | What it catches |
|---|---|
| **Leakage / contamination check** | Test outputs vs training shards — bigram-overlap and exact-SHA. Build-time checks consume the canonical `data/evals/eval_hashes.jsonl`; runtime loader enforcement remains #4. Recomputed on outputs as a generation-time check. |
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
| **W1 manual category** | `okina_survival`, `kahako_retention`, `unicode_nfc`, `tokenizer_survival`, `generation_sanity` from the local W1 JSONL. Keeps eval-only tripwires attributable by failure mode. |
| **OCR confidence** | Where source-level OCR confidence is available (nūpepa pipeline). Isolates OCR noise from model behavior. |
| **Tokenizer behavior** | Items binned by tokens/word and byte-fallback rate at the input. Identifies whether quality drops correlate with fragmentation. |
| **Data split** | Train vs dev vs test vs holdout. Gap between train and dev is the overfitting signal; gap between dev and holdout is the cluster-leak signal. |
| **Provider / environment handoff** | Provider 1 vs Provider 2 vs Provider 3 runs of the same eval. Catches harness drift, dtype/quantization differences, and environment-specific silent failures. |

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
| Test chrF improbably high | Eval leakage | Recompute after n-gram strip; re-run cluster-aware split builder; verify `eval_hashes.jsonl` was consumed by the build/check guard path. |
| Hallucination rate high on real-world Hawaiian entities | Corpus gap or overfitting to register | Slice by source; check whether hallucinations cluster on contemporary topics absent from the corpus. |
| Quality drop correlates with high tokens/word slices | Tokenizer fragmentation is the bottleneck | Vocab extension experiment; consider Hawaiian-specific BPE/Unigram piece set; weigh embedding-table cost. |
| Train↔dev gap large, dev↔holdout small | Overfitting on a specific source | Reweight data mix; cap per-source repeats. |
| Dev↔holdout gap large | Cluster leak across splits | Rebuild splits with stricter clustering; re-run contamination guard. |
| Numbers differ between providers on the same checkpoint | Environment drift (dtype, quantization, harness version) | Pin eval-suite SHA; pin dtype; run a same-checkpoint reproducibility eval as the harness sanity check. |
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
| `eval_hashes_sha` | Hash of `eval_hashes.jsonl` at run time. |
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

### 8.1 Stage 0 drift bundle (`stage0_eval.v2`)

`code/llm_hawaii/evaluate.py` and `scripts/run_stage0_eval.sh` together emit a Stage-0-specific subset of §8 plus the drift fields needed to compare two checkpoints fairly without leaking raw text into git. See `code/README.md` → "Stage 0 drift signal bundle" for the full field list. Tripwire fields written to the tracked summary include `wrong_okina_nonzero`, `nfc_failures`, `combining_macron_nonzero`, `kahako_collapse_on_high_diacritic`, `generation_count`, and `prompt_suite_sha256`. Fields whose harness is not wired yet (English PPL, per-source PPL slice, and `hawaiian_ppl` when no `--eval-file` is supplied) are emitted with `status: "not_configured"` rather than omitted. The W1 manual micro-eval probe (`manual_w1`) reads the off-git **JSONL** at `data/evals/manual_w1/w1-haw-micro-eval.jsonl` (override with `--manual-w1-jsonl`; disable with `--no-manual-w1`) — Stage 0 W1 input is JSONL-only — and reports a stable status enum (`not_configured` | `missing` | `invalid` | `draft_only` | `evaluated`) plus `jsonl_sha256`, `jsonl_size_bytes`, accepted-row counts, accepted category / `diacritic_density_bin` counts, `nfc_normalized_false_count`, and — on the `evaluated` path — `accepted_item_hashes` (sorted; uses each row's `sha256_normalized` when present, else canonical `sha256(NFC(prompt) + LF + NFC(reference))`; matches `scripts/315_hash_manual_w1_eval.py`), `w1_suite_sha256` (sha256 over sorted `(item_id, sha256_normalized)` pairs of accepted rows; stable under row reorder; flips when the accepted set churns), and `schema_version_seen = "manual-w1-jsonl-v1"`. Raw prompts/references/notes/author text never enter the report. Only `review_status=accepted` rows are counted as eval-consumable; drafts/reviewed rows are flagged but never reported as benchmark results. An `accepted` row that fails NFC, carries U+0304 combining macron, or uses a wrong-ʻokina codepoint (U+2018 / U+2019 / U+0027 / U+02BC) flips the file to `status="invalid"` with `error_count` plus `first_errors` carrying only `line N: <field> <category>` text — never row contents. Drafts/reviewed rows stay loose. `scoring_status: "not_wired"` until row-level model scoring lands — until then `manual_w1` is a metadata/validation probe, not task accuracy.

**human_fetch bidirectional translation probe (`human_fetch_translation`).** A **prototype/learning checkpoint eval probe** present on *every* checkpoint eval, including the Stage 0 no-training baseline. Source: the single English + Hawaiian parallel pair from the Ulukau institutional landing page, stored as an off-git JSONL at `data/tokenizer_audit/ulukau_nupepa/human_fetch.jsonl` (regenerate with `python3 scripts/_convert_ulukau_human_fetch.py`; override with `--human-fetch-jsonl` / `HUMAN_FETCH_JSONL=...`; disable with `--no-human-fetch` / `USE_HUMAN_FETCH=0`). The probe is "safe to miss": if the JSONL is absent it emits `status="missing"` and does not block the eval or flip the exit code. On the `evaluated` path the report carries hash-only direction descriptors for `en_to_haw` and `haw_to_en`, each with `prompt_sha256`, `generation_sha256`, `reference_sha256`, and a **baseline char-bigram F1 score** (`metric = "char_ngram_f1_baseline"`, `ngram_order = 2`, fields `char_f1`, `char_precision`, `char_recall`). Greedy/deterministic decoding is used so the score is checkpoint-comparable. Directions are always kept separate (see §3.3 and §5): en→haw and haw→en are never averaged. Policy: `eval_eligible = True`, `training_eligible = False` — this pair is never training data. Raw source, reference, and generation text never enter the report or the tracked summary. Purpose: gauge zero-training (Stage 0) translation baseline and track drift across checkpoints so asymmetric direction collapse is visible from the very first eval.

 `python -m llm_hawaii.evaluate` always writes the report JSON first, then exits **2** if `manual_w1.status == "invalid"` (orthographic contract violation on accepted rows, or a malformed W1 JSONL). All other states exit 0. `scripts/run_stage0_eval.sh` still writes the tracked summary projection in the failing case (so the artifact and summary are inspectable on disk) and then propagates the non-zero exit, so a bad W1 input cannot land as a green Stage 0 run in CI / cron.

**W1 expert-validated source directive.** The trusted source for W1 expert-validated Hawaiian rows is the raw file at `data/raw/ulukau_nupepa/human_fetch.txt` (sectioned `# English` / `# Hawaiian` — use the Hawaiian section only). `scripts/_convert_ulukau_human_fetch.py` is a parser/normalizer that informs converting the raw text into NFC, single-ʻokina-codepoint form; it is *not* the source itself. The converter currently emits tokenizer-audit candidates under ignored `data/tokenizer_audit/`; populating a W1 row from `human_fetch.txt` is a manual step (paste NFC-normalized prompt+reference into the local TSV, then run `python3 scripts/315_hash_manual_w1_eval.py --execute --jsonl-only` to regenerate the JSONL the Stage 0 harness consumes). W1 artifacts derived from `human_fetch.txt` remain off-git under the `data/` ignore rule (`data-sources/manual-eval/README.md`).

**Suite-design freeze invariant.** Any future high-diacritic / high-`diacritic_density_bin` prompt appended to the Stage 0 suite must *explicitly* instruct the model to use kahakō (and ʻokina). The `kahako_collapse_on_high_diacritic` tripwire derives its meaning from "the prompt asked for kahakō and the generation produced zero" — a high-bin prompt that doesn't request kahakō makes the tripwire fire spuriously or, worse, makes a zero-kahakō completion look acceptable. The same audit is required if the diacritic-density bin thresholds in `metrics.diacritic_density_bin` are ever retuned.

---

## 9. Non-goals

- **Not a release certification process.** The release gate is separate, lives in `training-pipeline.md` §6 / §7, and adds cultural review, training-rights review, license whitelist re-application, and per-source review by a named Hawaiian-speaking reviewer. This document does not duplicate or replace any of that.
- **Not a claim of Hawaiian fluency or cultural authority.** Numbers in the run report describe model behavior on a held-out distribution; they do not certify that the model speaks ʻŌlelo Hawaiʻi correctly, respectfully, or appropriately. They especially do not certify fitness for ceremonial, official, educational, or cultural use.
- **Not a replacement for human review.** Automatic metrics — chrF, PPL, COMET, all of them — are diagnostic instruments. A Hawaiian speaker's reading of the outputs is the ground truth this pipeline triangulates toward, never away from.
- **Not a benchmarking exercise.** This eval suite exists to find the bottleneck and decide the next experiment, not to publish leaderboard numbers. No eval scores are planned for public release.

---

## 10. References

- [`training-pipeline.md`](./training-pipeline.md) — stage-level gates this eval pipeline feeds.
- [`data-pipeline.md`](./data-pipeline.md) — `eval_hashes.jsonl`, cluster-aware splits, normalization invariants this eval pipeline depends on.
- [`.squad/decisions.md`](../.squad/decisions.md) — ADRs: two-stage training plan, prototype-vs-release split, base-model recommendation.
- `README.md` — project goals, non-goals, planning posture.
