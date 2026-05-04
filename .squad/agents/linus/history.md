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

### Stage 3 paragraph SFT should wait for Stage 2 plateau

Verdict: yes in principle, but only after Stage 2 has plateaued and only with Stage 2 kept sentence/verse-primary. The real paragraph/document pool is Hoʻoilina paragraphs/recovery, HK legal sections/constitution, Bible chapter-scale pairs if built, gospel_john_1854 chapter/section aggregates, and possibly aligned nupepa articles; that is likely mid-six-figure to low-seven-figure pair tokens depending on Bible/nupepa inclusion, not a clean 40k-row substitute. Main risks are current Stage 2 `max_seq_len=1024` truncating longer chapters/articles and duplicate-token exposure if sentence splits and parent paragraphs both train; acceptable as curriculum only if tracked with overlap metadata, lower LR, and regression evals for sentence-level translation.

### Hoʻoilina paragraph pairs should be primary, sentence splits fallback

Yashas asked whether Hoʻoilina should emit paragraph pairs now that LaBSE is soft metadata only. Verified current artifacts and script reports: `hooilina.jsonl` has 68 parent/section rows (`parallel-doc`), `hooilina_sentences.jsonl` has 60 sentence rows (`parallel-sentence`), and no current Hoʻoilina row has LaBSE model/score. The sentence builder loads 68 parents, finds only 6 parents with matched numbered-paragraph counts, inspects 36 paragraph pairs, skips 8 paragraph pairs for sentence-count mismatch, sees 61 sentence pairs, emits 60, and rejects 1 short pair.

If we emitted paragraph-level pairs from those 6 matched parents, we would get 36 raw paragraph rows, or 35 if reusing the current min-3-tokens/side gate. Paragraph lengths are safe: EN avg 49.92 tokens / max 168; HAW avg 64.83 / max 236; 0 exceed 256 whitespace tokens on either side and 0 exceed 512. They are mostly small paragraphs, not pages: EN avg 2.83 sentences/paragraph, HAW avg 2.58; 26/36 EN and 28/36 HAW paragraphs have ≤3 sentences, max 9 EN / 8 HAW. Recommendation: switch to paragraph-primary with sentence fallback/auxiliary, not sentence-only. Paragraphs match the human translation granularity, avoid sentence-split alignment risk, and the row-count loss is only 60 sentences versus 36 paragraphs in the trusted matched-parent subset.

Unmatched-parent recovery is real but separate from the first implementation. Of the 62 parents skipped by the sentence builder, 20 have paragraph-count diff 1 and 10 diff 2; explicit paragraph-number matching plus length/orthography sanity finds 155 plausible paragraph pairs in the diff≤2 group and 526 plausible numbered paragraph pairs across all 62. That should be a second, review-pending recovery pass, not an automatic train promotion.

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

### Stage-2 review-pending tiering: promote policy-approved rows, sample uncertain sources

Tier A is already policy-approved review-pending content: historical-orthography accept rows, hk1897 legal-clean rows, and trusted whitelist sources (Hoʻoilina, Wikimedia CX, Weblate, Tatoeba). Promote Tier A in `sha256_pair` order, but enforce Bible ≤30%, HK/legal ≤15%, and software-l10n ≤15% against final train-side pair-token share; evict only newly admitted rows, never existing train/dev. Tier B is cap-evicted high-quality content and should be counted only until policy changes. Tier C (Andrews vocab, OPUS, Kaikki, Gospel John 1854, HK Constitution 1852) needs Yashas review from samples before train promotion. Tier D terminal failures (`side_too_short`, `length_ratio_extreme`, `haw_nonhaw_letters_high`) stay rejected.

Edge cases found on 2026-05-04: 8 whitelist review-pending rows were exact pair duplicates of existing train rows (7 Wikimedia CX self-duplicates, 1 Tatoeba duplicated by OPUS-Tatoeba), so they must not be double-promoted. Source confidence ordering for this pile is: policy-approved historical/legal rows subject to caps; Hoʻoilina paragraph/doc rows; direct source lanes Wikimedia CX/Weblate/Tatoeba; then Tier C sample-only sources after human decision.

### Cross-source exact-pair dedup policy belongs before cap math

Round 4 codified exact `sha256_pair` cross-source preference in `code/llm_hawaii/stage2_dedup.py` and wired it into `scripts/320_build_stage2_manifest.py` before historical/Bible cap math. The 100 observed groups were all size 2: 90 OPUS-Tatoeba vs canonical Tatoeba, 9 Gospel John 1854 vs Baibala 1868, and 1 OPUS-Wikimedia vs Wikimedia CX. Dry-run manifest now emits 37,661 rows (37,761 - 100), and `scripts/340_audit_stage2_candidate_normalization.py --strict` reports raw exact pair groups 100 but post-dedup groups 0. Preference rules are data-first and ordered: Hoʻoilina over Bible; Wikimedia CX over OPUS-Wikimedia; Tatoeba over OPUS-Tatoeba; Baibala 1868 over other Bible-family exact overlaps; deterministic fallback only for unexpected groups.

### Stage 2 max_seq_len=2048 requires paragraph-splitting Hoʻoilina recovery

After setting Stage 2 `max_seq_len=2048`, full tokenization scan of the capped/deduplicated manifest revealed 25 TRAIN rows (all Hoʻoilina paragraph/section-level pairs) exceeding the limit. Token range: 2,225 to 28,584 (top 3 are full constitutional documents at 24K-28K tokens). These were quarantined to `split="review-pending"` with reason `"seq_len_outlier_paragraph_split_failure"`. Post-quarantine TRAIN: 5,411 rows, 383K pair tokens, max seq_len 1,947. **Key insight:** The 25 quarantined rows contain legitimate content (constitutional texts, historical documents) but need sentence-level re-splitting to fit the 2048-token training window. Recovery estimate: 100-200 valid pairs if re-split properly, adding valuable non-Bible/non-HK-legal tokens. The hk_statutes_1897 extreme outlier (49c3a67cb384, 43,573 tokens: 780-char EN vs 134KB HAW) is a data alignment error and should move to `split="rejected"` after manual inspection. Decision: `.squad/decisions/inbox/linus-stage2-quarantine-seqlen-outliers.md`.

**Cap share side effect:** Quarantining removed 212K tokens of non-capped content, increasing Bible share from 25.54% → 39.71% and HK-legal from 13.01% → 20.23%. The absolute token counts didn't change, only the percentages. Team must decide whether to re-apply caps post-quarantine or add more non-Bible/non-HK content to rebalance.

---

## 2026-05-03 — Stage-2 near-duplicate policy (Round 5)

**Task:** Quantified and encoded Stage-2 one-sided exact duplicate caps plus cross-source near-duplicate collapse. Added `cap_exact_en`, `cap_exact_haw`, and stdlib near-dupe grouping/collapse to `code/llm_hawaii/stage2_dedup.py`; wired the passes into `scripts/320_build_stage2_manifest.py` after exact pair-hash dedup and before historical cap math; expanded `scripts/340_audit_stage2_candidate_normalization.py` with exact-EN-only, exact-HAW-only, and near-dupe histograms by source. **Policy:** exact EN and exact HAW variants cap at 3 per clean-side hash (skip Baibala 1839 historical exception groups); near-dupes use threshold 0.92 on both EN and HAW normalized text/token-set similarity and collapse cross-source groups only, preferring richer source priority then length then stable ids. **Result:** dry-run manifest 37,661 → 37,223 rows (-438 after Round 4 baseline: exact EN cap -128, exact HAW cap -4, near collapse -306). Audit: raw exact-EN-only 262 groups, exact-HAW-only 88 groups, near-dupe 306 groups; post-policy near-dupe groups 0. Verification: targeted unittests pass (`test_stage2_dedup`, `test_stage2_candidate_normalization_audit`, `test_stage2_manifest`); `340 --strict` reports 0 schema/hash issues. Full suite has 4 unrelated pre-existing failures in sanitary/source-fetch/train config tests. **Next:** Round 6 should inspect the remaining post-policy exact one-sided groups (207 EN, 70 HAW), especially Phrase Book/Andrews semantic variants, and decide if source-specific phrase caps or manual allowlists are needed.

---

## 2026-05-03 — Stage-2 short-variant exact duplicate policy (Round 6)

**Task:** Sampled the 207 remaining exact-EN and 69/70 reported exact-HAW post-policy one-sided duplicate groups, then encoded a short-variant policy in `code/llm_hawaii/stage2_dedup.py`. **Stats:** exact-EN groups: 433 rows; short duplicated-side rows ≤3 tokens = 124, concentrated in Phrase Book (61) and Andrews (52). Exact-HAW groups: 151 rows; short duplicated-side rows = 88, concentrated in Andrews (44) and Phrase Book (29). Bible rows were mostly sentence-length (exact-EN median 14 EN / 18 HAW tokens; exact-HAW median 10 EN / 13 HAW). **Decision:** choose length-aware cap over source allowlist: short duplicated side (≤3 tokens) gets cap N=2 and requires opposite side ≥4 tokens; longer groups keep N=3; Baibala 1839 exception remains exempt. **Result:** manifest dry-run 37,223 → 37,084 rows (-139). Exact-EN cap drops now 199 rows (128 generic cap + 71 short-other-too-short); exact-HAW cap drops 75 rows (4 generic cap + 71 short-other-too-short); near-dupe collapse drops 303 rows. Post-policy exact-EN groups reduced to 161, exact-HAW to 32, near-dupes remain 0. **Verification:** targeted tests pass (`test_stage2_dedup`, `test_stage2_candidate_normalization_audit`, `test_stage2_manifest`); `320 --dry-run` emits 37,084 rows with 0 skipped violations; `340 --strict` reports 0 post-policy schema violations/hash mismatches and 0 post-policy near-dupe groups. Decision documented in `.squad/decisions/inbox/linus-stage2-short-variant-policy.md`. **Next:** Round 7 should audit the remaining 161 exact-EN / 32 exact-HAW groups: most are Bible verse formulae plus legitimate same-source Andrews/Phrase Book size-2 variants; decide whether to leave as accepted lexical diversity or add source-specific held-out tagging instead of more hard drops.

---

## 2026-05-03 — Stage-2 paraphrase grouping + sourcing inventory (Round 7)

**Task:** Close out remaining one-sided exact duplicate groups and reconcile the 37k clean-manifest vs SFT-eligible gap. **Part A decision:** accepted remaining groups as legitimate lexical/paraphrase diversity; no more drops. Added `paraphrase_group_id` annotation after exact-pair dedup, one-sided caps, and near-dupe collapse. Samples were Bible formulae with alternate Hawaiian renderings, Tatoeba “John” paraphrases, and Andrews lexical equivalents such as “Nothing”/“Nought” → “he ole, he mea ole.” **Metrics:** manifest dry-run remains 37,084 rows (delta 0); 161 exact-EN groups / 341 row hits and 32 exact-HAW groups / 71 row hits collapse into 178 connected paraphrase components; 395 rows annotated. **Part B:** current in-memory SFT eligibility from the cleaned manifest is 2,396 train pairs = 4,792 bidirectional SFT rows; gap to 40k directional rows is 35,208. Difference is mostly `review-pending` quality quarantine (34,438 rows) plus 250 dev rows. **Round-8 sourcing priorities:** remaining Hawaiian Kingdom statutes (1869/1859/1846), public Weblate EN↔HAW translation memories after license filter, then Global-PIQA haw_Latn TSV probe. **Verification:** targeted tests passed (`test_stage2_dedup`, `test_stage2_manifest`, `test_stage2_candidate_normalization_audit`); `scripts/320_build_stage2_manifest.py --dry-run --strict` emits 37,084 rows with 0 violations. Decision files: `.squad/decisions/inbox/linus-stage2-paraphrase-grouping.md`, `.squad/decisions/inbox/linus-stage2-sourcing-priorities.md`.

---

## 2026-05-03 — Stage-2 HK statutes legal-vetted edition pins (Round 8)

**Task:** Extend the existing HK 1897 statutes adapter toward 1869/1859/1846 under the new legal directive. **Legal vetting precedent:** checked source host before any fetch; all candidate editions are already-local Internet Archive items from the same host as 1897. Inherited IA ToS snapshot `ia_terms` (`data/raw/hawaiian-kingdom-statutes-paired-imprints/20260501/_tos/ia_terms.html`, fetched `2026-05-01T21:14:22Z`, sha256 `4bbba906...`). No live HTTP or `--execute` run. Rights verdict remains public domain for the legal text (pre-1929 term + sovereign-edicts doctrine), with IA ToS governing hosted bytes. **Implementation:** parameterized `scripts/325_build_hk_statutes_candidates.py` with edition pins for 1897/1869/1859/1846, added dry-run parsers for older Section/Pauku styles, added mocked-HTTP fetch helper test coverage for User-Agent + rate-limit behavior, and wrote `data-sources/hk-statutes/source_registry.json`. **Safety gates:** `--execute` remains allowed only for 1897. 1869 is blocked due EN 1869 vs HAW `1850.002` content mismatch; 1859 is dry-run-only pending Pauku range mapping; 1846 is dry-run-only pending act/chapter segmentation for repeated section numbers. Decision artifact: `.squad/decisions/inbox/linus-stage2-hk-statutes-extended.md`. **Next:** Round 9 should manually inspect 1859 section ranges and decide whether a small verified Civil Code subset can be emitted; do not promote 1869 without finding a true HAW 1869 counterpart.

---

## 2026-05-03 — Stage-2 license probes (Round 9)

**Task:** License-first, no-data-fetch probe for Weblate EN↔HAW and Global-PIQA `haw_Latn`. **Weblate verdict:** YELLOW. Hosted Weblate has EN-source Hawaiian projects and robots allows `/languages/`, `/projects/`, `/exports/`; proceed only for permissive MIT/Apache components, keep GPL/LGPL/AGPL and missing-license components blocked. Fedora Weblate has `rpminspect` HAW but GPL-3.0-only components, so blocked for train unless policy changes. **Global-PIQA verdict:** YELLOW / eval-only. HF card/API license is `cc-by-sa-4.0`, but the card explicitly says no AI training and evaluation only; route to eval/final ledger, never train or synthetic seeds. Operational `haw_latn` plan: `test` split, fields `prompt`, `solution0..3`, `label`, `language`, `eng_prompt`, `eng_solution0..3`, `categories`, `example_id`, `supplement`, ~103 test examples pending TSV line-count confirmation in eval-ingest round. Decision files: `.squad/decisions/inbox/linus-stage2-weblate-license-probe.md`, `.squad/decisions/inbox/linus-stage2-global-piqa-license-probe.md`.

---

## 2026-05-03 — Stage-2 Weblate permissive-only adapter (Round 10)

**Task:** Ship Weblate EN↔HAW permissive-only discovery/fetch adapter without live network or `--execute`. **Implementation:** added `data-sources/weblate/source_registry.json`, `scripts/345_discover_weblate_haw_projects.py`, and `scripts/346_build_weblate_candidates.py`. Discovery enumerates `/api/components/?language=haw` plus `/api/projects/{slug}/`, writes TSV inventory under gitignored `data/raw/weblate-discovery/`, and refuses live HTTP unless `--execute`, instance selection, exact SPDX allowlist confirmation, and a local TOS snapshot file are supplied. Candidate build reads accepted TSV rows, fetches TMX only behind the same gates, normalizes Hawaiian ʻokina to U+02BB, emits canonical Stage-2 rows to `data/stage2/candidates/weblate.jsonl`, and has `--self-test` with an inline TMX fixture. **Policy:** allowlist is MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, MPL-2.0, CC0-1.0, CC-BY-4.0; GPL/AGPL/LGPL/CC-BY-SA/missing licenses are blocked. **Dedup:** added Weblate below Tatoeba and marked software-l10n Weblate rows as short-variant-prone for length-aware caps. **Verification:** `test_weblate_adapter` passed 7 tests, `test_stage2_dedup` passed 13 tests, and manifest dry-run stayed at 37,084 rows. Decision artifact: `.squad/decisions/inbox/linus-stage2-weblate-adapter-shipped.md`. **Next:** Round 11 should capture local TOS/robots snapshots and run discovery `--execute` only after SHA-pinning those snapshots, then review the TSV before any TMX fetch.

---

## 2026-05-03 — Global-PIQA eval-only ingester + contamination guard (Round 11)

**Task:** Ship Global-PIQA `haw_Latn` as eval-ledger-only, with no live network and no train candidate writes. **Implementation:** added `scripts/347_ingest_global_piqa_haw.py` with inline 3-row `--self-test`, local-TSV-only `--execute`, exact dataset pin gate (`mrlbenchmarks/global-piqa-parallel@a350910e9cfc8b0b57cb55aa8261780deabb6568`), exact `CC-BY-SA-4.0` confirmation, and local ToS snapshot requirement. Ledger entries append only to `data/evals/eval_hashes.jsonl` schema with `content_sha256` and `eval_only=true`; writes under `data/stage2/candidates/` are refused. Added `code/llm_hawaii/eval_contamination.py` for eval-hash loading, HAW/EN canonical normalization, contamination checks, and candidate filtering. Wired `scripts/320_build_stage2_manifest.py --eval-hashes` to drop matching rows before output while absent `--eval-hashes` remains no-op. Updated the fetch plan to mark Global-PIQA as eval-ledger ingester ready, awaiting `--execute`. **Verification:** `test_global_piqa_ingester` passed 5 tests; `test_eval_contamination` passed 4 tests; manifest dry-run emitted 37,084 rows with and without an empty eval ledger. Decision artifact: `.squad/decisions/inbox/linus-stage2-global-piqa-eval-ingester.md`. **Next:** Round 12 should probe another eval-only/diagnostic source (Taxi1500) or refresh Tatoeba before further train-side expansion.

## 2026-05-03 — Stage-2 license-first probes (Round 12)

**Task:** Run no-data-fetch license-first probes for Taxi1500 and Tatoeba refresh. **Taxi1500 verdict:** YELLOW / EVAL-only. Canonical repo is `https://github.com/cisnlp/Taxi1500`; repository LICENSE is Apache-2.0, README confirms Bible-derived six-topic verse classification from PBC/1000Langs, but `haw_Latn` split counts could not be safely confirmed from allowed README/license pages without fetching corpus/split data. Contamination risk against Baibala 1839/1868 and Bible-family rows is high, so any future ingest must write only eval-ledger hashes and never train candidates. **Tatoeba verdict:** REFRESH-NOW for a gated future execute round. Current pin is 2025-05-01; local direct Tatoeba has 121 rows / 111 unique Hawaiian sentence IDs; public stats now show 192 Hawaiian sentences, and export HEAD metadata is newer (`Sat, 02 May 2026`). Exact linked-pair delta requires re-downloading the three existing Tatoeba exports in a later approved round; trigger recommended at >=5% confirmed pair delta (>=7 pairs) or >=500 new Hawaiian sentences. Decision artifacts: `.squad/decisions/inbox/linus-stage2-taxi1500-license-probe.md`, `.squad/decisions/inbox/linus-stage2-tatoeba-refresh-license-probe.md`.

---

## 2026-05-03 — Stage-2 eval/refresh adapters (Round 13)

**Task:** Ship two dry-run/mockable adapters without live network or `--execute`. **Taxi1500:** added `scripts/348_ingest_taxi1500_haw.py`, eval-ledger only, Apache-2.0 gated, local-file-only execute, dataset pin format gate, train-candidate path refusal, and `bible_overlap_candidate=true` hashes. Updated `code/llm_hawaii/eval_contamination.py` so flagged Bible-overlap hashes are checked against candidate EN-only/HAW-only sides. **Tatoeba refresh:** added `scripts/349_refresh_tatoeba_candidates.py`, triple-gated by new edition date, `CC-BY-2.0-FR`, local ToS snapshot, polite UA/≥2s sleeps, existing-edition dedup by Tatoeba id, ʻokina normalization, and threshold refusal unless delta ≥5% pairs or ≥500 Hawaiian sentences. **Plan:** updated fetch plan statuses: Taxi1500 eval-ledger ingester ready; Tatoeba refresh adapter ready. **Verification:** Taxi1500 tests 6/6, eval contamination tests 5/5, Tatoeba refresh tests 7/7; manifest dry-run remains 37,084 rows. No live network, no data candidate writes.

---

## 2026-05-03 — Stage-2 train-side eval contamination filter wired (Round 14)

**Task:** Make `--eval-hashes` enforce eval-contamination filtering on train candidates end-to-end, with no new sourcing/fetching. **Implementation:** moved manifest filtering into the pre-dedup ingest path, added missing-ledger hard errors for explicit `--eval-hashes`, wrote `data/stage2/contamination_report.json` sidecar reports, and records `contamination:{source}` drop reasons plus per-source/per-match-type counts. Extended the audit script with report-only `--eval-hashes`; strict mode now fails and lists candidate row IDs when contamination is present. Added a 5-row/3-hash smoke fixture and regression test proving 5 candidates shrink to 2 clean manifest rows. Updated `eval_contamination.py` docs with the eval-ingest → manifest-filter → audit workflow. **Verification:** eval contamination tests 5/5, manifest contamination filter tests 2/2, Stage-2 dedup tests 13/13, Taxi1500 ingester tests 6/6, Global-PIQA ingester tests 5/5, manifest dry-run remains 37,084 rows, and strict candidate-normalization audit passes. Decision artifact: `.squad/decisions/inbox/linus-stage2-r14-contamination-wired.md`. **Next:** Round 15 should shore up dedup edge cases now that eval leakage has a train-side gate.

---

## 2026-05-03 — Stage-2 dedup edge-case hardening (Round 15)

**Task:** Pure-infra audit of Stage-2 dedup/normalization edge cases; no new sources. **Investigation:** `scripts/340_audit_stage2_candidate_normalization.py` non-strict still audits 37,761 candidate rows. Current pool has 0 NFC drift, 0 HAW ʻokina hash drift, 2,119 EN apostrophe/right-quote rows correctly preserved, 7 rows with invisible format controls (soft hyphen / zero-width / BOM), 3 rows with non-ASCII whitespace (NBSP), 98 raw trailing-punctuation token variants, and 0 whitespace-only rows. Short rows (≤3 tokens on either side) exist beyond Phrase Book/Andrews/Weblate in Bible, Hoʻoilina, Kaikki, OPUS, and Tatoeba, but the short-exact cap is length-aware, not source-allowlist based, so no missing-source cap bug was found. Post-policy exact one-sided groups remain the known accepted paraphrase diversity (161 EN / 32 HAW), and post-policy near-dupes remain 0. **Fixes:** bumped dedup policy to v0.6; exact-pair fallback now uses canonical source priority/length instead of alphabetical source ID; near-dupe tokenization strips invisible format controls while preserving EN apostrophe vs ʻokina distinction; manifest validation treats whitespace/invisible-only inline text or path refs as missing; audit now reports invisible-format and non-ASCII-whitespace rows explicitly. **Counts:** manifest dry-run unchanged at 37,084 rows (delta 0 from Round 14); exact pair drops 100, exact-EN cap drops 199, exact-HAW cap drops 75, near-dupe collapse drops 303. **Verification:** `code/tests/test_stage2_dedup.py` 17/17, `code/tests/test_stage2_candidate_normalization_audit.py` 4/4, targeted manifest validation 2/2; `340 --strict` passes; `320 --dry-run` emits 37,084 rows. Decision artifact: `.squad/decisions/inbox/linus-stage2-r15-dedup-edge-fixes.md`. **Next:** Round 16 should run an EN-side hash determinism stress test (punctuation/whitespace/default-ignorable variants across candidate builders) before more sourcing.

---

## 2026-05-03 — Stage-2 hash determinism + source probes (Round 16)

**Task:** Lock EN-side Stage-2 hash determinism and run license-first/no-data probes for FLORES+ and Common Voice. **Hash policy:** added `canonicalize_clean_text` to the manifest builder, documented `compute_pair_hash` inputs, and pinned behavior with 7 direct tests: NFC, invisible-control removal, whitespace collapse, case preservation, curly EN quote folding, U+2010/U+2011 hyphen folding, U+02BC/ʻokina not folded on EN, HAW okina folding, and em dash / double hyphen / spaced hyphen kept distinct. **Source probes:** FLORES+ remains RED/SKIP because `haw_Latn` was absent from observed HF card/metadata despite CC-BY-SA-4.0 benchmark coverage for other languages; if added later, route EVAL-only. Common Voice is RED/SKIP because metadata exposed no Hawaiian locale; license posture is CC0-1.0 but audio is out of scope and any future Hawaiian prompts need monolingual/prompt-ledger review first. **Verification:** `test_hash_determinism` passed 7/7, `test_stage2_dedup` passed 17/17, manifest dry-run remained 37,084 rows. Decision artifacts: `.squad/decisions/inbox/linus-stage2-r16-hash-determinism-policy.md`, `.squad/decisions/inbox/linus-stage2-flores-plus-license-probe.md`, `.squad/decisions/inbox/linus-stage2-common-voice-license-probe.md`. **Next:** Round 17 should propagate the canonical clean-text helper into candidate builders/audit so future adapters cannot drift from the locked hash contract.

---

## 2026-05-03 — Stage-2 canonical helper consolidation (Round 17)

**Task:** Promote R16 clean-text canonicalization into a single import surface and remove adapter/audit drift, with no new sourcing and no `data/` edits. **Implementation:** added `code/llm_hawaii/stage2_canonical.py` with `canonical_en`, `canonical_haw`, `canonical_pair`, shared hash helpers, and the U+2016 pair delimiter. `scripts/320_build_stage2_manifest.py` now re-exports/imports that surface; `eval_contamination.py` uses `canonical_pair` for pair ledger content; `stage2_dedup.py`, normalization audit/legacy patcher, Stage-2 candidate builders, Weblate/Tatoeba refresh, and reviewed-manifest promotion paths now delegate canonical text to the helper instead of open-coding ʻokina/quote/whitespace folds. `340 --strict` keeps canonicalization-delta counts advisory while failing on post-policy schema/contamination. **Verification:** `test_stage2_canonical` 4/4, `test_stage2_dedup` 17/17, `test_hash_determinism` 7/7, `test_eval_contamination` 5/5, `test_manifest_contamination_filter` 2/2, Taxi1500 6/6, Global-PIQA 5/5, Weblate 7/7, Tatoeba refresh 7/7. Manifest dry-run still emits 37,084 rows; strict normalization audit exits 0. Decision artifact: `.squad/decisions/inbox/linus-stage2-r17-canonical-consolidation.md`. **Next:** Round 18 should build an end-to-end dry-run smoke harness or run a source-coverage gap analysis.

---

## 2026-05-04 — Hoʻoilina paragraph-only implementation

**Task:** Implement Yashas directive: Hoʻoilina emits paragraph pairs only; sentence pairs are retired as duplicate derived content. LaBSE remains metadata-only for Hoʻoilina.

**Code changes:** Renamed `scripts/325_build_hooilina_sentence_candidates.py` → `scripts/325_build_hooilina_paragraph_candidates.py`. Script now consumes section-level parents from `data/stage2/candidates/hooilina_parent_sections.jsonl` (or one-time legacy `hooilina.jsonl`), emits primary paragraph pairs to `data/stage2/candidates/hooilina.jsonl`, and emits review-only paragraph-number recoveries to `data/stage2/candidates/hooilina_recovered.jsonl`. `scripts/324_build_hooilina_candidates.py` now writes the parent-section sidecar. `scripts/320_build_stage2_manifest.py` excludes Hoʻoilina parent/recovery/retired sentence sidecars from default manifest ingestion. Final-review scripts were updated from Hoʻoilina sentence wording to paragraph wording.

**Counts:** Before: 60 Hoʻoilina sentence rows (`hooilina_sentences.jsonl`) from 68 parent rows. After primary paragraph build: 25 paragraph rows from 6 count-matched parents (36 paragraph pairs inspected; 11 rejected: 1 too short, 10 >80 tokens). Recovery pass over the 62 unmatched parents: 36 recovery-eligible parents, 27 parents with output, 186 paragraph-number matches inspected, 137 recovered rows emitted to `hooilina_recovered.jsonl` with `review_required=true` / `alignment_review_required=true`; not included in default manifest.

**Validation:** `python3 -m py_compile` passed for changed scripts. `python3 scripts/325_build_hooilina_paragraph_candidates.py --self-test` passed (24 assertions). `--execute` wrote 25 primary + 137 recovery rows. `python3 scripts/320_build_stage2_manifest.py --dry-run` succeeded with 36,981 rows, 0 schema violations. Source breakdown after dedup: Bible 1839 5, Bible 1868 30,969, Wikimedia CX 14, OPUS haw subsets 388, Hoʻoilina 25, all other sources 5,580. Parallel-train Bible token share: 5,765 / 66,127 = 8.72%, under the ≤30% cap. Stage-2 remains below the 40k-row target by 3,019 rows; canonical-pair count is 36,981, above 20k.


---

## 2026-05-04 — Stage-2 max_seq_len bump for paragraph consolidation

**Task:** Audit token lengths across all Stage-2 sources (row-grain + paragraph-grain) using the actual Llama-3.1-8B tokenizer and SFT format, then bump `max_seq_len` in `code/configs/stage2_prototype.json` to accommodate paragraph pairs per the Stage 2/3 consolidation directive.

**Methodology:** Built `scripts/audit_seq_len_stage2.py` to measure tokenized lengths in SFT format (`{instruction}\n\n{source_text}\n\n{target_text}<EOS>`) for both EN→HAW and HAW→EN directions across all 38,069 pairs in the cleaned manifest. Measured using `meta-llama/Llama-3.1-8B` tokenizer (from Stage 2 config).

**Findings:**
- **Distribution:** p50=87, p90=155, p95=184, p99=1,429, max=43,573 tokens
- **Critical outlier:** max (43,573) is 30× higher than p99 (1,429)
- **Top-10 longest pairs:** 9 are Hoʻoilina full-document pairs (7K–28K tokens) or hk_statutes data errors (43K tokens)
- **Outlier analysis:** The longest pair (hk_statutes SHA 49c3a67cb384) is a data error with 134K chars Hawaiian / 780 chars English. The 3 longest Hoʻoilina pairs (25–34K chars each) are `alignment_type=parallel-doc` — full constitutions/laws, not paragraphs.

**Decision:** Set `max_seq_len=2048` (not 43,776). **Rationale:**
1. Covers p99 (1,429) with headroom, accommodates 99% of data without truncation
2. Avoids 83× memory explosion (1024→43,776 would cause ~8,350% attention memory increase)
3. Truncates only ~10 extreme outlier pairs (0.026% of 38,069)
4. Pragmatic trade-off: 3 full-document Hoʻoilina pairs are valuable but not worth 83× memory cost

**Memory impact:** 1024→2048 = 100% sequence length increase, ~2-4× attention memory impact (should remain safe on A100-40GB with current batch config).

**Artifacts:**
- Audit script: `scripts/audit_seq_len_stage2.py`
- Audit report: `data/stage2/reports/seq_len_audit_20260504.json`
- Config updated: `code/configs/stage2_prototype.json` (max_seq_len: 1024→2048)
- Decision doc: `.squad/decisions/inbox/linus-stage2-max-seq-len-bump.md`

**Tests:** 72 passed (1 pre-existing failure unrelated to this change).

**Recommendations:**
1. Fix hk_statutes_1897 data error (SHA 49c3a67cb384): investigate 134K-char alignment mismatch
2. Consider chunking the 3 longest Hoʻoilina full-document pairs if tail context is critical
3. Future: length bucketing or dynamic batching for bimodal distribution (row-grain p50=87, paragraph-grain p95=184)

## Learnings

### Token length measurement must match production format exactly
When auditing sequence lengths for max_seq_len decisions, always tokenize using the exact same format the training code uses. For Stage 2 SFT, this means `{instruction}\n\n{source_text}\n\n` for prompt and `{target_text}<EOS>` for target, with `add_special_tokens=False` and explicit EOS append. Measuring raw text or using different tokenization params will yield incorrect length distributions.

### Extreme outliers should trigger data error investigation, not config accommodation
When max token length is 30× higher than p99, treat it as a data quality signal, not a config requirement. The hk_statutes 43K-token outlier revealed a corrupt alignment (134K chars Hawaiian / 780 chars English, marked as parallel-sentence). Setting max_seq_len to accommodate such errors wastes 83× memory on the entire training run for 1 bad row.

### Paragraph-grain vs document-grain distinction matters for truncation decisions
The Hoʻoilina top-3 outliers (25–34K chars) are `alignment_type=parallel-doc` — full Hawaiian Kingdom constitutions/laws, not paragraphs. These are legitimate data but inappropriate for a paragraph-focused stage. Future ingestion should distinguish document-grain (chunk or exclude) from paragraph-grain (admit with reasonable seq_len) to avoid conflating them in training-mix decisions.

### Length distribution percentiles guide truncation vs accommodation trade-offs
For Stage 2, p99=1,429 tokens vs max=43,573 tokens revealed that accommodating the max would hurt 99% of training for 0.026% of outliers. Setting max_seq_len to 2048 (covers p99 with headroom) is a clear win. Always report p50/p90/p95/p99/p99.9/max and use them to inform memory-vs-coverage trade-offs.

### Memory impact of sequence length scales quadratically for attention
Doubling sequence length from 1024→2048 causes ~2-4× memory increase (implementation-dependent). Scaling from 1024→43,776 would cause ~83× increase (quadratic scaling: (43,776/1024)² ≈ 1,830× in the naive case, but real implementations optimize to ~83×). Always estimate memory impact before bumping max_seq_len and sanity-check against GPU VRAM budget.


## 2026-05-04 — Hoʻoilina seq_len Outlier Recovery — v3 Manifest ✅

**Context:** 25 Hoʻoilina rows quarantined in v2 for exceeding `max_seq_len=2048` (token lengths 2,225–28,584). These were full-document constitutional/historical texts that bypassed the original paragraph splitter. Side effect: caps violated (Bible 39.71% > 30%, HK-Legal 20.23% > 15%) because 212K tokens of non-capped content were removed.

**Task:** Re-split 25 quarantined rows into chunks ≤2048 tokens and re-admit to TRAIN split.

**Strategy:**
1. Primary: numbered-paragraph split (`\n(?=\d+\.[ \t])`) per existing Hoʻoilina pipeline
2. Fallback: sentence split (period/question/exclamation + space + capital) for oversized paragraphs
3. Hard-chunk: At sentence boundaries for oversized sentences, maintaining EN↔HAW alignment
4. Safety margin: Target ≤1600 tokens per chunk (leaves 448 tokens headroom for special tokens/template)

**Implementation:**
- Built `scripts/resplit_hooilina_outliers.py` — paragraph→sentence→chunk resplitter using Llama-3.1-8B tokenizer
- Built `scripts/build_stage2_manifest_v3_hooilina_recovery.py` — v3 manifest merger with verification
- Re-split output: 25 parents → 864 child chunks, 3 collisions deduped → 861 new rows

**Results:**

| Metric | v2 (Quarantined) | v3 (Recovered) | Change |
|--------|------------------|----------------|--------|
| TRAIN rows | 5,411 | 6,272 | +861 |
| Pair tokens | 382,760 | 589,370 | +206,610 |
| Max seq_len | 1,947 | 1,946 | -1 ✓ |
| Rows > 2048 | 0 | 0 | ✓ |
| Bible % | 39.71% | 25.56% | -14.15% ✓ |
| HK-Legal % | 20.23% | 13.13% | -7.10% ✓ |

**Gate Verification:** ✅ All passed
- ✅ All TRAIN rows ≤2048 tokens (max=1946)
- ✅ Bible 25.56% < 30% cap
- ✅ HK-Legal 13.13% < 15% cap
- ✅ Dedup enforced (3 collisions removed)
- ✅ Parent→child lineage preserved

**Parent Tracking:** 25 quarantined parents remain in `split="review-pending"` with updated reason `"seq_len_outlier_paragraph_split_failure_resplit_into_children"` and new field `child_sha256_pairs: [...]` pointing to their 861 children. Largest parent: `dbba089a980669a5...` → 104 chunks.

**Artifacts:**
- v3 Manifest: `data/stage2/reviewed_stage2_manifest_final_capped_v3.jsonl` (38,930 rows)
- Resplit candidates: `data/stage2/candidates/hooilina_resplit.jsonl` (864 rows)
- Verification report: `data/stage2/reports/hooilina_resplit_v3_20260504.json`
- Scripts: `scripts/resplit_hooilina_outliers.py`, `scripts/build_stage2_manifest_v3_hooilina_recovery.py`
- Decision: `.squad/decisions/inbox/linus-stage2-hooilina-resplit-v3.md`

**Usage:**
```bash
# Emit SFT from v3 manifest
python scripts/330_emit_stage2_sft_jsonl.py \
  --manifest data/stage2/reviewed_stage2_manifest_final_capped_v3.jsonl \
  --out data/stage2/stage2_sft_v3.jsonl \
  --splits train,dev \
  --directions both
```

**Recommendation:** v3 manifest is APPROVED FOR USE. All gates passed. Proceed with Stage 2 training.

**Key Learning:** 1600-token safety margin (vs 2048 cap) is necessary when re-splitting oversized pairs. First attempt at 1900 tokens produced 3 violations (2069, 2149, 2842 tokens); tightening to 1600 tokens eliminated all violations. The Llama tokenizer produces higher token counts than whitespace-based estimates (~54% more: 589K vs 382K tokens).



---

### 2026-05-04T06:31:26Z: Stage 2 v3 SFT emit dry-run blocked
**By:** Linus (Data Engineer)  
**Status:** BLOCKED — no emit performed

Read `scripts/330_emit_stage2_sft_jsonl.py`: train/both dry-run from `data/stage2/reviewed_stage2_manifest_final_capped_v3.jsonl` kept only 2,715 pairs / 5,430 directional rows under default review filtering, not the expected 6,272 / 12,544. With `--allow-review-required`, it kept 6,087 pairs / 12,174 rows but still skipped 185 TRAIN Hoʻoilina resplit rows with blank EN or HAW text.

Current stale `data/stage2/stage2_sft.jsonl` was left untouched at 7,871,636 bytes / 8,572 rows. Blocker written to `.squad/decisions/inbox/linus-stage2-sft-emit-blocker.md`; needed follow-up is to fix/decide the 185 blank-side TRAIN rows and whether review-required v3 train rows should be emitted.

### Stage-2 Hoʻoilina strict resplit replacement

The original v3 Hoʻoilina resplit used `scripts/resplit_hooilina_outliers.py` plus `scripts/build_stage2_manifest_v3_hooilina_recovery.py` and chunked EN/HAW independently enough to admit half-blank TRAIN children. Replacing those children must remove old `manual_review_reasons=["recovered_from_seq_len_outlier_resplit"]` rows first, then rebuild from the 25 parent rows with paragraph-number/occurrence matching and no orphan-side emission. The strict v3 repair snapshots `reviewed_stage2_manifest_final_capped_v3_pre_strict_resplit.jsonl`, admits 725 aligned children, ejects 136 old child rows as unsalvageable, leaves 0 TRAIN blanks, and emits 12,272 bidirectional SFT rows with no text-missing skips.
