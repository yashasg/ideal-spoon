# Rusty — Stage 1 Frontier Comparison Row

**Date:** 2026-05-04T08:09:11Z
**Owner:** Rusty (NLP Researcher)
**Status:** Complete for Stage 1 row; GPT-5-chat still blocked

## Decision

Updated the frontier comparison artifact at `docs/eval-runs/frontier/20260504T074014Z__s0_vs_frontier_comparison.md` to keep the cross-model table restricted to metrics that are 1:1 across local checkpoints and frontier chat APIs: frozen `stage0.v1` `human_fetch` char-bigram F1, orthography aggregate, and tripwire pass/fail.

## Cells added for Stage 1 `checkpoint-10140`

Source artifact: `data/eval_runs/stage1/20260504T080245Z__stage1_checkpoint-10140_eval.json`.

| Cell | Value |
|---|---:|
| Model / run | Stage 1 `checkpoint-10140` |
| human_fetch EN→HAW char_F1 | 0.443894 |
| human_fetch HAW→EN char_F1 | 0.346667 |
| wrong ʻokina total | 0 |
| kahakō total | 53 |
| NFC failures | 0 |
| Tripwires | pass |
| Notes | Added from the Stage 1 full JSON artifact |

## PPL handling

Per prior frontier-chart PPL policy, PPL is not a cross-model metric. Frontier PPL is marked N/A / not supported because GitHub Models chat-completions APIs do not expose token logprobs. Local checkpoint PPL is recorded only in the comparison artifact's internal diagnostics section: Stage 0 `7.9152` → Stage 1 checkpoint-10140 `3.6229`, a `-54.2%` change. English PPL remains `not_configured`; manual W1 remains `draft_only` and is not reportable.

## GPT-5-chat retry outcome

Retried `MODELS="openai/gpt-5-chat" ./scripts/run_frontier_eval.sh` at `2026-05-04T08:09:11Z` using the GPT-5 harness fix from commit `7c8bf8f`. The run still hit GitHub Models API rate limits during the `human_fetch` probe before a complete JSON artifact could be emitted. No GPT-5 metrics were copied, inferred, or fabricated; the comparison row remains pending and `docs/eval-runs/frontier/BLOCKERS.md` records the new attempt timestamp.
