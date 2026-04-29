# W1 manual micro-eval (Hawaiian)

A small, hand-authored Hawaiian micro-eval used as a **W1 eval source independent
of FineWeb-2**. Lives here as a *schema + template only*. Populated TSVs are
local-only (see `/data/` gitignore rule) and never used as training data.

## Purpose

A 50–100 item, human-reviewed probe set that tests:

1. **ʻokina survival** — ʻokina present at U+02BB in generations and references; never collapsed to U+2018 / U+0027.
2. **Kahakō retention** — ā ē ī ō ū present at expected positions; not stripped, not NFD-decomposed.
3. **Unicode / NFC** — every row is NFC-normalized before use; load-time check fails loudly on NFD or U+2018/U+0027 in the ʻokina slot.
4. **Generation sanity** — short open-ended prompts that should produce coherent Hawaiian (no English collapse, no register collapse, no degenerate repetition).

## Why it exists

- Independent from FineWeb-2 `haw_Latn`. Lets us swap source distributions on checkpoint evals (per `docs/eval_pipeline.md` §3.1 and §4) without depending on the web crawl's quality.
- Small enough to run on every cheap-eval cadence; deterministic; comparable across runs once frozen.
- Hand-authored / human-reviewed, so the orthography and register are known-good rather than LID-classified.

## Hard rules

- **Hand-authored or quoted from rights-cleared sources.** Each row carries an `author` and a `notes` field; quoted material requires per-row citation.
- **Not training data, ever.** All accepted rows are hashed and added to `data/evals/eval_hashes.parquet` (the contamination ledger; covers both held-out divisions, `evals` and `final` — see `docs/data-pipeline.md` "Dataset division taxonomy"). The W1 manual micro-eval lives under the **`evals`** division (cheap, frequent, checkpoint-aligned). Stage 1 / Stage 2 dataloaders' contamination CI assertion catches any leak.
- **No fabricated Hawaiian.** If an authoring agent (human or model) is not a Hawaiian speaker, the row stays `review_status=draft` until a Hawaiian-literate reviewer marks it `accepted`. Drafts are not run.
- **NFC before commit.** `nfc_normalized=true` is required; loader rejects rows with U+2018 / U+0027 in the ʻokina slot or with NFD-decomposed kahakō.
- **Repo posture.** Only this template + this README live in git. Populated TSVs live at `data/evals/manual_w1/w1-haw-micro-eval.tsv` (gitignored, under the `evals` division).

## File layout

| Path | In git? | Purpose |
|---|---|---|
| `data-sources/manual-eval/w1-haw-micro-eval.template.tsv` | yes | Header + field semantics, no rows. |
| `data-sources/manual-eval/README.md` | yes | This file. |
| `data/evals/manual_w1/w1-haw-micro-eval.tsv` | no (gitignored) | Populated, NFC-normalized, human-reviewed rows. Lives under the canonical `evals` division. |
| `data/evals/eval_hashes.parquet` | no (gitignored) | Contamination ledger; all `accepted` row hashes appended here with `origin=manual_w1`, `stage=eval-only`. |

## Schema

Tab-separated, UTF-8, NFC. Header line is the first non-comment line.
Lines beginning with `#` are comments and stripped at load time.

| Field | Type | Notes |
|---|---|---|
| `item_id` | string | Stable id, kebab-case, category-prefixed (e.g. `w1-okina-001`). |
| `category` | enum | `okina_survival` \| `kahako_retention` \| `unicode_nfc` \| `generation_sanity`. |
| `prompt` | string | Model input. May be Hawaiian or English depending on probe. |
| `reference` | string | Gold continuation / expected substring. May be empty for open-ended sanity probes (judged by orthography metrics, not exact match). |
| `diacritic_density` | int | Count of ʻokina (U+02BB) + kahakō vowels (ā ē ī ō ū) in `prompt`+`reference`. Used as a slicing axis (`docs/eval_pipeline.md` §5). |
| `notes` | string | What this item tests; cite source if quoted from rights-cleared text. |
| `author` | string | Initials of the human author/reviewer. |
| `review_status` | enum | `draft` \| `reviewed` \| `accepted`. Only `accepted` rows are run. |
| `nfc_normalized` | bool | `true` \| `false`. Must be `true` before commit; verified at load time. |

## Integration with the eval harness

The eval harness is not yet built (`docs/eval_pipeline.md` describes the design,
not an implementation). When it lands, the W1 manual micro-eval is wired in as:

1. **Loader.** Reads the off-git TSV at `data/evals/manual_w1/w1-haw-micro-eval.tsv`,
   strips `#` comment lines, asserts NFC and `accepted` status, hashes each row's
   `(prompt, reference)` into `data/evals/eval_hashes.parquet` with
   `origin=manual_w1`, `stage=eval-only`.
2. **Cheap-eval cadence.** Runs alongside the FineWeb-2 dev slice on every
   checkpoint save. Reports per-category metrics (ʻokina survival, kahakō
   retention, NFC violations, generation sanity flags) and an overall pass-rate.
   Same eval-suite SHA gate as the rest of §3.1.
3. **Slicing.** `category` and `diacritic_density` become slicing axes per §5.
4. **Contamination.** Stage 1 / Stage 2 dataloaders already CI-assert
   `train ∩ eval_hashes = ∅`; adding `manual_w1` rows to the ledger is the
   only wiring needed for the leakage guard.

Until the harness exists, this directory is the contract. Authors can begin
populating the off-git TSV against this schema in parallel with FineWeb-2 ingest.
