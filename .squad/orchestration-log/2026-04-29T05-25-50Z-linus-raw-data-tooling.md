# Orchestration Log: Linus Raw Data Tooling Recommendation

**Timestamp:** 2026-04-29T05:25:50Z  
**Agent:** Linus (Data Engineer)  
**Mode:** Sync  
**Agent ID:** linus-raw-data-tooling  
**Topic:** Open-source Python CLI tooling for gathering raw public data

## Summary

Linus recommended a curated stack for raw data collection:

**Core Stack:**
- requests + tenacity (robust HTTP)
- warcio + trafilatura (content extraction)

**Crawling:**
- Scrapy for real crawling/link-following
- Playwright only for JS-heavy sites
- Skip newspaper3k and bare wget as primary tools

**Archives & Specialized:**
- internetarchive/wayback/cdx_toolkit for archive access
- yt-dlp for captions if needed
- datasketch for downstream dedup

**Output:**
- Each adapter should emit raw WARC plus manifest rows with source/provenance metadata

## Outcome

Recommendation accepted for implementation in raw data tooling framework.

## Files Touched

- .squad/agents/linus/history.md

