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
