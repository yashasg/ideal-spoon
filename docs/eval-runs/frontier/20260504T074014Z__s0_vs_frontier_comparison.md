# Frontier Baseline vs Stage 0 Comparison

**Run ID:** 20260504T074014Z  
**Suite:** stage0.v1 (frozen)  
**Date:** 2026-05-04T07:40:14.529165Z

## Model Configuration

| Model | Provider | Endpoint | Supports Greedy |
|-------|----------|----------|----------------|
| **openai/gpt-4o** | github-models | https://models.github.ai/inference/chat/completions | ✅ Yes (temp=0) |
| meta-llama/Llama-3.1-8B | local | N/A | ✅ Yes |

## Key Findings

### ✅ **Translation Quality: Significant Gains**

| Direction | Stage 0 (Llama-3.1-8B) | openai/gpt-4o | Delta |
|-----------|------------------------|---------------|-------|
| **EN → HAW** | 0.329114 | 0.398827 | **+21.2%** |
| **HAW → EN** | 0.469799 | 0.617021 | **+31.3%** |

Metric: char_ngram_f1 (2-gram, baseline)

### ✅ **Orthography: Comparable Performance**

| Metric | Stage 0 | openai/gpt-4o | Delta |
|--------|---------|---------------|-------|
| **Wrong ʻokina** | 0 | 0 | 0 (perfect) |
| **Kahakō total** | 34 | 32 | -2 |
| **NFC failures** | 0 | 0 | 0 (perfect) |

Both models maintain proper Hawaiian orthography with correct ʻokina usage.

### ⚠️ **Perplexity: Not Comparable**

| Metric | Stage 0 | openai/gpt-4o | Status |
|--------|---------|---------------|--------|
| **Hawaiian PPL** | 7.9152 | N/A | `not_supported` (no logprobs) |

Closed-API models (GPT-4o) do not expose token-level probabilities, so perplexity is not measurable.

## W1 Manual Micro-Eval

Both runs report W1 as `draft_only` — no accepted rows for task-accuracy benchmarking.

## Prompt Suite Integrity

- **Suite ID:** stage0.v1  
- **Suite SHA256:** 2683027f538ae8fb2910f758f2865596355893cc91c85dbdfe9ced130797bce6  
- **Verification:** ✅ Identical across runs

## Artifacts

- **Stage 0 Summary:** `docs/eval-runs/stage0/20260430T094425Z__stage0_base_eval_summary.json`  
- **Frontier Summary:** `docs/eval-runs/frontier/20260504T073812Z__frontier_github-models_openai_gpt-4o_eval_summary.json`  
- **Full JSON:** `data/eval_runs/frontier/20260504T073812Z__frontier_github-models_openai_gpt-4o_eval.json` (gitignored)

## Top-Line Takeaway

**openai/gpt-4o** demonstrates **+21% improvement in EN→HAW** and **+31% in HAW→EN translation** over the Stage 0 Llama-3.1-8B baseline, while maintaining perfect Hawaiian orthography (zero wrong ʻokina, proper kahakō).

Perplexity comparison not available due to API limitations, but translation quality is significantly higher.

---

## Blockers for Originally Requested Models

### ❌ GPT-5 Family (`openai/gpt-5`, `openai/gpt-5-chat`)

- **Status:** 500 Internal Server Error during smoke test  
- **Issue:** GitHub Models API returned server error; model may not be fully operational  
- **Parameter Constraints:** Does NOT support `temperature=0` (only default temperature=1), requires `max_completion_tokens` instead of `max_tokens`  
- **Requested:** gpt-5.5 (not in catalog; closest is `openai/gpt-5`)  
- **Substitution:** Used `openai/gpt-4o` as working baseline

### ❌ Claude Opus 4.x Family

- **Status:** Not in GitHub Models catalog  
- **Searched:** `anthropic/claude-opus-4`, `anthropic/*`, any `claude` models  
- **Result:** Zero Anthropic models found in https://models.github.ai/catalog/models  
- **Requested:** claude-opus-4.7  
- **Substitution:** None available; GPT-4o used as sole premium baseline

### Catalog Verified Models

Available in catalog but not tested due to GPT-5 issues:
- `openai/o3` (empty response during test)
- `openai/o4-mini` (empty response during test)
- `openai/gpt-5-mini`
- `openai/gpt-5-nano`

## Recommendations

1. **Baseline Established:** `openai/gpt-4o` provides a strong frontier comparison point
2. **GPT-5 Retry:** Monitor GitHub Models status page for GPT-5 availability
3. **Claude Alternative:** Request Anthropic models be added to GitHub Models catalog, or use direct Anthropic API
4. **O-series Models:** Investigate o3/o4-mini empty response issue (may require different parameter handling)
