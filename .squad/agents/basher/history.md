# Basher — History

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
