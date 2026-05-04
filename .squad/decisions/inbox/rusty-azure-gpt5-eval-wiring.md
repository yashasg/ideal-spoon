# Decision: Azure OpenAI wiring for GPT-5 frontier eval

Date: 2026-05-04T08:26:58Z
Owner: Rusty (NLP Researcher)

## Context

GitHub Models single-prompt GPT-5-chat smoke worked, but full frontier eval repeatedly hit provider rate limits before a complete artifact could be emitted.

## Decision

Add an Azure OpenAI provider path to `code/llm_hawaii/eval_frontier.py` and `scripts/run_frontier_eval.sh`, selected with `FRONTIER_PROVIDER=azure`. Azure uses the deployment name as the `model_id` / Azure client model argument. The runner loads only whitelisted frontier env keys from gitignored `data/.env` when present and redacts secret-bearing values in dry-run output.

Supported Azure env vars:
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_GPT5_DEPLOYMENT` or `AZURE_OPENAI_DEPLOYMENT`
- `AZURE_OPENAI_API_VERSION`

## Consequences

GitHub Models behavior remains the default. GPT-5 frontier eval can bypass GitHub Models rate limits on the compute machine by running Azure with the same frozen Stage 0/1 contract and summary/ledger flow.
