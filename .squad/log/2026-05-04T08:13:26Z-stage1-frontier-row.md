# Session Log — 2026-05-04T08:13:26Z — Stage 1 Frontier Row

**Agent:** Scribe (Logger)  
**Event:** Rusty frontier-chart follow-up  
**Status:** Complete

## Summary

Recorded Rusty's two sync spawns: frontier PPL is not a 1:1 chart metric, and the Stage 1 `checkpoint-10140` row was added to the frontier comparison report.

## Durable Outcomes

- Frontier PPL stays `N/A` / `not_supported`; local checkpoint PPL remains diagnostics-only.
- Stage 1 `checkpoint-10140` comparison row now reports EN→HAW F1 `0.443894`, HAW→EN F1 `0.346667`, wrong ʻokina `0`, kahakō `53`, NFC failures `0`, tripwires pass.
- Local PPL diagnostic: Stage 0 `7.9152` → Stage 1 `3.6229` (`-54.2%`).
- GPT-5-chat eval remains blocked by GitHub Models rate limits; no metrics fabricated.
