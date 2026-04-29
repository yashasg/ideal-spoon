# Orchestration: Linus — Script renumbering (phase hundreds)

**Time:** 2026-04-29T07:39:07Z  
**Agent:** linus-renumber-scripts (sync, claude-opus-4.7)  
**Directive:** Reconcile corrected phase-hundreds numbering: rename active scripts to 101, 201, 202, 301

## Outcome

✅ **COMPLETE**

- Renamed `scripts/001_collect_rightslight.py` → `scripts/101_collect_rightslight.py`
- Renamed `scripts/002_fetch_rightslight_raw.py` → `scripts/201_fetch_rightslight_raw.py`
- Renamed `scripts/002b_fetch_hawwikisource_raw.py` → `scripts/202_fetch_hawwikisource_raw.py`
- Renamed `scripts/003_build_stage1_dataset.py` → `scripts/301_build_stage1_dataset.py`
- Updated all internal and cross-file references in active scripts
- Updated docs/data-pipeline.md and .squad/decisions/inbox/*.md with new paths
- Validated all four scripts compile and execute correctly (dry-run mode)

## Reference sweep

- Confirmed no stale `001`, `002`, `003`, `002b` references in scripts/, docs/, inbox/
- Historical record (orchestration logs, decisions.md, agent histories) left as-is per convention
- Future entries use phase-hundreds naming

## Decision inbox

- `linus-phase-numbering.md` — formal rationale: phase shape from `ls scripts/`, ~99 slots per phase, flat sequence awkwardness eliminated

## Notes

Phase-hundreds convention approved by yashasg (user directive). Migration complete without history rewriting.
