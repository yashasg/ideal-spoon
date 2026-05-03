# Stage-2 license-first probe: Mozilla Common Voice Hawaiian metadata

- Date: 2026-05-03
- Probe owner: Linus, Stage-2 round 16
- Network scope: metadata/license/robots only; no audio, no clips TSV, no bulk download, no `--execute`.

## URL

- HF dataset card checked: https://huggingface.co/datasets/mozilla-foundation/common_voice_17_0
- Common Voice robots: https://commonvoice.mozilla.org/robots.txt
- Common Voice metadata endpoint checked: https://commonvoice.mozilla.org/api/v1/datasets/languages
- Mozilla Data Collective Common Voice page: https://mozilladatacollective.com/organization/cmfh0j9o10006ns07jq45h7xk
- Mozilla Data Collective robots: https://mozilladatacollective.com/robots.txt
- CC0 reference page: https://creativecommons.org/publicdomain/zero/1.0/

## License observed verbatim

- Mozilla Data Collective Common Voice table shows dataset license cells as `CC0-1.0`.
- Creative Commons deed title: `CC0 1.0 Universal`.
- Creative Commons deed notice: `The Commons Deed is not a legal instrument. It is simply a handy reference for understanding the CC0 Legal Code`.

## Robots / access

- `https://commonvoice.mozilla.org/robots.txt`: `User-agent: *`, `Disallow: /spontaneous-speech/`.
- `https://mozilladatacollective.com/robots.txt`: `User-Agent: *`, `Allow: /`.
- Probe used a polite UA and sleeps. No audio or clip archives were downloaded.

## Schema / coverage

- HF card page is reachable but did not expose `haw`, `Hawaiian`, `CC0`, clips, or duration in card text.
- Common Voice `/api/v1/languages` returned 431 language entries with no `haw` / `Hawaiian` match.
- Common Voice `/api/v1/datasets/languages` returned 137 dataset-language entries with no `haw` / `Hawaiian` match.
- Hawaiian locale status: not observed. Total clips/duration: `0 / not available` for Hawaiian in observed metadata.

## Contamination risk vs existing sources

- Audio is out of scope for text Stage-2.
- If Common Voice later exposes Hawaiian validated text prompts/sentences, they may be monolingual HAW or prompt text, not guaranteed parallel EN↔HAW.
- Prompt text may overlap public-domain sentence lists or other Common Voice prompt sources; it needs side-hash contamination checks before any use.

## Verdict

- RED for current Stage-2 ingestion: no Hawaiian locale observed in metadata.
- License posture for Common Voice generally looks GREEN (`CC0-1.0`), but absent Hawaiian coverage makes this source unusable now.

## Routing

- Current routing: SKIP.
- Future routing if Hawaiian appears: consider monolingual/prompt-ledger first, not parallel train; only promote to TRAIN if prompt text is actually CC0, Hawaiian text is present, no TOS restriction conflicts, and contamination checks pass.

## Adapter sketch

- No adapter now.
- Future probe should pin a Common Voice release, record robots/TOS/license snapshots, read metadata only first, and refuse audio downloads.
- Candidate path, if ever justified, should emit prompt strings as monolingual HAW or paired metadata only after confirming schema fields and license; no blind EN↔HAW parallel assumption.
