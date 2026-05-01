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

## 2026-04-29T22:56Z — Wikisource quality=4 (Validated) eval scan: zero reachable rows

User asked to fetch Validated Hawaiian Wikisource for eval to size the
volume. Wrote a one-off, additive scanner: `scripts/106_scan_hawwikisource_quality4.py`.
Output goes to a fresh path `data/raw/hawwikisource_quality4_candidates/<date>/`
(gitignored under `/data/`). Existing W1/Stage 1 artifacts untouched
(`data/raw/hawwikisource/fetch.jsonl` 42 lines, `page_plan.jsonl` 159
lines — byte-for-byte preserved). Eval-candidate-only by construction;
manifest carries `eval_candidate_only=true` and a non-replacement note.

**Method:** for each of the 159 ns=0 pages in `page_plan.jsonl`, GET
`prop=templates&tlnamespace=104` (with continuation, polite 1.5s rate
limit, 429-aware retry-after backoff), aggregate unique Page: titles,
batch `prop=proofread` 50 titles/call, filter `quality_text=="Validated"`.

**Counts (final):**
- main_ns pages inspected: 159 / 159
- unique Page: ns titles discovered via transclusion: **0**
- proofread quality probes: 0
- validated (q=4): **0**
- content records written: 0
- chars/bytes/tokens: 0 / 0 / 0

**Sanity cross-checks** (one-off probes, no artifacts):
- `Category:ʻŌlelo Hawaiʻi` cmnamespace=104 → 0 members
- `Category:ʻŌlelo Hawaiʻi` cmnamespace=106 (Index:) → 0 members
- `srsearch=haw, srnamespace=104` → top 5 hits are Sundanese / Old
  Irish / Cebuano / Hiligaynon (false positives on the `haw` substring),
  no Hawaiian Page: pages.

**Conclusion / volume estimate:** Validated (q=4) Hawaiian Wikisource
material reachable today via the Hawaiian tagging path is **zero rows /
zero chars / zero tokens**. The 159 main-ns pages are hand-typed
mele/songs/portal pages with no scan-backed Page: subpages transcluded.
This is the same shape as the prior 2026-04-29T21:34Z finding, now
quantitatively confirmed end-to-end. The metadata field captured by
102/202 will continue to populate `null` until either (a) Hawaiian
contributors upload Index:/Page: scans, or (b) we widen the discovery
path to non-category sources (e.g., scanned Hawaiian-language books on
Wikimedia Commons indexed manually).

**Artifacts written (local only):**
- `data/raw/hawwikisource_quality4_candidates/20260429/manifest.json`
- `data/raw/hawwikisource_quality4_candidates/20260429/per_main_stats.jsonl` (159 rows)
- `data/raw/hawwikisource_quality4_candidates/20260429/validated_pages.jsonl` (0 rows)
- `data/raw/hawwikisource_quality4_candidates/20260429/all_quality_rows.jsonl` (0 rows)
- `data/raw/hawwikisource_quality4_candidates/20260429/content/` (empty)

**Validated** by `python3 -m py_compile` and a real end-to-end run on
all 159 main pages with polite 1.5s rate limit and 429-aware backoff.
No raw text printed; no commits.

Decision note: `.squad/decisions/inbox/frank-quality4-fetch.md`.

## 2026-04-29T22:58:20Z — Wikisource quality=4 eval scan session recorded

**From:** Scribe (orchestration checkpoint)

**Outcome:** ✓ Zero-volume result recorded; decisions merged; session logs written.

Quality=4 (Validated) Hawaiian Wikisource scan quantitatively confirmed the metadata-only finding: **0 reachable rows / 0 chars / 0 tokens** via the Hawaiian-category transclusion path. The transclusion-walk method is sound and will auto-populate if Hawaiian contributors add Index:/Page: scans in the future.

**Session artifacts:**
- Orchestration log: `.squad/orchestration-log/2026-04-29T22:58:20Z-frank.md`
- Session log: `.squad/log/2026-04-29T22:58:20Z-wikisource-quality4-scan.md`
- Decisions merged to `.squad/decisions.md`

**Cross-team status:**
- Linus: W1-from-Wikisource path confirmed empty today; no candidate seeding this round
- Rusty: no language-fit work needed; zero candidate text
- User: non-replacement directive honored; scan is additive only

## 2026-05-01 — Stage-2 Bible verse-id adapter scaffolding (issue #16)

Landed the first real Stage-2 source adapter contract for the
(Baibala Hemolele × PD English Bible) verse-aligned pair. Live fetch
is intentionally inert pending Linus' edition pin; everything else on
the issue acceptance is in place and tested.

**Architecture decisions:**
- Two-script split mirroring the 100/200/300 numbering: `206_fetch_baibala_raw.py`
  owns raw HTTP + provenance, `322_build_bible_candidates.py` owns
  verse-id pair JSONL emission. Keeps fetch/parse decoupled and lets
  fixture-backed tests exercise the candidate contract without any
  network or HTML samples.
- Source registry as JSON (`data-sources/bible/source_registry.json`)
  rather than Python module: edition pins are config, not code, and
  Linus can edit `edition_pinned_by` without touching scripts.
- `--execute` on the fetcher is **triple-gated**: (a) registry has a
  non-null `edition_pinned_by`, (b) `--confirm-edition` matches the
  registry edition_or_version, (c) `--tos-snapshot <path>` points at
  an existing file. Refuses with rc=2 and a clear message otherwise.
- ʻokina canonicalization (U+2018/U+2019/ASCII apostrophe → U+02BB)
  applied **before** sha256 / pair_id computation so pair hashes are
  stable across upstream rendering quirks. Mirrors
  `code/llm_hawaii/stage2_quality.py::OKINA_MISENCODINGS`.
- Stdlib-only, no new requirements; scripts run on a fresh checkout.

**Patterns reused:**
- `ProvenanceRecord` dataclass shape from `202_fetch_hawwikisource_raw.py`
  (extended with `edition_or_version` + `tos_snapshot_path`).
- `compute_pair_hash()` imported as the canonical pair-hash helper from
  `320_build_stage2_manifest.py`; tests assert the candidate's
  `sha256_pair` matches that helper byte-for-byte.
- Dry-run-by-default + hard `--limit` cap (5 chapters; ceiling 200) per
  the safety posture in `data-sources/stage2-parallel-fetch-plan.json`.

**Key file paths:**
- `data-sources/bible/source_registry.json` — pinned pair + 66-book canon.
- `data-sources/bible/README.md` — run order, rights/boundaries.
- `scripts/206_fetch_baibala_raw.py` — raw fetcher (gated --execute).
- `scripts/322_build_bible_candidates.py` — verse-id pair builder.
- `code/tests/fixtures/bible/{haw,eng}/GEN_1.txt` — 5-verse synthetic
  fixture (clearly labelled NOT real Bible content).
- `code/tests/test_bible_adapter.py` — 18 tests, stdlib only.

**Validation:**
- 18/18 new tests pass; full `code/tests` suite still green.
- `322 --execute` emits 5 rows to `data/stage2/candidates/bible.jsonl`
  (correctly gitignored under `/data/`).
- `320 --check --strict --manifest-in data/stage2/candidates/bible.jsonl`
  → `schema_violations: []`, rc=0.
- GitHub issue #16 progress comment posted (comment id 4357023441).

**Open for Linus / future agents:**
1. Pin edition in `source_registry.json` (`edition_pinned_by`,
   `edition_pinned_at_utc`).
2. Live `baibala.org` URL/CGI confirmation; today's
   `url_template_status="placeholder_pending_endpoint_check"`.
3. ToS snapshot capture under
   `data/raw/baibala-hemolele-1839/<YYYYMMDD>/tos_snapshot.html`.
4. Real `parse_baibala_chapter_html()` implementation (currently
   raises NotImplementedError with a documented contract).
5. Versification reconciliation across editions; bulk run to hit
   "few thousand verse-aligned rows" acceptance.

**User preferences honored:**
- No corpus payloads committed (verified via `git check-ignore`).
- No git history changes; all work left in working tree per task spec.
- Synthetic fixtures over real PD Bible text — avoids any rights
  ambiguity for the test fixture.

---

## 2026-05-01T00:19:05Z — Stage 2 Readiness Checkpoint (Bible Adapter Landed)

**Team Orchestration:** Scribe session; Ralph Round 1 concluded.

**Your outcome:** Bible verse-id adapter contract scaffolded/tested/dry-run-clean. Edition pin in `source_registry.json` (not code), triple-gated `--execute`, ʻokina canonicalization locked in, synthetic test fixtures, 18/18 tests pass.

**Team outcomes:** Linus landed Tatoeba adapter (41 tests), Basher landed SFT trainer + config (target-only masking), Rusty landed eval gate (29 tests).

**Decisions merged:** Edition pin in JSON convention, triple-gated fetcher gate pattern, Tatoeba alignment_method="manual", SFT custom collator (no TRL), eval gate live, Colab GPU assessment conditional.

**Next:** Linus pins Hawaiian edition in `source_registry.json` to unblock your live fetcher.


---

## 2026-05-01 — Stage 2 coordination [AWARENESS]

**Orchestration:** Stage 2 readiness round complete (issues #18/#20/#24 resolved).

**Action for you:**
- If Bible adapter produces new candidates for Stage 2, run `python scripts/320_build_stage2_manifest.py --execute` to rebuild the manifest (deterministic 90/10 split, new layout enforced).
- Manifest builder globs `data/stage2/candidates/*.jsonl` by default; your adapter writes there.

## 2026-05-01 — Stage 2 Alignment-Quality Policy Integration (Issue #19)

**Status:** CROSS-AGENT UPDATE — Template Fixture Corrected

Rusty corrected the haw→en paraphrase templates in `code/tests/fixtures/stage2/templates.json`. The committed fixture had orthographically-inverted instructions (phrasing translation direction backwards). All haw→en paraphrases now correctly phrase the direction as `kēia ʻōlelo Hawaiʻi … i ka ʻōlelo Pelekānia`. No adapter logic changes required. Bible adapter maintains structural output contract.

