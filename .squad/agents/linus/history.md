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

### Data Pipeline Doc (2026-04-29T03:21:29Z)
- Authored `docs/data-pipeline.md`: Stage 1 monolingual Hawaiian DAPT/CPT + Stage 2 bidirectional en↔haw SFT.
- Includes source tiers, NFC/ʻokina/kahakō normalization, MinHash dedup, manifests (`stage1_manifest.parquet`, `stage2_manifest.parquet`), JSONL schemas, `eval_hashes.parquet` contamination guard, risks, next steps.
- Cross-linked with `docs/training-pipeline.md` (Basher) after Danny's polish.

## 2026-04-29 — Raw data gathering volume guidance (advisory)

User asked what to use for raw gathering and how much. Advisory only, no new ADR — gathering plan is consistent with existing Stage-1/Stage-2 ADRs in `.squad/decisions.md` and `docs/data-pipeline.md`.

Stage 1 raw-gathering order: hawwiki dump (validates pipeline) → Hawaiian Wikisource → one pinned Bible edition → Ulukau nūpepa (~125k OCR'd pages, the volume play, biggest unknown) → Awaiaulu/OHA/DOE/UH PDFs (manual, small).
- Cleaned-token target Stage 1: **10–30M Hawaiian tokens realistic, 5M floor below which DAPT probably isn't worth running, ~50M aspirational ceiling.** Confidence on nūpepa yield is low.
- Honest go/no-go gate: pilot ~5–10k nūpepa pages + run Rusty's tokenizer audit + token-count report before committing to bulk nūpepa pull.

Stage 2 raw-gathering order is hard-sequenced: **FLORES-200 first into `eval_hashes.parquet`** (~2k sentences, dev/test only, never train), then Bible verse-aligned (~31k verses, ≤30% cap), then Tatoeba, OPUS `haw` subsets (JW300 excluded pending ToS), NLLB-mined `haw`-`eng` (train-only, comparable), Wiki interlanguage + LaBSE alignment (<5k usable), Awaiaulu/OHA/DOE/UH bilingual PDFs.
- Cleaned-pair target Stage 2: **10k–30k parallel train pairs, ~1–2k dev/test pairs.** Binding constraint is the Bible ≤30% cap: if non-Bible parallel ends up <5k pairs, Bible has to be sampled down too.

What NOT to gather (unchanged from prior ADRs but reaffirmed): generic CommonCrawl haw-LID, social/forum content without permission, HF/Kaggle "Hawaiian dataset" artifacts as primary sources (use as pointers), JW300, hard-escalate cultural categories.

Manifest fields that must be captured **at fetch time** (unrecoverable later) — already in schema but worth restating: ToS snapshot per source/date, source_url fetch-resolved, fetch_date + http_status, sha256_raw, license_observed verbatim with license_inferred=null, source-specific IDs (Ulukau paper+issue+page, Bible edition+translator+year, OPUS subset+version, Wiki dump date, HF→upstream origin), cultural_flag pre-tagged at ingest, prototype_only=true default.

Flagged for a future Scribe / Linus edit (not done now): add a "raw-collection volume targets" subsection to `docs/data-pipeline.md` capturing the gathering-order rule (FLORES first), volume ranges, and the Stage-1 nūpepa-pilot go/no-go gate. Existing doc has cleaned-yield estimates and schemas but not raw-gathering volume guidance at this level.

## Learning — Tooling shortlist for raw data gathering (asked by yashasg)

For this prototype's Tier A/B sources (Ulukau, gov pages, curated dumps):
- **Default fetcher:** `requests` + `tenacity` (retry/backoff) for known URL lists; capture WARC via `warcio` so ToS snapshot + raw bytes are preserved per ADR.
- **HTML → text:** `trafilatura` (best signal/noise for prose; emits metadata) with `selectolax` or `lxml` as fallback.
- **Crawler framework:** `scrapy` only when a source needs link-following + politeness policies; `scrapy-warc` plugin to keep WARCs.
- **JS-heavy pages:** `playwright` (headless chromium) — last resort, slow, costlier provenance.
- **Bulk archive pulls:** `internetarchive` CLI + `wayback` for snapshots; `warcio`/`cdxj-indexer` to read.
- **OCR (nūpepa):** out of scope of "fetch," but pair with `pdf2image`+`tesserocr` or pre-OCR'd Ulukau exports.
- **Dedup helpers:** `datasketch` (MinHash) downstream — not a fetcher but lives in same pipeline.

Recommendation: start with `requests + tenacity + warcio + trafilatura`, add Scrapy only if a source's adapter needs crawl logic. Skip Playwright unless a source forces it.

## 2026-04-29 — Raw data deps setup script

- Added `scripts/setup.sh` (POSIX `sh`, idempotent) + `requirements.txt` at repo root. Script creates a local `./.venv`, upgrades pip/wheel, installs requirements; respects `PYTHON`, `VENV_DIR`, `REQ_FILE` env overrides; refuses to clobber a non-venv dir of the same name.
- Default stack: `requests`, `tenacity`, `warcio`, `trafilatura`, `selectolax`, `scrapy`, `scrapy-warc`, `internetarchive`, `wayback`, `cdx_toolkit`, `yt-dlp`, `datasketch`.
- **Playwright deliberately omitted** for the prototype. Ulukau/Wikisource/Bible/archive.org/Tatoeba/FLORES targets are static HTML or downloadable archives; JS rendering not worth the install cost yet. Revisit per-source if needed.
- Updated `.gitignore` to exclude `.venv/`, `.venv-*/`, `__pycache__/`, `*.pyc`. No README edit; the script is self-documenting and README is a design narrative, not a getting-started.
- Validation: `sh -n` and `bash -n` clean; no shellcheck available locally; full network install not run.
- No ADR — implements existing tooling guidance from prior data-pipeline notes; no decision file written.

## 2026-04-29 — Storage formats consolidated in data-pipeline.md

User asked what format the data should be stored in. Existing ADRs implied Parquet manifests + JSONL training text + `eval_hashes.parquet`, but `docs/data-pipeline.md` had no single subsection naming formats per layer. Added a "Storage formats" subsection (after Cross-stage invariants, before Stage 1) with a per-layer table.

Locked formats per layer:
- URL inventory: JSON in git (`docs/hawaiian-data-sources.json`).
- Raw web fetch: WARC (`.warc.gz`) via warcio/scrapy-warc; preserves request/response + ToS snapshot.
- Raw non-HTML originals: native bytes untouched, named by `sha256`, with `fetch.jsonl` sidecar.
- Extraction/intermediate: gzipped JSONL, one record per doc/page, OCR confidences attached here.
- Stage 1 manifest: `stage1_manifest.parquet` (zstd).
- Stage 1 training text: `stage1.jsonl.gz`; manifest fields stay out of training lines.
- Stage 1 packed: `.bin/.npy` + `index.json` sidecar with tokenizer hash.
- Stage 2 manifest: `stage2_manifest.parquet` (zstd).
- Stage 2 training text: `stage2.jsonl.gz` (two directional rows per pair + retention slice); `templates.json` separate.
- Contamination ledger: `eval_hashes.parquet` (zstd).
- Schemas & docs: JSON Schema + Markdown, in git.

Format rules captured: Parquet for manifests/hashes, JSONL for trainer-facing text; gzip (`.jsonl.gz`) for text >few MB, zstd for Parquet; one file per (source, fetch_date) at raw/extracted layers (re-fetches make new dirs); no CSV past bootstrap (quoting eats diacritics); hashes are the cross-layer join keys, never paths.

Wrote inbox decision proposal `linus-storage-formats.md` to lock this.

## 2026-04-29 — Storage location: local-first, not GitHub, not LFS

User asked "should we just put it in a github repo?" Closed the open gap from
prior ADRs ("raw archive storage location TBD"). Wrote
`.squad/decisions/inbox/linus-data-storage-location.md`.

Locked split:
- **In git:** code, schemas, docs, URL inventory (`data-sources/*.json`),
  `requirements.txt`, `scripts/`, ADRs.
- **Off git:** everything under `data/` — WARCs, extracted JSONL, both stage
  manifests, training JSONL, packed tensors, `eval_hashes.parquet`.
- **Where off-git lives (prototype):** local workstation tree at
  `IDEAL_SPOON_DATA_ROOT` (default `./data/`, gitignored), with one offline
  external-disk backup of `raw/` only. Everything else regenerable from raw +
  code. FileVault/LUKS at-rest encryption.
- **GitHub LFS rejected:** doesn't change the rights/redistribution story
  (private LFS still egresses to GH storage), wrong workload shape for
  WARC+Parquet, history-immutability is a takedown liability for
  rights-sensitive Hawaiian material, and clones get fat.
- **If local outgrows the disk:** single private Azure Blob container under
  the leftover-credit budget already approved in decisions.md. Same hash-keyed
  layout, SAS tokens, no public access. HF Datasets / Kaggle off the table
  until cultural-review owner is named and per-source rights are cleared.

Pre-emptive `.gitignore` addition for `data/` flagged as an action item but
deferred until proposal is accepted to avoid preempting the team review.

## 2026-04-29 — Rights-light Stage 1 MVP scope + go/no-go gate

User asked whether 2.5M–7M tokens of clear / right-clearable Stage 1
candidates (hawwiki + Wikisource + small reviewed long tail) is enough to
start, and whether we can avoid rights-review-heavy work for now.

Answer: yes for a prototype/plumbing Stage 1, no for a quality Stage 1 on a
7B–9B base. Wrote `.squad/decisions/inbox/linus-rights-light-stage1-mvp.md`
defining:

- **MVP IN:** every source tagged `open_license_candidate` or
  `public_domain_candidate` in `data-sources/hawaiian-data-sources.json` —
  hawwiki dump + dump status manifest, Hawaiian Wiktionary, Hawaiian
  Wikisource, pre-1925 Baibala scans (≤10% cap, religious-archaic register),
  plus a small per-doc-reviewed long tail.
- **MVP DEFERRED:** all `rights_review_required` /
  `unknown_review_required` entries — Ulukau nūpepa, Wayback CDX nūpepa,
  archive.org nūpepa mirrors, OPUS/NLLB haw slices (Stage 2 anyway),
  Baibala official site, OHA/DOE/UH bulk crawls, Awaiaulu, video
  transcripts.
- **"Rights-light" ≠ license-skipping:** per-doc `license_observed`,
  `source_url`, `fetch_date`, payload SHA-256, ToS snapshot all still
  required; `license_inferred=null` invariant unchanged.
- **Go/no-go gate before any rights-heavy ingest:** (1) MVP corpus exists
  end-to-end with manifest + packed tensors + CI lineage guard; (2)
  tokenizer audit done on MVP; (3) MVP token/register report published;
  (4) cultural-review owner named (long pole); (5) per-source rights
  review process written into decisions log; (6) storage + gitignore +
  encryption invariants verified.

No edits to `docs/data-pipeline.md` — existing Tier A/B framing already
sequences hawwiki-first; this proposal names the gate explicitly and
defines MVP scope by rights tag rather than by source name.

## 2026-04-29 — Stage 1 raw→training plan handed back to user

User asked for the practical sequence after Frank pulls raw rights-light data.
Produced an ordered workflow (intake → extract → normalize → langID → register
tag → dedup → split → JSONL emit → manifest write → CI guard → tokenizer audit
gate → packed tensors), tied to existing paths in `docs/data-pipeline.md`
(`data/raw/<source>/<fetch_date>/`, `data/extracted/`, `data/stage1/stage1.jsonl.gz`,
`data/stage1/stage1_manifest.parquet`, `data/eval/eval_hashes.parquet`,
`data/stage1/packed/`). Reaffirmed off-git boundary: only code, schemas, URL
inventory, ADRs, and tiny fixtures in GitHub; everything under `data/` stays
local under `IDEAL_SPOON_DATA_ROOT` with one offline backup of `raw/`.

Owners called out:
- Frank: raw fetch + WARC capture + ToS snapshot + raw fetch.jsonl sidecar.
- Linus: extraction → manifest → JSONL → split → contamination ledger.
- Rusty: tokenizer audit + packed tensors (gate to Stage 1 training).
- Basher: consumes packed tensors; not in this loop until gate passes.

Stop conditions stated: missing license_observed → drop row;
`license_inferred=null` invariant; eval ∩ train hash assertion in CI;
≤10% Baibala token cap; tokenizer audit must clear before any GPU spend.

No code/doc edits — plan is consistent with existing `docs/data-pipeline.md`
Stage 1 transformation pipeline and storage formats table. No ADR written;
the user asked for a plan, not a new decision.

## 2026-04-29T06:43:21Z — Raw-to-training pipeline plan (ordered workflow)

📌 **Team update:** Linus produced a complete 13-stage ordered workflow from Frank's raw fetch through Stage-1 training dataset, including extraction, normalization, LID, deduplication, eval-hash registration, tokenizer audit gate, and Basher handoff.

**Key plan points:**
- **Vertical-slice strategy:** Hawaiian Wikipedia first (smallest, cleanest), then add Wiktionary/Wikisource/Baibala/long tail.
- **Corpus stays local:** no git blobs, no HF uploads during prototype.
- **Rights-heavy sources deferred:** pre-1925 nūpepa bulk, Baibala, JW300 pending cultural-reviewer sign-off.
- **Manifest-first discipline:** every fetch-time field (ToS snapshot, source URL, fetch date, sha256_raw) registered at ingest (unrecoverable later).
- **Tokenizer audit is a hard gate:** Rusty's ʻokina/kahakō audit blocks Stage-1 export; no Stage-1 handoff without audit sign-off.
- **Dedup with cluster-aware split isolation:** MinHash clusters assigned to split uniformly; no similar-doc leakage into eval.
- **Three-way contamination guard:** `eval_hashes.parquet` (Stage-1 dev/test), cross-check Stage-2 eval, cross-check Stage-2 train via `crosslink_stage1_overlap`.

**Downstream:** Frank (raw fetch) → Linus (registration/LID/extraction/norm/dedup/eval-hash) → Rusty (tokenizer audit gate) → Basher (CI guard + training load).

**Open gaps flagged:** cultural-review owner (escalate to Coordinator), Bible edition pinning, raw archive storage location.

**Orchestration log:** `.squad/orchestration-log/2026-04-29T06-43-21Z-linus-raw-to-training-plan.md`


## 2026-04-29 — Stage-1 build script scaffolded

User asked: "how is linus going to do all of that, show me the scripts" (Python OK).
Wrote `scripts/build_stage1_dataset.py` — stdlib-only, wiki-only vertical slice.

Files touched:
- `scripts/build_stage1_dataset.py` (new, ~430 LOC, executable)

Script usage:
- `python scripts/build_stage1_dataset.py --dry-run` — validate provenance + heuristics, no writes.
- `python scripts/build_stage1_dataset.py --source hawwiki [--limit N]` — vertical slice.
- `python scripts/build_stage1_dataset.py --strict` — exits 2 on any quality-gate failure.

Upstream contract (Frank → Linus):
- Reads `data/raw/{source}/{fetch_date}/fetch.jsonl`, one JSON object per line, with at least:
  `path` (or `raw_path`/`filename`), `source_url`, `http_status`, `sha256_raw`, `content_type`,
  `license_observed`, `tos_snapshot_id`. Anything missing → recorded skip, not a guess.
- Raw blobs live untouched at `data/raw/{source}/{fetch_date}/...`. Wiki XML may be `.xml`,
  `.xml.gz`, or `.xml.bz2`; stdlib decompressors used.

Downstream contract (Linus → Rusty/Basher):
- `data/extracted/{source}/{fetch_date}/extracted.jsonl.gz` — per-doc cleaned text + sha hashes.
- `data/stage1/stage1_manifest.jsonl` — one row per surviving doc, schema = subset of the
  `stage1_manifest.parquet` ADR. Parquet is a follow-up read-this-jsonl pass once `pyarrow`
  is justified; deferred on purpose to keep stdlib-only.
- `data/stage1/stage1.jsonl.gz` — trainer-facing only:
  `{doc_id, text, source, register, split, prototype_only}`. Manifest fields excluded so the
  model can't memorize provenance. Only `language_id == "haw"` train rows go in.

Quality gates implemented (skip-with-reason, plus aggregate fail list):
- missing license_observed / sha256_raw / raw path → recorded skip.
- train ∩ (dev ∪ test) overlap on sha256_clean → failure.
- per-source token share > 60% → warn; Bible/Baibala > 10% → fail (placeholder; no Bible
  source in slice yet).
- missing sha256_clean / license per emitted doc → failure.

Normalization:
- NFC; ʻokina → U+02BB only when between two letters (conservative); kahakō untouched.
- Counter of swap events stored on each manifest row (`unicode_changes`).

Heuristic LID:
- Vowel-share + kahakō/ʻokina presence + foreign-letter penalty. Below 0.55 → `language_id`
  recorded as `unknown` with reason. Real LID is its own task; this only filters obvious junk.
- Verified end-to-end on a 3-page synthetic dump: 1 emitted to train JSONL, 1 retained in
  manifest as `unknown`, 1 empty page dropped.

Split assignment: deterministic `int(sha256(sha256_clean)[:8],16) % 100` → 0..89 train,
90..94 dev, 95..99 test. Stable across reruns.

What this script does NOT do (deferred, on purpose):
- MinHash dedup (`dedup_cluster_id` is currently sha256_clean stub).
- Real LID.
- Wiki markup cleanup beyond a crude regex pass.
- Parquet manifest.
- Cultural-flag inference (defaults to `none`).
- Eval-hash union write to `eval_hashes.parquet`.

Validated: `python3 -m py_compile`, `--dry-run`, real run on synthetic fixture, `--strict` exits 2.
No corpus committed. `.gitignore` confirms `/data/` ignores manifest, train JSONL, fetch.jsonl,
and extracted.jsonl.gz. Decision note written to `.squad/decisions/inbox/linus-stage1-jsonl-first.md`.

## 2026-04-29T06:56:07Z — Python Script Contracts: Stage-1 JSONL-First Approved

- **Scripts:** `scripts/build_stage1_dataset.py` validated via `python3 -m py_compile` — compiles clean.
- **Decision merged:** `linus-stage1-jsonl-first.md` approved and merged into `.squad/decisions.md` (inbox file deleted).
- **Stage-1 contract:** Output format is JSONL (`data/stage1/stage1_manifest.jsonl`), not Parquet. Parquet deferred until corpus > 50k docs or first DuckDB analytical query in CI.
- **Frank handoff:** Stage-1 consumes `data/raw/<source>/fetch.jsonl` (stable ProvenanceRecord schema, additive-only). Manifest-first discipline enforced.
- **Downstream ready:** Basher (contamination guard) and Rusty (tokenizer audit) aware; one-line change each to read JSONL until Parquet promotion.

## Learnings — Numbered pipeline script contract

- Pipeline scripts are now numbered to encode execution order. Current contract:
  1. `scripts/001_collect_rightslight.py` — plan rights-light sources (Frank).
  2. `scripts/002_fetch_rightslight_raw.py` — fetch raw artifacts + provenance JSONL (Frank).
  3. `scripts/003_build_stage1_dataset.py` — Stage-1 manifest from raw (Linus).
- Run order is `001 → 002 → 003`. New stages take the next free `NNN_` prefix; do not reorder old numbers.
- Updated docstrings, `generated_by`, `fetcher_tool_and_version`, cross-script comments, and `decisions.md` references. History logs left intact (mention old names as history).
- Validated: `python3 -m py_compile` and `--help` clean for all three; `002 --dry-run` and `003 --dry-run` exercise the new paths. Behavior and local-only data policy preserved.

## 2026-04-29T06:59:23Z — Orchestration: numbered scripts coordination logged

- Scribe wrote `.squad/orchestration-log/2026-04-29T06-59-23Z-numbered-pipeline-scripts.md` and `.squad/log/2026-04-29T06-59-23Z-numbered-pipeline-scripts.md`.
- Confirmed Linus references updated to numbered filenames throughout history and decisions.
- Frank history also appended with current filenames and manifest discipline note.
- All `.squad/` changes committed with trailer.

## 2026-04-29 — Stage-1 token-volume gate + 002↔003 schema fix

User flagged: "the fetch plan didnt pull enough raw data in the first place".
Two real problems behind the symptom:

1. **Schema mismatch hid 002's actual output.** `002_fetch_rightslight_raw.py`
   writes `data/raw/<source>/fetch.jsonl` (source-level) with `ProvenanceRecord`
   field names (`raw_sha256`, `raw_storage_path`, `tos_or_license_url`,
   `fetch_timestamp_utc`). `003_build_stage1_dataset.py` was walking
   `data/raw/<source>/<fetch_date>/fetch.jsonl` with field names `sha256_raw`,
   `path`/`raw_path`/`filename`, `tos_snapshot_id`. Net effect: 0 records seen
   even after 002 ran.

   Fix: rewrote `iter_fetch_records` + new `_coerce_record` / `_iter_manifest_paths`
   helpers. Loader now finds source-level `fetch.jsonl` (002 actual) and still
   accepts the legacy date-nested layout. Field aliases mean both schemas
   parse cleanly. `fetch_date` is derived from the YYYYMMDD parent dir of
   the raw artefact (or `fetch_timestamp_utc[:10]`) when not present.

2. **No mechanical token-volume gate.** `003` was reporting docs/splits/sources
   but not whether the corpus was actually big enough to call Stage-1 ready.
   On a near-empty manifest the summary looked green.

   Fix: added `TOKEN_TARGETS` (Conservative 2.5M / Base 4.5M / Upside 7M
   right-clearable train tokens) as first-class constants, a
   `compute_train_tokens` (sum over `split=train`, `language_id=haw`),
   and a `token_volume_report` block in every summary. `--strict` exits 2
   when train tokens fall below the conservative target. New CLI flags:
   `--token-target {conservative,base,upside}` and `--show-targets` (prints
   targets + current gap without needing a corpus download).
   Stage-1 doc updated to reference the mechanical gate.

**Discipline note:** the gate is right-clearable only. Closing the gap is
an upstream fetch-plan job for Frank, not a license relaxation; do not patch
by adding rights-heavy sources. This is called out explicitly in the stderr
warning and in the decision note.

Files touched:
- `scripts/003_build_stage1_dataset.py` — loader + targets + gate + flags
- `docs/data-pipeline.md` — one-line addition under Stage-1 next steps
- `.squad/decisions/inbox/linus-stage1-token-gate.md` — decision note

Validated:
- `python3 -m py_compile` clean.
- `--help` / `--show-targets` work with no data on disk.
- `--dry-run` on empty `data/raw/` reports `below_conservative=true` and
  warns on stderr.
- Local fixture with 002's actual schema (source-level `fetch.jsonl`,
  `raw_sha256`/`raw_storage_path`/`tos_or_license_url`, raw bytes under
  `data/raw/<source>/<YYYYMMDD>/<sha>.xml`) is discovered, one wiki doc
  emitted; `--strict --dry-run` exits 2 because tokens << 2.5M. Fixture
  removed; pre-existing `data/raw/rightslight` and `data/local/` left untouched.

## 2026-04-29 — Orchestrated Stage-1 token-gap correction (parallel with Frank)

Completed as part of paired agent session with Frank. Scribe consolidated outputs, merged decisions, filed orchestration log, and staged for git commit.

**Session outcome:**
- **Numbered pipeline convention locked:** 001_ (collect), 002_ (fetch), 003_ (build), with extension point for 004_+.
- **Schema handoff fixed:** 003 reads 002's source-level `fetch.jsonl` layout (raw_sha256, raw_storage_path, tos_or_license_url, fetch_timestamp_utc); backward compatible with legacy date-level paths; field-name aliases for older fixtures.
- **Token-volume gate first-class:** Conservative 2.5M / Base 4.5M / Upside 7M targets, mechanical go/no-go on conservative floor, exit code 2 in `--strict` mode below target.
- **New CLI flags:** `--show-targets` (print targets + gap, no corpus I/O), `--token-target {conservative|base|upside}` (select reported tier).
- **Token-volume block in every summary:** current train tokens, target, gap, `below_conservative` flag.
- **Right-clearable discipline:** gate does not add rights-heavy sources; closing the gap is Frank's upstream job (expansion candidates).
- All three numbered scripts validated via `py_compile` and CLI `--help`. `--dry-run` tests exercise renamed paths; no corpus committed.
- `.squad/orchestration-log/2026-04-29T07-19-07Z-linus.md` filed.
- Decisions merged into `.squad/decisions.md` as Accepted.

**Open follow-ups:**
- Frank: Expand fetch plan (Tatoeba, Wikisource, Wikipedia langlinks adapters).
- Rusty: Tokenizer audit to replace ±2× bands with ±20% bands.
- Coordinate Wikisource extracted-text contract (NFC sensitivity, ʻokina canonicalization).

## 2026-04-29 — Wikisource handoff: 003 dual-extractor dispatch

User: *"it looks like we need a separate 002 script for hawaiian wiki
source, just so that the scripts can maintain some sanity"*.

Source-fetcher implementation belongs to Frank; my scope is the
downstream contract so 003 can consume both the dump path and the
Wikisource per-page path without source-specific branching.

**Contract (filed in `.squad/decisions/inbox/linus-wikisource-handoff.md`):**
Wikisource fetcher reuses 002's `ProvenanceRecord` schema, writes to
`data/raw/hawwikisource/fetch.jsonl`. Builder dispatches by content
shape, not by source name:

- `wiki-xml-stream` ← Wikimedia `<mediawiki>` dump (existing path,
  untouched).
- `wikisource-pagetext` ← per-page artefacts under
  `data/raw/hawwikisource/<YYYYMMDD>/`. Four shapes accepted:
  plain `.txt`, raw wikitext (`.wiki`/`.wikitext`/`text/x-wiki`),
  MediaWiki API `.json` (`action=parse` or `query&prop=revisions`),
  bundled NDJSON (`.jsonl[.gz]` / `.ndjson` / `application/x-ndjson`).
  Per-page `page_id` / `title` ride in `source_specific_ids` for
  single-page artefacts, inline per line for bundles.

**Code changes (`scripts/003_build_stage1_dataset.py`):**
- New `extract_wikisource_pages` + `_coerce_page_dict` (handles plain
  shape, MediaWiki action=parse, action=query revisions, NDJSON).
- `process_record` now dispatches `is_wiki_xml` vs
  `is_wikisource_pagetext`; doc-emit factored into `_emit_pages` so
  both paths share one normalization/scoring/split body. ʻokina
  canonicalization, NFC, and deterministic splits unchanged.
- Module docstring updated to describe both extractors.

**`docs/data-pipeline.md`:** added the handoff contract block under
"Stage 1 immediate next steps" and extended the `extraction_method`
enum to include `wiki-xml-stream` / `wikisource-pagetext`.

**Validated (no real corpus pulled):**
- `python3 -m py_compile scripts/003_build_stage1_dataset.py` clean.
- `--help` and `--show-targets` work.
- Local fixture exercising both shapes (one `.wikitext` page + one
  NDJSON bundle of two pages) under
  `data/raw/hawwikisource/{fetch.jsonl,20260429/...}` produced 3 docs,
  all `split=train`, `language_id=haw`, `extraction_method=wikisource-pagetext`.
  Fixture removed.
- Existing `data/raw/hawwiki/fetch.jsonl` (real Frank manifest) still
  emits 4,896 hawwiki docs from the dump; the two metadata rows
  (`sha1sums.txt`, `dumpstatus.json`) remain `unsupported_content_type`
  skips because they're under `hawwiki`, not `hawwikisource` — token
  estimate 198,645 train tokens, identical to pre-change behaviour.

**Discipline:** I did **not** implement the fetcher; that's Frank's
scope. If Frank's storage choice (per-page files vs NDJSON bundle)
ends up needing fields I haven't keyed on, extend `_coerce_page_dict`
without touching `_emit_pages`.

**Open follow-ups:**
- Frank: implement `002b_fetch_hawwikisource_raw.py` and confirm
  storage shape.
- Rusty: flag wikitext residue in the tokenizer audit; current
  `_crude_dewiki` is prototype-grade and does not strip Wikisource-
  specific `{{header}}` / `<pages index=...>` proofread wrappers
  beyond the generic template-strip pass.

### Phase-hundreds script numbering (2026-04-30)
- User corrected the earlier `001/002/002b/003` flat numbering. New
  convention: **collect = 1xx, fetch = 2xx, build = 3xx**, with
  intra-phase suffixes assigned in landing order (`101`, `102`, …).
- Current files after the rename:
  - `scripts/101_collect_rightslight.py` (Frank, collect).
  - `scripts/201_fetch_rightslight_raw.py` (Frank, fetch — Wikimedia
    dump path: `hawwiki`, `hawwiktionary`).
  - `scripts/202_fetch_hawwikisource_raw.py` (Frank, fetch —
    Hawaiian Wikisource MediaWiki API path).
  - `scripts/301_build_stage1_dataset.py` (Linus, build — Stage-1
    manifest from `fetch.jsonl`).
- Rule of thumb when adding a new script: pick the next free number
  in the relevant phase. No more `b`-suffix new adapters; that is
  what `2xx` slots are for.
- Rewrote path/prose references across `scripts/*.py`,
  `docs/data-pipeline.md`, and pending inbox files. Left
  `.squad/decisions.md`, agent histories, and orchestration logs
  untouched — they are historical records of what was true at the
  time.
- Decision note: `.squad/decisions/inbox/linus-phase-numbering.md`.

### 2026-04-29 17:58:36Z — Scribe consolidation: 100-phase refactor confirmed, 202 consumes 102 page plans

Frank's source-specific 100-phase split is now the active standard across the team. Key consolidation points affecting downstream work (Linus → 301_build_stage1_dataset.py):

- **100 phase is now source-specific:** `101_collect_hawwiki.py`, `102_collect_hawwikisource.py`, `103_collect_hawwiktionary.py` replace the single broad `101_collect_rightslight.py`. Each emits a JSON plan file under `data/local/<source>/`.
- **202 consumes 102 page plans:** Wikisource page-fetch planner (`102_collect_hawwikisource.py`) writes `data/local/hawwikisource/page_plan.jsonl`; `202_fetch_hawwikisource_raw.py` now defaults to reading this plan (`--page-plan PATH`, fallback to direct enumeration if missing).
- **ProvenanceRecord schema unchanged:** `fetch.jsonl` rows still carry the same provenance shape. No 301-side changes required.
- **No corpus fetched.** All validation passed; git status clean.

Future sources should follow the same pattern: new `10X_collect_<source>.py` script → JSON plan → corresponding `2XX_fetch_<source>_raw.py` with optional plan-consumption flag → 301 source dispatch unchanged.

Broad planner (`001`–`003` phase-numbering era) now archived in decision history.

### 2026-04-29 09:18:58Z — Frank FineWeb-2 verification complete; Linus rights & dependency call pending

**From Scribe:** Frank (Hawaiian Data Collector) has verified FineWeb-2 `haw_Latn` dataset access:
- **95,507 train + 887 test rows, confirmed live**, ODC-By wrapper license, ungated + unauthenticated access.
- **12 fields including provenance** (url, date, dump, language_score, etc.) ship in-row.
- **Two access paths both working:** `datasets-server.huggingface.co/rows` (stdlib-friendly) and parquet auto-conversion (stable URLs).

**Your blocking decision (in order of urgency):**
1. **Rights posture:** ODC-By wrapper vs. per-URL allow/deny — accept FineWeb-2 rows wholesale at prototype scope, or impose blocklist (e.g., drop `*.staradvertiser.com`, keep `*.wikipedia.org`)?
2. **Dependency:** add `pyarrow` (+ optionally `huggingface_hub`) to `requirements.txt`, or stay stdlib-only via slower rows API?

**Implications:**
- Pending your rights call, scripts `105_collect_fineweb2_haw.py` + `205_fetch_fineweb2_haw_raw.py` can land as the next numbered adapters (or `104`/`204` if renumbering the existing FineWeb slot).
- Estimated yield: 40–80M raw tokens, single biggest unblocker for Stage-1 floor without touching nūpepa.
- English boilerplate is known (Kauakūkalahale demo sample shows English headers/footers); cleaning is downstream (your + Rusty's pipeline, not fetcher scope).

**Reference:** `.squad/decisions.md` → "Decision: FineWeb-2 `haw_Latn` Access Verified Live" (appended 2026-04-29T09:18:58Z).

### 2026-04-29 09:27:41Z — Rusty + Frank complete Hawaiian dataset variant audit

**From Scribe:** Two major audits completed and merged into decisions.md:

**Rusty (NLP Researcher) — Language/Script Code Normalization:**
- Confirmed `haw_Latn` canonical (ISO 639-3 + ISO 15924), with three acceptable variants: `haw-Latn` (BCP-47 hyphenated), bare `haw` (OPUS/Tatoeba), `hawn_Latn` (FLORES-Plus 4-letter, real alias not a bug).
- Provided deterministic normalization: explicit allow-list matching (never prefix-match), hard requirement for `source_language_config` (verbatim provider string) and `source_language_resolved` (our decision).
- False-positive inventory: `hwc` (Hawaiian Pidgin, distinct language), `hau` (Hausa), filename acronyms, English boilerplate in FineWeb-2 high-LID rows (needs paragraph-level re-LID).
- Recommended new manifest columns: `script_iso15924` (Latn), `source_language_config` (audit trail), `source_language_resolved` (our normalized interpretation).

**Frank (Hawaiian Data Collector) — HF Dataset Inventory:**
- 14 real Hawaiian configs found on HF beyond FineWeb-2 `haw_Latn`.
- **Key new sources:** GlotCC-V1 `haw-Latn` (independent CC filter for dedup), DCAD-2000 `haw_Latn` (free second-opinion filter), finepdfs `haw_Latn` (PDF modality, likely Ulukau overlap), `haw_Latn_removed` (recall pool, contingency only).
- **Critical finding:** FLORES / FLORES+ / FLORES-200 have **no Hawaiian**. Current `data-pipeline.md` §300 hedge ("If `hawn_Latn` is included") is false.
- **Stage 2 eval alternatives:** global-piqa-parallel (preferred), Taxi1500, Tatoeba held-out, BibleNLP (edition-pinned).

**Your follow-up actions (in order of urgency):**
1. **Data-policy review:** Is `haw_Latn_removed` (filter-rejected pool) allowable under prototype policy, even tagged? Frank defaults to "no, unless yield gate fails."
2. **DCAD-2000, finepdfs rights:** Confirm rights posture of these new sources.
3. **Rusty's normalization rules:** Incorporate into `data-pipeline.md` manifest schema (add the three new columns).
4. **FLORES correction:** Flag to Danny for docs update (FLORES is gone; eval anchor TBD).

**Reference:** `.squad/decisions.md` → "ADR: Hawaiian Language/Script Code Normalization" + "Inventory: Hawaiian Dataset Variants Beyond FineWeb-2 `haw_Latn`" (appended 2026-04-29T09:27:41Z).

### 2026-04-29 09:40:34Z — FineWeb-2 haw_Latn 100/200 scripts landed, awaiting Linus dep + rights ruling

**From Scribe:** Frank delivered `scripts/105_collect_fineweb2_haw.py` (100-phase planner) and `scripts/205_fetch_fineweb2_haw_raw.py` (200-phase fetcher) for FineWeb-2 `haw_Latn`. Live smoke test confirmed 2 real rows, 1,028 raw whitespace tokens from staradvertiser.com.

**Your open decisions:**
1. Dependency call: add `pyarrow`/`huggingface_hub` to `requirements.txt` or stay stdlib-only? Scripts default to rows API; parquet is opt-in with loud failure.
2. Per-URL rights posture: accept rows wholesale at prototype scope, or enforce per-URL allow/deny list? (205 preserves per-row `url` for downstream policy enforcement in 301.)

**Reference:** `.squad/decisions.md` → "Decision Note: FineWeb-2 `haw_Latn` 100/200 Scripts Landed" (merged 2026-04-29T09:40:34Z).
