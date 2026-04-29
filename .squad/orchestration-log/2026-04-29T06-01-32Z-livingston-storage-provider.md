# Orchestration Log — Livingston (Cost Strategist)

**Agent:** livingston-storage-provider  
**Date:** 2026-04-29T06:01:32Z  
**Requested by:** yashasg  
**Coordinator:** Squad v0.9.1

## Outcome

Sizing and cost analysis for data storage at prototype scale (~30–80 GB raw + ~10 GB derived).

**Recommendation (hybrid layout):**
1. **Git repository** — code, schemas, URL inventories, ADRs, `requirements.txt`. **Nothing under `data/` committed** (enforced by `.gitignore`).
2. **Local external disk (primary)** — working `data/raw/`, `data/extracted/`, `data/stage1/`, `data/stage2/`, SHA-256 keyed. Fastest for RTX 2080 workstation, no quota anxiety.
3. **Off-site backup of `data/raw/` only** (immutable WARCs + native originals, SHA-256 keyed):
   - **Phase 1 (while credits last):** Azure Blob Hot LRS, single container `raw`, lifecycle rule Hot→Cool at 30 days. Cost <$2/mo (fits inside existing $50–60/mo experiment budget).
   - **Phase 2 (post-credits):** Backblaze B2 (cheapest, ~$0.30/mo storage) OR Cloudflare R2 (zero egress, better when pulling shards to rented GPUs, ~$0.75/mo).
4. **Hugging Face Hub** — reserved for adapter checkpoints during training and eventual *releasable* derived artifacts. **Not** the raw corpus, **not** while rights review is open.

**Rejected:** GitHub (file/repo size caps, public-by-default risk); Git LFS (bandwidth-priced data packs hostile to dataset workloads); HF Datasets private (third-party platform for rights-sensitive cultural corpus before Linus's licensing review = wrong order); AWS S3 standard (egress cost kills it when shipping shards to rented GPUs).

**Rights-sensitive guardrails (non-negotiable):**
- Off-site bucket is **private**, no public read/list, no CDN
- Object keys are SHA-256 hex, not URLs/titles — no incidental disclosure of source identifiers
- Per-document license/provenance lives in manifest, not blob name
- Sources of uncertain redistributability stay **local-only** until Linus clears them

## Artifacts

- Decision note: `.squad/decisions/inbox/livingston-data-storage-prototype.md` (written by Livingston)
- Appended Livingston history: `.squad/agents/livingston/history.md`

## Cost Summary (Prototype)

| Layer | Where | Cost |
|---|---|---|
| Source code + small artifacts | GitHub | $0 |
| Working raw/derived data (~30–80 GB) | Local external disk | one-time HW |
| Off-site raw backup, Phase 1 | Azure Blob Hot LRS | <$2/mo, paid from existing leftover credit |
| Off-site raw backup, Phase 2 (post-credits) | Backblaze B2 *or* Cloudflare R2 | $0.30–$1.50/mo |
| Adapter/checkpoint bus during training | HF Hub (private) | $0 |

**Key insight:** Storage cost is negligible at every option except Git LFS. Decision is dominated by fit (file size, egress pattern), governance (rights-sensitive, no public release), and operational ergonomics (S3-compatible, mountable with rclone, integrates with existing tooling).

## Related Decisions

Aligns with Linus's `.squad/decisions/inbox/linus-data-storage-location.md` on the local+off-site hybrid model and reasons for rejecting git/LFS/HF Datasets at prototype scope.

## Open Questions for User

1. Is there an existing external SSD/HDD on workstation, or budget for HW (~$60–$120 for 1–2 TB external SSD)?
2. Is Azure tenant user-personal MSDN or employer-managed? (If employer, do not put Hawaiian cultural corpus on employer cloud; jump to B2/R2.)
3. Comfortable standardizing on `rclone` (works against Azure/B2/R2/S3 with one config) vs per-provider scripts?
