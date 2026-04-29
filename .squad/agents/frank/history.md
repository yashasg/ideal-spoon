# Frank — History

## Core Context

- **Project:** A prototype/learning project for adapting an existing multilingual LLM to Hawaiian, including data, model choices, infrastructure, evaluation, and costs.
- **Role:** Hawaiian Data Collector
- **Requested by:** yashasg
- **Joined:** 2026-04-29T05:38:40Z
- **Tech stack:** Python raw-data tooling installed through `scripts/setup.sh` / `requirements.txt`; current stack includes `requests`, `tenacity`, `warcio`, `trafilatura`, `selectolax`, `scrapy`, `scrapy-warc`, `internetarchive`, `wayback`, `cdx_toolkit`, `yt-dlp`, and `datasketch`.

## Learnings

### 2026-04-29 — Initial assignment

- Own Hawaiian source discovery and raw collection adapters, especially for public-domain, rights-cleared, or explicitly permitted sources.
- Use the repository setup script as the default data-collection environment; Playwright is intentionally omitted unless a target source proves JavaScript rendering is required.
- Preserve provenance at fetch time: source URL, fetch date, raw hash, ToS/license evidence, source-specific IDs, and WARC/raw archive artifacts.
- Coordinate with Linus on data-policy/manifest expectations and with Rusty when source material may affect Hawaiian language/modeling quality.

### 2026-04-29 — Hawaiian source URL inventory (docs/hawaiian-data-sources.json)

- Built a tool-bucketed source inventory at `docs/hawaiian-data-sources.json`. Buckets mirror the installed deps in `requirements.txt`: `requests_tenacity`, `internetarchive`, `wayback_cdx_toolkit`, `scrapy_scrapy_warc`, `trafilatura_selectolax`, `yt_dlp`.
- Routing rules I'm locking in for this project:
  - Wikimedia dumps + FLORES + Tatoeba + OPUS + Bible verse files → `requests_tenacity` (single-file polite GETs).
  - archive.org item-level pulls (Ulukau-mirrored items, archival Bible scans, Hawaiian books) → `internetarchive` client.
  - Live-site crawls of Ulukau, Wikisource, Awaiaulu, OHA, DOE Kaiapuni, UH ScholarSpace → `scrapy + scrapy-warc` so we keep WARC + ToS snapshot per crawl.
  - Historical/snapshot recovery for Ulukau/nupepa.org/OHA/DOE → `wayback + cdx_toolkit`.
  - `trafilatura`/`selectolax` are post-fetch extractors, not fetchers — modeled as a postprocess bucket.
  - `yt-dlp` bucket stays empty by default; only populated after per-channel rights confirmation, captions-only.
- Rights posture defaults: never assert public domain without source evidence. Used `rights_status_hint` values (`public_domain_candidate`, `open_license_candidate`, `rights_review_required`, `eval_only`, `unknown_review_required`) consistently. JW300 and hard-escalate categories (mele/oli/pule/moʻolelo/moʻokūʻauhau) are recorded under `deferred_or_excluded` so future agents don't accidentally re-add them.
- Project-relevant URLs/templates I confirmed are worth pinning:
  - `https://dumps.wikimedia.org/hawwiki/latest/` (dump + dumpstatus.json for SHA1 pinning).
  - `https://baibala.org/cgi-bin/bible?e={edition}&b={book}&c={chapter}` for verse-keyed Hawaiian Bible (pin one edition).
  - `https://ebible.org/Scriptures/eng-kjv2006_usfm.zip` / `eng-asv_usfm.zip` for the public-domain English verse anchor.
  - `https://downloads.tatoeba.org/exports/per_language/haw/` (haw_sentences.tsv.bz2, haw-eng_links.tsv.bz2).
  - `https://opus.nlpl.eu/{corpus}/{version}/moses/{src}-{tgt}.txt.zip` template for OPUS subsets.
  - Wayback CDX API: `https://web.archive.org/cdx/search/cdx?url={domain}/*&output=json` for historical enumeration.
- FLORES is tagged `eval_only` and P0 because data-pipeline.md §Stage 2 requires hashing it into `eval_hashes.parquet` before any other ingest.
- Pre-1925 nūpepa stays `prototype_only=true` per ADR; bulk publication out of scope.
- Key file paths to remember: `docs/data-pipeline.md` (canonical source spec), `docs/hawaiian-data-sources.json` (URL routing config), `requirements.txt` / `scripts/setup.sh` (the only sanctioned tool surface).
- **2026-04-29 path move:** Per Coordinator directive (yashasg), `docs/` is reserved for Markdown only. Moved the URL inventory to `data-sources/hawaiian-data-sources.json` (canonical path going forward). Updated `docs/data-pipeline.md` Stage 1 row to match. JSON re-validated with `python3 -m json.tool`. Earlier history entries and dated `.squad/log/`, `.squad/orchestration-log/`, and prior `inbox/` decision files still cite `docs/hawaiian-data-sources.json` — left as-is because they are dated provenance, not live references.
- **New canonical layout:** `data-sources/` for rights-aware data-source inventories (JSON, CSV, manifests); `docs/` for Markdown specs/ADRs; tool surface remains `scripts/setup.sh` + `requirements.txt`.

### 2026-04-29 — First-pass token-yield estimate across the 26 sources (no fetches yet)

Estimate is from URLs + public knowledge of the corpora; no bytes pulled. Token counts assume a SentencePiece-ish ~1.3× word→token factor; bands are conservative / base / upside.

- **Raw Stage-1 Hawaiian tokens (pre-clean, pre-dedup, pre-rights-filter):** ~45M / ~75M / ~120M. ≥90% of this is the **nūpepa OCR corpus** reachable via three overlapping routes (Ulukau crawl, archive.org/Ulukau-mirrored items, Wayback CDX of ulukau.org / nupepa.org). Treat the three as one corpus — heavy dedup expected.
- **Train-eligible Stage-1 Hawaiian tokens, publishable posture (no nūpepa bulk, per ADR `prototype_only=true` on pre-1925 nūpepa):** ~2.5M / ~4.5M / ~7M. Dominated by **hawwiki dump (~1.5–3M)** + **Wikisource (~0.5–1.5M)** + small contributions from ScholarSpace/OHA/Awaiaulu/Wiktionary that survive per-doc rights review. Bible capped at ≤10% in Stage 1 per data-pipeline.md §125.
- **Train-eligible Stage-1, prototype-only posture (nūpepa OCR included, never published):** ~30M / ~50M / ~80M after OCR cleaning + paragraph-level LID + MinHash dedup. This is the only path that produces a "real" pretraining-scale Hawaiian set.
- **Stage-2 parallel (haw side, train-eligible):** pipeline already states realistic clean yield is "<50k pairs, possibly <10k" (data-pipeline.md §250). At ~25 haw tokens/sentence that's ~250k / ~700k / ~1.25M tokens of *clean parallel*. With the Bible cap binding (≤30% of parallel-train tokens), total parallel-train haw side likely lands around **1–3M tokens**, Bible-dominant, with Tatoeba + OPUS-non-JW300 + any OHA/UH bilingual extracts contributing the long tail. NLLB-mined treated last-resort and excluded from base case.
- **Eval-only:** FLORES-200 hawn_Latn dev (997) + devtest (1012) ≈ ~50k haw tokens. Must be hashed into `eval_hashes.parquet` before any other ingest. Never train.

Sources that dominate raw volume vs. publishable yield:
- **Raw volume king:** Ulukau/nūpepa newspapers — and they're the *only* source that can move the order of magnitude. Also the source with the strictest publication block.
- **Publishable Stage-1 backbone:** hawwiki dump (largest open-licensed clean text), Wikisource (clean PD).
- **Stage-2 backbone:** Baibala Hemolele × KJV/ASV verse-aligned (cap-bound). Everything else combined is rounding noise on the Bible.
- **Small but high-value:** FLORES (eval anchor, non-negotiable), Tatoeba (clean human-curated parallel), Wiktionary (lexicon/diacritic audit), Awaiaulu (modern register, low volume).

Biggest uncertainty sources, in priority order:
1. **Nūpepa OCR yield rate** post-cleaning (could be 30% or 70% surviving) and the publishability ADR (drives whether the corpus counts toward training at all).
2. **Tokenizer choice** — Hawaiian's ʻokina/kahakō and short syllable structure make BPE token counts notably different from word counts; my 1.3× factor could be off ±30%.
3. **NLLB hawn coverage** — unknown until pulled; could add 0–2M parallel tokens.
4. **OHA/UH/DOE per-doc rights review pass rate** — bilingual PDFs are the only realistic non-Bible parallel source at scale.
5. **Cross-source dedup loss** between Bible editions, Wikipedia mirrors, and the three nūpepa routes.

Tightening plan (pilot, ~1–2 days, no bulk fetch):
- Pull hawwiki + hawwiktionary dumps; run exact SentencePiece token count after WikiExtractor pass.
- Pull Tatoeba haw export + FLORES dev/devtest; exact line + token counts (small, definitive).
- Pull one Hawaiian Bible edition + KJV + ASV USFM; verse-aligned exact counts.
- Inventory OPUS haw subsets via the per-corpus index (line counts only, no full unzip).
- `internetarchive` client: enumerate `language:haw mediatype:texts`; sample 50 random items; record OCR-confidence + word counts; extrapolate corpus-wide with CI bands.
- Wikisource: API `list=allpages&aplimit=500`; sample 20 pages for token density.
- Land all of the above in `data-sources/pilot_token_counts.parquet` (one row per source: `sample_size`, `observed_haw_tokens`, `extrapolated_total`, `ci_low`, `ci_high`, `rights_posture`, `prototype_only`).

This pilot replaces the current ±2× ranges with ±20% bands without committing to any rights-questionable bulk pull.

### 2026-04-29 — GitHub tracking and issue assignment

- **Issue #1 created:** "Frank: pull data from rights-light sources" (https://github.com/yashasg/ideal-spoon/issues/1).
- **Assignment method:** Label-based routing via `squad:frank` (team label assignment).
- **Milestone:** prototype.
- **Labels:** squad, squad:frank, data, prototype.
- **Project:** ideal-spoon (GitHub Project v2: https://github.com/users/yashasg/projects/5).
- **Scope:** Issue #1 integrates both rights-light source pulling and the approved ADR on local-first corpus storage (prototype_only data, no git blobs, storage encryption). All data-collection work for the prototype phase should reference this issue.
- **Coordination:** Team communications, PRs, and data manifests related to Hawaiian source collection should link to this issue or the project board for visibility.

### 2026-04-29 — Issue #1 first concrete step (rights-light collector starter)

- **Files touched (new):** `scripts/collect_rightslight.py`.
- **Files touched (edited):** `.gitignore` (added `/data/`, `*.warc`, `*.warc.gz` with rationale).
- **Local-only outputs (gitignored, never committed):**
  - `data/local/rightslight/fetch_plan.json` — selected vs deferred sources, with provenance fields and selection/deferral reasons.
  - `data/local/rightslight/fetch.jsonl` — per-artifact provenance ledger (one JSON object per fetched byte stream).
  - `data/local/rightslight/token_counts.json` — aggregate-only placeholder; no corpus text, just bands until a real dump pass runs.
  - `data/local/rightslight/hawwiki/{YYYYMMDD}/{sha256}.txt` — smoke-fetched Wikimedia infrastructure metadata only.
  - `data/local/rightslight/README.txt` — human-readable "this is gitignored" marker.
- **Rights-light MVP allow-list locked in (4 sources):** Hawaiian Wikipedia XML dump, Hawaiian Wikipedia dump-status manifest, Hawaiian Wiktionary dump, Hawaiian Wikisource. All `open_license_candidate` (CC BY-SA 4.0) per the inventory.
- **Deferred sources (25, recorded with machine-readable reasons):** Baibala (no specific pre-1925 edition reviewed yet), archive.org Baibala scans, Tatoeba (long-tail until per-source review), FLORES (eval-only path), and every `rights_review_required` / `unknown_review_required` source — nūpepa OCR (Ulukau, archive.org, Wayback CDX), OHA / DOE Kaiapuni / UH ScholarSpace, Awaiaulu, OPUS subsets, NLLB, yt-dlp captions, plus the inventory's `deferred_or_excluded` block (JW300, hard-escalate cultural categories, general web crawls).
- **Smoke fetch performed:** one rights-clear, ~3 KB Wikimedia infrastructure file (`hawwiki-latest-sha1sums.txt`), recorded with full provenance (source URL, fetch timestamp UTC, HTTP status, content type, content length, raw SHA-256, raw storage path, license observed, ToS URL, fetcher tool/version). No corpus text fetched.
- **Storage policy enforced:** `git status` after the run shows zero entries under `data/`; `git check-ignore` confirms `/data/` rule covers all generated outputs. No `gh` push, no HF push.
- **Validation:** `python3 -m py_compile scripts/collect_rightslight.py` clean; script runs end-to-end on stdlib only (no new requirements).
- **Open follow-ups for next pass (not done here):** add a polite `requests + tenacity` adapter over the same provenance schema for the actual dump pulls (hawwiki XML, hawwiktionary XML); decide on Baibala edition review with Linus before the verse-pair pull lands.

## 2026-04-29T06:43:21Z — Downstream Stage-1 pipeline locked (Linus handoff plan)

�� **Team update:** Linus completed the raw-to-training workflow plan. Frank's responsibility ends at "raw fetch"; downstream is Linus (registration/LID/extraction/norm/dedup/eval-hash), Rusty (tokenizer audit gate), Basher (CI guard + training).

**Frank's fetch deliverables:**
- Raw files (HTML/PDF/JSON per source).
- WARC archives per source (ToS snapshot + raw bytes).
- Metadata at fetch time: source URL, fetch date, HTTP status, sha256_raw.

**Key decision:** Start with Hawaiian Wikipedia (smallest, cleanest). Validate entire pipeline on 1 source before adding Wiktionary/Wikisource/Baibala/long tail. Pre-1925 nūpepa bulk (volume play, biggest unknown) deferred pending nūpepa-pilot token-count report and prototype-only ADR.

**Manifest-first discipline:** every fetch-time field captured at ingest (ToS snapshot, source URL, fetch date, sha256_raw) is unrecoverable later — register now.

**Orchestration log:** `.squad/orchestration-log/2026-04-29T06-43-21Z-linus-raw-to-training-plan.md`


### 2026-04-29 — Issue #1 raw fetch script (scripts/fetch_rightslight_raw.py)

- **New file:** `scripts/fetch_rightslight_raw.py` — concrete stdlib-only raw-data fetcher for the rights-light allow-list (hawwiki, hawwiktionary, hawwikisource). Companion to `scripts/collect_rightslight.py`; same allow-list, no new requirements.
- **Safety posture (CLI contract):**
  - `--source {hawwiki,hawwiktionary,hawwikisource,all}`, default `hawwiki` (smallest vertical slice).
  - `--limit N` caps enumerative metadata calls (Wikisource `aplimit`, default 50, max 500).
  - `--metadata-only` and `--smoke` (alias) restrict to checksum manifests / dumpstatus / API enumeration. No corpus bytes.
  - `--execute` is required to download corpus-bearing dump files (`*-pages-articles.xml.bz2`). Without it, corpus artefacts are listed and skipped.
  - `--dry-run` forces print-only behaviour (no GETs).
  - Anything outside the allow-list is unreachable through this script — Baibala/nūpepa/OHA/DOE/UH/Awaiaulu/OPUS/NLLB/FLORES/JW300 stay out.
- **Storage:** `data/raw/<source>/<YYYYMMDD>/<sha256>.<ext>`, gitignored under the existing `/data/` rule. No `.gitignore` change needed (verified with `git check-ignore`). Per-source ledger at `data/raw/<source>/fetch.jsonl`.
- **Provenance schema (stable for Linus, do not rename):** `source_id, source_url, fetch_timestamp_utc, http_status, content_type, content_length, raw_sha256, raw_storage_path, tos_or_license_url, license_observed, fetcher_user_agent, fetcher_tool_and_version, source_specific_ids{}, notes`. Implemented as `ProvenanceRecord` dataclass; appended one JSON object per line via `_append_provenance`.
- **Reliability:**
  - Polite retry/backoff (exponential + jitter, 4 attempts) on transient `URLError`/`TimeoutError` and on short reads (Content-Length vs body bytes).
  - Hard fail on non-2xx terminal status, repeated transient errors, or sha1 mismatch vs. the Wikimedia `*-sha1sums.txt` manifest entry (matched by suffix `-pages-articles.xml.bz2`).
  - Atomic-ish writes: `.part` temp file then rename, so a crash never leaves a corrupt `<sha>.<ext>`.
  - User-Agent identifies project + contact (`ideal-spoon/0.1.0 (frank rights-light raw fetcher; ...issue #1)`); also sent as `Api-User-Agent` for MediaWiki etiquette.
- **Wikimedia plumbing detail learned:** `dumpstatus.json` is **only** published under the dated path (`/<wiki>/<YYYYMMDD>/dumpstatus.json`), not under `/latest/`. Script discovers the date by parsing dated filenames in `<wiki>-latest-sha1sums.txt`, then fetches the dated `dumpstatus.json` automatically. Worth remembering for any future Wikimedia adapter.
- **Known upstream gap:** `hawwiktionary-latest-sha1sums.txt` returns 404 — Wikimedia is not publishing dump artefacts for the Hawaiian Wiktionary subdomain right now. Script fails loudly (exit 3) on that source, which is the correct posture; users can simply pass `--source hawwiki` or `--source hawwikisource` until Wikimedia starts publishing it. Re-check before bulk runs.
- **Validation performed (no commit, no push):**
  - `python3 -m py_compile scripts/fetch_rightslight_raw.py` clean.
  - `python3 scripts/fetch_rightslight_raw.py --source hawwiki --dry-run` — prints planned URLs, no fetches.
  - `python3 scripts/fetch_rightslight_raw.py --source all --smoke` — fetched hawwiki sha1sums (3,048 B) + dated dumpstatus.json (11,312 B) + hawwikisource allpages API (117 KB metadata JSON, 50 page titles); hawwiktionary failed loudly as expected. All three records appended to per-source `fetch.jsonl`.
  - `git status --short data/` empty; `git check-ignore -v data/raw/hawwiki/fetch.jsonl` confirms `/data/` rule covers it.
- **Files touched:** `scripts/fetch_rightslight_raw.py` (new). No edits to `.gitignore`, `requirements.txt`, `data-sources/hawaiian-data-sources.json`, or `scripts/collect_rightslight.py` were required.
- **Linus handoff contract:** consume `data/raw/<source>/fetch.jsonl` (one JSON object per line, schema above) plus `raw_storage_path` for downstream registration / LID / extraction. Schema is additive-only; new fields go at the end.

## 2026-04-29T06:56:07Z — Python Script Contracts: Validation & Merge

- **Scripts:** `scripts/collect_rightslight.py`, `scripts/fetch_rightslight_raw.py` validated via `python3 -m py_compile` — both compile clean.
- **CLI help:** Help text for all three Python scripts (Frank + Linus + Coordinator collect script) printed successfully.
- **Decisions merged:** `frank-fetch-raw-jsonl-schema.md` and `linus-stage1-jsonl-first.md` merged into `.squad/decisions.md`; inbox files deleted.
- **Coordinator directive:** Python-scripts directive persisted in decisions.
- **Frank's fetch contract locked:** ProvenanceRecord schema (14 fields + extension point) is additive-only; future Linus coordination point for any new fields.

## 2026-04-29T06:59:23Z — Numbered pipeline scripts orchestration

- Pipeline scripts renamed and numbered to encode execution order for clarity:
  1. `scripts/001_collect_rightslight.py` — Frank's rights-light source planning.
  2. `scripts/002_fetch_rightslight_raw.py` — Frank's raw artifact fetcher (replaces `fetch_rightslight_raw.py`).
  3. `scripts/003_build_stage1_dataset.py` — Linus's Stage-1 manifest builder.
- All docstrings, `generated_by` fields, `fetcher_tool_and_version` references, and decision notes updated to reflect numbered filenames.
- Validated: `python3 -m py_compile scripts/001_collect_rightslight.py scripts/002_fetch_rightslight_raw.py scripts/003_build_stage1_dataset.py` — all clean.
- Manifest-first discipline confirmed: every fetch-time field (ToS snapshot, source URL, fetch date, sha256_raw) is captured at ingest and unrecoverable later.
- Scribe logged coordination in `.squad/orchestration-log/` and `.squad/log/`. All `.squad/` changes committed.

## 2026-04-29 — Fetch plan now tiered against the 2.5M right-clearable token floor

User flagged that "the fetch plan didnt pull enough raw data in the first place." Reworked `scripts/001_collect_rightslight.py` so the plan no longer implies the MVP allow-list is sufficient for Stage-1.

- **Schema bumped to 0.2.0.** Plan now emits three tiers per source: `mvp_smoke` (covered by 002 today), `expansion_candidate` (right-clearable, needed to reach the 2.5M floor, blockers documented), `deferred` (rights-heavy/ambiguous, never used to backfill the gap).
- **Per-source fields added:** `token_estimate_haw{conservative,base,upside}`, `fetcher_status` ∈ {`supported`, `metadata_only`, `blocked_upstream`, `not_yet_implemented`}, `fetcher_script`, `blockers[]`.
- **Coverage roll-up** in `coverage_summary` exposes the gap explicitly:
  - target floor 2.5M; fetchable today (just hawwiki) ≈ 1.5M → **shortfall ~1.0M**.
  - mvp_smoke at face value ≈ 2.05M (Wiktionary 404s upstream; Wikisource only enumerates titles).
  - with expansion candidates ≈ 2.62M → barely clears the floor.
- **Expansion candidates promoted (right-clearable only):** Wikipedia interlanguage API (langlinks), Tatoeba haw exports (CC BY 2.0 FR), Hawaiian Wikisource bulk page text (action=parse or scrapy+WARC). Each carries blockers; none are auto-fetched.
- **No rights-heavy promotions.** Baibala without reviewed edition, nūpepa OCR, OHA/DOE/UH, Awaiaulu, OPUS/NLLB, JW300, hard-escalate cultural categories all stay deferred. FLORES stays eval-only.
- **`scripts/002_fetch_rightslight_raw.py`** docstring amended with a "Scope vs. the Stage-1 token target" paragraph pointing at the new `coverage_summary`. Fetcher behaviour, CLI, and provenance schema are unchanged.
- **Validation:** `python3 -m py_compile scripts/001_collect_rightslight.py scripts/002_fetch_rightslight_raw.py scripts/003_build_stage1_dataset.py` clean. `python3 scripts/001_collect_rightslight.py` (no smoke, no network) emits the new tiered plan and prints the shortfall against the floor. `git status --short data/` empty — outputs still gitignored.
- **Decision filed:** `.squad/decisions/inbox/frank-rightslight-token-target.md`. Coordination points: Linus on Wikisource extracted-text contract; Rusty on whether tokenizer fragmentation could push effective tokens below the floor even after expansion lands.
- **Honest go/no-go posture locked in:** if expansion adapters slip, delay Stage-1 DAPT; do **not** backfill with rights-ambiguous data. Captured in `coverage_summary.gap_vs_conservative_floor.note`.

## 2026-04-29 — Orchestrated Stage-1 token-gap correction (parallel with Linus)

Completed as part of paired agent session with Linus. Scribe consolidated outputs, merged decisions, filed orchestration log, and staged for git commit.

**Session outcome:**
- Tiered fetch plan in place (mvp_smoke / expansion_candidate / deferred).
- ~1.0M shortfall today (hawwiki only); expansion candidates needed to reach 2.5M floor.
- Coverage summary rolls up token estimates and blocker dependencies.
- `scripts/001_collect_rightslight.py` schema v0.2.0 locked.
- All three numbered scripts validated via `py_compile` and CLI `--help`.
- No corpus fetched. `.squad/orchestration-log/2026-04-29T07-19-07Z-frank.md` filed.
- Decision merged into `.squad/decisions.md` as Accepted.

**Open follow-ups:**
1. Land Tatoeba adapter (small, polite GET; minutes of work).
2. Land Wikisource bulk-text adapter (coordinate with Linus on extracted-text contract).
3. Land Wikipedia langlinks adapter (small but useful).
4. Pilot token counts post-fetch to replace ±2× bands with ±20% bands.

## 2026-04-30 — Wikisource adapter split out of 002 into 002b

User asked for a separate "002 script" for Hawaiian Wikisource so the dump-shaped fetcher and the API-shaped page fetcher don't share one allow-list. Split landed.

- **New script:** `scripts/002b_fetch_hawwikisource_raw.py`. Stdlib only. Dry-run by default. `--execute` required to pull per-page wikitext. Defaults: namespace 0 only, batch 50, total `--limit` 50, 1.0s rate limit between page fetches and between paginated allpages calls. Hard caps `MAX_TOTAL_PAGES=5000`, `MAX_BATCH=500`.
- **Namespace allow-list:** main (0) by default; `--namespaces` accepts only 0/104/106 (Page/Index). Talk/User/Special/maintenance namespaces are explicitly rejected at parse time.
- **Provenance:** writes to `data/raw/hawwikisource/<YYYYMMDD>/<sha256>.json`, appends to source-level `data/raw/hawwikisource/fetch.jsonl` with the same `ProvenanceRecord` schema as 002 (matters for Linus's source-level reader). Per-page records carry `page_id`, `revision_id`, `revision_timestamp`, `title`, `namespace` in `source_specific_ids`.
- **Page content path:** MediaWiki `action=query&prop=revisions&pageids=…&rvslots=main&rvprop=ids|timestamp|content|flags`. We store the raw JSON envelope as-is — extraction (NFC, ʻokina canonicalization) is downstream's job per Linus's contract.
- **002 trimmed:** `hawwikisource` removed from `ALLOWED_SOURCES`; `--source hawwikisource` now exits 2 with a message pointing at 002b. Docstring/usage examples updated. `--limit` flag kept (no current consumer) marked reserved.
- **001 repointed:** Wikisource MVP entry now `fetcher_status=supported` with `fetcher_script=scripts/002b_fetch_hawwikisource_raw.py --metadata-only`. Expansion-candidate entry for bulk page text also flips to `supported` with `--execute`. Both still carry the Linus extracted-text-contract blocker.
- **Validation:** `python3 -m py_compile scripts/00{1,2,2b,3}*.py` clean. `python3 scripts/002b_fetch_hawwikisource_raw.py --help` and `--dry-run --limit 5` print the planned URL only, write nothing. `python3 scripts/002_fetch_rightslight_raw.py --source all --dry-run` now lists `['hawwiki', 'hawwiktionary']` only. `python3 scripts/002_fetch_rightslight_raw.py --source hawwikisource` exits with the redirect message. `python3 scripts/001_collect_rightslight.py` emits the updated plan. No corpus pulled. `git status` clean for `data/`.
- **Decision filed:** `.squad/decisions/inbox/frank-wikisource-split.md`.
- **Coordination:** Linus still owns the Wikisource extracted-text contract; nothing about NFC/ʻokina policy changed here. Rusty unchanged.

## 2026-04-29 — 100-phase split into per-source collection scripts

User flagged that the broad rights-light collection plan was the wrong shape: each source has its own formatting (Wikimedia dump SHA1 manifest vs. MediaWiki API per-page enumeration vs. archive.org item IDs, …) and forcing them through one schema lost too much per-source detail. Refactored the 100 phase to source-specific `10X_collect_<source>.py` scripts.

- **Retired:** `scripts/101_collect_rightslight.py` (deleted).
- **New:**
  - `scripts/101_collect_hawwiki.py` — emits `data/local/hawwiki/collect_plan.json` (dump-shape metadata for 201).
  - `scripts/102_collect_hawwikisource.py` — emits `data/local/hawwikisource/collect_plan.json` always, and `page_plan.jsonl` (per-page fetch plan for 202) when `--enumerate` is passed. Default is metadata-safe with no network access; `--enumerate` walks the MediaWiki `list=allpages` API to populate the page plan; `--dry-run` keeps it print-only.
  - `scripts/103_collect_hawwiktionary.py` — emits `data/local/hawwiktionary/collect_plan.json`. Records the upstream `hawwiktionary-latest-sha1sums.txt` 404 as an explicit blocker so future agents re-check before any bulk run.
- **`202_fetch_hawwikisource_raw.py`** now accepts `--page-plan PATH` (default `data/local/hawwikisource/page_plan.jsonl`); reads `{ns, page_id, title}` rows produced by 102 and uses them as the page list. If the file is missing or empty, 202 falls back to direct enumeration as before. `--no-page-plan` forces the fallback. Docstring updated.
- **`201_fetch_rightslight_raw.py`** docstring/error message updated to point at `101_collect_hawwiki.py` and `103_collect_hawwiktionary.py` instead of the deleted broad planner. Behaviour, allow-list, and provenance schema unchanged.
- **`docs/data-pipeline.md`** — Source-fetcher → Stage-1 builder handoff section now describes the `10X_collect_<source>.py` convention and points each 100 → 200 → 300 step at its concrete script.
- **Page-plan row schema (the cross-script contract):** `{ns: int, page_id: int, title: str, source_url, api_url, rights_status_hint, license_observed, tos_or_license_url}`. 202 only requires the first three; the rest are advisory and propagate the source-level rights posture for downstream auditing.
- **No data-policy change.** Right-clearable allow-list unchanged; nūpepa/Baibala/etc. still deferred. Storage stays local-only under `data/local/<source>/` and `data/raw/<source>/`. `ProvenanceRecord` schema in 201/202 unchanged → no Linus-side breakage.
- **Validation:** `python3 -m py_compile` clean on all six active scripts (101/102/103/201/202/301). `--help` works for all new/changed scripts. Ran 101/102/103 with no flags → wrote `collect_plan.json` files (and an empty `page_plan.jsonl` placeholder for 102) under `data/local/<source>/`. Ran `202 --dry-run --limit 5` twice: once with empty page_plan (fell back to enumeration as expected), once with a 2-row synthetic page_plan (loaded both rows, printed the two `[dry-run] would GET page content: …` lines, no network corpus fetch). `git check-ignore -v` confirms `/data/` rule still covers everything written under `data/local/`.
- **Decision filed:** `.squad/decisions/inbox/frank-source-specific-100-phase.md`.
- **Open follow-ups:** new sources land as new `10X_collect_<source>.py` scripts (e.g. `104_collect_tatoeba_haw.py`, `105_collect_hawwiki_langlinks.py`) — same shape: emit a JSON plan to `data/local/<source>/collect_plan.json`, document fetcher_script, token estimates, blockers; the corresponding 2XX fetcher consumes it.

## 2026-04-29 17:58:36Z — Scribe consolidation: inbox decisions merged, active policy confirmed

Frank's 100-phase split work was reviewed, validated, and consolidated by Scribe. Inbox files merged into `.squad/decisions.md`. Active policy confirmed:

- **100-phase is now source-specific:** `10X_collect_<source>.py` scripts remain active standard for all future source/fetch/build work across the team.
- **202 consumes 102 page plans:** Wikisource page enumeration flows from `102_collect_hawwikisource.py` → `data/local/hawwikisource/page_plan.jsonl` → `202_fetch_hawwikisource_raw.py --page-plan`. Fallback to direct enumeration when plan is missing/empty or via `--no-page-plan`.
- **Broad planner archived:** Prior decision entries (001–003) concerning phase-100 broad planner superseded by unified source-specific convention documented above.
- **No corpus fetched, all validations passed, git status clean.**

Future work (source additions, fetch enhancements, build stage updates) should reference this consolidated policy.

## 2026-04-29 — New data source research (recovery from Wikimedia/Nupepa stall)

User asked Frank to research net-new Hawaiian source candidates beyond the four-source MVP allow-list and the blocked Nupepa CGI route. No code written; research only. All probes used a polite User-Agent; no Cloudflare/access-control bypass attempted.

### Confirmed-accessible candidates (probed live)

1. **HuggingFaceFW/fineweb-2 — `haw_Latn` config.**
   - Verified via `https://datasets-server.huggingface.co/rows?dataset=HuggingFaceFW%2Ffineweb-2&config=haw_Latn`: **95,507 rows** total, `partial=False`. Per-row schema preserves `text, id, dump, url, date, file_path, language, language_score, language_script, top_langs`. Licence on the dataset wrapper: **odc-by**. Underlying texts are CC-WET-derived (e.g., `staradvertiser.com` Kauakūkalahale columns appear with full URLs preserved → third-party rights live, dataset licence covers redistribution of the corpus form, not content reuse).
   - Adapter shape: `huggingface_hub` snapshot of `data/haw_Latn/*.parquet`, or HF datasets-server paginated rows API for stdlib-only path. Provenance is already in-row (url/dump/date) — Linus gets it for free.
   - Rough yield (back of envelope, sample lengths 0.5–11.6k chars): **~40–80M raw whitespace tokens**. First real path to clear the 2.5M Stage-1 floor without nūpepa.

2. **cis-lmu/Glot500 — `haw_Latn` config.**
   - **1,053,668 rows**, `partial=False`. Each row carries a `dataset` field exposing upstream source (sample showed `MC4`). Sample row 3 was Czech text mis-tagged as haw → Glot500 has known LID noise; per-row `language_score`-style filter not present, so any use **requires our own paragraph LID pass before counting tokens**. Treat as a "candidate pool" not a corpus.
   - Licence: composite, MC4-leaning (ODC-By ish); per-source flow-down. Rusty/Linus review needed.

3. **eBible.org `haw1868` — Baibala Hemolele 1868.**
   - Listed on eBible as **public-domain, redistributable**. Direct artefact URLs:
     - `https://eBible.org/Scriptures/haw1868_usfm.zip` (USFM canonical)
     - `https://eBible.org/Scriptures/haw1868_usfx.zip` (USFX)
     - `https://eBible.org/Scriptures/haw1868_readaloud.zip` (plain-text canon by chapter)
     - `https://eBible.org/Scriptures/haw1868_html.zip`
   - Single-zip artefact replaces the planned `baibala.org/cgi-bin/bible` per-verse scraper, which carries Cloudflare risk we don't need. Pair with `eng-kjv2006_usfm.zip` / `eng-asv_usfm.zip` (already pinned in inventory) for verse alignment.
   - Yield: standard Protestant canon ≈ 730k Hawaiian whitespace tokens (KJV is ~790k English; haw will be modestly lower per-verse).

4. **bible-nlp/biblenlp-corpus on HF.**
   - Confirmed `haw` is in the language list (verse-aligned across 833 langs). Useful as a Stage-2 parallel cross-check against eBible-derived alignment (deduplicate on verse refs). Direct `corpus.zip` returned 404 from the resolver — files live under `data/` in HF repo, not a single-zip; needs `huggingface_hub`/git-lfs-style fetch.

5. **Internet Archive `language:(haw) mediatype:(texts)`.**
   - Verified via advancedsearch.php: **216 items**; all-mediatype `language:(haw)` = **334 items**. Sample includes pre-1925 PD-candidate texts (`kekumumuaanohoui00pool` 1875, `peleandhiiakaam00emergoog` 1978 reprint of older work, Hawaiʻi Judiciary Fifth Circuit court records 1890–1892), plus modern children's books (clear copyright). Some items carry `licenseurl=publicdomain/mark/1.0/` already.
   - Adapter: `internetarchive` Python client (already in `requirements.txt`). Strategy: enumerate, filter for (`year < 1929` OR `licenseurl ∈ {PD, CC0}`), download `*_djvu.txt` only for those items, defer the rest behind Linus rights review.

6. **UH Mānoa eVols (ScholarSpace) — OAI-PMH endpoint.**
   - **Confirmed live OAI-PMH**: `https://evols.library.manoa.hawaii.edu/server/oai/request?verb=ListSets` returns a 334 KB DSpace 7 set list. Standard OAI-PMH `ListRecords&metadataPrefix=oai_dc` is enumerable without scraping. Awaiaulu specifically points at handle `10524/47856` (Ka Leo Hawaiʻi 1991-2000 audio + transcripts) as a known Hawaiian-language asset.
   - Rights are per-item; most UH theses are author-rights or CC; transcripts of native-speaker oral histories are culturally sensitive and likely fall in the **hard-escalate** category — keep audio out, request transcript-only with rights review.

### Probed-and-blocked (not pursuing further this round)

- **Chronicling America title-search API**: `chroniclingamerica.loc.gov` now returns a **308 → www.loc.gov/chroniclingamerica → 403** to our environment (Cloudflare). Public bulk batches at `https://chroniclingamerica.loc.gov/data/batches/` may still be reachable but enumeration of Hawaiian LCCNs from API is blocked from this env. Defer until we have an alternative network or LoC bulk mirror.
- **HathiTrust catalog/Babel**: Cloudflare interstitial on HTML and `babel.hathitrust.org/cgi/ls`. Defer.
- **Papakilo Database** (`papakilodatabase.com`): 403 from this env. Defer; may need OHA contact.
- **digitalcollections.hawaii.gov** (Hawaiʻi State Archives Greenstone): TCP failure on probe; intermittent. Re-probe later.
- **Mozilla Common Voice**: API returns `{"message":"no user"}` for `haw` locale → **Hawaiian is not a Common Voice supported locale**. Drop.
- **CC-100 (statmt.org)**: language manifest enumerated; **`haw` is not present** (`ht` Haitian only). Drop CC-100 specifically; FineWeb-2 supersedes it for our purposes anyway.

### Ulukau sub-collections beyond the broken Nupepa CGI

The Ulukau homepage lists collections on **different Greenstone instances** (`gsdl2.80`, `gsdl2.85`, plus standalone subdomains): Kauakūkalahale (modern Hawaiian newspaper column, `ulukau.org/apo/cgi-bin/kauakuka`), Ka Hoʻoilina journal of nūpepa reprints (`hooilina.org`), Ka ʻAhahui Kīwila Hawaiʻi documents (`gsdl2.85 c=ahcchist`), Ka Papa Haʻawina Hawaiʻi curriculum (`gsdl2.80 c=cbumbrella`), Ka Waihona Mele (`ulukau.org/mele/`). These are **distinct CGI surfaces** from the blocked `gsdl2.7/cgi-bin/nupepa` and have not been individually probed for Cloudflare posture. Worth a per-collection probe before assuming all Ulukau is dead.

### Source-evaluation pattern that worked

For each candidate, a 60-second probe answered the four go/no-go questions:
1. Is there a machine-readable enumeration endpoint (API / OAI-PMH / advanced search JSON / dataset-server rows)?
2. Does it return a real row count (not Cloudflare HTML, not 403)?
3. Does at least one row contain Hawaiian text (eyeball-confirmed, not just a `language=haw` tag)?
4. Is the licence on the *delivery wrapper* stated, even if per-document rights still need Linus review?
A "yes" on all four promotes to Tier A; "no" on (3) demotes to "candidate pool, needs LID first" (Glot500); "no" on (1) or (2) defers.

### Ranked shortlist + concrete next actions for the top 3

| Rank | Source | Adapter pair | Yield estimate | Blockers |
|------|--------|-------------|----------------|----------|
| 1 | FineWeb-2 `haw_Latn` | `104_collect_fineweb2_haw.py` + `204_fetch_fineweb2_haw_raw.py` | ~40–80M raw tokens | Linus rights review on the underlying CC URLs (not the ODC-By wrapper); add `huggingface_hub` to `requirements.txt` |
| 2 | eBible `haw1868` | `105_collect_ebible_haw.py` + `205_fetch_ebible_haw_raw.py` | ~700k tokens, PD | None significant; trivial adapter (3 single-zip GETs incl. KJV/ASV anchors) |
| 3 | Internet Archive PD `language:haw` slice | `106_collect_ia_haw_pd.py` + `206_fetch_ia_haw_pd_raw.py` | rough 1–5M tokens, depends on PD count after filter | Per-item rights filter (`year<1929` OR `licenseurl ∈ PD/CC0`); uses already-installed `internetarchive` client |

Tier-2 follow-ups (after top 3 land): Glot500 `haw_Latn` LID-filtered slice; UH eVols OAI-PMH for Hawaiian-language scholarly items; bible-nlp parallel-corpus alignment cross-check; per-collection Ulukau probe.

### Decisions filed

- `.squad/decisions/inbox/frank-new-data-sources.md` — team-relevant decision memo with the ranked shortlist and the three proposed `10X/20X` script numbers.

## 2026-04-29T09:13:49Z — Scribe logs and decision merge complete

Scribe filed orchestration log (`.squad/orchestration-log/2026-04-29T09-13-49Z-frank.md`) and session log (`.squad/log/2026-04-29T09-13-49Z-new-data-sources.md`). Inbox decision merged into `.squad/decisions.md`. All three new data source candidates (FineWeb-2, eBible, Internet Archive PD) now tracked as formal decisions awaiting Linus/Rusty coordination input.

Ready for adapter implementation once rights/LID policy green-light received.

## Learnings — 2026-04-29 FineWeb-2 `haw_Latn` live re-verification

Re-verified before any script work, per yashasg "1 sounds good, lets verify it works before we write scripts".

- **Dataset ID:** `HuggingFaceFW/fineweb-2`, config `haw_Latn`. Public, **not gated**, not private (`/api/datasets/...`: `gated:false, private:false, disabled:false`). License tag: `odc-by` (wrapper only — underlying CC URLs carry independent third-party rights; Linus call still pending).
- **Row counts (re-confirmed live, `partial:false`):** train **95,507** rows / 414,538,487 bytes in-memory / 127,502,750 bytes parquet; test **887** rows / 3,575,816 bytes in-memory. Earlier "95,507" claim ✅ holds exactly.
- **Schema (12 fields, all `Value`):** `text:str, id:str, dump:str, url:str, date:str, file_path:str, language:str, language_score:f64, language_script:str, minhash_cluster_size:i64, wordlist_ratio:f64, top_langs:str`. Provenance (CC dump id, original URL, crawl date, WARC s3 path) is in-row — fetcher gets receipts for free.
- **Access methods that work without auth:**
  1. `datasets-server.huggingface.co/rows?...&offset=N&length=K` — paginated rows API, stdlib-only. Confirmed returning real rows + `num_rows_total:95507`.
  2. Parquet auto-conversion endpoint: 2 files only — `train/0000.parquet` (127 MB) and `test/0000.parquet` (1.2 MB) at `https://huggingface.co/datasets/HuggingFaceFW/fineweb-2/resolve/refs%2Fconvert%2Fparquet/haw_Latn/{split}/0000.parquet`. Stable, deterministic, streamable with `pyarrow`/`requests`-range or `huggingface_hub.hf_hub_download`.
- **Tiny sample (2 rows, redacted lengths only):** row 0 `text` len=3215, row 1 len=3292. Both `language_score>0.995`, `language_script=Latn`. **But** both are Star-Advertiser "Kauakūkalahale" columns: text starts with English boilerplate ("POSTED: 01:30 a.m. HST, Oct 22, 2011 / Synopsis: ...") and ends with English bio line. So even at high LID score, documents contain English headers/footers — Stage-1 cleaning will need boilerplate strip, and Linus's per-URL allow-list discussion (`*.staradvertiser.com` posture) is sharper, not weaker.
- **Dependency reality check:** `requirements.txt` currently has **no `huggingface_hub`, no `datasets`, no `pyarrow`**. The rows-API path works on stdlib alone; parquet-bulk path needs at least `pyarrow` (or `huggingface_hub` for download + `pyarrow` to read). No script needs `datasets` proper. **Do not change `requirements.txt` yet** — that's tied to Linus's open question on hub-vs-stdlib path.
- **Risks (carry forward to scripts):**
  - Wrapper licence `odc-by` ≠ content licence on underlying CC URLs (e.g., staradvertiser.com). Per-URL allow-list still owed by Linus.
  - LID noise: 99% language_score documents still contain English boilerplate; Rusty/Linus pipeline must boilerplate-strip + re-LID at line/paragraph granularity.
  - Document boundaries: rows are CC-WET docs, already minhash-clustered (`minhash_cluster_size` provided). Our Stage-1 dedup needs to either trust their clusters or re-MinHash; ADR called for our own MinHash, so treat their field as provenance metadata, not a dedup decision.
  - HF rate limits: anonymous datasets-server is fine for metadata + tiny samples; for the 127 MB parquet bulk pull, polite single-file fetch is well within unauthenticated limits but still log UA + ETag.
  - No quality/toxicity filtering done by FineWeb-2 at this tier beyond LID + minhash — downstream cleaning is on us.
- **Verdict:** **Works.** Proceed to script planning. Proposed script names (per existing decision): `105_collect_fineweb2_haw.py` (planner: emit manifest of the 2 parquet URLs + per-row count + license snapshot) and `205_fetch_fineweb2_haw_raw.py` (fetcher: stream parquet to `data/raw/fineweb2/haw_Latn/{train,test}/0000.parquet` with sha256 + ETag + fetch-date + license-tag manifest).
- **Still blocked on (not by Frank):** Linus rights ruling on FineWeb-2 wrapper-vs-row posture for prototype use, and the `huggingface_hub`/`pyarrow` dependency call. Verification itself is unblocked.

### 2026-04-29 — `haw_*` variant survey across HF Hub (metadata-only)

Triggered by yashasg asking whether other `haw_*` dataset forms exist beyond FineWeb-2 `haw_Latn`. Probed HF Hub API only (sibling listings + `language:haw` filter). No bulk downloads; no raw text inspected.

Real Hawaiian text configs found (beyond FineWeb-2 `haw_Latn` train/test):

- `HuggingFaceFW/fineweb-2` **`haw_Latn_removed`** — filter-rejected pool from the same pipeline. New finding; recall-only contingency.
- `HuggingFaceFW/finepdfs` `haw_Latn` (train+test) — PDF-derived; likely overlaps Ulukau/archive.org. Run URL/SHA diff before pulling.
- `HuggingFaceFW/finetranslations` `haw_Latn` — synthetic/model-translated; synthetic-last-resort under our policy.
- `cis-lmu/GlotCC-V1` `haw-Latn` — independent CC filter; best second-source for cross-source dedup.
- `cis-lmu/Glot500` `haw_Latn` — older, smaller; comparator only.
- `cis-lmu/Taxi1500-RawData` `haw_Latn` — Bible-derived classification eval.
- `openbmb/DCAD-2000` `haw_Latn/{fineweb-2,mala}_*_{keep,remove,stas}.jsonl` — explicit second-filter `keep/remove` decisions over FineWeb-2 + MaLA shards.
- `wikimedia/wikipedia` `20231101.haw` — canonical Wikipedia parquet (already in our inventory).
- `graelo/wikipedia` `haw` (2023-06/09) — older Wikipedia snapshots; redundant.
- `allenai/c4` `multilingual/c4-haw*` — mC4 predecessor of FineWeb-2 lineage; skip.
- `bible-nlp/biblenlp-corpus` — `haw` present in language manifest (Bible verses).
- `ayymen/Weblate-Translations` `en-haw.tsv`, `en_GB-haw.tsv` — UI-string parallel; tag `register=software-l10n`.
- `mrlbenchmarks/global-piqa-parallel` `parallel_haw_latn.tsv` — eval-only commonsense parallel.
- `saillab/alpaca_hawaiian_taco`, `saillab/alpaca-hawaiian-cleaned` — LLM-translated alpaca; excluded under synthetic-quality rule.

Out-of-scope but tracked: `facebook/omnilingual-asr-corpus` `haw_Latn`, `espnet/mms_ulab_v2` (speech).

False positives: `und_Shaw` / `und-Shaw` (Shavian script for English; appears in FineWeb-2, GlotCC, DCAD-2000, Weblate). Not Hawaiian.

Confirmed **absent**: OSCAR (2301/2201/2109/colossal), CulturaX, CC100, HPLT 2.0, NLLB mined, OPUS-100, MADLAD-400 (only contamination canaries — no `data/haw/` config), and — important — **FLORES / FLORES+ / FLORES-200 have no Hawaiian.** This invalidates the "If `hawn_Latn` is included in FLORES-200…" hedge in `docs/data-pipeline.md` §Stage 2; eval anchor must come from elsewhere (global-piqa-parallel `haw`, Taxi1500 `haw_Latn`, held-out Tatoeba, BibleNLP `haw`).

Recommendation persisted to `.squad/decisions/inbox/frank-haw-variants.md`:

1. Keep FineWeb-2 `haw_Latn` as primary Stage-1 web text.
2. Add GlotCC-V1 `haw-Latn` as independent second source for cross-source dedup and filter-disagreement analysis.
3. Hold `haw_Latn_removed` as recall contingency only, behind data-policy review (Linus).
4. Inventory finepdfs `haw_Latn` separately and dedup against archive.org/Ulukau before any pull.
5. Use DCAD-2000 `keep/remove/stas` jsonls as a free second-opinion filter (metadata-level).
6. Replace FLORES eval-anchor assumption with global-piqa-parallel / Taxi1500 / Tatoeba held-out (Rusty's call on which is primary).

No bytes pulled. No new entries added to `data-sources/hawaiian-data-sources.json` yet — pending Linus/Rusty review of the inbox note.

### 2026-04-29 09:27:41Z — Hawaiian dataset inventory audit complete; merged to decisions.md

**From Scribe:** Your full HF metadata probe is now in decisions.md as "Inventory: Hawaiian Dataset Variants Beyond FineWeb-2 `haw_Latn`" (appended 2026-04-29T09:27:41Z). Rusty's complementary normalization advisory is also merged.

**Key additions to your next collector scripts:**
- Use Rusty's allow-list approach: `{haw_Latn, haw-Latn, haw, hawn_Latn, Hawaiian, hawaiian, HAW} → haw` (case-normalized, exact match, no prefix matching).
- Record verbatim `source_language_config` (e.g., `haw_Latn`, `hawn_Latn`, `haw`) and our normalized `source_language_resolved` (always `haw` for Hawaiian).
- For FineWeb-2: hard-code `haw_Latn`; for FLORES-Plus (when you hit it), hard-code `hawn_Latn` with a note.

**New sources from your audit to inventory:**
- GlotCC-V1 `haw-Latn` (independent CC filter) — recommended as second Stage-1 source.
- DCAD-2000 `haw_Latn` (keep/remove/stas splits) — metadata-level filter comparison tool.
- finepdfs `haw_Latn` (PDF modality) — defer until metadata diff vs. Ulukau/archive.org is done.
- `haw_Latn_removed` (FineWeb-2 reject pool) — contingency only; needs Linus data-policy sign-off.

**Eval anchor shift:** FLORES has no Hawaiian. Candidates (your recommendation): global-piqa-parallel (preferred), Taxi1500, Tatoeba held-out, BibleNLP.

**Open question for you:** Should finepdfs `haw_Latn` be pulled (after dedup check), or is it too-likely Ulukau re-ingest? Coordinate with Linus on archive-dedup strategy if you move forward.

**Reference:** `.squad/decisions.md` → your full inventory + Rusty's normalization rules (appended 2026-04-29T09:27:41Z).

