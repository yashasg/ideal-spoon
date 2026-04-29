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

