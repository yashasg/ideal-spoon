# Skill: Lineage Preflight Checks

## Pattern

Multi-stage ML pipelines need to assert that artifacts from one stage feed the next stage unchanged. The pattern:

1. **Stage N saves artifacts + computes their SHAs → writes to `run_report.json`.**
2. **Stage N+1 preflight loads Stage N's `run_report.json`, re-hashes the artifacts, asserts equality.**
3. Any tamper (byte flip, wrong file substitution) → hard fail before GPU spend.

## Implementation rules

- Hash computation: stdlib only (`hashlib`). No ML deps in preflight.
- Hash canonical files in **sorted order** by filename so the digest is deterministic across OSes.
- Store `run_report.json` in the output dir of every stage (same dir as saved model/tokenizer).
- `parent_run_dir` in the config is the single pointer from Stage N+1 to Stage N's output dir.
- Resolve `parent_run_dir` config-relative (same as `train_path`) so configs are portable.
- Run the lineage check **before** any tokenizer/model load in the training entrypoint.

## Key functions (ideal-spoon)

```python
compute_tokenizer_sha(tokenizer_dir: Path) -> str       # train.py
_compute_artifact_sha(out_dir: Path) -> Optional[str]  # train.py
run_stage2_lineage_preflight(cfg: TrainConfig) -> dict  # train.py
```

## Acceptance test shape

- ✅ Valid parent dir + matching SHA → `issues == []`
- ✅ Tampered tokenizer.json (single-byte flip) → SHA mismatch issue
- ✅ Missing `parent_run_dir` → issue reported
- ✅ Non-existent `parent_run_dir` → issue reported
- ✅ Missing `run_report.json` in parent dir → issue reported
- ✅ `run_report.json` lacking `tokenizer_sha` → issue reported
- ✅ Stage 1 preflight unaffected by Stage 2 lineage checks

---

## Extension: coverage preflight for mined-data sources (Frank, 2026-05-02)

Lineage preflight is not just "Stage N+1 re-hashes Stage N artifacts".
It also applies *upstream*: before building an adapter for a mined or
HF-hosted source, preflight that the upstream actually contains the
target language. The cost is a few HTTP GETs; the savings are an
entire adapter you don't write against a nonexistent slice.

### Pattern

For any HF dataset claimed to carry haw↔eng (or any low-resource
slice) bitext:

1. `GET https://huggingface.co/api/datasets/<owner>/<name>` — confirm
   `gated`, `private`, `lastModified`, `siblings` count.
2. `GET https://huggingface.co/api/datasets/<owner>/<name>/tree/main`
   — list root artifacts; if it's a script-loader dataset (`*.py`
   present, no per-config dirs), grab the loader.
3. `GET https://huggingface.co/datasets/<owner>/<name>/resolve/main/<loader>.py`
   and any `*_lang_pairs.py` / `*_configs.py` / `<name>.py` — parse
   and enumerate the lang codes. Use a tight regex like
   `r"[a-z]{3}_[A-Z][a-z]{3}"` for BCP-47-ish NLLB-style codes.
4. Smoke `https://datasets-server.huggingface.co/rows?dataset=...&config=<probe>&split=train&offset=0&length=1`
   for the most likely `<src>-<tgt>` config name. 404 = config absent;
   501 = script-loader dataset (rely on step 3 instead); 200 = real
   coverage and you can read the schema.
5. Write `endpoint_proof.json` with sha256 of every captured file plus
   a boolean `<lang>_present` and a closed-enum `verdict`
   (`OK_<LANG>_PRESENT` or `ENDPOINT_INVALID_NO_<LANG>_COVERAGE`).
6. Probe script must be stdlib-only, support
   `--self-test`/`--dry-run`/`--execute`, sleep ≥3.0s between requests,
   set a project-identifying User-Agent, and exit non-zero when
   coverage is absent so it can be wired into CI/automation later.

### Anti-patterns to forbid in code review

- Substring matching on lang codes — `"haw" in code` will match
  `"shaw_Xxxx"` if anyone ever invents one. Match exact code or use
  `code.startswith("haw_")` with explicit allowlist of script tags.
- Confusing `hau_Latn` (Hausa), `hat_Latn` (Haitian) with `haw_Latn`
  (Hawaiian). Add an explicit assertion to any probe / loader / score
  script: `assert lang_code != "hau_Latn"` if intent is Hawaiian.
- Trusting plan-stated yield projections without an endpoint proof
  artifact. The plan's expected_pair_yield is a hypothesis; the proof
  artifact is the receipt.

### Reference instance

`data-sources/nllb-mined-haw-eng/probe.py` — first concrete coverage
preflight on this scaffold. Verdict was
`ENDPOINT_INVALID_NO_HAW_COVERAGE`, captured under
`data/raw/nllb-mined-haw-eng/20260502/endpoint_proof.json`. Saved
building an entire mined-data adapter against a slice that does not
exist upstream.
