# Data Pipeline (Stage 1 + Stage 2)

> **Status:** Prototype design for a learning project. No corpora are committed to this repo, and **public sharing of weights, tokenizer, dataset, or demo is out of scope.** This document describes pipelines we'd build and run **privately/locally** to produce prototype artifacts only.
>
> **Owner:** Linus (Data Engineer). Accepted ADRs governing this pipeline (two-stage training plan, prototype scope, base-model recommendation, credit-fit) live in [`.squad/decisions.md`](../.squad/decisions.md).
>
> **Companion doc:** [`training-pipeline.md`](./training-pipeline.md) — the training pipeline that consumes the artifacts produced here. This document covers data ingest, normalization, manifests, and contamination guards (what goes *into* the model); the training pipeline doc covers Stage 1 CPT, the fp16 merge step, and Stage 2 SFT (what the model *does* with that data).

The project trains in two stages:

| Stage | Purpose | Data shape | Loss |
|---|---|---|---|
| **Stage 1** | Hawaiian DAPT/CPT — adapt the multilingual base to ʻŌlelo Hawaiʻi | Monolingual Hawaiian documents | Causal-LM over full text |
| **Stage 2** | Bidirectional en↔haw supervised translation SFT | Parallel sentence/verse pairs + 10–20% Stage-1-style retention slice | Target-only SFT |

Stage 2 ingest is **blocked on Stage 1 artifacts** existing and `eval_hashes.parquet` being populated. Stage-2 *design and adapter scaffolding* can land in parallel.

---

## Table of contents

- [Prototype scope](#prototype-scope)
- [Cross-stage invariants](#cross-stage-invariants)
- [Storage formats](#storage-formats)
- [Stage 1 — Monolingual Hawaiian (DAPT/CPT)](#stage-1--monolingual-hawaiian-daptcpt)
  - [Source tiers](#stage-1-source-tiers)
  - [Transformation pipeline](#stage-1-transformation-pipeline)
  - [Manifest schema](#stage-1-manifest-schema)
  - [Output JSONL](#stage-1-output-jsonl)
  - [Contamination & eval guards](#stage-1-contamination--eval-guards)
  - [Risks](#stage-1-risks-ranked)
  - [Immediate next steps](#stage-1-immediate-next-steps)
- [Stage 2 — Bidirectional en↔haw SFT](#stage-2--bidirectional-enhaw-sft)
  - [Source tiers](#stage-2-source-tiers)
  - [Transformation pipeline](#stage-2-transformation-pipeline)
  - [Manifest schema](#stage-2-manifest-schema)
  - [Output JSONL](#stage-2-output-jsonl)
  - [Contamination & eval guards](#stage-2-contamination--eval-guards)
  - [Risks](#stage-2-risks-ranked)
  - [Immediate next steps](#stage-2-immediate-next-steps)
- [Open team gaps](#open-team-gaps)

---

## Prototype scope

This project is a **learning prototype**. Public sharing of any artifact — corpora, manifests, tokenizer, adapters, weights, demo — is out of scope. The pipeline is built to run privately/locally and the safeguards below exist to keep it that way.

| Aspect | Prototype rule (private/local only) |
|---|---|
| Default row tags | `prototype_only=true` on every row; no row is ever tagged for external sharing |
| Sources allowed | Tier A/B with observed (not necessarily cleared) license; ToS-snapshot-on-fetch; no scraped sources whose ToS forbids the fetch |
| Hard-escalate categories (mele, oli, pule, moʻolelo from named tradition-bearers, moʻokūʻauhau) | **Excluded** until a cultural-review owner exists — even for prototype use |
| Pre-1925 nūpepa bulk | Allowed with `prototype_only=true`, but kept private; bulk publication is out of scope per prior ADR |
| OCR'd content | Allowed with `ocr_confidence_mean` recorded |
| Synthetic / back-translation | Stage 2: ≤25% train, 0% dev/test, `synthetic=true` recorded |
| CI guard on artifact publication | **Refuse** to emit any artifact externally — public sharing is out of scope, and the guard fires regardless of row tags |

A tokenizer trained on prototype data is itself a derivative; an adapter trained on prototype data is a derivative. The publication guard is mechanical, not a discretionary call: nothing in this lineage is shared.

---

## Dataset division taxonomy

All dataset artifacts produced by this pipeline are organized under four
top-level divisions on disk, rooted at `data/`. This is the canonical taxonomy;
future scripts, manifests, and handoffs use these names.

Two of the four divisions are training corpora (`stage1`, `stage2`); the other
two are **both held out from training**, distinguished only by how often the
harness is allowed to look at them:

- `evals` — **cheap, frequent, checkpoint-aligned** eval data. Read on every
  checkpoint save.
- `final` — **held-out, major-milestone** eval data. Read sparingly: only at
  stage gates, candidate-checkpoint promotion, and end-of-run evaluation. Kept
  protected so the harness can't be re-tuned against it run-over-run.

| Division | On-disk root | What lives here | Held out from training? |
|---|---|---|---|
| `evals` | `data/evals/` | **Cheap, frequent eval data:** FineWeb-2 `haw_Latn` test dev split, W1 manual micro-eval rows, Stage-0 smoke / per-checkpoint sanity anchors, plus the `eval_hashes.parquet` contamination ledger that covers **both** held-out divisions (`evals` and `final`). | **Yes — never train on `evals`.** Row hashes are appended to `eval_hashes.parquet` *before* anything else ingests; train candidates are deduped against the ledger at build time. |
| `stage1` | `data/stage1/` | Unsupervised / base-adaptation corpus artifacts produced by `301_build_stage1_dataset.py` from the cleaned Stage-1 training sources: `stage1_manifest.parquet`, `stage1.jsonl.gz`, packed/tokenized shards. Only `split=train` and `split=dev` rows that are *not* in `evals` or `final`. | n/a (this *is* the training corpus). Contamination CI: `stage1_train ∩ eval_hashes = ∅`. |
| `stage2` | `data/stage2/` | Supervised / instruction / preference / tiny task-tuning artifacts: `stage2_manifest.parquet`, `stage2.jsonl.gz` (bidirectional pairs + retention slice), `templates.json`. Populated only when Stage-2 sources exist; absent otherwise. | n/a. Contamination CI: `stage2_train ∩ eval_hashes = ∅` (pair, en-side, haw-side). |
| `final` | `data/final/` | **Major-milestone holdout eval data** — protected, accessed sparingly. FineWeb-2 `haw_Latn` test holdout split, milestone anchors (e.g., `global-piqa-parallel`, held-out Tatoeba), and any future major-milestone probe sets. Used at Stage 1 / Stage 2 gates and end-of-run evaluation per [`eval_pipeline.md`](./eval_pipeline.md) §2, not on every checkpoint. | **Yes — strictly never train.** Hashes are appended to the same `data/evals/eval_hashes.parquet` ledger before any train ingest, with `origin=<source>, stage=eval-only, division=final`. Treated like `evals` for contamination; access discipline is what differentiates it. |

Posture reminders:

- **This is private prototype / learning work.** No `data/` artifact in any of the four divisions is shared externally; the publication CI gate refuses any external emit of pipeline artifacts regardless of division (see [Prototype scope](#prototype-scope)). `final` is **not** a release / shipping bucket and never has been — it is the eval division reserved for milestone-grade holdouts.
- **`evals` ∪ `final` is the held-out boundary.** Any artifact landing in `data/evals/` or `data/final/` is hashed into `data/evals/eval_hashes.parquet` before any train ingest reads it. Train candidates are deduped against `eval_hashes.parquet` (exact-hash; cluster-aware split isolation handles near-dups). The invariant `train ∩ eval_hashes = ∅` covers both divisions.
- **`evals` vs `final` is an access-discipline distinction, not a contamination distinction.** Both are off-limits to training. The harness reads `evals` on every checkpoint; it reads `final` only at gates and milestones, so milestone numbers can't drift from accidental tuning against them.
- **Raw and intermediate data stays out of these divisions.** `data/raw/` (immutable fetched bytes) and `data/extracted/` (pre-manifest text) remain as today; they are inputs to `stage1` / `stage2` / `evals` / `final`, not divisions of the taxonomy.
- **Nothing under `data/` is committed to git.** Only schemas, templates, URL inventories, and these docs live in-repo. The `/data/` `.gitignore` rule covers all four divisions.

---

## Cross-stage invariants

These hold for both stages and are not negotiable per-source:

1. **Provenance manifest is the corpus.** Raw blobs are never the primary artifact. Each stage emits a Parquet manifest, one row per surviving doc/pair, with SHA-256 keys, fetch metadata, observed license, register, dedup cluster, and split.
2. **No license inference.** `license_observed` is what the source declared. `license_inferred` is always `null`. If we don't know, we don't guess.
3. **Unicode policy.** NFC throughout. ʻokina canonicalized to **U+02BB**; kahakō preserved as precomposed NFC (`ā` = U+0101, etc.). Apostrophe disambiguation across `'` (U+0027), `‘` (U+2018), `’` (U+2019), `ʻ` (U+02BB), `ʼ` (U+02BC) is context-aware — between/before vowels in Hawaiian context → ʻokina; English contractions are left alone.
4. **Raw archive is immutable, SHA-256 keyed, and not in git.** Storage location TBD (open team gap).
5. **`eval_hashes.parquet` is the contamination ledger.** Lives at `data/evals/eval_hashes.parquet`. Accumulates every held-out hash from **both `data/evals/` (cheap, frequent) and `data/final/` (major-milestone holdout)** — Stage-1 dev/test, Stage-2 dev/test (pair, en-side, haw-side independently), FineWeb-2 `haw_Latn` test dev (in `evals`) and holdout (in `final`), W1 manual micro-eval, milestone anchors like `global-piqa-parallel`, and any other eval anchor — *before* train ingest reads it. CI assertion: `train ∩ eval_hashes = ∅`. **Never train on rows in `data/evals/` or `data/final/`.**
6. **Cluster-aware split isolation.** Any near-dup cluster touching dev/test is fully held out from train. MinHash clusters are recorded in the manifest, not recomputed at split time.
7. **Hard-escalate categories are deny-by-default with an allow-list per source category** — never auto-ingested via deny-list filtering.
8. **Reproducibility:** every model dependency in the pipeline (LID model, OCR engine + lang data, embedding aligner) is recorded with name + version/hash in the manifest row that consumed it.

---

## Storage formats

One format per layer, chosen so the raw fetch is replayable, the manifests are the queryable source of truth, and the trainer eats line-delimited JSON. Nothing in `data/` is committed to git; only the URL inventory and schemas live in-repo.

| Layer | Format | Path (off-git unless noted) | Why |
|---|---|---|---|
| **URL inventory** (input contract) | JSON, in git | `data-sources/hawaiian-data-sources.json` | Hand-curated source list adapters consume. Small, diffable, reviewable. One entry per source/URL with `source_id`, `url`, `tier`, `expected_license_observed`, `tos_url`, `notes`. |
| **Raw fetch — web/HTML** | WARC (`.warc.gz`) | `data/raw/{source}/{fetch_date}/*.warc.gz` | `warcio`/`scrapy-warc` preserve request + response + headers + ToS snapshot in one immutable blob. SHA-256 of the WARC is the provenance key. |
| **Raw fetch — non-HTML originals** (PDFs, dump tars, TSVs from Tatoeba/global-piqa, IA items) | Native bytes, untouched | `data/raw/{source}/{fetch_date}/{sha256}.{ext}` | Don't transcode at fetch time. Sidecar `fetch.jsonl` (one line per fetched object) records `source_url`, `fetch_date`, `http_status`, `sha256_raw`, `tos_snapshot_id`, `content_type`. |
| **Extraction / intermediate text** | Gzipped JSONL (`.jsonl.gz`), one record per doc or per page | `data/extracted/{source}/{fetch_date}/*.jsonl.gz` | Streamable, append-friendly, language-agnostic. Schema: `{doc_id, sha256_raw, text, extraction_method, ocr_confidence_mean?, page_no?, source_url, fetch_date}`. OCR output lives here with confidences attached. |
| **Stage 1 manifest** | Parquet (zstd) | `data/stage1/stage1_manifest.parquet` | Columnar, compresses well, queryable with DuckDB/pandas. One row per surviving doc. Schema in [Stage 1 manifest](#stage-1-manifest-schema). |
| **Stage 1 training text** | Gzipped JSONL | `data/stage1/stage1.jsonl.gz` | Trainer-friendly. One example per line: `{doc_id, text, source, register, split, prototype_only}`. Manifest fields stay out of the line so the model can't memorize them. |
| **Stage 1 packed/tokenized** | Packed `.bin` (or `.npy`) + sidecar `index.json` | `data/stage1/packed/` | Produced after Rusty's tokenizer audit. Sidecar records tokenizer name + hash, doc-boundary offsets, and the source `stage1.jsonl.gz` SHA-256. |
| **Stage 2 manifest** | Parquet (zstd) | `data/stage2/stage2_manifest.parquet` | One row per canonical pair. Schema in [Stage 2 manifest](#stage-2-manifest-schema). |
| **Stage 2 training text** | Gzipped JSONL | `data/stage2/stage2.jsonl.gz` | One canonical pair → two directional rows (`en→haw`, `haw→en`) plus the 10–20% Hawaiian-mono retention slice rows in the same file. Instruction templates live separately in `data/stage2/templates.json`; the JSONL records the *resolved* instruction. |
| **Evals — contamination ledger** | Parquet (zstd) | `data/evals/eval_hashes.parquet` | Small, append-mostly. Schema: `sha256_normalized, origin, stage, division` (and for Stage 2: `sha256_pair`, `sha256_en`, `sha256_haw`). Covers both `evals` and `final` held-out divisions. Both dataloaders import it and assert empty intersection with their training shards. |
| **Evals — cheap held-out anchors** | Parquet / TSV (off-git) | `data/evals/fineweb2_haw_test/dev/`, `data/evals/manual_w1/w1-haw-micro-eval.tsv`, `data/evals/<other-cheap-anchor>/` | One sub-dir per cheap-cadence held-out source. Hashed into `eval_hashes.parquet` with `origin=<source>, stage=eval-only, division=evals` *before* any train ingest. Read on every checkpoint; never read by Stage-1/Stage-2 training loaders. |
| **Final — major-milestone holdout anchors** | Parquet / TSV (off-git) | `data/final/fineweb2_haw_holdout/`, `data/final/global_piqa_parallel/`, `data/final/<other-milestone-anchor>/` | One sub-dir per milestone-cadence held-out source. Hashed into the same `data/evals/eval_hashes.parquet` ledger with `origin=<source>, stage=eval-only, division=final` *before* any train ingest. Read only at stage gates / candidate-checkpoint promotion / end-of-run eval per [`eval_pipeline.md`](./eval_pipeline.md) §2. Never read by training loaders. |
| **Schemas & docs** | JSON Schema + Markdown, in git | `docs/schemas/*.json`, this doc | Schemas are the contract; data files are disposable. |

Format rules:

- **Parquet for manifests / hashes**, JSONL for trainer-facing text. Don't mix: a manifest is a query target; a JSONL is a stream.
- **Gzip (`.jsonl.gz`) over uncompressed** for any text artifact larger than a few MB. Zstd for Parquet.
- **One file per (source, fetch_date)** at the raw and extracted layers — never append across fetches. Re-fetches produce a new directory; the manifest points at the specific `sha256_raw`.
- **No CSV** for anything past bootstrap. Quoting/encoding bugs eat Hawaiian diacritics. The `.csv` bootstrap path in the prototype-manifest ADR is for first-day scaffolding only; promote to Parquet as soon as the validator runs.
- **Hashes are the join keys.** `sha256_raw`, `sha256_clean`, `sha256_pair` — every cross-layer link goes through a hash, never a path.

---

## Stage 1 — Monolingual Hawaiian (DAPT/CPT)

**Goal:** maximize Hawaiian-language tokens with reasonable register diversity, within prototype posture. Realistic clean yield is **likely <50M tokens, possibly <10M**. Plan accordingly.

### Stage 1 source tiers

#### Tier A — High value, prototype-usable

| Source                                             | What                                    | Notes                                                                                                                                     |
| -------------------------------------------------- | --------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| **Ulukau — Hawaiian-language newspapers (nūpepa)** | ~1834–1948 OCR'd newspapers             | Largest Hawaiian text trove. OCR noise heavy pre-1900. Pre-1925 bulk kept private (prototype-only) per prior ADR. ToS snapshot per fetch. |
| **Ulukau — dictionaries / readers / Baibala**      | Pukui-Elbert, Andrews, Baibala Hemolele | Useful but narrow register.                                                                                                               |
| **Hawaiian Wikipedia (`hawwiki`)**                 | Modern encyclopedic                     | Small (few thousand articles). CC BY-SA 4.0 dump — cleanest licensing posture among candidate sources.                                    |
| **Hawaiian Wikisource**                            | Public-domain Hawaiian texts            | Smaller than nūpepa, cleaner text.                                                                                                        |

#### Tier B — Useful, narrow register

| Source | What | Notes |
|---|---|---|
| **Hawaiian Bible (Baibala Hemolele)** | Multiple editions | Mainly a Stage-2 asset. In Stage 1, **cap ≤10% of tokens**, tag `register=religious-archaic`. |
| **Government / educational PDFs** | OHA, DOE Kaiapuni, UH | Mixed rights; manual per-doc review. |
| **Awaiaulu / kūpuna translation outputs** | Modern Hawaiian prose (where public) | High quality, low volume. |

#### Tier C — Pointers

Hugging Face / GitHub / Kaggle artifacts tagged Hawaiian: treat each as a *pointer* to its original source. Re-derive provenance from the source. **HF metadata is not license truth.**

#### Tier D — Avoid for Stage 1

- Generic CommonCrawl filtered by language ID (Hawaiian recall poor; Pidgin / English-with-loanwords FP rate high).
- Social media / forum content without explicit permission.
- mele / oli / pule, moʻolelo from named tradition-bearers, moʻokūʻauhau — hard-escalate, strip if found.

### Stage 1 transformation pipeline

```
[crawl/download]                 per-source adapters; emit raw bytes + fetch metadata + ToS snapshot
        ↓
[raw archive]                    immutable, SHA-256 keyed, not in git
        ↓
[extraction / OCR]               PDF→text, HTML→text, image→OCR (Tesseract haw); record OCR confidence
        ↓
[language ID]                    cld3 / fasttext-lid; gate at doc AND paragraph level
        ↓
[Unicode normalization]          NFC; ʻokina → U+02BB; kahakō preserved
        ↓
[boilerplate removal]            headers/footers, page numbers, OCR gutter junk, nav, license footers
        ↓
[paragraph / sentence segmentation]   Hawaiian-aware; do not apply English heuristics
        ↓
[dedup / minhash]                exact + MinHash near-dup; cluster IDs persisted
        ↓
[quality filters]                min length, max symbol/digit ratio, min Hawaiian-char ratio,
                                 optional perplexity filter (kahakō/ʻokina presence is a positive signal)
        ↓
[register / cultural tags]       news | religious | encyclopedic | educational | unknown
        ↓
[split isolation]                cluster-aware; held out from Stage-2 eval hashes too
        ↓
[manifest write]                 stage1_manifest.parquet (one row per surviving doc)
        ↓
[packed JSONL → tokenized]       canonical pre-tokenization JSONL; packed .bin/.npy + sidecar index after
```

Notes:
- Paragraph-level LID catches mixed nūpepa pages (Hawaiian article next to English ad).
- For the first prototype run, retain a debug column with the original apostrophe codepoint per doc; canonicalize for training.
- OCR-confidence filter is a sample gate: low-confidence pages still get manifested but flagged for review before packing.

### Stage 1 manifest schema

`stage1_manifest.parquet` — one row per surviving doc. Default `prototype_only=true`.

| Field | Type | Notes |
|---|---|---|
| `doc_id` | string | stable hash-derived |
| `source` | string | `ulukau-nupepa` \| `hawwiki` \| `wikisource-haw` \| `bible-{edition}` \| ... |
| `source_url` | string | |
| `fetch_date` | date | |
| `fetch_http_status` | int | |
| `sha256_raw` | string | |
| `sha256_clean` | string | post-normalization |
| `content_type` | string | `text/html` \| `application/pdf` \| `image/jpeg` |
| `extraction_method` | string | `native-text` \| `pdf-text` \| `ocr-tesseract-haw` \| `wiki-xml-stream` \| `wikisource-pagetext` |
| `ocr_confidence_mean` | float? | null if not OCR |
| `language_id` | string | `haw` expected |
| `language_id_confidence` | float | |
| `char_count` | int | |
| `token_count_est` | int | |
| `unicode_normalized` | bool | NFC + ʻokina canonicalized |
| `register_tag` | string | `news` \| `religious` \| `encyclopedic` \| `educational` \| `unknown` |
| `cultural_flag` | string | `none` \| `hard-escalate-{category}` |
| `dedup_cluster_id` | string | |
| `split` | string | `train` \| `dev` \| `test` \| `held-out` |
| `license_observed` | string | as stated by source; `unknown` allowed |
| `license_inferred` | null | always null |
| `prototype_only` | bool | default true |
| `notes` | string | |

### Stage 1 output JSONL

One example per line, canonical pre-tokenization artifact, round-trips from the manifest:

```json
{"doc_id":"ulukau-nupepa-kuokoa-1865-04-13-p2","text":"He nūpepa Hawaiʻi kēia ...","source":"ulukau-nupepa","register":"news","split":"train","prototype_only":true}
```

**Excluded from JSONL** (lives in the manifest, not the training text — otherwise the model memorizes it):
- License text, copyright notices, ToS boilerplate.
- Source URLs, fetch dates, manifest fields.
- HTML, page-number artifacts, OCR confidence markers.
- Hard-escalate cultural categories.
- Anything from dev/test splits.
- Mixed-language paragraphs that failed paragraph-level LID.

### Stage 1 contamination & eval guards

- `eval_hashes.parquet` accumulates Stage-1 dev/test `sha256_clean` hashes. CI assertion: `stage1_train ∩ eval_hashes = ∅`.
- Stage-1 dev/test hashes are also held out from any future Stage-2 train.
- Cluster-aware split isolation: a near-dup cluster touching dev/test is fully removed from train.
- Bible/religious-archaic share capped at ≤10% of tokens to limit register collapse.

### Stage 1 risks (ranked)

1. **Tiny corpus → overfitting / register collapse.** Document yield honestly; don't oversell DAPT improvements.
2. **Bible / register skew** — capped by source share, register distribution tracked in the manifest.
3. **Nūpepa OCR noise** — mean-confidence + char-ratio filters, manual sample review on the first batch.
4. **Apostrophe / diacritic chaos** — normalize before tokenizer training, audit before packing.
5. **English contamination** — paragraph-level LID, not just doc-level.
6. **Duplicate texts** (Bible reprints, nūpepa article reprints, Wikipedia mirrors) — cluster-aware MinHash dedup with split isolation.
7. **Eval contamination** — `eval_hashes.parquet` check is a CI assertion, not a suggestion.
8. **Accidental publication of prototype-tainted artifacts** — every artifact carries its prototype lineage; CI refuses to publish `prototype_only=true` lineage.
9. **Cultural overreach** — allow-list per source category, not deny-list.

### Stage 1 immediate next steps

1. **Land the adapter framework + empty manifest** (no data yet). Run the **Hawaiian Wikipedia dump** end-to-end — cleanest licensing posture, easiest to reason about. Output: `stage1_manifest.parquet` with real rows, packed JSONL, and a CI guard that refuses any external publication of pipeline artifacts (public sharing is out of scope for this prototype).
2. **Add the Ulukau nūpepa adapter** with ToS snapshot, polite fetch, OCR-confidence capture, paragraph-level LID, **manual review of ~50 random docs** before bulk ingest. Document register and OCR-quality stats per decade.
3. **Run a tokenizer audit + token-count report** across whatever corpus exists (Rusty owns the tokenizer; Linus supplies corpus + manifest stats). **This is the honest go/no-go gate for Stage 1** — decide whether DAPT is worth running or whether more sources are needed first. The Stage-1 builder enforces a mechanical version of this gate: train-token targets are **Conservative 2.5M / Base 4.5M / Upside 7M** (right-clearable monolingual Hawaiian); `scripts/301_build_stage1_dataset.py --strict` exits non-zero when train tokens fall below the conservative target, and `--show-targets` reports current gap without requiring a corpus pull.

#### Source-fetcher → Stage-1 builder handoff (downstream contract)

The 100-phase scripts are **source-specific** collection planners — one
per Hawaiian source — because each source has its own fetch shape and
metadata. The convention is `scripts/10X_collect_<source>.py` (Frank).
Active 100-phase scripts:

- `scripts/101_collect_hawwiki.py` — Hawaiian Wikipedia dump-plan metadata, input for `201`.
- `scripts/102_collect_hawwikisource.py` — Hawaiian Wikisource per-page fetch plan (`data/local/hawwikisource/page_plan.jsonl`), input for `202`.
- `scripts/103_collect_hawwiktionary.py` — Hawaiian Wiktionary dump-plan metadata, input for `201` (currently `blocked_upstream` per the plan's `blockers`).
- `scripts/104_collect_ulukau_nupepa.py` — Ulukau/Nupepa document-ID plan (`data/local/ulukau_nupepa/document_plan.jsonl`), input for `204`; prototype-only, rights-gated, and OCR/noise-gated.
- `scripts/105_collect_fineweb2_haw.py` — FineWeb-2 (`HuggingFaceFW/fineweb-2`) `haw_Latn` collection plan (`data/local/fineweb2_haw/collect_plan.json`), input for `205`. Records dataset coordinates, verified row counts (train 95,507 / test 887), parquet + datasets-server URLs, and ODC-By wrapper licence posture. **Now the primary verified Hawaiian web source for Stage 1**, superseding generic CommonCrawl; cleanup, paragraph-level LID re-gate, and MinHash dedup against `hawwiki` / `hawwikisource` happen downstream in 301, not here.

There is no longer a single broad `101_collect_rightslight.py` planner —
forcing every source through one schema lost too much per-source detail.
New sources land as new `10X_collect_*.py` scripts.

200-phase fetchers consume the corresponding 100-phase plans:

- `201_fetch_rightslight_raw.py` covers the Wikimedia **dump** path (`hawwiki`, `hawwiktionary`); inputs come from `101_collect_hawwiki.py` and `103_collect_hawwiktionary.py`.
- `202_fetch_hawwikisource_raw.py` covers Hawaiian **Wikisource** — per-page MediaWiki API page texts rather than a single bulk XML; its preferred input is the page plan emitted by `102_collect_hawwikisource.py` (consumed via `--page-plan`, default `data/local/hawwikisource/page_plan.jsonl`). Direct enumeration remains as a fallback when the plan is missing.
- `204_fetch_ulukau_nupepa_raw.py` covers **Ulukau/Nupepa** document HTML/OCR text candidates from `104`. It is dry-run by default, writes only local gitignored raw bytes, records actual extracted-text whitespace token counts, and fails loudly on Cloudflare/403 challenge pages instead of bypassing them. Until a legitimate bulk export/API or permissioned access path is available, this adapter is for seeded IDs or manually supplied HTML exports only.
- `205_fetch_fineweb2_haw_raw.py` covers **FineWeb-2 `haw_Latn`** rows from the plan emitted by `105`. Dry-run by default; `--execute --split {train,test} --limit N` actually fetches. Default fetch path is the HF `datasets-server` `/rows` JSON API (stdlib + `urllib`, polite paginated), with an opt-in `--use-parquet` path that streams the single parquet shard per split via `pyarrow` (not in `requirements.txt` — flag fails loudly if `pyarrow` is absent, since adding it is Linus's dependency call). Each fetched row is preserved verbatim — no cleanup — under `data/raw/fineweb2_haw/<YYYYMMDD>/<split>.jsonl` with in-row CC provenance (`source_url`, `cc_dump`, `cc_date`, `language_score`) plus a per-row `ProvenanceRecord` line in `data/raw/fineweb2_haw/fetch.jsonl`. Schema is checked against `per_row_schema.fields` from the 105 plan and missing/non-string `text` fails loudly. **English boilerplate inside Hawaiian-classified rows is expected** (FineWeb-2 LID flags whole rows; paragraph-level filtering is downstream in 301), so 205 reports actual raw whitespace token counts only and never claims cleaned tokens.

300-phase consumes 200-phase output:

- `310_split_dedupe_fineweb2_haw.py` — FineWeb-2 `haw_Latn` split/dedupe. Splits the official test split 70/30 into dev (→ `data/evals/fineweb2_haw/dev.jsonl`) vs holdout (→ `data/final/fineweb2_haw/holdout.jsonl`), dedupes train against the FULL test split (all 887 rows), and writes deduplicated train to `data/stage1/fineweb2_haw/train.jsonl`. Produces a manifest with row/token/char counts, split ratios, dedupe stats, deterministic seed, and the invariant `train ∩ eval_hashes = ∅`. Writes eval hashes to `data/evals/fineweb2_haw/eval_hashes.jsonl` (simple JSONL format with one hash + metadata per line).
- `301_build_stage1_dataset.py` reads the per-source `data/raw/<source>/fetch.jsonl` ledger.

To keep `301_build_stage1_dataset.py` source-agnostic, the Wikisource fetcher writes the **same `ProvenanceRecord` JSONL schema** to `data/raw/hawwikisource/fetch.jsonl`, and the builder dispatches by content shape:

- `extraction_method: wiki-xml-stream` — Wikimedia `<mediawiki>` dump (`.xml` / `.xml.bz2` / `.xml.gz`, used by `hawwiki` / `hawwiktionary`).
- `extraction_method: wikisource-pagetext` — per-page Hawaiian Wikisource artefacts under `data/raw/hawwikisource/<YYYYMMDD>/<sha>.<ext>`. Supported shapes:
  - plain text: `.txt` / `content_type: text/plain`,
  - raw wikitext: `.wiki` / `.wikitext` / `content_type: text/x-wiki` (run through the same crude de-wiki + ʻokina canonicalization as the dump path),
  - per-page MediaWiki API JSON (`.json`, either `action=parse` or `action=query&prop=revisions` payload),
  - bundled NDJSON: `.jsonl` / `.jsonl.gz` / `.ndjson` / `content_type: application/x-ndjson`, one page per line as `{"page_id":..., "title":..., "wikitext"|"text": ...}`.

Per-page identifiers (`page_id`, `title`, `revision_id`, `namespace`) ride in `source_specific_ids` on the provenance row for single-page artefacts and inline on each NDJSON line for bundles. The token-volume gate, ʻokina canonicalization, NFC pass, and deterministic split assignment are identical across both extractors — Wikisource pages are not special-cased downstream of extraction.

The Ulukau/Nupepa path is intentionally **not** part of the rights-light Wikimedia backbone. `104` records document candidates and the access/rights caveats; `204` can store raw HTML plus a visible-text extraction if the bytes are legitimately available. A Nupepa-specific 300-phase cleaner is still required before any nūpepa OCR is packed for training, because raw page text can contain OCR noise, boilerplate, English ads, issue navigation, and item-level rights ambiguity.

The FineWeb-2 path (`105` / `205`) is the **primary verified web source** for Stage 1 monolingual Hawaiian text and supersedes the previously-considered generic CommonCrawl/CC-100 path (CC-100 has no `haw`). It is *not* yet a "clean" source: rows classified Hawaiian by FineWeb-2's LID can still contain English boilerplate, navigation, ads, and per-URL third-party rights distinct from the ODC-By wrapper licence. Cleanup, paragraph-level LID re-gating, ʻokina/kahakō density gates, MinHash dedup against `hawwiki`/`hawwikisource`, and per-source-URL rights review (Linus) all happen downstream of 205 — `301_build_stage1_dataset.py` is the gate, not the fetcher.

---

## Stage 2 — Bidirectional en↔haw SFT

**Goal:** maximize *true parallel* en↔haw sentence pairs; accept *comparable* with alignment scoring; treat *synthetic* as last-resort and capped. Realistic clean yield is **likely <50k pairs, possibly <10k**.

Stage 2 trains both directions from the same canonical pair (one manifest row → two directional examples), with target-only loss and a 10–20% Stage-1-style monolingual Hawaiian retention slice mixed in by token.

### Stage 2 source tiers

#### Tier A — True parallel, prototype-usable

| Source | Type | Notes |
|---|---|---|
| **Baibala Hemolele ↔ English Bible (matched edition pair)** | Verse-aligned | Largest reliable parallel. **Verse-level only** — chapter-level is unsafe across editions. Pin a Hawaiian edition (translator/year) and a public-domain English edition (KJV/ASV). **Cap ≤30% of parallel-train tokens, 0% of dev/test.** |
| **Held-out non-Bible eval slices** (`global-piqa-parallel`, held-out Tatoeba, Taxi1500 diagnostics) | Sentence-aligned / classification-style | FLORES/FLORES+ do **not** currently provide Hawaiian, so do not plan on `hawn_Latn` as a dev/test anchor. Hash any selected held-out eval sentences into `eval_hashes.parquet` *before* anything else ingests. **Never train on held-out eval rows.** |
| **OPUS — `haw` filtered subsets** (Tatoeba, QED, Ubuntu, GNOME, KDE) | Sentence-aligned | Most are tiny. JW300 **excluded** unless ToS re-verified. Software-l10n sets are domain-skewed; tag `register=software-l10n`, cap. |
| **NLLB-Seed / NLLB mined `haw`-`eng`** | Mined parallel (comparable, not gold) | Train signal only, **never dev/test**. Re-derive provenance from origin URLs, not the HF mirror. |
| **Tatoeba `haw`↔`eng`** | Sentence-aligned | Hundreds of pairs, CC-BY 2.0 FR. Hash before deciding train vs dev. |

#### Tier B — Comparable / weakly aligned (alignment scoring required)

| Source | Type | Notes |
|---|---|---|
| **Hawaiian ↔ English Wikipedia (interlanguage links)** | Comparable docs | Topically aligned, not sentence-aligned. Sentence-align with LaBSE/LASER + similarity threshold. Expect <5k usable pairs. CC BY-SA 4.0 — cleanest licensing posture among comparable sources. |
| **Hawaiian ↔ English Wikisource** | Comparable | Per-text manual check; volume small. |
| **Awaiaulu / kūpuna translations (where public)** | Document-level parallel | High-quality modern prose; rights mixed. |
| **OHA / DOE Kaiapuni / UH bilingual publications** | Document-level parallel | Side-by-side or sequential PDFs; sentence alignment needed. |
| **Ulukau bilingual / annotated texts** | Mixed | Per-item ToS snapshot. |

#### Tier C — Dictionary / glossary derived

- Pukui-Elbert / Andrews **example-sentence fields** → short pairs. Headword-only entries are **not** training pairs. Tag `register=dictionary-example`, cap, exclude from dev/test.
- Glossary CSVs: same posture.

#### Tier D — Synthetic / back-translation

- **Back-translation** of Stage-1 monolingual via the Stage-1-merged base: ≤25% train cap, **0% dev/test**, `synthetic=true`, `synthetic_source_model` recorded. Source-model ToS for derivatives must permit use.
- **Forward-translation** of clean English via external MT: same caps; additional translationese risk — keep ≤10% inside the 25% cap.
- Dictionary-templated synthesis ("The word X means Y"): **excluded** — teaches templates, not translation.

#### Tier E — Excluded for Stage 2 prototype

- Hard-escalate cultural categories (unchanged from Stage 1).
- Any pair where one side is auto-MT and not flagged synthetic.
- JW300 / proselytizing-org bitext unless ToS re-verified.
- Social-media / forum bilingual posts without explicit permission.
- LLM-generated "synthetic Hawaiian dialogues" not grounded in a source pair.

#### Required tagging — parallel vs comparable vs synthetic

Every pair carries `alignment_type ∈ {parallel-verse, parallel-sentence, parallel-doc, comparable-aligned, dictionary-example, synthetic-bt, synthetic-ft}`. **Dev/test only accepts `parallel-*`.**

### Stage 2 transformation pipeline

```
[crawl/download per source]      adapters per source; raw bytes + fetch metadata + ToS snapshot
        ↓
[raw archive]                    immutable, SHA-256 keyed, not in git
        ↓
[extraction]                     TMX / JSON / TSV / verse-keyed text / HTML / PDF (+ OCR)
        ↓
[per-side text isolation]        split into (en_raw, haw_raw) with stable record_id
        ↓
[per-language normalization]
   en:  NFC, smart-quote → ASCII where safe, whitespace collapse, strip page-number/boilerplate
   haw: NFC, ʻokina → U+02BB, kahakō precomposed NFC, apostrophe disambiguation per Stage 1
        ↓
[sentence segmentation per side] language-aware; verse-keyed Bible skips splitter (verse = boundary)
        ↓
[document-level alignment]       only for Tier B: interlanguage-link / filename / verse-ID
        ↓
[sentence-level alignment]       deterministic where possible (verse ID, TMX line index);
                                 LaBSE/LASER for comparable docs
        ↓
[alignment scoring]              cosine score persisted; threshold gate (default 0.75 LaBSE, tunable);
                                 below threshold → alignment_review_required=true, excluded from train
        ↓
[language ID both sides]         reject pairs where en-side ≠ eng or haw-side ≠ haw (catches swap, code-mix)
        ↓
[length-ratio filter]            haw/en char-ratio in [0.5, 2.0] default; tune on Bible distribution
        ↓
[duplicate filters]              exact pair-hash dedup; MinHash near-dup on concatenated (en||haw);
                                 cluster IDs persisted; cluster-aware split isolation
        ↓
[register / source tags]         religious | software-l10n | encyclopedic | educational | news |
                                 dictionary-example | unknown
        ↓
[contamination checks]           (a) ∩ eval_hashes.parquet (Stage-1 + Stage-2 held-out)
                                 (b) ∩ Stage-1 train doc hashes → crosslink_stage1_overlap flag
                                 (c) within-Stage-2 train ↔ dev/test hash check
        ↓
[train / dev / test split]       cluster-aware; held-out non-Bible eval slices become dev/test by default
        ↓
[manifest write]                 stage2_manifest.parquet (one row per pair)
        ↓
[bidirectional JSONL emission]   one pair → two directional SFT examples (en→haw, haw→en);
                                 plus retention-slice monolingual Hawaiian (10–20% by token)
```

Notes:
- Verse-aligned Bible skips embedding alignment entirely; trust verse ID, sanity-check length ratio + LID.
- Embedding aligner (LaBSE/LASER) is a model dependency — record `alignment_model` name + hash per row.
- Alignment threshold is the highest-leverage knob. Bake the score **per row**, not per run, so we can re-filter without re-aligning.
- Cross-stage hash check is non-negotiable: any Stage-2 train pair whose Hawaiian side hashes match a Stage-1 train doc gets `crosslink_stage1_overlap=true`. Allowed in train, **banned from dev/test**.

### Stage 2 manifest schema

`stage2_manifest.parquet` — one row per pair. Default `prototype_only=true`.

| Field | Type | Notes |
|---|---|---|
| `pair_id` | string | stable hash-derived |
| `source` | string | `bible-{ed}` \| `global-piqa` \| `taxi1500` \| `tatoeba` \| `opus-{subset}` \| `nllb-mined` \| `wiki-aligned` \| `bt-stage1` \| ... |
| `source_url_en`, `source_url_haw` | string | |
| `fetch_date` | date | |
| `sha256_en_raw`, `sha256_haw_raw` | string | |
| `sha256_en_clean`, `sha256_haw_clean` | string | |
| `sha256_pair` | string | `hash(sha256_en_clean ‖ sha256_haw_clean)` — primary contamination key |
| `record_id_en`, `record_id_haw` | string | e.g., `Ioane 3:16`, TMX `<tu>` id, line index |
| `alignment_type` | string | `parallel-verse` \| `parallel-sentence` \| `parallel-doc` \| `comparable-aligned` \| `dictionary-example` \| `synthetic-bt` \| `synthetic-ft` |
| `alignment_method` | string | `verse-id` \| `tmx-line` \| `filename-pair` \| `laser` \| `labse` \| `manual` |
| `alignment_model` | string? | e.g., `LaBSE@<sha>`; null for deterministic methods |
| `alignment_score` | float? | cosine; null for deterministic |
| `length_ratio_haw_over_en` | float | |
| `lang_id_en`, `lang_id_en_confidence` | string, float | |
| `lang_id_haw`, `lang_id_haw_confidence` | string, float | |
| `direction_original` | string | `en->haw` \| `haw->en` \| `unknown` (which side is the human source) |
| `register` | string | `religious` \| `software-l10n` \| `encyclopedic` \| `educational` \| `news` \| `dictionary-example` \| `unknown` |
| `edition_or_version` | string? | e.g., `Baibala Hemolele 1868 (Andrews/Bingham)`, `global-piqa-parallel snapshot` |
| `synthetic` | bool | default false |
| `synthetic_source_model` | string? | required iff `synthetic=true` |
| `license_observed_en`, `license_observed_haw` | string | as stated; `unknown` allowed |
| `license_inferred` | null | always null |
| `tos_snapshot_id` | string? | for scrape-sourced data |
| `prototype_only` | bool | default true |
| `dedup_cluster_id` | string | |
| `crosslink_stage1_overlap` | bool | true if haw side hashes match Stage-1 train doc |
| `alignment_review_required` | bool | true if score below threshold |
| `split` | string | `train` \| `dev` \| `test` \| `held-out` \| `review-pending` |
| `notes` | string | |

### Stage 2 output JSONL

Bidirectional SFT, **target-only loss**: prompt + source segment contribute zero loss. One canonical pair → two directional examples (materialized to JSONL or expanded at load).

**en→haw:**

```json
{
  "example_id": "bible-ioane-3-16:en2haw",
  "pair_id": "bible-ioane-3-16",
  "direction": "en->haw",
  "instruction": "Translate the following English sentence into Hawaiian.",
  "source_lang": "en",
  "target_lang": "haw",
  "source_text": "For God so loved the world ...",
  "target_text": "No ka mea, ua aloha nui mai ke Akua i ko ke ao nei ...",
  "loss_mask": "target_only",
  "register": "religious",
  "alignment_type": "parallel-verse",
  "synthetic": false,
  "split": "train",
  "prototype_only": true
}
```

**haw→en (same pair, opposite direction):**

```json
{
  "example_id": "bible-ioane-3-16:haw2en",
  "pair_id": "bible-ioane-3-16",
  "direction": "haw->en",
  "instruction": "Unuhi i kēia ʻōlelo Pelekānia mai ka ʻōlelo Hawaiʻi.",
  "source_lang": "haw",
  "target_lang": "en",
  "source_text": "No ka mea, ua aloha nui mai ke Akua i ko ke ao nei ...",
  "target_text": "For God so loved the world ...",
  "loss_mask": "target_only",
  "register": "religious",
  "alignment_type": "parallel-verse",
  "synthetic": false,
  "split": "train",
  "prototype_only": true
}
```

**Retention slice (monolingual Hawaiian, 10–20% by token, mixed in same file):**

```json
{
  "example_id": "ulukau-nupepa-kuokoa-1865-04-13-p2:retention",
  "pair_id": null,
  "direction": "haw-mono",
  "instruction": null,
  "source_lang": null,
  "target_lang": "haw",
  "source_text": null,
  "target_text": "He nūpepa Hawaiʻi kēia ...",
  "loss_mask": "all_target",
  "register": "news",
  "alignment_type": null,
  "synthetic": false,
  "split": "train",
  "prototype_only": true
}
```

Notes:
- `direction` and `loss_mask` are **explicit** in every row — the trainer reads them, never infers.
- `haw-mono` retention rows compute loss over the full `target_text` (causal-LM, same as Stage 1).
- Instruction templates are swappable (~5 paraphrases per direction) to prevent the model from latching on a single prompt string. Templates live in `templates.json`; the JSONL records the *resolved* instruction for reproducibility.
- A Hawaiian-language instruction in `haw->en` is intentional — Hawaiian instruction-framing is part of the point. Fallback to English-only instructions if it underperforms.

**Excluded from Stage-2 JSONL:**
- Instructions / prompts inside `target_text`. Target is the translation, period.
- Source leakage (`target_text` near-copying `source_text` — common in noisy comparable data).
- Below-threshold alignments (`alignment_review_required=true`).
- Bible verse duplicates / reprints across editions (cluster-isolated dedup).
- Any row in `eval_hashes.parquet`.
- Stage-1 eval-hash overlaps on the Hawaiian side.
- Hard-escalate cultural categories.
- Mixed-language sentences that failed per-side LID.
- Boilerplate (copyright, "Translated by ...", chapter headers, page numbers, TMX metadata, license footers).
- URL / dataset-name strings on either side.
- Auto-MT outputs not flagged `synthetic=true`.
- Dictionary headword-only rows.
- `direction_original=unknown` AND `alignment_type=comparable-aligned` at low scores.

### Stage 2 contamination & eval guards

`eval_hashes.parquet` accumulates, for Stage 2:
- Every Stage-2 dev/test `sha256_pair`.
- Every Stage-2 dev/test `sha256_haw_clean` and `sha256_en_clean` **independently** — a sentence reused on the other side still counts.
- Every Stage-1 dev/test hash (carried forward).

CI assertions (mechanical, pre-pack):
1. `stage2_train_pairs ∩ eval_hashes = ∅` (pair, en-side, haw-side).
2. `stage2_train ∩ stage1_eval_hashes = ∅` on the haw side.
3. `crosslink_stage1_overlap=true` rows are allowed in train, **banned from dev/test**.
4. Cluster-aware split isolation passes.
5. **Lineage gate:** any artifact whose lineage contains `prototype_only=true` rows is refused for publication.

Backup: n-gram overlap audit between train and dev/test as a sanity check (small parallel corpora can otherwise be memorized verbatim).

### Stage 2 risks (ranked)

1. **Bible / register skew.** Uncapped, the model translates everything as 19th-century scripture. ≤30% parallel-train tokens, 0% dev/test, register-balanced eval probe.
2. **Verse alignment ≠ modern-prose alignment.** Verse pairs are short, archaic, structurally biased. Mix in non-Bible parallel; held-out non-Bible tests from global-piqa/Tatoeba-style sources are the honest gauge.
3. **Tiny parallel corpus → overfitting & memorization.** Likely <50k pairs, possibly <10k. Cap epochs (already in ADR), early-stop on chrF, dev/test from a separate source distribution.
4. **Translationese & synthetic feedback loops.** BT through Stage-1-merged base re-injects its biases. Cap ≤25%, 0% dev/test; **prefer BT over forward-translation** (BT noise lives on the source side, which is masked from loss).
5. **OCR'd parallel PDFs with bad alignment.** Layout-based alignment fails on column shifts/footnotes. Default: hold for review.
6. **English contamination in Hawaiian targets.** Wikipedia-aligned and software-l10n pairs leave untranslated English tokens. LID + token-level English-ratio filter on the target side.
7. **Memorization of small held-out sets.** Aggressive eval-hash guard + n-gram overlap audit.
8. **Direction-confused training.** Without explicit direction tags or with leaky instruction templates, both directions fuse into a noisy mid-pidgin. Explicit `direction` + target-only loss + per-direction eval (never averaged).
9. **Accidental publication of prototype-tainted artifacts.** CI lineage gate, same as Stage 1.
10. **Cross-stage contamination.** `crosslink_stage1_overlap` flag + eval-hash union — not optional.
11. **Unbalanced direction representation.** Track `direction_original` distribution; report in the run card.
12. **Cultural overreach via translation outputs.** Even on "safe" data, the model may produce ceremonial-register Hawaiian. Model card states not-fit-for-ceremonial-use; cultural-review owner still unassigned.

### Stage 2 immediate next steps

*Sequence after Stage 1 lands:*

1. **Land the Stage-2 adapter framework + empty `stage2_manifest.parquet`** (no parallel data yet). Select and ingest a small held-out Hawaiian eval anchor from verified sources such as `global-piqa-parallel` or held-out Tatoeba; use Taxi1500 only as a diagnostic because of its Bible/classification shape. FLORES/FLORES+ currently has no Hawaiian config. Hash all held-out eval sentences into `eval_hashes.parquet` *before* anything else. Wire the contamination CI assertions.
2. **Add the Bible verse-aligned adapter** (one pinned Hawaiian edition + one public-domain English edition). Verse-ID alignment is deterministic. Apply the Bible token cap, register tag, cluster-isolated dedup. After this step, count parallel-train tokens; if Bible share > cap, **sample down rather than gathering more Bible**.
3. **Add Tatoeba + one Wikipedia-aligned slice** (LaBSE-aligned, conservative threshold, `alignment_review_required=true` on borderline rows). Run the bidirectional JSONL emission with the 10–20% retention slice from the Stage-1 corpus. Output: a tiny prototype Stage-2 dataset (target ~5–20k clean pairs + retention) and a register/direction distribution report. **This is the honest go/no-go gate for Stage 2** — fails loudly without burning GPU credits if the parallel count is too low or Bible-dominated even after capping.

---

## Open team gaps

These block specific promotions; the pipeline can still land scaffolding around them.

- **Cultural review owner unassigned.** Hard-escalate categories cannot be promoted out of exclusion without this. Affects what register-tags can move out of `hard-escalate` status even for prototype use. Flagged to Coordinator.
- **Hawaiian-literate alignment spot-checker** for LaBSE/LASER threshold tuning — needed before any comparable-source ingest is trusted in Stage 2.
- **Bible edition rights confirmation** — needs a human decision on which Hawaiian + English editions we use; record once, pin per row.
- **Storage location for raw archive** — not in git. Local-only? Cheap blob? Livingston should weigh in on cost. Same answer for Stage 1 and Stage 2.

— Linus
