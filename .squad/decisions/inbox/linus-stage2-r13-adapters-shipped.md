# Linus Stage-2 Round 13 — adapters shipped

**Date:** 2026-05-03
**Owner:** Linus
**Status:** Implemented / awaiting gated `--execute`

## Decision

Ship two mocked, dry-run-only Stage-2 adapters now so execution can happen later only after explicit rights gates.

1. **Taxi1500 haw_Latn** is eval-only. `scripts/348_ingest_taxi1500_haw.py` writes only eval-ledger rows with `eval_only=true`, `license_spdx=Apache-2.0`, and `bible_overlap_candidate=true`; it refuses `data/stage2/candidates/` outputs.
2. **Tatoeba refresh** is train-candidate capable but gated. `scripts/349_refresh_tatoeba_candidates.py` writes `data/stage2/candidates/tatoeba_refresh_{date}.jsonl` only under `--execute` with edition date, `CC-BY-2.0-FR` confirmation, local ToS snapshot, polite UA, ≥2s sleeps, existing-edition dedup, and refresh threshold pass.

## Compliance

No live network was used. No `--execute` was run. Tests use only inline fixtures / local mocked rows. The ambiguous Taxi1500 split path is not fetched; later execution must provide a concrete local file and dataset pin in `org/repo/<40hex>` form.

## Verification

- `python3 code/tests/test_taxi1500_ingester.py -v` — 6 tests passed
- `python3 code/tests/test_eval_contamination.py -v` — 5 tests passed
- `python3 code/tests/test_tatoeba_refresh.py -v` — 7 tests passed
- `python3 scripts/320_build_stage2_manifest.py --dry-run` — 37,084 rows

## Next

Recommended Round 14: wire train-side eval-contamination filtering into the default manifest dry-run path, then probe Common Voice metadata, FLORES+ haw, or OPUS-TildeMODEL license/endpoint status.
