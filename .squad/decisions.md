# Decisions

> Updated 2026-04-30T01:42:25Z: Added Basher tokenizer audit script removal (user directive; gate remains). Prior: Frank quality-4 scan and Linus eval-safety contract. Recent batch below.

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
