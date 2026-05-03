# Linus Stage-2 Round 9 license probe — Weblate EN↔HAW translation memory

Date: 2026-05-03  
Scope: license-first metadata probe only; no PO/TMX/download exports fetched.

## Source name + canonical URLs

Source: public Weblate EN→HAW/Hawaiian projects.

Instances checked:

- Hosted Weblate: <https://hosted.weblate.org/languages/haw/>
- Fedora Weblate: <https://translate.fedoraproject.org/languages/haw/>
- Codeberg Translate: <https://translate.codeberg.org/languages/haw/> — no Hawaiian projects found.
- Framasoft Weblate: <https://weblate.framasoft.org/languages/haw/> — no Hawaiian projects found.

Hosted Weblate HAW projects found from the language page:

| Instance | Project URL | Source language(s) | Component license(s) seen via Weblate API |
|---|---|---:|---|
| Hosted Weblate | <https://hosted.weblate.org/projects/django-zxcvbn-password-validator/-/haw/> | `en` | `MIT` (2 components) |
| Hosted Weblate | <https://hosted.weblate.org/projects/dpo-voyager/-/haw/> | `en` | `Apache-2.0` (2 components) |
| Hosted Weblate | <https://hosted.weblate.org/projects/f-droid/-/haw/> | `en`, `en_US` | `GPL-3.0-or-later` (7), `Apache-2.0` (3), `AGPL-3.0-or-later` (10) |
| Hosted Weblate | <https://hosted.weblate.org/projects/geoweather/-/haw/> | `en` | `Apache-2.0` (1), but HAW page showed 0% translated; likely no usable pairs yet. |
| Hosted Weblate | <https://hosted.weblate.org/projects/iso-codes/-/haw/> | `en_GB` | `LGPL-2.1-or-later` (8) |
| Hosted Weblate | <https://hosted.weblate.org/projects/prismlauncher/-/haw/> | `en_US` | `Apache-2.0` (1), `GPL-3.0-or-later` (1) |
| Hosted Weblate | <https://hosted.weblate.org/projects/stellarium-mobile/-/haw/> | `en` | `GPL-2.0-only` (2) |
| Fedora Weblate | <https://translate.fedoraproject.org/projects/rpminspect/-/haw/> | `en` | `GPL-3.0-or-later` (`main`, `glossary`) |

## License / TOS quotes

Per-project/component license values were read from the public Weblate REST API. Verbatim API fields observed:

- Hosted `django-zxcvbn-password-validator`: `"license": "MIT", "license_url": "https://spdx.org/licenses/MIT.html"`
- Hosted `dpo-voyager`: `"license": "Apache-2.0", "license_url": "https://spdx.org/licenses/Apache-2.0.html"`
- Hosted `f-droid`: `"license": "GPL-3.0-or-later"`, `"license": "Apache-2.0"`, and `"license": "AGPL-3.0-or-later"` across components.
- Hosted `iso-codes`: `"license": "LGPL-2.1-or-later", "license_url": "https://spdx.org/licenses/LGPL-2.1-or-later.html"`
- Hosted `prismlauncher`: `"license": "Apache-2.0"` for launcher component and `"license": "GPL-3.0-or-later"` for glossary component.
- Hosted `stellarium-mobile`: `"license": "GPL-2.0-only", "license_url": "https://spdx.org/licenses/GPL-2.0-only.html"`
- Fedora `rpminspect`: `"license": "GPL-3.0-or-later", "license_url": "https://spdx.org/licenses/GPL-3.0-or-later.html"`

Relevant Weblate terms page text (Hosted and Fedora terms share the Weblate-hosted terms template):

> "Translation Memory means an optional translation memory service provided on Weblate"

> "Hosted String means a text unit defined in the translation format. It can be a word, sentence, or paragraph. It is counted separately for each language"

The terms page describes the Weblate service license; it did not provide a separate public-domain/open-data grant for hosted translation strings. Therefore the component/project license must be treated as the controlling content license, with the instance TOS/robots governing access mechanics.

## Robots.txt status

- Hosted Weblate robots: `Allow: /projects/`, `Allow: /languages/`, `Allow: /exports/`, then `Disallow: /`. Metadata pages and export paths are explicitly allowed.
- Fedora Weblate robots: same pattern: `Allow: /projects/`, `Allow: /languages/`, `Allow: /exports/`, then `Disallow: /`.
- Codeberg Translate robots: same pattern, but `/languages/haw/` returned no HAW projects.
- Framasoft Weblate robots: no wildcard `User-agent: *` group was observed; named AI bots are disallowed. `/languages/haw/` returned no HAW projects.

## Access method

Next-round adapter should use Weblate public endpoints only, no auth:

1. Metadata: REST API `GET /api/projects/{project}/components/` to snapshot `license`, `license_url`, `source_language`, and component slugs.
2. Data export only after license filter: public Weblate download/TMX/PO endpoint for `haw` translations, e.g. `GET /download/{project}/{component}/haw/?format=po` or a TMX export if the instance exposes it.
3. Accept only translated HAW rows (`msgstr` non-empty); exclude suggestions, fuzzy/unapproved rows unless Weblate marks them translated.

## Rate-limit guidance

- Hosted Weblate API response headers: `x-ratelimit-limit: 100`, `x-ratelimit-remaining: 58`, `x-ratelimit-reset: 86081`.
- Fedora Weblate API response headers: `x-ratelimit-limit: 100`, `x-ratelimit-remaining: 98`, `x-ratelimit-reset: 86372`.
- Use the user-mandated polite User-Agent and at least 2 seconds between requests; keep metadata probes well below 100 requests/window. Prefer one component-list request per project, then one export request only for cleared components.

## Verdict

**YELLOW — proceed with restrictions.**

Reasoning:

- Instances found: Hosted Weblate has multiple EN-source Hawaiian projects; Fedora has `rpminspect` EN→HAW.
- Robots explicitly allow `/languages/`, `/projects/`, and `/exports/` on Hosted and Fedora Weblate.
- Component licenses are explicit. MIT and Apache-2.0 components are usable candidates under a strict open-license gate.
- Copyleft components (`GPL-*`, `LGPL-*`, `AGPL-*`) are not clearly compatible with the mixed Stage-2 training corpus and should remain blocked unless counsel/project policy explicitly approves copyleft localization strings for ML training.
- Weblate TOS does not itself grant content reuse rights; do not treat platform-level openness as sufficient.

Allowed next-round subset:

- Hosted Weblate components with `MIT` or `Apache-2.0` only: `django-zxcvbn-password-validator`, `dpo-voyager`, Apache-licensed F-Droid components, `geoweather` if translated rows exist, and the Apache-licensed Prism Launcher component.
- Exclude Fedora `rpminspect`, Hosted `iso-codes`, GPL/AGPL F-Droid components, GPL Prism glossary, and Stellarium Mobile.

## Adapter sketch

Canonical Stage-2 candidate rows:

- `source`: `weblate-en-haw`
- `source_url`: component language URL, e.g. `https://hosted.weblate.org/projects/{project}/{component}/haw/`
- `edition_or_version`: `{instance_host}@{project}/{component}/haw; license={SPDX}; probed=20260503`
- `en`: PO `msgid` / source string.
- `haw`: PO `msgstr` / Hawaiian target string.
- `register`: `software-l10n`
- `direction_original`: `en->haw` when `source_language.code` is `en`, `en_US`, or `en_GB`.
- `alignment_type`: `parallel-sentence` for single string units; `alignment_method`: `source-target-localization`.
- `split`: `review-pending` initially; promote only after quality/cap review.
- `prototype_only`: `true`; `release_eligible`: `false` until final legal review.
- `license_inferred`: `null`; store SPDX in `source_license`/metadata field if schema supports it, otherwise report sidecar.
- Filters: non-empty source/target, source language EN-family, exact component license in permissive allowlist, no fuzzy/suggestion-only rows, min-length/ratio checks.

Dedup priority slot: low-priority `software-l10n`, below canonical Tatoeba/Wikimedia/HK legal sources; prefer non-software sources on exact-pair conflicts, but keep unique software localization rows as review-pending.

## What would change the verdict

- GREEN: each fetched component has permissive SPDX license (`MIT`, `Apache-2.0`, `BSD-*`, `ISC`, `CC0`, `CC-BY`) plus a stable, robots-allowed export endpoint and an on-disk TOS snapshot.
- RED for any component if license is missing, project-level license conflicts with component license, export path becomes robots-disallowed, or the instance requires auth/paywall/API terms that prohibit reuse.
