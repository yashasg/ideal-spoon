# Stage-2 Round 17 — Canonical helper consolidation

Date: 2026-05-03
Owner: Linus

## Decision

`code/llm_hawaii/stage2_canonical.py` is the locked Stage-2 canonicalization surface.
Future Stage-2 adapters, audit tools, contamination ledgers, and manifest code MUST import from it for candidate clean text and pair-hash canonicalization.

Required public helpers:

- `canonical_en(s)` — English clean side canonical form.
- `canonical_haw(s)` — Hawaiian clean side canonical form.
- `canonical_pair(en, haw)` — eval-ledger pair text, `canonical_en(en) + U+2016 + canonical_haw(haw)`.

The module also owns `canonicalize_clean_text`, `sha256_text`, and `compute_pair_hash` so legacy manifest wrapper APIs can remain compatible without duplicating rules.

## Contract

- NFC normalize all text.
- Remove soft hyphen, zero-width controls, and BOM.
- Collapse all whitespace runs to one ASCII space and trim ends.
- Preserve case.
- English folds curly single/double quotes and U+2010/U+2011 hyphen variants, but does not fold U+02BC or U+02BB.
- Hawaiian folds ASCII/curly/backtick/U+02BC apostrophe-like marks to U+02BB ʻokina.
- Pair hashes remain `SHA256(sha256_en_clean + U+2016 + sha256_haw_clean)`.

## Rationale

Before R17, the manifest builder, eval contamination helper, candidate adapters, and audit scripts had multiple local normalizers. Those could drift on EN punctuation, HAW ʻokina, invisible controls, or whitespace. A single module keeps future hash determinism testable and prevents adapters from silently creating incompatible ledger keys.

## Implementation notes

- `scripts/320_build_stage2_manifest.py` imports/re-exports the central helper for backward-compatible tests and callers.
- `code/llm_hawaii/eval_contamination.py` now uses `canonical_pair` for Stage-2 pair content and the same `sha256_text` primitive.
- Stage-2 builders/audits delegate clean candidate text to `stage2_canonical` rather than open-coding `.replace()`/`.strip()` folds.
- `scripts/340_audit_stage2_candidate_normalization.py --strict` treats canonicalization-delta counts as advisory and still fails on post-policy schema errors or eval contamination.

## Verification

- `python3 code/tests/test_stage2_canonical.py -v` — 4/4
- `python3 code/tests/test_stage2_dedup.py -v` — 17/17
- `python3 code/tests/test_hash_determinism.py -v` — 7/7
- `python3 code/tests/test_eval_contamination.py -v` — 5/5
- `python3 code/tests/test_manifest_contamination_filter.py -v` — 2/2
- `python3 code/tests/test_taxi1500_ingester.py -v` — 6/6
- `python3 code/tests/test_global_piqa_ingester.py -v` — 5/5
- `python3 code/tests/test_weblate_adapter.py -v` — 7/7
- `python3 code/tests/test_tatoeba_refresh.py -v` — 7/7
- `python3 scripts/320_build_stage2_manifest.py --dry-run` — 37,084 rows
- `python3 scripts/340_audit_stage2_candidate_normalization.py --strict` — pass

## Future rule

New Stage-2 source work must not introduce local canonicalization helpers for candidate clean text. If a source needs pre-cleaning (HTML unescape, OCR page-number stripping, template removal), do that first, then call `canonical_en`/`canonical_haw` for final clean text and hashing.
