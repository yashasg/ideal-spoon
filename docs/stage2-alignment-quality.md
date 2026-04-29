# Stage 2 Alignment Scoring & Quality-Filter Policy

> **Status:** Prototype-scoped policy (private/learning project). Issue #12.
> Owner: Rusty (NLP). Consumers: Linus' Stage-2 manifest builder (#11),
> Basher's bidirectional SFT JSONL emitter (#14).
>
> Generated/raw data stays local under `data/` (gitignored). This doc and
> the supporting code (`code/llm_hawaii/stage2_quality.py`,
> `scripts/321_score_stage2_alignment.py`) are the only things in-repo.

This is the contract for turning a *candidate* en↔haw pair into a manifest
row that the trainer can trust. It complements
[`docs/data-pipeline.md`](./data-pipeline.md) §"Stage 2 transformation
pipeline" / "Stage 2 manifest schema" — the schema fields named there
remain authoritative; this document fills in their *semantics* and the
*reject / review / accept* tiering.

## 1. What the policy decides

For each candidate pair the policy outputs:

| Field | Type | Notes |
|---|---|---|
| `alignment_confidence_tier` | enum | `accept` \| `review` \| `reject` |
| `alignment_review_required` | bool | true when tier ∈ {review, reject} (kept for compatibility with `data-pipeline.md` schema) |
| `quality_flags` | list[str] | machine tokens, stable vocabulary (see §4) |
| `manual_review_reasons` | list[str] | human-readable strings, 1:1 with `quality_flags` |
| `alignment_score_components` | object | per-rule breakdown for debuggability |
| `policy_version` | string | `stage2-quality-v0.1` (bumped on rule changes) |

Plus pass-throughs / re-computations of existing manifest fields:
`alignment_type`, `alignment_method`, `alignment_model`, `alignment_score`,
`length_ratio_haw_over_en`.

## 2. Inputs

The scorer consumes a candidate pair dict with at minimum:

- `text_haw`, `text_en` — the two sides, post-normalization (NFC, ʻokina
  canonicalized to U+02BB per Stage 1 normalizer).
- `alignment_type` ∈ `{parallel-verse, parallel-sentence, parallel-doc,
  comparable-aligned, dictionary-example, synthetic-bt, synthetic-ft}`.
- `alignment_method` ∈ `{verse-id, tmx-line, filename-pair, manual,
  laser, labse}`.

Optional but consulted when present: `alignment_score`, `alignment_model`,
`lang_id_haw`, `lang_id_haw_confidence`, `lang_id_en`,
`lang_id_en_confidence`, `source_url_en`, `source_url_haw`, `synthetic`.

## 3. Tiering rules

Two parallel signals are combined: **score-tier** (driven by
`alignment_method`) and **content-tier** (driven by the orthography,
LID, and structural checks below). The final tier is the *worst of the
two*, with hard flags forcing `reject` regardless.

### 3.1 Score-tier

| `alignment_method` | Score-tier rule |
|---|---|
| `verse-id`, `tmx-line`, `filename-pair`, `manual` | Trust the key. Score-tier = `accept`; `alignment_score` is null by design. |
| `labse`, `laser` | Score-tier driven by `alignment_score`: ≥ `accept_min` → accept; ∈ [`review_min`, `accept_min`) → review; < `review_min` → reject. Missing score → review (never silently accept). |
| Anything else | Unknown method; flag and force `review`. |

Defaults (overridable via `PolicyConfig`):

- `accept_min = 0.75` — per `docs/data-pipeline.md` §"Stage 2 transformation pipeline".
- `review_min = 0.55`.

### 3.2 Content-tier

`accept` if no soft flags fire; otherwise `review`. Hard flags force
`reject` regardless of score-tier.

**Hard flags** (force `reject`):

- `empty_side` — one side empty after normalization.
- `duplicate_pair_text` — both sides identical text.
- `side_too_short` — at least one side below `min_tokens_per_side` (default 3).
- `alignment_score_below_review` — embedding score < `review_min`.
- `alignment_type_unknown`, `alignment_method_unknown`.

**Soft flags** (force `review`):

- Length: `side_too_long` (>256 tokens), `length_ratio_extreme`
  (Hawaiian/English ratio outside [0.5, 2.5]).
- Hawaiian orthography:
  - `haw_no_diacritics` — Hawaiian side ≥60 letters yet zero ʻokina and zero kahakō. Almost always means OCR drift, ASR transcript, or mis-tagging.
  - `haw_okina_misencoding` — U+2018 / U+2019 / U+02BC / U+0060 / ASCII apostrophe found on the Hawaiian side. Stage-1's normalizer should have canonicalized these to U+02BB; presence here means either the row bypassed normalization or the candidate originates from a source that normalizes Hawaiian as English.
  - `haw_nfc_drift` — Hawaiian text is not in NFC.
  - `haw_nonhaw_letters_high` — share of non-Hawaiian-alphabet letters above `nonhaw_letter_share_max` (default 10%). Catches mixed/foreign content masquerading as Hawaiian.
- Language ID: `lid_haw_low`, `lid_en_low`, `lid_haw_wrong_label`,
  `lid_en_wrong_label` — when LID fields are present and disagree with
  the configured floors / expected labels.
- Alignment-score: `alignment_score_below_accept`,
  `alignment_score_missing`.
- Provenance: `source_url_missing` — non-synthetic pair lacking source
  URLs on both sides.
- Synthetic accounting: `synthetic_uncapped` — informational; the cap
  (≤25% of Stage-2 train tokens, 0% dev/test, per `data-pipeline.md`)
  is enforced at *manifest assembly* time, not per-row.

## 4. Quality-flag vocabulary

The string tokens in `quality_flags` are a **stable contract**. Add by
extending; do not rename. Renames force a `POLICY_VERSION` bump and a
manifest re-write. The full set lives in
`code/llm_hawaii/stage2_quality.py::QUALITY_FLAGS` and is mirrored in
`policy_summary()` for run-report logging.

## 5. Manual-review workflow

Pairs in tier `review` land in the manifest with
`alignment_review_required=true` and `split="review-pending"` (per the
`data-pipeline.md` Stage 2 schema). They are **never silently trained
on**. Resolution paths:

1. **Tighten** — adjust thresholds, re-run the scorer (cheap; per-row
   inputs are already on the manifest), flip tier on the same row.
2. **Hand-fix** — a Hawaiian-speaking reviewer corrects the source
   text, sets `alignment_method="manual"`, and the next pass promotes
   to `accept`.
3. **Drop** — set `split="held-out"` (kept for diagnostics) or remove
   from training selection. Do not delete from the manifest; the
   provenance row is the audit trail.

`reject` rows stay in the manifest for accounting and contamination
ledgers; they are never selected by the SFT emitter.

## 6. Hawaiian orthography caveats (notes for reviewers)

- **ʻokina is U+02BB**, not U+2018, U+2019, U+02BC, U+0060, or ASCII `'`.
  Stage 1's normalizer (`scripts/301_build_stage1_dataset.py::normalize_hawaiian`)
  canonicalizes these between Latin letters; Stage 2 candidates from
  *external* sources frequently have not been through that pass. The
  `haw_okina_misencoding` flag exists exactly for that case.
- **Kahakō are precomposed (NFC)** — `ā` is U+0101, not `a` + U+0304.
  Mixing NFC/NFD silently corrupts training. Enforced via the
  `haw_nfc_drift` flag.
- **No diacritics ≠ acceptable Hawaiian.** Some 19th-century nūpepa and
  many web sources omit ʻokina/kahakō entirely. This is *signal lost*,
  not *valid alternate orthography*. The `haw_no_diacritics` flag fires
  on long-enough Hawaiian text with zero markers; reviewers decide
  whether to keep (with a note) or drop, but the trainer must not
  default-accept silently.
- **English-side ʻokina on Hawaiian proper nouns is fine**
  (e.g., "Hawaiʻi" in an English sentence). The flag only inspects the
  Hawaiian side.

## 7. Compatibility with Linus (#11) and Basher (#14)

If Linus' manifest builder or Basher's SFT emitter land later, this
field vocabulary is the stable surface they should target:

- **Manifest builder (#11):** call `score_pair()` per candidate, merge
  the returned dict into the manifest row. The fields named in
  `data-pipeline.md` §"Stage 2 manifest schema" are preserved verbatim;
  policy additions (`alignment_confidence_tier`,
  `alignment_score_components`, `quality_flags`,
  `manual_review_reasons`, `policy_version`) extend that schema and do
  not collide with any existing column.
- **SFT emitter (#14):** select only rows with
  `alignment_confidence_tier == "accept"` and
  `split == "train"`. Pass `alignment_type`, `register`, `synthetic`,
  `prototype_only`, and `release_eligible` through to the JSONL example
  as documented in `data-pipeline.md` §"Stage 2 output JSONL".
  `quality_flags` and `manual_review_reasons` stay on the *manifest*,
  not the JSONL.

If either component's design lands and disagrees with this vocabulary,
that's a coordination point — bump `POLICY_VERSION` and update §3 / §4
in lockstep.

## 8. Non-goals

- **Not a release filter.** Release/cultural review remain a separate
  step per `eval_pipeline.md` §9.
- **Not an LID classifier.** LID confidence is consumed when present
  (e.g., from a future GlotLID pass); this module never runs a model.
- **Not an alignment engine.** Embedding cosines (LaBSE/LASER) come from
  upstream tools; this module persists the score and gates on it.
- **Not a contamination guard.** That's issue #4 (training-loader
  guard) and the `eval_hashes.jsonl` ledger.

## 9. References

- [`docs/data-pipeline.md`](./data-pipeline.md) — Stage 2 schema, source tiers, transformation pipeline.
- [`docs/eval_pipeline.md`](./eval_pipeline.md) — orthography-survival metrics that pair with these flags downstream.
- `code/llm_hawaii/stage2_quality.py` — the scoring module.
- `scripts/321_score_stage2_alignment.py` — CLI front-end + self-test.
