# Decisions

> Updated 2026-05-02T00:56:01Z: Merged 9 inbox files from Stage 2 final review verdicts session. Three primary decisions: (1) Danny final review verdict policy (closed enum, source-specific rules, 10 invariants), (2) Basher implementation complete (33,851 rows with verdict fields; Bible 29.92%, HK 14.59% caps verified; SFT 570 rows unchanged), (3) Basher Ulukau validation (hooilina.jsonl has HTML entity bugs; 6-check protocol established for all future candidates). Frank ready to plan NLLB/synthetic-BT yield using 32,756 re-promotion budget from stage2_final_review_verdicts_20260501.json. Linus HK statutes processing continues; Hoʻoilina adapter blocked on HTML decode fix.
>
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

Three fields are added to **every row** in the artifact (train + dev +
review-pending). No row may be missing them.

| Field | Type | Allowed values | Meaning |
|---|---|---|---|
| `review_status` | string | `finalized` | All rows; this artifact closes the review pass. |
| `review_verdict` | string | enum below (§2.3) | The categorical adjudication. |
| `final_review_reason` | string | free-text, ≤ 240 chars | Human-readable rationale citing the rule that produced the verdict. |

`review_status=finalized` is **uniform** — its purpose is to make it
trivial to assert "no row in the shipped artifact is unreviewed."
Future reviews would create a new artifact, not flip this field in
place.

### 2.3 Verdict taxonomy

Closed enum. Anything not in this list requires a new ADR.

| Verdict | Applies to | Promotable later? |
|---|---|---|
| `accepted-train` | The 285 train rows. | n/a (already train) |
| `accepted-dev` | The 15 frozen Tatoeba dev rows. | n/a (already dev) |
| `excluded-quality` | Row failed scorer / quality_flags / OCR / diacritic checks. | No — re-extract upstream first. |
| `excluded-policy-cap` | Row was structurally fine but dropped by the §1.4/§1.5/Bible/HK cap. | **Yes** — eligible for re-promotion only if N (non-Bible non-HK tokens) grows; cap math is the gate. |
| `excluded-source-not-trainable-now` | Source-level rights/year-mismatch/register block (Andrews, Hoʻoilina). | Conditional — see §3. |
| `future-work-realign` | Row needs a different alignment strategy (e.g., section-level vs. verse-level) before it could re-enter. | Yes, after re-alignment. |
| `future-work-native-review` | Row needs Hawaiian-literate human review (W1 reviewer) before any promotion. | Yes, gated on #7 reviewer. |
| `inventory-only` | Row exists for provenance / dedup signal; never intended for SFT. | No. |

`excluded-policy-cap` is the **only** verdict that means "would have
been trainable if the budget allowed." This distinction is the entire
point of the taxonomy: a future N-growth pass (NLLB-mined, synthetic
BT) re-runs the fixed-point cap and pulls from the
`excluded-policy-cap` pool only. It must never accidentally pull from
`excluded-quality` or `future-work-native-review`.

### 2.4 Optional companion field

`final_review_repromotion_pool` (string, optional) — when
`review_verdict=excluded-policy-cap`, this names the pool the row
belongs to (`bible-1839-cap-overflow`, `bible-1868-cap-overflow`,
`hk-1897-cap-overflow`). Used by future cap-rerun scripts to find
candidates without re-deriving eligibility.

---

## 3. Source-specific verdict rules

These rules are deterministic — Basher's implementation script must be
able to assign verdicts from existing fields without judgment calls.

### 3.1 Bible 1839 (`baibala-hemolele-1839`) — 10,216 review-pending

Two sub-pools exist, distinguishable by existing fields:

| Sub-pool | Selector | Verdict | `final_review_reason` |
|---|---|---|---|
| Cap overflow | row not in 5-row train selection AND `quality_flags` empty AND `alignment_review_required=false` | `excluded-policy-cap` (`pool=bible-1839-cap-overflow`) | `dropped-by-bible-cap-v2-fixedpoint; eligible for re-cap when N grows` |
| Quality reject | `quality_flags` non-empty OR `alignment_review_required=true` | `excluded-quality` | `quality_flags=[…]; haw_no_diacritics dominant in 1839 imprint` |

Note: the 1839 imprint is historical orthography (no kahakō/ʻokina);
the `haw_no_diacritics` flag is **expected** for 1839 and is the
correct quality signal to keep these out of train. Do not "rescue"
these rows by relaxing the diacritic check — that is a separate
re-extraction decision, not a review verdict flip.

### 3.2 Bible 1868 (`baibala-hemolele-1868`) — 20,827 review-pending

The dedup pass already removed 1839 overlaps (10,134 rows) and internal
dupes (115). The 25 train rows are the cap allotment. Of the 20,827
remaining:

- All have `quality_flags=[]` and `alignment_review_required=false`
  (per report `bible_quality_dropped=0` for 1868).
- Verdict: **`excluded-policy-cap`** (`pool=bible-1868-cap-overflow`).
- `final_review_reason`:
  `dropped-by-bible-cap-v2-fixedpoint; passes quality; re-promotable if N grows`.

This is the largest re-promotion pool in the artifact.

### 3.3 HK Statutes 1897 (`hk_statutes_1897`) — 1,098 review-pending

The 5 train rows came from the cap. Of the remaining 1,098:

| Sub-pool | Selector | Verdict |
|---|---|---|
| Cap overflow, eligible per Rusty §1.5 | row in `hk_eligible_pool` (747 of 1,098) and not in 5-row train selection (= 742) | `excluded-policy-cap` (`pool=hk-1897-cap-overflow`) |
| Failed §1.5 promotion rule | row not in `hk_eligible_pool` (= 351) | `excluded-quality` with reason `hk1897-legal-clean-v1 promotion rule failed` |

Implementation note: Basher must re-derive `hk_eligible_pool`
membership using the same predicate as
`333_build_reviewed_manifest_final_capped.py` — do not trust an
ad-hoc field; the pool is the source of truth.

### 3.4 Andrews 1865 (`andrews-1865-en-haw-vocab-appendix`) — 1,194 review-pending, 0 train

Frozen at zero by Rusty §1.1 (OCR noisy, no diacritics, dictionary
register saturated by Kaikki). All 1,194:

- Verdict: **`excluded-source-not-trainable-now`**
- `final_review_reason`: `Rusty §1.1: Andrews 1865 IA-djvu OCR;
  alignment_review_required=true on 100% of rows; not trainable
  pending a clean re-extraction (e.g., Wehewehe-side parse) and W1
  reviewer pass`
- `final_review_repromotion_pool`: not set; re-promotion requires
  upstream re-extraction, not a cap rerun.

### 3.5 Kaikki Wiktionary (`kaikki-haw-en-wiktionary`) — 139 review-pending, 153 train

Of the 139 leftovers, 94 are `side_too_short`, 41 `haw_nonhaw_letters_high`,
25 `length_ratio_extreme`, 6 `haw_no_diacritics` (overlap possible).

- Verdict: **`excluded-quality`**
- `final_review_reason`: `quality_flags=[…]` (echo the actual flags)
- These are **not** cap-overflow — Kaikki has no source cap; the 153
  train rows are everything that passed the scorer. The leftovers
  failed quality and stay out unless the source is re-cleaned.

### 3.6 Tatoeba (`tatoeba`) — 9 review-pending, 97 train, 15 dev

All 9 leftovers are `side_too_short`.

- Verdict: **`excluded-quality`**
- `final_review_reason`: `quality_flags=[side_too_short]`
- Frozen Tatoeba dev (15 rows) is untouched and gets verdict
  `accepted-dev`.

### 3.7 Hoʻoilina (`hooilina`) — 68 review-pending, 0 train

Per Rusty §1.4 (Hoʻoilina rights are prototype-only with citation;
dev/test promotion is forbidden, train promotion deferred until
section-level review).

- Verdict: **`future-work-native-review`**
- `final_review_reason`: `Rusty §1.4: KS editorial layer requires
  section-level Hawaiian-literate review (W1 reviewer / #7) before
  any train promotion; release_eligible=false`
- `final_review_repromotion_pool`: not set.

### 3.8 (Inventory-only sources)

If Basher's verdict-assignment pass discovers any rows with
`prototype_only=true` AND `release_eligible=false` AND no source-cap
membership AND no quality flags AND no alignment_review_required (none
expected, but defensive): assign `inventory-only` with reason
`provenance-only; not a training candidate`.

---

## 4. Expected post-implementation invariants

Basher's implementation must verify all of the following against the
**emitted artifact** (the same discipline as the fixed-point cap pass —
trust the file, not the script's print statements):

1. **Field presence.** Every row has non-null `review_status`,
   `review_verdict`, `final_review_reason`. Zero exceptions.
2. **Schema split unchanged.** Counts of `split=train` (285),
   `split=dev` (15), `split=review-pending` (33,551) are byte-identical
   to the current artifact.
3. **Verdict ↔ split consistency.** `review_verdict=accepted-train` ⟺
   `split=train`. `review_verdict=accepted-dev` ⟺ `split=dev`. Any row
   with `split=review-pending` has a verdict ∈ {`excluded-quality`,
   `excluded-policy-cap`, `excluded-source-not-trainable-now`,
   `future-work-realign`, `future-work-native-review`,
   `inventory-only`}. No `accepted-*` verdict on a `review-pending`
   row.
4. **Closed enum.** No verdict outside §2.3.
5. **Cap-pool membership coherent.** Sum of rows with
   `final_review_repromotion_pool=bible-1839-cap-overflow` plus the 5
   Bible-1839 train rows equals the Bible-1839 quality-pass pool size
   (i.e., 10,221 verse keys minus quality-rejected 1839 rows). Same
   shape for 1868 and HK 1897 against the report's
   `bible_pool_total` / `hk_eligible_pool`.
6. **Source-rule coverage.** For each of the 7 sources in §3, the
   distribution of verdicts matches the rule table exactly. Counts
   logged in a new report
   `data/stage2/reports/stage2_final_review_verdicts_<date>.json`.
7. **Caps still hold.** Bible share ≤ 30% and HK share ≤ 15% on the
   re-emitted artifact (re-run the artifact-side verifier from
   `333_build_reviewed_manifest_final_capped.py`).
8. **SFT emitter unchanged behavior.** `data/stage2/stage2_sft_final_capped.jsonl`
   regenerates to the same 570 directional rows. The new fields are
   ignored by the emitter — confirm via byte-diff or row-count check.
9. **No row claims to be both quality-rejected and cap-overflow.**
   `excluded-quality` and `excluded-policy-cap` are mutually exclusive.
10. **Honesty check.** Sum of `excluded-policy-cap` rows is the
    upper-bound budget for any future N-growth re-promotion. This
    number must appear in the new report so Frank's NLLB / synthetic-BT
    plan can quote it without re-deriving.

---

## 5. What this policy does **not** do

- It does not change which rows are in train. The 285/15 are locked.
- It does not relax any cap, scorer threshold, or rights gate.
- It does not promote any Andrews or Hoʻoilina row.
- It does not modify the canonical `stage2_manifest.jsonl`.
- It does not add a "review-completed" boolean. `review_status=finalized`
  is the single signal; future reviews produce a new artifact with a
  new datestamp.
- It does not commit to a re-promotion pass. It only *budgets* one
  honestly: when (and if) N grows enough that
  `B_max = 6N/11` and `H_max = 3N/11` exceed the current 285-row
  selection, the `excluded-policy-cap` pool is the **only** legal
  source.

---

## 6. Trade-offs (named, per charter)

- **Verdict granularity vs. cognitive load.** Six exclusion verdicts
  is more than two ("dropped" / "deferred") but less than per-source
  freeform reasons. Six was chosen because it maps 1:1 onto the
  *operational* question "what would unblock this row?" — cap rerun,
  re-extraction, re-alignment, native review, never. A reader who only
  wants the binary answer can collapse `excluded-*` vs `future-*`.
- **Schema-split kept noisy on purpose.** Reusing `split=review-pending`
  as the emitter signal preserves the existing `333_*` and emitter
  contracts at the cost of overloading the field. The alternative
  (introduce `split=excluded` and update the emitter) is a wider blast
  radius; the verdict fields give us the editorial signal without that
  churn.
- **Closed-form pools instead of per-row provenance.** We tag the cap
  pool name, not the position in the cap selection. Cheaper to compute,
  reproducible from `sha256_pair` ordering. Cost: a future re-cap pass
  must re-sort and re-select; it cannot resume from a half-emitted
  state. Acceptable — the cap pass is sub-second.
- **No backfill of `manual_review_reasons`.** That field stays as the
  upstream Rusty/Linus annotations. `final_review_reason` is the
  *adjudication* layer on top. Two fields, two purposes; do not merge.

---

## 7. Hand-off

- **Basher (implementation owner):** Write
  `scripts/334_finalize_review_verdicts.py` that takes
  `reviewed_stage2_manifest_final_capped.jsonl` as input, applies §3,
  emits `reviewed_stage2_manifest_final_capped.jsonl` (in-place
  rewrite is OK; keep a `.bak` of the prior file once) plus
  `data/stage2/reports/stage2_final_review_verdicts_<date>.json`.
  Verify all ten invariants in §4. Re-run the SFT emitter and confirm
  570 rows.
- **Linus:** Confirm verdict assignment for HK 1897 sub-pool
  (`hk_eligible_pool` predicate). Update SFT-side documentation to
  point at `review_verdict` instead of "split=review-pending" when
  describing exclusion semantics.
- **Frank:** Read the new report's `excluded-policy-cap` totals before
  finalizing the NLLB-mined / synthetic-BT yield plan. Those numbers
  are the honest re-promotion ceiling; do not exceed them with mined
  pairs that re-trip the cap.
- **Rusty:** No action required. This policy *consumes* Rusty's
  review-pending policy; it does not amend it.

---

## 8. Status

ACCEPTED for implementation. Pending Basher pickup.

---

# Decision: Basher — Stage 2 Finalized Review Verdicts (2026-05-02)

**Owner:** Basher (Training Engineer)  
**Date:** 2026-05-02  
**Status:** COMPLETE — no team decision required; informational

## Summary

All 33,551 review-pending rows in `reviewed_stage2_manifest_final_capped.jsonl` now carry explicit final verdicts. No rows remain in an ambiguous pending state.

## Verdict Distribution

| Verdict | Count | Interpretation |
|---------|------:|----------------|
| bible-cap-overflow | 31,012 | Passed quality; excluded by fixed-point Bible cap (≤30%) |
| andrews-dictionary-fragment-rejected | 1,194 | Rusty §1.1 rejection; dictionary fragments unsuitable for SFT |
| hk-legal-cap-overflow | 742 | Passed hk1897-legal-clean-v1 filter; excluded by HK cap (≤15%) |
| hk-quality-reject | 356 | Failed hk1897 ratio/length quality filters |
| kaikki-quality-reject | 139 | Failed stage2 quality gate |
| hooilina-alignment-pending | 68 | **Deferred** — requires adapter re-emit before promotion review |
| bible-quality-reject | 31 | Failed quality gate (independent of cap) |
| tatoeba-quality-reject | 9 | Failed stage2 quality gate |
| train-ready | 285 | Accepted train pairs |
| frozen-dev | 15 | Frozen dev pairs (Rusty §1.4) |

## Action Items for Team

- **Frank / Linus:** Hoʻoilina (68 rows) is **deferred**, not rejected. If sentence-level re-emit is completed, these rows can re-enter review. Needs `html.unescape()` + boilerplate filter + hash recompute.
- **No cap changes:** Bible 29.92% / HK 14.59% unchanged. Caps hold.
- **SFT:** 570 directional rows unaffected. Use `--allow-review-required` for HK train rows.

## Artifacts

- `data/stage2/reviewed_stage2_manifest_finalized_reviews.jsonl` (33,851 rows)
- `data/stage2/reports/stage2_finalized_review_verdicts_20260501.json`
- `scripts/334_finalize_stage2_review_verdicts.py`

---

# Stage 2 Ulukau-Family Candidate Validation — Proposal

**Author:** Basher (Tester / Validation Engineer)
**Date:** 2026-05-03
**Status:** PROPOSAL — for Scribe merge

---

## Context

Linus and Frank are building adapters for HK statutes and Wehewehe PD respectively.
`hooilina.jsonl` is the only Ulukau-family candidate currently on disk.
This document codifies (a) findings from validating `hooilina.jsonl` and
(b) the mandatory validation checklist that all future Ulukau-family candidate
JSONL files must pass before manifest merge.

---

## 1. Findings: `data/stage2/candidates/hooilina.jsonl`

| Check | Result |
|---|---|
| JSONL parse (0 errors) | ✅ |
| Required fields present in all rows | ✅ |
| `sha256_pair` hash invariant | ✅ |
| Duplicate `pair_id` | ✅ none |
| Duplicate `sha256_pair` (dedup collision) | ❌ **1 hash cluster shared by 41 rows** |
| Split distribution | `review-pending`: 109/109 (correct for KS editorial layer) |
| `prototype_only=True` / `release_eligible=False` | ✅ all rows |
| `alignment_review_required=True` | ✅ all rows |
| SFT emittable now | **0 rows** (all gated) |
| SFT potential after review + fix | **≤136 directional rows** (68 clean × 2 directions) |

### Bug 1 — UI Boilerplate Artifact (41 / 109 rows)

OID root `HASHe7d7c93d84511b86ea5ca7.*` produced rows where both
`text_en` and `text_haw` contain only the Greenstone JavaScript tooltip
`"Look up any word by double-clicking on it. Kuleana kope © 2002–2004 na N…"`.

These are not translation pairs. The dedup cluster is harmless here (manifest
dedup would collapse them to 1 representative row) but only 68 rows are real
content. The adapter must filter these at emit time.

**Fix:** In the hooilina adapter, skip any section where `text_en.strip() == text_haw.strip()` or where `text_en` matches the known Greenstone UI tooltip boilerplate string.

### Bug 2 — HTML Entity Leakage (68 / 68 content rows)

All 68 content rows have unescaped HTML numeric entities in the Hawaiian text:
- `&#699;` → ʻ (ʻokina)
- `&#256;` → Ā
- `&#332;` → Ō
- `&#298;` → Ī

The adapter did not call `html.unescape()` before NFC normalization and hash
computation. This means:
1. Text stored in candidates is incorrect (raw HTML, not Unicode).
2. `sha256_haw_clean` and `sha256_pair` will change once the fix lands —
   current `hooilina.jsonl` is stale and must be re-emitted.
3. The ʻokina canonicalization pass (`OKINA_MISENCODINGS`) does not fire
   before HTML decode, so diacritics from entity form are missed.

**Fix order (mandatory):**
```python
text = html.unescape(raw_html_body)       # decode HTML entities first
text = unicodedata.normalize("NFC", text) # then NFC
for c in OKINA_MISENCODINGS:              # then okina canonicalization
    text = text.replace(c, "\u02bb")
```

Re-emit `hooilina.jsonl` after fix. All hashes will change.

---

## 2. Mandatory Validation Checklist — Ulukau-Family Candidates

Run these checks on ANY new Ulukau-family candidate JSONL before proposing manifest merge.

### Check 1 — JSONL Parse

```bash
python3 -c "
import json, sys
errs = []
rows = []
with open(sys.argv[1]) as f:
    for i, line in enumerate(f, 1):
        try: rows.append(json.loads(line.strip()))
        except Exception as e: errs.append(f'Line {i}: {e}')
print(f'{len(rows)} rows, {len(errs)} parse errors')
for e in errs[:5]: print(e)
" data/stage2/candidates/<source>.jsonl
```

Expected: `N rows, 0 parse errors`

### Check 2 — Required Field Coverage

```bash
python3 -c "
import json, sys
REQUIRED = ['pair_id','source','text_en','text_haw','sha256_en_raw',
            'sha256_haw_raw','sha256_en_clean','sha256_haw_clean',
            'sha256_pair','manifest_schema_version','split',
            'prototype_only','release_eligible','synthetic',
            'register','alignment_type','alignment_method']
rows = [json.loads(l) for l in open(sys.argv[1])]
missing = {}
for r in rows:
    for f in REQUIRED:
        if f not in r: missing[f] = missing.get(f,0)+1
print('Missing:', missing or 'none')
" data/stage2/candidates/<source>.jsonl
```

Expected: `Missing: none`

### Check 3 — sha256_pair Hash Invariant

```bash
python3 -c "
import json, hashlib, sys
def ph(e,h): return hashlib.sha256((e+'\u2016'+h).encode()).hexdigest()
rows = [json.loads(l) for l in open(sys.argv[1])]
bad = [r['pair_id'] for r in rows if ph(r['sha256_en_clean'],r['sha256_haw_clean']) != r['sha256_pair']]
print(f'Hash mismatches: {len(bad)}')
for b in bad[:5]: print(b)
" data/stage2/candidates/<source>.jsonl
```

Expected: `Hash mismatches: 0`

### Check 4 — Dedup Collision Scan

```bash
python3 -c "
import json, sys
from collections import Counter
rows = [json.loads(l) for l in open(sys.argv[1])]
ids = Counter(r['pair_id'] for r in rows)
hashes = Counter(r['sha256_pair'] for r in rows)
dup_ids = {k:v for k,v in ids.items() if v>1}
dup_hashes = {k:v for k,v in hashes.items() if v>1}
print(f'Duplicate pair_ids: {len(dup_ids)}')
print(f'Duplicate sha256_pair clusters: {len(dup_hashes)} ({sum(v-1 for v in dup_hashes.values())} extra rows)')
# Flag same-text rows (potential boilerplate)
same_text = [r['pair_id'] for r in rows if r.get('text_en','').strip() == r.get('text_haw','').strip()]
print(f'Same text_en == text_haw (boilerplate risk): {len(same_text)}')
" data/stage2/candidates/<source>.jsonl
```

Expected: duplicate pair_ids = 0; warn if sha256_pair clusters > 0 or same-text rows > 0.

### Check 5 — SFT Dry-Run Potential

```bash
python3 -c "
import json, sys
rows = [json.loads(l) for l in open(sys.argv[1])]
gated_review = sum(1 for r in rows if r.get('alignment_review_required'))
gated_split = sum(1 for r in rows if r.get('split') not in ('train','dev','test'))
empty = sum(1 for r in rows if not r.get('text_en','').strip() or not r.get('text_haw','').strip())
emittable = len(rows) - empty
print(f'Total rows: {len(rows)}')
print(f'Gated (alignment_review_required): {gated_review}')
print(f'Gated (split not train/dev/test): {gated_split}')
print(f'Empty text: {empty}')
print(f'Emittable if review cleared: {emittable} canonical / {emittable*2} directional')
" data/stage2/candidates/<source>.jsonl
```

Expected: 0 empty-text rows; gated counts documented.

### Check 6 — Manifest Builder Dry-Run (after any new source added)

```bash
python3 scripts/320_build_stage2_manifest.py --dry-run \
  --candidates data/stage2/candidates/<source>.jsonl
python3 scripts/320_build_stage2_manifest.py --check
```

Expected: exit 0, 0 schema violations, 0 split-isolation violations.

---

## 3. Hooilina Adapter Fix Requirements

Before `hooilina.jsonl` can be merged into the manifest:

1. **HTML decode:** Apply `html.unescape()` before NFC normalization (see fix order above).
2. **Boilerplate filter:** Skip sections where `text_en.strip() == text_haw.strip()`.
3. **Re-emit:** Run adapter with `--execute` to regenerate the file; all hashes will change.
4. **Re-validate:** Run the 6-check sequence above on the re-emitted file.
5. **Alignment review:** `alignment_review_required=True` must remain; Linus/Rusty must clear it before SFT emission.

**Current effective SFT yield:** 0 rows (all gated).
**Post-fix + review potential:** ≤136 directional rows (68 clean content rows × 2 directions).

---

## 4. HK Statutes / Wehewehe PD — No Candidates Yet

As of validation run (2026-05-03), no `wehewehe*.jsonl` or `hk_statutes*.jsonl`
files exist in `data/stage2/candidates/`. Linus (HK) and Frank (Wehewehe PD)
are in-progress.

When these files appear, apply the 6-check sequence above. Additional source-specific gates:
- **HK statutes:** verify `register="legal"` on all rows; confirm 1897 Cornell pair only (not 1850/1869 until year-mismatch resolved); legal register ≤15% token cap enforcement at manifest build time.
- **Wehewehe PD:** verify source dict name in `source_url_haw` is on the PD whitelist (Andrews 1836/1865, Emerson 1845, Hitchcock 1887, Parker 1922, Dict. Biblical Words 1872); `register="dictionary-example"` on all rows; combined dict cap ≤3,806 rows remaining (1,194 consumed by andrews_1865_vocab).

---

# Frank — More Ulukau SFT Data Discovery

**By:** Frank (Hawaiian Data Collector)
**Date:** 2026-05-01T22:33:20Z
**Status:** DISCOVERY COMPLETE — no raw bytes pulled, candidates ranked for team review

---

## Context

Follow-up to the original Ulukau pivot session. User request: "go find more sft
training data in ulukau." Systematic survey of ALL Ulukau-family collections plus
targeted IA pre-1925 bilingual searches.

**Already in plan (not re-counted):**
- Ka Hoʻoilina (109 HAW/EN section pairs)
- Wehewehe (6 PD PDFs)
- Hawaiian Kingdom statutes bilingual (4 paired imprints)
- Bible/Baibala (1839 + 1868 candidate)
- Andrews 1865 vocab appendix, kaikki Wiktionary, Wikimedia CX (all in fetch-plan)

---

## New Candidates — Ranked

### Rank 1 ★★★★★ — Hawaiian Phrase Book (1881)
**IA item:** `hawaiianphrasebo00bishrich`  
**URL:** `https://archive.org/download/hawaiianphrasebo00bishrich/hawaiianphrasebo00bishrich_djvu.txt`  
**Size:** 181 KB djvu.txt  
**Why useful:** Explicit two-column EN/HAW layout. "ENGLISH | HAWAIIAN" headers with paired phrase entries throughout. Covers vocabulary and short conversational phrases across ~20 topic domains (trees, water, houses, body parts, food, clothing, commerce, etc.). 4th edition (1881) = revised and vetted.  
**Alignment unit:** phrase/term pair  
**Alignment method:** column-position (deterministic)  
**Tier:** dictionary-example (Tier C)  
**Estimated yield:** 800–2,000 pairs after filtering sub-word vocab entries  
**Rights:** PD (1881 US imprint). Google Books scan of a 19th-century publication. No scraping prohibition on IA djvu.txt.  
**Adapter approach:** djvu.txt column-split: parse on whitespace gap between EN and HAW halves per line. Filter lines where HAW side is empty or < 3 chars. Emit one pair per entry.  
**Blocker:** None. Ready for adapter implementation.  
**Register:** educational  

---

### Rank 2 ★★★★ — Hawaiian Kingdom Constitution and Laws 1852 Pair
**IA HAW item:** `hekumukanawaiam00hawagoog` (222 KB djvu.txt)  
**IA EN item:** `constitutionand00hawagoog` (238 KB djvu.txt)  
**Why useful:** Same-year (1852) paired bilingual editions of the Hawaiian Kingdom Constitution and Laws of Kamehameha III. Extends the existing `hawaiian-kingdom-statutes-bilingual` adapter with a third verified pair. Same-year match eliminates year-mismatch risk.  
**Alignment unit:** section/article  
**Alignment method:** section-id (article numbering preserved in both editions)  
**Tier:** parallel-doc (Tier B, legal register)  
**Estimated yield:** 200–600 section pairs  
**Rights:** PD (1852 Hawaiian Kingdom government publication, pre-1925). Sovereign-edicts doctrine applies. Google scan via IA — non-commercial use, djvu.txt freely accessible.  
**Adapter approach:** Extend HK statutes adapter. Add 1852 as a third pair. Section-id alignment same approach as 1897 Cornell pair.  
**Blocker:** OCR quality check on HAW Google scan (some "W→AV" substitutions observed). Linus: confirm register cap applies, add to pair registry, prototype-only gate.  

---

### Rank 3 ★★★★ — Hawaiian Statute Laws 1845-1847 Pair
**IA HAW item:** `kanawaiikauiaek00ricogoog` (1847, HAW-only Kanawai)  
**IA EN item:** `statutelawshism00ricogoog` (1546 KB djvu.txt, covers 1845+1846+1847 sessions)  
**Why useful:** Another expansion of the HK statutes adapter. The English volume explicitly covers "A.D. 1845 and 1846 and 1847," so the 1847 HAW Kanawai should match a subset of the EN volume.  
**Alignment unit:** section/article  
**Alignment method:** section-id  
**Tier:** parallel-doc (Tier B, legal register)  
**Estimated yield:** 100–400 section pairs (1847 session subset only)  
**Rights:** PD (pre-1925).  
**Adapter approach:** Must slice EN volume to 1847 session only. Year-range disambiguation pass required first.  
**Blocker:** Year-range verification needed before pairing. Treat as **inventory-only** until Linus reviews — similar caution as existing 1850/1869 year-mismatch issue.  

---

### Rank 4 ★★★ — Gospel of John in Parallel Columns (1854)
**IA item:** `gospelaccordingt00hawarich` (274 KB djvu.txt)  
**URL:** `https://archive.org/download/gospelaccordingt00hawarich/gospelaccordingt00hawarich_djvu.txt`  
**Why useful:** Explicitly formatted as parallel columns (English left, Hawaiian right). 21 chapters, ~880 verses. OCR is clean. Could serve as a supplementary English-side anchor for Bible adapter alignment.  
**Alignment unit:** verse  
**Alignment method:** verse-id (chapter.verse number visible in text)  
**Tier:** parallel-verse (Tier A, religious)  
**Estimated yield:** 700–880 verse pairs  
**Rights:** PD (1854). Mission Press, Honolulu. No scraping restriction.  
**Adapter approach:** Verse-id alignment same as Baibala adapter. Parse chapter.verse markers. HAW text is pre-1839 Baibala (early missionary translation).  
**Blocker:** OVERLAP with existing Baibala plan (already have John chapters planned). Linus: is this edition distinct enough to add, or is it dedup noise? If distinct, still counts against Bible cap (<= 30% parallel-train tokens). Recommend: use only as alternative English anchor, not as additional HAW source.  

---

### Rank 5 ★★★ — Sanitary Instructions for Hawaiians (1881)
**IA item:** `63140380R.nlm.nih.gov` (274 KB djvu.txt)  
**Why useful:** Government publication, explicitly "in the English and Hawaiian languages." 20 chapters on health/medicine/sanitation — unique register not present in other sources. Written by Walter Murray Gibson (Hawaiian Legislature, 1881).  
**Alignment unit:** chapter/paragraph  
**Alignment method:** comparable-aligned (LaBSE required, >= 0.75)  
**Tier:** comparable-aligned (Tier C, educational/health register)  
**Estimated yield:** 200–800 comparable paragraph pairs  
**Rights:** PD (1881, Hawaiian Kingdom Board of Education publication).  
**Adapter approach:** Two-phase — detect EN/HAW volume boundary; split into two corpora; align by chapter number; LaBSE paragraph scoring.  
**Blocker:** Requires LaBSE infrastructure (Rusty). Not deterministic. Lower priority than Ranks 1-3.  

---

### Rank 6 ★★ — Diglot New Testament (1859) — DEFERRED
**IA item:** `HAWPDF_DBS_HS` (2.4 MB djvu.txt, 44 MB PDF)  
**Why useful if unblocked:** Full NT in two-column HAW/EN format. Potentially 5k-7.9k verse pairs.  
**Blocker:** OCR severely garbled from two-column layout. djvu.txt is unusable. Would need hOCR/column bounding-box extraction from 84 MB hOCR file or 41 MB djvu.xml. Engineering cost is high; overlaps with existing Baibala plan; Bible cap already constrains yield. **DEFERRED until column-extraction tooling is available.**  

---

## Blocked/Deprioritized (confirmed this session)

| Source | URL | Reason |
|---|---|---|
| Hawaiian Place Names (hpn) | `ulukau.org/hpn/` | © 2002-2019 Lloyd Soehren |
| Kauakūkalahale | `ulukau.org/apo/cgi-bin/kauakuka` | © 2002-2004 Star-Bulletin/authors |
| Hawaiian Curriculum Materials (cbumbrella) | `ulukau.org/gsdl2.80/cgi-bin/library?c=cbumbrella` | © specific owners (PREL, UH CDS, etc.) |
| Māhele Database | `ulukau.org/cgi-bin/vicki` | © 2000-2005 Waihona ʻĀina |
| AHCC Historical Documents | `ulukau.org/gsdl2.85/cgi-bin/library.cgi?c=ahcchist` | © 2013 Hawaiʻi Maoli |
| EBOOK-DHLLT (Legal Land Terms) | `puke.ulukau.org/...EBOOK-DHLLT` | © 1995, 2022 Native Hawaiian Legal Corp. |
| Wehi ʻŌlelo | `wehiolelo.org` | Monolingual HAW only — no EN |
| Graduate Paper Collection (ma-phd) | `ulukau.org/ma-phd/` | 38 theses, © individual authors/UH |
| Kauakūkalahale | newspaper column | © 2002-2004 |
| Hoʻoikaika kino (cbumbrella pair) | bilingual curriculum | © 2007, 2009 PREL |

---

## Recommended Next Actions

1. **Immediate (no blockers):** Build phrase-book adapter for `hawaiianphrasebo00bishrich`.
   - Single IA djvu.txt fetch + column-split parser
   - 800-2k dictionary-example pairs, PD-clear
   - Register: educational; fits Tier C cap

2. **Linus action needed:** Review 1852 Constitution pair for HK statutes extension.
   - Confirm prototype-only gate + OCR quality acceptable
   - Year-mismatch risk = none (both 1852)

3. **Linus action needed:** Flag 1847 HAW / 1845-47 EN pair as inventory-only pending year-range verification.

4. **Bible cap check:** Confirm whether Gospel of John 1854 edition is worth adding against Bible cap, or mark as dedup-skip.

5. **Defer:** Sanitary Instructions (needs LaBSE); Diglot NT (needs hOCR column extraction).

---

## Yield Outlook (incremental, beyond existing plan)

| Source | Yield estimate | Tier | Readiness |
|---|---|---|---|
| Phrase Book 1881 | 800–2,000 pairs | dictionary-example | Immediate |
| HK Statutes 1852 pair | 200–600 pairs | parallel-doc legal | Linus OK needed |
| HK Statutes 1847 pair | 100–400 pairs | parallel-doc legal | Verify year-range first |
| Gospel John 1854 | 700–880 pairs | parallel-verse religious | Overlaps Bible — defer |
| Sanitary Instructions 1881 | 200–800 comparable pairs | comparable health | LaBSE needed |
| Diglot NT 1859 | blocked | — | hOCR tooling needed |
| **Realistic new total** | **1,000–3,000 confirmed pairs** | | |

Discovery artifact: `data/raw/ulukau-stage2-discovery/20260501/manifest.json`

---

# Decision proposal — Stage 2 raw-pull manifest coverage rule

**Proposer:** Frank (Hawaiian Data Collector)
**Date:** 2026-05-01
**Status:** PROPOSED — needs Linus + Coordinator review

## Context

Provenance audit of the three Stage 2 raw roots
(`hooilina-stage2/20260501`, `wehewehe-stage2/20260501`,
`hawaiian-kingdom-statutes-paired-imprints/20260501`) found:

- 100% local-path coverage and 0 failures across all three roots.
- One unmanifested orphan in `hooilina-stage2/20260501`:
  `classifier/all_classifier_nodes.json` — produced by the full
  classifier walk used to enumerate the 331 leaves. Useful, harmless,
  but invisible to a manifest-driven audit.
- One inventory-only row in wehewehe (`textchd`, Combined HD 2020)
  correctly omits `local_path`/`sha256` and carries
  `mode="inventory_only"`. Good shape — codify it.

## Proposal

Add the following rules to the Stage-2 source-adapter skill (and to
any future raw-pull script template):

1. **Every byte on disk under a Stage-2 raw root must be referenced
   by exactly one manifest row.**
   - Corpus bytes get a normal `kind` (`section`, `pdf`, `djvu_xml`,
     `landing`, etc.) with `local_path` + `sha256`.
   - Non-corpus aux files (classifier walks, robots.txt snapshots,
     enumeration dumps) get `kind="discovery_aux"` with `local_path`
     + `sha256` and a one-line `note`. They still count toward
     audit, but Linus skips them for candidate counting.

2. **Inventory-only rows must omit `local_path` and `sha256`** (no
   placeholder zeros), and must carry `mode="inventory_only"` plus a
   `rights_note`. Confirmed pattern in wehewehe.

3. **`manifest_summary.json` is the canonical count source**, not
   prose in agent histories or commit messages. Off-by-N drift was
   observed in this audit (history said 348/40; actual is 346/41).
   Linus should count from the JSONL or summary; agents should not
   re-state counts in prose without re-deriving them.

4. **Paired-source manifests must include the pair join key in the
   summary** (`paired_imprints` field on HK statutes is the reference
   shape).

## Scope

- Applies to: any new `data/raw/<source>-stage2/<date>/` pull.
- Does NOT require rewriting existing manifests; CLEANUP_NOTES.json
  sidecars are sufficient retroactive documentation. The hooilina
  classifier orphan can be left as-is (documented in CLEANUP_NOTES).

## Anti-scope

- This proposal is provenance-shape only. It does not touch
  rights/policy decisions, cleaning/normalization, or candidate
  emission.
- Does not require re-fetches.

## Asks

- **Linus:** Confirm this matches your structured-count expectations
  before I bake it into the next adapter.
- **Coordinator:** If accepted, promote into
  `.squad/skills/stage2-source-adapter/SKILL.md` under a new
  "Raw-pull manifest coverage" section.

---

# Frank — Wehewehe PD PDF Processing: Extraction Feasibility Report

**Author:** Frank (Hawaiian Data Collector)
**Date:** 2026-05-03
**Status:** FINDING — 0 rows emitted; forward path identified

---

## Context

Task: process the already-local Wehewehe PD raw pull (6 pre-1925 dictionaries in
`data/raw/wehewehe-stage2/20260501/pdfs/`) into Stage 2 candidate rows.

## Extraction Assessment

**Result: 0 structured candidate rows emittable from local PDFs.**

### Root Cause

All 6 PD PDFs are scanned image-only documents:
- Creator: `pdftk 1.41`, producer: `itext-paulo-155`, creation date 2009.
- PyMuPDF (fitz) returns **0 text characters** across all tested pages (EBOOK-VOCABULARY:
  139 pages, 0 chars; EBOOK-ANDREW: 559 pages, 0 chars fully scanned).
- These PDFs were created by scanning physical books and wrapping the images in PDF
  containers — there is no text layer.

### OCR Tooling Status

| Tool | Available |
|---|---|
| pdftotext | No |
| tesseract | No |
| pytesseract | No |
| PIL | Yes (but useless without tesseract) |
| fitz/PyMuPDF | Yes (confirmed image-only) |

No OCR tooling is installed. Installing tesseract is a non-trivial system dependency
(not in requirements.txt) and outside the scope of this task.

### Text Sidecars

`entries/`, `classifier/`, `meta/` subdirectories under the raw root are **empty**.
Sample entry HTML pages are search-result lists (headwords only, no definition text).
TOC landing pages are book-level catalog pages with no embedded entry content.

### Andrews 1865 Already Covered

`data/stage2/candidates/andrews_1865_vocab.jsonl` has **1,194 rows** built from the IA
djvu.txt source (IA item `cu31924026916167`, script `scripts/324_build_andrews_vocab_candidates.py`).
Processing the local PDF for this dict would only duplicate those rows. Skipped.

---

## Dict Cap Status

- Cap: ≤5,000 rows total across all wehewehe PD dicts
- Already consumed by Andrews 1865: 1,194 rows
- Remaining budget: **3,806 rows**

---

## Forward Path: IA djvu.txt for Remaining 5 Dicts

The Internet Archive hosts full-book djvu OCR for these same historical titles. The
pattern is already proven by `scripts/324_build_andrews_vocab_candidates.py` which
built 1,194 clean rows from Andrews 1865 IA djvu.txt.

**Priority order for IA djvu.txt fetch:**

1. **Hitchcock 1887 (EBOOK-ehd)** — English-Hawaiian direction; highest structural
   alignment value (EN headword → HAW gloss, same as Andrews 1865 vocab appendix).
2. **Andrews 1836 (EBOOK-VOCABULARY)** — shorter vocabulary list, probably simpler
   to parse than the full 1865 dictionary.
3. **Parker 1922 (EBOOK-PARKER)** — HAW-EN revised; large dict, useful.
4. **Emerson 1845 (EBOOK-emd)** — HAW-EN; shorter.
5. **Dict. of Biblical Words 1872 (EBOOK-CDD)** — lower priority; specialized
   biblical register; 376 MB PDF suggests high-DPI scan or multi-volume.

**Required steps:**
1. Identify IA item IDs for each of the 4 remaining dicts (archive.org title search).
2. Download `_djvu.txt` for each item via `internetarchive` lib (already in requirements.txt).
3. Write a precision-first 324-style builder script per dict (strict regex, Hawaiian OCR
   clean alphabet check, wordlist validation).
4. Emit candidate rows with `register="dictionary-example"`, `alignment_type="dictionary-example"`,
   `alignment_method="manual"` (headword→gloss is deterministic, not inferred).
5. Enforce combined cap: all wehewehe PD dicts ≤5,000 rows total.

---

## Proposal

> **Do NOT install OCR tooling just for this task.** The IA djvu.txt path is faster,
> lower-risk, and already proven. The local PDFs should remain as provenance/backup
> only — they prove we have the canonical source bytes.

> **Andrews 1836, Emerson 1845, CDD 1872, Hitchcock 1887, Parker 1922** need a targeted
> IA item-ID discovery pass before any adapter can be built. Recommend this as the
> next Frank subtask under "process ulukau-family sources".

---

## Files Created/Modified

- `data/raw/wehewehe-stage2/20260501/EXTRACTION_REPORT.json` — full per-PDF extraction
  probe results, tooling status, forward path (sidecar, raw originals untouched)
- `.squad/agents/frank/history.md` — Learnings appended
- This decision note

## Files NOT Created

- `data/stage2/candidates/wehewehe_pd_dictionary_examples.jsonl` — 0 rows to emit;
  file not created to avoid empty-file confusion in manifest builder

---

# HK Statutes 1897 — Processing Decision & Findings

**Agent:** Linus (Data Engineer)
**Date:** 2026-05-01
**Status:** Done — 1897 pair fully processed; 1869/1850 remains inventory-only.

---

## What was done

Processed the Hawaiian Kingdom Statutes 1897 bilingual pair from the already-local
`data/raw/hawaiian-kingdom-statutes-paired-imprints/20260501/` raw pull into
Stage-2 candidate rows.

**Script:** `scripts/325_build_hk_statutes_candidates.py`
**Output:** `data/stage2/candidates/hk_statutes_1897.jsonl` — 1,103 rows

---

## 1897 Pair (esrp641724381 EN × esrp641728581 HAW) — GO

### Approach
Section-level candidate extraction using deterministic section-ID pairing:
- EN chapter markers: `CHAPTER N.`  →  section markers: `^§N[,.]`
- HAW chapter markers: `MOKUNA N.`  →  section markers: `^[$S]N[,.]`
  (`$` and `S` are OCR artifacts for `§` in the HAW djvu.txt)

Section text extracted from each `§N` marker to the next marker, then cleaned
(hyphen-join, whitespace collapse, NFC + ʻokina canonicalization on HAW side).

### Counts
| Metric | Value |
|---|---|
| EN sections parsed | 1,292 |
| HAW sections parsed | 1,456 |
| Common (paired) sections | 1,103 |
| Rows emitted | 1,103 |
| Skipped (too short) | 0 |
| EN-only (unmatched) | 189 |
| HAW-only (unmatched) | 353 |
| Schema violations | 0 |

### Schema/policy
- `alignment_type = "parallel-sentence"` — section-level parallel (justified: official
  bilingual publication with matching section numbers)
- `alignment_method = "filename-pair"` — closest allowed enum value; section-ID
  pairing within paired files
- `alignment_review_required = True` — OCR noise present
- `prototype_only = True`, `release_eligible = False`
- `split = "review-pending"` (policy: OCR source requires review before train)
- `direction_original = "en->haw"` — HAW preface confirms *"Unuhiia mai ka Olelo
  Beritania mai."* (translated from English)
- License: `public-domain-US-pre1929` on both sides; sovereign-edicts doctrine applies

### Known OCR gaps
The HAW djvu.txt renders `§` as `8` in ~189 sections (e.g., `§7` → `87.`,
`§23` → `823.`). These are excluded conservatively because the `8N` pattern is
ambiguous with real section numbers. A future `§→8` normalization pass (with human
spot-check) could recover ~189 additional pairs.

---

## 1869/1850 Pair — INVENTORY-ONLY (no change)

Per decisions.md policy, HAW item `esrp468790723` has filename `1850.002_djvu.txt`,
indicating a year-mismatch with the EN 1869 penal code (`esrp475081650`).

No sections extracted. Status: inventory-only pending year-mismatch verification.

---

## Files created/modified

| File | Change |
|---|---|
| `scripts/325_build_hk_statutes_candidates.py` | NEW — section parser + row builder |
| `data/stage2/candidates/hk_statutes_1897.jsonl` | NEW — 1,103 candidate rows |
| `data/stage2/reports/hk_statutes_1897_report.json` | NEW — alignment report |
| `.squad/agents/linus/history.md` | Updated — added Learnings section |
| `.squad/decisions/inbox/linus-hk-statutes-processing.md` | NEW — this file |

---

## Durable decisions / proposals

1. **`alignment_method = "filename-pair"`** is used as the closest allowed enum value
   for section-ID-within-paired-files pairing. Propose adding `"section-id"` to the
   allowed alignment_method enum if future statute/legal sources follow the same pattern.

2. **`register = "unknown"`** is used for legal statute text. Propose adding `"legal"`
   to the register enum; it does not fit religious / encyclopedic / educational / news.

3. **OCR `§→8` recovery**: ~189 additional pairs are available if a human reviews the
   `87.`, `823.` etc. markers in the HAW djvu.txt. Recommend a targeted review pass
   after the current review-pending batch is assessed.

---

# Stage 2 Structured Counts — Inventory (2026-05-01)

**Owner:** Linus (Data Engineer)
**Date:** 2026-05-01
**Status:** INFORMATIONAL — counts and readiness assessment

## Summary

Full inventory of Stage 2 structured data as of the 2026-05-01 raw pull.

## Existing Prepared Stage 2

| Metric | Count |
|---|---|
| Canonical manifest rows | **11,828** |
| — train pairs | 4,665 |
| — review-pending | 7,148 |
| — dev | 15 |
| Directional SFT rows | **9,330** (4,665 en→haw + 4,665 haw→en) |
| Unique pair_ids | 11,828 |
| Unique dedup_cluster_ids | 11,828 |

**Candidates total on disk:** 32,822 rows across 6 files

| Candidate file | Rows | Merged? |
|---|---|---|
| `andrews_1865_vocab.jsonl` | 1,194 | ✅ in manifest |
| `bible.jsonl` | 5 | ✅ in manifest (smoke) |
| `bible_haw1868_kjv.jsonl` | 31,101 | ❌ not yet merged |
| `kaikki_wiktionary.jsonl` | 292 | ✅ in manifest |
| `tatoeba.jsonl` | 121 | ✅ in manifest |
| `hooilina.jsonl` | 109 | ❌ new this session |

## Newly Pulled Source Readiness

| Source | Raw Units | Structured Pairs | SFT Potential | Status |
|---|---|---|---|---|
| Hoʻoilina | 109 EN + 109 HAW_mod + 109 HAW_orig sections | 109 candidate pairs (emitted) | 218 directional rows (if accepted) | `candidate` |
| Wehewehe (PD subset) | 6 raw PDFs, 0 extracted entries | 0 | 0 | `raw-only` |
| Wehewehe (modern dicts) | 7 inventory landings, no PDFs | 0 | 0 | `inventory-only` |
| HK statutes 1897 Cornell | 2 djvu.txt, section markers confirmed | 0 (adapter needed) | est 400–1200 directional rows | `raw-structured` |
| HK statutes 1869 (EN) ↔ 1850 (HAW) | 2 djvu.txt | 0 | 0 | `inventory-only` (year-mismatch) |
| HK statutes 1846 + 1859 | 4 djvu.txt | 0 | TBD | `raw-structured` |
| Alpaca cleaned (synthetic) | 52,002 parquet rows | 0 | capped (synthetic pool, not human-parallel) | `raw-only` |
| haw1868 Bible USFM | 66 USFM files | 31,101 (pre-existing candidates) | 62,202 directional (if merged) | `candidate` |

## Key Gaps / Next Steps

1. **bible_haw1868_kjv** (31,101 rows) — ready to merge; run `320_build_stage2_manifest.py --execute`
2. **Hoʻoilina** (109 rows) — emitted; needs section-level review before manifest merge; `alignment_review_required=True`
3. **HK statutes 1897** — adapter needed to parse djvu.txt into section-level pairs; section markers confirmed present
4. **Wehewehe** — no OCR pipeline; Andrews 1865 already covered; other PD dicts need IA djvu.txt items to be useful
5. **1869 year-mismatch** — resolve before pairing; 1897 Cornell pair is the safe starting point

## Effective Directional SFT Capacity

| Pool | Rows in SFT | Direction |
|---|---|---|
| Current SFT (merged train) | 9,330 | 4,665 × 2 |
| If haw1868 merged | +62,202 | 31,101 × 2 |
| If Hoʻoilina accepted | +218 | 109 × 2 |
| **Potential total** | **~71,750** | pending review |

Human-parallel only (excluding synthetic Alpaca pool).

---

# Data Policy Proposal: Ulukau SFT Source Acceptance Rubric
**Author:** Linus (Data Engineer)
**Date:** 2026-05-03
**Status:** PROPOSAL — for team awareness

---

## Summary

Independent vetting of Ulukau-family Stage 2/SFT source classes. Defines a ranked acceptance rubric, row-yield estimates, source gates, and recommended next actions for reaching the 80k directional SFT row target.

Full analysis: `data/stage2/reports/ulukau_sft_vetting_20260503.md`

---

## Policy Decisions

### 1. Source Class Dispositions (Ulukau-family)

| Source Class | Status | Rationale |
|---|---|---|
| Verse-aligned parallel Bible (haw1868) | **GO** | Unblocked; merge immediately; enforce Bible ≤30% cap |
| Ka Hoʻoilina trilingual layers | **PROVISIONAL** | KS © editorial; `prototype_only=True`; `release_eligible=False`; citation required |
| HK statutes 1897 Cornell pair | **GO (adapter needed)** | PD; djvu.txt on disk; legal ≤15% token cap |
| HK statutes 1869/1850 pair | **PROVISIONAL** | Year-mismatch unresolved; inventory-only until verified |
| Wikimedia CX published | **GO (adapter needed)** | CC BY-SA; `stats.mt < 0.5` filter required |
| Wehewehe PD subset (Andrews 1836, Emerson, Hitchcock, Parker) | **RAW-ONLY** | PDFs on disk; OCR pipeline needed; combined dict cap ≤5k (1,194 consumed) |
| puke.ulukau.org bilingual books (EBOOK-DHLLT etc.) | **INVENTORY-ONLY** | Per-book rights audit required before adapter |
| Nupepa / monolingual HAW books/newspapers | **RAW-ONLY** | Stage 1 only; never Stage 2 primary |
| Modern copyrighted dicts (PE 1986, Māmaka Kaiao 2003, Combined 2020, Kent 1986) | **BLOCKED** | In-copyright; no license grant; do not pull |

### 2. Execution Priority Gate

Before any new Ulukau discovery is acted on, the following adapter backlog must be worked down:
1. Merge haw1868 with Bible cap enforcement (highest yield, no new code needed)
2. Wikimedia-cx adapter (CC BY-SA, cleanest quality/effort ratio)
3. HK statutes 1897 section-level adapter (djvu.txt on disk, rights clear)
4. Hooilina alignment review → manifest merge
5. Only then: expand Hoʻoilina full pull, puke.ulukau.org inventory, HK 1869 year-mismatch resolution

### 3. Realistic Gap to 80k Target

After executing P1–P4 above:
- Projected SFT total: ~55,000–57,000 directional rows
- Remaining gap: ~23,000–25,000 directional rows
- **NLLB mined pull is required to bridge this gap.** Non-Bible, non-synthetic human-parallel sources alone cannot reach 80k.

### 4. Adapter-First Principle Confirmed

**Do not search for new Ulukau sources before building adapters for sources already on disk.** Discovery is free; adapter implementation is the bottleneck. Exception: low-cost metadata sweeps of puke.ulukau.org bilingual-tagged book IDs can proceed in parallel.

---

## Caps Restated (existing policy, no changes)

- Bible: ≤30% parallel-train tokens
- Dictionary examples: ≤5k rows combined across all dict sources
- Synthetic (BT + FT): ≤15% directional rows, never dev/test
- Legal register: ≤15% parallel-train tokens
- Mined/NLLB: LaBSE ≥0.75; never dev/test
- Hoʻoilina: `prototype_only=True`, `release_eligible=False`

---

## Cross-Team Notes

- **Frank:** Build wikimedia-cx adapter and HK statutes 1897 adapter before next Ulukau discovery pass. Low-cost: inventory puke.ulukau.org EBOOK-* items tagged both `Pelekānia` + `Hawaiʻi` while adapters are being built.
- **Rusty:** Alignment review needed on hooilina.jsonl (109 rows) before manifest merge. Register tag `"educational"` for Hoʻoilina Lahaina Luna source stream.
- **Linus (self):** Confirm Bible cap enforcement logic in `320_build_stage2_manifest.py` before haw1868 merge — this is the most important immediate gate.

> Updated 2026-05-01T21:28:28Z: Merged Linus raw-pull rights gate + Frank Stage 2 raw acquisition for sources 1, 2, 3. Outcome: Linus issued go/no-go matrix + metadata schema for Ka Hoʻoilina (provisional prototype-only, KS citation required, release_eligible=False), Wehewehe PD (≤5k rows combined, pre-1925 imprints only, modern dicts blocked), HK statutes (1897 pair cleared, 1850/1869 deferred pending year-mismatch verification, Judd/Pukui/Stokes 1943 inventory-only pending US renewal check). Frank completed raw acquisition: Hoʻoilina 4.6 MB (331 leaf sections), Wehewehe 924 MB (6 PD PDFs + inventory landings), HK statutes 231 MB (8 IA item sets, djvu.txt re-registered). Total 1.16 GB, 0 failures. All gitignored, manifests + ToS captured, ready for adapter implementation after gate confirmations. User directive (raw-first acquisition) fulfilled. Full details in decisions below.
>
> Updated 2026-05-01T20:34:18Z: Merged Linus Stage 2 source filter + Frank Ulukau Stage 2 pivot. Outcome: Linus designed Stage 2 acceptance filter (bilingual alignment, rights gates, register taxonomy, 5 hard caps: Bible ≤30% token, dict ≤5k, synthetic ≤15%, mined never dev/test). Ranked 8 discovery targets across Tier A (search now) and Tier B (search next); recommended pilot `wikimedia-cx-en-haw-published` (CC BY-SA, 1–3k pairs, unblocks doc-level LaBSE). Frank confirmed Nupepa is Stage 1-only (monolingual Hawaiian OCR); ranked Ulukau-family candidates: Ka Hoʻoilina (★★★★★, 80% Veridian surface reuse, highest parallel-pair density), Wehewehe dictionary (★★★★, PD pre-1925 subset), HK statutes (★★★★, already in plan), Nā Puke (★★, defer), Baibala (in plan). Recommended adapter-pilot: Ka Hoʻoilina with 3 pre-pilot gates (Linus: citation OK for prototype-only? modernized-HAW primary? smoke test + ToS snapshot?). User directive (2026-05-01T13:28:17-07:00) captured: Stage 2 should focus on bilingual/parallel data, not monolingual newspaper OCR. Dependencies staged: Linus rights review (P1, Hoʻoilina + Wehewehe PD cutoff), Rusty register-fit review (Hoʻoilina spelling layer). Full reports in `.squad/decisions/inbox/linus-stage2-source-filter.md` and `.squad/decisions/inbox/frank-stage2-ulukau-focus.md`.
>
> Updated 2026-05-01T09:06:22Z: Merged Frank hub dataset row counts + corrections. Outcome: Confirmed monolingual counts (FineWeb-2 haw_Latn 96,394 docs; Glot500 haw_Latn 1,053,668; GlotCC-V1 haw-Latn 7,058; mC4 haw 84,398) and parallel counts (OPUS translatewiki 2,219 pairs, wikimedia 374, QED 167, Tatoeba 93; BibleNLP mmteb eng-haw 1,955). Three corrections: (1) mC4 present, move from "absent" to "deprioritized" (overlap with FineWeb-2); (2) HPLT v2 cleaned lacks haw_Latn config, drop from candidate-add; (3) OPUS bible-uedin haw nonexistent. Updated Stage 1 candidate-add for Linus: MADLAD-400, Glot500, GlotCC-V1. Stage 2 execution order unchanged. Full report in `.squad/decisions/inbox/frank-hub-dataset-row-counts.md`.
>
> Updated 2026-05-01T08:52:06Z: Merged Frank ready-made Hawaiian dataset sweep. Outcome: Stage 2 hub sources well covered (Tatoeba, OPUS, NLLB, BibleNLP, Global-PIQA, Taxi1500 in plan; FLORES+/Belebele/WMT24++ verified absent). Stage 1 hub sources not previously surveyed; confirmed present: MADLAD-400 (~109k tokens), Glot500-c, GlotCC-v1, HPLT v2 cleaned (all haw_Latn); confirmed absent: CC100, mC4, WikiMatrix, NTREX-128, likely CulturaX. Recommend Stage 2 execution order: NLLB mined (largest yield) → BibleNLP haw1868 (31k verses) → OPUS bible-uedin (dedup cross-check). Stage 1 three probes (MADLAD-400, Glot500-c, HPLT v2) require Linus rights sign-off before adapter implementation. Full report in `.squad/decisions/inbox/frank-ready-dataset-sweep.md`. **[SUPERSEDED by 2026-05-01T09:06:22Z correction above.]**
>
> Updated 2026-05-01T08:30:25Z: Merged Frank Pentateuch raw fetch. Outcome: Exodus–Deuteronomy HAW 137 chapters (~1.95 MB) fetched via Baibala Hemolele 1839 pin; provenance appended (137 rows in fetch.jsonl); cumulative 187 HAW chapters on disk (Genesis 50 + Pentateuch tail 137); candidate emission deferred pending Linus confirmations on USFM cleanup stability (EXO/LEV/NUM/DEU) and `322` book-bounded build support; next raw batch planned (JOS/JDG/RUT, 49 chapters, ~75 s polite).
>
> Updated 2026-05-02T08:23:02Z: Merged Frank Bible raw fetch + Linus parser fix + Genesis emission. Outcome: HAW Genesis 50 chapters (840 KB) + ENG KJV/ASV USFM zips (5.1 MB) fetched; Strong's number leakage identified in dry-run (1,533 rows); three-pass cleanup fix shipped in `206b_parse_eng_usfm.py`; 1,533 clean Genesis rows written; manifest dry-run 3,140 total rows, 0 violations; KJV pinned as ENG anchor; full HAW corpus (65 books) + OPUS adapter deferred.
>
> Updated 2026-05-01T00:23:47Z: Merged Stage 2 80k source plan finalization (Frank + Linus). Outcome: User directive captured (80k directional SFT rows); Frank's 4-source discovery accepted with gates; Linus reviewed + cleared all 4 sources; 11-bucket acquisition roadmap ranked; honest yield math confirmed (~28–35k pairs from human-parallel alone; NLLB mined + synthetic BT required to reach 80k); guardrails enforced (NLLB ≥0.80 LaBSE, BT ≤15% cap, never dev/test); HK statutes promoted to all-four-pairs; all scripts/tests/docs updated; team ready for adapter implementation.
>
> Updated 2026-05-01T00:59:31Z: Merged Linus Baibala Hemolele 1839 edition pin. Outcome: Edition confirmed on baibala.org with correct Greenstone URL pattern and verse anchor format; all 66 books mapped with `greenstone_oid` and `book_name_lower`; sample HTML + ToS captured; working tree ready for Frank parser implementation.
>
> Updated 2026-04-30T21:36:58Z: Merged Basher Kaggle venv robustness + docs idempotency and Copilot W1 eval skip directive. Outcome: `scripts/setup_training.py` now probes venv pip health and auto-recreates broken envs; `docs/kaggle-t4x2-setup.md` uses absolute cd paths; W1 provisional micro-eval skipped per directive.
>
> Updated 2026-04-30T10:06:39Z: Merged Basher QLoRA bitsandbytes compute dtype fix. Outcome: `_bnb_4bit_config()` now correctly derives compute dtype from TrainConfig `bf16`/`fp16` flags. Kaggle T4x2 config (fp16=true, bf16=false) now uses torch.float16 instead of unsupported torch.bfloat16.


---

## Directive: User — Raw-first acquisition for Stage 2 sources 1, 2, 3 (2026-05-01T14:02:02-07:00)

**By:** yashasg (via Copilot)  
**What:** Pull raw data for ranked Stage 2 sources 1, 2, and 3 first, preserving everything locally with provenance, then decide later what subset to use.  
**Why:** User request — captured for team memory

---

## Decision: Linus — Stage 2 raw-pull rights gate review (2026-05-01T21:28:28Z)

**Owner:** Linus (Data Engineer)  
**Date:** 2026-05-01  
**Status:** PROPOSAL — engineering go/no-go matrix for team  

### Context

Frank is pulling raw data for the top three Stage 2 sources (Ka Hoʻoilina, Wehewehe, Hawaiian Kingdom statutes bilingual). This document defines:
- Whether full local raw preservation is acceptable for each source
- Whether Stage 2 training use is allowed, provisional, or blocked
- Required metadata tags for raw manifests and candidate rows
- Caps and priority for later conversion
- Any sources that must remain inventory-only until explicit review

This is an engineering rights/provenance gate for prototype use only. It is NOT a legal opinion.

### Go/No-Go Matrix

| Source | Local Raw Pull | Stage 2 Training Use | Notes |
|---|---|---|---|
| **Ka Hoʻoilina** — KS editorial layers (modernized HAW + EN translation) | **GO** (prototype-only) | **PROVISIONAL** — prototype_only=True, release_eligible=False | "Free to public with citation" clause; NOT an explicit ML-training grant. Cite source HAW alongside reuse. Do NOT release weights without KS sign-off. |
| **Ka Hoʻoilina** — underlying 19c source documents (original HAW) | **GO** | **GO** | PD by age. Use as dedup signal / Stage 1 only; do not emit as Stage 2 primary train pair. |
| **Wehewehe** — PD subset (Andrews 1836/1865, Emerson 1845, Hitchcock 1887, Parker 1922, Dict. of Biblical Words 1872) | **GO** | **GO with cap** | Pre-1925 US imprints; unencumbered. dictionary-example tier; ≤5k rows combined. No dev/test. |
| **Wehewehe** — Judd/Pukui/Stokes 1943 | **INVENTORY-ONLY** | **BLOCKED pending review** | 1943 US publication; copyright renewal status not confirmed. If not renewed by 1970–71 (pre-1964 rule), it may be PD — but do not train until verified. |
| **Wehewehe** — modern copyrighted dicts (Pukui-Elbert 1986, Māmaka Kaiao 2003, Combined 2020, Kent 1986, Place Names 1974/2002, Legal Land-Terms 1995) | **NO** | **BLOCKED** | In-copyright works; no license grants training use. Do not pull beyond what is already in a smoke probe. |
| **HK Statutes Bilingual** — all four code pairs (1846, 1850/1859, 1869, 1897) | **GO** | **GO with cap + year-pair gate** | PD: pre-1925 US imprints + sovereign-edicts doctrine. IA ToS governs bytes only. Legal register cap ≤15% of parallel-train tokens combined. Year-mismatch on 1850 HAW ↔ 1869 EN must be verified before pairing (see below). |

### Required Metadata Tags

All raw manifests and candidate rows for these sources must carry 13 fields including: `source`, `layer`, `rights_note`, `prototype_only`, `release_eligible`, `synthetic`, `alignment_type`, `alignment_method`, `split`, `train_eligible`, `dev_eligible`, `register`, `kahako_recoverable`, `license_observed_*`.

### Year-Mismatch Flag: HK Statutes Pair #2

**Concern:** esrp468790723 filename contains `1850.002` (Hawaiian Penal Code, 1850 promulgation). esrp475081650 filename contains `1869.001`. The fetch plan pairs these as the "1869 Penal Code EN ↔ HAW" pair.

**Problem:** If esrp475081650 is the 1869 English revision and esrp468790723 is the original 1850 Hawaiian text, these are editions from different legislative sessions. Section-id pairing will produce false alignments for any sections added in 1869 that do not appear in the 1850 Hawaiian version.

**Required action before pairing:**
1. Verify whether the 1869 EN item is a full reprint of the 1850 law with amendments, or a new code.
2. If a full reprint with 1850 laws included: section-id pairing is safe within the shared section range; flag the 1869-additions as unpaired.
3. If a separate 1869 code: locate the correct 1850 English companion item on IA (if it exists) and re-pin the pair.

**Until resolved:** Treat esrp468790723 + esrp475081650 as inventory-only for pairing. The 1897 pair (esrp641724381 ↔ esrp641728581, both Cornell, cleanest OCR) is fully cleared.

### Recommendations to Team

1. **Ka Hoʻoilina pilot adapter** can proceed with `prototype_only=True` and explicit citation-compliance logging. Frank should smoke-fetch one document trio and capture the edintro page as `tos_snapshot.txt`. Linus will flag as **PROVISIONAL** in the manifest. Do NOT release model weights trained on KS editorial layer without a follow-up rights review.

2. **Wehewehe adapter** should filter by dictionary at extraction time. Build a per-dictionary whitelist into the fetch script; blocked dicts must never reach a candidate row. Andrews 1865 is already covered by `andrews-1865-en-haw-vocab-appendix` adapter — extend that adapter to cover Andrews 1836, Emerson 1845, Hitchcock 1887, Parker 1922 via Wehewehe, OR pull their IA djvu.txt items directly (likely cleaner).

3. **HK Statutes**: Start with the 1897 Cornell pair (esrp641724381 ↔ esrp641728581) — cleanest OCR, clearest year-match. Defer the 1850/1869 pair until the year-mismatch is resolved. The djvu.txt files are already on disk — Frank can proceed to section-level parsing for the 1897 pair immediately.

4. **Do not use Google-scan items** (`*goog`) as the primary extraction target if Cornell items exist for the same text. These are on disk as backups. The 1859 pair will need OCR quality evaluation before section-id alignment.

---

## Decision: Frank — Stage 2 raw acquisition for sources 1, 2, 3 (2026-05-01T21:28:28Z)

**Owner:** Frank (Hawaiian Data Collector)  
**Triggered by:** User directive 2026-05-01T14:02:02-07:00 — "pull 1,2,3 raw data, better to get everything and then decide what we need."  
**Status:** RAW ACQUISITION COMPLETE — local-only, gitignored. No normalization, no candidate emission.

### Summary

Pulled raw bytes for the three top-ranked Stage 2 sources from the prior Ulukau-focus discovery, preserved everything on disk with provenance, and deliberately deferred all subset-selection / cleaning / candidate-row work.

### Source 1 — Ka Hoʻoilina (hooilina.org)

- **Local root:** `data/raw/hooilina-stage2/20260501/`
- **Mode:** full pull (raw HTML)
- **Counts:** 7 ToS/edintro/about pages; 8 parent doc landings (4 root issues × 2 e-state variants); **331 leaf section HTML bodies = 109 original-HAW + 109 modernized-HAW + 109 English + 4 trailing textual-notes (.9 suffix)**; 0 failures.
- **Total bytes on disk:** ~4.6 MB.
- **Discovery confirmed:** the `?a=cl&cl=CL2.<n>.<m>` classifier walk enumerates all 331 leaf sections; suffix mapping is **`.3` = original HAW, `.5` = modernized HAW, `.7` = English translation** uniformly across all 4 issues.
- **Root issue OIDs (4 issues, vols. 1–4 of Ka Hoʻoilina, 2002–2004):** `HASH0166acfd8ec6df2fa38fd161`, `HASH01b8b242efc454f373219e6b`, `HASH01ce5dd8c7981a7202fe0ffb`, `HASHe7d7c93d84511b86ea5ca7`.
- **ToS captured (canonical):** `tos/edintro.html` — Kalena Silva 2002 editor's intro carries the per-layer copyright statement (editorial layers © 2002-2004 Kamehameha Schools; underlying 19c HAW source PD by age) and the reuse clause requiring source-HAW citation alongside any modernized-HAW or English reuse.
- **Rights status:** `permission_with_attribution_required`. Editorial-layer copyright held by Kamehameha Schools; underlying source HAW is PD-by-age.
- **Manifest:** `manifest.jsonl` (348 rows) + `manifest_summary.json`.

### Source 2 — Wehewehe (wehewehe.org) — PD subset

- **Local root:** `data/raw/wehewehe-stage2/20260501/`
- **Mode:** PD subset = full PDF pull; modern dictionaries = inventory only.
- **PD PDFs pulled (6 dictionaries, total 849 MB):**
  | EBOOK OID | Title | Year | Bytes |
  |---|---|---|---|
  | EBOOK-VOCABULARY | Andrews, "A vocabulary of words..." | 1836 | 37,975,843 |
  | EBOOK-emd | "He hoakakaolelo no na huaolelo Beritania" (Emerson 1845 attribution) | 1845 | 24,007,196 |
  | EBOOK-ANDREW | Andrews, "A dictionary of the Hawaiian language" | 1865 | 61,555,145 |
  | EBOOK-CDD | "He buke wehiwehi huaolelo Baibala" / Dictionary of Biblical Words | 1872 | 393,873,697 |
  | EBOOK-ehd | Hitchcock, "An English-Hawaiian dictionary" | 1887 | 283,462,763 |
  | EBOOK-PARKER | Parker (rev.), "A dictionary of the Hawaiian language" | 1922 | 147,924,455 |
- **Inventory-only landings (no PDF pull):** Pukui-Elbert 1986 (PED), Māmaka Kaiao 2003 (MKD), Judd/Pukui/Stokes 1943 (IHL — pending renewal-status review), Kent 1986 (THW01), Place Names 1974 (PEPN), Hawaiʻi Place Names 2002 (CPN), Hawaiian Legal Land-Terms 1995 (DHLLT). Combined Hawaiian Dictionary 2020 (textchd) is an aggregator — recorded as inventory-only.
- **ToS captured:** `tos/ulukau_copyright.html`, `tos/ulukau_about.html`, `tos/ulukau_privacy.html`, `tos/hdict_about.html`, `tos/hdict_help_en.html`, `tos/wehewehe_root.html`, `tos/puke_root_haw.html`, `tos/hdict_home_haw.html`, `tos/robots.txt`.
- **Smoke samples:** 12 query-result HTML pages at `sample_entries/` for headwords {aloha, wai, akua, iho, mauna, keiki} × {l=haw, l=en}.
- **Rights status:** `public_domain` for the 6 PD PDFs (US copyright term, pre-1929); `inventory_only` for everything else. Linus rights sign-off still required before any modern dictionary moves beyond inventory.
- **Manifest:** `manifest.jsonl` (40 rows) + `manifest_summary.json`.

### Source 3 — HK statutes paired imprints (1846 / 1859 / 1869 / 1897)

- **Local root:** `data/raw/hawaiian-kingdom-statutes-paired-imprints/20260501/` (augments the prior 8 `*_djvu.txt` OCR files already on disk).
- **Mode:** full pull of all useful IA derivatives for all 8 paired-imprint items.
- **Counts:**
  - 8 IA metadata JSONs (`<item>__ia_metadata.json`) — full IA file inventory + license / sponsor / publication metadata.
  - 8 PDFs total (5 "Text PDF" derivatives via the standard fetcher pass; 3 "Image Container PDF" originals for the Google-Books-sourced items pulled in a follow-up pass).
  - 8 `_djvu.xml` page-bbox OCR XMLs (range 2.4 MB – 19.8 MB; total ~89 MB) — page-coordinate-level OCR retained for future verse/section bounding-box alignment work.
  - 6 `_hocr_searchtext.txt.gz` searchable-OCR derivatives.
  - 8 `_meta.xml` and 6 `_marc.xml` IA bibliographic records.
  - 8 preexisting `*_djvu.txt` OCR text files re-registered with sha256 in the new manifest.
  - 0 failures.
- **Total bytes on disk for this dir:** ~231 MB.
- **ToS captured:** `_tos/ia_terms.html` (Internet Archive ToS).
- **Rights status:** `public_domain` (1846–1897 Hawaiian Kingdom government works; pre-1929; sovereign-edicts doctrine). IA ToS governs the redistributed bytes only.
- **Manifest:** `manifest_complete.jsonl` + `manifest_summary.json`.

### Scope Limits (deliberate)

- Did not normalize / clean any text. No Stage 2 candidate rows emitted. No tokenization, dedup, alignment, or NFC normalization.
- Did not commit anything under `data/`. Tree remains gitignored per the project ADR.
- Did not modify any existing fetcher script — added two one-off pullers under `scripts/_frank_pull_*.py` only.
- Did not enumerate D-id ranges per dictionary in Wehewehe — the full PDF pull subsumes the per-entry need for the PD subset.
- Did not pull JP2 page images or audio MP3s from any source (size; not required for text Stage 2).
- Did not capture any cookies, localStorage, auth headers, or session tokens. All fetches via stdlib `urllib.request` with a public, identifiable User-Agent.

### Open Asks

- **Linus (rights):** (a) Sign-off on Hoʻoilina editorial-layer reuse posture for prototype-only training. (b) Renewal-status check on Judd/Pukui/Stokes 1943 (Wehewehe). (c) Confirm whether any of the modern Wehewehe dictionaries warrant inventory promotion.
- **Rusty (register):** Hoʻoilina spelling-layer fit — confirm modernized-HAW (`.5` suffix) is the right primary for Stage 2 train pairs.
- **Self (Frank) next:** Build Hoʻoilina adapter walking parent-doc TOC and pairing `.5` ↔ `.7` per section; text-extraction pass for 6 Wehewehe PDFs; align HK statutes per-section/article between en/haw djvu_xml siblings.

### Provenance footprint

- 3 raw roots, all under `data/raw/`, all gitignored.
- 3 machine-readable manifests (`manifest.jsonl` × 2, `manifest_complete.jsonl`) + 3 `manifest_summary.json` rights-and-counts files.
- ~1.16 GB local raw (Wehewehe 924 MB + HK 231 MB + Hoʻoilina 4.6 MB).
- 0 failures across all three pulls.

---


## User Directive: Stage 2 target raised to 80k directional SFT rows (2026-05-01T07:09:23Z)

**By:** yashasg (via Copilot)  
**What:** Stage 2 target raised from 40k to 80k directional SFT rows.  
**Why:** User request — captured for team memory.  
**Status:** IMPLEMENTED — all downstream tasks aligned.

---

## Decision: Frank — Hub dataset row counts + corrections (2026-05-01T09:06:22Z)

**Owner:** Frank (Hawaiian Data Collector)  
**Date:** 2026-05-01  
**Status:** RESEARCH / CORRECTIONS — three prior findings contradicted

### Summary

Queried HF datasets-server `/size` and OPUS API (2026-05-03). Confirmed counts for monolingual and parallel Hawaiian sources. **Three findings contradict prior decisions.md entries:**

1. **mC4 (`allenai/c4` config `haw`) is present**, ~84,398 documents. Prior decision said "Do not add CulturaX / CC100 / mC4 / WikiMatrix / NTREX-128 — verify-and-record-absent." Correct: move from "absent" to "present, deprioritized" (CommonCrawl overlap with FineWeb-2 already harvests most).

2. **HPLT v2 cleaned does NOT have `haw_Latn` config.** Earlier history listed HPLT v2 cleaned among Stage-1 candidate-add sources. Verified: configs starting with "h" are hat_Latn, hau_Latn, heb_Hebr, hin_Deva, hne_Deva, hrv_Latn, hun_Latn, hye_Armn — no haw_Latn. **Drop from candidate-add list.**

3. **OPUS bible-uedin haw subcorpus does not exist.** Earlier history's "Top-3 ranked" mentioned "OPUS bible-uedin haw subcorpus (~31k pairs)". OPUS API returns only 5 corpora touching haw: translatewiki, wikimedia, QED, Tatoeba, Ubuntu. Bible-uedin not in that set. **Removes triple-counting concern.**

### Confirmed counts

**Monolingual (HF datasets-server `/size`, parquet):**

| Source | Config | Rows | Bytes | License |
|---|---|---:|---:|---|
| HuggingFaceFW/fineweb-2 | haw_Latn | 96,394 | 128.7 MB | ODC-By 1.0 |
| cis-lmu/Glot500 | haw_Latn | 1,053,668 | 137.8 MB | mixed |
| cis-lmu/GlotCC-V1 | haw-Latn | 7,058 | 20.2 MB | CC0 |
| allenai/c4 (mC4) | haw | 84,398 | 131.4 MB | ODC-By |

**Parallel / eval (OPUS API, sentence pairs):**

| Source | Pair | Rows | License |
|---|---|---:|---|
| OPUS translatewiki | en-haw v2025-01-01 | 2,219 | CC0 |
| OPUS wikimedia | en-haw v20230407 | 374 | CC BY-SA |
| OPUS QED | en-haw v2.0a | 167 | CC BY-NC-ND |
| OPUS Tatoeba | en-haw v2023-04-12 | 93 | CC BY 2.0 FR |
| davidstap/biblenlp-corpus-mmteb | eng-haw | 1,955 | per BibleNLP |

**Unconfirmed / not exposed:**
MADLAD-400 haw, OSCAR-2301 (gated), CulturaX (gated), bible-nlp/biblenlp-corpus full, allenai/nllb mined haw-eng, facebook/flores, FLORES+ haw_Latn (eval-only approx 997 dev + 1012 devtest).

**Confirmed absent:**
HPLT/HPLT2.0_cleaned haw_Latn, statmt/cc100, Helsinki-NLP/opus-100, Helsinki-NLP/tatoeba_mt haw config, mteb/NTREX, facebook/wikimatrix, OPUS ubuntu en-haw (empty), OPUS bible-uedin haw.

### Updated Stage 1 candidate-add list (for Linus rights review)

**Rank-ordered by confidence + dedup value:**

1. **MADLAD-400 haw** — CC-BY-4.0; ~109k tokens; second-source signal.
2. **Glot500 haw_Latn** — mixed licenses (component-wise); aggregate over 1M docs; high overlap risk, but independent dedup hashes.
3. **GlotCC-V1 haw-Latn** — CC0; ~7k docs; small clean second-source signal.

~~mC4 haw~~ **deprioritized** (CommonCrawl/FineWeb-2 overlap).  
~~HPLT v2 cleaned haw_Latn~~ **removed** (config absent).

### Stage 2 execution order unchanged

NLLB mined haw-eng (largest yield) → BibleNLP haw1868 (31k verses) → OPUS cross-check (no bible-uedin).

### Decisions locked

1. mC4 present; record as "deprioritized (CommonCrawl overlap)."
2. HPLT v2 cleaned removed from Stage 1 candidate-add.
3. OPUS bible-uedin haw nonexistent; removes triple-counting risk.
4. Linus proceed with rights review for MADLAD-400, Glot500, GlotCC-V1 only.

---

## Decision: Frank — Ready-made Hawaiian dataset sweep (2026-05-01T08:52:06Z)

**[SUPERSEDED by 2026-05-01T09:06:22Z correction above.]**

**Owner:** Frank (Hawaiian Data Collector)  
**Date:** 2026-05-01  
**Status:** RESEARCH / INVENTORY — no code or data fetched

### Question

Did we look for ready-made public datasets that already package Hawaiian (`haw`) text or parallel pairs, the way FineWeb-2 packages haw_Latn for Stage 1?

### What we already had

Already enumerated in plan / on disk:

| Source | Hub | Stage | Status |
|---|---|---|---|
| FineWeb-2 `haw_Latn` | HF `HuggingFaceFW/fineweb-2` | Stage 1 mono | Pinned & fetched. 95,507 train + 887 test. |
| Hawaiian Wikipedia dump | dumps.wikimedia.org | Stage 1 mono | In plan, P0. |
| Hawaiian Wikisource dump | dumps.wikimedia.org | Stage 1 mono | In plan. |
| Tatoeba haw-eng | downloads.tatoeba.org + OPUS | Stage 2 parallel | In plan; 121 candidates on disk. |
| OPUS subsets | opus.nlpl.eu | Stage 2 parallel | In plan; endpoint-verification pending. |
| NLLB mined haw-eng | HF `allenai/nllb` | Stage 2 parallel (mined) | In plan; not fetched. |
| BibleNLP `haw1868` | HF `bible-nlp/biblenlp-corpus` | Stage 2 parallel (verse) | In plan; not fetched. |
| Global-PIQA parallel haw_Latn | HF `mrlbenchmarks/global-piqa-parallel` | Eval-only | In plan. |
| Taxi1500 haw_Latn | github.com/cisnlp/Taxi1500 | Eval-only diagnostic | In plan. |
| FLORES+ haw_Latn | HF `openlanguagedata/flores_plus` | Eval | Probed 2026-05-02 — **NOT present**. |
| Belebele haw | HF `facebook/belebele` | Eval | Probed 2026-05-02 — **NOT present**. |
| WMT24++ haw | HF `google/wmt24pp` | Eval | Probed 2026-05-02 — **NOT present**. |

Stage-2 hub-packaged sources well covered. Stage-1 hub-packaged sources **beyond FineWeb-2 not previously surveyed.**

### What we found (Stage 1 gap survey)

Searched 2026-05-04. Stage 1 hub-packaged monolingual sources:

| Dataset | Hub | Has `haw_Latn`? | Recommendation |
|---|---|---|---|
| **MADLAD-400** | HF `allenai/MADLAD-400` | **Yes** (~109k tokens) | **Probe + dedup vs FineWeb-2.** Second-source signal on cleaning gates. |
| **Glot500-c / GlotCC-v1** | HF `cis-lmu/Glot500`, `cis-lmu/GlotCC-V1` | **Yes** (≥30k threshold) | **Probe + dedup vs FineWeb-2.** Same role as MADLAD. |
| **HPLT v2 cleaned** | data.hplt-project.org + HF | **Yes** (explicit haw_Latn) | **Probe.** Cleanest licensing posture. |
| **OSCAR-2301** | HF `oscar-corpus/OSCAR-2301` | Likely yes | **Skip.** Heavy overlap with FineWeb-2. |
| **CulturaX** | HF `uonlp/CulturaX` | **Likely no** (167 langs only) | **Skip.** Verify-absent and record. |
| **CC100** | statmt.org | **No** (100 langs, haw not in list) | **Skip / verify-absent.** |
| **mC4** | HF `allenai/c4` | **No** (101 langs, haw not in list) | **Skip / verify-absent.** |
| **WikiMatrix** | HF `facebook/wikimatrix` | **No** (85 langs, haw not in list) | **Skip / verify-absent.** |
| **NTREX-128** | github.com/MicrosoftTranslator/NTREX | **No** (128 langs, haw not in list) | **Skip / verify-absent.** Record alongside FLORES+/Belebele. |
| **xP3 / Aya** | HF `bigscience/xP3*`, CohereForAI | Not surveyed | **Probe-and-record-absent.** Low expected yield. |

### Top-3 ready-made adds ranked

For **Stage 2 row count**, no new external dataset found moves needle materially beyond what is already planned. Honest top-3 is "execute what we already planned":

1. **NLLB mined haw-eng (`allenai/nllb`)** — in plan, not fetched. Largest expected yield. Mined → ≤synthetic/mined budget, never dev/test, never released.
2. **BibleNLP `haw1868`** — in plan, not fetched. Verse-aligned Baibala vs eBible. ~31k verses, complies with ≤30% bible-token-share cap.
3. **OPUS bible-uedin haw** — ~31k verses; however same Baibala source as direct fetch + BibleNLP above. Treat as **cross-check/dedup signal**, not additive.

**Stage 1 adds** (separate from 80k Stage-2 target):

- **MADLAD-400 `haw_Latn`**, **Glot500-c `haw_Latn`**, **HPLT v2 cleaned `haw_Latn`** worth single fetch each, deduped vs FineWeb-2. Net gain small (FineWeb-2 already harvests most public Hawaiian web text), but provide second-source signal on cleaning gates + independent dedup hashes for contamination claims.

### Decisions locked

1. **Do not add** CulturaX / CC100 / mC4 / WikiMatrix / NTREX-128 / xP3 — **verify-and-record-absent only.** They either don't include `haw` or are downstream of sources we already pull.
2. **Stage 2 80k focus:** Execute NLLB → BibleNLP → finish OPUS verification. Do not block on adding new external parallel sources.
3. **Stage 1 three probes** (MADLAD-400, Glot500-c, HPLT v2 cleaned) require **Linus rights sign-off** before adapter implementation. Same posture class as FineWeb-2 (ODC-By/CC-derived web crawls)?

### Asks

- **Linus:** Rights/posture objection to adding MADLAD-400 / Glot500-c / HPLT-v2 cleaned `haw_Latn` to Stage-1 plan as ODC-By/CC-derived web crawls?
- **Linus / Rusty:** Is second-source dedup-signal value worth adapter cost given 80k Stage-2 focus? If "no, focus on parallel," defer Stage-1 probes.

---

## Decision: Frank — Stage 2 source discovery: 4 new sources + 6 deferred leads (2026-05-01)

**Owner:** Frank (Hawaiian Data Collector)  
**Date:** 2026-05-02  
**Status:** COMPLETE — 4 sources added to `data-sources/stage2-parallel-fetch-plan.json`

### Summary

User asked: "wait that was easy, lets find more data." Existing 13 source rows insufficient to reach ~20k canonical pairs without over-leveraging Bible. This pass discovered 4 new rights-light parallel sources ready to inventory, and documented 6 leads requiring further review or rights interpretation.

### Sources Accepted (4)

All conservatively scoped: dry-run-by-default, single pinned identifier or paginated metadata-only before any body fetch.

| source_id | alignment_type | rights | gating |
|---|---|---|---|
| `andrews-1865-en-haw-vocab-appendix` | dictionary-example | public_domain_candidate | None — ready to fetch |
| `kaikki-haw-en-wiktionary` | dictionary-example | open_license_candidate (CC BY-SA 4.0 + GFDL) | None — ready to fetch |
| `wikimedia-cx-en-haw-published` | parallel-doc | open_license_candidate (CC BY-SA 4.0) | Linus to pin `stats.mt < 0.5` cutoff |
| `hawaiian-kingdom-statutes-bilingual` | parallel-doc | public_domain_candidate (1846–1897, sovereign-edicts) | Linus to pin bilingual pair + confirm cap |

Honest yield from these four: **~5–13k canonical pair candidates** (pre-dedupe), assuming all gates pass.

### Deferred Leads (6)

Not yet defensible for fetch-plan inventory:
- **UDHR Hawaiian:** Rights fine (OHCHR); endpoint not stable. Defer.
- **Mozilla Firefox haw l10n:** No active haw locale. Drop.
- **Ulukau bilingual nūpepa:** PD haw side; copyrighted English translation. Needs fair-use analysis.
- **Ka Wai Ola (OHA):** Copyrighted, no permissive license. Requires direct permission.
- **Hawaiʻi State Constitution (UH translation):** Copyrighted translation. Requires permission.
- **Governor proclamations:** PD but low yield, per-document review needed. Low priority.

### Verified Absent (3)

Confirmed these do NOT include Hawaiian; pinned to `deferred_or_excluded` to avoid re-suggestion:
- FLORES+ (222 languages, no haw)
- Belebele (122 languages, no haw)
- WMT24++ (48 languages, no haw)

---

## Decision: Linus — Stage 2 yield plan & source ranking (2026-05-01)

**Owner:** Linus (Data Engineer)  
**Date:** 2026-05-01  
**Status:** GUIDANCE — team-relevant

### Summary

Ranked sources 1–8 by yield, blocker status, and adapter readiness. Identified that achieving the original 20k canonical-pair target from human-parallel inventory alone was insufficient; adapted strategy accordingly for 80k target.

### Key Findings

- **Target (original):** 40k SFT rows = ~20k canonical pairs  
- **Bible ceiling:** ≤30% of parallel-train tokens ≈ 6k pairs (unchanged constraint)  
- **Honest gap:** Remaining ~14k pairs require non-Bible sources; inventory exists but adapters are mostly unwritten  
- **Rights-cleared and ready:** Tatoeba (adapter ready), Bible (parser pending), OPUS (draft + rights clear), Wiki langlinks (draft), NLLB (clear for prototype)

### Source Ranking (Priority Order)

| # | Source | Type | Rights | Est. Yield | Status | Blocker |
|---|---|---|---|---|---|---|
| 1 | **Tatoeba** | parallel-sentence | 🟢 CC BY 2.0 FR | 0.5–2k | ✅ Adapter ready | None — execute |
| 2 | **Bible** | parallel-verse | 🟢 PD (1839 + KJV) | 8–12k (capped 30%) | 🟡 Parser pending | Frank owns parser |
| 3 | **OPUS haw** | parallel-sentence | 🟡 Per-corpus CC/GPL | 1–5k | ❌ No adapter | Write next |
| 4 | **NLLB mined** | mined parallel | 🟡 Cleared for prototype | 5–15k | ❌ No adapter | Rusty: quality floor |
| 5 | **Wiki langlinks** | comparable-aligned | 🟢 CC BY-SA 4.0 | 3–5k | ❌ No adapter | LaBSE infra decision |
| 6 | **Weblate** | parallel-sentence | 🟡 Per-project license | 1–3k | ❌ No adapter | Per-project filter |
| 7 | **Wikisource** | comparable-aligned | 🟢 CC BY-SA 4.0 | <500 | ❌ No adapter | LaBSE + cultural filter |
| 8 | **Dict examples** | dictionary | 🟡 Mixed rights | <1k | ❌ No adapter | Per-source gating |

### Next 3 Adapter Priorities

1. **OPUS haw subsets:** Static downloads, permissive licenses, diverse non-Bible sentences
2. **NLLB mined haw-eng:** Largest single yield, requires quality threshold + origin URL tracking
3. **Wiki-aligned:** Encyclopedic register, CC license, needs LaBSE embedding model

---

## Decision: Linus — Review and clear Frank's 4 new sources (2026-05-01)

**Owner:** Linus (Data Engineer)  
**Date:** 2026-05-02  
**Status:** COMPLETE — edits applied to `data-sources/stage2-parallel-fetch-plan.json`

### Verdicts

| source_id | Verdict | Action |
|---|---|---|
| `andrews-1865-en-haw-vocab-appendix` | ✅ Accept with schema fix | Trimmed `concrete_urls` to single pin; backups in note |
| `kaikki-haw-en-wiktionary` | ✅ Accept as-is | No edits required |
| `wikimedia-cx-en-haw-published` | ✅ Accept — gate resolved | `stats.mt < 0.5` cutoff confirmed; `do_not_invoke_until` cleared |
| `hawaiian-kingdom-statutes-bilingual` | ✅ Accept — gates resolved | Pair pinned (1897); rights cleared via PD + sovereign-edicts; `verification_status` updated |

### Rights Rulings

**Andrews 1865:** US PD by term (pre-1929). IA ToS covers digitization only. ✅ Cleared.

**Kaikki:** CC BY-SA 4.0 + GFDL from Wiktionary. Per-row attribution in provenance. ✅ Cleared.

**Wikimedia CX:** CC BY-SA 4.0 per Wikimedia Terms. `stats.mt` field indicates fraction unedited MT; threshold `< 0.5` is conservative and defensible. ✅ Threshold confirmed.

**HK Statutes:** All four paired codes are 1846–1897 imprints (pre-1929 = PD by term). Sovereign-edicts doctrine adds belt-and-suspenders support. 1897 Penal Laws pair pinned (`esrp641724381` ↔ `esrp641728581`, both clean OCR Cornell scans). ✅ Cleared.

### Validation

- JSON valid, 17 sources + 8 deferred + 5 open_questions
- `107 --dry-run` reports source_count=15, gated_static_download=1 (correct: 2 sources unblocked)
- 10/10 unit tests pass

---

## Decision: Linus — Stage 2 target updated to 80k directional SFT rows (2026-05-01)

**Owner:** Linus (Data Engineer)  
**Date:** 2026-05-02  
**Status:** IMPLEMENTED

### Summary

Per user directive, Stage 2 SFT row target raised from 40k (20k canonical pairs) to 80k (40k canonical pairs before retention). All scripts, tests, and documentation updated to reflect new target.

### Changes Made

| File | Change |
|---|---|
| `scripts/107_collect_stage2_parallel.py` | `SFT_ROW_TARGET = 80_000`; docstring updated |
| `code/tests/test_stage2_parallel_fetch_scripts.py` | Test expectations updated to 80k/40k |
| `docs/data-pipeline.md` | Script 107 description: 80k rows = ~40k canonical pairs |

### Validation

- ✅ Compile: `py_compile` all scripts pass
- ✅ Tests: 10/10 unit tests pass
- ✅ Dry-run: `--dry-run` reports `target_sft_rows: 80,000` and `canonical_pair_target: 40,000`

---

## Decision: Frank — Stage 2 80k acquisition plan (2026-05-01)

**Owner:** Frank (Hawaiian Data Collector)  
**Date:** 2026-05-02  
**Trigger:** User directive — 80k target  
**Status:** GUIDANCE — strategy document, not yet implemented

### Honest Yield Math

**80k directional SFT rows** = ~40k canonical pairs post-retention. Retention slicing (dedupe, Bible-cap, register-cap, ASCII-okina, eval contamination) realistically drops **15–25%**, so we need **~48–55k raw candidate pairs**.

**Critical finding:** Rights-light human-parallel sources alone yield **~28–35k accepted canonical pairs** (~56–70k directional rows). This is below 80k.

**Required gap-closers:**
1. **NLLB mined haw-eng** (8–15k pairs) — Linus cleared for prototype only with per-row origin URLs
2. **Synthetic back-translation** (5–10k pairs) — Stage-1-merged base, flagged `synthetic=true`, never dev/test, ≤15% cap

### 11-Bucket Acquisition Roadmap

| Rank | Bucket | Rights | Est. Accepted Pairs | Cumulative | Next Step |
|---|---|---|---|---|---|
| 1 | Bible (1839 + WEB/KJV) | 🟢 PD | 8–12k (≤30% cap) | ~10k | Pin WEB endpoint |
| 2 | **NLLB mined** | 🟡 Prototype-only | **8–15k** @ LaBSE ≥0.80 | ~22k | Rusty: 0.80 floor |
| 3 | OPUS haw | 🟡 Per-corpus CC/GPL | 2–5k | ~25k | Draft + fetch |
| 4 | Wiki langlinks | 🟢 CC BY-SA 4.0 | 3–5k | ~29k | LaBSE infra |
| 5 | **HK statutes (all 4 pairs)** | 🟢 PD + sovereign-edicts | 3–6k (≤15% cap) | ~33k | Rusty: alignment design |
| 6 | CX EN→HAW | 🟢 CC BY-SA 4.0 | 1–3k | ~35k | Gate: `stats.mt < 0.5` |
| 7 | Tatoeba | 🟢 CC BY 2.0 FR | 0.5–2k | ~36k | Execute ready adapter |
| 8 | **Synthetic BT** | n/a (synthetic) | **5–10k** (≤15% cap) | ~44k | Rusty: BT floor |
| 9 | Kaikki Wiktionary | 🟢 CC BY-SA 4.0 + GFDL | 0.3–0.7k | ~44.5k | Capped, never dev/test |
| 10 | Andrews 1865 | 🟢 PD | 0.2–0.5k | ~45k | Capped, never dev/test |
| 11 | Wikisource | 🟢 CC BY-SA 4.0 | <0.5k | ~45k | Low ROI; defer |

**Plan cumulative midpoint: ~45k accepted pairs → 68–76k directional rows post-retention. Realistic outcome: 70–80k rows, with 80k credible only if upper end of NLLB (15k) and BT (10k) both deliver.**

### Guardrails (Load-Bearing)

**NLLB mined:**
- LaBSE ≥0.80 cosine (stricter than 0.75 for curated comparable)
- Below-floor → `alignment_review_required=true`, excluded from train
- Per-row `license_observed` = `unknown`, origin URL recorded
- Never dev/test

**Synthetic BT:**
- Per-pair `model_id`, `model_checkpoint_sha`, `generation_decode_params` recorded
- Round-trip quality floor set by Rusty (BLEU or LaBSE)
- ≤15% of parallel-train tokens cap (enforced in `320_build_stage2_manifest.py`)
- Never dev/test; cross-checked against `eval_hashes.jsonl` before manifest ingest

### What Does NOT Get Us to 80k

- **Bible relaxation:** 30% cap is non-negotiable
- **Dictionary examples:** Combined sub-1k yield; cap honestly
- **Wikisource:** <500 yield; register diversity but not gap-closer
- **JW300 / BibleNLP:** Stay excluded
- **Pukui-Elbert modern edition:** Rights-encumbered
- **Cultural-hard-escalate web scrape:** Not safe to scale without cultural owner
- **Ulukau / Ka Wai Ola / State Constitution / OHA columns:** Lead-only; require permission grants

### Honest Answer: Can 80k be reached from human-parallel only?

**No.** Human-parallel sources alone max out ~56–70k directional rows. Reaching 80k requires NLLB mined + synthetic BT with guardrails. If either is rejected, target needs renegotiation.

### Next 6 Adapter Priorities

| Order | Script | Owner | Blocker |
|---|---|---|---|
| 1 | `108_collect_opus_haw.py` + fetch | Linus | None — execute |
| 2 | `109_collect_nllb_haw.py` + fetch | Linus | Rusty: 0.80 floor |
| 3 | `110_collect_wiki_aligned.py` + fetch | Linus | `sentence-transformers` decision |
| 4 | `111_collect_hk_statutes.py` + fetch (all 4 pairs) | Frank | Rusty: alignment design |
| 5 | `112_collect_cx_published.py` + fetch | Frank | None — gate cleared |
| 6 | `120_generate_bt_pairs.py` (synthetic BT) | Rusty (model) + Frank (provenance) | Rusty: BT floor + decode params |

---

## Decision: Linus — 80k acquisition strategy encoded into source artifacts (2026-05-01)

**Owner:** Linus (Data Engineer)  
**Date:** 2026-05-02  
**Status:** IMPLEMENTED

### Summary

Encoded the 80k directional SFT row acquisition strategy into `data-sources/stage2-parallel-fetch-plan.json` and `docs/data-pipeline.md`. Hawaiian Kingdom statutes promoted from 1897-only pin to all-four-pairs (1897, 1869, 1859, 1846). Guardrails confirmed and enforced at inventory level.

### HK Statutes Promotion

All four paired legislative codes are 1846–1897 Hawaiian Kingdom imprints (pre-1929 PD + sovereign-edicts doctrine):

- **1897 Penal Laws:** `esrp641724381` (EN) ↔ `esrp641728581` (HAW) — primary pin, cleanest OCR
- **1869 Penal Code:** `esrp475081650` ↔ `esrp468790723`
- **1859 Civil Code:** `civilcodehawaii00armsgoog` ↔ `hekumukanawaiam00hawagoog`
- **1846 Statute Laws:** `statutelawshism00ricogoog` ↔ `kanawaiikauiaek00ricogoog`

**Section-id-first alignment for all; LaBSE fallback for sub-sections.** Combined register cap: **≤15% of parallel-train tokens** (newly confirmed as hard cap).

### Guardrails Confirmed

| Rule | Detail |
|---|---|
| Bible cap | ≤30% of parallel-train tokens |
| Legal register (HK statutes) | ≤15% combined across all 4 code pairs |
| Software l10n (OPUS) | ≤15% of parallel-train tokens |
| NLLB quality floor | LaBSE cosine ≥0.80 |
| Synthetic BT cap | ≤15% of parallel-train tokens |
| Synthetic BT dev/test | 0% — never |

### Validation

- ✅ JSON valid
- ✅ `py_compile` passes on all scripts
- ✅ 10/10 unit tests pass
- ✅ `--dry-run` reports `target_sft_rows: 80,000` and `canonical_pair_target: 40,000`

### Open Gates (Team Coordination)

- **Rusty:** LaBSE 0.80 floor for NLLB; synthetic BT round-trip quality floor + decode params
- **Linus:** Implement synthetic cap registry in `320_build_stage2_manifest.py`
- **Frank:** `111_collect_hk_statutes.py` adapter for all-four-pairs
- **Coordinator:** Confirm NLLB mined + synthetic BT policy acceptable; renegotiate 80k target if rejected

---

## Decision: Linus — Baibala Hemolele 1839 edition pin confirmed (2026-05-01)

**Owner:** Linus (Data Engineer)  
**Tracks:** Issue #16  
**Status:** IMPLEMENTED — working tree changes only (not committed)

### Summary

Live-confirmed the canonical Baibala Hemolele source on baibala.org and pinned the 1839 edition in `source_registry.json`.

### Key findings

1. **Platform:** baibala.org runs **Greenstone Digital Library** software. The CGI URL is not a simple `?e=BAI1839&b={book_code}&c={chapter}` pattern — that placeholder was wrong and returns a CGI error.

2. **Correct URL pattern** (innermost content frame, returns verse HTML directly):
   ```
   https://baibala.org/cgi-bin/bible?e=d-1off-01839-bible--00-1-0--01839-0--4--Sec---1--1haw-Zz-1-other---20000-frameset-main-home----011-01839--210-0-2-utfZz-8&d={greenstone_oid}.{chapter}&d2=1&toc=0&exp=1-&gg=text
   ```
   Where `{greenstone_oid}` is per-book (all 66 now in registry `books[].greenstone_oid`).

3. **Verse anchor format** (confirmed on Genesis 1 and John 3):
   ```html
   <a name="agenesis-1-1"></a>1 &para; text... <br />
   ```
   Pattern: `a{book_name_lower}-{chapter}-{verse}` (see `books[].book_name_lower`).

4. **Rights:** 1839 imprint → US public domain. Site copyright 2003-2008 Partners In Development Foundation covers *digitization only* — the underlying text is unencumbered. No scraping prohibition found in ToS/acknowledgments.

5. **ToS snapshot** captured: `data/raw/baibala-hemolele-1839/20260501/tos_snapshot.html` (SHA-256: `254c552c...`).

6. **Sample HTML** captured (gitignored): `data/raw/baibala-hemolele-1839/20260501/` — Genesis 1 and John 3.

### Files changed (working tree, not committed)

- `data-sources/bible/source_registry.json` — edition pinned; correct URL template; `greenstone_oid` + `book_name_lower` added to all 66 books
- `data-sources/bible/README.md` — confirmed URL, rights, ToS snapshot path, parser contract documented
- `scripts/206_fetch_baibala_raw.py` — `render_url()` extended to accept `greenstone_oid` kwarg; `parse_baibala_chapter_html()` docstring updated with live HTML structure
- `scripts/322_build_bible_candidates.py` — `build_rows_for_chapter()` now passes `greenstone_oid` when rendering the haw URL template
- `code/tests/test_bible_adapter.py` — `test_execute_refused_without_edition_pin` updated to reflect that pin is now set (tests wrong-edition mismatch gate instead)
- `data/raw/baibala-hemolele-1839/20260501/` (gitignored) — sample HTML + ToS snapshot + provenance JSON

### Next actions for Frank

1. **Implement `parse_baibala_chapter_html()`** using the confirmed anchor pattern (see updated docstring in `206_fetch_baibala_raw.py`).  
2. Sample HTML at `data/raw/baibala-hemolele-1839/20260501/haw_genesis_1.html` and `haw_john_3.html` are available locally for parser development.  
3. Once parser is in, run `206_fetch_baibala_raw.py --execute --side haw --book GEN --chapters 1-3 --confirm-edition baibala-hemolele-1839 --tos-snapshot data/raw/baibala-hemolele-1839/20260501/tos_snapshot.html`.

---

## Decision: Basher — Kaggle venv robustness + docs idempotency (2026-04-30)

**Owner:** Basher (Training Engineer)

**Status:** IMPLEMENTED — All validation passed

### Summary

Two failure modes on Kaggle notebook reruns:
1. Broken `.venv-training` (pyvenv.cfg existed but pip was corrupt) → setup_training.py failed mid-run.
2. Non-idempotent `cd ideal-spoon` in docs → re-running notebook cells failed.

### Fixes Applied

**`scripts/setup_training.py`**
- Added `venv_is_healthy(venv_dir)` → runs `python -m pip --version` inside venv.
- Updated `ensure_venv()`: healthy venv reused; broken venv (pip missing/error) auto-deleted and recreated with clear warning.
- Dry-run unaffected.

**`docs/kaggle-t4x2-setup.md`**
- Changed relative `cd ideal-spoon` → absolute `cd /kaggle/working/ideal-spoon` (idempotent).
- Section 4 bolded `--no-venv --skip-torch` as recommended Kaggle path.
- Added note: venv unsuitable for Kaggle (PyTorch pre-installed); auto-recovery now handles broken venvs.

### Validation

- ✅ `py_compile scripts/setup_training.py` passed
- ✅ `setup_training.py --dry-run` correct output
- ✅ Broken-venv recovery path tested: deleted and recreated healthy venv
- ✅ `git diff --check` passed


---

## User Directive: W1 provisional micro-eval skipped (2026-04-30T21:32:04Z)

**By:** yashasg (via Copilot)

**What:** Skip the provisional W1 Hawaiian micro-eval data; do not include in Kaggle upload/setup path.

**Why:** User request — captured for team memory

**Status:** Honored in Basher Kaggle venv robustness session; no W1 eval data included in setup guidance.


---

## Decision: Basher — QLoRA bitsandbytes compute dtype now follows TrainConfig (2026-04-30)

**Owner:** Basher (Training Engineer)

**Status:** IMPLEMENTED — All validation passed

### Summary

`_bnb_4bit_config()` in `code/llm_hawaii/model.py` previously hardcoded
`bnb_4bit_compute_dtype=torch.bfloat16`, ignoring the `bf16`/`fp16` fields in
`TrainConfig`. This caused the Kaggle T4x2 config (`fp16=true, bf16=false`) to
silently use the wrong compute dtype (bfloat16 is not supported on Turing/T4).

### Fix applied

- Extracted `_bnb_compute_dtype_name(bf16, fp16) -> str` — pure Python, no torch.
- `_bnb_4bit_config(bf16, fp16)` uses it to derive `torch.<dtype>` via `getattr`.
- `load_base_model()` accepts `bf16`/`fp16` kwargs and passes them through.
- `build_model_and_tokenizer(cfg)` passes `cfg.bf16` / `cfg.fp16`.

**Result:** `fp16=true, bf16=false` → `torch.float16`; `bf16=true` → `torch.bfloat16`;
neither set → `torch.float32`.

### Docs updated

- `code/configs/stage1_fineweb2_haw_kaggle_t4x2.json`: added `device_placement` note
  clarifying `device_map="auto"` is single-process model sharding, not DDP.
- `docs/training-pipeline.md`: added callout box explaining the DDP/device_map distinction.
- `code/README.md`: added inline note on the Kaggle T4x2 config.

### Tests

Four new unit tests in `code/tests/test_model.py` cover `_bnb_compute_dtype_name`
without requiring torch.

### Validation

- ✅ JSON parse: `code/configs/stage1_fineweb2_haw_kaggle_t4x2.json` valid
- ✅ `--print-config` produces correct output
- ✅ `py_compile` on changed Python files passes
- ✅ `test_train` 16/16 pass
- ✅ `test_data` 14/14 pass
- ✅ 4 new dtype helper unit tests pass
- ✅ `git diff --check` passes


---

## Decision: Basher — Kaggle T4x2 Keep Single-Process; device_map="auto" is Model Placement Only (2026-04-30)

**Owner:** Basher (Training Engineer)

**Status:** RECOMMENDATION — no code changes required

### Summary

Kaggle T4x2 = 2 × NVIDIA T4 (16 GB VRAM each, 32 GB total, separate PCIe devices — not a unified pool).

Our current code is correct. `device_map="auto"` with QLoRA is **model-parallel placement** (layers split across GPUs to fit in memory), not data-parallel DDP. Single-process `python -m llm_hawaii.train` is the right and only viable launch strategy for this config.

### Key Findings

1. **Kaggle exposes 2 discrete T4 GPUs** to the notebook process. Both are visible via `torch.cuda.device_count()` and CUDA_VISIBLE_DEVICES.
2. **`device_map="auto"` + bitsandbytes 4-bit**: spreads model layers across GPUs for memory fitting. Training is still single-process/single-stream — no throughput DDP scaling.
3. **QLoRA + true DDP is not supported** by bitsandbytes. bitsandbytes 4-bit wraps params in custom `bnb.nn.Linear4bit` objects that are incompatible with DDP's gradient-gathering and state-dict contracts. This is an upstream blocker, not a configuration choice.
4. **`accelerate launch --num_processes 2`** would spawn 2 processes each trying to load the model with `device_map="auto"` + 4-bit — this causes CUDA init conflicts and is known broken for bnb-quantized models.

### What the Current Code Does on T4x2

| Aspect | Behavior |
|---|---|
| Launch method | `python -m llm_hawaii.train` (single process) |
| GPU placement | `device_map="auto"` spreads 8B layers across both T4s for memory |
| Compute | Single forward/backward pass — one GPU may be idle most steps |
| Throughput scaling | None (no DDP) |
| Memory benefit | Yes — fits 8B+QLoRA in ~13–15 GB active + 4-bit weights spread |

### Recommendation

**Keep single-process `python -m llm_hawaii.train`.** This is the only safe and correct option with QLoRA+bitsandbytes on T4x2.

- Do NOT add `accelerate launch` or `torchrun` with `num_processes > 1` for this QLoRA config.
- If true DDP throughput scaling is needed, drop QLoRA and use full bf16/fp16 fine-tune on higher-VRAM hardware (A100/H100). Then `accelerate launch` is appropriate.
- The config `notes.hardware` field is accurate; the "conservative for a single T4 process" wording is slightly loose (device_map=auto uses both for placement) but not wrong. No file edits required.

### Future: If Bitsandbytes DDP Support Lands Upstream

Monitor https://github.com/TimDettmers/bitsandbytes/issues for multi-GPU 4-bit DDP support. If it lands, revisit. Until then, single-process is correct.


---

> Updated 2026-04-30T10:00:52Z: Merged Basher Kaggle T4x2 DDP research. Outcome: QLoRA + bitsandbytes 4-bit cannot use DDP (upstream blocker). Keep single-process `python -m llm_hawaii.train` with `device_map="auto"` for model placement. No code changes required.


---

## Decision: Basher — Kaggle T4x2 Keep Single-Process; device_map="auto" is Model Placement Only (2026-04-30)

**Owner:** Basher (Training Engineer)

**Status:** RECOMMENDATION — no code changes required

### Summary

Kaggle T4x2 = 2 × NVIDIA T4 (16 GB VRAM each, 32 GB total, separate PCIe devices — not a unified pool).

Our current code is correct. `device_map="auto"` with QLoRA is **model-parallel placement** (layers split across GPUs to fit in memory), not data-parallel DDP. Single-process `python -m llm_hawaii.train` is the right and only viable launch strategy for this config.

### Key Findings

1. **Kaggle exposes 2 discrete T4 GPUs** to the notebook process. Both are visible via `torch.cuda.device_count()` and CUDA_VISIBLE_DEVICES.
2. **`device_map="auto"` + bitsandbytes 4-bit**: spreads model layers across GPUs for memory fitting. Training is still single-process/single-stream — no throughput DDP scaling.
3. **QLoRA + true DDP is not supported** by bitsandbytes. bitsandbytes 4-bit wraps params in custom `bnb.nn.Linear4bit` objects that are incompatible with DDP's gradient-gathering and state-dict contracts. This is an upstream blocker, not a configuration choice.
4. **`accelerate launch --num_processes 2`** would spawn 2 processes each trying to load the model with `device_map="auto"` + 4-bit — this causes CUDA init conflicts and is known broken for bnb-quantized models.

### What the Current Code Does on T4x2

| Aspect | Behavior |
|---|---|
| Launch method | `python -m llm_hawaii.train` (single process) |
| GPU placement | `device_map="auto"` spreads 8B layers across both T4s for memory |
| Compute | Single forward/backward pass — one GPU may be idle most steps |
| Throughput scaling | None (no DDP) |
| Memory benefit | Yes — fits 8B+QLoRA in ~13–15 GB active + 4-bit weights spread |

### Recommendation

**Keep single-process `python -m llm_hawaii.train`.** This is the only safe and correct option with QLoRA+bitsandbytes on T4x2.

- Do NOT add `accelerate launch` or `torchrun` with `num_processes > 1` for this QLoRA config.
- If true DDP throughput scaling is needed, drop QLoRA and use full bf16/fp16 fine-tune on higher-VRAM hardware (A100/H100). Then `accelerate launch` is appropriate.
- The config `notes.hardware` field is accurate; the "conservative for a single T4 process" wording is slightly loose (device_map=auto uses both for placement) but not wrong. No file edits required.

### Future: If Bitsandbytes DDP Support Lands Upstream

Monitor https://github.com/TimDettmers/bitsandbytes/issues for multi-GPU 4-bit DDP support. If it lands, revisit. Until then, single-process is correct.


---

## User Directive: W1 Stage 0 input is JSONL-only (2026-04-30T08:11:37Z)

**By:** yashasg (via Copilot)

**What:** W1 Stage 0 input should be JSONL-only; do not use TSV for W1 eval consumption.

**Why:** User request — captured for team memory

**Status:** Implemented by Linus; reviewed and APPROVED by Rusty.


---

## User Directive: Model preferences for team (2026-04-30T08:24:43Z - 2026-04-30T08:25:49Z)

**By:** yashasg (via Copilot)

**What:** 
- Scribe and Ralph should use `claude-haiku-4.5`
- Engineering agents (Linus, Basher, Livingston) should use `claude-sonnet-4.6`

**Why:** User model preferences — captured for team memory

**Status:** For future agent spawning


---

## Decision: Linus — W1 Stage 0 JSONL-only implementation

**Date:** 2026-04-30T08:29:53Z

**Owner:** Linus (Data Engineer)

**Status:** APPROVED by Rusty (background gate review)

### Summary

Stage 0 W1 path now reads JSONL only. TSV is authoring-source only (off-git); TSV → JSONL conversion happens via `scripts/315_hash_manual_w1_eval.py --execute --jsonl-only`.

### What changed

- **CLI:** `--manual-w1-jsonl <path>` (replaces `--manual-w1-tsv`)
- **Env:** `MANUAL_W1_JSONL=...` in `scripts/run_stage0_eval.sh` (replaces `MANUAL_W1_TSV`)
- **Default:** `data/evals/manual_w1/w1-haw-micro-eval.jsonl`
- **Report fields:** `jsonl_sha256`, `jsonl_size_bytes`, `schema_version_seen="manual-w1-jsonl-v1"`
- **No TSV fallback** in `evaluate.py` (TSV constants removed)

### Accepted-row orthographic gate (strict, loud, file-level invalid)

Any of these on a `review_status=accepted` row flips file to `status="invalid"` (exit 2):
- `nfc_normalized` not exactly `true`
- `prompt`, `reference`, or `text` is not NFC
- combining macron U+0304 in any field
- wrong ʻokina codepoint (U+2018 / U+2019 / U+0027 / U+02BC)
- empty `item_id`

Drafts/reviewed rows stay loose.

### Per-row JSONL fields

- `item_id` (required on accepted) or `id` (alias)
- `category` (optional, defaults `"unknown"`)
- `prompt` (string), `reference` (string, optional; falls back to `text`)
- `text` (optional, fallback for reference hash material)
- `review_status`: `draft | reviewed | accepted` (only `accepted` is eval-consumable)
- `nfc_normalized`: bool or `"true"`/`"false"` string
- `diacritic_density` (int) and/or `diacritic_density_bin` (`none|low|medium|high`)
- `sha256_normalized` (64-char hex, optional; otherwise computed)

### Hash + suite stability

- `w1_suite_sha256`: sha256 over sorted `(item_id, sha256_normalized)` pairs
- Stable under row reorder; flips when accepted set changes
- Hash formula: `sha256(NFC(prompt) + LF + NFC(reference))`

### Exit codes

- Exit 2 iff `manual_w1.status == "invalid"`
- Exit 0 otherwise
- Report JSON written before exit; tracked summary writes regardless

### Validation

- ✅ `python3 -m py_compile code/llm_hawaii/evaluate.py scripts/315_hash_manual_w1_eval.py scripts/_convert_ulukau_human_fetch.py`
- ✅ `sh -n scripts/run_stage0_eval.sh`
- ✅ `cd code && PYTHONPATH=. python3 -m unittest tests.test_evaluate tests.test_metrics` — **50/50 green**
- ✅ `git --no-pager diff --check`

### Trusted source for W1 rows

- **Source:** `data/raw/ulukau_nupepa/human_fetch.txt` (on-disk, off-git, gitignored under `data/raw/`)
- **Sections:** `# English` / `# Hawaiian` — use Hawaiian only for W1
- **Converter:** `scripts/_convert_ulukau_human_fetch.py` is parser/normalizer context, not source of truth
- **Populated TSV/JSONL:** Off-git under `data/evals/manual_w1/`


---

## Review: Rusty — W1 Stage 0 JSONL-only revision (Linus) [APPROVED]

**Date:** 2026-04-30T08:29:53Z

**Reviewer:** Rusty (NLP Researcher)

**Subject under review:** W1 Stage 0 JSONL-only implementation (Linus)

### Verdict — **APPROVE**

JSONL-only Stage 0 W1 path delivered, no TSV fallback, strict accepted-row gates preserved, tests/docs aligned. Validation re-runs clean: **50/50 tests green**, py_compile clean, sh -n clean, git diff --check clean.

### Spot checks

1. **JSONL-only wiring — PASS**
   - `evaluate.py:58`: `DEFAULT_MANUAL_W1_JSONL = "data/evals/manual_w1/w1-haw-micro-eval.jsonl"`
   - `evaluate.py:1003-1019`: `--manual-w1-jsonl` only, no `--manual-w1-tsv`
   - Legacy TSV symbols gone; pinned by unit tests

2. **Report fields — PASS**
   - `jsonl_sha256`, `jsonl_size_bytes` (rename from `tsv_sha256` / `tsv_size_bytes`)
   - `schema_version_seen = "manual-w1-jsonl-v1"` on valid states

3. **Accepted-row gate — PASS**
   - NFC normalization required, ʻokina orthography strict
   - Combining macron forbidden, item_id required
   - Drafts/reviewed rows loose

4. **Hash stability — PASS**
   - `w1_suite_sha256` stable under row reorder, flips on accepted-set changes
   - `accepted_item_hashes` sorted

5. **Exit propagation — PASS**
   - Exit 2 on invalid, 0 otherwise
   - Tracked summary writes unconditionally

6. **Docs/tests — PASS**
   - `code/README.md:164-209` describes JSONL-only
   - `docs/eval_pipeline.md` §3.1, §8.1 match
   - All unit tests pass

### Validation rerun (clean)

- ✅ py_compile
- ✅ sh -n scripts/run_stage0_eval.sh
- ✅ 50/50 tests green
- ✅ git diff --check

### Outcome

✅ **Lift the W1 JSONL-only revision.** Linus locked out of next revision cycle per standard rule; no re-spawn needed.


---


## User Directive: Stage 0 eval drift-signal bundle (2026-04-30T07:04:47Z)

**By:** yashasg (via Copilot)

Stage 0 evals should capture the full checkpoint drift-signal bundle so future checkpoints can be compared across PPL, orthography, generation, dtype/config identity, and related regression tripwires instead of only the current PPL summary.

**Status:** Implemented as `stage0_eval.v2` (Basher); reviewed and approved (Rusty, Linus). Post-review cleanups applied.


---

## Decision: Basher — Stage 0 eval drift-signal bundle (`stage0_eval.v2`)

**Date:** 2026-04-30
**Owner:** Basher (Training Engineer)
**Scope:** `code/llm_hawaii/evaluate.py`, `scripts/run_stage0_eval.sh`, `code/tests/test_evaluate.py`, `docs/eval_pipeline.md` §8.1, `code/README.md` Stage 0 section.
**Status:** Implemented, reviewed, and approved by Rusty + Linus. Post-review cleanups applied (hawaiian_ppl parity, schema_version fallback, suite-design freeze invariant documented).

### What changed

`evaluate.py` now emits a richer artifact under `schema_version = "stage0_eval.v2"` and `scripts/run_stage0_eval.sh` projects that into the tracked hash-only summary. Backwards-compatible CLI: `--prompt`, `--eval-file`, `--checkpoint` unchanged. New: `--no-prompt-suite`, `--max-length`, `--max-new-tokens`. Default behavior when no `--prompt` is given is now to run the built-in fixed suite.

### Captured drift signals (every Stage 0 eval, summary stays tracked-friendly)

1. **Run identity** — `identity.{checkpoint, base_model, is_adapter, model_class, model_dtype, model_device, device_map, quantization_config, tokenizer_class, tokenizer_name_or_path, tokenizer_vocab_size, torch_version, transformers_version, cuda_available}`. `decoding.{do_sample, max_new_tokens, greedy}`. `ppl_config.max_length`.
2. **Eval-set slice metadata** — `eval_set.{path, sha256, record_count, scored_record_count, total_tokens, total_chars, length_bin_counts_tokens, diacritic_density_bin_counts, source_counts, register_counts, max_length_used}`. No raw text. Source/register counts default to `{"status": "field_absent"}` when absent.
3. **Hawaiian held-out PPL** — unchanged headline (`hawaiian_ppl`). Per-source slice exposed as `hawaiian_ppl_by_source` with explicit `status: "not_configured"` placeholder.
4. **Fixed prompt suite** — `PROMPT_SUITE_ID = "stage0.v1"`, 7 items (1 English control, 2 low, 2 medium, 2 high diacritic). `prompt_suite.{suite_id, suite_sha256, items[]}` in artifacts; items carry `prompt_sha256`, `prompt_diacritics`, `diacritic_density_bin`, `prompt_len_chars` — never raw prompt text.
5. **Per-sample orthography + aggregate** — per-sample dict plus `orthography_aggregate.{n, okina_total, wrong_okina_total, kahako_total, combining_macron_total, nfc_failures, diacritic_density_bin_counts, kahako_collapse_on_high_diacritic}`.
6. **Tripwires** — `tripwires.{wrong_okina_nonzero, nfc_failures, combining_macron_nonzero, kahako_collapse_on_high_diacritic, generation_count, prompt_suite_sha256, prompt_suite_id}`.
7. **Explicit not-yet-wired probes** — `english_ppl`, `manual_w1`, `hawaiian_ppl_by_source` all emit `{"status":"not_configured", "reason":"..."}` instead of being silently absent.

### Prompt suite freeze (must not edit in place)

Editing a prompt in place changes `prompt_suite_sha256` and silently breaks comparability with all prior summaries. Adding/removing prompts at the end is fine **only if `PROMPT_SUITE_ID` is bumped** (`stage0.v1` → `stage0.v2`).

Current suite (fingerprint `stage0.v1`, `suite_sha256 = 2683027f538ae8fb2910f758f2865596355893cc91c85dbdfe9ced130797bce6`):

- `en_control_1` — none-density English control.
- `haw_low_1`, `haw_low_2` — 1–2 diacritics each.
- `haw_medium_1`, `haw_medium_2` — 3 diacritics each.
- `haw_high_1`, `haw_high_2` — 12–13 diacritics, both ʻokina + kahakō dense, used for the kahakō-collapse tripwire.

### Suite-design invariant (Rusty approval condition)

Any prompt placed in the `high` diacritic-density slot of the Stage 0 suite must explicitly instruct the model to use kahakō (and, where it makes sense, ʻokina). The `kahako_collapse_on_high_diacritic` tripwire's interpretive weight depends on this. Both `haw_high_1` / `haw_high_2` already comply.

### Post-review cleanups applied

1. **`hawaiian_ppl` shape parity** — When `evaluate_checkpoint` is called without an `--eval-file`, the report now emits `{"status": "not_configured", "reason": "no --eval-file provided; held-out PPL not run"}` instead of leaving the field absent.
2. **Summary `schema_version` fallback** — `scripts/run_stage0_eval.sh` fallback flipped from `"stage0_eval.v1"` to `"unknown"` so malformed or pre-v2 reports are visible rather than silently mislabeled.
3. **Suite-design freeze invariant documented** — `code/README.md` and `docs/eval_pipeline.md` §8.1 now state the invariant above.

### Validation

- `python3 -m py_compile code/llm_hawaii/evaluate.py code/tests/test_evaluate.py` ✓
- `sh -n scripts/run_stage0_eval.sh` ✓
- `PYTHONPATH=. python3 -m unittest tests.test_evaluate tests.test_metrics` — 18/18 passing

### Out of scope this pass

- English PPL probe — `evaluate.py` does not load an English eval JSONL yet. Status field carries `not_configured`. Stage 1 gate cannot be called green until this is wired.
- W1 manual micro-eval — loader/integration not implemented. Status field carries `not_configured`.
- Per-source / per-register PPL slice — needs `source`/`register` field on JSONL records. Eval-set metadata already counts those fields when present; PPL aggregation per slice is the follow-up.


---

## Decision: Rusty — Stage 0 eval coverage assessment (drift-signal acceptance checklist)

**Date:** 2026-04-30T07:30:00Z
**Owner:** Rusty (NLP Researcher)
**Status:** Assessment complete. Checklist defines the contract for Stage 0 summary → Stage 1 aggregation.

### Purpose

Specify acceptance criteria so that every Stage 0 eval summary must capture checkpoint-to-checkpoint drift signals in a form that is (a) machine-comparable across checkpoints and (b) sufficient to anchor Stage 1 gate decisions.

### Anchor baseline

Stage 0 baseline already captured: `hawaiian_ppl=7.9152` on FineWeb-2 `haw_Latn` dev. Single-prompt orthography sample is positive but **n=1 and not distributional** — current artifact is insufficient as a drift baseline.

### Acceptance checklist — Stage 0 eval summary must contain

#### A. Identity / fair-comparison header (required, all fields present and non-null)

- `stage`, `checkpoint`, `source_git_commit`, `command`
- `eval_file`, `eval_file_sha256`
- `eval_suite_sha` (suite identity, separate from eval-file content)
- `tokenizer_sha256` and `tokenizer_fingerprint` 
- `base_model_sha` / HF revision pin
- `eval_dtype` (must mirror training dtype — bf16 on A100, fp16 only as Turing fallback; record verbatim, do not silently coerce)
- Decoding config: `do_sample`, `max_new_tokens`, `max_length`, `pad_token_id`
- `prompt_set_sha256` over the canonical fixed prompt suite (frozen between runs)
- `generation_sha256.sample_*` per prompt (drift signal)
- `eval_hashes_ledger_sha256` (snapshot of contamination ledger at run time)

#### B. Hawaiian orthography (distributional, not n=1)

Computed over **every** generation and over the dev slice references, reported separately:

- `is_nfc` — boolean per sample; aggregate `nfc_violation_rate` over all generations (must be 0.0 at Stage 0)
- `wrong_okina` — per-sample integer; aggregate `wrong_okina_rate` and `wrong_okina_total` (must both be 0 at Stage 0)
- `okina` — per-sample count; aggregate `okina_per_1k_chars`
- `kahako` — per-sample count; aggregate `kahako_per_1k_chars`
- `combining_macron` — per-sample count (NFD detector); aggregate `combining_macron_total` (must be 0)
- `diacritic_density` and `diacritic_density_bin` per sample
- **Generation vs reference deltas** on the dev slice: `okina_survival_rate`, `kahako_retention_rate`, reported as distribution mean + min
- **Per-bin breakdown** for every orthography metric across `none / low / medium / high` density bins

#### C. Fixed prompt suite shape (frozen Stage 0 → Stage 1)

- **≥5–10 prompts**, deterministic ordering, content-frozen, NFC-normalized, hashed in `prompt_set_sha256`
- Spans `low / medium / high` diacritic density bins (≥1 prompt per bin; ≥2 in `high`)
- Mix of registers: contemporary + period/biblical + governmental/educational
- At least one open-ended Hawaiian prompt for generation-sanity
- At least one English prompt for English-PPL / forgetting baseline
- Suite stored under version control with the suite SHA pinned in the report

#### D. Perplexity reporting (drift signal)

- Global `hawaiian_ppl`
- **Per-source / per-register slice PPL** — needed before Stage 1 starts (currently TODO)
- **Per-length bin PPL** (short / medium / long)
- **English-PPL baseline** on a small frozen English slice
- Token-weighted *and* record count reported

#### E. Tokenizer behavior on outputs (drift signal)

- `tokens_per_word` on generations (and on dev references for delta)
- `explicit_byte_fallback_rate` on generations
- `byte_fallback_or_proxy_rate` on generations, **with byte-level-BPE caveat** (Llama-3 is tiktoken-family; raw proxy is a known false positive)
- `roundtrip_lossless` boolean over generations; must be `true`
- Same metrics on the high-diacritic prompt subset

#### F. W1 / manual micro-eval status (must be reported, even when not live)

W1 is not live at Stage 0 (only draft rows; not accepted). The Stage 0 summary must still carry the wiring so its absence is auditable:

- `manual_w1.status` ∈ {`absent`, `draft_only`, `accepted_subset`, `live`}
- `manual_w1.tsv_sha256` (or `null`)
- `manual_w1.row_counts.{draft, reviewed, accepted}`
- `manual_w1.eval_consumable_count` — only `accepted` rows count; current Stage 0 must report `0`
- If `eval_consumable_count == 0`: `manual_w1.metrics = null` and the summary explicitly says "W1 not used as Stage 0 benchmark"

#### G. Slice fields (mandatory on every reported metric block)

Every metric in B / D / E must be reported with the following slice keys:

- `source` / `register` (period-biblical / contemporary / governmental-educational / unknown)
- `diacritic_density_bin` (`none` / `low` / `medium` / `high`)
- `length_bin` (`short` / `medium` / `long`)
- `tokenizer_behavior_bin` (binned by input tokens/word + byte-fallback rate)
- `split` (`dev` / `holdout`)
- `w1_category` (once W1 live; `null` until then)

#### H. Tripwire harness (machine-checked, not just reported)

Serialize the tripwire predicates so checkpoint comparison is a pure function over two summaries:

- `tripwires.okina_collapse` — true if any generation contains U+2018 or U+0027 where ʻokina expected
- `tripwires.nfd_or_combining_macron` — true if `is_nfc=false` or `combining_macron > 0` anywhere
- `tripwires.wrong_okina_nonzero`
- `tripwires.high_density_slice_regression` (cross-checkpoint; `null` at Stage 0)
- `tripwires.tokens_per_word_up` / `tripwires.byte_fallback_up` (cross-checkpoint)
- `tripwires.english_ppl_up_gt_20pct` (cross-checkpoint)
- `tripwires.generation_sha_unchanged` (cross-checkpoint; identical SHA = stuck)
- `tripwires.degeneracy_detected` (repetition loop / English collapse / register collapse)
- `tripwires.contamination_overlap_up` (n-gram overlap vs contamination ledger)

### Bottom line

Current `20260430T063118Z__stage0_base_eval_summary.json` satisfies A partially (missing tokenizer SHA, eval-suite SHA, eval dtype, prompt-set SHA, ledger SHA), B only at n=1, none of C beyond a single prompt, only the global PPL of D, none of E, none of F as structured fields, none of G as slice keys, and none of H as serialized tripwires. It is a usable PPL anchor (`7.9152`) and nothing more.


---

## Decision: Rusty — Stage 0 prompt suite review (Hawaiian phrasing + tripwire)

**Date:** 2026-04-30
**Owner:** Rusty (NLP Researcher)
**Verdict:** **APPROVED for freeze as `stage0.v1` baseline.**

### What I checked

For each of the 7 prompts, verified mechanically:

- **NFC**: every prompt is already in NFC (no combining macron).
- **ʻokina codepoint**: every ʻokina is **U+02BB** — never ASCII `'`, never U+2018/U+2019, never U+02BC.
- **Wrong-ʻokina detector**: 0 hits per prompt (a Stage 0 baseline cannot ship a suite that itself trips `wrong_okina_nonzero`).
- **Density-bin coverage**: counts match the bin labels.

Diacritic counts per prompt (U+02BB ʻokina + ā/ē/ī/ō/ū):

| id            | bin    | ʻokina | kahakō | total |
|---------------|--------|--------|--------|-------|
| haw_low_1     | low    | 0      | 1      | 1     |
| haw_low_2     | low    | 0      | 2      | 2     |
| haw_medium_1  | medium | 2      | 1      | 3     |
| haw_medium_2  | medium | 1      | 2      | 3     |
| haw_high_1    | high   | 6      | 7      | 13    |
| haw_high_2    | high   | 5      | 7      | 12    |

### Hawaiian phrasing — per-prompt sign-off

- **`en_control_1`** — English is grammatical, no diacritics expected. ✓
- **`haw_low_1` "Aloha mai kākou."** — standard formal greeting. Natural, grammatical. ✓
- **`haw_low_2` "Aloha kāua i kēia kakahiaka."** — "greetings to us two this morning". Grammatical, common register. ✓
- **`haw_medium_1` "He aha ka mōʻaukala o Hawaiʻi?"** — "what is the history of Hawaiʻi?". Grammatical. ✓
- **`haw_medium_2` "Pehea ʻoe i kēia lā?"** — "how are you today?", textbook conversational form. ✓
- **`haw_high_1`** — instructional prompt on ʻohana with explicit kahakō/ʻokina instruction. Grammatical, self-referential design is exactly what we want. ✓
- **`haw_high_2`** — "show me a short story in Hawaiian about the first day of the year, with all the ʻokina and kahakō." Grammatical, self-referential. ✓

No phrase needs rewording.

### Tripwire `kahako_collapse_on_high_diacritic`

**Definition:** for each suite item whose `diacritic_density_bin == "high"`, if the matching sample orthography report has `kahako == 0`, increment the counter. Reported as an integer (0–N high-density items).

**Approved as a Stage 0 drift signal.** The Hawaiian-quality risk being detected is real: a model that drops kahakō on high-density Hawaiian prompts is ʻōlelo-Hawaiʻi-broken in a way the global PPL number won't surface. In `stage0.v1` specifically, both high-bin prompts explicitly instruct the model to use kahakō. So zero kahakō in a non-trivial Hawaiian generation is a legitimate failure signal.

### Suite-design invariant (now documented in code/README.md and docs/eval_pipeline.md)

Any prompt placed in the `high` diacritic-density slot of the Stage 0 suite must explicitly instruct the model to use kahakō (and, where it makes sense, ʻokina). The `kahako_collapse_on_high_diacritic` tripwire's interpretive weight depends on this.

### Follow-up notes (non-blocking)

1. **Symmetric `okina_collapse_on_high_diacritic` is cheap.** Both high prompts request ʻokina too. A sibling counter would catch the dual failure mode. Suggest as Stage 1 follow-up (additive, no SHA churn).
2. **`mōʻaukala` vs `moʻolelo`.** Both are valid; they represent distinct registers. Fine as-is.


---

## Decision: Linus — Stage 0 summary shape review (cross-checkpoint aggregator consumability)

**Date:** 2026-04-30
**Owner:** Linus (Data Engineer)
**Status:** APPROVED. No critical data-contract issues. No file changes requested at review time.

### What I checked

1. **Hash-only summary projection** ✅ — no raw generation text, no raw prompt text, full artifact under ignored `data/` with sha256 pointer
2. **Stable keys** ✅ — every top-level key always present; missing fields use `{"status":"absent"}` instead of dropping
3. **Schema/version fields** ✅ — `schema_version`, `prompt_suite.suite_id`, `prompt_suite.suite_sha256` all present for aggregator gating
4. **No raw text in tracked summaries** ✅ — confirmed across 5 surfaces (prompt_suite, eval_set, orthography_metrics, orthography_aggregate, tripwires)
5. **Placeholders for not-yet-configured probes** ✅ — uniform `{"status":"not_configured","reason":"..."}` shape
6. **Cross-checkpoint fairness** ✅ — all confounds captured: identity, decoding, ppl_config, eval_set, provenance

### Confirmed fair comparison patterns the aggregator can rely on

- **PPL diff is comparable** iff `identity.tokenizer_name_or_path`, `identity.tokenizer_vocab_size`, `ppl_config.max_length`, and `eval_set.sha256` all match. All four present.
- **Orthography/tripwires diff is comparable** iff `prompt_suite.suite_sha256` matches. Present.
- **Per-sample drift is comparable** by joining on `prompt_suite.items[i].id` and watching `generation_sha256.sample_i` flip. Present.

### Fairness gates the aggregator should enforce on entry

1. `prompt_suite.suite_sha256` equal across rows being compared (else refuse orthography/tripwire diff).
2. `eval_set.sha256`, `identity.tokenizer_name_or_path`, `identity.tokenizer_vocab_size`, `ppl_config.max_length` equal (else refuse PPL diff).
3. `schema_version` equal or carry an explicit migration table.

These are guidance for the future aggregator; the current summary already carries every field needed to enforce them.


---

## Decision: Linus — Tokenizer audit harness cleanup (schema/identity/evaluators)

# Linus — Tokenizer audit harness cleanup plan (pre-Llama re-run)

**Date:** 2026-04-30T03:43Z
**Owner:** Linus (Data Engineer)
**Status:** Proposed — data-engineering / reporting side; needs Rusty sign-off on threshold semantics and Basher sign-off on manifest consumers before re-running Llama-3.1-8B.

## Why now

The current Llama report at `data/tokenizer_audit/official/20260430T033208Z__meta-llama_Llama-3.1-8B.json` is internally inconsistent with the harness:

- File lives under `official/` but the JSON body says `"dry_run": true`. Two sources of truth for the same flag, both wrong half the time.
- `model.model_repo_sha`, `tokenizer_sha256`, `tokenizer_fingerprint_sha256` all `null`. Per Rusty's Stage-0 gate (decisions.md, 2026-04-29), the Stage-1 manifest must freeze these. We currently can't.
- `high_diacritic` and `diacritic_chars` are `"not_evaluated"`. Two of three Rusty gate dimensions are silently absent — the `go` / `no_go` line in the report only reflects overall metrics.
- `byte_fallback_or_proxy_rate = 0.193` — the `no_go` is real, but the proxy heuristic flags every non-ASCII char as fallback (see Rusty's inbox note). Reporting is muddying the signal.
- The harness is one `unittest` smoke that hardcodes model id, single eval file, and write path. Not reusable, not parameterizable, not committable as a gate.

## Cleanup contract

### 1. Path convention (single source of truth)

- `official/` ↔ real model load, real tokenizer fingerprint, real corpus pass. Body MUST NOT carry `dry_run`. Drop the field.
- `dryrun/` (one word, no underscore — match `data/tokenizer_audit/` siblings; rename existing `dry_run/` → `dryrun/` in a follow-up) ↔ harness-self-test runs with stub tokenizer or trimmed sample. Body carries `"run_kind": "dryrun"`.
- The directory is the contract. The body field `dry_run` is removed from the schema. Replace with `run_kind ∈ {"official","dryrun"}` echoed from the caller, validated against the parent directory at write time.

### 2. Function boundaries

Split `tokenizer_audit_output_from_encoding` into three pure functions plus one orchestrator:

1. `compute_overall_metrics(ids, pieces, word_count) -> dict` — overall block only. No I/O, no thresholds.
2. `compute_high_diacritic_metrics(samples, tokenizer) -> dict` — per Rusty's definition (`ʻokina + kahakō ≥ 3` AND `diacritics/word ≥ 0.25`). Returns `status ∈ {"evaluated","insufficient_samples"}` and metrics. Minimum sample requirement (≥10 high-diacritic samples, ≥1,500 words total per Rusty) enforced here, not at the gate.
3. `compute_standalone_diacritic_chars(tokenizer, charset) -> dict` — encodes each of the Hawaiian diacritic chars (`ʻ`, `ā`, `ē`, `ī`, `ō`, `ū` + uppercase) standalone and reports tokens-per-char. `status ∈ {"evaluated","tokenizer_unavailable"}`.
4. `build_audit_report(model_id, tokenizer, samples, run_kind, thresholds) -> dict` — orchestrator. Owns `model.*` fingerprint resolution, calls the three pure metric functions, applies thresholds once at the end, emits `recommendation`.

The harness test then becomes: build report → write to `official/` or `dryrun/` based on `run_kind` → schema-assert. Nothing more.

### 3. Model / tokenizer identity (must be filled before Llama re-run)

- `model.model_repo_sha`: resolve from `huggingface_hub.HfApi().repo_info(model_id).sha`. If unauthenticated/gated, fail loudly, do not silently null.
- `model.tokenizer_sha256`: SHA-256 over the resolved local `tokenizer.json` bytes (or concatenated tokenizer files if `tokenizer.model` only). Pin which file(s) define the hash.
- `model.tokenizer_fingerprint_sha256`: SHA-256 over a deterministic projection — sorted vocab pairs + merges + special tokens + `add_bos_token`/`add_eos_token` + normalizer/pre-tokenizer config. Independent of file layout so it survives format upgrades.
- All three null ⇒ report MUST set `recommendation.decision = "no_go"` with `blocking_reasons += ["model_identity_unresolved"]`. No more silent nulls in `official/`.

### 4. High-diacritic section

Currently `"not_evaluated"`. Required for the gate. Before Llama re-run:

- Source samples from `data/tokenizer_audit/ulukau_nupepa/kaehuikimanoopuuloa/kaehuikimanoopuuloa.jsonl` paragraph-split, plus any other ingested nūpepa/Baibala slices once available (per Rusty's Stage-0 note, my eval-safety contract).
- Filter to high-diacritic per the formula above.
- Emit: `tokens_per_word`, `explicit_byte_fallback_rate`, `byte_fallback_or_proxy_rate`, `sample_count`, `word_count`, plus `status`.
- If `sample_count < 10` or `word_count < 1500`: `status = "insufficient_samples"` and gate is `no_go` with reason `high_diacritic_coverage`.

### 5. Standalone diacritic section

Currently `"not_evaluated"`. Required for the gate. Per Rusty: each Hawaiian diacritic char must tokenize to ≤ 2 tokens standalone.

- `diacritic_chars.items[]` rows: `{ "char": "ʻ", "codepoint": "U+02BB", "ids": [...], "pieces": [...], "token_count": N, "passed": bool }`.
- Section-level `passed = all(item.passed)` feeds the gate.

### 6. Sample / debug dumps

- Add an optional `samples_summary` block: `{ "source_paths": [...], "row_count": N, "word_count": N, "char_count": N, "normalization": "NFC", "okina_canonicalization": "U+02BB" }`. No raw text in the report (corpus stays under ignored `data/`; report is committable metadata).
- Keep an off-report debug dump under `data/tokenizer_audit/<run_kind>/<timestamp>__<model>__debug.jsonl`, gitignored, one row per sample with `text_sha256`, `token_count`, `pieces` — for forensics. Decision report does not include it.

### 7. Manifest / schema shape

- Bump `schema_version` to `tokenizer_audit_report.v2` once these changes land. v1 stays parseable as historical only.
- v2 top-level keys (ordered): `schema_version`, `run_kind`, `generated_at`, `model`, `thresholds`, `samples_summary`, `overall`, `high_diacritic`, `diacritic_chars`, `checks`, `recommendation`, `errors`. Drop `dry_run`.
- `recommendation.blocking_reasons` becomes a closed enum: `{ overall_tokens_per_word, explicit_byte_fallback_rate, byte_fallback_or_proxy_rate, high_diacritic_tokens_per_word, high_diacritic_byte_fallback_or_proxy_rate, high_diacritic_coverage, standalone_diacritic_chars, model_identity_unresolved }`.
- Stage-1 manifest pin (Basher's contract) reads `model.model_repo_sha` + `model.tokenizer_fingerprint_sha256` directly from the chosen `official/` report path.

### 8. Testability

- Convert `code/tests/test_tokenizer_audit.py` from a one-shot writer into:
  - **unit tests** that hit the four functions with synthetic encodings (no model load, no network) — these run in CI.
  - **one integration test** behind an env gate (`HF_TOKEN` present + `RUN_TOKENIZER_AUDIT=1`) that loads the real Llama tokenizer, evaluates the local Hawaiian sample set, writes to `official/`. Skipped by default.
  - Schema assertion runs on both: every emitted report must match v2 keys/types.
- Replace hardcoded `_model_id` and `_dry_run` locals with parametrization (env vars or pytest params) so re-running for a fallback tokenizer does not require code edits.

### 9. Proxy heuristic — flagged, not owned by me

The 19% `byte_fallback_or_proxy_rate` is dominated by `▁<diacritic-char>` patterns that aren't real byte fallback. That's Rusty's call (see his inbox note). My ask: keep `explicit_byte_fallback_rate` and `byte_fallback_or_proxy_rate` as separate checks with separate thresholds in v2 so the heuristic can be tightened without re-cutting the schema.

## Order of operations before the Llama re-run

1. Land schema v2 + the four-function split + path/run_kind contract (no model needed).
2. Land the unit tests against synthetic encodings.
3. Wire the three identity fields. Verify against any model first (Qwen tokenizer is fine for plumbing).
4. Wire high-diacritic + standalone-diacritic sections. Verify via Qwen dryrun.
5. Re-run Llama-3.1-8B against `official/` with all sections evaluated and identity pinned. The `go`/`no_go` then reflects the full Stage-0 gate, not a partial.

## Out of scope this pass

- Choice of fallback tokenizer (Rusty owns).
- Tightening the proxy heuristic (Rusty owns).
- Adding a standalone `scripts/040_tokenizer_audit.py` — decisions.md keeps it as a test, not a script.
- Hawaiian-literacy review of sample selection (#7 territory).

## Asks

- **Rusty:** confirm v2 `blocking_reasons` enum and the high-diacritic minimum coverage numbers (10 samples / 1,500 words) are still the right floor.
- **Basher:** confirm the Stage-1 manifest will read from `model.model_repo_sha` + `model.tokenizer_fingerprint_sha256` of a specific `official/` filename, and that pinning that filename in the Stage-1 manifest is acceptable.
- **Coordinator:** sequence — schema/path/identity first, then Llama re-run; do not re-run while sections are still `not_evaluated`.



---

## Decision: Rusty — Tokenizer audit harness cleanup (tokenizer-family-aware proxy + round-trip)

# Decision: Rusty — Tokenizer audit harness cleanup (tokenizer-family-aware proxy + round-trip)

**Date:** 2026-04-30
**Owner:** Rusty (NLP Researcher)
**Status:** Proposed — implementation owner: Linus (test/harness code)

## Direction

Clean the tokenizer audit harness so that "byte fallback" means what it says by tokenizer family. Do not change thresholds. Add round-trip as the ground-truth check. Make the proxy decision auditable.

## Why

The Llama-3.1-8B run in `data/tokenizer_audit/official/20260430T033208Z__meta-llama_Llama-3.1-8B.json` returned `no_go` solely on `byte_fallback_or_proxy_rate = 0.193`, while `tokens_per_word = 2.474` (pass) and `explicit_byte_fallback_rate = 0.0` (pass). The proxy rule (`len(stripped)==1 and ord(stripped)>127` after stripping `▁Ġ `) was authored for SentencePiece+byte-fallback tokenizers. Llama-3 is byte-level BPE (tiktoken family); every multi-byte UTF-8 char (ʻokina, kahakō vowels) is encoded as a sequence of bytes from the GPT-2 byte-to-unicode map, all `ord>127`. The pieces are **lossless**, not fallback. Tokens/word at 2.47 is itself the disconfirming signal for true 19% fragmentation.

## Plan

### 1. Detect tokenizer family from the tokenizer, not the model id

Compute once per run, store under `model.tokenizer_family`:

- `byte_level_bpe` if the GPT-2 byte-to-unicode map's 256 byte-chars are a subset of the vocab and there are no `<0xXX>` tokens. (Llama-3, GPT-2/4, Qwen2.)
- `sentencepiece_byte_fallback` if `<0xXX>` byte-fallback tokens are in the vocab or `sp_model` is present with byte_fallback enabled. (Llama-2, Mistral, Gemma, T5 variants.)
- `wordpiece` / `unigram` / `other` otherwise.

Hard-coding by `model_id` is wrong: Llama-2 vs Llama-3 share a name and not a tokenizer.

### 2. Make `byte_fallback_or_proxy_rate` family-aware

| Family | `explicit_byte_fallback_rate` | `byte_fallback_or_proxy_rate` |
|---|---|---|
| `sentencepiece_byte_fallback` | evaluated, threshold = 0 | evaluated, threshold ≤ 0.01 (current) |
| `byte_level_bpe` | evaluated (structurally 0; informational) | **`status: not_evaluated`** + reason `"byte-level BPE: byte-pieces are lossless, not fallback"` |
| `wordpiece` / `unigram` / `other` | evaluated | evaluated, threshold ≤ 0.01 |

This mirrors how `high_diacritic` already uses a `status` field instead of a fake number. Do not silently pass; explicitly mark not-evaluated and exclude it from `blocking_reasons`.

### 3. Add round-trip as ground truth (all families)

Two cheap invariants, both must hold for `go`:

- **Slice round-trip:** `tokenizer.decode(all_ids, skip_special_tokens=True) == NFC(text)` (or differs only by documented whitespace/special-token policy — record diffs verbatim if any).
- **Per-piece round-trip:** `decode([id])` returns non-empty UTF-8 for every id; for byte-level BPE, the concatenation of `decode([id])` over consecutive byte-pieces reproduces the original UTF-8 substring.

Add a check `roundtrip_lossless` with threshold "must be true". For byte-level BPE this **replaces** the proxy check as the structural integrity gate. For SentencePiece+byte-fallback it is an additional cross-check (catches normalizer surprises, NFC drift, special-token leakage).

### 4. Debug dump (auditable proxy decision)

Always write, alongside `report.json`:

`samples.debug.jsonl` — one row per sample, fields:

```
{
  "sample_id": "...",
  "sentence": "...",                       // NFC text
  "ids": [int, ...],
  "pieces": [str, ...],                    // convert_ids_to_tokens
  "piece_decoded": [str, ...],             // decode([id]) per piece
  "piece_byte_lens": [int, ...],           // len(decode([id]).encode("utf-8"))
  "is_byte_level_bpe_piece": [bool, ...],  // every char in byte-to-unicode map
  "is_explicit_byte_fallback": [bool, ...],// matches <0xXX>
  "is_legacy_proxy_flag": [bool, ...],     // current heuristic, retained for diff
  "roundtrip_ok": bool,
  "decoded_equals_nfc_text": bool
}
```

Plus a `tokenizer.fingerprint.json` aggregate:

```
{
  "tokenizer_family": "byte_level_bpe" | "sentencepiece_byte_fallback" | ...,
  "byte_to_unicode_coverage": 256/256,
  "has_0xXX_vocab": false,
  "sp_model_present": false,
  "vocab_size": int,
  "tokenizer_sha256": "...",
  "tokenizer_fingerprint_sha256": "..."
}
```

The current report's null `tokenizer_sha256` / `tokenizer_fingerprint_sha256` / `model_repo_sha` must be populated; that is part of the cleanup, not optional.

Minimum live debug coverage: ≥5 sentences with both ʻokina (U+02BB) and kahakō vowels from `kaehuikimanoopuuloa.jsonl`.

### 5. Reporting changes

- `checks[*]` for non-evaluated metrics must use `passed: null` and `status: "not_evaluated"`, and must **not** appear in `blocking_reasons`. Current code adds `passed is None` to `blocking_reasons` (`test_tokenizer_audit.py:118-122`); fix that — `None` means "not evaluated", not "failed".
- `recommendation.blocking_reasons` must list only checks with `passed is False`.
- Add `recommendation.notes` capturing the family-aware decision (e.g. `"byte_fallback_or_proxy_rate not evaluated: byte-level BPE; round-trip lossless verified instead"`).

## Thresholds — do **not** change

Frozen per canonical decisions.md (Rusty / Issue #8):

- `overall_tokens_per_word_max = 2.50`
- `high_diacritic_tokens_per_word_max = 3.25`
- `explicit_byte_fallback_rate_max = 0.0` (where applicable)
- `byte_fallback_or_proxy_rate_max = 0.01` (SentencePiece+byte-fallback / unigram / wordpiece only)
- standalone diacritic chars ≤ 2 tokens
- minimum input: ≥1,500 words, ≥10 high-diacritic samples

The Llama-3.1-8B `no_go` is a harness bug, not a threshold problem. Loosening `byte_fallback_or_proxy_rate_max` would also hide real fragmentation on a future SentencePiece run; that is exactly the wrong fix.

## Owners / Boundaries

- **Linus:** owns harness/test code changes (`code/tests/test_tokenizer_audit.py`, any helper module). Round-trip + family detection + debug dump + `not_evaluated`-vs-`False` fix.
- **Rusty (me):** family-detection rules, round-trip semantics, threshold stance, debug-dump field list — above.
- **Basher:** keeps `code/configs/llama31_8b_a100.json` blocked until a clean re-run reports `go` with populated tokenizer/model SHAs.
- **Coordinator:** route the harness change to Linus; do not route it back to me for revision unless an NLP question reopens.

## Acceptance

A re-run of `test_smoke_tokenizer_audit` against `meta-llama/Llama-3.1-8B` on `kaehuikimanoopuuloa.jsonl` should produce:

- `tokenizer_family: "byte_level_bpe"`
- `explicit_byte_fallback_rate: 0.0` (passed)
- `byte_fallback_or_proxy_rate: status=not_evaluated` (excluded from blockers)
- `roundtrip_lossless: true` (passed)
- `overall_tokens_per_word: ~2.47` (passed)
- `recommendation.decision: go` (high-diacritic + diacritic-chars slices still need to be populated separately before final go; that's a slice-coverage task, not a tokenizer-family task)
- `tokenizer_sha256`, `tokenizer_fingerprint_sha256`, `model_repo_sha` all non-null
- `samples.debug.jsonl` written with ≥5 ʻokina+kahakō sentences

If round-trip fails on Llama-3 against the Hawaiian slice, that is a real `no_go` and I want to see the debug dump before recommending anything else.



---

## Decision: Basher — Standalone tokenizer audit script removed; gate remains

**Date:** 2026-04-29  
**Owner:** Basher (Training Engineer)  
**Status:** Recorded — direction set by user

### Direction

- The standalone tokenizer audit script `scripts/040_tokenizer_audit.py` has been removed at user request.
- A tokenizer audit will be added back as a **test** (not a standalone script). Implementation pending.
- The Stage-0 tokenizer-audit gate for Llama-3.1-8B (Issue #8) remains an open spend gate. Thresholds, fingerprint requirements, and "do not fabricate" stance recorded in this decisions.md (Rusty entry) still apply; only the implementation surface changed.
- Repo docs that previously instructed users to run `python3 scripts/040_tokenizer_audit.py ...` have been reworded to describe the gate and its planned test, without claiming the audit is complete.
- `code/configs/llama31_8b_a100.json` remains blocked pending a real `go` report and frozen tokenizer/model SHA in the Stage-1 manifest.

### Notes for other agents

- Rusty: the audit gate is still yours; expect to provide thresholds and the test harness when the tokenizer-audit test is authored.
- Linus: representative sample sourcing (nūpepa / Baibala / manual eval slices, NFC + U+02BB canonicalized) is unchanged.
- Coordinator: no orchestration change; #8 stays open.


---

## Decision: Frank — Hawaiian Wikisource quality=4 (Validated) eval-candidate scan

**Date:** 2026-04-29T22:56Z  
**Owner:** Frank (Hawaiian Data Collector)  
**Status:** Team recorded — additive eval scan; zero-volume result; no replacement of existing data

### Context

User asked: "ok lets fetch the quality level 4 data for eval, i want to see how much data is there." Per the standing user directive (2026-04-29T21:27:53Z), do not replace existing W1/Stage 1/hawwikisource data; treat any found Wikisource Validated material as new eval-candidate data.

### Execution Summary

Added one-off script `scripts/106_scan_hawwikisource_quality4.py` that reads existing `data/local/hawwikisource/page_plan.jsonl` (159 ns=0 rows, read-only) and runs a MediaWiki transclusion-walk (`prop=templates&tlnamespace=104`) to discover every Page: subpage transcluded into each main-namespace page. For each unique Page: title, batches `prop=proofread` queries (50/call, 1.5s rate limit, 429-aware backoff) and filters for `quality_text == "Validated"`.

### Result

**End-to-end scan of all 159 Hawaiian main-namespace pages: zero Validated rows found.**

| Count | Value |
|-------|-------|
| main_ns pages inspected | 159 |
| unique Page: titles discovered | 0 |
| proofread queries issued | 0 |
| validated (q=4) rows | 0 |
| chars / bytes / tokens | 0 / 0 / 0 |

Confirmation probes:
- `Category:ʻŌlelo Hawaiʻi` with `cmnamespace=104` → 0 members
- `Category:ʻŌlelo Hawaiʻi` with `cmnamespace=106` (Index:) → 0 members
- `srsearch=haw, srnamespace=104` returns language false positives, no Hawaiian presence

### Data Integrity

Existing data preserved (byte-for-byte):
- `data/raw/hawwikisource/fetch.jsonl` (42 rows)
- `data/local/hawwikisource/page_plan.jsonl` (159 rows)
- W1 ledger, Stage 1 manifest, eval hashes

New local-only artifacts (gitignored):
- `data/raw/hawwikisource_quality4_candidates/20260429/manifest.json`
- `data/raw/hawwikisource_quality4_candidates/20260429/per_main_stats.jsonl` (159 rows)
- `data/raw/hawwikisource_quality4_candidates/20260429/validated_pages.jsonl` (0 rows)
- `data/raw/hawwikisource_quality4_candidates/20260429/all_quality_rows.jsonl` (0 rows)
- `data/raw/hawwikisource_quality4_candidates/20260429/content/` (empty)

### Decision / Method Note

**Validated Hawaiian Wikisource material reachable today is 0 rows / 0 chars / 0 tokens.** This quantitatively confirms the 2026-04-29T21:34Z metadata-only finding. The transclusion-walk path is sound and will auto-populate if Hawaiian contributors add Index:/Page: scans. For immediate eval sourcing, W1 candidates must come from hand-authored or other pipeline sources.

### What Was Not Done

- No changes to scripts/102 or scripts/202 (existing quality metadata capture is correct)
- No promotion into W1 candidate ledger (nothing to promote)
- No data committed; all artifacts gitignored under `/data/`
- No new dependencies added; script uses stdlib only


---

## Decision: Linus — Quality-4 Wikisource fetch is count-only; eval contract established

**Date:** 2026-04-29T22:58Z  
**Owner:** Linus (Data Engineer)  
**Status:** Team approved — reconnaissance only; no W1 TSV/eval ledger writes; non-replacement policy honored

### Context

Frank's quality-4 scan is volume reconnaissance, not eval ingest. Any future Validated rows discovered require an established safety contract.

### Scope

**Count-only pass:**
1. Frank's fetch produces local artifact enumerating `proofread_quality == 4` Hawaiian Wikisource items
2. **No W1 rows created; no ledger writes; no TSV mutations**
3. Non-replacement per standing user directive: all returned rows are new artifacts; equivalence to existing Wikisource rows is a later dedupe concern, not this pass
4. Quality-4 is necessary signal for W1 candidate, not sufficient; acceptance requires Hawaiian-literate review (#7)
5. Any surfaced candidates remain `eval_consumable=false`, `prototype_local=true` if/when entering ledger as candidates

### Required Fields (Future Candidates)

When Frank's fetch surfaces candidates, local manifest (suggested: `data/evals/manual_w1/wikisource_quality4_candidates.jsonl`, gitignored) must carry:

- `source_url`, `page_title`, `page_id`, `revision_id` (MediaWiki metadata)
- `namespace` (truthful ns: 0 for main, 104 for Page:)
- `proofread_quality` (must equal 4), `quality_text` (must equal "Validated")
- `sha256_normalized` (SHA-256 over UTF-8 NFC-normalized text), `normalization_method` ("NFC"), `hash_method` ("sha256")
- `candidate_stage` ("eval-candidate"), `candidate_split` ("w1_candidate")
- `eval_consumable` (false), `prototype_local` (true), `release_eligible` (false)
- `origin_hint` ("wikisource_validated"), `fetched_at` (ISO-8601 UTC)

### Invariants Preserved

- `train ∩ eval_hashes = ∅` unaffected (no ledger writes this pass)
- `data/evals/eval_hashes.jsonl` schema unchanged (eval-hashes-jsonl-v1)
- Existing `data/raw/hawwikisource/fetch.jsonl` not replaced; new outputs additive

### Out of Scope This Pass

- No ledger writes to `data/evals/eval_hashes.jsonl`
- No W1 TSV writes to canonical `w1-haw-micro-eval.tsv`
- No new helper scripts (e.g., scripts/316_seed_w1_from_wikisource.py); lands only after count known and motivation clear
- No documentation changes; existing eval_pipeline.md already documents Validated→W1-candidate semantics

### Status

Ready to receive Frank's candidate manifest. Count and ns=0 vs ns=104 split will inform feasibility of transclusion walking before seeding.

**Open:** Coordinator clarification owed on whether wikisource-derived candidates can flip to W1 `accepted` (#7), or remain a separate `W1-wikisource` slice.


---

## User Directive Consolidation: Squad:Yashas & Issue #4 (2026-04-29T05-07–12-13Z)

**Date:** 2026-04-29
**By:** yashasg (via Copilot)
**Status:** Merged; enforced across Frank/Linus/Rusty/Basher batch

### Directives

1. **2026-04-29T05:07:32Z:** Things assigned to `yashasg` can be marked with `squad:yashas`; Squad should ignore those.
2. **2026-04-29T05:16:38Z:** Do not wait for user input while user is away; continue Ralph loop, skip `squad:yashas` work, process available Squad-owned work.
3. **2026-04-29T11:25:22Z:** Prefer implementation instructions at top of scaffold files instead of README as primary nav.
4. **2026-04-29T12:13:37Z:** Anything marked `squad:yashas` is human-owned and should be ignored by Squad unless explicitly requested. Issue #4 has `squad:yashas` and is assigned to yashasg; do not work on it.

### Application to Stage 2 Batch

All four Stage 2 agents (Frank, Linus, Rusty, Basher) explicitly deferred issue #4 (runtime training-loader contamination guard). #4 is marked `squad:yashas` and assigned to yashasg; Squad does not touch it. Manifest builder, manifest reader, emitter, and quality scorer all operate on artifacts only; no training-loop imports.

**Outcome:** Directive honored; no Squad overreach into Squad:Yashas territory.



---

## Decision: Basher — Stage 1 local manifest + trainer JSONL convention (Issue #6)

**Date:** 2026-04-29
**Owner:** Basher (Training Engineer)
**Status:** Team approved

Until a `pyarrow` dependency is explicitly accepted, `scripts/301_build_stage1_dataset.py` emits the Stage 1 manifest as stdlib JSONL at `data/stage1/stage1_manifest.jsonl`, not Parquet. The trainer-facing pre-tokenization pack is `data/stage1/stage1.jsonl.gz`; the token-volume gate report is `data/stage1/token_target_report.json`.

**Rationale:** This keeps the local Stage 1 build runnable with the current repo dependencies while preserving an exact schema contract via `--print-schema` and build-time validation. Corpus payloads remain under gitignored `data/`; no raw or trainer text is committed.

**Implications:**
- Training configs may point at `data/stage1/stage1.jsonl.gz` for local Stage 1 CPT runs.
- Tokenized `.bin` / `.npy` packing remains a later tokenizer-dependent step after Rusty's tokenizer audit.
- Parquet promotion is a follow-up dependency decision, not a blocker for issue #6.


---

## Decision: Linus — Canonical eval-hash ledger + FineWeb-2 split policy (Issues #2–#3)

**Date:** 2026-04-29
**Owner:** Linus (Data Engineer)
**Status:** Team approved

For the prototype, the canonical eval-hash contamination ledger is JSONL at `data/evals/eval_hashes.jsonl`. Each held-out hash row must carry at minimum: `schema_version`, `sha256_normalized`, `hash_method=sha256`, `normalization_method=NFC`, `origin`, `stage=eval-only`, `division`, `split`, `row_id`.

**FineWeb-2 split policy:** `scripts/310_split_dedupe_fineweb2_haw.py` owns the FineWeb-2 `haw_Latn` split/dedupe contract:
- Official test rows: 887
- Requested split: 70% dev / 30% holdout
- Rounding rule: `floor(test_rows * dev_ratio + 0.5)`
- Target counts: 621 dev, 266 holdout
- Split method: sort test rows by seeded stable row-id plus NFC-normalized text hash, take first target count as dev and remainder as holdout
- Division membership is by stable row id
- Contamination hashing is SHA-256 over NFC-normalized text
- Manifest must record requested ratio, target counts, actual counts, seed, split method, normalization method, and invariant checks including `train ∩ eval_hashes = ∅`

**Impact:** FineWeb-2, W1 manual eval, Stage 1, and Stage 2 contamination checks now point at the same ledger contract. Parquet is a future optional mirror only; if implemented, it must be derived from JSONL, not a second source of truth.


---

## Decision: Rusty — Stage-0 tokenizer audit gate for Llama-3.1-8B (Issue #8)

**Date:** 2026-04-29
**Owner:** Rusty (NLP Researcher)
**Status:** Team approved

Use a local-only tokenizer audit (a tokenizer-audit test is planned; no standalone audit script lives in the repo today) as the lightweight, no-spend audit path before any serious Llama-3.1-8B Stage-1 spend. Reports are written under ignored `data/tokenizer_audit/` and must record: model id, resolved model repo SHA when available, tokenizer fingerprint SHA-256, input sample paths/sources, overall metrics, high-diacritic slice metrics, and a `recommendation.decision` of `go` or `no_go`.

**Default no-spend gate policy:**
- Minimum sample coverage: at least 1,500 words and 10 high-diacritic samples
- High-diacritic sample definition: `ʻokina + kahakō >= 3` and `diacritics/word >= 0.25`
- Go thresholds: overall tokens/word ≤ 2.50; high-diacritic tokens/word ≤ 3.25; explicit `<0x..>` byte fallback rate = 0; combined byte-fallback/proxy token rate ≤ 1%; standalone Hawaiian diacritic chars tokenize to ≤2 tokens each
- Any miss is `no_go` for serious 8B Stage-1 spend until a fallback tokenizer is audited or a vocab/embedding policy is chosen

**Notes for other agents:**
- The audit must fail loudly with actionable install/login instructions if `transformers` is missing or gated Hugging Face Llama access is unavailable. Do not fabricate audit results.
- Basher: treat `code/configs/llama31_8b_a100.json` as blocked until a real report says `go` and its tokenizer/model SHA fields are frozen in the Stage-1 manifest.
- Linus: sample rows should come from local ignored data and cover nūpepa, Baibala, and contemporary/manual eval slices where possible.


---

## Decision: Linus — FineWeb-2 Stage-1 prototype cleaning policy (Issue #5)

**Date:** 2026-04-29
**Owner:** Linus (Data Engineer)
**Status:** Team approved

FineWeb-2 `haw_Latn` rows fetched by `205` and split/deduped by `310` are still raw web rows. Stage-1 training JSONL must be gated by `301_build_stage1_dataset.py` before use.

**Prototype cleaning policy in `301`:**
- Normalize all training text to Unicode NFC
- Canonicalize likely Hawaiian ʻokina variants (U+2018, U+2019, U+02BC, backtick, ASCII apostrophe in Hawaiian-letter context) to U+02BB
- Split FineWeb rows into paragraphs and re-gate each paragraph with the current cheap Hawaiian heuristic
- Drop timestamp/synopsis/navigation/ad/social-widget/URL-heavy boilerplate paragraphs
- Drop exact repeated normalized paragraph fingerprints after first sighting as a template-removal prototype
- Reject rows with no surviving paragraphs or with a failing row-level post-clean Hawaiian score
- Report raw and cleaned token counts, row/paragraph reject reason counts, diacritic density, and source/register token summaries under ignored `data/` outputs

**Local run result (621-dev / 266-holdout FineWeb split):**
- FineWeb rows seen: 95,507
- FineWeb rows rejected by cleaning: 6,528
- Raw vs cleaned Stage-1 train tokens: 59,534,611 → 44,067,289 (26.1% reduction)
- FineWeb train slice: 79,812 rows; raw 59,290,760 vs cleaned 43,843,711 tokens

**Follow-up:** Near-duplicate handling beyond exact text and repeated paragraphs is planned: build MinHash/LSH signatures over cleaned FineWeb + `hawwiki` + `hawwikisource` paragraphs/docs, persist cluster IDs, enforce cluster-aware eval/final isolation.


---

## Decision: Rusty — W1 manual eval local hash policy (Issue #7)

**Date:** 2026-04-29
**Owner:** Rusty (NLP Researcher)
**Status:** Proposed for team approval

W1 manual micro-eval rows remain local/off-git at `data/evals/manual_w1/w1-haw-micro-eval.tsv`. The eval-hash ledger remains the canonical JSONL file at `data/evals/eval_hashes.jsonl`.

**`manual_w1` ledger rows use:**
- `schema_version=eval-hashes-jsonl-v1`
- `origin=manual_w1`
- `stage=eval-only`
- `division=evals`
- `split=w1` for accepted rows; local draft preflight rows use their review status as split
- `row_id=<item_id>`
- SHA-256 over UTF-8 bytes of NFC-normalized `prompt + U+000A + reference`

**W1 TSV categories:** `okina_survival`, `kahako_retention`, `unicode_nfc`, `tokenizer_survival`, `generation_sanity`. Harness slices consume `category`, `diacritic_density`, and derived `diacritic_density_bin` (`none` = 0, `low` = 1–2, `medium` = 3–5, `high` ≥ 6).

**Guardrail:** `scripts/315_hash_manual_w1_eval.py` hashes only `review_status=accepted` rows by default. The explicit `--include-draft-for-local-ledger` path is local contamination preflight only; non-accepted ledger rows are marked `eval_consumable=false` and `prototype_local=true` and must not be reported as eval results.

**Rationale:** Reviewed Hawaiian rows require human review. The project can validate the local path, Unicode checks, category/slice contracts, and contamination ledger wiring with clearly marked draft rows while avoiding a fabricated public benchmark.


---

## Decision: Linus — Stage-2 manifest contract (Issue #11)

**Date:** 2026-04-29
**Owner:** Linus (Data Engineer)
**Status:** Team approved

For the private prototype, the canonical Stage-2 manifest artifact is JSONL at `data/stage2/stage2_manifest.jsonl`. Any Parquet form is a future derived mirror only and must not become a parallel source of truth.

**Contract details:**
- `scripts/320_build_stage2_manifest.py --print-schema` is the schema surface for downstream consumers
- `scripts/330_emit_stage2_sft_jsonl.py` consumes `stage2_manifest.jsonl` and emits `data/stage2/stage2_sft.jsonl` by default
- `release_eligible` remains in manifest and SFT JSONL provenance; private prototype rows default to `prototype_only=true`, `release_eligible=false`
- Schema/enforcement: `prototype_only=true ⟹ release_eligible=false` is enforced as a schema/check violation
- Raw/generated artifacts stay under ignored `data/`


---

## Decision: Danny — Prototype issue closure review policy (Issue #9 Epic closure)

**Date:** 2026-04-29T13:15:04Z
**Owner:** Danny (Lead / Architect)
**Status:** Team approved

For the Ralph review loop, classify issues by prototype acceptance, not production/release completeness:

1. **READY_TO_CLOSE:** Issue acceptance criteria satisfied by local artifacts and smoke validation for private prototype. Does **not** imply public-release readiness, legal/cultural clearance, or GPU budget permission.

2. **BLOCKED_HUMAN_REVIEW:** Remaining gate is Hawaiian-literate judgement or external gated access, not repo work. Do not fabricate benchmark rows (#7) or tokenizer audit results (#8).

3. **Stage-2 skeleton/source-plan work can close** when contract, schema, docs, and smoke tests are internally consistent, even with zero real Stage-2 rows. Trade-off: faster evolutionary architecture now, explicit follow-up issues for adapters/fetching later.

4. **Do not close skeleton issue when contract is internally inconsistent.** Hold #11 (and therefore #9) until Stage-2 JSONL-first manifest contract is reconciled across docs/scripts (stage2_manifest.jsonl vs stale parquet references, output naming, release_eligible tension).

**Application:** Issue #9 epic and all sub-issues (#10–#14) closed after Linus reconciled Stage-2 contract. #11 validation: py_compile 320/321/330, `320 --dry-run --print-schema`, targeted stale-name grep all passed.


---

## Decision: Frank — Hawaiian Wikisource ProofreadPage quality capture (W1 signal)

**Date:** 2026-04-29T21:34:03Z
**Owner:** Frank (Hawaiian Data Collector)
**Status:** Proposed for team awareness — fetch-side change only; eval-side unchanged

### Findings

Hawaiian Wikisource (on multilingual `wikisource.org`) has ProofreadPage extension enabled. The extension exposes per-page quality via `action=query&prop=proofread` returning `{quality: 0..4, quality_text: "Without text" | "Not proofread" | "Problematic" | "Proofread" | "Validated"}`. **`quality_text == "Validated"` (quality 4) is the natural W1 signal.**

**Critical caveat:** `prop=proofread` is **only meaningful on `ns=104` (`Page:`) pages**. For `ns=0` (main) pages, the API returns no `proofread` key. Main-page quality is rendered client-side by aggregating `Page:` subpages. The Hawaiian category `Category:ʻŌlelo Hawaiʻi` today contains **159 main-ns pages and 0 `Page:`-ns pages**. Thus, **no Hawaiian Wikisource page in the existing 102 plan can be tagged Validated by direct API lookup**; proofread fields will populate `null` on every current row. A future transclusion-walk is the only way to get real W1 on existing main-ns pages.

### What Changed (Fetch Side Only)

1. **`scripts/102_collect_hawwikisource.py`** — after `--enumerate`, runs batched `prop=proofread&pageids=...` follow-up (50/chunk, polite rate-limit) and writes `proofread_quality` (int|null) and `proofread_quality_text` (str|null) onto every `page_plan.jsonl` row. `ns=0` uniformly get `null` (truthful). `ns=104` get the real quality.
2. **`scripts/202_fetch_hawwikisource_raw.py`** — MediaWiki content URL now requests `prop=revisions|proofread` (one combined call, no extra HTTP). Records quality per `ProvenanceRecord.source_specific_ids`. Forward seeded values from 102 under `*_seeded` keys; live fetch-time value remains source of truth.
3. **`docs/data-pipeline.md`** — documented new fields, mapped `quality_text=="Validated"` to W1, documented ns=0 vs ns=104 limitation.

### Validation

- `py_compile` passed for 102/202
- Dry-run + small real enumerate (3 rows, ns=0,104) showed schema uniformity, null handling on ns=0
- Existing `page_plan.jsonl` preserved

### What I Did NOT Do

- Did not modify eval/W1 extraction — Linus's call
- Did not implement transclusion walks for Page-ns aggregation
- Did not auto-promote Validated rows
- Did not change `--namespaces` defaults


---

## Decision: Linus — Validated/proofread Wikisource as W1 candidates only

**Date:** 2026-04-29T21:34:03Z
**Owner:** Linus (Data Engineer)
**Status:** Proposed — needs Frank (adapter metadata) and Coordinator (review owner)

### Finding

1. **W1 today is hand-authored probes**, not arbitrary clean text. The five categories (`okina_survival`, `kahako_retention`, `unicode_nfc`, `tokenizer_survival`, `generation_sanity`) are *failure-mode probes*. A validated Wikisource paragraph measures something else (general PD reading), so it does not map 1:1 onto W1's accepted-row contract.
2. **Adapters do not currently fetch ProofreadPage metadata.** `scripts/102` and `scripts/202` enumerate via `list=categorymembers` and never request `prp_quality_level` / `prop=proofread`. The `ProvenanceRecord` JSONL on `data/raw/hawwikisource/fetch.jsonl` therefore carries no `proofread_status` field, nor does `data/stage1/stage1_manifest.jsonl` (159 hawwikisource rows; zero proofread keys). Frank owns this fetch-shape change.
3. **Contamination is the bigger risk.** Hawaiian Wikisource already feeds Stage 1 training. Promoting any Wikisource snippet to W1 must simultaneously remove that exact NFC text from `stage1.jsonl.gz` and append its SHA-256 to `data/evals/eval_hashes.jsonl` before the next Stage 1 build, or we break `train ∩ eval_hashes = ∅`.

### Recommendation

**Treat validated/proofread Wikisource snippets as W1 _candidates_, not W1 accepted rows.**

- `proofread_status = 4` ("validated", two reviewers) → eligible as W1 *candidate*, ledgered with `review_status=draft`, `eval_consumable=false`, `prototype_local=true`, `origin=manual_w1`, `split=w1_candidate`.
- `proofread_status = 3` ("proofread", one reviewer) → eligible **only as preflight contamination-check input**, never as candidate, because single-reviewer text on multilingual Wikisource is not Hawaiian-literate reviewed for our purpose.
- `proofread_status ≤ 2` → ignore.
- Promotion to `review_status=accepted` (real W1) still requires Hawaiian-literate reviewer assignment from #7. Proofread flag is *necessary*, not sufficient.

### Implementation Shape (After Frank Lands Metadata)

1. **Frank — adapter (out of scope this pass):** extend 102/202 to request ProofreadPage quality (`action=query&prop=proofread` or `prp_quality_level`). Persist `proofread_status ∈ {0,1,2,3,4}` on `data/raw/hawwikisource/fetch.jsonl` rows and `page_plan.jsonl` lines.
2. **Linus — surface in Stage 1 manifest:** once `fetch.jsonl` carries `proofread_status`, add it to `data/stage1/stage1_manifest.jsonl` row provenance in `301_build_stage1_dataset.py`. Reporting only; no filtering yet.
3. **Linus — new helper `scripts/316_seed_w1_from_wikisource.py`:**
   - Reads `data/raw/hawwikisource/fetch.jsonl` or cleaned wikisource slice from 301
   - Selects rows with `proofread_status == 4`
   - Extracts short snippets (1–2 sentences, ≤~200 NFC chars) suitable for W1 categories (primarily `kahako_retention`, `okina_survival`, `unicode_nfc`)
   - Writes `data/evals/manual_w1/w1-haw-micro-eval.candidates.tsv` (gitignored) with `review_status=draft` and `author=wikisource-validated-{revid}`
   - Hashes candidate rows via `315_hash_manual_w1_eval.py` `--include-draft-for-local-ledger` with `split=w1_candidate`, `eval_consumable=false`
4. **Linus — pre-promotion contract** (gating reviewer accept):
   - Asserts candidate's NFC SHA-256 is **not** in current Stage 1 train pack
   - On reviewer flip to `accepted`, migrates from `candidates.tsv` to canonical `w1-haw-micro-eval.tsv` and re-hashes under `split=w1`

### Asks

- **Frank:** confirm whether ProofreadPage quality is reachable for our `Category:ʻŌlelo Hawaiʻi` enumeration, or whether we'd need an Index/Page namespace walk.
- **Coordinator / #7 owner:** confirm whether Hawaiian-literate reviewers may flip wikisource-derived candidates to `accepted`, or whether W1 stays hand-authored only.


---

## User Directive: Non-replacement data policy for Wikisource-derived work

**Date:** 2026-04-29T21:27:53Z
**By:** yashasg (via Copilot)
**Status:** Team guidance — captured for future Wikisource fetches

Do not replace existing data when fetching or deriving Wikisource proofread/validated material. If found, treat it as new data unless a later dedupe pass validates equivalence.


---

## User Directive: PowerPoint deferral; Markdown journey doc preferred

**Date:** 2026-04-29T13:51:01-07:00
**By:** yashasg (via Copilot)
**Status:** Active guidance

Do not work on PowerPoint yet. Maintain a Markdown file documenting the project journey and decisions (e.g., `docs/prototype-journey-data-factcheck.md`).


---

## User Directive: VS Code IDE context

**Date:** 2026-04-29T13:51:45-07:00
**By:** yashasg (via Copilot)
**Status:** Context capture — for workflow and docs framing

The user is using VS Code as their IDE. Capture for future project journey notes and workflow/docs framing.


---

## Decision: Rusty — Tokenizer-audit input slice shape & `human_fetch.md` suitability

**Date:** 2026-04-30  
**Owner:** Rusty (NLP Researcher)  
**Status:** Team recorded — canonicalized from inbox

### TL;DR

`data/raw/ulukau_nupepa/human_fetch.md` is **useful** as one tokenizer-audit slice (Ulukau / Hoʻolaupaʻi-flavored Hawaiian, plausibly native-speaker authored/translated, already NFC-clean ʻokina at U+02BB and kahakō present), but it is **not** by itself sufficient to clear the gate, and it is **not** W1/eval material until separately reviewed. Linus owns conversion.

### Recommended minimum input shape for the audit test harness

The future `code/tests/test_tokenizer_audit.py` should consume a per-source slice file under `data/tokenizer_audit/` (off-git). Two formats, in priority order:

1. **JSONL (preferred).** One sample per line:
   - `id` (string, stable, e.g. `ulukau_nupepa-20260429-haw-001`)
   - `text` (string, **NFC**, ʻokina canonicalized to **U+02BB**, kahakō preserved as combining-mark NFC composites)
   - `source` (string, e.g. `ulukau_nupepa/human_fetch.md`)
   - `lang` (string, `haw` or `eng`; tokenizer audit consumes only `lang=haw`)
   - `is_high_diacritic` (bool, computed: `okina+kahakō ≥ 3` AND `diacritics/word ≥ 0.25`, per the canonical gate definition in decisions.md)
   - Optional: `notes`, `provenance` (e.g. `human_fetch`, `wikisource`, `manual_w1`)
2. **TXT fallback.** One paragraph per blank-line-separated block; the harness must paragraph-split, NFC-normalize, ʻokina-canonicalize, and compute `is_high_diacritic` itself. Use only when JSONL conversion is impractical.

The harness then aggregates `overall.*` and `high_diacritic.*` (`tokens_per_word`, `explicit_byte_fallback_rate`, `byte_fallback_or_proxy_rate`) and writes a report under ignored `data/tokenizer_audit/` that includes input sample paths/sources and tokenizer fingerprint SHA-256 — exactly per the existing canonical decision (decisions.md, Rusty entry for Issue #8). No threshold or fingerprint changes are proposed here; only the input shape.

### Suitability of `human_fetch.md` as an audit slice

- **Use as:** one Hawaiian-newspapers-flavored tokenizer-audit slice. The Hawaiian paragraph is short (~90–100 words) and contains rich ʻokina + kahakō (`ʻŌlelo`, `Hawaiʻi`, `nā`, `paʻi`, `huaʻōlelo`, `Hoʻolaupaʻi`, `Pīhopa`, `kūikawā`, `Māori`), which is exactly the high-diacritic stress profile the gate cares about.
- **Conversion (Linus):** split the file into two records by markdown heading; emit only the `# Hawaiian` block as `lang=haw`, drop the `# English` block from audit aggregation (or keep with `lang=eng` for sanity but exclude from Hawaiian metrics). NFC + ʻokina-canonicalize; the file already appears U+02BB-clean but normalize defensively.
- **Caveats — bright line:**
  - **Volume.** ~95 Hawaiian words is **far below** the gate's `≥1,500 words` and `≥10 high-diacritic samples` minimums. This file is one contributing slice, not a standalone gate input. The gate must still aggregate against `data/stage1/stage1.jsonl.gz` and the W1 micro-eval per docs/eval_pipeline.md §3.
  - **Not eval.** "Likely native-speaker / translated" is encouraging for tokenizer stress-testing but is **not** verified W1/eval data. Do **not** hash this into `data/evals/eval_hashes.jsonl`, do not promote to W1, and do not report as eval signal until Hawaiian-literate review per the W1 contract (decisions.md, manual W1 entry).
  - **Provenance.** Source is a manual fetch from Ulukau collection metadata; the licensing/attribution status of the prose itself should be confirmed before any non-local distribution. For local tokenizer audit only, this is fine.
  - **Bilingual contamination risk.** Keep English and Hawaiian in separate records so English tokens cannot inflate or deflate Hawaiian tokens/word.

### Alignment with existing test stub

`code/tests/test_tokenizer_audit.py` today is a placeholder smoke that loads a Qwen tokenizer via `llm_hawaii.data.load_tokenizer` and does not exercise the gate. When Linus authors the real test, the JSONL shape above is what it should consume; no changes to the stub are proposed in this task (Linus owns code conversion, and the canonical model under audit is still Llama-3.1-8B per decisions.md, not Qwen).

### Notes for other agents

- **Linus:** please convert `data/raw/ulukau_nupepa/human_fetch.md` into a JSONL slice under `data/tokenizer_audit/ulukau_nupepa/` (off-git) using the shape above, splitting by language heading and emitting NFC + U+02BB-canonical text. Treat as tokenizer-audit input only; do not route into Stage 1 ingest or eval ledger from this path.
- **Frank / W1 owners:** unchanged. This file is not W1.


---

## Decision: Linus — Ulukau/Nupepa human_fetch as tokenizer-audit candidate

**Date:** 2026-04-30  
**Owner:** Linus (Data Engineer)  
**Status:** Team recorded — canonicalized from inbox

### What

Converted `data/raw/ulukau_nupepa/human_fetch.md` (user-pasted Ulukau Hawaiian newspapers collection landing copy: English paragraph + Hawaiian paragraph) into a normalized tokenizer-audit input artifact.

### Where

Local-only, ignored per `/data/` rule:

- `data/tokenizer_audit/ulukau_nupepa/human_fetch.jsonl` (2 records)
- `data/tokenizer_audit/ulukau_nupepa/human_fetch.haw.txt`
- `data/tokenizer_audit/ulukau_nupepa/human_fetch.txt`
- `data/tokenizer_audit/ulukau_nupepa/README.md`
- Helper: `scripts/_convert_ulukau_human_fetch.py` (uncommitted, idempotent).

Aligned with Rusty's Stage-0 tokenizer-audit gate convention that audit inputs/reports live under ignored `data/tokenizer_audit/`.

### Policy (binding for downstream consumers)

- `audit_use = tokenizer_audit_candidate`, `audit_only = true`.
- **Not** Stage-1 eligible. **Not** eval-eligible. **Not** W1.
  **Not** training-eligible.
- License status: `unverified_landing_copy`. Frank should clear before any
  promotion path is even discussed.
- The user's belief that the Hawaiian paragraph is native-speaker
  authored/translated is recorded as a `quality_note`, not as a verification
  claim. A native-speaker review is still required for any escalation.

### Normalization

- Unicode NFC.
- ʻokina U+2018 / U+2019 / U+02BC / U+0060 → U+02BB.
- Markdown headings (`# English`, `# Hawaiian`) treated as scaffolding and
  removed; page title + paragraph body retained as source text.
- No diacritic stripping; Hawaiian punctuation preserved.

### Counts

- HAW: 527 chars, ~103 words, ʻokina × 22, kahakō × 21, diacritic density
  ≈ 0.082 — usable as a high-diacritic slice probe.
- EN: 539 chars, ~78 words, ʻokina × 2, kahakō × 1 (proper nouns).

### What I did NOT do

- Did not modify `data/raw/ulukau_nupepa/human_fetch.md`.
- Did not modify Stage 1 outputs, eval hashes, W1 files, or any committed
  manifests.
- Did not commit. Did not touch unrelated dirty files in `scripts/`.

### Asks

- **Rusty:** when authoring the tokenizer-audit test, this artifact is a
  ready high-diacritic Hawaiian probe row. Treat as candidate input only.
- **Frank:** if/when license clearance for Ulukau landing copy is in scope,
  this is the path to clear. Until then it stays audit-only.


---

## Decision: Linus — Kaʻehuikimanōopuʻuloa pages converted to tokenizer-audit candidate

**Date:** 2026-04-30  
**Owner:** Linus (Data Engineer)  
**Status:** Recorded — additive, audit-only; source integrity verified

### Summary

Converted manual book-page paste of *He moʻolelo kaʻao no Kaʻehuikimanōopuʻuloa* (Moses Manu) from `data/raw/ulukau_nupepa/human_fetch_book_pages.txt` into audit-only artifacts. Prior `human_fetch.*` landing-copy slice untouched (hashes verified). Additive under `data/tokenizer_audit/ulukau_nupepa/kaehuikimanoopuuloa/`.

### Content

- **Text:** 14,753 characters, 3,224 Hawaiian words, 21 paragraphs
- **ʻokina:** 756 instances (U+02BB)
- **kahakō:** 614 instances (macron vowels)
- **Diacritic density:** (756+614)/14,753 ≈ **0.1254** (12.54% of content)
  - vs. prior `human_fetch.md` slice ≈ 0.082 — **53% denser**, strong high-diacritic probe

### Artifacts (all under ignored `data/`)

- `data/tokenizer_audit/ulukau_nupepa/kaehuikimanoopuuloa/kaehuikimanoopuuloa.jsonl` (1 JSONL row, lang=haw)
- `data/tokenizer_audit/ulukau_nupepa/kaehuikimanoopuuloa/kaehuikimanoopuuloa.haw.txt` (plain text)
- `data/tokenizer_audit/ulukau_nupepa/kaehuikimanoopuuloa/manifest.json`
- `data/tokenizer_audit/ulukau_nupepa/kaehuikimanoopuuloa/README.md`
- Helper: `scripts/_convert_kaehuikimanoopuuloa.py` (local, idempotent, not committed)

### Normalization

- NFC applied; source already clean at U+02BB (0 substitutions)
- Paragraph boundaries preserved; multi-blank-line paste runs collapsed to single blank
- No content deletion; curly quotes (dialogue) preserved as-is
- Source SHA-256 verified pre/post

### Policy (Binding)

- `audit_use = tokenizer_audit_candidate`, `audit_only = true`
- **Not** Stage 1, **not** eval, **not** training, **not** W1
- License: `unverified` (published work; rights not cleared)
- User's "likely native speaker" framing recorded as note, not verification

### Invariants Preserved

- Raw source (`data/raw/ulukau_nupepa/human_fetch_book_pages.txt`) unchanged; SHA verified
- Prior `human_fetch.*` landing-copy artifact untouched
- Stage 1 manifest, eval_hashes.jsonl, W1 ledger: no writes
- No commits

### What Happens Next

- **Rusty:** Combined with `human_fetch.md` landing-copy slice, these two now meet Stage-0 minimums (≥1,500 words ✅, ≥10 high-diacritic samples ✅)
- **Coordinator:** Test harness can begin; multi-genre expansion (≥5–6k words, ≥3 genres) recommended for defensible gate numbers


---

## Decision: Rusty — Kaʻehuikimanōopuʻuloa assessed as strong tokenizer-audit slice

**Date:** 2026-04-30  
**Owner:** Rusty (NLP Researcher)  
**Status:** Recorded — combined slices meet minimum thresholds; single-register stress noted

### Assessment

**Verdict:** Strong tokenizer-audit candidate. The 3,224-word high-diacritic slice (0.1254 density) paired with earlier `human_fetch.md` landing-copy (0.082 density) now **meets** the frozen Stage-0 gate minimums:

| Criterion | Status | Detail |
|-----------|--------|--------|
| ≥1,500 words | ✅ PASS | 3,751 combined words |
| ≥10 high-diacritic samples | ✅ PASS | 26+ paragraphs/sentences with ʻokina+kahakō floor |
| Tokens/word ≤2.50 (overall) | ⏳ Pending | Harness run required |
| Tokens/word ≤3.25 (high-diacritic) | ⏳ Pending | Harness run required |
| Byte fallback / proxy rates | ⏳ Pending | Harness run required |

### Combined Audit Package

| Slice | Genre | Words | Density | Diacritics |
|-------|-------|-------|---------|-----------|
| `human_fetch.md` | Landing-copy blurb (EN+HW mixed) | 527 | 0.082 | Mixed |
| `kaehuikimanoopuuloa` | Narrative prose (Hawaiian-only) | 3,224 | 0.1254 | High |
| **Total** | Two genres, one author family | **3,751** | **0.119 avg** | **High** |

### Stress-Test Value

1. **Diacritic range:** 0.082 → 0.1254 shows workable variance; nūpepa likely higher; place names may spike different directions
2. **Register consistency:** Both 19th-century Hawaiian; word-internal diacritics common (prose stress)
3. **Single-author limitation:** Moses Manu + blurb pair; same author family minimizes genre variance
4. **All paragraphs pass floor:** Every paragraph in narrative slice clears ≥3 ʻokina+kahakō threshold easily (high-diacritic qualification)

### Recommendations

**Immediate:** Proceed with test harness authoring against this two-slice pair.

**Medium term (defensible gate numbers):** Target ≥5–6k words across ≥3 genres:
- Ulukau nūpepa (newspapers): modern Hawaiian, dialogue-heavy, register mix
- Modern prose: contemporary, possibly Aloha Aina or educational material
- Place names / proper nouns: high ʻokina, sparse kahakō — symbol-isolated stress

**Genre-specific stress profiles (future):**
- Landing-copy: minimal kahakō, high ʻokina (0.082) → symbol-mix load
- Narrative prose: balanced ʻokina+kahakō (0.1254) → word-internal diacritic density
- Nūpepa: dialogue + editorial → register variance, modern Hawaiian
- Place names: high ʻokina, sparse kahakō → isolated-character symbol stress

### Policy (Binding)

- Audit-only; no eval_hashes.jsonl, Stage 1 manifest, or W1 ledger writes
- Licensing (`unverified`) requires separate Hawaiian-literate review for any non-audit escalation
- Train ∩ eval = ∅ maintained

### Cross-Agent Notes

- **Linus:** Conversion complete; manifest.json ready for harness consumption
- **Basher:** Tokenizer audit output contract now has concrete candidate slices to validate schema against
- **Coordinator:** Two-slice pair passes minimum thresholds; test authoring unblocked; multi-genre expansion is nice-to-have, not blocker


---

## Decision: Basher — Tokenizer-audit output contract (Stage-0 gate reporting)

**Date:** 2026-04-30  
**Owner:** Basher (Training Engineer)  
**Status:** Recorded — output layout defined; implementation pending (test harness authoring)

### Summary

Defined file structure and JSON schema for tokenizer-audit runs. One run directory per audit: `data/tokenizer_audit/<run_id>/` with `report.json` (machine-readable gate truth), `report.md` (human narrative), `samples.jsonl` (annotated slices), and `inputs.manifest.json` (audit inputs). Hard-fail semantics: missing `transformers`, gated Llama, no Hawaiian samples → `no_go` with environment reasons, never fabricated metrics. No changes to docs, code, or eval ledger; schema ready for adoption.

### Output Structure

```
data/tokenizer_audit/<run_id>/
├── report.json             # Machine-readable gate truth (read by CI)
├── report.md               # Human narrative (for review)
├── samples.jsonl           # Annotated slice samples with tokenization
└── inputs.manifest.json    # Which input slices were audited
```

All files are local-only, gitignored.

### `report.json` Gate Logic

**Decision rule:** `go` iff all `checks[*].passed == true` AND `recommendation.decision == "go"`.

**No partial credit:** Hard-fail (missing `transformers`, gated model access, zero samples) writes `recommendation.decision = "no_go"` with `recommendation.reasons = ["environment.*"]` and null metrics. Never manufactured passing numbers.

**Checks (from frozen decisions.md):**
1. `overall_tokens_per_word ≤ 2.50` (overall text)
2. `high_diacritic_tokens_per_word ≤ 3.25` (high-diacritic only)
3. `explicit_byte_fallback = 0` (no synthetic bytes)
4. `proxy_rate ≤ 1%` (minimal fallback proxies)
5. `diacritic_char_tokens ≤ 2` (ʻokina/kahakō tokenize into ≤2 tokens each)

### `report.json` Schema (Abridged)

```json
{
  "run_id": "...",
  "timestamp": "2026-04-30T02:04:40Z",
  "model": {
    "model_id": "meta-llama/Llama-3.1-8B",
    "tokenizer_sha256": "abc123...",
    "tokenizer_fingerprint_sha256": "abc123..."
  },
  "overall": {
    "total_words": 3751,
    "tokens_per_word": 2.34,
    "explicit_byte_fallback_rate": 0.00,
    "byte_fallback_or_proxy_rate": 0.005
  },
  "high_diacritic": {
    "sample_count": 26,
    "tokens_per_word": 2.87,
    "explicit_byte_fallback_rate": 0.00,
    "byte_fallback_or_proxy_rate": 0.01
  },
  "checks": [
    {
      "id": "overall_tokens_per_word",
      "passed": true,
      "threshold": 2.50,
      "actual": 2.34
    },
    ...
  ],
  "recommendation": {
    "decision": "go",
    "reasons": ["all_checks_passed"],
    "blocks": [],
    "next_actions": [
      "Freeze tokenizer SHA into Stage-1 manifest",
      "Unblock code/configs/llama31_8b_a100.json",
      "Proceed to Stage 1 training"
    ]
  }
}
```

### `report.md` Structure

Human-readable narrative matching JSON:
1. Summary (headline + decision)
2. Model & tokenizer SHA
3. Overall metrics table
4. High-diacritic metrics table
5. Check results (each with threshold / actual / pass/fail)
6. Recommendation (decision + reasons + next steps)
7. Audit inputs (which slices, counts)

### `samples.jsonl` & `inputs.manifest.json`

- **`samples.jsonl`:** One JSONL row per sample with tokenization details (`source_manifest`, `tokens_per_word`, `has_explicit_byte_fallback`, `is_high_diacritic`, etc.)
- **`inputs.manifest.json`:** List of input slices used (source name, word count, sample count, policy tags)

### Integration with CI & Config

- **CI Gate:** Test harness writes `report.json`. CI/Makefile reads `recommendation.decision` field and blocks training entry if not `go`.
- **Config Unfreeze:** Once gate passes `go`, Linus updates `code/configs/llama31_8b_a100.json` with frozen tokenizer SHA and model ID.

### Guarantees & Constraints

1. **No fabricated metrics:** Hard-fail writes `no_go` with null metrics + environment reasons. Never backfill passing numbers.
2. **Thresholds frozen:** Values in `checks[*].threshold` match decisions.md frozen values. Schema version increments if threshold changes.
3. **Gate is binary:** `decision ∈ {go, no_go}`. No `conditional` or `partial`.
4. **SHA is portable:** `tokenizer_sha256` + `model_id` together sufficient to recreate audit on different machine.

### What Is NOT Changing

- Docs: no updates yet (deferred until contract adopted; training-pipeline §1.1, eval_pipeline §3.1 will be updated post-adoption)
- Data policy: audit slices remain `audit_only`; no eval_hashes.jsonl, Stage 1, W1 writes
- Code: no changes to `code/llm_hawaii/`, no test harness yet (Qwen smoke test remains until contract adoption)

### For Future Test Harness Author

1. Hard-fail early: check `transformers` + Llama gating at entry
2. Reuse `code/llm_hawaii/metrics.py` for diacritic counts and high-diacritic classification
3. Tokenize in batches: Llama tokenizer may choke on very long sequences
4. Preserve sample metadata: JSONL must include source for audit traceability


---

## Updated 2026-04-30T02:04:40Z: Linus, Rusty, Basher decisions added

Three decisions merged:
- Linus: Kaʻehuikimanōopuʻuloa book-slice conversion (additive, audit-only)
- Rusty: Assessment confirming strong audit candidacy; two-slice pair meets Stage-0 minimums
- Basher: Tokenizer-audit output contract (report.json gate schema, hard-fail semantics)


---

## Updated 2026-04-30T04:02:09Z: Copilot directive — User preference for tokenizer-audit helper API

**Timestamp:** 2026-04-30T04:02:09Z
**By:** yashasg (via Copilot)
**Scope:** Helper API surface

User directive: Tokenizer audit helper should derive required metadata from (model_id, tokenizer) arguments rather than requiring separate manual SHA/hash arguments.

**Impact:** Implementation target for Linus's metadata helper (landed 2026-04-30).


---

## Added 2026-04-30: Linus — Tokenizer audit helper metadata extraction (landed)

**Owner:** Linus (Data Engineer)
**Status:** Landed in `code/tests/test_tokenizer_audit.py`

### Summary

Implemented `tokenizer_metadata_from_model_and_tokenizer(model_id, tokenizer)` to derive audit report metadata directly from tokenizer object and model ID, eliminating null placeholders.

### New Helper

```
tokenizer_metadata_from_model_and_tokenizer(model_id, tokenizer) → dict
```

Returns:
- `model_id` — passed through
- `tokenizer_name_or_path` — from `tokenizer.name_or_path`
- `hf_commit_sha` — from `tokenizer._commit_hash` or `tokenizer.init_kwargs.get("_commit_hash")`
- `tokenizer_class` — class name
- `is_fast` — boolean
- `vocab_size` — `len(tokenizer)` or `None`

### Fields Removed from Audit Report

- `model.model_repo_sha` (was `None`)
- `model.tokenizer_sha256` (was `None`)
- `model.tokenizer_fingerprint_sha256` (was `None`)

These will be populated later when `build_audit_report` orchestrator can make Hub API calls or filesystem reads.

### Validation

- ✅ Compilation: `python3 -m py_compile code/tests/test_tokenizer_audit.py`
- ✅ Unit tests: 6/6 pass without `transformers` installed
- ⚠️ Smoke test blocked locally: missing `transformers` dependency

### Downstream Impact

Consumers expecting `model.{model_repo_sha, tokenizer_sha256, tokenizer_fingerprint_sha256}` will encounter `KeyError`. For now, use `model.hf_commit_sha`.


---

## Added 2026-04-30: Rusty — Kaʻehuikimanōopuʻuloa as tokenizer-audit candidate slice (assessment)

**Owner:** Rusty (NLP Researcher)
**Status:** Assessment; no code/data changes

User added pages from *He Moʻolelo Kaʻao no Kaʻehuikimanōopuʻuloa* (Moses Manu / Ulukau).

### Assessment Results

**Corpus volume:** 3,223 Hawaiian words, 21 paragraphs, 756 ʻokina, 614 kahakō, diacritic density ≈0.1254.

**Gate compatibility (Issue #8 Stage-0):**
- ✅ ≥1,500 words (actual: 3,223)
- ✅ ≥10 high-diacritic samples (21 paragraphs all pass ʻokina+kahakō ≥3; many pass diacritics/word ≥0.25)
- ✅ Clean NFC, U+02BB throughout (no canonicalization work needed)

**Verdict:** Strong tokenizer-audit candidate, covers gate minimums on its own.

### Caveats (binding for downstream)

- **Audit-only:** Not W1, not eval, not training
- **License unverified:** Ulukau/Moses Manu public domain plausible but not confirmed; do not redistribute/push remote
- **Single-genre:** One author, one moʻolelo, one register; audit will pass numerically but be genre-narrow
- **Recommendation for broader coverage:** Collect 3–5 additional small slices (~150–500 words each) from varied genres (news editorial, modern prose, place-names, numerals/dates) to reach ~5,000–6,000 words across ≥3 genres for defensible numbers

### Asks

- **Linus:** Convert `human_fetch_book_pages.txt` → `data/tokenizer_audit/ulukau_nupepa/kaehuikimanoopuuloa/` JSONL using prior slice shape
- **Coordinator:** Route varied-genre collection to user if/when audit needs defensibility upgrade


---

## Added 2026-04-30: Linus — Kaʻehuikimanōopuʻuloa converted to tokenizer-audit input (completed)

**Owner:** Linus (Data Engineer)
**Status:** Completed (additive, audit-only, not committed)

### Outputs

Under `data/tokenizer_audit/ulukau_nupepa/kaehuikimanoopuuloa/` (ignored, not committed):
- `kaehuikimanoopuuloa.jsonl` (1 row, `lang=haw`)
- `kaehuikimanoopuuloa.haw.txt`
- `manifest.json`
- `README.md`
- Helper script: `scripts/_convert_kaehuikimanoopuuloa.py`

### Normalization Applied

- Unicode NFC
- ʻokina: folded U+2018/U+2019/U+02BC/U+0060 → U+02BB (0 substitutions; source was clean)
- Whitespace: per-line stripped; runs collapsed to single space; multi-blank → single blank (page scaffolding removed)
- Content: no diacritics stripped, no deletions, curly quotes preserved

### Counts

| Metric | Value |
|---|---|
| Records | 1 (`lang=haw`) |
| Chars | 14,753 |
| Words | 3,224 |
| Paragraphs | 21 |
| ʻokina | 756 |
| Kahakō | 614 |
| Diacritic density | ≈0.1254 |

**Comparison:** Prior Ulukau landing-copy HAW slice: ≈0.082 density. New slice substantially stronger high-diacritic probe.

### Policy (binding)

- `audit_use = tokenizer_audit_candidate`
- `audit_only = true`
- `stage1_eligible = eval_eligible = training_eligible = w1_eligible = false`
- `license_status = unverified`
- **Do not promote** without fresh provenance + license + Hawaiian-literate review

### Invariants Preserved

- Raw source SHA verified equal pre/post
- Prior `data/tokenizer_audit/ulukau_nupepa/human_fetch.*` untouched
- No Stage-1 manifest, eval_hashes.jsonl, or W1 writes
- No commits

### Asks

- **Frank/licensing:** Clear rights for *Kaʻehuikimanōopuʻuloa* before any promotion
- **Rusty:** When tokenizer-audit test lands, consider this as high-diacritic probe (density 0.1254, 756 ʻokina, 614 kahakō)


---

## Added 2026-04-30: Basher — Tokenizer-audit output contract (schema, gates, hard-fail semantics)

**Owner:** Basher (Training Engineer)
**Status:** Proposed (team review)
**Scope:** Output shape of planned tokenizer-audit test (`code/tests/test_tokenizer_audit.py`)

### Artifact Locations (prototype-local, ignored)

```
data/tokenizer_audit/<run_id>/
  report.json          # machine-readable, gate-read
  report.md            # human summary (≤1 screen)
  samples.jsonl        # per-sample metrics
  inputs.manifest.json # consumed slices, counts
```

`<run_id>` format: `<UTC-yyyymmddThhmmssZ>__<model_short>__<tok_fp8>`
Example: `20260430T020225Z__llama31-8b__a1b2c3d4`

### `report.json` — Machine-Readable Gate Input

**Key sections:**
- `schema_version`, `run_id`, `created_utc`
- `tool`: name, version, git SHA, host platform/Python/transformers
- `model`: model_id, model_repo_sha, tokenizer_sha256, tokenizer_fingerprint_sha256, tokenizer_files_hashed
- `inputs.slices[]`: slice_id, path, sha256, lang_filter, records, words, audit_only
- `thresholds`: copies from decisions.md frozen values
- `overall`, `high_diacritic`: tokens_per_word, explicit_byte_fallback_rate, byte_fallback_or_proxy_rate
- `diacritic_chars[]`: char, codepoint, tokens, passes
- `checks[]`: id, passed, actual, threshold
- `recommendation`: decision (`go`|`no_go`), reasons, blocks, next_actions
- `errors[]`: hard-fail diagnostics

**Decision rule:** `recommendation.decision = "go"` **iff all** `checks[*].passed = true`. Any false → `"no_go"` with failed ids in reasons.

**Alias:** `tokenizer_sha256` and `tokenizer_fingerprint_sha256` are the same value (both emitted for doc-reference compatibility).

**Invariant:** Threshold values in report must match `decisions.md` at audit time or test fails loudly.

### `report.md` — Human Summary

≤1 screen, required sections:
1. Header: run_id, model id, repo SHA, tokenizer fingerprint (12 hex chars), date, decision (GO/NO-GO)
2. Inputs table: slice_id, words, high_diacritic_samples, audit_only
3. Metrics table: overall + high-diacritics with thresholds and ✅/❌ markers
4. Per-diacritic-char rows: ʻ, ā, ē, ī, ō, ū → token count, ✅/❌
5. Decision paragraph: on `no_go`, list failed check ids and literal text "This blocks `code/configs/llama31_8b_a100.json` Stage-1 spend until a re-run reports `go`."
6. Footer: "Prototype/local artifact. Not release certification. Not eval data."

### `samples.jsonl` — Per-Record Evidence

One JSON per audited record. Fields:
- slice_id, record_id, lang
- char_count, word_count, okina_count, kahako_count, diacritics_per_word
- is_high_diacritic
- token_count, tokens_per_word
- explicit_byte_fallback_count, byte_fallback_or_proxy_count
- explicit_byte_fallback_rate, byte_fallback_or_proxy_rate

Used for debugging `no_go` and future slice-level breakdowns. Gate reads only `report.json`.

### `inputs.manifest.json` — Slice Metadata

Lists slices consumed (paths, hashes, counts).

### Hard-Fail Behavior (do not fabricate)

If `transformers` missing, Llama gated, or no Hawaiian samples found:

1. Write `report.json` with `recommendation.decision = "no_go"`, `recommendation.reasons = ["environment.<reason>"]`, populated `errors[]`, and zero/null metrics (never fake numbers)
2. Write `report.md` with `NO-GO (environment)` header + install/login instructions
3. Return non-zero unittest result

**Principle:** Preserve "do not fabricate audit results" stance from Issue #8 decision.

### How Gate Is Interpreted

- **`decision == "go"`** → Basher may freeze `model_repo_sha` + `tokenizer_sha256` into Stage-1 manifest for `code/configs/llama31_8b_a100.json`. **Only** path unblocking serious 8B Stage-1 spend.
- **`decision == "no_go"`** → Stage-1 spend stays blocked. Either grow audit coverage + re-run, or open fallback-tokenizer/vocab-extension decision.
- **`go` is not release/eval signal:** Audit slices remain `audit_only`; no rows into `data/evals/eval_hashes.jsonl` or W1.

### What This Does NOT Do

- Change Rusty's thresholds, fingerprint requirements, or "do not fabricate" stance
- Introduce standalone audit script; surface remains `code/tests/test_tokenizer_audit.py` (smoke placeholder)
- Modify `data/evals/eval_hashes.jsonl`, W1, or docs (docs follow-up flagged, not included here)

### Notes for Other Agents

- **Rusty:** Thresholds + fingerprint requirements unchanged; copied verbatim into `report.json.thresholds`. If different decision rule needed, flag before test authoring.
- **Linus:** New audit slices under `data/tokenizer_audit/<src>/` need only expose JSONL shape already used; harness aggregates into `inputs.slices[]`. Slices stay `audit_only`.
- **Frank/licensing:** `report.md` carries "Prototype/local artifact" footer to prevent misread as release claim.


---

## Added 2026-04-30: Basher — Llama-3.1-8B tokenizer audit NO-GO (gate closed, awaits clean re-run)

**Owner:** Basher (Training Engineer)
**Status:** Recommendation; gate closed awaiting clean re-run + Rusty concurrence
**Input:** `data/tokenizer_audit/official/20260430T033208Z__meta-llama_Llama-3.1-8B.json`

### Current Report Says

- `recommendation.decision = "no_go"` — explicit blocker
- `overall.byte_fallback_or_proxy_rate = 0.1928` (~19× over 0.01 threshold) — **catastrophic**
- `overall.tokens_per_word = 2.474` (passes, 1% margin) — knife-edge
- `overall.explicit_byte_fallback_rate = 0.0` — passes but suspicious given 19% proxy rate
- `high_diacritic.status = "not_evaluated"` — Hawaiian-specific signal missing
- `diacritic_chars.status = "not_evaluated"` — standalone diacritic counts missing

### Contract Violations in Artifact

- File in `data/tokenizer_audit/official/…` but `"dry_run": true` (contradicts path convention)
- `model.tokenizer_sha256 = null`, `model.tokenizer_fingerprint_sha256 = null`, `model.model_repo_sha = null` — **cannot freeze SHA into config**; gate precondition violated
- High-diacritic and standalone-diacritic sections missing

**Verdict:** Even if metrics were green, artifact cannot legally promote gate due to missing fields.

### Decision

**No-go for Stage-1 GPU spend on Llama-3.1-8B.** No interim base swap yet.

### Next Actions (before any GPU spend, in order)

1. **Fix audit instrumentation:**
   - Populate non-null `tokenizer_sha256`, `tokenizer_fingerprint_sha256`, `model_repo_sha`
   - Evaluate `high_diacritic` slice (kahakō + ʻokina-heavy)
   - Populate `diacritic_chars` items (per-char token counts for ā ē ī ō ū ʻ)
   - Reconcile byte-fallback accounting: clarify why explicit=0 consistent with proxy=19%

2. **Re-run as true official audit:**
   - Output: `data/tokenizer_audit/official/<ts>__meta-llama_Llama-3.1-8B.json`
   - `dry_run` field absent (per path convention; dry runs → `data/tokenizer_audit/dryrun/`)

3. **Hand to Rusty** (gate owner) for go/no_go decision on clean report

4. **If no_go persists:** Evaluate interim bases (Qwen2.5-7B for multilingual, Gemma-2-9B, hold Qwen2.5-0.5B smoke tier). Let audit numbers decide; no pre-commit.

### Not Doing

- Modifying training data
- Starting any training run
- Freezing SHA into `code/configs/llama31_8b_a100.json`
- Swapping base model in config defaults

### Cross-refs

- Gate definition: `.squad/decisions.md` Issue #8
- Output contract: `.squad/decisions/inbox/basher-tokenizer-audit-output-contract.md`
- Metric definitions: `code/tests/test_tokenizer_audit.py`


---

## Added 2026-04-30: Rusty — Llama-3.1-8B audit no_go is proxy-heuristic mismatch, not tokenizer blocker (analysis)

**Owner:** Rusty (NLP Researcher)
**Status:** Analysis; no code/data/gate-threshold changes proposed
**Artifact:** `data/tokenizer_audit/official/20260430T033208Z__meta-llama_Llama-3.1-8B.json`

### Report Quick Summary

- ✅ `overall.tokens_per_word = 2.474` (passes ≤2.50)
- ✅ `explicit_byte_fallback_count = 0` (passes, no `<0xXX>` tokens)
- ❌ `byte_fallback_or_proxy_rate = 0.1928` (fails 1% gate)
- ⚠️ `high_diacritic` + `diacritic_chars` not evaluated

### Why no_go Is Mostly Heuristic Mismatch

The current proxy rule in `code/tests/test_tokenizer_audit.py`:

```python
stripped = piece.lstrip("▁Ġ ")
return len(stripped) == 1 and ord(stripped) > 127
```

**Was written for SentencePiece-with-byte-fallback** (Qwen, Llama-2) where a single non-ASCII piece is either (a) `<0xXX>` token (caught explicitly) or (b) an unmerged single-char fallback worth flagging.

**Llama-3 uses tiktoken-derived byte-level BPE** (GPT-2 family). In byte-level BPE:
- Every UTF-8 byte mapped to Latin-1-Supplement / Latin-Extended-A codepoint (all `ord > 127`)
- Multi-byte chars (ʻokina = 3 bytes; ā/ē/ī/ō/ū = 2 bytes) encoded as **sequence of byte-chars**
- Survival of single byte-char piece = **lossless, round-trip-clean**, not a lossy fallback
- Whether they fuse to multi-byte BPE token depends on learned merges during training

**On Hawaiian text:** Every ʻokina/kahakō missing a learned merge in Llama-3 vocab surfaces as exactly the flagged pattern: `len(stripped)==1, ord>127`. Corpus has ~1,370 diacritics (756 ʻokina + 614 kahakō); 1,538 hits is right order of magnitude for byte-level BPE on diacritic-dense Hawaiian without learned merges.

**Two clinching signals this is heuristic noise, not real damage:**

1. **`explicit_byte_fallback_rate = 0`** — Llama-3 has no `<0xXX>` vocab; check is structurally inapplicable, not "passing because tokenizer is great"
2. **`tokens_per_word = 2.47` passes** — If 19% of tokens were truly catastrophic fragmentation, tokens/word on diacritic-heavy text would blow to 2.5–3.0+. Hitting 2.47 is consistent with "byte-level BPE handling Hawaiian without learned merges, losslessly"

### What Is Still a Real Concern

- **Missing provenance:** `tokenizer_sha256` + `tokenizer_fingerprint_sha256` both `null`. Gate requires fingerprint; legitimate blocker.
- **Missing slice evaluations:** `high_diacritic` and `diacritic_chars` not evaluated. Gate explicitly requires both. Without these, clean overall number isn't gate-sufficient.
- **Single-genre stress:** Per prior assessment, audit on one author/register is suggestive, not defensible.

### Recommendation

Treat current no_go as:

- **NOT** tokenizer-quality blocker for Llama-3.1-8B on Hawaiian. Byte-level BPE does what byte-level BPE does; not lossy.
- **YES** harness blocker: `byte_fallback_or_proxy_rate` metric **not meaningful for byte-level BPE family** (Llama-3, GPT-2/3/4, tiktoken models). Applying it produces false negative every time on diacritic-heavy non-Latin scripts.
- **YES** gate blocker on missing fingerprint + unevaluated slices — real gate gaps regardless of proxy issue.

Private prototype/learning project → "tighten harness, re-run," not "abandon Llama-3.1-8B."

### Immediate Next Step (low-spend)

**Produce evidence, not opinion. On same `kaehuikimanoopuuloa.jsonl` slice:**

1. Take ~5 sentences with ʻokina + kahakō. Dump side-by-side:
   - Raw text
   - Token ids
   - `tokenizer.convert_ids_to_tokens(ids)` (pieces the heuristic sees)
   - `tokenizer.decode([id])` per token (round-trip text — this is truth)
   - Whether each piece flagged by `_is_byte_fallback_or_proxy`

2. **Confirm two things:**
   - Every flagged piece round-trips to non-empty UTF-8 byte/char (**lossless**, not U+FFFD or empty)
   - `tokenizer.decode(all_ids) == NFC(original_text)` (full round-trip identity)

3. **If both hold (expected):** Data in hand to:
   - File harness fix making proxy heuristic tokenizer-family-aware (skip/redefine for byte-level BPE; keep current for SentencePiece+byte-fallback). Linus owns; Rusty reviews.
   - Separately populate `tokenizer_sha256` / `tokenizer_fingerprint_sha256` and `high_diacritic` / `diacritic_chars` slices, re-run.

If round-trip **not** clean → picture changes, no_go becomes real tokenizer blocker. Current report does not show that yet.

### Bright Lines Held

- No threshold changes. Frozen gate (overall ≤2.50, high-diac ≤3.25, explicit byte fallback=0, proxy≤1%, diac chars≤2, fingerprint required) stands until evidence supports family-aware "proxy" redefinition.
- No training/eval promotion of audit slice. Tokenizer audit only.
- No edits to `data/`. No new `eval_hashes.jsonl` rows.

### Asks

- **Linus:** Ownership of harness change + round-trip dump
- **Coordinator:** Route harness to Linus; fingerprint/slice-population to audit-runner owner


---

## Added 2026-04-30T04:20:10Z: Rusty — Tokenizer-audit cleanup semantics (harness logic + reporting, not threshold change)

**Owner:** Rusty (NLP Researcher)  
**Status:** Proposal — gates Linus harness implementation (Phase 2 family-detector)  
**Date:** 2026-04-30

### Problem Statement

The `byte_fallback_or_proxy_rate ≤ 0.01` gate was designed for SentencePiece-with-byte-fallback tokenizers (Llama-2, Mistral, Gemma, Qwen) where single non-ASCII pieces reliably signal fallback. Llama-3 uses byte-level BPE (tiktoken/GPT-2 family): multi-byte UTF-8 chars decompose into sequences of byte-chars (all `ord>127`), and unmerged single-byte pieces are **structurally lossless**, not fallback. The heuristic produces 19% false positives on Hawaiian text — not evidence of tokenizer damage.

### Solution: Tokenizer-family-aware cleanup

Five core changes:

#### 1. Add `tokenizer_family` detection (new, required)

Detect from tokenizer object at audit time, not `model_id` (Llama-2 = SentencePiece; Llama-3 = byte-level BPE; same family name, different tokenization math). Detection priority:

1. **byte_level_bpe**: GPT-2 byte-to-unicode map in vocab covering 256 byte codepoints (high-ordinal Latin-1-Supplement / Latin-Extended-A), OR `backend_tokenizer.model.__class__` ∈ {`BPE`}, OR class ∈ {`GPT2Tokenizer*`, `LlamaTokenizerFast`} + GPT-2 probe.
2. **sentencepiece_byte_fallback**: `▁`-prefixed vocab AND `<0xXX>` byte-fallback tokens present (Llama-2, Mistral, Gemma), OR `sp_model` attribute.
3. **unigram / wordpiece**: `backend_tokenizer.model.__class__` ∈ {`Unigram`, `WordPiece`}.
4. **unknown**: fallback (treated as sentencepiece_byte_fallback for safety).

Report: `model.tokenizer_family = "byte_level_bpe"` (forensics).

#### 2. Per-check `applicability` + `passed` semantics

Each check carries `{value, threshold, passed, applicability, reason}`:
- `applicability ∈ {"applicable", "not_applicable"}`
- `passed ∈ {true, false, null}`; `null` iff `applicability="not_applicable"` or `insufficient_samples`
- **Critical:** `passed=null` must **NOT** appear in `recommendation.blocking_reasons`

| Check | byte_level_bpe | sentencepiece_byte_fallback | wordpiece/unigram |
|---|---|---|---|
| `overall_tokens_per_word ≤ 2.50` | applicable, BLOCKING | applicable, BLOCKING | applicable, BLOCKING |
| `explicit_byte_fallback_rate = 0` | applicable, BLOCKING (trivially pass; audit trail) | applicable, BLOCKING | not_applicable |
| `byte_fallback_or_proxy_rate ≤ 0.01` | **not_applicable** (proxy is SentencePiece-shaped) | applicable, BLOCKING | not_applicable |
| `roundtrip_lossless = true` (new) | applicable, BLOCKING | applicable, BLOCKING | applicable, BLOCKING |
| `high_diacritic.tokens_per_word ≤ 3.25` | applicable, BLOCKING | applicable, BLOCKING | applicable, BLOCKING |
| `high_diacritic.byte_fallback_or_proxy_rate ≤ 0.01` | not_applicable | applicable, BLOCKING | not_applicable |
| `diacritic_chars: all ≤ 2 tokens` | applicable, BLOCKING | applicable, BLOCKING | applicable, BLOCKING |
| `model_identity_resolved` (3 SHAs) | applicable, BLOCKING | applicable, BLOCKING | applicable, BLOCKING |

#### 3. Add `roundtrip_lossless` check (structural integrity gate)

Replaces proxy as the byte-level BPE fallback gate. For all families:
- Compute `decode(all_ids) == NFC(text)` over each evaluated slice (overall + high_diacritic)
- Per-piece: for every piece flagged by any detector, `decode([id])` returns non-empty UTF-8 and concatenated decodes of contiguous flagged pieces reproduce the original source substring (NFC-normalized)
- `passed=false` is unconditionally blocking — actual data loss

Byte-level BPE **requires** round-trip true; SentencePiece uses it as belt-and-suspenders.

#### 4. Fix status field distinctions

Three distinct states:
- **`not_applicable`**: Family-inappropriate (never blocks). Reason cites family. Example: proxy check on byte_level_bpe.
- **`insufficient_samples`**: Corpus didn't meet Stage-0 minimums (≥10 high-diac samples, ≥1,500 words). **Blocks** with reason `high_diacritic_coverage`.
- **`not_evaluated`**: Harness didn't run the section. **Blocks** with reason `<section>_unevaluated` until wired.

Current Llama-3.1-8B report should have:
```json
"recommendation": {
  "blocking_reasons": [
    "high_diacritic_unevaluated",
    "diacritic_chars_unevaluated"
  ],
  "decision": "no_go"
}
```

NOT `["byte_fallback_or_proxy_rate"]`.

#### 5. `recommendation.blocking_reasons` = closed enum

Only checks with:
- `passed=false` AND `applicability="applicable"`, OR
- `status="insufficient_samples"` OR `status="not_evaluated"`

contribute. All other entries must be excluded (e.g., `passed=null` from `not_applicable` checks).

### Bright Lines Held

- **No threshold changes.** All current limits (≤2.50, ≤3.25, =0, ≤0.01, ≤2) **stand unchanged**.
- **Not an exemption for Llama.** Same semantics apply to any byte-level BPE tokenizer; SentencePiece family retains proxy gate.
- **Not a substitute for high_diacritic / diacritic_chars sections.** Both remain required, blocking, and must be populated via multi-slice evaluation (Kaʻehuikimanōopuʻuloa + ≥2 varied genres).

### Expected Outcome on Llama-3.1-8B Re-run

- `tokenizer_family = "byte_level_bpe"` ✅
- `overall_tokens_per_word = 2.47` ✅
- `explicit_byte_fallback_rate = 0.0` ✅
- `byte_fallback_or_proxy_rate = 0.193`, `applicability=not_applicable, passed=null` (excluded from blocking)
- `roundtrip_lossless = true` (expected; must verify on the slice)
- `high_diacritic` / `diacritic_chars`: populated via Kaʻehuikimanōopuʻuloa + additional slices
- `recommendation = "go"` IFF diacritic sections clear; otherwise `no_go` with **correct** reasons (coverage/fragmentation), not phantom proxy failure

### Coordination

**Linus owns harness implementation.** This decision gates §2 (family-aware proxy + roundtrip) in his concrete plan. **Will not land §2 without this sign-off.**


---

## Added 2026-04-30T04:20:10Z: Linus — Tokenizer audit cleanup—concrete implementation steps

**Owner:** Linus (Data Engineer)  
**Status:** Step plan; no code yet  
**Date:** 2026-04-30T04:20Z  
**Driver report:** `data/tokenizer_audit/official/20260430T041606Z__meta-llama_Llama-3.1-8B.json`

### Implementation Roadmap

Seven phases, executed in order:

#### Phase 1: Module split (prep, no behavior change)

Move pure helpers out of `code/tests/test_tokenizer_audit.py`:
- **New:** `code/llm_hawaii/tokenizer_audit.py` — exports `tokenizer_metadata_from_model_and_tokenizer`, `tokenizer_audit_output_from_encoding`, `_is_byte_fallback`, `BYTE_FALLBACK_RE`, `DEFAULT_THRESHOLDS`, plus new functions (see §2–4).
- **Keep:** `code/tests/test_tokenizer_audit.py` for tests; import from new module. Smoke test continues to write report.
- **Unblocks:** Reuse from future CLI / `build_audit_report` orchestrator without circular imports.

#### Phase 2: Fix `byte_fallback_or_proxy_rate` — family-aware detector (**GATED ON RUSTY SIGN-OFF**)

**Problem:** `_is_byte_fallback_or_proxy(piece)` flags `len(stripped)==1 and ord>127` (after stripping `▁Ġ `) as proxy. On Hawaiian text in Llama-3 (byte-level BPE), produces 19% false positives because diacritic chars often merge to single byte-char pieces (lossless, not fallback).

**Function-level changes:**

1. **Add** `detect_tokenizer_family(tokenizer) -> str` (cheap, no network):
   - `byte_level_bpe`: GPT-2 byte-to-unicode map in vocab, OR `Ġ`-prefixed entries, OR class ∈ {`GPT2Tokenizer*`, `LlamaTokenizerFast`} with byte-map probe
   - `sentencepiece_byte_fallback`: `▁`-prefixed vocab AND `<0x00>..<0xFF>` byte tokens (Llama-2, Mistral, Gemma)
   - `wordpiece`: `##`-prefixed vocab
   - `unknown`: fallback (conservative)

2. **Replace** `_is_byte_fallback_or_proxy(piece)` with `_is_byte_fallback_or_proxy(piece, family)`:
   - `byte_level_bpe`: only `BYTE_FALLBACK_RE` matches (literal `<0xNN>` tokens; vanishingly rare). Multi-byte UTF-8 encoded via GPT-2 byte-alphabet = normal vocab, not proxies.
   - `sentencepiece_byte_fallback`: keep current heuristic — `<0xNN>` OR single non-ASCII after stripping `▁` (thresholds calibrated for this family)
   - `wordpiece`: `<0xNN>` OR `[UNK]`
   - `unknown`: same as sentencepiece_byte_fallback (conservative)

3. **Plumb** family through `tokenizer_audit_output_from_encoding` → compute once at top, pass to counter.

4. **Echo** detected family in report: `model.tokenizer_family` in output (add to `tokenizer_metadata_from_model_and_tokenizer` so `model` block is single home for tokenizer identity).

**Expected outcome on Llama-3.1-8B:** `byte_fallback_or_proxy_rate` drops from 0.193 → ≈0.0; `overall_tokens_per_word` and `explicit_byte_fallback_rate` unchanged; decision flips from `no_go` to `go` for overall section (high-diacritic gate then becomes binding constraint).

**Coordination:** Rusty confirms family table (above) and thresholds per family. **Will not land this phase without his sign-off.** Flag this section for Coordinator review gate.

#### Phase 3: Implement `high_diacritic` evaluator

**New function:** `compute_high_diacritic_metrics(samples, tokenizer, *, family, min_samples=10, min_words=1500) -> dict`

**Inputs:** `samples` = iterable of `{"text": str, ...}` rows (harness loads from `data/tokenizer_audit/ulukau_nupepa/.../*.jsonl`; will accept multiple paths once Rusty's nūpepa/Baibala slices land).

**Selection rule (Rusty's spec):** Sample qualifies when:
- Count of `ʻ` (U+02BB) + kahakō vowels (`ā ē ī ō ū` + uppercase) ≥ 3, AND
- Ratio diacritic_chars / words ≥ 0.25

Apply NFC normalization + ʻokina canonicalization before counting.

**Outputs (block `high_diacritic`):**
```json
{
  "status": "evaluated" | "insufficient_samples",
  "sample_count": int,
  "word_count": int,
  "tokens_per_word": float | null,
  "explicit_byte_fallback_rate": float | null,
  "byte_fallback_or_proxy_rate": float | null,
  "selection": {
    "min_diacritics_per_sample": 3,
    "min_diacritics_per_word_ratio": 0.25,
    "min_samples_required": 10,
    "min_words_required": 1500
  }
}
```

**Gate wiring:** Append two new checks to report:
- `high_diacritic_tokens_per_word` (threshold reuses overall max for now; Rusty may want tighter)
- `high_diacritic_byte_fallback_or_proxy_rate` (threshold reuses overall max)
- If `status == "insufficient_samples"`: append `high_diacritic_coverage` to `blocking_reasons`

#### Phase 4: Implement `diacritic_chars` evaluator

**New function:** `compute_standalone_diacritic_chars(tokenizer, charset=None) -> dict`

**Charset (default):** `["ʻ", "ā", "ē", "ī", "ō", "ū", "Ā", "Ē", "Ī", "Ō", "Ū"]` (pre-NFC-normalize).

**Rule:** Encode each char standalone (`tokenizer(char, add_special_tokens=False)`); pass when `token_count ≤ 2`. Return per-item rows:
```json
{ "char": "ʻ", "codepoint": "U+02BB", "ids": [...], "pieces": [...], "token_count": N, "passed": bool }
```

Section-level `passed = all(item.passed)`. `status = "evaluated"` when tokenizer not None, else `"tokenizer_unavailable"`.

**Gate wiring:** Add check `standalone_diacritic_chars` (`value = pass_count / total`, `threshold = 1.0`). Failures append `standalone_diacritic_chars` to `blocking_reasons`.

#### Phase 5: Report-shape changes (additive, schema stays v1)

Keep `tokenizer_audit_report.v1` this pass (schema-v2 + `run_kind` deferred). Additive changes only:
- `model.tokenizer_family` (new key)
- `high_diacritic` body filled per §3 (keys unchanged; `status` flips from `not_evaluated` to `evaluated` / `insufficient_samples`)
- `diacritic_chars.items[]` populated per §4; `status` flips from `not_evaluated`
- `checks[]` gains up to 3 new entries: `high_diacritic_tokens_per_word`, `high_diacritic_byte_fallback_or_proxy_rate`, `standalone_diacritic_chars`
- `recommendation.blocking_reasons` may contain new check names + `high_diacritic_coverage`

**Out of scope:** Schema-v2, `run_kind`, directory contract, identity SHAs, `samples_summary` (deferred; existing decisions.md queued them).

#### Phase 6: Tests (synthetic, except smoke)

**Family detection (4):**
- `_FakeTokenizerByteLevel` (vocab with `Ġhello`) → `"byte_level_bpe"`
- `_FakeTokenizerSentencePieceBF` (vocab with `▁hello`, `<0x00>`, `<0xFF>`) → `"sentencepiece_byte_fallback"`
- `_FakeTokenizerWordPiece` (vocab with `##ing`) → `"wordpiece"`
- Empty/None → `"unknown"`

**Proxy detector (3):**
- `byte_level_bpe`: `["Ġaloha", "ʻ", "ā"]` → count == 0
- `sentencepiece_byte_fallback`: `["▁aloha", "ʻ", "<0xC4>"]` → count == 2
- `wordpiece`: `["aloha", "##ʻ", "[UNK]"]` → count == 1

**high_diacritic (3):**
- 12 qualifying samples, 2,000 words → `status == "evaluated"`, metrics non-null
- 5 qualifying samples → `status == "insufficient_samples"`, `blocking_reasons` contains `high_diacritic_coverage`
- No diacritics → 0 qualifying, `insufficient_samples`

**diacritic_chars (2):**
- Stub where every char → 1 token → all items `passed=true`
- Stub where ʻ → 3 tokens → `passed=false`, `blocking_reasons` contains `standalone_diacritic_chars`

**Report shape (1):**
- Build end-to-end with synthetic encodings; assert `model.tokenizer_family` present, all new check names, `blocking_reasons` is closed enum

**Smoke test:** Leave as-is (still HF/transformers env-dependent); after §2–4 land should produce Llama report with `byte_fallback_or_proxy_rate ≈ 0` + two sections populated.

#### Phase 7: Execution sequence

1. §1 module split (lands first; existing tests still pass)
2. §2 family detector + proxy fix + tests — **gated on Rusty sign-off**
3. §3 + §4 evaluators + tests
4. Smoke re-run against Llama-3.1-8B → write fresh `official/<ts>__meta-llama_Llama-3.1-8B.json`
5. Compare new report vs. `20260430T041606Z` line-by-line in next decision update

### Out of Scope (deferred to existing decisions.md)

- Schema v2 / `run_kind` / `dry_run` removal / `dryrun/` directory rename
- `model.model_repo_sha` / `tokenizer_sha256` / `tokenizer_fingerprint_sha256` (orchestrator-owned, Hub-aware)
- `samples_summary` block + gitignored `debug.jsonl`
- Pytest parametrization of model_id / `run_kind` for smoke

These remain queued in harness-cleanup decision (2026-04-30T03:43Z) and will land after Llama gate unblocks.

### Coordination Asks

- **Rusty:** Confirm family table in §2 and whether high-diacritic thresholds in §3 should differ from overall
- **Basher:** Ack schema stays v1 this pass (additive); manifest pin work waits
- **Coordinator:** Route §2 decision back through Rusty before Linus implements


---

## Decision: Linus — Tokenizer audit cleanup implementation (status: ✅ Implemented)

**Date:** 2026-04-30T04:44:24Z  
**Status:** Implemented — all 33 unit tests passing locally, 1 smoke skipped (transformers unavailable).

### Summary

Linus completed tokenizer audit harness cleanup (phases 1–6 of 7-phase plan). Module split into reusable helpers, family detection algorithm implemented, proxy applicability fixed for byte-level BPE, roundtrip lossless check added, high-diacritic and diacritic-chars evaluators deployed.

### Files

- **New:** `code/llm_hawaii/tokenizer_audit_helpers.py` — all reusable logic.
- **Refactor:** `code/tests/test_tokenizer_audit.py` — imports from helpers; smoke test guarded with `@skipUnless(transformers)` and skips gracefully if Llama-3 tokenizer/eval slice unavailable.
- **Preserved:** `code/llm_hawaii/data.py`, `data/tokenizer_audit/official/20260430T041606Z__meta-llama_Llama-3.1-8B.json` (existing official report untouched, per task constraint).

### Schema (conservative; v1 preserved)

- `schema_version` remains `tokenizer_audit_report.v1`. Full v2 refactor (drop `dry_run`, add `run_kind`, `generated_at`, `samples_summary`) is **out of scope** for this pass; all changes are additive and backward-compatible with v1 readers.
- **New fields:**
  - `model.tokenizer_family`: populated by `detect_tokenizer_family`. Values: `byte_level_bpe`, `sentencepiece_byte_fallback`, `unknown`, or `null` when no tokenizer provided.
  - `checks[*].status`: explicit field (`evaluated` | `not_applicable` | `not_evaluated` | `insufficient_samples`).
  - `checks[*].reason`: optional explanatory text.
- **Fixed semantics:**
  - `recommendation.blocking_reasons` now contains only checks where `passed is False` — `not_applicable` and `not_evaluated` checks are **never** added (fixes prior bug where `passed=None` could block).
  - `byte_fallback_or_proxy_rate`: marked `not_applicable` for `byte_level_bpe` (numeric value preserved for forensics; threshold unchanged at 0.01).
  - `roundtrip_lossless`: new blocking check appended whenever both `text` and `tokenizer` provided; comparison exact after NFC normalization (whitespace changes are real failures).
  - `high_diacritic`: populated from Hawaiian diacritic-heavy spans (ʻokina + kahakō vowels). Returns `status ∈ {evaluated, insufficient_samples, not_evaluated}` plus metrics. Minimum gates (≥10 high-diacritic samples, ≥1,500 words) active via checks.
  - `diacritic_chars`: populated for `ʻ ā ē ī ō ū` (and uppercase). Each item carries `decode_ok` and `passed = decode_ok AND token_count <= thresholds["standalone_diacritic_char_max_tokens"]` (default 2). Blocking check appended iff any char fails.

### Threshold defaults (all frozen, no changes)

```
min_words:                                          1500
min_high_diacritic_samples:                         10
overall_tokens_per_word_max:                       2.50
explicit_byte_fallback_rate_max:                   0.0   (blocking, all families)
byte_fallback_or_proxy_rate_max:                   0.01  (not_applicable for byte_level_bpe, blocking for others)
high_diacritic_tokens_per_word_max:                3.25
high_diacritic_byte_fallback_or_proxy_rate_max:    0.01  (not_applicable for byte_level_bpe, blocking for others)
standalone_diacritic_char_max_tokens:              2
```

### Family detection algorithm

1. Vocab contains any `<0xNN>` token → `sentencepiece_byte_fallback`.
2. Explicit `tokenizer_family` hint in source → that hint.
3. Tokenizer class ∈ {`TokenizersBackend`, `GPT2Tokenizer*`, `LlamaTokenizerFast`, `Qwen2Tokenizer*`} → `byte_level_bpe`.
4. Vocab contains ≥200/256 GPT-2 byte_to_unicode chars → `byte_level_bpe`.
5. Otherwise → `unknown` (proxy rule conservatively kept applicable).

**Key:** Generic `PreTrainedTokenizerFast` alone is insufficient to classify byte-level BPE; without GPT-2 byte chars or explicit hint, remains `unknown`.

### SHA / Identity

No SHA256 computation in helpers (per Rusty constraint and prior Linus contract). `hf_commit_sha` resolution unchanged: tokenizer attr → `init_kwargs` → `huggingface_hub.try_to_load_from_cache` snapshot path. Tests monkeypatch `helpers._hf_commit_sha_from_cached_snapshot` to exercise cache path without real cache.

### Test coverage (33 unit tests, 1 smoke skipped)

- **Metadata (9):** All prior coverage migrated; now verifying `tokenizer_family` populated.
- **Family detection (6):** Llama, SPM-BF, unknown, generic fast unknown, explicit hint, metadata integration.
- **Proxy applicability + blocking-reason semantics (4):** not_applicable for BLBPE, blocking for unknown, not-evaluated never blocks, explicit byte fallback always blocks.
- **Roundtrip (4):** Passes, exact whitespace required, blocks on lossy, omitted when text/tokenizer missing.
- **High-diacritic (4):** Paragraph filter, BLBPE not-applicable proxy, threshold gating into blocking_reasons, insufficient_samples.
- **Diacritic chars (5):** Lossless pass, decode-fail, token-count gate, blocking-reason wiring, tokenizer_unavailable.

### Out of scope (deferred)

- Schema v2 + `run_kind`, `generated_at`, `samples_summary` refactor (defer until v2 schema owner lands).
- Off-report debug JSONL dump (defer).
- Re-running Llama-3 audit (no `transformers` in this env; gated model; phase 7 TBD).

### Next steps (Phase 7)

- Re-run against Llama-3.1-8B tokenizer when `transformers` available.
- Write fresh official report to `data/tokenizer_audit/official/{timestamp}__meta-llama_Llama-3.1-8B.json`.
- Verify `tokenizer_family=byte_level_bpe`, `roundtrip_lossless=true`, all sections populated.
- Compare new report vs. `20260430T041606Z` baseline for gate decision update.

**Orchestration log:** `.squad/orchestration-log/2026-04-30T04:44:24Z-linus-tokenizer-audit-cleanup-implementation.md`  
**Session log:** `.squad/log/2026-04-30T04:44:24Z-tokenizer-audit-cleanup-implementation.md`



---

## Decision: Basher + Rusty — Between-checkpoint evaluation signals for Stage-1 Hawaiian LLM monitoring

**Date:** 2026-04-30T07:00:17Z  
**Owners:** Basher (Training Engineer), Rusty (NLP Researcher)  
**Status:** Proposed signal contract; no code/doc changes. Read-only assessment.  
**Inputs reviewed:** `code/llm_hawaii/evaluate.py`, `scripts/run_stage0_eval.sh`, `docs/eval_pipeline.md`, `docs/training-pipeline.md`, `docs/eval-runs/stage0/20260430T063118Z__stage0_base_eval_summary.json`.  

### Anchor

Stage 0 baseline (Llama-3.1-8B base, FineWeb-2 `haw_Latn` dev, 621 rows):

- `hawaiian_ppl = 7.9152`
- `eval_file_sha256 = 6e2595be…60db` (frozen)
- Single-prompt orthography: `is_nfc=true`, `okina=15`, `wrong_okina=0`, `kahako=9`, `diacritic_density_bin=high`.

This is the anchor for every Stage 1 checkpoint comparison. Always plot Stage 0 alongside checkpoint deltas.

### What we check at every checkpoint (cheap cadence)

Cheap signals run on frozen eval set (same `eval_file_sha256` + `eval_suite_sha` as Stage-0 baseline):

**1. Hawaiian held-out PPL:** On FineWeb-2 dev split (621 rows). Primary trend signal. Per-source/register slice also required (no headline-only averaging).

**2. Orthography on fixed prompt set (≥5–10 prompts, spanning low/medium/high diacritic density):**
   - `is_nfc` — must stay `true`
   - `wrong_okina` — must stay `0`
   - `okina`, `kahako`, `diacritic_density` — track absolute counts; sudden drops on known-high-density prompt = orthography collapse

**3. Generation SHA drift:** `generation_sha256.sample_*` vs previous checkpoint — confirms model actually changed; identical SHAs = training stuck or eval cached.

**4. Training-side companions:** Train loss, grad norm, LR logged at same step. PPL anomalies only interpretable next to these.

**5. English PPL delta:** vs base (currently unwired in `evaluate.py` — gap noted).

**6. Tokenizer behavior on outputs:** tokens/word, byte-fallback rate. Drift up = model learning to fragment Hawaiian.

### Gate-level signals (promotion / stage boundary only)

- English PPL within ±20% of base
- Per-source/register PPL slice (TODO at `evaluate.py:84`)
- W1 manual micro-eval (when accepted rows exist)
- Held-out (not dev) FineWeb-2 split (266 rows) reserved for stage-boundary gates

### How we declare "improving" (conjunction required, all of these must be true)

1. `hawaiian_ppl` ≤ previous checkpoint, monotone-or-flat across ≥2 checkpoints (allow ±2% noise band); no register slice up >5% rel
2. ʻokina survival = 1.0; `wrong_okina = 0`; `is_nfc = true` on 100% of generations; `combining_macron = 0`
3. Kahakō retention ≥ reference distribution within tolerance (no silent stripping)
4. `english_ppl_delta` ≤ +20% rel vs base
5. Tokens/word and byte-fallback rate not worse than Stage-0 audit baseline
6. No new contamination overlap; hallucination rate flat-or-down
7. (Once W1 live) per-category pass-rates flat-or-up

Stage 1 gate target: ≥20% relative PPL reduction vs 7.9152 → **≤ ~6.33**.

### How we declare "getting worse" (any one tripwire is sufficient)

- ʻokina collapses to U+2018 / U+0027 anywhere in generations **[Stage-1 hard-fail gate]**
- Kahakō stripped, or NFD output (`is_nfc=false` or combining macron present)
- `wrong_okina` becomes non-zero or trends up
- PPL up > 5% checkpoint-to-checkpoint, or up across 2 consecutive checkpoints
- English PPL up >20% rel (catastrophic forgetting; triggers rerun with more rehearsal)
- High-diacritic-density slice degrades while low-density improves (orthography handling regression masked by averaging)
- Tokens/word or byte-fallback up on outputs (model learning to fragment)
- Generation degeneracy: repetition loops, English collapse, register collapse on open-ended Hawaiian prompts
- Train↔dev gap widening with dev↔holdout flat (overfit) or dev↔holdout gap widening (cluster leak)
- n-gram overlap of generations vs `eval_hashes.jsonl` rising (leakage suspect)
- Hallucination rate climbing on real-Hawaiian-entity probes
- Provider/environment handoff disagreement on same checkpoint (harness drift, not model quality)

The asymmetry is intentional: **improvement requires conjunction; regression requires only one tripwire.** Held-out PPL alone cannot license a "better" claim.

### Slicing required (not optional)

Every cheap eval reports the same generations sliced along:

- **Source / register** — period/biblical vs contemporary vs governmental/educational (catches "model only sounds like 1860s nūpepa")
- **Diacritic density** — `none`/`low`/`medium`/`high` bins (already wired in `metrics.py`; present in Stage-0 summary)
- **Length** — short / medium / long
- **Tokenizer behavior bin** — items binned by input tokens/word + byte-fallback rate
- **Split** — train↔dev↔holdout gaps
- **W1 category** (once accepted) — `okina_survival`, `kahako_retention`, `unicode_nfc`, `tokenizer_survival`, `generation_sanity`

### Fair-comparison preconditions (must be identical across all compared checkpoints)

- `eval_file_sha256` (already recorded)
- Prompt set + `generation_sha256` keys
- Decoding config: `max_length`, `do_sample=False`, `max_new_tokens`
- Tokenizer SHA, base-model SHA
- **Eval-time dtype/quantization for the base model**
- Re-anchor every plot against Stage 0 (7.9152)
- Eval set is never re-tuned mid-run

### Critical corrections (reported, not implemented in this decision)

1. **`evaluate.py:59` hard-codes `dtype=torch.float16`.** A100 training runs bf16. Loading bf16-trained adapter on fp16 base for eval introduces precision mismatch masking/amplifying PPL deltas. Mirror training dtype (bf16 on A100; fp16 only as Turing fallback) before first 7B/8B checkpoint comparison is trusted.

2. **`run_stage0_eval.sh` exercises one prompt.** Per-checkpoint orthography trending needs fixed ≥5–10 prompt set spanning low/medium/high diacritic density; otherwise per-prompt noise dominates signal.

3. **No English-PPL probe in `evaluate.py`.** Stage 1 gate #3 (`training-pipeline.md` §2.4) currently unmeasurable. Wire it or explicitly re-scope the gate.

4. **No per-source slice PPL** (existing TODO at `evaluate.py:84`). Without it, regressions cannot be attributed to nūpepa-vs-contemporary skew.

5. **Run-report schema partially populated.** `evaluate.py` returns subset; promote to full `run_report.json` next to each checkpoint per `eval_pipeline.md` §8 before gate calls.

6. **Stage-0 orthography baseline carries n=1.** The `orthography_metrics.sample_0` block (one generation from one prompt) is not distributional. Per-checkpoint orthography deltas must compute against full dev slice (621 rows). Held-out PPL (7.915) *is* usable anchor (computed over eval file, not sample).

7. **W1 manual micro-eval not yet live.** Proposed Stage-2 category (once rows accepted) is wiring-only until real accepted rows exist; not reportable benchmark until then.

### Out of scope

- No GPU spend implied; no code or doc edits performed by this note.
- Tokenizer-audit gate (separate, currently `no_go`) still blocks Stage 1 spend independently.
- Stage-2 chrF / direction / "always translate" probes (covered in `eval_pipeline.md` §3.3 and §6, not this checkpoint).
- Human spot eval (≥20–50 minimum, full eval only at stage gates; not between-checkpoint signal).

### Flagged for later action

- Wire English PPL probe in `evaluate.py`
- Implement per-source/register PPL slicing (resolve TODO at `evaluate.py:84`)
- Fix dtype mismatch (mirror training dtype in eval harness)
- Expand Stage-0 orthography baseline to ≥5–10 prompts across density bins before Stage-1 checkpoint comparison begins
- Formalize `run_report.json` schema for full gate reporting (per `eval_pipeline.md` §8)

**Orchestration logs:** `.squad/orchestration-log/2026-04-30T07-00-17Z-basher.md`, `.squad/orchestration-log/2026-04-30T07-00-17Z-rusty.md`  
**Session log:** `.squad/log/2026-04-30T07-00-17Z-eval-checkpoints.md`


---

## Decision Timeline: Stage 0 W1 manual micro-eval metadata + orthography wiring (2026-04-30)

> Updated 2026-04-30T08:08:04Z: Linus W1 revision approved by Rusty (42/42 tests green, four blockers resolved, corrected source directive honored). Basher's prior in-flight work rejected per strict reviewer lockout; Linus performed independent complete rework. User directive corrected: W1 expert-validated source is `data/raw/ulukau_nupepa/human_fetch.txt`; `scripts/_convert_ulukau_human_fetch.py` is parser/normalizer context only, not the source. Orchestration logs written. Decisions merged from inbox with deduplication; superseded directives marked.


---

### User Directive (Superseded): W1 expert-validated source path — Initial statement

**Date/Time:** 2026-04-30T07:52:13Z  
**By:** yashasg (via Copilot)  
**Statement:** For W1 eval, use `scripts/_convert_ulukau_human_fetch.py` as the source path for Ulukau human-fetch rows and consider those rows expert-validated.  
**Status:** **SUPERSEDED** by the correction below (2026-04-30T07:59:13Z).


---

### User Directive (Current): W1 expert-validated source path — Corrected

**Date/Time:** 2026-04-30T07:59:13Z  
**By:** yashasg (via Copilot)  
**Statement:** For W1 eval expert-validated Ulukau rows, the data source is `data/raw/ulukau_nupepa/human_fetch.txt` (sections: `# English` / `# Hawaiian`; use Hawaiian section for W1). `scripts/_convert_ulukau_human_fetch.py` is the related parser/normalizer (NFC, ʻokina-folding, basic stats), not the source of truth.  
**Status:** Current. Supersedes 2026-04-30T07:52:13Z directive.


---

## Decision: Rusty — W1 Stage 0 contract (read-only approved)

**Date:** 2026-04-30  
**Owner:** Rusty (NLP Researcher)  
**Status:** Approved as reference contract. Implementation belongs to others; this defines requirements before the next Stage 0 run.

### Why this is needed

`evaluate.py:522` currently hard-codes `manual_w1 = {"status": "not_configured", ...}` unconditionally. A populated, human-accepted off-git W1 TSV at `data/evals/manual_w1/w1-haw-micro-eval.tsv` is invisible to Stage 0 — no accepted rows are counted.

This contract closes that gap without shipping a fabricated benchmark.

### Stage 0 W1 state machine (5 states)

1. **`absent`** — neither JSONL nor TSV exists at `data/evals/manual_w1/`. Stage 0 does not fail.
2. **`invalid`** — file exists but fails loader checks (NFC, ʻokina codepoint, combining macron, density, header, no duplicate item_id). **Stage 0 exits non-zero.** Raw text never in errors; line/field-only format.
3. **`draft_only`** — file valid, zero `review_status=accepted` rows. Stage 0 does not fail.
4. **`evaluated`** — ≥1 accepted row exists and passes orthography checks. Includes mechanical category pass counts (okina_survival, kahako_retention, unicode_nfc, tokenizer_survival), `overall_pass_rate` over mechanically-checkable rows only.
5. **`harness_error`** — accepted rows exist but inference/tokenizer probe crashed. Stage 0 exits non-zero.

### Fields for `evaluated` shape

- `w1_suite_sha256` — sha256 over sorted `(item_id, sha256_normalized)` pairs of accepted rows only.
- `accepted_item_hashes` — sorted list of `sha256_normalized` strings (hashes only, no text).
- `schema_version_seen` — `"manual-w1-tsv-v1"` on TSV-capable branches; `null` otherwise.
- Row counts: `total_valid`, `draft`, `reviewed`, `accepted`, `scored`.
- `accepted_by_category` and `accepted_by_diacritic_density_bin` — category/bin name counts.
- Mechanical pass counts per category + `overall_pass_rate`.
- Tripwires: `wrong_okina_nonzero`, `nfc_failures`, `combining_macron_nonzero`.

### Off-Git safety constraints

- Read from `data/evals/manual_w1/` only.
- Tracked summary carries: status, reason, file path, file SHA, schema version, row counts, category/bin counts, `item_id`s, `sha256_normalized`s, mechanical pass counts, tripwires. **Never** raw prompt/reference/notes/author.
- `first_errors` uses line+field-only format (no row content).
- No new files written under `data-sources/manual-eval/`. Populated TSVs stay off-git.
- Generations go through hash-only treatment (no raw Hawaiian in tracked summary).

### Verdict

**Approved.** Wire the loader into Stage 0 per the state machine before the next Stage 0 run.


---

## Decision: Basher — W1 manual micro-eval status wired into Stage 0 (metadata only)

**Date:** 2026-04-30  
**Author:** Basher (Training Engineer)  
**Status:** Implementation circulated; review requested from Rusty and Linus.

### Summary

`evaluate.py` now reads the off-git W1 TSV and reports a stable status object on every Stage 0 run. No raw prompts/references are emitted.

### Status enum

| status       | meaning |
|--------------|---------|
| not_configured | probe explicitly disabled (`--no-manual-w1`) |
| missing | TSV file not present at resolved path |
| invalid | file present, but no header / header mismatch / unreadable; `tsv_sha256` emitted when available |
| draft_only | parsed cleanly, **zero** `review_status=accepted` rows |
| evaluated | accepted rows present and validated. **Metadata-evaluated, not task-scored.** |

`scoring_status: "not_wired"` on every output. Row-level model scoring is a follow-up.

### Fields on `evaluated` / `draft_only`

- `path`, `tsv_sha256`, `tsv_size_bytes`
- `row_count`, `review_status_counts`
- `accepted_count` = `eval_consumable_count` (alias intentional)
- `accepted_category_counts`, `accepted_diacritic_density_bin_counts`
- `nfc_normalized_false_count` (loud but non-blocking; authoritative validator in `scripts/315_hash_manual_w1_eval.py`)
- `scoring_status`, `scoring_reason`

### Validation

- `python3 -m py_compile code/llm_hawaii/evaluate.py` → clean.
- `sh -n scripts/run_stage0_eval.sh` → clean.
- `cd code && PYTHONPATH=. python3 -m unittest tests.test_evaluate tests.test_metrics` → 25/25 green.


---

## Review: Rusty — W1 Stage 0 implementation review (Basher's work)

**Date:** 2026-04-30  
**Reviewer:** Rusty (NLP Researcher)  
**Subject:** Basher's W1 metadata/status wiring in `code/llm_hawaii/evaluate.py` + tests + `scripts/run_stage0_eval.sh` projection.

### Verdict

**Reject — request revision.** The submission is close, well-scoped, and honest about scope. Three contract requirements are missing:

1. **`accepted_item_hashes`** (blocking) — sorted list of `sha256_normalized` values for accepted rows. Without it, "did the accepted set change?" cannot be answered from the tracked summary.
2. **`w1_suite_sha256`** (blocking) — sha256 over sorted `(item_id, sha256_normalized)` pairs of accepted rows. Distinguishes "drafts churned" from "accepted set churned".
3. **`schema_version_seen`** (blocking, low cost) — hardcode `"manual-w1-tsv-v1"` on TSV-capable branches; `null` otherwise.
4. **NFC / ʻokina / combining-macron on accepted rows must flip `invalid`** (blocking) — not silently counted. Accepted-row failures are contract violations; must fail loud.

### Non-blocking naming drift

- `missing`/`absent`, `tsv_sha256`/`input_sha256`, `accepted_category_counts`/`accepted_by_category`. Pick one per field; reconcile in one document.

### Recommended next agent

**Basher** — implementation-side, contained, mechanical fixes. All 25 tests to remain green.


---

## Review: Linus — W1 Stage 0 summary review (Basher's wiring)

**Date:** 2026-04-30  
**Reviewer:** Linus (Data Engineer)  
**Subject:** Read-only review of Basher's W1 manual TSV → Stage 0 wiring for cross-checkpoint comparability.

### Verdict

**Reject — fixes required.** Two items in Rusty's approved contract are not honored:

1. **`invalid` state must fail the run, not silently report** — Rusty's contract: "Stage 0 must not swallow this. It writes the `invalid` block to the report and exits the eval with a non-zero status." Today the CLI exits 0. Conditional on this fix, `run_stage0_eval.sh` already uses `set -eu` and pipes via temp file, so a non-zero exit will abort the summary writer as desired.

2. **Add `accepted_suite_sha256` and `accepted_item_hashes` on the `evaluated` shape** — required for the cross-checkpoint aggregator to answer "did the *accepted* eval set change between Stage-0 runs A and B?" without re-reading the off-git TSV. `tsv_sha256` covers non-accepted noise; these two fields disambiguate actual accepted-set churn.

### What's good (will not change)

- Raw-text exclusion is solid. No prompt/reference/notes/author.
- `scoring_status: "not_wired"` is on every shape.
- `accepted_count == eval_consumable_count` alias is intentional and stable.
- Draft/reviewed rows are tallied but never counted as benchmark-reportable.
- `run_stage0_eval.sh` projection is correct.
- Status enum is downstream-diffable across 5 values.

### Schema diff confirmation (conditional on fixes)

Cross-checkpoint aggregator can switch on:

1. `manual_w1.status` — primary discriminator (5 values).
2. `manual_w1.tsv_sha256` — did the underlying off-git file change at all?
3. `manual_w1.accepted_suite_sha256` *(to be added)* — did the *accepted* eval set change identity?
4. `manual_w1.accepted_count` — did the human-review queue advance numerically?
5. `manual_w1.accepted_category_counts` / `accepted_diacritic_density_bin_counts` — did the slice distribution shift?
6. `manual_w1.scoring_status` — flips from `not_wired` to `wired` when row-level scoring lands.

### Required fixes (ordered)

1. **`invalid` → non-zero CLI exit** — one-line `sys.exit(2)` after report write when `report["manual_w1"]["status"] == "invalid"`. Add unit tests (header-mismatch fixture, passing path tests for `draft_only`+`evaluated`).
2. **Add `accepted_suite_sha256` and `accepted_item_hashes` on `evaluated`** — read `sha256_normalized` from accepted rows; field is already in `MANUAL_W1_HEADER`. Two new unit tests: suite sha deterministic; suite sha changes when accepted set's identities change.

### Recommended next agent

**Basher** — implementation-side contract-compliance work.


---

## Decision: Basher — W1 contract-revision (Stage 0 eval) [In-flight]

**Date:** 2026-04-30  
**Author:** Basher (Training Engineer)  
**Subject:** Revision of `manual_w1_status` in `code/llm_hawaii/evaluate.py` to address four blocking gaps from Rusty's review.

### What changed (draft)

1. **`accepted_item_hashes`** — sorted list of canonical `sha256_normalized` values for `review_status=accepted` rows. Empty list when no accepted rows.
2. **`w1_suite_sha256`** — sha256 over sorted `(item_id, sha256_normalized)` pairs of accepted rows, encoded as `item_id\tsha\n`. `null` when no accepted rows. Stable across row reorder; flips when the accepted set churns.
3. **`schema_version_seen`** — hardcoded `"manual-w1-tsv-v1"` on `evaluated` and `draft_only`; `null` on `invalid`/`missing`/`not_configured`.
4. **Strict orthographic gate on accepted rows** — any `review_status=accepted` row whose `nfc_normalized != "true"`, OR fails NFC, OR carries U+0304, OR carries wrong-ʻokina codepoint flips the file to `status=invalid` with `error_count` and `first_errors`.

### Helper-reuse decision

Mirrored the hash formula from `scripts/315_hash_manual_w1_eval.py` into `evaluate._manual_w1_sha256_normalized` with a pinning unit test (script filename is not a legal Python module identifier).

### Validation (draft)

- `python3 -m py_compile …` → clean.
- `sh -n scripts/run_stage0_eval.sh` → clean.
- `cd code && PYTHONPATH=. python3 -m unittest tests.test_evaluate tests.test_metrics` → **36/36 green** (+11 covering the four contract gaps).

### Status

Circulated for Rusty re-review and Linus sign-off on run-script projection.

**⚠️ Note:** This work was subsequently rejected by Linus and the coordinator enforced strict reviewer lockout (rejected author cannot revise). Linus performed independent complete rework (see Linus W1 revision below).


---

## Decision: Linus — W1 revision (Stage 0 eval) [APPROVED]

**Date:** 2026-04-30  
**Author:** Linus (Data Engineer)  
**Subject:** Final revision of `manual_w1` / Stage 0 W1 wiring after Basher's in-flight patch was rejected. **This decision is the authoritative data contract.**

**Status:** ✅ **APPROVED by Rusty** (42/42 tests green, all four blockers resolved, corrected source directive honored).

### Final data contract — `report["manual_w1"]`

Stable status enum (mutually exclusive, mandatory):

| status       | trigger |
|--------------|---------|
| not_configured | probe explicitly disabled (`--no-manual-w1` / `USE_MANUAL_W1=0`) |
| missing | TSV file absent at resolved path |
| invalid | unreadable file, no header, header mismatch, **or** any `review_status=accepted` row that fails NFC / carries U+0304 / uses wrong-ʻokina codepoint / has `nfc_normalized != "true"` |
| draft_only | TSV parsed cleanly, zero `review_status=accepted` rows |
| evaluated | accepted rows present and orthographically clean. **Metadata-evaluated, not task-scored.** |

`scoring_status: "not_wired"` on every output. This revision is metadata + orthography validation only; W1 row-level model scoring is a follow-up.

### Fields by status

| field | not_configured | missing | invalid | draft_only | evaluated |
|-------|:-:|:-:|:-:|:-:|:-:|
| `status` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `scoring_status` (= `"not_wired"`) | ✓ | ✓ | ✓ | ✓ | ✓ |
| `scoring_reason` | — | ✓ | ✓ | ✓ | ✓ |
| `schema_version_seen` | `null` | `null` | `null` | `"manual-w1-tsv-v1"` | `"manual-w1-tsv-v1"` |
| `path` | — | ✓ | ✓ | ✓ | ✓ |
| `tsv_sha256`, `tsv_size_bytes` | — | — | ✓ (when readable) | ✓ | ✓ |
| `row_count`, `review_status_counts` | — | — | ✓ (when parsed) | ✓ | ✓ |
| `accepted_count` = `eval_consumable_count` | — | — | `0` on accepted-row-orth fail | `0` | `>0` |
| `accepted_category_counts` | — | — | (counted for telemetry) | `{}` | populated |
| `accepted_diacritic_density_bin_counts` | — | — | (counted for telemetry) | `{}` | populated |
| `nfc_normalized_false_count` | — | — | ✓ | ✓ | ✓ |
| `accepted_item_hashes` (sorted) | — | — | `[]` * | `[]` | sorted SHA list |
| `w1_suite_sha256` | — | — | `null` * | `null` | hex SHA |
| `error_count`, `first_errors` | — | — | accepted-row-orth branch only | — | — |

\* Emitted on the accepted-row-orthographic-failure `invalid` branch only. Header-mismatch / no-header / read-failed `invalid` branches keep their existing minimal shape.

### Hash formula (frozen)

`sha256_normalized = sha256(NFC(prompt) + U+000A + NFC(reference))`

Mirrored verbatim from `scripts/315_hash_manual_w1_eval.py:compute_hash` into `evaluate._manual_w1_sha256_normalized`. The byte-exact match is pinned by unit test.

`w1_suite_sha256 = sha256(join sorted "{item_id}\t{sha256_normalized}\n" over accepted rows only)` — stable under row reorder; flips when the *accepted* set churns even if the file SHA does not.

### `first_errors` safety contract

Every entry is a string `line N: <field> <category>` where `<field> ∈ {prompt, reference}` and `<category>` is one of `is not NFC-normalized`, `contains combining macron U+0304`, `contains wrong ʻokina/apostrophe codepoint`, `nfc_normalized field is not 'true' on accepted row`, `item_id is empty on accepted row`. **No row contents, no prompt/reference text, no notes/author.** Capped at 10 entries; `error_count` carries the true total.

### CLI exit-code posture

`python -m llm_hawaii.evaluate` writes the report JSON first, then:

- exits **2** when `manual_w1.status == "invalid"` (the report dict is still complete and on stdout);
- exits **0** otherwise (`missing`, `not_configured`, `draft_only`, `evaluated`, or `manual_w1` absent).

Implemented via `_cli_exit_code(report)` (pure, testable, no I/O).

### Shell propagation

`scripts/run_stage0_eval.sh` captures the evaluate.py exit code and writes the tracked summary projection regardless (so the artifact + hash-only summary are both on disk for post-mortem), then propagates the non-zero exit. The tracked summary's `metrics.manual_w1` is a verbatim pass-through.

### Corrected source directive (user correction, 2026-04-30)

The trusted source for W1 expert-validated Hawaiian rows is **`data/raw/ulukau_nupepa/human_fetch.txt`**, sectioned `# English` / `# Hawaiian`. For W1, use the Hawaiian section only.

`scripts/_convert_ulukau_human_fetch.py` is a *parser/normalizer* (NFC, ʻokina-variant folding to U+02BB, basic stats) that informs converting the raw text into the `prompt` / `reference` shape the W1 TSV expects. It is **not** the source of truth.

The previous decision file (`copilot-directive-20260430T075213Z.md`) named the converter script as the source path; that was superseded by `copilot-directive-20260430T075913Z.md`. This decision aligns with the later directive.

Populated W1 TSVs derived from `human_fetch.txt` remain off-git under `data/evals/manual_w1/` per `data-sources/manual-eval/README.md`.

### Validation

- `python3 -m py_compile code/llm_hawaii/evaluate.py scripts/315_hash_manual_w1_eval.py scripts/_convert_ulukau_human_fetch.py` — clean.
- `sh -n scripts/run_stage0_eval.sh` — clean.
- `cd code && PYTHONPATH=. python3 -m unittest tests.test_evaluate tests.test_metrics` — **42/42 green**.
- `git --no-pager diff --check` — clean.

### Out of scope (still)

- Row-level model scoring (`scoring_status` stays `not_wired`).
- `harness_error` 5th-status branch — re-introduce when scoring lands and there is an inference path that can crash.
- JSONL-first wiring (read `sha256_normalized` and `MANUAL_W1_JSONL_SCHEMA_VERSION` directly from W1 JSONL). Natural follow-up.
- English PPL probe and `hawaiian_ppl_by_source` — separate work; both still emit `status: "not_configured"` placeholders.

### Asks

- **Coordinator:** if anyone touches the W1 TSV format or the canonical hash formula, the `evaluate._manual_w1_sha256_normalized` mirror and the unit test that pins it must be updated in the same change.


---

## Review: Rusty — W1 Linus revision review [APPROVED]

**Date:** 2026-04-30  
**Reviewer:** Rusty (NLP Researcher)  
**Subject under review:** `.squad/decisions/inbox/linus-w1-revision.md`

### Verdict — **APPROVE**

The four blockers from `rusty-w1-implementation-review.md` are addressed and the corrected source directive is honored throughout. Validation re-runs clean: **42/42 tests green**, matching Linus's claim.

### Item-by-item

1. **Hash + suite metadata, no raw text — PASS.**
   - `evaluate.py:378-419` collects `(item_id, sha256_normalized)` per accepted row, sorts pairs, emits `accepted_item_hashes` as the sorted SHA list.
   - Computes `w1_suite_sha256` over sorted `"{item_id}\t{sha256}\n"` pairs.
   - Hash formula (`NFC(prompt) + LF + NFC(reference)`) mirrors `scripts/315_hash_manual_w1_eval.py:hash_material/compute_hash` byte-for-byte.
   - Pinned by tests `TestManualW1HashesAndSuite`.
   - Suite SHA stable under row reorder; flips on accepted-set churn.
   - No prompt / reference / notes / author text written on any branch.

2. **`schema_version_seen` semantics — PASS.**
   - `MANUAL_W1_TSV_SCHEMA_VERSION = "manual-w1-tsv-v1"` set only on TSV-capable status branches (`draft_only`, `evaluated`) at `evaluate.py:404`.
   - `not_configured` / `missing` / `invalid` all emit `None`.
   - JSONL properly reserved-only; comment block + unused `MANUAL_W1_JSONL_SCHEMA_VERSION` reference make clear the JSONL switch is a follow-up.

3. **Accepted-row strict gate, drafts loose — PASS.**
   - `evaluate.py:323-376`: drafts/reviewed rows skip strict gate via `if rs != "accepted": continue`.
   - On accepted rows: each of `nfc_normalized != "true"`, non-NFC `prompt`/`reference`, `count_combining_macron > 0`, `count_wrong_okina > 0`, empty `item_id` appends `f"line {line_no}: <field> <category>"` strings only — no row content.
   - Tests confirm both strict on accepted and loose on drafts.

4. **CLI exit-2 + shell propagation — PASS.**
   - `_cli_exit_code` returns `2` iff `report["manual_w1"]["status"] == "invalid"`, else `0`.
   - `main()` prints JSON report first, then returns exit code.
   - `scripts/run_stage0_eval.sh:121` captures rc with `… > "$TMP_OUTPUT" && EVAL_RC=0 || EVAL_RC=$?`.
   - Unconditionally writes tracked summary projection (forwards `report.get("manual_w1", …)` verbatim).
   - Propagates non-zero exit only at the very end. `set -eu` does not eat rc because of `&& … || EVAL_RC=$?` capture pattern.

5. **Corrected source directive — PASS.**
   - `data/raw/ulukau_nupepa/human_fetch.txt` exists on disk with expected `# English` / `# Hawaiian` sections.
   - `scripts/_convert_ulukau_human_fetch.py` now (a) describes itself as "parser/normalizer, not the source of truth", (b) names trusted source path explicitly, (c) has `SRC = REPO / "data/raw/ulukau_nupepa/human_fetch.txt"` (no `.md` typo).
   - Both `code/README.md` and `docs/eval_pipeline.md` state converter is parser context, not the source.
   - Linus's revision file mirrors and supersedes earlier directive correctly.

6. **Docs and tests match contract; raw data not committed — PASS.**
   - `docs/eval_pipeline.md` §8.1 describes all contract fields, NFC invalid trigger, `first_errors` shape, exit-2 posture, wrapper behavior, corrected source directive.
   - `code/README.md` mirrors same.
   - `data/` is gitignored; `git check-ignore` confirms both `data/raw/ulukau_nupepa/human_fetch.txt` and `data/evals/manual_w1/w1-haw-micro-eval.tsv` are ignored.

### Notes for follow-up (non-blocking)

- Once row-level model scoring lands, `scoring_status` flips to `wired` and `harness_error` 5th-status branch should be re-introduced.
- JSONL-first wiring (read `sha256_normalized` and `MANUAL_W1_JSONL_SCHEMA_VERSION` directly per row) would let us delete the mirrored hash helper. Natural follow-up.
- Coordinator: per Linus's ask, any future change to W1 TSV format or canonical hash formula must touch `evaluate._manual_w1_sha256_normalized` and its pinning unit test in the same change.

### Outcome

✅ **Lift the W1 revision.** Linus is locked out of the next revision cycle on this scope by standard rule; no rejection-driven re-spawn needed because the verdict is APPROVE.


---

## User Directive: human_fetch as checkpoint eval probe (2026-04-30T08:37:06Z)

**By:** yashasg (via Copilot)

**What:** Use `human_fetch.jsonl` / `human_fetch.txt` as the trusted parallel source for checkpoint evals. Stage 0 is checkpoint 0 in the same checkpoint-eval series. Every checkpoint (including Stage 0 with no training) should evaluate English-to-Hawaiian and Hawaiian-to-English translation behavior to gauge baseline and drift over time.

**Why:** User request — captured for team memory

**Status:** Implemented by Linus; reviewed and APPROVED by Rusty.


---

## Decision: Linus — human_fetch bidirectional translation probe for checkpoint evals

**Date:** 2026-04-30

**Owner:** Linus (Data Engineer)

**Status:** APPROVED by Rusty (sync reviewer gate)

### Summary

`human_fetch.jsonl` (the Ulukau English/Hawaiian parallel pair) is now the trusted local source for a bidirectional translation probe (`en→haw`, `haw→en`) that runs on every checkpoint eval, including the Stage 0 no-training baseline. The probe is `eval_eligible = True`, `training_eligible = False`.

### What changed

**`scripts/_convert_ulukau_human_fetch.py`**
- Fixed stale `source_path` field (`human_fetch.md` → `human_fetch.txt`) by centralising the path in a `SOURCE_PATH_FIELD` constant.
- Updated policy: `eval_eligible: True`, `training_eligible: False`, `translation_probe_eligible: True`. `audit_only: False`.
- Updated `audit_use`: `"tokenizer_audit_candidate,translation_probe"`.
- Regenerated `data/tokenizer_audit/ulukau_nupepa/human_fetch.jsonl`.

**`code/llm_hawaii/evaluate.py`**
- New constants: `DEFAULT_HUMAN_FETCH_JSONL`, `HUMAN_FETCH_PROBE_SCHEMA`, `HUMAN_FETCH_EN_TO_HAW_TEMPLATE`, `HUMAN_FETCH_HAW_TO_EN_TEMPLATE`.
- New `_char_ngram_f1(reference, hypothesis, n=2)` — pure-Python baseline char-bigram F1. Documented as a *baseline string-overlap/character-F score*; no new dependencies. Directions always separate (en→haw ≠ haw→en; never averaged).
- New `human_fetch_translation_probe(jsonl_path, *, enabled, model, tokenizer, max_new_tokens)` — reads the parallel JSONL, validates the en+haw pair, builds prompts from the baked-in templates, runs greedy generation when model is provided, and computes char-bigram F1 per direction. Status enum: `not_configured` | `missing` | `invalid` | `ready` | `evaluated`. Safe to miss (missing → probe reports status=missing, eval continues). No raw source/reference/generation text in return value; only hashes and numeric metrics.
- Updated `evaluate_checkpoint()` to accept `human_fetch_jsonl` and `use_human_fetch` params and to emit `report["human_fetch_translation"]` on every call (parallel to `manual_w1` and `english_ppl`).
- Updated `main()` CLI: `--human-fetch-jsonl` and `--no-human-fetch`.

**`scripts/run_stage0_eval.sh`**
- Added `HUMAN_FETCH_JSONL` and `USE_HUMAN_FETCH` env vars with defaults.
- Threaded through to `evaluate.py` argv.
- Summary Python heredoc: adds `metrics.human_fetch_translation` (hash/numeric fields only) to the tracked summary; strips `note` field defensively. Heredoc now passes two additional positional args.

**`code/tests/test_evaluate.py`**
- `TestCharNgramF1`: 7 tests covering identical strings (F1=1), empty hypothesis/reference (F1=0), partial overlap, Hawaiian NFC text.
- `TestHumanFetchTranslationProbe`: 13 tests covering disabled, missing, invalid JSON, missing haw row (valid two-row pair path), ready-state, bidirectional directions presence, hash-only fields, no raw text in summary-like structures, policy fields, mock-model evaluated path, bidirectional scores separate, schema constant, default path constant, CLI args wired, `evaluate_checkpoint` signature, and Stage 0 report includes the probe.

**`code/README.md`**
- Added human_fetch translation probe bullet to "Stage 0 drift signal bundle".
- Added `HUMAN_FETCH_JSONL`, `USE_HUMAN_FETCH` to wrapper overrides list.

**`docs/eval_pipeline.md` §8.1**
- Added human_fetch translation probe paragraph before CLI exit posture. Describes: prototype/learning probe, source, safe-to-miss posture, hash-only direction fields, char-bigram F1 metric, direction separation, `eval_eligible`/`training_eligible` policy.

**`data-sources/manual-eval/README.md`**
- Added "Relationship to the human_fetch bidirectional translation probe" section clarifying separation from W1.

### Key design decisions

1. **JSONL-only input** — preserves the existing W1 JSONL-only direction. TSV is never used as eval input.
2. **Safe-to-miss** — missing JSONL reports `status="missing"`, never fails the eval or flips the exit code.
3. **Directions strictly separate** — en→haw and haw→en carry separate `char_f1` / `char_precision` / `char_recall`; never averaged.
4. **No new dependencies** — `_char_ngram_f1` is pure Python (stdlib only), documented as a *baseline character-F score*, not a production chrF.
5. **No raw text in reports** — all direction dicts contain only sha256 hashes and numeric metrics.
6. **eval_eligible = True, training_eligible = False** — the converter policy is updated to reflect that the pair is now eval-eligible for the translation probe but remains off-limits for training.

### Validation

- ✅ `python3 -m py_compile code/llm_hawaii/evaluate.py scripts/315_hash_manual_w1_eval.py scripts/_convert_ulukau_human_fetch.py`
- ✅ `sh -n scripts/run_stage0_eval.sh`
- ✅ `cd code && PYTHONPATH=. python3 -m unittest tests.test_evaluate tests.test_metrics` — **73/73 green** (was 50; +23 new tests)
- ✅ `git --no-pager diff --check`


---

## Decision: Rusty — review of Linus's human_fetch bidirectional translation probe

**Date:** 2026-04-30

**Reviewer:** Rusty (NLP Researcher)

**Subject under review:** `linus-human-fetch-translation-eval.md`

**Verdict:** ✅ **APPROVED**

### Scope

Reviewer gate against the 10-point checklist for the Stage-0-as-checkpoint-0 bidirectional translation probe (en→haw, haw→en) wired into every checkpoint eval. Read-only review; no source files modified.

### Spot checks (all pass)

1. **Stage 0 = checkpoint 0, not a special case.** The probe is wired in `evaluate_checkpoint()` (`code/llm_hawaii/evaluate.py:1129`) on every call, parallel to `manual_w1` and `english_ppl`. No "if stage == 0" branch anywhere. Confirmed by `test_stage0_report_includes_probe_key` and the `evaluate_checkpoint` signature test.

2. **Safe to disable/miss.** `enabled=False` → `status="not_configured"`; missing JSONL → `status="missing"` with regenerate hint, returns early. `_cli_exit_code` (`evaluate.py:1230`) only flips on `manual_w1.status == "invalid"`; human_fetch never affects exit code. Wrapper `scripts/run_stage0_eval.sh` echoes "missing" cleanly and proceeds.

3. **Directions strictly separate.** `out["directions"]` carries `en_to_haw` and `haw_to_en` as distinct keys, each with its own `char_f1` / `char_precision` / `char_recall` / `prompt_sha256` / `generation_sha256` / `reference_sha256`. No averaging anywhere. `test_bidirectional_scores_are_separate` asserts the two F1s diverge under different mock generations. Docstring on `_char_ngram_f1` and §8.1 of `docs/eval_pipeline.md` both call out the no-averaging rule.

4. **Metric honestly documented as baseline.** `metric = "char_ngram_f1_baseline"`, `ngram_order = 2`. Docstring says "simple string-overlap drift metric, **not** a production chrF". README and `docs/eval_pipeline.md` §8.1 use the phrasing "baseline char-bigram F1", not "translation quality". Pure stdlib, no new deps.

5. **No raw text leaks.** Probe return dict carries only sha256 hashes (`pair_sha256`, `template_sha256`, `prompt_sha256`, `generation_sha256`, `reference_sha256`) plus numeric metrics, status, schema, path, policy fields, and an advisory `note`. The `note` is advisory boilerplate (no corpus text), and the tracked-summary projection in `scripts/run_stage0_eval.sh:_safe_translation_probe` defensively strips it anyway. `test_hash_only_fields_no_raw_text` recursively scans every string in the output and asserts neither the English nor the Hawaiian source text appears anywhere. `test_no_raw_text_in_summary_like_directions` asserts each direction dict has no `text` / `reference` / `prompt` keys.

6. **Hawaiian orthography handling appropriate for a probe.** Source bodies and generations are both `unicodedata.normalize("NFC", ...)` before n-gram extraction (`evaluate.py:523`, `:661`, `:723-724`). The canonical ʻokina-variant fold to U+02BB is enforced upstream by the converter (`scripts/_convert_ulukau_human_fetch.py:38-43`, `OKINA_VARIANTS = ["\u2018", "\u2019", "\u02bc", "`"]`), and the regenerated JSONL on disk shows `okina_codepoint: "U+02BB"` and `kahako_count: 1` on the Hawaiian row — orthographic state is trustworthy at probe time. Templates are plain ASCII, no orthographic risk.

7. **Converter metadata truthful.** `SOURCE_PATH_FIELD = "data/raw/ulukau_nupepa/human_fetch.txt"` (`.txt`, not the stale `.md`). Policy on every record: `eval_eligible: true`, `training_eligible: false`, `translation_probe_eligible: true`, `audit_only: false`, `w1_eligible: false`. `audit_use: "tokenizer_audit_candidate,translation_probe"`. Verified directly against `data/tokenizer_audit/ulukau_nupepa/human_fetch.jsonl`.

8. **W1 JSONL-only and invalid-gate semantics intact.** `DEFAULT_MANUAL_W1_JSONL` constant unchanged. `manual_w1_status()` path untouched. `_cli_exit_code` still flips to 2 *only* on `manual_w1.status == "invalid"` and emits the report first. Wrapper still echoes the W1-invalid warning. The new probe's `status="invalid"` correctly does **not** flip exit code (matches "safe-to-miss" probe semantics — this is a drift signal, not a gate).

9. **CLI / env compatibility preserved.** Existing flags (`--manual-w1-jsonl`, `--no-manual-w1`, `--prompt`, `--no-prompt-suite`, `--eval-file`, `--max-length`, `--max-new-tokens`) unchanged; new flags `--human-fetch-jsonl` / `--no-human-fetch` are purely additive. Wrapper env vars `HUMAN_FETCH_JSONL` / `USE_HUMAN_FETCH` follow the same pattern as the W1 vars and have sensible defaults plus a "(missing — translation probe will report 'missing')" diagnostic line. Tracked summary heredoc receives the extra positional args without breaking existing fields.

10. **Tests / validation sufficient and reproducible.** Re-ran focused validation:
    - `python3 -m py_compile code/llm_hawaii/evaluate.py scripts/_convert_ulukau_human_fetch.py` → clean.
    - `sh -n scripts/run_stage0_eval.sh` → clean.
    - `cd code && PYTHONPATH=. python3 -m unittest tests.test_evaluate tests.test_metrics` → **73/73 green** (matches Linus's count).
    The 23 new tests cover: char-F edge cases (identical, empty hyp/ref, partial overlap, NFC Hawaiian), all five status states, hash-only output, direction separation under mock generation, policy fields, schema/path constants, CLI-arg wiring, `evaluate_checkpoint` signature, and probe-key presence on every checkpoint run.

### Hawaiian-language correctness

NFC + U+02BB-only ʻokina normalization is enforced at converter time and re-asserted via NFC at probe time — appropriate for a baseline char-overlap metric. The Hawaiian reference text retains its kahakō (`stats.kahako_count = 1`) and ʻokina (`stats.okina_count = 2`) on the regenerated JSONL, so high-diacritic survival is part of the score's signal: a checkpoint that strips kahakō or substitutes a wrong ʻokina codepoint will see its char-F drop relative to the Stage 0 baseline. That is exactly the asymmetric drift signal the directive asked for.

### Posture / framing

The metric is correctly framed throughout (docstring, README, `eval_pipeline.md` §8.1) as a **baseline character-overlap signal**, not as "translation quality". The probe is labelled a "prototype/learning checkpoint eval probe". Anyone reading the tracked summary will not mistake `char_f1` for chrF++/BLEU/COMET. Good honesty about what this probe can and cannot tell us.

### Non-blocking observations (do not gate this revision)

- The probe NFC-normalizes input bodies but does not re-enforce single-ʻokina-codepoint at probe time. Today this is fine because the converter is the canonical regeneration path and folds variants to U+02BB. If a future caller hand-passes a non-canonical `--human-fetch-jsonl`, the score will silently be against a non-canonical reference. Not blocking — but a future hardening could add a wrong-ʻokina-count assertion on the loaded `haw_text` and flip the probe to `status="invalid"` if found, mirroring the W1 strictness on the accepted set.
- When `eval-file` is omitted, `hawaiian_ppl` is absent from the report and the summary projection currently emits `null` for that field rather than a `{"status": "absent"}` shape. Pre-existing wart, not introduced by this change.
- The probe's `note` field, while harmless, is the only free-prose string on the probe output. The wrapper strips it from the tracked summary; consider dropping it from the in-report dict in a future pass to make the "hash-only" contract literal. Non-blocking.

### Verdict

✅ **APPROVED.** Implementation faithfully delivers Stage 0 as checkpoint 0 in the same checkpoint-eval series, with bidirectional translation behaviour visible from the first eval and drift trackable across checkpoints. No raw text leaks, directions never averaged, metric framed honestly as a baseline string-overlap signal, converter metadata correct and truthful, W1 invalid-gate and CLI compatibility intact. Ready to land.



---

## Decision: Training Input Path for Stage 1 Prototype Run (2026-05-01)

**Owner:** Linus (Data Engineer)

**Status:** APPROVED — ready for Stage 1 CPT/QLoRA run

### Chosen training input path

`data/stage1/fineweb2_haw/train.jsonl` (95,507 rows)

Configured in `code/configs/stage1_fineweb2_haw.json`:
```json
"train_path": "../../data/stage1/fineweb2_haw/train.jsonl"
"eval_path": "../../data/evals/fineweb2_haw/dev.jsonl"
"eval_steps": 200
```

Eval input: `data/evals/fineweb2_haw/dev.jsonl` (621 rows).

### Data quality gate

1. **Complete and clean.** 95,507 rows; zero missing `text`, zero empty `text`, 100% NFC. No blocker for `data.py` path.
2. **Contamination guard passes.** SHA-dedup against 887-row test split before writing. `train ∩ eval_hashes = ∅`.
3. **Orthography gated.** Paragraph-level Hawaiian LID and ʻokina canonicalization in `301_build_stage1_dataset.py`; rejected rows excluded.
4. **Prototype framing preserved.** `prototype_only=True`, `release_eligible=False` on every row.

### Changes in code/config

- `code/configs/llama31_8b_a100.json`: `train_path`, `eval_path`, `eval_steps`, updated notes
- `code/llm_hawaii/train.py`: wired `eval_strategy="steps"` + eval loading
- `code/tests/test_data.py`: +9 new tests (no ML deps)
- `docs/data-readiness-stage1.md`: count/hash summary, no raw text

### Caveats

1. **Not release-eligible.** `prototype_only=True`; do not publish resulting checkpoints.
2. **Token volume ~17.6M** (FineWeb-only slice); full-cleaned output is ~44M.
3. **Exact dedup only.** LSH/MinHash across multi-source planned.
4. **eval_strategy key:** Newer HF uses `eval_strategy`; older uses `evaluation_strategy`. If run fails, switch key.

### Coordination with Basher (training runner)

Config paths are config-relative (resolved from config file location). Basher's runner does not change CWD or pass absolute override unless it writes `resolved_config.json` with absolute paths.


---

## Decision: Training Runner Readiness Contract (Stage 1) (2026-05-01)

**Owner:** Basher (Training Engineer)

**Status:** Implemented; ready for Stage 1 CPT run

### Summary

`code/llm_hawaii/train.py` is now runnable with durable contracts for:
1. Config-relative data paths (resolved from config file location)
2. New CLI flags: `--preflight`, `--resume-from-checkpoint PATH`, `--eval-after-train`
3. Run report schema `training-run-report.v1` with file hashes, row counts, no raw text
4. Preflight checks (validate config/data/runtime; no model download)
5. New config `code/configs/stage1_fineweb2_haw.json` for active run

### Config-relative data paths

All `train_path` / `eval_path` in JSON configs resolve **relative to config file location**, not working directory.
- `load_config(path)` calls `resolve_data_paths(cfg, config_path)` immediately after parse
- Running from repo_root/ or code/ is equivalent
- Tested in `code/tests/test_train.py`

**Migration:** Configs updated:
- `smoke.json`: `"../examples/train.jsonl.example"`
- `llama31_8b_a100.json`: `"../../data/stage1/fineweb2_haw/train.jsonl"` + eval
- `stage1_fineweb2_haw.json` (new): same paths, output dir `runs/llama31-8b-stage1-fw2/`

### New CLI flags

| Flag | Purpose |
|---|---|
| `--preflight` | Validate config + data + runtime; exit 0 (pass) or 1 (fail). No model download. |
| `--resume-from-checkpoint PATH` | Pass checkpoint dir to `Trainer.train()`. |
| `--eval-after-train` | Run `trainer.evaluate()` after training (requires `eval_path`). |

### Run report schema (training-run-report.v1)

Every `run_training()` call writes `{output_dir}/run_report.json`:
- `schema_version`, `stage`, `run_name`, `config_path`, `resolved_config`, `output_dir`
- `train.path`, `train.sha256`, `train.row_count`
- `eval` (same shape; null if no eval)
- `git_commit`, `runtime_capability`, `wallclock_seconds`, `completed_at_utc`

No raw training text in report.

### Preflight checks

`run_preflight(cfg)` verifies:
- Config parses cleanly (paths resolved to absolute)
- `train_path` exists, row count > 0, `text_field` present in first row
- `eval_path` exists if configured
- `output_dir` creatable
- Runtime capability (warning if torch/CUDA absent, not error)

### Next-run command sequence

```bash
# 1. Preflight — always before GPU spend
python3 -m llm_hawaii.train --config code/configs/stage1_fineweb2_haw.json --preflight

# 2. Train
python3 -m llm_hawaii.train --config code/configs/stage1_fineweb2_haw.json

# 3. Resume after interruption
python3 -m llm_hawaii.train \
    --config code/configs/stage1_fineweb2_haw.json \
    --resume-from-checkpoint runs/llama31-8b-stage1-fw2/checkpoint-NNN
```

### Unchanged

- No data files committed
- No `.superset/` files touched
- Smoke defaults (Qwen2.5-0.5B, tiny corpus)
- Lazy imports preserved (root venv, no torch, still compiles)
- Existing `--config` / `--print-config` behavior unchanged


---

## Decision: DummyTokenizer Test Fix (2026-05-01)

**Owner:** Basher (Training Engineer)

**Status:** Implemented; 103 tests pass

### Problem

Unit tests imported real HuggingFace tokenizers, causing:
- Automatic transformer model downloads
- GPU/CUDA availability checks
- Heavy dependency tree (torch, transformers, tokenizers, etc.)
- Blocker on CPU-only environments

### Solution

**Implement `_DummyTokenizer` in `code/llm_hawaii/data.py`:**
- Minimal mock tokenizer with `encode()` and `get_vocab_size()` methods
- No HF imports at module load time
- All unit test tokenizer calls route through dummy in test context

**Update `code/tests/test_data.py`:**
- All tokenizer usage now uses `_DummyTokenizer`
- Result: `unittest discover` runs without any ML deps
- No change to production code paths

### Validation

- `python3 -m py_compile code/llm_hawaii/*.py` → clean
- `cd code && PYTHONPATH=. python3 -m unittest tests.test_data tests.test_train tests.test_evaluate tests.test_metrics` → **103 tests OK**
- Faster local feedback loop (~10s for unit tests)

### Caveats

- `_DummyTokenizer` is test-only; never used in production
- Real tokenizer validation at preflight/train time
- Unit tests do not verify actual token counts (integration test scope)



---

## Decision: Maximize T4x2 — Bump max_seq_len and Reduce Accumulation Steps (2026-05-01)

**Owner:** Basher (Training Engineer)

**Status:** IMPLEMENTED — Validation passed

### Context

User directed: "we should try to maximize the x2."

Prior decision (2026-04-30) established that `device_map="auto"` is single-process model sharding — **not DDP** — and QLoRA + bitsandbytes 4-bit cannot use DDP. With that settled, the question was: given both T4s are addressable as ~32GB total via `device_map="auto"`, was the original conservative config (max_seq_len=1024, gradient_accumulation_steps=32) leaving memory on the table?

**Answer:** Yes. The original config was written defensively for a single 16GB T4. With device_map="auto" spanning both T4s, we can push max_seq_len to 2048.

### Changes Applied

**File:** `code/configs/stage1_fineweb2_haw_kaggle_t4x2.json`

| Field | Before | After | Rationale |
|---|---|---|---|
| `max_seq_len` | 1024 | **2048** | Exploit ~32GB addressable VRAM across T4x2; longer context = better CPT signal on Hawaiian text |
| `gradient_accumulation_steps` | 32 | **16** | seq_len 2× → 2× tokens per micro-step; halving accumulation steps keeps ~32K tokens/update (1024×32 = 32768 = 2048×16), fewer micro-steps per update = faster wall-clock |

Notes in the config were also updated:
- "hardware" note: removed "conservative for a single T4" language; now states this config exploits the full ~32GB budget
- "memory" note: explains the token-per-update equivalence math
- "device_placement" note: clarifies QLoRA cannot use DDP (explicit)
- "oom_fallback" note: clear fallback path — reduce max_seq_len to 1024, gradient_accumulation_steps to 32

**No code changes.** `device_map="auto"` already handles model sharding across both GPUs without any config field for `max_memory`. No new TrainConfig fields required.

### Token Budget Math

```
Old: max_seq_len=1024 × batch=1 × accum_steps=32 = 32,768 tokens/update
New: max_seq_len=2048 × batch=1 × accum_steps=16 = 32,768 tokens/update  ← same
```

Effective gradient signal density is unchanged. We just train with richer context windows and do fewer accumulation steps per optimizer step.

### OOM Fallback Strategy

If Kaggle session OOMs at max_seq_len=2048:
1. Revert `max_seq_len=1024`, `gradient_accumulation_steps=32` (original conservative values)
2. If still OOM: reduce `lora_rank=16`, `lora_alpha=32`
3. Quick plumbing test only: `max_seq_len=512`

### Validation

- ✅ JSON parses without error
- ✅ `load_config()` returns `max_seq_len=2048`, `gradient_accumulation_steps=16`, `fp16=True`, `bf16=False`
- ✅ All assertions pass


---

## Decision: GPU VRAM Optimization Analysis — Kaggle T4x2 Headroom Allocation

**Date:** 2026-05-02  
**Owner:** Rusty (NLP Researcher)  
**Status:** ANALYZED & DEFERRED (context-length expansion)

### Context

Kaggle T4x2 prototype run observes 8–10 GB unused VRAM across both GPUs combined. Current config: `max_seq_len=2048, per_device_train_batch_size=1, gradient_accumulation_steps=16, lora_rank=32/alpha=64/dropout=0.05`, using `device_map='auto'` (single-process model sharding, not DDP).

### Memory Usage Breakdown

**Current Configuration:**
- Model: Llama-3.1-8B in 4-bit (NF4 + double-quant via bitsandbytes)
- Quantized base: ~2.5 GB (8B fp32 ÷ 4)
- LoRA rank=32 projections on all-linear: ~500 MB
- Optimizer state (bfloat16 copy + momentum): ~1.5 GB for LoRA weights only
- Activations (forward/backward): max_seq_len=2048 × 1 batch × hidden_dim × 2 passes ≈ 2–3 GB
- **Subtotal: ~6.5–7.5 GB per GPU under peak load**
- Result: **~24–28 GB in use across 32 GB total** → 8–10 GB headroom is realistic.

### Option Analysis & Recommendation

**Option 1: Increase `max_seq_len` (2048 → 4096)**
- Pros: Direct quality win for Hawaiian; longer context = better long-range dependency modeling.
- Cons: Activation memory scales linearly; 4096 tokens ≈ 2× activations → ~30–31 GB total, near ceiling. QA-risk: peak transient spikes may exceed 32 GB (OOM).
- **Recommendation:** ⚠️ Higher risk. Only if you observe stable per-step memory < 28 GB after first 100 steps.

**Option 2: Increase `per_device_train_batch_size` (1 → 2)** ✅ IMPLEMENTED
- Pros: Doubles token throughput per GPU per step; modest memory cost: +1–1.5 GB per GPU.
- Cons: Batch=1 + grad_accum=16 already achieves effective batch=16 tokens/update (~32K tokens = 1 gradient step). Not DDP, so limited parallelization gain.
- **Recommendation:** ✅ Safe lever. Implement immediately.

**Option 3: Increase LoRA rank (32 → 64)**
- Pros: Higher rank = more adapter expressiveness; modest VRAM cost: ~1–2 GB.
- Cons: Minimal PPL benefit in CPT. Risk of overfitting on small Hawaiian corpus (81k rows, 44M tokens).
- **Recommendation:** ⚠️ Conditional. Defer to Stage-2 downstream task evals if room for improvement shown.

**Option 4: Leave headroom (status quo)**
- Pros: Safe. Kaggle's VRAM varies session-to-session; headroom absorbs spikes.
- Cons: Unused VRAM is unused learning capacity.
- **Recommendation:** ❌ Don't leave full headroom without exploring other options first.

### Decision

**Primary:** Implement `per_device_train_batch_size` 1→2 and `gradient_accumulation_steps` 16→8 (safe, immediate).

**Secondary (deferred):** Explore `max_seq_len` ≤ 3072 after Stage-1 checkpoint validation. If stable, revisit for Stage-2 prototype; if not, keep 2048.

**Deferred (Stage-2 tuning):** `lora_rank` expansion only if downstream task evals show capacity bottleneck.

### Key Insights

- Context-length is the highest-ROI VRAM lever for Hawaiian language modeling.
- Batch-size increase provides immediate implementable gain without changing optimizer semantics.
- QLoRA cannot use DDP (bitsandbytes `Linear4bit` incompatible with gradient gathering); single-process `device_map='auto'` is mandatory.


---

## Decision: Kaggle T4x2 VRAM Tuning — Config-Only Pass

**Date:** 2026-04-30T23:14:55Z  
**Owner:** Basher (Training Engineer)  
**Status:** IMPLEMENTED

### Decision

Use the observed 8–10GB spare aggregate VRAM on Kaggle T4x2 by raising the single-process training micro-batch from 1 to 2 and lowering accumulation from 16 to 8.

**New Config:**
```json
{
  "max_seq_len": 2048,
  "per_device_train_batch_size": 2,
  "gradient_accumulation_steps": 8
}
```

This preserves the same effective ~32K token/update budget:
```
Old: 2048 × 1 × 16 = 32,768 tokens/update
New: 2048 × 2 × 8  = 32,768 tokens/update  ← same
```

### Why This is the Safe Lever

- It is config-only; no trainer/model code path changes.
- It uses more activation memory directly, which is the resource currently underused.
- It keeps the optimizer update size and LR schedule effectively stable.
- It does not change the model architecture, LoRA capacity, dtype, or device placement.

### What NOT to Change Yet

- Do not raise `max_seq_len` beyond 2048 yet; 4096 is a much larger attention/activation jump.
- Do not raise LoRA rank or expand target modules; current `rank=32`, `all-linear` already changes trainable capacity.
- Keep gradient checkpointing enabled; disabling it risks a large activation-memory jump.
- Keep `device_map="auto"` single-process placement. QLoRA + bitsandbytes 4-bit cannot use DDP.

### Implementation

**File:** `code/configs/stage1_fineweb2_haw_kaggle_t4x2.json`
- Changed: `per_device_train_batch_size` 1→2
- Changed: `gradient_accumulation_steps` 16→8

**File:** `docs/kaggle-t4x2-setup.md`
- Updated memory tuning guidance to reflect new batch/accumulation settings

### OOM Fallback Strategy

If Kaggle session OOMs at batch=2, gradient_accum=8:
1. Revert to `per_device_train_batch_size=1`, `gradient_accumulation_steps=16` (original conservative values)
2. If still OOM: reduce `lora_rank=16`, `lora_alpha=32`
3. If still needed: fallback to `max_seq_len=512`


---

## Decision: pip check Non-Fatal on Shared Provider Environments

**Date:** 2026-05-01  
**Owner:** Basher (Training Engineer)  
**Status:** IMPLEMENTED

### Summary

`pip check` at the end of `setup_training.py --no-venv --skip-torch` was failing with exit code 1 on Kaggle because the provider base image already contains unresolved package conflicts unrelated to this project.

### Decision

- `pip check` defaults to **non-fatal** when `--no-venv` is used (shared provider environment assumed).
- `pip check` remains **fatal** (strict) for managed venv installs.
- A new `--strict-pip-check` CLI flag (and `STRICT_PIP_CHECK` env var) lets users override to hard-failure in any mode.
- Strictness logic: `pip_check_strict = args.strict_pip_check or (not args.no_venv)`.
- Non-strict failure prints a clear warning attributing conflicts to the provider image with a hint to use `--strict-pip-check`.

### Implementation

**File:** `scripts/setup_training.py`
- New `pip_check()` helper function
- New `--strict-pip-check` CLI argument
- Updated pip check logic to handle non-fatal vs. fatal modes

**File:** `docs/kaggle-t4x2-setup.md`
- Added pip check troubleshooting note to section 4 (setup instructions)

### Rationale

On shared provider environments like Kaggle, the base image often contains pre-installed packages with unresolved dependency conflicts. These conflicts are not caused by this project's setup and should not block training setup. Local/managed venv installs should be stricter to catch genuine issues in the project's dependency tree.


## Decision: Basher — CLM collator wraps to strip pre-tokenized labels

**Owner:** Basher (Training Engineer)  
**Date:** 2026-05-01  
**Status:** IMPLEMENTED — All tests pass

### Problem

`per_device_train_batch_size=2` in `stage1_fineweb2_haw_kaggle_t4x2.json` caused:

```
ValueError: expected sequence of length 196 at dim 1 (got 519)
ValueError: Unable to create tensor ... features (`labels`) have excessive nesting
```

**Root cause:** `tokenize_example()` stores `labels = list(input_ids)` on each
record. `DataCollatorForLanguageModeling` calls `tokenizer.pad()` on all feature
keys — including `labels` — *before* creating its own padded label tensor. With
batch size 1, no cross-sequence tensorization happens; with batch size 2, the
variable-length `labels` lists collide and raise.

### Fix

**`code/llm_hawaii/data.py` — `make_collator()`:**

Replace the bare `DataCollatorForLanguageModeling` return with a thin wrapper
`_collate()` that strips `labels` from each feature before calling the inner HF
collator. The CLM collator then derives labels from the padded `input_ids`,
correctly setting -100 at padding positions.

`tokenize_example()` is **unchanged** — its `labels` output is still present for
inspection and unit tests; the collator just doesn't forward them to the HF pad
call.

### New test

`test_collator_strips_labels_before_inner` in `code/tests/test_data.py`:
- Monkeypatches `_require` to inject a fake `DataCollatorForLanguageModeling`.
- Feeds two features with different-length `labels` (the exact pattern that failed).
- Asserts the inner collator receives features with `labels` stripped and
  `input_ids`/`attention_mask` intact.
- No HF model download required.

### Validation

- ✅ `py_compile code/llm_hawaii/data.py`
- ✅ `py_compile code/tests/test_data.py`
- ✅ All 16 `test_data.py` tests pass (including new `test_collator_strips_labels_before_inner`)
- ✅ Full test suite: 147 tests, 0 new failures (pre-existing torch-missing error unrelated)

### Kaggle retry command

From `/kaggle/working/ideal-spoon`:

```bash
PYTHONPATH=code python -m llm_hawaii.train \
  --config code/configs/stage1_fineweb2_haw_kaggle_t4x2.json
```
# Decision: Revert T4x2 config to batch=1/accum=16 after backward-pass OOM

**Owner:** Basher (Training Engineer)
**Date:** 2026-05-01
**Status:** IMPLEMENTED

## Context

After `per_device_train_batch_size=2` / `gradient_accumulation_steps=8` was promoted to the Kaggle T4x2 config in the "maximize T4x2" session, the user restarted the run and hit:

```
torch.OutOfMemoryError: CUDA out of memory.
Tried to allocate 1.96 GiB.
GPU 1 total 14.56 GiB, 1.60 GiB free, 12.13 GiB allocated by PyTorch.
```

## Root Cause

Batch=2 was survivable during the forward pass (activations distributed across both T4s via `device_map="auto"`), but the real backward pass materialises gradient accumulation buffers for both sequences on GPU 1 simultaneously. GPU 1 carries the tail model layers and bears the heaviest backward-pass allocation — this pushed peak demand ~360 MiB above the available headroom.

## Decision

Revert to the stable T4x2 baseline:
- `per_device_train_batch_size = 1`
- `gradient_accumulation_steps = 16`
- `max_seq_len = 2048` (unchanged)
- `save_total_limit = 300` (unchanged)

Effective token budget per optimizer step is unchanged: 1 × 2048 × 16 = 32 768 tokens.

## `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`

Setting `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` in the notebook environment may reduce allocator fragmentation for varying sequence lengths and is worth adding as a belt-and-suspenders measure. However, it cannot resolve a capacity deficit — the observed OOM is a capacity issue, not a fragmentation issue. The primary fix is `batch=1`.

## Files Changed

| File | Change |
|------|--------|
| `code/configs/stage1_fineweb2_haw_kaggle_t4x2.json` | `per_device_train_batch_size` 2→1, `gradient_accumulation_steps` 8→16, `memory` note updated |
| `docs/kaggle-t4x2-setup.md` | Section 5 VRAM note updated; batch=2 flagged experimental/OOMed; `expandable_segments` note added |

## Do Not Retry batch=2 Without

- Per-GPU memory profiling (`torch.cuda.memory_stats()`) at the backward-pass peak
- Or gradient offload / CPU offload enabled
- Or sequence length reduced below 2048

## Retry Commands (see docs/kaggle-t4x2-setup.md §5 for full setup)

```bash
# After pulling the updated config:
PYTHONPATH=code python3 -m llm_hawaii.train \
  --config code/configs/stage1_fineweb2_haw_kaggle_t4x2.json \
  --preflight

PYTHONPATH=code python3 -m llm_hawaii.train \
  --config code/configs/stage1_fineweb2_haw_kaggle_t4x2.json
```


---

## Decision: Stage-2 Bible verse-id adapter — edition pin lives in JSON, not code (2026-05-01)

**Date:** 2026-05-01
**Owner:** Frank (Hawaiian Data Collector)
**Tracks:** issue #16
**Status:** Adapter contract landed in working tree; awaiting Linus rights review for edition pin.

Stood up the first real Stage-2 source adapter for the (Baibala Hemolele × public-domain English Bible) verse-id-aligned pair. Edition pin lives in JSON (`source_registry.json`), not Python. Triple-gated `--execute` enforced on fetchers. ʻokina canonicalization runs before pair hashing. Synthetic fixtures over real PD text. Two-script split (fetch vs build) for every Stage-2 source.

**Validation:** 18/18 new tests pass; full `code/tests` suite still green. `322 --execute` emits 5 rows to `data/stage2/candidates/bible.jsonl` (gitignored). Schema check → rc=0.

**Files:** `data-sources/bible/{source_registry.json, README.md}`, `scripts/{206_fetch_baibala_raw.py, 322_build_bible_candidates.py}`, `code/tests/fixtures/bible/`, `code/tests/test_bible_adapter.py`.


---

## Decision: Tatoeba en↔haw adapter — alignment_method and register choices (2026-05-01)

**Agent:** Linus (Data Engineer)
**Date:** 2026-05-01
**Issue:** #17 Stage 2 source adapter: Tatoeba en-haw sentence pairs

**alignment_method = "manual"** — Tatoeba sentence links are manually added by human contributors, not derived from TMX. Semantically accurate; in schema's `DETERMINISTIC_METHODS` (no embedding score required).

**register = "unknown"** — Tatoeba contains mixed-domain content. `"unknown"` is more conservative and accurate than `"educational"`.

**Pinned dump date = 2025-05-01** with three URLs from `data-sources/stage2-parallel-fetch-plan.json`.

**Team Impact:** Quality scorer (321) will treat Tatoeba pairs as deterministic and skip embedding checks. Downstream register-balancing should treat Tatoeba as unlabelled.

**Files:** `data-sources/tatoeba/{fetch.py, README.md, PINNED_DUMP.json}`, `code/tests/fixtures/tatoeba/*.tsv`, `code/tests/test_tatoeba_adapter.py` (41 tests, all green).


---

## Decision: Stage-2 SFT data path and target-only masking (no TRL) (2026-05-01)

**Date:** 2026-05-01
**Author:** Basher (Training Engineer)
**Issues:** #21, #22

Stage-2 SFT uses custom tokenizer + collator in `code/llm_hawaii/data.py` rather than TRL's `SFTTrainer`.

**Rationale:** No new heavy deps; explicit masking at tokenization time; EOS in target (not masked); separate tokenization prevents BPE boundary ambiguity.

**Dispatch:** `run_training` dispatches on `cfg.stage == "stage2-sft"` and calls `build_sft_dataset` + `make_sft_collator`.

**Config fields added:** `sft_instruction_field`, `sft_source_field`, `sft_target_field` (defaults match `scripts/330_emit_stage2_sft_jsonl.py` output).

**Validation:** Target-only labels at tokenization; prompt/padding = -100 (inspectable); EOS placement correct; no BOS/EOS injection mid-sequence.


---

## Decision: Colab Pro vs Kaggle T4x2 — conditional GPU assessment (2026-05-01)

**Date:** 2026-05-01
**Author:** Basher (Training Engineer)
**Context:** 1h19m lost to setup/config bugs; 30h budget remaining; user asking about Colab Pro for Llama-3.1-8B QLoRA Stage 1.

**Verdict:** Conditional — Check the GPU before committing.

| Colab GPU | Switch? | Config |
|-----------|---------|--------|
| A100 40GB | Yes | `stage1_fineweb2_haw.json` (exists) |
| L4 24GB   | Yes | New config: bf16, single-GPU, batch=1, accum=16 |
| T4 16GB   | No  | Stay on Kaggle T4x2 (32GB total beats 16GB single) |

**How to check before committing:** `print(torch.cuda.get_device_name(0))` and `torch.cuda.get_device_properties(0).total_memory / 1e9`.


---

## Decision: Stage 2 eval gate landed (issue #23) (2026-05-01)

**Owner:** Rusty (NLP Researcher)
**Date:** 2026-05-01
**Status:** IMPLEMENTED — 29 tests green, full suite passes.

Stage 2 prototype eval gate is live at `code/llm_hawaii/stage2_eval.py` with CLI front-end `scripts/410_stage2_eval.py`.

**Key decisions:**
1. Generation decoupled from scoring — gate takes `predictions.jsonl` keyed by `pair_id`.
2. chrF backend recorded, not pinned — sacrebleu when importable; pure-Python fallback otherwise.
3. Direction separation is structural — `chrf_both_directions` returns `en_to_haw` / `haw_to_en` dicts; no averaged number.
4. Leakage check fails closed — missing ledger/manifest = `fail` verdict with status `missing`.
5. No blocking CI thresholds — numbers are advisory at prototype tier.

**Files:** `code/llm_hawaii/stage2_eval.py`, `scripts/410_stage2_eval.py`, `code/tests/test_stage2_eval.py` (29 tests), `code/tests/fixtures/stage2_eval/`.

**Hand-offs:** Basher (predictions keyed by `pair_id`), Linus (manifest schema fields: `sha256_pair`, `sha256_normalized`, etc.).


---

## Decision: Colab Pro ROI for Stage-1 Prototype (2026-05-01)

**Author:** Livingston (Cost Strategist)
**Date:** 2026-05-01
**Status:** Recommendation — hold off for now

**Analysis:** Kaggle free tier has ~28.7h quota remaining (more than enough for prototype). The 1h19m burn was setup friction, not compute scarcity. Colab Pro does not solve setup issues.

**Recommendation:** Do not buy Colab Pro right now. You have sufficient Kaggle quota. Revisit if quota exhaustion is confirmed AND the run is not done.

**When Colab Pro *would* make sense:**
1. Confirm remaining 28h41m is not enough to complete the run.
2. Need A100 (bf16, faster throughput) — requires new config.
3. Iterating rapidly and exhausting free quota repeatedly in the same week.


---

## Decision: Basher — Stage 2 Lineage CI (Issue #24)

**Owner:** Basher (Training Engineer)
**Status:** IMPLEMENTED — All validation passed

### Summary

Added Stage 2 tokenizer SHA equality check and parent artifact recording to the trainer preflight.

### Design choices

1. **Tokenizer SHA computation is file-based, not object-based.** We hash the files saved in `parent_run_dir` rather than a live tokenizer object so the check runs in pure stdlib without any ML deps. This keeps preflight fast (no HF download).

2. **SHA covers all canonical tokenizer files present in sorted order.** Files: `added_tokens.json`, `merges.txt`, `special_tokens_map.json`, `tokenizer.json`, `tokenizer_config.json`, `vocab.json`. Missing files are skipped (different tokenizer families omit different files). Empty dir → `FileNotFoundError`.

3. **`parent_run_dir` is a new `TrainConfig` field resolved config-relative** (like `train_path`). Set to Stage 1 / merged-base output dir. `null` in shipped configs — user fills it in before running Stage 2.

4. **`write_run_report` gains lineage kwargs with `None` defaults** — backward compatible; Stage 1 run reports still valid without them.

5. **Stage 1 path is explicitly unaffected** — `run_stage2_lineage_preflight` is only called when `cfg.stage == "stage2-sft"`. Confirmed by `test_stage1_preflight_unaffected_by_lineage_checks`.

### Files changed
- `code/llm_hawaii/config.py` — `parent_run_dir` field + resolution
- `code/llm_hawaii/train.py` — `compute_tokenizer_sha`, `_compute_artifact_sha`, `run_stage2_lineage_preflight`, updated `run_preflight` + `write_run_report` + `run_training`
- `code/configs/stage2_smoke.json`, `stage2_prototype.json` — `parent_run_dir: null`
- `docs/training-pipeline.md` §5 — implementation notes
- `code/tests/test_train.py` — 12 new tests


---

## Decision: Stage 2 manifest ingestion + SFT template rotation

**Date:** 2026-05-01
**Author:** Linus (Data Engineer)
**Issues:** #18, #20

### Decisions made

#### 1. Split assignment: hash mod 10 (≈10% dev)

`assign_split(pair_id, dev_modulus=10)` uses `int(sha256(pair_id)[:8], 16) % 10 == 0 → dev; else → train`. No test split yet — defer until corpus is large enough. Do NOT change the modulus retroactively on an existing manifest without a full re-derivation (pair_ids will silently reclassify).

#### 2. Candidate JSONL files in `data/stage2/candidates/`

The manifest builder globs `data/stage2/candidates/*.jsonl` by default. Adapters write their candidates there. Explicit `--candidates` paths override the glob (for single-adapter reruns or CI gating).

#### 3. `data/stage2/templates.json` is gitignored; fixture lives in `code/tests/fixtures/stage2/`

Consistent with the decision that nothing under `data/` is committed. The fixture is tiny (3 per direction) and marked with a `_comment` key. The production file has 5 per direction.

#### 4. Template rotation is deterministic by pair_id hash, not sequential

Rationale: re-emission must be reproducible. Sequential rotation would change instructions if rows are filtered differently across runs.

#### 5. Hawaiian-language paraphrases need Rusty review before release

Two `haw->en` templates are in Hawaiian. Flagged in issue #20 comment for Rusty's orthography review before any data leaves prototype status.

### Impact

- **Basher:** `330_emit_stage2_sft_jsonl.py --dry-run` now reports `templates_loaded: true` when `data/stage2/templates.json` exists. The `instruction` field in each emitted SFT row may vary per pair_id.
- **Rusty:** Please review the two Hawaiian-language instruction paraphrases in `data/stage2/templates.json` (haw->en direction).
- **Frank:** If the Bible adapter produces new candidates, run `python scripts/320_build_stage2_manifest.py --execute` to rebuild the manifest.



---

## Decision: Stage 2 Alignment-Quality Policy Integration (Issue #19)

**Owner:** Rusty (NLP Researcher)
**Date:** 2026-05-01
**Status:** IMPLEMENTED — Manifest builder integrated

### Summary

The alignment-quality scoring policy is now wired directly into the manifest builder at `scripts/320_build_stage2_manifest.py`. Every candidate row is scored through `llm_hawaii.stage2_quality.score_pair` before validation. Policy fields are required on the manifest but NOT on adapter candidate output.

### Key decisions

1. **Policy fields required on manifest, not on adapters.** The six fields (`alignment_confidence_tier`, `alignment_review_required`, `quality_flags`, `manual_review_reasons`, `alignment_score_components`, `policy_version`) are computed by the builder, not the adapters. Adapters keep their structural-only contract.

2. **Tier → split contract:**
   - `tier == "accept"` → split is preserved if explicit, else `assign_split(pair_id)` (deterministic train/dev).
   - `tier ∈ {"review", "reject"}` → split is forced to `"review-pending"`, overriding upstream value. The SFT emitter already excludes `review-pending` from default split set and skips `alignment_review_required=true`, so quarantined rows are double-belted out of training.

3. **Run-level summary persisted.** `data/stage2/score_summary.json` is written on every `--execute` with `row_count`, `tier_counts`, `flag_counts`, and serialized active `policy_summary()`. `policy_version="stage2-quality-v0.1"` is recorded on every row and on the manifest's `ingest.policy_version`.

4. **Policy version tracking for explainability.** Any change to `PolicyConfig` defaults must bump `POLICY_VERSION` in `code/llm_hawaii/stage2_quality.py` and trigger a manifest re-write — old rows remain explainable via their recorded policy version.

### Hawaiian-language template fixture correction

The committed haw→en paraphrase was orthographically/grammatically inverted (`"Unuhi i kēia ʻōlelo Pelekānia mai ka ʻōlelo Hawaiʻi."` — "Translate this English speech FROM Hawaiian", which is wrong for a haw→en prompt whose input is Hawaiian). Replaced in `code/tests/fixtures/stage2/templates.json` and in the emitter's `DEFAULT_INSTRUCTIONS`. All haw→en paraphrases now phrase the direction as `kēia ʻōlelo Hawaiʻi … i ka ʻōlelo Pelekānia`.

### Impact on other agents

- **Linus:** Adapters do not need to emit policy fields. If adding a new adapter, only ship structural manifest fields; the builder scores on ingest. Schema-compatibility tests should `apply_policy(dict(row))` before calling `validate_row` — see `test_bible_adapter.py` and `test_tatoeba_adapter.py` for pattern.
- **Basher:** No change required. Emitter's existing `alignment_review_required` filter and split filter already honor the quarantine. Trainer fields are unchanged.
- **Frank:** Template fixtures corrected; no adapter logic change.

### Files changed
- `scripts/320_build_stage2_manifest.py` — policy scoring integrated
- `code/llm_hawaii/stage2_quality.py` — policy version tracking
- `code/tests/fixtures/stage2/templates.json` — haw→en templates corrected
- `code/llm_hawaii/score_stage2_sft_batch.py` — emitter default instructions updated
- `data/stage2/score_summary.json` — persisted on each build
# Decision — Baibala live HTML parser landed (issue #16)

**From:** Frank (Hawaiian Data Collector)
**Date:** 2026-05-01
**Tracks:** issue #16 — Stage 2 source adapter: Baibala Hemolele verse-aligned en-haw

## Decisions

1. **Verse-body terminator = `<br />`, not the next anchor.** Greenstone
   appends an inner navigation `<table>` after the final verse with a
   "next chapter &gt;" link; using the next-anchor / `</table>` boundary
   leaks that nav text into verse 31 (or whatever the last verse is).
   Terminating each verse at the first `<br />` cleanly avoids it and
   matches the per-verse line layout 1:1.

2. **ASCII apostrophe is a real ʻokina mis-encoding on the 1839 imprint.**
   Live HTML uses `hana'i` (ASCII `'`) where modern orthography would use
   `hanaʻi` (U+02BB). The haw normalization pipeline (`OKINA_MISENCODINGS
   = ("\u2018", "\u2019", "'")`) already canonicalizes this, but it was
   previously framed as a defensive case. After observing live samples,
   this is the *primary* ʻokina canonicalization path on the haw side
   for this edition. Documented in `data-sources/bible/README.md` and
   pinned by `test_ascii_apostrophe_canonicalized_to_okina`.

3. **Candidate JSONL is policy-merge-required for `--check --strict`.**
   The Stage-2 alignment-quality policy fields
   (`alignment_confidence_tier`, `quality_flags`,
   `manual_review_reasons`, `alignment_score_components`,
   `policy_version`) are stamped on by
   `320_build_stage2_manifest.py --execute` via `apply_policy()`, NOT
   by the per-source candidate builders. Running
   `--check --strict --manifest-in <candidates.jsonl>` directly will
   always report `missing:*` violations by design. The correct gate is
   `--check --strict` against the post-build manifest at
   `data/stage2/stage2_manifest.jsonl`. Adapter-contract tests already
   apply policy before validating; we should not add the policy fields
   to candidate rows because that would duplicate logic that the
   manifest builder owns.

4. **Raw-derived rows are tagged in `notes`.** `build_rows_from_raw_haw`
   appends `; src=raw_html` to the `notes` field so a downstream review
   can distinguish fixture-derived rows (used in CI / dry-run) from
   raw-fetch-derived rows (real source bytes). The intent is *not* to
   gate behavior on this; it's a provenance breadcrumb.

5. **English side stays on fixture for this round.** The English WEB
   `url_template_status` is still `placeholder_pending_endpoint_check`.
   `--from-raw` and `--haw-raw-dir` only override the haw side; eng
   defaults to `--eng-fixture-dir code/tests/fixtures/bible`. A bulk
   run that hits the issue-#16 "few thousand verse-aligned rows"
   acceptance number is blocked on Linus pinning the WEB endpoint.

## What others should know

- **Linus:** when you pin the WEB url_template, please flip
  `url_template_status` to a `confirmed_live_<date>` value the same way
  you did for the haw side; the fetcher's `assert_execute_preconditions`
  reads `edition_pinned_by` per-side and will refuse `--execute` until
  the eng pin is real.
- **Rusty:** verse-id pairs come out at `score-tier=accept` per
  `docs/stage2-alignment-quality.md` §3.1. No embedding model needed.
  The Hawaiian normalization on this source produces NFC + U+02BB text;
  this matches the assumption your tokenizer / training pipeline makes
  on Stage-1 input.
- **Coordinator:** parser implementation does not require a fetch (live
  samples were already on disk via Linus' pin work); the only network
  egress this round was to verify the previously-committed registry
  URL renders against the corrected Greenstone `d=` parameter.

## Files touched (working tree only — not committed)

- `scripts/206_fetch_baibala_raw.py` — implemented
  `parse_baibala_chapter_html()`, added `_normalize_haw_verse_text()`
  and `_VERSE_ANCHOR_RX`, added `html` + `unicodedata` imports.
- `scripts/322_build_bible_candidates.py` — added
  `_load_fetch_module()`, `iter_raw_haw_chapters()`,
  `build_rows_from_raw_haw()`; CLI gained `--from-raw`,
  `--haw-raw-dir`, `--eng-fixture-dir`.
- `data-sources/bible/README.md` — status header, run order,
  parser-contract section refreshed.
- `code/tests/test_bible_adapter.py` — +12 tests
  (`TestLiveHtmlParser`, `TestRawHawCandidateBuilder`).
- `code/tests/fixtures/bible/haw_html/GEN_001.html` — synthetic chapter
  HTML fixture mirroring the live anchor pattern. Not real Bible text.

No corpus payloads committed.


---

## Kaggle T4x2 Stage 1 Eval OOM Fix

**Owner:** Basher  
**Date:** 2026-05-01  
**Status:** IMPLEMENTED — working tree only (not committed)

### Problem

Training reached step 100/5070 then OOMed in `_maybe_log_save_evaluate` before writing checkpoint-100.

Root cause (two compounding issues):
1. **Trainer default eval batch=8:** `per_device_eval_batch_size` defaults to 8 in HuggingFace Trainer. Llama-3.1-8B (vocab=128,256) × seq=2048 × fp16 × batch=8 = **~4.2 GiB** of logits per eval step. GPU 1 had training state resident; allocation of 3.91 GiB failed.
2. **Eval fires before save at same step:** When `eval_steps == save_steps == 100`, Trainer's `_maybe_log_save_evaluate` evaluates before saving. OOM during eval ⇒ no checkpoint written.

### Decision

Config-only fix preferred (no training behaviour change). Two settings applied to `stage1_fineweb2_haw_kaggle_t4x2.json`:

| Setting | Old | New | Effect |
|---|---|---|---|
| `eval_steps` | 100 | 500 | checkpoints 100-400 exist before first eval; eval still happens at 500/1000/… (10 eval points across 5070 steps) |
| `per_device_eval_batch_size` | *(unset, default 8)* | 1 | logits ~500 MB instead of ~4.2 GiB |
| `eval_accumulation_steps` | *(unset)* | 1 | GPU logit tensors released after each eval batch |

Code change required to support config fields: `per_device_eval_batch_size` and `eval_accumulation_steps` added to `TrainConfig` (both `Optional[int] = None`) and wired through `build_training_args()`. Fields are only forwarded when explicitly set so configs that don't need them get Trainer defaults unchanged.

### Why not disable eval entirely?

Eval perplexity on the FineWeb-2-haw dev split is the only signal we have during Stage 1 CPT. Disabling it permanently would lose that. Deferring to step 500 with batch=1 keeps the signal at low cost.

### Files changed

- `code/llm_hawaii/config.py` — added `per_device_eval_batch_size`, `eval_accumulation_steps` fields
- `code/llm_hawaii/train.py` — `build_training_args()` forwards new fields when not None
- `code/configs/stage1_fineweb2_haw_kaggle_t4x2.json` — `eval_steps=500`, `per_device_eval_batch_size=1`, `eval_accumulation_steps=1`; updated notes
- `docs/kaggle-t4x2-setup.md` — Eval OOM fix section added with table
- `code/tests/test_train.py` — `TestEvalMemoryControls` class (6 new tests); 38/38 pass

### Team impact

Any config that sets `per_device_eval_batch_size` or `eval_accumulation_steps` will now have those respected. Configs that don't set them are unaffected (None → not forwarded → Trainer default).

---

## Frank — Stage 2 first real fetch pass

**Owner:** Frank (Hawaiian Data Collector)
**Date:** 2026-05-01
**Status:** COMPLETE (this pass) — ledger of actual fetched data, distinct from roadmap estimates.

### Headline (to answer user directly)

**The "40k canonical pairs / 80k directional rows" figure is a TARGET, not data on disk.**
Pre-fetch on-disk total was 10 candidate rows (5 Bible smoke + 5 stale manifest). Post-fetch on-disk total is **126 candidate rows** (5 Bible + 121 Tatoeba). That is ~0.3% of target. All other yield estimates in prior memos remain projections gated on adapters not yet written.

### What this pass actually did

Executed `scripts/107_collect_stage2_parallel.py` then `scripts/207_fetch_stage2_parallel_raw.py --execute` source-by-source for all rights-cleared static-download sources with no open gates, plus the existing Tatoeba source-specific adapter.

### Actual artifacts on disk (post-pass)

#### Raw bytes (gitignored, with provenance ledgers)

| source_id | artifacts | bytes | notes |
|---|---|---|---|
| `tatoeba-haw-eng` | 3 | ~34.6 MB | haw + eng sentences + links |
| `andrews-1865-en-haw-vocab-appendix` | 1 | 2.73 MB | IA djvu.txt — full book OCR |
| `kaikki-haw-en-wiktionary` | 1 | 5.22 MB | full Hawaiian Wiktionary jsonl |
| `wikimedia-cx-en-haw-published` | 1 | 29 KB | API page 1 only — needs paginating adapter |
| `hawaiian-kingdom-statutes-bilingual` | 8 | ~2 MB | IA detail pages for all 4 paired codes; book bodies require source-specific adapter |

#### Candidate JSONL (post-adapter)

| file | rows |
|---|---|
| `data/stage2/candidates/bible.jsonl` | 5 (pre-existing) |
| `data/stage2/candidates/tatoeba.jsonl` | **121 (new)** |
| `data/stage2/stage2_manifest.jsonl` | 5 (stale; not regenerated this pass) |

### Sources skipped this pass — and why

- Bible (haw + eng): no full scrape per scope; eng PD zips deferred; haw still gated on edition pin + ToS snapshot.
- OPUS, BibleNLP, Weblate, Wikisource, Wiki langlinks, Pukui-Elbert: adapter-needed or rights/endpoint gates open.
- NLLB mined, BT synthetic: blocked on Rusty (LaBSE 0.80, BT quality floor) and Linus (cap registry in 320).
- Eval-only (`global-piqa-parallel-haw`, `taxi1500-haw`): auto-skipped, correct.

### Blockers surfaced this pass

1. **HK statutes:** generic fetcher pulls IA detail HTML, not book bodies. The provenance anchor is correct, but the candidate-row builder needs `111_collect_hk_statutes.py` (Frank's roadmap, blocked on Rusty alignment design).
2. **Wikimedia CX:** single API call returns one page; need pagination + parser before this source produces candidates.
3. **Andrews 1865 + kaikki:** raw OCR / dump captured; downstream extractors still unwritten.

### Honest gap to 80k target

Actual: 126 candidate rows.
Target: 80,000 directional SFT rows (~40,000 canonical pairs).
**Delta:** ~99.7%, entirely in the adapter-needed bucket (Bible parser → 8–12k, NLLB mined → 8–15k, OPUS → 2–5k, HK statutes → 3–6k, Wiki langlinks → 3–5k, BT → 5–10k, CX → 1–3k, Andrews/kaikki/Wikisource → sub-2k combined).

Prior decisions.md memos already document these as estimates. This memo's job is just to make sure the actual-vs-estimate distinction is unambiguous in the team record.

### No code edits this pass

`107`, `207`, and `data-sources/tatoeba/fetch.py` ran clean as written; no first-batch fetch bugs.

---

## Stage 2 Count Audit — Actual vs Estimate

**Author:** Linus  
**Date:** 2026-05-02  
**Trigger:** User asked whether the 80k/40k row target is data already in hand.

### Decision: 80k/40k is an estimate — zero real pairs on disk

After auditing all Stage 2 artifacts:

- `data/stage2/stage2_manifest.jsonl` → **5 rows**, all from `baibala-hemolele-1839`, EN side is placeholder test text ("This is a marker for the writer's test."). **Not real parallel data.**
- `data/stage2/stage2_sft.jsonl` → **does not exist** (correct; smoke data does not justify SFT emission).
- `data/stage2/candidates/bible.jsonl` → **5 rows**, same smoke set.

**Real parallel pairs on disk: 0.**

### Raw artifacts fetched but not yet converted

| Source | File | Size | Est. pairs on conversion |
|---|---|---|---|
| `tatoeba-haw-eng` | `haw_sentences_detailed.tsv.bz2` + links | ~33 MB | 500–2,000 |
| `andrews-1865-en-haw-vocab-appendix` | `cu31924026916167_djvu.txt` | 2.6 MB | 200–500 |

These are the only two Stage 2 sources with raw data fetched. Both need a conversion script run before they contribute candidate rows.

### Next concrete queue (post Frank's safe first batch)

1. **Convert `tatoeba-haw-eng`** raw TSVs → `data/stage2/candidates/tatoeba-haw-eng.jsonl`
2. **Convert `andrews-1865-en-haw-vocab-appendix`** OCR text → `data/stage2/candidates/andrews-1865-en-haw-vocab-appendix.jsonl`
3. **Fetch + convert `kaikki-haw-en-wiktionary`** → `data/stage2/candidates/kaikki-haw-en-wiktionary.jsonl`

After all three: run `320_build_stage2_manifest.py` to get first real accepted count.

### Team implications

- Do **not** report any row count to the user as "data we have" until `stage2_manifest.jsonl` contains rows with real (non-placeholder) text and `alignment_confidence_tier: accept`.
- The 80k target requires NLLB mined + synthetic BT in addition to human-parallel sources; human-parallel alone projects ~28–35k pairs at best.
- `stage2_sft.jsonl` must not be generated from smoke data. Gate on manifest having meaningful accepted rows.

---

## Decision: Frank — Stage 2 Second Raw Fetch Pass (HK Statutes + CX Revisions)

**Owner:** Frank (Hawaiian Data Collector)  
**Date:** 2026-05-02  
**Status:** Decision — informational + two hand-offs (Rusty alignment infra; Linus plan-entry rename)  
**Reference:** `.squad/orchestration-log/2026-05-01T08-09-38Z-frank-stage2-second-batch.md`

### Summary

Both known raw-only Stage-2 leads now have body text on disk:

- **Hawaiian Kingdom statutes** — 8 IA `_djvu.txt` OCR files (6.86 MB total) for all four paired imprints, written under `data/raw/hawaiian-kingdom-statutes-paired-imprints/20260501/`. IA filename mapping recorded in `fetch.jsonl`.
- **Wikimedia CX EN→HAW** — 42 article-revision JSON responses (1.2 MB; 21 EN + 21 HAW) under `data/raw/wikimedia-cx-en-haw-published/20260501/revisions/`, covering all 21 translations surviving the gate `stats.mt<0.5 AND stats.human>0`.

**Zero new candidate rows.** On-disk Stage-2 candidate inventory unchanged at **1,612** (Andrews 1194 + Kaikki 292 + Tatoeba 121 + Bible smoke 5). Both adapters blocked on alignment infra Frank does not own.

### Numbers

| Source | Files | Bytes | Output dir |
|---|---|---|---|
| HK statutes paired imprints | 8 | 6,860,576 | `data/raw/hawaiian-kingdom-statutes-paired-imprints/20260501/` |
| CX revision wikitext | 42 | ~1,200,000 | `data/raw/wikimedia-cx-en-haw-published/20260501/revisions/` |

### Key Findings

**HK statutes candidate adapter not shipped:**

- 1859 Civil Code: EN has 1866 appendix laws bound in, breaking monotonic Section-N numbering
- 1869 Penal Code: HAW `Pauku N` yields only 3 regex matches — column/page-region OCR needed
- 1897 Penal Laws: EN uses §N continuously; HAW uses Pauku N with chapter resets — integer intersection invalid
- 1846 Statute Laws: bilingual *interleaved-columns* imprint, needs page-layout-aware OCR

Per identity (precision > recall), no rows emitted. Per Rusty's "section-id-first vs LaBSE-fallback" memo.

**CX candidate adapter not shipped:**

Needs LaBSE infra Frank does not own. Fetch plan step 4 delegates to "standard Tier-B pipeline (Rusty owns threshold; default 0.75)." Substantive HAW content thinner than gate suggests:

| Pair shape | Count |
|---|---|
| HAW=0 words (target deleted/empty) | 8 |
| HAW < 50 words | 5 |
| HAW < 250 words and ratio HAW/EN < 0.10 | 6 |
| HAW comparable to EN (ratio 0.5–1.5) | **2** |

Two substantive pairs: translationIds **1378441** and **2851619**. Yield from this corpus: low tens of pairs post-LaBSE at best (not 1–3k as originally projected).

### Hand-offs

→ **Rusty (alignment infra):** HK statutes need layout-aware re-OCR or LaBSE-based sentence alignment; CX needs LaBSE thresholding (default 0.75).

→ **Linus (fetch plan):** Plan entry `hawaiian-kingdom-statutes-bilingual` mislabels esrp468790723 as "1869 Penal Code HAW" when it's the 1850 reissue that was the *source* for the EN code. Consider relabeling or splitting.

### Files

- `scripts/208_fetch_hk_statutes_djvu.py` (new, ~170 LOC, stdlib-only)
- `scripts/209_fetch_cx_published_revisions.py` (new, ~205 LOC, stdlib-only)
- Raw output directories and `fetch.jsonl` ledgers (gitignored)

---

## Decision: Linus — Bible & OPUS Status Reconciliation

**Owner:** Linus (Data Engineer)  
**Date:** 2026-05-02  
**Status:** Decision — gates clarified; priority queue established  
**Reference:** `.squad/orchestration-log/2026-05-01T08-09-38Z-linus-queue-bible-opus.md`

### Bible (Baibala Hemolele 1839 × English PD)

**Gate Status:** ✅ **ALL GATES CLEARED** (as of 2026-05-01)

Prior fetch plan showed stale gates (`rights_review_required`, `verification_status: pending_rights_review`). Both resolved:

1. **Edition pinned:** `baibala-hemolele-1839` — Linus confirmed live Greenstone URL, all 66 books mapped with `greenstone_oid` and `book_name_lower`.
2. **ToS snapshot captured:** `data/raw/baibala-hemolele-1839/20260501/tos_snapshot.html` (SHA-256: `254c552c...`).
3. **Rights confirmed:** Public domain 1839 imprint; digitization copyright (2003–2008, Partners In Development Foundation) does not extend to the text.

**Action taken:** `stage2-parallel-fetch-plan.json` updated:
- `rights_status_hint` → `public_domain_confirmed`
- `verification_status` → `confirmed_live`
- `do_not_invoke_until` → `[]`
- Added `edition_pinned`, `edition_pinned_by`, `tos_snapshot_path`, `tos_snapshot_sha256` fields

`python3 scripts/107_collect_stage2_parallel.py --dry-run` passes cleanly.

### What Remains Before Full Bible Production

| Step | State | Owner |
|---|---|---|
| HAW HTML parser | ✅ Done | Frank |
| HAW smoke fetch (3 chapters) | ❌ Not yet run | Frank |
| ENG USFM zip fetch | ❌ Ready (no gates) | Frank |
| **ENG USFM-to-verse-txt parser** | ❌ **Unwritten** | **Linus** |
| Bible candidate build | ❌ Blocked on ENG parser | Frank |

**Blocker detail:** `322_build_bible_candidates.py` currently reads ENG from fixture `.txt` files (one line per verse: `N: text`). Real implementation needs `scripts/206b_parse_eng_usfm.py` to parse KJV USFM zip → `eng/<BOOK>_<chapter>.txt` verse files. This is the only unwritten piece before smoke test can run.

**Smoke command:**

```bash
# Step 1: HAW smoke fetch (3 chapters, safe)
python3 scripts/206_fetch_baibala_raw.py \
  --execute --side haw \
  --book GEN --chapters 1-3 \
  --confirm-edition baibala-hemolele-1839 \
  --tos-snapshot data/raw/baibala-hemolele-1839/20260501/tos_snapshot.html

# Step 2: ENG zip fetch (ready now)
python3 scripts/207_fetch_stage2_parallel_raw.py \
  --execute --source bible-eng-pd-anchor

# Step 3: Once ENG parser exists, build smoke candidates
python3 scripts/322_build_bible_candidates.py --from-raw <YYYYMMDD> --execute
```

**Yield projection:** 8–12k pairs (largest immediate opportunity).

### OPUS (haw-containing parallel subsets)

**Gate Status:** 🔴 **GATES REMAIN** — both valid (live blockers, not stale)

| Gate | Status | Reason |
|---|---|---|
| `rights_review_required` | ❌ Open | Per-corpus licenses not yet snapshotted (Ubuntu/GNOME/KDE permissive but heterogeneous; QED unknown) |
| `endpoint_check_required` | ❌ Open | Exact version IDs not confirmed at fetch time; OPUS URLs can shift |

**Technical readiness:** Can be raw-fetched with `--allow-rights-review --allow-pending-endpoint` flags. But:

- No candidate converter exists (`adapter_status: "none"`)
- Tatoeba duplicate risk — upstream adapter already pulled Tatoeba HAW-ENG
- Software-l10n skew — Ubuntu/GNOME/KDE are UI-string heavy; ≤15% parallel-train token cap applies

**Yield projection:** 2–5k pairs (after dedup + caps).

**Blocker:** Per-corpus rights snapshots + endpoint version confirmation needed before fetch.

### What Blocks OPUS Candidate Rows

| Step | State | Owner |
|---|---|---|
| `rights_review_required` gate cleared | ❌ Open | Linus |
| `endpoint_check_required` gate cleared | ❌ Open | Frank |
| Raw zip fetch | ❌ Blocked | Frank |
| Candidate converter | ❌ Not written | Linus |
| Dedup against upstream Tatoeba | ❌ Not yet done | Linus |

### Priority Order for 80k Gap Closure

1. **Bible ENG USFM parser** (Linus) — unlocks 8–12k pairs, critical path
2. **Bible HAW smoke + full fetch** (Frank) — 3-chapter smoke first
3. **OPUS rights snapshots + endpoint check** (Linus rights, Frank endpoint)
4. **OPUS converter `32X_build_opus_candidates.py`** (Linus)

**Do not fetch OPUS until per-corpus rights snapshots are on disk and endpoint versions confirmed.**

### Impact on 80k Target

- Bible (full): 8–12k pairs ← ENG parser is critical path
- OPUS: 2–5k pairs ← gates + converter needed
- HK statutes: 3–6k pairs (pending Rusty LaBSE) ← blocked
- CX: 0–1k pairs (pending Rusty LaBSE) ← blocked, honest yield much lower than projected

NLLB mining + synthetic BT remain necessary to bridge remaining gap to 80k.


---

## Decision: Frank — Bible raw fetch pass (HAW Genesis + ENG KJV/ASV anchor) (2026-05-02)

**Owner:** Frank (Hawaiian Data Collector)  
**Date:** 2026-05-02  
**Status:** COMPLETE (execution blocked by downstream text-quality fix)

### Summary

Fetched raw bytes for Bible stage-2 adapter per fetch-plan. HAW Genesis (50 chapters, 840 KB) + ENG KJV/ASV USFM zips (5.1 MB) now on disk with full provenance ledgers. Dry-run candidate generation showed 1,533 Genesis verse pairs, but identified contamination: Strong's number attributes (`|strong="H7225"`) leaking into `text_en`. Holding candidate write pending USFM parser cleanup (Linus task).

### What was fetched

| Side | Source ID | Path | Files | Bytes | ToS |
|---|---|---|---|---|---|
| HAW | `baibala-hemolele-1839` | `data/raw/baibala-hemolele-1839/20260501/GEN_001.html` … `GEN_050.html` | 50 chapter HTML | 840 KB | snapshot at 20260501/tos_snapshot.html |
| ENG | `bible-eng-pd-anchor` | `data/raw/bible-eng-pd-anchor/20260501/eng-kjv2006_usfm.zip` | 1 zip | 2.47 MB | public domain (eBible) |
| ENG | `bible-eng-pd-anchor` | `data/raw/bible-eng-pd-anchor/20260501/eng-asv_usfm.zip` | 1 zip | 2.87 MB | public domain (eBible) |

### Provenance

- `data/raw/baibala-hemolele-1839/fetch.jsonl` — 54 rows (50 GEN chapters + 4 prior smoke rows). Each row: `raw_sha256`, `source_url`, `fetch_timestamp_utc`, `tos_snapshot_path`.
- `data/raw/bible-eng-pd-anchor/fetch.jsonl` — 2 rows (KJV + ASV zips).

### Candidate generation validation

- Infrastructure ready: `scripts/322_build_bible_candidates.py` already supports USFM via `scripts/206b_parse_eng_usfm.py`.
- Dry-run: 50 chapters paired → 1,533 rows emitted (0 skipped).
- **Blocker:** ENG text contaminated with Strong's markers:
  ```
  "text_en": "In the beginning|strong=\"H7225\" God|strong=\"H0430\" created|strong=\"H1254\""
  ```

### Why candidates not written

`206b_parse_eng_usfm.py` strips standard USFM markers (`\wj`, `\nd`, `\add`, etc.) but does NOT strip `\w …|strong="…"\w*` word-with-attributes markers used in eBible KJV2006 + ASV packaging. Fetch plan explicitly forbids: "USFM-to-plain-text extraction must drop section headers, footnote anchors, and editorial brackets to avoid leaking non-translation tokens into target_text." Emitting 1,533 rows with Strong-number leakage into `text_en` would be overcounting on a contaminated field.

### Next steps (hand-offs)

1. **Parser fix (Linus):** Strip `\w …|strong="…"\w*` markers in `206b_parse_eng_usfm.py` → add regression tests → unblock 1,533 Genesis rows.
2. **Baibala completion (Frank + Coordinator):** Fetch remaining 65 books (~30 min polite fetching) once parser is fixed.
3. **OPUS (Linus):** Deferred; requires rights review + per-corpus license snapshots.

### Caller-trap (small fix worth flagging)

`206_fetch_baibala_raw.py --execute` requires `--tos-snapshot` to be absolute path or REPO_ROOT-resolvable. Passing `--tos-snapshot data/raw/.../tos_snapshot.html` (CWD-relative string) crashes inside `fetch_one()` with `ValueError: '...' is not in the subpath of '<REPO_ROOT>'` from `Path.relative_to()`. Real fix: resolve path against REPO_ROOT before `relative_to` is called.

### Sign-off

✅ Fetched HAW Genesis 1-50 (50 chapters, 840 KB) and ENG KJV+ASV USFM zips (5.1 MB) with full provenance. Confirmed end-to-end candidate yield is ~1,533 rows for Genesis alone. Blocked on one-line USFM text-cleanup fix (not Frank's lane). Zero new candidate rows written; total on disk still 1,612. No commits.

---

## Decision: Linus — Bible English USFM parser + wiring (2026-05-02)

**Owner:** Linus (Data Engineer)  
**Date:** 2026-05-02  
**Status:** COMPLETE (pending upstream fetch)

### Summary

Delivered stdlib-only English USFM parser (`scripts/206b_parse_eng_usfm.py`) and wired Bible candidate builder (`scripts/322_build_bible_candidates.py`). Parser handles any `.usfm` file or `.zip` of USFM files (KJV, ASV, WEB, etc.). All 50/50 Bible tests passing. Infrastructure now ready to consume WEB or KJV USFM zip on arrival.

### What is now unblocked

**English USFM parser:** `scripts/206b_parse_eng_usfm.py` is live, stdlib-only, and tested:
- 13 parser unit tests + 7 wired-builder tests
- Consumes any single `.usfm` file (KJV, ASV, WEB — all use same USFM markers)
- Consumes any `.zip` of `.usfm` files (e.g. WEB full-Bible zip from ebible.org)

**Builder wiring:** `scripts/322_build_bible_candidates.py` now accepts `--eng-usfm-file` and `--eng-usfm-zip` alongside `--haw-raw-dir`. Single command produces full candidate rows:
```
python scripts/322_build_bible_candidates.py --execute \
  --haw-raw-dir data/raw/baibala-hemolele-1839/<YYYYMMDD>/ \
  --eng-usfm-zip data/raw/english-bible-web/<YYYYMMDD>/web.zip
```

**Candidate schema:** Both USFM-wired and raw-HTML paths produce rows that pass `320_build_stage2_manifest.py --check`. All rows carry `split=train`, `prototype_only=true`, `release_eligible=false` per Bible tier policy.

### Remaining gaps

| Gap | Owner | Blocker Level |
|---|---|---|
| ENG USFM zip not yet fetched (WEB or KJV) | Frank | HIGH |
| HAW corpus incomplete (Genesis only, 50/1189 chapters) | Frank | HIGH |
| ENG edition pin in `source_registry.json` | Linus | MEDIUM (post-fetch) |
| OPUS adapter not started | Linus | MEDIUM |

### Yield projections (pending full fetch)

- Genesis alone (31 chapters): ~930–1000 pairs
- Full 66-book canon: ~8k–12k pairs
- Policy cap: ≤30% of parallel-train tokens

### Sign-off

✅ Parser + wiring complete; 50/50 tests passing. Infrastructure ready for WEB/KJV fetch. No commits.

---

## Decision: Linus — Bible English USFM markup cleanup + Genesis candidate emission (2026-05-02)

**Owner:** Linus (Data Engineer)  
**Date:** 2026-05-02  
**Status:** COMPLETE (manifest ready for materialization)

### Summary

Fixed Strong's number leakage in USFM parser. Implemented three-pass cleanup in `_strip_inline_markers()` to handle `\w word|strong="H7225"\w*` annotated-word format. Shipped 1,533 clean Genesis candidates with 0 leakage. Manifest dry-run: 3,140 total rows, 0 violations. KJV pinned as ENG anchor.

### Root cause identified & fixed

**Issue:** `\w word|strong="H7225"\w*` USFM markers left `|strong="…"` fragments in `text_en`.

**Solution:** Three-pass cleanup in `_strip_inline_markers()` (`206b_parse_eng_usfm.py`):
1. `_WORD_ATTR_RX` — extract bare word from `\w word|attrs\w*`, drop all attributes
2. `_INLINE_MARKER_RX` — strip existing `\marker` / `\marker*` tokens
3. `_ATTR_FRAGMENT_RX` — belt-and-suspenders catch leftover `|attr="…"` fragments

No changes to `322_build_bible_candidates.py` or `normalize_en()`.

### Regression tests (3 new)

Added to `TestUSFMParser` in `code/tests/test_bible_adapter.py`:
- `test_strong_number_attribute_stripped` — direct leakage case
- `test_nested_inline_markers_with_word_attrs_stripped` — nested marker case
- `test_plain_text_verse_unchanged_by_cleanup` — determinism guard

**Result:** 53/53 tests passing (+3 new)

### Validation

| Check | Result |
|---|---|
| `py_compile 206b_parse_eng_usfm.py 322_build_bible_candidates.py` | ✅ clean |
| `python3 code/tests/test_bible_adapter.py -v` | ✅ 53/53 OK (+3 new) |
| `grep '\|strong=' data/stage2/candidates/bible.jsonl` | ✅ 0 matches |

### Genesis candidate emission

```
python3 scripts/322_build_bible_candidates.py \
  --execute \
  --haw-raw-dir data/raw/baibala-hemolele-1839/20260501/ \
  --eng-usfm-zip data/raw/bible-eng-pd-anchor/20260501/eng-kjv2006_usfm.zip \
  --fetch-date 20260501
```

**Result:** 1,533 rows written to `data/stage2/candidates/bible.jsonl`. KJV anchor. 50 HAW Genesis chapters paired, 0 skipped. 0 leakage.

### Manifest dry-run

```
python3 scripts/320_build_stage2_manifest.py --dry-run
→ 3,140 total rows   0 violations
```

Breakdown: baibala-hemolele-1839 = 1,533 | andrews-1865 = 1,194 | kaikki-wiktionary = 292 | tatoeba = 121.

### Decisions locked

1. **KJV (`eng-kjv2006_usfm.zip`) is the pinned English anchor** for Bible pair. ASV on disk but not used. Consistent with Frank's recommendation (canonicality + smaller corpus for Genesis sanity-check).

2. **Cleanup in parser layer, not normalization.** Intentional: parser produces clean plain text regardless of downstream `normalize_en()`. `normalize_en()` in `322` remains thin NFC+strip.

3. **Manifest `--execute` is safe.** Dry-run clean, 0 violations. Recommend triggering materialization post-coordinator confirmation no other candidates pending.

4. **Remaining Bible gap:** Only Genesis (50 chapters) fetched HAW side. Remaining 65 books require `206_fetch_baibala_raw.py --book <code> --execute`. Expected full-Bible yield: ~8k–12k pairs.

### Sign-off

✅ Parser fix shipped; 1,533 clean Genesis rows written; manifest validated 0 violations. Total candidates on disk: 3,140. KJV edition locked; policy compliance confirmed. No commits.


---

## Decision: Frank — Pentateuch raw fetch batch completed (EXO/LEV/NUM/DEU) (2026-05-01)

**Owner:** Frank (Hawaiian Data Collector)  
**Date:** 2026-05-01T08:28Z  
**Status:** COMPLETE — raw fetch done; candidate emission deferred  

### Summary

Fetched the next bounded, polite Baibala HAW batch after Genesis: **Exodus + Leviticus + Numbers + Deuteronomy** (Pentateuch tail). Used existing `baibala-hemolele-1839` edition pin and on-disk ToS snapshot. One bounded `--execute` invocation per book to honor per-book chapter spec; `--limit 200` (hard cap) on each. Zero candidate emission pending Linus confirmations.

### Actual Raw Fetch Counts

| Book | Chapters fetched | Bytes |
|---|---|---|
| EXO | 40 | 567,354 |
| LEV | 27 | 388,943 |
| NUM | 36 | 547,196 |
| DEU | 34 | 490,140 |
| **This pass** | **137** | **1,993,633** (~1.95 MB) |

Provenance ledger `data/raw/baibala-hemolele-1839/fetch.jsonl`:
54 → **191** lines (+137). Each row carries source URL, fetch timestamp UTC, HTTP 200, content-type, raw_sha256, raw_storage_path, ToS snapshot path, and source-specific IDs (side/book_code/chapter).

Cumulative HAW canonical chapter HTML on disk under `data/raw/baibala-hemolele-1839/20260501/`: **187 files** (Genesis 50 + Pentateuch tail 137).

### Why This Scope (not "all remaining books")

`206_fetch_baibala_raw.py` has no safe all-book mode:

- `MAX_LIMIT_CHAPTERS=200` hard cap per invocation.
- A single `--chapters` spec applies to *every* `--book` passed, so multi-book calls fail when a book's chapter count is below the range (verified: `EXO 1-50` rejected for `max_chapter=40`).
- Per-book/group invocation is the only safe shape; Pentateuch tail is the natural next contiguous block after Genesis and stays well under the cap.

At 1.5 s polite rate this batch was ~3.5 min of traffic. No overload risk; no errors.

### Candidates Emitted

**Zero — intentionally.** Per task directive, Frank did not run `scripts/322_build_bible_candidates.py`. The directive was:

> "Do not emit candidates unless the exact matching English USFM path is already proven clean and the candidate build can be bounded to the fetched books without disrupting Linus's concurrent materialization."

Frank has no signal that `322`'s `--book-codes` style scoping (or equivalent bounded-build flag) is wired and that Linus's USFM Strong's-marker cleanup, confirmed clean for Genesis (1,533 rows), also produces clean text for EXO/LEV/NUM/DEU. Surfacing for Linus.

### Handoff to Linus

1. **Confirm the USFM Strong's-marker cleanup** applied to KJV Genesis also handles EXO/LEV/NUM/DEU (no `|strong="…"` leakage, `\add`/`\add*` stripped, section headers dropped).
2. **Confirm `322_build_bible_candidates.py` can be invoked book-bounded** (e.g. only on EXO/LEV/NUM/DEU) without colliding with the Stage-2 manifest materialization currently running. If yes, Frank will run the bounded candidate build and report row counts in a follow-up inbox note. If a book-bounded mode is missing, the one-flag addition (e.g. `--book-codes EXO,LEV,NUM,DEU`) is the smallest unblock.

### Next Recommended Bible Batch (after Pentateuch candidates ship)

**JOS (24) + JDG (21) + RUT (4) = 49 chapters** — Historical books group 1. Bounded, ~75 s polite, contiguous canonical block, well under the 200-chapter cap. Same invocation pattern as this pass (per-book `--execute` with the existing edition pin and ToS snapshot).

### Blockers

- **For raw HAW fetch:** None.
- **For candidate emission:** Blocked on two Linus confirmations above.

### Commits

None (per task directive).

---

## Decision: Rusty — Baibala Hemolele 1839 historical-orthography policy exception (2026-05-02)

**Owner:** Rusty (NLP Researcher)  
**Date:** 2026-05-02  
**Status:** IMPLEMENTED — merged into POLICY_VERSION v0.2 by Linus (commit 50b89c0)

### Recommendation

Add a **narrow, source-pinned, train-only** acceptance carve-out for `haw_no_diacritics` when the row is genuine 1839 Baibala Hemolele text. Keep the flag itself and tag affected rows so any downstream consumer can see the historical register.

**Conditions for promotion (review → accept):**

1. `source == "baibala-hemolele-1839"` AND `edition_or_version == "baibala-hemolele-1839"` AND `register == "religious"`
2. `quality_flags ⊆ {"haw_no_diacritics"}` — no other soft/hard flags
3. `synthetic == false` AND `alignment_method == "verse-id"`
4. `split == "train"` (forced; never dev/test)

Gated by `PolicyConfig.allow_historical_orthography_exception` (default True for prototype).

### Key Findings

- 5,823 Bible candidates; 3,956 (~68%) flagged `haw_no_diacritics`; 3,897 carry **only** that flag
- Sampled rows confirm genuine 1839 Andrews/Bingham register — pre-Pukui-Elbert, intentional
- Signal interpretation differs by source: for Tatoeba/Wiktionary, no-diacritics is extraction loss; for 1839 Baibala, it is native register

### Guardrails

**Sub-cap (inside 30% Bible cap):**
- Historical-orthography rows ≤ 50% of accepted Bible train rows AND ≤ 15% of total parallel-train tokens
- Enforced deterministically by pair_id hash; recorded in build_manifest.json

**Dev/test exclusion:** Train-only; required for eval gate diacritic retention tripwires

**Source specificity:** Keyed on source==baibala-hemolele-1839 only

### Out of Scope

- Programmatic ʻokina/kahakō insertion
- Release-tier promotion
- Ulukau nūpepa OCR handling

---

## Decision: Frank — Baibala 1839 raw fetch: 1SA + 2SA + 1KI + 2KI (2026-05-02)

**Owner:** Frank (Hawaiian Data Collector)  
**Date:** 2026-05-02  
**Status:** COMPLETE — raw fetch done; candidates deferred

### Summary

Fetched 1 Samuel, 2 Samuel, 1 Kings, 2 Kings (102 chapters, 1.5 MB) from baibala.org. Provenance rows 240→342 appended.

### Counts

| Book | Chapters | Bytes |
|---|---:|---:|
| 1SA | 31 | 477,392 |
| 2SA | 24 | 375,849 |
| 1KI | 22 | 369,392 |
| 2KI | 25 | 299,908 |
| **Total** | **102** | **1,522,541** |

**Cumulative on disk:** 236 HAW chapter HTMLs (was 187 + 49 earlier).

### Status

- Fetch complete; provenance ledger updated
- Candidates deferred pending Linus USFM cleanup sign-off
- No blocker on raw side; next batch is 1CH + 2CH + EZR + NEH + EST

---

## Decision: Linus — Baibala 1839 historical-orthography policy implemented (2026-05-02)

**Owner:** Linus (Data Engineer)  
**Date:** 2026-05-02  
**Status:** IMPLEMENTED — committed as 50b89c0 `feat(stage2): Baibala 1839 historical-orthography policy (v0.2)`

### Code Changes

| File | Change |
|------|--------|
| `code/llm_hawaii/stage2_quality.py` | POLICY_VERSION → v0.2. PolicyConfig: allow_historical_orthography_exception, historical_orthography_train_token_share_max. score_pair() detects carve-out conditions and promotes to accept tier. |
| `scripts/320_build_stage2_manifest.py` | Added _apply_historical_orthography_cap() for deterministic row-count capping. Sub-cap enforcement and split=train forcing for exception rows. |
| `code/tests/test_stage2_manifest.py` | 15 new tests covering exception logic, cap enforcement, metadata fields, kill switch, determinism. |
| `docs/data-pipeline.md` | One-line entry linking to decision. |

### Manifest Results (GEN–RUT, v0.2)

| Metric | Value |
|--------|-------|
| Total candidates | 8,791 |
| Train | 3,350 |
| Dev | 15 |
| Review-pending | 5,426 |
| Historical-orthography accepted | 1,071 |
| Historical-orthography dropped (cap) | 3,791 |
| SFT rows | 6,700 |

### Test Results

- Existing: 53/53 ✅
- New historical-orthography: 15/15 ✅
- Kill switch verified
- Cap determinism confirmed

### Commit

```
50b89c0 feat(stage2): Baibala 1839 historical-orthography policy (v0.2)

- POLICY_VERSION bumped to v0.2
- New PolicyConfig fields for exception control
- score_pair() detects carve-out and applies tagging
- Manifest builder enforces sub-cap deterministically
- 15 new tests + docs update
```


---

## Decision: 1SA/2SA/1KI/2KI Bible materialization complete

**Owner:** Linus (Data Engineer)  
**Date:** 2026-05-01  
**Status:** EXECUTED

### What changed

Extended Bible candidate scope from GEN–RUT to GEN–2KI by adding 1 Samuel (31 ch), 2 Samuel (24 ch), 1 Kings (22 ch), and 2 Kings (25 ch). All 102 chapters were already on disk in `data/raw/baibala-hemolele-1839/20260501/` as confirmed in the task brief.

No code changes were required — the `--books` filter introduced in the Pentateuch batch is sufficient.

### Final counts

| Metric | Value |
|---|---|
| Bible candidates (GEN–2KI) | 10,221 (+3,037 vs GEN–RUT) |
| Total manifest rows (all sources) | 11,828 (was 8,791) |
| Train rows | 4,665 (was 2,279) |
| Dev rows | 15 (unchanged, all non-Bible) |
| Review-pending rows | 7,148 (was 6,512) |
| SFT directional rows | 9,330 (was 4,558) |
| Bible dev/test rows | 0 ✅ |
| Historical-orthography accepted | 1,509 |
| Historical-orthography dropped | 5,399 |
| USFM/Strong/footnote leaks | 0 ✅ |
| Duplicate pair_ids | 0 ✅ |

### Policy in effect

Historical-orthography v0.2 cap (`token_share_max=0.15`) is in effect. 1SA/2SA/1KI/2KI rows follow the same policy path as existing books — no special handling.

### Bounded scope

Per task brief: included only the 12 books listed (GEN through 2KI). No concurrent raw batches included.

---

## Decision: KJV TSV accepted as valid English anchor format

**Owner:** Linus (Data Engineer)  
**Date:** 2026-05-01  
**Status:** IMPLEMENTED

### Summary

`data/raw/kjv/kjv.usfm` is parsed as TSV (not USFM) for the haw1868 adapter path. This is the canonical KJV English anchor for Stage 2 Bible candidates from the `haw1868` USFM source.

### Format

Tab-separated, 31,103 lines (1 header + 31,102 verse rows):

```
orig_book_index  orig_chapter  orig_verse  orig_subverse  order_by  text
01O              1             1                          10        In the beginning God created ...
...
66N              22            21                         311020    The grace of our Lord...
```

`orig_book_index` prefix (2-digit 1-based position, e.g. `01O` = book 1 = GEN, `40N` = book 40 = MAT, `66N` = book 66 = REV) maps to canonical USFM book code via `_build_book_index_map(registry)`.

### Validation

- Header fields exactly: `orig_book_index`, `orig_chapter`, `orig_verse`, `orig_subverse`, `order_by`, `text`.
- Full local file: 31,102 verse rows, 0 malformed.
- GEN.1.1 and REV.22.21 present and correctly routed.
- `--books` filter supported for bounded runs.

### Usage

```bash
python3 scripts/322_build_bible_candidates.py \
  --dry-run \
  --haw-usfm-dir data/raw/haw1868/haw1868_usfm \
  --eng-kjv-tsv-file data/raw/kjv/kjv.usfm
```

### Source identity

- `source = "baibala-hemolele-1868"` (distinct from existing 1839 HTML rows)
- `edition_or_version = "haw1868-usfm+kjv-tsv"`
- `dedup_cluster_id = pair_id = "bible:{BOOK}:{CHAPTER}:{VERSE}"` — overlaps with 1839 rows for future collapse
- `license_observed_en = "Public domain — King James Version 1611 (pre-1925, US public domain)."`

---

## Decision: haw1868 as Verse-Aligned Source — Linus Review

**Owner:** Linus (Data Engineer)  
**Date:** 2026-05-03  
**Status:** DECISION — strategy change, implementation step defined

### Trigger

User confirmed `haw1868` has verse IDs. Task: determine whether it can be treated as a
verse-aligned Hawaiian Bible source by joining to existing public-domain English anchors
(ASV/KJV USFM already parsed locally), rather than as monolingual only.

### Findings

#### Edition identity — confirmed via eBible metadata

`haw1868` in the BibleNLP corpus (`bible-nlp/biblenlp-corpus`) is:

| Field | Value |
|---|---|
| ISO code | `haw` |
| Config id | `haw1868` |
| Full name | *Baibala Hemolele* — 1868 Andrews/Bingham revision |
| Description | "The Holy Bible in the Hawaiian language of the United States, 1868 revision" |
| Rights | **public domain** |
| Source | eBible.org digitization (`http://ebible.org/haw1868/`) |
| OT books/chapters/verses | 39 / 929 / 23,145 |
| NT books/chapters/verses | 27 / 260 / 7,957 |
| **Total** | **66 books / 1,189 chapters / 31,102 verses** |

The 1868 edition is the **same translators** (Andrews/Bingham) as our pinned
`baibala-hemolele-1839` source — it is a revised edition of the 1839 translation.

#### Verse IDs are sufficient for alignment — YES

The BibleNLP corpus stores each translation as monolingual `{vref, text}` rows where
`vref` is standard USFM notation (`GEN 1:1`, `MAT 5:3`, etc.). Our existing
`206b_parse_eng_usfm.py` produces `{"book":"GEN","chapter":1,"verse":1,"text":"..."}`.
Join key transformation: `vref.replace(" ", " ").split()` → `book, ch_v.split(":")` → trivial.
No new alignment methodology required. `alignment_method="verse-id"` applies.

#### Relationship to baibala-hemolele-1839

| Dimension | 1839 (current) | 1868 (new) |
|---|---|---|
| Translation team | Andrews/Bingham | Andrews/Bingham (same) |
| Rights | Public domain (confirmed, pinned) | Public domain (eBible metadata) |
| Coverage in bible.jsonl | GEN–2KI (12 books, 10,221 rows) | Full 66 books (31,102 verses) |
| Text similarity | — | High: same translators, revised edition |
| Exact-sha256 overlap | — | Partial: some verses identical, some editorially revised |

### Decision: Source Strategy Change

**haw1868 is an acceleration path for the remaining Bible acquisition**, not an
orthogonal new source. We had planned to scrape the remaining 54 books from
baibala.org chapter-by-chapter. haw1868 via the BibleNLP hub covers the full 66 books
in one download at effectively zero scraping cost.

**Adopt haw1868 as the primary acquisition path for Bible books not yet in bible.jsonl.**
Baibala.org 1839 remains the canonical pinned source for GEN–2KI (already materialized);
haw1868 fills in the remaining 54 books.

### Adapter Changes Required

#### 1. Extend `322_build_bible_candidates.py` — preferred over a new adapter script

All the join logic (normalize_haw, compute_pair_hash, verse-id pairing) already lives in
322. Add a `--from-biblenlp-jsonl HAW_VERSES_JSONL` input mode that:

- Reads a pre-downloaded `{vref, text}` JSONL file (one verse per row)  
- Parses `vref` → `(book_code, chapter, verse)` using the standard `"BOOK CH:V"` format  
- Joins to the locally-parsed KJV USFM verses (already available via `--eng-usfm-zip`)  
- Applies existing `normalize_haw` + `compute_pair_hash`  
- Emits to **`data/stage2/candidates/bible-haw1868.jsonl`** (separate file from
  `bible.jsonl` so each source is independently managed and the manifest can track per-source counts)

#### 2. source_id / edition metadata

| Field | Value |
|---|---|
| `source` | `"biblenlp-haw1868"` |
| `edition_or_version` | `"baibala-hemolele-1868"` |
| `pair_id` | `"bible-1868:{BOOK}:{CH}:{V}"` (unique, distinguishes from 1839 rows) |
| `dedup_cluster_id` | `"bible:{BOOK}:{CH}:{V}"` (**shared edition-neutral key**) |
| `license_observed_haw` | `"Public domain — 1868 Andrews/Bingham revision, pre-1925 US work. Source: eBible.org haw1868 corpus (http://ebible.org/haw1868/)."` |
| `alignment_method` | `"verse-id"` |
| `register` | `"religious"` |
| `split` | `"train"` (Tier A: 0% dev/test) |

#### 3. Dedup against baibala-hemolele-1839 candidates

`dedup_cluster_id = "bible:{BOOK}:{CH}:{V}"` is already the format used by existing
`bible.jsonl` rows (`dedup_cluster_id` = `pair_id` = `"bible:{BOOK}:{CH}:{V}"`).

When both editions produce a row for the same verse position, the manifest's dedup pass
sees two rows with the **same `dedup_cluster_id`**. Resolution rule:

- Prefer `baibala-hemolele-1839` (already pinned, ToS snapshot captured) for GEN–2KI.  
- For books NOT yet in bible.jsonl (books beyond 2KI), `biblenlp-haw1868` is the only
  row in the cluster → no collision.

This means the haw1868 rows for GEN–2KI are **redundant** (cluster already satisfied)
and will be skipped by the dedup pass. The net-new contribution comes from the 54 books
not yet fetched from baibala.org.

**Important:** The manifest builder (`320_build_stage2_manifest.py`) must be confirmed
to implement or receive a dedup-cluster collapse step before this matters. If it does
not currently collapse by `dedup_cluster_id`, both rows would land in the manifest as
separate training examples — which is acceptable for near-identical editions but should
be flagged as a cross-edition near-duplicate.

#### 4. Historical orthography policy

The existing `stage2-quality-v0.2` policy (`historical_orthography_exception=true`,
`orthography_era="pre-pukui-elbert"`, `haw_no_diacritics` flag) applies verbatim.
The 1868 edition is the same pre-Pukui-Elbert orthographic era as 1839; no separate
policy is needed. The policy language does not name a specific year — it applies to
all pre-1949 Hawaiian text. No change required.

#### 5. Train-only / dev-test rule

Same Tier A rule: `split="train"` only, 0% dev/test. Combined Bible token cap (≤30%
of parallel-train tokens) applies across BOTH `bible.jsonl` + `bible-haw1868.jsonl`.
The manifest builder must sum both sources when checking the Bible cap.

### Yield Estimate

| Segment | Verse count | Est. net-new candidates |
|---|---|---|
| GEN–2KI (already in bible.jsonl) | ~10,221 | ~0 (dedup_cluster_id collapses to 1839) |
| Remaining 54 books (not yet fetched) | ~20,881 | **~19,000–20,500** (after filtering empties, versification gaps) |
| Total haw1868 full Bible | 31,102 | **~19,000–20,500 net-new pairs** |

This would roughly double the Bible candidate pool (10,221 → ~30,000), covering the
full Protestant canon without the ~20k remaining baibala.org chapter scraping calls.

### Next Concrete Implementation Step

1. **Rights confirmation (Linus, immediate):** Confirm eBible haw1868 rights posture.
   eBible metadata says `public domain`; eBible.org terms allow free use of PD texts.
   Capture a ToS snapshot from `http://ebible.org/terms/` analogous to the baibala.org
   snapshot. Add a `biblenlp-haw1868` entry to `data-sources/bible/source_registry.json`
   (new `sides.haw1868` block or a separate registry at `data-sources/biblenlp-haw/`).

2. **Hub probe (cheap, no bulk download):** Hit the `bible-nlp/biblenlp-corpus`
   datasets-server `/rows` endpoint for `haw1868`, limit=5, to confirm `{vref, text}`
   schema and check a sample verse for ʻokina encoding and character normalization needs.

3. **Download haw1868 JSONL** (single parquet/JSONL pull, ~1–2 MB compressed; 31k rows):
   `huggingface-cli download --repo-type dataset bible-nlp/biblenlp-corpus --include "haw1868*"`
   or via `datasets` Python API. Store at `data/raw/biblenlp-haw/20260503/haw1868.jsonl`.

4. **Extend `322_build_bible_candidates.py`:** Add `--from-biblenlp-jsonl` flag with
   vref parser + join logic. Output to `data/stage2/candidates/bible-haw1868.jsonl`.
   Reuse existing normalization and `compute_pair_hash`.

5. **Tests:** Add fixtures and test class in `code/tests/test_bible_adapter.py` for the
   new input mode (synthetic vref JSONL → candidate rows).

### Risks

| Risk | Severity | Mitigation |
|---|---|---|
| eBible haw1868 ToS disallows training use | High | ToS snapshot first; if restricted, treat as eval-only |
| BibleNLP corpus digitization adds its own license layer | Medium | Verify dataset card license field before `--execute` |
| 1839 ≈ 1868 near-duplicates inflate Bible token share silently | Medium | `dedup_cluster_id` collapse; count combined token share against ≤30% cap |
| Versification differences (minor verse splits) | Low | Drop orphan vrefs; they are a small fraction |
| ʻOkina encoding in eBible corpus differs from baibala.org | Low | Confirmed `normalize_haw` already handles all common mis-encodings |

### Source Strategy Impact

This changes the Bible acquisition plan:

**Before:** Scrape remaining 54 books from baibala.org chapter-by-chapter (~20k HTTP
requests, rate-limited at 1.5 s/req = ~8 hours wall-clock).

**After:** Download haw1868 JSONL in one shot from the BibleNLP hub (~1 API call),
covering all 66 books. Continue to use baibala.org 1839 for GEN–2KI (already done).
Use haw1868 for books ISA onward. The two editions serve as mutual cross-validation.

**Recommend updating `data-sources/stage2-parallel-fetch-plan.json`** to promote
`biblenlp-haw` source from `pending_endpoint_check` / `eval cross-check only` to
**Tier A supplementary — train-eligible for books not covered by baibala-hemolele-1839**,
rights confirmation pending.

---

## Decision: 1868 Hawaiian Bible Stage-2 Candidates Materialized

**Date:** 2026-05-01  
**Author:** Linus (Data Engineer)

### Decision

Generated `data/stage2/candidates/bible_haw1868_kjv.jsonl` — 31,101 rows for the 1868 Hawaiian Bible paired with KJV, kept separate from `bible.jsonl` (1839 edition).

### Key Facts

- **Output path:** `data/stage2/candidates/bible_haw1868_kjv.jsonl`
- **source:** `baibala-hemolele-1868` | **edition:** `haw1868-usfm+kjv-tsv`
- **Rows:** 31,101 — all 1:1, no duplicate pair_ids or dedup_cluster_ids
- **Missing sides:** 1 haw-side missing, 1 eng-side missing (different keys)
- **Overlap with 1839 manifest:** 10,221 of 11,828 manifest dedup_cluster_ids overlap → merging would collapse those to 1,607 new 1839-only rows + 20,880 net-new 1868 rows

### Implication

Before merging into `stage2_manifest.jsonl`, the team needs to decide how to handle 10,221 verse dedup_cluster_ids shared between editions (same verse key = same dedup ID). The 1868 file covers the full Bible (31K rows) vs. the current manifest's 11,828 rows (GEN–2KI subset of 1839).

---

## Team Directive: Dedupe Bible Edition Overlap

**Date:** 2026-05-01  
**By:** yashasg (via Copilot)

Do not keep both the 1839 and 1868 Bible as independent Stage 2 training pairs; dedupe/collapse Bible verse overlap. Captured for team record.

---

## Team Directive: Stage 2 Total & Nupepa Expansion

**Date:** 2026-05-01  
**By:** yashasg (via Copilot)

Treat the deduped Stage 2 total as roughly 32k canonical rows after collapsing overlapping 1839/1868 Bible verses; next Stage 2 data expansion should use Playwright to pull data from Nupepa. Captured for team record.


---

## User Directive: Stage 2 discovery pivot to bilingual/parallel data (2026-05-01T13:28:17-07:00)

**By:** yashasg (via Copilot)

**What:** Stage 2 data discovery should focus on bilingual/parallel or SFT-suitable data, not monolingual newspaper OCR. Nupepa/newspapers are monolingual and OCR-faulty, so they are not the first place to look for Stage 2.

**Why:** User request — captured for team memory

**Status:** IMPLEMENTED — Linus and Frank spawned to operationalize; decisions staged in inbox.

---

## Decision: Linus — Stage 2 Source Filter: Acceptance Criteria & Discovery Target List (2026-05-01)

**Owner:** Linus (Data Engineer)  
**Date:** 2026-05-01  
**Status:** PROPOSAL — for Frank's next Ulukau-family discovery pass and team alignment  
**Triggered by:** User correction that Nupepa/newspapers are monolingual OCR and should not be the primary Stage 2 discovery target.

### Summary

Stage 2 currently holds **11,828 canonical manifest rows / 9,330 directional SFT rows** against an **80k directional SFT row target**. The corpus is heavily Bible-weighted. Bible token-share approaches the 30% cap once both 1839 and 1868 editions are merged (~32k combined after dedup). All remaining volume must come from non-Bible sources. The prior discovery session was routed toward Nupepa newspaper OCR — correct for Stage 1 monolingual signal, wrong for Stage 2 parallel expansion.

### Stage 2 Acceptance Filter

A source qualifies for **Stage 2 (parallel manifest)** if and only if **all** of the following hold:

| Gate | Requirement |
|---|---|
| **Both sides present** | Source contains both a Hawaiian (haw) and English (en) text for each record. One side cannot be auto-inferred or MT-generated without being flagged `synthetic=true`. |
| **Alignment traceable** | Pair alignment is deterministic (verse-id, line-number, filename-pair, TMX) or score-gated (LaBSE ≥0.75 for comparable sources, per pipeline policy). Community/crowd translations only if density ≥50% of records have an English companion. |
| **Rights clear for prototype** | License is open (CC BY*, CC0, public domain) OR a rights-review decision exists on disk confirming prototype-only posture is covered. No "All Rights Reserved" sources without explicit sign-off. |
| **Not eval-contaminated** | Source records not already in `data/evals/eval_hashes.jsonl`. Eval-only sources (FLORES+, Global-PIQA) must hash into eval first and never enter train. |
| **Register supported** | `register` value must be one of: `religious`, `software-l10n`, `encyclopedic`, `educational`, `news`, `dictionary-example`, `unknown`. |

### Alignment type sub-tiers

| alignment_type | Accepted for Stage 2? | Notes |
|---|---|---|
| `parallel-verse` | ✅ Tier A | Bible only; 30% token cap enforced. |
| `parallel-sentence` | ✅ Tier A | Tatoeba, OPUS TMX lines. Best quality. |
| `parallel-doc` | ✅ Tier B | Document-level pairs (statutes, bilingual moolelo); needs sentence segmentation pass. LaBSE score recommended. |
| `dictionary-example` | ✅ Tier B | Andrews, Parker, Wiktionary. Cap at 5k rows; never dev/test. |
| `comparable-aligned` | ✅ Tier C (score-gated) | Must have LaBSE ≥0.75. NLLB mined lives here. |
| `synthetic-bt` | ✅ Tier D (capped) | Back-translation; ≤15% of directional SFT rows; never dev/test. |
| `synthetic-ft` | ✅ Tier D (tighter cap) | Forward-translation; ≤10% of directional SFT rows; never dev/test. |
| `monolingual-ocr` | ❌ **Not Stage 2** | Route to Stage 1 only. |
| `community-translation-sparse` | ❌ **Eval-only** | If density <50% aligned, treat as eval signal only. |

### Reject / Deprioritize List

| Source class | Disposition | Reason |
|---|---|---|
| **Nupepa.org Hawaiian newspapers** | ❌ Stage 1 only (or eval-slice if <1k bilingual articles found) | Monolingual Hawaiian OCR. English user-translations are sparse (<1k articles estimated). Rights also restrictive (All Rights Reserved). |
| **Other Veridian/Greenstone OCR-only collections** | ❌ Stage 1 only | Same class as Nupepa. If a collection has zero English companion text, it is monolingual by definition. |
| **mC4 haw** | ❌ Deprioritized Stage 1 | CommonCrawl overlap with FineWeb-2. Already captured. |
| **OSCAR-2301 haw** | ❌ Skip | Heavy FineWeb-2 overlap. |
| **Rights-restricted bulk pages** | ❌ Do not fetch | "All Rights Reserved" + "no copying" = cannot use even prototype-only without explicit institution sign-off. |
| **Community-contributed sparse translations** (Veridian `getUserTranslation`) | ⚠️ Eval-only | If density <50% of articles have an English companion, use only for eval, never train. Hash into eval_hashes.jsonl before any other ingest. |
| **Social media / forum bilingual** | ❌ Excluded | No per-poster permission; excluded by pipeline global policy. |
| **LLM-generated synthetic Hawaiian not grounded in source pair** | ❌ Excluded | Violates pipeline policy; no provenance chain. |
| **Auto-MT outputs not flagged synthetic** | ❌ Excluded | Must carry `synthetic=true` on both sides if MT-generated; otherwise excluded. |
| **FLORES+ / Belebele / Global-PIQA / Taxi1500** | 🔒 Eval-only | Confirmed in plan. Hash before any other use. Never train. |

### Ranked Target List for Frank's Ulukau-Family Discovery Pass

Priority: **density of bilingual alignment × rights posture × likely row yield × dedup novelty vs existing plan.**

**Tier A — Search now:**

| Rank | Source class | URL | alignment_type | Expected yield | Rights |
|---|---|---|---|---|---|
| 1 | **wehewehe.org full dictionary** (Andrews 1865 + Parker 1922 entries with example sentences) | wehewehe.org | `dictionary-example` | 5–15k examples, cap 5k | Public domain (pre-1925) |
| 2 | **Ulukau bilingual moolelo / paired texts** (hooilina.org, puke.ulukau.org with English companion) | hooilina.org, puke.ulukau.org | `parallel-doc` | Unknown; pilot 1–2 first | Likely PD or institution permission |
| 3 | **Hawaiian Kingdom statutes bilingual** (already in fetch plan) | Various | `parallel-doc` | 2–5k sentence pairs | Public domain (pre-1925) |
| 4 | **Wikimedia Content Exchange haw-en published** (already in fetch plan) | commons.wikimedia.org | `parallel-doc` | 1–3k confirmed pairs | CC BY-SA 4.0 |

**Tier B — Search next:** OPUS haw, UH Mānoa bilingual texts, translatewiki + wikimedia, NLLB mined (score-gated).

### Metadata Tags and Caps

| Source class | alignment_type | register | synthetic | Cap | dev/test eligible? |
|---|---|---|---|---|---|
| Bible (1839+1868 deduped) | `parallel-verse` | `religious` | false | **≤30% token share** | No |
| Dictionary examples (Andrews, Wiktionary) | `dictionary-example` | `dictionary-example` | false | **≤5k rows total** | No |
| HK statutes / bilingual docs | `parallel-doc` | `educational` or `encyclopedic` | false | None; LaBSE ≥0.75 required | Yes if score ≥0.75 |
| NLLB mined | `comparable-aligned` | `unknown` | false | **≤25% combined mined** | No |
| Alpaca-hawaiian-cleaned synthetic | `synthetic-ft` | `unknown` | true | **≤15% directional rows** (combined BT+FT) | No |
| BT synthetic Stage 1 | `synthetic-bt` | per source | true | **≤15% directional rows** | No |
| Nupepa OCR | *(Stage 1 only)* | `news` | false | N/A for Stage 2 | N/A |

### Recommended Immediate Next Pilot Adapter

**Recommendation: `wikimedia-cx-en-haw-published`**

Rationale:
- Already in fetch plan, endpoint verified
- CC BY-SA 4.0 license; clean rights
- `parallel-doc` alignment type — scaffold pattern same as statutes adapter
- Yield 1–3k pairs; small enough for fast pilot, large enough to validate doc-level alignment
- Unblocks `parallel-doc` → LaBSE scoring path for all remaining doc-level sources
- Pinned gate: Frank's `stats.mt < 0.5` cutoff — Linus to confirm before `--execute`

### Asks

- **Frank:** Redirect Ulukau-family discovery from Nupepa/newspapers to: (1) wehewehe.org full dictionary bilingual examples, (2) any hooilina.org / puke.ulukau.org text with English companion, (3) other Ulukau-hosted bilingual paired text. Report findings before fetching.
- **Frank:** Confirm `wikimedia-cx-en-haw-published` adapter ready for pilot. If yes, proceed to `--execute`.
- **Linus (self):** Pin `stats.mt < 0.5` cutoff for wikimedia-cx (or override) before `--execute`. Confirm HK statutes bilingual pair and cap.
- **Rusty:** Register-fit review on hooilina/puke.ulukau.org bilingual texts if Frank finds any.

---

## Decision: Frank — Stage 2 Ulukau-family focus (pivot from Nupepa) (2026-05-01)

**Owner:** Frank (Hawaiian Data Collector)  
**Date:** 2026-05-01  
**Status:** PROPOSAL — ranked candidates + 1 adapter-pilot pick

### Summary

Pivot Ulukau-family Stage 2 discovery off newspaper OCR. Newspapers (Nupepa.org, Kauakūkalahale, Kanihoa-tagged collections) are HAW-monolingual machine OCR with mixed human correction; they are a Stage 1 candidate at best, not Stage 2. They are already adequately captured by Wikipedia/FineWeb-2/Glot500 for Stage 1. **Keep the Veridian/Greenstone protocol notes for adapter pattern reuse; remove newspapers from Stage 2 sourcing rotation.**

Within the Ulukau family, four Stage 2-fit surfaces exist (one already in plan, three new). Ranking below.

### Ranked Stage 2 candidates (Ulukau family)

**1. Ka Hoʻoilina (`hooilina.org`)** ★★★★★ *(NEW, recommended pilot)*

- **Classification:** `parallel-doc` (per-section: original HAW ↔ modernized HAW ↔ English translation, all three versions human-curated and explicitly cross-referenced). Modernized-HAW × English is cleanest Stage 2 pair; original-HAW × English also valid (spelling-variant signal for Stage 1 dedup).
- **Extraction surface:** Greenstone CGI (`/cgi-bin/journal?a=...`) with same Veridian-family AJAX shape as Nupepa (`a=da&command=getSectionText`, `a=da&command=getDocumentContents`). Per-document HTML/XML body for text. Each text version is separate Greenstone document under one parent ID; `mana` (version) selector is in `e=` state token / `gg=text` parameter.
- **Expected yield:** ~O(low-thousands) of paragraph-level haw↔eng pairs after sentence segmentation; needs proper enumeration probe.
- **Rights / ToS:** Editorial intro page carries free-to-public-with-citation clause: reuse of modernized HAW or English requires citation of source HAW. Cover-page footer: `Kuleana kope © 2002-2004 na Nā Kula ʻo Kamehameha` (Kamehameha Schools holds editorial layer). Underlying 19c Hawaiian documents are public domain by age.
- **Open question for Linus:** Does citation requirement satisfy prototype-only posture, or do we need explicit Kamehameha Schools sign-off? Proposed: modernized-HAW and English-translation layers are creative work owned by KS; safer as prototype-only cap.
- **Why pilot first:** Highest parallel-pair density per Ulukau-domain document; structure explicitly designed for parallelism; reuses 80% of Veridian/Greenstone discovery work already mapped; large code reuse, low new risk.

**2. Wehewehe combined dictionary (`wehewehe.org`)** ★★★★

- **Classification:** `dictionary-example` for entry-level haw↔en pairs; some dictionaries include example sentences inside entries (worth probing) = `parallel-sentence` cap-counted.
- **Extraction surface:** Greenstone `hdict` CGI; query at `https://wehewehe.org/gsdl2.85/cgi-bin/hdict?a=q&q=<word>&l=haw` returns list of `D<id>` document IDs tagged with source dictionary and side language.
- **Expected yield:** PD-only subset (Andrews 1836, Andrews 1865, Emerson 1845, Hitchcock 1887, Parker 1922, Judd/Pukui/Stokes 1943) yields bulk of usable Stage 2 rows; modern dictionaries (Pukui-Elbert 1986, Māmaka Kaiao 2003, Combined 2020) are copyright-restricted.
- **Rights / ToS:** No site-wide ToS link; per-dictionary copyright implicit in publication date. **Linus to:** (a) walk dict landing page to confirm per-dict rights matrix, (b) draw PD line at pre-1925 US imprints, (c) decide Judd/Pukui/Stokes 1943 (US pre-1978 + post-1925 → renewal-status check needed).
- **Note:** `andrews-1865-en-haw-vocab-appendix` already in fetch plan as `dictionary-example`. Wehewehe access to Andrews 1865 is same source via different surface — adopt whichever extracts cleanest.

**3. Hawaiian Kingdom statutes** ★★★★ *(already in plan)*

- **Classification:** `parallel-doc` (long-form bilingual government text, official-translation register).
- **Status:** Already in `data-sources/stage2-parallel-fetch-plan.json` as `hawaiian-kingdom-statutes-bilingual`. Within Ulukau family reachable through `ahcchist` / `ahccreso` Greenstone collections.
- **Reuse note:** Same Greenstone surface as Hoʻoilina/Wehewehe. Hoʻoilina pilot adapter generalizes here.

**4. Nā Puke / Ulukau ebooks (`puke.ulukau.org`)** ★★

- **Classification:** mixed; per-book `ʻŌlelo` metadata field exposes language. Books tagged `ʻŌlelo Hawaiʻi` only = Stage 1 mono. **Bilingual subset** = `dictionary-example` or `parallel-doc` candidates.
- **Extraction surface:** custom `/ulukau-books/?a=d&d=EBOOK-<ID>` UI with rights tagging per-book (not always machine-readable — manual rights triage required, lower-yield-per-hour than top three).
- **Recommendation:** Defer until Hoʻoilina + Wehewehe-PD shipped; revisit only for `EBOOK-DHLLT` glossary + statutes companion volumes if Stage 2 row count still short.

**5. Baibala (`baibala.org`)** *(already in plan, Tier A)*

- `parallel-verse`, `bible-haw-baibala-pinned-edition` already pinned to 1839 edition, adapter live.

### Not Stage 2 fit (de-prioritize)

- **Nupepa.org + tagged-newspaper collections** — HAW-monolingual OCR, Stage 1 only, already covered by FineWeb-2 + Wiki.
- **Ka Waihona Mele** — songs; cultural hard-escalate per `docs/data-pipeline.md` §52.
- **Kaniʻāina** — audio/video; out of text scope.
- **Ka ʻOhina Kiʻi** — photographs; not text.
- **Algene** — genealogies; cultural hard-escalate.
- **HPN (Hawaiian Place Names)** — searchable index, not bilingual pairs; dictionary glossary at best.

### Recommended adapter-pilot pick

**Pilot: Ka Hoʻoilina (`hooilina.org`).**

**Why:**
1. Highest parallel-pair density per fetched document among Ulukau-family surfaces.
2. Reuses 80% of Veridian/Greenstone discovery already mapped. Same `getSectionText` / `getDocumentContents` AJAX endpoints work; only OID grammar and `e=` state suffix change.
3. Rights clearer than newspaper OCR: editorial layer copyright explicitly Kamehameha Schools 2002–2004; reuse clause published; underlying 19c documents PD by age.
4. Register diversity (HEN, gov't, newspapers, literary, student texts) — gives SFT mix more breadth than Bible-only or dictionary-only.
5. Pair is human translation (not OCR + alignment), so `alignment_method` is `manual` / `tmx-line` style, no LaBSE thresholding required for train side.

**Pre-pilot gates I will not bypass:**
- (a) Linus to rule on citation requirement → proposed adapter posture: `prototype_only=true`, `release_eligible=false`, cite Kamehameha Schools + Kalena Silva editorial in per-row provenance.
- (b) Linus to confirm modernized-HAW × English as primary pair and original-HAW × English as secondary for Stage 1 dedup.
- (c) Smoke fetch ONE document trio first, capture ToS snapshot from copyright page, propose adapter shape.

### Asks

- **Linus:** Rights/posture review on Hoʻoilina and Wehewehe per-dictionary PD cutoff.
- **Rusty:** Sanity-check whether Hoʻoilina "modernized HAW" spelling layer is right Hawaiian-side surface for Stage 2 (vs. original-HAW), given rest of our HAW data is modern-spelling.

### Anti-actions taken

- Did NOT treat Nupepa as Stage 2.
- Did NOT bulk-fetch any Hoʻoilina, Wehewehe, or Puke document. Only landing pages + editorial intro + one dictionary lookup + one books listing retrieved; all small, saved under `data/raw/ulukau-stage2-discovery/20260501/`.
- Did NOT read/persist cookies, localStorage, or auth headers.
- Did NOT modify `data-sources/stage2-parallel-fetch-plan.json` yet — Hoʻoilina goes in only after Linus rights review.
- Did NOT add tooling to `requirements.txt`.


---

## Decision: Frank — Pull Ulukau-family Raw (Round 4 SFT Candidates) (2026-05-01)

**Owner:** Frank (Hawaiian Data Collector)  
**Date:** 2026-05-01T23:05Z  
**Status:** PROPOSAL — raw pull complete; adapters + alignment infra needed for candidates

### Summary

All 6 Ulukau-family SFT candidates from `data/raw/ulukau-stage2-discovery/20260501/manifest.json` have been addressed. Output root: `data/raw/ulukau-family-sft-candidates/20260501/`.

### New raw downloads (~29.7 MB total)

| item_id | Title | Kind | Key assets |
|---|---|---|---|
| `hawaiianphrasebo00bishrich` | Hawaiian Phrase Book (1881) | full | djvu.txt 181KB, PDF 8MB, meta.xml, marc.xml |
| `constitutionand00hawagoog` | Constitution and Laws 1852 (EN) | full | djvu.txt 238KB, meta.xml (PDF 500, no marc on Google scan) |
| `gospelaccordingt00hawarich` | Gospel of John Parallel Columns (1854) | raw | djvu.txt 274KB, PDF 12.9MB, meta.xml, marc.xml |
| `63140380R.nlm.nih.gov` | Sanitary Instructions for Hawaiians (1881) | raw | djvu.txt 274KB, PDF 7.7MB, meta.xml |
| `HAWPDF_DBS_HS` | Diglot New Testament (1859) | inventory_only | ia_metadata.json only |

### Reused from HK statutes paired imprints dir (no large-file duplication)

| item_id | Files reused |
|---|---|
| `hekumukanawaiam00hawagoog` | 5 files (HAW 1852 Constitution) |
| `kanawaiikauiaek00ricogoog` | 5 files (HAW 1847 Statute Laws) |
| `statutelawshism00ricogoog` | 7 files (EN 1846/47 Statute Laws) |

Dedup check: **zero sha256 collisions** between new djvu.txt files and all existing raw roots.

### Current structured row counts (data/stage2/candidates/)

| Source | Rows |
|---|---|
| bible_haw1868_kjv.jsonl | 31,101 |
| andrews_1865_vocab.jsonl | 1,194 |
| hk_statutes_1897.jsonl | 1,103 |
| kaikki_wiktionary.jsonl | 292 |
| tatoeba.jsonl | 121 |
| hooilina.jsonl | 109 |
| bible.jsonl (smoke) | 5 |
| **TOTAL** | **33,925** |

### Pending actions by agent

**Linus (Data Engineer):**
1. Confirm 1852 Constitution pair is within legal register cap (≤15% combined legal tokens). HAW `hekumukanawaiam00hawagoog` + EN `constitutionand00hawagoog` are now both locally staged. Extending the HK statutes adapter (section-id alignment) is the path. Note: Google scan djvu.txt has some W→AV OCR substitutions on the HAW side — flag in adapter.
2. Year-range verification for 1847 HAW / 1846 EN pair. Does `statutelawshism00ricogoog` (EN, 1846) cover exactly the same laws as `kanawaiikauiaek00ricogoog` (HAW, 1847)? The EN item covers years 1845–1847 and may have broader coverage. Confirm pairing is valid before section-id alignment.
3. Gospel of John (1854) Bible cap accounting. `gospelaccordingt00hawarich` has ~880 verses (John only). This is a pre-Baibala edition (1854 vs 1839), so the HAW text may differ from our existing Baibala chapters. Confirm: (a) treat as distinct edition → separate dedup hash; (b) still counts against ≤30% Bible-token train cap as a class.
4. Build adapter for Hawaiian Phrase Book (1881). `scripts/325_build_phrase_book_candidates.py` (following naming convention). Approach: column-detection on djvu.txt; split lines on whitespace gap between EN and HAW columns; filter entries where HAW side < 3 chars. Estimated yield: 800–2,000 phrase pairs. No rights gate; PD clear.

**Rusty (Alignment Scorer):**
1. Sanitary Instructions (1881) paragraph alignment. `63140380R_djvu.txt` (274 KB) has EN volume first, HAW volume second (not interleaved). Two-phase: (1) Detect EN/HAW boundary; (2) Align chapters by number (deterministic); (3) LaBSE paragraph-level scoring ≥ 0.75 within chapters. Unique health/medical register — worth having once LaBSE infra is up.

**Frank (self / next session):**
1. Implement `325_build_phrase_book_candidates.py` — no blockers, highest-priority new adapter from this discovery round. Should land 800–2,000 rows quickly.
2. Probe Gospel of John djvu.txt OCR column quality. If parallel columns are cleanly separated in OCR output, verse-id extraction may be feasible without hOCR. Sample 10 verse pairs; report quality to Linus.

### Deferred (no action needed now)

- **Diglot NT (1859):** Inventory only. OCR blocked. hOCR column extraction is a significant engineering investment. Defer until after simpler sources ship.
- **1847 Statute Laws pair:** Inventory-only pending Linus year-range verification.

### Provenance

- Pull script: `scripts/_frank_pull_ulukau_family_sft.py`
- Manifest: `data/raw/ulukau-family-sft-candidates/20260501/manifest.jsonl`
- Summary: `data/raw/ulukau-family-sft-candidates/20260501/manifest_summary.json`
- Cleanup notes: `data/raw/ulukau-family-sft-candidates/20260501/CLEANUP_NOTES.json`
- Discovery source: `data/raw/ulukau-stage2-discovery/20260501/manifest.json`

---

## Decision: Linus — Clean Current Ulukau Candidates (2026-05-01)

**Owner:** Linus (Data Engineer)  
**Date:** 2026-05-01  
**Status:** EXECUTED — data policies and findings for team

### Summary

Completed candidate cleaning and dedup baseline for all currently-available Ulukau-family SFT candidate files. This produces a stable structured-row count that Frank can extend once remaining raw sources are pulled.

### Hoʻoilina Candidate Fix

**Problem (Basher-reported):**
- 41 rows containing only Greenstone site footer boilerplate ("Look up any word by double-clicking on it. Kuleana kope © 2002–2004…") instead of article content.
- 68 rows (all) with raw HTML numeric entities in text fields (`&#699;`, `&#257;`, `&#8216;`, etc.) — `html.unescape()` was never called.

**Root cause:** The prior ad-hoc generation extracted the full page body rather than the bounded `<table width=_pagewidth_>...<td>` content block. Empty sections had no `<p>` tags in the main block but the footer `<center>` block was captured as text.

**Fix (`scripts/324_build_hooilina_candidates.py`):**
- Regex-bounded extraction: stops at `</td></tr></table></center></span>` before the footer.
- `html.unescape()` on all text before NFC.
- ʻokina canonicalization (U+02BB) on HAW side after unescape.
- Skips pairs where either side is empty or has fewer than 5 words.
- Self-test: 19/19 assertions pass.

**Outcome:** 68 clean rows written (replaced prior 109-row file). 0 HTML entities, 0 boilerplate, 0 ʻokina mis-encodings.

**Policy flags preserved:**
- `alignment_review_required = True` (section-level parallel-doc, KS editorial + OCR noise)
- `prototype_only = True`, `release_eligible = False`
- `split = "review-pending"` — human alignment spot-check required before train promotion
- KS attribution clause: *"Ua noa i ka lehulehu akea… me ke koina nae"* — cite source HAW alongside any reuse of modernized-HAW or EN layer.

### HK Statutes 1897 Validation

- 1,103 rows: 0 schema violations, 0 sha256_pair hash mismatches, 0 internal dupes.
- All rows `split = "review-pending"` (OCR noise; `alignment_review_required = True`).
- **0 SFT train rows** until human review pass completed.
- Rights: PD (pre-1925 US imprint). No restriction on use.

### Bible 1868 × KJV Dedup Note

The `bible_haw1868_kjv.jsonl` candidate (31,101 rows, source `baibala-hemolele-1868`) overlaps with the existing manifest's `baibala-hemolele-1839` entries (10,221 verse keys). Cross-edition dedup policy: **preserve manifest rows (1839 edition) first; exclude 1868 rows whose verse key is already in the manifest.** This yields 20,852 unique new rows from the 1868 edition.

An additional 28 internal sha256_pair dupes within the 1868 candidate file are also excluded.

### Deduped Structured-Row Baseline

| Source | Structured Rows | Train-Ready (candidate split) | Notes |
|---|---|---|---|
| Existing manifest (all sources) | 11,828 | 4,665 train + 15 dev | Prepared; do not re-dedup |
| Bible 1868 (new unique) | 20,852 | 20,852 | After verse-key dedup vs manifest |
| Hoʻoilina (cleaned) | 68 | 0 | review-pending; needs alignment review |
| HK Statutes 1897 | 1,103 | 0 | review-pending; needs alignment review |
| **TOTAL** | **33,851** | **25,532** | |

**Policy-filtered SFT train rows (320 quality model):** ~358. The large gap from 25,532 → 358 is driven by the Bible 30%-cap policy and the 1839/1868 historical-orthography flags. This will increase once review-pending rows pass human review.

### Data Policy Proposals

1. **Hoʻoilina HTML parser convention:** Any Greenstone/Veridian section adapter must extract text only from the `<table width=_pagewidth_>...<td>` content block and call `html.unescape()` before NFC/hash. Add to SKILL.md adapter pattern notes.

2. **Candidate-level vs policy-filtered counts:** Reports must distinguish (a) "structured rows" (all deduped candidate rows regardless of split), (b) "candidate-level train rows" (rows with `split=train` in candidate files), and (c) "policy-accepted train rows" (320 quality-policy output). Mixing these creates confusion.

3. **Bible cross-edition dedup by verse key:** When two Bible editions share the same verse reference system, preserve the already-manifested edition's rows and exclude the new edition's matching verse keys rather than relying solely on sha256_pair dedup.

### Report Location

Full structured counts with methodology: `data/stage2/reports/ulukau_family_structured_counts_20260501.json`

Designed to be extended once Frank pulls remaining Ulukau-family raw sources (Wehewehe PD subset, HK statutes 1846/1850).

---

## Decision: Basher — Ulukau Batch Validation (2026-05-01)

**Filed:** 2026-05-01  
**Author:** Basher (Validation Engineer)  
**Scope:** Ka Hoʻoilina + HK Statutes 1897 candidate batch validation  

### Validated Files

| File | Rows | Status |
|---|---|---|
| `data/stage2/candidates/hooilina.jsonl` | 109 | ❌ FAIL — needs cleaning pass |
| `data/stage2/candidates/hk_statutes_1897.jsonl` | 1,103 | ⚠️ PASS with OCR warnings |

### Binding Validation Decisions

**1. Hooilina MUST NOT merge as-is**
- **29 rows are Greenstone UI footer boilerplate** (text_en == text_haw, the "double-click" copyright notice). All share one sha256_pair (`efbee0995becb2b4...`). Drop these before any manifest merge.
- **3 rows have misaligned boilerplate** (footer leaked onto one side of real pair — confirmed by extreme length ratio and text inspection). Drop these too.
- **HTML entities are unescaped** throughout all content rows (`&#699;`, `&#257;`, `&nbsp;`, `&amp;`, `&copy;`, etc.). A `html.unescape()` pass must precede NFC + sha256 computation. After fixing, all hashes will change — current hooilina.jsonl hashes are stale.
- **Net clean rows after fix:** ~77 candidate-quality translation pairs.
- **Recommendation:** Adapter re-emit required. Do not merge the current 109-row file into the canonical manifest.

**2. HK Statutes 1897 is merge-eligible as review-pending**
- Passes all structural checks (schema, hash invariant, dedup, text length).
- 970 of 1103 HAW text fields have `§→$` OCR artifact from djvu.txt. Fixable with targeted substitution + hash recompute. Does not block review-pending intake.
- 892 rows have hyphen-split line-break artifacts. Fixable. Does not block review-pending intake.
- **Zero collisions** with existing manifest or hooilina (pair_id and sha256_pair both clean).
- **Recommendation:** Include in next manifest build pass as review-pending. Flag OCR issues in quality_flags field during that pass.

**3. Total structured row count (authoritative)**

| State | Canonical Rows |
|---|---|
| Current manifest (live) | 11,828 |
| Deduped preview (bible_haw1868 + hooilina, all 109) | 32,817 |
| Deduped preview — clean (drop 29 boilerplate hooilina rows) | ~32,788 |
| + hk_statutes_1897 (not yet in any preview) | +1,103 |
| **Total if both sources cleaned + merged** | **~33,891 canonical structured rows** |
| SFT directional (train split, current preview) | 51,090 |

**Bible share:** 94.8% of current deduped pool (31,101 of 32,817). Hard non-Bible growth gate is binding — do not add more Bible until non-Bible sources grow.

**4. Deduped preview is slightly inflated**

The existing `stage2_manifest_deduped_safe_preview_20260501.jsonl` (32,817 rows) includes 29 hooilina boilerplate rows. Any row count citing 32,817 should be understood as containing ~29 invalid rows that must be cleaned before final SFT emission.

### Checklist for Next Merge Pass (Linus/Frank)

- [ ] Re-emit `hooilina.jsonl` with `html.unescape()` + boilerplate filter + hash recompute
- [ ] Verify re-emitted hooilina has 0 rows where text_en == text_haw
- [ ] Verify re-emitted hooilina has 0 rows matching Greenstone footer substring
- [ ] Run manifest build with re-emitted hooilina + hk_statutes_1897 as new candidates
- [ ] Apply §→$ normalization pass to hk_statutes text_haw before or during manifest build
- [ ] Enforce Bible ≤30% token cap in manifest build pass
- [ ] Enforce legal register ≤15% token cap for hk_statutes rows
- [ ] Validate new manifest with `320_build_stage2_manifest.py --check`
- [ ] Re-run Basher validation script on merged manifest before SFT emit

---

## Decision: Rusty — Stage 2 Review-Pending Promotion Policy (2026-05-02T00:25:04Z)

**Owner:** Rusty (NLP Researcher)  
**Date:** 2026-05-01  
**Status:** ACCEPTED — defines deterministic source-pinned promotion gate

### TL;DR

Deterministic, source-pinned promotion gate using existing `stage2_quality` flags plus orthography/OCR-aware filters. NOT claiming human Hawaiian line-by-line review.

### Source-by-source recommendations

1. **Andrews 1865 (1,194 rows):** **Stay rejected** — dictionary fragments (1–4 token pairs) teach glossary-style failure mode.
2. **Kaikki (292 rows; 153 accept, 139 review):** Promote narrow subset (both sides ≥3 tokens, 0.5 ≤ length_ratio ≤ 2.5, no nonhaw_letters/no_diacritics). Expected yield: ~30–50 of 139 review rows.
3. **Tatoeba (121 rows; 96 accept, 15 dev, 25 review):** Promote almost all review-pending (both sides ≥2 tokens). Expected yield: ~20 of 25. **Hard rule: dev frozen.**
4. **Hoʻoilina (68 candidates):** **Stay review-pending** pending sentence-level re-segmentation. If forced: ≤250 directional rows, prototype_only=True, never dev/test/release.
5. **HK Statutes 1897 (1,103 candidates):** Promote filtered subset (HAW tokens ∈ [25,600], 0.6 ≤ length_ratio ≤ 1.6, no nonhaw/$ markers). Expected yield: ~500–700.
6. **Bible 1839 (10,221 rows; 9,830 accept):** No change — 360 review rows have additional flags (real quality issues), stay quarantined.
7. **Bible 1868 × KJV (31,101 candidates):** Merge, then subsample under Bible token cap. Net new ≈20,765 after dedup.

### Acceptance/rejection criteria (all must pass)

1. `alignment_confidence_tier ∈ {accept}` OR matches documented source-pinned rule.
2. `alignment_review_required = false` UNLESS source-pinned exception with sub-cap.
3. Both sides ≥2 tokens (dict: ≥3), length_ratio in [0.5,2.5] (legal: [0.6,1.6]).
4. `haw_nonhaw_letters_high` NOT set.
5. `haw_no_diacritics` NOT set, EXCEPT existing 1839 Baibala carve-out.
6. Source not BLOCKED/INVENTORY-ONLY.
7. If `prototype_only=True`: release_eligible=False + sub-cap.

### Final recommended counting method (§4)

**Step 1:** Apply per-source promotion rules.  
**Step 2:** Compute non-Bible accepted-train tokens `T_nonbible`.  
**Step 3:** Bible token budget `T_bible_max = (0.30 / 0.70) × T_nonbible`.  
**Step 4:** Bible deterministic subsample (sha256_pair order, drop excess as "dropped-by-bible-cap-v1").  
**Step 5:** Legal sub-cap HK-1897 ≤ 0.15 × (T_nonbible + T_bible_kept).  
**Step 6:** Dictionary sub-cap Andrews+Kaikki ≤ 5,000 rows.  
**Step 7:** Synthetic sub-cap ≤ 15% directional.  
**Step 8:** Hoʻoilina sub-cap ≤ 250 directional (default 0).  
**Step 9:** Emit score_summary.json.  
**Step 10:** Re-run eval gate leakage check.

Expected order-of-magnitude: ~7,300–10,000 parallel pairs (~14,600–20,000 directional). NLLB mined + synthetic BT still required to hit 80k.

### Risks mitigated

1. **OCR noise:** nonhaw_letter_share ≤10% + section-marker regex.
2. **Dictionary fragments:** ≥3-token floor for dict + ≤5k combined cap.
3. **Unaligned legal:** section-id alignment + tight ratio + nonhaw filter.
4. **Bible dominance:** deterministic subsample ≤30% of train tokens.
5. **Dev/test leakage:** Tatoeba dev frozen (15 rows), eval-gate fixtures locked.

### Hand-off

- **Linus:** manifest builder (steps 1,4,5) + score_summary.json
- **Basher:** eval gate re-run post-promotion
- **Frank:** unblocked for next raw pulls
- **Coordinator:** compare gate to Linus's implementation

---

## Decision: Linus — Stage 2 Review-Pending Completion Pass (2026-05-02T00:25:04Z)

**Owner:** Linus (Data Engineer)  
**Date:** 2026-05-01  
**Status:** REJECTED — policy violations + cap misapplication

### What Was Done

Full automated machine/data review pass over every Stage 2 review-pending row.

- **Manifest:** `data/stage2/reviewed_stage2_manifest.jsonl` (33,425 rows)
- **Report:** `data/stage2/reports/stage2_review_pass_20260501.json`
- **Script:** `scripts/331_stage2_review_pass.py`
- **Train rows:** 26,118 (Bible 91.9% of train)
- **Directional SFT:** 52,236 rows

### Policy Decisions

1. **Dictionary-example relaxed:** min_tokens=1, length_ratio_max=5.0 → promoted 969 Andrews rows.
2. **Tatoeba short-sentence:** min_tokens=2 for manual alignment → promoted 16 rows.
3. **HK 1897 historical-orthography override:** rows with ONLY haw_no_diacritics promoted → 757 rows.
4. **Bible 1868 source_url_missing waiver:** source documented, waive flag for hist_orth override.
5. **Bible 30% cap hardened:** 24,000 rows cap (=30% of 80k target), currently 91.9% of 26,118 train.

### Issues Raised

1. **Bible cap misapplied:** treated as 30% of 80k target, not 30% of actual parallel-train token share.
2. **Bible left at 91.9% of train rows** — hard cap violation per Rusty §4.
3. **Andrews 1865 promoted (969 rows)** — violates Rusty §1.1; should stay rejected.
4. **Hoʻoilina promoted and placed in dev** — violates Rusty §1.4; no promoted review rows in dev/test.

### Status

**REJECTED by Coordinator.** Superseded by Basher's corrected artifact.

---

## Decision: Basher — Stage 2 Review Pass Cap Correction (2026-05-02T00:25:04Z)

**Owner:** Basher (Training Engineer)  
**Date:** 2026-05-02  
**Status:** REJECTED — cap math drift

### What Was Done

Applied Rusty's review gate as sole source of truth; corrected Bible/HK cap enforcement.

### Algorithm Applied (per Rusty §4)

- T_nonbible = all non-Bible accepted train tokens (pre-HK-cap)
- T_bible_max = (0.30/0.70) × T_nonbible
- Bible pool = 1839-train ∪ 1868-net-new-after-dedup; sorted by sha256_pair
- Bible subsampled until T_bible_max; excess → "dropped-by-bible-cap-v1"
- HK cap = 0.15 × (T_nonbible + T_bible_kept)

### Corrected Artifact

- **Manifest:** `data/stage2/reviewed_stage2_manifest_cap_corrected.jsonl` (33,851 rows)
- **Report:** `data/stage2/reports/stage2_review_pass_cap_corrected_20260501.json`
- **Script:** `scripts/332_build_reviewed_manifest_cap_corrected.py`
- **Train rows:** 1,627
- **Directional SFT:** 3,254 rows

### Cap Verification

Against reference denominator `T_nonbible_total + T_bible_kept = 228,264`:
- Bible: 68,478 / 228,264 = **30.0% ✓**
- HK: 34,218 / 228,264 = **15.0% ✓**

### Issues Raised

Cap math self-consistent against reference denominator, but **artifact violates the cap**:
- Bible: 68,478 tokens / 105,646 final = **64.8%** ✗
- HK: 34,218 tokens / 105,646 final = **32.4%** ✗

**Root cause:** HK cap computed against pre-cap denominator; HK reduction shrunk the denominator after the fact, causing drift.

### Status

**REJECTED by Coordinator.** Superseded by Danny's fixed-point solution.

---

## Decision: Danny — Stage 2 Review Pass Final Cap Solution (2026-05-02T00:25:04Z)

**Owner:** Danny (Lead/Architect)  
**Date:** 2026-05-02  
**Status:** ACCEPTED — final corrected artifact (canonical source of truth)

### The Fix

Caps enforced against **final artifact tokens**, not stale pre-cap reference denominators.

### Closed-Form Math

Let N = non-Bible non-HK train tokens, H = HK train tokens, B = Bible train tokens, T = N + H + B.

Constraints:
- B/T ≤ 0.30 ⇔ B ≤ (3/7)(N + H)
- H/T ≤ 0.15 ⇔ H ≤ (3/17)(N + B)

Solving simultaneous binding case:
- **H_max = 3N/11**
- **B_max = 6N/11**
- **T = 20N/11**
- **B/T = 30% (exact)**
- **H/T = 15% (exact)**

Pools sorted by sha256_pair ascending, selected greedily up to target. After selection, shares recomputed from artifact; tail dropped one row at a time until both caps hold.

### Final Canonical Counts

| Source | Train | Dev | Review-Pending | Total |
|---|---:|---:|---:|---:|
| baibala-hemolele-1839 | 5 | 0 | 10,216 | 10,221 |
| baibala-hemolele-1868 | 25 | 0 | 20,827 | 20,852 |
| hk_statutes_1897 | 5 | 0 | 1,098 | 1,103 |
| kaikki-haw-en-wiktionary | 153 | 0 | 139 | 292 |
| tatoeba | 97 | 15 | 9 | 121 |
| andrews-1865-en-haw-vocab-appendix | 0 | 0 | 1,194 | 1,194 |
| hooilina | 0 | 0 | 68 | 68 |
| **TOTAL** | **285** | **15** | **33,551** | **33,851** |

- **Directional SFT rows (2× train, emitter-verified):** **570**
- **Bible token share:** **29.92%** ✓ ≤30%
- **HK token share:** **14.59%** ✓ ≤15%
- **Total train tokens:** 5,317 (Bible 1,591 / HK 776 / Kaikki+Tatoeba 2,950)
- **Canonical stage2_manifest.jsonl:** unchanged

### Rejected Predecessors

- **Linus (26,118 train / 52,236 directional):** Bible 91.9% of train. Promoted Andrews + Hoʻoilina; placed promoted rows in dev. Hard violations of Rusty §1.1, §1.4, dev-freeze rule.
- **Basher (1,627 train / 3,254 directional):** Cap math self-consistent against `(T_nonbible_total + T_bible_kept)`, but artifact shows Bible 64.8% / HK 32.4% of actual tokens. Computed Bible cap before applying HK cap; HK reduction shrank denominator post-fact.

### Artifacts

- **Manifest (canonical):** `data/stage2/reviewed_stage2_manifest_final_capped.jsonl` (33,851 rows)
- **Report:** `data/stage2/reports/stage2_review_pass_final_capped_20260501.json`
- **Builder:** `scripts/333_build_reviewed_manifest_final_capped.py`
- **SFT JSONL (verification):** `data/stage2/stage2_sft_final_capped.jsonl` (570 rows)

### Hand-off

- **Linus:** New source-of-truth manifest for all downstream work. Drop prior reviewed artifacts.
- **Basher:** Re-run Stage 2 eval gate. Confirm leakage check passes + ʻokina/kahakō tripwire green on frozen Tatoeba dev.
- **Frank:** Unblocked for NLLB-mined + synthetic BT. 285-pair set honestly small; 80k target requires additional non-Bible sources (per Rusty §4).
- **SFT emitter:** Use `--allow-review-required` for HK rows whose `alignment_review_required=true` is overridden by `hk1897-legal-clean-v1` promotion rule.

### Cost vs. Benefit

**Cost:** With current data, 285 pairs / 570 directional SFT rows is small.

**Benefit:** Honest. Linus's 26,118 is fiction; Basher's 1,627 satisfies a cap that the artifact violates. This number holds.

---

## Decision: Frank — NLLB-Mined haw↔eng is endpoint-invalid (2026-05-02)

**Owner:** Frank (Hawaiian Data Collector)  
**Date:** 2026-05-02  
**Status:** Verified — closes Stage 2 gap-closer bucket

### Finding

The allenai/nllb-200 mined release contains **no Hawaiian language pairs**. Its lang-pair table enumerates 188 codes; none is `haw_Latn`. Two `h*_Latn` codes exist (`hat_Latn` / Haitian Creole, `hau_Latn` / Hausa) but must **never be substituted** for Hawaiian.

### Decision

- **Endpoint status:** `endpoint_invalid_no_haw_coverage`
- **Expected yield:** 0 (was 8–15k in Stage 2 plan)
- **Artifact update:** `data-sources/stage2-parallel-fetch-plan.json` marked `verification_status=endpoint_invalid_no_haw_coverage`, `adapter_status=blocked_endpoint_invalid`

### Impact on Stage 2 Yield Math

The 8–15k pairs from NLLB-mined was the single largest gap-closer in the 80k Stage 2 target. **That bucket is now empty.**

- **Honest ceiling without NLLB:** ~50–60k directional rows per existing honest-prognosis text (Linus + Rusty, both prior).
- **80k target status:** No longer justified without replacement mined source authorization.

### Evidence

- `data/raw/nllb-mined-haw-eng/20260502/endpoint_proof.json` — probe artifact with sha256 of every captured file
- `data/raw/nllb-mined-haw-eng/20260502/{README.md, nllb.py, nllb_lang_pairs.py}` — upstream loader bytes
- `data-sources/nllb-mined-haw-eng/probe.py` — rerunnable, polite, stdlib-only probe
- `datasets-server /rows` returns HTTP 404 for `haw_Latn-eng_Latn` and `eng_Latn-haw_Latn`

### Next Steps (awaiting Coordinator direction)

1. **Stage 2 yield renegotiation:** ~50–60k target vs. relaxed thresholds (not recommended).
2. **Replacement mined sources** (require discovery + fresh rights review):
   - MADLAD-400 sentence-pivot subsets
   - HPLT v2 bilingual pivots
   - OPUS mined collections with explicit `haw_Latn` support
3. **Rights rule reminder:** Never alias `hau_Latn`/`hat_Latn` to Hawaiian.

### Asks

- **Linus:** if pivoting to MADLAD-400 / HPLT v2 / OPUS-mined, fresh rights review needed (per-row origin posture differs from NLLB).
- **Rusty:** LaBSE 0.80 floor remains valid for remaining sources; `321_score_stage2_alignment.py` unblocked (no NLLB rows to score).

---

## Decision: Linus — Wikimedia CX en→haw Candidates Processed (2026-05-02)

**Owner:** Linus (Stage 2 Rights and Alignment)  
**Date:** 2026-05-01  
**Status:** For-the-record — no train-ready rows; all blocked by rights + alignment gates

### Output

- **File:** `data/stage2/candidates/wikimedia_cx_en_haw.jsonl`
- **Row count:** 14 (all review-pending)
- **Train-ready added:** 0
- **Manifest update:** NOT included in `stage2_manifest.jsonl`

### Key Decisions

**1. Alignment strategy: lead-only for CX stubs**
- Only 1 of 13 valid articles had exact paragraph matching (n_en_paras == n_haw_paras).
- CX-translated HAW articles are almost universally stubs (lead paragraph only).
- **Rule:** Positional alignment only when n_en_paras == n_haw_paras exactly. Lead-only for all others.
- **Rationale:** Honest. Never fabricate alignment for untranslated content.

**2. All CX rows are review-pending, prototype-only**
- Wikipedia content is CC BY-SA 4.0 / GFDL — not public domain.
- **Set on all 14 rows:** `prototype_only=True`, `release_eligible=False`, `split="review-pending"`, `alignment_review_required=True`
- **Train-ready rows added:** 0

**3. nosuchrevid HAW revisions are skipped, not faked**
- 7 HAW revisions return `nosuchrevid` (pinned targetRevisionId deleted on haw.wikipedia.org).
- **Skipped translationIds:** 2064967, 2088758, 2100548, 2128336, 2142723, 3259133, 542994 (also 654538: both sides error)
- Never substitute current revision without re-checking CX alignment.

### Blockers for Future Promotion

1. **Rights gate:** CC BY-SA encyclopedic content requires explicit policy clearance for train promotion.
2. **Alignment review:** `alignment_review_required=True`; needs human spot-check.
3. **nosuchrevid** (7 articles): recoverable only by fetching current HAW article + re-aligning.

### Artifacts

- `data/stage2/candidates/wikimedia_cx_en_haw.jsonl` — ready for future review pass when policy settled.
- No impact on `stage2_manifest.jsonl` or existing train-ready counts.
# Decision: wiki-haw-en-langlinks landed as raw-probe only; not counted toward Stage-2 N

**Author:** Frank (Hawaiian Data Collector)
**Date:** 2026-05-02
**Lane:** Stage-2 priority #3 (after NLLB closed, parallel with Linus's CX lane)

## What I decided

Land the Wikipedia haw↔en langlinks lane as a **raw-probe + provenance ledger only**. Do **not** emit `data/stage2/candidates/wiki_haw_en_langlinks.jsonl`. Do **not** modify `data/stage2/stage2_manifest.jsonl` or any final-capped artifact. Stage-2 N stays at 603 canonical / 1,206 directional.

## Why

The fetch plan declares `alignment_method=labse` for this source because it produces *comparable*, not parallel, docs. LaBSE/LASER is not wired into this repo yet. Emitting candidate rows in this state would require either:

1. Faking an alignment score (forbidden by Stage-2 quality rules and my charter).
2. Setting `alignment_method=null` + `alignment_review_required=true` for unscored doc-level pairs that haven't been sentence-segmented (would dilute the alignment-review queue with 1000s of rows that nobody can review without a tool, and silently inflate N).

Neither is honest. Capturing raw provenance now means the next agent who lands a LaBSE pass can pull from a fully-sha256'd, revision-pinned manifest without re-fetching anything.

## What I shipped

- `data-sources/wiki-haw-en-langlinks/probe.py` — stdlib-only, polite (≤1 req/sec, `maxlag=5`), three-mode CLI (`--self-test`, `--dry-run`, `--execute`).
- `data-sources/wiki-haw-en-langlinks/README.md`.
- `data/raw/wiki-haw-en-langlinks/20260502/` — ToS snapshot, batched API JSON with sha256s, `langlinks_manifest.jsonl`, `probe_summary.json`.
- `data/stage2/reports/wiki_haw_en_langlinks_probe_report.json`.
- `data-sources/stage2-parallel-fetch-plan.json` — `adapter_status` → `raw_probe_landed_blocked_on_labse` + `raw_probe` block.

Smoke set: 60 mainspace hawwiki titles → 53 langlink pairs with full revision IDs on both sides. Zero CX overlap in the smoke set; expect overlap at full scale on popular articles.

## What this means for the team

- **Linus:** my probe writes only under `data/raw/wiki-haw-en-langlinks/`. I did not touch `data/raw/wikimedia-cx-en-haw-published/` or the CX candidates JSONL. Your CX lane is the stricter, human-translation-attested subset; when alignment lands, langlinks must cluster-isolate against your manifest before counting rows. The probe records `dedup_cluster_id_seed = wiki-haw-en-langlinks::<haw_pageid>::<en_pageid>` at fetch time so the dedup is a join, not a re-crawl.
- **Rusty:** when you confirm the LaBSE threshold for the Tier-B pipeline, this lane is ready to feed in. The honest yield projection from the plan is 3–5k *before* a LaBSE-≥0.75 cut; expect well under that after threshold + length-ratio + LID + CX dedup.
- **Coordinator:** Stage-2 N is unchanged. NLLB lane (priority #1) is closed at 0; CX lane (priority #2, Linus) is in progress; Wikipedia langlinks (priority #3) is now raw-probe-landed. Honest ceiling without a LaBSE pass remains ~50–60k directional rows against the 80k target.

## Asks

- **Linus, when you have cycles:** rights-review sign-off on CC BY-SA 4.0 / GFDL attribution carry-through to derivative artifacts (per-revision URLs are intrinsic; the question is whether downstream training rows must include them or whether dataset-card-level attribution suffices).
- **Whoever owns 320-phase alignment next:** the probe manifest at `data/raw/wiki-haw-en-langlinks/<YYYYMMDD>/langlinks_manifest.jsonl` is the canonical input. Do not re-crawl titles/revisions; pull article bodies by `haw_revid` / `en_revid` only.

## Reversal cost

Cheap. The probe is additive — re-running with `--execute` produces a new dated subdir and never overwrites the manifest. Removing the lane is `rm -r data/raw/wiki-haw-en-langlinks/` + revert the fetch-plan diff.
