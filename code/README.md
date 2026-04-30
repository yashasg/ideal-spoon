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
│   ├── smoke.json                              # tiny smoke/preflight config
│   ├── stage1_fineweb2_haw.json               # general Stage 1 prototype config
│   ├── stage1_fineweb2_haw_kaggle_t4x2.json   # Kaggle T4x2 prototype config
│   └── llama31_8b_a100.json                   # A100 serious-prototype config
└── examples/
    └── train.jsonl.example    # placeholder schema only — NOT real data
```

## Configs and purposes

The skeleton ships separate configs so hardware choices stay explicit:

- **`configs/smoke.json`** — *learning / debug.* Defaults to
  Qwen2.5-0.5B, QLoRA off, fp32, max_seq_len 256, one tiny example
  file. Designed to fit on a laptop or a free-tier GPU and to surface
  pipeline bugs fast. **Numbers from this config are not eval results.**
- **`configs/stage1_fineweb2_haw.json`** — *general Stage 1 prototype.*
  Defaults to `meta-llama/Llama-3.1-8B`, QLoRA on, the local
  FineWeb-2 Hawaiian train/dev paths, and the default Stage 1 checkpoint
  cadence.
- **`configs/stage1_fineweb2_haw_kaggle_t4x2.json`** — *Kaggle T4x2
  prototype iteration.* Uses the same Stage 1 data paths and model as the
  general config, but switches to `fp16`, disables `bf16`, targets
  `max_seq_len=2048`, and checkpoints/evals more often for interruptible
  free-tier sessions. Treat its numbers as prototype-debug signals, not
  promotion/gate numbers. If Kaggle OOMs, fall back to `max_seq_len=1024`
  with `gradient_accumulation_steps=32`. **Note:** the standard launch
  command uses a single process with `device_map="auto"` (big-model
  sharding), not DDP. The second T4 helps fit the model but does not add
  data-parallel throughput. True DDP requires a separate experiment.
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

## Stage 1 training — next run

> ⚠️ **Prototype / learning code.** Raw training data stays off-git (under
> `data/`, which is gitignored). Do not stage or commit data files.

### Step 1 — Preflight (no GPU spend, no model download)

Run from the **repo root** (paths are config-relative, not CWD-relative):

```bash
cd /path/to/ideal-spoon        # repo root
PYTHONPATH=code python3 -m llm_hawaii.train --config code/configs/stage1_fineweb2_haw.json --preflight
```

Expected output: a JSON report with `"issues": []`. If issues appear, fix
them before touching the GPU.

### Step 2 — Print resolved config (sanity-check)

```bash
PYTHONPATH=code python3 -m llm_hawaii.train --config code/configs/stage1_fineweb2_haw.json --print-config
```

Confirm `train_path` / `eval_path` are absolute paths that point to the local
`data/` tree, not to `code/` or the working directory.

### Step 3 — Train

Requires HF model access (`huggingface-cli login`) and a GPU. Run from the
**repo root**:

```bash
PYTHONPATH=code python3 -m llm_hawaii.train --config code/configs/stage1_fineweb2_haw.json
```

Checkpoints are saved under `runs/llama31-8b-stage1-fw2/`. A
`run_report.json` (no raw text; hashes + config + git SHA + timing) is
written there automatically after training completes.

### Kaggle T4x2 prototype run

Kaggle notebooks need **Internet enabled** before `git clone`, `pip install`,
or Hugging Face downloads will work. From a fresh notebook shell:

```bash
cd /kaggle/working
git clone --depth 1 https://github.com/yashasg/ideal-spoon.git
cd ideal-spoon
```

If `git clone` still fails but `curl` works, download the GitHub zipball
instead:

```bash
cd /kaggle/working
curl -L https://github.com/yashasg/ideal-spoon/archive/refs/heads/main.zip -o ideal-spoon-main.zip
python3 -m zipfile -e ideal-spoon-main.zip .
mv ideal-spoon-main ideal-spoon
cd ideal-spoon
```

If the repo is private, do not paste a token into a notebook cell. Store it in
Kaggle Secrets and use that environment secret for GitHub/Hugging Face auth.

The repo clone does **not** include `data/` because it is gitignored. Add the
data as a Kaggle Dataset or copy it into:

```bash
/kaggle/working/ideal-spoon/data/
```

Then install compute deps into Kaggle's current Python environment and run the
T4 profile:

```bash
python3 scripts/setup_training.py --no-venv --skip-torch
huggingface-cli login
PYTHONPATH=code python3 -m llm_hawaii.train --config code/configs/stage1_fineweb2_haw_kaggle_t4x2.json --preflight
PYTHONPATH=code python3 -m llm_hawaii.train --config code/configs/stage1_fineweb2_haw_kaggle_t4x2.json
```

Outputs land under `runs/llama31-8b-stage1-fw2-kaggle-t4x2/` relative to the
directory where you launch the command. Sync that directory to persistent
storage before the Kaggle session ends.

### Resume after interruption

```bash
PYTHONPATH=code python3 -m llm_hawaii.train \
    --config code/configs/stage1_fineweb2_haw.json \
    --resume-from-checkpoint runs/llama31-8b-stage1-fw2/checkpoint-200
```

### Eval immediately after training

```bash
PYTHONPATH=code python3 -m llm_hawaii.train \
    --config code/configs/stage1_fineweb2_haw.json \
    --eval-after-train
```

### Data paths contract

All paths in `.json` configs are **config-relative** (resolved against the
config file's directory, not `$PWD`). The smoke config uses
`../examples/train.jsonl.example`; the Stage 1 configs use
`../../data/stage1/...`. This means the same `--config` flag works
regardless of whether you run from `repo_root/` or `code/`.

Output dirs (e.g., `runs/`) are resolved relative to `$PWD` as written in
the config — keep them as relative paths so they land where you expect.

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
`CHECKPOINT=...`, `EVAL_FILE=...`, `PROMPT=...`, `USE_SUITE=...`,
`MANUAL_W1_JSONL=...`, `USE_MANUAL_W1=...`, `HUMAN_FETCH_JSONL=...`,
`USE_HUMAN_FETCH=...`, `OUTPUT_DIR=...`, and `SUMMARY_DIR=...` overrides.

### Stage 0 drift signal bundle (schema `stage0_eval.v2`)

Both the full report and the tracked hash-only summary capture a richer
bundle than just `hawaiian_ppl`, so future checkpoints can be compared
fairly without leaking raw text into git:

- **Run identity** (`identity`, `decoding`, `ppl_config`): checkpoint,
  base model, peft-adapter flag, model class, model dtype, model device,
  device map, quantization config, tokenizer name/class/vocab size, torch
  + transformers versions, decoding flags (`do_sample`, `max_new_tokens`,
  `greedy=True`), and PPL `max_length`. Plus `eval_file_sha256` and
  `source_git_commit` from the wrapper. Two checkpoints can only be
  compared honestly if these match.
- **Eval set slice metadata** (`eval_set`): record count, scored record
  count, total tokens / chars, length-bin counts (`short`/`medium`/`long`
  by token count), `diacritic_density_bin_counts`, and per-`source` /
  per-`register` counts when those fields are present on JSONL records.
  Raw record text is never written.
- **Hawaiian held-out PPL** (`metrics.hawaiian_ppl`): unchanged, stays
  the headline trend signal.
- **Fixed prompt suite** (`prompt_suite`): `suite_id = stage0.v1`,
  `suite_sha256`, and per-item `prompt_sha256` + `diacritic_density_bin`
  for a 7-prompt set spanning low/medium/high Hawaiian diacritic density
  plus an English control. Generations themselves go to the full report;
  the summary keeps only `generation_sha256` per sample.
- **Per-sample orthography** (`metrics.orthography_metrics`) +
  **aggregate** (`metrics.orthography_aggregate`): per-generation NFC,
  ʻokina, wrong-okina, kahakō, combining-macron counts; plus aggregated
  totals across the suite and `kahako_collapse_on_high_diacritic` count.
- **Tripwires** (`tripwires`): `wrong_okina_nonzero`, `nfc_failures`,
  `combining_macron_nonzero`, `kahako_collapse_on_high_diacritic`,
  `generation_count`, `prompt_suite_sha256`, `prompt_suite_id`. Any
  non-zero/true tripwire on a Stage 1 checkpoint is a regression flag.
- **Probes not yet wired**: `metrics.english_ppl` and
  `metrics.hawaiian_ppl_by_source` are emitted with
  `status: "not_configured"` and a reason string instead of being
  silently absent. The Stage 1 gate's English-forgetting check
  (`docs/training-pipeline.md` §2.4) reads this field — when it lands,
  flip the status. Do not pretend they ran.
- **W1 manual micro-eval status** (`metrics.manual_w1`): metadata-only
  probe driven by the local off-git **JSONL** at
  `data/evals/manual_w1/w1-haw-micro-eval.jsonl` (override with
  `--manual-w1-jsonl` / `MANUAL_W1_JSONL=...`; disable with
  `--no-manual-w1` / `USE_MANUAL_W1=0`). Stage 0 W1 input is
  JSONL-only per the user directive
  (`.squad/decisions/inbox/copilot-directive-20260430T081137Z.md`);
  the TSV remains the local authoring/source format consumed by
  `scripts/315_hash_manual_w1_eval.py`, which emits the JSONL eval
  artifact via `python3 scripts/315_hash_manual_w1_eval.py --execute --jsonl-only`.
  Stable status enum: `not_configured` (probe disabled), `missing`
  (JSONL absent), `invalid` (malformed JSONL or **accepted-row
  orthographic failure**: `nfc_normalized != true`, non-NFC
  prompt/reference/text, wrong-ʻokina codepoint, or U+0304 combining
  macron on any `review_status=accepted` row), `draft_only` (no
  `review_status=accepted` rows — drafts are **never** reportable as
  eval results), `evaluated` (accepted rows present and validated).
  Emits `jsonl_sha256`, `jsonl_size_bytes`, `row_count`,
  `review_status_counts`, `accepted_count` (=
  `eval_consumable_count`), `accepted_category_counts`,
  `accepted_diacritic_density_bin_counts`, and
  `nfc_normalized_false_count`. On the `evaluated` path also emits
  `accepted_item_hashes` (sorted; uses each row's
  `sha256_normalized` when present, else canonical
  `sha256(NFC(prompt) + LF + NFC(reference))` matching
  `scripts/315_hash_manual_w1_eval.py:compute_hash`),
  `w1_suite_sha256` (sha256 over sorted
  `(item_id, sha256_normalized)` pairs of accepted rows; stable
  under row reorder; flips when the *accepted* set churns even if
  the file SHA is unchanged), and `schema_version_seen =
  "manual-w1-jsonl-v1"`. On the `invalid` accepted-row-orthographic
  branch the report carries `error_count` plus `first_errors`
  containing only `line N: <field> <category>` text — never row
  contents. Raw prompts/references/notes/author text never enter
  the report. `scoring_status: "not_wired"` is always set: this
  probe validates W1 metadata, **not** task accuracy. Once
  row-level model-scoring lands, flip `scoring_status` and add the
  per-row pass/fail summary alongside.
- **human_fetch bidirectional translation probe**
  (`metrics.human_fetch_translation`): **prototype/learning checkpoint
  eval probe** present on *every* checkpoint eval, including the Stage 0
  no-training baseline. Reads the local off-git JSONL at
  `data/tokenizer_audit/ulukau_nupepa/human_fetch.jsonl` (the single
  English + Hawaiian parallel pair from the Ulukau institutional landing
  page); override with `--human-fetch-jsonl` / `HUMAN_FETCH_JSONL=...`;
  disable with `--no-human-fetch` / `USE_HUMAN_FETCH=0`. Regenerate
  the JSONL with `python3 scripts/_convert_ulukau_human_fetch.py`.
  Status enum: `not_configured` (disabled), `missing` (JSONL absent —
  safe to miss, never blocks the eval), `invalid` (parse/lang-pair
  error), `ready` (pair parsed, no model provided), `evaluated`
  (greedy generation run for both en→haw and haw→en). On `evaluated`,
  both direction dicts carry `prompt_sha256`, `generation_sha256`,
  `reference_sha256`, and a **baseline char-bigram F1 score**
  (`metric = "char_ngram_f1_baseline"`, `ngram_order = 2`) with
  `char_f1`, `char_precision`, `char_recall`. Directions are **always
  kept separate** — en→haw and haw→en are never averaged into one
  number. The probe is `eval_eligible = True`,
  `training_eligible = False`. Raw source, reference, and generation
  text never enter the report; only hashes and numeric metrics. Purpose:
  gauge zero-training (Stage 0) translation baseline and track drift
  across checkpoints so asymmetric direction collapse is visible early.
- **Stage 0 CLI exit code.** `python -m llm_hawaii.evaluate` writes
  the report JSON first, then exits **2** when `manual_w1.status ==
  "invalid"` (orthographic contract violation on accepted rows or a
  malformed W1 JSONL). All other states exit 0.
  `scripts/run_stage0_eval.sh` still writes the tracked summary
  projection in this case (so the failing artifact is inspectable),
  then propagates the non-zero exit so a bad W1 input cannot land as
  a green Stage 0 run.
- **W1 expert-validated source directive.** The trusted source for
  W1 expert-validated Hawaiian rows is the raw file at
  `data/raw/ulukau_nupepa/human_fetch.txt` (sectioned `# English` /
  `# Hawaiian`; use the Hawaiian section only). The converter
  `scripts/_convert_ulukau_human_fetch.py` informs
  parsing/normalization but is **not** the source of truth itself.
  Populated W1 TSVs derived from this source remain off-git under
  the `data/` ignore rule per
  `data-sources/manual-eval/README.md`.

The fixed prompt suite is frozen by `PROMPT_SUITE_ID` /
`prompt_suite_sha256`. Editing prompts in place breaks
checkpoint-to-checkpoint comparability — append new prompts and bump the
suite id instead.

**Suite-design freeze invariant.** Any new `haw_high_*` (or otherwise
high-diacritic-bin) prompt added to the suite must *explicitly* ask the
model to use kahakō (and ʻokina) in its output. The
`kahako_collapse_on_high_diacritic` tripwire fires when a high-bin
prompt produces a generation with zero kahakō; if the prompt itself
doesn't request kahakō, a zero-kahakō completion is no longer a
regression signal and the tripwire silently loses meaning. Same rule
applies if the bin thresholds in `metrics.diacritic_density_bin` are
ever retuned: re-audit every high-bin prompt for an explicit kahakō
ask before shipping the change.

### Pulling Stage 0 results back from the compute box

After running `run_stage0_eval.sh` on a remote GPU machine, mirror the
artifacts into the local repo over SSH/SCP:

```
./scripts/download_stage0_eval.sh user@gpu-box ~/ideal-spoon
```

The first arg is the SSH destination, the second (optional) is the remote
repo root (defaults to `~/ideal-spoon`). It pulls full reports into
`data/eval_runs/stage0/` (gitignored) and the hash-only summaries into
`docs/eval-runs/stage0/` (tracked). Existing local files are skipped unless
`OVERWRITE=1`. Useful overrides: `SSH_PORT=...`, `SSH_OPTS="-i ~/.ssh/key"`,
`ONLY=full|summary|both`, `DRY_RUN=1`. The script is read-only on the
remote.

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
