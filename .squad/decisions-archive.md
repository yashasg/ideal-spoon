# Decisions

## Decision: W1 Manual Micro-Eval TSV (User Directive 2026-04-29T10-09-47Z)

**Status:** Orchestrated 2026-04-29T10:13:35Z

### User Request (2026-04-29T10-09-47Z)

**By:** yashasg (via Copilot)

Add a W1 manual micro-eval TSV to the eval mix: hand-authored ~50–100 prompts/sentences for ʻokina/kahakō survival, Unicode/NFC, and simple generation sanity. Use an independent clean eval source to switch up checkpoint/Stage-0 evaluation beyond FineWeb-2.

### Spec & Implementation (2026-04-29)

**By:** Rusty (NLP Researcher) + Linus (Data Engineer)

**Spec locked.** ~80-item target (range 50–100), hand-authored + dual-reviewed, NFC + Unicode strict.

**Repo scaffold committed:**
- `data-sources/manual-eval/w1-haw-micro-eval.template.tsv` (header-only template)
- `data-sources/manual-eval/README.md` (schema, hard rules, integration plan)
- `docs/eval_pipeline.md` §3.1 (pointer to new eval source)
- Off-git data: `data/eval/manual_w1/w1-haw-micro-eval.tsv` (covered by `/data/` gitignore)

**Scope:**
- **Categories (target counts):** `orth_okina` 15, `orth_kahako` 15, `nfc_roundtrip` 10, `tokenizer_survival` 10, `gen_completion` 10, `gen_register` 5, `codeswitch_resist` 10, `closed_qa_trivial` 5
- **Columns:** `item_id`, `category`, `task_type`, `prompt`, `reference`, `expected_chars`, `forbidden_chars`, `notes`, `author`, `reviewed_by`, `review_date`, `license`, `is_holdout`, `train_leak_check` (SHA-256 of NFC `prompt+reference`)
- **Automatic scoring every checkpoint:** NFC integrity, ʻokina (U+02BB) presence vs. forbidden U+0027/U+2018/U+2019/U+02BC, kahakō precomposed (U+0101 etc., not base+U+0304), per-item PPL, cloze EM, tokenizer round-trip
- **Manual scoring at milestones only:** `gen_*` and `codeswitch_resist` outputs reviewed by Rusty + Hawaiian-literate reviewer
- **Holdout discipline:** ~20% frozen (`is_holdout=true`), never used for tuning; same rule as FineWeb-2 test. Touched only at Stage-1 final report + Stage-2 entry gate.

**Leakage gate:** Every item's NFC SHA-256 added to `data/eval/eval_hashes.parquet`; `301_build_stage1_dataset.py` excludes training rows matching it. No items lifted from `hawwiki`, FineWeb-2, Baibala, or nūpepa; authors paraphrase/compose.

**Hard rules:**
1. Hand-authored or rights-cleared, per-row citation in `notes`
2. No fabricated Hawaiian: `review_status=draft` until Hawaiian-literate reviewer marks `accepted`
3. NFC-normalized (`nfc_normalized=true` required); loader rejects U+2018/U+0027 in ʻokina slot or NFD kahakō
4. Never training data; all `accepted` hashes → `eval_hashes.parquet` before any other use
5. Frozen once shipped; changing rows bumps eval-suite SHA per `docs/eval_pipeline.md` §4
6. **Explicitly not a public benchmark:** hygiene tripwire, no speaker-authority claim, no HF/leaderboard upload

**Cadence:**
- Automatic slice (~55 items): **every Stage-1 checkpoint** alongside FineWeb-2 dev PPL
- Generative slice (~25 items): **milestone checkpoints only** (e.g., epoch-end, pre-merge, pre-Stage-2)
- Holdout: Stage-1 final report + Stage-2 entry gate only

**Ownership:**
- **Rusty:** authors items + codepoint table + schema JSON; coordinates 2nd-reviewer pass
- **Linus:** wires TSV loader + NFC validator into eval harness; adds hashes to `eval_hashes.parquet`; ensures `301_build_stage1_dataset.py` excludes them
- **Eval architect (Livingston/Basher):** places cadence split in harness config

### Status

| Phase | Status | Blocker |
|-------|--------|---------|
| **Spec** | ✅ Locked | None |
| **Repo scaffold** | ✅ Committed | None |
| **Row drafting** | ⏸ Unblocked off-git | Hawaiian-literate reviewer needed for `accepted` promotion |
| **Harness wiring** | ⏸ Awaiting harness code | Rusty/Livingston/Basher eval-harness scope |
| **Integration to train gate** | ⏸ Trivial when hashes ledger exists | No blocker — flows from existing contamination CI |

### Reference

- Spec detail: `.squad/decisions/inbox/rusty-manual-micro-eval.md` (merged into this entry)
- Implementation plan: `.squad/decisions/inbox/linus-manual-micro-eval.md` (merged into this entry)
- Orchestration log: `.squad/orchestration-log/2026-04-29T10:13:35Z-manual-micro-eval.md`
- Session log: `.squad/log/2026-04-29T10:13:35Z-manual-micro-eval.md`

---

## Decision: Final Dataset Taxonomy — `evals` / `stage1` / `stage2` / `final`

**Date:** 2026-04-29
**By:** Linus (Data Engineer)
**Status:** Adopted; docs-only; no code changes yet
**Related directive:** User directive 2026-04-29T10-13-58Z (canonical top-level dataset taxonomy)

### Decision

Adopt a single canonical four-division taxonomy for **final dataset artifacts** on disk and in docs, rooted at `data/`:

| Division | On-disk root | Contents | Train Policy |
|---|---|---|---|
| `evals` | `data/evals/` | Held-out / eval-only: FineWeb-2 `haw_Latn` test dev+holdout, W1 manual micro-eval, Stage-0/checkpoint/final eval anchors, `eval_hashes.parquet` (contamination ledger) | **Never train; hash-ledger gated** |
| `stage1` | `data/stage1/` | Unsupervised / base-adaptation: `stage1_manifest.parquet`, `stage1.jsonl.gz`, packed/tokenized shards | Dedupe against `evals` before ingest |
| `stage2` | `data/stage2/` | Supervised / instruction / preference / tiny task-tuning: `stage2_manifest.parquet`, `stage2.jsonl.gz`, `templates.json` (populated only when sources exist) | Dedupe against `evals` before ingest |
| `final` | `data/final/<run_id>/` | Assembled local-final manifest outputs: pointers + SHAs to stage1/stage2/evals artifacts a run consumed (not payload duplicates) | Local prototype only; private |

### Contamination Gates (Mandatory)

1. **`evals` is held out from training, period.** Every `evals`-tier row is hashed into `data/evals/eval_hashes.parquet` *before* any train ingest reads it. Stage-1/Stage-2 dataloaders CI-assert `train ∩ eval_hashes = ∅`. Cluster-aware split isolation handles near-dups; exact-hash dedup is the leakage backstop. **Never train on `evals`.**

2. **`final` is not public release.** This project is private prototype/learning work. Publication CI gate refuses any external emit of pipeline artifacts; `final` is local-only.

3. **Raw and intermediate stay outside the taxonomy.** `data/raw/` and `data/extracted/` remain inputs to `stage1`/`stage2`/`evals`; they are not divisions of the final taxonomy.

4. **Nothing under `data/` is committed to git.** Existing `/data/` `.gitignore` rule covers all four divisions; only schemas, templates, URL inventories, and docs live in-repo.

### Path Migration

The previous singular `data/eval/` path is **renamed to `data/evals/`** for taxonomy consistency. This affects:
- `data/eval/eval_hashes.parquet` → `data/evals/eval_hashes.parquet`
- `data/eval/manual_w1/...` → `data/evals/manual_w1/...`
- `data/eval/fineweb2_haw_test/{dev,holdout}/...` → `data/evals/fineweb2_haw_test/{dev,holdout}/...`

**No fetcher or builder script currently writes those paths** (eval harness not implemented, `eval_hashes.parquet` does not exist on disk), so the rename is documentation-only at this point. Future scripts and harnesses **MUST use `data/evals/`**.

### Consistency with Prior Decisions

- **FineWeb-2 `haw_Latn` test split (887 rows):** ~80/20 dev/holdout under `data/evals/fineweb2_haw_test/{dev,holdout}/`. Train deduped against full test set before Stage 1. Unchanged from locked decision.
- **W1 manual micro-eval:** Lives at `data/evals/manual_w1/w1-haw-micro-eval.tsv`, schema unchanged, `origin=manual_w1, stage=eval-only` in ledger, `accepted`-only, NFC-validated. Unchanged from prior decision.
- **Stage-1 token gates and Stage-2 sequencing:** Unchanged. Stage 2 still blocks on Stage 1 artifacts existing and `eval_hashes.parquet` being populated.

### Repo Footprint (Surgical, Docs-Only)

- `docs/data-pipeline.md` — added "Final dataset taxonomy" section; updated Storage formats table (split eval ledger row into "Evals — contamination ledger" + "Evals — held-out anchors"; added "Final — assembled run manifest" row); updated Cross-stage invariants #5 to anchor on `data/evals/`.
- `docs/eval_pipeline.md` — `data/eval/...` paths in §3.1 micro-eval paragraph updated to `data/evals/...`.
- `data-sources/manual-eval/README.md` — file-layout table and integration loader paths updated to `data/evals/...`.
- `data-sources/manual-eval/w1-haw-micro-eval.template.tsv` — comment header path updated.

No code changes, schema changes, or fetcher changes. No raw payloads added. `/data/` `.gitignore` rule already covers all four divisions.

### Out of Scope

- Updating historical decision-log entries in `.squad/decisions.md` that reference `data/eval/...` (audit trail only; this entry supersedes them).
- Formal schema for `data/final/<run_id>/manifest.json` (sketched as pointer + SHAs; will be defined when first prototype run is assembled).
- Updating `301_build_stage1_dataset.py` and future Stage-2 builder to read/write under `data/evals/` instead of `data/eval/` (follow-up; grep shows no current script writes the old path).

### Next Steps

- **Linus/Frank/Basher:** When implementing Stage-1 / Stage-2 builders and eval harness, wire paths to the new four-division taxonomy.
- **CI:** Ensure `train ∩ eval_hashes` assertion runs before Stage-1/Stage-2 training begins.
- **Final manifest:** Schema for `data/final/<run_id>/manifest.json` will be defined at first prototype run assembly.

### Reference

- User directive: `.squad/decisions/inbox/copilot-directive-2026-04-29T10-13-58Z-dataset-taxonomy.md` (merged into this entry)
- Implementation: `.squad/decisions/inbox/linus-dataset-taxonomy.md` (merged into this entry)
- Orchestration log: `.squad/orchestration-log/2026-04-29T10-18-43Z-dataset-taxonomy.md`
- Session log: `.squad/log/2026-04-29T10-18-43Z-dataset-taxonomy.md`

---

## Decision Note: FineWeb-2 `haw_Latn` 100/200 Scripts Landed

**From:** Frank (Hawaiian Data Collector)
**Date:** 2026-04-29
**Status:** Implementation in place; awaits Linus dep + rights ruling

### What landed

- `scripts/105_collect_fineweb2_haw.py` — 100-phase planner. Writes `data/local/fineweb2_haw/collect_plan.json` with dataset id (`HuggingFaceFW/fineweb-2`), config (`haw_Latn`), verified row counts (train **95,507** / test **887**), parquet URLs, datasets-server rows-API URL templates, per-row schema, license tag (`odc-by`), and known caveats (English boilerplate inside Hawaiian-LID rows, per-URL third-party rights). No corpus text fetched.
- `scripts/205_fetch_fineweb2_haw_raw.py` — 200-phase fetcher. Dry-run by default; `--execute --split {train,test} --limit N` to fetch. Default path is HF datasets-server `/rows` (stdlib only, polite paginated). Optional `--use-parquet` uses `pyarrow` and fails loudly if dep absent. Writes per-row JSONL under `data/raw/fineweb2_haw/<YYYYMMDD>/<split>.jsonl` and `ProvenanceRecord` ledger. Schema-validated; raw whitespace token counts from fetched text only.
- `docs/data-pipeline.md` updated: 105/205 documented; FineWeb-2 noted as primary verified web source for Stage 1.
- **Verified live:** `--execute --split test --limit 2` returned 2 real rows, 1,028 raw whitespace tokens from staradvertiser.com editorial pages — confirms per-URL rights caveat is real, not theoretical.

### Open questions for Linus

1. **Dependency call:** Add `pyarrow` / `huggingface_hub` to `requirements.txt` or stay stdlib-only via rows API? Scripts default to rows API; parquet is opt-in. Bulk pull of all 95,507 train rows via rows API is workable (~955 paginated calls @ length=100).
2. **Per-URL rights posture:** Accept rows wholesale at prototype scope, or enforce per-URL allow/deny list downstream? 205 preserves per-row `url` for either policy.

### Open question for Rusty

- Tokenizer-fragmentation sanity check on FineWeb-2 sample once bulk pull authorized; LID/quality threshold for Stage-1 inclusion given boilerplate mix.

### Status

✅ Scripts ready for integration. Awaiting Linus (dependency + rights ruling) and Rusty (tokenizer feedback) before Stage 2 planning.

---

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


---

## Merged Decision: Stage-0 Evaluation Data Source Candidates

**Authors:** Rusty (NLP Researcher), Frank (Hawaiian Data Collector)
**Date:** 2026-04-29
**Status:** Accepted — W1 (first wave) sources approved; W2 sources queued; Linus decisions pending
**Scribe orchestration:** orchestration-log/2026-04-29T09-54-52Z-stage0-eval-sources.md

### Scope

Stage-0 = tiny sanity-check / smoke-test eval slices for prototype loops. Not for public benchmark claims; not for Stage-2 dev/test anchoring (separate decision). Goal: which sources can we *actually fetch or manually seed* today, end-to-end, with no Cloudflare bypass and no rights gamble.

### Ground Rules (Reaffirmed)

- **No Cloudflare/access-control bypass:** Nupepa CGI, Papakilo, HathiTrust, Chronicling America Hawaiian batches all deferred.
- **No FLORES Hawaiian:** FLORES-200 and FLORES-Plus do **not** include Hawaiian. Explicitly flagged in `docs/data-pipeline.md` Stage-2 §300; do not assume `hawn_Latn` FLORES config exists.
- **`hwc` is not Hawaiian:** ISO `hwc` = Hawaiian Pidgin / Hawaiʻi Creole English (English-lexified creole). Real Hawaiian ISO is `haw` / `haw_Latn`.
- **No new scripts in this memo:** FineWeb-2 adapters already landed (105/205). Stage-0 reuses existing fetch paths or hand-seeded files.
- **Stage-0 ≠ training:** Anything seeded as Stage-0 eval hashes into `data/eval/eval_hashes.parquet` *before* any training adapter touches it (contamination rule).

### Recommended Stage-0 First Wave (W1 — Zero Blockers)

| # | Source | Access | Notes |
|---|---|---|---|
| 1 | **FineWeb-2 `haw_Latn` test split** (887 rows) | HF datasets-server `/rows` API or parquet. Already wired via `205_fetch_fineweb2_haw_raw.py --split test`. Verified live. | Web-text sanity slice. Expect English boilerplate inside Hawaiian-LID rows (feature for Stage 0, lets us measure paragraph-level LID). ODC-By wrapper; per-URL rights vary. Eval-only internal use OK. |
| 2 | **Hawaiian Wikipedia held-out slice** (50–100 random page IDs from `hawwiki` dump already pulled) | Trivial — no new fetch. Deterministic hold-out from existing extracted artefact. Must hash into `eval_hashes.parquet` before Stage-1 ingest re-runs. | Wikipedia contemporary-ish encyclopedic register. CC BY-SA 4.0 + GFDL. Memorization risk (globally available, base may have seen it) — useful as floor sanity check, not generalization claim. |
| 3 | **eBible `haw1868` + KJV anchor** (Baibala Hemolele 1868) | One-zip GET from eBible + `eng-kjv2006_usfm.zip` for verse alignment. Public, stable URL. PD. | Verse-aligned bilingual probe. Religious-domain overfit baseline ("is the model collapsing into Bible register?"). Edition pin required (Linus decision pending). |
| 4 | **`global-piqa-parallel` → `parallel_haw_latn.tsv`** (HF) | `huggingface_hub.hf_hub_download` or raw `resolve/main/...tsv` GET. Small commonsense QA pairs. Trivial fetch. | Commonsense parallel eval anchor (doesn't rely on FLORES). Eval-only by design. Hash into `eval_hashes.parquet` first. License verification pending (Frank action). |
| 5 | **Manual-seed micro eval set** (10–50 hand-written `en↔haw` sentence pairs, openly licensed sources) | Hand-curated TSV in `data/eval/manual_seed/` with per-row source URL + licence column. No fetcher. Zero blockers; fluent-reviewer gate pending (Linus decision). | Tokenizer / orthography survival. Register diversity (newspaper / Bible / wiki / dictionary). Minimum row count + register split TBD (Rusty action). Fastest unblock for "does the model output Hawaiian at all" smoke test. |

**This W1 bundle gives us:**
- Orthography survival numbers (sources 1, 2, 3, 5 via varied diacritic density).
- Language-ID + paragraph-level LID re-gate sanity (sources 1, 2).
- Translation sanity floor (sources 3, 4).
- Religious-domain overfit signal (source 3, comparison vs. 1, 2).
- Lexical / morphological probe (manual seed from source 5).
- Plumbing: does the eval harness load, normalize, produce a number?

**All small enough to evaluate in <30 min on single GPU.** Enough to drive "does this prototype generate Hawaiian at all, and does it align verses correctly" smoke loop.

### W2 (Second Wave — After W1 Lands)

- **BibleNLP corpus `haw`:** verse-aligned cross-check vs. eBible (edition mismatch expected; dedup-by-verse, not string).
- **Weblate Translations `en-haw.tsv`:** software-l10n strings (domain-shift smoke test, tag `register=software-l10n`).
- **Taxi1500 Hawaiian:** Bible-derived topic classification diagnostic *only* (verify row count before promotion).
- **Tatoeba `haw`↔`eng`:** translation sanity. **Live row count unverified** — confirm before use; small enough that careless use makes eval memorisable. Hold out aggressively; n-gram overlap audit. CC BY 2.0 FR.
- **Internet Archive PD slice:** OCR noise is blocker for eval; better as register-diversity training comparator.
- **Hawaiian Corpus Project derived artefacts:** status unknown; no fetch until source URL + licence pinned.
- **`hawwikisource` literary slice:** weak Stage-0 fit (small, mostly Bible/historical reprints already covered by eBible/IA); use as training register, not Stage-0 eval slice.
- **`hawwiktionary` headword + example slice:** lexical coverage, morphology probe. `103_collect_hawwiktionary.py` exists. CC BY-SA 4.0. Headword-only entries **not** translation pairs. (Rusty flags "use now"; Frank defers to W2; collect on W1 if dump available.)

### Avoid (Do Not Pursue for Stage-0)

- **FLORES / FLORES+ / FLORES-200 Hawaiian:** **Does not exist.** Explicitly absent from all FLORES variants checked.
- **`hwc` (Hawaiian Pidgin / Creole English):** False friend; English-lexified creole, not Hawaiian.
- **Nupepa CGI (`gsdl2.7/cgi-bin/nupepa`):** Cloudflare-blocked; bypass policy-prohibited.
- **Ulukau automated fetch:** Cloudflare / Greenstone risk; per-collection manual probing OK, automated bulk fetch not.
- **Mozilla Common Voice `haw`:** Hawaiian is **not** a Common Voice locale (API returns `{"message":"no user"}`).
- **CC-100 `haw`:** Not in CC-100 manifest; FineWeb-2 supersedes.
- **JW300:** ToS-blocked (per `docs/data-pipeline.md`).

### Open Questions Routed to Team

1. **Linus (Hawaiian Data Licensing Lead):**
   - FineWeb-2 W1 eval-only use: accept wrapper ODC-By posture without per-URL allow-list, or resolve per-URL rights first? (Stage-1 training side separately blocked; W1 eval-only is narrower question.)
   - Baibala edition pin for Stage-0 held-out verse sample (Hemolele 1868 vs. modern) + matched English PD edition (KJV vs. ASV).
   - Gate on Hawaiian-reader review before any quoted Stage-0 diagnostic number, or acceptable as-is?
   - Confirm `docs/data-pipeline.md` Stage-2 §300 gets "FLORES has no Hawaiian" fix before Stage-0 eval-hash work starts.

2. **Rusty (NLP Researcher):**
   - Manual-seed micro eval minimum row count + register split (newspaper / Bible / wiki / dictionary) before treating as real signal vs. smoke test?
   - Tatoeba row-count confirmation (needs to be small enough to hold out aggressively without memorization risk).
   - Paragraph-level LID re-gate timing: evaluate at Stage 0 on FineWeb-2 test split, or defer to Stage 1? (Rusty leans Stage 0 — cheap diagnostic, load-bearing for any Stage-1 cleanup claim.)

3. **Frank (Hawaiian Data Collector):**
   - Verify `global-piqa-parallel` Hawaiian row count + license before Stage-0 load.
   - Verify Tatoeba Hawaiian row count (via direct download from Tatoeba export endpoints).
   - Confirm NLLB-Seed actually carries `haw_Latn`; confirm UDHR Hawaiian translation availability + license; confirm Taxi1500 Hawaiian slice presence (before promoting items 7–10 from "verify next" to "use now").

4. **Coordinator / Danny (Lead):**
   - Route paragraph-level LID re-gate design decision to Livingston (eval architect) or Danny, if not resolving to Rusty Stage-0 proposal.

### What We Are *Not* Claiming with Stage-0 Data

- No headline chrF / BLEU / COMET number.
- No "the model is fluent in Hawaiian" claim.
- No generalization claim from `hawwiki` (memorization risk).
- No benchmark comparison to other Hawaiian models (no benchmark-grade sources; FLORES has no Hawaiian).
- No row counts beyond `docs/data-pipeline.md` assertions (FineWeb-2 train 95,507 / test 887). Everything else "size not asserted".

### Deliberate Scope Limits

- Did **not** fetch new data (existing live verifications reused from prior history).
- Did **not** write or modify scripts (source-shortlist memo only).
- Did **not** add to `data-sources/hawaiian-data-sources.json` (routing config; Stage-0 eval-only entries belong in `data/eval/eval_hashes.parquet` + per-source manifest).
- Did **not** propose probing Nupepa / Ulukau / HathiTrust / Papakilo / Chronicling America further from this environment.

### Cross-References

- `docs/data-pipeline.md` — Stage 1 / Stage 2 source tiers, FineWeb-2 row counts, FLORES-absent note, eval-hash discipline, manifest schema.
- `docs/eval_pipeline.md` — eval cadence, slicing axes, metrics, 30–60 min fixed eval budget.
- `.squad/decisions.md` § "Language Config Normalization Advisory" — `haw_Latn` manifest handling, false-positive filter risks.

### Integration Checkpoint

✅ **W1 sources approved for harness integration.** Linus rights + review-gate decisions unblock quoted diagnostics. Rusty row-count decisions unblock manual-seed trust. Coordinator routes paragraph-level LID decision. Stage-0 eval harness ready to load W1 bundle once decisions resolve.

---

## FineWeb-2 Test Split: Checkpoint Eval Reuse (2026-04-29T09:59:05Z)

**Question:** Can FineWeb-2 `haw_Latn` test split (887 rows) be reused for checkpoint evals (PPL, fluency metrics) during Stage 1 DAPT training?

**Answer:** Yes, **with hard constraints.**

**Decision:**
- ✅ FineWeb-2 test (887 rows) is safe for **checkpoint monitoring/dev signal** during Stage 1 (not a final benchmark)
- ✅ **Dedupe requirement:** Remove any FineWeb-2 train-set rows (95,507 total) that overlap with test rows via exact hash match on ingest. FineWeb train and test come from the same source pool; without train-test dedupe, the checkpoint signal measures memorization, not generalization.
- ✅ **Frozen split:** Deterministically split 887 test rows (fixed seed, stratified if possible) into:
  - **~80% (≈710 rows) = Checkpoint dev:** use for perplexity, orthography, fluency metrics *during* training
  - **~20% (≈177 rows) = Final holdout:** never use for any hyperparameter tuning, learning-rate decisions, or model selection
- ✅ **Stage-0 diversity:** Pair FineWeb-2 checkpoint monitoring with independent Stage-0 sources (FLORES `haw_Latn` if available, UDHR, Taxi1500). Single-source checkpoint signals can mask generalization failures.

**Implementation:**
- Before Stage 1 harness start: Load FineWeb-2 full test set (887), dedupe against train hashes, split into dev + holdout with fixed seed. Record which rows appear in each split for reproducibility.
- During Stage 1 training: Checkpoint probes only touch dev rows. Never use holdout rows for any decision.
- Stage 1 final report: Report dev-set metrics with explicit caveat ("checkpoint monitoring only, not final benchmark"). Report holdout-set metrics separately, unreleased during training.
- Stage 2 onward: Holdout rows remain frozen; do not include in Stage-2 dev sets unless explicitly re-approved in a separate ADR.

**Rationale:**
- **Checkpoint evals are not benchmarks:** They measure training diagnostics (learning curves, metric stability). Implicit hyperparameter leakage risk is managed by the frozen holdout split.
- **Dedupe is critical:** Train-test contamination inflates checkpoint signals; mechanical hash filtering is the solution.
- **Frozen split prevents taint:** Once dev rows are used for *any* decision (learning rate, early stopping, model selection), they bias all downstream estimates. Final holdout isolation is non-negotiable.
- **Diversity prevents overfitting:** FineWeb-2 alone exhibits CCNet filtering + language-model biased-crawl artifacts. Checkpoint monitoring on FineWeb alone can hide generalization failures on other data distributions.

**Next Steps:**
- **Linus (Data Engineer):** Implement dedupe + frozen-split logic in Stage-0 harness. Coordinate with Livingston or Basher for eval harness integration.
- **Rusty (NLP Researcher):** Confirm checkpoint dev signal does not drive Stage 1 stopping decisions (holdout remains frozen).
- **Basher/Livingston (Eval Architect):** Ensure eval harness tracks FineWeb-2 split membership; never leak holdout rows into training loop.

**Reference:**
- Orchestration log: `.squad/orchestration-log/2026-04-29T09-59-05Z-fineweb2-checkpoint-eval.md`
- Session log: `.squad/log/2026-04-29T09-59-05Z-fineweb2-checkpoint-reuse-question.md`
- Rusty history: `.squad/agents/rusty/history.md` (2026-04-29T09:59:05Z entry)
- Linus history: `.squad/agents/linus/history.md` (2026-04-29T09:59:05Z entry)


## 2026-04-29T10-07-46Z: User Directive — FineWeb-2 Eval Split & Dedupe

**From:** yashasg (via Copilot)
**Logged by:** Scribe (2026-04-29T10-08-17Z)

**Directive:**
Once Frank completes the FineWeb-2 raw pull, implement the following in Linus data engineering:

1. **Split FineWeb-2 `haw_Latn` test split (887 rows) into dev and holdout**
   - ~710 rows (80%) for checkpoint dev monitoring during Stage 1
   - ~177 rows (20%) frozen holdout for final eval
   - Use fixed seed for reproducibility

2. **Dedupe FineWeb-2 train (95,507 rows) against full test split (887 rows)**
   - Exact hash match on ingest
   - Prevents train-test leakage before Stage 1 DAPT training

**Rationale:** Ensure clean train-test boundary, enable non-contaminated checkpoint signaling during tuning.

**Status:** Blocked on Frank's raw FineWeb-2 fetch completion.

**Implementation Owner:** Linus (Data Engineering)

**Reference:** Orchestration log `2026-04-29T10-08-17Z-fineweb2-eval-split-directive.md`, session log `2026-04-29T10-08-17Z-fineweb2-eval-split-directive.md`.

---

## 2026-04-29T10-19-35Z: User Directive — Dataset Division Taxonomy

**By:** yashasg (via Copilot)
**Logged by:** Scribe (2026-04-29T10-29-52Z)

**What:** Clarification to dataset division taxonomy: `final` dataset division means **major-milestone holdout evaluation data**, not assembled run manifests or release buckets.

**Why:** User correction — align dataset divisions so `final` is holdout-eval focused and separate from training, distinct from `evals` (cheap, frequent) by access cadence (milestone-only vs. checkpoint-every-save).

**Reference:** `.squad/log/2026-04-29T10-29-52Z-code-taxonomy-framework.md` (session log)

---

## 2026-04-29T10-21-16Z: User Directive — Create Code Scaffold

**By:** yashasg (via Copilot)
**Logged by:** Scribe (2026-04-29T10-29-52Z)

**What:** Create root-level code folder to house training/eval code. The model choice is already decided, but the training stack / framework is **not yet decided** — options remain PyTorch, TensorFlow, Karpathy-style/minimal, or other approaches. Do not prematurely lock the project code/docs to one framework.

**Why:** User request — need a stable home for forthcoming prototype code while keeping the framework choice open.

**Resolution:** See "2026-04-29: Basher Code Scaffold Lands (Framework Undecided)" below.

**Reference:** `.squad/log/2026-04-29T10-29-52Z-code-taxonomy-framework.md` (session log)

---

## 2026-04-29T10-25-59Z: User Directive — Code Folder Naming

**By:** yashasg (via Copilot)
**Logged by:** Scribe (2026-04-29T10-29-52Z)

**What:** The root code scaffold is named `code/`, not `@code/`. Treat `code/` as the canonical project code folder going forward. Prior notes referring to `@code/` are superseded.

**Why:** User correction — captures naming clarification before scaffold is finalized and referenced downstream.

**Reference:** `.squad/log/2026-04-29T10-29-52Z-code-taxonomy-framework.md` (session log)

---

## 2026-04-29: Basher Code Scaffold Lands — Framework Undecided

**By:** Basher (Training Engineer)
**Logged by:** Scribe (2026-04-29T10-29-52Z)
**Status:** Accepted; repo scaffold committed

### Outcome

- Created root-level `code/` directory with `.gitkeep` to ensure git tracks it.
- Updated `README.md` §"Repository Layout" to list `code/` as where prototype training/eval code will land.
- Explicitly noted in README that the training framework (PyTorch / TensorFlow / Karpathy-style / other) is **not yet chosen**.
- No framework-specific files, requirements pins, configs, or stubs added. No edits to `requirements.txt`.

### Why

Per user directives (2026-04-29T10-21-16Z and 2026-04-29T10-25-59Z), the model is decided but the training stack is open. Need a stable home for forthcoming code without prematurely locking the framework.

### Implications for the Team

- Anyone landing first training/eval code should drop it under `code/` and, in the same PR, propose the framework decision in `.squad/decisions.md` (ADR format) **before importing a framework**.
- Until that ADR lands: **no framework imports**, **no `requirements.txt` pins**, **no vendored reference implementations**.
- The framework ADR is a gate; implementation starts after it's approved.

### Reference

- Orchestration log: `.squad/orchestration-log/2026-04-29T10-29-52Z-scribe.md`
- Session log: `.squad/log/2026-04-29T10-29-52Z-code-taxonomy-framework.md`

---

## 2026-04-29: Dataset Division Taxonomy Corrected — `final` is Milestone Holdout, Not Run Manifests

**By:** Linus (Data Engineer)
**Logged by:** Scribe (2026-04-29T10-29-52Z)
**Status:** Adopted; docs-only; no code changes yet
**Related directive:** User directive 2026-04-29T10-19-35Z (dataset division semantics correction)

### Context

The prior "Final Dataset Taxonomy" ADR (earlier in this document) locked `final` as `data/final/<run_id>/` for **assembled run manifests** — pointers/SHAs to stage1, stage2, and eval artifacts. That framing treated `final` as a **release / run-output bucket**.

The user has clarified: **"by final i meant the holdout/major milestone eval data"**. The prior interpretation was wrong.

### Correction

The four canonical dataset divisions remain `evals`, `stage1`, `stage2`, `final`. Their updated semantics are:

| Division | Role | Cadence | Training Policy |
|---|---|---|---|
| `evals` | **Cheap, frequent eval data.** FineWeb-2 dev split, W1 manual micro-eval, Stage-0/per-checkpoint sanity anchors. Plus `eval_hashes.parquet` ledger. | Every checkpoint save. | **Never train; hash-ledger gated.** |
| `stage1` | Monolingual Hawaiian CPT corpus. | Training only. | Dedupe against `evals` before ingest. |
| `stage2` | Bidirectional en↔haw SFT pairs + retention slice. | Training only. | Dedupe against `evals` before ingest. |
| `final` | **Major-milestone holdout eval data.** FineWeb-2 `haw_Latn` test holdout split, milestone anchors (`global-piqa-parallel`, held-out Tatoeba), and any future milestone probe sets. | Stage gates, candidate-checkpoint promotion, end-of-run eval — **not on every checkpoint.** | **Never train; held-out.** |

**Key distinction:** `final` is **not** a release, shipping, or run-manifest bucket. There is no `data/final/<run_id>/manifest.json` under this taxonomy. The "assembled run manifest" concept is **withdrawn**; if a run-pointer artifact is needed later, it will live elsewhere (likely under `training/` or `runs/`) and will not reuse the `final` name.

### Path Convention

Held-out anchors live as sibling directories under each division root. Picked flat siblings (`data/evals/...`, `data/final/...`) over nested (`data/evals/final/...`) so the access-discipline distinction is visible in the path and the four divisions stay symmetric:

- `data/evals/fineweb2_haw_test/dev/` (checkpoint evals, every save)
- `data/evals/manual_w1/w1-haw-micro-eval.tsv` (cheap sanity)
- `data/evals/eval_hashes.parquet` *(canonical ledger; covers both divisions)*
- `data/final/fineweb2_haw_holdout/` (milestone holdout, frozen)
- `data/final/global_piqa_parallel/` (milestone anchor)
- `data/final/<other-milestone-anchor>/` (future probes)

### Invariants Preserved

- `train ∩ eval_hashes = ∅` (unchanged). The single ledger at `data/evals/eval_hashes.parquet` covers both `evals` and `final`; rows are tagged with a new `division` column (`evals` | `final`).
- `evals` ∪ `final` = the held-out boundary. Both are off-limits to training. The distinction is **access cadence** (checkpoint-every-save vs. milestone-only), not contamination scope.
- Prototype posture unchanged: nothing under `data/` is shared externally; publication CI gate refuses external emit regardless of division.

### Files Changed (Docs-Only)

- `docs/data-pipeline.md` — renamed section "Final dataset taxonomy" → "Dataset division taxonomy"; rewrote the `final` row semantics; updated posture reminders; replaced the "Final — assembled run manifest" storage-formats row with "Final — major-milestone holdout anchors"; split cheap-anchors row from milestone-anchors row; updated contamination invariant #5 to span both `data/evals/` and `data/final/`; added `division` column to the eval-hashes ledger schema.
- `docs/eval_pipeline.md` — section-name reference fix; added `division=evals` tag to W1 manual micro-eval ledger entry.
- `data-sources/manual-eval/README.md` — section-name reference fix; clarified that the W1 micro-eval lives under `evals` (cheap) and the ledger covers both `evals` and `final`.

### Out of Scope (Intentional)

- Rewriting the prior ADR text in `.squad/decisions.md` (audit trail). This proposal supersedes it; once accepted, the ADR will be amended in a follow-up entry.
- Defining a schema for run-pointer artifacts (no current home). That artifact has no current home; decide separately if/when needed.
- Updating code paths — none exist yet that write to `data/final/`.

### Open Question

- Whether the FineWeb-2 `haw_Latn` test holdout slice (~177 rows) should be physically moved from `data/evals/fineweb2_haw_test/holdout/` to `data/final/fineweb2_haw_holdout/`. The docs now describe the milestone slice as living under `data/final/`. No script writes either path yet, so this is a docs-vs-future-script alignment question, not a migration. Flagged for Frank when the ingest script lands.

### Reference

- User directive: `.squad/decisions/inbox/copilot-directive-2026-04-29T10-19-35Z-final-means-holdout-eval.md` (merged)
- Proposal detail: `.squad/decisions/inbox/linus-final-holdout-taxonomy.md` (merged)
- Orchestration log: `.squad/orchestration-log/2026-04-29T10-29-52Z-scribe.md`
- Session log: `.squad/log/2026-04-29T10-29-52Z-code-taxonomy-framework.md`

---

## Decision: PyTorch + Hugging Face for the Learning Skeleton under `code/`

**Date:** 2026-04-29
**By:** Basher (Training Engineer)
**Status:** Adopted (learning-scope; production framework choice remains open)
**User directives:** 2026-04-29T10-33-57Z (learning skeleton preference)

### What

Per user directive, created a beginner-friendly skeleton under `code/llm_hawaii/` for first-time LLM trainer implementation:
- Module templates: `config.py`, `data.py`, `model.py`, `train.py`, `evaluate.py`, `metrics.py`
- `code/configs/smoke.json` — tiny smoke-run config with placeholder paths
- `code/examples/train.jsonl.example` — schema only, no fabricated Hawaiian data
- `code/README.md` — learning guide with suggested implementation order
- Stack: PyTorch + Hugging Face (`transformers`, `peft`, `bitsandbytes`, `trl`, `accelerate`, `datasets`)

### Why This Stack

- Lowest-friction path to working QLoRA at budget tier
- Matches two-stage ADR (Stage 1 CPT → fp16 merge → Stage 2 SFT) without forcing learner to assemble primitives
- Lets user experience `Trainer`, `peft.LoraConfig`, 4-bit loading as separate concepts before building custom logic

### Constraints Respected

- **No heavy ML bloat in root `requirements.txt`.** ML deps install into separate venv; skeleton modules lazy-import all packages with clear `RuntimeError` + install hints if missing
- **No fabricated Hawaiian content.** Templates only; `examples/train.jsonl.example` contains `<PLACEHOLDER>` strings
- **Skeleton is bare-Python.** `python3 -m py_compile` passes without external deps
- **Existing work untouched.** Additions only; README "Repository Layout" updated to reflect `code/` no longer empty

### What This Is NOT

- Not a production framework commitment. Framework-pinning ADR with version locks, container hashes, reproducibility guarantees required before cloud GPU spend
- Not a green light to train. Data foundation (manifest, license whitelist, contamination guard) remains gating prerequisite per two-stage ADR
- Not an eval surface. Numbers from `evaluate.py` are pipeline smoke, not run-report rows

### Follow-ups (Basher)

- Tokenizer audit harness on candidate bases (gates 7B/8B selection)
- Proper run-report writer matching `docs/eval_pipeline.md` §8 once learner fills in `train.py` / `evaluate.py`
- Framework + version pinning ADR before cloud GPU spend

### Cross-Team Notes

- **Linus:** `data.py` has TODO for contamination guard against `data/eval/eval_hashes.parquet`; no training data loaded yet
- **Rusty:** Smoke config defaults to Qwen2.5-0.5B per recommendation; 7B/8B slot remains gated on tokenizer audit
- **Coordinator:** Learning-scope review route to different agent per charter rules

### Reference

- Proposal: `.squad/decisions/inbox/basher-learning-skeleton-code.md` (merged)
- Orchestration log: `.squad/orchestration-log/2026-04-29T10-46-19Z-basher-llm-skeleton.md`
- Session log: `.squad/log/2026-04-29T10-46-19Z-llm-learning-skeleton.md`

---

## Decision: Llama-3.1-8B + A100 as Config, Not Python Constants

**Date:** 2026-04-29
**By:** Basher (Training Engineer)
**Status:** Adopted (prototype-scope)
**User directives:** 2026-04-29T10-36-37Z (Llama-3.1-8B + A100 defaults), 2026-04-29T10-46-04Z (A100 40GB acceptable for QLoRA)

### What

Per user directives, encoded Llama-3.1-8B as prototype default model and A100 as target serious-training GPU as **config + docs**, not Python constants:
- New file: `code/configs/llama31_8b_a100.json`
  - `base_model: "meta-llama/Llama-3.1-8B"`
  - `use_qlora: true`, `bf16: true`, `gradient_checkpointing: true`
  - `max_seq_len: 2048`, `gradient_accumulation_steps: 16`
  - `hardware_profile: "a100-40gb-single"` (metadata for run reports)
  - `run_name: "llama31-8b-a100-prototype"`
  - Placeholder data paths; will be replaced by gated Hawaiian manifest
- `TrainConfig` dataclass extended with optional fields:
  - `run_name: Optional[str] = None` — informational hint for run reports
  - `hardware_profile: Optional[str] = None` — GPU metadata, non-enforcing
- `model.py` utility: `check_runtime_capability(...)` — returns CUDA info, device name, compute capability, generic bf16_supported signal (sm_80+)
  - **Non-fatal;** does not assert "must be A100"
- Documentation in `code/README.md` explains smoke-vs-serious config split; GPU target lives in config
- `configs/smoke.json` default path unchanged (Qwen2.5-0.5B)

### Why Config, Not Code

- Keeps code skeleton learning-honest; no hardcoded "if A100 else error"
- Swap prototype defaults (model, GPU tier) via JSON without Python patches
- Permits debug runs on non-A100 hardware; avoids false assertions on H100/L40S/multi-GPU/small-batch scenarios

### What This Is NOT

- Not a Llama-3.1-8B product commitment. License terms, tokenizer audit, contamination check, framework-pinning ADR required first
- Not a green light to train on real Hawaiian corpus. Placeholder paths only; manifest must replace them
- Not a deprecation of smoke tier. Qwen2.5-0.5B default untouched; unconfigured run stays smoke-tier

### GPU Target Rationale

A100 40GB is acceptable reference target because:
- Prototype uses QLoRA, not full fine-tune (8B model + 4-bit quantization fits comfortably in 40GB)
- A100 80GB not required for this path
- H100/L40S viable alternatives; config makes swap trivial

### Cross-Team Notes

- **Rusty:** 8B slot now wired in config; tokenizer audit on `meta-llama/Llama-3.1-8B` against Hawaiian text remains gate before real run
- **Linus:** Placeholder paths only; no data manifest referenced
- **Coordinator:** No Python defaults promoted to Llama/A100; directive honored at config layer

### Reference

- Proposal: `.squad/decisions/inbox/basher-llama31-a100-config-not-code.md` (merged)
- Orchestration log: `.squad/orchestration-log/2026-04-29T10-46-19Z-basher-llama-a100-config.md`
- Session log: `.squad/log/2026-04-29T10-46-19Z-llm-learning-skeleton.md`

---

## User Directives Consolidated

**Date:** 2026-04-29
**By:** yashasg (via Copilot)
**Status:** Merged into main decisions

Three user directives, collected 2026-04-29 10:33–10:46 UTC, guided Basher's skeleton and config work:

1. **2026-04-29T10-33-57Z:** For first LLM training code, prefer beginner-friendly skeleton code that the user can implement and learn from, rather than a fully abstracted production pipeline
2. **2026-04-29T10-36-37Z:** The prototype default model is Llama-3.1-8B, and target serious-training GPU is A100; treat these as selected defaults unless superseded
3. **2026-04-29T10-46-04Z:** A single A100 40GB is acceptable as serious-run reference target because prototype uses QLoRA; A100 80GB not required

**Outcome:** Both Basher decisions (learning skeleton, config-driven defaults) now reflect user intent. No conflicting directives remain in inbox.

---

## Vendor Observation: Lightning AI Free Plan (2026-04-29T10-49-36Z)

**Date:** 2026-04-29
**By:** yashasg (via Copilot)
**Status:** Vendor observation, not a commitment
**Relevance:** Provider landscape for prototype GPU training

### Observation

User shared Lightning AI Free plan pricing table:

| GPU | Session Limit | Credits | Cost Model |
|-----|---|---|---|
| **T4/L4/L40S** | **Unlimited** | 15/mo free | Pay-as-you-go for overage |
| **A100/H100/H200** | 4 hours | 15/mo free | Pay-as-you-go for overage |

Free credits estimated at ~80 T4-hr or ~20–22 A100-hr equivalent per Livingston's prior research.

### Cross-Agent Notes

**Basher:** L40S 48GB is viable for Llama-3.1-8B QLoRA if available. Monitor:
- `bf16` + Flash Attention 2 support on L40S (vendor claims supported; verify in practice)
- CUDA kernel compatibility with `bitsandbytes` (known friction on newer GPUs)
- Throughput vs A100/H100 (L40S tensor core tuning lags high-end; expect ~60–75% of A100 FP8 peak for matrix ops)
- Keep A100 40GB as reference; consider L40S profile for provider configs if cost-benefits materialize

**Livingston:** Unlimited session ≠ unlimited credit. Verify before adoption:
- Credit burn rate at typical batch size for L40S (15/mo at current price → likely 4–8 training hours before paid overage kicks in)
- Idle timeout / background execution limits on free tier (common friction on Colab/Modal-style platforms)
- Storage allocation and egress policy for HF Hub sync (if applicable)
- Exact SKU confirmation (L40S 48GB, not L40 24GB or downgrade variant)
- Preemption/interruption risk on free tier (rare but affects reproducibility)

### Status

No immediate action. Candidate for next provider-fit pass if Basher + Livingston confirm cost-effectiveness. Current recommendation remains: **Kaggle for iteration, RunPod/Lambda A100 spot for final runs**. Lightning L40S is practical mid-tier option if details pan out.

### Reference

- Observation inbox: `.squad/decisions/inbox/copilot-observation-2026-04-29T10-49-36Z-lightning-l40-unlimited.md` (merged into this entry)

---

## Stage 2 Parallel Pipeline: Frank, Linus, Rusty, Basher Integration (2026-04-29T10-13–12-26Z)

**Date:** 2026-04-29
**Status:** Batch landed; integration review passed; ready for Coordinator decision log

### Summary

Five-agent parallel batch on Stage 2 pipeline issues #10–#14 executed without blocking dependencies. All agents completed; integration review (Danny) verified cross-agent schema consistency. Batch ready for orchestration log + decision consolidation.

### Decision: Frank — Stage 2 Source Inventory (Issue #10)

**Author:** Frank (Hawaiian Data Collector)
**Status:** Artifact landed; no fetches; awaits Linus rulings on edition pinning + mined-data rights

**What landed:**
- `data-sources/stage2-parallel-fetch-plan.json` — per-source fetch-plan layer for Stage-2 parallel and comparable Hawaiian-English candidates
- 13 sources with `alignment_type` tags matching `docs/data-pipeline.md`; 5 excluded entries
- Doc pointer under `docs/data-pipeline.md` §"Stage 2 source tiers"

**Design principle:**
Fetch-plan is distinct from routing config (`hawaiian-data-sources.json`). Routing carries adapter/bucket info; fetch-plan carries per-source acquisition steps, alignment type, dry-run default, rights-status verification, expected shape — concerns that don't belong in routing.

**Open questions for the team:**

1. **Linus (data policy):** Pin Hawaiian Bible edition + English PD edition; unblocks largest Stage-2 parallel pool
2. **Linus:** NLLB-mined haw↔eng rights posture — origin-URL provenance per row or allow/deny list?
3. **Linus:** Pukui-Elbert vs Andrews dictionary edition pin
4. **Rusty (NLP / alignment):** LaBSE/LASER threshold tune for comparable-aligned Wikipedia / Wikisource (default 0.75)?
5. **Frank (follow-up):** Endpoint-verification sweep for 8 pending sources

**What was explicitly not done:**
- Did not modify routing config
- Did not fetch any bytes; did not add scripts; did not touch requirements.txt
- Did not pin Bible/dictionary editions
- Did not create manifest writer — that is Linus's territory

**Reference:** `data-sources/stage2-parallel-fetch-plan.json` (artifact), `.squad/orchestration-log/20260429-122655-frank.md`

---

### Decision: Linus — Stage-2 Manifest Builder + Split/Dedup Checks (Issues #11/#13)

**Author:** Linus (Data Engineer)
**Status:** Landed (prototype-private); no commit/push by directive

**What is decided:**

1. **Stage-2 manifest path + format:** `data/stage2/stage2_manifest.jsonl`, one row per canonical pair, `manifest_schema_version="stage2.v0"`. Per-run provenance at `data/stage2/build_manifest.json`. Both gitignored.

2. **Schema:** As encoded in `MANIFEST_FIELDS` in `scripts/320_build_stage2_manifest.py`; documented in `docs/data-pipeline.md` §"Stage 2 manifest schema". Adds `text_ref_en` / `text_ref_haw` and `manifest_schema_version`; everything else matches.

3. **Text requirement:** A pair must populate `text_en` or `text_ref_en` (and same for haw). Refs are pointers Basher's SFT emitter will resolve.

4. **Split-isolation enforcement (issue #13):** Five mechanical assertions at build time by `--check --strict`:
   - Intra-manifest pair / en-side / haw-side hash isolation between train and {dev, test, held-out}
   - External-ledger isolation: train hashes ∩ union of eval_hashes.jsonl files = ∅
   - `crosslink_stage1_overlap=true` allowed in train only
   - `dedup_cluster_id` never spans train and {dev, test, held-out}
   - `prototype_only=true ⇒ release_eligible=false`

5. **Out of scope:** Runtime contamination guard (issue #4, Squad:Yashas owns it). This script is artifact-only; must not be imported by training loops.

**FineWeb-2 Split/Dedupe Implementation (nested under #11/#13):**

Created `scripts/310_split_dedupe_fineweb2_haw.py` that:
- Splits test split (887 rows) deterministically: 70% dev → 582 rows / 30% holdout → 305 rows (seed=42)
- Dedupes train (95,507 rows) against all test row text SHA-256 hashes (zero overlaps found)
- Writes eval hash ledger: `data/evals/fineweb2_haw/eval_hashes.jsonl` (JSONL, not parquet, to avoid pyarrow)
- Writes manifest: `data/stage1/fineweb2_haw/split_dedupe_manifest.json` with full provenance

**Invariant enforced:** `train ∩ eval_hashes = ∅`

**Format choice (JSONL over Parquet for eval hashes):**
- Frank flagged pyarrow as optional in fetch script; not in requirements.txt
- JSONL sufficient for prototype scale (887 hashes)
- Compatible with stdlib-only toolchain
- Easy conversion to parquet later when justified
- Defers parquet adoption decision

**Why JSONL for manifest (not parquet):**
Same as 310: keep dependency surface stdlib-only until parquet is justified. Schema is parquet-clean (no nested types) so 1:1 promotion is possible later.

**Docs updated:**
- `docs/data-pipeline.md` §300-phase (added 310, 320 entries; added Stage 2 contamination & eval guards section)
- `docs/eval_pipeline.md` §3.1 (FineWeb-2 eval splits, hash ledger)

**Open questions:**
- **Rusty/Basher:** Additional alignment-quality fields to pre-allocate in schema?
- **Frank:** When canonical `data/evals/eval_hashes.parquet` ledger lands, checker should read it as primary source (legacy per-source JSONL as fallback)
- **Coordinator:** Confirm #4 routing — manifest builder explicitly does not touch runtime guard or `code/llm_hawaii/data.py`

**Reference:** `scripts/320_build_stage2_manifest.py`, `scripts/310_split_dedupe_fineweb2_haw.py` (new), `.squad/orchestration-log/20260429-122655-linus.md`

---

### Decision: Rusty — Stage 2 Alignment Scoring + Quality-Filter Policy (Issue #12)

**Author:** Rusty (NLP)
**Status:** Landed (prototype-private). No commit/push by directive.

**What is decided:**

Adopt `stage2-quality-v0.1` as the Stage-2 alignment-scoring + quality-filter policy for the prototype.

**Implementation surface:**
- `code/llm_hawaii/stage2_quality.py` — stdlib-only scorer with stable `quality_flags` vocabulary and `accept/review/reject` tiering
  - Public API: `PolicyConfig`, `score_pair(pair, config)`, `policy_summary()`
- `scripts/321_score_stage2_alignment.py` — CLI front-end + `--self-test`
- `docs/stage2-alignment-quality.md` — policy doc (tier rules, flag vocabulary, Hawaiian orthography caveats, manual-review workflow)
- `docs/data-pipeline.md` — cross-link added in Stage-2 transformation-notes block

**Field-vocabulary contract for Linus (#11) and Basher (#14):**

Stage 2 manifest rows extend the schema with:

| Field | Type | Source |
|-------|------|--------|
| `alignment_confidence_tier` | enum `accept`/`review`/`reject` | `score_pair()` |
| `alignment_review_required` | bool | derived = tier ∈ {review, reject} |
| `alignment_score_components` | object | per-rule breakdown |
| `quality_flags` | list[str] | stable vocabulary in `QUALITY_FLAGS` |
| `manual_review_reasons` | list[str] | 1:1 with `quality_flags` |
| `policy_version` | string | `"stage2-quality-v0.1"` |

Existing schema fields (`alignment_type`, `alignment_method`, `alignment_model`, `alignment_score`, `length_ratio_haw_over_en`, ...) are passed through / recomputed. **No schema field is renamed or repurposed.**

**Selection rule for Basher's SFT emitter (#14):**
`alignment_confidence_tier == "accept" AND split == "train"`

Quality flags and manual review reasons stay on manifest, never on SFT JSONL.

**Default thresholds:**
- `accept_min = 0.75`, `review_min = 0.55` (LaBSE/LASER cosine)
- `length_ratio ∈ [0.5, 2.5]` (haw/en whitespace-token ratio)
- `min_tokens_per_side = 3`, `max_tokens_per_side = 256`
- `diacritic_required_min_len = 60` (Hawaiian letter count)
- `nonhaw_letter_share_max = 0.10`
- `lid_*_min_confidence = 0.50` (consumed when present)

These match `data-pipeline.md` §"Stage 2 transformation pipeline" defaults; override via `PolicyConfig` without re-align.

**Out of scope (this card):**
- Issue #4 (training-loader contamination guard) — explicitly left for separate change
- Real LID classifier integration (e.g., GlotLID) — policy consumes `lang_id_*` when present; no model runs here
- Embedding alignment itself — LaBSE/LASER scores come from upstream; policy persists and gates

**Verification:**
- `python3 -m py_compile` clean on both new Python files + touched `__init__.py`
- `python3 scripts/321_score_stage2_alignment.py --self-test` passes with expected tier sequence `['accept', 'review', 'reject', 'reject', 'review']`

**Reference:** `code/llm_hawaii/stage2_quality.py`, `scripts/321_score_stage2_alignment.py`, `docs/stage2-alignment-quality.md`, `.squad/orchestration-log/20260429-122655-rusty.md`

---

### Decision: Basher — Stage 2 SFT JSONL Emitter (Issue #14)

**Author:** Basher (Training Engineer)
**Status:** Skeleton landed; not yet wired into training run

**Design choices:**

1. **Skeleton location:** `scripts/330_emit_stage2_sft_jsonl.py` (follows 3xx-builder convention; stdlib only; Parquet support deferred)
2. **Manifest input format:** JSONL (mirrors 301; Parquet adapter is follow-up)
3. **Text resolution order:** inline (`text_en` / `text_haw`) → path ref (`text_*_path`, absolute or repo-relative) → skip-with-reason
4. **Split passthrough:** Re-splitting at emit would break cluster-aware split isolation in manifest; emitter never assigns splits
5. **Conservative filtering:** Default excludes `alignment_review_required=true`, `synthetic=true`, out-of-spec alignment types, and (with `--min-alignment-score`) embeddings below floor. Deterministic alignments (null score) always admitted.
6. **Narrow provenance per row:** `pair_id`, `source`, `register`, alignment_{type,method,score}, `synthetic`, `synthetic_source_model`, `edition_or_version`, `prototype_only`, `dedup_cluster_id`, `crosslink_stage1_overlap`, `split`. Heavier fields queryable by `pair_id` on manifest.
7. **Out of scope (deliberately):** Retention-slice (haw-mono) rows — Stage-1 builder owns; contamination guard (#4) — separate pass before any training read; instruction-template rotation — TODO once templates.json exists

**Asks for the team:**

- **Linus:** When Stage-2 manifest gains real schema, confirm field names match emitter reads (`text_en`, `text_haw`, `text_*_path`, `alignment_*`, `split`) or push back
- **#4 owner:** Contamination guard belongs upstream; emitter intentionally does not consult `eval_hashes.parquet`

**Reference:** `scripts/330_emit_stage2_sft_jsonl.py`, `docs/training-pipeline.md` (update), `.squad/orchestration-log/20260429-122655-basher.md`

---

### Integration Review: Danny — Stage 2 Cross-Agent Alignment (2026-04-29T12-26Z)

**Reviewer:** Danny (Integration Reviewer)
**Status:** Review passed; batch approved for Coordinator capture

**What was reviewed:**
- Frank fetch-plan JSON schema (13 sources, alignment types)
- Linus manifest builder schema + 310 split/dedupe implementation
- Rusty quality policy fields (`alignment_confidence_tier`, `quality_flags`, vocabulary)
- Basher SFT emitter text resolution + filter logic

**Findings + fixes:**
- **Field naming consistency:** Fixed manifest text path field names (`text_en` / `text_haw` / `text_en_path` / `text_haw_path`) to align Linus builder, Rusty policy docs, Basher emitter
- **Schema alignment:** All four agents use consistent alignment_{type,method,score,confidence_tier} terminology; no conflicts
- **Doc cross-references:** Pointer checks passed (data-pipeline, stage2-alignment-quality, training-pipeline)

**Outcome:** Batch approved; no blockers; ready for Coordinator decision consolidation + orchestration log capture

**Reference:** `.squad/orchestration-log/20260429-122655-danny.md`, session log

---
1. **wiki-haw-en-langlinks first.** 53 pairs, structured, small
   embedding budget (~2k sentences total). Smoke validates the whole
   pipeline end-to-end in <5 min on CPU.
2. **sanitary-instructions-1881 second.** ~3k paragraphs total,
   chapter-scoped DP keeps the cosine matrix small. ~15 min CPU.
3. Then revisit OPUS-Wikimedia 275 mined rows under the same
   pre-pass once the script exists.

## Self-test

`python3 scripts/321_score_stage2_alignment.py --self-test` → passes
under current head. The test file covers
`{accept, review, reject, reject, review}` across deterministic and
embedding methods including missing-score → review.

## Anti-patterns Rusty refused

- Did **not** emit `data/stage2/candidates/sanitary_instructions_1881.jsonl`
  or `data/stage2/candidates/wiki_haw_en_langlinks.jsonl` with
  `alignment_score=null` and `alignment_review_required=true`.
  Per the lineage-preflight skill that's review-queue spam.
- Did **not** invent a heuristic "alignment_score" from
  TF-IDF / character n-gram / length ratio. No fake scores.
- Did **not** rewrite `data/stage2/stage2_manifest.jsonl` or
  `data/stage2/reviewed_stage2_manifest_finalized_reviews.jsonl` —
  finalized 603 canonical / 1206 directional remain the head of train.

## What this means for the team

- **Linus:** Decide on OPUS adapter fix vs policy fix for the 275 mined Wikimedia rows.
  Either way, do not promote them to manifest in current state. Tatoeba (75 accept)
  is clean to promote separately.
- **Frank:** None of the three blocked lanes (langlinks, sanitary, OPUS-wikimedia)
  proceed without LaBSE. Recommend deprioritizing further raw-probe work and coordinating
  on embedding infrastructure with the team.
- **Coordinator:** Three remaining Stage-2 priority lanes (langlinks, sanitary,
  OPUS-wikimedia subset) all blocked on the same LaBSE/LASER bring-up. Next move:
  wire sentence-transformers + LaBSE into requirements-compute.txt and run the
  embedding pre-pass in order (langlinks smoke → sanitary → OPUS-wikimedia).

## Reversal cost

Low. If team decides embedding-aligned sources are too risky for Stage 2, simply
do not run the embedding pre-pass. Scored review artefacts remain but do not merge
to manifest. Tatoeba (75 rows, deterministic) is independently safe to promote.

---

---

# Diglot NT 1859 Assessment (Corrected) — hOCR Column Extraction Deferred

**Owner:** Linus (Data Engineer)
**Date:** 2026-05-03
**Status:** DECISION — source assessment complete; extraction deferred pending Bible cap relief
**Source:** Diglot NT 1859 (`HAWPDF_DBS_HS`)
**Applies to:** Source priority queue; hOCR extraction pipeline planning

## 1. Summary

The Diglot NT 1859 assessment is **revised from "OCR-blocked" to "feasible-pending-hOCR-column-extraction"**.

## 2. Prior Assessment — Corrected

**Prior status:** `inventory_only` with blocker "OCR severely garbled from two-column layout."

**Corrected finding:** OCR text quality is **GOOD**. Only 0.1% of content lines are garbled (52/84,271 lines). Hawaiian text IS readable despite the OCR model being English-only (`-l eng+Latin`), because pre-1859 Hawaiian uses plain Latin script without ʻokina or kahakō diacritics.

## 3. Actual Blocker (Evidence-Based)

The blocker is **column inversion in the DjVu OCR reading order**, not OCR quality.

Each physical page scan in the pageindex produces a text chunk where **EN column content appears BEFORE HAW column content**:

- Page 5: EN Matt 1:10-13 → `"6 MATAIO, I."` running header → HAW Matt 1:14+
- Page 6: EN Matt 1:21-24 → `"MATAIO, II."` running header → HAW Matt 1:24b-25

Without page-break markers in djvu.txt and without x-coordinate bounding boxes, HAW and EN streams cannot be separated reliably from djvu.txt alone.

## 4. Path Forward (Deferred)

The **hocr_pageindex.json.gz** (9KB, already saved locally) gives exact byte offsets for each of 725 physical pages in the 84MB hOCR file. HTTP range requests against the hOCR file can fetch per-page bounding box data (~116KB/page) without downloading the full 84MB asset. Algorithm: x-coordinate < page_midpoint → HAW column; x ≥ page_midpoint → EN column.

**Prototype cost:** ~2–4 hours for Matthew (60 pages, ~7MB range data).  
**Full NT:** ~84MB total if all pages fetched, but cacheable and resumable.

**Decision:** Do not build the hOCR column extractor until Bible cap headroom opens. When N_nonbible grows (e.g., after Sanitary Instructions + additional non-Bible sources), revisit. The path is clear and low-risk.

## 5. Bible Cap Constraint (Why Defer)

Bible cap is saturated at 29.9% (≤30% target). **Zero train-ready rows** from any Bible source until N_nonbible increases. Any extracted verse pairs would be `review-pending / prototype_only / release_eligible=False` in the Bible pool until cap math allows promotion.

## 6. Artifacts

- **Location:** `data/raw/diglot-nt-1859/20260501/` — djvu.txt (2.4MB) + hocr_pageindex.json.gz (9KB) + provenance files
- **Report:** `data/stage2/reports/diglot_nt_1859_blocker_report.json`

## 7. Estimated Yield (When Extraction Built)

**5,500–6,400 review-pending candidate verse pairs** (all capped until N_nonbible headroom).
# Decisions

> Updated 2026-05-04T05:29:51Z: Merged decision inbox files: copilot-directive-2026-05-04T03-49-hooilina-paragraphs-only.md, linus-hooilina-paragraph-impl.md, linus-hooilina-paragraph-pairs.md, linus-stage2-common-voice-license-probe.md, linus-stage2-flores-plus-license-probe.md, linus-stage2-hk-statutes-extended.md, linus-stage2-tier-a-promotion.md, linus-stage3-paragraph-stage.md, rusty-hooilina-labse-policy.md. Prior 2026-05-03T20:55:00Z: Merged R17 linus-stage2-r17-canonical-consolidation (canonical helpers consolidated to single source of truth in `code/llm_hawaii/stage2_canonical.py`: canonical_en, canonical_haw, canonical_pair; 25 files refactored (adapters, audit, dedup, legacy normalizer); NFC normalize, strip invisibles, collapse whitespace, preserve case, EN folds curly quotes/hyphens, HAW ʻokina folding; 60/60 tests pass, 37,084 rows stable, strict audit pass, commit bf4b57e; future adapters MUST import from stage2_canonical, no local canonicalization helpers). Prior 2026-05-03T20:45:08Z: Merged R16 linus-stage2-r16-hash-determinism-policy (EN-side hash canonicalization contract locked: NFC normalize, strip invisibles, collapse whitespace, preserve case, fold EN curly quotes/hyphens to ASCII, keep U+02BC/U+02BB/em-en-dashes, HAW ʻokina folding HAW-only; 7 determinism tests added; FLORES+ and Common Voice probed RED/SKIP for Hawaiian; 37,084 rows stable, all suites green, commit 85ba2e5). Prior 2026-05-03T20:38:30Z: Merged R15 linus-stage2-r15-dedup-edge-fixes (fallback exact-pair ordering uses canonical source priority not alphabetical; near-dupe matching strips invisible controls U+00AD/U+200B/U+200C/U+200D/U+FEFF; manifest validation rejects whitespace/invisible-only refs; audit reports 7 invisible-control rows, 3 NBSP rows, 37,084 rows stable, all suites green). Prior 2026-05-03T20:33:14Z: Merged R14 linus-stage2-r14-contamination-wired (train-side eval-contamination filter now enforcing gate; `--eval-hashes` loads explicit eval ledgers before dedup, drops matches before cross-source/side/near-duplicate dedup, missing ledger hard error, writes contamination_report.json sidecar, all regression suites green). Prior 2026-05-03T1100Z: Merged R7 linus-stage2-paraphrase-grouping (161 EN/32 HAW exact groups accepted as lexical diversity, 395 rows annotated, zero drops, copilot user directive captured). Prior 2026-05-03T10:55:58Z: Merged R6 linus-stage2-short-variant-policy (37,223→37,084 rows; length-aware N=2 cap for short exact variants ≤3 tokens, 161 EN/32 HAW groups remain). Prior 2026-05-03T10:50:51Z: Merged R5 linus-stage2-near-dupe-policy (37,661→37,223 rows; 306 near-dupe groups collapsed, strong Bible-Gospel-John signal).
>

---

### 2026-05-04T03:49:30Z: User directive — Hoʻoilina paragraph-only emission
**By:** Yashas (via Copilot)
**What:** For Hoʻoilina, emit paragraph pairs only. Drop sentence-pair emission. Sentence pairs are derived from paragraphs, so emitting both trains on duplicate content; paragraphs carry more tokens and richer context per row.
**Why:** User decision — avoid duplicate content in Stage-2 SFT and prefer the longer, translator-aligned unit.

---

# Implementation: Hoʻoilina paragraph-only candidates

**Owner:** Linus  
**Date:** 2026-05-04  
**Status:** Implemented  
**Requested by:** Yashas

## Decision implemented

Hoʻoilina now emits paragraph pairs only. Sentence-pair emission is retired because those rows are derived from paragraph pairs and duplicate content at a less trusted alignment unit. LaBSE remains metadata-only for Hoʻoilina; no LaBSE threshold gates these rows.

## Code/path changes

- Renamed `scripts/325_build_hooilina_sentence_candidates.py` to `scripts/325_build_hooilina_paragraph_candidates.py`.
- `scripts/325_build_hooilina_paragraph_candidates.py`:
  - reads section-level parent rows from `data/stage2/candidates/hooilina_parent_sections.jsonl`;
  - falls back once to legacy parent rows in `data/stage2/candidates/hooilina.jsonl` and preserves them to the parent sidecar before overwriting;
  - writes primary paragraph-pair rows to `data/stage2/candidates/hooilina.jsonl`;
  - writes review-only recovered paragraph-number rows to `data/stage2/candidates/hooilina_recovered.jsonl`.
- `scripts/324_build_hooilina_candidates.py` now writes `hooilina_parent_sections.jsonl`, not the train-candidate path.
- `scripts/320_build_stage2_manifest.py` excludes `hooilina_parent_sections.jsonl`, `hooilina_recovered.jsonl`, and retired `hooilina_sentences.jsonl` from default candidate ingestion.
- `scripts/333_build_reviewed_manifest_final_capped.py` and `scripts/334_finalize_stage2_review_verdicts.py` were updated from Hoʻoilina sentence promotion wording to paragraph promotion wording.

## Hard gates retained

The paragraph builder keeps the existing deterministic gates and drops only sentence splitting:

- parent count match for primary paragraph emission;
- explicit paragraph-number matching for recovery;
- min 3 tokens per side;
- max 80 tokens per side;
- Hawaiian/English token ratio 0.5–2.5;
- boilerplate rejection;
- Hawaiian orthography/OCR non-Hawaiian-letter share ≤0.25;
- deduplication by `sha256_pair`;
- Hawaiian-only ʻokina normalization via Stage-2 canonicalization;
- `compute_pair_hash` reused from `scripts/320_build_stage2_manifest.py`.

## Before/after counts

| Artifact | Before | After |
|---|---:|---:|
| Hoʻoilina parent sections | 68 | 68 sidecar rows (`hooilina_parent_sections.jsonl`) |
| Primary Hoʻoilina sentence rows | 60 | retired / excluded from default manifest |
| Primary Hoʻoilina paragraph rows | 0 | 25 (`hooilina.jsonl`) |
| Review-only recovered rows | 0 | 137 (`hooilina_recovered.jsonl`) |

Primary build details:

- parent rows loaded: 68
- parent rows count-matched/splittable: 6
- parent rows not splittable: 62
- paragraph pairs inspected: 36
- paragraph pairs emitted: 25
- rejected: 11 total = 1 too short + 10 too long (>80 tokens)

Recovery details:

- recovery-eligible unmatched parents: 36
- parents with recovered output: 27
- paragraph-number matches inspected: 186
- recovered rows emitted: 137
- recovery quality rejected: 49
- recovered rows are tagged `review_required=true` and `alignment_review_required=true`
- recovered rows are not included in default Stage-2 manifest ingestion

## Manifest dry-run result

`python3 scripts/320_build_stage2_manifest.py --dry-run` after the change:

- total Stage-2 rows: 36,981
- schema violations: 0
- split counts: review-pending 34,387; train 2,350; dev 244

Source breakdown after dedup:

| Source | Rows |
|---|---:|
| Bible 1839 (`baibala-hemolele-1839`) | 5 |
| Bible 1868 (`baibala-hemolele-1868`) | 30,969 |
| Wikimedia CX (`wikimedia-cx-en-haw`) | 14 |
| OPUS haw subsets (`opus-haw-subsets`) | 388 |
| Hoʻoilina | 25 |
| Other sources combined | 5,580 |
| **Total** | **36,981** |

Bible cap check on parallel-train rows:

- parallel-train tokens: 66,127
- Bible train tokens: 5,765
- Bible share: 8.72%
- cap status: satisfied (≤30%)

Target status:

- 40k-row Stage-2 target: **not met**; short by 3,019 rows.
- 20k canonical-pair target: met; dry-run manifest has 36,981 canonical rows after dedup.

## Validation commands

```bash
python3 -m py_compile scripts/324_build_hooilina_candidates.py scripts/325_build_hooilina_paragraph_candidates.py scripts/320_build_stage2_manifest.py scripts/333_build_reviewed_manifest_final_capped.py scripts/334_finalize_stage2_review_verdicts.py
python3 scripts/325_build_hooilina_paragraph_candidates.py --self-test
python3 scripts/325_build_hooilina_paragraph_candidates.py --execute
python3 scripts/320_build_stage2_manifest.py --dry-run
```

---

# Proposal: Hoʻoilina Paragraph-Pair Emission

**Owner:** Linus  
**Date:** 2026-05-04  
**Status:** Proposed  
**Requested by:** Yashas

## Decision

Use **paragraph-primary with sentence fallback/auxiliary** for Hoʻoilina.

Hoʻoilina should emit paragraph-level candidate rows for deterministically matched numbered paragraph pairs. Sentence-level rows can remain as auxiliary/fallback training material, but they should no longer be the primary representation for this source.

## Current state

Current artifacts:

| Artifact | Rows | Unit | Alignment type | LaBSE |
|---|---:|---|---|---|
| `data/stage2/candidates/hooilina.jsonl` | 68 | parent/section row, often multiple numbered paragraphs | `parallel-doc` | none |
| `data/stage2/candidates/hooilina_sentences.jsonl` | 60 | sentence pair | `parallel-sentence` | none |

Current sentence-builder stats from `data/stage2/reports/hooilina_sentence_build_report_20260501.json` and re-run analysis of `scripts/325_build_hooilina_sentence_candidates.py`:

- Parent rows loaded: 68
- Parent rows with matched numbered-paragraph counts and >1 paragraph: 6
- Parent rows not splittable by current gate: 62
- Paragraph pairs inspected from the 6 matched parents: 36
- Paragraph pairs skipped because EN/HAW sentence counts differ: 8
- Sentence pairs seen: 61
- Sentence pairs emitted: 60
- Sentence-pair quality rejects: 1 (`too_short`)

No current Hoʻoilina row has `alignment_model` or `alignment_score`; LaBSE is not being used for Hoʻoilina selection.

## Paragraph-pair yield from the trusted matched parents

If we emit one row per paragraph pair from the same 6 parents with matched paragraph counts:

- Raw deterministic paragraph-pair rows: **36**
- Rows after reusing the sentence builder's min-3-tokens/side gate: **35** (one 1-token/1-token pair drops)
- EN token length: avg **49.92**, median **34**, max **168**, min **1**
- HAW token length: avg **64.83**, median **44.5**, max **236**, min **1**
- Paragraphs over 80 tokens on either side: **10/36**
- Paragraphs over 128 tokens on either side: **6/36**
- Paragraphs over 256 tokens on either side: **0/36**
- Paragraphs over 512 tokens on either side: **0/36**
- Sentence count: EN avg **2.83**, max **9**; HAW avg **2.58**, max **8**
- Paragraphs with ≤3 sentences: EN **26/36**, HAW **28/36**

Conclusion: these are normal short-to-medium paragraphs, not full pages. They are safely below the repo's training sequence regimes (`max_length=1024` for SFT tokenization defaults; training configs commonly use `max_seq_len=2048`). Even allowing tokenizer expansion, the largest observed paragraph pair is not a sequence-length problem.

## Tradeoff

Paragraph-level pros:

- Zero sentence-alignment risk inside the trusted paragraph unit.
- Preserves the human translators' actual alignment granularity.
- Preserves discourse context useful for Hawaiian particles, references, and phrase ordering.
- Avoids English/Hawaiian sentence splitter errors; current pipeline already drops 8/36 paragraph pairs only because sentence counts differ.

Sentence-level pros:

- More rows in this subset: 60 sentence rows versus 36 paragraph rows.
- Shorter examples are cheaper and easier for pure sentence-level translation pattern learning.
- Some SFT recipes prefer atomic source/target units.

For this source, the paragraph argument wins. The row-count argument is weak: 60 versus 36 is not enough gain to justify introducing splitter/alignment risk after deciding to trust the human paragraph translations. This is Hawaiian low-resource data; preserving high-confidence aligned content matters more than maximizing row count by splitting.

## Unmatched-parent recovery

The current hard gate skips 62 parents before sentence splitting because paragraph counts do not match or the parent has only one paragraph.

Observed recovery signals:

- 7 skipped parents are 1 EN paragraph / 1 HAW paragraph; 5 pass basic paragraph length/ratio/orthography sanity.
- 20 skipped parents have paragraph-count diff 1.
- 10 skipped parents have paragraph-count diff 2.
- Diff ≤2 group: explicit paragraph-number matching plus length/orthography sanity finds **155** plausible paragraph pairs.
- All 62 skipped parents: explicit paragraph-number matching plus sanity checks finds **526** plausible numbered paragraph pairs.

This is not a license to auto-promote all recovered rows. It is a strong reason to build a separate review-pending recovery mode that matches explicit paragraph numbers and applies length-ratio/OCR sanity checks. Paragraph-pairing gives a recovery path where sentence splitting currently gives none.

## Recommendation

Implement, if approved:

1. Add a Hoʻoilina paragraph-pair builder/output.
2. Make paragraph rows the primary Hoʻoilina representation for matched numbered paragraphs.
3. Keep sentence rows as auxiliary/fallback only, preferably derived from paragraph rows and not used to override paragraph-primary policy.
4. For the first pass, emit the 36 deterministic paragraph pairs from the 6 matched parents.
5. Add a second review-pending recovery pass for explicit paragraph-number matches in the 62 skipped parents; do not promote recovered rows without review.

Bottom line: **paragraph-primary with sentence fallback**.

---

# Stage-2 license-first probe: Mozilla Common Voice Hawaiian metadata

- Date: 2026-05-03
- Probe owner: Linus, Stage-2 round 16
- Network scope: metadata/license/robots only; no audio, no clips TSV, no bulk download, no `--execute`.

## URL

- HF dataset card checked: https://huggingface.co/datasets/mozilla-foundation/common_voice_17_0
- Common Voice robots: https://commonvoice.mozilla.org/robots.txt
- Common Voice metadata endpoint checked: https://commonvoice.mozilla.org/api/v1/datasets/languages
- Mozilla Data Collective Common Voice page: https://mozilladatacollective.com/organization/cmfh0j9o10006ns07jq45h7xk
- Mozilla Data Collective robots: https://mozilladatacollective.com/robots.txt
- CC0 reference page: https://creativecommons.org/publicdomain/zero/1.0/

## License observed verbatim

- Mozilla Data Collective Common Voice table shows dataset license cells as `CC0-1.0`.
- Creative Commons deed title: `CC0 1.0 Universal`.
- Creative Commons deed notice: `The Commons Deed is not a legal instrument. It is simply a handy reference for understanding the CC0 Legal Code`.

## Robots / access

- `https://commonvoice.mozilla.org/robots.txt`: `User-agent: *`, `Disallow: /spontaneous-speech/`.
- `https://mozilladatacollective.com/robots.txt`: `User-Agent: *`, `Allow: /`.
- Probe used a polite UA and sleeps. No audio or clip archives were downloaded.

## Schema / coverage

- HF card page is reachable but did not expose `haw`, `Hawaiian`, `CC0`, clips, or duration in card text.
- Common Voice `/api/v1/languages` returned 431 language entries with no `haw` / `Hawaiian` match.
- Common Voice `/api/v1/datasets/languages` returned 137 dataset-language entries with no `haw` / `Hawaiian` match.
- Hawaiian locale status: not observed. Total clips/duration: `0 / not available` for Hawaiian in observed metadata.

## Contamination risk vs existing sources

- Audio is out of scope for text Stage-2.
- If Common Voice later exposes Hawaiian validated text prompts/sentences, they may be monolingual HAW or prompt text, not guaranteed parallel EN↔HAW.
- Prompt text may overlap public-domain sentence lists or other Common Voice prompt sources; it needs side-hash contamination checks before any use.

## Verdict

- RED for current Stage-2 ingestion: no Hawaiian locale observed in metadata.
- License posture for Common Voice generally looks GREEN (`CC0-1.0`), but absent Hawaiian coverage makes this source unusable now.

## Routing

- Current routing: SKIP.
- Future routing if Hawaiian appears: consider monolingual/prompt-ledger first, not parallel train; only promote to TRAIN if prompt text is actually CC0, Hawaiian text is present, no TOS restriction conflicts, and contamination checks pass.

## Adapter sketch

- No adapter now.
- Future probe should pin a Common Voice release, record robots/TOS/license snapshots, read metadata only first, and refuse audio downloads.
- Candidate path, if ever justified, should emit prompt strings as monolingual HAW or paired metadata only after confirming schema fields and license; no blind EN↔HAW parallel assumption.

---

# Stage-2 license-first probe: FLORES+ haw_Latn

- Date: 2026-05-03
- Probe owner: Linus, Stage-2 round 16
- Network scope: license/card/robots only; no dataset download, no `--execute`.

## URL

- Dataset card: https://huggingface.co/datasets/openlanguagedata/flores_plus
- Dataset metadata checked for file/config names only: https://huggingface.co/api/datasets/openlanguagedata/flores_plus
- License page: https://creativecommons.org/licenses/by-sa/4.0/
- Robots: https://huggingface.co/robots.txt

## License observed verbatim

- HF card metadata: `cc-by-sa-4.0`
- HF card text: `FLORES+ is a multilingual machine translation benchmark released under CC BY-SA 4.0.`
- Creative Commons deed title: `Attribution-ShareAlike 4.0 International`
- Creative Commons condition: `ShareAlike — If you remix, transform, or build upon the material, you must distribute your contributions under the same license as the original.`

## Robots / access

- `https://huggingface.co/robots.txt`: `User-agent: *` / `Allow: /`.
- Probe used a polite UA and sleeps. No data files were downloaded.

## Schema / coverage

- HF card says FLORES+ has `228 language varieties`.
- HF card says each included language has `997 sentences for the dev split and 1012 sentences for the devtest split`.
- Metadata check found `siblings 480`, `haw []`, and `configs haw []`.
- Result for Hawaiian: `haw_Latn` not present in observed card/metadata. Row count for Hawaiian is therefore `0 / not available`, not 997+1012.

## Contamination risk vs existing sources

- If Hawaiian is added later, risk is high for train contamination because FLORES is a standard MT benchmark and should be kept out of training.
- No current collision work is needed because no haw_Latn rows were observed.

## Verdict

- RED for current Stage-2 ingestion: Hawaiian absent.
- If future `haw_Latn` appears: YELLOW / EVAL-only due benchmark status and CC-BY-SA share-alike obligations.

## Routing

- Current routing: SKIP.
- Future routing if haw_Latn appears: EVAL ledger only; never train candidates.

## Adapter sketch

- No adapter now.
- Future adapter must require exact dataset revision pin, exact `cc-by-sa-4.0` confirmation, local ToS/license snapshot, and `--execute`.
- It should hash EN and HAW sentences into `data/evals/eval_hashes.jsonl` before any train ingest, mark `eval_only=true`, and refuse writes under `data/stage2/candidates/`.

---

# Linus — Stage-2 HK statutes Round 8 extension

## Legal/TOS check

- Host for 1869/1859/1846 is the same as the already-processed 1897 pair: `archive.org`.
- Existing IA ToS snapshot inherited: `data/raw/hawaiian-kingdom-statutes-paired-imprints/20260501/_tos/ia_terms.html`, snapshot id `ia_terms`, fetched `2026-05-01T21:14:22Z`, sha256 `4bbba9062696abf26a594e0c9fb3e84101cf05321f557b9d8baf862f863ada7b`.
- Rights status: public domain for the legal text (pre-1929 public-domain term + sovereign-edicts doctrine for government legal edicts). IA ToS governs hosted scan/OCR bytes.
- No live fetch was performed in Round 8; only already-local raw OCR and manifests were inspected.

## Editions added to source registry / adapter pins

- 1869 Penal Code: EN `https://archive.org/details/esrp475081650`; HAW `https://archive.org/details/esrp468790723`; status `blocked-content-mismatch` because HAW OCR filename is `1850.002_djvu.txt` and prior sampling found mismatched content. Dry-run parsed 38 EN sections / 2 HAW sections / 1 common / 0 emitted.
- 1859 Civil Code: EN `https://archive.org/details/civilcodehawaii00armsgoog`; HAW `https://archive.org/details/hekumukanawaiam00hawagoog`; status `in-progress-dryrun-only` pending manual Pauku range mapping. Dry-run parsed 195 EN sections / 80 HAW sections / 21 common / 0 emitted.
- 1846 Statute Laws: EN `https://archive.org/details/statutelawshism00ricogoog`; HAW `https://archive.org/details/kanawaiikauiaek00ricogoog`; status `in-progress-dryrun-only` pending act/chapter segmentation because section numbers repeat across acts. Dry-run parsed 633 EN section markers / 36 HAW markers / 0 common / 0 emitted.

## Shipped

- `scripts/325_build_hk_statutes_candidates.py` is now edition-parameterized (`--edition 1897|1869|1859|1846`).
- `--execute` remains allowed only for 1897; non-1897 editions are dry-run/inventory only until alignment blockers are cleared.
- Added `data-sources/hk-statutes/source_registry.json` with license/TOS, source URLs, access timestamps, raw sha256 values, and edition status.
- Added stdlib unittest with mocked HTTP layer to verify User-Agent/rate-limit behavior without live network.

---

# Stage-2 Tier A Review-Pending Promotion

**Owner:** Linus  
**Date:** 2026-05-04  
**Status:** Proposed / implemented as additive v2 artifact

## Decision proposal

Promote only review-pending rows that are already policy-approved:

- `manual_review_reasons` contains `Accepted under historical-orthography policy`
- `manual_review_reasons` contains `Eligible under hk1897-legal-clean-v1`
- Source whitelist: `hooilina`, `wikimedia-cx-en-haw`, `weblate-en-haw`, `tatoeba`

Then enforce train-side caps by pair-token share, using whitespace tokens on `text_en + text_haw`:

- Bible-family sources ≤ 30%
- HK/legal sources ≤ 15%
- software-l10n sources ≤ 15%

Existing train rows are frozen. Newly admitted Tier A rows are greedily considered in `sha256_pair` order; if a cap is breached, evict the highest-`sha256_pair` newly admitted row from that cap group until the final artifact passes. Dev rows are untouched.

## Audit result

Input: `data/stage2/reviewed_stage2_manifest_final_capped.jsonl`

- Splits before: train 4,286; review-pending 33,830; dev 15
- Train pair tokens before: 113,453
- Review-pending pair tokens before: 2,227,600
- Tier A identified: 7,632 rows / 724,253 pair tokens
  - historical orthography accepted: 6,873 rows / 460,504 tokens
  - hk1897 legal-clean eligible: 670 rows / 140,578 tokens
  - whitelist: 89 rows / 123,171 tokens
- Dedup skip: 8 whitelist rows already had exact pair hashes in train (7 Wikimedia CX, 1 Tatoeba)
- Tier A after dedup: 7,624 rows / 723,283 tokens
- Cap evicted from newly admitted set: 6,412 rows / 501,390 tokens
- Promoted in v2: 1,212 rows / 221,893 tokens

## What got promoted

Output: `data/stage2/reviewed_stage2_manifest_final_capped_v2.jsonl`

Per-source promoted deltas:

| Source | Rows | Pair tokens |
|---|---:|---:|
| baibala-hemolele-1839 | 975 | 66,570 |
| hk_statutes_1897 | 156 | 33,122 |
| hooilina | 68 | 120,940 |
| weblate-en-haw | 4 | 354 |
| wikimedia-cx-en-haw | 9 | 907 |

New train state:

- Train rows: 5,498
- Train pair tokens: 335,346
- Review-pending rows: 32,618
- Dev rows: 15, unchanged

Cap shares after promotion:

- Bible: 100,594 / 335,346 = 29.9971%
- HK/legal: 50,129 / 335,346 = 14.9484%
- software-l10n: 1,882 / 335,346 = 0.5612%

## Count-only and sample-only piles

Tier B remains blocked by cap policy, count-only:

- `dropped-by-bible-cap-v2-fixedpoint`: 25,283 rows / 1,450,151 tokens
- `dropped-by-hk-legal-cap-v2-fixedpoint`: 735 rows / 149,234 tokens
- `historical_orthography_sub_cap_reached`: 5,399 rows / 361,128 tokens

Tier C was sampled only, no promotion:

- Andrews vocab: 1,194 rows / 5,785 tokens
- OPUS haw subsets: 332 rows / 8,994 tokens
- Kaikki Wiktionary: 48 rows / 1,362 tokens
- Gospel John 1854: 590 rows / 32,713 tokens
- HK Constitution 1852: 68 rows / 9,030 tokens

Sample files are under `data/stage2/reports/tier_c_samples_*_20260504.jsonl`.

Tier D stays rejected: terminal quality failures (`side_too_short`, `length_ratio_extreme`, `haw_nonhaw_letters_high`).

## Verification

- `python3 -m py_compile scripts/335_promote_tier_a_review_pending.py`
- `python3 scripts/335_promote_tier_a_review_pending.py`
- Re-read v2 manifest: row count unchanged, dev rows byte-identical, only `split` changed on promoted rows, all caps pass.

Primary report: `data/stage2/reports/stage2_tier_a_promotion_20260504.json`.

---

# Linus verdict — Stage 3 paragraph SFT

**Requested by:** Yashas  
**Owner:** Linus  
**Status:** Recommendation

## Verdict

Yes in principle, but not now: keep Stage 2 sentence/verse/row-grain and add a paragraph/document Stage 3 only after Stage 2 plateaus and passes regression gates.

## Rationale

The data supports a real longer-context lane, but it is a different training objective, not a replacement for Stage 2 row SFT. Plausible paragraph/document sources are Hoʻoilina paragraph pairs plus recovery rows, HK statute sections and constitution articles, Bible whole-chapter aggregates if built, gospel_john_1854 chapter/section aggregates, and nupepa articles if alignment is strong enough. That pool is probably mid-six-figure to low-seven-figure pair tokens depending on whether Bible chapters and nupepa are included; Hoʻoilina alone is tiny, HK sections are useful but register-skewed, and Bible/nupepa dominate scale.

## Curriculum tradeoff

Benefit: Stage 3 can teach longer-context translation/generation, paragraph coherence, document register, and less choppy sentence-by-sentence behavior. Cost: it is another run, another eval surface, and another forgetting vector for Stage 2 sentence-level translation quality. Treat it as late curriculum with lower LR/short epochs and explicit regression evals, not as a data-volume hack.

## Sequence length and dedup hazards

Current serious Stage 2 config is `code/configs/stage2_prototype.json` with `max_seq_len=1024`; smoke is 256. HK sections and Hoʻoilina paragraphs are mostly safe, but Bible chapters and nupepa articles can exceed 1024 once prompt+source+target are concatenated and would need filtering, packing policy, chunking, or a Stage 3 config with longer sequence length. If Stage 2 trains sentence splits and Stage 3 trains source paragraphs, the model sees overlapping content twice; that is acceptable as curriculum only when overlap is intentional and measured, otherwise it becomes memorization and source-register overweighting.

## Recommendation

Do not interrupt Stage 2 to build this now. Finish Stage 2 row SFT, evaluate plateau/forgetting, then run a Stage 3 paragraph prototype with length-aware admission, overlap metadata, and sentence-regression gates. If we need paragraphs sooner, fold a small capped paragraph lane into Stage 2 via a length-aware sampler rather than creating a premature new stage.

---

# Proposal: Hoʻoilina LaBSE Policy

**Owner:** Rusty  
**Date:** 2026-05-04  
**Status:** Proposed  
**Requested by:** Yashas

## Decision

For Hoʻoilina, keep LaBSE as a **soft metadata signal only**. Do not auto-reject or auto-demote Hoʻoilina rows solely because a LaBSE score falls below a generic threshold.

Policy choice: **(b) Keep LaBSE as a soft signal — log the score, never auto-reject.**

## Rationale

Hoʻoilina is not a mined/comparable web source. It is a numbered-paragraph bilingual journal source where the English and Hawaiian were published together by human translators/editors. For this source class, the main risk is not whether the source texts mean the same thing; it is whether our extraction has paired the correct units.

The current Hoʻoilina sentence builder (`scripts/325_build_hooilina_sentence_candidates.py`) does not use LaBSE. It uses deterministic filename pairing, numbered-paragraph counts, sentence-count agreement, length filters, boilerplate filters, non-Hawaiian-letter filters, and deduplication. Emitted rows carry no embedding score: `alignment_model=None`, `alignment_score=None`.

Current measured Hoʻoilina builder stats:

- 68 parent rows loaded
- 6 parent rows splittable
- 62 parent rows not splittable because EN/HAW paragraph counts fail the deterministic structure gate
- 36 paragraph pairs inspected
- 8 paragraph pairs skipped because sentence counts mismatch
- 61 sentence pairs seen
- 60 sentence pairs emitted
- 1 sentence pair quality-rejected

Current candidate-file annotations:

- `data/stage2/candidates/hooilina.jsonl`: 68 rows, all review-pending; 18 accept-tier by deterministic/content checks, 50 review-tier mostly due to `side_too_long`; no LaBSE scores.
- `data/stage2/candidates/hooilina_sentences.jsonl`: 60 rows, all review-pending; 59 accept-tier by deterministic/content checks, 1 review-tier due to `haw_nonhaw_letters_high`; no LaBSE scores.

We have no Hoʻoilina-specific calibration showing LaBSE is reliable for Hawaiian journal translation. Prior LaBSE usage in this repo was for CX/OPUS/mined comparable triage, not for human-translated Hoʻoilina paragraphs. In the current environment the LaBSE scorer cannot run because `sentence_transformers` is not installed, so there are no local Hoʻoilina LaBSE distributions to cite.

## Operational rule

For Hoʻoilina:

1. Structural gates remain hard:
   - matched numbered-paragraph count
   - matched sentence count within paragraph
   - no boilerplate
   - token length and length-ratio bands
   - Hawaiian orthography/OCR sanity filters
   - deduplication
2. `prototype_only=True` and `release_eligible=False` remain until a release review changes that.
3. If LaBSE is later run, store `labse_score` / `labse_verdict` or equivalent metadata, but do not map low score to automatic rejection.
4. A very low score may add `manual_review_reasons += ["low_labse_soft_signal"]` for reviewer attention only.
5. Hard LaBSE thresholds remain appropriate for mined/comparable sources such as OPUS-wikimedia, NLLB-style mined pairs, wiki langlinks, and other sources where parallelism is inferred rather than source-published.

## Counter-risk

Yashas is right about the source-level human translation quality, but source quality is not extraction quality. Bad rows can still arise from OCR corruption, footnote or copyright boilerplate, paragraph-mid splits, missing paragraph numbers, article headers, or sentence splitter errors. Those risks should be handled by deterministic structural extraction and content/OCR filters, not by letting an uncalibrated 109-language encoder overrule Hoʻoilina's human translators.

---

# Stage-2 Canonical Helper Consolidation (Round 17)

**Owner:** Linus  
**Date:** 2026-05-03  
**Status:** Implemented  
**Commit:** bf4b57e

## Decision

`code/llm_hawaii/stage2_canonical.py` is the locked Stage-2 canonicalization surface.
Future Stage-2 adapters, audit tools, contamination ledgers, and manifest code MUST import from it for candidate clean text and pair-hash canonicalization.

Required public helpers:

- `canonical_en(s)` — English clean side canonical form.
- `canonical_haw(s)` — Hawaiian clean side canonical form.
- `canonical_pair(en, haw)` — eval-ledger pair text, `canonical_en(en) + U+2016 + canonical_haw(haw)`.

The module also owns `canonicalize_clean_text`, `sha256_text`, and `compute_pair_hash` so legacy manifest wrapper APIs can remain compatible without duplicating rules.

## Contract

- NFC normalize all text.
- Remove soft hyphen, zero-width controls, and BOM.
- Collapse all whitespace runs to one ASCII space and trim ends.
- Preserve case.
- English folds curly single/double quotes and U+2010/U+2011 hyphen variants, but does not fold U+02BC or U+02BB.
- Hawaiian folds ASCII/curly/backtick/U+02BC apostrophe-like marks to U+02BB ʻokina.
- Pair hashes remain `SHA256(sha256_en_clean + U+2016 + sha256_haw_clean)`.

## Rationale

Before R17, the manifest builder, eval contamination helper, candidate adapters, and audit scripts had multiple local normalizers. Those could drift on EN punctuation, HAW ʻokina, invisible controls, or whitespace. A single module keeps future hash determinism testable and prevents adapters from silently creating incompatible ledger keys.

## Implementation notes

- `scripts/320_build_stage2_manifest.py` imports/re-exports the central helper for backward-compatible tests and callers.
- `code/llm_hawaii/eval_contamination.py` now uses `canonical_pair` for Stage-2 pair content and the same `sha256_text` primitive.
- Stage-2 builders/audits delegate clean candidate text to `stage2_canonical` rather than open-coding `.replace()`/`.strip()` folds.
- `scripts/340_audit_stage2_candidate_normalization.py --strict` treats canonicalization-delta counts as advisory and still fails on post-policy schema errors or eval contamination.

## Verification

- `python3 code/tests/test_stage2_canonical.py -v` — 4/4
- `python3 code/tests/test_stage2_dedup.py -v` — 17/17
- `python3 code/tests/test_hash_determinism.py -v` — 7/7
- `python3 code/tests/test_eval_contamination.py -v` — 5/5
- `python3 code/tests/test_manifest_contamination_filter.py -v` — 2/2
- `python3 code/tests/test_taxi1500_ingester.py -v` — 6/6
- `python3 code/tests/test_global_piqa_ingester.py -v` — 5/5
- `python3 code/tests/test_weblate_adapter.py -v` — 7/7
- `python3 code/tests/test_tatoeba_refresh.py -v` — 7/7
- `python3 scripts/320_build_stage2_manifest.py --dry-run` — 37,084 rows
- `python3 scripts/340_audit_stage2_candidate_normalization.py --strict` — pass

## Future rule

New Stage-2 source work must not introduce local canonicalization helpers for candidate clean text. If a source needs pre-cleaning (HTML unescape, OCR page-number stripping, template removal), do that first, then call `canonical_en`/`canonical_haw` for final clean text and hashing.

---

# Stage-2 Hash Determinism Contract (Round 16)

**Owner:** Linus  
**Date:** 2026-05-03  
**Status:** Implemented  
**Commit:** 85ba2e5

## Decision

Stage-2 EN clean-text hashes now have an explicit canonicalization contract before side hashing:

- NFC normalize.
- Remove soft hyphen, zero-width space/joiner/non-joiner, and BOM.
- Collapse all whitespace runs to one ASCII space and trim edges.
- Preserve case.
- For EN, fold curly single quotes to ASCII apostrophe, curly double quotes to ASCII quote, and U+2010/U+2011 hyphens to ASCII hyphen-minus.
- For EN, do not fold U+02BC modifier-letter apostrophe or U+02BB Hawaiian ʻokina.
- For HAW, fold apostrophe-like marks to U+02BB ʻokina.
- Keep em/en dashes, double hyphen, and spaced hyphen distinct.

## Rationale

This makes `sha256_en_clean`, `sha256_haw_clean`, and `sha256_pair` deterministic across typographic punctuation and whitespace drift without erasing case or Hawaiian orthography distinctions on the English side.

## License Probes (No Fetch)

**FLORES+:** RED/SKIP — Hawaiian split absent from FLORES+/200 set; would be CC-BY-SA if added (eval-only gate applies).

**Common Voice:** RED/SKIP — no Hawaiian locale present; would be CC0 if added (audio not relevant for text Stage-2).

## Verification

- `python3 code/tests/test_hash_determinism.py -v`: 7 tests passed.
- `python3 code/tests/test_stage2_dedup.py -v`: 17 tests passed.
- `python3 scripts/320_build_stage2_manifest.py --dry-run`: 37,084 rows.

---

# Stage-2 Dedup/Normalization Edge-Case Fixes (Round 15)

**Owner:** Linus  
**Date:** 2026-05-03  
**Status:** Implemented  
**Commit:** 2ea6615

## Decision

Keep Stage-2 clean hashes byte-preserving under the existing candidate artifacts, but make dedup/audit matching robust to default-ignorable Unicode format controls. English-side apostrophe and ʻokina remain distinct for dedup keys; Hawaiian-side ʻokina folding remains Hawaiian-only.

## Findings

- Candidate audit rows: 37,761
- NFC drift: 0 EN / 0 HAW
- HAW ʻokina hash drift: 0
- EN apostrophe/right-quote rows: 2,119; preserved by policy
- Invisible format-control rows: 7 (soft hyphen, zero-width, BOM)
- Non-ASCII whitespace rows: 3 (NBSP in Tatoeba HAW strings)
- Whitespace-only rows after normalization: 0
- Raw trailing-punctuation token variants: 98; existing token-based near-dupe policy already collapses final cross-source token-pair duplicates to 0
- Short rows appear in several sources beyond Phrase Book/Andrews/Weblate, but the cap is length-aware and source-independent except Weblate's software-l10n threshold; no missing-source cap change is needed

## Policy Implications

- `stage2-cross-source-dedup-v0.6` changes fallback exact-pair ordering to canonical source priority + length + stable IDs, avoiding accidental alphabetical-source wins when no explicit preference rule exists
- Near-dupe comparisons remove U+00AD, U+200B, U+200C, U+200D, and U+FEFF before token comparison
- Manifest validation treats inline text/path refs containing only whitespace and default-ignorable controls as missing
- Audit reports invisible controls and non-ASCII whitespace but does not make them strict failures unless they also create schema/hash/contamination failures

## Verification

- Dedup tests: 13/13 ✓
- Audit tests: 4/4 ✓
- Manifest validation: 2/2 ✓ (new)
- Strict passes: 340 ✓
- Manifest dry-run: 37,084 rows (unchanged) ✓

Row drops stable: exact-pair 100, exact-EN cap 199, exact-HAW cap 75, near-dupe 303.

---

# Stage-2 Train-Side Eval-Contamination Filter (Round 14)

**Owner:** Linus  
**Date:** 2026-05-03  
**Status:** Implemented  
**Commit:** 934c0f2

## Decision

`--eval-hashes` is now an enforcing train-side gate in `scripts/320_build_stage2_manifest.py`, not a cosmetic output-time filter. Explicit eval ledgers are loaded before dedup; matching candidate rows are dropped before cross-source/side/near-duplicate dedup runs. Missing explicit ledgers are hard errors.

## Reporting Contract

Manifest builds with `--eval-hashes` write `data/stage2/contamination_report.json` with:

- `ledger_path`
- `ledger_size`
- `total_dropped`
- `per_source_dropped`
- `per_match_type` (`full_pair`, `single_side_haw`, `single_side_en`)
- `drop_reasons` using `contamination:{source}`
- dropped row IDs/source/match type examples

The build manifest also embeds the contamination filter stats under `ingest.contamination_filter`.

## Audit Contract

`scripts/340_audit_stage2_candidate_normalization.py --eval-hashes <ledger>` reports how many candidate rows would be dropped without mutating inputs. `--strict` treats any contamination as an error and lists row IDs in the JSON report.

## Verification

No network fetches or new sources were used. Regression results:

- `test_eval_contamination.py`: 5/5 ✓
- `test_manifest_contamination_filter.py`: 2/2 ✓
- `test_stage2_dedup.py`: 13/13 ✓
- `test_taxi1500_ingester.py`: 6/6 ✓
- `test_global_piqa_ingester.py`: 5/5 ✓
- `scripts/320_build_stage2_manifest.py --dry-run`: 37,084 rows
- `scripts/340_audit_stage2_candidate_normalization.py --strict`: pass

## Round 15 Recommendation

Dedup edge-case shoring up is the best next infra piece: add focused tests around interaction order between contamination filtering, exact-side caps, near-dupe collapse, and historical-orthography caps.

---

# Stage-2 Paraphrase Grouping Decision (Round 7)

**Owner:** Linus  
**Date:** 2026-05-03  
**Status:** Implemented

## Decision

Accept the remaining one-sided exact duplicate groups as legitimate lexical diversity and annotate them with `paraphrase_group_id`; do not drop more rows and do not move them to held-out.

## Evidence

Post-Round-6 dry-run still shows 161 exact-English groups and 32 exact-Hawaiian groups. Samples are mostly expected formulaic or lexical variants:

- Bible formulae with distinct Hawaiian renderings: "The grace of our Lord Jesus Christ be with you all. Amen." maps to multiple verse endings.
- Bible narrative formulae: "And the LORD spake unto Moses, saying," and "The word of the LORD came unto me, saying," recur with small Hawaiian lexical/OCR/casing variation.
- Hawaiian-side lexical variants: Tatoeba keeps "ʻO Keoni koʻu inoa." for "My name is John." / "My name's John." / "John is my name."
- Dictionary variants are semantically legitimate: Andrews "Nothing" / "Nought" both map to "he ole, he mea ole."

No obvious broken pattern justified another hard drop rule. Additional dedup would mostly erase useful paraphrase/lexical diversity.

## Implementation

`code/llm_hawaii/stage2_dedup.py` now annotates connected one-sided exact groups after exact-pair collapse, one-sided caps, and near-duplicate collapse. `scripts/320_build_stage2_manifest.py` records `paraphrase_grouping` stats in ingest provenance. The manifest row count remains unchanged.

## Metrics

- Manifest rows: 37,084 → 37,084 (delta 0)
- Exact-EN groups annotated: 161 groups / 341 row hits
- Exact-HAW groups annotated: 32 groups / 71 row hits
- Connected paraphrase components: 178
- Rows with `paraphrase_group_id`: 395

---

# Stage-2 Sourcing Priorities (Round 7 Part B)

**Owner:** Linus  
**Date:** 2026-05-03  
**Status:** Round-8 handoff

## Current eligibility

Round-7 in-memory dry-run from `scripts/320_build_stage2_manifest.py` emits 37,084 clean manifest rows. Current train split contains 2,396 canonical pairs, or 4,792 bidirectional SFT rows via `scripts/330_emit_stage2_sft_jsonl.py` filters. Gap to 40,000 directional SFT rows: 35,208.

The large difference between clean rows and SFT rows is expected: 34,438 rows are `review-pending`, 250 are `dev`, and only 2,396 are `train`. The manifest builder forces review/reject quality tiers to `review-pending`; only accept-tier rows are assigned train/dev, with non-parallel rows forced train-only. The SFT emitter then emits only requested splits and skips synthetic rows by default.

## Prioritized next sources

1. **Hawaiian Kingdom statutes bilingual — remaining 1869/1859/1846 pairs.** Public IA / PD, no compute dependency, deterministic section-id alignment, and the 1897 adapter provides the clearest pattern. Plan: extend `scripts/325_build_hk_statutes_candidates.py` to parameterize edition pairs and reuse CHAPTER/MOKUNA/section matching; enforce combined legal-register cap downstream.
2. **Weblate EN↔HAW public translation memories.** Plain HTTP/Weblate API, no embedding dependency, existing localization/TMX-line adapter pattern from Weblate/software-l10n work. Plan: dry-run enumerate public Hawaiian projects, apply permissive-license filter first, then adapt `scripts/329_build_weblate_en_haw_candidates.py` style rows.
3. **Global-PIQA haw_Latn TSV.** Public static TSV, no auth/compute, simple row-id adapter pattern. Plan: HEAD/probe the TSV and verify license/register; if train-appropriate, emit parallel-sentence candidates; otherwise hash into eval ledger only.

Excluded for Round 8: NLLB and Wikisource endpoints are invalid; wiki-langlinks and Sanitary require LaBSE/compute; Bible-family additions are cap-saturated; Pukui/modern dictionary work needs rights review; synthetic BT needs model-quality and cap infrastructure.

---

# Copilot User Directive: Stage-2 Sourcing Compliance

**Date:** 2026-05-03T10:40Z  
**From:** yashasg (via Copilot CLI)  
**Scope:** Stage-2 sourcing and all future data intake

## Directive

Stage-2 sourcing must not break any laws. Respect TOS, copyright, license terms, robots.txt, and rate limits. License/TOS check happens **BEFORE** fetch. No bypassing auth/paywalls. When in doubt, escalate to user instead of fetching.

## Implementation

- All sourcing agents (Frank, Linus, data-sourcing specialists) must read this before executing any remote fetch or data integration.
- Log license/TOS check results in adapter history or sourcing decision file.
- If a source requires legal review or user sign-off, block the fetch and document the hold.

---


**Owner:** Linus  
**Date:** 2026-05-03  
**Status:** Implemented (Round 6)

## Decision

Use a length-aware exact one-sided duplicate policy for Stage-2 candidate dedup. For exact-EN or exact-HAW groups whose duplicated side is at most 3 normalized tokens, keep at most 2 variants and require the opposite side to contain at least 4 normalized tokens. Rows failing the opposite-side minimum are dropped before cap ranking. Longer exact one-sided groups keep the Round 5 cap of 3. The Baibala 1839 historical-orthography exception remains exempt from these exact-side caps.

## Rationale

Round 6 sampling showed the short-variant problem is mostly phrase/dictionary material: exact-EN remaining groups had 124 short duplicated-side rows, concentrated in Phrase Book (61) and Andrews (52); exact-HAW remaining groups had 88 short rows, concentrated in Andrews (44) and Phrase Book (29). Bible/Hoʻoilina-style rows are generally sentence-length and should keep the generic cap. A source allowlist with N=5 would preserve more dictionary variants but also retain one-word/short-gloss rows that add little SFT value. The source-agnostic length rule is simpler, deterministic, and directly targets low-information short variants regardless of source.

## Verification

- `PYTHONPATH=code python3 code/tests/test_stage2_dedup.py` ✓
- `PYTHONPATH=code python3 code/tests/test_stage2_candidate_normalization_audit.py` ✓
- `PYTHONPATH=code python3 code/tests/test_stage2_manifest.py` ✓
- `python3 scripts/320_build_stage2_manifest.py --dry-run` → 37,084 rows ✓
- `python3 scripts/340_audit_stage2_candidate_normalization.py --strict --max-examples 3` → 0 post-policy schema violations, 0 hash mismatches, 0 post-policy near-dupe groups ✓

## Alternative considered

Source-allowlisting Phrase Book and Andrews with N=5 plus a sentence heuristic was rejected for now. The data showed the problem is not that these sources were over-clipped; it is that many rows are very short on both sides. Raising their cap would increase low-signal lexicon-style variants in the SFT pool.

---

# Stage-2 Near-Duplicate and One-Sided Exact Duplicate Policy

**Owner:** Linus  
**Date:** 2026-05-03  
**Status:** Implemented in manifest dry-run path

## Decision

Stage-2 post-policy dedup now runs in this order:

1. collapse exact cross-source `sha256_pair` duplicates;
2. cap exact-English-only groups at **3** variants per `sha256_en_clean`;
3. cap exact-Hawaiian-only groups at **3** variants per `sha256_haw_clean`;
4. collapse cross-source near-duplicate groups at **0.92** similarity on both sides.

Selection is deterministic: source priority (richer provenance first), then longer combined text, then stable `(source, pair_id, record_id_haw)`. Baibala 1839 historical-orthography exception groups are excluded from one-sided caps so the historical sub-cap math remains stable.

## Rationale

A cap of 3 keeps useful translation/paraphrase signal for common strings (e.g. greetings and short phrase-book rows) without letting one English or Hawaiian phrase dominate the manifest. Near-duplicate collapse is cross-source only to avoid deleting intentional within-source variants or test fixtures; current hits are mostly Bible-family overlap plus Andrews/Phrase Book-style short phrase duplication.

## Round-5 measurements

After Round-4 exact pair dedup baseline (37,661 rows):

| Pass | Groups | Rows dropped |
|---|---:|---:|
| Exact EN cap (N=3) | 15 capped groups | 128 |
| Exact HAW cap (N=3) | 2 capped groups | 4 |
| Near-dupe collapse (threshold 0.92) | 306 groups | 306 |

Manifest dry-run: **37,661 → 37,223** rows.

Audit before policy reported 262 exact-EN-only groups, 88 exact-HAW-only groups, and 306 near-dupe groups. After policy, near-dupe groups are 0; remaining one-sided exact groups are ≤3 variants each (207 EN groups, 70 HAW groups).

## Follow-up

Round 6 should sample the remaining one-sided exact groups by source (especially Andrews/Phrase Book and short dictionary rows) and decide whether source-specific caps or manual allowlists should supplement the global N=3 policy.

---


# Sanitary Instructions 1881 — Comparable-Aligned Row Schema Gate

**Owner:** Linus  
**Date:** 2026-05-03  
**Status:** Implemented in adapter/test seam

## Decision

Sanitary Instructions 1881 candidates are comparable-aligned LaBSE rows, not deterministic paragraph-parallel rows. The adapter must emit schema-compatible generic enums:

- `alignment_type = "comparable-aligned"`
- `alignment_method = "labse"`
- adapter policy details in `policy_version`, `manual_review_reasons`, and `alignment_score_components`

Rows remain `split="review-pending"`, `alignment_review_required=true`, `prototype_only=true`, and `release_eligible=false` until rights/cap finalization promotes or excludes them. `license_inferred` stays null per manifest schema. The adapter's `--execute` mode requires both `--confirm-edition sanitary-instructions-1881-ia-nlm-paired` and an existing `--tos-snapshot` path.

## Why

The manifest validator accepts only fixed enum values. Encoding the mutual-nearest paragraph policy in enum fields would make every emitted row schema-invalid and block later manifest builds. Keeping rows prototype-only also matches current Stage-2 policy for non-finalized source candidates.

---

# Stage-1 A100 Loss Plateau Diagnosis

**Owner:** Basher
**Status:** Finding / recommendation

## Finding

The reported telemetry near epoch 1 (`loss ~= 1.17-1.23`, `grad_norm ~= 0.35`, `learning_rate = 5e-05`) matches the checked Stage-1 A100 config:

- `code/configs/stage1_fineweb2_haw.json`
  - `stage`: `stage1-cpt`
  - `learning_rate`: `0.00005`
  - `lr_scheduler_type`: `constant_with_warmup`
  - `warmup_ratio`: `0.01`
  - `num_train_epochs`: `2.0`
  - `per_device_train_batch_size`: `1`
  - `gradient_accumulation_steps`: `16`
  - `max_seq_len`: `2048`
  - `lora_rank`: `32`, `lora_alpha`: `64`
  - `bf16`: `true`, `fp16`: `false`

Training code confirms Stage 1 is full-token CLM/CPT: `code/llm_hawaii/train.py` routes non-`stage2-sft` configs through `build_train_dataset()` and `make_collator()`, and `code/llm_hawaii/data.py` sets `labels = input_ids` for Stage-1 records. Stage 2 is the target-only masked SFT path.

## Diagnosis

This is not a proven plateau from five adjacent log points near the end of epoch 1. At this point warmup is long complete and the configured scheduler keeps LR constant at 5e-5, so small local movement in training loss is expected. Grad norms around 0.35 are below Trainer's default `max_grad_norm=1.0`, so clipping is not suppressing updates.

However, the A100 config is materially more conservative than the documented Stage-1 recipe in `docs/training-pipeline.md`: docs call for LoRA r64/α128, LR 2e-4 cosine, warmup 3%, and ~64k-128k effective tokens/update. The checked config uses r32/α64, LR 5e-5, constant-with-warmup, and about 32k max tokens/update before padding/short-document effects.

## Recommendation

Do not switch to Stage 2 and do not change LR mid-run. Let the current run finish its configured 2 epochs, evaluate Stage-1 gates, then decide whether to rerun with the documented Stage-1 recipe (`2e-4` cosine, warmup `0.03`, LoRA `64/128`, larger effective token/update if memory allows). Stage 2 should wait for Stage-1 eval gates.

---

# Stage 2 Final Review Verdict Policy — Closing the `split=review-pending` Ambiguity

**Owner:** Danny (Lead / Architect)
**Date:** 2026-05-03
**Status:** PROPOSAL — accepted policy; Basher owns implementation
**Applies to:** `data/stage2/reviewed_stage2_manifest_final_capped.jsonl` (33,851 rows; 33,551 currently `split=review-pending`)
**Related:** `.squad/decisions/inbox/rusty-review-pending-policy.md`, `.squad/skills/fixed-point-cap-enforcement/SKILL.md`, `data/stage2/reports/stage2_review_pass_final_capped_20260501.json`

---

## 1. Problem statement

The final-capped artifact ships 285 train / 15 dev rows. The remaining
**33,551 rows carry `split=review-pending`** with no further verdict
field. That label is doing two incompatible jobs:

1. **Schema-level signal** to the SFT emitter: "do not promote this row
   to a directional training pair right now."
2. **Editorial state**: "this row has not been adjudicated yet."

The first is correct and must persist (the emitter relies on it). The
second is **false** for almost every row in the file: each was already
inspected by the cap-enforcement pass, by Rusty's review-pending policy,
or by Linus's source-rights gate. Leaving them as undifferentiated
`review-pending` lets a future reader (or a future us) believe these
rows are still candidates for promotion to train, when in fact most are
not.

This policy gives every row a final verdict without changing the
emitter contract or the accepted train/dev counts.

---

## 2. Decision (accepted policy)

### 2.1 Schema invariant — DO NOT CHANGE

- `split` field stays as-is on every row. `review-pending` remains the
  emitter signal "not a training row."
- Train (285) and dev (15) counts stay frozen. Caps stay verified
  against the artifact (Bible 29.92%, HK 14.59%).
- `stage2_manifest.jsonl` (canonical, pre-review) is **not touched**.

### 2.2 New required fields on every row

---

## Archived: 2026-05-03T06:10:38Z

See decisions-archive.md for prior decisions (431K trimmed).


---

# Hoʻoilina Sentence Pipeline — Basher Verification

**Date:** 2026-05-03
**Owner:** Basher
**Status:** All claims verified ✅

## Decision

Linus's Hoʻoilina sentence pipeline and Stage 2 final training artifact are approved. All 7 claims independently confirmed:

1. **35 Hoʻoilina sentence candidates** emitted (35 file lines; report `para_pairs_emitted=35`; 1 rejected for quality).
2. **368 final train-ready canonical rows** (finalized reviews + direct row count).
3. **736 directional SFT rows** (368 × 2; verified by `wc -l`).
4. **Zero Hoʻoilina dev rows** — all 35 Hoʻoilina train rows are `split=train`; the 15 frozen dev rows are Tatoeba only.
5. **Bible train token share: 29.98%** ≤ 30% — cap holds against actual artifact.
6. **HK legal token share: 14.9953%** ≤ 15% — cap holds against actual artifact.
7. **`data/stage2/stage2_manifest.jsonl` untouched** — git working tree clean; pipeline wrote to `reviewed_stage2_manifest_final_capped.jsonl`; canonical manifest still has 11,828 rows with no Hoʻoilina entries.

## Implication for Team

The Stage 2 SFT artifact (`data/stage2/stage2_sft_final_capped.jsonl`, 736 rows) is ready for training. Fixed-point caps remain enforced on the final artifact per SKILL.md protocol. No re-run of cap math is needed.


---

# Stage-2 40k Target: Proposed Next Actions

**From:** Frank  
**To:** Coordinator  
**Date:** 2026-05-02  
**Context:** User directive to reach 40k Stage-2 rows; Frank investigation complete

## Current State

- **Manifest:** 37,711 rows (31,073 Bible + 6,638 non-Bible)
- **Gap to 40k:** 2,289 rows
- **Bible cap saturated:** 31k Bible vs 1,994 cap (30% of 6,638 non-Bible)
- **Need:** ~1,728 more non-Bible rows (unlocks 518 Bible = 2,246 total)

## Frank's Finding

**Deterministic-alignment non-Bible pool is exhausted.** All viable sources processed:
- tatoeba (121), weblate (107), phrase_book_1881 (2,516), andrews (1,194), kaikki (292), hk_statutes_1897 (1,103), hooilina (128), gospel_john_1854 (602), hk_constitution_1852 (74), wikimedia_cx (14), opus (487 review-pending)
- **Total:** 6,638 non-Bible candidates

HK Statutes 1869/1859 pairs blocked (content mismatches, low yield).

## Three Paths to 40k

### Option 1: LaBSE-Align Comparable Sources (FASTEST TO 40k)

**Unblock:**
- wiki-haw-en-langlinks (53 probed, 3000-5000 expected)
- sanitary-instructions-1881 (200-800 expected)
- wikimedia-cx expansion (1000-3000 expected)
- OPUS-wikimedia mined (275 rows)

**Estimated combined yield:** 4,000-8,000 rows after LaBSE alignment + filtering

**Blocker:** sentence-transformers + LaBSE model not in requirements.txt; no embedding pre-pass script exists

**Ownership:**
- Rusty: LaBSE threshold tuning (already investigated comparable-aligned scoring)
- Frank or Linus: Write embedding pre-pass script (model load, batch embed, cosine threshold, emit candidates)

**ETA:** 1-2 days if prioritized (install libs, write script, run langlinks smoke, iterate)

**This is the HIGHEST-LEVERAGE path** — one infra unlock yields 4k-8k rows.

### Option 2: Synthetic BT/FT from Stage-1 Monolingual

**Unblock:**
- Stage-1-merged checkpoint (fineweb2 + hooilina mono)
- Generator script (back-translate HAW→EN via merged checkpoint)
- Rusty quality floor policy

**Estimated yield:** 5,000-10,000 capped at ≤15% of parallel-train tokens

**Blocker:** Stage-1 merge not done; BT generation pipeline not written

**Ownership:**
- Linus: Stage-1 merge
- Rusty: BT quality floor
- Frank: BT adapter if raw generation outputs exist

**ETA:** Unknown (Stage-1 merge is multi-day; BT pipeline is new)

**Lower priority** unless Stage-1 merge is already in progress.

### Option 3: Promote Review-Pending Candidates + Revise Cap

**Immediate action:**
- 715 review-pending candidates exist (OPUS 487, tatoeba 121, weblate 107)
- If Linus promotes these, non-Bible grows to 7,353 → Bible cap lifts to 2,206

**This buys 212 more Bible rows** but doesn't close the 2,289 gap.

**Cap revision (policy decision):**
- If Bible cap raised from 30% to 35%, cap = 2,573 → allows 579 more Bible
- If raised to 40%, cap = 2,941 → allows 947 more Bible
- **35% cap + promote review-pending = 7,353 non-Bible + 2,573 Bible = 9,926 DIRECTIONAL** (not enough for 40k canonical)

**This alone does NOT reach 40k** without also adding non-Bible rows.

## Recommendation

**PRIORITIZE OPTION 1 (LaBSE):**

1. **Coordinator:** Assign LaBSE bring-up to Rusty + Frank (or Linus)
2. **Step 1 (infra):** Add sentence-transformers to requirements-compute.txt; install; test model load
3. **Step 2 (script):** Write `scripts/310_embed_and_align_comparable.py` (load LaBSE, batch embed, cosine threshold, emit candidates)
4. **Step 3 (smoke):** Run wiki-langlinks (53 pairs, small embedding budget) to validate pipeline
5. **Step 4 (scale):** Run sanitary-instructions-1881, then wikimedia-cx, then OPUS-wikimedia
6. **Step 5 (promote):** Linus reviews + promotes accepted candidates

**ETA to 40k:** 2-3 days if LaBSE is prioritized.

**Fallback:** If LaBSE is blocked on model licensing or compute, escalate to Option 2 (synthetic BT) or accept <40k target with current pool.

## Frank's Next Step

Awaiting coordinator decision. If LaBSE is GO:
- Frank can prototype the embedding pre-pass script
- Rusty owns threshold tuning
- Coordinate on who writes the final version

If LaBSE is NO-GO, Frank has no further deterministic sources to collect.


---

### 2026-05-02T04:06Z: User directive
**By:** Yashas (via Copilot)
**What:** Continue working Stage 2 data acquisition without stopping until manifest reaches 40k SFT rows, OR the user explicitly says stop. No idle pauses between work cycles — chain follow-ups automatically.
**Why:** User request — Stage 2 row target is 40k (≈20k canonical pairs + retention). Current head ~603 canonical / 1206 directional; major gap remaining.


---

# Decision: Hoʻoilina Sentence Pipeline v2 (Frank)

**Date:** 2026-05-02  
**Author:** Frank (Hawaiian Data Collector)  
**Revision cycle:** v2 — Linus lockout applies; Frank owns this artifact.  
**Status:** Implemented and verified.

---

## Decision

Revised `scripts/325_build_hooilina_sentence_candidates.py` to perform genuine
two-level splitting (section → paragraph → sentence), replacing the v1
paragraph-level emission that incorrectly labeled multi-sentence paragraph
rows as `parallel-sentence`.

---

## Sentence Split Policy (binding for this source)

**Splitter:** stdlib-only regex `(?<=[.!?])\s+(?=[A-ZĀĒĪŌŪ\u02bb])` —
splits only at sentence-ending punctuation followed by whitespace and an
uppercase letter (EN uppercase + Hawaiian macron vowels + U+02BB ʻOkina prefix).

**Abbreviation protection:** `ABBREV_SET` (Mr., Dr., No., St., etc.) prevents
false splits. Last word before a candidate split is checked after stripping `.`.

**Decimal protection:** The uppercase lookahead ensures "3.14 kg" is not split.

**Whitespace normalisation:** All runs of whitespace/newlines are collapsed to a
single space before splitting, so `\n`-separated paragraphs are handled correctly.

**Conservative skip:** If EN sentence count ≠ HAW sentence count for a given
paragraph pair, the paragraph is **skipped entirely**. No partial emission.

---

## Gate Changes in Script 333

Hoʻoilina sentence candidate promotion gate now requires ALL of:
- `alignment_type == "parallel-sentence"` (hard filter; rejects old paragraph-level rows)
- `en_t >= 3 and haw_t >= 3` (min tokens)
- `en_t <= 80 and haw_t <= 80` (max tokens, conservative 80-token cap)
- `ratio in [0.5, 2.5]`
- `sha256_pair not in seen` (dedup)

Promotion rule id updated to `hooilina-sentence-v2`.

---

## Verified Counts

| Artifact | Count |
|---|---|
| Sentence candidates emitted | 60 |
| EN token range | 3–59 |
| HAW token range | 5–64 |
| Multi-sentence violations | 0 |
| Side > 80 tokens | 0 |
| Promoted to train | 60 |
| Total train (all sources) | 369 |
| Dev (frozen) | 15 |
| SFT rows (2× train) | 738 |
| Bible share | 29.66% (≤30% ✓) |
| HK share | 14.90% (≤15% ✓) |

---

## Files Modified

- `scripts/325_build_hooilina_sentence_candidates.py` — v2 two-level sentence builder
- `scripts/333_build_reviewed_manifest_final_capped.py` — tightened Hoʻoilina gate
- `scripts/334_finalize_stage2_review_verdicts.py` — updated train reason string

## Data Artifacts Regenerated

- `data/stage2/candidates/hooilina_sentences.jsonl`
- `data/stage2/reports/hooilina_sentence_build_report_20260501.json`
- `data/stage2/reviewed_stage2_manifest_final_capped.jsonl`
- `data/stage2/reports/stage2_review_pass_final_capped_20260501.json`
- `data/stage2/reviewed_stage2_manifest_finalized_reviews.jsonl`
- `data/stage2/reports/stage2_finalized_review_verdicts_20260501.json`
- `data/stage2/stage2_sft_final_capped.jsonl`

## Not Modified

- `data/stage2/stage2_manifest.jsonl` — untouched per task spec.


---

# Decision: Bishop 1881 Hawaiian Phrase Book → first PD non-prototype Stage-2 train source

**Author:** Frank (Hawaiian Data Collector) · 2026-05-02
**Status:** Inbox — needs review by curators
**Affected sources:** `ia-hawaiian-phrase-book-1881`
**Affected scripts:** 326 (new), 330, 333, 334

## Context

The Bishop 1881 *Hawaiian Phrase Book* (IA `hawaiianphrasebo00bishrich`) is the first source we are admitting to the Stage-2 train split as **release-eligible PD** — i.e. with `prototype_only=False` and `release_eligible=True`. Prior train sources are either:

- prototype-only (Hoʻoilina paragraphs/sentences, HK 1897),
- cap-constrained (Bible 1839/1868 ≤30%, HK ≤15%),
- or different licensing tier (Tatoeba CC-BY, Kaikki/Wiktionary CC-BY-SA).

This is a meaningful release-readiness milestone, so it deserves an explicit decision record.

## Decisions made

1. **License posture:** treat as `PD-pre-1928-US` (`license_inferred`), with `license_observed = "Public Domain (pre-1928, U.S.; IA NOT_IN_COPYRIGHT)"` confirmed via IA `possible-copyright-status=NOT_IN_COPYRIGHT` and 1881 publication date. Set `release_eligible=true`, `prototype_only=false`.

2. **Precision-first parser, not coverage-first.** djvu OCR has 12,903 lines but only ~4,400 are cleanly column-stripped two-column phrase blocks. We hard-cut at the `"A Conversation with a Native Woman."` anchor and discard the back-of-book dialog/correspondence section. We also drop wrap-block multi-line entries and any single-line block that does not end with `.!?`. Yield: **224 pairs**, all clean by manual sample inspection. Recall is not the goal here — pair-level cleanliness is.

3. **Uncapped contribution.** Phrase Book is *not* a cap-controlled source. It is small (~900 tokens), so dwarfed by the Bible budget anyway, but as a precedent: PD non-Bible non-HK Stage-2 train sources are uncapped and count toward N in the fixed-point cap math.

4. **alignment_type = "phrase-pair"** is now allowed in the SFT emitter (`scripts/330_emit_stage2_sft_jsonl.py`'s `DIRECTIONAL_ALIGNMENT_TYPES`). This applies to any future short phrase-list adapter (Andrews appendix when promoted, future Pukui sets, etc.).

5. **alignment_review_required = true** is kept on every row even after promotion, because (a) 1881 OCR has no ʻokina/kahakō, and (b) two-column block pairing is heuristic not deterministic. The `train-ready` verdict is still issued because the gates are tight.

## Numbers after promotion

- Train pairs: 369 → **603** (+234, of which +224 are phrase book; the +10 difference comes from re-running cap fixed-point with the larger N).
- Bible: 29.91% (cap 30%, PASS).
- HK: 14.83% (cap 15%, PASS).
- Phrase Book: 8.20%.
- Directional SFT rows: 738 → **1,206**.

## Open questions for the team

1. Should phrase-book rows be considered eligible for **dev** as well? Current pipeline keeps dev frozen on Tatoeba. The phrase book has a clean enough sample that 10–20 rows could ship as a held-out sanity slice. Not done in this PR — flagged for a follow-up decision.
2. The same parser strategy could likely double our yield (~450 pairs) if we built a *paragraph-level* aligner for the dialog section that uses speaker turns rather than block pairing. Worth ~1 sprint of work; deferred.

## Pointers

- Adapter: `scripts/328_build_phrase_book_candidates.py`
- Build artifact: `data/stage2/candidates/phrase_book_1881.jsonl` (224 rows)
- Build report: `data/stage2/reports/phrase_book_1881_build_report_20260502.json`
- Post-promotion manifest: `data/stage2/reviewed_stage2_manifest_finalized_reviews.jsonl`
- SFT: `data/stage2/stage2_sft_final_capped.jsonl` (1,206 rows)
- Frank history: `.squad/agents/frank/history.md` (entry 2026-05-02)


---

# Frank — Round 2 NLLB + Wikipedia Langlinks Extraction: 40k Target Assessment

**Date:** 2026-05-03  
**Owner:** Frank (Hawaiian Data Collector)  
**Context:** User directive: "don't stop until you have 40k rows"  
**Status:** ❌ **40K TARGET NOT REACHABLE WITH AVAILABLE SOURCES**

---

## Executive Summary

**Round 2 actual yield: 2 SFT rows** (vs. estimated 18k-36k)

**Blockers:**
1. **NLLB mined haw-eng** — Source DOES NOT EXIST. The `allenai/nllb` dataset does not include `haw_Latn` in its 188 supported language pairs. Estimated 16k-30k yield is **unrecoverable** from this endpoint.
2. **Wikipedia langlinks haw-en** — Extraction completed but yielded only **1 accepted pair = 2 SFT rows** (vs. 2k-6k estimate). Root cause: Hawaiian Wikipedia articles are stubs; comparable-aligned assumption doesn't hold.

**Gap to 40k:**
- Rusty's LaBSE baseline: 8,208 SFT rows
- Round 2 actual addition: +2 SFT rows
- New ceiling: 8,210 SFT rows
- **Gap to 40k: 31,790 SFT rows** (79% shortfall)

---

## Track A: NLLB Mined Haw-Eng — BLOCKED (0 rows)

### Finding (confirmed via probe 2026-05-02)

`allenai/nllb` dataset **does not include Hawaiian (`haw_Latn`)** in its mined bitext collection. Probe verified:
- Dataset loader script (`nllb_lang_pairs.py`) enumerates 188 language codes
- Hawaiian is NOT among them (only `hat_Latn` [Haitian Creole] and `hau_Latn` [Hausa])
- datasets-server `/rows` endpoint returns 404 for both `haw_Latn-eng_Latn` and `eng_Latn-haw_Latn` configs

**Artifacts:**
- `data-sources/nllb-mined-haw-eng/README.md` (documents blocker)
- `data/raw/nllb-mined-haw-eng/20260501/endpoint_proof.json` (probe receipts)

**Verdict:** The 16k-30k estimated yield from NLLB is **unrecoverable**. This source cannot contribute to the 40k target.

---

## Track B: Wikipedia Langlinks Haw-En — CRITICAL YIELD FAILURE (2 rows)

### Execution Summary

**Script:** `scripts/338_build_wiki_langlinks_candidates.py` (built + tested)  
**Input:** 53 langlinks pairs from `data/raw/wiki-haw-en-langlinks/20260502/langlinks_manifest.jsonl`  
**Extraction result:** 8 candidates (15.1% success rate)  
**LaBSE scoring (threshold 0.75):** 1 accept, 4 review, 3 reject  
**Final yield:** 1 accepted pair = **2 SFT rows** (1 pair × 2 directions)

### Root Cause Analysis

1. **Low extraction rate (8/53 = 15.1%):**  
   MediaWiki API `prop=extracts&exintro=1&explaintext=1` returns empty text for most Hawaiian Wikipedia articles. Many are:
   - Stub articles with <50 words
   - Templates or category pages (e.g., `Anakuhi:Okina`)
   - Redirect pages

2. **Low LaBSE acceptance rate (1/8 = 12.5%):**  
   Extracted text pairs are **not semantically parallel**. Hawaiian and English Wikipedia articles are independent articles about the same topic, not translations. Hawaiian articles are typically much shorter and simpler than English counterparts.

   **Example (rejected, LaBSE score 0.49):**
   - EN: "San Francisco, officially the City and County of San Francisco, is the fourth-most populous city in California and the 17th-most populous in the United States, with a population of 826,079 in 2025." (30+ words, detailed)
   - HAW: "He kūlanakauhale ʻo Kapalakiko (ʻōlelo Pelekania: San Francisco) o Kaleponi." (16 words, simple identification)

**Verdict:** Wikipedia langlinks is **not a viable path** to the 2k-6k estimated yield. Comparable-aligned assumption does not hold for Hawaiian Wikipedia. **Actual yield: 2 SFT rows.**

**Artifacts:**
- `scripts/338_build_wiki_langlinks_candidates.py` (extraction script)
- `data/stage2/candidates/wiki_langlinks_haw_en.jsonl` (8 candidates)
- `data/stage2/_scored/wiki_langlinks_haw_en.labse.jsonl` (8 scored)
- `data/stage2/_scored/wiki_langlinks_haw_en.labse.summary.json` (1 accept, 4 review, 3 reject)

---

## Track C: Alternative NLLB/Mined Sources — INVESTIGATION INCOMPLETE

### Sources Investigated

1. **CCMatrix (OPUS/Facebook)** — Web search indicates Hawaiian-English pair NOT available in CCMatrix corpus
2. **CCAligned (HuggingFace)** — Dataset not accessible via HuggingFace (`ccaligned` doesn't exist on Hub)
3. **MADLAD-400 (Google/AllenAI)** — Probe script hung while checking 419-language configs; Hawaiian presence uncertain
4. **WikiMatrix (OPUS/Facebook)** — Wikipedia-based mined sentences; likely same issues as langlinks approach (stub articles, non-parallel)

### Time Constraint Assessment

Investigating all alternative mined sources would require:
- 2-4 hours per source (probe, verify Hawaiian coverage, assess yield, build adapter if viable)
- Estimated 8-16 hours total for 4-8 sources
- High risk of same blockers: Hawaiian not included or yield too low

**Recommendation:** Escalate to coordinator. Alternative mined sources are unlikely to bridge the 31,790-row gap.

---

## Track D: Sanitary Instructions 1881 — NOT ATTEMPTED

**Status:** Not attempted this round (low priority, estimated <1k yield)  
**Raw data available:** `data/raw/sanitary-instructions-1881/20260502/` (document pair)  
**Blocker:** Requires sentence-level alignment extraction + LaBSE scoring  
**Estimated effort:** 2-4 hours  
**Max yield:** 200-800 candidates → dozens to low-hundreds post-LaBSE (per Rusty's estimate)

**Verdict:** Even if successful, would add <200 SFT rows. Not a 40k blocker.

---

## Honest Gap Analysis: Path to 40k

### Current State (Post-Round 2)

| Source | Estimated Yield | Actual Yield | Status |
|--------|-----------------|--------------|--------|
| Round 1 deterministic | 6,638 candidates | ~6,638 rows | ✅ Complete (Linus) |
| NLLB mined haw-eng | 16k-30k SFT rows | **0 rows** | ❌ Source doesn't exist |
| Wikipedia langlinks | 2k-6k SFT rows | **2 rows** | ❌ Yield failure |
| Sanitary Instructions | <1k SFT rows | 0 rows | ⚠️  Not attempted |
| **TOTAL (Round 1+2)** | **24k-43k** | **~8,210 rows** | **Gap: 31,790 rows (79%)** |

### Paths Forward (Coordinator Decision Required)

**Option 1: Synthetic BT/FT Generation**
- Use Stage-1 Hawaiian monolingual corpus as source
- Back-translate Hawaiian → English (using existing MT model)
- Forward-translate English → Hawaiian (using existing MT model)
- Quality filter with LaBSE ≥0.80
- **Estimated yield:** Variable, depends on base model quality
- **Risk:** Synthetic data quality floor; requires Rusty's BT pipeline

**Option 2: Revise 40k Target**
- Accept realistic ceiling of ~10k-15k SFT rows with available sources
- Focus on quality over quantity
- Prioritize deterministic parallel sources over synthetic
- **Tradeoff:** Lower training volume, but higher-quality pairs

**Option 3: Wait for More Hawaiian Parallel Data**
- Community-contributed translations (e.g., Tatoeba expansion)
- New mined corpora that include Hawaiian (e.g., future NLLB releases, community efforts)
- Hawaiian language revitalization projects producing parallel text
- **Timeline:** Unknown; could be months or years

**Recommendation:** **Option 1 (Synthetic BT) + Option 2 (Revised target to 15k)** is the most realistic path. Option 3 is long-term only.

---

## Round 2 Deliverables

1. ✅ **Wikipedia langlinks candidate JSONL** — `data/stage2/candidates/wiki_langlinks_haw_en.jsonl` (8 candidates)
2. ✅ **Wikipedia langlinks LaBSE-scored output** — `data/stage2/_scored/wiki_langlinks_haw_en.labse.jsonl` (1 accept, 4 review, 3 reject)
3. ✅ **Extraction script** — `scripts/338_build_wiki_langlinks_candidates.py` (stdlib + urllib only, triple-gated)
4. ✅ **NLLB blocker documentation** — Confirmed via existing probe; documented in `data-sources/nllb-mined-haw-eng/README.md`
5. ✅ **Orchestration log** — `.squad/orchestration-log/2026-05-03T03-54-21Z-frank-round2-extract.md`
6. ✅ **This decision note** — `.squad/decisions/inbox/frank-round2-40k-honest-gap.md`

---

## Final Summary (Terse)

**NLLB: 0 pairs / 0 accepted (source doesn't exist). Langlinks: 8 pairs / 1 accepted at 0.75. Estimated SFT addition: 2 rows. Path to 40k: NOT REACHABLE. Gap: 31,790 rows (79%). Recommend: Synthetic BT + revised target to 15k.**

---

**Date:** 2026-05-03  
**Orchestration log:** `.squad/orchestration-log/2026-05-03T03-54-21Z-frank-round2-extract.md`  
**History update:** `.squad/agents/frank/history.md` (to be written)


---

# Frank — Stage-2 40k Target Blockers

**Date:** 2026-05-02  
**Context:** User directive to reach 40k Stage-2 rows without stopping  
**Current state:** 37,711 manifest rows (31,073 Bible + 6,638 non-Bible); gap = 2,289 rows  
**Target:** ~1,728 more non-Bible rows needed (allowing 518 Bible cap lift = 2,246 total)

## Investigation Summary

Spent 2+ hours investigating remaining non-Bible sources. Key findings:

### ✅ Sources Already Processed
- tatoeba: 121 rows (full dataset)
- weblate: 107 rows (only 5 permissive-license components exist; full coverage)
- andrews_1865_vocab: 1,194 rows (full dataset)
- kaikki_wiktionary: 292 rows (full dataset)
- phrase_book_1881: 2,516 rows (full dataset)
- opus_haw_subsets: 487 rows (review-pending)
- wikimedia_cx: 14 rows (small dataset)
- hk_statutes_1897: 1,103 rows (1897 Penal Laws only)
- hooilina: 128 rows combined
- gospel_john_1854: 602 rows
- hk_constitution_1852: 74 rows

**Total non-Bible candidates:** 6,638 rows (matches manifest)

### ❌ HK Statutes Remaining Pairs — BLOCKED

**1869 Penal Code pair (esrp475081650 EN / esrp468790723 HAW):**
- **BLOCKER:** Content mismatch confirmed via section sampling
- EN Section 1: "robbery, larceny" offenses
- HAW Section 1: "Moi me ke kuka pu" (King and council) — different law entirely
- HAW imprint year is **1850**, not 1869 (noted in fetch plan but not investigated until now)
- **Verdict:** NOT a valid translation pair. Same blocker as 1846/1847.

**1859 Civil Code pair (civilcodehawaii00armsgoog EN / hekumukanawaiam00hawagoog HAW):**
- EN: 201 "Section N" markers found
- HAW: 97 "Pauku N" markers found
- **Only 21 common section numbers** (11% overlap)
- **Estimated yield if built:** 20-50 rows after filtering
- **Cost-benefit:** Not worth adapter complexity for <50 rows

**Assessment:** Only the 1897 Penal Laws pair is a valid translation match. The other three pairs in the fetch plan are either volume mismatches or have poor section overlap.

### 🚫 LaBSE-Blocked Sources (Coordinator Confirmed)

Per coordinator message, these are **intentionally parked** pending LaBSE infrastructure:
- wiki-haw-en-langlinks (53 probed, 3000-5000 expected)
- sanitary-instructions-1881 (200-800 expected)
- wikimedia-cx expansion (1000-3000 expected, but requires LaBSE alignment)
- OPUS-wikimedia subset (275 rows mined, require LaBSE score gate)

**Coordinator quote:** "LaBSE-blocked work is parked. Focus on non-LaBSE-blocked, non-Bible, deterministic-alignment sources."

### 📊 Remaining Deterministic Sources

**Evaluated and exhausted:**
- tatoeba: ✅ Full coverage (121 rows)
- weblate: ✅ Full coverage (107 rows across 5 components; no more permissive-license projects)
- andrews/kaikki: ✅ Full coverage
- HK Statutes 1869: ❌ Blocked (content mismatch)
- HK Statutes 1859: ⚠️  Low yield (<50 rows), not cost-effective

**Not evaluated (eval-only or rights-blocked):**
- global-piqa-parallel-haw: eval-only per fetch plan
- taxi1500-haw: eval-only per fetch plan
- pukui-elbert-andrews-examples: modern edition rights-encumbered

## Conclusion

**The 40k target cannot be reached via deterministic-alignment sources alone without:**
1. LaBSE/LASER infrastructure for comparable-aligned sources (wiki langlinks, sanitary instructions, OPUS-wikimedia), OR
2. Synthetic BT/FT generation from Stage-1 monolingual, OR
3. Revising the Bible cap policy (currently 30% of non-Bible)

**Current bottleneck:** Non-Bible deterministic pool is exhausted at ~6,638 candidates. Lifting this requires unblocking LaBSE lanes (coordinator's call) or synthetic generation (blocked on Stage-1-merged checkpoint + Rusty quality floor).

## Recommendations

1. **Coordinator:** Decide on LaBSE bring-up priority vs synthetic generation
2. **Linus:** Promote existing review-pending candidates (OPUS 487, others) to increase non-Bible manifest count
3. **Rusty:** If LaBSE infra is ready, prioritize wiki-langlinks (highest yield, smallest embedding budget)
4. **Frank (self):** Document HK Statutes 1869/1859 blockers in fetch plan; no further action until LaBSE or synthetic lanes open

## Artifacts Created

- This decision note
- Updated `.squad/agents/frank/history.md`
- No new candidate files (all viable deterministic sources exhausted)


---

# Frank — Stage 2 source verdicts (2026-05-02)

## Decision summary

Processed the remaining Stage-2 source lanes to concrete receipts/verdicts. No train-ready rows were added; no manifest was mutated.

## Candidate outputs

- `data/stage2/candidates/opus_haw_subsets.jsonl` — 487 review-pending rows, 0 train-ready. Rows by corpus: Tatoeba 93, QED 16, Ubuntu 4, wikimedia 374. QED is language-mismatched; Ubuntu is effectively unusable/misaligned; Tatoeba is duplicate-heavy; wikimedia is the only non-trivial contributor but remains review-pending pending rights/dedup/LaBSE policy.
- `data/stage2/candidates/tatoeba.jsonl` — pre-existing 121 rows; dry-run verified upstream URLs reachable. Not refreshed in this pass.

## Hard rejects / blocked lanes

- `nllb-mined-haw-eng`: hard reject for current endpoint. `allenai/nllb` has no `haw_Latn`; datasets-server haw configs 404. Report: `data/stage2/reports/nllb_mined_haw_eng_probe_report.json`.
- `wikisource-haw-en-comparable`: plan endpoint invalid. `https://haw.wikisource.org/w/api.php` redirects to multilingual `wikisource.org` HTML, not a haw-specific API JSON endpoint. Report: `data/stage2/reports/wikisource_haw_en_comparable_probe_report.json`.
- `bt-stage1-monolingual-haw`: no generation today. Blocked on Stage-1-merged checkpoint, BT generator script, Rusty quality floor, and synthetic cap enforcement. Report: `data/stage2/reports/bt_stage1_monolingual_haw_blocker_report.json`.

## LaBSE/LASER blocked, receipts preserved

- `wiki-haw-en-langlinks`: 53 haw↔en page-revision receipts from 60 hawwiki titles. No candidates. Report: `data/stage2/reports/wiki_haw_en_langlinks_probe_report.json`.
- `sanitary-instructions-1881`: EN/HAW IA receipts refreshed. No deterministic paragraph/sentence extraction; no candidates. Report: `data/stage2/reports/sanitary_instructions_1881_probe_report.json`.

## Excluded/deferred entries

Plan statuses were made concrete: JW300/social media are do-not-fetch rights exclusions; general web crawls are out-of-scope for Stage-2 parallel; hard-escalate cultural categories remain excluded pending cultural review; ungrounded LLM Hawaiian dialogues remain excluded; FLORES+/Belebele/WMT24++ remain verified-absent for Hawaiian.

## Linus handoff

Use `data/stage2/reports/stage2_source_lane_inventory_20260502.json` for command receipts and lane status. Next high-leverage unblocker is an embedding pre-pass (LaBSE preferred) before wiki langlinks, Sanitary Instructions, or OPUS-wikimedia can contribute honestly.


---

# Ulukau Nupepa Fetch BLOCKED — HTTP 403 Forbidden

**Author:** Frank (Hawaiian Data Collector)  
**Date:** 2026-05-03  
**Status:** BLOCKED — fetch cannot proceed  

---

## Summary

Attempted to execute a dry-run test of the Ulukau Nupepa fetch adapter (`data-sources/ulukau-nupepa/fetch.py --dry-run`). The fetch immediately failed with:

```
urllib.error.HTTPError: HTTP Error 403: Forbidden
```

**URL attempted:** `https://www.nupepa.org/?a=cl&cl=CL1&e=-------haw-20--1--txt-txIN%7CtxNU%7CtxTR%7CtxTI---------`

**User-Agent sent:** `ideal-spoon/0.1.0 (frank ulukau-nupepa adapter; contact via github.com/yashasg/ideal-spoon; prototype-only, no public release)`

---

## Interpretation

The 403 Forbidden response indicates one of:

1. **User-Agent filtering:** The site may block automated requests (scrapers, bots) based on User-Agent header.
2. **Referrer requirement:** The site may require a `Referer` header indicating the request came from the nupepa.org site itself.
3. **Rate limiting:** The site may have imposed a block after detecting the initial request pattern.
4. **Robots.txt or site policy change:** The site may have updated its policy to forbid automated access (need to check `robots.txt`).
5. **Session/cookie requirement:** The site may require a session cookie or CSRF token (though the discovery probe via CDP did not suggest this).

---

## Discovery probe context

The discovery probe (2026-05-03, captured under `data/raw/ulukau-discovery/`) was conducted via **Chrome DevTools Protocol (CDP)** with a signed-in browser tab. That probe succeeded without 403 errors. Key differences:

* Discovery probe: Chrome browser, full JS rendering, session cookies, standard User-Agent.
* Fetch adapter: Python urllib, no JS, no cookies, custom User-Agent.

This suggests the site may require:
* A browser-like User-Agent, OR
* A Referer header, OR
* Session cookies / CSRF tokens.

---

## Immediate action: Check robots.txt

Before proceeding further, check `https://www.nupepa.org/robots.txt` to confirm whether automated access is explicitly forbidden.

If `robots.txt` disallows automated crawling, the fetch adapter is **NOT PERMITTED** under the non-negotiables ("If anything in your fetch loop produces evidence the rights posture is more restrictive than the ToS implies (e.g., robots.txt forbids it, login-walled content, rate-limit responses), STOP and document").

---

## Next steps (conditional on robots.txt)

### If robots.txt ALLOWS crawling:

Attempt workarounds:
1. **Browser-like User-Agent:** Change User-Agent to mimic Chrome/Firefox.
2. **Add Referer header:** Set `Referer: https://www.nupepa.org/` on all requests.
3. **CDP-based fetch:** Reuse the `cdp.py` helper from the discovery probe (requires Chrome running with `--remote-debugging-port=9222`).

### If robots.txt FORBIDS crawling:

STOP immediately. Document in rights memo and report to Linus. The Ulukau ToS "personal use" exception may NOT extend to automated bulk fetching if `robots.txt` explicitly disallows it.

---

## Recommendation

1. **Check robots.txt NOW** (see next inbox note: `frank-ulukau-robots-txt-check.md`).
2. **Do not proceed with fetch** until robots.txt is confirmed to allow access.
3. **If blocked:** Report to Linus that Ulukau Nupepa is NOT accessible for automated fetching, and the Stage-2 yield from this source is **ZERO** (not hundreds, not thousands — zero).
4. **If allowed:** Attempt CDP-based fetch (browser automation) as fallback, since that succeeded during discovery.

---

**End of note.**


---

# Ulukau Nupepa — Cloudflare Bot Protection Blocks HTTP Fetch

**Author:** Frank (Hawaiian Data Collector)  
**Date:** 2026-05-03  
**Status:** CRITICAL — HTTP fetch impossible; CDP workaround required  

---

## Finding

Nupepa.org is protected by **Cloudflare's JavaScript challenge** ("Just a moment..."). Any HTTP request (curl, Python urllib) receives a Cloudflare interstitial page requiring JavaScript execution to prove it's a real browser.

**Evidence:**
* Homepage (`https://www.nupepa.org/`) returns 403 with Cloudflare JS challenge.
* Robots.txt (`https://www.nupepa.org/robots.txt`) also returns 403 with Cloudflare JS challenge.
* User-Agent variation (browser-like vs. bot-like) makes NO difference — Cloudflare blocks all non-browser requests.

**Response HTML snippet:**
```html
<!DOCTYPE html><html lang="en-US"><head><title>Just a moment...</title>
<meta name="robots" content="noindex,nofollow">
<meta http-equiv="refresh" content="360">
...
<noscript>Enable JavaScript and cookies to continue</noscript>
```

---

## Implications

### 1. HTTP fetch (urllib, requests, curl) is NOT VIABLE

The Python `urllib`-based fetch adapter (`data-sources/ulukau-nupepa/fetch.py`) **cannot work** without a JavaScript runtime. Cloudflare will block every request with a 403 or challenge page.

### 2. CDP-based fetch (browser automation) IS VIABLE

The discovery probe (2026-05-03, `data/raw/ulukau-discovery/`) succeeded by using **Chrome DevTools Protocol (CDP)** with a real Chrome browser tab. This bypasses Cloudflare because:
* Real browser (Chrome) with full JS runtime.
* Cloudflare's challenge is automatically solved by the browser.
* Session cookies persist across requests.

**Evidence:** The discovery probe fetched multiple pages (title browse, article indexes, AJAX endpoints) without any 403 errors, using the same endpoints the HTTP adapter attempted.

---

## Recommended approach: CDP-based adapter

Rewrite the fetch adapter to use the existing `cdp.py` helper (`data/raw/ulukau-discovery/cdp.py`). This requires:

1. **Chrome running with remote debugging:** `google-chrome --remote-debugging-port=9222 --user-data-dir=~/.copilot/chrome-profile-ulukau`
2. **CDP client in Python:** Reuse `cdp.py` from discovery probe.
3. **Fetch protocol:**
   * CDP → navigate to title browse URL → extract HTML → parse paper codes.
   * For each paper: CDP → navigate to article index → extract HTML → parse article OIDs.
   * For each article: CDP → navigate to `getUserTranslation` endpoint → extract XML → check if non-empty.
   * If translation exists: CDP → navigate to `getSectionText` endpoint → extract XML.
   * Store results as before.

### Pros:
* Bypasses Cloudflare (browser-native JS execution).
* Same approach as discovery probe (proven to work).
* No Cloudflare CAPTCHA solving required (browser handles it automatically).

### Cons:
* Requires Chrome running with `--remote-debugging-port=9222` (manual setup step).
* Slower than HTTP (full page loads, not just AJAX).
* Heavier resource footprint (browser memory/CPU).

---

## Alternative: Playwright / Selenium

If CDP is too brittle, use Playwright or Selenium (headless browser automation). Same principle: real browser solves Cloudflare challenge automatically.

**However:** CDP is lighter-weight and already proven to work for this site (discovery probe). Recommend sticking with CDP unless it fails.

---

## User authorization still required

Even with a working CDP-based fetcher, the rights review (`frank-ulukau-rights-memo.md`) still applies:
* `prototype_only=True`, `release_eligible=False` always.
* No release of weights/data/demo.
* Attribution required.
* Linus must confirm rights approval before executing any fetch.

---

## Next steps

1. **Rewrite fetch adapter** to use CDP instead of urllib (see `data-raw/ulukau-discovery/cdp.py` for helper).
2. **Document CDP setup** in README (Chrome with `--remote-debugging-port=9222`).
3. **Test dry-run** with CDP-based fetcher.
4. **If successful:** Await Linus rights approval before executing full fetch.
5. **If Cloudflare blocks CDP too:** Report to Linus that Ulukau Nupepa is NOT accessible, yield is ZERO.

---

## Honest yield assessment (unchanged)

Even if CDP-based fetch succeeds:
* Expected parallel yield: hundreds to low-thousands (user translations are rare).
* This is NOT a 31k-row solution for Stage 2.
* Primary value: ~69k pages of Hawaiian-monolingual text (Stage 1 opportunity, separate task).

---

**End of note.**


---

# Ulukau Nupepa Stage-2 Attempt — Cloudflare Blocked, ZERO Yield

**Author:** Frank (Hawaiian Data Collector)  
**Date:** 2026-05-03  
**Status:** BLOCKED — cannot proceed without CDP-based workaround  
**Estimated SFT addition:** **ZERO rows** (Cloudflare blocks HTTP fetch)  
**Path to 40k:** Gap remains ~31k rows (8,572 current → 40k target)  

---

## Summary (honest assessment)

Attempted to build a Stage-2 parallel data adapter for Ulukau Hawaiian Newspaper Collection (`www.nupepa.org`) to harvest human-contributed English translations of Hawaiian newspaper articles (1834-1948).

**Critical blocker:** Site is protected by **Cloudflare's JavaScript challenge** ("Just a moment..."). All HTTP requests (curl, Python urllib, requests) are blocked with 403 Forbidden. This makes the standard HTTP-based fetch adapter **non-viable**.

**Workaround:** CDP-based fetch (Chrome DevTools Protocol with real browser) is required. This was proven to work during the discovery probe (2026-05-03, `data/raw/ulukau-discovery/`), but requires manual Chrome setup (`--remote-debugging-port=9222`) and is significantly slower/heavier than HTTP.

**Current status:** Adapter infrastructure is built (registry, README, fetch.py, candidate emitter, LaBSE scorer integration), but **ZERO articles have been fetched** due to Cloudflare block.

**Recommendation:** Do NOT pursue this source further unless:
1. Linus confirms rights approval (see rights memo: `frank-ulukau-rights-memo.md`), AND
2. CDP-based fetch is acceptable (requires Chrome automation, 10–30x slower than HTTP), AND
3. Expected yield (hundreds to low-thousands of pairs) justifies the effort.

---

## Deliverables (infrastructure built, fetch blocked)

### 1. Rights memo
**File:** `.squad/decisions/inbox/frank-ulukau-rights-memo.md`

* Ulukau Terms: "All Rights Reserved", personal-use only, no commercial use, no copying.
* User authorization: explicit, this turn, prototype-only-never-released.
* Project posture alignment: private prototype, no release (matches `.squad/decisions.md`).
* Recommendation: APPROVE for prototype-only ingest IF Linus confirms.
* Tagging: `prototype_only=True`, `release_eligible=False`, `license_observed=ulukau_personal_use_only` always.
* Attribution requirement: Ka Haka ʻUla O Keʻelikōlani + ALU LIKE canonical string.

### 2. Adapter infrastructure
**Files:**
* `data-sources/ulukau-nupepa/source_registry.json` — endpoint catalog, OID grammar, alignment defaults.
* `data-sources/ulukau-nupepa/README.md` — ToS snapshot reference, fetch protocol, safeguards.
* `data-sources/ulukau-nupepa/fetch.py` — HTTP-based fetcher (BLOCKED by Cloudflare; needs CDP rewrite).

**Fetch protocol (designed, not executed):**
* Triple-gated `--execute --confirm-edition --tos-snapshot`.
* Fast-path: query `getUserTranslation` endpoint FIRST; only fetch `getSectionText` if translation exists.
* Cap: 5,000 articles probed or 30 min wallclock, whichever comes first.
* Polite throttling: ≥1.0s between requests.
* Resume cursor: persist `(paper_code, last_article_oid)` to resume after interruption.

**Status:** Fetch script is complete but **cannot execute** due to Cloudflare block. CDP-based rewrite required (see `frank-ulukau-cloudflare-block.md`).

### 3. Candidate emitter
**File:** `scripts/339_build_ulukau_nupepa_candidates.py`

* Reads raw fetch output (`data/raw/ulukau-nupepa/20260502/articles.jsonl`).
* Paragraph-level alignment if `<p>` counts match; else article-level.
* ʻOkina U+02BB canonicalization (Hawaiian text); ASCII apostrophe U+0027 (English).
* `compute_pair_hash` from `scripts/320_build_stage2_manifest.py` for dedup.
* Tags: `alignment_type='comparable-aligned'`, `alignment_method='ulukau_user_translation'`, `prototype_only=True`, `register='newspaper'`, `era='kingdom'/'republic-early-territory'/'territory'` (depending on issue date).
* Outputs: `data/stage2/candidates/ulukau_nupepa.jsonl`.

**Status:** Script is complete and tested (syntax), but **NO RAW INPUT** exists (fetch blocked).

### 4. LaBSE scoring integration
**Command:** `python scripts/336_score_comparable_with_labse.py --source ulukau_nupepa --execute`

* Threshold: 0.75 (default; human translations).
* Output: `data/stage2/_scored/ulukau_nupepa.labse.jsonl` + summary.
* Verdict splits: accept (≥0.75) / review (0.55–0.75) / reject (<0.55).

**Status:** Integration is ready, but **NO CANDIDATES** exist to score (fetch blocked).

### 5. Cloudflare block notes
**Files:**
* `.squad/decisions/inbox/frank-ulukau-403-blocked.md` — initial 403 Forbidden finding.
* `.squad/decisions/inbox/frank-ulukau-cloudflare-block.md` — Cloudflare JS challenge analysis + CDP workaround recommendation.

**Key finding:** CDP-based fetch (Chrome automation) is the ONLY viable approach. HTTP fetch is permanently blocked.

### 6. Stage-1 monolingual opportunity note
**File:** `.squad/decisions/inbox/frank-ulukau-stage1-monolingual.md`

* ~69k pages of Hawaiian-monolingual newspaper text (1834-1948).
* Estimated token volume: 27M–31M tokens (post-dedup).
* Register: newspaper (mixed: news, opinion, literature, government notices, ads).
* Era: Kingdom (1834–1893), Republic/early Territory (1894–1920), Territory (1921–1948).
* Quality concerns: OCR errors, ʻokina/kahakō handling, era-specific orthography.
* Recommendation: future Stage-1 augmentation task (NOT Stage-2).

---

## Articles probed: 0 (fetch blocked)

**Cloudflare block:** All HTTP requests return 403 Forbidden or Cloudflare JS challenge page. Cannot proceed without CDP-based fetcher.

---

## Articles with user translations: UNKNOWN (cannot measure)

Expected: low hundreds to low-thousands (user translations are rare on nupepa.org, per discovery probe).

Discovery probe (2026-05-03) sampled several articles and found **ZERO non-empty user translations**. The `getUserTranslation` endpoint exists but is consistently empty.

---

## Pairs emitted: 0 (no raw fetch)

**By paper:** N/A  
**By era:** N/A  

---

## LaBSE splits: N/A (no candidates)

**Accept (≥0.75):** N/A  
**Review (0.55–0.75):** N/A  
**Reject (<0.55):** N/A  

---

## Estimated SFT row addition: ZERO

Even if CDP-based fetch succeeds and user translations are found:
* Expected parallel yield: **hundreds to low-thousands** (not 31k).
* LaBSE accept rate (assuming 0.75 threshold on human translations): ~60–80% (optimistic).
* Estimated SFT addition (accepted pairs × 2 directions): **200–2,000 rows** (order-of-magnitude guess).

**Current State-2 SFT:** 8,572 rows (after Linus Round 2).  
**Gap to 40k:** ~31,000 rows.  
**Ulukau Nupepa contribution (if unblocked):** ~200–2,000 rows (0.6–6% of gap).

**Conclusion:** Ulukau Nupepa is NOT a 31k-row solution. It is a low-yield source that does NOT justify the CDP automation effort unless Linus has a specific reason to prioritize newspaper-era Hawaiian.

---

## Path to 40k: Gap remains ~31k rows

**Sources considered so far:**
* Tatoeba: ~100–600 pairs (done; minimal yield).
* Bible (1839): ~30k verses (capped at 30% of Stage-2 tokens; exhausted).
* HK 1897 statutes: ~6k sections (capped at 15%; exhausted).
* Ulukau Nupepa: ZERO rows (Cloudflare blocked; expected max 2k even if unblocked).

**Remaining options (for Linus to consider):**
1. **NLLB-mined / synthetic BT:** Use the 32,756 re-promotion budget from `stage2_final_review_verdicts_20260501.json` (Bible + HK overflow rows marked `excluded-policy-cap`). This was Frank's next planned task before the Ulukau detour.
2. **Wikisource Hawaiian-English comparable:** Investigate `wikisource-haw-en-comparable` (already in `data-sources/` but not yet fully mined).
3. **OPUS subsets:** Check `data-sources/opus-haw-subsets/` for additional parallel data (if not already exhausted).
4. **Hoʻoilina bilingual articles:** Fix the HTML entity bugs in `hooilina.jsonl` (per Basher's Ulukau validation; see `.squad/decisions.md` §Basher implementation complete).
5. **Manual curation:** Hire Hawaiian-literate annotators to create 10k–20k high-quality parallel pairs (expensive, slow, but guaranteed yield).

**Recommendation:** Do NOT spend CDP automation effort on Ulukau Nupepa. Focus on NLLB-mined / synthetic BT (option #1) or Hoʻoilina fix (option #4), both of which have higher yield potential.

---

## Recommended verdict policy

Since ZERO candidates exist, no verdict policy is applicable. If CDP-based fetch is pursued and candidates are generated:

* **Accept (LaBSE ≥0.75):** Promote to train pool (but tag `prototype_only=True`, never dev/test).
* **Review (0.55–0.75):** Hold in review-pending (human translations should score high; review verdicts suggest low-quality OCR or misaligned pairs).
* **Reject (<0.55):** Drop (alignment failure; OCR errors; not parallel).

**Special constraint:** Ulukau rows are NEVER dev/test eligible (ToS forbids redistribution). They may enter train pool IF LaBSE-accepted, but remain `prototype_only=True` always.

---

## Open questions for Linus

1. **Rights approval:** Are Ulukau ToS ("personal use only, no copying to other websites") acceptable for prototype-only ingest, given the project's private-prototype policy? (See `frank-ulukau-rights-memo.md`.)
2. **CDP effort justification:** Is the expected yield (200–2,000 rows) worth the CDP automation setup + 10–30x slower wallclock time vs. HTTP?
3. **Priority vs. NLLB-mined:** Should Frank prioritize NLLB-mined / synthetic BT (32k re-promotion budget) over Ulukau Nupepa (200–2k max yield)?

---

## Next steps (conditional on Linus decision)

### If Linus approves Ulukau AND CDP-based fetch:
1. **Rewrite fetch.py** to use CDP (reuse `data/raw/ulukau-discovery/cdp.py` helper).
2. **Test dry-run** with CDP-based fetcher (Chrome with `--remote-debugging-port=9222`).
3. **Execute first pull** (cap at 5,000 articles probed or 30 min wallclock).
4. **Measure yield** (articles with non-empty translations).
5. **Build candidates** (`scripts/339_build_ulukau_nupepa_candidates.py --execute`).
6. **LaBSE score** (`scripts/336_score_comparable_with_labse.py --source ulukau_nupepa --execute`).
7. **Report final yield** (LaBSE splits, SFT row addition).

### If Linus DECLINES Ulukau:
1. **Archive adapter infrastructure** (mark as blocked, do not delete).
2. **Move to NLLB-mined / synthetic BT** (Frank's next planned task).
3. **Update path-to-40k assessment** (remove Ulukau from candidate sources).

---

**End of memo.**


---

# Ulukau Nupepa.org Rights Review — Prototype-Only Authorization

**Author:** Frank (Hawaiian Data Collector)  
**Date:** 2026-05-03  
**Status:** RECOMMENDATION — awaiting Linus confirmation  
**Applies to:** Ulukau Hawaiian Newspaper Collection (`www.nupepa.org`)  
**User authorization:** Explicit, this turn, prototype-only-never-released  

---

## 1. Source description

[Ulukau](https://ulukau.org/) is an umbrella portal for Hawaiian-language digital collections, operated by Ka Haka ʻUla O Keʻelikōlani (UH Hilo College of Hawaiian Language) and ALU LIKE, Inc. The Nupepa collection (`www.nupepa.org`) contains ~69,000 OCR'd pages from Hawaiian-language newspapers published 1834–1948.

The collection runs on Greenstone/Veridian digital library software (confirmed by footer attribution to NZDL Niupepa project) and exposes a public AJAX API for article OCR text and a small fraction of human-contributed English translations.

**Discovery snapshot:** `data/raw/ulukau-discovery/` (captured 2026-05-03, gitignored).

---

## 2. Ulukau Terms of Use (paraphrased from `data/raw/ulukau-discovery/08-copyright.txt`)

Updated August 21, 2018. Key excerpts:

* **Copyright owners:** Ka Haka ʻUla O Keʻelikōlani College of Hawaiian Language and ALU LIKE, Inc. (for Ulukau site); other collections in the Ulukau library are owned as shown on their sites.
* **"All Rights Reserved."**
* **Personal-use permitted:** "This website may be fully utilized for personal use."
* **Commercial use prohibited:** "...but may not be used for commercial purposes."
* **No copying to other websites:** "...or copied to any other website."
* **User responsibility for fair use:** "It is the user's obligation to determine and satisfy copyright or other use restrictions when publishing or otherwise distributing materials found on this website. ... Users must make their own assessments of rights in light of their intended use."
* **Linking permitted:** Webmasters may link to the site (but not frame it), provided the link does not suggest endorsement or use content for commercial purposes.
* **No warranty:** Standard disclaimer re accuracy/completeness.

Full text: `data/raw/ulukau-discovery/08-copyright.txt` (gitignored).

---

## 3. User authorization (this turn)

User provided explicit authorization for this turn:

> "Ulukau/nupepa.org rights review + private prototype-only pull authorized. The pull stays under `data/raw/` (gitignored). Never released. Personal-use only consistent with Ulukau ToS."

---

## 4. Project posture alignment

Per `.squad/decisions.md` (final review verdict policy, merged 2026-05-02):

* Project is **private/prototype-only**: no release of weights, data, or demo.
* All data artifacts under `data/` are **gitignored** and never committed.
* Stage-2 manifest rows carry `prototype_only=True`, `release_eligible=False`.

This aligns with Ulukau's "personal use only, no copying to other websites" requirement, PROVIDED the prototype stays internal and is never deployed or shared.

---

## 5. Proposed ingest protocol

### 5.1 Storage location

`data/raw/ulukau-nupepa/20260502/` (gitignored, timestamped snapshot).

### 5.2 Adapter tagging

Every manifest row MUST carry:

| Field | Value |
|-------|-------|
| `prototype_only` | `True` |
| `release_eligible` | `False` |
| `license_observed` | `"ulukau_personal_use_only"` |
| `source` | `"ulukau-nupepa"` |
| `attribution_required` | `"Ka Haka ʻUla O Keʻelikōlani College of Hawaiian Language, University of Hawaiʻi at Hilo, and ALU LIKE, Inc. via Ulukau: The Hawaiian Electronic Library (www.nupepa.org)"` |

Rows are **NEVER** eligible for dev/test splits, per docs/data-pipeline.md policy (dev/test require unambiguous redistribution rights; Ulukau ToS forbids it). They may enter the `review-pending` pool for internal prototype training IF LaBSE scores are acceptable, but remain tagged `prototype_only=True` always.

### 5.3 Adapter safeguards

* **Triple-gated `--execute`:** `--execute --confirm-edition --tos-snapshot` required.
* **Polite throttling:** ≥1s between requests.
* **Fast-path skip:** Query `getUserTranslation` endpoint FIRST; only fetch `getSectionText` (Hawaiian OCR) if translation is non-empty. This avoids pulling all 69k pages when the vast majority lack English translations.
* **Resume cursor:** Persist progress so a partial run can resume without re-fetching.

---

## 6. Expected yield (HONEST assessment)

From the discovery snapshot:

* ~69,000 OCR pages total (Hawaiian-monolingual, primarily).
* KNK (Ka Nupepa Kuokoa) alone reports 3,316 articles; extrapolating across all 50+ papers, total article count is likely 30k–80k.
* **User translations:** The `getUserTranslation` endpoint was present on the sample article checked, but the response was empty (expected; user translations are a community-contributed feature and rare).
* **Realistic parallel yield:** Low thousands at best, possibly only hundreds of article-level parallel pairs. The discovery probe did NOT encounter a single non-empty translation in the sample checked. This source is NOT a 31k-row solution for Stage 2.

**Primary value:** ~69k pages of **Stage 1 monolingual Hawaiian** newspaper text (1834–1948, covering Kingdom, Republic, Territory eras) — high historical value, but a different pipeline (Stage 1 augmentation, separate task).

---

## 7. Bilingual government proclamations (secondary parallel source)

Some issues contain embedded bilingual government notices / proclamations / court announcements (Hawaiian + English side-by-side in the same issue). These were common in the Kingdom/Republic/Territory eras. However:

* Identifying them requires either:
  * Manual article tagging (not scalable),
  * OCR-level layout analysis (newspaper columns are interleaved), or
  * Heuristic detection (article title patterns like "PALAPALA HOIKE", "PROCLAMATION").
* This is a **future-work** opportunity; it is NOT in scope for this initial pull, which targets only the `getUserTranslation` endpoint.

---

## 8. Recommendation

**APPROVE** for prototype-only ingest under the following conditions:

1. **Adapter enforces `prototype_only=True`, `release_eligible=False` ALWAYS** — no exceptions, no manual overrides.
2. **Attribution requirement:** Every manifest row must carry the canonical Ulukau attribution string (see §5.2).
3. **Storage:** Raw fetch stays under `data/raw/ulukau-nupepa/20260502/` (gitignored).
4. **Tag:** `license_observed=ulukau_personal_use_only` on every row for future audits.
5. **Dev/test exclusion:** Rows are train-pool-only (if LaBSE-accepted) or review-pending (if scores are low); never dev/test.
6. **Stop condition:** If fetch produces evidence of stricter restrictions (robots.txt forbids, rate-limit responses, login-wall), STOP immediately and document.

### Open question for Linus to confirm:

Are these terms acceptable as "rights_review_required → approved-for-prototype" given the team's private-prototype policy? Ulukau ToS says "personal use" (permitted) but "no copying to other websites" (which a public release would violate). As long as the prototype stays internal, this appears consistent. Linus should confirm before any pull is executed.

---

## 9. Next steps (if approved)

1. **Build adapter:** `data-sources/ulukau-nupepa/` (registry + fetch.py + README).
2. **Execute first pull:** Cap at 5,000 articles probed (or 30 min wallclock, whichever comes first).
3. **Measure yield:** Count articles with non-empty translations.
4. **Build candidates:** `scripts/339_build_ulukau_nupepa_candidates.py` → `data/stage2/candidates/ulukau_nupepa.jsonl`.
5. **LaBSE score:** `scripts/336_score_comparable_with_labse.py --source ulukau_nupepa --execute`.
6. **Report to Linus:** LaBSE splits, estimated SFT row addition, updated path-to-40k assessment.

---

## 10. Stage 1 monolingual opportunity (deferred)

The ~69k pages of Hawaiian OCR are **high-value Stage 1 data** (pre-training / augmentation). Recommend a future task to:

* Fetch all `getSectionText` responses (without translation requirement).
* Clean OCR errors, canonicalize ʻokina/kahakō.
* Deduplicate against existing Stage 1 corpus.
* Estimate token volume after dedup.
* Assess quality (OCR error rate, era spread, diacritic handling).

This is OUT OF SCOPE for the current Stage-2 task (path to 40k SFT rows). Note it in a separate inbox memo.

---

**End of memo.**


---

# Ulukau Stage 1 Monolingual Opportunity — Deferred

**Author:** Frank (Hawaiian Data Collector)  
**Date:** 2026-05-03  
**Status:** FUTURE-WORK — Stage 1 augmentation opportunity, not Stage 2  
**Applies to:** ~69,000 pages of Hawaiian-monolingual newspaper text (1834-1948)  

---

## Summary

The Ulukau Hawaiian Newspaper Collection (`www.nupepa.org`) contains **~69,000 OCR'd pages** of Hawaiian-language newspapers spanning 1834–1948. This covers Kingdom, Republic, and Territory eras — historically significant periods for Hawaiian language evolution.

**Primary finding:** The vast majority of this content is **Hawaiian-monolingual** (no English translations). It is NOT a Stage-2 parallel data source (Stage-2 target: 40k SFT rows). Instead, it is a high-value **Stage-1 augmentation opportunity** for pre-training or continued pre-training.

---

## Collection scale (from discovery probe)

| Metric | Value |
|--------|-------|
| Total OCR'd pages | ~69,000 |
| Automatic OCR coverage | All ~69,000 pages (article text + human-corrected headlines) |
| Human-transcribed page text | ~21,000 pages (subset; higher quality) |
| User-contributed English translations | Rare (low hundreds to low thousands at best) |
| Time span | 1834–1948 (114 years) |
| Register | Newspaper (mixed: news, opinion, literature, government notices, ads) |

**Sample paper:** Ka Nupepa Kuokoa (KNK) alone reports **3,316 articles** in its title index. Extrapolating across 50+ papers, total article count is 30k–80k.

---

## Token volume estimate (rough)

Assumptions:
* ~69,000 pages.
* Average OCR page length: 500–1,000 tokens (newspaper columns, mixed formatting).
* Conservative: 500 tokens/page average.

**Gross token count:** 69,000 × 500 = **34.5M tokens** (before dedup).

After deduplication (remove duplicates from existing Stage-1 corpus, handle OCR errors, remove English loan words / ads):
* Estimated dedup rate: 10–20% (newspapers reprint content, ads repeat).
* **Net token count:** ~27M–31M tokens (post-dedup estimate).

For context:
* Current Stage-1 Hawaiian corpus (after Linus Round 2): unknown size (check `data/stage1/manifest.json`).
* 30M tokens is roughly 5–10× the size of a typical monolingual Hawaiian corpus (e.g., Bible ~300k tokens, HK ~1M tokens).

---

## Quality concerns

### OCR error rate
* Automatic OCR (not human-transcribed for most pages).
* ʻOkina/kahakō handling: OCR may use ASCII apostrophes, omit macrons, or substitute characters.
* Column interleaving: Newspapers have multi-column layouts; OCR may merge columns incorrectly.
* Era-specific orthography: 19th-century Hawaiian spelling differs from modern conventions (e.g., `v` vs. `w`, diacritic placement).

**Mitigation:**
* Canonicalize ʻokina to U+02BB.
* Heuristic kahakō restoration (if missing) via dictionary lookup or morphological analysis.
* Filter out English loan words / ads (common in late Territory-era papers).
* Quality-gate on character-level entropy (reject garbled OCR).

### Era spread
* 1834–1948 is a wide time span covering:
  * Kingdom era (1834–1893): classical Hawaiian orthography.
  * Republic / early Territory (1894–1920s): transitional orthography, mixed Hawaiian-English.
  * Late Territory (1930s–1948): declining Hawaiian usage, heavy English influence.
* Later eras may have lower Hawaiian purity (code-switching, English ads).

**Recommendation:** Stratify by era; prioritize Kingdom/early Republic (1834–1900) for higher Hawaiian purity.

### Human-transcribed subset
* ~21,000 pages have human-transcribed "page text" (higher quality than automatic OCR).
* **Recommendation:** Fetch human-transcribed pages FIRST (if endpoint supports filtering); fallback to automatic OCR for remainder.

---

## Fetch protocol (for Stage 1)

### Difference from Stage-2 adapter
* **Stage 2:** Fast-path skip (only fetch articles WITH English translations).
* **Stage 1:** Fetch ALL `getSectionText` (Hawaiian OCR) regardless of translation status.

### Steps
1. **Title browse** → parse paper codes.
2. **Article index** → parse article OIDs.
3. **getSectionText** (`?a=da&command=getSectionText&d={oid}&f=AJAX`) → fetch Hawaiian OCR for ALL articles.
4. **Store** `(oid, haw_text_html, issue_date, paper_code)` tuples.
5. **Dedup:** Hash-based dedup against existing Stage-1 corpus.
6. **Clean:** Canonicalize ʻokina/kahakō, filter English ads, reject garbled OCR.

### Cloudflare blocker applies
Same as Stage-2: HTTP fetch is blocked by Cloudflare; CDP-based fetch (browser automation) required. See `.squad/decisions/inbox/frank-ulukau-cloudflare-block.md`.

---

## Recommended priority (future task)

### High priority IF:
* Stage-1 Hawaiian corpus is small (<5M tokens).
* Pre-training budget allows for another 30M tokens.
* Kingdom-era newspapers (1834–1900) can be isolated (higher quality, purer Hawaiian).

### Lower priority IF:
* Stage-1 corpus already has sufficient monolingual Hawaiian (>20M tokens).
* OCR quality is too low (requires manual correction).
* Cloudflare blocker makes fetching too costly (CDP setup + wallclock time).

---

## Out of scope for Stage 2

This is NOT part of the path-to-40k Stage-2 SFT rows. The Stage-2 gap (31k rows) cannot be filled by monolingual Hawaiian text. Parallel yield from user translations is estimated at hundreds to low-thousands at best.

**Recommendation:** Note this as a future Stage-1 augmentation task; do NOT block Stage-2 work on this.

---

## Next steps (deferred to future task)

1. **Assess current Stage-1 corpus size** (check `data/stage1/manifest.json` or equivalent).
2. **If Stage-1 augmentation is desired:**
   * Reuse CDP-based fetcher (from Stage-2 adapter, modified to fetch ALL articles).
   * Stratify by era (Kingdom > Republic > Territory).
   * Prioritize human-transcribed pages (~21k) over automatic OCR (~48k).
   * Dedup against existing Stage-1 corpus.
   * Quality-gate on OCR error rate / Hawaiian purity.
3. **Estimate cost:** ~69k pages × 1.5s/request (CDP + rate limit) = ~29 hours wallclock. Cap at 10k pages for initial sample.
4. **Report yield:** Token count post-dedup, era distribution, quality metrics.

---

**End of note.**


---

# Hoʻoilina sentence-level pipeline — decision record

**Date:** 2026-05-02
**Owner:** Linus (Data Engineer)
**Status:** Implemented; artifacts regenerated

## Decision

Split Hoʻoilina paragraph/section rows into sentence-level parallel pairs via numbered-paragraph splitting. 35 sentence pairs promoted to prototype train; 68 paragraph rows deferred with new `hooilina-para-deferred` verdict.

## Key design choices

1. **Splitting method:** `\n(?=\d+\.[ \t])` — numbered-paragraph boundaries are the natural atomic translation units in Hoʻoilina articles. Period-delimited sentence splitting was NOT used because sentence counts rarely match between EN and HAW.

2. **Conservative gate:** Only 6 of 68 parent rows have matching EN/HAW paragraph counts. The other 62 are not splittable and stay deferred. No fallback alignment; mismatched rows get `hooilina-para-deferred` verdict.

3. **Quality gates (script 325):** ≥3 tokens/side, ratio [0.5, 2.5], nonhaw_share ≤ 25%, no boilerplate. Result: 35 of 36 candidate pairs emitted (1 too-short rejected).

4. **Prototype-only policy preserved:** All Hoʻoilina rows carry `prototype_only=True`, `release_eligible=False`, `alignment_review_required=True`. SFT emitter requires `--allow-review-required`.

5. **N impact:** Hooilina train tokens (4,129) added to N before fixed-point cap, raising Bible/HK budgets. Bible: 30→72 rows; HK: 5→11 rows. Caps still verified at 29.98% and 15.00%.

6. **script 334 validation:** Hardcoded counts (285/33851) replaced with dynamic structural invariants. Hooilina verdict taxonomy: `train-ready`, `hooilina-para-deferred`, `hooilina-sentence-quality-reject`.

## Final artifact counts

| Metric | Value |
|---|---|
| Train-ready pairs | 368 |
| Hoʻoilina train | 35 (prototype-only) |
| Bible train tokens share | 29.98% |
| HK train tokens share | 15.00% |
| Directional SFT rows | 736 |
| Total artifact rows | 33,886 |

## Files

- `scripts/325_build_hooilina_sentence_candidates.py` (new)
- `scripts/333_build_reviewed_manifest_final_capped.py` (updated)
- `scripts/334_finalize_stage2_review_verdicts.py` (updated)
- `data/stage2/candidates/hooilina_sentences.jsonl`
- `data/stage2/reports/hooilina_sentence_build_report_20260501.json`


---

# Linus — LaBSE Merge Round 2: +296 Accept, 8,572 SFT Rows

**Date:** 2026-05-02  
**Owner:** Linus (Data Engineer)  
**Status:** ✅ Complete  
**Context:** 40k push Round 2 — merge Rusty's LaBSE-scored rows into manifest

---

## Executive Summary

**Merged 296 LaBSE-accepted pairs from 2 scored sources into Stage 2 manifest.** Re-ran cap enforcement chain (332→333→334) and re-emitted SFT. **New SFT ceiling: 8,572 rows (+1,134 from Round 1's 7,438).** Gap to 40k: **31,428 rows**. Path forward: wiki-langlinks extraction (2k–6k) + NLLB mined (16k–30k).

---

## Deliverables Completed

### 1. LaBSE-Scored Row Merge ✅

**Input:**
- `data/stage2/_scored/wikimedia_cx_en_haw.labse.jsonl` (14 rows: 9 accept, 4 review, 1 reject)
- `data/stage2/_scored/opus_haw_subsets.labse.jsonl` (487 rows: 287 accept, 120 review, 80 reject)

**Merge script:** `scripts/337_merge_labse_scored_to_manifest.py`

**Logic:**
- Accept (≥0.75): `split='train'`, `release_eligible=True`, `alignment_method='labse'`
- Review (0.65–0.75): `split='review-pending'`, `release_eligible=False`, `alignment_method='labse'`
- Reject (<0.65): dropped, not added to manifest

**Result:**
- Added 296 accept + 124 review = **420 new rows** to raw manifest
- Dropped 81 reject rows

**Raw manifest after merge:**
- Total: 12,248 rows (was 11,828)
- Train: 4,961 pairs (includes uncapped Bible)
- Review-pending: 7,272

---

### 2. Cap Enforcement Chain (332→333→334) ✅

**Script 332:** `build_reviewed_manifest_cap_corrected.py`
- Applied Rusty review gate (Andrews stay rejected, Hoʻoilina frozen, etc.)
- Bible 1839 pool: 4,431 → 226 kept (cap enforcement)
- Bible 1868 pool: 20,852 → 1,105 kept
- HK 1897 legal cap: 177 kept (570 capped)
- **Output:** 34,271 rows, 2,054 train pairs

**Script 333:** `build_reviewed_manifest_final_capped.py`
- Fixed-point cap enforcement (Bible ≤30%, HK ≤15%, software-l10n ≤15%)
- Bible cap headroom unlocked additional non-Bible rows
- **Output:** 38,131 rows, 4,286 train pairs
- **New sources promoted:**
  - opus-haw-subsets: 562 train (up from 287 raw → benefited from Bible headroom)
  - wikimedia-cx: 11 train (up from 9 raw)

**Script 334:** `finalize_stage2_review_verdicts.py`
- Validation passed
- Final verdict distribution:
  - train-ready: 4,286
  - bible-cap-overflow: 31,042
  - andrews-dictionary-fragment-rejected: 1,194
  - hk-legal-cap-overflow: 735
  - (others): 874
- **Output:** 38,131 rows finalized

---

### 3. SFT Re-Emission ✅

**Command:**
```bash
python3 scripts/330_emit_stage2_sft_jsonl.py --allow-review-required \
    --manifest data/stage2/reviewed_stage2_manifest_finalized_reviews.jsonl
```

**Result:**
- Manifest rows in: 38,131
- Train pairs kept: 4,286
- **SFT rows emitted: 8,572** (4,286 pairs × 2 directions)
- Held-out: 33,830 (bible-cap-overflow, quality-reject, etc.)
- Dev: 15 (Tatoeba frozen dev set)

---

### 4. Tests Passed ✅

**Run:** `python3 code/tests/test_stage2_sft_templates.py -v`
- 25 tests PASSED

**Run:** `python3 code/tests/test_stage2_finalizer.py -v`
- 11 tests PASSED

---

## Counts Before/After

| Metric | Round 1 (Pre-Merge) | Round 2 (Post-Merge) | Delta |
|---|---|---|---|
| **Raw manifest rows** | 11,828 | 12,248 | **+420** |
| **Raw manifest train** | 4,665 | 4,961 | **+296** |
| **Finalized manifest rows** | ~34,000 | 38,131 | ~+4,131 |
| **Finalized train pairs** | 3,719 | 4,286 | **+567** |
| **SFT rows** | 7,438 | 8,572 | **+1,134** |

**Notes:**
- Delta in train pairs (567) > LaBSE-accepted (296) because Bible cap headroom unlocked +271 additional pairs from overflow pools.
- Rusty estimated +770 SFT rows (296 accept × 2 + 89 Bible headroom × 2); actual +1,134 due to dynamic cap adjustments in script 333.

---

## Gap to 40k

**Current:** 8,572 SFT rows  
**Target:** 40,000 SFT rows  
**Gap:** **31,428 rows**

**Path forward (per Rusty's analysis):**
1. **wiki-haw-en-langlinks** (P0): 2k–6k SFT rows (sentence extraction + LaBSE scoring)
2. **NLLB mined @ ≥0.80** (P1): 16k–30k SFT rows (fetch + LaBSE scoring)
3. **Synthetic BT** (P2): Variable yield (depends on Stage-1 checkpoint quality)

**Not blocking:**
- sanitary-instructions-1881: Low yield (<1k rows), requires sentence alignment

---

## Alignment Method Correction

**OPUS-wikimedia mined subset:**
- Prior adapter incorrectly set `alignment_method='tmx-line'` for mined comparable sub-corpus
- LaBSE scoring confirmed policy gap: 59% (220/374) accept rate vs. 100% if truly deterministic
- **Fix applied:** Merged rows now have `alignment_method='labse'` with explicit `labse_score` field
- **Recommendation:** Update OPUS adapter (`scripts/207_fetch_stage2_parallel_raw.py` or equivalent) to mark mined sub-corpora with `alignment_method='labse'` at ingestion time

---

## Artifacts Produced

**Scripts:**
- `scripts/337_merge_labse_scored_to_manifest.py` (merge script, new)

**Data (gitignored):**
- `data/stage2/stage2_manifest.jsonl` (updated, 12,248 rows)
- `data/stage2/reviewed_stage2_manifest_cap_corrected.jsonl` (34,271 rows)
- `data/stage2/reviewed_stage2_manifest_final_capped.jsonl` (38,131 rows)
- `data/stage2/reviewed_stage2_manifest_finalized_reviews.jsonl` (38,131 rows, final)
- `data/stage2/stage2_sft.jsonl` (8,572 rows)

**Decisions:**
- This file: `.squad/decisions/inbox/linus-labse-merge-round2.md`

---

## Final Summary (Terse)

**Merged 296 LaBSE-accepted pairs.** Cap enforcement chain produced 4,286 train pairs → **8,572 SFT rows** (+1,134 vs. Round 1). Gap to 40k: **31,428 rows**. Tests passed. Path forward: wiki-langlinks + NLLB mined (requires Frank's extraction work).

**User directive compliance:** Merged all LaBSE-scored rows from Rusty's handoff. 40k target remains out of reach without additional sources. Stopping at Round 2 completion per task scope.

---

**Date:** 2026-05-02  
**Orchestration log:** `.squad/orchestration-log/<timestamp>-linus-labse-merge.md` (to be written)  
**History update:** `.squad/agents/linus/history.md` tail (to be written)


---

# LaBSE Review Promotion — Round 1

**Owner:** Linus (Data Engineer)
**Date:** 2026-05-03
**Status:** Complete — 0 net gain

## Task

Audit the 124 review-tier rows from LaBSE Round 2 scoring and promote high-quality rows using a tightened promotion rule. Re-run cap enforcement chain and SFT emission to measure impact.

## Promotion rule (ALL clauses required)

- **a.** LaBSE score ≥ 0.65 (review band midpoint, not just above reject floor 0.55)
- **b.** Length ratio sane: 0.5 ≤ len(en_tokens) / len(haw_tokens) ≤ 2.0
- **c.** Both sides ≥ 3 tokens (whitespace split)
- **d.** Not a duplicate by pair_hash (sha256_pair) of any row already in reviewed_stage2_manifest_final_capped.jsonl
- **e.** Hawaiian orthography check: text_haw contains ʻokina (U+02BB) OR a vowel-cluster [aeioāēīōū]{2,}

## Input

- data/stage2/_scored/wikimedia_cx_en_haw.labse.jsonl (4 review rows)
- data/stage2/_scored/opus_haw_subsets.labse.jsonl (120 review rows)
- **Total review band:** 124 rows, LaBSE scores 0.5606–0.7472 (median 0.6866)

## Results

### Promotion filter outcome

| Verdict | Count | Reason |
|---------|-------|--------|
| Promoted | 9 | Passed all 5 clauses |
| Duplicate pair_hash | 67 | Already in manifest (expected) |
| Score too low (<0.65) | 44 | Below midpoint threshold |
| Length ratio outlier | 6 | Ratio <0.5 or >2.0 |
| Too short | 4 | <3 tokens on one or both sides |
| No Hawaiian orthography | 3 | Missing ʻokina and vowel clusters |
| **Total** | **124** | |

### Promoted rows (9 total)

1. **wikimedia-cx-en-haw-2794307-p0** — score 0.6663
   - EN: "The Lord of the Rings is an epic high fantasy novel..."
   - HAW: "ʻO \"Lord of the Rings\" kekahi moʻolelo fantasy..."

2–4. **opus-tatoeba** (3 rows) — scores 0.7132, 0.6781, 0.7283
   - Simple sentence pairs (e.g., "I'm not a teacher." / "ʻAʻole au he kumu.")

5–9. **opus-wikimedia** (5 rows) — scores 0.7056–0.7381
   - Wikipedia comparable-aligned fragments

## Pipeline re-run

Ran:
1. `scripts/332_build_reviewed_manifest_cap_corrected.py`
2. `scripts/333_build_reviewed_manifest_final_capped.py`
3. `scripts/334_finalize_stage2_review_verdicts.py`
4. `scripts/330_emit_stage2_sft_jsonl.py --allow-review-required`

### Final verdict: 0 net gain

All 9 promoted rows were **overridden to held-out status** by script 334's source-specific exclusion policies:

- **3 OPUS-Tatoeba rows:** `opus-tatoeba-upstream-duplicate` (Tatoeba lane is canonical)
- **5 OPUS-wikimedia rows:** `opus-wikimedia-quality-heldout` (did not pass conservative alignment gate)
- **1 wikimedia-cx row:** `wikimedia-cx-rights-alignment-heldout` (no train clearance for encyclopedic stub pairs)

### Before/after counts

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| SFT train rows | 8,572 | 8,572 | **0** |
| Manifest train pairs | 4,286 | 4,286 | **0** |
| Manifest release_eligible | 3,414 | 3,414 | **0** |

## Interpretation

The review band (scores 0.55–0.75) contained 124 rows. Of these:

- **67 (54%)** were already in the manifest as review-pending (duplicates)
- **48 (39%)** failed the tightened promotion rule (score/length/orthography)
- **9 (7%)** passed the promotion rule but were policy-excluded by Rusty's source-specific gates

**No rows from the review band are train-eligible under current policy.** The band correctly flagged rows requiring human review (duplicates, weak alignments, or policy-excluded sources).

## Deliverables

- `scripts/337_promote_labse_review_round1.py` — promotion filter script
- `data/stage2/_scored/labse_review_promotion_round1.jsonl` — 9 promoted rows (policy-overridden)
- Updated `reviewed_stage2_manifest_finalized_reviews.jsonl` (no net change after pipeline)
- This decision log

## Recommendation

**Do not lower the promotion threshold.** The review band exists for good reason: most rows are duplicates or policy-excluded. Future LaBSE efforts should focus on:

1. **New sources** (not already in manifest) with accept-tier scores (≥0.75)
2. **NLLB mined** or **synthetic-BT** candidates (16k–30k projected yield per Round 2 gap analysis)
3. **Wiki-langlinks sentence extraction** (2k–6k projected)

The 48 rows that failed the tightened rule are genuine quality rejects (weak scores, length mismatch, missing Hawaiian orthography).

## Learnings

### LaBSE review band is policy-filtered, not just quality-filtered

The review band (0.55–0.75) is correct but requires source-level policy checks. My promotion rule (score + length + orthography + dedup) is necessary but not sufficient. Scripts 332-334 apply:

- Source-specific gates (e.g., OPUS-Tatoeba upstream dedup, wikimedia-cx rights)
- Bible/HK/software-l10n cap enforcement (30%/15%/15% token shares)
- Historical orthography exceptions (e.g., HK 1897)

Any future promotion from review-pending MUST run the full pipeline (332→333→334) to verify final eligibility.

### Promotion script structure

Script 337 correctly implements:
- Compute pair_hash using NFC + ʻokina canonicalization (U+02BB) per repo convention
- Dedup check against existing manifest (sha256_pair field)
- Hawaiian orthography heuristic (ʻokina OR vowel-cluster regex)
- Length ratio + token count sanity checks

Tests: None added (one-off script for specific task). Future promotion scripts should be generalized into a reusable module with pytest coverage.



---

# Source Backlog Resolution: Stage 2 "Do Later" Candidates
**Author:** Linus (Data Engineer)
**Session date:** 2025-05-01
**Status:** Resolved — 2 adapters implemented, 3 hard blockers issued

---

## Summary

Five Stage 2 source candidates that had been deferred with vague "do later" notes in
`data/raw/ulukau-family-sft-candidates/20260501/manifest.jsonl` have been fully resolved.
Two feasible adapters were built and executed. Three are hard-blocked with specific evidence.

---

## 1. HK Constitution 1852 (hekumukanawaiam / constitutionand) — IMPLEMENTED

**Script:** `scripts/326_build_hk_constitution_1852_candidates.py`
**Output:** `data/stage2/candidates/hk_constitution_1852.jsonl` — 74 rows

**Method:** Section-level alignment on `Art. N.` (EN) / `Pauku N.` (HAW) markers.
HAW regex loosened to `^[. ]{0,3}Pauk.?\s+(\d+)` to handle OCR variants: Paukū, Paukc,
Pauk€, and leading `. ` noise.

**Key facts:**
- 105 EN articles; ~23 HAW sections absent due to OCR failure (W→AV substitution garbled
  some section headers; pages missing from scan)
- 80 alignable pairs; 6 rejected for length ratio; net 74 candidates
- `register=legal`, `prototype_only=True`, `release_eligible=False`,
  `alignment_review_required=True`
- Wired into shared HK legal cap pool (pooled with `hk_statutes_1897`; combined cap ≤15%)
- At current N=6,102 tokens, H_max=1,664 tokens ≈ 8 rows total; constitution rows
  compete with 1897 rows via sha256_pair sort; all 74 currently cap-overflowed

**Action required:** No immediate action. Rows will become train-eligible as N grows.
Native reviewer should verify OCR-reconstructed article boundaries before any bulk promotion.

---

## 2. Gospel of John 1854 (gospelaccordingt00hawarich) — IMPLEMENTED

**Script:** `scripts/327_build_gospel_john_1854_candidates.py`
**Output:** `data/stage2/candidates/gospel_john_1854.jsonl` — 611 rows

**Method:** Verse-level alignment using MOKUNA chapter markers as primary tracker (EN and
HAW interleaved in two-column djvu.txt scan). Language detection via closed-class word
scoring per verse block.

**Key facts:**
- 21 chapters, 879 verse slots; 602 passed quality gates into Bible pool after cross-edition
  dedup (0 verse-key collisions with 1839/1868 — confirmed no overlap)
- Critical OCR quirk: `CHAP. I.` → `CHAP.  L` (Roman numeral I → letter L); fixed by
  MOKUNA-primary chapter tracking + expanded `_ROMAN` dict
- `quality_flags: ["haw_no_diacritics", "bible_cross_edition_dedup_required"]`
- `register=religious`, `prototype_only=True`, `release_eligible=True`
- Wired into shared Bible pool; at current N=6,102, Bible cap ≈ 63 rows total across
  all three editions; all 602 John rows currently cap-overflowed
- `record_id_en` format: `JHN.{chapter}.{verse}` — distinct from 1839/1868 namespace

**Action required:** No immediate action. Rows will enter train as N grows.
Before bulk promotion: diacritic restoration assessment recommended (1854 orthography
lacks systematic kahakō/ʻokina).

---

## 3. HK Statute Laws 1847 — HARD BLOCK (INVENTORY-ONLY)

**Source files:**
- EN: `data/raw/ulukau-family-sft-candidates/20260501/statutelawshism00ricogoog/statutelawshism00ricogoog_djvu.txt` (1.5 MB)
- HAW: `data/raw/ulukau-family-sft-candidates/20260501/kanawaiikauiaek00ricogoog/kanawaiikauiaek00ricogoog_djvu.txt` (592 KB)

**Blockers (all three required to resolve):**

1. **EN double-space OCR throughout.** Every word in the EN file is rendered with
   double internal spaces: `"Statute  Laws  of  His  Majesty"`. Normalization
   (`re.sub(r' {2,}', ' ', line)`) is required before any token or section parsing.
   This is automatable but was not implemented — risk of degrading structured tokens
   (e.g., section references like `Section  V`) is non-trivial.

2. **Roman-vs-Arabic section ID mismatch with per-Act reset.** EN uses Roman numerals
   (`Section I, Section II, ...`) that reset to `I` for every new Act. HAW uses Arabic
   Pauku numbers that appear to be global within the volume. Alignment requires a
   two-level hierarchy: `(Act name, Section number)` for EN, mapped to `(Act name, Pauku number)`
   for HAW. The Act boundaries in EN are identifiable by headers like
   `"AN ACT to Regulate..."`, but the HAW equivalents need verification.
   Roman-to-Arabic mapping is trivial; hierarchical alignment is not.

3. **Year mismatch is benign but worth noting.** EN title: `"Statute Laws... A.D. 1845
   and 1846"` (Vol. I); HAW published 1847 (delayed edition of same laws). This is NOT
   a separate corpus — same laws, different publication years. Not a blocker per se.

**Recommendation:** Mark `status: inventory_only` with note
`"EN double-space OCR + Roman/Arabic section ID mismatch + per-Act section reset require
hierarchical alignment adapter; deferred to Stage 3 backlog."` No adapter will be built
this session.

---

## 4. Sanitary Instructions 1881 (63140380R.nlm.nih.gov) — HARD BLOCK (WRONG VOLUME)

**Source file:**
`data/raw/ulukau-family-sft-candidates/20260501/63140380R/63140380R_djvu.txt` (274 KB)

**Blocker:**

The downloaded Internet Archive item `63140380R` is the **English-only volume** of
*"Sanitary Instructions for Hawaiians"* by W.N. Armstrong (1881). The item-level metadata
explicitly states `"language": "eng"`. The HAW counterpart is a **separate IA item**:

> `"Hawaiian ed. has title: He mau olelo ao e pili ana i ke ola kino o na Kanaka Hawaii"`

This HAW volume was **never downloaded** into the project raw data. Without both volumes,
no parallel alignment is possible.

**Additional consideration:** Even if both volumes were retrieved, chapter-level alignment
alone would not be sufficient for SFT quality — `alignment_method=labse` (comparable-aligned)
was the planned approach, requiring sentence-level embedding similarity, which is not
currently implemented in the pipeline.

**Recommendation:** Mark `status: blocked` with notes:
1. `"HAW volume not downloaded — separate IA item required (title: 'He mau olelo ao...'). Fetch HAW item from IA before any adapter work."`
2. `"Comparable-aligned (LaBSE) method required even if both volumes present — not yet implemented."`

---

## 5. Diglot NT 1859 (HAWPDF_DBS_HS) — HARD BLOCK (NO OCR + BIBLE CAP EXHAUSTED)

**Source directory:**
`data/raw/ulukau-family-sft-candidates/20260501/HAWPDF_DBS_HS/`

**Blockers (both apply independently):**

1. **No OCR text downloaded.** Only `ia_metadata.json` (6.9 KB) is present locally.
   The Internet Archive item has available assets — `djvu.txt` (2.4 MB), `hOCR` (84 MB),
   `djvu.xml` (41 MB), `chOCR` (35 MB) — but none were fetched. The original inventory
   note reads: `"OCR garbled from two-column layout. hOCR extraction needed."` Since
   even the raw djvu.txt is not available locally, no assessment or implementation can
   begin without a targeted IA fetch.

2. **Bible cap already fully consumed.** At current N=6,102, B_max ≈ 3,328 tokens ≈ 63
   rows total across all Bible sources (Baibala 1839, 1868, Gospel of John 1854). The
   Diglot NT 1859 covers all four Gospels + Acts; even if perfectly extracted, every row
   would be cap-overflowed until N grows substantially (roughly 3× current N to admit
   meaningful new Bible rows). The opportunity cost of building a complex hOCR pipeline
   for an immediately cap-saturated source is not justified this session.

**Recommendation:** Keep existing `status: inventory_only` + blocker note. Add:
`"Both blockers must be resolved before adapter work: (1) fetch djvu.txt from IA,
(2) Bible cap has headroom at B_max≈6N/11 — currently exhausted at N=6,102; revisit
when N≥15,000."`

---

## Cap state after this session

| Source | Rows produced | In pool | Train at N=6,102 |
|---|---|---|---|
| HK Constitution 1852 | 74 | hk_pool (shared w/ 1897) | 0 (cap-overflowed) |
| Gospel of John 1854 | 602 (after dedup) | bible_pool | 0 (cap-overflowed) |
| HK Statute Laws 1847 | 0 | — | — |
| Sanitary Instructions 1881 | 0 | — | — |
| Diglot NT 1859 | 0 | — | — |

Both new candidate pools are correctly wired: as N grows, the fixed-point cap formula
(H_max=3N/11, B_max=6N/11) will automatically admit new rows from both pools without
any script changes.

---

## Files changed

```
scripts/326_build_hk_constitution_1852_candidates.py   [new]
scripts/327_build_gospel_john_1854_candidates.py        [new]
data/stage2/candidates/hk_constitution_1852.jsonl       [new — 74 rows]
data/stage2/candidates/gospel_john_1854.jsonl           [new — 611 rows]
data/stage2/reports/hk_constitution_1852_report.json    [new]
data/stage2/reports/gospel_john_1854_report.json        [new]
scripts/333_build_reviewed_manifest_final_capped.py     [updated]
  - CANDIDATES dict: +hk_constitution_1852, +gospel_john_1854
  - HK_LEGAL_SOURCES frozenset: replaces single-source check
  - BIBLE_SOURCES frozenset: +gospel_john_1854
  - hk_pool: +constitution_1852 filtering block (haw_tok[8,500], ratio[0.4,2.5])
  - bible_pool: +gospel_john_1854 with verse-key dedup vs 1839/1868
  - N computation: uses HK_LEGAL_SOURCES set exclusion
  - Artifact verification: uses HK_LEGAL_SOURCES set
scripts/334_finalize_stage2_review_verdicts.py          [updated]
  - _verdict_hk_constitution_1852(): new verdict helper
  - _verdict_gospel_john_1854(): new verdict helper
  - dispatch: +hk_constitution_1852, +gospel_john_1854 branches
  - _TRAIN_REASONS: +hk_constitution_1852, +gospel_john_1854 entries
data/stage2/reviewed_stage2_manifest_final_capped.jsonl [regenerated — 34,811 rows]
data/stage2/reviewed_stage2_manifest_finalized_reviews.jsonl [regenerated]
```


---

# Stage 2 Gap Analysis: Path to 40k SFT Rows

**Author:** Linus (Data Engineer)  
**Date:** 2026-05-02  
**Context:** User directive to reach 40,000 Stage-2 SFT training rows

---

## 1. Current State (Actual Measurement)

| Metric | Count | Notes |
|---|---|---|
| Canonical pairs in manifest | 37,711 | `reviewed_stage2_manifest_final_capped.jsonl` |
| — split=train | 3,719 | After fixed-point cap enforcement |
| — split=dev | 15 | Frozen Tatoeba dev |
| — split=review-pending | 33,977 | Held back by cap/quality/policy |
| Current SFT emit (default) | **1,346 rows** | 673 pairs × 2 directions |
| — Blocked by `alignment_review_required` | 3,046 train pairs | HK, Phrase Book, etc. |
| Current SFT with `--allow-review-required` | **7,438 rows** | 3,719 pairs × 2 directions |

---

## 2. Gap Calculation

| Metric | Value |
|---|---|
| **Current SFT rows** (with `--allow-review-required`) | **7,438** |
| **Target SFT rows** | **40,000** |
| **Gap** | **32,562 rows** |
| **Canonical pairs needed** (÷2 directions) | **16,281 pairs** |

---

## 3. Leverage Analysis

### Option A: Change SFT emitter flag (DONE, +6,092 rows)
**What:** Use `--allow-review-required` flag in `scripts/330_emit_stage2_sft_jsonl.py`.  
**Impact:** 673 pairs → 3,719 pairs; 1,346 rows → 7,438 rows (+6,092).  
**Status:** Feasible immediately; HK/Phrase Book rows already marked `alignment_review_required=true` per policy.  
**Risk:** Low — rows are already in train split, just gated by conservative flag.

### Option B: Promote review-pending rows to train
**What:** Move rows from `split=review-pending` to `split=train` in the manifest.  
**Available pools:**
- **Bible overflow (31,679 rows):** baibala-1868 (20,485), baibala-1839 (10,149), gospel_john_1854 (591), hk_statutes_1897 (1,045). **BLOCKED** — Bible cap saturated at 29.9%/30%. Cannot promote until N_nonbible grows.
- **Andrews vocab (1,194 rows):** Dictionary fragments, currently `verdict=excluded-source-not-trainable-now` per Rusty §1.1 (OCR noisy, no diacritics). **BLOCKED** — needs clean re-extraction.
- **OPUS comparable-aligned (212 rows):** Currently review-pending. **GATED** — needs LaBSE alignment scores >0.75 per Rusty policy. Infrastructure not wired.
- **Kaikki (139 rows):** Failed quality gate (`side_too_short`, `haw_nonhaw_letters_high`, etc.). **BLOCKED** — not cap overflow, genuine quality rejects.
- **Others (small):** hooilina (68), wikimedia-cx (12). Blocked on KS editorial review / volume too small.

**Impact:** If we could promote all non-Bible review-pending (~2,000 rows), we'd get +4,000 SFT rows.  
**Reality:** Most pools are blocked by quality/policy gates, not just cap math.

### Option C: Increase SFT template multiplier
**What:** The emitter applies 5 template variants per direction (10 total per pair). Could duplicate each pair N times.  
**Impact:** Linear multiplier — 3,719 pairs × 2 directions × N templates.  
**Status:** **DISHONEST** — this is synthetic duplication, not new training signal. Violates Stage-2 data philosophy (no fake alignment scores, no synthetic data unless explicitly tagged and capped).  
**Verdict:** **REJECTED** — not a valid path.

### Option D: Wait for new sources
**What:** Frank/coordinator bring in new PD sources (NLLB mined, synthetic BT, Wehewehe PD, etc.).  
**Impact:** Depends on source yield. NLLB could yield ~5k–10k pairs at ≥0.80 LaBSE; synthetic BT capped at 25% of train.  
**Status:** Out of scope for this task — requires upstream data collection.

---

## 4. Chosen Path (Highest-Leverage, Policy-Compliant)

### Immediate Action (Phase 2):
1. **Re-emit SFT with `--allow-review-required` flag** (LINE 1)  
   - Input: `reviewed_stage2_manifest_final_capped.jsonl` (37,711 rows)
   - Output: `stage2_sft_finalized_train.jsonl` (7,438 rows)
   - Justification: Rows are already in train split; flag is a conservative gate that Danny's final-review-verdict policy makes safe to lift (HK rows have `verdict=train-ready` even with `alignment_review_required=true`).

### Blocked Actions (Document, Hand Off):
2. **Promote Bible overflow (31,679 rows)** — BLOCKED until N_nonbible grows. Bible cap math:
   - Current: B_train = 439 pairs (1868 + 1839 + John); N_nonbible ≈ 1,467 pairs → 29.9% (cap 30%).
   - To promote +1 Bible row: N_nonbible must grow by ~2.3× (from 1,467 → ~3,400).
   - Requires NLLB mined / synthetic BT / new PD non-Bible sources.

3. **OPUS comparable-aligned promotion (212 rows)** — BLOCKED on LaBSE infrastructure. Per coordinator's note, Rusty filed a policy gap analysis on comparable-alignment. LaBSE not wired; cannot compute alignment scores >0.75. Needs Frank + Rusty to unblock.

4. **Andrews vocab (1,194 rows)** — BLOCKED on clean re-extraction. Current rows are OCR-noisy djvu from IA. Rusty §1.1 verdict stands: not trainable until Wehewehe-side parse or manual correction.

---

## 5. Result After Phase 2

| Metric | Value |
|---|---|
| SFT rows emitted | 7,438 |
| Gap from 40k | 32,562 rows |
| Pairs still needed | 16,281 pairs |

**Path to 40k:** Requires new source ingestion (NLLB mined, synthetic BT, or comparable-aligned with LaBSE). Current manifest exhausted at policy-compliant boundaries.

---

## 6. Recommendation

**Immediate:** Execute Phase 2 (re-emit with `--allow-review-required`). Verify 7,438 SFT rows. Run repo tests.

**Next move:** Coordinator should:
- **Frank:** Wire LaBSE for OPUS comparable-aligned (212 rows → +424 SFT rows when scored ≥0.75).
- **Frank:** Fetch NLLB mined pairs or synthetic BT to grow N_nonbible by ~2× (enables Bible overflow promotion).
- **Linus:** Stand by for new candidate files; current backlog exhausted.

**Hard constraint:** Bible/HK caps are non-negotiable. 40k target requires non-Bible, non-HK source growth.


---

# Linus — Stage 2 hard source verdicts

Date: 2026-05-02
Owner: Linus (Data Engineer)
Status: DECISION

## Decision

Remaining processed Stage-2 sources must enter the final path with concrete verdicts, not `review-pending` limbo. For this cut, OPUS, Wikimedia CX, and Weblate are merged only as held-out rows; NLLB, wiki langlinks, sanitary instructions, and Wikisource remain source-level hard blocker reports with zero row candidates.

## Source verdicts

| Source | Rows | Verdict |
|---|---:|---|
| OPUS QED | 16 | Held out: language-mislabeled; not en↔haw bitext. |
| OPUS Ubuntu | 4 | Held out: row-misaligned / loan-heavy software strings. |
| OPUS-Tatoeba | 93 | Held out: duplicates upstream Tatoeba after normalized-text dedup. |
| OPUS-wikimedia | 374 | Held out: treated as mined/comparable; no LaBSE/LASER score; no fake score. |
| Wikimedia CX | 14 | Held out: partial-stub Wikipedia rows lack hard alignment + attribution clearance for train. |
| Weblate | 107 | Held out: software-l10n register lacks approved cap/context-quality gate for SFT. |
| NLLB mined | 0 | Source blocker: endpoint has no `haw_Latn`; do not substitute `hau_Latn` or `hat_Latn`. |
| wiki-haw-en-langlinks | 0 | Source blocker: raw probe only; LaBSE/LASER required before candidates. |
| sanitary-instructions-1881 | 0 | Source blocker: comparable alignment requires LaBSE/LASER. |
| wikisource-haw-en-comparable | 0 | Source blocker: haw Wikisource endpoint redirects to multilingual HTML; LaBSE still required after endpoint repair. |

## Resulting artifact counts

`data/stage2/reviewed_stage2_manifest_finalized_reviews.jsonl` now has 35,419 rows: 603 train, 15 dev, 34,801 held-out, 0 review-pending. `data/stage2/stage2_sft_finalized_train.jsonl` remains 1,206 directional train rows.

## Rationale

The user explicitly rejected promotion/deferred limbo. Holding out rows early is preferable to adding unscored comparable pairs or source-policy exceptions that would silently weaken the training set.


---

# Rusty — LaBSE Bring-Up Complete: 4-Source Scoring Summary

**Date:** 2026-05-02  
**Status:** ✅ LaBSE infrastructure wired, 2/4 sources scored, 40k feasibility assessed  
**Owner:** Rusty (NLP Researcher)  
**Context:** User directive: "don't stop until you have 40k rows or i tell you to stop"

---

## Executive Summary

**LaBSE wired and operational.** Scored 501 candidate rows across 2 sources, accepted 296, review 124, reject 81. **New SFT ceiling: 8,208 rows (+770).** 40k target **not reachable** with currently scored sources; requires wiki-langlinks extraction (1k–3k estimated) + NLLB mined (8k–15k) or synthetic BT.

---

## Deliverables Completed

### 1. LaBSE Infrastructure ✅

**Installed:**
- `sentence-transformers>=2.7` + `torch>=2.0` (Apple Silicon MPS-compatible)
- Updated `requirements-compute.txt` with LaBSE dependency

**Model verified:**
- `sentence-transformers/LaBSE` (768-dim, L2-normalized embeddings)
- Cosine similarity scoring on (en, haw) pairs
- ʻokina canonicalization (U+02BB) + NFC normalization on Hawaiian text

**Code artifacts:**
- `code/llm_hawaii/labse_scorer.py` — LaBSE embedding module (batch scoring, deterministic)
- `scripts/336_score_comparable_with_labse.py` — CLI scorer (triple-gated: --dry-run, --limit, --execute)

**Self-test passed:**
- Dry-run on wikimedia_cx (5 rows): 2 accept, 2 review, 1 reject
- Full scoring on opus_haw_subsets (487 rows): 2 minutes elapsed

---

### 2. Four-Source Scoring Results

| Source | Status | Total Scored | Accept (≥0.75) | Review (0.55–0.75) | Reject (<0.55) | SFT Impact |
|---|---|---|---|---|---|---|
| **wikimedia_cx_en_haw** | ✅ Scored | **14** | **9** | **4** | **1** | **+18 rows** |
| **opus_haw_subsets** | ✅ Scored | **487** | **287** | **120** | **80** | **+574 rows** |
| **sanitary-instructions-1881** | ❌ Blocked | **0** | — | — | — | **0 rows** |
| **wiki-haw-en-langlinks** | ❌ Blocked | **0** | — | — | — | **0 rows** |
| **TOTAL (scored)** | — | **501** | **296** | **124** | **81** | **+592 rows** |

**Blockers for unscored sources:**
- `sanitary-instructions-1881`: No sentence-level alignment extracted; raw document pair only. **Requires:** sentence segmentation + within-chapter LaBSE aligner. **Estimated yield:** 200–800 candidates → dozens-to-low-hundreds post-threshold.
- `wiki-haw-en-langlinks`: No sentence-level candidates; raw provenance manifest only. **Requires:** Wikipedia article sentence extraction + LaBSE cross-product scoring. **Estimated yield:** 3k–5k candidates → 1k–3k accept post-threshold.

---

### 3. OPUS-Wikimedia Mined Subset — Policy Gap Confirmed

**Finding (validated):**
- OPUS adapter incorrectly set `alignment_method=tmx-line` for OPUS-wikimedia (mined comparable, not deterministic)
- Prior orchestration log estimated 275 mined rows; actual count: **374 rows**
- **LaBSE acceptance rate: 59% (220/374)** — confirms mined pairs need embedding scores

**Verdict:**
- 220 accept (≥0.75) → train-eligible
- 95 review (0.55–0.75) → review-required
- 59 reject (<0.55) → drop

**Recommendation:** Fix OPUS adapter to mark mined sub-corpora as `alignment_method="labse"` (not `tmx-line`).

---

### 4. SFT Row Impact Analysis

**Current baseline (from Linus gap analysis):**
- SFT rows emitted (with `--allow-review-required`): **7,438 rows**
- Current train pairs: 3,719 (1,467 non-Bible, 439 Bible; 29.9% Bible cap)

**New LaBSE-accepted rows:**
- wikimedia_cx: +9 accept
- opus_haw_subsets: +287 accept
- **Total: +296 new comparable pairs**
- **Directional SFT: +592 rows** (296 pairs × 2 directions)

**Bible cap headroom unlocked:**
- Current non-Bible: 1,467 pairs
- New non-Bible: 1,763 pairs (+296)
- Bible cap (30% × 1,763): 528.9 pairs
- Current Bible train: 439 pairs
- **Bible headroom: 89.9 pairs** (promotable from 31,679 overflow)
- **Directional SFT from Bible: +178 rows** (89 pairs × 2 directions)

**Total new SFT rows: +770 rows (592 + 178)**
**New SFT ceiling: 8,208 rows**

---

### 5. Path to 40k SFT Rows

**Gap: 31,792 rows (40,000 - 8,208)**

**Next moves to close the gap:**

| Source | Status | Estimated Yield (SFT rows) | Owner | Priority |
|---|---|---|---|---|
| **wiki-haw-en-langlinks** | Blocked on sentence extraction | **2k–6k rows** (1k–3k pairs × 2) | Frank / general-purpose agent | **P0** (highest yield) |
| **NLLB mined (@ LaBSE ≥0.80)** | Not fetched yet | **16k–30k rows** (8k–15k pairs × 2) | Frank | **P1** |
| **Synthetic BT (≤15% token cap)** | Blocked on Stage-1-merged checkpoint | **Variable** (depends on base quality) | Rusty + Frank | **P2** |
| **sanitary-instructions-1881** | Blocked on sentence extraction | **~200–800 rows** (dozens-hundreds pairs × 2) | Frank / general-purpose agent | **P3** (low yield) |

**Verdict:**
- **40k target is NOT reachable** with currently scored sources (8,208 ceiling).
- **Minimum additional sources needed:** wiki-langlinks (2k–6k) + NLLB (16k–30k) = 18k–36k → total 26k–44k (40k reachable).
- **Sanitary-instructions is NOT blocking** — yield too low to move the needle.

---

### 6. Inbox Decisions Written

Per-source decisions delivered to Linus for manifest merge:

1. `.squad/decisions/inbox/rusty-wikimedia-cx-labse-scored.md` — 9 accept, 4 review, 1 reject
2. `.squad/decisions/inbox/rusty-opus-haw-subsets-labse-scored.md` — 287 accept, 120 review, 80 reject
3. `.squad/decisions/inbox/rusty-sanitary-instructions-blocked.md` — Blocked on sentence alignment
4. `.squad/decisions/inbox/rusty-wiki-langlinks-blocked.md` — Blocked on sentence extraction (highest yield)

**Linus handoff:**
- Read scored JSONLs: `data/stage2/_scored/*.labse.jsonl`
- Promote accept rows → `stage2_manifest.jsonl` with `split=train`, `labse_score` field
- Promote review rows → `split=review-pending`
- Drop reject rows
- Re-run fixed-point cap enforcement (Bible headroom: +89 pairs)
- Re-emit SFT JSONL

---

### 7. Artifacts Produced

**Code:**
- `code/llm_hawaii/labse_scorer.py` (LaBSE embedding module)
- `scripts/336_score_comparable_with_labse.py` (CLI scorer)

**Data (gitignored):**
- `data/stage2/_scored/wikimedia_cx_en_haw.labse.jsonl` (14 rows)
- `data/stage2/_scored/wikimedia_cx_en_haw.labse.summary.json`
- `data/stage2/_scored/opus_haw_subsets.labse.jsonl` (487 rows)
- `data/stage2/_scored/opus_haw_subsets.labse.summary.json`

**Decisions:**
- This file: `.squad/decisions/inbox/rusty-labse-bringup-complete.md`
- Per-source inbox decisions (4 files, listed above)

**Config:**
- `requirements-compute.txt` updated with `sentence-transformers>=2.7` dependency

---

### 8. Tests Status

**Existing tests:**
- `code/tests/test_stage2_*.py` — **NOT RUN YET** (pending verification that torch/sentence-transformers don't break existing test suite)
- Smoke test recommendation: Add minimal LaBSE scorer test gated with `@pytest.mark.skipif(not torch_available)` or equivalent

**Action item for Linus/Basher:** Run full test suite to verify LaBSE dependencies don't break existing pipeline:
```bash
cd /Users/yashasgujjar/dev/ideal-spoon
source .venv/bin/activate
pytest code/tests/test_stage2_*.py -v
```

---

## Final Summary (Terse)

**LaBSE wired.** Scored 501 rows across 2 sources, accepted 296, review 124, reject 81. **New SFT ceiling: 8,208 rows (+770).** **Path to 40k:** Requires wiki-langlinks extraction (2k–6k) + NLLB mined (16k–30k). Sanitary-instructions is low-priority (yield <1k). OPUS-wikimedia mined policy gap confirmed: 59% LaBSE acceptance rate validates need for embedding scores.

**User directive compliance:** I have scored all LaBSE-blocked sources with existing candidate JSONLs (2/4). The other 2 sources (wiki-langlinks, sanitary-instructions) are blocked on sentence-level alignment extraction, which is out of scope for this LaBSE bring-up task. 40k target is not reachable without wiki-langlinks + NLLB; I'm stopping here per scope boundary and documenting the honest gap.

---

**Date:** 2026-05-02  
**Orchestration log:** `.squad/orchestration-log/<timestamp>-rusty-labse-bringup.md` (to be written)  
**History update:** `.squad/agents/rusty/history.md` tail (to be written)


---

# Rusty — opus_haw_subsets LaBSE Scoring Complete

**Date:** 2026-05-02  
**Status:** ✅ Scored, ready for Linus manifest merge  
**Source:** `opus_haw_subsets`  
**Scored JSONL:** `data/stage2/_scored/opus_haw_subsets.labse.jsonl`  
**Summary:** `data/stage2/_scored/opus_haw_subsets.labse.summary.json`

---

## Scoring Results

| Metric | Count |
|---|---|
| Total rows scored | **487** |
| Accept (≥0.75) | **287** |
| Review (0.55–0.75) | **120** |
| Reject (<0.55) | **80** |

---

## OPUS Corpus Breakdown

| Corpus | Total | Accept | Review | Reject |
|---|---|---|---|---|
| **wikimedia** | **374** | **220** | **95** | **59** |
| Tatoeba | 93 | 66 | 25 | 2 |
| QED | 16 | 0 | 0 | 16 |
| Ubuntu | 4 | 1 | 0 | 3 |

---

## Key Finding: OPUS-Wikimedia Mined Subset

Per prior orchestration log (`.squad/orchestration-log/2026-05-02T04-16-26Z-rusty-alignment.md`):

> **OPUS adapter sets `alignment_method=tmx-line` for all sub-corpora, including `wikimedia` (mined comparable, not deterministic line-aligned).** Result: 275 mined OPUS-Wikimedia rows incorrectly accept on line index alone.

**LaBSE scoring confirms the policy gap:**
- OPUS-wikimedia (374 rows): 220 accept / 95 review / 59 reject
- **Only 59% (220/374) pass the LaBSE ≥0.75 threshold** — the rest were misclassified by deterministic line-index alignment

The prior orchestration log recommended adapter fix (mark mined sub-corpora as `alignment_method="labse"` in OPUS adapter). LaBSE scoring now provides the correct alignment scores for these rows.

---

## LaBSE Verdict Treatment Recommendation

Per comparable-alignment policy (docs/data-pipeline.md § Stage 2 thresholds):

1. **Accept rows (287):** Set `alignment_score=<labse_score>`, `alignment_method="labse"`, `split=train`, `verdict=accept`. These are train-eligible.
   - OPUS-wikimedia: 220 accept → train-eligible (CC BY-SA 4.0)
   - Tatoeba: 66 accept → train-eligible (CC BY 2.0 FR)
   - Ubuntu: 1 accept → train-eligible (CC BY-SA 3.0, but NC clause may block)
2. **Review rows (120):** Set `alignment_score=<labse_score>`, `alignment_method="labse"`, `split=review-pending`, `verdict=review-required`. Manual review recommended.
3. **Reject rows (80):** Set `alignment_score=<labse_score>`, `alignment_method="labse"`, `verdict=reject`. Do not promote to manifest.
   - QED (16) + Ubuntu (3) + OPUS-wikimedia (59) + Tatoeba (2)

---

## Impact on Stage 2 Manifest

- **New train-eligible rows:** +287 canonical pairs (220 wikimedia + 66 Tatoeba + 1 Ubuntu)
- **Directional SFT impact:** +574 rows (287 pairs × 2 directions)
- **Register mix:**
  - OPUS-wikimedia (220): encyclopedic (CC BY-SA 4.0)
  - Tatoeba (66): educational-conversational (CC BY 2.0 FR)
  - Ubuntu (1): technical-UI (CC BY-SA 3.0, NC clause check needed)

---

## Rights Note: Ubuntu License Check

Per OPUS metadata, Ubuntu corpus is **CC BY-NC-SA 3.0** (NonCommercial). Confirm with Linus whether NC clause blocks train use or requires `prototype_only=true` annotation.

---

## Handoff to Linus

Linus owns manifest merge. Recommended actions:

1. Read `data/stage2/_scored/opus_haw_subsets.labse.jsonl`
2. Promote accept rows (287) → `stage2_manifest.jsonl` with `split=train`, `labse_score` field
3. Promote review rows (120) → `stage2_manifest.jsonl` with `split=review-pending`
4. Drop reject rows (80) — do not add to manifest
5. Fix OPUS adapter: Mark mined sub-corpora as `alignment_method="labse"` (not `tmx-line`)
6. Re-run fixed-point cap enforcement (Bible cap may unlock additional rows)
7. Re-emit SFT JSONL with new train rows

---

## Notes

- LaBSE model: `sentence-transformers/LaBSE` (768-dim, L2-normalized embeddings)
- Scoring method: Cosine similarity on (en, haw) pairs
- ʻokina canonicalization: Applied to Hawaiian side before embedding (U+02BB canonical)
- NFC normalization: Applied to both sides
- Threshold constants: `accept_min=0.75`, `review_min=0.55` (PolicyConfig defaults)

---

**Artifacts:**
- Scored JSONL: `data/stage2/_scored/opus_haw_subsets.labse.jsonl` (gitignored)
- Summary JSON: `data/stage2/_scored/opus_haw_subsets.labse.summary.json` (gitignored)


---

# Rusty — sanitary-instructions-1881 Scoring Blocked (No Candidate JSONL)

**Date:** 2026-05-02  
**Status:** ❌ Blocked — sentence-level alignment not yet extracted  
**Source:** `sanitary-instructions-1881`  
**Blocker:** No candidate JSONL exists; raw document pairs only  

---

## Why This Source Cannot Be Scored Today

Per source README (`data-sources/sanitary-instructions-1881/README.md`):

> Deterministic alignment is **not honest** here:
>   - **Chapter level:** ~20 chapters on each side; OCR noise on Roman numerals
>   - **Paragraph level:** EN 1,277 paragraphs vs HAW 1,529 paragraphs (~20% delta)
>   - **Sentence level:** Requires segmentation + comparable-aligned scorer (LaBSE/LASER)

**What exists:**
- Raw document-level pair under `data/raw/sanitary-instructions-1881/20260502/`
- EN: `63140380R_djvu.txt` (274 KB)
- HAW: `63140370R_djvu.txt` (284 KB)

**What is missing:**
- Sentence segmentation on both sides
- Sentence-level alignment (either positional or LaBSE-scored)
- `data/stage2/candidates/sanitary_instructions_1881.jsonl`

---

## Honest Next Step

Build a sentence-level alignment extractor (out of scope for this LaBSE bring-up task):

1. **Input:** Raw djvu.txt files (already fetched)
2. **Pipeline per side:**
   - NFC normalization
   - ʻokina canonicalization (HAW only; mirror `code/llm_hawaii/stage2_quality.py::OKINA_MISENCODINGS`)
   - Sentence segmentation (e.g., spaCy, NLTK, or simple `.` + newline heuristics)
3. **Alignment pass:**
   - Option A: Chapter-scoped LaBSE scoring (embed all EN sentences in chapter X, embed all HAW sentences in chapter X, find best matches above threshold)
   - Option B: Cross-product LaBSE scoring (expensive: 1,277 EN × 1,529 HAW = 1.95M pairs)
   - Option C: Hybrid: OCR-repair Roman numerals → deterministic chapter-level pairing → within-chapter LaBSE sentence alignment
4. **Output:** `data/stage2/candidates/sanitary_instructions_1881.jsonl` with `alignment_method="labse"`, `alignment_score=<cosine>`, `split=review-pending`

**Expected yield (per Frank's estimate):** 200–800 review-pending rows; final post-threshold likely dozens to low hundreds.

**Register:** health/medical — unique, currently absent from Stage-2 train mix.

---

## Impact on This Task

- **Rows scored:** **0** (no candidate JSONL to score)
- **Train-eligible rows added:** **0**
- **SFT row impact:** **0**

---

## Recommendation

**To Linus:** If sentence-level alignment is a priority, assign a new adapter task to Frank or a general-purpose agent to build the sentence extractor + within-chapter LaBSE aligner. Once `data/stage2/candidates/sanitary_instructions_1881.jsonl` exists, re-run the LaBSE scorer (`scripts/336_score_comparable_with_labse.py --source sanitary_instructions_1881 --execute`).

**To Coordinator:** This source is not blocking 40k SFT row target math today — the yield is expected to be low hundreds at best. Prioritize only if register diversity (health/medical) is strategically important.

---

**Status:** Raw probe landed, no candidates emitted, LaBSE scoring not applicable.


---

# Rusty — wiki-haw-en-langlinks Scoring Blocked (No Candidate JSONL)

**Date:** 2026-05-02  
**Status:** ❌ Blocked — sentence-level alignment not yet extracted  
**Source:** `wiki-haw-en-langlinks`  
**Blocker:** No candidate JSONL exists; raw document-level provenance only  

---

## Why This Source Cannot Be Scored Today

Per source README (`data-sources/wiki-haw-en-langlinks/README.md`):

> What this source does NOT do today:
>   - It does **not** emit `data/stage2/candidates/<source>.jsonl`. The plan-stated
>     `alignment_method` is `labse`; LaBSE/LASER scoring is not implemented in
>     this repo. Emitting fake or unscored sentence pairs would violate Frank's
>     charter ("no source without a receipt") and Stage-2 quality rules.

**What exists:**
- `probe.py` script that fetches MediaWiki API langlinks
- Raw API JSON batches under `data/raw/wiki-haw-en-langlinks/<YYYYMMDD>/batches/`
- `langlinks_manifest.jsonl` with per-pair metadata (haw_pageid, en_pageid, revision IDs)
- Probe summary: `data/stage2/reports/wiki_haw_en_langlinks_probe_report.json`

**What is missing:**
- Sentence extraction from Wikipedia article wikitext (requires MediaWiki API `prop=extracts` or HTML parsing + sentence segmentation)
- Sentence-level alignment (LaBSE-scored cross-product or pre-aligned sentence pairs)
- `data/stage2/candidates/wiki_haw_en_langlinks.jsonl`

---

## Honest Next Step

Build a sentence-level alignment extractor (out of scope for this LaBSE bring-up task):

1. **Input:** `langlinks_manifest.jsonl` (53 probed page pairs, Frank estimated 3k–5k total)
2. **Per page pair:**
   - Fetch EN article wikitext via MediaWiki API (`prop=extracts&explaintext=1` or `prop=revisions&rvprop=content`)
   - Fetch HAW article wikitext via MediaWiki API
   - Parse/extract sentences from both sides (wikitext → plain text → sentence segmentation)
3. **Alignment pass:**
   - Option A: Cross-product LaBSE scoring (all EN sentences × all HAW sentences per page pair)
   - Option B: Pre-aligned sentence pairs if Wikipedia provides them (unlikely for langlinks)
4. **Output:** `data/stage2/candidates/wiki_haw_en_langlinks.jsonl` with `alignment_method="labse"`, `alignment_score=<cosine>`, `split=review-pending`

**Expected yield (per Frank's estimate):** 3k–5k pairs (before LaBSE threshold cut). Post-threshold ≥0.75: likely 1k–3k accept, 1k–2k review.

**Register:** encyclopedic (CC BY-SA 4.0 Wikipedia content).

**Dedup posture:** Must cluster-isolate against `wikimedia-cx-en-haw` per Frank's probe report.

---

## Impact on This Task

- **Rows scored:** **0** (no candidate JSONL to score)
- **Train-eligible rows added:** **0**
- **SFT row impact:** **0**

---

## Recommendation

**To Linus:** If sentence-level alignment is a priority, assign a new adapter task to Frank or a general-purpose agent to build the Wikipedia sentence extractor + LaBSE aligner. Once `data/stage2/candidates/wiki_haw_en_langlinks.jsonl` exists, re-run the LaBSE scorer (`scripts/336_score_comparable_with_labse.py --source wiki_haw_en_langlinks --execute`).

**To Coordinator:** This source has the **highest expected yield** (1k–3k accept rows) of the 4 LaBSE-blocked sources. If 40k SFT row target is the priority, unblocking this source should be next after scoring the existing 2 candidate JSONLs (wikimedia_cx, opus_haw_subsets).

**To Frank:** The probe script exists and provenance is captured. Next step: wire a Wikipedia article sentence extractor that respects the revision IDs in `langlinks_manifest.jsonl`.

---

**Status:** Raw probe landed, no candidates emitted, LaBSE scoring not applicable.


---

# Rusty — wikimedia_cx_en_haw LaBSE Scoring Complete

**Date:** 2026-05-02  
**Status:** ✅ Scored, ready for Linus manifest merge  
**Source:** `wikimedia_cx_en_haw`  
**Scored JSONL:** `data/stage2/_scored/wikimedia_cx_en_haw.labse.jsonl`  
**Summary:** `data/stage2/_scored/wikimedia_cx_en_haw.labse.summary.json`

---

## Scoring Results

| Metric | Count |
|---|---|
| Total rows scored | **14** |
| Accept (≥0.75) | **9** |
| Review (0.55–0.75) | **4** |
| Reject (<0.55) | **1** |

---

## LaBSE Verdict Treatment Recommendation

Per comparable-alignment policy (docs/data-pipeline.md § Stage 2 thresholds):

1. **Accept rows (9):** Set `alignment_score=<labse_score>`, `alignment_method="labse"`, `split=train`, `verdict=accept`. These are train-eligible.
2. **Review rows (4):** Set `alignment_score=<labse_score>`, `alignment_method="labse"`, `split=review-pending`, `verdict=review-required`. Manual Hawaiian-literate review recommended before promotion.
3. **Reject rows (1):** Set `alignment_score=<labse_score>`, `alignment_method="labse"`, `verdict=reject`. Do not promote to manifest.

---

## Impact on Stage 2 Manifest

- **New train-eligible rows:** +9 canonical pairs
- **Directional SFT impact:** +18 rows (9 pairs × 2 directions)
- **Register:** encyclopedic (CC BY-SA 4.0 Wikipedia content)
- **Dedup posture:** Already cluster-isolated against `wiki-haw-en-langlinks` per Frank's CX probe report

---

## Handoff to Linus

Linus owns manifest merge. Recommended actions:

1. Read `data/stage2/_scored/wikimedia_cx_en_haw.labse.jsonl`
2. Promote accept rows (9) → `stage2_manifest.jsonl` with `split=train`, `labse_score` field
3. Promote review rows (4) → `stage2_manifest.jsonl` with `split=review-pending`
4. Drop reject rows (1) — do not add to manifest
5. Re-run fixed-point cap enforcement (Bible cap may unlock additional rows)
6. Re-emit SFT JSONL with new train rows

---

## Notes

- LaBSE model: `sentence-transformers/LaBSE` (768-dim, L2-normalized embeddings)
- Scoring method: Cosine similarity on (en, haw) pairs
- ʻokina canonicalization: Applied to Hawaiian side before embedding (U+02BB canonical)
- NFC normalization: Applied to both sides
- Threshold constants: `accept_min=0.75`, `review_min=0.55` (PolicyConfig defaults)

---

**Artifacts:**
- Scored JSONL: `data/stage2/_scored/wikimedia_cx_en_haw.labse.jsonl` (gitignored)
- Summary JSON: `data/stage2/_scored/wikimedia_cx_en_haw.labse.summary.json` (gitignored)

---

# Linus — Stage-2 candidate normalization audit (Round 2)

**Date:** 2026-05-03  
**Status:** Landed dry-run audit tooling; no `data/` mutation.

## Decision

Add a dry-run-only normalization/dedup/schema audit before doing further Stage-2 manifest/cap promotion work.

## Why

Current candidate pool has enough mixed-era adapters that cap math can hide source-shape problems. The audit found:

- 37,761 candidate rows across 15 JSONL files.
- 311 Hawaiian rows need canonical ʻokina folding before clean hash/pair hash computation.
- 2,119 English rows contain apostrophes/right quotes; EN apostrophes are intentionally preserved while HAW okina-like marks are folded.
- 91 cross-source exact pair-hash duplicate groups, including OPUS-Tatoeba duplicates of upstream Tatoeba.
- Near-duplicate examples where Andrews number entries duplicate Phrase Book number rows.
- Post-policy schema violations concentrated in older/probe adapters: Gospel John/HK constitution raw-hash/license fields, Phrase Book enum drift, and wiki-langlinks probe rows.

## Consequence

Round 3 should fix adapters and regenerate candidate JSONL via each adapter's `--execute` only where already cleared, then rebuild the manifest. Do not hand-edit files under `data/`.

## Verification

- `python3 -m py_compile scripts/340_audit_stage2_candidate_normalization.py`
- `python3 code/tests/test_stage2_candidate_normalization_audit.py`
- `python3 scripts/340_audit_stage2_candidate_normalization.py --max-examples 4`
- `python3 scripts/320_build_stage2_manifest.py --dry-run`

---

# Linus — Stage-2 Legacy Candidate Normalization (Round 3)

**Date:** 2026-05-03  
**Status:** Implemented; verified dry-run—37,761 clean rows, all violations fixed.

## Decision

Build a one-shot legacy candidate normalizer to canonicalize generated candidate JSONLs under `data/stage2/candidates/` before proceeding with dedup and cap policy work. Normalizer uses `--apply` (not `--execute`) for local artifact patching; never touches `data/raw/`.

## Why

Round 2 audit identified highest-leverage blockers as schema drift in older/probe adapters plus HAW ʻokina hash drift. These are mechanical generated-artifact issues, not raw-source issues. Re-emitting through the canonical `320_build_stage2_manifest.py` contract removes schema noise before dedup/cap policy work.

## Implemented Behavior

`scripts/341_normalize_legacy_candidates.py`:

- Folds HAW ASCII/right/left quote/backtick ʻokina variants → U+02BB before `sha256_haw_clean` and `sha256_pair`
- Preserves English apostrophes/right quotes
- Maps legacy enum values → schema-compatible values (e.g., `phrase-pair` → `parallel-sentence`, coordinate pairing → `manual`) while preserving legacy detail in `notes`
- Renames probe fields (`source_id`, `source_pair_id`, `schema_version`) → canonical manifest fields
- Fills required provenance defaults for legacy rows
- Sets `license_inferred = null` and enforces `prototype_only=true => release_eligible=false`
- Recomputes clean and pair hashes; applies Stage-2 quality policy fields

## Verification (Before → After)

| Metric | Before | After | Status |
|--------|--------|-------|--------|
| Schema drift cases | 206,670 | 0 | ✓ Fixed |
| Post-policy violations | 21,118 | 0 | ✓ Fixed |
| HAW ʻokina-fold rows | 311 | 0 | ✓ Fixed |
| Pair-hash mismatches | 693 | 0 | ✓ Fixed |
| Manifest dry-run rows | — | 37,761 | ✓ Clean |
| Manifest skipped (violations) | — | 0 | ✓ All valid |

Cross-source exact pair-hash dup groups: 91 → 100 (canonical hashing surfaced more duplicates).

## Follow-up

Round 4: Codify dedup preference policy—OPUS-Tatoeba vs upstream Tatoeba (Tatoeba canonical), Bible cross-edition overlaps.

**Artifact:** Commit `2efacb6` — "Normalize legacy stage2 candidates"
# Linus — Stage-2 cross-source exact-pair dedup policy

**Date:** 2026-05-03
**Requested by:** yashasg
**Status:** Implemented in `code/llm_hawaii/stage2_dedup.py`; wired into `scripts/320_build_stage2_manifest.py`; audit-aware in `scripts/340_audit_stage2_candidate_normalization.py`.

## Problem

After legacy candidate normalization fixed canonical HAW hashing, 100 exact `sha256_pair` collisions surfaced across sources. These are not near-dupes; they are byte-identical canonical EN/HAW pair hashes and must collapse to one manifest row before cap math and SFT emission.

## Source-pair breakdown observed

- 90 groups: `opus-haw-subsets` OPUS-Tatoeba mirror vs canonical `tatoeba`.
- 9 groups: `gospel_john_1854` vs `baibala-hemolele-1868` exact John verse overlaps.
- 1 group: `opus-haw-subsets` OPUS-Wikimedia mirror vs canonical `wikimedia-cx-en-haw`.
- All groups were size 2, so 100 groups => 100 rows dropped.

## Preference rules

Ordered first-match policy for exact `sha256_pair` collision groups:

1. **Hoʻoilina over Bible** (`hooilina-over-bible`): keep Hoʻoilina if any Bible-family source exactly overlaps. Rationale: Hawaiian newspaper/periodical register is preferred over Bible register for diversity; Bible rows remain allowed when not exact duplicates.
2. **Wikimedia CX over OPUS-Wikimedia** (`wikimedia-cx-over-opus-wikimedia`): keep canonical `wikimedia-cx-en-haw`; drop OPUS mirror rows whose pair IDs classify as `opus-wikimedia-*`. Rationale: CX rows retain article/revision provenance while OPUS is derivative.
3. **Canonical Tatoeba over OPUS-Tatoeba** (`tatoeba-over-opus-tatoeba`): keep `tatoeba`; drop OPUS mirror rows whose pair IDs classify as `opus-tatoeba-*`. Rationale: canonical Tatoeba rows retain sentence/link IDs while OPUS is derivative.
4. **Baibala 1868 over other Bible editions on exact overlap** (`bible-1868-over-other-bible-editions`): keep `baibala-hemolele-1868`; drop exact duplicate Bible-family rows (`baibala-hemolele-1839`, `gospel_john_1854`, or other Bible-family IDs). Rationale: ADR allows multiple editions under the combined Bible cap, but an exact duplicate should retain the later, more standardized orthography.
5. **Fallback** (`deterministic_fallback_no_policy_rule`): only if an unexpected cross-source exact-pair group appears without a matching rule, keep the deterministic source/pair-id minimum and log the fallback for review.

## Verification

- `python3 scripts/320_build_stage2_manifest.py --dry-run`: 37,761 -> 37,661 rows; 100 duplicate groups collapsed; 0 schema violations.
- `python3 scripts/340_audit_stage2_candidate_normalization.py --strict`: raw groups 100; post-dedup exact pair groups 0; raw/post-policy schema violations 0; hash mismatches 0.
- `PYTHONPATH=code python3 -m unittest discover -s code/tests -p 'test_stage2_dedup.py'`: 5/5 pass.
- `python3 code/tests/test_stage2_manifest.py`: 45/45 pass.
- `python3 code/tests/test_stage2_candidate_normalization_audit.py`: 3/3 pass.

---

# Linus Stage-2 Round 9 license probe — Weblate EN↔HAW translation memory

Date: 2026-05-03  
Scope: license-first metadata probe only; no PO/TMX/download exports fetched.

## Source name + canonical URLs

Source: public Weblate EN→HAW/Hawaiian projects.

Instances checked:

- Hosted Weblate: <https://hosted.weblate.org/languages/haw/>
- Fedora Weblate: <https://translate.fedoraproject.org/languages/haw/>
- Codeberg Translate: <https://translate.codeberg.org/languages/haw/> — no Hawaiian projects found.
- Framasoft Weblate: <https://weblate.framasoft.org/languages/haw/> — no Hawaiian projects found.

Hosted Weblate HAW projects found from the language page:

| Instance | Project URL | Source language(s) | Component license(s) seen via Weblate API |
|---|---|---:|---|
| Hosted Weblate | <https://hosted.weblate.org/projects/django-zxcvbn-password-validator/-/haw/> | `en` | `MIT` (2 components) |
| Hosted Weblate | <https://hosted.weblate.org/projects/dpo-voyager/-/haw/> | `en` | `Apache-2.0` (2 components) |
| Hosted Weblate | <https://hosted.weblate.org/projects/f-droid/-/haw/> | `en`, `en_US` | `GPL-3.0-or-later` (7), `Apache-2.0` (3), `AGPL-3.0-or-later` (10) |
| Hosted Weblate | <https://hosted.weblate.org/projects/geoweather/-/haw/> | `en` | `Apache-2.0` (1), but HAW page showed 0% translated; likely no usable pairs yet. |
| Hosted Weblate | <https://hosted.weblate.org/projects/iso-codes/-/haw/> | `en_GB` | `LGPL-2.1-or-later` (8) |
| Hosted Weblate | <https://hosted.weblate.org/projects/prismlauncher/-/haw/> | `en_US` | `Apache-2.0` (1), `GPL-3.0-or-later` (1) |
| Hosted Weblate | <https://hosted.weblate.org/projects/stellarium-mobile/-/haw/> | `en` | `GPL-2.0-only` (2) |
| Fedora Weblate | <https://translate.fedoraproject.org/projects/rpminspect/-/haw/> | `en` | `GPL-3.0-or-later` (`main`, `glossary`) |

## License / TOS quotes

Per-project/component license values were read from the public Weblate REST API. Verbatim API fields observed:

- Hosted `django-zxcvbn-password-validator`: `"license": "MIT", "license_url": "https://spdx.org/licenses/MIT.html"`
- Hosted `dpo-voyager`: `"license": "Apache-2.0", "license_url": "https://spdx.org/licenses/Apache-2.0.html"`
- Hosted `f-droid`: `"license": "GPL-3.0-or-later"`, `"license": "Apache-2.0"`, and `"license": "AGPL-3.0-or-later"` across components.
- Hosted `iso-codes`: `"license": "LGPL-2.1-or-later", "license_url": "https://spdx.org/licenses/LGPL-2.1-or-later.html"`
- Hosted `prismlauncher`: `"license": "Apache-2.0"` for launcher component and `"license": "GPL-3.0-or-later"` for glossary component.
- Hosted `stellarium-mobile`: `"license": "GPL-2.0-only", "license_url": "https://spdx.org/licenses/GPL-2.0-only.html"`
- Fedora `rpminspect`: `"license": "GPL-3.0-or-later", "license_url": "https://spdx.org/licenses/GPL-3.0-or-later.html"`

Relevant Weblate terms page text (Hosted and Fedora terms share the Weblate-hosted terms template):

> "Translation Memory means an optional translation memory service provided on Weblate"

> "Hosted String means a text unit defined in the translation format. It can be a word, sentence, or paragraph. It is counted separately for each language"

The terms page describes the Weblate service license; it did not provide a separate public-domain/open-data grant for hosted translation strings. Therefore the component/project license must be treated as the controlling content license, with the instance TOS/robots governing access mechanics.

## Robots.txt status

- Hosted Weblate robots: `Allow: /projects/`, `Allow: /languages/`, `Allow: /exports/`, then `Disallow: /`. Metadata pages and export paths are explicitly allowed.
- Fedora Weblate robots: same pattern: `Allow: /projects/`, `Allow: /languages/`, `Allow: /exports/`, then `Disallow: /`.
- Codeberg Translate robots: same pattern, but `/languages/haw/` returned no HAW projects.
- Framasoft Weblate robots: no wildcard `User-agent: *` group was observed; named AI bots are disallowed. `/languages/haw/` returned no HAW projects.

## Access method

Next-round adapter should use Weblate public endpoints only, no auth:

1. Metadata: REST API `GET /api/projects/{project}/components/` to snapshot `license`, `license_url`, `source_language`, and component slugs.
2. Data export only after license filter: public Weblate download/TMX/PO endpoint for `haw` translations, e.g. `GET /download/{project}/{component}/haw/?format=po` or a TMX export if the instance exposes it.
3. Accept only translated HAW rows (`msgstr` non-empty); exclude suggestions, fuzzy/unapproved rows unless Weblate marks them translated.

## Rate-limit guidance

- Hosted Weblate API response headers: `x-ratelimit-limit: 100`, `x-ratelimit-remaining: 58`, `x-ratelimit-reset: 86081`.
- Fedora Weblate API response headers: `x-ratelimit-limit: 100`, `x-ratelimit-remaining: 98`, `x-ratelimit-reset: 86372`.
- Use the user-mandated polite User-Agent and at least 2 seconds between requests; keep metadata probes well below 100 requests/window. Prefer one component-list request per project, then one export request only for cleared components.

## Verdict

**YELLOW — proceed with restrictions.**

Reasoning:

- Instances found: Hosted Weblate has multiple EN-source Hawaiian projects; Fedora has `rpminspect` EN→HAW.
- Robots explicitly allow `/languages/`, `/projects/`, and `/exports/` on Hosted and Fedora Weblate.
- Component licenses are explicit. MIT and Apache-2.0 components are usable candidates under a strict open-license gate.
- Copyleft components (`GPL-*`, `LGPL-*`, `AGPL-*`) are not clearly compatible with the mixed Stage-2 training corpus and should remain blocked unless counsel/project policy explicitly approves copyleft localization strings for ML training.
- Weblate TOS does not itself grant content reuse rights; do not treat platform-level openness as sufficient.

Allowed next-round subset:

- Hosted Weblate components with `MIT` or `Apache-2.0` only: `django-zxcvbn-password-validator`, `dpo-voyager`, Apache-licensed F-Droid components, `geoweather` if translated rows exist, and the Apache-licensed Prism Launcher component.
- Exclude Fedora `rpminspect`, Hosted `iso-codes`, GPL/AGPL F-Droid components, GPL Prism glossary, and Stellarium Mobile.

## Adapter sketch

Canonical Stage-2 candidate rows:

- `source`: `weblate-en-haw`
- `source_url`: component language URL, e.g. `https://hosted.weblate.org/projects/{project}/{component}/haw/`
- `edition_or_version`: `{instance_host}@{project}/{component}/haw; license={SPDX}; probed=20260503`
- `en`: PO `msgid` / source string.
- `haw`: PO `msgstr` / Hawaiian target string.
- `register`: `software-l10n`
- `direction_original`: `en->haw` when `source_language.code` is `en`, `en_US`, or `en_GB`.
- `alignment_type`: `parallel-sentence` for single string units; `alignment_method`: `source-target-localization`.
- `split`: `review-pending` initially; promote only after quality/cap review.
- `prototype_only`: `true`; `release_eligible`: `false` until final legal review.
- `license_inferred`: `null`; store SPDX in `source_license`/metadata field if schema supports it, otherwise report sidecar.
- Filters: non-empty source/target, source language EN-family, exact component license in permissive allowlist, no fuzzy/suggestion-only rows, min-length/ratio checks.

Dedup priority slot: low-priority `software-l10n`, below canonical Tatoeba/Wikimedia/HK legal sources; prefer non-software sources on exact-pair conflicts, but keep unique software localization rows as review-pending.

## What would change the verdict

- GREEN: each fetched component has permissive SPDX license (`MIT`, `Apache-2.0`, `BSD-*`, `ISC`, `CC0`, `CC-BY`) plus a stable, robots-allowed export endpoint and an on-disk TOS snapshot.
- RED for any component if license is missing, project-level license conflicts with component license, export path becomes robots-disallowed, or the instance requires auth/paywall/API terms that prohibit reuse.

---

# Linus Stage-2 Round 9 license probe — Global-PIQA haw_Latn

Date: 2026-05-03  
Scope: license-first Hugging Face metadata probe only; no TSV/raw dataset download.

## Source name + canonical URLs

Source: Global PIQA Parallel, Hawaiian Latin-script configuration.

Canonical URLs:

- Dataset card: <https://huggingface.co/datasets/mrlbenchmarks/global-piqa-parallel>
- Raw card metadata: <https://huggingface.co/datasets/mrlbenchmarks/global-piqa-parallel/raw/main/README.md>
- HF dataset API: <https://huggingface.co/api/datasets/mrlbenchmarks/global-piqa-parallel>
- Dataset-server metadata: <https://datasets-server.huggingface.co/splits?dataset=mrlbenchmarks/global-piqa-parallel&config=haw_latn>
- File listed by card/API: `data/parallel_haw_latn.tsv`
- Repository commit observed from HF metadata/download checksums elsewhere in the dataset-server response: `a350910e9cfc8b0b57cb55aa8261780deabb6568`.

## License / dataset-card quotes

Verbatim dataset card/API license fields:

> `license: cc-by-sa-4.0`

> `cardData license: cc-by-sa-4.0`

Verbatim dataset card license section:

> "Global PIQA is released under a [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.en) license. However, we do <b>not</b> allow training of AI systems on Global PIQA, or on synthetic data that uses Global PIQA as a seed."

> "Global PIQA is intended for LLM evaluation only."

Dataset card description of construction:

> "In the parallel split, each example was machine-translated from English, then manually corrected by a native speaker of the target language."

## Robots.txt status

- `https://huggingface.co/robots.txt`: `User-agent: *` and `Allow: /`.
- `https://datasets-server.huggingface.co/robots.txt`: returned 404 (no robots.txt found). Treat as no robots restriction found for metadata endpoints, but keep access minimal.

## Access method

Allowed next-round access method is metadata/eval-only HF access, no auth:

1. Use HF dataset API/card to pin repo id, commit SHA, license, and file path.
2. Use datasets-server metadata endpoints for splits/schema where available.
3. If building the eval ledger, fetch only `data/parallel_haw_latn.tsv` once after recording the no-training license restriction; hash rows into `data/evals`/`data/final` ledger before any train ingest.
4. Do **not** use `load_dataset()` in training code or any train candidate adapter.

## Rate-limit guidance

HF API response headers from the dataset API:

- `RateLimit: "api";r=499;t=240`
- `RateLimit-Policy: "fixed window";"api";q=500;w=300`

Use the user-mandated polite User-Agent and at least 2 seconds between requests. A next-round eval adapter should need one API/card request plus one raw TSV GET if approved.

## Schema and row-count findings

Config/split from card and dataset-server:

- `config_name: haw_latn`
- split: `test`
- file path: `data/parallel_haw_latn.tsv`

Field schema from dataset-server preview metadata:

| Field | Type |
|---|---|
| `prompt` | string |
| `solution0` | string |
| `solution1` | string |
| `solution2` | string |
| `solution3` | string |
| `label` | int64 |
| `language` | string |
| `eng_prompt` | string |
| `eng_solution0` | string |
| `eng_solution1` | string |
| `eng_solution2` | string |
| `eng_solution3` | string |
| `categories` | string |
| `example_id` | string |
| `supplement` | string |

Row count: **103 test examples** for `haw_Latn`/`haw_latn` is the operational count to plan around. Caveat: the direct `datasets-server /size?dataset=...&config=haw_latn` endpoint returned 500 and the all-config `/info` response did not include `haw_latn`, so this count is inferred from the dataset-server size pattern for cached Global-PIQA parallel configs (103 rows/config) and from the preview endpoint showing the `haw_latn` test split. Confirm by counting TSV lines only in the next round if proceeding with eval-ledger ingestion.

## Verdict

**YELLOW — EVAL-only; do not train.**

Reasoning:

- Dataset is public on HF and the card/API license is explicit (`cc-by-sa-4.0`).
- The dataset card adds an explicit no-training restriction: "we do not allow training of AI systems" and "intended for LLM evaluation only."
- Therefore it must **not** route to TRAIN and must not seed synthetic/back-translation data.
- It can proceed only as an eval/final ledger source, consistent with existing Stage-2 docs that list `global-piqa-parallel` as a milestone holdout/eval anchor.

## Adapter sketch

Do not create Stage-2 training candidates. Build an eval/final ledger ingester instead:

- `origin`: `global-piqa-parallel-haw`
- `division`: `final` (major-milestone holdout) unless evaluator owner chooses `evals`.
- `split`: `test`
- `edition_or_version`: `mrlbenchmarks/global-piqa-parallel@a350910e9cfc8b0b57cb55aa8261780deabb6568; config=haw_latn; split=test; license=CC-BY-SA-4.0; no-training`
- Preserve row id: `example_id`.
- Evaluation schema: PIQA multiple-choice, not simple parallel training rows.
  - Hawaiian prompt/options: `prompt`, `solution0`..`solution3`.
  - English prompt/options for reference/diagnostics only: `eng_prompt`, `eng_solution0`..`eng_solution3`.
  - Gold answer: `label`.
  - Metadata: `language`, `categories`, parsed `supplement` JSON if needed.
- Hash ledger before use: hash Hawaiian prompt+options+label and optionally English prompt+options to prevent contamination.
- Dedup priority: eval-only ledger, not part of train dedup priority. If any text overlaps existing train rows, train rows must be dropped/held out, not this eval source.

## What would change the verdict

- GREEN for TRAIN would require the dataset owner to remove the no-training restriction and publish a training-compatible open license (for example CC0/CC-BY or an explicit dataset-card grant permitting ML training). Current CC-BY-SA plus the explicit no-training sentence is not train-compatible.
- RED would apply if the owner disallowed evaluation use, if HF access became gated/authenticated, or if the card license became ambiguous. Current card explicitly permits evaluation intent, so eval-only remains YELLOW.
# Linus Stage-2 Round 10 — Weblate permissive-only adapter shipped

Date: 2026-05-03

## Verdict

Adapter-ready, awaiting `--execute`. No live network calls were made in Round 10; tests use mocked HTTP and an inline TMX fixture only.

## SPDX allowlist

Accepted exact SPDX IDs:

- `MIT`
- `Apache-2.0`
- `BSD-2-Clause`
- `BSD-3-Clause`
- `MPL-2.0`
- `CC0-1.0`
- `CC-BY-4.0`

Allowlist regex: `^(MIT|Apache-2\.0|BSD-2-Clause|BSD-3-Clause|MPL-2\.0|CC0-1\.0|CC-BY-4\.0)$`

Blocked: GPL family, AGPL, LGPL, CC-BY-SA, all-rights-reserved, missing/ambiguous license.

## Instance list

- Hosted Weblate: `https://hosted.weblate.org`
- Fedora Weblate: `https://translate.fedoraproject.org`

Round 9 found Hosted Weblate has permissive MIT/Apache HAW components; Fedora `rpminspect` was GPL and remains blocked unless policy changes.

## What is gated behind `--execute`

Discovery (`scripts/345_discover_weblate_haw_projects.py`) refuses live HTTP unless all gates pass:

1. `--execute`
2. `--instance hosted|fedora|all`
3. `--confirm-license-allowlist` exactly matching the allowlist regex above
4. `--tos-snapshot` pointing at an existing local TOS snapshot file
5. polite User-Agent, >=2s sleep, <=30 requests/minute default

Candidate build (`scripts/346_build_weblate_candidates.py`) refuses TMX downloads/writes unless all gates pass:

1. `--execute`
2. `--inventory` pointing at a local discovery TSV
3. exact allowlist confirmation
4. local TOS snapshot file
5. accepted inventory row (`accepted=true`) and exact allowlisted SPDX license

Output on execute: `data/stage2/candidates/weblate.jsonl` (under gitignored `data/`). Rows remain `prototype_only=true`, `release_eligible=false`, `split=review-pending`, `register=software-l10n`.
# Linus Stage-2 Round 11 — Global-PIQA eval-only ingester

Date: 2026-05-03

## Verdict carried forward

Global-PIQA `haw_Latn` remains **YELLOW / eval-only**. The dataset card advertises `CC-BY-SA-4.0`, but also explicitly forbids AI training and says the dataset is intended only for LLM evaluation. Therefore this source must not create Stage-2 train candidates and must not seed synthetic data.

## Implementation

- Added `scripts/347_ingest_global_piqa_haw.py`.
- No live network is implemented or tested.
- `--self-test` uses an inline 3-row TSV fixture and writes eval hashes only.
- `--execute` is triple-gated:
  - exact dataset pin: `mrlbenchmarks/global-piqa-parallel@a350910e9cfc8b0b57cb55aa8261780deabb6568`
  - exact license confirmation: `CC-BY-SA-4.0`
  - local ToS/license snapshot path
- `--execute` still requires a local TSV path; it does not fetch from Hugging Face.
- Ledger output appends to `data/evals/eval_hashes.jsonl` with `source`, `item_id`, `content_sha256`, `license_spdx`, `license_url`, `dataset_revision`, `fetched_at`, and `eval_only: true`.
- The ingester refuses any output path under `data/stage2/candidates/`.

## Contamination guard

Added `code/llm_hawaii/eval_contamination.py` and wired `scripts/320_build_stage2_manifest.py --eval-hashes`. When an eval ledger path is explicitly supplied, matching Stage-2 candidates are dropped before manifest emission and the drop count is recorded as `eval_contamination_dropped`. If `--eval-hashes` is absent, build behavior remains unchanged.

Normalization is NFC + whitespace collapse. Hawaiian maps ASCII/curly apostrophe variants to U+02BB ʻokina; English maps apostrophe variants to ASCII apostrophe. This makes PIQA eval hashes usable as a train-side backstop for future candidate rows with matching normalized content.

## Verification

- `python3 code/tests/test_global_piqa_ingester.py -v`: 5 tests passed.
- `python3 code/tests/test_eval_contamination.py -v`: 4 tests passed.
- `python3 scripts/320_build_stage2_manifest.py --dry-run`: 37,084 rows.
- `python3 scripts/320_build_stage2_manifest.py --dry-run --eval-hashes data/evals/r11_empty_eval_hashes.jsonl`: 37,084 rows, 0 contamination drops.

## Next

Recommended Round 12: probe another eval-only diagnostic (Taxi1500) or refresh Tatoeba before adding more train-side sources.

---

# Stage-2 Round 12 — Taxi1500 License-First Probe

**Owner:** Linus  
**Date:** 2026-05-03  
**Status:** Verdict finalized

## Canonical URL

- Repository: `https://github.com/cisnlp/Taxi1500`
- Stage-2 registry entry: `data-sources/stage2-parallel-fetch-plan.json:414-450`
- Prior inventory alias: `cis-lmu/Taxi1500-RawData` / `haw_Latn`, documented in `.squad/decisions-archive.md:2220-2252`.

## Network/TOS clearance

Allowed metadata-only requests made with a polite UA; no corpus zip, TSV, split file, or authenticated endpoint was fetched.

- `https://github.com/robots.txt`: HTTP 200. `User-agent: *` blocks raw/tree/search-like crawler paths on `github.com`, but the repository README was read via `raw.githubusercontent.com` as a license/card-style metadata page; no bulk data path was fetched.
- `https://raw.githubusercontent.com/cisnlp/Taxi1500/main/README.md`: HTTP 200; repository card/README only.
- `https://raw.githubusercontent.com/cisnlp/Taxi1500/main/LICENSE`: HTTP 200; license text only.
- `Taxi1500-c_v1.0/README.md` and `Taxi1500-c_v2.0/README.md`: HTTP 200; subdirectory README metadata only.

## License

Repository `LICENSE` is Apache-2.0. Verbatim grant excerpt:

> "Apache License Version 2.0, January 2004"
>
> "Subject to the terms and conditions of this License, each Contributor hereby grants to You a perpetual, worldwide, non-exclusive, no-charge, royalty-free, irrevocable copyright license to reproduce, prepare Derivative Works of, publicly display, publicly perform, sublicense, and distribute the Work and such Derivative Works in Source or Object form."

Important caveat from the README:

> "While Taxi1500 covers 1502 languages in total, we release 1871 editions in 823 languages which are either open access or have a license permitting distribution at the time of publication. Due to copyright restrictions, these are released as a corpus instead of the actual dataset, and can be converted into the dataset format shown below using the included processing code."

Subdir metadata says v1.0/v2.0 corpora are downloadable ZIPs from LMU and explains permissive filtering, but those ZIPs were not fetched.

## haw_Latn coverage

- Coverage remains **not count-confirmed** in this no-data-fetch probe.
- Existing project inventory says `cis-lmu/Taxi1500-RawData` has `haw_Latn` and describes it as "Bible-derived topic classification eval" (`.squad/decisions-archive.md:2220-2252`).
- The active fetch plan still marks `taxi1500-haw` as `verification_status: pending_endpoint_check` and `adapter_status: none` (`data-sources/stage2-parallel-fetch-plan.json:414-450`).
- Train/dev/test row counts for `haw_Latn`: **unknown from the allowed README/license pages**. Confirming counts appears to require either fetching/listing corpus/split contents or using a dedicated metadata endpoint not cleared in this round. Under the hard rule, stop here rather than infer counts.

## Schema

README dataset structure:

| Field | Meaning |
|---|---|
| `id` | verse id |
| `label` | topic label |
| `verse` | verse text |

Label set quoted from the README table:

- `Recommendation`
- `Faith`
- `Description`
- `Sin`
- `Grace`
- `Violence`

## Contamination risk

**High.** Taxi1500 is explicitly Bible-derived:

> "Taxi1500 is developed based on the PBC and 1000Langs corpora."

The task examples are Bible verses, and the Stage-2 plan already says "never train on FLORES / global-piqa / Taxi1500" (`data-sources/stage2-parallel-fetch-plan.json:975`). Any Hawaiian rows may overlap semantically or exactly with existing Baibala 1839 / Baibala 1868 / BibleNLP-style candidate rows. If ever ingested, every row must be registered in `data/evals/eval_hashes.jsonl` before any train manifest build, and train candidates matching Taxi1500 verse hashes must be dropped or quarantined.

## Verdict

**YELLOW — EVAL-only pending count/pin confirmation.**

The repo license is clear for repository contents, but the released corpus is Bible-derived and count/split metadata for `haw_Latn` was not safely confirmable without fetching data. Routing remains diagnostic/eval-only, never TRAIN.

## Routing

**EVAL-only.** Rationale:

1. Bible-domain classification, not translation training data.
2. Direct contamination risk against existing Bible 1839/1868 rows.
3. Existing project policy explicitly says never train on Taxi1500.
4. Split/count confirmation still needs a later metadata-cleared or local-file round.

## Adapter sketch if proceeding

Do not create `data/stage2/candidates/` rows. Build an eval-ledger ingester only after a future round confirms `haw_Latn` counts and pins an exact commit or release artifact:

- Require exact source pin: repo commit plus corpus version (`Taxi1500-c_v1.0` or `Taxi1500-c_v2.0`) and local license/TOS snapshot.
- Require operator confirmation: `--confirm-routing EVAL_ONLY_NO_TRAIN`.
- Parse fields `id`, `label`, `verse`; reject rows outside the six-label set.
- Emit only `data/evals/eval_hashes.jsonl` entries with `origin=taxi1500-haw`, `eval_only=true`, `content_sha256`, `label`, and source row id.
- Before manifest emission, use the existing eval contamination guard to exclude matching Bible-family train rows.

---

# Stage-2 Round 12 — Tatoeba Refresh License-First Probe

**Owner:** Linus  
**Date:** 2026-05-03  
**Status:** Verdict finalized; gated next round

## Current registry pin

- Fetch plan source: `tatoeba-haw-eng` (`data-sources/stage2-parallel-fetch-plan.json:188-229`).
- Adapter pin: `data-sources/tatoeba/PINNED_DUMP.json` records `dump_date: 2025-05-01`, `license: CC-BY 2.0 FR`, and the haw/eng/link export URLs.
- Adapter README records the same pinned dump date and says raw downloads live under `data/raw/tatoeba-haw-eng/<YYYYMMDD>/` (`data-sources/tatoeba/README.md:7-17`, `:56-60`). No raw Tatoeba dump directory is present locally.
- Current local direct Tatoeba candidate file: `data/stage2/candidates/tatoeba.jsonl` has 121 rows, 111 unique `tatoeba_sentence_id_haw` values. The finalized review manifest has 121 Tatoeba rows: 105 train, 15 dev, 1 held-out/finalized.

## Network/TOS clearance

Allowed metadata-only requests made with a polite UA; no Tatoeba export body was downloaded.

- `https://tatoeba.org/robots.txt`: HTTP 200. It specifies `Crawl-delay: 8`; this probe used >=8s sleeps for Tatoeba requests. The stats page is not disallowed.
- `https://downloads.tatoeba.org/robots.txt`: HTTP 404; no robots restriction found for download metadata. Only HEAD requests were sent to export URLs.
- `https://tatoeba.org/eng/stats/sentences_by_language`: HTTP 200; public stats page only.
- `https://tatoeba.org/eng/terms_of_use`: HTTP 200; license/TOS page only.
- HEAD metadata only:
  - `haw_sentences_detailed.tsv.bz2`: `Last-Modified: Sat, 02 May 2026 06:25:58 GMT`, `Content-Length: 3039`.
  - `haw-eng_links.tsv.bz2`: `Last-Modified: Sat, 02 May 2026 06:33:37 GMT`, `Content-Length: 941`.

## License confirmation

Tatoeba terms still state the text-sentence default license. Verbatim excerpt:

> "Tatoeba's technical infrastructure uses the default Creative Commons Attribution 2.0 France license (CC-BY 2.0 FR) for the use of textual sentences. The BY mention implies a single restriction on the use, reuse, modification and distribution of the sentence: a condition of attribution. That is, using, reusing, modifying and distributing the sentence is only allowed if the name of the author is cited."

Existing adapter policy is still correct: preserve `contributor_haw`, `contributor_en`, sentence IDs, and source URLs for attribution flow-down.

## Latest public haw sentence count

The public stats page row for Hawaiian is:

```html
<tr><td>222</td><td>... alt="haw" title="Hawaiian" ...</td><td>haw</td><td>...Hawaiian...</td><td class="num-sentences"><div class="bar" style="width:0.0094427545301861%"></div>192</td></tr>
```

Latest public Hawaiian sentence count: **192**.

## Comparison to pinned edition

Exact pinned total Hawaiian sentence count is **not stored** in `PINNED_DUMP.json` or the README; local raw downloads are absent. The local candidate artifact has 121 en↔haw rows and 111 unique Hawaiian sentence IDs, which is a linked-pair count, not the same denominator as the stats page's total Hawaiian sentence count.

Best safe delta estimate without re-download:

- Latest total haw sentences: 192.
- Current local linked haw sentence IDs: 111.
- Upper-bound unrepresented Hawaiian sentences relative to our linked set: **up to 81**.
- Upper-bound new en↔haw pair opportunity relative to 121 current pairs: **up to 71** if every extra Hawaiian sentence has an English link; actual pair delta may be lower and requires a future licensed export refresh/count.
- Export `Last-Modified` dates are 2026-05-02, newer than the 2025-05-01 pin, so metadata indicates the export changed since our pin.

## Refresh trigger threshold

Recommend refresh when either condition is met:

1. Confirmed en↔haw pair delta is **≥5%** of the pinned 121 pairs (≥7 new linked pairs), or
2. Confirmed new Hawaiian sentence count is **≥500**.

For this tiny source, the 5% linked-pair threshold is the practical trigger; 500 new Hawaiian sentences is a long-tail safeguard for larger future growth.

## Verdict

**REFRESH-NOW for a gated next round; no data fetched in this round.**

Reason: license remains clear, export metadata is newer than the 2025-05-01 pin, and the latest public haw count (192) leaves a large enough upper-bound gap versus the local linked set (111 unique haw IDs / 121 pairs) to exceed the 5% trigger if even a small fraction are English-linked.

## Next adapter action

In a separate execute-approved round:

- Reconfirm robots/TOS snapshots.
- HEAD all three pinned export URLs and record `Last-Modified`, `Content-Length`, and hashes after download.
- Download only the three existing Tatoeba export files, rebuild `data/stage2/candidates/tatoeba.jsonl`, and report exact pair delta.
- Preserve the current split policy: hash before split, keep held-out/dev rows protected, and prefer canonical Tatoeba over OPUS-Tatoeba duplicates.

---

# Linus Stage-2 Round 13 — Adapters Shipped

**Date:** 2026-05-03  
**Owner:** Linus  
**Status:** Implemented / awaiting gated `--execute`

## Decision

Ship two mocked, dry-run-only Stage-2 adapters now so execution can happen later only after explicit rights gates.

1. **Taxi1500 haw_Latn** is eval-only. `scripts/348_ingest_taxi1500_haw.py` writes only eval-ledger rows with `eval_only=true`, `license_spdx=Apache-2.0`, and `bible_overlap_candidate=true`; it refuses `data/stage2/candidates/` outputs.
2. **Tatoeba refresh** is train-candidate capable but gated. `scripts/349_refresh_tatoeba_candidates.py` writes `data/stage2/candidates/tatoeba_refresh_{date}.jsonl` only under `--execute` with edition date, `CC-BY-2.0-FR` confirmation, local ToS snapshot, polite UA, ≥2s sleeps, existing-edition dedup, and refresh threshold pass.

## Compliance

No live network was used. No `--execute` was run. Tests use only inline fixtures / local mocked rows. The ambiguous Taxi1500 split path is not fetched; later execution must provide a concrete local file and dataset pin in `org/repo/<40hex>` form.

## Verification

- `python3 code/tests/test_taxi1500_ingester.py -v` — 6 tests passed
- `python3 code/tests/test_eval_contamination.py -v` — 5 tests passed
- `python3 code/tests/test_tatoeba_refresh.py -v` — 7 tests passed
- `python3 scripts/320_build_stage2_manifest.py --dry-run` — 37,084 rows

## Next

Recommended Round 14: wire train-side eval-contamination filtering into the default manifest dry-run path, then probe Common Voice metadata, FLORES+ haw, or OPUS-TildeMODEL license/endpoint status.

---

### 2026-05-04T05:51:29Z: Stage 2 Sequence Length Audit & Quarantine (Merged from inbox)
**By:** Linus (Data Engineer)  
**Status:** ✅ Implemented & Completed

## Stage 2 max_seq_len Bump — Audit & Decision

Measured token lengths across 38,069 pairs in Stage 2 training manifest using Llama-3.1-8B tokenizer. Key findings:

**Distribution:** p50=87, p90=155, p95=184, p99=1,429, max=43,573 tokens  
**Critical outlier:** hk_statutes_1897 (49c3a67cb384) at 43,573 tokens — data alignment error (134K HAW vs 780 chars EN)  
**Legitimate max:** Hoʻoilina full-document pairs at 25-34K tokens (3 of 128 records)

**Decision:** Set `max_seq_len=2048` in `code/configs/stage2_prototype.json`

**Rationale:** Covers p99 with headroom (2048 > 1,429), avoids 83x memory explosion (1024 → 43,776 would require ~83x attention memory). Truncates only ~10 extreme outliers (0.026% of 38,069).

**Implementation:** ✅ Config updated, audit report generated (`data/stage2/reports/seq_len_audit_20260504.json`), 72 unit tests passed.

## Stage 2 Quarantine seq_len Outliers

Follow-up action: Full scan identified 25 TRAIN rows (all Hoʻoilina) exceeding 2048-token limit.

**Action:** Moved 25 rows from `split="train"` → `split="review-pending"` with reason `"seq_len_outlier_paragraph_split_failure"`

**Manifest transformation:**
- TRAIN rows: 5,436 → 5,411 (-25)
- Pair tokens: 595,046 → 382,760 (-212,286)
- Max seq_len: 28,584 → 1,947 ✓ Under 2048
- Rows > 2048: 25 → 0 ✓ All quarantined

**New canonical manifest:** `data/stage2/reviewed_stage2_manifest_final_capped_v2_dedup_quarantined.jsonl`

**Side effect — Cap violations:** Quarantining removed 212K non-capped Hoʻoilina tokens, increasing relative share of capped sources:
- Bible: 25.54% → 39.71% (30% cap exceeded)
- HK-Legal: 13.01% → 20.23% (15% cap exceeded)

**Why:** Absolute token counts for Bible/HK-Legal unchanged; percentages increased due to removal of non-capped tokens.

**Resolution needed:** Yashas to decide:
1. Accept current distribution (5,411 TRAIN rows, 383K tokens)?
2. Re-apply caps post-quarantine (drop ~57K capped tokens)?
3. Add non-Bible/non-HK-legal content to rebalance?

**Recommendations:**
1. **Short-term:** Use 5,411-row TRAIN split for next training run; defer cap rebalancing to Yashas.
2. **Medium-term:** Re-split 25 quarantined Hoʻoilina rows at sentence granularity (potential 100-200 valid pairs).
3. **Follow-up:** Manual inspection of hk_statutes_1897 alignment error; move to `split="rejected"` if confirmed.

**Artifacts:**
- Audit script: `scripts/audit_seq_len_stage2.py`
- Audit report: `data/stage2/reports/seq_len_audit_20260504.json`
- Orchestration logs: `.squad/orchestration-log/2026-05-04T05-51-29Z-linus-{seqlen,quarantine}.md`
- Session log: `.squad/log/2026-05-04T05-51-29Z-stage2-seqlen-bump.md`
