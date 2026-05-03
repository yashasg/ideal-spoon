# Linus Stage-2 Round 14 — train-side eval contamination wired

Date: 2026-05-03

## Decision

`--eval-hashes` is now an enforcing train-side gate in `scripts/320_build_stage2_manifest.py`, not a cosmetic output-time filter. Explicit eval ledgers are loaded before dedup; matching candidate rows are dropped before cross-source/side/near-duplicate dedup runs. Missing explicit ledgers are hard errors.

## Reporting contract

Manifest builds with `--eval-hashes` write `data/stage2/contamination_report.json` with:

- `ledger_path`
- `ledger_size`
- `total_dropped`
- `per_source_dropped`
- `per_match_type` (`full_pair`, `single_side_haw`, `single_side_en`)
- `drop_reasons` using `contamination:{source}`
- dropped row IDs/source/match type examples

The build manifest also embeds the contamination filter stats under `ingest.contamination_filter`.

## Audit contract

`scripts/340_audit_stage2_candidate_normalization.py --eval-hashes <ledger>` reports how many candidate rows would be dropped without mutating inputs. `--strict` treats any contamination as an error and lists row IDs in the JSON report.

## Verification

No network fetches or new sources were used. Regression results:

- `test_eval_contamination.py`: 5/5
- `test_manifest_contamination_filter.py`: 2/2
- `test_stage2_dedup.py`: 13/13
- `test_taxi1500_ingester.py`: 6/6
- `test_global_piqa_ingester.py`: 5/5
- `scripts/320_build_stage2_manifest.py --dry-run`: 37,084 rows
- `scripts/340_audit_stage2_candidate_normalization.py --strict`: pass

## Round 15 recommendation

Dedup edge-case shoring up is the best next infra piece: add focused tests around interaction order between contamination filtering, exact-side caps, near-dupe collapse, and historical-orthography caps.
