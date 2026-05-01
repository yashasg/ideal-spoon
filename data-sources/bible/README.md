# Stage 2 source adapter — Baibala Hemolele × public-domain English Bible

> **Owner:** Frank (Hawaiian Data Collector). **Tracks:** [issue #16](https://github.com/yashasg/ideal-spoon/issues/16). **Status:** Edition PINNED by Linus 2026-05-01. ToS snapshot captured. Live HTML parser implemented and verified against Genesis 1 + John 3 samples (Frank 2026-05-01).

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
python scripts/322_build_bible_candidates.py --dry-run                    # in-tree fixtures
python scripts/322_build_bible_candidates.py --execute                    # writes data/stage2/candidates/bible.jsonl from fixtures
python scripts/322_build_bible_candidates.py --execute \
  --from-raw 20260501                                                     # parses raw haw HTML under data/raw/baibala-hemolele-1839/20260501/
python scripts/322_build_bible_candidates.py --execute \
  --haw-raw-dir <path> --eng-fixture-dir <path>                           # explicit override (test/dev)

# 3. Feed into the Stage-2 manifest builder (Linus' script):
python scripts/320_build_stage2_manifest.py --execute --candidates data/stage2/candidates/bible.jsonl
python scripts/320_build_stage2_manifest.py --check --strict              # schema + invariant validation
```

## Rights / boundaries

* **Hawaiian side:** 1839 Andrews/Bingham translation — **PUBLIC DOMAIN** (pre-1925 US imprint). Edition pinned by Linus 2026-05-01. Site copyright 2003-2008 held by Partners In Development Foundation for the *digitization* (Greenstone platform, UI, audio); the underlying 1839 text is unencumbered. No scraping prohibition found in ToS/acknowledgments page as of 2026-05-01.
* **English side:** WEB (Rainbow Missions, declared public domain) is the default. KJV (US PD) is an acceptable alternative; both share versification with the Baibala protocanon.
* **Cap:** Bible token share ≤ 30% of Stage-2 parallel-train tokens; **0%** of dev/test (see `docs/data-pipeline.md` §"Stage 2 source tiers" Tier A). Allocation enforced downstream by Linus.

## Confirmed source URL

baibala.org runs **Greenstone Digital Library** software. The canonical content URL for a chapter in the **1839 edition** is:

```
https://baibala.org/cgi-bin/bible?e=d-1off-01839-bible--00-1-0--01839-0--4--Sec---1--1haw-Zz-1-other---20000-frameset-main-home----011-01839--210-0-2-utfZz-8&d={greenstone_oid}.{chapter}&d2=1&toc=0&exp=1-&gg=text
```

Where `{greenstone_oid}` is per-book (see `books[].greenstone_oid` in `source_registry.json`). Examples:

| Book | `greenstone_oid` | Genesis 1 URL fragment |
|------|-----------------|----------------------|
| Genesis | `NULL.2.1.1` | `d=NULL.2.1.1.1` |
| John | `NULL.4.1.4` | `d=NULL.4.1.4.1` |
| Revelation | `NULL.4.4.1` | `d=NULL.4.4.1.1` |

The old placeholder `e=BAI1839&b={book_code}&c={chapter}` is **wrong and returns an error**. The `source_registry.json` `haw.url_template` has been corrected.

## Live HTML verse structure (for parser implementation)

Sample HTML in `data/raw/baibala-hemolele-1839/20260501/` (gitignored, local only). Anchor pattern confirmed on Genesis 1 and John 3:

```html
<!-- Chapter OID: NULL.2.1.1.1-->
<a name="agenesis-1-1"></a>1 &para; I KINOHI hana ke Akua i ka lani a me ka honua. <br />
<a name="agenesis-1-2"></a>2 He ano ole ka honua, ua olohelohe; ... <br />
```

**Parser contract for `parse_baibala_chapter_html()` in `scripts/206_fetch_baibala_raw.py`** *(implemented 2026-05-01, verified on Genesis 1 → 31 verses, John 3 → 36 verses)*:

1. Find all `<a name="a{book_name_lower}-{chapter}-{verse}">` anchors (where `book_name_lower` comes from `books[].book_name_lower` in the registry — e.g. `genesis`, `1samuel`, `songofsolomon`).
2. Extract the text between the anchor and the next `<br />` (the verse terminator), strip leading verse number + `&para;` (¶) marker, decode HTML entities, collapse whitespace.
3. NFC-normalize + canonicalize ʻokina mis-encodings (`U+2018`, `U+2019`, ASCII `'`) to U+02BB. The 1839 imprint actually uses ASCII apostrophes (e.g. `hana'i` → `hanaʻi`) so this canonicalization is load-bearing on the haw side.
4. Return `{"book": book_code, "chapter": chapter, "verse": int, "text": str}` list, sorted by verse.

A small synthetic chapter HTML fixture mirroring this anchor pattern (no real Bible text) lives at `code/tests/fixtures/bible/haw_html/GEN_001.html` and exercises the parser end-to-end via `scripts/322_build_bible_candidates.py --haw-raw-dir`.

Note: The 1839 text uses pre-modern orthography (no kahakō/macrons). NFC normalization is still required; ASCII apostrophe → U+02BB canonicalization fires often.

## ToS snapshot

Captured at: `data/raw/baibala-hemolele-1839/20260501/tos_snapshot.html`  
SHA-256: `254c552c3519f503d98fab03e46616b7789d3ac95cbbc5f41dd76d3e74af268c`  
URL: `https://baibala.org/cgi-bin/bible?...&a=p&p=ack&gg=text&exp=1`  
Hosted by: Partners In Development Foundation; supported by Ka Haka ʻUla O Keʻelikōlani (UH Hilo).  
No robots.txt prohibition or scraping ban found. Polite rate limit (1.5 s between requests) is enforced by the fetcher.

The `--execute` gate in `206_fetch_baibala_raw.py` now passes preconditions (edition pinned + ToS snapshot on disk).
