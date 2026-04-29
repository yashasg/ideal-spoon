# 2026-04-29T06:56:07Z — Python Script Contracts Merged

**Scribe:** Consolidating python-scripts directive and data-pipeline task contracts.

## Status

- **Frank** (`scripts/fetch_rightslight_raw.py`): stable raw-fetch provenance ledger schema JSONL at `data/raw/<source>/fetch.jsonl` (ProvenanceRecord dataclass, 14 fields + extension point). Dry-run safe, `--execute` gated, `--metadata-only`/`--smoke` restrict to checksum manifests. Validated: compiles, CLI help works.
- **Linus** (`scripts/build_stage1_dataset.py`): JSONL-first manifest strategy (Stage 1 prototype output is `data/stage1/stage1_manifest.jsonl` not `.parquet`; parquet deferred until corpus > 50k docs or first analytical query). Stdlib-only, handles XML extraction, NFC + U+02BB normalization, deterministic splits, `--dry-run`/`--source`/`--limit`/`--strict` flags. Validated: compiles, CLI help works.
- **Coordinator directive:** Python for project scripts (user: "you can use python, for scripts").

## Decisions Merged

- `.squad/decisions.md` updated with three items: Python-scripts directive, Frank's raw-fetch JSONL schema, Linus's JSONL-first decision.
- Inbox files merged and deleted (decision-inbox/). No duplicate decisions.

## Provenance

- Contracts validated via `python3 -m py_compile` for all three scripts; CLI help printed.
- Schema additive-only rules locked (Frank + Linus coordination point for future fields).
- Stdlib-only posture preserved for both.
