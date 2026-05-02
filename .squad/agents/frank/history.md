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

## 2026-05-01T00:59:31Z — Baibala Hemolele 1839 Edition Pin Confirmed (Issue #16)

**Status:** UNBLOCKING NOTIFICATION — You are now unblocked to implement `parse_baibala_chapter_html()`

**From:** Linus (Data Engineer)

**What:** Edition pinned; live-confirmed Greenstone URL structure, verse anchors, and rights.

**Key findings:**
- Platform: Greenstone Digital Library (baibala.org)
- Correct URL pattern: `https://baibala.org/cgi-bin/bible?e=d-1off-01839-bible--00-1-0--01839-0--4--Sec---1--1haw-Zz-1-other---20000-frameset-main-home----011-01839--210-0-2-utfZz-8&d={greenstone_oid}.{chapter}&d2=1&toc=0&exp=1-&gg=text`
- Verse anchors: `<a name="a{book_name_lower}-{chapter}-{verse}"></a>` (confirmed on Genesis 1 and John 3)
- All 66 books mapped with `greenstone_oid` and `book_name_lower` in `source_registry.json`
- Rights: 1839 text is US public domain; no scraping prohibition found

**Your next steps:**
1. Implement `parse_baibala_chapter_html()` using the confirmed anchor pattern (see updated docstring in `scripts/206_fetch_baibala_raw.py`)
2. Sample HTML available locally: `data/raw/baibala-hemolele-1839/20260501/haw_genesis_1.html` and `haw_john_3.html`
3. Once parser is ready, run: `206_fetch_baibala_raw.py --execute --side haw --book GEN --chapters 1-3 --confirm-edition baibala-hemolele-1839 --tos-snapshot data/raw/baibala-hemolele-1839/20260501/tos_snapshot.html`

**Artifacts:**
- Orchestration log: `.squad/orchestration-log/2026-05-01T00-59-31Z-linus-baibala-pin.md`
- Decision merged to `.squad/decisions.md`


## 2026-05-01 — Issue #16: Live Baibala HTML parser implemented

### What landed
- `parse_baibala_chapter_html()` in `scripts/206_fetch_baibala_raw.py` —
  regex-based, stdlib-only, terminates each verse at the first `<br />`
  (cleanly avoids the trailing "next chapter >" navigation table that
  Greenstone appends after the last verse). Filters by
  `book_name_lower` and `chapter`; canonicalizes U+2018/U+2019/ASCII
  apostrophe → U+02BB; NFC-normalizes; collapses whitespace.
- `scripts/322_build_bible_candidates.py` — new `--from-raw YYYYMMDD`
  and `--haw-raw-dir <path>` modes. `build_rows_from_raw_haw()` parses
  raw haw chapter HTML (file convention `<BOOK_CODE>_<CHAPTER:03d>.html`,
  matching the live fetcher's output) and pairs against the eng
  fixture/dir. Rows carry `notes=...src=raw_html` so downstream can tell
  fixture-derived rows apart from raw-fetch-derived rows.
- New tiny synthetic HTML fixture at
  `code/tests/fixtures/bible/haw_html/GEN_001.html`. Mirrors the live
  Greenstone anchor pattern but contains the same synthetic
  Hawaiian-flavored lines as the existing text fixture — no real Bible
  content committed.
- 12 new tests added (30 total in `test_bible_adapter.py`, all green):
  parser correctness, NFC + ʻokina canonicalization, ASCII-apostrophe
  canonicalization (covers the live 1839 `hana'i` case), chapter
  filter, book-name filter, `&para;` strip, idempotency on duplicate
  anchors, `--haw-raw-dir` and `--from-raw` CLI paths, and
  schema-conformance of raw-derived rows via `manifest.apply_policy` +
  `manifest.validate_row`.

### Verified end-to-end
- Live samples Linus committed under
  `data/raw/baibala-hemolele-1839/20260501/` parse cleanly:
  - `haw_genesis_1.html` → 31 verses, all anchored
  - `haw_john_3.html` → 36 verses, all anchored
  - `GEN_001.html` (live fetcher output) → 31 verses
- `python scripts/322_build_bible_candidates.py --execute --haw-raw-dir
  data/raw/baibala-hemolele-1839/20260501 --fetch-date 20260501` →
  5 rows (paired against eng fixture verses 1-5 of the synthetic
  fixture, since that's all the eng side has in-tree).
- `python scripts/320_build_stage2_manifest.py --execute --candidates
  data/stage2/candidates/bible.jsonl` then `--check --strict` → rc=0.

### What I deliberately did NOT do
- No corpus text committed. `data/raw/...` and `data/stage2/...` stayed
  gitignored throughout (`git check-ignore` confirmed).
- Did NOT implement an English-side raw fetcher. WEB url_template is
  still `placeholder_pending_endpoint_check`; the eng side stays on the
  in-tree synthetic fixture for now. Pairing 5 verse rows against the
  full 31-verse Genesis 1 raw haw side is the proof-of-pipeline; a
  real bulk run needs a pinned WEB endpoint first.
- Did NOT touch `requirements.txt`. Parser is `re` + `html` + stdlib.
- Did NOT commit/push. Working tree only, per task spec.

### Open follow-ups for next round
1. Pin English WEB url_template (Linus / new spawn): Frank can write the
   fetcher once the URL pattern is confirmed.
2. Versification reconciliation pass once both sides fetch (Hebrew vs
   LXX Psalms numbering, etc.).
3. Bulk fetch: the parser is ready for the "few thousand verse-aligned
   rows" acceptance criterion the moment the eng side endpoint lands.

## Learnings

- **Greenstone Baibala HTML pattern:** verse anchors are
  `<a name="a{book_name_lower}-{chapter}-{verse}"></a>` and each verse
  terminates at the first `<br />`. Using `<br />` as the body
  terminator (rather than the next anchor / `</table>`) cleanly avoids
  the inner navigation `<table>` that Greenstone appends with a
  "next chapter >" link after the final verse.
- **The 1839 imprint uses ASCII apostrophes**, not curly U+2018/U+2019
  and not U+02BB — so `'` → `\u02bb` canonicalization is load-bearing
  on the haw side (e.g. `hana'i` → `hanaʻi`). The existing
  `OKINA_MISENCODINGS = ("\u2018", "\u2019", "'")` policy already
  covers this; the test
  `TestLiveHtmlParser::test_ascii_apostrophe_canonicalized_to_okina`
  pins it.
- **Stage-2 candidate JSONL is NOT directly `--check --strict` clean.**
  The five alignment-quality fields (`alignment_confidence_tier`,
  `quality_flags`, `manual_review_reasons`, `alignment_score_components`,
  `policy_version`) are stamped on by `320_build_stage2_manifest.py
  --execute` via `apply_policy()`. Tests must call
  `manifest.apply_policy(dict(row))` before `manifest.validate_row(...)`
  — running `--check --strict` against raw candidate JSONL will
  always report `missing:*` violations by design.
- **Python 3.14 + dynamic module load + dataclasses:** when loading a
  numeric-prefix script like `206_fetch_baibala_raw.py` via
  `importlib.util.spec_from_file_location`, the module MUST be
  registered in `sys.modules` BEFORE `spec.loader.exec_module(...)`,
  otherwise `@dataclasses.dataclass` raises
  `'NoneType' object has no attribute '__dict__'`. Pattern captured in
  `_load_fetch_module()` in `scripts/322_build_bible_candidates.py`.
- **File-naming convention for raw chapter HTML:** the live fetcher
  writes `<BOOK_CODE>_<chapter:03d>.html` (e.g. `GEN_001.html`).
  `iter_raw_haw_chapters()` and the test fixture both follow this
  convention, so `--from-raw YYYYMMDD` works against actual fetcher
  output without rename gymnastics.

## 2026-05-01T01:11:50Z — Baibala Live HTML Parser + Raw Candidate Builder (Issue #16 Implementation & Validation Complete)

**Status:** APPROVED by Danny — Ready for Stage 2 intake

### What was done

Implemented live Greenstone HTML parser and raw-candidate generation for the Baibala Hemolele (Hawaiian Bible) source:

**Parser Logic (`scripts/206_fetch_baibala_raw.py`)**
- `parse_baibala_chapter_html(html_string, book_code, chapter_num)` — extracts verse spans from Greenstone's anchor-based markup
- `_VERSE_ANCHOR_RX` — regex for verse anchors (e.g., `<a name="v1">`) 
- `_normalize_haw_verse_text()` — canonicalizes NFC + U+02BB (modern ʻokina) from ASCII apostrophes in the 1839 imprint
- Verse terminator is `<br />`, not the next anchor — avoids leaking Greenstone's nav table into the final verse

**Candidate Builder (`scripts/322_build_bible_candidates.py`)**
- `build_rows_from_raw_haw(raw_dir, book_code, edition_pinned_by)` — generates verse-aligned candidates from raw HTML
- `iter_raw_haw_chapters()` — streams chapter files from `{raw_dir}/{BOOK_CODE}_{NN:03d}.html`
- CLI flags: `--from-raw YYYYMMDD`, `--haw-raw-dir /path/to/raw`, `--eng-fixture-dir /path/to/eng` — override defaults per-side

**Tests (`code/tests/test_bible_adapter.py`)**
- `TestLiveHtmlParser` — 6 tests for parser boundary conditions, apostrophe canonicalization, verse-id correctness
- `TestRawHawCandidateBuilder` — 6 tests for candidate generation, split assignment, notes provenance tagging
- Synthetic fixture: `code/tests/fixtures/bible/haw_html/GEN_001.html` — mirrored Greenstone anchor pattern (not real Bible text)

**Documentation (`data-sources/bible/README.md`)**
- Status header, run order, parser-contract section refreshed
- ASCII apostrophe canonicalization decision documented
- Orthography notes linked to haw normalization pipeline

### Key design decisions

1. **Verse terminator = `<br />`**  
   Greenstone appends nav table after final verse. Using next-anchor or `</table>` boundary leaked nav text into verse 31. Terminating at `<br />` matches per-verse line layout 1:1.

2. **ASCII apostrophe as real ʻokina mis-encoding**  
   Live HTML uses `hana'i` (ASCII `'`); modern orthography is `hanaʻi` (U+02BB). This is the *primary* canonicalization path for this 1839 edition on the haw side (not a defensive edge case). Haw normalization pipeline already handles via `OKINA_MISENCODINGS`.

3. **Policy fields not on adapter candidates**  
   Stage-2 alignment-quality fields (`alignment_confidence_tier`, `quality_flags`, etc.) are applied by `320_build_stage2_manifest.py`, not the adapter. Candidates omit them. Manifest builder applies policy before validation.

4. **Raw-derived rows tagged in notes**  
   `build_rows_from_raw_haw()` appends `; src=raw_html` to notes field → provenance breadcrumb for downstream review (not a gate; purely informational).

5. **English side stays on fixture**  
   English WEB `url_template_status` still `placeholder_pending_endpoint_check`. Awaiting Linus pin. `--from-raw` and `--haw-raw-dir` only override haw side; eng defaults to `--eng-fixture-dir code/tests/fixtures/bible`.

### Validation & review

- **Fixture & live sample testing:** Parser validated against synthetic fixture (CI) and pre-fetched live samples (from Linus' pin work); no additional network egress required.
- **Contract compliance:** Adapter contract tests (`code/tests/test_bible_adapter.py`) passed; policy-field expectations met.
- **Danny's code review (2026-05-01T01:11:50Z):** APPROVED. All logic, tests, docs, and policy integration sound. Non-blocker: WEB endpoint deferral appropriate.

### Hand-off notes

- **Rusty:** Verse-id pairs score at `tier=accept` per docs/stage2-alignment-quality.md §3.1. No embedding needed. Haw text is NFC + U+02BB; matches your tokenizer assumptions.
- **Linus:** When WEB endpoint pinned, flip `url_template_status` to `confirmed_live_<date>` so fetcher allows `--execute` on eng side.
- **Coordinator:** Issue #16 ready for closure. Combined with Danny's review, Stage 2 readiness proceeding.

### Files touched (working tree only — not committed)

- `scripts/206_fetch_baibala_raw.py`  
- `scripts/322_build_bible_candidates.py`  
- `code/tests/test_bible_adapter.py`  
- `data-sources/bible/README.md`  
- `code/tests/fixtures/bible/haw_html/GEN_001.html` (synthetic fixture)

## 2026-05-02 — Stage 2 source discovery pass (round 2)

**Trigger:** User: "wait that was easy, lets find more data."

### What I did

Source-discovery + inventory hardening pass on `data-sources/stage2-parallel-fetch-plan.json`. No raw bytes fetched. All probes were metadata-only HEADs / API list calls / IA advanced-search queries.

### What landed in the fetch plan

Added **4 new source rows** (sources count: 13 → 17):

1. `andrews-1865-en-haw-vocab-appendix` — pinned IA item `cu31924026916167` (1865 Cornell scan), djvu.txt available. Pre-1925 PD. Dictionary-example Tier C. **verified_endpoint, no rights gate.**
2. `kaikki-haw-en-wiktionary` — `https://kaikki.org/dictionary/Hawaiian/kaikki.org-dictionary-Hawaiian.jsonl` confirmed live (HTTP 200, JSONL with senses[].examples[].{text, english}). CC BY-SA 4.0 + GFDL via Wiktionary. Dictionary-example Tier C. **verified_endpoint, no rights gate.**
3. `wikimedia-cx-en-haw-published` — `cxpublishedtranslations` API on `haw.wikipedia.org`. 68 published EN→HAW articles at probe time, each with `sourceRevisionId` / `targetRevisionId` / `stats.human` / `stats.mt`. CC BY-SA 4.0. parallel-doc Tier B. **verified_endpoint** but gated on Linus pinning a `stats.mt` cutoff (proposed `< 0.5`).
4. `hawaiian-kingdom-statutes-bilingual` — paired pre-1900 IA imprints confirmed via advanced-search. Best pin: 1897 Penal Laws English `esrp641724381` ↔ Hawaiian `esrp641728581`. Three other paired-edition pairs also identified (1869 Penal Code, 1859 Civil Code, 1846 Statute Laws). Public domain by copyright term + sovereign-edicts doctrine. parallel-doc Tier B. **pending_rights_review** until Linus pins the prototype pair and confirms a legal-register cap.

Added **3 verified-absent rows** to `deferred_or_excluded`:

- `flores-plus-haw-verified-absent` — `openlanguagedata/flores_plus` covers 222 langs, haw_Latn NOT included (Maori is the nearest Polynesian).
- `belebele-haw-verified-absent` — `facebook/belebele` covers 122 langs, haw_Latn NOT included.
- `wmt24pp-haw-verified-absent` — `google/wmt24pp` covers 48 langs, haw NOT included.

These are pinned so the next discovery pass does not silently re-suggest them; if any add Hawaiian later, the rule is hash to `data/evals/eval_hashes.jsonl` BEFORE any other ingest.

Added **2 new open_questions** to Linus:
- `stats.mt` cutoff for the Wikimedia CX parallel-doc source.
- Pinned bilingual code pair for the Hawaiian Kingdom statutes source + register cap.

JSON validation passed: 17 sources, 8 deferred, 7 open_questions.

### Honest yield outlook

If all four new rows land cleanly (post-filter + post-LaBSE):
- Andrews 1865 vocab appendix: low hundreds of true example pairs (rest are gloss-only).
- kaikki haw Wiktionary: several hundred bilingual examples.
- Wikimedia CX: 1–3k Tier-B candidates.
- Hawaiian Kingdom statutes (1897 pin alone): 1–2k legal-register pairs; all four pairs combined potentially 3–8k.

**Total ~5–13k new canonical pair candidates** on top of the existing inventory. Plausible path to the 20k canonical-pair target without leaning harder on Bible (which already has a ≤30% parallel-train-token cap).

### Verified-absent learnings (so I don't probe them again)

- **FLORES+ does not have haw_Latn.** It has `mri_Latn` (Maori). Future agents asking about Polynesian eval, the right answer is "use Hawaiian-specific Bible holdouts + Tatoeba dev splits, not FLORES."
- **Belebele does not cover haw_Latn either.** Same answer.
- **WMT24++ does not cover haw.** Confirmed against the HF dataset card's `language` list (48 langs, no haw).
- **Mozilla Pontoon haw is not an active locale.** No Firefox / Mozilla l10n haw repo on `hg.mozilla.org/l10n-central/` either.
- **UDHR Hawaiian endpoints are unreliable.** `unicode.org/udhr/d/udhr_haw.{html,txt}`, `efele.net/udhr/`, and the OHCHR direct PDF all returned 404 or 403. The translation exists in publication, but no defensible mirror surfaced; defer.

### Key file paths

- `data-sources/stage2-parallel-fetch-plan.json` — authoritative inventory, now with the four new entries.
- `.squad/decisions/inbox/frank-stage2-source-leads.md` — full memo for the team incl. lead-only items (Ulukau translations, Ka Wai Ola, State Constitution).
- IA pinned item for the Andrews 1865 vocab appendix: `cu31924026916167`. djvu.txt at `https://archive.org/download/cu31924026916167/cu31924026916167_djvu.txt`.
- kaikki JSONL: `https://kaikki.org/dictionary/Hawaiian/kaikki.org-dictionary-Hawaiian.jsonl`.
- CX EN→HAW list endpoint: `https://haw.wikipedia.org/w/api.php?action=query&list=cxpublishedtranslations&from=en&to=haw&format=json&limit=500`.

### Next adapter priorities (for me)

1. **kaikki haw Wiktionary adapter first** — single JSONL file, no rights gate, smallest fetch footprint, fastest path to a working dictionary-example Tier-C feeder.
2. **Andrews 1865 vocabulary appendix adapter** — single djvu.txt, also no rights gate, but OCR cleanup / appendix-detection regex is more involved.
3. **Wikimedia CX adapter** — only after Linus pins the `stats.mt` cutoff. Two-stage adapter: enumerate-and-filter pass, then per-translationId revision pull (EN side from en.wikipedia.org, HAW side from haw.wikipedia.org).
4. **Hawaiian Kingdom statutes 1897 Penal Laws pair** — only after Linus pins the pair + confirms register cap. Section-id-first alignment is the right approach (Bible-verse-style determinism), with LaBSE fallback only for unanchored sub-section paragraphs.

### Hand-offs

- **Linus:** two new open_questions (CX cutoff, statutes pin) + the deferred lead set (Ulukau bilingual translations, Ka Wai Ola, State Constitution Hawaiian translation).
- **Rusty:** weigh in on LaBSE 0.75 default for CX encyclopedic register; opine on section-id-first vs LaBSE-only for the legal-register statutes.
- **Coordinator:** four new fetch-plan rows + three verified-absent rows are inventory-only landings — no fetch executed, no commit forced.

## 2026-05-02 — Stage 2 80k-row source strategy (round 3)

**Trigger:** User: "the 4 rows means nothing, i want to hit 80k rows." Stage 2 target raised 40k → 80k directional SFT rows (per coordinator directive `20260501T070923Z`).

### Learnings

**1. 80k feasibility — honest answer.**

80k directional SFT rows ≈ 40k canonical pairs post-retention, ≈ 48–55k canonical pair candidates pre-retention (15–25% loss to alignment / dedupe / cap / okina canon / eval-contam filter).

The rights-light human-parallel inventory **does not get us there alone.** Combined midpoint of Bible (cap-bound 8–12k) + Tatoeba (0.5–2k) + OPUS non-JW300 (2–5k) + Wiki langlinks (3–5k) + HK Kingdom statutes all-four-pairs (3–6k) + CX (1–3k) + dictionaries (sub-1k) + Wikisource (sub-0.5k) = **~28–35k accepted canonical pairs**, i.e., 56–70k directional rows. Below target.

To land 80k credibly the plan **must** include:
- **NLLB mined haw-eng** (8–15k pairs). Linus already cleared for prototype-only. Single largest gap-closer.
- **Capped synthetic BT** of Stage-1 monolingual haw (5–10k pairs). Tagged `synthetic-bt`, never dev/test, ≤15% cap.

If either is policy-rejected, the 80k target needs renegotiation, not threshold-relaxation.

**2. Source-bucket midpoint estimates (accepted pairs, post-filter).**

| Bucket | Mid | Cap/risk |
|---|---|---|
| Bible | 8–12k | Cap-bound (≤30%) |
| NLLB mined | 8–15k | LaBSE ≥0.80; prototype_only |
| OPUS non-JW300 | 2–5k | per-corpus license; ≤15% cap |
| Wiki langlinks | 3–5k | LaBSE ≥0.75; needs sentence-transformers |
| HK Kingdom statutes (all 4 pairs) | 3–6k | Legal cap ≤15%; section-id-first |
| Wikimedia CX | 1–3k | `stats.mt<0.5`; 68 articles only |
| Tatoeba | 0.5–2k | Already adapter-ready |
| Synthetic BT | 5–10k | ≤15% cap; never dev/test |
| kaikki Wiktionary | 0.3–0.7k | Tier C, capped |
| Andrews 1865 | 0.2–0.5k | Tier C, capped |
| Wikisource comparable | <0.5k | Hard-escalate cultural filter |

Sum mid: ~45k accepted → ~34–38k post-retention pairs → **~70–80k directional rows**. 80k credible, not guaranteed.

**3. Promotions vs prior memo.**

- HK Kingdom statutes pin promoted from "1897 Penal Laws only" to **all four paired codes** (1846 Statutes, 1859 Civil Code, 1869 Penal Code, 1897 Penal Laws). Yield delta: 1–2k → 3–6k accepted pairs.
- Synthetic BT moved from "future option" to **on the critical path** for 80k. Cannot duck it without renegotiating target.
- kaikki + Andrews dropped in priority (still ship for register diversity, but accepted-pair contribution is sub-1k combined; not on critical path to 80k).

**4. Verified-NOT-helpful for 80k math.**

- Bible cap relaxation — non-negotiable, declined.
- Dictionary scaling — combined sub-1k regardless.
- Ulukau/Ka Wai Ola/State Constitution UH translation — lead-only, need permission grants, not in 80k math.
- General CC scrape of `.haw` web — hard-escalate cultural risk; no cultural-review owner.
- FLORES+/Belebele/WMT24++ — verified absent for haw_Latn (already in `deferred_or_excluded`).

**5. Next adapter priorities (revised for 80k target).**

1. `108_collect_opus_haw.py` (Linus' plan)
2. `109_collect_nllb_haw.py` (Linus' plan; Rusty: LaBSE 0.80)
3. `110_collect_wiki_aligned.py` (Linus' plan; sentence-transformers dep)
4. `111_collect_hk_statutes.py` — **all four pairs** (mine; Rusty: section-id alignment)
5. `112_collect_cx_published.py` (mine; cutoff already cleared by Linus)
6. `120_generate_bt_pairs.py` (Rusty: model; me: provenance)

kaikki and Andrews adapters slip from #1/#2 to post-critical-path.

### Guardrails I will enforce

- **NLLB:** LaBSE ≥0.80 cosine (stricter than 0.75 for curated comparable); below-threshold → `alignment_review_required=true`, excluded from train; license=unknown per row; origin URL recorded.
- **BT:** Per-pair `model_id`, `model_checkpoint_sha`, `generation_decode_params` recorded; round-trip BLEU or LaBSE floor (Rusty); ≤15% synthetic cap; never dev/test; cross-checked against `eval_hashes.jsonl` before ingest.
- **Bucket caps must be enforced in `320_build_stage2_manifest.py`** — flagging to Linus. If caps are not in code, 80k is theoretical.

### Hand-offs

- **Linus:** bucket-cap enforcement in 320; `expected_pair_yield_estimate` field per source when his fetch-plan pass closes; HK statutes promotion to all-four-pairs.
- **Rusty:** LaBSE 0.80 for NLLB; BT quality floor + decode params; section-id-first vs LaBSE-fallback for HK legal register.
- **Coordinator:** If NLLB mined or synthetic BT are policy-rejected, target must be renegotiated.

### Files touched

- `.squad/decisions/inbox/frank-stage2-80k-source-plan.md` (new — full memo).
- `.squad/agents/frank/history.md` (this entry).
- **No edit to `data-sources/stage2-parallel-fetch-plan.json`** — Linus is concurrently updating target math; landing the new fields is his.

---

## 2026-05-01 Session: Stage 2 80k source finalization

**Co-authors:** Linus, Scribe (session logging)

### Your phase in this session

1. **Stage 2 source discovery pass (2026-05-02 00:03:49Z):** Probed high-frequency suggestions; found 4 new rights-light sources (Andrews 1865 vocab, Kaikki Wiktionary, Wikimedia CX, HK Statutes); verified 3 candidates absent (FLORES+, Belebele, WMT24++); deferred 6 leads pending rights/endpoint verification.

2. **80k acquisition roadmap (2026-05-02 00:12:07Z):** Mapped 11-bucket strategy responding to user's 80k target directive. Honest finding: human-parallel alone yields ~28–35k accepted pairs (~56–70k rows); NLLB mined (8–15k) and synthetic BT (5–10k) are required gap-closers. Documented guardrails: NLLB ≥0.80 LaBSE, synthetic BT ≤15% cap, never dev/test. Escalated NLLB/BT policy decision to Coordinator; escalated quality-floor design decisions to Rusty.

3. **HK statutes promotion:** All four paired codes now in scope (1897 Penal Laws, 1869 Penal Code, 1859 Civil Code, 1846 Statute Laws). Rights cleared via PD+sovereign-edicts. 1897 pair pinned as priority 1 (cleanest OCR). Combined legal-register cap ≤15%.

4. **Next adapter roadmap:** Prioritized 6 scripts: (1) OPUS haw — static TMX, no blocker; (2) NLLB mined — blocked on Rusty 0.80 floor; (3) Wiki-aligned — blocked on LaBSE infra; (4) HK statutes (all 4 pairs) — blocked on Rusty alignment design; (5) CX published — gate cleared, ready; (6) Synthetic BT — blocked on Rusty quality floor.

### Linus updates in this session (parallel track)

- Updated 80k target across `scripts/107_collect_stage2_parallel.py`, tests, and docs.
- Reviewed your 4 sources; cleared all 4 with gates/fixes (andrews-1865 schema trim, CX stats.mt confirmation, HK statutes rights ruling).
- Encoded 80k strategy into `data-sources/stage2-parallel-fetch-plan.json` + docs.

### Merged to decisions.md

All 7 inbox files merged and deleted. Session now consolidated into Team record.

---

## 2026-05-01 Session: Stage 2 first real fetch pass

### Learnings

**Honest answer to "do we have the 40k?":** No. The 40k canonical pair / 80k directional row figure has always been a *target/estimate*, not actual data on disk. After this fetch pass, on-disk candidate inventory is:

| File | Actual rows |
|---|---|
| `data/stage2/candidates/bible.jsonl` | 5 (pre-existing smoke) |
| `data/stage2/candidates/tatoeba.jsonl` | **121 (new)** |
| `data/stage2/stage2_manifest.jsonl` | 5 (stale, pre-fetch) |
| **Total candidate pairs on disk** | **126** |

That is **~0.3%** of the 40k canonical-pair target. The remainder is still in the roadmap, gated on adapters (NLLB, OPUS, HK statutes, CX, kaikki/Andrews parsers, BT) — none of which were in scope for this pass.

### Sources actually fetched this pass

Raw bytes captured under gitignored `data/raw/<source>/20260501/` with provenance ledgers (`fetch.jsonl`):

| source_id | artifacts | total bytes |
|---|---|---|
| `tatoeba-haw-eng` | 3 (haw sentences, links, eng sentences) | ~34.6 MB |
| `andrews-1865-en-haw-vocab-appendix` | 1 (IA djvu.txt) | 2.73 MB |
| `kaikki-haw-en-wiktionary` | 1 (jsonl dump) | 5.22 MB |
| `wikimedia-cx-en-haw-published` | 1 (cxpublishedtranslations API page 1, limit=500) | 29 KB |
| `hawaiian-kingdom-statutes-bilingual` | 8 (IA detail pages for all 4 paired codes) | ~2 MB |

Bible: untouched this pass per directive (no full 66-book scrape; existing 5-row smoke retained).

### Candidate JSONL produced

- `data/stage2/candidates/tatoeba.jsonl`: **121 rows** via `data-sources/tatoeba/fetch.py --execute`. Adapter ran clean first try; 3 eng IDs missing in Tatoeba export (deleted/merged) — warned and skipped, expected behavior.

### Sources skipped this pass and why

| source_id | reason |
|---|---|
| `bible-eng-pd-anchor` | Skipped per task scope ("no full Bible scrape this pass"); KJV/ASV USFM zips still available next pass. |
| `bible-haw-baibala-pinned-edition` | gate: `rights_review_required` + edition pin / ToS snapshot still pending Linus. |
| `bible-haw-archive-org-pre1925` | gate: `endpoint_check_required`. |
| `opus-haw-subsets` | gate: `rights_review_required` + `endpoint_check_required`. |
| `nllb-mined-haw-eng` | adapter-needed; blocked on Rusty LaBSE 0.80 floor + scoring script. |
| `biblenlp-haw` | adapter-needed; rights review + endpoint check pending. |
| `weblate-en-haw` | adapter-needed; per-project license filter pending. |
| `wiki-haw-en-langlinks` | template-or-api adapter not yet written. |
| `wikisource-haw-en-comparable` | adapter-needed; endpoint check pending. |
| `pukui-elbert-andrews-examples` | adapter-needed; rights review. |
| `bt-stage1-monolingual-haw` | synthetic; blocked on Rusty quality floor + Linus cap registry. |
| `global-piqa-parallel-haw`, `taxi1500-haw` | eval-only; correctly auto-skipped. |

### Blockers / follow-ups

1. **HK statutes raw artifacts are IA detail HTML pages (~230 KB each), not the book bodies.** Plan-as-written points the generic fetcher at `archive.org/details/<id>` which returns the landing page. Body extraction (DJVU/OCR text) needs a source-specific adapter (`111_collect_hk_statutes.py` per Frank's roadmap). Provenance is captured; conversion is the next pass. **Not a bug in 207** — the plan deliberately uses detail URLs as the provenance anchor.
2. **Wikimedia CX response is 1 page (limit=500).** Need pagination + rate-limit-aware adapter to enumerate full 68-article corpus before parser pass.
3. **Andrews 1865 djvu.txt fetched (2.7 MB OCR).** Vocab appendix parser not yet written — raw is staged for the appendix-anchor adapter.
4. **Kaikki Hawaiian dictionary (5.2 MB jsonl) fetched.** Dictionary-example extractor not yet written.

### Exact commands that worked

```bash
python3 scripts/107_collect_stage2_parallel.py
python3 scripts/207_fetch_stage2_parallel_raw.py --execute --source tatoeba-haw-eng
python3 scripts/207_fetch_stage2_parallel_raw.py --execute --source andrews-1865-en-haw-vocab-appendix
python3 scripts/207_fetch_stage2_parallel_raw.py --execute --source kaikki-haw-en-wiktionary
python3 scripts/207_fetch_stage2_parallel_raw.py --execute --source wikimedia-cx-en-haw-published
python3 scripts/207_fetch_stage2_parallel_raw.py --execute --source hawaiian-kingdom-statutes-bilingual
python3 data-sources/tatoeba/fetch.py --execute
```

No source-code edits made this pass; 207 fetcher and Tatoeba adapter both ran clean as written.

## 2026-05-02 — Stage 2 raw→candidate conversion pass (kaikki + Andrews)

**Trigger:** User: "ok now go source the data". Convert already-fetched raw Stage-2 sources into actual candidate JSONL where feasible. Precision over recall; do not fabricate.

### Scripts added

- `scripts/323_build_kaikki_candidates.py` — reads `data/raw/kaikki-haw-en-wiktionary/<date>/kaikki.org-dictionary-Hawaiian.jsonl`, walks `senses[].examples[]`, emits one row per bilingual example (`text`+`english` both populated). NFC + ʻokina canonicalization on haw side. Dedup by `sha256_pair`. Alignment fields: `dictionary-example`/`manual`. License: CC-BY-SA-4.0 / GFDL-1.3+. Stdlib-only.
- `scripts/324_build_andrews_vocab_candidates.py` — reads `data/raw/andrews-1865-en-haw-vocab-appendix/<date>/cu31924026916167_djvu.txt`, locates the appendix via `rfind("ENGLISH-HAWAIIAN  VOCABULARY.")`, parses `EN-headword, haw-gloss.` lines. Strict precision filters: regex-shaped headword, **system wordlist** (`/usr/share/dict/words`) check on dehyphenated headword to drop OCR errors like `Acqnire`/`Accorse`, Hawaiian gloss restricted to bare-13-letter alphabet + ʻokina + punctuation, no consonant clusters, no English filler tokens, no 4+ letter repeats, no single-consonant tokens. Every row emitted with `alignment_review_required=true` since OCR strips diacritics. Stdlib-only.

### Actual rows produced (this pass)

| File | Rows |
|---|---|
| `data/stage2/candidates/andrews_1865_vocab.jsonl` | **1194** (new) |
| `data/stage2/candidates/kaikki_wiktionary.jsonl` | **292** (new) |
| `data/stage2/candidates/tatoeba.jsonl` | 121 (unchanged) |
| `data/stage2/candidates/bible.jsonl` | 5 (unchanged) |
| **Total candidate rows on disk** | **1612** |

Up from 126 → 1612 (≈12.8×). Still ~4% of the 40k canonical-pair target.

### Manifest builder dry-run

```
python3 scripts/320_build_stage2_manifest.py --dry-run
```

Output: `rows_emitted: 1612`, `total_candidates_ingested: 1612`, `total_violations: 17` (all `split:dev_requires_parallel_alignment` — manifest builder hashed some dictionary-example rows to dev split which fails the policy gate). Tier counts: 254 accept / 45 review / 1313 reject. Reject majority is expected — Andrews glosses lack diacritics (`haw_no_diacritics` flag) and dictionary-style register fails several quality flags by design. **Adapter rows are schema-valid**; the policy filter is downstream.

### Sources NOT converted this pass and why

- **Wikimedia CX en-haw published (`data/raw/wikimedia-cx-en-haw-published/20260501/api.php`).** Raw is the `cxpublishedtranslations` API metadata page only: 68 translation entries with `translationId`, `sourceURL`, `targetURL`, `stats`, but **no body text**. Cannot emit candidate rows without per-translation revision pulls (en.wikipedia.org `?action=raw&oldid=<sourceRevisionId>` and haw.wikipedia.org `?action=raw&oldid=<targetRevisionId>`), then a section-aligner. **Next fetch needed:** per-translationId revision pull (68 calls × 2 sides) before any 32x adapter is feasible.
- **Hawaiian Kingdom statutes (`data/raw/hawaiian-kingdom-statutes-bilingual/20260501/`).** Raw is 8 IA detail HTML pages (~230 KB each, item-landing chrome — title, sidebar, embed widgets). No DJVU/OCR text bodies were fetched. **Next fetch needed:** for each of the 8 IA item IDs (`civilcodehawaii00armsgoog`, `esrp468790723`, `esrp475081650`, `esrp641724381`, `esrp641728581`, `hekumukanawaiam00hawagoog`, `kanawaiikauiaek00ricogoog`, `statutelawshism00ricogoog`), fetch `https://archive.org/download/<id>/<id>_djvu.txt`. Then a section-id-first parallel adapter per the all-four-pairs plan.

### Blockers / hand-offs

- **Linus:** manifest builder's split assigner produced 17 `dev_requires_parallel_alignment` violations on dictionary-example rows. Either the assigner should force dictionary-example rows to `train` deterministically (skipping dev) or the policy gate should be relaxed for dict examples. Adapter side: every dictionary-example row is correctly labeled `parallel-doc/parallel-sentence`-incompatible by `alignment_type`; the dev/train hash is downstream.
- **Coordinator:** raw→candidate pass for CX and HK statutes is **NOT** complete this pass — the raw fetches captured detail/metadata pages, not body text. New fetches required before 325/326-style adapters can produce rows.

### Exact commands that worked

```bash
python3 -m py_compile scripts/323_build_kaikki_candidates.py scripts/324_build_andrews_vocab_candidates.py
python3 scripts/323_build_kaikki_candidates.py --dry-run
python3 scripts/323_build_kaikki_candidates.py --execute    # 292 rows
python3 scripts/324_build_andrews_vocab_candidates.py --dry-run
python3 scripts/324_build_andrews_vocab_candidates.py --execute   # 1194 rows
python3 scripts/320_build_stage2_manifest.py --dry-run             # 1612 ingested
```

No commits made (per task directive).

## 2026-05-02 — Stage 2 second raw fetch pass (HK statutes djvu + CX revisions)

**Trigger:** User: "ok now go source the data". Convert the two known
raw-only leads (Wikimedia CX, HK statutes) into actual full-text raw, and
emit candidate JSONLs only if precision is defensible.

### Scripts added

- `scripts/208_fetch_hk_statutes_djvu.py` — pulls IA `_djvu.txt` OCR for all
  four paired Hawaiian-Kingdom code imprints (8 files). Derived `esrp*`
  filenames from `archive.org/metadata/<id>` (date-based, not `<id>_djvu.txt`).
  Output: `data/raw/hawaiian-kingdom-statutes-paired-imprints/<YYYYMMDD>/`,
  per-item provenance row in `fetch.jsonl`.
- `scripts/209_fetch_cx_published_revisions.py` — for each of the 68 CX
  translations surviving the Linus gate (`stats.mt<0.5 AND stats.human>0`),
  pulls EN source revision wikitext from en.wikipedia.org and HAW target
  revision wikitext from haw.wikipedia.org via `?action=parse&prop=wikitext`.
  Output: `data/raw/wikimedia-cx-en-haw-published/<YYYYMMDD>/revisions/`.

### Raw artifacts on disk (this pass)

| Source | Files | Bytes |
|---|---|---|
| `hawaiian-kingdom-statutes-paired-imprints/20260501/` | 8 djvu OCR | 6.86 MB |
| `wikimedia-cx-en-haw-published/20260501/revisions/`   | 42 JSON (21 EN + 21 HAW after retry) | 1.2 MB |

### CX gate filter result

`api.php` index has 68 published EN→HAW translations. Linus-confirmed gate
(`stats.mt < 0.5 AND stats.human > 0`) leaves **21** survivors. All 21 ×
2 sides fetched (35 ok on first pass, 7 rate-limited 429s — recovered on
retry with sleep=3s). Pair-content reality check (wikitext word counts):

| Pair shape | Count |
|---|---|
| HAW=0 words (target deleted/empty) | 8 |
| HAW < 50 words (stub) | 5 |
| HAW < 250 words and ratio < 0.10 | 6 |
| HAW comparable to EN (ratio 0.5–1.5) | **2** (translationId 1378441, 2851619) |

Net: across 68 published rows the post-gate human-substantive bilingual
yield is **two articles**. The `stats.human` metric in the CX index is the
*fraction of the current target preserved as human translation*, not target
size — so 21 survivors does NOT mean 21 usable parallel docs. This is honest
sourcing data, not a fetch failure.

### IA filename mapping recorded (HK statutes)

| IA item | IA filename | side | pair |
|---|---|---|---|
| esrp641724381 | 1897.001_djvu.txt | en | 1897 Penal Laws |
| esrp641728581 | 1897.002_djvu.txt | haw | 1897 Penal Laws |
| esrp475081650 | 1869.001_djvu.txt | en | 1869 Penal Code |
| esrp468790723 | 1850.002_djvu.txt | haw | (paired by plan to 1869, but IA filename year=1850 — flag) |
| civilcodehawaii00armsgoog | civilcodehawaii00armsgoog_djvu.txt | en | 1859 Civil Code |
| hekumukanawaiam00hawagoog | hekumukanawaiam00hawagoog_djvu.txt | haw | 1859 Civil Code |
| statutelawshism00ricogoog | statutelawshism00ricogoog_djvu.txt | en | 1846 Statute Laws |
| kanawaiikauiaek00ricogoog | kanawaiikauiaek00ricogoog_djvu.txt | haw | 1846 Statute Laws |

### HK candidate adapter — NOT shipped this pass

Section/chapter markers were probed across all 8 djvu files. The structure
is too noisy for a precision-first section-id-aligned adapter without
chapter context:

- 1859 Civil Code: EN matches `^Section N\.` 201× but with 10 duplicates
  across appendix laws (1866 reissue is appended to the EN imprint, breaking
  monotonic numbering); HAW Pauku N matches 97× (only ~half the EN side).
  Naive `intersect(en_ids, haw_ids)` yields 21 candidate pairs but
  spot-check shows the matched bodies belong to *different* sections of
  different acts — section-1 of an appendix law on the EN side aligned to
  section-1 of the underlying code on the HAW side.
- 1869 Penal Code: EN has 70 `Section N` matches; HAW (esrp468790723) has
  3 Pauku markers — OCR is not picking up the HAW section structure. Pairs
  are not extractable without column/page-region OCR.
- 1897 Penal Laws: EN uses §N (1417 markers, statutory format); HAW uses
  Pauku N (77 markers). EN section numbering is sequential across all
  chapters; HAW has gaps. Cross-imprint number alignment is *not* valid
  without chapter context.
- 1846 Statute Laws: EN file labeled `statutelawshism00ricogoog` actually
  contains both EN+HAW columns interleaved by chapter (OCR shows 653
  `Pauku N` markers on the "EN" side). These are bilingual interleaved
  imprints, not parallel separated codes — needs page-layout-aware OCR.

Conclusion: **section-id alignment is not a valid precision strategy for
these specific OCR dumps**. Per Frank's identity (precision over recall) +
per Rusty's "section-id-first vs LaBSE-fallback" memo, I will not emit
candidate rows from these files until either (a) page-layout-aware OCR
re-extraction or (b) LaBSE alignment infra is available. Hand-off to Rusty
+ Linus.

### CX candidate adapter — NOT shipped this pass

The fetch-plan `acquisition_plan.steps[3]` for CX states: "Adapter: strip
wikitext to plaintext, sentence-segment, LaBSE-align with the standard
Tier-B pipeline (Rusty owns the threshold; default 0.75)." LaBSE infra is
not in scope this pass and Rusty owns the threshold. Of the 21 mt<0.5
survivors, only 2 (translationId 1378441 and 2851619) have HAW articles
substantive enough to attempt sentence alignment in the first place. A
high-recall sentence-pair extractor without LaBSE would either (a) emit ~2
articles' worth of low-confidence sentence pairs (~10–30 rows) — not worth
new adapter LOC — or (b) fabricate alignments by paragraph order, which
violates precision policy.

### Actual rows produced (this pass)

**Zero new candidate rows.** Total candidate JSONL on disk unchanged:

| File | Rows |
|---|---|
| `data/stage2/candidates/andrews_1865_vocab.jsonl` | 1194 |
| `data/stage2/candidates/kaikki_wiktionary.jsonl`  | 292 |
| `data/stage2/candidates/tatoeba.jsonl`            | 121 |
| `data/stage2/candidates/bible.jsonl`              | 5 |
| **Total** | **1612** |

Raw bytes for HK + CX bodies are now on disk for downstream adapter work
once alignment infra is unblocked.

### Exact commands that worked

```bash
python3 -m py_compile scripts/208_fetch_hk_statutes_djvu.py scripts/209_fetch_cx_published_revisions.py
python3 scripts/208_fetch_hk_statutes_djvu.py --dry-run
python3 scripts/208_fetch_hk_statutes_djvu.py --execute      # 8 files, 6.86 MB
python3 scripts/209_fetch_cx_published_revisions.py --dry-run
python3 scripts/209_fetch_cx_published_revisions.py --execute  # 35 ok / 7 429
# Inline retry of 7 rate-limited revisions with sleep=3s -> all 7 ok.
```

### Blockers / hand-offs

- **Rusty:** HK statutes need either page-layout-aware re-OCR (especially
  esrp468790723 HAW Penal Code 1850 reissue and statutelawshism00ricogoog
  1846 bilingual-columns) or LaBSE-based sentence alignment as the
  primary path. Section-id intersection is not a defensible precision
  strategy on these OCR dumps. Section-id alignment was the assumption
  baked into the fetch-plan promotion; that assumption needs revision.
- **Linus:** plan entry `hawaiian-kingdom-statutes-bilingual` previously
  said the 1869 Penal Code pair is `esrp475081650 <-> esrp468790723`. The
  IA filename for `esrp468790723` is `1850.002_djvu.txt` (Hawaiian Penal
  Laws 1850 reissue, 308 KB), not the Hawaiian translation of the 1869
  compiled Penal Code. The 1869 EN compilation was made *from* the 1850
  Code, so they share content but the pair label "1869 Penal Code EN/HAW"
  is misleading. Consider renaming or splitting the plan entry.
- **Coordinator:** raw fetches now done for both CX and HK statutes.
  Candidate generation for both is blocked on infra (LaBSE / page-layout
  OCR) — neither is a Frank-lane unblock. The 80k target math from the
  prior memo continues to assume HK contributes 3–6k accepted pairs;
  honest read after seeing the OCR is that figure now requires Rusty to
  produce the alignment pipeline before it can be defended.

No commits made (per task directive).

## 2026-05-02 — Bible raw fetch pass (HAW Genesis 1-50 + ENG KJV/ASV anchor)

**Trigger:** User: "what about bible, and opus". OPUS remains gated; this
pass is Bible-only. Linus cleared Baibala stale gates on 2026-05-01 (1839
edition pinned, ToS snapshot on disk).

### Steps run

1. Refreshed `data/local/stage2_parallel/collect_plan.json` via
   `python3 scripts/107_collect_stage2_parallel.py`. After Linus's gate
   metadata update, both `bible-haw-baibala-pinned-edition` and
   `bible-eng-pd-anchor` show `fetch_gates: []`. ENG anchor is now
   classified `fetch_kind: static-download`, `fetch_state:
   ready-static-download` with two artifacts (`eng-kjv2006_usfm.zip`,
   `eng-asv_usfm.zip`).

2. Confirmed ToS snapshot on disk:
   `data/raw/baibala-hemolele-1839/20260501/tos_snapshot.html`,
   SHA-256 `254c552c3519f503d98fab03e46616b7789d3ac95cbbc5f41dd76d3e74af268c`
   (matches the SHA recorded in `decisions.md` line 314).

3. **HAW smoke fetch — Genesis 1–3 from Baibala 1839.** First execute
   attempt failed: `--tos-snapshot` passed as a relative path triggered
   `pathlib.Path.relative_to(REPO_ROOT)` ValueError in
   `206_fetch_baibala_raw.py:fetch_one()`. Retried with absolute path
   (`$(pwd)/...`), succeeded. 3 chapters written, 3 distinct SHAs, 3
   distinct content lengths (14865 / 12849 / 12980 bytes).

4. **HAW bounded fetch — Genesis 4–50 from Baibala 1839.** Used
   `--limit 50 --chapters 4-50` to avoid re-fetching ch. 1–3. Polite
   rate limit `1.5 s/chapter` from registry honored by the script.
   47 chapters written. All 50 GEN chapter HTML files now on disk
   (`data/raw/baibala-hemolele-1839/20260501/GEN_001.html` … `GEN_050.html`,
   840 KB total). `fetch.jsonl` ledger has 54 rows total
   (4 prior + 3 smoke + 47 batch).

5. **ENG KJV / ASV anchor.** Dry-run → 2 eligible artifacts;
   `--check-headers` → both 200 OK, `application/zip`, sizes 2 465 879 B
   (KJV) and 2 874 452 B (ASV); `--execute` → both written under
   `data/raw/bible-eng-pd-anchor/20260501/` (5.1 MB total). No gates
   needed; no rights-review or pending-endpoint flags required.

6. **Candidate build dry-run.** Two passes:

   - First pass (default ENG fixture dir): 50 HAW chapters seen,
     1 chapter paired (GEN:1, the only chapter with an ENG fixture),
     5 rows — same as already on disk. As expected.
   - Second pass with `--eng-usfm-zip
     data/raw/bible-eng-pd-anchor/20260501/eng-kjv2006_usfm.zip`
     (`322` already supports USFM via `_load_usfm_parser_module()` →
     `scripts/206b_parse_eng_usfm.py`): **50 chapters paired, 1533
     rows emitted, 0 skipped**. All HAW Genesis verses pair against
     KJV verses by `(book, chapter, verse)`.

   **Did not run `--execute`.** The `text_en` field in dry-run rows
   still contains USFM Strong's-number inline annotations
   (`In the beginning|strong="H7225" God|strong="H0430" …`). The
   `206b_parse_eng_usfm.py` parser does not strip `|strong="…"`
   markers, and `322`'s `normalize_en()` does not strip them either.
   The fetch-plan exclusion explicitly calls this out: "USFM-to-plain-
   text extraction must drop … editorial brackets to avoid leaking
   non-translation tokens into target_text." Emitting 1533 rows with
   Strong-number leakage into `text_en` would be **overcounting on a
   contaminated field** — fails the task's "do not fabricate or
   overcount" gate. Hand-off to the USFM parser owner instead.

### Raw artifacts on disk (this pass)

| Path | Files | Bytes |
|---|---|---|
| `data/raw/baibala-hemolele-1839/20260501/GEN_*.html` | 50 chapter HTML | 840 KB |
| `data/raw/bible-eng-pd-anchor/20260501/eng-kjv2006_usfm.zip` | 1 zip | 2 465 879 |
| `data/raw/bible-eng-pd-anchor/20260501/eng-asv_usfm.zip` | 1 zip | 2 874 452 |

Provenance ledgers:
- `data/raw/baibala-hemolele-1839/fetch.jsonl` — 54 rows (per-chapter,
  with raw_sha256, source_url, fetch_timestamp, ToS snapshot path).
- `data/raw/bible-eng-pd-anchor/fetch.jsonl` — 2 rows (per-zip).

### Candidate rows produced this pass

**Zero new candidate rows.** Total candidate JSONL on disk unchanged
at 1612 (5 bible smoke + 121 tatoeba + 292 kaikki + 1194 andrews).

### Exact commands that worked

```bash
python3 scripts/107_collect_stage2_parallel.py
python3 scripts/206_fetch_baibala_raw.py --dry-run --side haw --book GEN --chapters 1-3
python3 scripts/206_fetch_baibala_raw.py --execute --side haw --book GEN --chapters 1-3 \
  --confirm-edition baibala-hemolele-1839 \
  --tos-snapshot "$(pwd)/data/raw/baibala-hemolele-1839/20260501/tos_snapshot.html"
python3 scripts/206_fetch_baibala_raw.py --execute --side haw --book GEN --chapters 4-50 \
  --limit 50 --confirm-edition baibala-hemolele-1839 \
  --tos-snapshot "$(pwd)/data/raw/baibala-hemolele-1839/20260501/tos_snapshot.html"
python3 scripts/207_fetch_stage2_parallel_raw.py --dry-run --source bible-eng-pd-anchor
python3 scripts/207_fetch_stage2_parallel_raw.py --check-headers --source bible-eng-pd-anchor
python3 scripts/207_fetch_stage2_parallel_raw.py --execute --source bible-eng-pd-anchor
python3 scripts/206b_parse_eng_usfm.py --self-test
python3 scripts/206b_parse_eng_usfm.py \
  --usfm-zip data/raw/bible-eng-pd-anchor/20260501/eng-kjv2006_usfm.zip \
  --book-codes GEN \
  --out-jsonl data/raw/bible-eng-pd-anchor/20260501/parsed/eng-kjv2006_GEN.jsonl
python3 scripts/322_build_bible_candidates.py --dry-run --from-raw 20260501
python3 scripts/322_build_bible_candidates.py --dry-run --from-raw 20260501 \
  --eng-usfm-zip data/raw/bible-eng-pd-anchor/20260501/eng-kjv2006_usfm.zip
```

### Blockers / hand-offs

- **Linus / adapter owner:** the USFM parser script
  `scripts/206b_parse_eng_usfm.py` already exists in the working tree
  (untracked) and `322` already wires it in via
  `--eng-usfm-zip` / `--eng-usfm-file`. Dry-run pairs all 50 HAW
  Genesis chapters against KJV and emits **1 533 rows**. The blocker
  is text quality, not infrastructure: `text_en` contains USFM
  Strong's-number inline annotations
  (`In the beginning|strong="H7225" God|strong="H0430" …`). Neither
  `206b_parse_eng_usfm.py` nor `normalize_en()` in
  `322_build_bible_candidates.py` strips `|strong="…"` markers,
  `\\add` / `\\add*` translator-supplied tokens, or section headers.
  Per fetch-plan `bible-eng-pd-anchor.exclusions_or_risks`, this
  needs to be cleaned before `--execute`. One-line fix in either
  script (regex `r'\|strong="[^"]*"'` → `''`) is the unblock; tests
  in `code/tests/test_bible_adapter.py` should grow a Strong's-number
  scrub case.

- **OPUS:** Untouched this pass per task scope. Still gated.

- **Future Baibala fetches:** if/when the USFM parser lands, the
  remaining 65 books (1 188 chapters total in a Protestant-canon Bible)
  can be pulled via the same `206_fetch_baibala_raw.py` invocation
  pattern with `--book` repeated. At 1.5 s/chapter that is ~30 minutes
  of polite fetching for the full HAW corpus; safe to do in chunks per
  book to keep run sizes bounded.

No commits made (per task directive).

---

## 2026-05-01T08:28Z — Bible HAW raw fetch: Exodus → Deuteronomy

### Scope chosen

Pentateuch minus Genesis (already on disk): **EXO, LEV, NUM, DEU**.
Total chapters this run: **137** (40 + 27 + 36 + 34).

Why this batch and not "all remaining books":
- `scripts/206_fetch_baibala_raw.py` has a hard `MAX_LIMIT_CHAPTERS=200`
  per invocation and no "all-book" mode. It accepts a single
  `--chapters` spec applied to every `--book` passed, so a single call
  spanning books with different chapter counts fails (Exodus 1-50
  rejected for max_chapter=40). Bounded, polite, book-by-book is the
  only safe pattern.
- Pentateuch is the next contiguous canonical block after Genesis,
  fits well under the 200-chapter cap, and at the registry's polite
  rate of 1.5 s/chapter is ~3.5 min of traffic to baibala.org —
  well-bounded, no overload risk.
- Did **not** run candidate build (`322`); per task scope, don't
  disrupt Linus's concurrent USFM materialization. Raw-only this pass.

### Exact commands

```bash
# Inspection
python3 scripts/206_fetch_baibala_raw.py --print-pin-status

# Dry-runs (one per book, since --chapters is shared across --book args)
python3 scripts/206_fetch_baibala_raw.py --dry-run --side haw --book EXO --chapters 1-40 --limit 200
python3 scripts/206_fetch_baibala_raw.py --dry-run --side haw --book LEV --chapters 1-27 --limit 200
python3 scripts/206_fetch_baibala_raw.py --dry-run --side haw --book NUM --chapters 1-36 --limit 200
python3 scripts/206_fetch_baibala_raw.py --dry-run --side haw --book DEU --chapters 1-34 --limit 200

# Execute (TOS snapshot + edition pin already on disk from prior pass)
TOS="$(pwd)/data/raw/baibala-hemolele-1839/20260501/tos_snapshot.html"
for spec in "EXO 1-40" "LEV 1-27" "NUM 1-36" "DEU 1-34"; do
  set -- $spec
  python3 scripts/206_fetch_baibala_raw.py --execute --side haw \
    --book $1 --chapters $2 --limit 200 \
    --confirm-edition baibala-hemolele-1839 \
    --tos-snapshot "$TOS"
done
```

All four runs completed cleanly:
- `[EXECUTE] fetched 40 chapter(s)` — Exodus
- `[EXECUTE] fetched 27 chapter(s)` — Leviticus
- `[EXECUTE] fetched 36 chapter(s)` — Numbers
- `[EXECUTE] fetched 34 chapter(s)` — Deuteronomy

### Raw artifacts added this pass

| Book | Files | Bytes |
|---|---|---|
| EXO | 40 | 567,354 |
| LEV | 27 | 388,943 |
| NUM | 36 | 547,196 |
| DEU | 34 | 490,140 |
| **Total this pass** | **137** | **1,993,633** (~1.95 MB) |

Cumulative under `data/raw/baibala-hemolele-1839/20260501/`:
- 187 canonical-book chapter HTML files (50 GEN + 137 Pentateuch tail)
- Plus 2 legacy fixtures (`haw_genesis_1.html`, `haw_john_3.html`) and
  `tos_snapshot.html` from earlier passes.
- `fetch.jsonl` provenance ledger now at **191 lines** (was 54 → +137).

### Candidate emission

**Zero candidates emitted this pass — by design.** Per task:
> "Do not emit candidates unless the exact matching English USFM path
> is already proven clean and the candidate build can be bounded to
> the fetched books without disrupting Linus's concurrent
> materialization."

`scripts/322_build_bible_candidates.py` was NOT invoked. Raw HAW chapters
sit on disk awaiting Linus's clean-USFM-pass to run book-bounded
candidate builds against EXO/LEV/NUM/DEU.

### Next recommended Bible batch

After Pentateuch ships clean candidates, the next bounded HAW batch
should be the **Historical books group 1: JOS (24) + JDG (21) + RUT (4)
= 49 chapters**. That stays well under the 200-chapter cap, completes
in ~75 s of polite traffic, and represents another contiguous canonical
block. Following that: 1SAM/2SAM/1KGS/2KGS = 31+24+22+25 = 102 chapters
(also under cap). Continue book-group-by-book-group; don't try the full
remaining canon in one invocation — the per-call cap and the shared
`--chapters` spec across `--book` args make per-book/group invocation
the right shape.

### Blockers

None for raw fetch. Candidate emission for EXO/LEV/NUM/DEU is gated on
Linus confirming the USFM Strong's-marker cleanup also covers these
books and that `322`'s book-bounded mode is safe to invoke concurrently
with his materialization work. Surfaced in
`.squad/decisions/inbox/frank-bible-next-fetch.md`.

No commits made.

## 2026-05-02T00:00Z — Bible HAW raw fetch: Joshua + Judges + Ruth

### Scope chosen

Historical books group 1: **JOS (24) + JDG (21) + RUT (4) = 49 chapters**.
Contiguous canonical block immediately following Pentateuch. Well under
the script's 200-chapter cap; ~75 s of polite (1.5 s/req) traffic per
book group. Linus is concurrently materializing only GEN/EXO/LEV/NUM/DEU,
so JOS/JDG/RUT raw are safe to land without disturbing his candidate
work.

### Exact commands

```bash
# Dry-runs (one per book — --chapters is shared across --book args)
python3 scripts/206_fetch_baibala_raw.py --dry-run --side haw --book JOS --chapters 1-24 --limit 200
python3 scripts/206_fetch_baibala_raw.py --dry-run --side haw --book JDG --chapters 1-21 --limit 200
python3 scripts/206_fetch_baibala_raw.py --dry-run --side haw --book RUT --chapters 1-4  --limit 200

# Execute (TOS snapshot + edition pin already on disk)
TOS="$(pwd)/data/raw/baibala-hemolele-1839/20260501/tos_snapshot.html"
for spec in "JOS 1-24" "JDG 1-21" "RUT 1-4"; do
  set -- $spec
  python3 scripts/206_fetch_baibala_raw.py --execute --side haw \
    --book $1 --chapters $2 --limit 200 \
    --confirm-edition baibala-hemolele-1839 \
    --tos-snapshot "$TOS"
done
```

All three runs completed cleanly:
- `[EXECUTE] fetched 24 chapter(s)` — Joshua
- `[EXECUTE] fetched 21 chapter(s)` — Judges
- `[EXECUTE] fetched  4 chapter(s)` — Ruth

### Raw artifacts added this pass

| Book | Files | Bytes |
|---|---|---|
| JOS | 24 | 334,964 |
| JDG | 21 | 315,870 |
| RUT |  4 |  51,374 |
| **Total this pass** | **49** | **702,208** (~686 KiB) |

Cumulative under `data/raw/baibala-hemolele-1839/20260501/`:
- 236 canonical-book chapter HTML files (50 GEN + 137 Pentateuch tail
  + 49 Joshua/Judges/Ruth) plus 2 legacy fixtures and `tos_snapshot.html`.
- `fetch.jsonl` provenance ledger now at **240 lines** (was 191 → +49).
  Per-book provenance row counts confirmed: JOS=24, JDG=21, RUT=4.

### Candidate emission

**Zero candidates emitted this pass — by design.** Per task scope
("Do not emit candidates in this task"). `scripts/322_build_bible_candidates.py`
was NOT invoked. Raw HAW chapters sit on disk awaiting Linus's next
clean-USFM-pass for JOS/JDG/RUT before any book-bounded candidate build.

### Next recommended Bible batch

After Linus extends his clean-USFM materialization to JOS/JDG/RUT, the
next bounded HAW batch is **1SA (31) + 2SA (24) + 1KI (22) + 2KI (25)
= 102 chapters** — still under the 200-chapter cap, ~2.5 min of polite
traffic. Following that: 1CH/2CH/EZR/NEH/EST = 29+36+10+13+10 = 98
chapters (also under cap). Continue book-group-by-book-group.

### Blockers

None for raw fetch. Candidate emission for JOS/JDG/RUT is gated on
Linus extending USFM cleanup + book-bounded `322` invocation to those
books. Surfaced in `.squad/decisions/inbox/frank-bible-jos-rut-fetch.md`.

No commits made.

## 2026-05-03T00:00Z — Bible HAW raw fetch: 1SA + 2SA + 1KI + 2KI

### Scope chosen

Historical books group 2: **1SA (31) + 2SA (24) + 1KI (22) + 2KI (25)
= 102 chapters**. Contiguous canonical block immediately following
JOS/JDG/RUT. Under the script's 200-chapter cap; ~2.5 min of polite
(1.5 s/req) per-book traffic. Edition pin (`linus`,
`baibala-hemolele-1839`) and ToS snapshot already on disk under
`data/raw/baibala-hemolele-1839/20260501/tos_snapshot.html`.

### Exact commands

```bash
# Dry-runs (one per book — --chapters is shared across --book args)
python3 scripts/206_fetch_baibala_raw.py --dry-run --side haw --book 1SA --chapters 1-31 --limit 200
python3 scripts/206_fetch_baibala_raw.py --dry-run --side haw --book 2SA --chapters 1-24 --limit 200
python3 scripts/206_fetch_baibala_raw.py --dry-run --side haw --book 1KI --chapters 1-22 --limit 200
python3 scripts/206_fetch_baibala_raw.py --dry-run --side haw --book 2KI --chapters 1-25 --limit 200

# Execute
TOS="$(pwd)/data/raw/baibala-hemolele-1839/20260501/tos_snapshot.html"
for spec in "1SA 1-31" "2SA 1-24" "1KI 1-22" "2KI 1-25"; do
  set -- $spec
  python3 scripts/206_fetch_baibala_raw.py --execute --side haw \
    --book $1 --chapters $2 --limit 200 \
    --confirm-edition baibala-hemolele-1839 \
    --tos-snapshot "$TOS"
done
```

All four runs completed cleanly:
- `[EXECUTE] fetched 31 chapter(s)` — 1 Samuel
- `[EXECUTE] fetched 24 chapter(s)` — 2 Samuel
- `[EXECUTE] fetched 22 chapter(s)` — 1 Kings
- `[EXECUTE] fetched 25 chapter(s)` — 2 Kings

### Raw artifacts added this pass

| Book | Files | Bytes |
|---|---|---|
| 1SA | 31 | 437,082 |
| 2SA | 24 | 361,200 |
| 1KI | 22 | 354,473 |
| 2KI | 25 | 369,786 |
| **Total this pass** | **102** | **1,522,541** (~1.45 MiB) |

Cumulative under `data/raw/baibala-hemolele-1839/20260501/`:
- 338 canonical-book chapter HTML files (50 GEN + 137 EXO/LEV/NUM/DEU
  + 49 JOS/JDG/RUT + 102 1SA/2SA/1KI/2KI) plus 2 legacy fixtures,
  `tos_snapshot.html`, and `FETCH_PROVENANCE.json`.
- `fetch.jsonl` provenance ledger now at **342 lines** (was 240 → +102).
  Per-book provenance row counts confirmed for this batch:
  1SA=31, 2SA=24, 1KI=22, 2KI=25. Matches canonical chapter counts.
- No duplicates; no unexpected book directories.

### Candidate emission

**Zero candidates emitted this pass — by design.** Raw-only task per
spec. `scripts/322_build_bible_candidates.py` was NOT invoked.

### Next recommended Bible batch

After Linus extends his clean-USFM materialization to
1SA/2SA/1KI/2KI, the next bounded HAW batch is
**1CH (29) + 2CH (36) + EZR (10) + NEH (13) + EST (10) = 98 chapters**
— under the 200-chapter cap, ~2.5 min of polite traffic. Following
that: JOB (42) + PSA (150) likely needs splitting (PSA alone is 150,
under cap but heavy — fetch it solo).

### Blockers

None for raw fetch. Candidate emission for the historical books
remains gated on Linus's USFM-cleanup + book-bounded `322` invocation.

No commits made.

## 2026-05-04T00:00Z — Ready-made Hawaiian dataset sweep (FineWeb2-style hubs)

### Scope

User asked whether we ever surveyed FineWeb2-style ready-made hub
datasets for Hawaiian (mono + parallel), beyond raw source websites.
Research-only sweep; no code, no fetches.

### What I confirmed already in repo

- **Stage 1 mono:** FineWeb-2 haw_Latn (pinned + fetched: 95,507 train
  + 887 test, split via 310). Hawaiian Wikipedia + Wikisource dumps
  in plan.
- **Stage 2 parallel (already in `stage2-parallel-fetch-plan.json`):**
  Tatoeba (fetched, 121 candidates), OPUS subsets (Tatoeba mirror +
  QED/Ubuntu/GNOME/KDE4), NLLB mined (allenai/nllb), BibleNLP
  (bible-nlp/biblenlp-corpus), Global-PIQA parallel haw (eval-only),
  Taxi1500 (eval-only), Wikimedia CX, kaikki Wiktionary, Andrews
  1865 vocab, Hawaiian Kingdom statutes.
- **Eval probes already filed:** FLORES+, Belebele, WMT24++ all
  recorded in `deferred_or_excluded` — **Hawaiian verified absent**
  on 2026-05-02. Future agents will not silently re-add them.
- **Excluded:** JW300 (ToS), general CC slices, social media,
  ungrounded LLM synthetic.

### What was NOT surveyed before — gap is on the Stage-1 mono side

Searched `docs/`, `data-sources/`, `scripts/`, `.squad/`. Found zero
references to: CulturaX, OSCAR-2301, CC100, mC4, MADLAD-400,
Glot500-c, GlotCC-v1, HPLT (v1 or v2), WikiMatrix, NTREX-128, xP3,
Aya. The plan is dense on Stage-2 hub coverage and sparse on
Stage-1 hub coverage beyond FineWeb-2.

### Verified haw_Latn presence (web-search receipts, no fetch)

| Dataset | Has haw_Latn? | Notes |
|---|---|---|
| MADLAD-400 | **Yes** | ~109k tokens; tiny. ODC-By per-source CC. |
| Glot500-c | **Yes** | ≥30k sentence threshold for inclusion. |
| GlotCC-v1 | **Yes** | Broad CC, 1000+ langs. |
| HPLT v2 cleaned | **Yes (explicit)** | data.hplt-project.org/two/cleaned/ lists `haw_Latn`. |
| OSCAR-2301 | Likely yes (haw was in 22.01); not directly probed today. |
| CulturaX | Likely **no** (167 langs, haw not confirmed). |
| CC100 | **No** (100 langs, haw not in list). |
| mC4 | **No** (101 langs, haw not in list). |
| WikiMatrix | **No** (85 langs, haw not among them). |
| NTREX-128 | **No** (haw not in `LANGUAGES.tsv`). |

### Top-3 ready-made adds for the 80k Stage-2 target

Honest answer: **no new external parallel dataset moves the needle
beyond what is already planned.** Top-3 is "execute the planned
unfetched":

1. **NLLB mined haw-eng** (`allenai/nllb`) — largest expected yield;
   mined-budget caps apply; never dev/test.
2. **BibleNLP `haw1868`** (`bible-nlp/biblenlp-corpus`) — clean
   verse-aligned, bounded yield (~31k verses); subject to the
   ≤30% bible-token-share cap *as a class* (Linus's gate; risk of
   double-counting with the Baibala raw fetch already on disk).
3. **OPUS bible-uedin haw subcorpus** — not currently in plan; same
   Baibala source as our direct Baibala fetch and as BibleNLP.
   Useful as a **dedup cross-check**, not as additive yield.

### Stage-1 ready-made adds (separate from 80k target)

Recommend adding **MADLAD-400 / Glot500-c / HPLT-v2 cleaned**
(`haw_Latn` each) to `hawaiian-data-sources.json` as
`pending_endpoint_check`, adapter modeled on
`205_fetch_fineweb2_haw_raw.py`. Net token volume probably small
(FineWeb-2 already absorbs most public Hawaiian web text), but
buys us:
- a second-source signal on FineWeb-2 cleaning gates (paragraph LID,
  ʻokina canonicalization);
- independent dedup hashes for Stage-1 contamination claims.

Asked Linus for rights-posture sign-off and whether the
second-source dedup value is worth adapter cost given the 80k
Stage-2 focus. Surfaced in
`.squad/decisions/inbox/frank-ready-dataset-sweep.md`.

### Decisions locked

- **Do not add** CulturaX / CC100 / mC4 / WikiMatrix / NTREX-128 /
  xP3 to the plan — verify-and-record-absent only when a probe is
  cheap. They either lack `haw` or are downstream of sources we
  already pull.
- **Stage 2 80k focus:** execute NLLB → BibleNLP → finish OPUS
  endpoint verification before chasing new external parallel sources.

### No commits, no fetches.


## 2026-05-01T08:52:06Z — Ready-made Hawaiian dataset sweep complete; merged to decisions

**Status:** RESEARCH / INVENTORY — no code or data fetched.

### Survey scope
Searched for ready-made public datasets already packaging Hawaiian (`haw`) text or parallel pairs (analogous to FineWeb-2 for Stage 1).

### Key findings
- **Stage 2 hub sources:** Well covered in existing plan. Explicitly probed and confirmed absent: FLORES+, Belebele, WMT24++ (no haw). Major ready-made resources (Tatoeba, OPUS, NLLB, BibleNLP, Global-PIQA, Taxi1500) already inventoried.
- **Stage 1 hub sources (gap):** Previously not comprehensively surveyed beyond FineWeb-2.
  - **Present:** MADLAD-400 (~109k tokens), Glot500-c, GlotCC-v1, HPLT v2 cleaned (all haw_Latn available).
  - **Absent:** CC100, mC4, WikiMatrix, NTREX-128, likely CulturaX (all verified-absent or confirm-absent).

### Top-3 ready-made additions ranked
For Stage 2 80k row target, no new external dataset moves needle materially beyond plan. Honest top-3 is "execute what we already planned":

1. **NLLB mined haw-eng** — in plan, not yet fetched. Largest expected yield. Mined → ≤synthetic/mined budget, never dev/test, never released.
2. **BibleNLP haw1868** — in plan, not yet fetched. Verse-aligned Baibala vs eBible. Clean alignment, ~31k verses, complies with ≤30% bible-token-share cap.
3. **OPUS bible-uedin haw subcorpus** — not in plan; ~31k haw-eng verse pairs. However: same Baibala source as direct fetch + BibleNLP path above — risk of triple-counting. Treat as cross-check/dedup signal, not additive.

### Stage 1 candidate adds (awaiting Linus rights sign-off)
- **MADLAD-400 haw_Latn**, **Glot500-c haw_Latn**, **HPLT v2 cleaned haw_Latn**: All worth single fetch each, deduped against FineWeb-2 clean train hashes. Net gain small (FineWeb-2 already harvests most public Hawaiian web text), but provide second-source signal on cleaning gates and independent dedup hashes.

### Decisions locked
- **Do not add** CulturaX / CC100 / mC4 / WikiMatrix / NTREX-128 / xP3 — verify-and-record-absent only.
- **Stage 2 80k focus:** Execute NLLB → BibleNLP → finish OPUS verification. Do not block on adding new external parallel datasets.
- **Stage 1 three probes** (MADLAD-400, Glot500-c, HPLT v2) require Linus rights review before adapter implementation.

### Full report
`.squad/decisions/inbox/frank-ready-dataset-sweep.md` (merged to `.squad/decisions.md` by Scribe).

### No commits, no fetches.

## 2026-05-02 — Baibala 1839 raw fetch: 1SA + 2SA + 1KI + 2KI (COMPLETE)

**Task:** Fetch 1 Samuel, 2 Samuel, 1 Kings, 2 Kings raw from baibala.org.

**Outcome:** ✅ COMPLETE — 102 chapters, 1.5 MB fetched; provenance rows 240→342 appended.

- 1SA: 31 chapters, 477 KB
- 2SA: 24 chapters, 376 KB
- 1KI: 22 chapters, 369 KB
- 2KI: 25 chapters, 300 KB
- Cumulative HAW on disk: 236 chapters

**Candidate emission:** Deferred pending Linus USFM cleanup confirmation. No code changes to fetcher; next batch (1CH, 2CH, EZR, NEH, EST) follows identical pattern.

**Decision merged:** `.squad/decisions/inbox/frank-bible-jos-rut-fetch.md` → `.squad/decisions.md`

## 2026-05-03 — Hub dataset row counts (confirmed via HF datasets-server + OPUS API)

User asked for row counts of ready-made Hawaiian dataset releases (analogous to FineWeb-2), not local data.

### Monolingual (rows = documents/segments per hub viewer)

| Dataset (HF) | Config | Rows (confirmed) | Bytes | License | Notes |
|---|---|---:|---:|---|---|
| HuggingFaceFW/fineweb-2 | haw_Latn | **96,394** (train 95,507 + test 887) | 128.7 MB parquet | ODC-By 1.0 | Already in our local data (Stage 1). |
| cis-lmu/Glot500 | haw_Latn | **1,053,668** (train) | 137.8 MB parquet | mixed/component-wise | Aggregate over many sub-sources; high duplication risk vs FineWeb-2. |
| cis-lmu/GlotCC-V1 | haw-Latn | **7,058** (train) | 20.2 MB parquet | CC0 (CC dump derived) | Smaller, single-pass CommonCrawl pull. |
| allenai/c4 (mC4 multilingual) | haw | **84,398** (train 84,312 + val 86) | 131.4 MB parquet | ODC-By | **Correction to earlier history**: mC4 *does* have haw. Previously marked verify-and-record-absent. |
| HPLT/HPLT2.0_cleaned | — | **0 / not present** | — | — | **Correction**: HPLT v2 cleaned does NOT have haw_Latn (only hat/hau/heb…). Prior history was wrong. |
| allenai/MADLAD-400 | haw | unknown via viewer (no parquet); paper reports ~109k tokens / a few thousand docs | — | CC-BY-4.0 (research) | Viewer can't size; cite paper. |
| oscar-corpus/OSCAR-2301 | — | gated; not queryable anonymously | — | CC0 (CC derived) | Auth needed. |
| uonlp/CulturaX | — | gated; not queryable anonymously | — | mC4+OSCAR derived | Auth needed; expected absent (built from mC4+OSCAR; haw may pass through). |
| statmt/cc100 | — | viewer error; haw not in CC100 (per Conneau et al. 2019) | — | — | Confirmed absent. |

### Parallel / eval (rows = sentence pairs)

| Dataset | Config | Rows (confirmed) | License | Stage 2 fit |
|---|---|---:|---|---|
| OPUS translatewiki | en-haw v2025-01-01 | **2,219** pairs | CC0 (translatewiki ToS) | Stage 2 train-eligible after dedup. |
| OPUS wikimedia | en-haw v20230407 | **374** pairs | CC BY-SA | Stage 2 train (license flowdown). |
| OPUS QED | en-haw v2.0a | **167** pairs | CC BY-NC-ND | Stage 2 mined-only / non-commercial caution. |
| OPUS Tatoeba | en-haw v2023-04-12 | **93** pairs | CC BY 2.0 FR | Eval-friendly; tiny. |
| OPUS Ubuntu | en-haw v14.10 | 0 usable | — | Empty for haw. |
| davidstap/biblenlp-corpus-mmteb | eng-haw | **1,955** verses (train 1,779 / val 81 / test 95) | per BibleNLP | Eval-tier subset of full BibleNLP. |
| bible-nlp/biblenlp-corpus | full | viewer blocked (custom code); ~31k haw1868 verses per prior probe | mixed bible-text licenses | Stage 2 train (≤30% bible-token cap). |
| facebook/flores, openlanguagedata/flores_plus | — | viewer blocked / gated; FLORES+ adds haw_Latn (~997 dev + 1012 devtest); FLORES-200 itself does **not** include haw | CC BY-SA 4.0 | Eval-only. |
| allenai/nllb (NLLB mined bitext) | — | viewer blocked (custom code); Meta release lists haw_Latn-eng_Latn but counts must be read from manifest | ODC-By | Stage 2 mined-tier; never dev/test. |
| Helsinki-NLP/tatoeba_mt | eng-haw | **0** (no haw config exposed) | — | Use OPUS Tatoeba directly. |
| Helsinki-NLP/opus-100 | — | **0** (no haw) | — | Confirmed absent. |
| mteb/NTREX | — | **0** (no haw) | — | Confirmed absent. |
| Helsinki-NLP/wikimatrix | — | gated/no public viewer; haw not in WikiMatrix v1 per paper | — | Confirmed absent in v1. |

### OPUS aggregate (any pair touching haw)

5 corpora total: translatewiki, wikimedia, QED, Tatoeba, Ubuntu. **bible-uedin is NOT in OPUS for haw** — earlier history note about an "OPUS bible-uedin haw subcorpus" was incorrect; that Baibala path only flows through BibleNLP / direct baibala.org fetch.

### Decisions / corrections to prior records

- mC4 (allenai/c4) `haw` is **present** (84k docs); update verify-and-record-absent ledger.
- HPLT v2 cleaned `haw_Latn` is **absent**; remove from candidate Stage 1 add list.
- OPUS bible-uedin haw is **absent**; the only hub-side bible parallel is BibleNLP.
- No new actions on the 80k Stage 2 target — these confirm priorities already locked (NLLB → BibleNLP).

Inbox note written: `.squad/decisions/inbox/frank-hub-dataset-row-counts.md`.

### No commits, no fetches.

---

## Session: Hub dataset row counts + corrections (2026-05-01T09:06:22Z)

**Scribe action:** Merged Frank hub dataset row counts into decisions.md, updated header, marked prior survey superseded.

**Outcome:** Three corrections locked:
1. mC4 haw (allenai/c4) is present, 84k docs — deprioritize (CommonCrawl overlap with FineWeb-2).
2. HPLT v2 cleaned haw_Latn absent — drop from Stage 1 candidate-add.
3. OPUS bible-uedin haw nonexistent — no triple-counting risk.

**Updated Stage 1 candidate-add (for Linus rights review):** MADLAD-400, Glot500, GlotCC-V1 only.

**Logs written:**
- `.squad/orchestration-log/2026-05-01T09-06-22Z-frank-hub-dataset-row-counts.md`
- `.squad/log/2026-05-01T09-06-22Z-hub-dataset-row-counts.md`

**Inbox consolidated:** `.squad/decisions/inbox/frank-hub-dataset-row-counts.md` merged; file deleted.

**Next:** Linus rights review on MADLAD-400, Glot500, GlotCC-V1.

## 2026-05-03 — Ulukau / Nupepa.org live discovery (signed-in Chrome via CDP)

**Status:** DISCOVERY — no bulk fetch, no commits, no rights commitment. Provenance artifacts under `data/raw/ulukau-discovery/` (gitignored).

### Source identification

`https://www.nupepa.org/` is the public face of the Ulukau **Hawaiian Newspaper Collection** (Ka ʻOhina Nūpepa ʻŌlelo Hawaiʻi). Backend is **Veridian (CVS-D2024.05.10) over Greenstone**, descended from NZDL Niupepa. Same query-param family as the Baibala collection we already pull (`?a=`/`?d=`/`?cl=`).

### Endpoints (URL grammar)

State suffix is mandatory: `e=-------haw-20--1--txt-txIN%7CtxNU%7CtxTR%7CtxTI---------`

| Verb | URL | What it returns |
|---|---|---|
| Issue | `/?a=d&d=<OID>` | HTML issue-viewer shell |
| Section text | `/?a=da&command=getSectionText&d=<OID>&f=AJAX&<state>` | **XML** with HTML-inside-CDATA: `<SectionText>` = the article OCR (Hawaiian) |
| Issue TOC | `/?a=da&command=getDocumentContents&d=<ISSUE_OID>&f=AJAX&<state>` | XML/HTML — per-page article list |
| Section metadata | `/?a=da&command=getSectionMetadata&d=<OID>&f=AJAX&<state>` | XML |
| User translation | `/?a=da&command=getUserTranslation&d=<OID>&f=AJAX&<state>` | XML — community-contributed English (sparse) |
| Persistent link | `/?a=da&command=getPersistentLink&d=<OID>&f=AJAX&<state>` | XML — canonical citation URL |
| Title browse | `/?a=cl&cl=CL1[&sp=<PAPER>][&ai=1]` | HTML — calendar / large article index |
| Date browse | `/?a=cl&cl=CL2[.<YYYY>[.<MM>]][&sp=<PAPER>]` | HTML |
| Place browse | `/?a=pcl&pcl=PCL1` | HTML |
| Search | `/?a=q&q=<term>&adv={0,1}` | HTML, faceted |

OID grammar: `<PAPER><YYYYMMDD>-<ISSUE>(.<page>(.<article>(.<sub>)?)?)?`. Example: `KNK19040722-01.2.16.3` = Ka Nupepa Kuokoa, 22 July 1904, page 2, article 16, sub 3.

### Scale

Per the public Help page (saved as `09-nupepa-help-en.txt`):

* ~**69,000 pages** total in the collection.
* **100%** of pages have **automatic OCR article text** (article-segmented; headlines human-corrected).
* ~**21,000 pages** also have human-keyed transcribed text.
* User translations exist for a small number of articles.
* 50+ newspaper title codes spanning roughly 1834–1948. Ka Nupepa Kuokoa (KNK) alone shows **3,316 articles** in its title index badge.

### Text format

Article text is delivered as an **HTML fragment, entity-encoded inside an XML envelope**. Smoke-tested on `KNK19040722-01.2.1`: ~2.7 KB XML, ~900 chars of (mediocre) Hawaiian OCR after de-tagging. Quality matches the standard Niupepa OCR baseline. No JSON API. No bulk corpus dump exposed by the UI; page imagery is OpenSeadragon DZI (not probed).

### Rights snapshot — DO NOT TREAT AS LEGAL CONCLUSION

Ulukau site-wide TOS (Aug 21, 2018, captured `08-copyright.txt`):

* Copyright owners: Ka Haka ʻUla O Keʻelikōlani College of Hawaiian Language (UH Hilo) + ALU LIKE, Inc.
* "All Rights Reserved." **Personal use only; no commercial use; no copying to other websites.**
* Users responsible for their own fair-use determination; written permission required for redistribution.
* No machine-readable license; no per-page rights metadata in the AJAX responses.

Backend originally NZDL Niupepa — the underlying scans and OCR derive from the Bishop Museum / Awaiaulu / Hale Kuamoʻo digitization program. Some upstream pages may carry separate rights.

### Recommendation for next adapter step

1. **Block** on Linus rights review before any `--execute` run. Site TOS is restrictive and explicitly bars copying to other websites. We can keep this for **prototype/internal** use only, never released or republished.
2. If Linus clears (with prototype-only flag): build `data-sources/nupepa/fetch.py` modeled on `data-sources/bible/` adapter:
   * Pin enumeration via CL1 (per-paper) + CL2.YYYY.MM (per-month) → issue OID list → per-section AJAX `getSectionText` → strip HTML → NFC + ʻokina canonicalize → SHA256 raw + clean.
   * Polite rate (≥1 s between AJAX hits) — the underlying Greenstone is single-host shared infra; bulk = noisy.
   * Cloudflare interstitial active on first request: adapter must do the Cloudflare-cleared GET via the same browser channel OR via a long-lived `requests.Session` with sane UA + retries (not yet validated).
   * Save raw XML response per OID to `data/raw/nupepa/<paper>/<issue>/<section>.xml` for provenance, plus the parsed text alongside.
3. Stage 2 fit: this is **monolingual Hawaiian** — feeds Stage 1 + downstream BT pipelines, not Stage 2 parallel target directly. The "translation" facility is sparse user-contributed English and not a meaningful parallel source on its own. Treat user translations as a tiny (<<1k) eval-only candidate set if Linus/Rusty want a domain-news eval slice.
4. Image/DZI ingestion is not justified for the LLM track.

### Provenance saved

`data/raw/ulukau-discovery/` (gitignored):
* `01-homepage.html`, `02-nupepa-home.html`, `03-nupepa-doc.html`, `05-section-text.{xml,html}`
* `06-classifier-CL1.html`, `07-knk-list.html`, `07-knk-body.html`
* `08-{copyright,privacy,about,nupepa_terms}.{html,txt}`
* `09-nupepa-help-en.{html,txt}` (full Help page with OCR coverage numbers)
* `veridian-doc.js`, `pdnupepa.min.js` (vendor JS confirming AJAX URLs)
* `cdp.py`, `README.md` (this discovery's index)

No cookies, auth headers, local storage or session secrets were read or recorded.

### No commits, no fetches into the corpus.

## 2026-05-01T13:35Z — Stage 2 Ulukau-family pivot away from Nupepa

User correction landed (decisions.md 2026-05-01T13:28:17-07:00):
Nupepa/newspapers are HAW-monolingual OCR, not Stage 2 candidates.
Pivoted Ulukau-family Stage 2 discovery to bilingual/parallel surfaces.

### Learnings — Ulukau-family Stage 2 surface map

- **Ka Hoʻoilina (`hooilina.org`)** is the only Ulukau-family resource
  *explicitly designed* as bilingual: every document is published in
  three versions (original HAW transcription, modernized HAW, English
  translation) with editorial cross-references and per-version textual
  notes. Greenstone CGI on the same Veridian AJAX surface family as
  Nupepa/Baibala — `?a=da&command=getSectionText|getDocumentContents`
  endpoints work the same; only the OID grammar and `e=` state suffix
  differ. Editorial intro at
  `?a=p&p=edintro&gg=text` is the canonical rights+structure source.
  Editorial-layer copyright: Kamehameha Schools 2002–2004; reuse
  clause "noa i ka lehulehu akea ... me ke koina nae" requires source
  HAW citation alongside any reuse of modernized HAW or English.
  Underlying 19c source documents are PD by age.

- **Wehewehe (`wehewehe.org`)** = Greenstone `hdict` CGI fronting 14
  dictionaries. Per-entry doc IDs `D<numeric>` carry side tag
  `(Hawaiʻi)` vs `(Pelekānia)` — clean structural haw↔en pair surface.
  Lookup endpoint: `?a=q&q=<word>&l=haw`; entry: `?a=d&d=D<id>`. PD
  subset = Andrews 1836, Emerson 1845, Andrews 1865, Hitchcock 1887,
  Parker 1922, Dictionary of Biblical Words 1872. Modern dicts
  (Pukui-Elbert 1986, Māmaka Kaiao 2003, Combined 2020,
  Place Names 1974/2002, Kent 1986, Legal Land-Terms 1995) are
  copyrighted and out of scope without explicit clearance.
  Judd/Pukui/Stokes 1943 needs renewal-status check (Linus).

- **Puke / Nā Puke (`puke.ulukau.org`)** = Ulukau-Books custom UI on
  `?a=d&d=EBOOK-<ID>`. Per-book metadata field `ʻŌlelo` exposes
  monolingual-HAW vs monolingual-EN vs bilingual at the listing level —
  this is the only Ulukau-family collection where the "is it bilingual?"
  question is answered structurally before fetching the body. Bilingual
  subset is small; manual rights triage required per book; rank below
  Hoʻoilina + Wehewehe-PD.

- **Ulukau portal `ulukau.org`** is just a federated landing page for
  the above. The `gsdl2.85/cgi-bin/library.cgi` Greenstone instance
  serves several smaller bilingual collections (`ahcchist`, `ahccreso`)
  that overlap with the Hawaiian Kingdom statutes already in the
  fetch plan; they share the Hoʻoilina pilot adapter shape.

- **Nupepa.org**: confirmed monolingual HAW OCR, NOT a Stage 2 source.
  Existing `data/raw/ulukau-discovery/` snapshot retained as a
  Veridian/Greenstone protocol reference for adapter pattern reuse,
  not as a Stage 2 candidate.

- **Mele / Kaniʻāina / Algene / Photos**: out of Stage 2 text scope
  (cultural-escalate categories, audio/video, image, or genealogical).

### Recommended adapter-pilot

Ka Hoʻoilina, gated on Linus rights review of Kamehameha Schools
editorial-layer reuse clause. Reuses ~80% of the Veridian discovery
already done. Honest pair-yield estimate: O(low-thousands) of
paragraph-level haw↔eng pairs after segmentation; firm number requires
a non-bulk enumeration probe (deferred until rights cleared).

### Anti-actions

- Did not bulk fetch.
- Did not capture cookies/auth headers via CDP.
- Did not modify `data-sources/stage2-parallel-fetch-plan.json` —
  Hoʻoilina addition awaits Linus review.
- Did not touch `requirements.txt` or add any tooling.

### Artifacts

- Discovery snapshot: `data/raw/ulukau-stage2-discovery/20260501/`
- Decision proposal: `.squad/decisions/inbox/frank-stage2-ulukau-focus.md`

## 2026-05-01T20:34:18Z — Stage 2 Ulukau-family Focus (Pivot from Nupepa)

**Task:** Find concrete Ulukau-family Stage 2 source candidates after user directive pivoting away from Nupepa. Rank candidates by parallel-pair density, extraction cleanliness, rights posture, and novelty.

**Outcome:** PROPOSAL — 5 sources ranked + 1 adapter-pilot pick + gates staged

**Deliverables:**
1. **Pivot Decision** — Confirmed Nupepa is Stage 1-only (monolingual Hawaiian OCR). Kept Veridian/Greenstone protocol notes for adapter pattern reuse; removed newspapers from Stage 2 rotation.

2. **Ranked Stage 2 Candidates (Ulukau family):**
   - **1. Ka Hoʻoilina (`hooilina.org`)** ★★★★★ — `parallel-doc` trilingual (original HAW ↔ modernized HAW ↔ English translation), ~O(low-thousands) paragraph pairs, Greenstone CGI surface (80% reuse from Veridian protocol), explicit citation requirement (Kamehameha Schools editorial, 2002–2004). **NEW, recommended pilot.**
   - **2. Wehewehe combined dictionary (`wehewehe.org`)** ★★★★ — `dictionary-example` haw↔en pairs + example sentences, 14-dictionary set, Greenstone CGI, public-domain subset (Andrews/Emerson/Hitchcock/Parker pre-1925), ~5–15k pairs capped at 5k.
   - **3. Hawaiian Kingdom statutes** ★★★★ — `parallel-doc` bilingual government text, already in fetch plan as `hawaiian-kingdom-statutes-bilingual`, Greenstone surface, public domain (sovereign edicts, pre-1925).
   - **4. Nā Puke / Ulukau ebooks (`puke.ulukau.org`)** ★★ — mixed: bilingual subset = `dictionary-example` or `parallel-doc` candidates; custom Ulukau Books UI; manual rights triage required; **defer until top three shipped** (lower yield-per-hour).
   - **5. Baibala (`baibala.org`)** — `parallel-verse` Bible, already in plan (Tier A), no new work.

3. **Not Stage 2 fit (de-prioritized):**
   - Nupepa.org + tagged-newspaper collections (HAW-monolingual OCR; Stage 1 only, already covered by FineWeb-2 + Wiki).
   - Ka Waihona Mele (songs; cultural hard-escalate).
   - Kaniʻāina (audio/video; out of text scope).
   - Ka ʻOhina Kiʻi (photographs; not text).
   - Algene (genealogies; cultural hard-escalate).
   - HPN (Hawaiian Place Names; dictionary glossary at best, not bilingual pairs).

4. **Recommended Adapter-Pilot Pick** — **Ka Hoʻoilina (`hooilina.org`)**
   - Rationale: highest parallel-pair density; reuses 80% of Veridian/Greenstone discovery work; explicit trilingual design (vs. "hope an English version exists"); clearer rights posture than newspaper OCR; register diversity (HEN, gov't, newspapers, literary, student texts).
   - Pre-pilot gates (Linus to rule): (a) citation requirement OK for prototype-only? (b) confirm modernized-HAW × English as primary pair? (c) smoke fetch one document trio + capture ToS snapshot?

**Discovery Artifacts:**
- Saved under `data/raw/ulukau-stage2-discovery/20260501/`: editorial intro, document family browser, Wehewehe lookup + sample entry, Puke ebook sample listing, small snapshot files (landing pages, AJAX samples) — all small, no bulk fetch.

**Anti-Actions (for record):**
- Did NOT treat Nupepa as Stage 2.
- Did NOT bulk-fetch any Hoʻoilina, Wehewehe, or Puke document. Only landing pages + editorial intro + one dictionary lookup + one books listing retrieved.
- Did NOT read/persist cookies, localStorage, or auth headers.
- Did NOT modify `data-sources/stage2-parallel-fetch-plan.json` yet — Hoʻoilina after Linus rights review.
- Did NOT add tooling to `requirements.txt`.

**Supersedes:**
- Previous decision in inbox `frank-ulukau-nupepa-discovery.md` — which treated Nupepa as a Stage 2 candidate pending rights review. **Now explicitly Stage 1-only per Linus Stage 2 Source Filter.**

**Dependencies:**
- **Linus:** Rights/posture review on Hoʻoilina (citation requirement for Kamehameha Schools editorial layer) + Wehewehe per-dictionary PD cutoff.
- **Rusty:** Sanity-check whether Hoʻoilina "modernized HAW" spelling layer is right Hawaiian-side surface for Stage 2 training (vs. original-HAW).

**Next steps (Team):**
1. Linus: Rights review on Hoʻoilina + Wehewehe PD cutoff (P1 unblocker).
2. Rusty: Register/spelling-layer fit review on Hoʻoilina (secondary decision gate).
3. Frank (self): After Linus gate, smoke fetch Hoʻoilina one trio + capture Kamehameha Schools ToS; then propose adapter shape.


## 2026-05-01 — Stage 2 raw pull for sources 1, 2, 3 (Hoʻoilina + Wehewehe + HK statutes)

Per user directive 2026-05-01T14:02:02-07:00 ("pull 1,2,3 raw data, better
to get everything and then decide what we need"). Raw acquisition only —
no normalization, no candidate emission. All artifacts gitignored under
`data/`.

**Source 1 — Ka Hoʻoilina (`data/raw/hooilina-stage2/20260501/`):**
- 7 ToS / edintro / about pages, 8 parent doc landings, **331 leaf section
  HTML bodies** = 109 original-HAW (`.3`) + 109 modernized-HAW (`.5`) +
  109 English (`.7`) + 4 textual-notes (`.9`). 0 failures. ~4.6 MB.
- New finding (now fully verified): **leaf-OID suffix → spelling-layer
  mapping is uniform** across all 4 root issues. `.3` orig HAW, `.5`
  modernized HAW, `.7` English. The `.9` slot is the optional textual
  notes per section. The `?a=cl&cl=CL2.<n>.<m>` walk yields all 331 leaves
  in 22 classifier nodes; `cl=CL1` is alphabetical and contains no docs.
- Editorial-layer copyright = Kamehameha Schools 2002-2004 (per
  `tos/edintro.html`); underlying 19c HAW source PD by age. Reuse clause
  requires citing source HAW alongside any modernized-HAW or English reuse.
- Manifest: `manifest.jsonl` (348 rows) + `manifest_summary.json`.
- Fetcher: `scripts/_frank_pull_hooilina.py` (one-off; 1.2s rate limit;
  stdlib urllib only; respects `Crawl-delay: 1` from robots.txt).

**Source 2 — Wehewehe PD subset (`data/raw/wehewehe-stage2/20260501/`):**
- Mapped all 14 dictionary tags to wehewehe checkbox values (saved at
  `tos/`). PD pre-1925 PDFs pulled as full bytes via
  `https://ulukau.org/ulukau-books/cgi-bin/imageserver.pl?oid=<EBOOK-...>&getpdf=true`:
  - EBOOK-VOCABULARY (Andrews 1836, 38 MB), EBOOK-emd (Emerson 1845
    attribution, 24 MB), EBOOK-ANDREW (Andrews 1865, 62 MB), EBOOK-CDD
    (Biblical Words 1872, 394 MB), EBOOK-ehd (Hitchcock 1887, 283 MB),
    EBOOK-PARKER (Parker 1922, 148 MB). **Total 849 MB.**
- Inventory-only landings (no PDF) for: Pukui-Elbert 1986 (PED), Māmaka
  Kaiao 2003 (MKD), Judd/Pukui/Stokes 1943 (IHL — pending Linus US
  renewal-status check), Kent 1986 (THW01), Place Names 1974 (PEPN), 2002
  (CPN), Hawaiian Legal Land-Terms 1995 (DHLLT). Combined Hawaiian
  Dictionary 2020 (textchd) recorded in manifest as inventory-only without
  EBOOK fetch.
- 12 sample-query HTML probes saved at `sample_entries/` for headwords
  {aloha, wai, akua, iho, mauna, keiki} × {l=haw, l=en} so the per-entry
  D-id surface is preserved even though no per-entry walk was done.
- Manifest: `manifest.jsonl` (40 rows) + `manifest_summary.json`.
- Fetcher: `scripts/_frank_pull_wehewehe.py`.

**Source 3 — HK statutes paired imprints (`data/raw/hawaiian-kingdom-statutes-paired-imprints/20260501/`):**
- Augmented the prior 8 `_djvu.txt` OCR files (still byte-for-byte
  preserved) with: 8 IA metadata JSONs, **8 PDFs** (5 IA-Text-PDF + 3
  Google-Books "Image Container PDF" via follow-up pass for armsgoog /
  hawagoog / ricogoog items), 8 `_djvu.xml` page-coordinate OCR XMLs
  (~89 MB), 6 `_hocr_searchtext.txt.gz`, 8 `_meta.xml`, 6 `_marc.xml`. 0
  failures. ~231 MB total for this dir.
- Manifest: `manifest_complete.jsonl` + `manifest_summary.json`. Pre-existing
  `fetch.jsonl` from `scripts/208_fetch_hk_statutes_djvu.py` left
  untouched.
- Fetcher: `scripts/_frank_pull_hk_complete.py`.

**Total raw on disk after this session:** ~1.16 GB across the three roots.
**Failures:** 0 across all three pulls.

**Decision inbox:** `.squad/decisions/inbox/frank-stage2-raw-pull-123.md`.

**Skill update fact (Hoʻoilina):** `.3` / `.5` / `.7` leaf-suffix → orig
HAW / modernized HAW / English mapping is now CONFIRMED uniform across all
4 root issues, not just sampled. Future adapter can rely on it directly
(no per-section disambiguation walk needed).

## 2026-05-01T22:?? — Stage 2 raw provenance check (sources 1, 2, 3)

User asked Linus to do the structured-count pass for Stage 2; Frank's
parallel job was provenance/layout validation only. No raw data deleted;
no auth/cookie traffic; no scripts re-run.

### Results per root

**hooilina-stage2/20260501** — manifest.jsonl 346 entries (7 ToS + 8
parent docs + 331 sections). 346/346 local_path present on disk; sha256
verified on a 4-row sample. 0 failures. ToS/edintro snapshots present.
1 unmanifested orphan: `classifier/all_classifier_nodes.json` (full
classifier-walk dump used to enumerate leaves) — keep, useful re-run
audit. **Stage 2 pairable surface: 109 modernized HAW × 109 English =
327 trilingual sections (with the 109 original-HAW retained for dedup
hashing); 4 textual-notes (.9) supplementary.** Note: prior history
note said "348" — actual is 346 (history note off by 2).

**wehewehe-stage2/20260501** — manifest.jsonl 41 entries. 40/41 have
local_path+sha256; the 1 without is the `textchd` "Combined Hawaiian
Dictionary 2020" aggregator row, correctly marked
`mode="inventory_only"` with no body fetched. 0 failures. 9 ToS pages
present incl. ulukau disclaimer/privacy + hdict about/help. **Stage 2
candidate surface: 6 PD-pre-1925 dictionary PDFs (Andrews 1836, Emerson
1845, Andrews 1865, Biblical Words 1872, Hitchcock 1887, Parker 1922)
+ 6 landing pages.** 8 inventory-only rows (modern dictionaries —
INVENTORY ONLY, not extractable). 12 sample-query smoke probes —
discovery aid only, not pair candidates. Note: prior history note
said "40" — actual is 41 (the `textchd` aggregator row is included).

**hawaiian-kingdom-statutes-paired-imprints/20260501** —
manifest_complete.jsonl 53 entries. 53/53 local_path present on disk;
sha256 verified on sample (incl. PDFs). 0 failures. IA ToS snapshot
captured. **Stage 2 candidate surface: 4 paired imprints (1846/1859/
1869/1897) = 8 IA items, 8 PDFs (5 IA-Text-PDF + 3 Google-Books
"Image Container PDF"), 8 OCR `_djvu.txt`, 8 OCR `_djvu.xml`, 6
`_hocr_searchtext.txt.gz`, 8 `_meta.xml`, 6 `_marc.xml`, 8 IA-metadata
JSONs.** Pre-existing `fetch.jsonl` from `scripts/208_fetch_hk_statutes_djvu.py`
remains untouched alongside `manifest_complete.jsonl` (intentional —
legacy artifact, not part of complete manifest).

### CLEANUP_NOTES.json written

Non-destructive provenance audit dropped at:
- `data/raw/hooilina-stage2/20260501/CLEANUP_NOTES.json`
- `data/raw/wehewehe-stage2/20260501/CLEANUP_NOTES.json`
- `data/raw/hawaiian-kingdom-statutes-paired-imprints/20260501/CLEANUP_NOTES.json`

Each notes manifest size, local_path coverage, ToS presence, failure
count, orphan disposition, and the full / inventory-only / smoke split
so Linus's structured-count pass has a single canonical reference.

### Learnings — Stage-2 raw-provenance contract (durable)

1. Every file under a Stage-2 raw root should be either (a) referenced
   by a `local_path` in that root's manifest, or (b) explicitly logged
   under a `kind` that says it isn't a corpus byte (e.g.,
   `discovery_aux`). The hooilina classifier walk dump is the case in
   point — useful, harmless, but currently un-manifested.
2. Inventory-only rows must omit `local_path` and `sha256` (no
   placeholder zeros) and carry `mode="inventory_only"` plus a
   `rights_note`. Confirmed pattern in wehewehe `textchd` row.
3. Manifest counts in summary docs are the authoritative source of
   truth — agent prose summaries drift (off-by-2 here on hooilina,
   off-by-1 on wehewehe). Linus should count from the JSONL, not from
   prose.
4. For sources with paired imprints, keep `paired_imprints` in
   `manifest_summary.json` so Linus can join pairs without re-deriving
   from filenames. Confirmed clean on HK statutes.

### Anti-actions

- Did not delete any raw bytes.
- Did not re-fetch any source.
- Did not touch cookies, tokens, or session state.
- Did not modify the manifests themselves (CLEANUP_NOTES.json is a
  sidecar, not an edit).
- Did not encroach on Linus's count/structuring scope.

### Decision proposal

`.squad/decisions/inbox/frank-stage2-raw-provenance-check.md` — proposes
the durable manifest-coverage rule above so future raw-pull adapters
register every byte, including discovery aux dumps.

## 2026-05-03 — Wehewehe PD PDF Extraction Feasibility Assessment

**Task:** Process already-local Wehewehe PD raw pull (6 PD-pre-1925 dictionary PDFs)
into Stage 2 candidate rows.

**Result: 0 candidate rows emitted.** Blocker: all 6 PDFs are scanned image-only.

### Findings

1. **PDFs are image-only (scanned).** PyMuPDF (fitz) returns 0 text characters from
   every page of every PDF tested (EBOOK-VOCABULARY 139 pages: 0 chars; EBOOK-ANDREW
   559 pages: 0 chars fully confirmed). PDF creator metadata: `pdftk 1.41` /
   `itext-paulo-155`, creation date 2009 — these are digitized-scan wrappers, no
   text layer.

2. **No OCR tooling available.** pdftotext, tesseract, and pytesseract are all absent.
   PIL is installed but cannot do OCR without tesseract. Do not install tesseract as a
   system dependency for this task — the IA djvu.txt path is faster and already proven.

3. **No text sidecars.** entries/, classifier/, meta/ dirs are empty. Sample entry HTML
   pages contain search results (headword lists only, no definition text). TOC landing
   pages have no embedded entry content.

4. **Andrews 1865 already covered.** `data/stage2/candidates/andrews_1865_vocab.jsonl`
   has 1,194 rows built from IA djvu.txt (item cu31924026916167, script
   `324_build_andrews_vocab_candidates.py`). Local PDF extraction for this dict would
   duplicate — skipped.

5. **Dict cap status.** ≤5,000 rows total cap; Andrews 1865 consumes 1,194; 3,806
   rows of budget remain for the other 5 PD dicts.

### Forward Path

The Internet Archive hosts `_djvu.txt` OCR for these same historical titles (same
pattern used for Andrews 1865). Remaining 5 dicts need a targeted IA item-ID discovery
pass, then a 324-style builder script per dict.

**Priority:**
- Hitchcock 1887 (EN→HAW direction — highest structural value)
- Andrews 1836 (shorter vocab list)
- Parker 1922 (HAW-EN revised)
- Emerson 1845 (HAW-EN short)
- Dict. of Biblical Words 1872 (specialized register, lower priority)

### Files Written

- `data/raw/wehewehe-stage2/20260501/EXTRACTION_REPORT.json` — per-PDF probe results,
  tooling status, forward path (sidecar; raw originals untouched)
- `.squad/decisions/inbox/frank-wehewehe-pd-processing.md` — durable proposal

### Learnings (durable)

1. **Ulukau/puke.ulukau.org PDFs are image-only scans (2009 digitization).** Do not
   attempt fitz/pdftotext text extraction on them — the tool will return 0 bytes and
   silently succeed. Always probe 5+ pages before concluding a PDF has a text layer.

2. **IA djvu.txt is the correct path for these PD Hawaiian dictionaries.** Archive.org
   holds djvu OCR for the same titles; the `internetarchive` lib (already in
   requirements.txt) can fetch them without a separate download step. Pattern proven
   by `324_build_andrews_vocab_candidates.py`.

3. **Empty candidate file = don't create it.** When 0 rows are emittable, do not
   create the candidates JSONL file. An empty file would confuse the manifest builder
   (counts 0 rows but still injects source metadata). Create the file only when rows
   are actually ready to emit.

4. **Dict cap accounting.** The ≤5k combined wehewehe PD dict cap includes all
   pre-1925 imprints. Track budget explicitly: Andrews 1865 = 1,194 rows consumed,
   3,806 remaining. Flag this in any new adapter for these dicts.

## 2026-05-01T22:33:20Z — More Ulukau SFT Data Discovery (Round 4)

**Trigger:** User: "ok go find more sft training data in ulukau."

### What I did

Systematic survey of all Ulukau-family collections (20+ collections on ulukau.org,
puke.ulukau.org, and related sites) plus targeted IA pre-1925 bilingual Hawaiian↔English
text searches. No raw bytes pulled. Discovery manifest written to
`data/raw/ulukau-stage2-discovery/20260501/manifest.json`.

### What I found

**6 new candidates not previously in the fetch plan:**

1. **Hawaiian Phrase Book (1881)** `hawaiianphrasebo00bishrich` — 181 KB djvu.txt.
   Explicit EN/HAW two-column format. ~800-2k phrase pairs. PD-clear. No rights gate.
   **Rank 1 — ready for adapter immediately.**

2. **HK Constitution+Laws 1852 pair** — `hekumukanawaiam00hawagoog` (HAW, 222KB) +
   `constitutionand00hawagoog` (EN, 238KB). Same year (1852) = no year-mismatch risk.
   Extends existing HK statutes adapter. ~200-600 section pairs. PD (sovereign-edicts).

3. **HK Statute Laws 1847/1845-47 pair** — `kanawaiikauiaek00ricogoog` (HAW 1847) +
   `statutelawshism00ricogoog` (EN 1845-47, 1.5 MB). Year-range verification required
   first (like existing 1850/1869 year-mismatch). ~100-400 pairs. Inventory-only until
   Linus reviews.

4. **Gospel of John Parallel Columns (1854)** `gospelaccordingt00hawarich` — 274 KB.
   Explicit parallel columns, verse-id aligned, ~880 verses. BUT overlaps with Baibala
   plan. Recommend: use as supplementary English anchor, not additive HAW source.

5. **Sanitary Instructions for Hawaiians (1881)** `63140380R.nlm.nih.gov` — 274 KB.
   EN+HAW in two separate half-volumes. Health/medical register. Comparable-aligned.
   Requires LaBSE. ~200-800 paragraph pairs.

6. **Diglot New Testament (1859)** `HAWPDF_DBS_HS` — 2.4 MB djvu.txt, full NT. BUT OCR
   is severely garbled from two-column layout. hOCR column extraction needed. Deferred.

### What was blocked (confirmed this session)

Every other Ulukau collection is either copyrighted (Hawaiian Place Names © 2002-2019,
Kauakūkalahale © 2002-2004, Curriculum Materials © by owners, Māhele Database ©
2000-2005, AHCC History © 2013, EBOOK-DHLLT © 1995+2022) or monolingual Hawaiian
(Wehi ʻŌlelo). Graduate Papers (38 theses) likely © individual authors/UH.

### Yield outlook (incremental)

Realistic new confirmed pairs: 1,000-3,000 across Ranks 1-3. If Sanitary Instructions
and Gospel of John are also cleared: potentially 2,000-5,000 total.

### Artifacts

- `data/raw/ulukau-stage2-discovery/20260501/manifest.json` (6 ranked candidates +
  blocked list + collections surveyed)
- `data/raw/ulukau-stage2-discovery/20260501/README.md` (updated with findings table)
- `.squad/decisions/inbox/frank-more-ulukau-sft-data.md` (proposal for Linus + team)

## Learnings

- **Hawaiian Phrase Book (1881, IA `hawaiianphrasebo00bishrich`):** Confirmed PD, 181 KB
  djvu.txt, 4th edition. Two-column EN/HAW layout with explicit "ENGLISH | HAWAIIAN"
  headers. Parse on column-gap between EN and HAW halves. Filter entries < 3 chars on
  HAW side. Covers ~20 topic domains. dictionary-example Tier C.

- **IA `hehoakakaolelono00emer` (1845 Emerson) = same as `EBOOK-emd` on Wehewehe.** IA
  djvu.txt is already covered by the Wehewehe PD subset plan. Don't count twice.

- **1852 Hawaiian Constitution and Laws** has confirmed IA pair with no year-mismatch.
  HAW scan has some "W→AV" OCR substitutions (Google scan). Cornell-quality scans
  preferred for pairing — check if Cornell scan exists before defaulting to Google.

- **Sanitary Instructions (1881, IA `63140380R.nlm.nih.gov`):** Two-part structure —
  NOT interleaved parallel text. EN version first, HAW version second. Volume boundary
  detection is step 1 of adapter. Chapter-title alignment is deterministic key; paragraph
  alignment within chapters requires LaBSE.

- **Diglot (two-column) OCR is unreliable from djvu.txt.** Both `HAWPDF_DBS_HS` (1859)
  and `gospelaccordingt00hawarich` (1854 parallel columns) show that parallel-column
  scans interleave columns in OCR output. For parallel-column sources, prefer hOCR
  bounding-box extraction or use explicit verse anchors (like Greenstone) rather than
  OCR text.

- **Kauakūkalahale** (Honolulu Star-Bulletin modern Hawaiian column, 2002-present) is
  copyright-blocked. It is NOT a PD source despite being on Ulukau.

- **Most modern Ulukau collections are copyrighted databases** — rights do not pass even
  if underlying government records are PD. The PD "window" for Ulukau is basically:
  pre-1925 IA items, Ka Hoʻoilina KS editorial layer (provisional/prototype-only), and
  the Wehewehe PD dictionary subset.

## 2026-05-01T23:05Z — Ulukau-family SFT candidates: raw pull + dedup pass

**Trigger:** User: "pull all ulukau family sft candidates raw data, clean and dedupe with
existing data and tell me how many total structured rows we have."

### What was done

Full raw acquisition for all 6 Ulukau-family SFT candidates discovered in
`data/raw/ulukau-stage2-discovery/20260501/manifest.json`. Pull script:
`scripts/_frank_pull_ulukau_family_sft.py`. Output root:
`data/raw/ulukau-family-sft-candidates/20260501/`.

### Per-source disposition

| source_id | item_id | status | assets | bytes |
|---|---|---|---|---|
| ia-hawaiian-phrase-book-1881 | hawaiianphrasebo00bishrich | full | djvu.txt 181KB + PDF 8MB + meta.xml + marc.xml + ia_metadata.json | 8.2 MB |
| ia-hk-constitution-1852-en | constitutionand00hawagoog | full | djvu.txt 238KB + meta.xml + ia_metadata.json (PDF HTTP 500 on IA; no marc.xml on Google scan) | 246 KB |
| ia-gospel-john-parallel-columns-1854 | gospelaccordingt00hawarich | raw | djvu.txt 274KB + PDF 12.9MB + meta.xml + marc.xml + ia_metadata.json | 13.2 MB |
| ia-sanitary-instructions-1881 | 63140380R.nlm.nih.gov | raw | djvu.txt 274KB + PDF 7.7MB + meta.xml + ia_metadata.json | 8.0 MB |
| ia-diglot-nt-1859 | HAWPDF_DBS_HS | inventory_only | ia_metadata.json only | 7 KB |
| ia-hk-constitution-1852-haw | hekumukanawaiam00hawagoog | reused | 5 files from HK statutes dir | 6.4 MB |
| ia-hk-statute-laws-1847-haw | kanawaiikauiaek00ricogoog | reused | 5 files from HK statutes dir | 16.7 MB |
| ia-hk-statute-laws-1847-en | statutelawshism00ricogoog | reused | 7 files from HK statutes dir | 55.4 MB |

**Total new bytes downloaded:** ~29.7 MB
**Total reused bytes registered:** ~78.5 MB (no large-file duplication)

### Dedup check

SHA256 cross-check of all 4 new djvu.txt files against all existing raw
roots (HK statutes paired imprints, hooilina-stage2, wehewehe-stage2):
**zero collisions**. All 4 new djvu.txt files are genuinely new content.

### Structured candidate row counts (data/stage2/candidates/)

| File | Rows |
|---|---|
| andrews_1865_vocab.jsonl | 1,194 |
| bible.jsonl | 5 (smoke only) |
| bible_haw1868_kjv.jsonl | 31,101 |
| hk_statutes_1897.jsonl | 1,103 |
| hooilina.jsonl | 109 |
| kaikki_wiktionary.jsonl | 292 |
| tatoeba.jsonl | 121 |
| **TOTAL** | **33,925 structured rows** |

### Noteworthy findings / blockers per source

- **Phrase Book (1881):** Ready for adapter (325_build_phrase_book_candidates.py). No
  blockers. Column-detection on djvu.txt is the approach. Estimated 800–2,000 pairs.
- **1852 Constitution EN + HAW:** HAW already in HK statutes dir. EN pulled fresh.
  Section-id alignment extends existing HK statutes adapter. Google scan has no marc.xml
  and PDF returned HTTP 500 from IA — djvu.txt is sufficient for text extraction.
  Linus: confirm 1852 pair is within ≤15% combined legal register cap.
- **Gospel of John (1854):** djvu.txt + PDF pulled. Parallel-column OCR may interleave
  EN+HAW lines — check OCR quality before building verse-id adapter. Bible cap risk
  (≤30% train tokens). Dedupe against Baibala 1839 required.
- **Sanitary Instructions (1881):** djvu.txt + PDF pulled. Two-part structure (EN first,
  HAW second, NOT interleaved). Deterministic chapter-title alignment; paragraph-level
  alignment needs LaBSE (Rusty gate). Unique health/medical register.
- **Diglot NT (1859):** Inventory only. 2.4 MB djvu.txt available on IA but OCR
  garbled from two-column layout; hOCR/djvu.xml column extraction needed. Defer.
- **1847 HAW/EN Statute Laws:** Reused from HK statutes dir. Year-range verification
  still required (does EN 1846 cover exactly same laws as HAW 1847?). Inventory-only
  until Linus reviews.

### Artifacts

- `data/raw/ulukau-family-sft-candidates/20260501/manifest.jsonl` (8 rows)
- `data/raw/ulukau-family-sft-candidates/20260501/manifest_summary.json`
- `data/raw/ulukau-family-sft-candidates/20260501/CLEANUP_NOTES.json`
- `scripts/_frank_pull_ulukau_family_sft.py` (one-off fetch script, stdlib + requests only)

### Anti-actions

- Did not delete or overwrite any existing raw files.
- Did not copy large HK statutes files — registered by reuse pointer only.
- No cookies, auth headers, or session secrets read or recorded.
- No commits made (working tree only).

Decision proposal: `.squad/decisions/inbox/frank-pull-ulukau-family-raw.md`

---

## Session: Ulukau-family Batch (2026-05-01T23:13:13Z)

**Orchestration log:** `.squad/orchestration-log/2026-05-01T23-13-13Z-frank.md`

### Team handoff state (from Linus + Basher)

- **Linus cleaned Hoʻoilina:** 109 → 68 rows (boilerplate removal, HTML entity unescape, ʻokina canonicalization). 0 train-ready rows until human alignment review. Calls for HTML parser convention: must extract `<table width=_pagewidth_>...<td>` content block + `html.unescape()` before NFC/hash.
- **Linus deduped baseline:** 33,851 total structured rows (11,828 existing manifest + 20,852 Bible 1868 unique + 68 Hoʻoilina + 1,103 HK Statutes); 25,532 candidate-level train rows available after review-pending gates lift.
- **Basher validated Hoʻoilina + HK Statutes:** Hoʻoilina FAIL (re-emit required with `html.unescape()` + boilerplate filter); HK Statutes PASS (merge-ready as review-pending, 970 rows have §→$ OCR artifact, 892 have hyphen-break artifacts — both fixable during manifest build).

### Awaiting from Linus

1. Year-range verification (1847 HAW / 1846 EN statutes pair)
2. 1852 Constitution legal register cap confirmation
3. Gospel-of-John Bible cap accounting
4. Wehewehe PD dictionary line confirmation (for rights policy)

### Next actions

1. Implement `325_build_phrase_book_candidates.py` — high-priority, no blockers, estimated 800–2k rows
2. Re-emit Hoʻoilina adapter with `html.unescape()` + boilerplate filter
3. Probe Gospel of John djvu.txt OCR column quality (10-verse sample)

## 2026-05-02T00:56:01Z — Re-promotion Budget Available for NLLB/BT Planning

**Milestone:** Stage 2 final review verdicts completed by Danny + Basher.

**What you need to know:**
- Final re-promotion budget (sum of `excluded-policy-cap` rows across all sources) = **32,756 rows**.
  - Bible 1839 cap-overflow: 10,185 rows (passes quality; dropped by 30% cap).
  - Bible 1868 cap-overflow: 20,827 rows (all pass quality; dropped by 30% cap).
  - HK 1897 cap-overflow: 742 rows (passed hk1897-legal-clean-v1; dropped by 15% cap).
  - Others: ~2 rows (likely rounding).
- **Source:** `data/stage2/reports/stage2_finalized_review_verdicts_20260501.json` (full verdict distribution).
- **Constraint:** This 32,756 is the honest ceiling. Any NLLB-mined or synthetic-BT pairs that re-trigger the Bible/HK cap must come from this pool only. Do not exceed it.
- **Action:** Integrate this budget into your NLLB yield + synthetic-BT yield plans. Recommend next spawn = Frank (refine NLLB discovery bounds + synthetic-BT generation cap).

## 2026-05-02 — Hoʻoilina Sentence Pipeline v2 (Frank revision, under Linus lockout)

**Trigger:** Linus's `325_build_hooilina_sentence_candidates.py` rejected for emitting paragraph-level rows labeled `parallel-sentence`. Frank owns this revision cycle.

### What changed

**`scripts/325_build_hooilina_sentence_candidates.py` (v2):**
- Added `split_sentences()` function: stdlib-only, conservative boundary detection using `SENT_SPLIT_RE = re.compile(r'(?<=[.!?])\s+(?=[A-ZĀĒĪŌŪ\u02bb])')` — splits only when sentence-ending punctuation is followed by whitespace and an uppercase letter (covers both EN and HAW, including ʻOkina-prefixed starts like `ʻO`).
- Added `ABBREV_SET` for common EN abbreviations (Mr., Dr., No., etc.) to prevent over-splitting.
- Decimal numbers are protected by the uppercase lookahead (e.g. "3.14 kg" does not split).
- Whitespace/newlines normalised to a single space before splitting, so `\n`-separated sentences are handled correctly.
- Paragraph pairs are now **skipped** (conservative) when EN sentence count ≠ HAW sentence count.
- Added `MAX_TOKENS_PER_SIDE = 80` quality gate.
- New metadata fields per row: `paragraph_index`, `sentence_index`, `sentence_count_in_paragraph`.
- Updated `alignment_method` to `"filename-pair+paragraph-order+sentence-split-v2"`.
- Updated `pair_id` format: `hooilina-sent-v2-{suffix}.p{NNN}.s{NNN}`.
- All hashes recomputed per sentence (not paragraph).

**`scripts/333_build_reviewed_manifest_final_capped.py`:**
- Hoʻoilina gate now requires `alignment_type == "parallel-sentence"` (hard filter: paragraph rows cannot pass).
- Added `en_t <= 80 and haw_t <= 80` to promotion gate.
- Updated promotion rule id to `hooilina-sentence-v2`.

**`scripts/334_finalize_stage2_review_verdicts.py`:**
- Updated train reason string for hooilina source to reference v2 gate.

### Results

- Parent rows: 68; splittable at paragraph level: 6 (62 have no numbered-paragraph structure).
- Paragraph pairs: 36 total; sentence-count mismatches: 8 skipped; quality rejections: 1 (too_short).
- **Sentence pairs emitted: 60** (was 35 paragraph-level rows in v1).
- EN tok range: 3–59 (max well under 80); HAW tok range: 5–64. Zero rows over 80 tokens.
- All 8 verification checks pass: no multi-sentence rows, no side >80 tok, no dev rows, Bible 29.66%, HK 14.90%, SFT = 2× train.
- Final capped manifest: 369 train, 15 dev, 33527 review-pending. SFT rows: 738.

### Key files

- `scripts/325_build_hooilina_sentence_candidates.py` — v2 sentence builder (Frank)
- `scripts/333_build_reviewed_manifest_final_capped.py` — tightened Hoʻoilina gate
- `scripts/334_finalize_stage2_review_verdicts.py` — updated hooilina train reason
- `data/stage2/candidates/hooilina_sentences.jsonl` — 60 actual sentence pairs
- `data/stage2/reports/hooilina_sentence_build_report_20260501.json` — v2 build stats
- `data/stage2/reviewed_stage2_manifest_final_capped.jsonl` — regenerated (60 hooilina train)
- `data/stage2/reports/stage2_review_pass_final_capped_20260501.json` — regenerated
- `data/stage2/reviewed_stage2_manifest_finalized_reviews.jsonl` — regenerated
- `data/stage2/reports/stage2_finalized_review_verdicts_20260501.json` — regenerated
- `data/stage2/stage2_sft_final_capped.jsonl` — 738 rows (369 pairs × 2 directions)

### Sentence-split policy (for future agents)

- Use `(?<=[.!?])\s+(?=[A-ZĀĒĪŌŪ\u02bb])` as the sentence boundary pattern for HAW/EN mixed text.
- Protect abbreviations by checking if the last word before the split is in `ABBREV_SET`.
- Normalise whitespace (including `\n`) to a single space before sentence splitting.
- Conservative: skip paragraph pairs where EN sentence count ≠ HAW sentence count.
- Cap per sentence: min 3 tokens/side, max 80 tokens/side, ratio 0.5–2.5.
- All Hoʻoilina sentence rows must have `alignment_type="parallel-sentence"` to be eligible for promotion in script 333.
