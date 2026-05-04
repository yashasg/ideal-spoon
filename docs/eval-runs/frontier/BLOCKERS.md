# Frontier Eval Blockers

## GPT-5-chat — Rate Limits

**Date:** 2026-05-04T07:52:00Z  
**Model:** `openai/gpt-5-chat`  
**Status:** ⚠️ Blocked by GitHub Models API rate limits

### Smoke Test — ✅ Passed

Single-prompt test succeeded:

```bash
curl -H "Authorization: Bearer $(gh auth token)" \
     -H "Content-Type: application/json" \
     https://models.github.ai/inference/chat/completions \
     -d '{"model":"openai/gpt-5-chat","messages":[{"role":"user","content":"Aloha"}],"max_completion_tokens":16}'

# Response: 200 OK
# {"choices":[{"finish_reason":"length","message":{"content":"Aloha! 🌺 How are you doing today?  \n\nAre you just greeting"}}]}
```

### Full Eval — ❌ Rate Limited

Full eval (7 prompts + 2 translation probes = 9 API calls) blocked on first generation:

```
RateLimitError: Too many requests. For more on scraping GitHub and how it may 
affect your rights, please review our Terms of Service 
(https://docs.github.com/en/site-policy/github-terms/github-terms-of-service).
```

**Retry attempts:** 2 (60s cooldown insufficient)

### Retry Plan

1. Wait for rate limit reset (likely 24h or next billing period)
2. Re-run: `MODELS="openai/gpt-5-chat" ./scripts/run_frontier_eval.sh`
3. Update comparison table with GPT-5-chat column
4. Append ledger row to `data/evals/eval_hashes.jsonl`

### Harness Status

✅ **Fixed** — harness correctly handles GPT-5 parameter shape:
- Detects reasoning models (`gpt-5`, `o1`, `o3`, `o4`)
- Uses `max_completion_tokens` instead of `max_tokens`
- Omits `temperature` and `top_p` (not supported)
- Marks outputs as `determinism: "non_deterministic"`

✅ **Tests pass** — 16/16 unit tests green

---

## GPT-5 Base — 500 Internal Server Error

**Date:** 2026-05-04T07:52:00Z  
**Model:** `openai/gpt-5`  
**Status:** ❌ API unstable

Smoke test returns 500 error even with correct param shape:

```bash
curl -H "Authorization: Bearer $(gh auth token)" \
     -H "Content-Type: application/json" \
     https://models.github.ai/inference/chat/completions \
     -d '{"model":"openai/gpt-5","messages":[{"role":"user","content":"Aloha"}],"max_completion_tokens":16}'

# Response: 500 Internal Server Error
# {"error":{"message":"The server had an error while processing your request. Sorry about that!","type":"server_error"}}
```

**Workaround:** Use `openai/gpt-5-chat` (stable) instead of base `openai/gpt-5`.

---

## Anthropic Models — Not in Catalog

**Date:** 2026-05-04T07:52:00Z  
**Status:** ❌ Not available

Requested models not found in GitHub Models catalog:
- `claude-opus-4.7`
- `claude-3.5-sonnet`
- Any `anthropic/*` models

**Catalog search:**
```bash
curl -H "Authorization: Bearer $(gh auth token)" \
     https://models.github.ai/catalog/models | jq -r '.[] | select(.id | contains("claude"))'
# (empty result)
```

**Alternative:** Use direct Anthropic API with `anthropic` Python SDK.

---

## Summary

| Model | Smoke Test | Full Eval | Blocker |
|-------|------------|-----------|---------|
| `openai/gpt-4o` | ✅ | ✅ | None (completed last spawn) |
| `openai/gpt-5-chat` | ✅ | ❌ | Rate limits |
| `openai/gpt-5` | ❌ | ❌ | 500 error (API unstable) |
| `claude-opus-4.7` | ❌ | ❌ | Not in catalog |

**Next action:** Retry `openai/gpt-5-chat` after rate limit reset (24h).
