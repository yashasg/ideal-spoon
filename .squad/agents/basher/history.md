# Basher — History

## Core Context

Condensed older entries; newest detailed entries remain below.

- **2026-05-01 — Kaggle venv robustness + docs idempotency:** Diagnose `[Errno 2] No such file or directory: 'ideal-spoon'` and `No module named pip`...
- **2026-05-01 — Maximize T4x2: bump max_seq_len + halve accumulation steps:** "we should being conservative then, we should try to maximize the x2"

---

## 2026-05-03 — Stage-1 A100 Loss Plateau Diagnosis (decision formalized)

**Summary:** Stage-1 A100 telemetry near epoch 1 (`loss ~= 1.17-1.23`, `grad_norm ~= 0.35`, `learning_rate = 5e-05`) is not a proven plateau. This is expected local movement with the configured `constant_with_warmup` scheduler at 5e-5 after warmup completes. Grad norms 0.35 < max_grad_norm 1.0, so clipping is not suppressing updates. However, config is more conservative than documented Stage-1 recipe (r64/α128, LR 2e-4 cosine, warmup 3%, ~64k-128k eff tokens/update vs current r32/α64, LR 5e-5, ~32k). **Recommendation:** Let current run finish 2 epochs, do not switch to Stage 2, do not change LR mid-run. Evaluate Stage-1 gates, then decide whether to rerun with documented recipe. Decision documented in `.squad/decisions.md`.

---

## Learnings

- **Stage-1 A100 loss telemetry diagnosis:** Llama-3.1-8B Stage-1 config is CPT/DAPT (`stage=stage1-cpt`) with full-token CLM loss, not SFT target masking. Current A100 config uses LR 5e-5 with `constant_with_warmup`, warmup 1%, LoRA r32/α64, bf16, batch 1 × grad_accum 16 × seq 2048, and 2 epochs; late-epoch train loss around 1.2 with grad_norm ~0.35 is not clipping-bound and is expected to flatten locally, but the config is more conservative than the documented Stage-1 recipe (2e-4 cosine, warmup 3%, LoRA r64/α128, ~64k-128k effective tokens/update).
- **Shared-provider pip check:** Kaggle and other managed notebook environments pre-install packages that may already conflict before any project deps are added. `pip check` on `--no-venv` paths should default to non-fatal; expose `--strict-pip-check` / `STRICT_PIP_CHECK` to opt-in to hard failure.
- **CLM collator + pre-tokenized labels:** `DataCollatorForLanguageModeling` calls `tokenizer.pad()` on all feature keys (including `labels`) before creating its own padded labels. If `labels` are variable-length lists (from `tokenize_example`), batch size > 1 raises `ValueError: expected sequence of length X at dim 1 (got Y)`. Fix: wrap the collator to strip `labels` before calling the inner HF collator; it then derives correct labels (-100 at pads) from the padded `input_ids`. Batch size 1 hides this because no padding/tensorization is attempted across sequences.
- **Strictness default pattern:** `pip_check_strict = args.strict_pip_check or (not args.no_venv)` — this naturally makes venv installs strict and shared-env installs lenient without requiring two separate flags.
- **Key files:** `scripts/setup_training.py`, `docs/kaggle-t4x2-setup.md`, `requirements-compute.txt`, `requirements.txt`.
- **CPU torch trap:** Running `setup_training.py` without `--skip-torch` on Kaggle installs the default PyPI CPU wheel (`+cpu`) on top of Kaggle's CUDA torch. The `+cpu` suffix in `torch.__version__` is the definitive signal. Fix: `pip uninstall torch -y && pip install torch --index-url https://download.pytorch.org/whl/cu121`. Always use `--skip-torch` on Kaggle.
- **GPU-attached vs wrong-wheel:** `nvidia-smi` present + returning rows = GPU attached; `torch.cuda.is_available() == False` with `+cpu` wheel = wheel problem, not hardware. `nvidia-smi` absent = accelerator not attached — fix in notebook settings.
- **Bash heredoc in Kaggle cells:** `<<TERM` heredocs passed as a one-shot string to bash (e.g. via `%%bash` magic) emit EOF-before-terminator warnings if the terminator has trailing whitespace or the cell is `cat`'d into bash. Use `%%python` cells or plain `!` lines instead.
- **Fake inner collator pattern:** When testing a collator wrapper end-to-end (output correctness, not just call interception), replace the inner collator with a minimal fake that *implements* the real pad+label semantics (pad input_ids to max length, set -100 at pad positions in labels). A plain `MagicMock` returning hardcoded values only verifies the wrapper calls through; the semantic fake verifies the wrapper correctly strips pre-tokenized labels so the inner can produce valid output. See `test_collator_end_to_end_variable_length_padding` in `code/tests/test_data.py`.
- **HF Trainer eval default batch=8 OOMs large-vocab models:** `per_device_eval_batch_size` defaults to 8 in Trainer. Llama-3.1-8B (vocab=128,256) with seq=2048 fp16 produces `8×2048×128256×2 ≈ 4.2 GiB` logits per eval step — enough to OOM a T4 with training state resident. Always set `per_device_eval_batch_size=1` and `eval_accumulation_steps=1` on memory-constrained hardware. These are now `TrainConfig` fields wired through `build_training_args()`.
- **Trainer fires eval before save at same step:** When `eval_steps == save_steps`, HF Trainer's `_maybe_log_save_evaluate` evaluates before saving. An OOM during eval means no checkpoint is written. Fix: set `eval_steps > save_steps` (e.g., `eval_steps=500, save_steps=100`) so multiple checkpoints exist before the first eval fires.

---

## 2026-05-01 — Kaggle pip check non-fatal fix

**User Directive:** `setup_training.py --no-venv --skip-torch` fails at `pip check` due to pre-existing conflicts in Kaggle's shared base image.

**Deliverables:**
- `scripts/setup_training.py` — extracted inline `pip check` call into `pip_check(python, *, strict, dry_run)` helper; added `--strict-pip-check` CLI flag + `STRICT_PIP_CHECK` env var; default strict = `not args.no_venv` (i.e. strict for venv, non-fatal for `--no-venv`); non-strict path prints provider-image warning with `--strict-pip-check` hint.
- `docs/kaggle-t4x2-setup.md` — added troubleshooting note in section 4 explaining that `pip check` warnings on `--no-venv` are non-fatal, may be from provider image, and how to force strict mode.
- `.squad/decisions/inbox/basher-pip-check-nonfatal.md` — decision drop.

**Key Design Decisions:**
- `pip_check_strict = args.strict_pip_check or (not args.no_venv)` — no new negating flag needed; venv is always strict unless explicitly overridden; shared-env is always lenient unless explicitly escalated.
- Prior fixes preserved: `venv_is_healthy()`, `ensure_venv()` auto-recreate, absolute Kaggle `cd` paths.
- W1 micro-eval guidance not added (standing directive honoured).

**Validation:**
- ✅ `python3 -m py_compile scripts/setup_training.py`
- ✅ `--dry-run` venv path: pip check printed correctly
- ✅ `--no-venv --skip-torch --dry-run`: pip check printed correctly
- ✅ Direct unit test of `pip_check()`: strict mode raises SystemExit; non-strict prints warning

**Status:** Implemented.

---
