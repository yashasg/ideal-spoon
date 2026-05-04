# Decisions

> Updated 2026-05-04T06:40:10Z: Merged decision inbox file: linus-stage2-resplit-stricter-v3-emit.md (strict Hoʻoilina resplit under v3 manifest, 861→725 children, 185 blank dropped, 0 new collisions, 6,136 final TRAIN pairs, Bible 26.18% / HK 13.45%, SFT emit 12,272 rows). Prior 2026-05-04T06:06:29Z: Merged decision inbox files: linus-stage2-hooilina-resplit-v3.md, copilot-directive-20260504-stage2-consolidate.md. Prior 2026-05-04T05:29:51Z: Merged decision inbox files: copilot-directive-2026-05-04T03-49-hooilina-paragraphs-only.md, linus-hooilina-paragraph-impl.md, linus-hooilina-paragraph-pairs.md, linus-stage2-common-voice-license-probe.md, linus-stage2-flores-plus-license-probe.md, linus-stage2-hk-statutes-extended.md, linus-stage2-tier-a-promotion.md, linus-stage3-paragraph-stage.md, rusty-hooilina-labse-policy.md. Prior 2026-05-03T20:55:00Z: Merged R17 linus-stage2-r17-canonical-consolidation (canonical helpers consolidated to single source of truth in `code/llm_hawaii/stage2_canonical.py`: canonical_en, canonical_haw, canonical_pair; 25 files refactored (adapters, audit, dedup, legacy normalizer); NFC normalize, strip invisibles, collapse whitespace, preserve case, EN folds curly quotes/hyphens, HAW ʻokina folding; 60/60 tests pass, 37,084 rows stable, strict audit pass, commit bf4b57e; future adapters MUST import from stage2_canonical, no local canonicalization helpers). Prior 2026-05-03T20:45:08Z: Merged R16 linus-stage2-r16-hash-determinism-policy (EN-side hash canonicalization contract locked: NFC normalize, strip invisibles, collapse whitespace, preserve case, fold EN curly quotes/hyphens to ASCII, keep U+02BC/U+02BB/em-en-dashes, HAW ʻokina folding HAW-only; 7 determinism tests added; FLORES+ and Common Voice probed RED/SKIP for Hawaiian; 37,084 rows stable, all suites green, commit 85ba2e5). Prior 2026-05-03T20:38:30Z: Merged R15 linus-stage2-r15-dedup-edge-fixes (fallback exact-pair ordering uses canonical source priority not alphabetical; near-dupe matching strips invisible controls U+00AD/U+200B/U+200C/U+200D/U+FEFF; manifest validation rejects whitespace/invisible-only refs; audit reports 7 invisible-control rows, 3 NBSP rows, 37,084 rows stable, all suites green). Prior 2026-05-03T20:33:14Z: Merged R14 linus-stage2-r14-contamination-wired (train-side eval-contamination filter now enforcing gate; `--eval-hashes` loads explicit eval ledgers before dedup, drops matches before cross-source/side/near-duplicate dedup, missing ledger hard error, writes contamination_report.json sidecar, all regression suites green). Prior 2026-05-03T1100Z: Merged R7 linus-stage2-paraphrase-grouping (161 EN/32 HAW exact groups accepted as lexical diversity, 395 rows annotated, zero drops, copilot user directive captured). Prior 2026-05-03T10:55:58Z: Merged R6 linus-stage2-short-variant-policy (37,223→37,084 rows; length-aware N=2 cap for short exact variants ≤3 tokens, 161 EN/32 HAW groups remain). Prior 2026-05-03T10:50:51Z: Merged R5 linus-stage2-near-dupe-policy (37,661→37,223 rows; 306 near-dupe groups collapsed, strong Bible-Gospel-John signal).
>

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
