# Stage 2 Manifest Ingest Pattern

Reusable pattern for ingesting adapter candidate JSONL files into the Stage 2 manifest.

## Core contract

Adapters write `data/stage2/candidates/<source>.jsonl`. The manifest builder (`scripts/320_build_stage2_manifest.py`) reads and validates all of them.

## Split assignment

```python
def assign_split(pair_id: str, dev_modulus: int = 10) -> str:
    h = int(hashlib.sha256(pair_id.encode("utf-8")).hexdigest()[:8], 16)
    return "dev" if (h % dev_modulus) == 0 else "train"
```

- Default modulus 10 → ≈10% dev
- **Do not change modulus after first manifest write** — pairs will silently reclassify
- Use `pair_id` as the key (stable across adapter reruns)

## Ingest flow

```
data/stage2/candidates/*.jsonl
        ↓ iter_candidate_files() — dedup, resolve globs
        ↓ ingest_candidates()
            → assign_split() replaces "review-pending"
            → validate_row() for schema compliance
            → per-source counts for build provenance
        ↓ write_manifest() → data/stage2/stage2_manifest.jsonl
        ↓ write_build_manifest() → data/stage2/build_manifest.json
```

## Build provenance fields (ingest block)

```json
{
  "ingest": {
    "candidate_files": {"<path>": "<sha256>", ...},
    "per_source_row_counts": {"<source>": N, ...},
    "total_candidates_ingested": N,
    "total_violations": N,
    "dev_modulus": 10
  }
}
```

## Module globals as output paths

Tests can patch `m.DATA_STAGE2`, `m.DEFAULT_STAGE2_MANIFEST`, `m.DEFAULT_BUILD_MANIFEST` for isolation. Argparser help strings must use `_rel(path)` (catches `ValueError` from `relative_to(REPO_ROOT)`) to avoid crashing when globals are patched to paths outside the repo.
