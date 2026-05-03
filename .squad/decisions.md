# Decisions

> Updated 2026-05-03T10:50:51Z: Merged R5 linus-stage2-near-dupe-policy (37,661→37,223 rows; 306 near-dupe groups collapsed, strong Bible-Gospel-John signal). Prior 2026-05-03T10:25:53Z: Merged 11 inbox files from Stage 2 autonomous work round. Five primary decisions: (1) Linus sanitary-schema-gate, (2) Basher stage1-loss-plateau, (3) Danny final review verdict policy, (4) Basher implementation complete, (5) Basher Ulukau validation.
>
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
