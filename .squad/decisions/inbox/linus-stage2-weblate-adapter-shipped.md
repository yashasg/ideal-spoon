# Linus Stage-2 Round 10 — Weblate permissive-only adapter shipped

Date: 2026-05-03

## Verdict

Adapter-ready, awaiting `--execute`. No live network calls were made in Round 10; tests use mocked HTTP and an inline TMX fixture only.

## SPDX allowlist

Accepted exact SPDX IDs:

- `MIT`
- `Apache-2.0`
- `BSD-2-Clause`
- `BSD-3-Clause`
- `MPL-2.0`
- `CC0-1.0`
- `CC-BY-4.0`

Allowlist regex: `^(MIT|Apache-2\.0|BSD-2-Clause|BSD-3-Clause|MPL-2\.0|CC0-1\.0|CC-BY-4\.0)$`

Blocked: GPL family, AGPL, LGPL, CC-BY-SA, all-rights-reserved, missing/ambiguous license.

## Instance list

- Hosted Weblate: `https://hosted.weblate.org`
- Fedora Weblate: `https://translate.fedoraproject.org`

Round 9 found Hosted Weblate has permissive MIT/Apache HAW components; Fedora `rpminspect` was GPL and remains blocked unless policy changes.

## What is gated behind `--execute`

Discovery (`scripts/345_discover_weblate_haw_projects.py`) refuses live HTTP unless all gates pass:

1. `--execute`
2. `--instance hosted|fedora|all`
3. `--confirm-license-allowlist` exactly matching the allowlist regex above
4. `--tos-snapshot` pointing at an existing local TOS snapshot file
5. polite User-Agent, >=2s sleep, <=30 requests/minute default

Candidate build (`scripts/346_build_weblate_candidates.py`) refuses TMX downloads/writes unless all gates pass:

1. `--execute`
2. `--inventory` pointing at a local discovery TSV
3. exact allowlist confirmation
4. local TOS snapshot file
5. accepted inventory row (`accepted=true`) and exact allowlisted SPDX license

Output on execute: `data/stage2/candidates/weblate.jsonl` (under gitignored `data/`). Rows remain `prototype_only=true`, `release_eligible=false`, `split=review-pending`, `register=software-l10n`.
