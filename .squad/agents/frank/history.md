# Frank — History

## Core Context

- **Project:** A prototype/learning project for adapting an existing multilingual LLM to Hawaiian, including data, model choices, infrastructure, evaluation, and costs.
- **Role:** Hawaiian Data Collector
- **Requested by:** yashasg
- **Joined:** 2026-04-29T05:38:40Z
- **Tech stack:** Python raw-data tooling installed through `scripts/setup.sh` / `requirements.txt`; current stack includes `requests`, `tenacity`, `warcio`, `trafilatura`, `selectolax`, `scrapy`, `scrapy-warc`, `internetarchive`, `wayback`, `cdx_toolkit`, `yt-dlp`, and `datasketch`.

## 2026-04-29T10:13:35Z — Manual Micro-Eval Planning Complete (Independent of FineWeb Fetch)

W1 manual micro-eval TSV spec finalized and repo scaffold committed. **Planning does not block on or depend on your FineWeb-2 raw fetch.** Eval planning is independent; row authoring can start in parallel. Manual eval is a separate eval-only source using hand-authored Hawaiian content, not web-sourced.


## 2026-04-29T10:18:43Z — Dataset Taxonomy Finalized: FineWeb-2 Eval Paths Locked

**From:** Scribe (via Orchestration)

**Update:** Final dataset taxonomy adopted. FineWeb-2 `haw_Latn` eval artifacts rooted at `data/evals/fineweb2_haw_test/`:
- Collected train (95,507 rows) → `data/stage1/` after deduping against evals
- Test dev (710 rows, ~80%) → `data/evals/fineweb2_haw_test/dev/` (checkpoint monitoring)
- Test holdout (177 rows, ~20%) → `data/evals/fineweb2_haw_test/holdout/` (frozen, final eval only)

**For your FineWeb-2 collection work:**
- When fetching completes, coordinate with Linus to split test set and write to `data/evals/fineweb2_haw_test/{dev,holdout}/`.
- Train split (95,507) does not go to `data/evals/`; Linus dedupes it into `data/stage1/`.

**Reference:** `.squad/decisions.md` → "Decision: Final Dataset Taxonomy — `evals` / `stage1` / `stage2` / `final`".


### 2026-04-29 — FineWeb-2 haw_Latn full fetch
- Full pull complete via rows API (not parquet, pyarrow not installed; did NOT touch requirements.txt).
- On-disk counts match plan exactly: 95,507 train + 887 test = 96,394 rows. Zero dup ids per split, zero train/test id overlap. Raw whitespace tokens: train 67,792,427 / test 626,123 / total 68,418,550. Chars total 326,629,051.
- HF datasets-server `/rows` rate-limits hard on this dataset: even `--rate-limit-seconds 1` got 429s after ~33 pages. Stable recipe = `--rate-limit-seconds 3.0` after a multi-minute cooldown, sustained ~1,750 rows/min.
- Added `--start-offset N` flag to `scripts/205_fetch_fineweb2_haw_raw.py` for safe resume (script appends; naive rerun would dup). Rows-API path only.
- Smoke artifacts archived to `data/raw/fineweb2_haw/_smoke_validation_backup_20260429/` before the full fetch — raw bytes preserved per provenance policy.
- Decision note: `.squad/decisions/inbox/frank-fineweb2-fetch.md` (incl. parquet/pyarrow tradeoff for Linus).
- Per-row schema in `data/raw/fineweb2_haw/<date>/{split}.jsonl` carries `text`, `fineweb2_row_id`, `cc_dump`, `cc_date`, `cc_file_path`, `source_url`, `language*`, `raw_whitespace_token_count`, `license_*`, `prototype_only=true`, `release_eligible=false`.

## 2026-04-29 — Stage 2 parallel fetch-plan inventory landed (issue #10)

Added `data-sources/stage2-parallel-fetch-plan.json` as the per-source fetch-plan
layer for Stage 2 parallel/comparable Hawaiian-English candidates. Issue #10
acceptance criteria mapped explicitly:
- Source inventory has exact dataset ids/URLs and rights notes for 13 candidate
  sources across `parallel-verse` / `parallel-sentence` / `comparable-aligned` /
  `dictionary-example`, plus 5 excluded entries.
- Every source row carries `acquisition_plan.dry_run_default: true` and
  `execute_flag_required` — fetch plans are dry-run by default, period.
- `alignment_type` tag matches `docs/data-pipeline.md` §"Required tagging" exactly:
  no `parallel-*` source goes unlabeled; comparable Wikipedia/Wikisource use
  `comparable-aligned`; dictionary examples use `dictionary-example`; everything
  else is in `deferred_or_excluded`.
- **JW300 is recorded as `excluded_pending_verification` only.** Listed solely so
  future agents do not silently re-add it. No verified status, no fetch path,
  explicit "do not fetch" language.
- Hard-escalate cultural categories, social-media bilingual, ungrounded LLM
  synthesis, and arbitrary CC slices are excluded with reason strings tied to
  `docs/data-pipeline.md` §52 / Tier E.

Docs touch: one pointer line under `docs/data-pipeline.md` §"Stage 2 source
tiers" referring to the new artifact. No tier-table content changed.

What I deliberately did *not* do:
- Did not modify `data-sources/hawaiian-data-sources.json` (routing config; the
  new file is the *fetch-plan* layer the routing config did not carry).
- Did not fetch any bytes; did not touch `requirements.txt`; did not add scripts.
- Did not pin the Bible edition or Pukui-Elbert/Andrews edition — both flagged
  as open questions for Linus in the artifact.
- Did not include `bible-haw-baibala` as `verified_endpoint`: it is
  `pending_rights_review` until Linus pins the edition.

Open questions surfaced in the artifact:
- Linus: pin Hawaiian Bible edition + English PD edition; mined-data rights
  posture for NLLB; PD vs modern Pukui-Elbert.
- Rusty: LaBSE threshold tuning for comparable-aligned Wikipedia/Wikisource.
- Frank (self): endpoint-verification sweep for the `pending_endpoint_check`
  sources is a follow-up, not a blocker for this inventory landing.

Decision inbox: `.squad/decisions/inbox/frank-stage2-parallel-fetch-plan.md`.

## 2026-04-29 — Wikisource ProofreadPage W1 capture wired into 102/202

Verified via metadata-only `wikisource.org` API probes that the
ProofreadPage extension is installed and exposes per-page quality on
`prop=proofread` for `ns=104` (`Page:`) pages: `{quality 0..4,
quality_text in {Without text, Not proofread, Problematic, Proofread,
Validated}}`. `Validated` (q=4) is the natural W1 signal.

**Hard caveat:** for `ns=0` (main) pages — which is *every* one of the
159 Hawaiian-category pages today — the API returns no `proofread` key.
ProofreadPage only surfaces quality on Page: subpages; main-page quality
is rendered by aggregating transcluded Page: subpages client-side. So
the field is currently `null` on the entire existing Hawaiian plan, and
honest W1 selection on Hawaiian Wikisource needs either a 102 mode that
enumerates `ns=104` Hawaiian Page: pages directly or a future
scantranscluded/transclusion-walk roll-up. I captured the surface anyway
so the day either of those lands the field populates without further
adapter changes.

Surgical changes (fetch side only — no W1 / extraction / manifest
changes; that's Linus's call):
- `scripts/102_collect_hawwikisource.py`: after `--enumerate`, batched
  `prop=proofread&pageids=...` follow-up (50/chunk, polite sleep)
  annotates every page_plan row with `proofread_quality` and
  `proofread_quality_text` (uniform schema; null on ns=0).
- `scripts/202_fetch_hawwikisource_raw.py`: per-page URL now uses
  `prop=revisions|proofread` (single combined call, zero extra HTTP).
  Both single-page and batch fetchers record the per-page quality into
  `ProvenanceRecord.source_specific_ids` (and a
  `proofread_validated_page_ids` list of W1 candidates on the bundle
  row). `_load_page_plan` forwards any seeded values from 102 under
  `*_seeded` keys; live fetch-time value remains source of truth.
- `docs/data-pipeline.md`: one paragraph explains the new fields, the
  `Validated == W1` mapping, and the ns=0 limitation.

Validated by `py_compile`, a small live enumerate (limit=3,
namespaces=0,104) showing uniform null fields and a working "skip when
no ns=104 rows" path, and a 202 dry-run on the existing 159-row plan
confirming the new `prop=revisions|proofread` URL. No raw bytes
committed; existing page_plan preserved.

Decision note: `.squad/decisions/inbox/frank-wikisource-quality.md`.

## 2026-04-29T21:34:03Z — Wikisource ProofreadPage W1 quality capture wired into 102/202 (Session complete)

**From:** Scribe (orchestration checkpoint)

**Outcome:** ✓ Instrumentation complete; decisions recorded; ready for Linus feedback.

Verified via metadata-only `wikisource.org` API probes that ProofreadPage extension exposes per-page quality on `prop=proofread` for `ns=104` (`Page:`) pages. Updated adapters and docs.

**Key findings:**
- ProofreadPage quality (`ns=104`) + quality_text mapping confirmed; "Validated" = Q4 (natural W1 signal)
- Hard caveat: current Hawaiian plan all ns=0; no direct W1 signal without transclusion walk
- Updated 102/202 to capture metadata; 202 now requests `prop=revisions|proofread` (combined, no extra HTTP)
- Docs updated; no data changes; existing artifacts preserved

**Validation:** py_compile clean; dry-run + small enumeration passed; null handling on ns=0 confirmed.

**Open questions for team:**
1. Linus: how to surface `proofread_status` into W1 path? Separate slice or row-level flag?
2. Should 102 enumerate ns=104 Hawaiian-tagged Page: pages directly or wait for transclusion walk?

**Session artifacts:**
- Orchestration log: `.squad/orchestration-log/2026-04-29T21-34-03Z-frank.md`
- Session log: `.squad/log/2026-04-29T21-34-03Z-wikisource-w1-quality.md`
- Decisions merged to `.squad/decisions.md`
