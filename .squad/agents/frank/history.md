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
