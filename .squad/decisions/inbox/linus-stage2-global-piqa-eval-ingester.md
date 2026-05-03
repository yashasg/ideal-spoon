# Linus Stage-2 Round 11 — Global-PIQA eval-only ingester

Date: 2026-05-03

## Verdict carried forward

Global-PIQA `haw_Latn` remains **YELLOW / eval-only**. The dataset card advertises `CC-BY-SA-4.0`, but also explicitly forbids AI training and says the dataset is intended only for LLM evaluation. Therefore this source must not create Stage-2 train candidates and must not seed synthetic data.

## Implementation

- Added `scripts/347_ingest_global_piqa_haw.py`.
- No live network is implemented or tested.
- `--self-test` uses an inline 3-row TSV fixture and writes eval hashes only.
- `--execute` is triple-gated:
  - exact dataset pin: `mrlbenchmarks/global-piqa-parallel@a350910e9cfc8b0b57cb55aa8261780deabb6568`
  - exact license confirmation: `CC-BY-SA-4.0`
  - local ToS/license snapshot path
- `--execute` still requires a local TSV path; it does not fetch from Hugging Face.
- Ledger output appends to `data/evals/eval_hashes.jsonl` with `source`, `item_id`, `content_sha256`, `license_spdx`, `license_url`, `dataset_revision`, `fetched_at`, and `eval_only: true`.
- The ingester refuses any output path under `data/stage2/candidates/`.

## Contamination guard

Added `code/llm_hawaii/eval_contamination.py` and wired `scripts/320_build_stage2_manifest.py --eval-hashes`. When an eval ledger path is explicitly supplied, matching Stage-2 candidates are dropped before manifest emission and the drop count is recorded as `eval_contamination_dropped`. If `--eval-hashes` is absent, build behavior remains unchanged.

Normalization is NFC + whitespace collapse. Hawaiian maps ASCII/curly apostrophe variants to U+02BB ʻokina; English maps apostrophe variants to ASCII apostrophe. This makes PIQA eval hashes usable as a train-side backstop for future candidate rows with matching normalized content.

## Verification

- `python3 code/tests/test_global_piqa_ingester.py -v`: 5 tests passed.
- `python3 code/tests/test_eval_contamination.py -v`: 4 tests passed.
- `python3 scripts/320_build_stage2_manifest.py --dry-run`: 37,084 rows.
- `python3 scripts/320_build_stage2_manifest.py --dry-run --eval-hashes data/evals/r11_empty_eval_hashes.jsonl`: 37,084 rows, 0 contamination drops.

## Next

Recommended Round 12: probe another eval-only diagnostic (Taxi1500) or refresh Tatoeba before adding more train-side sources.
