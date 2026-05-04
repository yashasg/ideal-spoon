# Frontier Baseline vs Stage 0/1 Comparison

**Run ID:** 20260504T074014Z
**Suite:** stage0.v1 (frozen)
**Suite SHA256:** 2683027f538ae8fb2910f758f2865596355893cc91c85dbdfe9ced130797bce6
**Updated:** 2026-05-04T08:09:11Z

## Scope

This comparison uses only the 1:1 metrics shared by local checkpoints and frontier chat APIs: `human_fetch` char-bigram F1, prompt-suite orthography aggregate, and serialized tripwires. Per the frontier-chart PPL policy, Hawaiian PPL is **not** a cross-model column because closed frontier APIs do not expose logprobs. Frontier PPL is therefore N/A / not supported; local checkpoint PPL is tracked separately as an internal diagnostic.

## Model Configuration

| Model | Provider | Endpoint / runtime | Decoding | Status |
|---|---|---|---|---|
| meta-llama/Llama-3.1-8B (Stage 0 base) | local | HF checkpoint on GPU | greedy | complete |
| checkpoint-10140 (Stage 1) | local | PEFT adapter on GPU | greedy | complete |
| openai/gpt-4o | github-models | https://models.github.ai/inference/chat/completions | temp=0 | complete |
| openai/gpt-5-chat | github-models | https://models.github.ai/inference/chat/completions | default sampling | pending — rate-limited |

## Cross-model stage0.v1 generation metrics

| Model / run | human_fetch EN→HAW char_F1 | human_fetch HAW→EN char_F1 | wrong ʻokina total | kahakō total | NFC failures | Tripwires | Notes |
|---|---:|---:|---:|---:|---:|---|---|
| Stage 0 base (`meta-llama/Llama-3.1-8B`) | 0.329114 | 0.469799 | 0 | 34 | 0 | pass | Anchor: `docs/eval-runs/stage0/20260430T094425Z__stage0_base_eval_summary.json` |
| Stage 1 `checkpoint-10140` | 0.443894 | 0.346667 | 0 | 53 | 0 | pass | Added from `data/eval_runs/stage1/20260504T080245Z__stage1_checkpoint-10140_eval.json` |
| `openai/gpt-4o` | 0.398827 | 0.617021 | 0 | 32 | 0 | pass | Frontier baseline summary: `docs/eval-runs/frontier/20260504T073812Z__frontier_github-models_openai_gpt-4o_eval_summary.json` |
| `openai/gpt-5-chat` | pending | pending | pending | pending | pending | pending | Retry at 2026-05-04T08:09:11Z still rate-limited; no complete artifact, no fabricated metrics |

## PPL support policy

| Model / family | Hawaiian PPL cell | Reason |
|---|---|---|
| Stage 0 base (`meta-llama/Llama-3.1-8B`) | internal diagnostic only | Teacher-forced loss is available locally, but this is not a 1:1 closed-frontier metric. |
| Stage 1 `checkpoint-10140` | internal diagnostic only | Teacher-forced loss is available locally, but this is not a 1:1 closed-frontier metric. |
| `openai/gpt-4o` | N/A | Chat-completions APIs do not expose token-level log probabilities. |
| `openai/gpt-5-chat` | N/A | Chat-completions APIs do not expose token-level log probabilities; eval also remains incomplete due to rate limits. |

## Internal diagnostics — local checkpoints only

| Diagnostic | Stage 0 base | Stage 1 checkpoint-10140 | Change |
|---|---:|---:|---:|
| Hawaiian PPL | 7.9152 | 3.6229 | -54.2% |
| English PPL | not_configured | not_configured | N/A |
| manual_w1 | draft_only | draft_only | not reportable |

Interpretation: Stage 1 sharply improves held-out Hawaiian PPL on the local diagnostic, while `human_fetch` translation moves asymmetrically: EN→HAW improves over Stage 0, HAW→EN drops below Stage 0 on this one-pair probe. Orthography tripwires remain clean for Stage 1.

## GPT-5-chat retry outcome

`MODELS="openai/gpt-5-chat" ./scripts/run_frontier_eval.sh` was retried at 2026-05-04T08:09:11Z using the GPT-5 harness fix from commit `7c8bf8f`. The run still hit GitHub Models API rate limits before a complete JSON report could be emitted. GPT-5-chat remains pending in the comparison until a complete artifact exists.

## Artifacts

- **Stage 0 Summary:** `docs/eval-runs/stage0/20260430T094425Z__stage0_base_eval_summary.json`
- **Stage 1 Full JSON:** `data/eval_runs/stage1/20260504T080245Z__stage1_checkpoint-10140_eval.json`
- **Frontier Summary:** `docs/eval-runs/frontier/20260504T073812Z__frontier_github-models_openai_gpt-4o_eval_summary.json`
- **Frontier Full JSON:** `data/eval_runs/frontier/20260504T073812Z__frontier_github-models_openai_gpt-4o_eval.json` (gitignored)
- **GPT-5 Blocker:** `docs/eval-runs/frontier/BLOCKERS.md`
