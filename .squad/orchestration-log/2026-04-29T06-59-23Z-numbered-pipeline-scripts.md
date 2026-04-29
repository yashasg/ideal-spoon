# Orchestration Log: Numbered Pipeline Scripts

**Timestamp:** 2026-04-29T06:59:23Z  
**Agent:** Scribe (session logger)  
**Event:** Script naming coordination and history consolidation

## Summary

Linus completed renaming the Python data pipeline scripts to encode execution order:
1. `scripts/001_collect_rightslight.py` (formerly `scripts/collect_rightslight.py`)
2. `scripts/002_fetch_rightslight_raw.py` (formerly `scripts/fetch_rightslight_raw.py`)
3. `scripts/003_build_stage1_dataset.py` (formerly `build_stage1_dataset.py`)

All references in script docstrings, usage examples, `generated_by`/`fetcher` fields, comments, and current decision text have been updated. Coordinator validated compilation: `python3 -m py_compile scripts/001_collect_rightslight.py scripts/002_fetch_rightslight_raw.py scripts/003_build_stage1_dataset.py` — all clean.

## Coordination Notes

- **Frank's responsibility:** Stage 1 raw fetch (via `scripts/002_fetch_rightslight_raw.py`).
- **Linus's responsibility:** Registration, LID, extraction, normalization, deduplication, eval-hash pipeline (via `scripts/003_build_stage1_dataset.py`).
- **Manifest discipline:** Every fetch-time field (ToS snapshot, source URL, fetch date, sha256_raw) is captured at ingest and unrecoverable later.
- **Numbered order:** Scripts run in sequence; numbering ensures no ambiguity on expected order.

## Git Status

- `.squad/` modified: `.squad/agents/linus/history.md`, `.squad/decisions.md`
- `scripts/` untracked: numbered scripts not yet staged/committed (pending user approval)

## Next Steps

- Merge any pending decision-inbox files into `.squad/decisions.md`
- Append concise updates to Linus and Frank history nodes
- Commit `.squad/` changes with trailer: `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`
