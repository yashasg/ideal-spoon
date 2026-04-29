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
