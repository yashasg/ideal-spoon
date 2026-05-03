# Linus Stage-2 Round 12 — Tatoeba refresh license-first probe

Date: 2026-05-03

## Current registry pin

- Fetch plan source: `tatoeba-haw-eng` (`data-sources/stage2-parallel-fetch-plan.json:188-229`).
- Adapter pin: `data-sources/tatoeba/PINNED_DUMP.json` records `dump_date: 2025-05-01`, `license: CC-BY 2.0 FR`, and the haw/eng/link export URLs.
- Adapter README records the same pinned dump date and says raw downloads live under `data/raw/tatoeba-haw-eng/<YYYYMMDD>/` (`data-sources/tatoeba/README.md:7-17`, `:56-60`). No raw Tatoeba dump directory is present locally.
- Current local direct Tatoeba candidate file: `data/stage2/candidates/tatoeba.jsonl` has 121 rows, 111 unique `tatoeba_sentence_id_haw` values. The finalized review manifest has 121 Tatoeba rows: 105 train, 15 dev, 1 held-out/finalized.

## Network/TOS clearance

Allowed metadata-only requests made with a polite UA; no Tatoeba export body was downloaded.

- `https://tatoeba.org/robots.txt`: HTTP 200. It specifies `Crawl-delay: 8`; this probe used >=8s sleeps for Tatoeba requests. The stats page is not disallowed.
- `https://downloads.tatoeba.org/robots.txt`: HTTP 404; no robots restriction found for download metadata. Only HEAD requests were sent to export URLs.
- `https://tatoeba.org/eng/stats/sentences_by_language`: HTTP 200; public stats page only.
- `https://tatoeba.org/eng/terms_of_use`: HTTP 200; license/TOS page only.
- HEAD metadata only:
  - `haw_sentences_detailed.tsv.bz2`: `Last-Modified: Sat, 02 May 2026 06:25:58 GMT`, `Content-Length: 3039`.
  - `haw-eng_links.tsv.bz2`: `Last-Modified: Sat, 02 May 2026 06:33:37 GMT`, `Content-Length: 941`.

## License confirmation

Tatoeba terms still state the text-sentence default license. Verbatim excerpt:

> "Tatoeba's technical infrastructure uses the default Creative Commons Attribution 2.0 France license (CC-BY 2.0 FR) for the use of textual sentences. The BY mention implies a single restriction on the use, reuse, modification and distribution of the sentence: a condition of attribution. That is, using, reusing, modifying and distributing the sentence is only allowed if the name of the author is cited."

Existing adapter policy is still correct: preserve `contributor_haw`, `contributor_en`, sentence IDs, and source URLs for attribution flow-down.

## Latest public haw sentence count

The public stats page row for Hawaiian is:

```html
<tr><td>222</td><td>... alt="haw" title="Hawaiian" ...</td><td>haw</td><td>...Hawaiian...</td><td class="num-sentences"><div class="bar" style="width:0.0094427545301861%"></div>192</td></tr>
```

Latest public Hawaiian sentence count: **192**.

## Comparison to pinned edition

Exact pinned total Hawaiian sentence count is **not stored** in `PINNED_DUMP.json` or the README; local raw downloads are absent. The local candidate artifact has 121 en↔haw rows and 111 unique Hawaiian sentence IDs, which is a linked-pair count, not the same denominator as the stats page's total Hawaiian sentence count.

Best safe delta estimate without re-download:

- Latest total haw sentences: 192.
- Current local linked haw sentence IDs: 111.
- Upper-bound unrepresented Hawaiian sentences relative to our linked set: **up to 81**.
- Upper-bound new en↔haw pair opportunity relative to 121 current pairs: **up to 71** if every extra Hawaiian sentence has an English link; actual pair delta may be lower and requires a future licensed export refresh/count.
- Export `Last-Modified` dates are 2026-05-02, newer than the 2025-05-01 pin, so metadata indicates the export changed since our pin.

## Refresh trigger threshold

Recommend refresh when either condition is met:

1. Confirmed en↔haw pair delta is **>=5%** of the pinned 121 pairs (>=7 new linked pairs), or
2. Confirmed new Hawaiian sentence count is **>=500**.

For this tiny source, the 5% linked-pair threshold is the practical trigger; 500 new Hawaiian sentences is a long-tail safeguard for larger future growth.

## Verdict

**REFRESH-NOW for a gated next round; no data fetched in this round.**

Reason: license remains clear, export metadata is newer than the 2025-05-01 pin, and the latest public haw count (192) leaves a large enough upper-bound gap versus the local linked set (111 unique haw IDs / 121 pairs) to exceed the 5% trigger if even a small fraction are English-linked.

## Next adapter action

In a separate execute-approved round:

- Reconfirm robots/TOS snapshots.
- HEAD all three pinned export URLs and record `Last-Modified`, `Content-Length`, and hashes after download.
- Download only the three existing Tatoeba export files, rebuild `data/stage2/candidates/tatoeba.jsonl`, and report exact pair delta.
- Preserve the current split policy: hash before split, keep held-out/dev rows protected, and prefer canonical Tatoeba over OPUS-Tatoeba duplicates.
