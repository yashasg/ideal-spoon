# Session Log: Stage-1 Token Gap Correction

**Date:** 2026-04-29T07:19:07Z
**Coordinator:** yashasg

## Summary

Two agents (Frank, Linus) in parallel addressed the Stage-1 data pipeline gap:

1. **Frank** reworked `scripts/001_collect_rightslight.py` to tier sources against the 2.5M conservative right-clearable floor. Honest posture: ~1.0M shortfall today (just hawwiki fetched), barely clears 2.5M with expansion adapters. No corpus fetched; validation via `py_compile` and metadata-free dry run.

2. **Linus** fixed schema handoff (002→003), added token-volume gate (conservative=2.5M, base=4.5M, upside=7M), and introduced `--show-targets` / `--strict` flags. Also locked in numbered pipeline convention (001_, 002_, 003_) for clarity.

## Files Modified

- `scripts/001_collect_rightslight.py` — tiered fetch plan, token estimates, blockers, coverage summary (schema v0.2.0)
- `scripts/002_fetch_rightslight_raw.py` — docstring "Scope vs. Stage-1 target" paragraph
- `scripts/003_build_stage1_dataset.py` — token-volume gate, field-name aliases, backward compat, --show-targets, --strict (exit 2)
- `docs/data-pipeline.md` — one-line Stage-1 update

## Decisions Filed

1. `frank-rightslight-token-target.md` — Proposed (team awareness; coordinate with Linus on Wikisource adapter)
2. `linus-numbered-pipeline-scripts.md` — Proposed (pipeline numbering convention)
3. `linus-stage1-token-gate.md` — Proposed (right-clearable targets, mechanical gate)

## Next Steps

- Frank: Land Tatoeba, Wikisource bulk-text, Wikipedia langlinks adapters (expansion candidates).
- Linus: Coordinate Wikisource extracted-text contract; align NFC / ʻokina canonicalization.
- Rusty: Tokenizer audit to replace ±2× token bands with ±20% bands; verify fragmentation doesn't drop below floor.
- Basher: CI gate on exit code 2 (`--strict` fail) for Stage-1 volume check.

All validation passed. No corpus committed. Local `.squad/` and orchestration logs staged for git commit.
