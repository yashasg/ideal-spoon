# Stage 2 Source Adapter Pattern

Reusable pattern for building Stage 2 en↔haw parallel corpus source adapters.

## Pattern Overview

Each adapter owns one source (e.g., Tatoeba, Bible, OPUS subset) and produces
a candidates JSONL under `data/stage2/candidates/<source>.jsonl` (gitignored).

## Required Structure

```
data-sources/<source-id>/
  fetch.py           # main adapter script
  README.md          # provenance, dump URL, date, license
  PINNED_DUMP.json   # machine-readable provenance + policy metadata
```

## Adapter Script Contract

Must support three modes:
```bash
python data-sources/<source>/fetch.py --dry-run    # HEAD URLs, no download
python data-sources/<source>/fetch.py --execute    # download + emit candidates
python data-sources/<source>/fetch.py --self-test  # in-memory smoke, no network
```

Exit codes: `0` success, `1` I/O error, `2` CLI misuse, `3` schema failure.

## Candidate JSONL Fields

All required manifest fields from `scripts/320_build_stage2_manifest.py::MANIFEST_FIELDS`
that can be computed at fetch time. Key fields to pre-populate:

| Field | Source |
|-------|--------|
| `pair_id` | `{source}-haw{haw_id}-en{eng_id}` |
| `source` | source identifier string |
| `source_url_en`, `source_url_haw` | per-sentence URLs |
| `fetch_date` | `datetime.date.today().strftime("%Y%m%d")` |
| `sha256_en_raw`, `sha256_haw_raw` | `sha256(raw_text.encode())` |
| `sha256_en_clean`, `sha256_haw_clean` | `sha256(nfc(text).encode())` |
| `sha256_pair` | `sha256(sha256_en_clean + "‖" + sha256_haw_clean)` |
| `record_id_en`, `record_id_haw` | source-native IDs |
| `text_en`, `text_haw` | NFC-normalized text |
| `alignment_type` | per source (e.g., `"parallel-sentence"`) |
| `alignment_method` | per source (e.g., `"manual"`, `"verse-id"`) |
| `alignment_score` | `null` for deterministic methods |
| `alignment_review_required` | `False` (scorer will update) |
| `length_ratio_haw_over_en` | `len(haw.split()) / len(en.split())` |
| `lang_id_en`, `lang_id_haw` | `"en"`, `"haw"` |
| `lang_id_en_confidence`, `lang_id_haw_confidence` | `1.0` (known from source) |
| `direction_original` | `"unknown"` or actual direction |
| `register` | per source; use `"unknown"` for mixed-domain |
| `synthetic` | `False` for human-sourced corpora |
| `prototype_only` | always `True` |
| `release_eligible` | always `False` |
| `license_observed_en`, `license_observed_haw` | per source |
| `license_inferred` | always `None` |
| `dedup_cluster_id` | `pair_id` (reassigned by dedup pass later) |
| `crosslink_stage1_overlap` | `False` (unknown at fetch time) |
| `split` | `"review-pending"` |
| `manifest_schema_version` | `"stage2.v0"` |

## Hash Invariant

```python
sha256_pair == sha256((sha256_en_clean + "\u2016" + sha256_haw_clean).encode("utf-8"))
```

This mirrors `compute_pair_hash()` in `320_build_stage2_manifest.py`. Tests must
verify this invariant.

## alignment_method Choices (schema-compatible values)

| Value | Use When |
|-------|----------|
| `"verse-id"` | Bible verse alignment (deterministic) |
| `"manual"` | Human-curated links (Tatoeba) |
| `"tmx-line"` | TMX or Moses-format line-aligned bitext |
| `"filename-pair"` | Paired filename alignment |
| `"labse"` | LaBSE embedding alignment (requires score) |
| `"laser"` | LASER embedding alignment (requires score) |

## register Choices (schema-compatible values)

`"religious"`, `"software-l10n"`, `"encyclopedic"`, `"educational"`, `"news"`, `"dictionary-example"`, `"unknown"`

Use `"unknown"` for mixed-domain sources (e.g., Tatoeba).

## Testing Pattern

```
code/tests/fixtures/<source>/          # synthetic TSV/JSONL fixtures
code/tests/test_<source>_adapter.py   # unittest, no network
```

Key test classes:
1. `TestParseXxx` — parse functions with blank-line / malformed input cases
2. `TestBuildCandidateRow` — all field values, hash invariant, NFC normalization
3. `TestJoinPairs` — join correctness, missing-side skipping, unique hashes
4. `TestSchemaCompatibility` — `validate_row()` from 320 returns no violations
5. `TestSelfTest` — adapter's `--self-test` exits 0

## Examples

- `data-sources/tatoeba/fetch.py` — reference implementation (issue #17)

---

## Reference instance: Baibala Hemolele × WEB Bible (issue #16, 2026-05-01)

First concrete adapter to land on this scaffold. Adds three conventions
that future Stage-2 adapters should adopt:

### Edition pin lives in JSON, not Python

`data-sources/<source>/source_registry.json::sides.<lang>.edition_pinned_by`
is the single source of truth for which edition we have rights to pull.
The fetcher reads it; the rights-reviewer (Linus) edits it. Keeps pins
reviewable as data, not buried in script constants.

### Triple-gated `--execute` on the live fetcher

Required for any rights-review-pending source. The fetcher's
`--execute` path must refuse with rc=2 unless ALL of:

1. Registry's `edition_pinned_by` is non-null.
2. CLI `--confirm-edition <id>` matches the registry `edition_or_version`.
3. CLI `--tos-snapshot <path>` points at an existing on-disk file.

Reference: `scripts/206_fetch_baibala_raw.py::assert_execute_preconditions`.

### ʻokina canonicalization runs before any sha256

On the Hawaiian side: NFC-normalize AND fold U+2018, U+2019, and ASCII
apostrophe (`'`) to the canonical ʻokina U+02BB **before** computing
`sha256_haw_clean` or `sha256_pair`. Mirror the `OKINA_MISENCODINGS`
set in `code/llm_hawaii/stage2_quality.py`. Skipping this step makes
pair hashes drift across upstream rendering quirks and silently breaks
contamination dedup. Reference: `scripts/322_build_bible_candidates.py::normalize_haw`.

### Pair-hash via the canonical helper

`sha256_pair = compute_pair_hash(en_clean, haw_clean)` — reuse
`scripts/320_build_stage2_manifest.py::compute_pair_hash` rather than
reimplementing. Add a unit test asserting the candidate row's
`sha256_pair` matches the helper byte-for-byte (see
`code/tests/test_bible_adapter.py::test_pair_hash_invariant`).

### Synthetic test fixtures over real corpus excerpts

Test fixtures under `code/tests/fixtures/<source>/` should be small
synthetic content clearly labelled NOT real corpus. The adapter
contract is a pure-function test of normalization + row shape; using
real PD text only adds rights ambiguity and edition-drift failure
modes. Real text only enters the pipeline via `data/` (gitignored)
once the edition is pinned.

---

## Reference instance: Veridian/Greenstone discovery (Ulukau Nupepa, 2026-05-03)

Reusable pattern for **any Veridian/Greenstone-fronted source on the Ulukau
family** (nupepa.org, baibala.org, hooilina.org, puke.ulukau.org, etc.).
The same query-param family applies; only the OID grammar and `e=` state
suffix differ per collection.

### How to map a new Veridian collection in one session

1. Land on the home page; capture the canonical URL and "veridian-version" meta.
2. Open one document; note its **OID grammar** (e.g., Niupepa = `<PAPER><YYYYMMDD>-<ISSUE>(.<page>(.<article>(.<sub>)?)?)?`; Baibala = `<book>:<chapter>`).
3. Capture the `e=` state token that all internal links carry — it encodes language + index scope and is required by the back-end.
4. Find the AJAX endpoints by reading `veridian-documentdisplay.js` (and any per-collection custom JS like `pdnupepa.min.js`). Look for `doAjaxGetRequest("a=da&command=...")` calls. Common commands:
   * `getSectionText` — the OCR / transcribed body (XML → HTML inside `<SectionText>`)
   * `getDocumentContents` — TOC of an issue/document
   * `getSectionMetadata`, `getPersistentLink`, `getUserTranslation`, `getSectionTags`, `getSectionComments`
5. Smoke-fetch one section through the live signed-in browser via CDP rather than `curl` — Veridian sites are usually behind Cloudflare and reject naked curl.
6. Browse the classifier hierarchy (`?a=cl&cl=CL1`, `?a=cl&cl=CL2.<YYYY>.<MM>`) to estimate enumeration cost before proposing an adapter.

### CDP-from-signed-in-Chrome helper (reuse pattern)

When a source needs auth or sits behind Cloudflare and we don't want to add
Playwright deps, drive the user's already-signed-in Chrome via DevTools
Protocol on `127.0.0.1:9222`:

* Use `websocket-client` (pip in a local throwaway venv) with
  `suppress_origin=True` to bypass Chrome's `--remote-allow-origins` check.
* Run `Runtime.evaluate` with `awaitPromise=True` and a `fetch(...)` IIFE to
  use the page's own Cloudflare-cleared session for AJAX probes.
* **Never** read cookies, localStorage, or auth headers via the protocol.
  We only navigate and DOM-eval — provenance comes from response bodies.

This pattern stays out of the repo; it lives in `data/raw/<source>-discovery/`
alongside saved HTML/XML artifacts and a `README.md` that is the discovery
audit trail.

### When to NOT build an adapter for a discovered Veridian source

Even when the AJAX endpoints exist, abort the adapter proposal if:

* Site TOS says "All Rights Reserved" + "no copying to other websites" + no
  per-item machine-readable license — flag for explicit rights-reviewer
  sign-off, not implicit "fair use" assumption.
* The collection is small enough (< a few thousand sections) that per-item
  manual rights vetting is cheaper than building an adapter.
* The "translation" facility is community-contributed and sparsely populated
  — treat it as eval-only signal, not a parallel-corpus source.

---

## Reference instance: Ka Hoʻoilina trilingual Greenstone (2026-05-01)

Reusable sub-pattern for **any Veridian/Greenstone collection that
publishes the same document in multiple languages or spelling layers**
(Hoʻoilina is original-HAW × modernized-HAW × English; the same shape
will recur on any Ulukau-family bilingual journal/legal/educational
collection).

### Tell-tale: editorial intro page is the rights + structure ground truth

Before mapping URLs, read `?a=p&p=edintro&gg=text` (or the
collection's equivalent `about` / `edintro` page). For Hoʻoilina that
single page declared:
- Number of language layers per document and which is editorial vs PD.
- Per-layer copyright owner (Kamehameha Schools 2002–2004 for the
  editorial layers, PD-by-age for the underlying source).
- Reuse clause language ("noa i ka lehulehu akea ... me ke koina nae")
  → must cite source HAW alongside any reuse of modernized HAW or
  English. **Save this page as the ToS snapshot, not the home page.**

### Versioned-document pattern

When a Greenstone collection publishes parallel versions of the same
document, the version selector lives in either the OID suffix or the
`e=` state token / `gg=text` parameter. To enumerate trios:

1. Resolve the parent document OID via `?a=d&d=<OID>` and
   `command=getDocumentContents`.
2. For each child section, fetch the same OID with each version
   selector (e.g., `gg=text` for transcribed source, alternate values
   for modernized HAW, English translation).
3. Treat the per-version XML response as one row's `text_<lang>`
   field. Persist all three versions even if Stage 2 only consumes
   two (modernized-HAW × English) — the third (original-HAW) is
   valuable for Stage 1 dedup hashing.

### When to keep multiple HAW spelling layers

If a collection has both a transcribed-original HAW and a
modernized/corrected HAW, prefer the **modernized** layer for the
Stage 2 train pair (matches modern spelling in the rest of the corpus).
Keep the original layer as a `dedup_cluster_id`-only signal — emit a
candidate row with `synthetic=False`, `register="<source-register>"`,
but mark it `release_eligible=False` and exclude from train sampling
unless a downstream skill explicitly rehabilitates it.

## Reference instance: Ka Hoʻoilina full enumeration (2026-05-01, raw pull pass)

Confirms and tightens the trilingual-Greenstone sub-pattern above with
fully enumerated counts.

### Confirmed leaf-OID suffix → spelling layer (uniform across all issues)

For Ka Hoʻoilina (`hooilina.org`, Greenstone `journal` collection), every
leaf section OID has depth 3 (`HASH<root>.<X>.<Y>.<Z>`) and `Z` selects
the spelling layer:

| Suffix `Z` | Layer |
|---|---|
| `.3` | Original HAW (transcribed from source document; pre-modern spelling) |
| `.5` | Modernized HAW (paʻi-hewa-corrected; ʻokina + kahakō added) |
| `.7` | English translation (editorial layer) |
| `.9` | Optional "kuhia kikokikona" textual notes (sparse — 4/331 sections only) |

Verified across all 4 root issues (vols. 1–4, 2002–2004), 109 sections
each in `.3` / `.5` / `.7` (= 327 trilingual + 4 notes = 331 leaves).

### Enumerator: classifier walk (CL2 = date browse)

```
GET /cgi-bin/journal?e=<state>&a=d&cl=CL2&gg=text   # 3 child nodes
GET /cgi-bin/journal?e=<state>&a=d&cl=CL2.1&gg=text # ~105 doc OIDs
GET /cgi-bin/journal?e=<state>&a=d&cl=CL2.2&gg=text # ~76
GET /cgi-bin/journal?e=<state>&a=d&cl=CL2.3&gg=text # ~150
```

Restrict the recursive walk to children matching `^CL\d+(\.\d+)*$` —
trailing-dot variants like `CL2.1.` will infinite-loop the walker if not
filtered (Greenstone tolerates them but emits the same body, re-yielding
the same children).

### Per-section body URL

```
https://hooilina.org/cgi-bin/journal
  ?e=d-0journal--00-0-0-004-Document---0-1--1haw-50---20-frameset---ka--001-0110escapewin
  &cl=search
  &d=<HASH<root>.<X>.<Y>.<Z>>
  &d2=1
  &gg=text
```

Returns plain HTML body content, no further frame-walking required.

### Wehewehe PD subset = full PDF over per-entry crawl

For the Wehewehe (`wehewehe.org`, Greenstone `hdict`) PD subset, do NOT
walk per-entry D-id ranges; the same content is served as a single
canonical full-text PDF on the books portal:

```
HEAD https://ulukau.org/ulukau-books/cgi-bin/imageserver.pl?oid=<EBOOK_OID>&getpdf=true
```

Mapping (PD pre-1925, US):

| EBOOK OID       | wehewehe tag    | Title (year)                            |
|---              |---              |---                                       |
| EBOOK-VOCABULARY| textvocabulary  | Andrews — Vocabulary of words (1836)     |
| EBOOK-emd       | textemd         | "He hoakakaolelo no na huaolelo Beritania" — Emerson attribution (1845) |
| EBOOK-ANDREW    | textandrew      | Andrews — Dictionary of the Hawaiian language (1865) |
| EBOOK-CDD       | textcdd         | Dictionary of Biblical Words (1872)     |
| EBOOK-ehd       | textehd         | Hitchcock — English-Hawaiian dict. (1887) |
| EBOOK-PARKER    | textparker      | Parker (rev.) (1922)                    |

Modern dictionaries served by the same `hdict` collection (Pukui-Elbert
1986 / Māmaka Kaiao 2003 / Judd/Pukui/Stokes 1943 / Kent 1986 / Place
Names 1974 + 2002 / Hawaiian Legal Land-Terms 1995 / Combined 2020) are
INVENTORY ONLY pending rights-reviewer sign-off — capture only the
EBOOK landing page, do not pull the PDF.

---

## Reference instance: Wikimedia Content Translation CX (2026-05-01)

Reusable sub-pattern for **any CX-style source where one side is a partial
translation stub of the other**.

### CX stub pattern

Wikimedia CX produces target-language articles that are typically partial
translations. The strategy:

1. **Extract paragraphs** from both sides using robust wikitext cleaning.
2. **Compare para counts**:
   - If `n_en == n_haw` (exact match): positional alignment (n pairs).
   - Otherwise: **lead-only** (1 pair = first body paragraph from each side).
3. Never assume the full EN article corresponds to the full HAW article
   when HAW is a stub.

### Wikitext multi-line template stripping (critical)

Apply `re.sub(r'\{\{[^{}]*\}\}', '', text, flags=re.DOTALL)` **before**
splitting into lines. Without DOTALL, `{{flat list|\n* item\n}}` leaks
its list items into paragraph output as content. Apply iteratively (≥6×)
to catch nested templates.

### nosuchrevid is an expected hazard for small wikis

When a CX targetRevisionId returns `nosuchrevid` from the MediaWiki parse
API, the article was deleted or moved. Skip these pairs entirely — do not
substitute the current revision without re-verifying alignment. Log the
skipped translationIds in the report for future recovery.

### record_id shape for CX pairs

```python
record_id_en  = f"en-rev-{sourceRevisionId}-p{para_idx}"
record_id_haw = f"haw-rev-{targetRevisionId}-p{para_idx}"
```

### License

Wikipedia content is **CC BY-SA 4.0 / GFDL — not PD**. All CX rows must be
`prototype_only=True`, `release_eligible=False` until a rights policy
explicitly clears the encyclopedic register for training use.

---

## Reference instance: comparable-aligned LaBSE adapters (Sanitary Instructions, 2026-05-03)

For comparable sources aligned by embeddings, keep manifest enum fields generic and put adapter policy detail elsewhere:

- `alignment_type="comparable-aligned"`.
- `alignment_method="labse"` or `"laser"` only; do not invent values like `labse-mutual-nearest-paragraph-v1` because `320_build_stage2_manifest.py::validate_row` rejects them.
- Put the specific algorithm/threshold policy in `policy_version`, `manual_review_reasons`, and `alignment_score_components`.
- New comparable-source rows should remain `prototype_only=True`, `release_eligible=False`, `split="review-pending"`, and `alignment_review_required=True` until a final cap/rights pass promotes or excludes them.
- Extract mutual-nearest selection into a pure function that accepts a score matrix; unit tests can verify schema/hash invariants without loading LaBSE or touching the network.

---

## Reference instance: candidate normalization/dedup audit (2026-05-03)

Before rebuilding the Stage-2 manifest after multiple adapter changes, run the dry-run audit:

```bash
python3 scripts/340_audit_stage2_candidate_normalization.py --max-examples 8
```

Use it to catch four adapter regressions before they enter cap math:

1. **HAW-side ʻokina drift:** NFC-normalize and fold ASCII apostrophe, U+2018, and U+2019 to U+02BB before `sha256_haw_clean` / `sha256_pair`.
2. **EN apostrophe preservation:** do not apply HAW ʻokina folding to English text; contractions/possessives remain literal EN punctuation.
3. **Schema drift:** compare raw candidate rows and post-`320.apply_policy()` rows; older adapters may rely on policy fill-ins, but enum/license/hash violations still need adapter fixes.
4. **Cross-source duplicates:** exact pair/en/haw hash groups and near-dupes should be handled in adapters or manifest dedup, not manually edited under `data/`.

The audit is intentionally read-only and writes no files under `data/`.

---

## Reference instance: legacy candidate normalization patcher (2026-05-03)

When older/probe adapters have already emitted candidate JSONLs with schema/hash drift, use a patcher rather than editing raw data or hand-editing rows:

```bash
python3 scripts/341_normalize_legacy_candidates.py          # dry-run report
python3 scripts/341_normalize_legacy_candidates.py --apply  # rewrites candidates with .jsonl.bak copies
python3 scripts/340_audit_stage2_candidate_normalization.py --strict
python3 scripts/320_build_stage2_manifest.py --dry-run
```

Reusable rules from `341_normalize_legacy_candidates.py`:

1. Patch only generated `data/stage2/candidates/*.jsonl`; never touch `data/raw/`.
2. Back up every changed candidate file as `<file>.bak` before rewriting.
3. Use `--apply`, not `--execute`, for artifact patchers so they are distinct from source fetchers.
4. HAW clean text/hash path is NFC + ʻokina fold; EN clean text/hash path is NFC only.
5. Map legacy adapter-specific enums into manifest enums and preserve adapter-specific detail in `notes`.
6. Recompute `sha256_en_clean`, `sha256_haw_clean`, and `sha256_pair` together; never update one hash in isolation.
7. Null `license_inferred` and enforce `prototype_only=true => release_eligible=false` before validation.
8. Re-run both audit strict mode and manifest dry-run before considering the patch complete.

---

## Reference instance: cross-source exact-pair dedup policy (2026-05-03)

Manifest-level exact-pair dedup belongs after candidate normalization/scoring and before cap math. Do not hand-delete duplicate rows under `data/`; codify source preference in `code/llm_hawaii/stage2_dedup.py` and let `scripts/320_build_stage2_manifest.py` collapse exact `sha256_pair` groups.

Current ordered preference rules:

1. Hoʻoilina over Bible-family exact overlaps (`hooilina-over-bible`).
2. Wikimedia CX over OPUS-Wikimedia mirrors (`wikimedia-cx-over-opus-wikimedia`).
3. Canonical Tatoeba over OPUS-Tatoeba mirrors (`tatoeba-over-opus-tatoeba`).
4. Baibala Hemolele 1868 over other Bible-family exact overlaps (`bible-1868-over-other-bible-editions`).
5. Deterministic fallback only for unexpected cross-source groups; fallback hits should trigger a decision-log update.

Verification pattern after changing adapters or dedup rules:

```bash
python3 scripts/320_build_stage2_manifest.py --dry-run
python3 scripts/340_audit_stage2_candidate_normalization.py --strict
PYTHONPATH=code python3 -m unittest discover -s code/tests -p 'test_stage2_dedup.py'
```

The audit reports both raw exact-pair groups and post-dedup exact-pair groups; the latter should be `0` before promotion/cap work proceeds.
