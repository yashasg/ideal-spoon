# Session Log: Raw Data Tooling

Linus recommended Python CLI stack for raw data collection: requests + tenacity, warcio + trafilatura, Scrapy for crawling, Playwright for JS-heavy sites, internetarchive/wayback/cdx_toolkit for archives, yt-dlp for captions, datasketch for dedup. Output: raw WARC + manifest with provenance metadata.
