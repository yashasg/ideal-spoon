# Linus Stage-2 Round 12 — Taxi1500 license-first probe

Date: 2026-05-03

## Canonical URL

- Repository: `https://github.com/cisnlp/Taxi1500`
- Stage-2 registry entry: `data-sources/stage2-parallel-fetch-plan.json:414-450`
- Prior inventory alias: `cis-lmu/Taxi1500-RawData` / `haw_Latn`, documented in `.squad/decisions-archive.md:2220-2252`.

## Network/TOS clearance

Allowed metadata-only requests made with a polite UA; no corpus zip, TSV, split file, or authenticated endpoint was fetched.

- `https://github.com/robots.txt`: HTTP 200. `User-agent: *` blocks raw/tree/search-like crawler paths on `github.com`, but the repository README was read via `raw.githubusercontent.com` as a license/card-style metadata page; no bulk data path was fetched.
- `https://raw.githubusercontent.com/cisnlp/Taxi1500/main/README.md`: HTTP 200; repository card/README only.
- `https://raw.githubusercontent.com/cisnlp/Taxi1500/main/LICENSE`: HTTP 200; license text only.
- `Taxi1500-c_v1.0/README.md` and `Taxi1500-c_v2.0/README.md`: HTTP 200; subdirectory README metadata only.

## License

Repository `LICENSE` is Apache-2.0. Verbatim grant excerpt:

> "Apache License Version 2.0, January 2004"
>
> "Subject to the terms and conditions of this License, each Contributor hereby grants to You a perpetual, worldwide, non-exclusive, no-charge, royalty-free, irrevocable copyright license to reproduce, prepare Derivative Works of, publicly display, publicly perform, sublicense, and distribute the Work and such Derivative Works in Source or Object form."

Important caveat from the README:

> "While Taxi1500 covers 1502 languages in total, we release 1871 editions in 823 languages which are either open access or have a license permitting distribution at the time of publication. Due to copyright restrictions, these are released as a corpus instead of the actual dataset, and can be converted into the dataset format shown below using the included processing code."

Subdir metadata says v1.0/v2.0 corpora are downloadable ZIPs from LMU and explains permissive filtering, but those ZIPs were not fetched.

## haw_Latn coverage

- Coverage remains **not count-confirmed** in this no-data-fetch probe.
- Existing project inventory says `cis-lmu/Taxi1500-RawData` has `haw_Latn` and describes it as "Bible-derived topic classification eval" (`.squad/decisions-archive.md:2220-2252`).
- The active fetch plan still marks `taxi1500-haw` as `verification_status: pending_endpoint_check` and `adapter_status: none` (`data-sources/stage2-parallel-fetch-plan.json:414-450`).
- Train/dev/test row counts for `haw_Latn`: **unknown from the allowed README/license pages**. Confirming counts appears to require either fetching/listing corpus/split contents or using a dedicated metadata endpoint not cleared in this round. Under the hard rule, stop here rather than infer counts.

## Schema

README dataset structure:

| Field | Meaning |
|---|---|
| `id` | verse id |
| `label` | topic label |
| `verse` | verse text |

Label set quoted from the README table:

- `Recommendation`
- `Faith`
- `Description`
- `Sin`
- `Grace`
- `Violence`

## Contamination risk

**High.** Taxi1500 is explicitly Bible-derived:

> "Taxi1500 is developed based on the PBC and 1000Langs corpora."

The task examples are Bible verses, and the Stage-2 plan already says "never train on FLORES / global-piqa / Taxi1500" (`data-sources/stage2-parallel-fetch-plan.json:975`). Any Hawaiian rows may overlap semantically or exactly with existing Baibala 1839 / Baibala 1868 / BibleNLP-style candidate rows. If ever ingested, every row must be registered in `data/evals/eval_hashes.jsonl` before any train manifest build, and train candidates matching Taxi1500 verse hashes must be dropped or quarantined.

## Verdict

**YELLOW — EVAL-only pending count/pin confirmation.**

The repo license is clear for repository contents, but the released corpus is Bible-derived and count/split metadata for `haw_Latn` was not safely confirmable without fetching data. Routing remains diagnostic/eval-only, never TRAIN.

## Routing

**EVAL-only.** Rationale:

1. Bible-domain classification, not translation training data.
2. Direct contamination risk against existing Bible 1839/1868 rows.
3. Existing project policy explicitly says never train on Taxi1500.
4. Split/count confirmation still needs a later metadata-cleared or local-file round.

## Adapter sketch if proceeding

Do not create `data/stage2/candidates/` rows. Build an eval-ledger ingester only after a future round confirms `haw_Latn` counts and pins an exact commit or release artifact:

- Require exact source pin: repo commit plus corpus version (`Taxi1500-c_v1.0` or `Taxi1500-c_v2.0`) and local license/TOS snapshot.
- Require operator confirmation: `--confirm-routing EVAL_ONLY_NO_TRAIN`.
- Parse fields `id`, `label`, `verse`; reject rows outside the six-label set.
- Emit only `data/evals/eval_hashes.jsonl` entries with `origin=taxi1500-haw`, `eval_only=true`, `content_sha256`, `label`, and source row id.
- Before manifest emission, use the existing eval contamination guard to exclude matching Bible-family train rows.
