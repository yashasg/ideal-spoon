---
name: "eval-probe-safe-to-miss"
description: "Pattern for writing checkpoint eval probes that degrade gracefully when their local data source is absent, without blocking the eval run or silently swallowing the missing probe."
domain: "evaluation, data-engineering"
confidence: "high"
source: "earned — implemented in human_fetch translation probe (evaluate.py)"
---

## Context

Checkpoint evals in this project run against local off-git data sources. Some
probes (e.g. the human_fetch translation probe) are not critical enough to block
the entire eval if their JSONL is missing, but their absence should be explicitly
surfaced so it doesn't silently vanish from cross-checkpoint diffs.

## Patterns

### Status enum contract
Every probe function returns a dict with a stable `status` key from a fixed enum:
- `not_configured` — explicitly disabled by caller (`enabled=False`)
- `missing` — local file not found (eval continues, no exit-code flip)
- `invalid` — file present but unreadable/malformed
- `ready` — data loaded but no model yet (metadata only)
- `evaluated` — generation run and scored

### Early-return on missing
```python
if not p.exists():
    out["status"] = "missing"
    out["reason"] = f"not found at {p}; regenerate with ..."
    return out  # never raise, never crash
```

### Hash-only report shape
Never include raw source text, reference text, or generation text in the
returned dict. Only sha256 hashes and numeric metrics. This allows the report
to be committed to git (tracked summary) without leaking corpus text.

```python
out["pair_sha256"] = {"en": _sha256_text(en_text), "haw": _sha256_text(haw_text)}
# NOT: out["en_text"] = en_text
```

### Stable top-level key in evaluate_checkpoint
Always assign the probe result to a fixed key on `report`, even when disabled:
```python
report["human_fetch_translation"] = human_fetch_translation_probe(
    human_fetch_jsonl, enabled=use_human_fetch, model=model, ...
)
```
This ensures the cross-checkpoint aggregator always sees the same key structure
and never has to handle a missing key separately from a `not_configured` status.

### Policy fields on every output
```python
out["eval_eligible"] = True
out["training_eligible"] = False
```
These are redundant with the JSONL source policy but explicit in the report so
the aggregator can assert training safety without re-reading the source.

## Examples

- `code/llm_hawaii/evaluate.py` — `human_fetch_translation_probe()` (full impl)
- `code/llm_hawaii/evaluate.py` — `manual_w1_status()` (same pattern for W1)

## Anti-Patterns

- **Raising on missing file** — use `status="missing"` and return early instead.
- **Omitting the key when disabled** — always emit `status="not_configured"`, never drop the key.
- **Including raw text in the report** — use sha256 hashes only.
- **Averaging bi-directional metrics** — en→haw and haw→en must always be separate keys.
