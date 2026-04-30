# Decision: Training Runner Readiness Contract (Stage 1)

**Date:** 2026-05-01
**Owner:** Basher (Training Engineer)
**Status:** Implemented; ready for next Stage 1 CPT run on compute

---

## Summary

`code/llm_hawaii/train.py` is now runnable for a Stage 1 CPT/QLoRA attempt.
The new active config for the local data is `code/configs/stage1_fineweb2_haw.json`.

---

## Durable Contracts

### 1. Config-relative data paths

All `train_path` / `eval_path` values in JSON configs are resolved **relative
to the config file's directory**, not the process working directory.

- `load_config(path)` calls `resolve_data_paths(cfg, config_path)` immediately
  after parsing; callers always receive absolute paths.
- Running from `repo_root/` or `code/` produces identical behavior.
- This is enforced in `config.py:resolve_data_paths` and tested in
  `code/tests/test_train.py`.

**Migration:** existing configs updated to use config-relative offsets:
- `smoke.json`: `"../examples/train.jsonl.example"`
- `llama31_8b_a100.json`: `"../../data/stage1/fineweb2_haw/train.jsonl"` + eval
- `stage1_fineweb2_haw.json` (new): same paths, output dir `runs/llama31-8b-stage1-fw2/`

### 2. New CLI flags (backward-compatible)

`--config` and `--print-config` unchanged.  Added:

| Flag | Purpose |
|---|---|
| `--preflight` | Validate config + data + runtime without model download. Exit 0 pass / 1 fail. |
| `--resume-from-checkpoint PATH` | Pass a checkpoint dir to `Trainer.train()`. |
| `--eval-after-train` | Run `trainer.evaluate()` after training (requires `eval_path`). |

### 3. Run report schema: `training-run-report.v1`

Every `run_training()` call writes `{output_dir}/run_report.json`.  Fields:

```
schema_version        "training-run-report.v1"
stage                 cfg.stage
run_name              cfg.run_name
config_path           resolved absolute path to .json config
resolved_config       full TrainConfig dict (all fields)
output_dir            resolved absolute path
train.path            absolute train path
train.sha256          SHA-256 of train file
train.row_count       integer row count
eval                  same shape (null if no eval_path)
git_commit            HEAD SHA at run time
runtime_capability    dict from model.check_runtime_capability
wallclock_seconds     float
completed_at_utc      ISO 8601 Z
```

No raw training text enters the report.  This is sufficient to re-run or
compare any run from the output directory alone.

### 4. Preflight checks (no model download required)

`run_preflight(cfg)` verifies:
- Config parsed cleanly (paths resolved to absolute)
- `train_path` file exists, row count > 0, `text_field` present in first row
- `eval_path` exists if configured
- `output_dir` is creatable
- Runtime capability (non-fatal; torch/CUDA absence produces a warning, not an error)

### 5. Next-run command sequence

```bash
# 1. Preflight — always run before GPU spend
python3 -m llm_hawaii.train --config code/configs/stage1_fineweb2_haw.json --preflight

# 2. Train
python3 -m llm_hawaii.train --config code/configs/stage1_fineweb2_haw.json

# 3. Resume after interruption
python3 -m llm_hawaii.train \
    --config code/configs/stage1_fineweb2_haw.json \
    --resume-from-checkpoint runs/llama31-8b-stage1-fw2/checkpoint-NNN
```

---

## What is NOT changed

- No data files staged or committed.
- No `.superset/` files touched.
- Smoke defaults in `config.py` remain on `Qwen2.5-0.5B` / tiny corpus.
- Lazy imports preserved; root venv (no torch) still compiles cleanly.
- Existing `--config` / `--print-config` behavior unchanged.
