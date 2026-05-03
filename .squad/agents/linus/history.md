# Linus — History

## 2026-05-03 — Stage-2 Legacy Candidate Normalization (Round 3)

**Task:** Built `scripts/341_normalize_legacy_candidates.py` + test. One-shot normalizer canonicalizes all generated candidate JSONLs under `data/stage2/candidates/` before dedup/cap policy work. Normalizer uses `--apply` for local artifact patching; never touches `data/raw/`. **Result:** All schema violations and HAW ʻokina hash drift fixed. Verified: `scripts/340_audit_stage2_candidate_normalization.py --strict` reports 0 violations; `scripts/320_build_stage2_manifest.py --dry-run` emits 37,761 clean rows. **Metrics before→after:** Schema drift 206,670→0, post-policy 21,118→0, hash drift 693→0, ʻokina rows 311→0. Cross-source dup groups 91→100 (canonical recompute surfaced more). Dry-run 320 script: clean at 37,761 rows. Commit `2efacb6`. Decision documented in `.squad/decisions.md`. **Next:** Round 4 dedup policy (Tatoeba canonical, Bible cross-editions).

---

## 2026-05-03 — Sanitary Instructions 1881 adapter implementation (decision formalized)

**Task:** Built scripts/335_build_sanitary_instructions_candidates.py + code/tests/test_sanitary_instructions_adapter.py. Commit eae312b. **Key Decision:** Sanitary Instructions 1881 candidates are comparable-aligned LaBSE rows (not deterministic paragraph-parallel). Adapter must emit schema-compatible generic enums: `alignment_type="comparable-aligned"`, `alignment_method="labse"`, policy details in `policy_version`/`manual_review_reasons`/`alignment_score_components`. Rows stay `split="review-pending"`, `alignment_review_required=true`, `prototype_only=true`, `release_eligible=false` until rights/cap finalization; `license_inferred` null per schema. `--execute` requires `--confirm-edition sanitary-instructions-1881-ia-nlm-paired` + existing `--tos-snapshot` path. Why: validator accepts only fixed enums; encoding policy in enum fields breaks schema validation and blocks manifest builds. Keeping rows prototype-only matches Stage-2 policy for non-finalized candidates. Decision documented in `.squad/decisions.md`.

---

## 2026-05-03 — LaBSE review promotion Round 1: 0 net gain

**Task:** Audit 124 review-tier rows (LaBSE scores 0.55–0.75) from Round 2 scoring. Apply tightened promotion rule (score ≥0.65, length ratio 0.5–2.0, ≥3 tokens, no dupes, Hawaiian orthography check). Re-run cap enforcement + SFT emission. **Result:** 9 rows passed promotion filter but all 9 were policy-overridden to held-out by scripts 332-334 (3 OPUS-Tatoeba upstream dupes, 5 OPUS-wikimedia quality-heldout, 1 wikimedia-cx rights-heldout). SFT unchanged at 8,572 rows. **Net gain: 0.** Review band correctly flags duplicates (67/124) and policy-excluded sources (9/124); remaining 48 are genuine quality rejects. Deliverables: `scripts/337_promote_labse_review_round1.py`, decision log `.squad/decisions/inbox/linus-labse-review-promotion-r1.md`, history update. Recommendation: Focus future efforts on new sources with accept-tier scores (≥0.75), not review-band re-promotion. Tests: none (one-off script).

---

## 2026-05-03 — Checkpoint patcher built

**Task:** Build scripts/patch_checkpoint_for_resume.py + code/tests/test_patch_checkpoint_for_resume.py to strip training_args.bin and scheduler.pt from HF checkpoint (moves to .bak), so HF Trainer rebuilds from current config on resume. **Result:** Complete. 6 tests pass. Requested by yashasg.

---

## 2026-05-02 — LaBSE merge Round 2: +296 accept, 8,572 SFT rows

**Task:** Merge Rusty's LaBSE-scored rows (wikimedia_cx_en_haw + opus_haw_subsets) into Stage 2 manifest, re-run cap enforcement chain, and re-emit SFT. Part of 40k push directive. **Result:** 296 LaBSE-accepted pairs merged → 8,572 SFT rows (+1,134 from Round 1's 7,438). Gap to 40k: 31,428 rows. Deliverables: merge script `scripts/337_merge_labse_scored_to_manifest.py`, updated manifests (raw + finalized), SFT re-emission, decision log `.squad/decisions/inbox/linus-labse-merge-round2.md`, and this history update. Tests pass (25/25 SFT templates, 11/11 finalizer). Path forward blocked on wiki-langlinks sentence extraction (2k–6k) + NLLB mined (16k–30k).

---

## 2026-05-02 — Stage 2 40k SFT expansion attempt

**Directive:** User hard directive to reach 40,000 Stage-2 SFT training rows without stopping. **Result:** Stopped at 7,438 rows — 40k target not achievable with current manifest (Bible cap saturated, all non-Bible sources exhausted or policy-blocked). Gap analysis identified one executable action: re-emit SFT with `--allow-review-required` flag, lifting the conservative gate on 3,046 train pairs (HK statutes, Phrase Book, etc.). Executed successfully: 1,346 rows → 7,438 rows (+6,092). Remaining gap to 40k is 32,562 rows (16,281 pairs), blocked by: (1) Bible overflow (31,679 review-pending rows) cannot promote until N_nonbible grows ~2.3×; (2) OPUS comparable-aligned (212 rows) needs LaBSE infrastructure; (3) Andrews vocab (1,194 rows) needs clean re-extraction; (4) Kaikki (139 rows) genuine quality rejects. Path forward requires new source ingestion (NLLB mined, synthetic BT, or Wehewehe PD). Deliverables: gap analysis in `.squad/decisions/inbox/linus-stage2-40k-gap.md`, SFT artifact `data/stage2/stage2_sft_train_with_review.jsonl` (7,438 rows), orchestration log, and history update. Tests pass (25/25 SFT templates, 11/11 finalizer). No code changes required; emitter flag was already wired per Danny's final-review-verdict policy.

---

## 2026-05-01 — HK Statutes 1897 section-level candidates

**Task:** Process already-local Hawaiian Kingdom Statutes 1897 bilingual imprint
(Cornell/LLMC digitization) into Stage-2 section-level candidate rows.

**Policy context:** 1897 pair cleared (GO) per decisions.md; 1869/1850 pair
inventory-only due to year-mismatch (HAW file is `1850.002_djvu.txt`).

**Implementation:**
- **`scripts/325_build_hk_statutes_candidates.py`** (new) — stdlib-only section
  parser for CHAPTER/MOKUNA + §-prefixed markers. Handles three OCR artifacts for
  `§` in the HAW djvu.txt (`$`, `S`; excludes ambiguous `8`). Supports `--dry-run`,
  `--execute`, `--self-test`. Exit 0/1/2/3 per convention.

**Commands run:**
```bash
python3 -m py_compile scripts/325_build_hk_statutes_candidates.py  # syntax OK
python3 scripts/325_build_hk_statutes_candidates.py --self-test     # 8 assertions OK
python3 scripts/325_build_hk_statutes_candidates.py --dry-run       # 1103 rows, 0 violations
python3 scripts/325_build_hk_statutes_candidates.py --execute       # wrote candidates + report
python3 scripts/320_build_stage2_manifest.py --dry-run              # 33925 rows, 0 violations
```

**Counts:**

| Metric | Value |
|---|---|
| EN sections parsed | 1,292 |
| HAW sections parsed | 1,456 |
| Common (paired) sections | 1,103 |
| Rows emitted | 1,103 |
| Skipped (too short) | 0 |
| EN-only unmatched | 189 |
| HAW-only unmatched | 353 |
| Schema violations (320) | 0 |
| Total manifest rows (all sources) | 33,925 (after this addition) |

**Outputs created:** `data/stage2/candidates/hk_statutes_1897.jsonl` (1,103 rows),
`data/stage2/reports/hk_statutes_1897_report.json`,
`scripts/325_build_hk_statutes_candidates.py`,
`.squad/decisions/inbox/linus-hk-statutes-processing.md`.

**Schema/policy flags:**
- `alignment_type = "parallel-sentence"` (section-level parallel, justified)
- `alignment_review_required = True` (OCR noise; conservative)
- `split = "review-pending"`; `prototype_only = True`; `release_eligible = False`
- `direction_original = "en->haw"` (HAW preface confirms translation)

---

## Learnings

### LaBSE review band (0.55–0.75) requires full pipeline verification for train promotion

The review band correctly flags rows needing manual/policy review, not just "marginal quality" rows. Of 124 review-band rows audited in Round 1:

- **67 (54%)** were duplicates already in manifest (expected)
- **48 (39%)** failed tightened promotion rule (score <0.65, length mismatch, missing Hawaiian orthography)
- **9 (7%)** passed promotion rule but were policy-overridden by scripts 332-334 (source-specific exclusion gates)

**Key insight:** Promotion from review-pending requires running the full cap enforcement chain (332→333→334), not just a local quality filter. Source-level policies (e.g., OPUS-Tatoeba upstream dedup, wikimedia-cx rights-heldout, Bible/HK/software-l10n caps) override local score-based promotion. Any future review-band re-promotion MUST verify final eligibility post-pipeline.

### OCR artifact mapping in 19th-century Hawaiian-government djvu.txt files

Three OCR renderings of `§` appear in the 1897 HAW Penal Laws djvu.txt:
- `$` (dollar sign) — most common (~50% of occurrences)
- `S` (uppercase S) — second common (~35%)
- `8` (digit 8) — third artifact (e.g., `§7` → `87.`, `§23` → `823.`)

The `8` artifact is **excluded** from the section parser because it is ambiguous
with real section numbers (§87 in EN also appears and `87.` in HAW could be §7
or §87). Recovery requires human spot-check.

### 1897 vs 1869/1850 year-mismatch

The "1869 penal code" pair has EN item `esrp475081650` (1869.001.pdf) paired
with HAW item `esrp468790723` whose local filename is `1850.002_djvu.txt`. This
filename mismatch (1869 EN vs 1850 HAW) indicates the HAW file may be a different
edition. Keep inventory-only until the year discrepancy is verified by content
examination (title page, chapter count, section range comparison).

### Aligned penal code structure: CHAPTER ↔ MOKUNA, §N ↔ $N/SN

The 1897 bilingual imprint has a clean 1:1 structural correspondence:
- `CHAPTER N.` (EN) ↔ `MOKUNA N.` (HAW)
- `§N[,.]` (EN) ↔ `[$S]N[,.]` (HAW, OCR-normalized)
- Titles align (e.g., "DEFINITIONS" ↔ "NA WEHEWEHE ANO")
- HAW preface explicitly states *"Unuhiia mai ka Olelo Beritania mai"*
  (Translated from English) → `direction_original = "en->haw"` is reliable.

### Sanitary Instructions 1881 adapter schema gotcha

The Sanitary Instructions paired volumes are comparable-aligned, not deterministic parallel paragraphs. Candidate rows must use schema enums `alignment_type="comparable-aligned"` and `alignment_method="labse"`; keep the adapter-specific mutual-nearest policy in `policy_version` / `manual_review_reasons`. Because this source is still review-pending and rights/cap-gated, rows stay `prototype_only=True`, `release_eligible=False`, `license_inferred=None`, and `register="unknown"` until final policy review. The adapter's `--execute` path is triple-gated by pinned edition confirmation plus an on-disk IA ToS snapshot.

### Stage-2 candidate normalization audit should run before cap/manifest decisions

Round 2 added `scripts/340_audit_stage2_candidate_normalization.py` to audit all existing candidate JSONL without mutating `data/`. Current pool findings: 37,761 rows across 15 candidate files; 311 Hawaiian rows would change under canonical ʻokina folding; 2,119 English rows contain apostrophes/right quotes that must be preserved on the EN side; 91 cross-source exact pair-hash duplicate groups were found (mostly OPUS-Tatoeba vs upstream Tatoeba); 4 sampled near-dupes show Andrews number entries duplicated in Phrase Book. Post-policy schema violations remain concentrated in older adapters (Gospel John/HK constitution null raw hashes + non-null `license_inferred`, Phrase Book enum drift, wiki-langlinks probe shape). Next normalization work should fix adapters before rebuilding manifests, not edit gitignored data by hand.

### Legacy candidate normalizer should patch generated candidates, not raw data

Round 3 added `scripts/341_normalize_legacy_candidates.py` to re-emit Stage-2 candidate JSONLs through the canonical `320_build_stage2_manifest.py` schema. The script is dry-run by default; `--apply` rewrites only `data/stage2/candidates/*.jsonl`, creates sibling `.jsonl.bak` copies first, and never touches `data/raw/`. It folds HAW ʻokina before clean hashes, preserves EN apostrophes, maps legacy enum values to schema-compatible values while preserving detail in `notes`, nulls `license_inferred`, fixes prototype/release lineage violations, recomputes clean/pair hashes, and applies the Stage-2 quality policy fields so both raw and post-policy audit validation are clean.

Verification after applying to the local candidate artifacts: `scripts/340_audit_stage2_candidate_normalization.py --strict` reported 0 HAW ʻokina-fold rows, 0 hash mismatches, and 0 raw/post-policy schema violations; `scripts/320_build_stage2_manifest.py --dry-run` emitted 37,761 rows with 0 skipped schema violations. Cross-source exact pair dup groups remain (100 after canonical hash recomputation) and are the next policy target.

### Cross-source exact-pair dedup policy belongs before cap math

Round 4 codified exact `sha256_pair` cross-source preference in `code/llm_hawaii/stage2_dedup.py` and wired it into `scripts/320_build_stage2_manifest.py` before historical/Bible cap math. The 100 observed groups were all size 2: 90 OPUS-Tatoeba vs canonical Tatoeba, 9 Gospel John 1854 vs Baibala 1868, and 1 OPUS-Wikimedia vs Wikimedia CX. Dry-run manifest now emits 37,661 rows (37,761 - 100), and `scripts/340_audit_stage2_candidate_normalization.py --strict` reports raw exact pair groups 100 but post-dedup groups 0. Preference rules are data-first and ordered: Hoʻoilina over Bible; Wikimedia CX over OPUS-Wikimedia; Tatoeba over OPUS-Tatoeba; Baibala 1868 over other Bible-family exact overlaps; deterministic fallback only for unexpected groups.

---

## 2026-05-03 — Stage-2 near-duplicate policy (Round 5)

**Task:** Quantified and encoded Stage-2 one-sided exact duplicate caps plus cross-source near-duplicate collapse. Added `cap_exact_en`, `cap_exact_haw`, and stdlib near-dupe grouping/collapse to `code/llm_hawaii/stage2_dedup.py`; wired the passes into `scripts/320_build_stage2_manifest.py` after exact pair-hash dedup and before historical cap math; expanded `scripts/340_audit_stage2_candidate_normalization.py` with exact-EN-only, exact-HAW-only, and near-dupe histograms by source. **Policy:** exact EN and exact HAW variants cap at 3 per clean-side hash (skip Baibala 1839 historical exception groups); near-dupes use threshold 0.92 on both EN and HAW normalized text/token-set similarity and collapse cross-source groups only, preferring richer source priority then length then stable ids. **Result:** dry-run manifest 37,661 → 37,223 rows (-438 after Round 4 baseline: exact EN cap -128, exact HAW cap -4, near collapse -306). Audit: raw exact-EN-only 262 groups, exact-HAW-only 88 groups, near-dupe 306 groups; post-policy near-dupe groups 0. Verification: targeted unittests pass (`test_stage2_dedup`, `test_stage2_candidate_normalization_audit`, `test_stage2_manifest`); `340 --strict` reports 0 schema/hash issues. Full suite has 4 unrelated pre-existing failures in sanitary/source-fetch/train config tests. **Next:** Round 6 should inspect the remaining post-policy exact one-sided groups (207 EN, 70 HAW), especially Phrase Book/Andrews semantic variants, and decide if source-specific phrase caps or manual allowlists are needed.
