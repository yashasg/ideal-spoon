# Decisions

## ADR: Hawaiian LLM Planning Repository README

**Date:** 2026-04-29  
**Status:** Accepted  
**Owner:** Danny (Lead)

### Decision

Rewrite README.md as a clear planning artifact that:
1. Corrects the "llc" typo → "LLM"
2. Explicitly states the repo is **planning**, not implementation
3. Captures team recommendations without overclaiming
4. Organizes by functional domain: goals, approach, data, model, eval, budget, roadmap

### Context

The team (Rusty, Basher, Linus, Livingston) provided coherent recommendations on:
- **Tokenization & modeling** (Rusty): preserve Hawaiian diacritics, adapt multilingual base model
- **Training & infrastructure** (Basher): QLoRA on 7B–9B, optimize data/eval before scaling GPUs
- **Licensing & data** (Linus): require per-document provenance, avoid undercurated scrapes
- **Budget & cost** (Livingston): $10k–$30k practical tier with vendor tradeoffs

README needed to reflect this without lying about implementation status: no dataset exists, no code yet, no model weights.

### Trade-offs

| Option | Pros | Cons |
|--------|------|------|
| **Plan artifact (chosen)** | Honest, sets expectations, useful for contributors | Requires discipline to keep planning/implementation separate |
| **Remove all detail** | Safe, minimal claim surface | Loses value; doesn't guide next steps |
| **Pretend code exists** | Looks impressive | Risks credibility when someone clones and finds nothing |

### Implementation

- README sections: Goal → Approach → Data/Provenance → Model/Training → Evaluation → Budget → Roadmap
- Data section explicitly lists sources as *planned*, not acquired
- Model/Training section uses candidate models and conditional language ("try", "if corpus size justifies")
- Budget shows tiered estimates with vendor/tradeoff analysis
- Roadmap is 7-week sketch, not detailed sprint plan

### Implications for Next Work

- **Data team**: use README's Data/Provenance section as spec for corpus assembly
- **Training team**: use Model/Training and Evaluation sections to guide adapter selection and benchmark build
- **All teams**: if README becomes out-of-date, update it; this is a live document, not a static spec

### Alternatives Considered

1. **Keep the stub**: "training an llc on Hawaiian language" — too vague, doesn't help onboard new contributors
2. **Write full implementation spec**: too much detail for a planning artifact; belongs in ADRs + team docs, not README
3. **Link to external wiki**: GitHub wiki is often abandoned; README stays with code

---

## ADR: Default model is `claude-opus-4.7`

**Date:** 2026-04-29
**Status:** Accepted
**Owner:** yashasg (via Coordinator)

### Decision

Every Squad agent uses `claude-opus-4.7` as the default model. Persisted in `.squad/config.json` as `defaultModel`.

### Context

User directed that `claude-opus-4.7` be the team default and explicitly confirmed it is a valid model, overriding any stale internal model lists.

### Implementation

- `.squad/config.json` holds `{"defaultModel": "claude-opus-4.7"}`.
- Coordinator reads this file when spawning agents and passes the value as the model parameter unless the spawn explicitly overrides.
- Charters declaring `Preferred: auto` resolve to this default.

### Implications

- Agents previously using mixed models (haiku/sonnet/opus) now uniformly run on `claude-opus-4.7` unless a task-specific override is justified.
- If the user changes the default later, update `.squad/config.json` and append a new ADR; do not silently rewrite this one.

---

## Decision Note: Azure leftover credit ($50–$60/mo) is experiment budget, not training budget

**Date:** 2026-04-29
**Status:** Proposed — team awareness
**Owner:** Livingston (Cost Strategist)

### Decision

Treat the ~$50–$60 of monthly leftover Azure employee credit as a **plan-validation / scratchpad** budget. It does not change the README's $10k–$30k practical training tier.

### Good uses (per Azure list-price ballparks)

- Tokenizer audits at scale on a CPU VM.
- 1–4 hr QLoRA smoke tests on T4 / V100 spot to validate the pipeline.
- Inference / baseline scoring of candidate models on the early eval set.
- Cheap Blob storage for provenance manifests and small corpus snapshots.

### Avoid

- Long training runs, H100 / ND-series / 8-GPU SKUs, always-on VMs, premium SSDs, public inference endpoints.

### Mandatory guardrails

1. Cost Management budget alerts at $30 / $50 / $60.
2. Auto-shutdown on every VM (default 1 hr after creation if untouched).
3. Spot VMs for any GPU work.
4. One resource group per experiment; tear down at end.
5. Tag everything `project=hawaiian-llm`.

### Local RTX 2080 (8GB) division of labor

- Owns: data work, Unicode/NFC pipeline, tokenizer experiments, manifest building, 4-bit 7B inference (slow but viable), LoRA on 1B–3B.
- Doesn't own: full-precision 7B fine-tunes, multi-GPU, real training-scale batch sizes.

### Microsoft-employee caveat

Internal policy is the user's responsibility to confirm: credit-usage terms, RAI / data policy, IP / OSS release posture, cultural-data review, tenant separation. No claim made about what the policy says.

### Implication

When the project is ready for a real training run, dedicated budget is required (Azure spot, Lambda, RunPod bake-off). Leftover credit is for de-risking the plan only.

---

## Decision Note: Training-work fit in $50–$60 Azure credits

**Date:** 2026-04-29
**Status:** Proposed (advisory)
**Owner:** Basher (Training Engineer)

### Decision

Within the leftover Azure credit, scope to **one focused 7B QLoRA run** on A100 40GB / L4 / A10, plus optionally a partial retry. All other ML work runs locally on the RTX 2080.

### Local on RTX 2080 (no credits)

- Tokenizer audits, data pipeline, NFC normalization, eval harness scaffolding.
- Baseline generation from 1B–3B models in 4-bit.
- QLoRA smoke tests on 1B–3B at short seq len to validate the recipe.
- (2080 Ti only) 7B QLoRA at seq 512, bs 1 + grad-accum is *technically* possible — debug only, not deliverable.

### Azure spend (high value per dollar)

1. Single 7B QLoRA training run on a single A100 40GB / L4 / A10.
2. Maybe one repeat run with a tweaked data mix or LoRA rank.

Don't spend credits on data prep, eval harness dev, tokenizer audits, baseline inference.

### Budget reality

- $50–$60 buys low-double-digit hours of A100 80GB on-demand, or meaningfully more on A100 40GB / L4 / A10.
- One real run + maybe a partial retry. **Not** enough for the README's iterative Weeks 5–6 unless credits accumulate across months or vendors switch (RunPod / Lambda often cheaper for this exact workload).

### Runtime guidance

- Pick one SKU and stick with it (default A100 40GB or L4, single GPU).
- Plan one training run of ~6–10 wall-clock hours; lock corpus + config before the GPU spins up.
- Hard-cap each VM session at ~12 hours; auto-shutdown mandatory.
- Reserve ~25–30% of credits as contingency for one re-run.

### Practical guardrails

Auto-shutdown, spot/low-priority for non-final runs, full local pre-stage, `tmux`/`screen` + disk logging, checkpoint to Blob every N steps, budget alerts at 50%/80%, no premium SSDs, log GPU utilization (<70% sustained = dataloader fix locally before redeploy).

### Open questions for the user

1. RTX 2080 (8GB) or 2080 Ti (11GB)? Changes local 7B feasibility.
2. Are the $150/mo credits a recurring monthly grant? If so, plan across 2–3 months unlocks an iteration loop.
3. Deadline pressure for a single-run attempt vs paced multi-month?

---

## Decision Note: Base-model recommendation for Hawaiian adaptation

**Date:** 2026-04-29
**Status:** Proposed (gated on tokenizer audit)
**Owner:** Rusty (NLP Researcher)

### Decision

Two-tier base-model plan:

1. **Smoke-test slot**: `Qwen2.5-0.5B` (Apache-2.0) primary, `Gemma-3-270M` alternate. Validates the data → tokenizer-audit → QLoRA → eval pipeline end-to-end on RTX 2080 + Kaggle before any cloud spend.
2. **Main 7B-class slot**: `Llama-3.1-8B` primary (best Polynesian-adjacent pretraining signal), `Qwen2.5-7B` fallback (cleanest license: Apache-2.0). Final pick is **gated on a Hawaiian tokenizer audit** (ʻokina U+02BB + kahakō, Unicode pinned to NFC).
3. **Held as third option**: `Gemma-2-9B` (license flow-down + no-competing-foundation-models clauses).
4. **Avoid as released base**: `Aya-23` / `Aya-Expanse` (CC-BY-NC contaminates the "openly licensed" release goal — usable only as private reference / silver-data generator). `Mistral-7B` has clean Apache-2.0 but weak multilingual / no Polynesian signal.

### Tokenizer audit (the gate, not vibes)

1. Assemble ~10k tokens of representative Hawaiian text covering ʻokina, kahakō vowels, code-switching with English, proper nouns.
2. Pin Unicode to NFC; record the policy.
3. For each candidate, measure tokens-per-word, byte-fallback rate, ʻokina survival, kahakō unitarity.
4. Pick the model with the lowest fragmentation. Tie-break on license (prefer Apache-2.0).

### Free-compute sequencing

Local RTX 2080 + Kaggle (P100 / 2×T4, 30 GPU-h/wk) for iteration; Lightning AI as small backup; reserve Azure credits for the **single main QLoRA run** on the chosen 7B–9B base + eval (~10–20 hr A100 / A10 / L4).

### License caveats flagged for Linus

- Llama 3.1 Community License: open weights, commercial use OK *unless* >700M MAU; "Built with Llama" attribution + naming requirement; AUP applies.
- Gemma terms: no-competing-foundation-models clause, mandatory flow-down, Google's right to unilaterally modify/terminate.
- Qwen2.5 Apache-2.0 is cleanest for "publish weights and tokenizer under permissive terms."
- License analysis is a research summary, not legal advice.

### Implications

- README's Tokenization & Orthography section already calls for this audit — Rusty's recommendation makes it a hard gate before main-run model selection.
- Final main-run model selection waits on audit results.

