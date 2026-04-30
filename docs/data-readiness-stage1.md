# Stage 1 Training Data Readiness Report

> Generated: 2026-05-01 (Linus — Data Engineer)
> Scope: Prototype Stage 1 CPT run — FineWeb-2 haw_Latn slice only.
> **No raw text.** All fields are counts, hashes, or status flags.

---

## ⚠️ Data Framing

All data described here is **prototype-only** (`prototype_only=True`, `release_eligible=False`).  
FineWeb-2 rows come from CommonCrawl via the HuggingFace FineWeb-2 dataset wrapper (ODC-By licence on the wrapper). Underlying texts carry independent third-party rights per source URL. **Do not assume release clearance.** These data are for internal learning/research only.

---

## 1. Training Input — `data/stage1/fineweb2_haw/train.jsonl`

| Field | Value |
|---|---|
| Path (from `code/`) | `../data/stage1/fineweb2_haw/train.jsonl` |
| Total rows | 95,507 |
| Missing `text` field | 0 |
| Empty `text` rows | 0 |
| NFC-ok rows | 95,507 (100%) |
| NFC-fail rows | 0 |
| Char total | 323,638,532 |
| Approx tokens (chars/4) | ~80.9 M |
| `source_id` | `fineweb2_haw` (100%) |
| `split` | `train` (100%) |
| `prototype_only` | `True` (100%) |
| `release_eligible` | `False` (100%) |
| Blockers | None — `text` present, NFC clean, no empty rows |

### 1.1 Pipeline history (no raw text)

- Script `310_split_dedupe_fineweb2_haw.py` produced this file: deduped FineWeb-2 haw_Latn train slice against the full 887-row test split using NFC-normalised SHA-256 hashes. Seed-stable, deterministic split.
- `301_build_stage1_dataset.py` ran paragraph-level cleaning against this file: 95,507 rows seen, 6,528 rejected, 88,979 accepted; clean-token estimate `59,534,611 → 44,067,289`.
- Cleaned output is `data/stage1/stage1.jsonl.gz` (81,117 rows, 6-field slim schema). That file is the canonical post-cleaning trainer candidate; see §4.

### 1.2 ʻOkina / diacritic orthography (from `cleaning_report.json`)

| Item | Count |
|---|---|
| ʻokina canonicalized to U+02BB | 339,598 |
| Variant U+0027 (apostrophe) | 304,204 |
| Variant U+0060 (backtick) | 1,341 |
| Variant U+02BC (modifier apostrophe) | 6 |
| Variant U+2018 (left single quotation) | 19,801 |
| Variant U+2019 (right single quotation) | 14,246 |
| Raw combining macron U+0304 seen | 2 |
| Kahakō count (clean) | 8,322,754 |
| ʻOkina count (clean) | 11,141,104 |
| Diacritics per 100 chars | 8.57 |

The single `kahako_not_precomposed_after_nfc` paragraph was rejected by the cleaning gate.

---

## 2. Eval Input — `data/evals/fineweb2_haw/dev.jsonl`

| Field | Value |
|---|---|
| Path (from `code/`) | `../data/evals/fineweb2_haw/dev.jsonl` |
| Total rows | 621 |
| Missing `text` field | 0 |
| Empty `text` rows | 0 |
| NFC-ok rows | 621 (100%) |
| Char total | 2,172,006 |
| Approx tokens (chars/4) | ~543 K |
| `split` | `test` (100%) |
| `prototype_only` | `True` (100%) |
| `release_eligible` | `False` (100%) |
| Blockers | None |

Produced by `310_split_dedupe_fineweb2_haw.py` (70/30 seeded split from 887-row FineWeb-2 haw_Latn test split). Train ∩ eval intersection is zero by construction (dedupe pass).

---

## 3. Config Alignment — `code/configs/llama31_8b_a100.json`

| Field | Value |
|---|---|
| `train_path` | `../data/stage1/fineweb2_haw/train.jsonl` |
| `eval_path` | `../data/evals/fineweb2_haw/dev.jsonl` |
| `text_field` | `text` |
| `unicode_normalization` | `NFC` |
| `eval_steps` | `200` |
| `eval_strategy` wired | Yes (in `train.py`: both `eval_path` and `eval_steps` must be non-null) |

---

## 4. Note on `stage1.jsonl.gz` (post-cleaning alternative)

`data/stage1/stage1.jsonl.gz` exists (81,117 rows, slim 6-field schema: `doc_id, text, source, split, prototype_only, register`). It is the canonical cleaned trainer output from `301_build_stage1_dataset.py` and contains multi-source rows (FineWeb-2 + hawwiki + hawwikisource). Token target report estimates 44M clean tokens.

**Using `train.jsonl` vs `stage1.jsonl.gz`:** For prototype Stage 1, `train.jsonl` is the immediate candidate (per user directive). `stage1.jsonl.gz` is the cleaner, pipeline-canonical alternative — to switch, set `train_path` to `../data/stage1/stage1.jsonl.gz`. Both files are off-git (`data/` is gitignored).

---

## 5. Blocking Issues

None identified. Training can proceed once hardware and HF model access are confirmed.

### Known caveats (non-blocking)

1. **Not release-eligible.** All data is `prototype_only=True`. Do not publish checkpoints trained solely on this data as production artifacts.
2. **MinHash dedup not yet complete.** Exact-SHA dedup against eval/test is done; near-duplicate MinHash/LSH across FineWeb × hawwiki × hawwikisource is planned (see `cleaning_report.json: near_duplicate_minhash_status`).
3. **No cultural-sensitivity tagging pass** on FineWeb-2 rows yet (only hawwiki/hawwikisource had this gate in prior pipeline design).
4. **Token volume is 17.6% of conservative target** (44M of 250M). This is expected for the FineWeb-only prototype slice.
5. **`transformers` not installed locally** — ML-dep tests will skip/error until installed with `pip install -r requirements-compute.txt`.
