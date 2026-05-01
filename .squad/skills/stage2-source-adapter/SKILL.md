# Stage 2 Source Adapter Pattern

Reusable pattern for building Stage 2 en↔haw parallel corpus source adapters.

## Pattern Overview

Each adapter owns one source (e.g., Tatoeba, Bible, OPUS subset) and produces
a candidates JSONL under `data/stage2/candidates/<source>.jsonl` (gitignored).

## Required Structure

```
data-sources/<source-id>/
  fetch.py           # main adapter script
  README.md          # provenance, dump URL, date, license
  PINNED_DUMP.json   # machine-readable provenance + policy metadata
```

## Adapter Script Contract

Must support three modes:
```bash
python data-sources/<source>/fetch.py --dry-run    # HEAD URLs, no download
python data-sources/<source>/fetch.py --execute    # download + emit candidates
python data-sources/<source>/fetch.py --self-test  # in-memory smoke, no network
```

Exit codes: `0` success, `1` I/O error, `2` CLI misuse, `3` schema failure.

## Candidate JSONL Fields

All required manifest fields from `scripts/320_build_stage2_manifest.py::MANIFEST_FIELDS`
that can be computed at fetch time. Key fields to pre-populate:

| Field | Source |
|-------|--------|
| `pair_id` | `{source}-haw{haw_id}-en{eng_id}` |
| `source` | source identifier string |
| `source_url_en`, `source_url_haw` | per-sentence URLs |
| `fetch_date` | `datetime.date.today().strftime("%Y%m%d")` |
| `sha256_en_raw`, `sha256_haw_raw` | `sha256(raw_text.encode())` |
| `sha256_en_clean`, `sha256_haw_clean` | `sha256(nfc(text).encode())` |
| `sha256_pair` | `sha256(sha256_en_clean + "‖" + sha256_haw_clean)` |
| `record_id_en`, `record_id_haw` | source-native IDs |
| `text_en`, `text_haw` | NFC-normalized text |
| `alignment_type` | per source (e.g., `"parallel-sentence"`) |
| `alignment_method` | per source (e.g., `"manual"`, `"verse-id"`) |
| `alignment_score` | `null` for deterministic methods |
| `alignment_review_required` | `False` (scorer will update) |
| `length_ratio_haw_over_en` | `len(haw.split()) / len(en.split())` |
| `lang_id_en`, `lang_id_haw` | `"en"`, `"haw"` |
| `lang_id_en_confidence`, `lang_id_haw_confidence` | `1.0` (known from source) |
| `direction_original` | `"unknown"` or actual direction |
| `register` | per source; use `"unknown"` for mixed-domain |
| `synthetic` | `False` for human-sourced corpora |
| `prototype_only` | always `True` |
| `release_eligible` | always `False` |
| `license_observed_en`, `license_observed_haw` | per source |
| `license_inferred` | always `None` |
| `dedup_cluster_id` | `pair_id` (reassigned by dedup pass later) |
| `crosslink_stage1_overlap` | `False` (unknown at fetch time) |
| `split` | `"review-pending"` |
| `manifest_schema_version` | `"stage2.v0"` |

## Hash Invariant

```python
sha256_pair == sha256((sha256_en_clean + "\u2016" + sha256_haw_clean).encode("utf-8"))
```

This mirrors `compute_pair_hash()` in `320_build_stage2_manifest.py`. Tests must
verify this invariant.

## alignment_method Choices (schema-compatible values)

| Value | Use When |
|-------|----------|
| `"verse-id"` | Bible verse alignment (deterministic) |
| `"manual"` | Human-curated links (Tatoeba) |
| `"tmx-line"` | TMX or Moses-format line-aligned bitext |
| `"filename-pair"` | Paired filename alignment |
| `"labse"` | LaBSE embedding alignment (requires score) |
| `"laser"` | LASER embedding alignment (requires score) |

## register Choices (schema-compatible values)

`"religious"`, `"software-l10n"`, `"encyclopedic"`, `"educational"`, `"news"`, `"dictionary-example"`, `"unknown"`

Use `"unknown"` for mixed-domain sources (e.g., Tatoeba).

## Testing Pattern

```
code/tests/fixtures/<source>/          # synthetic TSV/JSONL fixtures
code/tests/test_<source>_adapter.py   # unittest, no network
```

Key test classes:
1. `TestParseXxx` — parse functions with blank-line / malformed input cases
2. `TestBuildCandidateRow` — all field values, hash invariant, NFC normalization
3. `TestJoinPairs` — join correctness, missing-side skipping, unique hashes
4. `TestSchemaCompatibility` — `validate_row()` from 320 returns no violations
5. `TestSelfTest` — adapter's `--self-test` exits 0

## Examples

- `data-sources/tatoeba/fetch.py` — reference implementation (issue #17)

---

## Reference instance: Baibala Hemolele × WEB Bible (issue #16, 2026-05-01)

First concrete adapter to land on this scaffold. Adds three conventions
that future Stage-2 adapters should adopt:

### Edition pin lives in JSON, not Python

`data-sources/<source>/source_registry.json::sides.<lang>.edition_pinned_by`
is the single source of truth for which edition we have rights to pull.
The fetcher reads it; the rights-reviewer (Linus) edits it. Keeps pins
reviewable as data, not buried in script constants.

### Triple-gated `--execute` on the live fetcher

Required for any rights-review-pending source. The fetcher's
`--execute` path must refuse with rc=2 unless ALL of:

1. Registry's `edition_pinned_by` is non-null.
2. CLI `--confirm-edition <id>` matches the registry `edition_or_version`.
3. CLI `--tos-snapshot <path>` points at an existing on-disk file.

Reference: `scripts/206_fetch_baibala_raw.py::assert_execute_preconditions`.

### ʻokina canonicalization runs before any sha256

On the Hawaiian side: NFC-normalize AND fold U+2018, U+2019, and ASCII
apostrophe (`'`) to the canonical ʻokina U+02BB **before** computing
`sha256_haw_clean` or `sha256_pair`. Mirror the `OKINA_MISENCODINGS`
set in `code/llm_hawaii/stage2_quality.py`. Skipping this step makes
pair hashes drift across upstream rendering quirks and silently breaks
contamination dedup. Reference: `scripts/322_build_bible_candidates.py::normalize_haw`.

### Pair-hash via the canonical helper

`sha256_pair = compute_pair_hash(en_clean, haw_clean)` — reuse
`scripts/320_build_stage2_manifest.py::compute_pair_hash` rather than
reimplementing. Add a unit test asserting the candidate row's
`sha256_pair` matches the helper byte-for-byte (see
`code/tests/test_bible_adapter.py::test_pair_hash_invariant`).

### Synthetic test fixtures over real corpus excerpts

Test fixtures under `code/tests/fixtures/<source>/` should be small
synthetic content clearly labelled NOT real corpus. The adapter
contract is a pure-function test of normalization + row shape; using
real PD text only adds rights ambiguity and edition-drift failure
modes. Real text only enters the pipeline via `data/` (gitignored)
once the edition is pinned.
