# Danny — History

## Core Context

- **Project:** A plan for training an open-source LLM focused on the Hawaiian language, including data, model choices, infrastructure, evaluation, and costs.
- **Role:** Lead
- **Joined:** 2026-04-29T01:38:35.140Z

## Learnings

### README Update (2026-04-29)
- Rewrote README as honest planning artifact: fixed "llc" → "LLM", explained we have no code/data yet.
- Organized into Goal, Approach, Data/Provenance, Model/Training, Evaluation, Budget, and Roadmap sections.
- Captured team recommendations (Rusty on tokenization, Basher on training, Livingston on costs, Linus on data licensing) without overstating implementation status.
- Key trade-off: adapt vs. train from scratch → adapt wins for low-resource language with ~$10k–$30k budget.
- Emphasized data quality and eval rigor as bottleneck, not GPU cost.

### README Restoration (2026-04-29)
- README.md had reverted to the two-line stub ("# ideal-spoon" / "training an llc on Hawaiian language").
- Restored it from the accepted ADR "Hawaiian LLM Planning Repository README" in `.squad/decisions.md`, preserving all team recommendations (Rusty tokenization/diacritics, Basher QLoRA-first, Linus provenance, Livingston $10k–$30k tier with vendor tradeoffs).
- No new team-level decision; this was a pure restoration of the existing ADR, so no inbox entry created.

### README Re-Restoration (2026-04-29)
- README.md had reverted again to the two-line stub. Root cause: the previous restoration was never committed — it lived only in the working tree, and a later Scribe cleanup that reset accidental log-only commits also wiped the uncommitted README changes back to HEAD.
- Re-restored README.md from the accepted ADR in `.squad/decisions.md`, again preserving Rusty (orthography/tokenization, diacritics), Basher (QLoRA-first), Linus (provenance/licensing), and Livingston ($10k–$30k practical tier with vendor tradeoffs) recommendations, and keeping the planning-artifact framing (no datasets, no training code, no weights, no benchmarks claimed).
- This run **commits README.md** (alongside this history update) so the restoration is persistent and cannot be wiped by future cleanup/reset operations. No new team-level decision; the ADR is unchanged, so no inbox entry created.
