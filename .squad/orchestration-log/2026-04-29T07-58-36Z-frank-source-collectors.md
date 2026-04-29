# Orchestration Log: 2026-04-29T07:58:36Z — Frank source-collectors consolidation

## Agent
- **Name:** Frank (hawaiian data collector)
- **Task:** Implement source-specific 100-phase collection scripts

## Scope
- Retired single broad `scripts/101_collect_rightslight.py` planner
- Introduced `101_collect_hawwiki.py`, `102_collect_hawwikisource.py`, `103_collect_hawwiktionary.py`
- Enhanced `202_fetch_hawwikisource_raw.py` with `--page-plan` / `--no-page-plan` flags
- Updated `201_fetch_rightslight_raw.py` (documented)
- Updated documentation in `docs/data-pipeline.md`

## Changes
- **Added scripts:** 101, 102, 103 per-source collectors
- **Modified scripts:** 201, 202 fetchers (202 now consumes 102 page plans)
- **Validation:** All scripts compile; --help works; dry-run successful; no corpus fetched
- **Metadata:** Staged under `data/local/<source>/`, gitignored

## Decisions Consolidated
1. **Copilot directive (2026-04-29T00:48:05-07:00):** User request — source-specific scripts for 100 phase
2. **Frank proposal (2026-04-29):** Per-source 100-phase split, status Proposed → Active
3. **Superseded:** Broad rights-light planner (phase-100) now archived in decision history

## Coordination Notes
- **Linus:** No schema change to `ProvenanceRecord`; 202 handoff unchanged
- **Rusty:** No tokenizer impact from phase-100 restructure

## Status
Completed. Inbox decisions merged into decisions.md. Frank and Linus histories updated. Team policies confirmed.
