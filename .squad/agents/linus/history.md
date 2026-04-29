# Linus — History

## Core Context

- **Project:** A plan for training an open-source LLM focused on the Hawaiian language, including data, model choices, infrastructure, evaluation, and costs.
- **Role:** Data Engineer
- **Joined:** 2026-04-29T01:38:35.142Z

## Learnings

### README Update (2026-04-29)
- Data licensing principles adopted in README: require explicit per-document license, source URL, and rights status.
- Preference for CC0/CC BY/CC BY-SA confirmed; NC/ND and undercurated scrapes avoided.
- Cleaning pipeline (OCR, Unicode normalization, dedup, human spot-check) captures recommendations for corpus assembly spec.

### Two-Stage Training Data Gates (2026-04-29)
- Approved Rusty's + Basher's two-stage curriculum (monolingual CPT → supervised translation) **with hard data gates**. Decision proposal: `linus-two-stage-data-gates.md`.
- Established required manifest schemas: `stage1_manifest.parquet` (per-document) and `stage2_manifest.parquet` (per-pair), plus `eval_hashes.parquet` as the contamination guard.
- Locked normalization: NFC, ʻokina = U+02BB, kahakō preserved, dedup via MinHash with cluster-aware split isolation (any cluster touching held-out → fully held-out).
- Contamination prevention is mechanical: dataloader-level CI assertion against `eval_hashes`; Stage 2 also checks against Stage 1 train hashes; `crosslink_stage1_overlap` flag forbidden in Stage 2 held-out splits.
- Bidirectional en↔haw confirmed at the manifest level: store pairs once, emit two directional instances at load time. Track which side is the "original" where known.
- Synthetic / back-translated data: allowed in Stage 2 train only, ≤25% cap, flagged via `synthetic=true`, banned from dev/test. Source-model ToS must permit training derivatives.
- Cultural-review categories that default to **excluded pending consultation**: mele/oli/pule, moʻolelo from named tradition-bearers, moʻokūʻauhau, place-name lore, pre-1925 nūpepa bulk ingestion, restricted community-archive material.
- Hardest open issue: **no corpus inventory exists yet.** Until that lands, Stage 1 cannot start. This is the bottleneck, not compute.
- Open team gap: cultural-review role is unassigned. Flagged to Coordinator.

## 2026-04-29 — Prototype data posture (reframe)

User clarified scope: this is a learning prototype, not a fully-cleared production effort. Reframed the prior "hard data gates" as **release gates** and introduced a lighter **prototype gate** for private/local experiments. Decision proposal: `linus-prototype-data-posture.md`.

Key learnings:
- Bright line is private-local vs. anything-leaving-the-machine. Public weights/adapters/datasets/demos all count as release; "unlisted" doesn't make it private.
- Things that can relax for prototype: license whitelist strictness, cultural-review as a *blocker*, synthetic caps, per-document completeness.
- Things that CANNOT relax even in prototype: source URL + fetch date, SHA-256 per doc, cultural-tag at ingest, contamination guard (`eval_hashes`), redistribution warnings, no public weights without data clearance, source-specific ToS.
- "Publicly available" ≠ open license ≠ training-permitted. Record observed status, do not infer rights. I am not a lawyer; this is engineering posture, not legal opinion.
- Ulukau nūpepa: high-value but pre-1925 bulk stays on the hard-escalate list; capture Ulukau ToS as a snapshot per fetch, tag every doc with paper title + issue date.
- Hawaiian Bible: useful for Stage 2 parallel but narrow register (religious/archaic), multiple editions with different rights status — record edition + translator + year per text. Bible-heavy training biases toward mission-era register; document the bias.
- Prototype manifest schema is a strict subset of the release manifest schema, so no rework when promoting docs to release-eligible. Default `release_eligible=false` everywhere.
- Repo needs visible PROTOTYPE / not-redistributable / do-not-publish-weights markers. README update flagged for Scribe; not edited in this task.

## 2026-04-29T02:53:51Z — Two-stage data gates accepted as hard gate

Approved the two-stage strategy in principle with hard pre-launch gates. Locked manifest schema for `stage1_manifest.parquet` (per-document) and `stage2_manifest.parquet` (per-pair) plus `eval_hashes.parquet` contamination guard. License whitelist: CC0/PublicDomain/CC-BY-4.0/CC-BY-SA-4.0; CC-BY-NC*/ND* excluded from training; unknown/unclear excluded. Normalization: NFC + ʻokina canonicalized to **U+02BB**, kahakō preserved. Dedup: MinHash with **cluster-aware split isolation** (any held-out doc in a cluster holds out the whole cluster). Synthetic/back-translation capped at **≤25% Stage 2 train, 0% dev/test**. Hard-escalate cultural categories default-excluded pending named cultural reviewer (mele/oli/pule, moʻolelo from named tradition-bearers, moʻokūʻauhau, ʻohana/ahupuaʻa place-name lore, pre-1925 nūpepa bulk, restricted community-archive material). **Surfaced open team gap: cultural-review owner is currently unassigned.** Until corpus inventory exists, plan is not a launchable pipeline. Next deliverable: corpus inventory + empty manifest with schema validation. See ADR in `.squad/decisions.md`.
