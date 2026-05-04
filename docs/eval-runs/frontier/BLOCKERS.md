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

**Retry attempts:** 
- Retry #1 @ 2026-05-04T07:59:05Z (initial attempt after prior spawn's rate limit)
- Retry #2 @ 2026-05-04T08:01:15Z (60s cooldown, still rate-limited)
- Retry #3 @ 2026-05-04T08:09:11Z (cooldown elapsed; still rate-limited during `human_fetch` probe before a complete JSON artifact could be emitted)

**Cooldown window:** Rate limits persist beyond the latest retry. Likely requires extended reset period (estimated 24h or next billing cycle).

### Azure OpenAI Bypass — ✅ Wired

The frontier harness now supports `FRONTIER_PROVIDER=azure`, using Azure OpenAI deployment names as the `model` argument. This bypasses the GitHub Models rate-limit path for GPT-5-chat while preserving the same Stage 0/1 eval contract and GitHub Models behavior.

```bash
FRONTIER_PROVIDER=azure ./scripts/run_frontier_eval.sh
```

Required Azure env vars can be supplied by the shell or gitignored `data/.env`: `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_GPT5_DEPLOYMENT` (or `AZURE_OPENAI_DEPLOYMENT`), and `AZURE_OPENAI_API_VERSION`.

### Retry Plan

1. Prefer Azure: `FRONTIER_PROVIDER=azure ./scripts/run_frontier_eval.sh`
2. If using GitHub Models, wait for rate limit reset (likely 24h or next billing period)
3. Re-run GitHub Models: `MODELS="openai/gpt-5-chat" ./scripts/run_frontier_eval.sh`
4. Update comparison table with GPT-5-chat column
5. Append ledger row to `data/evals/eval_hashes.jsonl`

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
| `openai/gpt-5-chat` | ✅ | ❌ via GitHub Models; Azure path wired | GitHub Models rate limits; use `FRONTIER_PROVIDER=azure` |
| `openai/gpt-5` | ❌ | ❌ | 500 error (API unstable) |
| `claude-opus-4.7` | ❌ | ❌ | Not in catalog |

**Next action:** Run GPT-5-chat through Azure OpenAI with `FRONTIER_PROVIDER=azure`; GitHub Models retry can wait for rate-limit reset.
