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
