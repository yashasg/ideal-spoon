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
