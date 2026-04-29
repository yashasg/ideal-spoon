# Orchestration Log — Frank (Hawaiian Data Collector)

**Timestamp:** 2026-04-29T05:50:27Z  
**Agent:** Frank  
**Topic:** Hawaiian data-source URL inventory and storage format guidance  
**Status:** Completed  
**Outcome:** Success  

## Deliverables

1. **`docs/hawaiian-data-sources.json`**
   - Tool-bucketed URL inventory for Hawaiian-language and Hawaiian-parallel sources
   - 26 candidate entries grouped by installed collection tooling:
     - `requests_tenacity`: Wikimedia dumps, Wikipedia langlinks API, FLORES-200, Tatoeba, OPUS, baibala.org, eBible
     - `internetarchive`: archive.org Ulukau-mirrored items, Hawaiian books/dictionaries, archival Bible scans
     - `wayback_cdx_toolkit`: Historical snapshots of Ulukau, nupepa.org, OHA, DOE Kaiapuni, UH PDFs
     - `scrapy_scrapy_warc`: Live crawls of Ulukau, Hawaiian Wikisource, Awaiaulu, OHA, DOE, UH ScholarSpace
     - `trafilatura_selectolax`: Post-fetch extraction (not a fetcher)
     - `yt_dlp`: Captions-only, intentionally empty pending per-channel rights confirmation
   - Rights hints, license/ToS URLs, provenance fields, priorities, and deferred/excluded notes included
   - Validated: `python3 -m json.tool docs/hawaiian-data-sources.json` passed

2. **`.squad/agents/frank/history.md`**
   - Updated with 2026-04-29 Hawaiian source URL inventory entry
   - Recorded tool-bucketing decisions and rights posture
   - Documented routing rules for each installed dependency
   - Captured project-relevant URLs and templates for FLORES, Bible, Tatoeba, OPUS, Wayback CDX

3. **`.squad/decisions/inbox/frank-hawaiian-source-url-inventory.md`**
   - Decision proposal routed by installed tool, with team context for Linus, Rusty, and Coordinator
   - Captured open questions on Bible edition, OHA/DOE/UH scope, and YouTube channel licensing

## Coordination Notes

- **For Linus:** JSON serves as per-source manifest seed with provenance fields
- **For Rusty:** P0 sources (hawwiki dump, FLORES-200, Tatoeba) are clean fodder for tokenizer audit (ʻokina U+02BB + kahakō, NFC); Bible capped per Stage-2 ADR (≤30% parallel-train, 0% dev/test)
- **For Coordinator:** First build-out should prioritize P0 entries (hawwiki dump, FLORES-200 eval hashing, Tatoeba, baibala.org + eBible verse anchor)

## Quality Checks

✓ JSON parses cleanly  
✓ Tool routing covers all installed deps  
✓ Rights posture consistent (no bare "public domain" claims)  
✓ Deferred/excluded entries documented (JW300, hard-escalate cultural)  
✓ Manifest seed ready for Linus adapter work  

## Known Open Items

1. Pinned Hawaiian Bible edition (e.g., 1868 Andrews/Bingham) — needs human pick before adapter work
2. OHA/DOE/UH bilingual PDF scope — in prototype or deferred?
3. Hawaiian-language YouTube channel licensing — confirmation needed before `yt_dlp` bucket populated
