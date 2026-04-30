# W1 manual micro-eval (Hawaiian)

A small, hand-authored Hawaiian micro-eval used as a **W1 eval source independent
of FineWeb-2**. Lives here as a *schema + template only*. Populated TSVs are
local-only (see `/data/` gitignore rule) and never used as training data.

## Purpose

A 50–100 item, human-reviewed probe set that tests:

1. **ʻokina survival** — ʻokina present at U+02BB in generations and references; never collapsed to U+2018 / U+0027.
2. **Kahakō retention** — ā ē ī ō ū present at expected positions; not stripped, not NFD-decomposed.
3. **Unicode / NFC** — every row is NFC-normalized before use; load-time check fails loudly on NFD or U+2018/U+0027 in the ʻokina slot.
4. **Tokenizer survival** — exact round-trip probes for U+02BB and precomposed kahakō characters.
5. **Generation sanity** — short open-ended prompts that should produce coherent Hawaiian (no English collapse, no register collapse, no degenerate repetition).

## Why it exists

- Independent from FineWeb-2 `haw_Latn`. Lets us swap source distributions on checkpoint evals (per `docs/eval_pipeline.md` §3.1 and §4) without depending on the web crawl's quality.
- Small enough to run on every cheap-eval cadence; deterministic; comparable across runs once frozen.
- Hand-authored / human-reviewed, so the orthography and register are known-good rather than LID-classified.

## Hard rules

- **Hand-authored or quoted from rights-cleared sources.** Each row carries an `author` and a `notes` field; quoted material requires per-row citation.
- **Not training data, ever.** All accepted rows are hashed and added to `data/evals/eval_hashes.jsonl` (the contamination ledger; covers both held-out divisions, `evals` and `final` — see `docs/data-pipeline.md` "Dataset division taxonomy"). The W1 manual micro-eval lives under the **`evals`** division (cheap, frequent, checkpoint-aligned). Stage 1 / Stage 2 dataloaders' contamination CI assertion catches any leak.
- **No fabricated Hawaiian benchmark.** If an authoring agent (human or model) is not a Hawaiian speaker, the row stays `review_status=draft` until a Hawaiian-literate reviewer marks it `accepted`. Drafts are not run. Prototype local drafts may exist only under ignored `data/evals/manual_w1/` and must say they are pending review.
- **NFC before commit.** `nfc_normalized=true` is required; loader rejects rows with U+2018 / U+0027 in the ʻokina slot or with NFD-decomposed kahakō.
- **Repo posture.** Only this template + this README live in git. Populated rows live off-git under `data/evals/manual_w1/`: the authoring TSV at `w1-haw-micro-eval.tsv` and the **eval-consumable JSONL** at `w1-haw-micro-eval.jsonl` (the file Stage 0 reads — Stage 0 W1 input is JSONL-only per the user directive at `.squad/decisions/inbox/copilot-directive-20260430T081137Z.md`).

## File layout

| Path | In git? | Purpose |
|---|---|---|
| `data-sources/manual-eval/w1-haw-micro-eval.template.tsv` | yes | Header + field semantics, no rows. Authoring template only. |
| `data-sources/manual-eval/README.md` | yes | This file. |
| `data/evals/manual_w1/w1-haw-micro-eval.tsv` | no (gitignored) | Local **authoring** source: populated, NFC-normalized, human-reviewed rows. Lives under the canonical `evals` division. Not consumed by the Stage 0 eval harness directly — convert to JSONL first. |
| `data/evals/manual_w1/w1-haw-micro-eval.jsonl` | no (gitignored) | **Eval-consumable** JSONL emitted from the TSV. This is the artifact `code/llm_hawaii/evaluate.py` reads (Stage 0 W1 input is JSONL-only). Carries `item_id`, `category`, `prompt`, `reference`, `text`, `review_status`, `nfc_normalized`, `diacritic_density`, `diacritic_density_bin`, `sha256_normalized`, and `schema_version: "manual-w1-jsonl-v1"`. |
| `data/evals/eval_hashes.jsonl` | no (gitignored) | Canonical JSONL contamination ledger; all `accepted` row hashes appended here with `schema_version`, `sha256_normalized`, `hash_method=sha256`, `normalization_method=NFC`, `origin=manual_w1`, `stage=eval-only`, `division=evals`, and `row_id`. |
| `scripts/315_hash_manual_w1_eval.py` | yes | Local validator/hash path. Can initialize a clearly marked draft TSV, summarize categories/slices, write the eval JSONL mirror, and update the JSONL ledger. |

## Schema

Authors edit a tab-separated, UTF-8, NFC TSV. Header line is the first
non-comment line; lines beginning with `#` are comments and stripped at
load time. The TSV is the **authoring** format only; the Stage 0 eval
harness reads the JSONL emitted by
`scripts/315_hash_manual_w1_eval.py` (Stage 0 W1 input is JSONL-only).

| Field | Type | Notes |
|---|---|---|
| `item_id` | string | Stable id, kebab-case, category-prefixed (e.g. `w1-okina-001`). |
| `category` | enum | `okina_survival` \| `kahako_retention` \| `unicode_nfc` \| `tokenizer_survival` \| `generation_sanity`. |
| `prompt` | string | Model input. May be Hawaiian or English depending on probe. |
| `reference` | string | Gold continuation / expected substring. May be empty for open-ended sanity probes (judged by orthography metrics, not exact match). |
| `diacritic_density` | int | Count of ʻokina (U+02BB) + precomposed kahakō vowels (ā ē ī ō ū / Ā Ē Ī Ō Ū) in `prompt` + LF + `reference`. Used as a slicing axis (`docs/eval_pipeline.md` §5). |
| `notes` | string | What this item tests; cite source if quoted from rights-cleared text. |
| `author` | string | Initials of the human author/reviewer. |
| `review_status` | enum | `draft` \| `reviewed` \| `accepted`. Only `accepted` rows are run. |
| `nfc_normalized` | bool | `true` \| `false`. Must be `true` before commit; verified at load time. |

Each TSV row maps 1:1 to a JSONL record with `schema_version: "manual-w1-jsonl-v1"`,
adding `sha256_normalized` (canonical `sha256(NFC(prompt) + LF + NFC(reference))`),
a `text` convenience field (the same NFC-normalized concatenation), a
derived `diacritic_density_bin`, and an `eval_consumable` boolean
(true iff `review_status=accepted`).

## Local bootstrap / hashing

The first local draft can be generated without committing rows:

```bash
python3 scripts/315_hash_manual_w1_eval.py --init-draft --execute
python3 scripts/315_hash_manual_w1_eval.py --dry-run --include-draft-for-local-ledger
```

The generated rows are `review_status=draft`, `author=rusty-ai-draft`, and
clearly marked prototype/local pending human review. They are useful only for
exercising the file path, Unicode checks, category/slice summaries, tokenizer
audit input, and local contamination preflight. They are **not accepted eval
items** and must not be reported as a benchmark.

Convert the populated TSV to the eval-consumable JSONL (the artifact
Stage 0's `evaluate.py` reads) without touching the contamination
ledger:

```bash
python3 scripts/315_hash_manual_w1_eval.py --execute --jsonl-only
```

The JSONL includes every valid TSV row and preserves
`review_status`/`eval_consumable` flags. Draft rows remain prototype-local
and must not be reported as accepted eval results. **Stage 0 W1 input is
JSONL-only**: the harness no longer reads the TSV directly.

Once rows are human-reviewed and changed to `review_status=accepted`, update the
canonical local ledger:

```bash
python3 scripts/315_hash_manual_w1_eval.py --execute
```

For local-only contamination preflight before review, the explicit escape hatch
is:

```bash
python3 scripts/315_hash_manual_w1_eval.py --execute --include-draft-for-local-ledger
```

Those non-accepted ledger rows are marked `eval_consumable=false` and
`prototype_local=true`.

## Integration with the eval harness

The Stage 0 eval harness (`code/llm_hawaii/evaluate.py`) wires W1 in as
follows:

1. **Loader (Stage 0, JSONL-only).** Reads the off-git JSONL at
   `data/evals/manual_w1/w1-haw-micro-eval.jsonl`, skips comment/blank
   lines, and asserts NFC + `review_status=accepted` orthographic gates
   on accepted rows only. Drafts/reviewed rows stay loose. The probe
   surfaces a stable status enum (`not_configured` | `missing` |
   `invalid` | `draft_only` | `evaluated`) plus `jsonl_sha256`,
   `jsonl_size_bytes`, `accepted_item_hashes`, and `w1_suite_sha256`.
2. **Ledger writer (TSV → ledger).** When the TSV is updated, run
   `scripts/315_hash_manual_w1_eval.py --execute` to NFC-normalize and
   hash each accepted row's `prompt + LF + reference` into
   `data/evals/eval_hashes.jsonl` using the canonical eval-hash JSONL
   schema (`sha256_normalized`, `hash_method=sha256`,
   `normalization_method=NFC`, `origin=manual_w1`, `stage=eval-only`,
   `division=evals`, `split=w1`, `row_id=item_id`).
3. **Cheap-eval cadence.** Runs alongside the FineWeb-2 dev slice on every
   checkpoint save. Reports per-category metrics (ʻokina survival, kahakō
   retention, NFC violations, tokenizer survival, generation sanity flags)
   and an overall pass-rate. Same eval-suite SHA gate as the rest of §3.1.
4. **Slicing.** `category`, `diacritic_density`, and the derived
   `diacritic_density_bin` (`none` = 0, `low` = 1–2, `medium` = 3–5,
   `high` ≥ 6; see `code/llm_hawaii/metrics.py`) become slicing axes per §5.
5. **Contamination.** Stage 1 / Stage 2 dataloaders already CI-assert
   `train ∩ eval_hashes = ∅`; adding `manual_w1` rows to the ledger is the
   only wiring needed for the leakage guard.

Authors can begin populating the off-git TSV against this schema in
parallel with FineWeb-2 ingest. The Stage-0 tokenizer audit (planned as
a test) is expected to consume the populated rows directly —
concatenating `prompt` + `reference` by default — so the manual rows
feed in as one of the high-diacritic sample sources.

## Relationship to the human_fetch bidirectional translation probe

The W1 manual micro-eval (this file) is a **separate** probe from the
`human_fetch` bidirectional translation probe. The translation probe runs
independently as `human_fetch_translation` in every checkpoint eval report,
sourced from `data/tokenizer_audit/ulukau_nupepa/human_fetch.jsonl` (the
Ulukau parallel pair). It is a **prototype/learning probe** that measures the
model's en→haw and haw→en translation behavior at the Stage 0 no-training
baseline and tracks drift over checkpoints. It is `eval_eligible = True`,
`training_eligible = False`. Neither the W1 JSONL nor the human_fetch
translation probe is ever used as training data.
