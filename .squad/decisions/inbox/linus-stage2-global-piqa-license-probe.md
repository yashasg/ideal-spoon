# Linus Stage-2 Round 9 license probe — Global-PIQA haw_Latn

Date: 2026-05-03  
Scope: license-first Hugging Face metadata probe only; no TSV/raw dataset download.

## Source name + canonical URLs

Source: Global PIQA Parallel, Hawaiian Latin-script configuration.

Canonical URLs:

- Dataset card: <https://huggingface.co/datasets/mrlbenchmarks/global-piqa-parallel>
- Raw card metadata: <https://huggingface.co/datasets/mrlbenchmarks/global-piqa-parallel/raw/main/README.md>
- HF dataset API: <https://huggingface.co/api/datasets/mrlbenchmarks/global-piqa-parallel>
- Dataset-server metadata: <https://datasets-server.huggingface.co/splits?dataset=mrlbenchmarks/global-piqa-parallel&config=haw_latn>
- File listed by card/API: `data/parallel_haw_latn.tsv`
- Repository commit observed from HF metadata/download checksums elsewhere in the dataset-server response: `a350910e9cfc8b0b57cb55aa8261780deabb6568`.

## License / dataset-card quotes

Verbatim dataset card/API license fields:

> `license: cc-by-sa-4.0`

> `cardData license: cc-by-sa-4.0`

Verbatim dataset card license section:

> "Global PIQA is released under a [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.en) license. However, we do <b>not</b> allow training of AI systems on Global PIQA, or on synthetic data that uses Global PIQA as a seed."

> "Global PIQA is intended for LLM evaluation only."

Dataset card description of construction:

> "In the parallel split, each example was machine-translated from English, then manually corrected by a native speaker of the target language."

## Robots.txt status

- `https://huggingface.co/robots.txt`: `User-agent: *` and `Allow: /`.
- `https://datasets-server.huggingface.co/robots.txt`: returned 404 (no robots.txt found). Treat as no robots restriction found for metadata endpoints, but keep access minimal.

## Access method

Allowed next-round access method is metadata/eval-only HF access, no auth:

1. Use HF dataset API/card to pin repo id, commit SHA, license, and file path.
2. Use datasets-server metadata endpoints for splits/schema where available.
3. If building the eval ledger, fetch only `data/parallel_haw_latn.tsv` once after recording the no-training license restriction; hash rows into `data/evals`/`data/final` ledger before any train ingest.
4. Do **not** use `load_dataset()` in training code or any train candidate adapter.

## Rate-limit guidance

HF API response headers from the dataset API:

- `RateLimit: "api";r=499;t=240`
- `RateLimit-Policy: "fixed window";"api";q=500;w=300`

Use the user-mandated polite User-Agent and at least 2 seconds between requests. A next-round eval adapter should need one API/card request plus one raw TSV GET if approved.

## Schema and row-count findings

Config/split from card and dataset-server:

- `config_name: haw_latn`
- split: `test`
- file path: `data/parallel_haw_latn.tsv`

Field schema from dataset-server preview metadata:

| Field | Type |
|---|---|
| `prompt` | string |
| `solution0` | string |
| `solution1` | string |
| `solution2` | string |
| `solution3` | string |
| `label` | int64 |
| `language` | string |
| `eng_prompt` | string |
| `eng_solution0` | string |
| `eng_solution1` | string |
| `eng_solution2` | string |
| `eng_solution3` | string |
| `categories` | string |
| `example_id` | string |
| `supplement` | string |

Row count: **103 test examples** for `haw_Latn`/`haw_latn` is the operational count to plan around. Caveat: the direct `datasets-server /size?dataset=...&config=haw_latn` endpoint returned 500 and the all-config `/info` response did not include `haw_latn`, so this count is inferred from the dataset-server size pattern for cached Global-PIQA parallel configs (103 rows/config) and from the preview endpoint showing the `haw_latn` test split. Confirm by counting TSV lines only in the next round if proceeding with eval-ledger ingestion.

## Verdict

**YELLOW — EVAL-only; do not train.**

Reasoning:

- Dataset is public on HF and the card/API license is explicit (`cc-by-sa-4.0`).
- The dataset card adds an explicit no-training restriction: "we do not allow training of AI systems" and "intended for LLM evaluation only."
- Therefore it must **not** route to TRAIN and must not seed synthetic/back-translation data.
- It can proceed only as an eval/final ledger source, consistent with existing Stage-2 docs that list `global-piqa-parallel` as a milestone holdout/eval anchor.

## Adapter sketch

Do not create Stage-2 training candidates. Build an eval/final ledger ingester instead:

- `origin`: `global-piqa-parallel-haw`
- `division`: `final` (major-milestone holdout) unless evaluator owner chooses `evals`.
- `split`: `test`
- `edition_or_version`: `mrlbenchmarks/global-piqa-parallel@a350910e9cfc8b0b57cb55aa8261780deabb6568; config=haw_latn; split=test; license=CC-BY-SA-4.0; no-training`
- Preserve row id: `example_id`.
- Evaluation schema: PIQA multiple-choice, not simple parallel training rows.
  - Hawaiian prompt/options: `prompt`, `solution0`..`solution3`.
  - English prompt/options for reference/diagnostics only: `eng_prompt`, `eng_solution0`..`eng_solution3`.
  - Gold answer: `label`.
  - Metadata: `language`, `categories`, parsed `supplement` JSON if needed.
- Hash ledger before use: hash Hawaiian prompt+options+label and optionally English prompt+options to prevent contamination.
- Dedup priority: eval-only ledger, not part of train dedup priority. If any text overlaps existing train rows, train rows must be dropped/held out, not this eval source.

## What would change the verdict

- GREEN for TRAIN would require the dataset owner to remove the no-training restriction and publish a training-compatible open license (for example CC0/CC-BY or an explicit dataset-card grant permitting ML training). Current CC-BY-SA plus the explicit no-training sentence is not train-compatible.
- RED would apply if the owner disallowed evaluation use, if HF access became gated/authenticated, or if the card license became ambiguous. Current card explicitly permits evaluation intent, so eval-only remains YELLOW.
