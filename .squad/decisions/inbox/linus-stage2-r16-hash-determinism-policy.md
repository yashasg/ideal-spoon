# Stage-2 R16 hash determinism policy

- Date: 2026-05-03
- Owner: Linus

## Decision

Stage-2 EN clean-text hashes now have an explicit canonicalization contract before side hashing:

- NFC normalize.
- Remove soft hyphen, zero-width space/joiner/non-joiner, and BOM.
- Collapse all whitespace runs to one ASCII space and trim edges.
- Preserve case.
- For EN, fold curly single quotes to ASCII apostrophe, curly double quotes to ASCII quote, and U+2010/U+2011 hyphens to ASCII hyphen-minus.
- For EN, do not fold U+02BC modifier-letter apostrophe or U+02BB Hawaiian ʻokina.
- For HAW, fold apostrophe-like marks to U+02BB ʻokina.
- Keep em/en dashes, double hyphen, and spaced hyphen distinct.

## Rationale

This makes `sha256_en_clean`, `sha256_haw_clean`, and `sha256_pair` deterministic across typographic punctuation and whitespace drift without erasing case or Hawaiian orthography distinctions on the English side.

## Verification

- `python3 code/tests/test_hash_determinism.py -v`: 7 tests passed.
- `python3 code/tests/test_stage2_dedup.py -v`: 17 tests passed.
- `python3 scripts/320_build_stage2_manifest.py --dry-run`: 37,084 rows.
