# Orchestration Log — Linus (Data Engineer)

**Agent:** linus-data-storage-layout  
**Date:** 2026-04-29T06:01:32Z  
**Requested by:** yashasg  
**Coordinator:** Squad v0.9.1

## Outcome

Closed the open gap from prior ADRs: **"raw archive storage location TBD"**.

**Decision:** Local-first, off-git architecture.
- **In git:** code, schemas, docs, URL inventory (`data-sources/*.json`), `requirements.txt`, `scripts/`, ADRs.
- **Off git, on local workstation disk:** all `data/` — WARCs, extracted JSONL, stage manifests, training JSONL, packed tensors, `eval_hashes.parquet`.
- **Off-site backup (if/when local outgrows):** Azure Blob (existing leftover-credit budget) or Backblaze B2 / Cloudflare R2 post-credits.
- **Rejected:** GitHub repo (size/rights risk), Git LFS (bandwidth-hostile to WARC+Parquet workload, history immutability liability for rights-sensitive Hawaiian material), HF Datasets (third-party platform before Linus's licensing review is complete).

Rationale: prototype posture is explicit — nothing leaves the machine without formal clearance. Storing raw bytes on GitHub (private or LFS) effectively re-publishes them under one location, which we cannot justify per-source. Git history is immutable; WARC+Parquet are append-only workloads, not LFS's small-binary-asset design.

## Artifacts

- Decision proposal: `.squad/decisions/inbox/linus-data-storage-location.md` (written by Linus)
- Appended Linus history: `.squad/agents/linus/history.md`

## Related Open Gaps

- Unchanged: cultural-review owner unassigned (team-wide blocker for release decisions)
- Unchanged: Hawaiian-literate alignment spot-checker for Stage-2 threshold tuning
- Unchanged: pinned Bible edition decision

## Next Steps

Action items from proposal deferred pending team acceptance:
1. Add `data/` to `.gitignore` (pre-emptive; adapters will create it)
2. Adapters resolve data root from env/config, default outside repo
3. Scribe edits `docs/data-pipeline.md` § Storage location after acceptance
