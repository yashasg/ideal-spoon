# 2026-04-29T10-08-17Z: FineWeb-2 Evaluation Split Directive

**Received from:** yashasg (via Copilot)  
**Logged by:** Scribe  

## Directive

Once Frank completes the FineWeb-2 raw pull, execute the following:

1. **Split the full `haw_Latn` test split into dev and holdout**
   - Deterministic split (fixed seed for reproducibility)
   - Approximately 80% dev (~710 rows), 20% holdout (~177 rows) from 887 total test rows
   - Dev rows: checkpoint monitoring/validation during Stage 1
   - Holdout rows: reserved for final holdout evaluation, never used for tuning decisions

2. **Dedupe FineWeb-2 train against the full test split**
   - Match rows in train set (95,507 rows) against all test set rows (887 total) via exact hash
   - Remove any train rows that match test rows
   - Prevents train-test data leakage before Stage 1 DAPT training

## Blocking Condition

Frank's full FineWeb-2 fetch is still in progress. Linus data engineering implementation is blocked until raw data arrives.

## Implementation Owner

Linus (Data Engineering) — after raw FineWeb-2 data is available, before Stage 1 training harness integration.

## Reference Context

- FineWeb-2 `haw_Latn` dataset: 95,507 train + 887 test rows, confirmed live access via ODC-By wrapper
- Access methods: HF datasets-server `/rows` API or parquet conversion
- Linked decision: "FineWeb-2 Test Split: Checkpoint Eval Reuse Locked" (2026-04-29T09:59:05Z)

## Notes

- Use fixed seed for frozen split to ensure reproducibility across runs
- Record which specific rows belong to dev vs holdout for final reporting
- Dedupe should use robust hashing (e.g., SHA-256 on text content) to catch exact duplicates
- Final Stage 1 report will separate checkpoint dev metrics from holdout holdout metrics with clear caveats
