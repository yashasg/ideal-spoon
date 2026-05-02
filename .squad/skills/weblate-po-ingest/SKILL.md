# Skill: Weblate PO Ingest for haw↔en

Reusable pattern for fetching and ingesting translation pairs from
`hosted.weblate.org` into Stage-2 candidate rows.

## Key facts

- **HAW project discovery**: scrape `https://hosted.weblate.org/languages/haw/`
  (HTML) for `/projects/{slug}/-/haw/` links. The REST API `?language=haw` filter
  does NOT work (returns all languages).
- **License metadata**: `GET /api/projects/{slug}/components/?format=json` — each
  component has a `license` (SPDX ID) and `license_url` field.
- **Translation count**: `GET /api/translations/{project}/{component}/haw/?format=json`
  returns `translated` / `total` counts.
- **REST API rate limit**: 100 req/window on `/api/` endpoints. Do NOT use the units
  API for bulk fetching (`/api/translations/.../units/`).
- **Correct fetch method**: `GET /download/{project}/{component}/haw/?format=po`
  — returns a full PO file, unauthenticated, not rate-limited like the API.

## License gate

Accept only: MIT, Apache-2.0, BSD-2/3-Clause, ISC, Unlicense, CC0-1.0.
Block: GPL-*, LGPL-*, AGPL-* — translation strings are derivative works of the
licensed software; copyleft is not "clearly compatible" even for private prototype ML.

## PO parsing pitfalls

1. Multi-line string continuation (`"part1 "` + `"part2"`) must be concatenated
   before the quality gate.
2. `msgctxt` blocks come before `msgid` — capture context for the unit_id hash.
3. Plural forms (`msgstr[0]`, `msgstr[1]`) — use `msgstr[0]` as the primary.
4. Header entry (`msgid ""`) must be skipped.

## Quality gate

- EN ≥ 2 words; HAW ≥ 1 word + ≥ 3 chars
- Char ratio (haw/en): [0.05, 15.0]

## Candidate row required fields

```json
{
  "source": "weblate-en-haw",
  "project_slug": "...",
  "component_slug": "...",
  "tm_unit_id": "{project}__{component}__{sha256(ctx+msgid)[:12]}",
  "text_en": "...",
  "text_haw": "...",
  "direction_original": "en->haw",
  "register": "software-l10n",
  "alignment_type": "parallel-sentence",
  "alignment_method": "tmx-line",
  "license_observed": "<SPDX-ID>",
  "license_url": "...",
  "source_url": "https://hosted.weblate.org/translate/{proj}/{comp}/haw/?checksum=...",
  "prototype_only": true,
  "release_eligible": false,
  "split": "review-pending"
}
```

## Reference script

`scripts/329_build_weblate_en_haw_candidates.py` — stdlib-only, `--self-test` / `--dry-run` / `--execute`.

## HAW projects on hosted.weblate.org (as of 2026-05-03)

| Project | Component | License | haw translated | Gate |
|---------|-----------|---------|---------------|------|
| django-zxcvbn-password-validator | translations | MIT | 49/49 | PASS |
| dpo-voyager | dpo-voyager | Apache-2.0 | 61/65 | PASS |
| f-droid | privileged-extension-metadata | Apache-2.0 | 11/11 | PASS |
| f-droid | glossary-f-droid | Apache-2.0 | 26/26 | PASS |
| prismlauncher | launcher | Apache-2.0 | 27/2660 | PASS |
| iso-codes | iso-3166-1 | LGPL-2.1-or-later | 19/425 | BLOCKED |
| prismlauncher | glossary | GPL-3.0-or-later | 22/22 | BLOCKED |
| stellarium-mobile | app | GPL-2.0-only | 61/605 | BLOCKED |
