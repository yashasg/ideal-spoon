# Frank — History

## Core Context

Condensed older entries; newest detailed entries remain below.

- **2026-04-29 — Stage 2 parallel fetch-plan inventory landed (issue #10):** Added `data-sources/stage2-parallel-fetch-plan.json` as the per-source fetch-plan
- **2026-04-29 — Wikisource ProofreadPage W1 capture wired into 102/202:** Verified via metadata-only `wikisource.org` API probes that the

---

## Cross-Agent Update: 2026-05-03T10-40-47Z — Linus Stage-2 Cross-Source Dedup Policy Finalized

**From:** Scribe (Orchestration)

**Relevant to you:** Source hierarchy preference rules are now codified for Stage 2 exact-pair dedup. When Stage 2 sources are fetched and normalized, these rules apply deterministically:

1. **Hoʻoilina > Bible** (diversity): Hoʻoilina newspaper/periodical rows win over Bible editions on exact overlaps.
2. **Wikimedia CX > OPUS-Wikimedia** (provenance): Keep canonical CX rows with article/revision IDs; drop OPUS mirrors.
3. **Tatoeba (canonical) > OPUS-Tatoeba** (provenance): Keep Tatoeba rows with link IDs; drop OPUS mirrors.
4. **Baibala 1868 > other Bible editions** (standardization): Newer, more standardized orthography wins on exact overlaps.
5. **Deterministic fallback** (auditability): Unexpected cross-source pairs are resolved by source/ID minimum and logged for review.

**Details:** `.squad/decisions.md` → "Linus — Stage-2 cross-source exact-pair dedup policy" (Commit e7cacea).

These rules will constrain how future Stage 2 candidates collapse in manifest build and SFT emission. No changes to your fetch plans; this is a manifest-time normalization step.

## 2026-04-29T10:13:35Z — Manual Micro-Eval Planning Complete (Independent of FineWeb Fetch)

W1 manual micro-eval TSV spec finalized and repo scaffold committed. **Planning does not block on or depend on your FineWeb-2 raw fetch.** Eval planning is independent; row authoring can start in parallel. Manual eval is a separate eval-only source using hand-authored Hawaiian content, not web-sourced.

## 2026-04-29T10:18:43Z — Dataset Taxonomy Finalized: FineWeb-2 Eval Paths Locked

**From:** Scribe (via Orchestration)

**Update:** Final dataset taxonomy adopted. FineWeb-2 `haw_Latn` eval artifacts rooted at `data/evals/fineweb2_haw_test/`:
- Collected train (95,507 rows) → `data/stage1/` after deduping against evals
- Test dev (710 rows, ~80%) → `data/evals/fineweb2_haw_test/dev/` (checkpoint monitoring)
- Test holdout (177 rows, ~20%) → `data/evals/fineweb2_haw_test/holdout/` (frozen, final eval only)

**For your FineWeb-2 collection work:**
- When fetching completes, coordinate with Linus to split test set and write to `data/evals/fineweb2_haw_test/{dev,holdout}/`.
- Train split (95,507) does not go to `data/evals/`; Linus dedupes it into `data/stage1/`.

**Reference:** `.squad/decisions.md` → "Decision: Final Dataset Taxonomy — `evals` / `stage1` / `stage2` / `final`".


### 2026-04-29 — FineWeb-2 haw_Latn full fetch
- Full pull complete via rows API (not parquet, pyarrow not installed; did NOT touch requirements.txt).
- On-disk counts match plan exactly: 95,507 train + 887 test = 96,394 rows. Zero dup ids per split, zero train/test id overlap. Raw whitespace tokens: train 67,792,427 / test 626,123 / total 68,418,550. Chars total 326,629,051.
- HF datasets-server `/rows` rate-limits hard on this dataset: even `--rate-limit-seconds 1` got 429s after ~33 pages. Stable recipe = `--rate-limit-seconds 3.0` after a multi-minute cooldown, sustained ~1,750 rows/min.
- Added `--start-offset N` flag to `scripts/205_fetch_fineweb2_haw_raw.py` for safe resume (script appends; naive rerun would dup). Rows-API path only.
- Smoke artifacts archived to `data/raw/fineweb2_haw/_smoke_validation_backup_20260429/` before the full fetch — raw bytes preserved per provenance policy.
- Decision note: `.squad/decisions/inbox/frank-fineweb2-fetch.md` (incl. parquet/pyarrow tradeoff for Linus).
- Per-row schema in `data/raw/fineweb2_haw/<date>/{split}.jsonl` carries `text`, `fineweb2_row_id`, `cc_dump`, `cc_date`, `cc_file_path`, `source_url`, `language*`, `raw_whitespace_token_count`, `license_*`, `prototype_only=true`, `release_eligible=false`.
