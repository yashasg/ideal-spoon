# Stage 2 source adapter — Baibala Hemolele × public-domain English Bible

> **Owner:** Frank (Hawaiian Data Collector). **Tracks:** [issue #16](https://github.com/yashasg/ideal-spoon/issues/16). **Status:** Adapter contract + fixtures landed; live URL pin pending Linus rights review.

## What this is

The first real Stage-2 source adapter: a verse-id-aligned (Hawaiian, English) parallel pair sourced from a pinned Hawaiian edition of the **Baibala Hemolele** and a pinned **public-domain** English Bible (default: World English Bible / WEB). Verse-id alignment is `score-tier = accept` per `docs/stage2-alignment-quality.md` §3.1 — no embedding model is needed.

## What this is **not**

* Not a license determination. Linus owns the final rights ruling on which Hawaiian edition we pin (1839 Andrews/Bingham is the public-domain candidate path).
* Not a corpus dump. Raw bytes go under the gitignored `data/` tree. Only this directory (registry, README), the adapter scripts, and the small test fixtures live in-repo.
* Not a chapter-level aligner. Chapter-level alignment is unsafe across editions; we only emit verse-keyed rows.

## Files

| Path | Purpose |
|---|---|
| `source_registry.json` | Pinned (haw, eng) edition pair, URL templates, licensing, full 66-book canon with codes / chapter counts. Edition pin is currently `null` pending Linus. |
| `../../scripts/206_fetch_baibala_raw.py` | Raw fetcher. Dry-run by default; `--execute` is gated on a confirmed edition pin and a captured ToS snapshot. Writes provenance JSONL records compatible with `scripts/202_fetch_hawwikisource_raw.py`. |
| `../../scripts/322_build_bible_candidates.py` | Verse-id pair builder. Reads parsed verse JSONL from `data/raw/<source>/<date>/verses.jsonl` (or a fixture dir via `--fixture-dir`) and emits `data/stage2/candidates/bible.jsonl` ready for `scripts/320_build_stage2_manifest.py`. |
| `../../code/tests/fixtures/bible/` | Tiny synthetic verse fixture (clearly labelled — **not** real Bible text) exercising NFC + ʻokina canonicalization, verse-id alignment, and schema conformance. |
| `../../code/tests/test_bible_adapter.py` | Adapter contract tests. |

## Provenance fields captured per row

Stage-2 manifest schema fields populated by `322_build_bible_candidates.py`:

* `pair_id` = `bible:<BOOK_CODE>:<chapter>:<verse>` (deterministic).
* `source` = `baibala-hemolele-1839` (or whatever Linus pins).
* `source_url_haw`, `source_url_en` — resolved from `source_registry.json` URL templates.
* `record_id_haw`, `record_id_en` — `<BOOK_CODE>:<chapter>:<verse>` on each side.
* `fetch_date` — `YYYYMMDD` (UTC) of the raw fetch.
* `sha256_haw_raw`, `sha256_en_raw` — sha256 of the raw fetched bytes (chapter-level html if from live fetch, fixture file bytes for tests).
* `sha256_haw_clean`, `sha256_en_clean` — sha256 of the per-verse text after NFC + ʻokina canonicalization.
* `sha256_pair` — `sha256(en_clean ‖ haw_clean)` per `scripts/320_build_stage2_manifest.py::compute_pair_hash`.
* `alignment_type="parallel-verse"`, `alignment_method="verse-id"`, `alignment_score=null`, `alignment_review_required=false`.
* `register="religious"`, `direction_original="unknown"`, `synthetic=false`, `license_inferred=null`, `prototype_only=true`, `release_eligible=false`.
* `edition_or_version` — pulled from registry per side (Hawaiian).
* `license_observed_haw`, `license_observed_en` — pulled from registry per side.
* `lang_id_haw="haw"`, `lang_id_en="eng"`, both with `confidence=1.0` (deterministic source assignment, not LID).
* `length_ratio_haw_over_en` — token-count ratio (whitespace tokens) for downstream filtering.
* `crosslink_stage1_overlap=false`, `dedup_cluster_id=pair_id`, `split="train"`.

## Run order

```bash
# 0. Dry-run / plan only — never fetches verse bodies.
python scripts/206_fetch_baibala_raw.py --dry-run

# 1. Once Linus pins the edition AND ToS snapshot is captured:
python scripts/206_fetch_baibala_raw.py --execute \
  --side haw --book GEN --chapters 1-3 \
  --confirm-edition baibala-hemolele-1839 \
  --tos-snapshot data/raw/baibala-hemolele-1839/<YYYYMMDD>/tos_snapshot.html

# 2. Build candidate pair JSONL (works with raw fetch OR test fixtures):
python scripts/322_build_bible_candidates.py --dry-run
python scripts/322_build_bible_candidates.py --execute  # writes data/stage2/candidates/bible.jsonl

# 3. Feed into the Stage-2 manifest builder (Linus' script):
python scripts/320_build_stage2_manifest.py --check  # schema validation
```

## Rights / boundaries

* **Hawaiian side:** 1839 Andrews/Bingham translation is the public-domain candidate. Final pin pending Linus. Adapter refuses `--execute` without `--confirm-edition <id>` matching the registry pin.
* **English side:** WEB (Rainbow Missions, declared public domain) is the default. KJV (US PD) is an acceptable alternative; both share versification with the Baibala protocanon.
* **Cap:** Bible token share ≤ 30% of Stage-2 parallel-train tokens; **0%** of dev/test (see `docs/data-pipeline.md` §"Stage 2 source tiers" Tier A). Allocation enforced downstream by Linus.

## What's still open (not in this PR)

1. Live URL confirmation against `baibala.org` — exact CGI parameter shape and the edition code (`BAI1839` is a placeholder).
2. ToS snapshot capture (`data/raw/baibala-hemolele-1839/<YYYYMMDD>/tos_snapshot.html`) before any `--execute`.
3. Real HTML → verse parser. Today the `--fixture-dir` path is the proven extraction surface; the live HTML parser is a small `parse_baibala_chapter_html()` function with a clear contract and a `NotImplementedError` until Frank has live samples to write against.
4. Versification reconciliation across editions (Psalms numbering, etc.).

— Frank, source-first, provenance-obsessed.
