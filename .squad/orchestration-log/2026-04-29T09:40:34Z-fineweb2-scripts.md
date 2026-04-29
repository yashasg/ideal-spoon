# Orchestration Log: FineWeb-2 Hawaiian Scripts Integration

**Date:** 2026-04-29T09:40:34Z  
**Trigger:** Frank (Hawaiian Data Collector) completed 100/200 phase scripts for FineWeb-2 `haw_Latn`

## Outcome Summary

Frank spawned to create verified FineWeb-2 Hawaiian data collection pipeline:

- **Output:** `scripts/105_collect_fineweb2_haw.py` (100-phase planner) + `scripts/205_fetch_fineweb2_haw_raw.py` (200-phase fetcher)
- **Validation:** py_compile passed; 105 dry-run succeeded; 205 smoke test (`--execute --split test --limit 2`) fetched 2 real rows, 1,028 raw whitespace tokens, 4,974 chars from staradvertiser.com
- **Documentation:** `docs/data-pipeline.md` updated with Stage 1 FineWeb-2 integration; FLORES eval anchor corrected (no Hawaiian in FLORES/FLORES+)
- **Decisions:** Boxed open questions for Linus (dependency/rights posture) and Rusty (tokenizer sanity check) in `.squad/decisions/inbox/frank-fineweb2-scripts.md`

## Files Produced/Modified

**Outside .squad (committed via Scribe):**
- `scripts/105_collect_fineweb2_haw.py` — new
- `scripts/205_fetch_fineweb2_haw_raw.py` — new
- `docs/data-pipeline.md` — updated

**Inside .squad (via Scribe):**
- `.squad/decisions/inbox/frank-fineweb2-scripts.md` — appended by Frank; merged to decisions.md by Scribe
- `.squad/agents/frank/history.md` — appended learnings + re-verification entry
- `.squad/orchestration-log/2026-04-29T09:40:34Z-fineweb2-scripts.md` — this log

**Local data (gitignored):**
- `data/local/fineweb2_haw/collect_plan.json` — 105 output
- `data/raw/fineweb2_haw/{YYYYMMDD}/{split}.jsonl` — 205 smoke-test output
- `data/raw/fineweb2_haw/fetch.jsonl` — provenance ledger

## Open Questions Escalated

1. **Linus (dependency call):** Add `pyarrow`/`huggingface_hub` to `requirements.txt` or stay stdlib-only via rows API? Scripts default to rows API; parquet is opt-in with loud failure if dep missing.
2. **Linus (per-URL rights posture):** Accept all rows at prototype scope, or enforce per-URL allow/deny list downstream?
3. **Rusty (tokenizer sanity):** Fragmentation analysis on FineWeb-2 sample once bulk pull authorized; LID/quality threshold for Stage-1 inclusion given boilerplate mix.

## Coordinator Actions Taken

1. Corrected stale `docs/data-pipeline.md` FLORES assumptions: FLORES/FLORES+ have no Hawaiian config; Stage 2 eval anchors now point to global-piqa/Tatoeba/Taxi1500 diagnostics instead.
2. Verified all generated Python files compile without syntax errors.
3. Confirmed live data fetch and provenance logging working.

## Status

✅ Scripts ready for integration. Awaiting Linus (dependency + rights ruling) and Rusty (tokenizer feedback) before Stage 2 planning.
