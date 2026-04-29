# Session Log: FineWeb-2 Hawaiian Scripts

**Date:** 2026-04-29T09:40:34Z

## What Landed

Frank delivered:
- `scripts/105_collect_fineweb2_haw.py` (planner)
- `scripts/205_fetch_fineweb2_haw_raw.py` (fetcher)
- Updated `docs/data-pipeline.md`

Smoke test: 2 real rows, 1,028 whitespace tokens. Live.

## Open Questions

- **Linus:** Dependencies (pyarrow/huggingface_hub) and per-URL rights posture
- **Rusty:** Tokenizer fragmentation; LID/quality threshold

## Next

Await Linus/Rusty feedback. No commit until decisions in place.
