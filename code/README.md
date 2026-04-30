# `code/` — Learning Skeleton for Hawaiian LLM Fine-Tuning

> ⚠️ **Prototype / learning code.** This is not a production training pipeline,
> not a release path, and not wired to any real corpus. Files here are
> intentionally skeletal: the right function boundaries are in place, the
> hard parts are marked `TODO`, and the heavy ML imports are deferred so the
> module parses on a laptop with nothing installed.
>
> Goal: a first-time LLM-trainer can read these files top-to-bottom, fill in
> the TODOs, and learn the moving parts of a QLoRA fine-tune by doing.

## What's here

```
code/
├── README.md                  # this file
├── llm_hawaii/
│   ├── __init__.py
│   ├── config.py              # dataclass config + JSON load/save
│   ├── data.py                # JSONL loader + tokenization hooks (TODO)
│   ├── model.py               # base model + LoRA/QLoRA loading (TODO)
│   ├── train.py               # training entrypoint with main() CLI
│   ├── evaluate.py            # checkpoint eval CLI (PPL + generation)
│   └── metrics.py             # pure-Python Hawaiian text checks
├── configs/
│   ├── smoke.json             # tiny config for an end-to-end smoke run
│   └── llama31_8b_a100.json   # serious-prototype target config
└── examples/
    └── train.jsonl.example    # placeholder schema only — NOT real data
```

## Two configs, two purposes

The skeleton ships two configs to make the learn-vs-prototype split
explicit:

- **`configs/smoke.json`** — *learning / debug.* Defaults to
  Qwen2.5-0.5B, QLoRA off, fp32, max_seq_len 256, one tiny example
  file. Designed to fit on a laptop or a free-tier GPU and to surface
  pipeline bugs fast. **Numbers from this config are not eval results.**
- **`configs/llama31_8b_a100.json`** — *serious-prototype target.*
  Defaults to `meta-llama/Llama-3.1-8B` (HF-gated), QLoRA on, bf16 on,
  longer sequence length, gradient accumulation tuned for a single
  A100. The target hardware is recorded as `hardware_profile:
  "a100-40gb-single"` — a config-level hint, not a code assertion.
  Requires HF model access and a real Hawaiian data manifest before
  it should ever be run.

The Python code itself is *config-driven*: `Llama-3.1-8B` and
`A100` appear only in JSON and docs. The dataclass defaults in
`config.py` stay on the smoke tier so an unconfigured run can't
accidentally pull an 8B base.

## Suggested implementation order

Work top-to-bottom; each step builds on the last. Each Python module also has
a short implementation checklist at the top, so you can open a file and work
without bouncing back here.

1. **`metrics.py`** — easiest. Pure Python, no ML deps. Implement the
   ʻokina / kahakō / NFC checks first to build intuition for what we
   actually care about in Hawaiian text.
2. **`config.py`** — fill in additional fields as you discover you need
   them. Keep it a plain dataclass; don't reach for hydra/pydantic yet.
3. **`data.py`** — write the JSONL loader, then the tokenization hook,
   then think about packing/masking. Look at what `transformers`'
   `DataCollatorForLanguageModeling` gives you before writing your own.
4. **`model.py`** — load a small base model (Qwen2.5-0.5B is the
   project's smoke-tier choice), then add LoRA via `peft`, then add
   4-bit QLoRA via `bitsandbytes`. One layer at a time.
5. **`train.py`** — start with `trl.SFTTrainer` or
   `transformers.Trainer`; only roll your own loop once you've felt the
   pain of doing it the easy way. When you bring up a real GPU, call
   `model.check_runtime_capability(...)` and read the dict — it tells
   you whether CUDA is up, what compute capability you have, and
   whether bf16 will work. It deliberately does **not** assert on a
   specific GPU SKU; A100 targeting lives in config, not code.
6. **`evaluate.py`** — held-out PPL is the first thing to wire up; add
   generation samples + the `metrics.py` checks once PPL reports.

## Install notes

The skeleton itself imports nothing heavy at module load time, so

```
python3 -m py_compile code/llm_hawaii/*.py
```

works on a fresh machine. On a GPU/compute machine, use the training setup
script so the heavy ML stack stays separate from the data-collection venv:

```
python3 scripts/setup_training.py
```

If the provider needs a specific PyTorch CUDA wheel index, pass it explicitly:

```
python3 scripts/setup_training.py --torch-index-url https://download.pytorch.org/whl/cu121
```

These dependencies are deliberately **not pinned in the root `requirements.txt`**.
Root `requirements.txt` is for the data-collection pipeline; ML deps live in
`requirements-compute.txt` until they're hardened.

If a heavy dep is missing when you try to run, the module will raise a
clear `RuntimeError` with the install line — no silent fallbacks.

## Stage 0 eval runner

After compute dependencies are installed and Hugging Face access is configured,
run the current base-model baseline wrapper:

```
./scripts/run_stage0_eval.sh
```

It defaults to `meta-llama/Llama-3.1-8B` and
`data/evals/fineweb2_haw/dev.jsonl`. The full JSON report is written under
ignored `data/eval_runs/stage0/`, while a small hash-only summary is written
under tracked `docs/eval-runs/stage0/` for GitHub. The wrapper accepts
`CHECKPOINT=...`, `EVAL_FILE=...`, `PROMPT=...`, `OUTPUT_DIR=...`, and
`SUMMARY_DIR=...` overrides.

## What this skeleton intentionally does NOT do

- Ship real Hawaiian training data. None checked in. The
  `examples/*.jsonl.example` is a schema sketch, not a corpus.
- Hide the training loop behind layers of abstraction. You should be
  able to read every file in one sitting.
- Make framework decisions for you long-term. PyTorch + Hugging Face is
  the **learning path**. Final production choices stay open and need
  their own ADR before anything ships.
- Run anywhere except as a learning aid. Don't promote outputs of this
  code to "results" without a proper run report (see
  `docs/eval_pipeline.md`).

## Where the design docs live

- `../docs/training-pipeline.md` — stage gates, recipes, lineage.
- `../docs/eval_pipeline.md` — metrics, slicing, run report schema.
- `../.squad/decisions.md` — ADRs (two-stage training, base-model
  recommendation, prototype-vs-release split).

Read those alongside the code. The skeleton is a starting point for
*implementing* the design — it is not the design itself.
