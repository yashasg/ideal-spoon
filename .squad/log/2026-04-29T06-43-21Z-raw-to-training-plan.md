# Session Log — Raw to Training Plan

**Date:** 2026-04-29T06:43:21Z  
**Agent:** Linus (Data Engineer)  
**Requested by:** yashasg  

## What Happened

Linus planned the complete ordered workflow from Frank's rights-light raw fetch through Linus's Stage-1 training dataset preparation, including extraction, normalization, LID, deduplication, eval-hash registration, CI guards, tokenizer audit gate, and Basher handoff.

## Key Outcomes

- 13-stage pipeline documented (raw fetch → JSONL export + CI guard).
- **Vertical-slice strategy:** Hawaiian Wikipedia first (smallest, cleanest); add Wiktionary/Wikisource/Baibala/long tail after validation.
- **Corpus storage:** local-only during prototype (no git, no HF).
- **Rights-heavy sources:** pre-1925 nūpepa bulk, Baibala, JW300 deferred pending cultural reviewer + rights escalation.
- Manifest-first discipline: every fetch-time field registered immediately (ToS snapshot, source URL, fetch date, sha256_raw).
- **Tokenizer audit is a gate:** ʻokina/kahakō audit by Rusty blocks Stage-1 export.

## Decisions Made

1. Dedup via MinHash with cluster-aware split isolation (no similar-doc leakage into eval).
2. Hard contamination guard: `eval_hashes.parquet` blocks any eval doc from training.
3. Three-way cross-contamination check (Stage-1 eval, Stage-2 eval, Stage-2 train).

## Open Gaps

- Cultural-review owner: unassigned (escalate to Coordinator).
- Bible edition pinning: TBD.
- Raw archive storage location: TBD.

## No Repo Edits

This session produced a plan, not code.
