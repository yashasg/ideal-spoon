# Kaggle T4x2 prototype setup

This is a prototype/learning run path, not a release path. Keep `data/` and `runs/` off-git, and preserve checkpoints before the Kaggle session ends.

## 1. Notebook settings

Create a Kaggle Notebook and enable:

| Setting | Value |
|---|---|
| Accelerator | GPU T4 x2 |
| Internet | On |

The T4 x2 setting gives two discrete 16GB T4 GPUs. The current training command uses one Python process with `device_map="auto"` to shard the 8B model across both GPUs for memory; it is not DDP/data-parallel throughput.

## 2. Get the repo

```bash
cd /kaggle/working
git clone --depth 1 https://github.com/yashasg/ideal-spoon.git
cd /kaggle/working/ideal-spoon   # absolute path — safe to re-run if already inside the repo
```

If `git clone` fails but outbound download works:

```bash
cd /kaggle/working
curl -L https://github.com/yashasg/ideal-spoon/archive/refs/heads/main.zip -o ideal-spoon-main.zip
python3 -m zipfile -e ideal-spoon-main.zip .
mv ideal-spoon-main ideal-spoon
cd /kaggle/working/ideal-spoon   # absolute path — safe to re-run
```

If the repo is private, do not paste tokens into notebook cells. Use Kaggle Secrets for GitHub and Hugging Face credentials.

## 3. Attach the data

The repo does not contain `data/`. Attach a private Kaggle Dataset containing the off-git data tree, then copy it under the clone:

```bash
mkdir -p /kaggle/working/ideal-spoon/data
cp -R /kaggle/input/<your-dataset-name>/data/. /kaggle/working/ideal-spoon/data/
cd /kaggle/working/ideal-spoon
```

Required files for the current Kaggle config:

```bash
test -s data/stage1/stage1.jsonl.gz
test -s data/evals/fineweb2_haw/dev.jsonl
```

`data/stage1/stage1.jsonl.gz` is train-only and multi-source: 81,117 cleaned rows / ~44.1M whitespace tokens from FineWeb-2, hawwiki, and hawwikisource. The eval file remains the FineWeb-2 Hawaiian dev split.

## 4. Install deps and authenticate

Kaggle already provides PyTorch, so skip reinstalling torch. **Use `--no-venv --skip-torch`** — this is the recommended path for Kaggle notebooks (installs directly into Kaggle's Python env, no virtualenv needed):

```bash
python3 scripts/setup_training.py --no-venv --skip-torch
huggingface-cli login
```

> **Note on `setup_compute.sh`:** The shell wrapper (`scripts/setup_compute.sh`) delegates directly to `setup_training.py`. It creates a `.venv-training` virtualenv by default, which is not useful on Kaggle where PyTorch is pre-installed. Always pass `--no-venv --skip-torch` on Kaggle. If you previously ran `setup_compute.sh` without these flags and the session still has a broken `.venv-training`, the script will now automatically detect a corrupt venv (missing pip) and recreate it rather than failing.

> **If `pip check` reports conflicts:** When using `--no-venv`, Kaggle's shared base image may already contain unresolved package conflicts unrelated to this project. The setup script treats `pip check` as a **warning** (not a hard error) on `--no-venv` paths. A message like `>> warning: pip check exited 1` means the install itself likely succeeded — the conflicts are from the provider image. You can safely proceed to the preflight step. If you want to verify only project-installed packages are clean, inspect the conflict list manually; if all flagged packages are Kaggle base-image packages, the install is fine. To force a hard failure on any conflict, re-run with `--strict-pip-check`.

You need Hugging Face access to `meta-llama/Llama-3.1-8B`.

## 5. Preflight, then train

```bash
PYTHONPATH=code python3 -m llm_hawaii.train \
  --config code/configs/stage1_fineweb2_haw_kaggle_t4x2.json \
  --preflight

PYTHONPATH=code python3 -m llm_hawaii.train \
  --config code/configs/stage1_fineweb2_haw_kaggle_t4x2.json
```

Outputs land under:

```text
runs/llama31-8b-stage1-multisource-kaggle-t4x2/
```

The Kaggle config saves/evals every 100 steps and keeps up to 300 checkpoints, disk permitting, so a separate checkpoint watcher is usually unnecessary.

Current VRAM tuning uses `max_seq_len=2048`, `per_device_train_batch_size=1`, and `gradient_accumulation_steps=16`, giving 16 × 2048 = 32 768 tokens per gradient update. **`per_device_train_batch_size=2` was tested as an experimental optimisation but OOMed on the real backward pass** (tried to allocate ~1.96 GiB with only ~1.60 GiB free on GPU 1); batch=1 is the stable default.

> **`PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`** may reduce allocator fragmentation and is worth trying if you see fragmentation-related OOMs. It is not sufficient to hold `batch=2` with this model — the observed allocation error is a capacity issue, not a fragmentation issue. The primary fix is `batch=1`.

## 6. Preserve outputs

Before the notebook ends, archive the run directory and save it to persistent storage:

```bash
tar -czf /kaggle/working/stage1-kaggle-run.tgz \
  runs/llama31-8b-stage1-multisource-kaggle-t4x2
```

Resume from a checkpoint with:

```bash
PYTHONPATH=code python3 -m llm_hawaii.train \
  --config code/configs/stage1_fineweb2_haw_kaggle_t4x2.json \
  --resume-from-checkpoint runs/llama31-8b-stage1-multisource-kaggle-t4x2/checkpoint-NNN
```

If Kaggle OOMs, first set `per_device_train_batch_size=1` and `gradient_accumulation_steps=16`. If it still OOMs, try `max_seq_len=1024` and `gradient_accumulation_steps=32`. If it still OOMs after that, reduce LoRA rank to 16 / alpha to 32. Use `max_seq_len=512` only as a plumbing test.
