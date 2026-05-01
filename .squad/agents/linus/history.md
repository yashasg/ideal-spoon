# Linus — History

## 2026-04-30 — human_fetch bidirectional translation probe

**User directive:** Use `human_fetch.jsonl` / `human_fetch.txt` as the trusted local parallel source for checkpoint evals — every checkpoint (including Stage 0 no-training baseline) should run English→Hawaiian and Hawaiian→English translation so we can gauge baseline and drift.

**Implementation summary:**

- **`scripts/_convert_ulukau_human_fetch.py`** — Fixed stale `source_path` field (`.md` → `.txt`) by centralising it in `SOURCE_PATH_FIELD`; updated policy to `eval_eligible: True`, `training_eligible: False`, `translation_probe_eligible: True`; regenerated `data/tokenizer_audit/ulukau_nupepa/human_fetch.jsonl`.

- **`code/llm_hawaii/evaluate.py`** — Added `DEFAULT_HUMAN_FETCH_JSONL`, `HUMAN_FETCH_PROBE_SCHEMA`, `HUMAN_FETCH_EN_TO_HAW_TEMPLATE`, `HUMAN_FETCH_HAW_TO_EN_TEMPLATE` constants; `_char_ngram_f1()` pure-Python baseline char-bigram F1 (no new deps); `human_fetch_translation_probe()` that reads the JSONL, validates the en+haw pair, runs greedy generation for both en→haw and haw→en, and returns hash-only summary with numeric metrics (never raw text). Wired into `evaluate_checkpoint()` as `report["human_fetch_translation"]` on every call. Added `--human-fetch-jsonl` / `--no-human-fetch` CLI flags.

- **`scripts/run_stage0_eval.sh`** — Added `HUMAN_FETCH_JSONL` / `USE_HUMAN_FETCH` env vars; threaded through to Python argv; added `metrics.human_fetch_translation` to the tracked summary projection (hash-only).

- **Tests** — 23 new tests in `TestCharNgramF1` and `TestHumanFetchTranslationProbe` covering: missing source, valid two-row pair, bidirectional directions, hash-only fields, no raw text, policy, mock-model evaluated path, separate direction scores, CLI wiring, and Stage 0 report includes probe.

- **Docs** — Updated `code/README.md`, `docs/eval_pipeline.md` §8.1, `data-sources/manual-eval/README.md`.

**Key patterns established:**
- "Safe to miss" probe: missing JSONL → `status="missing"`, eval continues.
- Directions always separate: en→haw ≠ haw→en, never averaged.
- `audit_only` in converter policy is not the same as `eval_eligible`; they are orthogonal.
- Template strings are hashed and included in the descriptor so cross-checkpoint comparators can detect template drift.

**Validation:** ✅ py_compile clean, ✅ sh -n clean, ✅ 73/73 tests green (+23 new), ✅ git diff --check clean.

---

## Learnings

- **Stage 2 Tatoeba adapter (issue #17):** `alignment_method="manual"` is the correct schema value for Tatoeba (human-curated links, deterministic). `"tmx-line"` would be inaccurate. `register="unknown"` is correct for Tatoeba mixed-domain content; `"educational"` would misrepresent many pairs.
- **Stage 2 adapter pattern:** Adapters should produce candidates JSONL under `data/stage2/candidates/` with all computable manifest fields pre-populated (hashes, ratios, lang_id, etc.), so `320_build_stage2_manifest.py --check` can validate schema compliance before the manifest builder wires them in.
- **Tatoeba eng_sentences streaming:** `eng_sentences_detailed.tsv.bz2` is large. Stream through it keeping only IDs needed from the links table. Early-exit once all needed IDs are found.
- **Adapter self-test pattern:** Include a `--self-test` flag that runs in-memory against synthetic string fixtures (no network, no disk). This lets tests invoke the adapter's core logic without requiring file system fixtures.
- **Key paths:** `data-sources/tatoeba/fetch.py`, `data-sources/tatoeba/PINNED_DUMP.json`, `code/tests/test_tatoeba_adapter.py`, `code/tests/fixtures/tatoeba/*.tsv`.
- **Validation (issue #17):** ✅ py_compile clean, ✅ 41/41 tests green, ✅ manifest schema validation passes, ✅ self-test exits 0.

- When a JSONL converter has a hard-coded path string that can drift from reality (e.g., file renamed `.md` → `.txt`), centralise it as a named constant at the top of the file. This makes regeneration idempotent.
- `eval_eligible` and `audit_only` are independent policy dimensions; a tokenizer audit candidate can also be eval-eligible for a specific probe without being general training data.
- For a "safe to miss" probe pattern: check file existence first, return early with `status="missing"`, never raise. The eval framework tolerates this — only `status="invalid"` on W1 triggers an exit code change.
- Pure-Python char-bigram F1 is a reasonable baseline string-overlap drift signal when no sacrebleu/nltk is available. Document it explicitly as a *baseline character-F score* so consumers don't mistake it for a production chrF metric.
- For tests involving callable mocks on module-level functions (like `sample_generations`), `unittest.mock.patch("llm_hawaii.evaluate.sample_generations")` is the right pattern — patch the name as used in the module under test.

- **Baibala Hemolele URL structure (issue #16):** baibala.org runs Greenstone Digital Library software. The 1839 edition is accessed via `d=NULL.{group}.{book}.{chapter}` Greenstone OIDs, NOT simple `?e=BAI1839&b={book}&c={chapter}`. The outer frameset peels back 3 layers before reaching the actual text page (use `a=d` + `d2=1` directly on the innermost e= string). Verse anchors are `<a name="a{bookname_lower}-{chapter}-{verse}"></a>`. All 66 OIDs are now in `source_registry.json books[].greenstone_oid`.
- **Baibala rights:** 1839 imprint is US public domain. Site copyright (PIDF 2003-2008) covers digitization only; the text is unencumbered. No scraping prohibition found as of 2026-05-01.
- **URL template upgrades:** When a new URL template introduces a per-book variable (like `greenstone_oid`), update BOTH the fetcher (`render_url`) AND the candidate builder (`build_rows_for_chapter`) to pass the new keyword. Both call `template.format(...)` and will raise `KeyError` if the new placeholder is not supplied.
- **Test gate updates after pin:** When the edition pin is set, a test checking "execute refused without pin" becomes stale. Update such tests to test the next-in-line safety gate (wrong edition mismatch) rather than removing the safety gate test entirely.

---



**User directive:** W1 Stage 0 input is JSONL-only; do not use TSV for W1 eval consumption.

**Implementation:** Removed TSV fallback from `evaluate.py`, added `--manual-w1-jsonl` CLI flag, updated `scripts/run_stage0_eval.sh` to use `MANUAL_W1_JSONL` env. Implemented strict accepted-row orthographic gate: NFC normalization, ʻokina orthography (U+02BB only), no combining macron U+0304, non-empty item_id. Emits JSONL-specific report fields: `jsonl_sha256`, `jsonl_size_bytes`, `schema_version_seen="manual-w1-jsonl-v1"`. Preserved accepted-row hashes and `w1_suite_sha256` computation. Updated docs/tests.

**Validation:** ✅ py_compile clean, ✅ sh -n clean, ✅ 50/50 tests green, ✅ git diff --check clean.

**Review:** Rusty (NLP Researcher) — APPROVED background gate. Confirmed JSONL-only consumption, strict accepted-row gates, stable hashes, invalid exit propagation, docs/tests alignment.

**Outcome:** ✅ W1 Stage 0 now reads JSONL only; TSV is authoring-source only for `scripts/315_hash_manual_w1_eval.py --execute --jsonl-only`. Locked out of next revision cycle per standard rule.

---

## 2026-04-30 — Stage 0 summary-shape review and post-review coordination

**Action:** Reviewed `stage0_eval.v2` tracked summary shape for consumability by a future cross-checkpoint aggregator.

**Verdict:** APPROVED. No critical data-contract issues; three non-blocking cosmetic notes forwarded to Basher for optional post-review cleanup (all three applied).

**What I verified:**
1. Hash-only summary projection: `scripts/run_stage0_eval.sh` excludes raw `generations`, raw prompt text, raw eval text. Per-sample orthography dicts carry only counts/bools. Full artifact stays under ignored `data/eval_runs/` with `full_artifact_sha256` pointer in summary.
2. Stable top-level keys: all present always; missing fields use `{"status":"absent"}` instead of dropping keys → aggregator can do dense diffs without per-checkpoint key gymnastics.
3. Schema/version fields: `schema_version = "stage0_eval.v2"`, `prompt_suite.suite_id = "stage0.v1"` + `suite_sha256` → aggregator can gate fairness (mismatched suite ⇒ refuse orthography diff; mismatched tokenizer/eval_set/max_length ⇒ refuse PPL diff).
4. No raw text tracked: confirmed across 5 surfaces (prompt_suite, eval_set, orthography_metrics, orthography_aggregate, tripwires).
5. Not-yet-wired probes: uniform `{"status":"not_configured","reason":"..."}` → aggregator branches on single shape.
6. Cross-checkpoint fairness: all confounds captured in-band (identity, decoding, ppl_config, eval_set, provenance) so deltas are readable without hidden skew.

**Fair-comparison patterns aggregator can rely on:**
- PPL diff comparable iff `tokenizer_name_or_path`, `tokenizer_vocab_size`, `ppl_config.max_length`, `eval_set.sha256` match (all present).
- Orthography/tripwires diff comparable iff `prompt_suite.suite_sha256` matches (present).
- Per-sample drift comparable via `prompt_suite.items[i].id` join on `generation_sha256.sample_i` (present).
- English-forgetting check: field exists as `english_ppl.status = "not_configured"`; when wired, only status flips + numeric appears; schema stable.

**Fairness gates aggregator must enforce on entry:**
1. `prompt_suite.suite_sha256` equal across comparison rows (else refuse orthography/tripwire diff).
2. `eval_set.sha256`, `tokenizer_name_or_path`, `tokenizer_vocab_size`, `ppl_config.max_length` equal (else refuse PPL diff).
3. `schema_version` equal or migrated explicitly.

**Post-review cleanups applied by Basher (per notes):**
1. `hawaiian_ppl` parity: now emits `{"status":"not_configured","reason":"..."}` when eval_file is absent, matching the shape used by other absent probes.
2. `schema_version` fallback: flipped from `"stage0_eval.v1"` (silent mislabel) to `"unknown"` (visible).
3. Suite-design invariant documented in `code/README.md` + `docs/eval_pipeline.md` §8.1.

**Testing observed:** 18/18 passing via `PYTHONPATH=. python3 -m unittest tests.test_evaluate tests.test_metrics` from `code/`.

**Durable lesson:** For drift-signal artifacts, review checklist is: (1) raw text excluded? (2) keys stable across modes? (3) version + suite hash for gating? (4) confounds captured in-band? (5) not-yet-wired probes uniform placeholder shape? Basher's bundle hits all five; hold future eval/manifest work to this bar.

---

## 2026-04-30 — Reviewed Basher's Stage 0 drift-signal bundle (`stage0_eval.v2`)

**Asked by:** yashasg, on Basher's request. Review-only; no code changes.

**Verdict:** Approved. Wrote `.squad/decisions/inbox/linus-stage0-summary-review.md`.

**What I confirmed:**
- Hash-only summary projection in `scripts/run_stage0_eval.sh` excludes `generations` and any raw prompt/eval text. Per-sample orthography dicts carry only counts/bools, no text. Full artifact stays under ignored `data/eval_runs/`; summary references it via `full_artifact_sha256`.
- Stable top-level keys with `{"status": "absent"}` fallback ⇒ aggregator can do dense diffs.
- `schema_version = "stage0_eval.v2"`, `prompt_suite.suite_id = "stage0.v1"` + `suite_sha256` give the aggregator the gates it needs to refuse unfair comparisons (mismatched suite ⇒ no orthography diff; mismatched tokenizer/eval-set/max_length ⇒ no PPL diff).
- Not-yet-wired probes (`english_ppl`, `manual_w1`, `hawaiian_ppl_by_source`) all use uniform `{"status":"not_configured","reason":"..."}` so the aggregator can branch on a single shape.
- Confounds that would silently bias cross-checkpoint deltas are captured in-band: `identity.{model_dtype, device_map, quantization_config, tokenizer_*, model_class, is_adapter, base_model, *_version}`, `decoding.*`, `ppl_config.max_length`, `eval_set.{sha256, *_count, total_tokens, max_length_used}`, `source_git_commit`.
- 18/18 tests green via `PYTHONPATH=. python3 -m unittest tests.test_evaluate tests.test_metrics` from `code/`.

**Small follow-ups noted (non-blocking, no agent re-route):**
- Wrap `hawaiian_ppl` with `{"status":"absent"}` when `eval_file` is omitted, for parity with other absent probes.
- Wrapper's fallback `schema_version` default of `"stage0_eval.v1"` should be `"unknown"` to avoid silent mislabeling if the report ever loses the field.
- `diacritic_density_bin_counts` appears under both `eval_set` (records) and `orthography_aggregate` (generations); future aggregator must qualify by parent path. Doc-only note.

**Lesson for future review passes:**
- For drift-signal artifacts, the right review checklist is: (1) raw text excluded? (2) keys stable across run modes? (3) version + suite hash for comparability gating? (4) confounds captured in-band? (5) not-yet-wired probes have uniform placeholder shape? Basher's bundle hits all five. This is the bar I should hold future eval/manifest schema work to.

## Core Context

- **Project:** A plan for training an open-source LLM focused on the Hawaiian language, including data, model choices, infrastructure, evaluation, and costs.
- **Role:** Data Engineer
- **Joined:** 2026-04-29T01:38:35.142Z

## 2026-04-29 — FineWeb-2 Stage-1 prototype cleaning gate

- Extended `scripts/301_build_stage1_dataset.py` so FineWeb-2 train rows from `310` are no longer passed through as raw LID-classified web rows.
- Cleaning policy: NFC normalization, likely Hawaiian ʻokina variants → U+02BB, paragraph-level Hawaiian re-gating, timestamp/synopsis/navigation/ad/social/URL boilerplate removal, exact repeated-paragraph template removal, kahakō sanity checks, and diacritic-density reporting.
- Local full run from existing FineWeb raw data: 95,507 rows seen; 88,979 accepted before exact cleaned-doc dedupe; 6,528 rejected. Paragraphs: 1,876,399 seen; 922,066 kept; 954,333 rejected with reason counts in `data/stage1/fineweb2_haw/cleaning_report.json`.
- Stage-1 train token counts after final manifest split/dedupe: raw 59,534,611 vs cleaned 44,067,289 overall train tokens. FineWeb train slice alone: 79,812 rows, raw 59,290,760 vs cleaned 43,843,711 tokens.
- Reports now carry source/register token summaries plus raw/clean token counts; outputs remain under ignored `data/` paths. MinHash/LSH against cleaned `hawwiki`/`hawwikisource` remains a planned next pass, not implemented here.

## 2026-04-29 — Stage-2 JSONL contract follow-up (#11)

- Reconciled Stage-2 docs/scripts around JSONL-first prototype artifacts: canonical manifest is `data/stage2/stage2_manifest.jsonl`; `data/stage2/stage2_sft.jsonl` is the emitter default.
- Demoted Parquet to future derived mirror only; removed stale Stage-2 Parquet-as-canonical references from docs/scripts.
- Resolved `release_eligible`: kept in schema/provenance, default false under `prototype_only=true`, and added a schema violation for prototype rows that claim release eligibility.
- Validation passed: `python3 -m py_compile scripts/320_build_stage2_manifest.py scripts/321_score_stage2_alignment.py scripts/330_emit_stage2_sft_jsonl.py`; `python3 scripts/320_build_stage2_manifest.py --dry-run --print-schema`; targeted stale-reference check found no `stage2_manifest.parquet`, `stage2_manifest.*`, or `stage2.jsonl.gz` references.

## 2026-04-29T19:54:48Z — Cross-doc data-accuracy pass

**From:** Scribe (orchestration checkpoint). In parallel with Danny's docs consistency pass.

**Summary:** Completed data-doc accuracy validation. Audited all data-sensitive sections of `docs/data-pipeline.md`, `docs/training-pipeline.md`, `docs/eval_pipeline.md`, and `docs/stage2-alignment-quality.md`. Reconciled manifest schemas, token/pair counts, and script contracts against Stage 1/2 builders, emitters, and quality scorers.

**Key outcomes:**
- FineWeb split counts locked per Frank audit: 100/200 scripts confirmed live; no reconciliation issues.
- Stage 1 token yield estimates (10–30M cleaned, 5M floor, 50M aspirational) consistent with nūpepa-pilot go/no-go gate guidance.
- W1 draft eval status: FLORES-200 confirmed no Hawaiian; substitutes (global-piqa-parallel, Taxi1500, Tatoeba, BibleNLP) documented; no public-release headlines.
- Tokenizer audit (Rusty) remains hard blocker for Stage 1 token binning; explicitly listed in Stage 0 prereqs.
- Stage 2 JSONL/SFT: canonical JSONL confirmed; per-pair + directional expansion locked; instruction templates deferred.
- JW300: deferred/excluded, explicit in fetch plan, no attempts to ingest.

**Validation:**
- `py_compile` passed for scripts 301, 320, 330.
- `scripts/301 --self-test` passes.
- `scripts/301 --show-targets` produces expected manifest schema.
- `scripts/330` empty dry-run clean.
- `git diff --check` clean.
- `rg` sweep: no stale `582/305`, `eval_hashes.parquet`, or `stage2_manifest.parquet` mismatches; no unintended release promises except documented prohibition.

**Orchestration logs:** `.squad/orchestration-log/2026-04-29T19-54-48Z-linus-docs-pass.md` (data validation details). Session log: `.squad/log/2026-04-29T19-54-48Z-docs-pass.md`.

**Open items unchanged:** Cultural-review owner assignment (blocker #7); Ulukau nūpepa pilot decision gate; Bible edition pinning for Stage 2; Tokenizer audit (Rusty) for base-model choice.

**Status:** ✓ Data-doc consistency locked. Ready for Stage 0 go/no-go decision pending cultural-review owner assignment and tokenizer audit completion. No commits; user requested docs pass only.

## 2026-04-29T20:30Z — Prototype journey fact-check document

**Task:** Produce a concise fact-check note at `docs/prototype-journey-data-factcheck.md` for Danny/Coordinator—PowerPoint-ready journey doc for prototype decisions.

**Deliverable:** `docs/prototype-journey-data-factcheck.md` (19.8KB, structured, audience-aware).

**What was verified:**
- FineWeb-2 dataset config: 887 official test rows, 70/30 split (621 dev / 266 holdout), stable NFC-SHA256 ordering verified against `split_dedupe_manifest.json`.
- Official test split + ledger policy: Canonical JSONL at `data/evals/eval_hashes.jsonl`, 892 hashes (887 FineWeb + 5 W1 draft), schema version `eval-hashes-jsonl-v1`, JSONL-first (Parquet deferred).
- Stage 1 cleaning token/count summary: 44M cleaned from 59.5M raw (26% reduction), 92.5k docs, conservative gate met (2.5M target ✅), source/register summaries recorded.
- Stage 1 manifest/pack status: `stage1_manifest.jsonl`, `stage1.jsonl.gz`, `token_target_report.json` all live; tokenized `.bin` blocked on tokenizer audit.
- W1 manual eval status: 5 draft rows (all categories, high/medium diacritic), hashing method proven, **blocker: no accepted rows yet** (requires Hawaiian-literate review, issue #7).
- Stage 2 JSONL manifest/SFT status: Schema and tools landed (scripts 320/321/330 compile + pass dry-run); zero real pairs yet (source adapters pending); JSONL canonical, Parquet deferred.
- Local vs. closed: Mapped each fact to closure status — Stage-1 cleaning (#5) and split policy (#2–#3) and Stage-2 contract (#11) **ready to close** once final review passes; W1 review (#7) and tokenizer audit (#8) **blocked on human/external gated gates**; Stage-2 adapters (#14) **contract ready, wiring deferred**.

**Wording guidance included:** ✅/❌ phrasing for PowerPoint slides to avoid overclaiming (e.g., "44M cleaned tokens" not "final tokens", "Parquet optional future mirror" not "canonical", "5 draft W1 rows ready for review" not "W1 eval complete").

**Structure:** Executive summary → 8 fact sections → local-vs-closed mapping → PowerPoint narrative summary + verification checklist. Zero tool internals exposed; all counts traced to source.

**Status:** ✓ Document complete and verified against live data. No code changes; docs-only output. Ready for Danny's PowerPoint preparation.

## 2026-04-29 — W1 from Wikisource proofread/validated (yashasg ask)

**Question:** can `proofread_status` / validated Wikisource snippets be treated as W1?

**Findings:**
- Adapters `102/202` enumerate via `list=categorymembers` only; ProofreadPage quality (`prp_quality_level`) is **not** fetched, and `data/raw/hawwikisource/fetch.jsonl` + `stage1_manifest.jsonl` carry no proofread keys (verified: 159 hawwikisource rows in current manifest, zero proofread/validated/quality fields). Frank owns adapter shape.
- W1 contract is hand-authored failure-mode probes across 5 categories; a clean PD paragraph isn't an automatic W1 row.
- Wikisource already feeds Stage 1 training, so any promotion creates a contamination risk against `train ∩ eval_hashes = ∅`.

**Recommendation:** validated Wikisource (`proofread_status=4`) becomes a **W1 candidate** (`review_status=draft`, `eval_consumable=false`, `split=w1_candidate`) — never auto-accepted. `proofread_status=3` is preflight-only. Acceptance still requires #7 Hawaiian-literate review.

**No code changes this pass** — surgical edits would be premature without Frank's `proofread_status` field. Implementation shape (Frank: extend 102/202 to request `prop=proofread`; Linus: surface in `301` manifest, add `scripts/316_seed_w1_from_wikisource.py`, gate on `train ∩ candidate = ∅` before reviewer accept) recorded in `.squad/decisions/inbox/linus-w1-wikisource-quality.md`.

**Open asks:** Frank to confirm reachability of ProofreadPage quality from main-ns category enumeration; Coordinator to confirm whether wikisource-derived candidates may merge into W1 proper or live as a separate `W1-wikisource` slice.

## 2026-04-29 — Quality-4 Wikisource fetch: count-only contract (parallel to Frank)

**Ask:** yashasg — "fetch the quality level 4 data for eval, i want to see how much data is there."

**Read:** count-only volume reconnaissance. Not eval ingest, not W1 acceptance.

**Stance (no code changes this pass):**
- No W1 rows created; no writes to `data/evals/eval_hashes.jsonl` or `data/evals/manual_w1/w1-haw-micro-eval.tsv`.
- Quality-4 (`quality_text=="Validated"`) remains *necessary, not sufficient* for W1 — Hawaiian-literate review (#7) still gates acceptance.
- Non-replacement (user directive 2026-04-29T21:27:53Z) holds: Frank's output is additive, lives in its own file under ignored `data/`, and existing `data/raw/hawwikisource/fetch.jsonl` rows are untouched. Equivalence to prior fetches is a later dedupe-pass question.
- Confirmed candidate-manifest field list for whenever seeding does happen: `source_url`, `page_title`, `page_id`, `revision_id` (or explicit null + `fetched_at`), `namespace`, `proofread_quality=4`, `quality_text="Validated"`, `sha256_normalized` (NFC + SHA-256), `normalization_method="NFC"`, `hash_method="sha256"`, `candidate_stage="eval-candidate"`, `candidate_split="w1_candidate"`, `eval_consumable=false`, `prototype_local=true`, `release_eligible=false`, `origin_hint="wikisource_validated"`, `fetched_at`. These let later dedupe/contamination passes validate without replacing existing data.
- Docs check: `docs/data-pipeline.md` §ProofreadPage quality and `docs/eval_pipeline.md` §W1 already cover Validated→W1-candidate semantics and `eval_consumable=false` for draft/preflight rows. No doc edit warranted until a count motivates the seeding script.

**Decision recorded:** `.squad/decisions/inbox/linus-quality4-eval-contract.md`.

**Open asks:** Frank — share count + ns=0 vs ns=104 split when fetch lands; Coordinator — still owed call on whether wikisource candidates may flip to W1 `accepted` or live as a separate `W1-wikisource` slice.

## 2026-04-29T22:58:20Z — Quality-4 Wikisource eval-safety contract session recorded

**From:** Scribe (orchestration checkpoint)

**Outcome:** ✓ Count-only contract established; zero-volume result confirmed; decisions merged; session logs written.

Established eval-safety contract for future Validated (quality=4) Wikisource candidates: reconnaissance-only this pass, no ledger writes, no W1 TSV mutations, non-replacement policy honored.

**Contract fields (future candidates):**
- Metadata: `source_url`, `page_title`, `page_id`, `revision_id`, `namespace`, `proofread_quality=4`, `quality_text="Validated"`
- Content: `sha256_normalized` (NFC-SHA256), `normalization_method="NFC"`, `hash_method="sha256"`
- Flags: `candidate_stage="eval-candidate"`, `candidate_split="w1_candidate"`, `eval_consumable=false`, `prototype_local=true`, `release_eligible=false`, `origin_hint="wikisource_validated"`, `fetched_at`

**Invariants preserved:**
- `train ∩ eval_hashes = ∅` unaffected (no ledger writes this pass)
- Existing `data/raw/hawwikisource/fetch.jsonl` not replaced; outputs additive
- `data/evals/eval_hashes.jsonl` schema unchanged

**Session artifacts:**
- Orchestration log: `.squad/orchestration-log/2026-04-29T22:58:20Z-linus.md`
- Session log: `.squad/log/2026-04-29T22:58:20Z-wikisource-quality4-scan.md`
- Decisions merged to `.squad/decisions.md`

**Status:** Ready to receive Frank's candidate manifest (0 rows this round). Count and ns=0 vs ns=104 split will inform transclusion-walk feasibility for future seeding.

**Open:** Coordinator clarification owed on wikisource-candidates merge path (issue #7).

## 2026-04-29T21:34:03Z — W1 from Wikisource proofread/validated (Session complete)

**From:** Scribe (orchestration checkpoint)

**Outcome:** ✓ Recommendation recorded; implementation roadmap defined; ready for team decision.

Recommended treating `proofread_status=4` ("Validated") Wikisource as W1 _candidates_ (not auto-accepted).

**Key recommendation:**
- `proofread_status=4` → W1 candidate: `review_status=draft`, `eval_consumable=false`, `split=w1_candidate`
- `proofread_status=3` → preflight contamination-check input only (single reviewer, not Hawaiian-literate)
- Promotion to accepted still requires #7 Hawaiian-literate review
- Pre-acceptance gating: candidate NFC-SHA must not exist in current Stage 1 train pack

**Implementation shape (post-Frank metadata):**
1. Frank extends 102/202 to fetch `proofread_status` field
2. Linus surfaces in `301_build_stage1_dataset.py` manifest
3. Linus writes `scripts/316_seed_w1_from_wikisource.py` to extract short W1-suitable snippets
4. Linus gates on `train ∩ candidate = ∅` before reviewer can accept

**Contamination contract:** W1 today is hand-authored probes (not arbitrary clean text); validated Wikisource ≠ automatic W1. Preserves "hand-authored probe" semantics while seeding larger candidate pool.

**Open asks:**
1. Frank: confirm ProofreadPage reachability for category enumeration
2. Coordinator: confirm wikisource candidates merge into W1 proper or stay separate slice

**Session artifacts:**
- Orchestration log: `.squad/orchestration-log/2026-04-29T21-34-03Z-linus.md`
- Session log: `.squad/log/2026-04-29T21-34-03Z-wikisource-w1-quality.md`
- Decisions merged to `.squad/decisions.md`

## Learnings

### 2026-04-30 — Ulukau/Nupepa human_fetch → tokenizer-audit candidate

- Converted `data/raw/ulukau_nupepa/human_fetch.md` (manual paste of Ulukau Hawaiian newspapers landing copy, EN + HAW) into an additive, audit-only artifact.
- Outputs (all under ignored `data/`):
  - `data/tokenizer_audit/ulukau_nupepa/human_fetch.jsonl` (2 records, `lang` ∈ {en, haw}).
  - `data/tokenizer_audit/ulukau_nupepa/human_fetch.haw.txt` (Hawaiian-only).
  - `data/tokenizer_audit/ulukau_nupepa/human_fetch.txt` (both sections).
  - `data/tokenizer_audit/ulukau_nupepa/README.md` (manifest + policy).
- Helper: `scripts/_convert_ulukau_human_fetch.py` (local one-shot, idempotent; not committed).
- Normalization: NFC; ʻokina folded to U+02BB from U+2018/U+2019/U+02BC/U+0060; markdown `# English` / `# Hawaiian` scaffolding stripped; page titles + bodies preserved.
- HAW slice: 527 chars, ~103 words, ʻokina × 22, kahakō × 21, diacritic density ≈ 0.082 — useful as a high-diacritic probe row for the planned tokenizer-audit test (Rusty, Issue #8 gate).
- Policy: tagged `audit_use=tokenizer_audit_candidate`, `audit_only=true`, `stage1/eval/training/w1_eligible=false`. License status `unverified_landing_copy`. User's "likely native speaker" belief recorded as note, not verification.
- Did NOT touch raw source, Stage 1, eval hashes, or W1. Did not commit. Pre-existing dirty files in `scripts/` left alone.

### 2026-04-30 — Ulukau Kaʻehuikimanōopuʻuloa pages → tokenizer-audit candidate (additive)

- Converted manual page-paste of *He moʻolelo kaʻao no Kaʻehuikimanōopuʻuloa*
  at `data/raw/ulukau_nupepa/human_fetch_book_pages.txt` into a new audit-only
  artifact. **Additive** — prior `human_fetch.*` landing-copy artifact
  untouched (hashes verified).
- Outputs (all under ignored `data/`):
  - `data/tokenizer_audit/ulukau_nupepa/kaehuikimanoopuuloa/kaehuikimanoopuuloa.jsonl` (1 row, `lang=haw`).
  - `data/tokenizer_audit/ulukau_nupepa/kaehuikimanoopuuloa/kaehuikimanoopuuloa.haw.txt` (Hawaiian-only).
  - `data/tokenizer_audit/ulukau_nupepa/kaehuikimanoopuuloa/manifest.json`.
  - `data/tokenizer_audit/ulukau_nupepa/kaehuikimanoopuuloa/README.md`.
- Helper: `scripts/_convert_kaehuikimanoopuuloa.py` (local one-shot, idempotent; not committed).
- Normalization: NFC; ʻokina U+02BB rule applied (source already clean; 0 substitutions);
  per-line whitespace collapse; multi-blank-line page-paste runs collapsed to single blank;
  paragraph boundaries preserved; no content deletion; curly quotes preserved as dialogue.
- Counts: 14,753 chars · 3,224 rough words · 21 paragraphs · ʻokina × 756 · kahakō × 614 ·
  diacritic density ≈ **0.1254** (vs ≈ 0.082 for the landing-copy HAW slice — strong
  high-diacritic probe row for the planned tokenizer-audit test, Issue #8 gate).
- Policy: `audit_use=tokenizer_audit_candidate`, `audit_only=true`,
  `stage1/eval/training/w1_eligible=false`. License: `unverified` (published
  work; rights NOT cleared). User's "likely native speaker" framing recorded
  as note, not verification.
- Did NOT touch raw source (SHA verified pre/post), Stage 1, eval hashes, W1,
  or prior tokenizer_audit artifacts. Did not commit.

## Learnings

- 2026-04-30: Tokenizer audit harness has a path/body split-brain — the `dry_run` JSON field can disagree with the parent directory (`official/` vs `dry_run/`). Fix is to drop the body field, make the directory the source of truth, and echo `run_kind` from the caller validated against the path at write time. Schema bump to `tokenizer_audit_report.v2`.
- 2026-04-30: Rusty's Stage-0 gate has three dimensions (overall, high-diacritic slice, standalone diacritic chars) but the current harness only computes overall and emits `"not_evaluated"` for the other two — so any `go` it prints today is a partial. Llama re-run must wait until all three sections are wired and the three identity fields (model_repo_sha, tokenizer_sha256, tokenizer_fingerprint_sha256) are non-null in `official/`.

## 2026-04-30T03:47:33Z — Tokenizer audit harness cleanup planning

**From:** Scribe (session logger + orchestration)

**Sync task:** Planned tokenizer audit harness cleanup to fix internal inconsistencies in schema/path/identity fields and prepare for Llama-3.1-8B re-run.

**Summary:** Coordinated cleanup with Rusty (NLP lead). Linus scope: schema v2 (remove dry_run, add run_kind contract), populate model/tokenizer identity fields (model_repo_sha, tokenizer_sha256, tokenizer_fingerprint_sha256), add high-diacritic evaluator (minimum coverage gates: 10 samples / 1,500 words), add diacritic-char evaluator (per-character tokenization), add debug artifacts (samples_summary, debug.jsonl gitignored), convert one-shot test to parametrized unit+integration suite.

**Order of operations:** Schema/path/identity first (no model needed); unit tests on synthetic encodings; high-diacritic+diacritic-char sections; then Llama-3.1-8B re-run. Do not re-run while sections are `not_evaluated`.

**Decision:** `.squad/decisions/inbox/linus-tokenizer-audit-harness-cleanup.md` (now merged to decisions.md).

---

## 2026-04-30 — Tokenizer audit helper: metadata derived from inputs

- Added `tokenizer_metadata_from_model_and_tokenizer(model_id, tokenizer)` in `code/tests/test_tokenizer_audit.py`. Pulls `tokenizer_name_or_path`, `hf_commit_sha` (`_commit_hash` then `init_kwargs["_commit_hash"]`), `tokenizer_class`, `is_fast`, and `vocab_size = len(tokenizer)` directly off the tokenizer object. Robust to `tokenizer=None` (returns dict with `model_id` set, rest `None`).
- `tokenizer_audit_output_from_encoding(...)` now embeds this dict as the `model` section. Removed null placeholder fields `model_repo_sha`, `tokenizer_sha256`, `tokenizer_fingerprint_sha256` — those need Hub/file access and aren't derivable from this helper's inputs; they belong in the future `build_audit_report` orchestrator (see harness-cleanup decision), not here.
- Deferred `import llm_hawaii.data` into the smoke test method so the module is importable (and the helper unit tests runnable) without `transformers` installed.
- Added 6 unit tests with fake tokenizers; all pass: `cd code/tests && python3 -m unittest -v test_tokenizer_audit.TestTokenizerMetadataFromModelAndTokenizer` → 6/6 OK. `python3 -m py_compile code/tests/test_tokenizer_audit.py` clean.
- Decision recorded: `.squad/decisions/inbox/linus-tokenizer-helper-metadata.md`.

## Learnings

- 2026-04-30: HF `PreTrainedTokenizer*` exposes the loaded revision via `tokenizer._commit_hash` (set when loaded from the Hub), with `tokenizer.init_kwargs["_commit_hash"]` as the older/serialized fallback. That's the cheap, no-network handle for "which exact tokenizer revision" — prefer it over null placeholders or fabricated SHAs in audit reports. Real `tokenizer.json` SHA + repo SHA still belong in a Hub-aware orchestrator, not in shape-only helpers.

## 2026-04-30T04:05:58Z — Tokenizer helper metadata update landed

**From:** Scribe (Session logger)

**Summary:** Linus tokenizer helper metadata extraction task completed and logged:
- New function: `tokenizer_metadata_from_model_and_tokenizer(model_id, tokenizer)` pulls metadata directly from tokenizer object inputs
- Removed null placeholder fields: `model.model_repo_sha`, `model.tokenizer_sha256`, `model.tokenizer_fingerprint_sha256`
- Includes tokenizer name, class, `is_fast` flag, vocab size, and `hf_commit_sha` derived from `tokenizer._commit_hash` or `init_kwargs`
- Validation: ✅ compilation, ✅ 6/6 unit tests pass; ⚠️ smoke test blocked locally by missing `transformers` dependency

**Orchestration log:** `.squad/orchestration-log/2026-04-30T04:05:58Z-linus.md`  
**Session log:** `.squad/log/2026-04-30T04:05:58Z-tokenizer-helper-metadata-update.md`  
**Related decision:** Merged to `.squad/decisions.md` under "Added 2026-04-30: Linus — Tokenizer audit helper metadata extraction (landed)"

**Next:** Full smoke test on CI/full environment with `transformers` installed. Ready for integration with tokenizer audit pipeline.

## 2026-04-30T04:20:10Z — Tokenizer audit cleanup: 7-phase implementation plan finalized

**From:** Scribe (session logger)

**Summary:** Linus mapped Rusty's NLP-side cleanup semantics into concrete implementation phases. Concrete plan now in decisions.md.

**Merged to decisions.md — 7 phases:**

1. **Module split** (prep, no behavior change): `code/tokenizer_audit.py` + helpers; `code/tests/test_tokenizer_audit.py` imports
2. **Family-aware proxy detector** (**gated on Rusty sign-off**): `detect_tokenizer_family()`, family-aware `_is_byte_fallback_or_proxy()`, echo family in report
3. **`high_diacritic` evaluator**: Selection rule (≥3 diacritics + ≥0.25 ratio), min 10 samples / 1,500 words for evaluated status
4. **`diacritic_chars` evaluator**: Standalone encoding for ʻ ā ē ī ō ū + uppercase; pass ≤2 tokens each
5. **Report-shape updates** (additive, schema stays v1): `model.tokenizer_family` + high_diacritic populated + diacritic_chars.items[] + 3 new checks
6. **Test coverage** (synthetic + smoke): 4 family detection + 3 proxy + 3 high_diacritic + 2 diacritic_chars + 1 report + smoke
7. **Execute in order**: §1 → §2 (**Rusty approval**) → §3–4 → smoke re-run vs. 20260430T041606Z

**Out of scope (deferred):** Schema v2, `run_kind`, identity SHAs, `samples_summary`, pytest parametrization.

**Phase 2 gate:** Will not implement §2 without Rusty sign-off on family table + thresholds per family. Coordinator to route through Rusty.

**Orchestration log:** `.squad/orchestration-log/2026-04-30T04-20-10Z-linus-tokenizer-cleanup.md`  
**Session log:** `.squad/log/2026-04-30T04-20-10Z-tokenizer-cleanup-plan.md`

**Next steps:** Rusty confirms family table; Coordinator gates; Linus implements.


## 2026-04-30T04:44:24Z — Tokenizer audit cleanup implementation (phases 1–6 complete)

**From:** Scribe (orchestration logger)

**Summary:** Linus implemented tokenizer audit harness cleanup (phases 1–6 of 7-phase plan from prior decision). Module split, family detection, proxy applicability fixing, roundtrip checks, high-diacritic and diacritic-chars evaluators all deployed locally. All 33 unit tests passing; 1 smoke skipped because `transformers` unavailable in env.

**Deliverables:**
- **New:** `code/llm_hawaii/tokenizer_audit_helpers.py` (all reusable audit logic)
- **Refactored:** `code/tests/test_tokenizer_audit.py` (33 unit tests, 1 smoke)
- **Schema:** Remains `tokenizer_audit_report.v1` (backward-compatible, additive changes only)
- **Report changes (all additive):**
  - `model.tokenizer_family` populated via `detect_tokenizer_family` algorithm (byte_level_bpe, sentencepiece_byte_fallback, unknown, null)
  - `checks[*].status` explicit (evaluated, not_applicable, not_evaluated, insufficient_samples)
  - `checks[*].reason` optional explanatory text
  - `byte_fallback_or_proxy_rate` → `status=not_applicable` for byte-level BPE (threshold unchanged 0.01, excluded from blocking_reasons)
  - `roundtrip_lossless` check appended (exact after NFC normalization, required when both text+tokenizer present)
  - `high_diacritic` section populated (Hawaiian diacritic-heavy spans, ʻokina+kahakō vowels, min 10 samples/1500 words to reach evaluated status)
  - `diacritic_chars` section populated (ʻ ā ē ī ō ū + uppercase, standalone encoding, pass if ≤2 tokens)
  - `recommendation.blocking_reasons` fixed (never includes `passed=null` or `not_evaluated` items)

**Thresholds (all frozen):** min_words=1500, min_high_diacritic_samples=10, overall_tokens/word≤2.50, explicit_byte_fallback=0, proxy≤0.01 (not_applicable for BLBPE), high_diac_tokens/word≤3.25, diacritic_char_max_tokens=2

**Family detection algorithm:**
1. Vocab has `<0xNN>` → `sentencepiece_byte_fallback`
2. Explicit hint in source → that hint
3. Class ∈ {TokenizersBackend, GPT2Tokenizer*, LlamaTokenizerFast, Qwen2Tokenizer*} → `byte_level_bpe`
4. Vocab has ≥200/256 GPT-2 byte_to_unicode chars → `byte_level_bpe`
5. Else → `unknown`

**Test coverage (33 unit + 1 smoke):**
- Metadata: 9 (tokenizer_family populated)
- Family detection: 6 (Llama, SPM-BF, unknown, generic fast, explicit, integration)
- Proxy + blocking semantics: 4 (not_applicable BLBPE, blocking unknown, not-evaluated never blocks, explicit byte fallback always blocks)
- Roundtrip: 4 (passes, whitespace exact, lossy blocks, omitted when text/tokenizer missing)
- High-diacritic: 4 (paragraph filter, BLBPE proxy not_applicable, threshold gating, insufficient_samples)
- Diacritic chars: 5 (lossless pass, decode-fail, token-count gate, blocking-reason, tokenizer_unavailable)

**Validation:** `PYTHONPATH=code python3 -m py_compile code/llm_hawaii/tokenizer_audit_helpers.py code/tests/test_tokenizer_audit.py` ✅; `PYTHONPATH=code python3 -m unittest discover -s code/tests -p test_tokenizer_audit.py -v` ✅ (33 unit passed, 1 smoke skipped)

**Out of scope (deferred):** Schema v2, `run_kind`, `generated_at`, `samples_summary`, debug JSONL dump, Llama-3 re-run (transformers unavailable), SHA computation

**Phase 7 (next):** Re-run Llama-3.1-8B audit when transformers available; write fresh official report; verify byte_level_bpe family, roundtrip_lossless=true, all sections populated

**Decision merged to canonical decisions.md:** `.squad/decisions.md` (2026-04-30T04:44:24Z entry)

**Orchestration log:** `.squad/orchestration-log/2026-04-30T04:44:24Z-linus-tokenizer-audit-cleanup-implementation.md`

**Session log:** `.squad/log/2026-04-30T04:44:24Z-tokenizer-audit-cleanup-implementation.md`

## 2026-04-30 — W1 Stage 0 summary review (Basher's wiring) — REJECT

**Reviewed:** `code/llm_hawaii/evaluate.py:manual_w1_status` + Stage 0
dispatcher + `scripts/run_stage0_eval.sh` projection +
`code/tests/test_evaluate.py` (7 W1 tests) + decisions
`basher-w1-stage0-status.md` and `rusty-w1-stage0-contract.md`.

**Verdict:** Reject — two blocking fixes required.

**What's clean:**
- Raw-text exclusion is enforced and pinned by a leak-check test.
- Status enum is stable and documented in 3 places (decision, README,
  `eval_pipeline.md` §11).
- `accepted_count == eval_consumable_count` alias is the right call
  for single-field summary diffs.
- Wrapper projection passes `manual_w1` through unflattened and
  always lands the resolved TSV path / `--no-manual-w1` flag in the
  tracked `command` field.
- `scoring_status: "not_wired"` is on every shape — metadata-evaluated
  vs task-scored is unambiguous in every artifact.

**Blocking #1 — `invalid` does not fail the run.** Rusty's contract
required non-zero exit on `invalid` (same posture as a failed hash
audit). Implementation returns the dict and the CLI exits 0; a
header drift / UTF-8 corruption silently lands in
`docs/eval-runs/stage0/` as a "successful" Stage-0 run. Required fix:
`sys.exit(2)` after report write when `manual_w1.status == "invalid"`.

**Blocking #2 — no accepted-suite hash.** Contract specified
`w1_suite_sha256` (sha over sorted accepted `(item_id,
sha256_normalized)` pairs) and `accepted_item_hashes` (sorted hash
list). Neither is emitted. Whole-file `tsv_sha256` conflates
draft-row churn with accepted-set identity changes — the cross-
checkpoint aggregator cannot answer "did the *accepted* eval set
change?" without these. Required fix: read `sha256_normalized` from
accepted rows (column is already in `MANUAL_W1_HEADER`), emit both
fields on the `evaluated` shape.

**Acknowledged non-blocking divergences:**
- `tsv_sha256` (Basher) vs `input_sha256` (contract) — three docs
  agree on `tsv_sha256`; don't rename.
- `missing` vs `not_configured` split (Basher) is more informative
  than contract's single `absent` — keep the split.
- `harness_error` shape deferred until row-level scoring lands.
- `nfc_normalized_false_count` is whole-file, not accepted-only —
  honest field name; if a tripwire boolean is ever surfaced it must
  be accepted-scoped.
- `MANUAL_W1_HEADER` duplicated from `315_hash_manual_w1_eval.py` —
  deliberate (`llm_hawaii/` stays import-light); track as follow-up.

**Recommended next agent:** Basher (implementation-side, contract-
compliance work; both fixes mechanical and contained).
**Rusty re-review:** not required unless naming diverges further.

**Verdict file:** `.squad/decisions/inbox/linus-w1-summary-review.md`.

## Learnings

- 2026-04-30: When reviewing tracked-summary safety, check three
  axes independently and don't let "no raw text" carry the whole
  review. (1) Raw-text exclusion: assert via leak-check test.
  (2) Cross-checkpoint comparability: ask "what change to the
  underlying inputs is *not* visible in this summary?" — whole-file
  hashes silently conflate eval-relevant edits (accepted rows) with
  irrelevant churn (draft edits, whitespace). Require an accepted-
  set-scoped hash whenever the summary will be diffed across runs.
  (3) Failure posture: an "error" status that produces a zero exit
  is a silent-breakage vector — a Stage-0 run with a quietly broken
  probe block is worse than a noisy failure, because the broken
  artifact lands in the tracked dir and pollutes diffs going
  forward. Match contract posture exactly: `invalid`/`harness_error`
  must trip a non-zero exit; `missing`/`draft_only`/`not_configured`
  are zero-exit expected states.

## 2026-04-30 — W1 revision ownership (Stage 0)

**Action:** Took ownership of the rejected Stage 0 W1 / `manual_w1` artifact
after Basher's in-flight patch. The four contract gaps Rusty flagged
(`accepted_item_hashes`, `w1_suite_sha256`, `schema_version_seen`,
strict orthographic gate on accepted rows) were already addressed in the
worktree; I confirmed the code, then layered the Linus-side asks on top
and corrected the source directive.

**What I changed (mine, not Basher's):**

1. **CLI exit-2 posture** — added `_cli_exit_code(report)` in
   `code/llm_hawaii/evaluate.py` and wired it into `main()`. The report
   JSON is still printed first (so the failing artifact is inspectable),
   then the process exits 2 when `manual_w1.status == "invalid"`. Other
   states (`missing` / `not_configured` / `draft_only` / `evaluated`,
   absent block) stay at 0. Six unit tests in
   `TestCliExitCode` pin the matrix.
2. **Shell propagation** — `scripts/run_stage0_eval.sh` now captures the
   evaluate.py exit code via `… && EVAL_RC=0 || EVAL_RC=$?`, still writes
   the tracked summary projection in the failing case so the bad
   artifact is on disk for inspection, then propagates the non-zero exit.
   `set -eu` is preserved.
3. **Corrected source directive** — `scripts/_convert_ulukau_human_fetch.py`
   was pointing at a non-existent `human_fetch.md`. Per user directive,
   the trusted source is `data/raw/ulukau_nupepa/human_fetch.txt`
   (sectioned `# English` / `# Hawaiian`). Updated `SRC`,
   `source_path`, and the module docstring to make explicit that the
   converter is a *parser/normalizer*, not the source of truth. The
   raw `.txt` file stays under ignored `data/` (it is now `data/raw/…`,
   which is a tracked path, but the populated W1 TSVs derived from it
   remain off-git under `data/evals/manual_w1/`).
4. **Doc updates** — `code/README.md` and `docs/eval_pipeline.md` §8.1
   now spell out: the new `evaluated`-path fields
   (`accepted_item_hashes`, `w1_suite_sha256`, `schema_version_seen`),
   the strict orthographic gate trigger conditions, the
   `error_count` / `first_errors` shape on the `invalid` branch (line +
   field labels only, no row contents), the CLI exit-2 posture, and the
   corrected `human_fetch.txt` source directive.

**What I deliberately left alone:**

- The pass-through projection of `manual_w1` in `scripts/run_stage0_eval.sh`
  is correct as-is — the underlying dict already contains only safe
  fields (status/hashes/counts/errors-by-line), so verbatim forwarding
  preserves raw-data safety without an explicit allowlist. Adding an
  allowlist would silently drop new safe fields the next time we
  extend the contract.
- `scoring_status: "not_wired"` stays put. This revision is metadata
  and orthography validation; row-level scoring is still a follow-up.

**Validation:**

- `python3 -m py_compile code/llm_hawaii/evaluate.py scripts/315_hash_manual_w1_eval.py scripts/_convert_ulukau_human_fetch.py` — clean.
- `sh -n scripts/run_stage0_eval.sh` — clean.
- `cd code && PYTHONPATH=. python3 -m unittest tests.test_evaluate tests.test_metrics` — 42/42 green (was 36/36; +6 from `TestCliExitCode`).
- `git --no-pager diff --check` — clean.

**Why this matters:**

A W1 TSV with an orthographically broken accepted row is a contract
violation by the human reviewer, not a benign config issue. Without the
exit-2 posture, the failing report could land in the tracked summary
dir as a "successful" Stage 0 run and pollute checkpoint-to-checkpoint
diffs going forward. The shell script still writes the summary so the
artifact stays inspectable; it just refuses to claim green.

## 2026-04-30 — W1 Stage 0 input is JSONL-only

**Action:** Implemented the user directive
(`.squad/decisions/inbox/copilot-directive-20260430T081137Z.md`): Stage 0
W1 eval input is now JSONL-only. The TSV stays as the local authoring
format consumed by `scripts/315_hash_manual_w1_eval.py`; the harness no
longer reads it. Final contract logged at
`.squad/decisions/inbox/linus-w1-jsonl-only.md`.

**Changes (mine):**

1. `code/llm_hawaii/evaluate.py` — `manual_w1_status()` rewritten to
   parse JSONL. New default constant `DEFAULT_MANUAL_W1_JSONL`; old
   `DEFAULT_MANUAL_W1_TSV` / `MANUAL_W1_HEADER` /
   `MANUAL_W1_TSV_SCHEMA_VERSION` removed (clean break per directive,
   no TSV fallback in evaluate.py). New emitted fields `jsonl_sha256` /
   `jsonl_size_bytes` replace `tsv_*`. `schema_version_seen` is now
   `"manual-w1-jsonl-v1"` (matches the script-emitted JSONL row
   `schema_version`). Accepted-row hash uses each row's
   `sha256_normalized` when present and well-formed (64 hex chars), else
   computes the canonical `sha256(NFC(prompt) + LF + NFC(reference))` —
   byte-for-byte identical to `scripts/315_hash_manual_w1_eval.py`.
   Orthographic gate also covers `text` field on accepted rows. CLI:
   `--manual-w1-jsonl` replaces `--manual-w1-tsv`.
2. `scripts/run_stage0_eval.sh` — `MANUAL_W1_JSONL` env replaces
   `MANUAL_W1_TSV`; `--manual-w1-jsonl` arg threaded through `build_cmd`
   and the `set --` argv builder. Tracked-summary projection inherits
   the rename via `manual_w1` pass-through (no allowlist; safe by
   construction because the dict only carries hash/count/error-line
   fields). `set -eu` preserved; non-zero `EVAL_RC` still propagated.
3. `code/tests/test_evaluate.py` — full rewrite for JSONL fixtures.
   50/50 green. New coverage: `id` alias, string-bool `nfc_normalized`,
   row-supplied `sha256_normalized` vs harness-computed, gating on
   `text` field, JSONL parse errors → invalid + non-zero exit, empty
   file → `draft_only`, `--manual-w1-tsv` is gone.
4. Docs — `code/README.md`, `docs/eval_pipeline.md` §8.1, and
   `data-sources/manual-eval/README.md` updated. The TSV is now
   described as the authoring/source format; the JSONL is the
   eval-consumable artifact. The `human_fetch.txt` → W1 row workflow is
   documented (manual paste into TSV → `--jsonl-only` regenerate) since
   the converter remains a tokenizer-audit utility.

**What I deliberately did NOT do:**

- Did not commit anything (per instructions).
- Did not modify `scripts/315_hash_manual_w1_eval.py` — it already
  emits `manual-w1-jsonl-v1` JSONL with the right field set, and its
  TSV-input role is intentional (authors edit TSV, the script emits the
  eval JSONL).
- Did not auto-convert `data/raw/ulukau_nupepa/human_fetch.txt` into a
  W1 row — that requires Hawaiian-literate human review and the raw
  W1 row would need to live off-git. Documented the manual command
  path instead.

**Validation (clean):**

- `python3 -m py_compile code/llm_hawaii/evaluate.py scripts/315_hash_manual_w1_eval.py scripts/_convert_ulukau_human_fetch.py`
- `sh -n scripts/run_stage0_eval.sh`
- `cd code && PYTHONPATH=. python3 -m unittest tests.test_evaluate tests.test_metrics` — 50/50 green.
- `git --no-pager diff --check` — clean.
- Smoke test on the actual local JSONL: parses to `draft_only` with
  `schema_version_seen=manual-w1-jsonl-v1`, `jsonl_sha256` populated,
  no raw text in the dict.

## Learnings

- A single eval-consumable file format (JSONL) per probe avoids
  silent-drift between authoring and consumption surfaces. The earlier
  dual-path setup (evaluate.py read TSV, ledger script wrote JSONL)
  meant `w1_suite_sha256` would shift on TSV whitespace edits even when
  no accepted row changed. JSONL-only fixes that: suite hash now
  reflects *accepted-set* churn only.
- When renaming a CLI/env surface, removing the old symbol from the
  Python module beats keeping a deprecated alias when there are no
  external consumers — the test
  `assertFalse(hasattr(ev, "DEFAULT_MANUAL_W1_TSV"))` is the cheapest
  way to guarantee the old name doesn't sneak back in via copy-paste.
- Lenient `nfc_normalized` parsing (accept native bool *or* the strings
  `"true"`/`"false"`) is worth it because the script-emitted JSONL uses
  a native bool but a hand-edited JSONL would naturally stringify it;
  rejecting hand-edits at the type level is friction with no safety
  payoff (the orthographic gate catches the actual NFC violations).

## 2026-04-30T08:55:56Z — Scribe session log + orchestration + decision merge

**Team update:** Linus's human_fetch probe implementation (73/73 tests, full Stage-0-as-checkpoint-0 integration) + Rusty's approval gate have been transcribed into:
- `.squad/orchestration-log/2026-04-30T08-55-56Z-linus.md` (this work summary)
- `.squad/orchestration-log/2026-04-30T08-55-56Z-rusty.md` (Rusty's 10-point review)
- `.squad/log/2026-04-30T08-55-56Z-human-fetch-translation-eval.md` (session log)
- `.squad/decisions.md` (merged from inbox; added full decision + approval + user directive)

**Decision inbox status:** `copilot-directive-20260430T083706Z.md`, `linus-human-fetch-translation-eval.md`, `rusty-human-fetch-translation-review.md` → merged and deleted.

**Key archival:** Stage 0 is checkpoint 0 in a unified eval series; human_fetch is the trusted parallel source for baseline+drift tracking (en→haw, haw→en bidirectional, char-F1 baseline, safe-to-miss, never averaged, hash-only output, eval_eligible=True training_eligible=False).

---

## 2026-05-01 — Stage 1 training data readiness audit

**User directive:** Prepare and verify training input data for the next Stage 1 run. Config paths should be unambiguous and compatible with the runner.

**Implementation summary:**

- **Audit:** `data/stage1/fineweb2_haw/train.jsonl` — 95,507 rows, zero missing/empty `text`, 100% NFC, all `prototype_only=True`, `release_eligible=False`, source `fineweb2_haw`. Eval `data/evals/fineweb2_haw/dev.jsonl` — 621 rows, same provenance flags.

- **`code/configs/llama31_8b_a100.json`:** `train_path` updated from stale `../data/stage1/stage1.jsonl.gz` to `../data/stage1/fineweb2_haw/train.jsonl`; `eval_path` wired to `../data/evals/fineweb2_haw/dev.jsonl`; `eval_steps` set to 200; notes updated.

- **`code/llm_hawaii/train.py`:** `build_training_args` now wires `eval_strategy="steps"` + `eval_steps` when both `cfg.eval_path` and `cfg.eval_steps` are non-null. `run_training` loads `eval_dataset` when `eval_path` is set and passes it to `Trainer`.

- **`code/tests/test_data.py`:** +9 new tests (no ML deps for config tests): `test_iter_jsonl_bad_json`, `test_iter_jsonl_empty_lines_skipped`, `test_normalize_text_nfc_idempotent`, `test_normalize_text_unknown_form`; new `TestTrainConfig` class with 5 tests covering config load, unknown-key rejection, eval pairing, roundtrip. Total suite 111 → 120, same 3 pre-existing ML-dep errors.

- **`docs/data-readiness-stage1.md`:** New doc — counts/hashes/status only, no raw text.

- **`.squad/decisions/inbox/linus-training-data-readiness.md`:** Decision record with chosen path, rationale, caveats, and Basher coordination note.

**Key patterns established:**

- `stage1.jsonl.gz` is the post-cleaning multi-source canonical trainer output (81,117 rows, 6-field slim schema); `fineweb2_haw/train.jsonl` is the pre-cleaning FineWeb-only input (95,507 rows, 22-field rich schema). Both are off-git. Switch between them by changing `train_path` in the config — `data.py` handles `.gz` transparently.
- Eval-during-train is safe-no-op: wired only when BOTH `eval_path` AND `eval_steps` are non-null. No silent skips.
- Config tests (`TestTrainConfig`) require no ML deps — fast to run anywhere without GPU environment.
- Paths in JSON configs are relative to `code/` (run convention: `python -m llm_hawaii.train --config configs/<name>.json`).

**Validation:** ✅ py_compile clean on all modified files, ✅ 120/120 non-ML tests pass, ✅ 3 pre-existing ML-dep errors unchanged.

## Learnings

- `data/` is gitignored. Audit results belong in `docs/` (counts/status/hashes only) or the decision inbox, never as committed JSONL/text.
- For eval-during-train gating: check both `eval_path` AND `eval_steps` before passing `eval_strategy` to `TrainingArguments`. Setting one without the other produces a silent no-op or a Trainer error.
- Newer HF Trainer uses `eval_strategy`; older versions use `evaluation_strategy`. Document this caveat explicitly so the runner can adapt without source changes.
- `TestTrainConfig` tests (config load/roundtrip/unknown-key) are zero-dep and very fast — add them first when validating config schema changes.

---

## 2026-04-30T09:15:54Z — Orchestration checkpoint: Stage 1 training input audit APPROVED + merged

**Orchestration context:** Scribe merged training input audit decisions into `.squad/decisions.md` and archived orchestration logs. 

**Status:** ✅ Stage 1 training readiness complete. 
- Training input `data/stage1/fineweb2_haw/train.jsonl` (95,507 rows) validated and wired in `code/configs/stage1_fineweb2_haw.json`
- Eval input `data/evals/fineweb2_haw/dev.jsonl` (621 rows) validated
- Basher's training runner (config-relative paths, `--preflight`, `--resume-from-checkpoint`, run report v1) ready for compute
- Basher's test fix (`_DummyTokenizer`) integrated; 103 tests pass
- Orchestration logs written to `.squad/orchestration-log/2026-04-30T09-15-54Z-*.md`
- Session log: `.squad/log/2026-04-30T09-15-54Z-training-readiness.md`

**Next:** Ready for compute environment preflight + Stage 1 CPT run.


---

## 2026-05-01T00:19:05Z — Stage 2 Readiness Checkpoint (Tatoeba Adapter Landed)

**Team Orchestration:** Scribe session; Ralph Round 1 concluded.

**Your outcome:** Tatoeba en↔haw adapter with alignment_method="manual", register="unknown", 2025-05-01 pinned dump, 41/41 tests pass.

**Team outcomes:** Frank landed Bible adapter (18 tests), Basher landed SFT trainer + config, Rusty landed eval gate (29 tests).

**Decisions merged:** Tatoeba alignment/register choices (manual + unknown), Bible edition pin in JSON, SFT custom collator (no TRL), eval gate live, Colab GPU assessment.

**Team integration points:** 
- Frank needs your pin for Hawaiian edition in `source_registry.json` to unblock live fetcher.
- Rusty's eval gate consumes manifest fields: `sha256_pair`, `sha256_normalized`, `sha256_normalized_haw`, `sha256_normalized_en`.
- Your adapter pattern (alignment_method + register in schema) sets template for Stage 2 adapters.

**Next:** Pin Hawaiian edition; confirm WEB as English anchor (or swap for KJV).


---

## 2026-05-01 — Stage 2 manifest ingestion + SFT template rotation (issues #18 + #20)

**Issues:** #18 (wire adapters into 320 execute path), #20 (template paraphrases for 330)

**Implementation summary:**

- **`scripts/320_build_stage2_manifest.py`** — Replaced `iter_stage2_pairs()` stub with `ingest_candidates()` that reads `data/stage2/candidates/*.jsonl` (or explicit `--candidates` paths). Added `assign_split()` using SHA-256 hash mod (default modulus 10 → ≈10% dev). Added `--candidates`, `--dev-modulus` CLI args. Build provenance now includes per-source row counts and candidate-file SHA-256s. Added `_rel()` helper for safe path display (avoids `relative_to` crash when globals are patched in tests).

- **`scripts/330_emit_stage2_sft_jsonl.py`** — Added `DEFAULT_TEMPLATES_PATH`, `load_templates()`, `pick_template()`, `resolve_instructions()`. Template rotation is deterministic by SHA-256 hash of pair_id mod len(templates). EmitConfig gains `templates` field. Summary output reports `templates_loaded` and `template_counts`. Added `--templates PATH` / `--no-templates` CLI flags.

- **`data/stage2/templates.json`** (gitignored) — 5 paraphrases per direction. Hawaiian-side prompts use U+02BB ʻokina throughout. **Rusty review requested** on Hawaiian-language `haw->en` paraphrases.

- **`code/tests/fixtures/stage2/templates.json`** (committed) — Tiny 3-per-direction fixture for unit tests. Contains `_comment` key marking it as test-only.

- **Tests** — 42 new tests: 18 in `test_stage2_manifest.py` (assign_split, ingest_candidates, CLI execute/dry-run) and 24 in `test_stage2_sft_templates.py` (load_templates, pick_template, resolve_instructions, build_directional_row, CLI wiring). 305 total, pre-existing error unchanged.

**Smoke test:**
- `python scripts/320_build_stage2_manifest.py --execute` → 5 rows (from bible fixture candidates), build_manifest.json written
- `python scripts/330_emit_stage2_sft_jsonl.py --dry-run --splits train,dev` → pairs_kept=5, rows_emitted=10, templates_loaded=true

**Key patterns:**
- Module globals used as output paths: tests can safely patch them for isolation, but argparser help strings must use a safe `_rel()` wrapper to avoid `relative_to` crash when patched path is outside REPO_ROOT.
- `review-pending` split replacement happens at ingest time (before schema validation), so validators see a real split value.
- Template fixture under `code/tests/fixtures/` must include a `_comment` key to distinguish it from a production template file on visual inspection.

## Learnings
- When module-level path constants are used both in argparser help strings (`f"...{PATH.relative_to(ROOT)}..."`) and as write targets, patching them in tests requires the help string to be tolerant of paths outside ROOT. A `_rel(path)` helper that catches `ValueError` is the correct pattern.
- Template rotation: `int(sha256(pair_id)[:8], 16) % len(templates)` is a clean one-liner that is stable across languages/runtimes (pure hex arithmetic). Document modulus in the fixture comment so future readers know it's not magic.
- Hawaiian-language instruction paraphrases should always be flagged for Rusty (NLP Researcher) review before any release, even when they look grammatically correct. The bar is higher than English-language prompts because errors are harder to spot in code review.

---

## 2026-05-01 — Stage 2 manifest ingestion & SFT template rotation [COMPLETED]

**Issues:** #18, #20

**Orchestration update:** This round focused on Stage 2 readiness. Ralph identified three blockers; you handled #18/#20 with manifest ingestion and template rotation.

**Summary:**
- `scripts/320_build_stage2_manifest.py --execute` now ingests candidate JSONL from `data/stage2/candidates/`, validates rows, performs deterministic 90/10 split via SHA256 mod 10, writes manifest with provenance.
- `scripts/330_emit_stage2_sft_jsonl.py` loads and rotates templates by pair_id hash (deterministic for reproducibility).
- 12 tests added; all passing.
- **Rusty note:** Two `haw->en` templates are in Hawaiian; flagged for orthography review before data release.
- **Frank note:** Bible adapter new candidates → rebuild manifest with `scripts/320_build_stage2_manifest.py --execute`.

**Next:** Basher's lineage CI (issue #24) also now complete. Stage 2 readiness depends on Rusty's review of issue #19.

## 2026-05-01 — Stage 2 Alignment-Quality Policy Integration (Issue #19)

**Status:** CROSS-AGENT UPDATE — Action Required

Rusty's manifest builder now scores all rows and emits policy fields. Linus's adapters do NOT need to emit policy fields. Structural-only contract is maintained. When adding new adapters, ensure schema-compatibility tests use `apply_policy(dict(row))` before `validate_row` — see `test_bible_adapter.py` and `test_tatoeba_adapter.py` for the pattern. No changes required to existing adapters.

**Reference:** `code/tests/fixtures/stage2/templates.json` corrected for haw→en template direction.


## 2026-05-01T00:59:31Z — Baibala Hemolele 1839 Edition Pin Confirmed (Issue #16)

**Status:** COMPLETED — Edition pinned; Frank unblocked

**Issue:** #16

**What:** Live-confirmed the canonical Baibala Hemolele source on baibala.org and pinned the 1839 edition in `source_registry.json`.

**Key findings:**
- **Platform:** baibala.org runs **Greenstone Digital Library** software
- **Correct URL pattern:** `https://baibala.org/cgi-bin/bible?e=d-1off-01839-bible--00-1-0--01839-0--4--Sec---1--1haw-Zz-1-other---20000-frameset-main-home----011-01839--210-0-2-utfZz-8&d={greenstone_oid}.{chapter}&d2=1&toc=0&exp=1-&gg=text`
- **Verse anchor format:** `<a name="a{book_name_lower}-{chapter}-{verse}"></a>` (confirmed on Genesis 1 and John 3)
- **Rights:** 1839 imprint is US public domain; digitization copyright 2003-2008 covers only digitization, not underlying text
- **ToS/provenance:** Captured to `data/raw/baibala-hemolele-1839/20260501/tos_snapshot.html`

**Files changed (working tree, not committed):**
- `data-sources/bible/source_registry.json` — edition pinned with `greenstone_oid` and `book_name_lower` for all 66 books
- `data-sources/bible/README.md` — documented URL, rights, ToS path, parser contract
- `scripts/206_fetch_baibala_raw.py` — render_url() extended; parse_baibala_chapter_html() docstring updated with confirmed anchor pattern
- `scripts/322_build_bible_candidates.py` — build_rows_for_chapter() now passes greenstone_oid
- `code/tests/test_bible_adapter.py` — test_execute_refused_without_edition_pin updated (pin now set)
- `data/raw/baibala-hemolele-1839/20260501/` (gitignored) — Genesis 1, John 3 sample HTML + ToS + provenance.json

**Unblocking Frank:** Parser implementation (`parse_baibala_chapter_html()`) now ready to proceed using confirmed anchor pattern. Sample HTML available locally for development.

**Next:** Frank implements parser and runs live fetch when ready.

**Artifacts:**
- Orchestration log: `.squad/orchestration-log/2026-05-01T00-59-31Z-linus-baibala-pin.md`
- Decision merged to `.squad/decisions.md`
