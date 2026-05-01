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
