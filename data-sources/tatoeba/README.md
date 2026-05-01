# Tatoeba en↔haw Source Adapter

Stage 2 source adapter for Hawaiian–English sentence pairs from [Tatoeba](https://tatoeba.org).

## Provenance

| Field | Value |
|-------|-------|
| Source | Tatoeba (https://tatoeba.org) |
| Pinned dump date | 2025-05-01 |
| Hawaiian sentences | `haw_sentences_detailed.tsv.bz2` |
| en↔haw links | `haw-eng_links.tsv.bz2` |
| English sentences | `eng_sentences_detailed.tsv.bz2` |
| License | CC-BY 2.0 FR (site-level; some entries CC0) |
| License URL | https://tatoeba.org/en/terms_of_use |

See `PINNED_DUMP.json` for full URL list and policy notes.

## Alignment

- `alignment_type`: `parallel-sentence`
- `alignment_method`: `manual` — Tatoeba links are manually added by contributors, making them deterministic via the link table (not an embedding score). This is the schema-compatible value that best represents Tatoeba's actual provenance.
- `alignment_score`: `null` (not applicable for `manual` method)

## Register

`unknown` — Tatoeba contains mixed-domain content (conversational, educational, encyclopedic). No single register label is accurate, so `unknown` is used.

## License Flow-Down

Tatoeba sentences are CC-BY 2.0 FR (most entries). Attribution is satisfied by recording:
- `source = "tatoeba"`
- `source_url_en = "https://tatoeba.org/sentences/{id}"`
- `source_url_haw = "https://tatoeba.org/sentences/{id}"`
- `contributor_en`, `contributor_haw` fields in candidates JSONL

`prototype_only=true`, `release_eligible=false` — do **not** assume release eligibility.

## Volume

Hawaiian has ~100–600 sentences on Tatoeba as of the pinned dump date. All available en↔haw pairs are extracted.

## Usage

```bash
# Dry-run: verify URLs, count expected pairs, do not download
python data-sources/tatoeba/fetch.py --dry-run

# Execute: download, parse, emit candidates JSONL
python data-sources/tatoeba/fetch.py --execute

# Self-test against synthetic fixtures (no network)
python data-sources/tatoeba/fetch.py --self-test
```

### Output

- **Candidates JSONL**: `data/stage2/candidates/tatoeba.jsonl` (gitignored)
- **Raw downloads**: `data/raw/tatoeba-haw-eng/<YYYYMMDD>/` (gitignored)

## Schema Compliance

Output candidates are schema-compliant with `scripts/320_build_stage2_manifest.py`'s `MANIFEST_FIELDS`. Run a schema check:

```bash
python scripts/320_build_stage2_manifest.py --check
```

## Files

| File | Purpose |
|------|---------|
| `fetch.py` | Adapter script (dry-run + execute) |
| `PINNED_DUMP.json` | Pinned dump URLs, date, license metadata |
| `README.md` | This file |
