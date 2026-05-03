# Linus Stage-2 R15 — dedup/normalization edge-case fixes

Date: 2026-05-03

## Decision

Keep Stage-2 clean hashes byte-preserving under the existing candidate artifacts, but make dedup/audit matching robust to default-ignorable Unicode format controls. English-side apostrophe and ʻokina remain distinct for dedup keys; Hawaiian-side ʻokina folding remains Hawaiian-only.

## Findings

- Candidate audit rows: 37,761.
- NFC drift: 0 EN / 0 HAW.
- HAW ʻokina hash drift: 0.
- EN apostrophe/right-quote rows: 2,119; preserved by policy.
- Invisible format-control rows: 7 (soft hyphen, zero-width, BOM).
- Non-ASCII whitespace rows: 3 (NBSP in Tatoeba HAW strings).
- Whitespace-only rows after normalization: 0.
- Raw trailing-punctuation token variants: 98; existing token-based near-dupe policy already collapses final cross-source token-pair duplicates to 0.
- Short rows appear in several sources beyond Phrase Book/Andrews/Weblate, but the cap is length-aware and source-independent except Weblate's software-l10n threshold; no missing-source cap change is needed.

## Policy implications

- `stage2-cross-source-dedup-v0.6` changes fallback exact-pair ordering to canonical source priority + length + stable IDs, avoiding accidental alphabetical-source wins when no explicit preference rule exists.
- Near-dupe comparisons remove U+00AD, U+200B, U+200C, U+200D, and U+FEFF before token comparison.
- Manifest validation treats inline text/path refs containing only whitespace and default-ignorable controls as missing.
- Audit reports invisible controls and non-ASCII whitespace but does not make them strict failures unless they also create schema/hash/contamination failures.

## Counts

Manifest dry-run remains 37,084 rows (delta 0). Row drops remain exact-pair 100, exact-EN cap 199, exact-HAW cap 75, near-dupe 303.
