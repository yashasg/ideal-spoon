# Linus — History

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
