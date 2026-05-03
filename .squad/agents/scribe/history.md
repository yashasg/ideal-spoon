# Scribe — History

## Core Context

- **Project:** A plan for training an open-source LLM focused on the Hawaiian language, including data, model choices, infrastructure, evaluation, and costs.
- **Role:** Session Logger
- **Joined:** 2026-04-29T01:38:35.144Z

## Learnings

<!-- Append learnings below -->

### Free-compute + base-model research session (2026-04-29)
- Merged 3 inbox decisions into `.squad/decisions.md`: Livingston Azure-credit framing, Basher credit-fit advisory, Rusty base-model recommendation.
- Wrote 5 orchestration-log entries (one per spawn) and 1 session log under `.squad/log/`.
- Decisions.md size ~10KB, well under archive threshold; no archive needed.
- All agent histories self-updated by the spawned agents (Livingston, Basher, Rusty); no cross-agent appends required.

### Prototype / public-data scope session (2026-04-29T03:01:58Z)
- Merged 3 inbox decisions into one consolidated ADR in `.squad/decisions.md`: Copilot directive (prototype framing), Linus prototype data posture, Danny prototype-vs-release split.
- Wrote 3 orchestration-log entries (Copilot directive, Linus, Danny) and 1 session log.
- Decisions.md grew to ~44KB; all entries dated 2026-04-29 (none ≥30 days old), so no archive yet.
- Cross-agent appends: Basher, Rusty, Livingston histories nudged with prototype-vs-release awareness. Danny and Linus self-updated.
- One unrelated inbox file (`linus-stage1-data-pipeline.md`) left in place — not in this session's scope.

## 2026-04-29T03:13:13Z — Stage-1 + Stage-2 data pipeline consolidation

Wrote orchestration-log entries for both Linus pipeline passes; wrote session log `2026-04-29T03:13:13Z-data-pipeline-stage1-stage2.md`; merged both inbox proposals into `.squad/decisions.md` as a single ADR; deleted the two inbox files. No archive needed (all decisions dated 2026-04-29). README not edited per spawn directive; flagged for later.

## 2026-04-29T06:56:07Z — Session Log: Python Script Contracts

- **Decisions merged:** Three inbox files merged into `.squad/decisions.md`: (1) Python-scripts directive (Coordinator/yashasg), (2) frank-fetch-raw-jsonl-schema.md, (3) linus-stage1-jsonl-first.md. Inbox files deleted. No duplicates.
- **Orchestration log:** `.squad/orchestration-log/2026-04-29T06-56-07Z-python-script-contracts.md`
- **Session log:** `.squad/log/2026-04-29T06-56-07Z-python-script-contracts.md`
- **Agent histories updated:** Frank (validation + merge), Linus (Stage-1 JSONL approval), Scribe (this session).

## 2026-05-01T00:59:31Z — Orchestration Log: Baibala Edition Pin Dependency Resolution

**What:** Processed Linus's completed work on Baibala Hemolele 1839 edition pin (issue #16). Frank now unblocked for parser implementation.

**Tasks completed:**
1. ✅ Orchestration log written: `.squad/orchestration-log/2026-05-01T00-59-31Z-linus-baibala-pin.md`
2. ✅ Session log written: `.squad/log/2026-05-01T00-59-31Z-baibala-edition-pin.md`
3. ✅ Inbox decision merged: `linus-baibala-edition-pin.md` → `.squad/decisions.md`; inbox file deleted
4. ✅ Cross-agent history appends: Frank history updated with unblocking notification; Linus history updated with session summary
5. ✅ Decisions archive: Not needed (decisions.md remains under 300KB; newest entry is today)

**Deferred:**
- No git commit (per spawn manifest)
- No history summarization (per spawn manifest)

**Status:** Ready for Frank parser implementation; Coordinator may route #16 to Frank next.

## 2026-05-02T00:56:01Z — Stage 2 Final Review Verdicts Session Log

**Spawn request:** "finish the pending reviews man"

**Tasks completed:**
1. ✅ **Orchestration log:** `.squad/orchestration-log/2026-05-02T00-56-01Z-stage2-final-review-verdicts.md` — documented Danny policy + Basher implementation + Basher validation + team outcomes.
2. ✅ **Session log:** `.squad/log/2026-05-02T00-56-01Z-stage2-final-review-verdicts.md` — summarized what happened, artifacts, team impact, next steps.
3. ✅ **Decisions merge:** Merged 9 inbox files into `.squad/decisions.md`. Updated tag with merge summary. Decisions.md grew from 6,073 to 7,214 lines (~370 KB total; well under 500 KB archive threshold and 30-day policy).
4. ✅ **Inbox cleanup:** Deleted all 9 inbox files from `.squad/decisions/inbox/`.
5. ✅ **Cross-agent history appends:** Updated Danny (policy filed) + Basher (implementation + validation complete) histories. Appended brief updates to Scribe (this entry).
6. ✅ **Git staging:** Will commit `.squad/` changes with co-authored trailer.

**Decisions merged:**
- Danny final review verdict policy (8 sections, closed enum, source rules, 10 invariants)
- Basher finalized review verdicts (33,851 rows with verdicts; caps verified; SFT 570 rows unchanged)
- Basher stage 2 Ulukau validation (hooilina findings + 6-check mandatory protocol)
- 6 other inbox files (Frank raw-provenance, Frank Wehewehe PD, Frank more-Ulukau-SFT, Linus HK, Linus structured-counts, Linus Ulukau-vetting)

**Status:** All pending reviews finished. Frank ready for NLLB/synthetic-BT budget planning (32,756 re-promotion budget). Linus ready for HK statutes / Wehewehe PD parsing. Hoʻoilina adapter blocked on upstream HTML decode fix.

## 2026-05-03T07:11:32Z — Linus LaBSE Review-Row Promotion R1 Session Log

**Spawn request:** Linus completed LaBSE review-row promotion R1 work. Process orchestration logs, session logs, merge inbox, commit.

**Tasks completed:**
1. ✅ **Orchestration log:** `.squad/orchestration-log/2026-05-03T07-11-32Z-linus.md` — documented 5-gate promotion filter outcome (9 passed → all 9 cap-policy-excluded), SFT unchanged, recommendation.
2. ✅ **Session log:** `.squad/log/2026-05-03T07-11-32Z-labse-review-promotion-r1.md` — brief session summary with key findings and artifacts.
3. ✅ **Decisions merge:** Merged 24 inbox files into `.squad/decisions.md`. Linus labse-review-promotion-r1 decision appended with full 124-row audit, filter outcome breakdown, recommendation.
4. ✅ **Inbox cleanup:** Deleted all 24 inbox files from `.squad/decisions/inbox/`.
5. ✅ **Cross-agent updates:** No cross-agent history appends required (Linus self-contained decision).

**Decisions merged:**
- Linus LaBSE review-row promotion R1 (124 rows: 9 promoted → all policy-excluded; SFT 8,572 unchanged)
- Linus LaBSE merge round 2 (+296 accept, total 8,572 SFT)
- Linus stage 2 gap analysis (40k target path)
- Linus source-backlog resolution
- Frank round 2 NLLB + wiki-langlinks extraction (40k target assessment)
- Frank stage 2 blockers (Ulukau access blocked, rights memo)
- Rusty LaBSE bringup complete (4-source scoring)
- Basher Hoʻoilina verification
- And 16 other team-generated decisions

**Size:** Decisions.md now ~70 KB (under 20 KB archive threshold for policy-excluded; no 30+ day entries yet).

**Status:** LaBSE review band correctly filtered by policy. Recommendation to target new sources at ≥0.75 LaBSE score. All decisions recorded; ready for git commit.
