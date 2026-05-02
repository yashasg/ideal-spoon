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

---

## Extension: raw-provenance probe for comparable-aligned MediaWiki sources (Frank, 2026-05-02)

Some Stage-2 sources (Wikipedia langlinks, Wikisource cross-links) are
**comparable, not parallel**: their fetch plans declare
`alignment_method=labse`. The honest stance for a data collector when the
required aligner isn't wired into the repo is **not** to emit candidate rows
with `alignment_method=null` and `alignment_review_required=true` — that
silently floods the review queue and inflates N. The honest stance is to
land a raw-provenance probe that the alignment agent can consume later
without re-crawling.

### Pattern (mirrors nllb probe scaffold; differs in posture)

For any HF-or-MediaWiki source whose plan-stated alignment is `labse`/`laser`:

1. Read input titles/IDs from the **already-ingested Stage-1 artifact** if
   present (e.g. `data/extracted/hawwiki/<YYYYMMDD>/extracted.jsonl.gz`).
   Don't re-crawl what Stage 1 already pinned.
2. Hit the upstream API (MediaWiki: `prop=langlinks|info|revisions` with
   `lllang=<en>`, `formatversion=2`, `redirects=1`, `maxlag=5`) and persist
   *every raw response* under
   `data/raw/<source-id>/<YYYYMMDD>/batches/<endpoint>_batch_NNNN.json` with
   sha256, http status, fetch timestamp, content-type.
3. Snapshot the ToS / license page once per probe day → `tos_snapshot.html`
   plus a `tos_snapshot.meta.json` with sha256.
4. Capture *both sides'* current revision IDs (haw side from langlinks query,
   en side via a follow-up `prop=info|revisions` batch on resolved titles).
   These are the immutable join keys for the future alignment pass.
5. Emit a per-pair `langlinks_manifest.jsonl` with at minimum:
   `{haw_title, haw_pageid, haw_revid, haw_revision_timestamp, haw_url,
     en_title_requested, en_title_resolved, en_pageid, en_revid,
     en_revision_timestamp, en_url, fetch_timestamp_utc,
     license_observed, tos_or_license_url, tos_snapshot_path,
     alignment_type=comparable-aligned, alignment_method_required=labse,
     alignment_blocker, dedup_cluster_id_seed}`.
6. Emit `probe_summary.json` with `verdict`, `stats`, explicit `blockers`,
   and `dedup_overlap_risk` against any sibling lane (e.g. CX-published).
7. Copy `probe_summary.json` to `data/stage2/reports/<source>_probe_report.json`.
8. **Do NOT** emit `data/stage2/candidates/<source>.jsonl`. **Do NOT** touch
   `data/stage2/stage2_manifest.jsonl` or final-capped artifacts.
9. Update `data-sources/stage2-parallel-fetch-plan.json::sources[].adapter_status`
   to `raw_probe_landed_blocked_on_<aligner>` with a `raw_probe` block
   pointing at script + report + raw dir + smoke counts + blocker.

### MediaWiki API etiquette

- `User-Agent: <project>/<version> (... contact ...)`. Wikimedia bans naked UAs.
- Sleep ≥1.0s between calls; `maxlag=5` skips during high replication lag
  with no penalty.
- `formatversion=2` returns `pages` as a list, not a dict; index code must
  handle both shapes.
- `redirects=1` rewrites `pages[].title` to the resolved title and exposes
  `query.redirects[]` as the alias map. Attach the resolved revision record
  to *both* requested and resolved title keys when building the join index.
- Filter mainspace at the *probe input* layer: title-prefix denylist of
  English-language namespace prefixes (`Wikipedia:`, `Module:`, …) is fine
  for a smoke set; production-grade filter should use `prop=info` `ns` field
  to handle Hawaiian-namespace prefixes (`Anakuhi:` for Template,
  `Hoʻonohonoho:` for Category, etc.).

### Anti-patterns

- Emitting `alignment_method=null` doc-level pairs and tagging them
  `alignment_review_required=true`. This is review-queue spam, not data.
- Setting `alignment_score` to a placeholder (0.0, 1.0, or any heuristic).
  No score is honest until LaBSE/LASER actually runs.
- Re-crawling titles for which Stage 1 already pinned a revision ID. The
  probe must consume the Stage-1 extract.
- Mutating a sibling lane's raw dir (e.g.
  `data/raw/wikimedia-cx-en-haw-published/`) for "dedup convenience". Probes
  are additive; dedup is recorded as `dedup_cluster_id_seed` and resolved
  downstream.

### Reference instance

`data-sources/wiki-haw-en-langlinks/probe.py` — Stage-2 priority #3 lane,
2026-05-02. Smoke set 60 hawwiki titles → 53 langlink pairs with full
revision IDs both sides. Verdict `OK_RAW_PROBE_LANGLINKS_RECORDED`,
adapter_status `raw_probe_landed_blocked_on_labse`. Stage-2 N unchanged.
