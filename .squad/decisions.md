# Decisions

> Updated 2026-05-04T05:29:51Z: Merged decision inbox files: copilot-directive-2026-05-04T03-49-hooilina-paragraphs-only.md, linus-hooilina-paragraph-impl.md, linus-hooilina-paragraph-pairs.md, linus-stage2-common-voice-license-probe.md, linus-stage2-flores-plus-license-probe.md, linus-stage2-hk-statutes-extended.md, linus-stage2-tier-a-promotion.md, linus-stage3-paragraph-stage.md, rusty-hooilina-labse-policy.md. Prior 2026-05-03T20:55:00Z: Merged R17 linus-stage2-r17-canonical-consolidation (canonical helpers consolidated to single source of truth in `code/llm_hawaii/stage2_canonical.py`: canonical_en, canonical_haw, canonical_pair; 25 files refactored (adapters, audit, dedup, legacy normalizer); NFC normalize, strip invisibles, collapse whitespace, preserve case, EN folds curly quotes/hyphens, HAW ʻokina folding; 60/60 tests pass, 37,084 rows stable, strict audit pass, commit bf4b57e; future adapters MUST import from stage2_canonical, no local canonicalization helpers). Prior 2026-05-03T20:45:08Z: Merged R16 linus-stage2-r16-hash-determinism-policy (EN-side hash canonicalization contract locked: NFC normalize, strip invisibles, collapse whitespace, preserve case, fold EN curly quotes/hyphens to ASCII, keep U+02BC/U+02BB/em-en-dashes, HAW ʻokina folding HAW-only; 7 determinism tests added; FLORES+ and Common Voice probed RED/SKIP for Hawaiian; 37,084 rows stable, all suites green, commit 85ba2e5). Prior 2026-05-03T20:38:30Z: Merged R15 linus-stage2-r15-dedup-edge-fixes (fallback exact-pair ordering uses canonical source priority not alphabetical; near-dupe matching strips invisible controls U+00AD/U+200B/U+200C/U+200D/U+FEFF; manifest validation rejects whitespace/invisible-only refs; audit reports 7 invisible-control rows, 3 NBSP rows, 37,084 rows stable, all suites green). Prior 2026-05-03T20:33:14Z: Merged R14 linus-stage2-r14-contamination-wired (train-side eval-contamination filter now enforcing gate; `--eval-hashes` loads explicit eval ledgers before dedup, drops matches before cross-source/side/near-duplicate dedup, missing ledger hard error, writes contamination_report.json sidecar, all regression suites green). Prior 2026-05-03T1100Z: Merged R7 linus-stage2-paraphrase-grouping (161 EN/32 HAW exact groups accepted as lexical diversity, 395 rows annotated, zero drops, copilot user directive captured). Prior 2026-05-03T10:55:58Z: Merged R6 linus-stage2-short-variant-policy (37,223→37,084 rows; length-aware N=2 cap for short exact variants ≤3 tokens, 161 EN/32 HAW groups remain). Prior 2026-05-03T10:50:51Z: Merged R5 linus-stage2-near-dupe-policy (37,661→37,223 rows; 306 near-dupe groups collapsed, strong Bible-Gospel-John signal).
>

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
