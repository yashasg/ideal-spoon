# Skill: LaBSE Trust Policy

## Rule

Do not treat LaBSE as equally authoritative across all Hawaiian bitext sources.

Use LaBSE as a **hard gate** only when the pair itself is inferred or mined: comparable web pages, langlinks, OPUS mined subsets, NLLB-style mined data, or any source where sentence parallelism is not guaranteed by the source.

Use LaBSE as a **soft signal only** when the source is already human-translated and source-published as bilingual/parallel material, especially Hoʻoilina-style numbered bilingual journal text. In that case, a low score may create a review note but must not auto-reject without independent structural or OCR evidence.

## Why

For human-translated bilingual sources, the main failure mode is extraction structure: paragraph count mismatch, sentence splitter error, footnotes, boilerplate, OCR noise, or mid-paragraph alignment drift. LaBSE can only score the pair after extraction has already chosen what to compare; it cannot fix or discover the correct structural alignment.

For mined/comparable sources, the main failure mode is semantic non-parallelism. There, LaBSE provides useful triage signal and hard thresholds can be appropriate after Hawaiian-specific sanity checks.

## Hoʻoilina precedent

Hoʻoilina dry-run evidence from `scripts/325_build_hooilina_sentence_candidates.py`:

- 68 parent rows
- 6 splittable parent rows
- 62 parent rows skipped for EN/HAW numbered-paragraph count mismatch
- 36 paragraph pairs inspected
- 8 paragraph pairs skipped for sentence-count mismatch
- 60 sentence pairs emitted

Policy: Hoʻoilina LaBSE scores, if later computed, are metadata/review hints only. Promotion/rejection should be based on deterministic structure, OCR/orthography filters, provenance, caps, and human review policy.
