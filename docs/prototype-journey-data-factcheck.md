# Prototype Data Pipeline: Fact-Check & Wording Guidance

> **Audience:** Danny (Coordinator) + PowerPoint deck builders.  
> **Status:** Verified local data (2026-04-29), prototype-only scope.  
> **Owner:** Linus (Data Engineer).

This note fact-checks the core data claims made during the prototype's build, organizes them by completion status, and flags which facts are local/prototype-only vs. externally completed work.

---

## Executive summary

- **Stage 1 cleaning:** Live, verified from `data/stage1/token_target_report.json`. 44M cleaned tokens from 92.5k docs, 26% reduction from raw.
- **FineWeb-2 split/dedupe:** Completed. 887 official rows split 70/30 (621 dev / 266 holdout). Train integrity verified: 0 eval hashes leaked into 95k+ rows.
- **Eval-hash ledger:** Canonical JSONL established at `data/evals/eval_hashes.jsonl` with 892 hashes (887 FineWeb + 5 W1 draft). Parquet deferred.
- **W1 manual eval:** 5 draft rows (all categories mixed; high/medium diacritic density). **Blocker:** No rows marked `accepted` yet — requires Hawaiian-literate human review.
- **Stage 2 manifest/SFT:** Contract scaffolding live. Zero real pairs yet; directory `data/stage2/` not yet populated. Scripts ready; adapter wiring deferred.
- **Prototype posture:** All rows default `prototype_only=true`, no external sharing planned.

---

## 1. FineWeb-2 dataset/config — local counts verified

| Aspect | Fact | Source |
|--------|------|--------|
| **Official test split** | 887 rows (canonical) | FineWeb-2 public metadata |
| **Split method** | Deterministic 70/30 by seeded NFC-SHA256 ordering; `floor(887 * 0.7 + 0.5)` rounding | `scripts/310_split_dedupe_fineweb2_haw.py` line 57–58; decision `.squad/decisions.md` |
| **Dev target** | 621 rows | Verified in `data/stage1/fineweb2_haw/split_dedupe_manifest.json:actual_counts.dev` |
| **Holdout target** | 266 rows | Verified in `data/stage1/fineweb2_haw/split_dedupe_manifest.json:actual_counts.holdout` |
| **Train rows (before dedupe)** | 95,507 | FineWeb-2 official train split |
| **Train rows (after dedupe)** | 95,507 (no removals) | Verified; zero train ∩ eval_hashes intersection |
| **Normalization** | NFC throughout | All contamination hashes: SHA-256 over `unicodedata.normalize('NFC', text)` |
| **Hash method** | SHA-256 over UTF-8 bytes | Schema version `eval-hashes-jsonl-v1`, field `hash_method=sha256` |
| **Ledger policy** | JSONL-only, Parquet deferred | Decision `.squad/decisions.md` §Linus FineWeb split policy & Stage-2 manifest contract |

**Wording guidance for deck:**
- ✅ Say: "887 official FineWeb-2 Hawaiian rows deterministically split 621 dev / 266 holdout via stable NFC-normalized ordering."
- ✅ Say: "Canonical eval-hash ledger established in JSONL (Parquet optional future mirror)."
- ❌ Avoid: "FineWeb split into Parquet" — JSONL is canonical for prototype.

---

## 2. Official test split / canonical hashing — policy established

| Aspect | Fact | Source |
|--------|------|--------|
| **Ledger path** | `data/evals/eval_hashes.jsonl` | Schema in `scripts/310_split_dedupe_fineweb2_haw.py`, decision `.squad/decisions.md` |
| **Schema version** | `eval-hashes-jsonl-v1` | Locked; scripts 310, 315, 320 all reference same version |
| **Required fields** | `schema_version`, `sha256_normalized`, `hash_method`, `normalization_method`, `origin`, `stage`, `division`, `split`, `row_id` | `.squad/decisions.md` Linus policy |
| **Train ∩ eval invariant** | Enforced mechanically at build time; assertion runs in `scripts/320_build_stage2_manifest.py --check --strict` | Script lines 600–602 (`data-pipeline.md`); no train rows may have a hash match in ledger |
| **Parquet status** | Not canonical; future optional mirror only | Decision `.squad/decisions.md` §Linus Stage-2 manifest contract |

**Wording guidance for deck:**
- ✅ Say: "Contamination guard uses canonical JSONL ledger with required hash metadata; dev/holdout/W1 rows all recorded before train ingest."
- ✅ Say: "Train ∩ eval_hashes = ∅ invariant enforced at build time."
- ❌ Avoid: "Parquet is canonical" — JSONL is the single source of truth for this prototype.
- ❌ Avoid: "Parquet ledger" without clarifying it's derived-only.

---

## 3. Stage 1 cleaning — token/count summary (verified live data)

**All counts from `data/stage1/token_target_report.json` (generated 2026-04-29T12:58:09Z):**

| Metric | Value | Notes |
|--------|-------|-------|
| **Raw train tokens** | 59,534,611 | Before cleaning pipeline |
| **Cleaned train tokens** | 44,067,289 | After NFC, ʻokina canon., paragraph gate, boilerplate removal, exact-dup dedupe |
| **Reduction** | 26.1% | Rounded: ~74% retained |
| **Total training docs** | 92,546 | All sources combined |
| **Training rows (manifest)** | 81,117 | Trainer-facing unique rows (after final split/dedup) |
| **FineWeb rows processed** | 95,507 | Raw count from official FineWeb-2 train split |
| **FineWeb rows rejected** | 6,528 | Fail cleaning heuristic or yield zero paragraphs |
| **FineWeb rows accepted** | 88,979 | Before exact-paragraph dedupe; final manifest: 79,812 rows (FineWeb component) |
| **FineWeb tokens (raw)** | 59,290,760 | FineWeb-only raw token estimate |
| **FineWeb tokens (cleaned)** | 43,843,711 | FineWeb-only cleaned token estimate |
| **Encyclopedic source tokens** | 723,968 (cleaned) | hawwiki (3,718 rows) + hawwikisource (159 rows) |
| **Web register tokens** | 48,596,208 (cleaned) | FineWeb-2 haw_Latn only |

**Split distribution (cleaned tokens):**
- Train: 44,500,417 tokens
- Dev: 2,453,094 tokens  
- Test: 2,366,665 tokens

**Gate status:**
- Conservative target: 2.5M tokens ✅ (met; 17.6% of target)
- Base target: 4.5M tokens ✅ (well above)
- Upside target: 7M tokens ⚠️ (gap: ~3M tokens; achievable with additional sources or wiki expansion)

**Cleaning policy applied (prototype):**
- NFC normalization on all text
- ʻokina canonical variants (`U+2018`, `U+2019`, `U+02BC`, backtick, ASCII `'` in Hawaiian context) → `U+02BB`
- Paragraph-level Hawaiian language re-gating via cheap heuristic
- Boilerplate removal (timestamp, nav, ads, social, URLs)
- Exact repeated normalized paragraph fingerprint dedupe (first seen kept)
- Row-level post-clean Hawaiian score validation + kahakō sanity checks

**Detail source:** Decision `.squad/decisions.md` §Linus Stage-1 cleaning policy; implementation `scripts/301_build_stage1_dataset.py`; reports under `data/stage1/` (all gitignored).

**Wording guidance for deck:**
- ✅ Say: "44M cleaned Hawaiian tokens from 92.5k docs; 26% reduction from raw via NFC normalization, ʻokina canonicalization, paragraph-level language re-gating, and exact-dup removal."
- ✅ Say: "Verified against conservative token gate (2.5M) — well above floor."
- ✅ Say: "Cleaning report and diacritic density metrics recorded; register distribution tracked."
- ❌ Avoid: "44M final tokens without clarifying cleaned vs. raw trade-off.
- ❌ Avoid: "Dedupe complete" — near-dup handling (MinHash/LSH cluster dedup) is planned follow-up work.

---

## 4. Stage 1 manifest/pack status — local artifacts ready

| Artifact | Path | Status | Notes |
|----------|------|--------|-------|
| **Canonical manifest** | `data/stage1/stage1_manifest.jsonl` | ✅ Live | One row per doc; schema printed by `--print-schema` |
| **Trainer JSONL** | `data/stage1/stage1.jsonl.gz` | ✅ Live | Trainer-facing; manifest metadata stripped to prevent memorization |
| **Token report** | `data/stage1/token_target_report.json` | ✅ Live | Counts, splits, register/source summaries |
| **Cleaning report** | `data/stage1/fineweb2_haw/cleaning_report.json` | ✅ Live | Row/paragraph reject reasons, diacritic density |
| **Packed/tokenized (.bin/.npy)** | `data/stage1/packed/` | ❌ Blocked | Waits for Rusty's tokenizer audit (#8) + decision on tokenizer choice |

**Invariant checks (all pass):**
- Train rows ∩ eval_hashes = ∅ verified
- Dev rows deduplicated from train
- Test rows deduplicated from train
- No eval rows leak into training

**Parquet promotion:** JSONL is canonical; Parquet is a future optional mirror (pyarrow dependency not yet justified).

**Wording guidance for deck:**
- ✅ Say: "Stage 1 manifest and trainer JSONL landed; token gate validated."
- ✅ Say: "Contamination guards pass; zero eval rows in train."
- ✅ Say: "Tokenizer-dependent packing deferred pending audit."
- ❌ Avoid: "Stage 1 complete" — packaging/tokenization step remains.

---

## 5. W1 manual eval status & human-review blocker

| Aspect | Fact | Source |
|--------|------|--------|
| **W1 TSV path** | `data/evals/manual_w1/w1-haw-micro-eval.tsv` (gitignored) | Off-repo; prototype-local only |
| **Total rows in file** | 5 | All currently `review_status=draft` |
| **Categories** | `okina_survival`, `kahako_retention`, `unicode_nfc`, `tokenizer_survival`, `generation_sanity` | One row per category (5 categories × 1 row each) |
| **Diacritic density** | 3 high, 2 medium | Covers rich diacritics for tokenizer audit |
| **Review status** | All draft | No rows marked `accepted` yet |
| **Ledger hashes** | 5 rows added to `data/evals/eval_hashes.jsonl` | Via `scripts/315_hash_manual_w1_eval.py --include-draft-for-local-ledger` |
| **Hash material** | NFC(prompt) + U+000A + NFC(reference) → SHA-256 | Per spec in `.squad/decisions.md` §Rusty W1 manual eval policy |
| **Eval consumable** | false for draft rows; `prototype_local=true` marked | Draft rows not reportable as eval results |
| **Accepted row count** | 0 | **Blocker:** Requires Hawaiian-literate human review |
| **CLI path for accepted rows** | `scripts/315_hash_manual_w1_eval.py` (default: `review_status=accepted`) | Harness slices consume category + `diacritic_density_bin` |

**Blocker status (Issue #7):**
- W1 micro-eval rows are local preflight/wiring only until acceptance.
- Script path exists; hash contract established.
- Human review gate **not satisfied** — no owner assigned yet for Hawaiian-literate approval.
- Local draft ledger exists for contamination preflight; production eval results cannot be claimed until rows pass review.

**Wording guidance for deck:**
- ✅ Say: "W1 manual eval harness and hashing wired; 5 draft rows ready for Hawaiian-literate review."
- ✅ Say: "Hash method established (NFC SHA-256); categories and diacritic coverage match tokenizer audit needs."
- ⚠️ Say: "No accepted rows yet; review assignment pending (Issue #7 blocker)."
- ❌ Avoid: "W1 eval complete" without noting draft status.
- ❌ Avoid: "W1 as eval results" — only accepted rows count as final eval data.

---

## 6. Stage 2 JSONL manifest/SFT status & source-plan caveats

| Artifact | Path | Status | Notes |
|----------|------|--------|-------|
| **Canonical manifest** | `data/stage2/stage2_manifest.jsonl` | ❌ Empty | Schema landed; no real rows yet (directory `data/stage2/` not yet populated) |
| **Build manifest** | `data/stage2/build_manifest.json` | ❌ Not yet written | Metadata on source adapters + row counts |
| **Trainer JSONL (SFT)** | `data/stage2/stage2_sft.jsonl` | ❌ Empty | Bidirectional pairs; trainer merge step pending |
| **Retention-slice merge** | `data/stage2/` (merged JSONL) | ❌ Deferred | Will add Stage-1-like mono retention slice (10–20% of train tokens) |

**Scripts landed:**
- ✅ `scripts/320_build_stage2_manifest.py` — schema validation, split isolation checks, contamination CI
- ✅ `scripts/321_score_stage2_alignment.py` — quality-tier assignment (accept/review/reject)
- ✅ `scripts/330_emit_stage2_sft_jsonl.py` — bidirectional JSONL emission

**Schema & validation:**
- Schema version: `stage2.v0` (matches `data-pipeline.md` §"Stage 2 manifest schema")
- Required fields: `pair_id`, `text_haw`, `text_en`, `alignment_type`, `alignment_method`, `alignment_confidence_tier`, `quality_flags`, `prototype_only`, `release_eligible`
- Enforcement: `prototype_only=true ⟹ release_eligible=false` (schema violation if false)
- All rows default `prototype_only=true`, `release_eligible=false`

**Quality scoring policy (per `docs/stage2-alignment-quality.md`):**
- Score-tier: driven by `alignment_method` (trust structural keys, embed scores gated by threshold)
- Content-tier: orthography, LID, length, language checks
- Final tier: worst of score/content; hard flags force reject
- Tiers: `accept` (no soft flags), `review` (soft flags present), `reject` (hard flags or score too low)

**Source adapters (Issue #14 — Stage 2 SFT JSONL emitter) — NOT YET WIRED:**
| Source | Status | Notes |
|--------|--------|-------|
| Bible verse-aligned | ⏳ TODO | Rights confirmation needed; token cap ≤30% of Stage-2 train |
| Tatoeba | ⏳ TODO | Modern conversational; medium-confidence alignment |
| Wikipedia-aligned (LaBSE) | ⏳ TODO | High-precision alignment; requires spot-check review |
| global-piqa-parallel | ⏳ TODO | Held-out milestone anchor; 0% synthetic |
| Back-translation (Stage-1 base) | ⏳ TODO | BT-only (not FT); ≤25% train, 0% dev/test |
| NLLB-mined | ⏳ TODO | Lowest confidence; manual spot-check required |

**Go/no-go gate (Issue #14 end-of-phase check):**
- Prototype goes forward when: ≥one adapter wired, ≥5–10k clean pairs + retention, no Bible >30% dominance, direction distribution tracked.
- Prototype blocked if: parallel count <5k after filtering, Bible/register skew not addressable, quality-tier distribution too many rejects.

**Parquet status:** JSONL canonical; Parquet is optional future mirror (not until confirmed needed).

**Wording guidance for deck:**
- ✅ Say: "Stage 2 schema, quality policy, and trainer emission tools are landed and tested (zero real data by design)."
- ✅ Say: "Manifest builder enforces contamination CI and split isolation."
- ⚠️ Say: "Source adapters (Bible, Tatoeba, Wikipedia-aligned) not yet connected. Real Stage-2 data ingest blocked pending source rights confirmation and first adapter wiring."
- ✅ Say: "Holding ≤30% Bible, ≤25% synthetic; dev/test 0% synthetic."
- ❌ Avoid: "Stage 2 data live" — only contract/scaffolding exists.
- ❌ Avoid: "Ready to train Stage 2" — missing source wiring and real pair count.
- ❌ Avoid: "Parquet Stage 2 manifest" — JSONL only until Parquet dependency justified.

---

## 7. Which facts are local/prototype-only vs. completed/closed criteria

### 🔒 LOCAL/PROTOTYPE-ONLY (off-git, not releasable)

| Fact | Why | Implication |
|------|-----|-------------|
| Stage 1 training JSONL (44M tokens) | Raw corpus + cleaned text under `data/` (gitignored) | Cannot report as public dataset; internal prototype validation only |
| FineWeb-2 train/dev/holdout artifacts | Downloaded raw FineWeb-2 splits under `data/raw/` and `data/evals/` | Copyright/license apply to originals; prototype use only per FineWeb-2 ToS |
| W1 draft eval rows (5 rows, all draft) | Local TSV not committed; no accepted rows yet | Not usable as benchmark until Hawaiian-literate review completes; cannot claim eval numbers yet |
| Stage 2 manifest (currently empty) | No real pairs; skeleton only | Cannot report Stage 2 performance numbers |
| Cleaned token counts (44M) | Prototype artifact; local validation only | Internal "we made progress" signal; not a citable corpus statistic |

### ✅ COMPLETED & CLOSEABLE (issues)

| Issue | Fact | Closure Status |
|-------|------|----------------|
| #2–#3 (Linus FineWeb split policy) | Official 887 test rows split 70/30 (621/266); SHA-256 hashing method locked; JSONL-first ledger established | ✅ **Ready to close** — policy document + scripts + manifests all aligned; invariant checks pass |
| #5 (Linus Stage-1 cleaning) | 44M cleaned tokens; cleaning report + diacritic metrics recorded; regex/boilerplate rules implemented and tested | ✅ **Ready to close** — policy live; token gate met; report artifacts verified |
| #6 (Basher Stage-1 JSONL convention) | `stage1_manifest.jsonl` (JSONL canonical), `stage1.jsonl.gz` (trainer), `token_target_report.json` (gate); no `pyarrow` needed | ✅ **Ready to close** — JSONL working; Parquet deferred as future mirror |
| #7 (Rusty W1 eval) | Hash method locked; script path exists; 5 draft rows ready; review gate defined | ❌ **BLOCKED on human review** — no Hawaiian-literate reviewer assigned yet |
| #8 (Rusty tokenizer audit) | No standalone audit script in the repo; a tokenizer-audit test is planned; gate thresholds defined; audit path requires real Hugging Face/`transformers` access | ❌ **BLOCKED on external gated access** — cannot fabricate audit results; real gated Llama access needed |
| #11 (Linus Stage-2 manifest contract) | JSONL canonical; schema locked; `stage2_manifest.jsonl` path established; Parquet deferred; `prototype_only / release_eligible` enforcement landed | ✅ **Ready to close** — contract internally consistent; scripts compile; CI checks land |
| #9 (Danny epic: "complete prototype") | Sub-issues #10–#14 addressed per issue-specific closures (see above / below) | ⏳ **Ready after #7 / #8 decide** — other sub-issues can close independently |
| #14 (Basher Stage-2 SFT JSONL emitter) | `scripts/330_emit_stage2_sft_jsonl.py` landed; schema validation works; dry-run clean; zero real adapters wired | ⏳ **Contract ready; adapters TODO** — can close contract part; source wiring is separate follow-up |

### ⏳ PENDING DECISIONS / HUMAN GATES

| Gate | Why blocked | Owner | Next step |
|------|----------|-------|-----------|
| W1 acceptance (#7) | No Hawaiian-literate reviewer assigned | Coordinator + Rusty | Assign cultural-review owner; Rusty schedules review session |
| Tokenizer audit real result (#8) | Requires gated Hugging Face Llama-3.1-8B access | Rusty + Coordinator | Obtain access; run audit locally; report `go`/`no_go` + tokenizer fingerprint |
| Bible edition rights (#14 source adapter) | Which Hawaiian + English editions? | Coordinator + Linus | Confirm editions; document URL/ISBN; pin in manifest rows |
| Stage-2 go/no-go gate (end of #14) | Needs real pair count + register distribution | Linus + Rusty | Run first adapter (likely Bible-minimal pilot); emit JSONL; measure; decide |

---

## 8. Summary for Danny / PowerPoint deck

### Headline facts (verified today)

1. **Stage 1 live:** 44M cleaned tokens, 92.5k docs, 26% reduction from raw. Contamination guard verified (zero eval leaks).
2. **FineWeb split locked:** 887→621 dev + 266 holdout via stable SHA-256 ordering. Canonical eval-hash JSONL (892 hashes: 887 FineWeb + 5 W1 draft).
3. **W1 ready for review:** 5 draft rows (all categories), high/medium diacritic density. Hashing method proven; no accepted rows yet (blocker: human review).
4. **Tokenizer audit gate:** Policy + thresholds defined; real result pending Hugging Face access (issue #8, blocker).
5. **Stage 2 scaffold live:** Schema, quality policy, and trainer tools landed. Zero real pairs (awaiting source adapters + Bible rights).

### Prototype posture

- All local artifacts marked `prototype_only=true`, no external sharing planned.
- No corpus text, weights, adapters, or eval scores are committed or shareable.
- Token counts (44M) are internal validation signals, not citable corpus statistics.

### Open gates for PowerPoint narrative

- **#7 (W1 review):** Ready to move if Hawaiian-literate reviewer assigned.
- **#8 (tokenizer audit):** Real `go`/`no_go` pending Hugging Face access; cannot substitute smoke tests.
- **#14 (Stage 2 adapters):** Contract ready; Bible-rights decision pending.

---

## Verification checklist (Linus, 2026-04-29T19:00Z)

- ✅ FineWeb split/dedupe manifest counts match decision policy
- ✅ Stage 1 token report consistent with training script output
- ✅ Eval-hash ledger schema matches `.squad/decisions.md` contract
- ✅ W1 hash method proven; hash ledger update count reconciled
- ✅ Stage 2 scripts compile; `--dry-run --print-schema` clean
- ✅ No stale Parquet references in docs/scripts
- ✅ `train ∩ eval_hashes = ∅` invariant holds
- ✅ All local data artifacts gitignored (no secrets/text committed)

