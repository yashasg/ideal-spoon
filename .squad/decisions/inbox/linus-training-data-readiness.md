# Decision: Training Input Path for Stage 1 Prototype Run

**Date:** 2026-05-01  
**Owner:** Linus (Data Engineer)  
**Status:** PROPOSED — awaiting run confirmation

---

## Chosen training input path

`data/stage1/fineweb2_haw/train.jsonl` (95,507 rows)

In `code/configs/llama31_8b_a100.json`, this is expressed as:
```
"train_path": "../data/stage1/fineweb2_haw/train.jsonl"
```
(relative to `code/`, matching the `path_note` run convention).

Eval input: `data/evals/fineweb2_haw/dev.jsonl` (621 rows), wired as `eval_path`.

---

## Why this file is acceptable for prototype Stage 1

1. **Complete and clean fields.** 95,507 rows; zero missing `text`, zero empty `text`, 100% NFC. No blocker for `data.py`'s `iter_jsonl` / `build_train_dataset` path.
2. **Contamination guard passes.** `train.jsonl` was produced by `310_split_dedupe_fineweb2_haw.py` which SHA-deduped training rows against the *full* 887-row test split before writing. `train ∩ eval_hashes = ∅` by construction.
3. **Orthography gated.** Paragraph-level Hawaiian LID re-gate and ʻokina canonicalization ran inside `301_build_stage1_dataset.py`; rejected rows are excluded from `stage1.jsonl.gz` (see §4 of `docs/data-readiness-stage1.md`).
4. **Prototype framing is preserved.** `prototype_only=True`, `release_eligible=False` on every row. This framing is not relaxed.

---

## What changed in code/config

- `code/configs/llama31_8b_a100.json`:
  - `train_path`: `../data/stage1/stage1.jsonl.gz` → `../data/stage1/fineweb2_haw/train.jsonl`
  - `eval_path`: `null` → `../data/evals/fineweb2_haw/dev.jsonl`
  - `eval_steps`: `null` → `200`
  - `notes`: updated `path_note`, added `train_data_note` and `eval_data_note`

- `code/llm_hawaii/train.py`:
  - `build_training_args`: wires `eval_strategy="steps"` + `eval_steps` when both `cfg.eval_path` and `cfg.eval_steps` are non-null (safe no-op otherwise)
  - `run_training`: loads `eval_dataset` when `cfg.eval_path` is set; passes it to `Trainer`

- `code/tests/test_data.py`: +9 new tests
  - `TestData`: `test_iter_jsonl_bad_json`, `test_iter_jsonl_empty_lines_skipped`, `test_normalize_text_nfc_idempotent`, `test_normalize_text_unknown_form`
  - `TestTrainConfig` (new class, no ML deps): `test_smoke_config_loads`, `test_llama31_config_loads`, `test_unknown_key_raises`, `test_eval_path_and_eval_steps_paired`, `test_config_roundtrip`

- `docs/data-readiness-stage1.md`: new — count/hash/status summary, no raw text.

---

## Note on `stage1.jsonl.gz` (the post-cleaning alternative)

`data/stage1/stage1.jsonl.gz` also exists (81,117 rows, 6-field slim schema). It is the cleaned, multi-source output of `301_build_stage1_dataset.py` and is the pipeline-canonical trainer candidate per `docs/data-pipeline.md §3`. Token estimate is ~44M clean tokens.

Per user directive, this run targets `fineweb2_haw/train.jsonl` (pre-cleaning, FineWeb-only). To switch to the cleaned output, change `train_path` to `../data/stage1/stage1.jsonl.gz`. The `data.py` loader handles `.gz` transparently.

---

## Caveats remaining

1. **Not release-eligible.** `prototype_only=True` — do not publish resulting checkpoints as production artifacts.
2. **MinHash near-dedup not complete.** Exact SHA dedup is done; LSH/MinHash across FineWeb × hawwiki × hawwikisource is planned.
3. **No cultural-sensitivity tagging** on FineWeb-2 rows yet.
4. **Token volume ~17.6% of conservative target** (44M of 250M). Expected for FineWeb-only prototype slice.
5. **eval_strategy key:** newer HF Trainer uses `eval_strategy`; older uses `evaluation_strategy`. Current `train.py` uses `eval_strategy`. If run fails with unknown-key error, downgrade to `evaluation_strategy`.

---

## Coordination with Basher (training runner)

The config path resolution convention is: paths in JSON configs are relative to `code/` (where `python -m llm_hawaii.train` is invoked). Basher's runner should not change this CWD or pass an absolute override unless it writes `resolved_config.json` with absolute paths. The `run_training()` function already writes `resolved_config.json` alongside checkpoints.

If Basher modifies `llama31_8b_a100.json` for runner-specific settings, coordinate to avoid clobbering `train_path`/`eval_path`.
