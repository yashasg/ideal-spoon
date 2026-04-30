# Basher — History

## Learnings

- **Shared-provider pip check:** Kaggle and other managed notebook environments pre-install packages that may already conflict before any project deps are added. `pip check` on `--no-venv` paths should default to non-fatal; expose `--strict-pip-check` / `STRICT_PIP_CHECK` to opt-in to hard failure.
- **CLM collator + pre-tokenized labels:** `DataCollatorForLanguageModeling` calls `tokenizer.pad()` on all feature keys (including `labels`) before creating its own padded labels. If `labels` are variable-length lists (from `tokenize_example`), batch size > 1 raises `ValueError: expected sequence of length X at dim 1 (got Y)`. Fix: wrap the collator to strip `labels` before calling the inner HF collator; it then derives correct labels (-100 at pads) from the padded `input_ids`. Batch size 1 hides this because no padding/tensorization is attempted across sequences.
- **Strictness default pattern:** `pip_check_strict = args.strict_pip_check or (not args.no_venv)` — this naturally makes venv installs strict and shared-env installs lenient without requiring two separate flags.
- **Key files:** `scripts/setup_training.py`, `docs/kaggle-t4x2-setup.md`, `requirements-compute.txt`, `requirements.txt`.
- **CPU torch trap:** Running `setup_training.py` without `--skip-torch` on Kaggle installs the default PyPI CPU wheel (`+cpu`) on top of Kaggle's CUDA torch. The `+cpu` suffix in `torch.__version__` is the definitive signal. Fix: `pip uninstall torch -y && pip install torch --index-url https://download.pytorch.org/whl/cu121`. Always use `--skip-torch` on Kaggle.
- **GPU-attached vs wrong-wheel:** `nvidia-smi` present + returning rows = GPU attached; `torch.cuda.is_available() == False` with `+cpu` wheel = wheel problem, not hardware. `nvidia-smi` absent = accelerator not attached — fix in notebook settings.
- **Bash heredoc in Kaggle cells:** `<<TERM` heredocs passed as a one-shot string to bash (e.g. via `%%bash` magic) emit EOF-before-terminator warnings if the terminator has trailing whitespace or the cell is `cat`'d into bash. Use `%%python` cells or plain `!` lines instead.
- **Fake inner collator pattern:** When testing a collator wrapper end-to-end (output correctness, not just call interception), replace the inner collator with a minimal fake that *implements* the real pad+label semantics (pad input_ids to max length, set -100 at pad positions in labels). A plain `MagicMock` returning hardcoded values only verifies the wrapper calls through; the semantic fake verifies the wrapper correctly strips pre-tokenized labels so the inner can produce valid output. See `test_collator_end_to_end_variable_length_padding` in `code/tests/test_data.py`.

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

## 2026-05-01 — Kaggle venv robustness + docs idempotency

**User Directive:** Diagnose `[Errno 2] No such file or directory: 'ideal-spoon'` and `No module named pip` failures on Kaggle.

**Deliverables:**
- `scripts/setup_training.py` — added `venv_is_healthy()` (probes `python -m pip --version` inside the venv); updated `ensure_venv()` to auto-delete and recreate a broken venv instead of failing mid-run.
- `docs/kaggle-t4x2-setup.md` — changed `cd ideal-spoon` → `cd /kaggle/working/ideal-spoon` (both git and curl paths); bolded `--no-venv --skip-torch` in section 4; added explanatory note about the default venv path and the new auto-recovery behaviour.
- `.squad/decisions/inbox/basher-kaggle-venv-robustness.md` — team-relevant decision drop.

**Key Design Decisions:**
- `venv_is_healthy()` uses `capture_output=True` so health-probe stderr does not pollute normal script output.
- Dry-run mode skips the health probe (no side effects in dry-run).
- No W1 / Hawaiian micro-eval data touched or added to Kaggle guidance (standing directive honoured).

**Validation:**
- `python3 -m py_compile scripts/setup_training.py` ✅
- `python3 scripts/setup_training.py --dry-run` ✅

**Status:** Implemented.

---

## 2026-05-01 — Maximize T4x2: bump max_seq_len + halve accumulation steps

**User Directive:** "we should being conservative then, we should try to maximize the x2"

**Deliverables:**
- `code/configs/stage1_fineweb2_haw_kaggle_t4x2.json` — `max_seq_len` 1024→**2048**, `gradient_accumulation_steps` 32→**16**; notes updated to drop "conservative" language, explain memory rationale, and document explicit OOM fallback.
- `.squad/decisions/inbox/basher-maximize-t4x2.md` — decision drop with token-budget math and fallback ladder.

**Key Design Decisions:**
- Prior config was written for single 16GB T4 defensively. With `device_map="auto"` addressing ~32GB across both T4s, the memory budget supports seq_len=2048.
- Halving gradient_accumulation_steps preserves the same ~32K tokens/gradient-update (1024×32 = 2048×16), so gradient signal density is unchanged — we just train with richer context and fewer accumulation micro-steps per optimizer step.
- No code changes required. `device_map="auto"` already handles placement; no `max_memory` config field needed.

**Validation:**
- ✅ JSON parse clean
- ✅ `load_config()` asserts: max_seq_len=2048, gradient_accumulation_steps=16, fp16=True, bf16=False

**Status:** Implemented. Ready for Kaggle T4x2 run.

---

## 2026-04-30 — QLoRA bitsandbytes compute dtype fix

**User Directive:** Fix QLoRA bitsandbytes compute dtype wiring to follow TrainConfig bf16/fp16 flags.

**Deliverables:**
- `code/llm_hawaii/model.py` — Extracted `_bnb_compute_dtype_name(bf16, fp16) -> str` (pure Python); refactored `_bnb_4bit_config(bf16, fp16)` to derive dtype dynamically; updated `load_base_model()` and `build_model_and_tokenizer()` to wire through TrainConfig flags.
- `code/tests/test_model.py` — 4 new unit tests for `_bnb_compute_dtype_name` (no torch dependency).
- `code/configs/stage1_fineweb2_haw_kaggle_t4x2.json` — added `device_placement` note clarifying `device_map="auto"` is single-process model sharding, not DDP.
- `code/README.md` — added inline note on Kaggle T4x2 config.
- `docs/training-pipeline.md` — added callout box explaining DDP/device_map distinction.

**Key Design Decisions:**
- **Pure-Python dtype naming:** `_bnb_compute_dtype_name()` takes bool flags, returns string ("float16", "bfloat16", "float32"), then `getattr(torch, name)`. Testable without torch.
- **Compute dtype derivation:** `fp16=true, bf16=false` → torch.float16 (Kaggle T4x2); `bf16=true` → torch.bfloat16; neither set → torch.float32.
- **Kaggle T4x2 correctness:** Config now uses correct dtype for Turing/T4 GPUs (no bfloat16 support on T4).

**Validation:**
- ✅ JSON parse: `code/configs/stage1_fineweb2_haw_kaggle_t4x2.json` valid
- ✅ `--print-config` produces correct output
- ✅ `py_compile` on changed Python files passes
- ✅ `test_train` 16/16 pass
- ✅ `test_data` 14/14 pass
- ✅ 4 new dtype helper unit tests pass
- ✅ `git diff --check` passes

**Status:** Implemented. Merged into `.squad/decisions.md`.

---

## 2026-05-01 — Training runner readiness for Stage 1 CPT run

**User Directive:** Make the training runner ready for the next Stage 1 CPT/QLoRA run on compute.

**Deliverables:**
- `code/llm_hawaii/train.py` — full implementation: `--preflight`, `--resume-from-checkpoint`, `--eval-after-train` CLI flags; `run_preflight()` (no model download); `write_run_report()` (schema `training-run-report.v1`, no raw text); resume wired via `Trainer.train(resume_from_checkpoint=...)`; eval-after-train path; runtime capability snapshot.
- `code/llm_hawaii/config.py` — added `resolve_data_paths()` and updated `load_config()` to resolve all relative paths against the config file's directory (not CWD). Deterministic, documented, tested.
- `code/configs/stage1_fineweb2_haw.json` — new dedicated config for the local FineWeb-2 haw_Latn slice (95507 train / 621 eval, off-git). Paths config-relative. Output dir `runs/llama31-8b-stage1-fw2/`.
- `code/configs/llama31_8b_a100.json` — updated paths to config-relative (`../../data/stage1/fineweb2_haw/train.jsonl`); updated notes.
- `code/configs/smoke.json` — updated train_path to config-relative (`../examples/train.jsonl.example`).
- `code/tests/test_train.py` — 16 new tests covering config path resolution, preflight, run report schema, CLI flag wiring; all pure-Python (no ML deps).
- `code/README.md` — added "Stage 1 training — next run" section with exact commands, data path contract, and prototype/off-git reminder.
- `.squad/decisions/inbox/basher-training-runner-readiness.md` — durable contract for paths, CLI flags, run report schema, and next-run commands.

**Key Design Decisions:**
- **Config-relative paths:** `load_config()` always resolves relative paths against config file directory. CWD does not affect data resolution. Smoke test confirms `smoke.json` resolves to `code/examples/train.jsonl.example`.
- **Preflight contract:** `run_preflight()` is the mandatory first step before any GPU spend. Checks config + data + output dir + runtime capability (non-fatal for torch absence). Exits 1 on any issue.
- **Run report schema `training-run-report.v1`:** Every train run writes `{output_dir}/run_report.json` with hashes (no raw text), resolved config, git SHA, timing. Required for run reproducibility (docs/eval_pipeline.md §8).
- **Resume:** `--resume-from-checkpoint PATH` passed directly to `Trainer.train()`. Designed for free-GPU / short-session providers where interruption is likely.
- **No accidental 8B download:** Smoke config default (`Qwen2.5-0.5B`, `use_qlora=false`) unchanged. Heavy model only activated via `stage1_fineweb2_haw.json` or `llama31_8b_a100.json`.

**Validation:**
- `python3 -m py_compile code/llm_hawaii/train.py code/llm_hawaii/config.py` ✓
- `cd code && PYTHONPATH=. python3 -m unittest tests.test_train` — **16/16 green**
- All pre-existing ML-dep-free tests pass; 2 test_data.py tests requiring `transformers` remain pre-existing failures (not caused by this work)

**Status:** Implemented. Ready for Stage 1 CPT run on compute after preflight passes.

## Learnings

- Config-relative path resolution eliminates a whole class of "works from code/ but not repo root" bugs. Pattern: `resolve_data_paths(cfg, config_path)` called immediately after `from_json()`; callers get absolute paths, period.
- `run_preflight()` should be the first thing you run on a new compute box, before `huggingface-cli login` even — it tells you if the data files landed correctly.
- Run reports that contain no raw text (only hashes + counts + git SHA) are sufficient for reproducibility and can be committed safely if needed.



**User Directive:** Stage 0 evals should capture the full checkpoint drift-signal bundle so checkpoints can be compared across PPL, orthography, generation, dtype/config identity, and related regression tripwires.

**Deliverables:**
- `code/llm_hawaii/evaluate.py` — rewrote report shape (additive, retaining existing CLI); captures 7 drift signals: run identity, eval-set metadata, Hawaiian PPL (with per-source placeholder), fixed 7-item prompt suite (stage0.v1), per-sample + aggregate orthography, tripwires, and not-yet-wired probes (english_ppl, manual_w1, hawaiian_ppl_by_source with explicit "not_configured" status)
- `scripts/run_stage0_eval.sh` — wrapper now defaults to suite-on; summary projects the full bundle without raw text
- `code/tests/test_evaluate.py` — new file, 7 new tests (no ML deps); all 18 passing (+ existing 11 metrics tests)
- `docs/eval_pipeline.md` — added §8.1 pointer
- `code/README.md` — Stage 0 section documents drift bundle + prompt-suite-freeze rule
- Post-review cleanups applied: hawaiian_ppl parity shape, schema_version fallback flip to "unknown", suite-design freeze invariant documented

**Key Design Decisions:**
- Prompt suite freeze: `PROMPT_SUITE_ID = "stage0.v1"`, `suite_sha256 = 2683027f538ae8fb2910f758f2865596355893cc91c85dbdfe9ced130797bce6`. Editing in place invalidates all prior baselines; only way to change is to bump PROMPT_SUITE_ID.
- Summary carries no raw text (prompt/eval/generation text stays under ignored `data/`); hash-only projection with stable top-level keys means aggregator can do dense cross-checkpoint diffs.
- Placeholders for not-yet-wired probes (english_ppl, manual_w1, hawaiian_ppl_by_source) use uniform `{"status":"not_configured","reason":"..."}` so future wiring only flips status, not the schema.
- `kahako_collapse_on_high_diacritic` tripwire counts zero-kahakō generations when high-bin prompts explicitly request kahakō — reports as integer 0–N (signal, not gate).

**Reviews (both approved, no code changes required for this scope):**
- **Rusty:** Hawaiian phrasing of 7 prompts verified NFC, U+02BB ʻokina throughout, zero wrong-ʻokina seeds, density bins match labels. Tripwire approved conditional on suite-design invariant (high-density prompts must instruct kahakō use). Approved for `stage0.v1` freeze.
- **Linus:** Summary shape consumable by future cross-checkpoint aggregator. Confirmed hash-only projection, stable keys with `{"status":"absent"}` fallback, fair-comparison gating via `suite_sha256` + `eval_set.sha256` + `ppl_config`, all confounds captured in-band, not-yet-wired probes uniform. Approved for downstream aggregation.

**Validation:**
- `python3 -m py_compile code/llm_hawaii/evaluate.py code/tests/test_evaluate.py` ✓
- `sh -n scripts/run_stage0_eval.sh` ✓
- `PYTHONPATH=. python3 -m unittest tests.test_evaluate tests.test_metrics` — 18/18 passing

**Status:** Implemented, reviewed, approved. Not committed (awaiting coordination for batch commit).

**Cross-team context:**
- **Rusty:** Approved suite + tripwire + coverage checklist sections A–H as the contract for Stage 0 → Stage 1 aggregation. Flag: critical corrections outstanding (dtype hardcode at evaluate.py:162, per-source PPL slice TODO, English PPL not wired, single prompt not ≥5–10 spanning bins, n=1 orthography not distributional). These don't block v2 freeze; they block Stage 1 gate.
- **Linus:** Approved shape; noted cosmetic follow-ups (hawaiian_ppl parity when eval_file absent, schema_version fallback visibility) forwarded and applied. No re-review needed; changes are doc + shape parity.

## Core Context

- **Project:** A plan for training an open-source LLM focused on the Hawaiian language, including data, model choices, infrastructure, evaluation, and costs.
- **Role:** Training Engineer
- **Joined:** 2026-04-29T01:38:35.143Z

## 2026-04-29T10:46:19Z — Learning skeleton + Llama-3.1-8B A100 config finalized; decisions merged to main

**From:** Scribe (Orchestration + decision merging)

**Update:** Two Basher tasks completed and decisions merged to `.squad/decisions.md`:

**1. Learning skeleton (PyTorch + Hugging Face):**
- Delivered beginner-friendly skeleton under `code/llm_hawaii/` matching user directive for first-time trainer learning experience.
- Stack: PyTorch + Hugging Face (transformers, peft, bitsandbytes, trl, accelerate, datasets) chosen as lowest-friction QLoRA entry path.
- Config/data/model/train/evaluate/metrics modules + smoke.json + train.jsonl.example + learning README.
- All ML deps lazy-imported; python3 -m py_compile passes clean. No fabricated Hawaiian. Existing work untouched.
- **Decision now in main decisions.md** under "Decision: PyTorch + Hugging Face for the Learning Skeleton under `code/`".

**2. Llama-3.1-8B + A100 config (config, not constants):**
- Added `code/configs/llama31_8b_a100.json`: base_model, QLoRA on, bf16 on, seq 2048, grad_accum 16, hardware_profile metadata.
- Extended TrainConfig with optional run_name and hardware_profile (informational, non-enforcing).
- Added model.check_runtime_capability(...) — generic probe, no A100 assertion.
- Smoke tier (Qwen2.5-0.5B) default untouched.
- **Decision now in main decisions.md** under "Decision: Llama-3.1-8B + A100 as Config, Not Python Constants".

**3. User directives consolidated:**
- 2026-04-29T10-33-57Z: Learning skeleton preference (adopted)
- 2026-04-29T10-36-37Z: Llama-3.1-8B + A100 defaults (adopted)
- 2026-04-29T10-46-04Z: A100 40GB acceptable for QLoRA (adopted)
- All three now consolidated in `.squad/decisions.md` under "User Directives Consolidated".
- Decision inbox cleared; all files merged to main.

**Reference:**
- Orchestration logs: `.squad/orchestration-log/2026-04-29T10-46-19Z-basher-llm-skeleton.md` and `2026-04-29T10-46-19Z-basher-llama-a100-config.md`
- Session log: `.squad/log/2026-04-29T10-46-19Z-llm-learning-skeleton.md`
- Main decisions updated: `.squad/decisions.md` (3 new sections, inbox cleared)

**Next gates:**
- Framework-pinning ADR before cloud GPU spend
- Tokenizer audit on Llama-3.1-8B (Rusty gate)
- Data foundation (Linus gate) before training entry

## 2026-04-29T10:49:36Z — Vendor observation: Lightning AI L40S as practical training surface

**From:** Scribe (Cross-agent context)

**Update:** Lightning AI Free plan shows L40S with unlimited session time (vs 4-hr cap on A100/H100). User flagged as potential cost/availability win.

**Your assessment requested:**
- **Practical fit for Llama-3.1-8B QLoRA:** L40S 48GB has NVLink 400 GB/s (lower than A100), but tensor-core tuning may not matter much for single-GPU 4-bit work. Verify `bf16` + Flash Attention 2 vendor claims in practice.
- **Quantization stability:** bitsandbytes + CUDA kernel compatibility on L40S is known friction; flag if Vivitashkam/Faster-than-I8 ops drift. This is a real blocker — don't assume it "just works."
- **Throughput vs A100:** expect L40S to hit ~60–75% of A100's peak matrix throughput for this workload. If that's acceptable for iteration, it's worth exploring.
- **Keep A100 40GB as reference.** Don't swap the config default; add L40S as an optional profile if empirical testing confirms stability + reasonable throughput.

**Advisory intent:** L40S is a candidate surface for iteration if you confirm CUDA/bnb alignment; not a replacement for A100 reference. Livingston will verify credit burn and provider reliability.

**Reference:** `.squad/decisions.md` → "Vendor Observation: Lightning AI Free Plan (2026-04-29T10-49-36Z)"

### Stage 2 SFT JSONL emitter skeleton (#14)
- Added `scripts/330_emit_stage2_sft_jsonl.py`: stdlib-only JSONL→JSONL emitter; one canonical Stage-2 manifest pair → up to two directional rows (`en->haw`, `haw->en`) matching docs/data-pipeline.md §"Stage 2 output JSONL".
- Filters: `--splits`, `--directions`, `--min-alignment-score` (only gates non-null embedding scores; deterministic alignments admitted), opt-in `--allow-review-required` / `--allow-synthetic`. Default output `data/stage2/stage2_sft.jsonl` (gitignored).
- Robust to inline text (`text_en`/`text_haw`) or path refs (`text_en_path`/`text_haw_path`); sha-addressed text refs deferred (TODO).
- Out of scope by design: retention slice (Stage-1 builder owns it), contamination guard #4 (separate pass against `eval_hashes.parquet` before any training read).
- Smoke-tested on a 5-row fixture: 2 pairs kept → 4 rows emitted; review/score/missing-text rows skipped with counted reasons. `python3 -m py_compile` clean.
- Doc: added §4.3.1 in `docs/training-pipeline.md` describing the emitter contract.

### Stage 1 manifest + trainer JSONL build (#6) — 2026-04-29
- Extended `scripts/301_build_stage1_dataset.py` to consume the accepted FineWeb-2 Stage-1 train slice from `data/stage1/fineweb2_haw/train.jsonl` once, while keeping Wikimedia/Wikisource on `data/raw/<source>/fetch.jsonl` ledgers.
- Current local build emits ignored outputs: `data/stage1/stage1_manifest.jsonl` (99,390 rows), `data/stage1/stage1.jsonl.gz` (66,404 trainer rows), and `data/stage1/token_target_report.json` (49,189,650 train tokens; conservative/base/upside targets met). Manifest schema validation reports zero errors.
- Strict mode still fails honestly on undersized slices (checked with `--source hawwiki --limit 1 --strict`, exit 2). Full build still warns on FineWeb-2 source-share skew, so data-mix review remains needed before a real GPU run.

---

## 2026-04-29T12:40:50Z — Orchestration Log Capture

**From:** Scribe (Session logger)

**Summary:** Batch spawn for Stage 1 (#6) consolidated with Linus (#2/#3), Rusty (#8), and Stage2 Squad (#9–#14). Orchestration logs created; 3 inbox decisions merged into canonical decisions.md (Stage 1 JSONL manifest, eval-hash ledger, tokenizer audit gate). No regressions.

**Your related decisions now in canonical decisions.md:**
- Stage 1 local manifest + trainer JSONL convention: JSONL output at `data/stage1/stage1_manifest.jsonl` + `data/stage1/stage1.jsonl.gz` (stdlib, no pyarrow); Parquet promotion deferred.
- Parquet dependency decision is follow-up, not blocker.
- `code/configs/llama31_8b_a100.json` remains blocked pending Rusty's tokenizer audit `go` decision and frozen tokenizer/model SHA in manifest.

**Next steps:** Stage 1 build ready for training entry once eval ledger/tokenizer gate are satisfied.

## Learnings

### 2026-04-29 — Removed standalone tokenizer audit script (user request)

User decision: drop `scripts/040_tokenizer_audit.py`; a tokenizer-audit test will be added later. Stage-0 tokenizer-audit gate for Llama-3.1-8B remains an open #8 spend gate.

Changes:
- Deleted `scripts/040_tokenizer_audit.py`.
- Removed `TODO(audit-tokenizer)` blocks from `code/llm_hawaii/model.py` and `code/tests/test_model.py`.
- Reworded references in:
  - `docs/training-pipeline.md` §1.1
  - `docs/eval_pipeline.md` §3.1
  - `docs/data-pipeline.md` (Stage 1 next steps)
  - `docs/implementation_plan.md` §3
  - `docs/prototype-journey-compute-factcheck.md` (Tokenizer Audit section)
  - `docs/prototype-journey-deck.md` (Slide 9, status table, "How to Reference", scripts inventory)
  - `docs/prototype-journey-data-factcheck.md` (#8 row)
  - `data-sources/manual-eval/README.md`
  - `.squad/decisions.md` (Issue #8 entry — gate kept; script reference replaced with "planned tokenizer-audit test")

Preserved: thresholds, gate semantics, "do not fabricate" stance, #8 still blocking serious 7B/8B spend. Did not commit. Left `.squad/agents/rusty/history.md` and `.squad/orchestration-log/...rusty.md` untouched as historical records.

`py_compile` clean on the two edited Python files. Final grep confirms zero active references to `scripts/040_tokenizer_audit.py` or `TODO(audit-tokenizer)` in `*.py`/docs.

### 2026-04-30 — Proposed tokenizer-audit output contract (Stage-0 gate)

User asked what the tokenizer audit's output should look like (never discussed). Wrote `.squad/decisions/inbox/basher-tokenizer-audit-output-contract.md` defining the file layout and JSON schema for the planned `code/tests/test_tokenizer_audit.py`. Key shape:

- One run dir per audit: `data/tokenizer_audit/<run_id>/` with `report.json`, `report.md`, `samples.jsonl`, `inputs.manifest.json`. All ignored, local-only.
- `report.json` is the single source of truth read by the gate. Reuses field paths already named in docs/decisions: `model.tokenizer_sha256` (+ `tokenizer_fingerprint_sha256` alias), `overall.{tokens_per_word, explicit_byte_fallback_rate, byte_fallback_or_proxy_rate}`, `high_diacritic.*`, plus `checks[]` and `recommendation.{decision, reasons, blocks, next_actions}`.
- Decision rule: `go` iff every `checks[*].passed == true`; otherwise `no_go` with failing ids enumerated. Thresholds copied into the report (so old reports stay interpretable). No partial-credit.
- Hard-fail (missing `transformers`, gated Llama, no Hawaiian samples) writes a `no_go` report with `recommendation.reasons = ["environment.*"]` and null metrics — never fabricated numbers. Preserves Rusty's "do not fabricate" stance.
- Gate semantics unchanged: `go` is the only path to freeze tokenizer/model SHA into `code/configs/llama31_8b_a100.json` Stage-1 manifest. Audit slices stay `audit_only`; no eval-hash ledger writes from this path.

No code, no docs, no eval ledger changes touched. Flagged a follow-up doc edit (training-pipeline §1.1, eval_pipeline §3.1) for after the contract is adopted.

### 2026-04-30 — Llama-3.1-8B tokenizer audit assessed: NO-GO for Stage 1 GPU spend

Input: `data/tokenizer_audit/official/20260430T033208Z__meta-llama_Llama-3.1-8B.json`.

Findings:
- `recommendation.decision = no_go`. Honor it.
- `byte_fallback_or_proxy_rate = 0.193` vs threshold `0.01` → ~19× over. Real signal of bad Hawaiian coverage on Llama-3.1 BPE.
- `tokens_per_word = 2.474` passes 2.5 by ~1% — knife-edge, not a comfort.
- `explicit_byte_fallback_rate = 0.0` while proxy = 19% is suspicious; likely detector mismatch on Llama-3 byte tokens (`<0xE2>` etc.). Audit instrumentation needs reconciliation.
- Artifact is in `official/` but carries `dry_run: true` — violates user's path convention (`dryrun/` = dry, `official/` files must not carry dry-run flag).
- `model.tokenizer_sha256`, `model.tokenizer_fingerprint_sha256`, `model.model_repo_sha` all null — cannot freeze SHA into `code/configs/llama31_8b_a100.json`, so the documented Stage 1 precondition fails independently of metrics.
- `high_diacritic` and `diacritic_chars` sections both `not_evaluated` — the Hawaiian-specific signal the audit exists for is missing.

Recommendation: fix the audit pipeline (populate SHAs, evaluate high_diacritic + diacritic_chars, reconcile explicit-vs-proxy byte fallback accounting, drop `dry_run` field on `official/` outputs), re-run as a true official audit, hand to Rusty for the gate call, and only consider an interim base swap (Qwen2.5-7B, Gemma-2-9B) if the clean re-run still says no_go. No GPU spend, no data changes, no SHA freeze.

Decision note: `.squad/decisions/inbox/basher-llama31-tokenizer-audit-no-go.md`.

---

## 2026-04-30T033611Z — Tokenizer audit review + Stage 1 GPU freeze confirmed

**From:** Scribe (Orchestration logger)

**Summary:** Joint assessment with Rusty of `data/tokenizer_audit/official/20260430T033208Z__meta-llama_Llama-3.1-8B.json`:
- **Blocking issues:** missing hashes, missing Hawaiian-specific sections, dry_run flag in official path, proxy accounting mismatch
- **Gate status:** Stage 1 GPU fine-tuning **no-go**
- **Decision:** Do not spend GPU until clean official audit exists
- **Next:** Rusty's round-trip inspection, tokenizer-family-aware heuristic, re-run with populated metadata

**Your related orchestration log:** `.squad/orchestration-log/20260430T033611Z-basher.md`  
**Session log:** `.squad/log/20260430T033611Z-llama-tokenizer-audit-review.md`

## 2026-04-30T04:05:58Z — Tokenizer audit output contract and Llama-3.1-8B no_go decisions finalized

**From:** Scribe (Session logger)

**Summary:** Basher tokenizer audit decisions logged and merged to canonical decisions.md:

**1. Tokenizer-audit output contract (proposed, team review):**
- Schema for `code/tests/test_tokenizer_audit.py` audit outputs: `report.json` (gate-read), `report.md` (human), `samples.jsonl`, `inputs.manifest.json`
- `report.json` machine-readable contract: gate decision rule, threshold copying, hard-fail semantics (no fabrication on missing `transformers` / gated Llama / no Hawaiian samples)
- `report.md` human summary structure (≤1 screen): header, inputs table, metrics table, diacritic-char rows, decision paragraph, footer
- Hard-fail: write `no_go` with `errors[]` and null metrics, never fabricated numbers
- Decision logic: `go` iff all `checks[*].passed == true`; otherwise `no_go`

**2. Llama-3.1-8B tokenizer audit no-go (gate closed):**
- Input: `data/tokenizer_audit/official/20260430T033208Z__meta-llama_Llama-3.1-8B.json`
- Current blockers: `byte_fallback_or_proxy_rate = 0.1928` (~19× over 0.01 threshold), missing `tokenizer_sha256` / `tokenizer_fingerprint_sha256` / `model_repo_sha` (cannot freeze), high-diacritic and diacritic-chars sections `not_evaluated`, `dry_run: true` field in `official/` path (violates convention)
- Verdict: **No-go for Stage-1 GPU spend on Llama-3.1-8B.** Even if metrics were green, missing SHAs prevent config freeze.
- Next actions (in order): fix audit instrumentation, re-run as true official audit, hand to Rusty for gate call, evaluate interim bases only if clean re-run still says no_go

**3. Key findings from joint Basher/Rusty assessment:**
- No GPU spend, no data changes, no SHA freeze until clean official audit exists
- Audit SHAs, high-diacritic coverage, and diacritic-char coverage are hard preconditions, independent of metric values

**Orchestration logs:** `.squad/orchestration-log/2026-04-30T04:05:58Z-linus.md`  
**Related decisions:** Merged to `.squad/decisions.md` under:
- "Added 2026-04-30: Basher — Tokenizer-audit output contract (schema, gates, hard-fail semantics)"
- "Added 2026-04-30: Basher — Llama-3.1-8B tokenizer audit NO-GO (gate closed, awaits clean re-run)"

**Stage-1 GPU freeze:** Enforced until clean Llama audit passes `go`. Basher decision documented in canonical decisions.md.

## Learnings — 2026-04-30 — Stage 0 eval download helper

- Added `scripts/download_stage0_eval.sh`: SSH/SCP puller for Stage 0 eval artifacts. Mirrors the producer split from `scripts/run_stage0_eval.sh`:
  - full reports → `data/eval_runs/stage0/*__stage0_base_eval.json` (gitignored)
  - tracked summaries → `docs/eval-runs/stage0/*__stage0_base_eval_summary.json`
- CLI: `./scripts/download_stage0_eval.sh <ssh-dest> [remote-repo-path]` (defaults remote to `~/ideal-spoon`). Env knobs: `SSH_PORT`, `SSH_OPTS`, `SCP_OPTS`, `ONLY=full|summary|both`, `DRY_RUN=1`, `OVERWRITE=1`.
- Read-only on remote (ls + scp). Default no-clobber. `set -eu`, POSIX sh.
- README: usage added under `code/README.md` "Stage 0 eval runner" → "Pulling Stage 0 results back from the compute box".

### 2026-04-30 — Checkpoint-eval signal review (read-only assessment)

User asked what to look at between checkpoints to know if the model is improving or regressing. Reviewed `code/llm_hawaii/evaluate.py`, `scripts/run_stage0_eval.sh`, `docs/eval_pipeline.md`, `docs/training-pipeline.md`, and the Stage 0 baseline summary (`docs/eval-runs/stage0/20260430T063118Z__stage0_base_eval_summary.json`).

Stage 0 baseline (Llama-3.1-8B, FineWeb-2 dev 621 rows): `hawaiian_ppl = 7.9152`, eval_file_sha256 frozen, single prompt orthography clean (NFC=true, okina=15, wrong_okina=0, kahako=9, density=high). Treat 7.92 as the anchor every Stage 1 checkpoint is compared against.

**What to check between checkpoints (cheap, every save):**
1. Hawaiian held-out PPL on the same dev split — primary trend signal.
2. Orthography on a fixed prompt set: `is_nfc`, `okina`, `wrong_okina`, `kahako`, `diacritic_density_bin`. ʻokina-survival and kahakō-retention are the early-warning canaries — they collapse before PPL does.
3. Generation SHA drift vs prior checkpoint (already recorded in summary) — confirms model actually changed.
4. Train-loss trajectory + grad-norm + LR alongside the eval point so PPL anomalies can be attributed.

**What to add at gate-level (not every checkpoint):**
- English PPL regression vs base (≤+20% per `eval_pipeline.md` §3.2 / `training-pipeline.md` §2.4 gate 3). **Not currently wired in `evaluate.py`** — documented gap, blocks the Stage 1 gate from being callable as written.
- Per-source / per-register PPL slice (already a TODO in `perplexity()` requiring `source` field on JSONL records).
- W1 manual micro-eval (when accepted), and Stage 2 chrF-by-direction.

**Numeric gates (improvement vs regression):**
- Improvement: PPL trends monotonically downward across ≥2 consecutive checkpoints; target ≥20% relative reduction vs 7.92 (≈ ≤6.33) by Stage 1 gate. Tolerate ±2% noise band.
- Hard regression flags (any of):
  - PPL up >5% checkpoint-to-checkpoint, or up across 2 consecutive checkpoints.
  - `wrong_okina` becomes non-zero or trends up — orthography breaking.
  - `is_nfc=false` on any sample — pipeline-level NFC failure.
  - `kahako` collapses to 0 on a known high-density prompt — kahakō retention loss.
  - Generation length collapses, repetition explodes, or output flips to English/other script.
  - (Once wired) English PPL >+20% vs base — catastrophic forgetting.

**Fair-comparison preconditions (must be identical across compared checkpoints):**
- `eval_file_sha256` (already recorded), prompt set + `generation_sha256` keys, `max_length`, decoding config (greedy, `do_sample=False`, `max_new_tokens`), tokenizer SHA, base-model SHA, and **eval-time dtype/quantization** (eval the base model the same way for every checkpoint).
- Always re-anchor against the Stage 0 base row (7.9152) on the same plot — PPL deltas mean nothing without it.
- Never re-tune the eval set mid-run (`eval_pipeline.md` §4).

**Critical corrections (reported, not edited):**
- `evaluate.py:59` hard-codes `dtype=torch.float16`. Llama-3.1-8B/A100 trains in bf16; loading a bf16-trained adapter on an fp16 base for eval introduces a precision mismatch that can mask or amplify PPL changes between checkpoints. Should mirror the training dtype (bf16 on A100, fp16 only as Turing fallback). Worth a follow-up before any 7B/8B checkpoint comparison is trusted.
- `run_stage0_eval.sh` exercises a single prompt. For checkpoint-to-checkpoint orthography trending, the fixed prompt set should be ≥5–10 deterministic prompts (covering low/medium/high diacritic density per `metrics.diacritic_density_bin`); otherwise per-prompt noise dominates the signal.
- English-PPL probe absent in `evaluate.py` — Stage 1 gate #3 in `training-pipeline.md` §2.4 is currently unmeasurable. Either implement it before Stage 1 gate is called, or explicitly re-scope the gate.
- Per-source slice PPL absent (already TODO in `evaluate.py:84`); without it, regressions are not attributable to nūpepa-vs-contemporary skew per `eval_pipeline.md` §6.

Decision inbox: `.squad/decisions/inbox/basher-eval-checkpoints.md`.

## 2026-04-30: Checkpoint eval signals finalized

Joint advisory with Rusty on per-checkpoint Hawaiian LLM evaluation signals. Delivered:
- Cheap cadence metrics (PPL, orthography, generation SHA, training companions)
- Gate-level signals (English PPL, per-source slicing, W1 micro-eval)
- Improvement thresholds (≥20% PPL reduction to ≤6.33 target; flat orthography; stable English)
- Regression tripwires (PPL +>5%, okina collapse to U+2018/U+0027, wrong_okina>0, is_nfc=false, English >+20% delta, high-diacritic degradation, generation degeneracy, contamination rise)
- Fair-comparison preconditions (frozen eval_file_sha256, prompt set, decoding config, dtype/quantization, tokenizer SHA, base-model SHA)

Critical corrections flagged (not implemented): dtype mismatch (bf16 train vs fp16 eval), single-prompt orthography baseline (n=1 insufficient), unwired English probe, no per-source slicing, partial run_report schema.

Outcome: `.squad/decisions.md` entry, orchestration logs, session log recorded. Ready for implementation phase.

## 2026-04-30 — Stage 0 eval drift bundle implemented (`stage0_eval.v2`)

Implemented the drift-signal bundle promised by the 2026-04-30 checkpoint-eval advisory. Surgical edits, not committed.

**Schema bump:** `EVAL_SCHEMA_VERSION = "stage0_eval.v2"` in `code/llm_hawaii/evaluate.py`. Prior summaries are `v1`-implied (no field).

**New artifact fields** (full report and tracked summary; raw text never touches the summary):
- `identity.*` — checkpoint, base_model, is_adapter, model_class, model_dtype/device/device_map, quantization_config, tokenizer name/class/vocab size, torch+transformers versions, cuda_available. Captured per-eval so dtype mismatches (the prior bf16-vs-fp16 flag on Llama-3.1-8B) are at least *visible* in every summary.
- `decoding.*` — do_sample, max_new_tokens, greedy.
- `ppl_config.max_length`.
- `eval_set.*` — sha256, record_count, scored_record_count, total_tokens, total_chars, length_bin_counts_tokens (short/medium/long), diacritic_density_bin_counts, source_counts/register_counts (or `{"status":"field_absent"}`).
- `prompt_suite.*` — suite_id (`stage0.v1`), suite_sha256, items[] with prompt_sha256/prompt_diacritics/diacritic_density_bin/prompt_len_chars. No prompt text.
- `orthography_aggregate.*` — totals across the suite plus `kahako_collapse_on_high_diacritic`.
- `tripwires.*` — `wrong_okina_nonzero`, `nfc_failures`, `combining_macron_nonzero`, `kahako_collapse_on_high_diacritic`, `generation_count`, `prompt_suite_sha256`, `prompt_suite_id`.
- Explicit `status: "not_configured"` placeholders for `english_ppl`, `manual_w1`, `hawaiian_ppl_by_source`. No silent gaps.

**Fixed prompt suite (freeze):** 7 prompts — 1 English control, 2 low (1–2 diacritics), 2 medium (3 each), 2 high (12–13 each). `suite_sha256 = 2683027f538ae8fb2910f758f2865596355893cc91c85dbdfe9ced130797bce6`. **Editing a prompt in place silently breaks cross-checkpoint comparability**; rule now in `code/README.md`: append + bump `PROMPT_SUITE_ID` instead. First-pass prompts authored by me; needs Rusty (Hawaiian-literate) sign-off before any Stage 1 checkpoint compares to the v2 baseline.

**Backwards-compatible CLI:** `--checkpoint`, `--eval-file`, `--prompt` (repeatable, overrides suite) unchanged. New: `--no-prompt-suite`, `--max-length`, `--max-new-tokens`. New behavior: when no `--prompt` is given, the built-in suite runs. Wrapper script defaults `USE_SUITE=1` and no longer hardcodes a single prompt.

**Wrapper changes:** `scripts/run_stage0_eval.sh` now exposes `USE_SUITE`, projects the rich artifact into the tracked summary, and excludes `generations` text from the summary by design (full artifact still has it under ignored `data/eval_runs/stage0/`).

**Validation done:**
- `python3 -m py_compile` on changed Python files.
- `sh -n scripts/run_stage0_eval.sh`.
- 18/18 green via `cd code && PYTHONPATH=. python3 -m unittest tests.test_evaluate tests.test_metrics` (7 new in `test_evaluate.py` — no ML deps). `tests.test_data` requires `transformers`, pre-existing skip.
- `DRY_RUN=1` of the wrapper rendered correctly under suite-on, `USE_SUITE=0`, and `PROMPT=...` extra.
- `pytest` not available locally; ran via stdlib `unittest`.

**Decision inbox:** `.squad/decisions/inbox/basher-stage0-drift-signals.md`.

**Asks:**
- Rusty: review prompt content + the kahakō-collapse tripwire definition.
- Linus: confirm summary schema works for the cross-checkpoint diff/aggregator he intends to build.
- Coordinator: routing for English PPL + W1 manual harness wiring (still placeholders); flipping their `status` from `not_configured` to real values is the next blocker for a callable Stage 1 gate.

**Lesson:** placeholder fields (`status: "not_configured"`) beat silent absence — downstream diffs catch the moment a probe lights up instead of dropping the gap on the floor.

## stage0_eval.v2 — post-approval cleanups (Linus + Rusty)

Applied three surgical follow-ups after Linus and Rusty signed off on the
v2 drift bundle:

- `evaluate.py`: when `--eval-file` is omitted, `hawaiian_ppl` now emits
  `{"status": "not_configured", "reason": ...}` instead of being absent.
  Other probes (`english_ppl`, `manual_w1`, `hawaiian_ppl_by_source`)
  already used this shape; PPL was the odd one out and would silently
  vanish from summary diffs. Existing PPL-runs path is untouched.
- `scripts/run_stage0_eval.sh`: summary `schema_version` fallback flipped
  from `stage0_eval.v1` to `unknown`. A missing `schema_version` is now
  visible instead of being mislabeled as v1, which matters for any
  future schema bump (v2 → v3) where a stale full-report would otherwise
  look legitimate.
- `code/README.md` + `docs/eval_pipeline.md` §8.1: documented the
  suite-design freeze invariant — every future `haw_high_*` /
  high-`diacritic_density_bin` prompt must explicitly request kahakō,
  otherwise `kahako_collapse_on_high_diacritic` decays into noise. Same
  rule applies if the bin thresholds in `metrics.diacritic_density_bin`
  are ever retuned.

Validated with `python3 -m py_compile`, `sh -n`, and the existing
`tests/test_evaluate.py` (7/7 pass). No new tests added: the cleanups
are doc/string-shape changes; the existing aggregate + tripwire tests
already cover the semantic surface.

Lesson: when a report dict mixes "always-on" probes (PPL) and
"sometimes-wired" probes (English PPL, W1), pick one absent-shape and
apply it uniformly. Letting one field be `null`/missing while the
others are status objects creates a quiet diff hole the moment a flag
flips.

## 2026-04-30 — W1 manual micro-eval status wired into Stage 0 (metadata only)

Closed the "manual_w1 = not_configured forever" gap before re-running
Stage 0. Surgical, additive within `stage0_eval.v2` — no schema bump.

**`code/llm_hawaii/evaluate.py`:**
- New `manual_w1_status(path, *, enabled)` reads the off-git W1 TSV
  (defaults to `data/evals/manual_w1/w1-haw-micro-eval.tsv`,
  overridable). Strips `#` comments, validates header against the
  contract duplicated from `scripts/315_hash_manual_w1_eval.py:HEADER`
  (kept duplicated on purpose so `evaluate.py` doesn't import a
  scripts/ module).
- Stable status enum: `not_configured` (probe disabled) | `missing`
  (no file) | `invalid` (header mismatch / no header / unreadable) |
  `draft_only` (parsed but zero accepted rows) | `evaluated`
  (accepted rows present and metadata-validated).
- Always emits `scoring_status: "not_wired"` + reason — `evaluated`
  means metadata-evaluated, NOT task-scored. `accepted_count` is not
  a benchmark number until row-level scoring lands.
- Aggregates emitted on accepted rows: `tsv_sha256`,
  `accepted_count` (= `eval_consumable_count` alias),
  `review_status_counts`, `accepted_category_counts`,
  `accepted_diacritic_density_bin_counts`,
  `nfc_normalized_false_count`. **No raw prompt/reference text** in
  the report.
- New CLI: `--manual-w1-tsv PATH`, `--no-manual-w1`. Wired into
  `evaluate_checkpoint(...)` and `main()`.

**`scripts/run_stage0_eval.sh`:**
- New env vars: `MANUAL_W1_TSV` (default
  `data/evals/manual_w1/w1-haw-micro-eval.tsv`), `USE_MANUAL_W1=1`.
- Passes `--manual-w1-tsv` / `--no-manual-w1` through to evaluate.py
  and into the recorded `command` field of the tracked summary.
- Banner reports presence/disabled/missing for W1 TSV before the run.

**`code/README.md` + `docs/eval_pipeline.md` §8.1:** documented the
status enum, the override knobs, and the explicit
`scoring_status: not_wired` distinction. `manual_w1` removed from the
"probes not yet wired" placeholder bullet — it's now wired for
metadata; row-level scoring is the next assignment.

**Tests (`code/tests/test_evaluate.py`):** 7 new cases under
`TestManualW1Status` covering each status, the NFC-false counter, and
a leak check that no raw Hawaiian text reaches the status object.

**Validation:**
- `python3 -m py_compile code/llm_hawaii/evaluate.py` — clean.
- `sh -n scripts/run_stage0_eval.sh` — clean.
- `PYTHONPATH=. python3 -m unittest tests.test_evaluate
  tests.test_metrics` → **25/25 green** (14 evaluate, 11 metrics).
- Wrapper `DRY_RUN=1` over five matrices (defaults / W1 disabled /
  suite off / suite off + W1 disabled / custom TSV + ad-hoc prompt)
  — line continuations and final-flag rules render correctly with no
  dangling backslashes.

**Decision inbox:**
`.squad/decisions/inbox/basher-w1-stage0-status.md`.

**Asks:**
- Rusty: confirm `data/evals/manual_w1/w1-haw-micro-eval.tsv` is the
  canonical path; if it moves, bump `DEFAULT_MANUAL_W1_TSV`.
- Linus: schema diff sanity check — `manual_w1` is now a status-keyed
  object with stable shape across all five enum values. Aggregator
  should key on `status` + `accepted_count` + `tsv_sha256`.
- Coordinator: route the next chunk — wire **row-level model scoring**
  for W1 (per-row pass/fail per category). That flips
  `scoring_status` to `wired` and gives Stage 1 a real W1 gate
  signal. Explicitly out of scope for this PR.

**Lesson:** the `not_configured` placeholder I baked in two iterations
ago turned out to fight a real status the moment the TSV existed.
Reserving `not_configured` strictly for the *explicitly disabled*
path — and inventing `missing` / `draft_only` / `evaluated` for the
file-driven states — is what lets a downstream diff distinguish "we
chose not to look" from "we looked and there are zero accepted rows".
Same lesson as the v2 cleanup: pick one absent-shape and apply it
uniformly, but don't conflate "probe off" with "probe on, nothing
there yet".

---

## 2026-04-30 — W1 contract revision (Rusty rejection follow-up)

Rusty rejected the v2 W1 wiring with four blocking gaps; revised in
place rather than redesigning.

**Changes landed (TSV path only, JSONL-first follow-up flagged):**
- Added `accepted_item_hashes`: sorted `sha256(NFC(prompt + LF +
  reference))` for accepted rows. `[]` when no accepted rows.
- Added `w1_suite_sha256`: sha256 over sorted `(item_id, sha)` pairs
  encoded `item_id\tsha\n`. `null` when no accepted rows. Verified
  stable under row reorder; flips on accepted↔draft swap.
- Added `schema_version_seen`: `"manual-w1-tsv-v1"` on `evaluated` /
  `draft_only`; `null` elsewhere. Reserves the field for the JSONL
  switch (which will read `MANUAL_W1_JSONL_SCHEMA_VERSION`).
- Added strict orthographic gate on accepted rows: `nfc_normalized`
  field, NFC of prompt/reference, no `U+0304`, no wrong-ʻokina. Any
  failure flips file to `status=invalid` with `error_count` and
  `first_errors` (line+field only — no row content).

**Helper-reuse decision:** `scripts/315_hash_manual_w1_eval.py` is the
canonical hash source but cannot be `import`ed — the filename starts
with a digit and contains a hyphen, and the module performs CLI-side
mutating work (ledger updates) on load. I mirrored *only* the exact
canonical formula into two private helpers in `evaluate.py`, and
pinned the byte-exact match with a unit test that recomputes the
SHA inline. Documented in
`.squad/decisions/inbox/basher-w1-contract-revision.md`.

**Validation:**
- `python3 -m py_compile code/llm_hawaii/evaluate.py
  scripts/315_hash_manual_w1_eval.py` → clean.
- `sh -n scripts/run_stage0_eval.sh` → clean.
- `PYTHONPATH=. python3 -m unittest tests.test_evaluate
  tests.test_metrics` → **36/36 green** (+11 from 25).
- `git diff --check` → clean.

**Lesson:** when a contract has helper-reuse intent but the helper
lives in a non-importable script, mirror-with-pinned-test beats both
(a) re-deriving the formula by reading the spec, which drifts, and
(b) `runpy`-loading a CLI module, which leaks side effects into a
read-only probe. The pinned test is the single tripwire that catches
formula drift in either direction.

**Out of scope still:** row-level model scoring (`scoring_status`
stays `not_wired`); `harness_error` 5th branch; English PPL;
`hawaiian_ppl_by_source`. Naming drift (`tsv_sha256` vs
`input_sha256` etc.) deliberately untouched per Rusty's
non-blocking note.

---

## 2026-04-30T09:15:54Z — Orchestration checkpoint: Training runner + test fix APPROVED + merged

**Orchestration context:** Scribe merged training runner readiness and test fix decisions into `.squad/decisions.md` and archived orchestration logs.

**Status:** ✅ Stage 1 runner ready for compute.
- Config-relative path resolution contract established (paths resolve from config file location, not CWD)
- New CLI flags: `--preflight`, `--resume-from-checkpoint PATH`, `--eval-after-train` (backward compatible)
- Run report schema `training-run-report.v1`: git commit, file hashes, row counts, no raw text
- Preflight checks validate config/data/runtime without model download
- Test fix (`_DummyTokenizer`): unit tests now run without transformers/torch deps; 103 tests pass
- Orchestration logs: `.squad/orchestration-log/2026-04-30T09-15-54Z-basher-training-runner.md` and `.squad/orchestration-log/2026-04-30T09-15-54Z-basher-test-fix.md`

**Next-run command sequence:**
```bash
python3 -m llm_hawaii.train --config code/configs/stage1_fineweb2_haw.json --preflight
python3 -m llm_hawaii.train --config code/configs/stage1_fineweb2_haw.json
```

**Ready for:** Compute environment Stage 1 CPT/QLoRA run.


## 2026-04-30 — Kaggle T4x2 DDP Feasibility Research

**Context:** Baseline understanding of Kaggle T4x2 hardware (2× NVIDIA T4, 16 GB each) and whether DDP (Distributed Data Parallel) is viable for Stage 1 training under the current QLoRA config.

**Research Outcome:**

Kaggle exposes two discrete T4 GPUs via CUDA. The current training config uses `device_map="auto"` with bitsandbytes 4-bit quantization, which is **model-parallel placement** (layers spread across GPUs to fit in memory), not data-parallel DDP. Training is single-process/single-stream; one GPU may be idle most steps.

QLoRA + bitsandbytes 4-bit cannot use DDP: bitsandbytes wraps parameters in custom `bnb.nn.Linear4bit` objects that break DDP's gradient gathering and state-dict contracts (upstream blocker). `accelerate launch --num_processes 2` would fail with CUDA init conflicts (known broken for bnb-quantized models).

**Decision:** Keep single-process `python -m llm_hawaii.train`. No code changes required. This is the only safe and correct option with current QLoRA+bitsandbytes config on T4x2.

- Do NOT add multi-process launchers (accelerate, torchrun) for QLoRA.
- If DDP throughput scaling needed in future: drop QLoRA, use full precision (bf16/fp16), retarget to higher-VRAM hardware (A100/H100).
- Monitor upstream bitsandbytes for 4-bit DDP support.

**Merged to decisions.md:** 2026-04-30T10:00:52Z

**Status:** Recommendation — no implementation required. First Kaggle T4x2 run ready to proceed with single-process model placement.


---

## 2026-05-01 — T4x2 Config Finalized + Green Light for Stage 1

**Scribe orchestration checkpoint:** Decision `basher-maximize-t4x2` merged to decisions.md. Rusty Stage 0 eval baseline confirmed (Hawaiian PPL 7.92); all orthography tripwires green.

**T4x2 Config Outcome:**
- `max_seq_len`: 1024 → 2048 (exploit ~32GB addressable VRAM across device_map="auto" model placement)
- `gradient_accumulation_steps`: 32 → 16 (preserve 32K tokens/update, faster wall-clock)
- OOM fallback strategy documented
- All validation passed

**Status:** Ready for Stage 1 training launch on Kaggle T4x2. Monitor for OOM; fallback plan ready.

---

## 2026-04-30 — Kaggle T4x2 spare-VRAM tuning

**User Directive:** Inspect Stage 1 Kaggle T4x2 memory usage; user observed roughly 8–10GB unused VRAM across the two T4s.

**Outcome:**
- `code/configs/stage1_fineweb2_haw_kaggle_t4x2.json` — raised `per_device_train_batch_size` 1→**2** and lowered `gradient_accumulation_steps` 16→**8**.
- `docs/kaggle-t4x2-setup.md` — documented the new 2048×2×8 token budget and OOM fallback order.
- `.squad/decisions/inbox/basher-vram-tuning.md` — decision drop with rationale and code-change follow-ups.

**Reasoning:**
- This is the safest config-only way to use the spare VRAM: it increases micro-batch activation memory while preserving the same ~32K tokens/update (`2048×1×16 = 2048×2×8 = 32768`).
- Do not use DDP/torchrun/accelerate multi-process with this QLoRA+bitsandbytes setup; `device_map="auto"` remains the correct single-process sharding strategy.
- Do not raise `max_seq_len` beyond 2048, raise LoRA rank, or disable gradient checkpointing based only on spare-memory observation; those are more likely to destabilize training.

**Fallback:** If Kaggle OOMs, revert batch to 1 and accumulation to 16 first. Then fall back to seq_len 1024 / accumulation 32, then LoRA rank 16 / alpha 32.
