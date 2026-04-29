# Orchestration Log: Linus — Rights-Light Stage 1 MVP + Go/No-Go Gate (2026-04-29T06:13:58Z)

**Agent:** Linus (Data Engineer)  
**Outcome:** Approved (decision proposal, inbox → decisions.md pending merge)  
**Request:** Whether 2.5M–7M tokens of clear/right-clearable Stage 1 candidates are sufficient to start without rights-review-heavy work.

## Headline

**Yes** — Stage 1 can start with rights-light candidates only (hawwiki, Wikisource, pre-1925 Baibala scans, small reviewed long tail). Rights-review-heavy sources (nūpepa, OHA/DOE/UH bulk, Awaiaulu, OPUS/NLLB at scale) stay deferred behind an explicit six-point go/no-go gate. This is *not* a license-skipping shortcut; manifest discipline (per-doc license, source URL, fetch date, ToS snapshot, SHA-256) remains non-negotiable even for "rights-light" material.

## Stage 1 MVP — Sources IN

All sources tagged `open_license_candidate` or `public_domain_candidate` in `data-sources/hawaiian-data-sources.json`:

- **hawwiki + dump status manifest:** CC BY-SA 4.0 + GFDL. Cleanest license. Already §Stage 1 "first adapter" target.
- **Hawaiian Wiktionary:** Same license posture; tiny but free.
- **Hawaiian Wikisource:** Public-domain Hawaiian texts, cleaner than nūpepa OCR.
- **Pre-1925 Baibala Hemolele scans (archive.org):** Pre-1925 → PD in US. Capped ≤10% Stage 1 tokens per existing ADR; tag `register=religious-archaic`.
- **Small reviewed long tail:** Only per-doc human-review-passing items. No bulk crawls.

**Note:** Stage-2-only or eval-only entries (interlanguage links, Tatoeba, FLORES-200 devtest) unaffected.

## Stage 1 MVP — Sources DEFERRED

All `rights_review_required` and `unknown_review_required` entries:
- Ulukau nūpepa crawl + Wayback CDX snapshots.
- archive.org nūpepa mirrors.
- OPUS haw subsets, NLLB Seed/MD haw slices (Stage 2 anyway).
- Baibala Hemolele official site (modern editions; pre-1925 scans stay OK).
- OHA / DOE Kaiapuni / UH bulk crawls + Wayback snapshots.
- Awaiaulu public translations.
- Hawaiian-language video transcripts.

Remain in inventory as *known* sources. Not fetched in MVP.

## "Rights-Light" Still Requires (Non-Negotiable)

This is not a license-skipping shortcut. Per existing pipeline rules:

1. **Per-document `license_observed`** captured in manifest — even for CC BY-SA 4.0 / public-domain rows.
2. **Per-document `source_url` + `fetch_date` + payload SHA-256** — same as any source.
3. **ToS snapshot at fetch time** — Wikimedia ToS URL captured per `provenance_fields_to_capture`.
4. **`license_inferred = null` invariant unchanged.** CC BY-SA is *observed*, not inferred, because the dump declares it.
5. **No raw blobs in git, no public publication of artifacts** — prior ADRs on storage + prototype scope still bind.

What "rights-light" buys: *avoiding bulk human rights review of rights-review-heavy collections*, not avoiding manifest discipline.

## Honest Size Expectation

Numbers on Hawaiian open-license corpora are small (order-of-magnitude only):

- hawwiki + Wiktionary: low single-digit million tokens after cleanup.
- Wikisource (haw): ~hundreds of thousands to ~1M tokens, optimistically.
- Pre-1925 Baibala scans (≤10% cap): few hundred thousand tokens at most.
- Reviewed long tail: entirely dependent on human-time budget.

**Total MVP corpus is sufficient for pipeline validation + tokenizer audit.** It is **not** sufficient on its own to expect strong DAPT signal on 7B–9B model. Treat as *plumbing-grade*, not *training-grade*.

## Go / No-Go Gate Before Touching Rights-Review-Heavy Sources

Do **not** start the Ulukau nūpepa adapter or any bulk `rights_review_required` ingest until **all** of these are true:

1. **MVP corpus exists end-to-end:** `stage1_manifest.parquet`, `stage1.jsonl.gz`, packed tensors produced from hawwiki + Wiktionary + Wikisource + pre-1925 Baibala. CI lineage gate refuses public export.

2. **Tokenizer audit completed on MVP corpus** (Rusty owns; Linus supplies). ʻokina survival, kahakō unitarity, tokens-per-word, byte-fallback rate measured on candidate bases.

3. **MVP token count + register mix reported.** If MVP alone demonstrably sufficient for prototype's stated goal, may stop here and skip rights-heavy work entirely.

4. **Cultural-review owner named** for hard-escalate categories (mele/oli/pule, moʻolelo from named tradition-bearers, moʻokūʻauhau). **Required** before nūpepa bulk (contains these registers).

5. **Per-source rights review process written into decisions log:** who reviews, what evidence recorded in manifest, how takedown requests honored, where ToS snapshots live. Not a Slack message — formal ADR entry.

6. **Storage + access controls confirmed** for any `prototype_only=true` material (gitignore, disk-encryption invariants verified before pulling at scale).

**If any of 1–6 is missing: no-go on rights-heavy ingest.**

## Documentation Impact

- **`docs/data-pipeline.md`:** No text change required. Existing Tier A/B framing and §"Stage 1 immediate next steps" already sequence hawwiki-first → nūpepa-second. This proposal *names the gate explicitly* and *defines MVP scope by rights tag* rather than by source name.
- **`data-sources/hawaiian-data-sources.json`:** No change required; `rights_status_hint` field already encodes the split.

If accepted, the MVP set above becomes binding "Stage 1 phase 1" scope; rights-heavy ingest is "Stage 1 phase 2" and gated.

## Open Items for Team

1. **Cultural-review owner** — still unfilled. Long-pole item for unblocking nūpepa bulk regardless of rights cleanup.
2. **Reviewed long-tail budget** — how many human-hours/week willing to spend doing per-doc rights review on OHA/DOE/UH PDFs? If ~zero, long tail effectively excluded from MVP; say so plainly.
3. **Tokenizer-audit pass criteria** — Rusty to define what "good enough" looks like on MVP corpus before committing to phase 2 scope.

## Decision Status

**Approved.** `.squad/decisions/inbox/linus-rights-light-stage1-mvp.md` written 2026-04-29T23:13:00Z (per agent history). Ready for merge into `.squad/decisions.md`.

## References

- `.squad/agents/linus/history.md` § 2026-04-29 — Rights-light Stage 1 MVP scope + go/no-go gate (lines 155–187)
- `.squad/decisions/inbox/linus-rights-light-stage1-mvp.md` (source proposal)
