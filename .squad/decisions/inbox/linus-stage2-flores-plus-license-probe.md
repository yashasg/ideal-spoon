# Stage-2 license-first probe: FLORES+ haw_Latn

- Date: 2026-05-03
- Probe owner: Linus, Stage-2 round 16
- Network scope: license/card/robots only; no dataset download, no `--execute`.

## URL

- Dataset card: https://huggingface.co/datasets/openlanguagedata/flores_plus
- Dataset metadata checked for file/config names only: https://huggingface.co/api/datasets/openlanguagedata/flores_plus
- License page: https://creativecommons.org/licenses/by-sa/4.0/
- Robots: https://huggingface.co/robots.txt

## License observed verbatim

- HF card metadata: `cc-by-sa-4.0`
- HF card text: `FLORES+ is a multilingual machine translation benchmark released under CC BY-SA 4.0.`
- Creative Commons deed title: `Attribution-ShareAlike 4.0 International`
- Creative Commons condition: `ShareAlike — If you remix, transform, or build upon the material, you must distribute your contributions under the same license as the original.`

## Robots / access

- `https://huggingface.co/robots.txt`: `User-agent: *` / `Allow: /`.
- Probe used a polite UA and sleeps. No data files were downloaded.

## Schema / coverage

- HF card says FLORES+ has `228 language varieties`.
- HF card says each included language has `997 sentences for the dev split and 1012 sentences for the devtest split`.
- Metadata check found `siblings 480`, `haw []`, and `configs haw []`.
- Result for Hawaiian: `haw_Latn` not present in observed card/metadata. Row count for Hawaiian is therefore `0 / not available`, not 997+1012.

## Contamination risk vs existing sources

- If Hawaiian is added later, risk is high for train contamination because FLORES is a standard MT benchmark and should be kept out of training.
- No current collision work is needed because no haw_Latn rows were observed.

## Verdict

- RED for current Stage-2 ingestion: Hawaiian absent.
- If future `haw_Latn` appears: YELLOW / EVAL-only due benchmark status and CC-BY-SA share-alike obligations.

## Routing

- Current routing: SKIP.
- Future routing if haw_Latn appears: EVAL ledger only; never train candidates.

## Adapter sketch

- No adapter now.
- Future adapter must require exact dataset revision pin, exact `cc-by-sa-4.0` confirmation, local ToS/license snapshot, and `--execute`.
- It should hash EN and HAW sentences into `data/evals/eval_hashes.jsonl` before any train ingest, mark `eval_only=true`, and refuse writes under `data/stage2/candidates/`.
