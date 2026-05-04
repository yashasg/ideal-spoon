# Decisions

> Updated 2026-05-04T08:13:26Z: Merged Rusty frontier inbox: gpt-4o live baseline, GPT-5 parameter/determinism handling, GPT-5-chat rate-limit blocker, frontier PPL chart policy, and Stage 1 checkpoint-10140 comparison row.

>


---

# Rusty Frontier Eval Follow-ups — Live Baseline, GPT-5 Blocker, PPL Policy, Stage 1 Row

**Date:** 2026-05-04T08:13:26Z  
**Owner:** Rusty (NLP Researcher)  
**Status:** ✅ Merged; GPT-5-chat remains blocked by rate limits

## Live frontier baseline

Rusty corrected the GitHub Models catalog/inference endpoint to `https://models.github.ai/inference/chat/completions` and successfully ran the frozen `stage0.v1` eval contract against `openai/gpt-4o`.

| Metric | Stage 0 Llama-3.1-8B | openai/gpt-4o | Delta |
|---|---:|---:|---:|
| EN→HAW char-F1 | 0.329114 | 0.398827 | +21.2% |
| HAW→EN char-F1 | 0.469799 | 0.617021 | +31.3% |
| Wrong ʻokina | 0 | 0 | 0 |
| Kahakō | 34 | 32 | -2 |
| Hawaiian PPL | 7.9152 | N/A | not_supported |

Artifacts: `docs/eval-runs/frontier/20260504T073812Z__frontier_github-models_openai_gpt-4o_eval_summary.json`, `docs/eval-runs/frontier/20260504T074014Z__s0_vs_frontier_comparison.md`, and `data/evals/eval_hashes.jsonl`.

## GPT-5 family handling

`code/llm_hawaii/eval_frontier.py` now routes GPT-5/o-series models through reasoning-model settings: `max_completion_tokens`, no `temperature`, no `top_p`, and identity/decoding metadata marking outputs as non-deterministic. GPT-4o and standard chat models remain deterministic with `temperature=0` and `max_tokens`.

`openai/gpt-5-chat` smoke-tested successfully, but full eval is blocked by GitHub Models rate limits. Retries at `2026-05-04T07:59:05Z`, `2026-05-04T08:01:15Z`, and `2026-05-04T08:09:11Z` failed before complete artifacts. No GPT-5-chat metrics are copied, inferred, or fabricated.

## Frontier PPL chart policy

Frontier comparison charts must not present Hawaiian PPL as a direct GPT/Claude/Gemini comparison metric. Use `N/A` / `not_supported` or omit PPL from frontier comparison views because closed chat-completions APIs do not expose token logprobs over arbitrary held-out text. Local Stage 0/1/2 PPL remains an our-model-only checkpoint diagnostic.

1:1 frontier/local comparison metrics remain: frozen `human_fetch` EN→HAW and HAW→EN char-F1, orthography aggregates (wrong ʻokina, kahakō, NFC), prompt-suite generations, and tripwires.

## Stage 1 checkpoint-10140 row

The frontier comparison report now includes Stage 1 `checkpoint-10140` from `data/eval_runs/stage1/20260504T080245Z__stage1_checkpoint-10140_eval.json`.

| Cell | Value |
|---|---:|
| EN→HAW char-F1 | 0.443894 |
| HAW→EN char-F1 | 0.346667 |
| Wrong ʻokina | 0 |
| Kahakō | 53 |
| NFC failures | 0 |
| Tripwires | pass |

Local checkpoint diagnostic PPL: Stage 0 `7.9152` → Stage 1 `3.6229` (`-54.2%`). This is not a frontier-chart column.

---

# Frontier Eval Harness — GitHub Models + Semantic Kernel

**Date:** 2026-05-04T07:17:38Z  
**Owner:** Rusty (NLP Researcher)  
**Status:** ✅ Implemented (mock/dry-run only; user will execute against live API)

## Context

The project needs to evaluate frontier chat models (OpenAI GPT, Anthropic Claude) as baselines for Stage 0/1 local HF model evals. The goal is to use the SAME eval contract (frozen `stage0.v1` prompt suite, human_fetch translation probe, orthography metrics) for direct comparison on metrics both model types support.

## Decision

Build a frontier eval harness using:
1. **GitHub Models API** as the model endpoint
2. **GitHub token** (`gh auth token`) as the auth mechanism
3. **Semantic Kernel (Python)** as the provider-agnostic orchestration layer
4. **Same eval contract** as Stage 0/1

## Deliverables

| Component | Path | Purpose | Status |
|---|---|---|---|
| **Requirements** | `requirements-eval-frontier.txt` | Pinned: semantic-kernel, httpx, tenacity, openai | ✅ |
| **Eval module** | `code/llm_hawaii/eval_frontier.py` | Frontier eval logic | ✅ |
| **Shell wrapper** | `scripts/run_frontier_eval.sh` | Multi-model sweep | ✅ |
| **Tests** | `code/tests/test_eval_frontier.py` | 9 unit tests, all pass | ✅ |
| **Docs** | `docs/eval_pipeline.md` §9 | Frontier baselines section | ✅ |

## Honesty on PPL

**Hawaiian PPL:** Marked `not_supported` for closed frontier APIs.
- Chat-completions endpoints do not expose token-level log probabilities.
- This is an **intrinsic API limitation**, not a missing feature.

## What WORKS

- **Generations:** Full prompt suite (7 samples: 1 English + 6 Hawaiian)
- **Orthography:** ʻokina, kahakō, NFC integrity, diacritic density
- **Translation probe:** en↔haw char-bigram F1
- **W1 probe:** Metadata/validation status

## Schema Parity

Frontier eval emits `stage0_eval.v2` with `provider: github-models`, `is_local: false`, `supports_logprobs: false`, `hawaiian_ppl.status: not_supported`.

## Auth

Primary: GitHub Models + `gh auth token` (requires `copilot` or `models:read` scope).
Fallback (stubs): Direct OpenAI / Anthropic keys.

## Default Models

- `gpt-4o` — OpenAI flagship
- `claude-3.5-sonnet` — Anthropic fast
- `claude-opus-4` — Anthropic reasoning

User override: `MODELS="gpt-4o,gpt-5" ./scripts/run_frontier_eval.sh`

## Testing

9 unit tests, all passing, all mocked (no live API calls).

## Comparison Contract

**Comparable to Stage 0/1 on:**
- Translation F1 (en→haw, haw→en)
- Orthography metrics
- Prompt suite generations (qualitative)
- W1 metadata/validation

**NOT comparable on:**
- Hawaiian PPL (not_supported)
- Tokenizer-opaque metrics

## Session Constraints

✅ No live API calls  
✅ Stage 0 contract FROZEN  
✅ Schema FROZEN  
✅ Honest about PPL gap  

## Next Actions (User)

1. Verify token scope: `gh auth status`
2. Verify model availability on GitHub Models marketplace
3. Dry-run: `DRY_RUN=1 ./scripts/run_frontier_eval.sh`
4. Execute: `./scripts/run_frontier_eval.sh`
5. Compare frontier F1 + orthography vs Stage 0 anchor

---

# Rusty — Stage 1 Checkpoint-10100 Eval Blocker

**Date:** 2026-05-04T07:03:09Z  
**Owner:** Rusty (NLP Researcher)  
**Status:** BLOCKED — full eval requires GPU + authenticated private checkpoint access

## Checkpoint Correction

The requested checkpoint is **checkpoint-10100** (corrects prior checkpoint-10140 mention).

## Confirmed

- Frozen eval bundle: `schema_version="stage0_eval.v2"`
- Frozen prompt suite: `PROMPT_SUITE_ID="stage0.v1"`, hash `2683027f538ae8fb2910f758f2865596355893cc91c85dbdfe9ced130797bce6`
- Eval input exists: `data/evals/fineweb2_haw/dev.jsonl`, 621 scored records
- `human_fetch` translation probe exists locally
- **No local checkpoint-10100** under `runs/` or `data/`
- **Local runtime not viable:** no torch, no CUDA, no HF_TOKEN
- HF API probes return `401` for private repos:
  - `yashasg/llama31-8b-stage1-haw`
  - `RainbowMassacre/llama31-hawaii-checkpoints`

## To Unblock

GPU access (A100/Lambda preferred, Kaggle T4x2 acceptable) with:
- Read access to private checkpoint repo
- HuggingFace token auth
- torch/CUDA environment

## Stage 0 → Stage 1 Comparison

| Metric | Stage 0 base | Stage 1 checkpoint-10100 | Status |
|---|---:|---:|---|
| Hawaiian PPL | 7.9152 | blocked | awaiting inference |
| human_fetch en→haw F1 | 0.329114 | blocked | awaiting inference |
| human_fetch haw→en F1 | 0.469799 | blocked | awaiting inference |

## Interpretation

No Stage 1 learning claim yet. Only valid statement: **comparison blocked before inference**. Without checkpoint-10100 + GPU, any S0→S1 delta would be fabricated.

## Coordination

Basher: Provide GPU eval target with HF read access to private checkpoint repo, then run `scripts/run_stage1_eval.sh`. Return Stage 1 summary JSON for final S0→S1 delta report.

---


# Stage 2 Hoʻoilina Strict Resplit & SFT Emit — v3 Manifest Final

**Date:** 2026-05-04T06:38:49Z  
**Owner:** Linus (Data Engineer)  
**Status:** ✅ Complete & Emitted

## Context

Following the initial v3 Hoʻoilina resplit recovery that re-admitted 861 loosely resplit children, a stricter rebuild was requested to eliminate half-blank chunks and re-align paragraphs by their numbered structure (EN: § 1, 2, 3; HAW: matching sections). This refinement preserved the v3 philosophy while raising consistency standards.

## Decision

Replace in-place all 861 loose Hoʻoilina children in the v3 manifest (`reviewed_stage2_manifest_final_capped_v3.jsonl`) with a stricter paragraph-aligned rebuild. Pre-snapshot the prior v3 before modification.

## Results

| Metric | Loose → Strict | Value |
|--------|---|---|
| Loose children (TRAIN) | 861 | — |
| Half-blank children (dropped) | 185 | — |
| Strict children (admitted) | 725 | ✅ |
| Unsalvageable rows (ejected) | 136 | — |
| New dedup collisions | 0 | ✅ |
| Final TRAIN pairs | — | 6,136 |
| Bible % | — | 26.18% (≤30%) ✅ |
| HK/legal % | — | 13.45% (≤15%) ✅ |
| Rows > 2048 tokens | — | 0 ✅ |

## Manifest Artifacts

- **Updated v3 manifest:** `data/stage2/reviewed_stage2_manifest_final_capped_v3.jsonl` (manifest hash: `4cff0b826c5c423ba57bcdb3e83d20a3def2bcb4b49fa64fd6ac72c65fd55ff1`)
- **Pre-strict snapshot:** `data/stage2/reviewed_stage2_manifest_final_capped_v3_pre_strict_resplit.jsonl` (source hash: `1c0bdf803676c0eac5093ca53bebf1afdca7f80071608ff11ba696244ad39a27`)

## SFT Emit Outcome

```bash
python3 scripts/330_emit_stage2_sft_jsonl.py \
  --manifest data/stage2/reviewed_stage2_manifest_final_capped_v3.jsonl \
  --out data/stage2/stage2_sft.jsonl \
  --splits train \
  --directions both \
  --allow-review-required
```

**Output:** 
- File: `data/stage2/stage2_sft.jsonl`
- Pairs: 6,136 (12,272 SFT rows)
- Size: 12.1 MiB

## Gating Status

✅ All Stage 2 gates satisfied:
1. Max sequence length ≤2048 tokens (actual max 1,946)
2. Bible % < 30%
3. HK/legal % < 15%
4. Zero blank TRAIN rows
5. Zero new dedup collisions
6. Parent→child lineage preserved

## Recommendation

**APPROVED FOR IMMEDIATE USE.** Stage 2 SFT data is production-ready.

---

# Stage 2 Hoʻoilina Resplit Recovery — v3 Manifest (Prior)

**Date:** 2026-05-04  
**Owner:** Linus (Data Engineer)  
**Status:** ✅ Implemented & Verified

## Context

25 Hoʻoilina rows were quarantined in v2_dedup_quarantined because their concatenated EN+HAW token length exceeded the new `max_seq_len=2048` limit. These were full-document constitutional/historical texts (e.g., Hawaiian Kingdom Statutes 1851) that bypassed the original paragraph splitter. The audit report indicated they were "recoverable as 100-200 sentence/paragraph pairs".

Side issue: Removing them broke cap shares:
- Bible: 25.54% → 39.71% (cap: 30%)
- HK-Legal: 13.01% → 20.23% (cap: 15%)

Re-admitting non-Bible/non-HK Hoʻoilina content would mechanically restore caps.

## Decision

Re-split 25 quarantined Hoʻoilina rows using a length-aware strategy and re-admit them to TRAIN split.

**Strategy:**
1. Primary: numbered-paragraph split (`\n(?=\d+\.[ \t])`) per existing Hoʻoilina pipeline
2. Fallback: sentence split (period/question/exclamation + space + capital) for paragraphs still >2048 tokens
3. Hard-chunk: At sentence boundaries for any sentence pairs still >2048 tokens, maintaining EN↔HAW alignment
4. Safety margin: Target ≤1600 tokens per chunk (leaves 448 tokens headroom for special tokens/template)

**Implementation:**
- Created `scripts/resplit_hooilina_outliers.py` to re-split 25 parent rows
- Created `scripts/build_stage2_manifest_v3_hooilina_recovery.py` to merge resplit candidates into v3 manifest
- Used Llama-3.1-8B tokenizer for accurate token counts

## Results

### Re-split Output
- 25 parent rows → 864 child chunks
- 3 collisions with existing manifest (deduped)
- 861 new rows admitted to TRAIN split

### Manifest Transformation: v2 → v3

| Metric | v2 (Quarantined) | v3 (Recovered) | Change |
|--------|------------------|----------------|--------|
| TRAIN rows | 5,411 | 6,272 | +861 |
| Pair tokens | 382,760 | 589,370 | +206,610 |
| Max seq_len | 1,947 | 1,946 | -1 ✓ |
| Rows > 2048 | 0 | 0 | ✓ |
| Bible % | 39.71% | 25.56% | -14.15% ✓ |
| HK-Legal % | 20.23% | 13.13% | -7.10% ✓ |

### Cap Verification ✅

Both caps are now **under** their limits:
- Bible: 25.56% < 30% ✓
- HK-Legal: 13.13% < 15% ✓

The Hoʻoilina recovery diluted the over-represented capped sources back to healthy levels.

### Sequence Length Verification ✅

All 6,272 TRAIN rows are ≤2048 tokens (max=1946). The 1600-token safety margin in the resplitter was sufficient.

## Parent Row Tracking

25 quarantined parent rows remain in `split="review-pending"` with:
- Updated reason: `"seq_len_outlier_paragraph_split_failure_resplit_into_children"`
- New field: `child_sha256_pairs: [...]` pointing to 861 child rows
- Example: `5716fa6955f0018b...` → 45 child chunks

## Artifacts

- **v3 Manifest:** `data/stage2/reviewed_stage2_manifest_final_capped_v3.jsonl` (38,930 rows)
- **Resplit Candidates:** `data/stage2/candidates/hooilina_resplit.jsonl` (864 rows)
- **Verification Report:** `data/stage2/reports/hooilina_resplit_v3_20260504.json`
- **Scripts:**
  - `scripts/resplit_hooilina_outliers.py` (re-splitter)
  - `scripts/build_stage2_manifest_v3_hooilina_recovery.py` (v3 builder)

## Usage

To emit Stage 2 SFT training data from v3 manifest:

```bash
python scripts/330_emit_stage2_sft_jsonl.py \
  --manifest data/stage2/reviewed_stage2_manifest_final_capped_v3.jsonl \
  --out data/stage2/stage2_sft_v3.jsonl \
  --splits train,dev \
  --directions both
```

## Recommendation

**APPROVED FOR USE.** v3 manifest passes all gates:
1. ✅ All TRAIN rows ≤2048 tokens
2. ✅ Bible % < 30%
3. ✅ HK-Legal % < 15%
4. ✅ Dedup enforced (3 collisions removed)
5. ✅ Parent→child lineage preserved

Proceed with Stage 2 training using v3 manifest.

## Next

If caps need further tightening, consider:
- Lower Bible cap (e.g., 25%)
- Lower HK-Legal cap (e.g., 12%)
- Add more non-capped parallel sources (Tatoeba refresh, OPUS-TildeMODEL, etc.)

---

### 2026-05-04T05:30:30Z: User directive — consolidate row + paragraph training into Stage 2
**By:** Yashas (via Copilot)
**What:** Do not split into Stage 2 (rows) + Stage 3 (paragraphs). Stage 2 will hold both sentence/verse-grain rows AND paragraph-grain pairs. We don't have enough data to justify a separate Stage 3. Reverses the Stage 3 proposal previously evaluated by Linus (file `linus-stage3-paragraph-stage.md` in this inbox).
**Why:** Insufficient unique long-form parallel data to support a standalone curriculum stage; consolidation avoids extra training run + eval surface and keeps all SFT material in one mix.
**Implications:**
- Stage 2 mix must accommodate both grains (length-aware sampler or simple length bucketing).
- `max_seq_len` may need to grow from 1024 to fit longest paragraph pairs, OR long pairs get chunked.
- Hoʻoilina paragraph-primary policy (decision already in place) carries over: paragraphs win, derived sentences excluded to avoid duplicate-token training.
- Other paragraph-grain sources (HK statute sections, gospel_john sections, eventual nupepa articles) admitted into Stage 2 alongside row-grain sources.

---



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
