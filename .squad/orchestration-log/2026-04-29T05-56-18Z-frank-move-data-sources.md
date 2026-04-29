# 2026-04-29T05:56:18Z — Frank: Move Hawaiian Data-Sources Out of Docs

**Agent:** Frank (Hawaiian Data Collector)  
**Agent ID:** frank-move-data-sources  
**Status:** Completed  
**Spawn Request:** yashasg via Coordinator Squad v0.9.1  

## Outcome

- ✅ Created top-level `data-sources/` directory
- ✅ Moved `docs/hawaiian-data-sources.json` → `data-sources/hawaiian-data-sources.json` (canonical path)
- ✅ Updated `docs/data-pipeline.md` reference (Stage 1 row)
- ✅ Validated JSON: `python3 -m json.tool data-sources/hawaiian-data-sources.json` passed
- ✅ Appended history entry to `.squad/agents/frank/history.md`

## Rationale

User directive: `docs/` is reserved for Markdown files; data-source inventories (JSON, CSV, manifests) belong in `data-sources/`.

## Files Changed

- `data-sources/hawaiian-data-sources.json` (created)
- `docs/data-pipeline.md` (reference update)
- `.squad/agents/frank/history.md` (history entry)

## Notes

- No duplicate decision file created (Coordinator directive exists; no team decision needed)
- Pre-existing history entries and dated logs that cite `docs/hawaiian-data-sources.json` remain as provenance
- New canonical layout: `data-sources/` for manifests; `docs/` for Markdown; tool surface: `scripts/setup.sh` + `requirements.txt`
