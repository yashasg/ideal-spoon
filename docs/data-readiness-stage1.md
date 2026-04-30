# Stage 1 Training Data Readiness Report

> Generated: 2026-05-01 (Linus — Data Engineer)
> Scope: Prototype Stage 1 CPT run — cleaned multi-source trainer corpus.
> **No raw text.** All fields are counts, hashes, or status flags.

---

## ⚠️ Data Framing

All data described here is **prototype-only** (`prototype_only=True`, `release_eligible=False`).  
FineWeb-2 rows come from CommonCrawl via the HuggingFace FineWeb-2 dataset wrapper (ODC-By licence on the wrapper). Underlying texts carry independent third-party rights per source URL. **Do not assume release clearance.** These data are for internal learning/research only.

---

## 1. Training Input — `data/stage1/stage1.jsonl.gz`

| Field | Value |
|---|---|
| Path (repo root) | `data/stage1/stage1.jsonl.gz` |
| Total rows | 81,117 |
| Missing `text` field | 0 |
| Empty `text` rows | 0 |
| NFC-ok rows | 81,117 (100%) |
| NFC-fail rows | 0 |
| Char total | 206,030,394 |
| Whitespace tokens | 44,067,289 |
| Source mix | FineWeb-2: 79,812 rows / 43,843,711 tokens; hawwiki: 1,163 rows / 190,499 tokens; hawwikisource: 142 rows / 33,079 tokens |
| `split` | `train` (100%) |
| `prototype_only` | `True` (100%) |
| Release status | Prototype/learning only; not release-cleared |
| Blockers | None — `text` present, NFC clean, no empty rows |

### 1.1 Pipeline history (no raw text)

- Script `310_split_dedupe_fineweb2_haw.py` produced the deduped raw FineWeb-2 haw_Latn train slice against the full 887-row test split using NFC-normalised SHA-256 hashes. Seed-stable, deterministic split.
- `301_build_stage1_dataset.py` consumed that FineWeb-2 slice plus hawwiki and hawwikisource ledgers, then emitted `data/stage1/stage1.jsonl.gz` with the slim trainer schema: `doc_id, text, source, split, prototype_only, register`.
- Stage 1 configs now point at this cleaned multi-source trainer file instead of the raw FineWeb-only split.

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
| `train_path` | `../data/stage1/stage1.jsonl.gz` |
| `eval_path` | `../data/evals/fineweb2_haw/dev.jsonl` |
| `text_field` | `text` |
| `unicode_normalization` | `NFC` |
| `eval_steps` | `200` |
| `eval_strategy` wired | Yes (in `train.py`: both `eval_path` and `eval_steps` must be non-null) |

---

## 4. Note on the raw FineWeb-2 split

`data/stage1/fineweb2_haw/train.jsonl` still exists as the deduped but raw FineWeb-2 haw_Latn train split (95,507 rows). It was the first immediate prototype candidate because the FineWeb split/dedupe/eval ledger was wired before the cleaned multi-source trainer file.

The active training configs now use `data/stage1/stage1.jsonl.gz` so hawwiki and hawwikisource are included. Both files remain off-git (`data/` is gitignored).

---

## 5. Blocking Issues

None identified. Training can proceed once hardware and HF model access are confirmed.

### Known caveats (non-blocking)

1. **Not release-eligible.** All data is `prototype_only=True`. Do not publish checkpoints trained solely on this data as production artifacts.
2. **MinHash dedup not yet complete.** Exact-SHA dedup against eval/test is done; near-duplicate MinHash/LSH across FineWeb × hawwiki × hawwikisource is planned (see `cleaning_report.json: near_duplicate_minhash_status`).
3. **No cultural-sensitivity tagging pass** on FineWeb-2 rows yet (only hawwiki/hawwikisource had this gate in prior pipeline design).
4. **FineWeb-2 still dominates volume.** The wiki sources add register diversity, but the current trainer file is still mostly FineWeb-2 by token count.
5. **`transformers` not installed locally** — ML-dep tests will skip/error until installed with `pip install -r requirements-compute.txt`.
