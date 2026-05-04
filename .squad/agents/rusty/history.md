# Rusty — History

## Core Context

Condensed older entries; newest detailed entries remain below.

- **2026-05-04T07:03:09Z — Stage 1 checkpoint-10100 eval blocked before inference:** Read `decisions.md` and prior Rusty eval history first. Corrected the Stage 1 eval targ...
- **2026-05-04T07:02:00Z — Stage 1 checkpoint-10140 eval blocked before inference:** Read `decisions.md` and the prior eval history before touching the Stage 1 request. Con...

---

## 2026-05-04T08:13:26Z — Frontier PPL policy and Stage 1 checkpoint-10140 row

Rusty sync spawns clarified chart policy and updated the frontier comparison artifact. Frontier PPL is not 1:1 with local checkpoint PPL because closed chat-completions APIs do not expose token logprobs; frontier charts should mark PPL `N/A` / `not_supported` or omit it, while local Stage 0/1 PPL remains diagnostics-only.

Added Stage 1 `checkpoint-10140` to `docs/eval-runs/frontier/20260504T074014Z__s0_vs_frontier_comparison.md` from `data/eval_runs/stage1/20260504T080245Z__stage1_checkpoint-10140_eval.json`: EN→HAW F1 `0.443894`, HAW→EN F1 `0.346667`, wrong ʻokina `0`, kahakō `53`, NFC failures `0`, tripwires pass. Local PPL diagnostic is Stage 0 `7.9152` → Stage 1 `3.6229` (`-54.2%`). GPT-5-chat retry remains rate-limited; no GPT-5 metrics fabricated.

---

## 2026-05-04T08:01:00Z — GPT-5-chat eval blocked by persistent rate limits

**Task:** Run full frontier eval against `openai/gpt-5-chat` on frozen stage0.v1 prompt suite; update comparison artifact with GPT-5-chat column alongside Stage 0 and gpt-4o results.

**Status:** ❌ Blocked by GitHub Models API rate limits (2 retry attempts, 60s+ cooldown insufficient).

Confirmed harness fix is committed and pushed (commit 7c8bf8f). Attempted full eval run twice:
1. Initial attempt @ 2026-05-04T07:59:05Z — rate-limited on first API call
2. Retry after 60s @ 2026-05-04T08:01:15Z — rate limit persists

Error: `RateLimitError: Too many requests. For more on scraping GitHub and how it may affect your rights, please review our Terms of Service (https://docs.github.com/en/site-policy/github-terms/github-terms-of-service).`

**Rate limit window:** Extends beyond 60s; likely requires 24h reset or next billing period. Cannot complete evaluation without API access.

**Blocker documented:** Updated `docs/eval-runs/frontier/BLOCKERS.md` with retry timestamps and cooldown analysis. Did NOT fabricate metrics. Did NOT append to `eval_hashes.jsonl` or update comparison table without real eval results.

**Stage 1 checkpoint note:** Task mentioned Stage 1 checkpoint-10140 with PPL 7.9152 → 3.6229 (-54.2% improvement). However, per history (2026-05-04T07:03:09Z), the correct checkpoint is **checkpoint-10100**, and no local eval artifact exists yet — inference is blocked pending GPU access. The PPL numbers mentioned in task appear to reference a planned/expected result, not a completed eval. Did NOT add Stage 1 data to comparison table without verified eval artifact.

**Artifacts:**
- ✅ Harness fix committed/pushed (7c8bf8f)
- ✅ BLOCKERS.md updated with retry attempts
- ❌ GPT-5-chat eval incomplete (rate-limited)
- ❌ eval_hashes.jsonl update deferred
- ❌ Comparison table update deferred

**Next steps:** 
1. Wait for rate limit reset (24h window expected)
2. Re-run `MODELS="openai/gpt-5-chat" ./scripts/run_frontier_eval.sh`
3. Update comparison table with GPT-5-chat results (en→haw F1, haw→en F1, wrong-ʻokina, kahakō totals, determinism caveat)
4. Append eval_hashes.jsonl with `stage: "frontier_baseline"`, `model: "openai/gpt-5-chat"`

**Learnings — Rate limit behavior:**
- GitHub Models API enforces strict per-user rate limits
- Single-prompt smoke tests succeed, but batch evals (7+ prompts) trigger limits
- 60s cooldown insufficient for rate limit reset
- Rate window likely resets on 24h cycle or billing period boundary
- Cannot parallelize or batch requests to work around limit

---

## 2026-05-04T07:52:00Z — GPT-5 param shape & determinism harness update

Fixed `code/llm_hawaii/eval_frontier.py` to handle GPT-5 family parameter requirements: (1) GPT-5/o-series reject `temperature=0`, use default sampling; (2) require `max_completion_tokens` instead of `max_tokens`. Implemented model-family detection via `_is_reasoning_model()` — routes GPT-5/o1/o3/o4 to reasoning-tier param shape (no temperature/top_p, max_completion_tokens), routes gpt-4o and others to legacy shape (temperature=0, max_tokens). Added determinism tracking: identity includes `determinism: "non_deterministic"` for reasoning models vs `"deterministic_temp_0"` for greedy models; decoding section surfaces non-repeatability caveat.

Smoke test passed for `openai/gpt-5-chat` (200 OK, valid response). Base `openai/gpt-5` still returns 500 Internal Server Error despite correct param shape. Full eval blocked by GitHub Models API rate limits: `RateLimitError: Too many requests` on first prompt generation (7-prompt suite + 2 translation probes = 9 API calls). 60s cooldown insufficient; rate limit persists across retries. Cannot complete GPT-5-chat eval summary or comparison table until rate limits reset (likely 24h or next billing period).

Added 7 new unit tests to `code/tests/test_eval_frontier.py` covering param-shape detection, decoding kwargs, and determinism fields. All 16/16 tests pass. Decision drop-box at `.squad/decisions/inbox/rusty-gpt5-param-shape.md` documents model family quirks, rate limit blocker, and retry plan. No fabricated metrics; honest blocker surfaced.

**Learnings — GPT-5 family quirks:**
- GPT-5 family rejects `temperature=0`; only supports default sampling (non-deterministic outputs).
- Requires `max_completion_tokens` instead of `max_tokens`.
- Model ID variants matter: `openai/gpt-5` unstable (500 errors), `openai/gpt-5-chat` stable (200 OK).
- o-series models (o1/o3/o4) share same param shape as GPT-5.
- Cannot anchor GPT-5 as frozen baseline — outputs drift across runs due to sampling variance.
- GitHub Models rate limits stricter for batch evals (7+ prompts) than single-prompt tests.

**Retry plan:** Wait for rate limit reset, re-run `MODELS="openai/gpt-5-chat" ./scripts/run_frontier_eval.sh`, update comparison table, append eval_hashes.jsonl with `stage: "frontier_baseline"`, model: `openai/gpt-5-chat`, caveat non-determinism in docs.

---
