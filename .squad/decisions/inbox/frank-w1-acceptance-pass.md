# Frank — W1 acceptance pass

Date: 2026-05-04
Requested by: Yashas

## Decision

Frank accepted all five current `data/evals/manual_w1/w1-haw-micro-eval.jsonl` rows for W1 reportability. No rows were flagged.

## Row decisions

- `w1-okina-001` — ACCEPT: `Hawaiʻi` uses U+02BB ʻokina, is NFC-normalized, and retained its existing normalized hash.
- `w1-kahako-001` — ACCEPT: `mālama i ka ʻōlelo Hawaiʻi` has expected precomposed kahakō and U+02BB ʻokina, is NFC-normalized, and retained its existing normalized hash.
- `w1-unicode-001` — ACCEPT: `ā ē ī ō ū ʻ` is a clean Unicode/NFC probe with precomposed kahakō vowels plus U+02BB ʻokina, and retained its existing normalized hash.
- `w1-tokenizer-001` — ACCEPT: `ʻĀā ʻĒē ʻĪī ʻŌō ʻŪū` is a clean tokenizer round-trip probe using U+02BB and precomposed kahakō vowels, and retained its existing normalized hash.
- `w1-generation-001` — ACCEPT: the Hawaiian prompt is orthographically clean; empty reference is allowed for `generation_sanity`; existing normalized hash retained.

## Provenance and policy checks

All accepted rows carried `schema_version=manual-w1-jsonl-v1`, `source_id=manual_w1`, `source_path=data/evals/manual_w1/w1-haw-micro-eval.tsv`, `nfc_normalized=true`, and recomputed hashes matching the stored `sha256_normalized` values. The regenerated JSONL now has `review_status=accepted`, `eval_consumable=true`, `prototype_local=false`, and `split=w1` for all five W1 rows. The W1 hash manifest and `data/evals/eval_hashes.jsonl` were regenerated with accepted-only manual W1 ledger rows.

## Sanity result

`accepted=5, draft=0, flagged=0`. The Stage 0/1 W1 probe now reports `status=evaluated`, `accepted_count=5`, `schema_version_seen=manual-w1-jsonl-v1`, and `scoring_status=not_wired`.
