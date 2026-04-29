# Session Log: Stage 1 Rights-Light Sufficiency Outcome (2026-04-29T06:13:58Z)

**Topic:** Whether right-clearable hawwiki/Wikisource-like sources are sufficient for Stage 1 and whether rights-review-heavy data can be avoided initially.

**Agents Polled:**
- Rusty (NLP Researcher): Stage 1 corpus-size sufficiency
- Linus (Data Engineer): Rights-light Stage 1 MVP scope

## Outcome Summary

✓ **Stage 1 can proceed with rights-light candidates only.**

Linus proposes explicit MVP set (hawwiki, Wikisource, pre-1925 Baibala scans ≤10%, small reviewed long tail) + six-point go/no-go gate before rights-review-heavy ingest (nūpepa, OHA/DOE/UH bulk, Awaiaulu). Manifest discipline unchanged; stage-specific eval triggers defined.

Rusty confirms 2.5–7M tokens sufficient for *prototype/plumbing-grade* Stage 1 (pipeline + tokenizer + adapter validation). Not sufficient for strong DAPT on 7B–9B base without triggering at least one of: non-wiki PPL improvement, Stage-2 chrF gains across registers, dedup-validated learning (not memorization), tokenizer audit clearance.

## Next Steps

1. Merge Linus proposal into `.squad/decisions.md`.
2. Schedule tokenizer audit (Rusty + hawwiki + Wikisource + non-wiki sample).
3. Assign cultural-review owner (long-pole for phase 2 gate #4).
4. Define tokenizer-audit pass criteria (gate #2).
