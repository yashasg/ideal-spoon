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

## 2026-04-29 — Stage-2 data pipeline proposal (companion to Stage-1)

Drafted `linus-stage2-data-pipeline.md` covering bidirectional en↔haw SFT data. Key locked points:
- **Source tiers:** Tier A true-parallel = Bible (capped ≤30% parallel-train tokens, 0% dev/test), FLORES-200 `hawn_Latn` (dev/test anchor), OPUS `haw` subsets (Tatoeba clean; JW300 excluded pending ToS recheck), NLLB mined (train only); Tier B comparable = Wiki interlanguage links, Wikisource, Awaiaulu, OHA/DOE/UH bilingual PDFs, Ulukau bilingual; Tier C dictionary example sentences only (headwords ≠ pairs); Tier D synthetic BT/FT under ADR ≤25% cap; Tier E excluded (hard-escalate cultural, JW300, unflagged auto-MT).
- **Alignment typing:** every pair carries `alignment_type ∈ {parallel-verse, parallel-sentence, parallel-doc, comparable-aligned, dictionary-example, synthetic-bt, synthetic-ft}`. Dev/test only accepts `parallel-*`.
- **Pipeline additions over Stage 1:** per-side LID (catches swapped/mixed sides), per-side normalization (Hawaiian rules unchanged from Stage 1; English smart-quote/whitespace cleanup), deterministic alignment for verse-keyed/TMX, embedding alignment (LaBSE/LASER) with model-hash recorded and per-row score persisted, length-ratio filter, pair-hash + MinHash dedup, cluster-aware split isolation, three-way contamination check (Stage-2 eval, Stage-1 eval, Stage-1 train via `crosslink_stage1_overlap`).
- **Manifest delta:** `stage2_manifest.parquet` per-pair, with `pair_id`, both-side hashes (raw+clean) plus `sha256_pair` as primary contamination key, `alignment_type`/`alignment_method`/`alignment_model`/`alignment_score`, `length_ratio_haw_over_en`, both-side LID + confidence, `direction_original`, `register`, `edition_or_version`, `synthetic`+`synthetic_source_model`, both-side `license_observed`, `license_inferred=null` always, `tos_snapshot_id`, `prototype_only=true`/`release_eligible=false` defaults, `dedup_cluster_id`, `crosslink_stage1_overlap`, `alignment_review_required`, `split`.
- **JSONL contract:** one canonical pair → two directional rows (en→haw, haw→en) with explicit `direction`, `loss_mask=target_only`, instruction resolved into the row (template paraphrases stored separately), no metadata leakage into instruction or target. Retention slice = monolingual Hawaiian rows in same file, `direction=haw-mono`, `loss_mask=all_target`, 10–20% by token per ADR. Hawaiian-language instruction allowed for haw→en.
- **Exclusions:** prompts in target, source leakage, sub-threshold alignments, Bible duplicates beyond cap, anything in `eval_hashes`, Stage-1 eval-hash overlaps on the haw side, hard-escalate cultural categories, mixed-language sentences, boilerplate (copyright, translator credits, chapter headers, TMX metadata, URLs), unflagged auto-MT, dictionary headword-only rows.
- **Top risks:** Bible/register skew, verse-style overfitting, tiny-corpus memorization, translationese/synthetic feedback loops, OCR'd bilingual PDF misalignment, English tokens leaking into Hawaiian targets, FLORES leakage with small datasets, direction-confused training, prototype lineage leaking into released artifacts, cross-stage contamination, unbalanced `direction_original`, cultural overreach in outputs.
- **Next 3 steps (post Stage-1):** (1) FLORES-200 adapter + populated `eval_hashes.parquet` + CI assertion before any other ingest; (2) Bible verse-aligned adapter with pinned editions and cap; (3) Tatoeba + one Wiki-aligned LaBSE slice + retention slice → tiny Stage-2 prototype dataset and register/direction report as the go/no-go gate.
- **Hard precondition restated:** no Stage-2 ingest until Stage-1 artifacts and `eval_hashes.parquet` exist; design and adapter scaffolding can land now.
- Open gaps unchanged: cultural-review owner, Hawaiian-literate alignment spot-checker for threshold tuning, pinned Bible edition decision, raw archive storage location.

## 2026-04-29T02:53:51Z — Two-stage data gates accepted as hard gate

Approved the two-stage strategy in principle with hard pre-launch gates. Locked manifest schema for `stage1_manifest.parquet` (per-document) and `stage2_manifest.parquet` (per-pair) plus `eval_hashes.parquet` contamination guard. License whitelist: CC0/PublicDomain/CC-BY-4.0/CC-BY-SA-4.0; CC-BY-NC*/ND* excluded from training; unknown/unclear excluded. Normalization: NFC + ʻokina canonicalized to **U+02BB**, kahakō preserved. Dedup: MinHash with **cluster-aware split isolation** (any held-out doc in a cluster holds out the whole cluster). Synthetic/back-translation capped at **≤25% Stage 2 train, 0% dev/test**. Hard-escalate cultural categories default-excluded pending named cultural reviewer (mele/oli/pule, moʻolelo from named tradition-bearers, moʻokūʻauhau, ʻohana/ahupuaʻa place-name lore, pre-1925 nūpepa bulk, restricted community-archive material). **Surfaced open team gap: cultural-review owner is currently unassigned.** Until corpus inventory exists, plan is not a launchable pipeline. Next deliverable: corpus inventory + empty manifest with schema validation. See ADR in `.squad/decisions.md`.

## 2026-04-29T03:13:13Z — Stage-1 + Stage-2 pipelines consolidated into ADR

Scribe merged `linus-stage1-data-pipeline.md` and `linus-stage2-data-pipeline.md` from inbox into a single appended ADR in `.squad/decisions.md` ("Stage-1 monolingual + Stage-2 bidirectional en↔haw data pipelines (prototype)"). Inbox files deleted. Stage-2 ingest stays gated on Stage-1 artifacts + `eval_hashes.parquet`. Open gaps unchanged: cultural-review owner, Hawaiian-literate alignment/OCR spot-checker, pinned Bible edition rights, raw-archive storage location. README sequencing update flagged for a later Scribe pass.
