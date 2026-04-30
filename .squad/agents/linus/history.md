# Linus — History

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
