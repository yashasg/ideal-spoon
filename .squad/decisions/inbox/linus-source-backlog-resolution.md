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
