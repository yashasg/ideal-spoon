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
