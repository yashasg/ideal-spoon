# Session Log — Data Storage Location Decisions

**Date:** 2026-04-29T06:01:32Z

## Topic

Where to store Hawaiian raw/extracted/training data; whether GitHub repo is appropriate.

## Agents Coordinated

1. **Linus (Data Engineer)** — Recommended git for code/docs/schemas/source inventory only; corpus/manifests/training JSONL/packed tensors/eval hashes off-git on local disk with offline backup. Rejected Git LFS for rights and history reasons.
2. **Livingston (Cost Strategist)** — Recommended local external disk as primary; Azure Blob Hot LRS while credits last, then Backblaze B2 or Cloudflare R2 depending egress needs. Rejected GitHub/Git LFS/HF Datasets for rights-sensitive prototype corpus. Reserved HF Hub for private adapter/checkpoint handoff only.

## Decision

**Hybrid local-first architecture:**
- GitHub: code, schemas, docs, URL inventory, `requirements.txt`
- Local external disk: primary working store for `data/` (raw, extracted, stages, eval hashes)
- Off-site backup: Azure Blob (Phase 1) → B2/R2 (Phase 2)
- No LFS, no HF Datasets, no GitHub storage

Rationale: prototype posture is explicit (nothing leaves machine without clearance); rights-sensitive corpus; Git immutability is a liability for WARC/Parquet append workloads.

## Outcomes

- Closed open gap: "raw archive storage location TBD"
- Aligned Linus + Livingston on hybrid model, cost, and governance
- Deferred action items (`.gitignore`, adapter config, doc edits) pending team acceptance
- Open questions: user's external HW, Azure tenant type, `rclone` buy-in

## Files

- Linus proposal: `.squad/decisions/inbox/linus-data-storage-location.md`
- Livingston note: `.squad/decisions/inbox/livingston-data-storage-prototype.md`
- Orchestration logs: `.squad/orchestration-log/2026-04-29T06-01-32Z-{linus-data-storage-layout,livingston-storage-provider}.md`
