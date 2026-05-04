# Session Log — Stage 3 Paragraph Proposal

- **Timestamp:** 2026-05-04T05:29:51Z
- **Scribe:** Copilot Scribe
- **Subject:** Stage 3 paragraph-grain SFT proposal

## Spawn manifest handled

- `linus-stage3-eval` ran sync on `claude-sonnet-4.5`.
- Verdict: yes to a separate Stage 3 paragraph/document lane, but defer until Stage 2 plateaus.
- Required controls: lower LR, short epochs, overlap metadata, length-aware admission, and sentence-regression gates.
- Cross-agent follow-up: none.

## Scribe actions

- Wrote orchestration log for `linus-stage3-eval`.
- Wrote this session log.
- Merged `.squad/decisions/inbox/` into `.squad/decisions.md` with exact-content de-dupe.
- Deleted merged inbox files.

## Decision summary

Stage 2 remains the sentence/verse/row-grain SFT path. Stage 3 can later train paragraph/document coherence from Hoʻoilina paragraphs/recovery, HK legal sections/articles, Bible or Gospel aggregates if built, and possibly aligned nupepa articles, but only as an intentional late curriculum with overlap tracking and regression protection.
