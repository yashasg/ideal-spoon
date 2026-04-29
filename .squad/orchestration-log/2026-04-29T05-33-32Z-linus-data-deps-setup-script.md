# Orchestration: Linus — Data Deps Setup Script

**Agent:** Linus (Data Engineer)  
**Agent ID:** linus-data-deps-setup-script  
**Timestamp:** 2026-04-29T05:33:32Z  
**Status:** Complete  
**Mode:** sync  

## Outcome

Created foundational setup infrastructure for raw-data gathering pipeline dependencies.

### Deliverables

1. **scripts/setup.sh** — POSIX `sh`-compliant, idempotent setup script
   - Creates/reuses local `.venv` virtual environment
   - Upgrades pip and wheel
   - Installs raw-data tooling dependencies
   - Playwright **intentionally omitted** (revisit per-source if needed)
   - Respects `PYTHON`, `VENV_DIR`, `REQ_FILE` env overrides

2. **requirements.txt** — Root-level dependency manifest
   - Default stack: `requests`, `tenacity`, `warcio`, `trafilatura`, `selectolax`, `scrapy`, `scrapy-warc`, `internetarchive`, `wayback`, `cdx_toolkit`, `yt-dlp`, `datasketch`
   - Rationale comments updated to avoid public-domain assumptions
   - Aligns with existing Stage-1/Stage-2 data-pipeline ADRs

3. **.gitignore** — Updated to exclude runtime/cache artifacts
   - `.venv/`, `.venv-*/` (virtual env variants)
   - `__pycache__/`, `*.pyc` (Python compiled)

## Context

- User requested raw-data gathering tooling with **Playwright explicitly omitted** for prototype phase
- Ulukau/Wikisource/Bible/archive.org/Tatoeba/FLORES targets are static HTML or downloadable archives; JS rendering not justified yet
- Implements existing tooling guidance from prior data-pipeline notes; no new decision required

## Rationale

POSIX `sh` + idempotent design ensures portability (macOS, Linux, CI). Local `.venv` avoids system-wide pollution. Explicit Playwright skip signals to team: JS rendering is not part of current prototype scope.

## Notes

- No shellcheck available locally; validated with `sh -n` and `bash -n` only
- Full network install not executed in this task
- Script is self-documenting; README remains a design narrative, not getting-started guide
