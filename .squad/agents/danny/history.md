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

### Prototype scope reframe (2026-04-29)
- User directive 2026-04-28T19:55:04 reframed the project as prototype/learning; user will use ulukau.org nūpepa and parallel Bible texts (Baibala Hemolele etc.).
- Drafted ADR `danny-prototype-scope.md` to inbox. Two-stage plan kept; what changes is **gate semantics**, not the recipe.
- Key move: split engineering gates into **prototype gates** (pipeline integrity, contamination guard, manifest discipline, NFC/ʻokina/kahakō hygiene) vs. **release gates** (cultural review by named reviewer, per-source training-rights review, license whitelist with no `unreviewed_prototype` rows, human eval, model card, no prototype-tainted weights in the released chain).
- Manifest schema gains `intended_use ∈ {prototype_private, release_candidate}` and a new `cultural_review` value `unreviewed_prototype`. Loader enforces release-candidate runs reject prototype rows. CI check.
- Important nuance: "publicly available" ≠ "openly licensed." Ulukau provides reading access; copyright posture, archive posture, and cultural posture are three separate things. Pre-1929 nūpepa are PD by copyright but still hit the existing "hard-escalate" cultural-categories list. Baibala Hemolele 1839 is PD; modern Hawaiian Bibles are not; Bible text introduces heavy register skew.
- Recommended (did not perform) a README follow-up: prototype banner, soften the "we will release weights" promise into a conditional, rewrite Data & Provenance to describe the public-source exploration honestly, add a Prototype-vs-Release section pointing at the ADR.
- Open gaps: cultural-review owner still unassigned (now soft-blocker for prototype, hard-blocker for release); archive/community-relations owner unassigned; register-balance reviewer for Bible-heavy mixes implicit in Rusty's scope and should be made explicit.
- Lesson: when a user-stated reality conflicts with an accepted ADR, don't quietly violate the ADR — write a new one that names the boundary. Here the boundary is the word "release."

### README Re-Restoration (2026-04-29)
- README.md had reverted again to the two-line stub. Root cause: the previous restoration was never committed — it lived only in the working tree, and a later Scribe cleanup that reset accidental log-only commits also wiped the uncommitted README changes back to HEAD.
- Re-restored README.md from the accepted ADR in `.squad/decisions.md`, again preserving Rusty (orthography/tokenization, diacritics), Basher (QLoRA-first), Linus (provenance/licensing), and Livingston ($10k–$30k practical tier with vendor tradeoffs) recommendations, and keeping the planning-artifact framing (no datasets, no training code, no weights, no benchmarks claimed).
- This run **commits README.md** (alongside this history update) so the restoration is persistent and cannot be wiped by future cleanup/reset operations. No new team-level decision; the ADR is unchanged, so no inbox entry created.

### Pipeline Docs Polish (2026-04-29T03:21:29Z)
- Removed stale inbox references from `docs/data-pipeline.md`.
- Cross-linked `docs/data-pipeline.md` ↔ `docs/training-pipeline.md`.

### Prototype-scope doc sweep (2026-04-29)
- User clarified project is a prototype/learning effort with no release plan. Updated docs to match.
- **README.md** edits: tagline + banner now say "prototype and learning project, not a release effort"; Goals dropped "Publish weights..." and reframed as design-learning outcomes; Non-Goals strengthened to explicitly exclude shipping models/APIs/datasets; Evaluation no longer references "released weights"; Roadmap Week 7 dropped "prepare a release"; License (intent) section rewritten so code/configs may be MIT/Apache, but weights/adapters/tokenizer/corpora are explicitly *not planned for release*.
- **docs/training-pipeline.md**: top status banner now declares no public release planned; "release-candidate" scope reframed as *hypothetical* if the project ever changed posture. Existing prototype-vs-release ADR machinery left intact as conditional guidance.
- **docs/data-pipeline.md**: status line now says "no public release of weights, tokenizer, dataset, or demo is planned"; "Prototype vs Release" section intro clarifies only the Prototype column is operative.
- Verification: `rg -i '(prepare a release|intent to release|production[- ]ready|public[- ]release|going to release|productioni[sz]e)'` returns only my own clarifying language.
- **Pattern:** when softening a release-claim doc that already has prototype-vs-release ADR scaffolding, prefer adding banners + reframing the "Release" branch as hypothetical over deleting the ADR machinery — preserves useful gate guidance without committing to ship.
- **Key paths:** `README.md`, `docs/training-pipeline.md`, `docs/data-pipeline.md`, ADR in `.squad/decisions.md` ("Prototype-vs-release split").

### Team input integrated (2026-04-29T03:58:26Z)

- **Rusty (NLP Researcher)** confirmed Llama-3.1-8B primary model choice (contingent on tokenizer audit for Hawaiian diacritics); Qwen2.5-7B as fallback; Qwen2.5-0.5B for smoke tests. No new decision; rationale aligned with existing model ADR in decisions.md.
- **Basher (Training Engineer)** confirmed 7B/8B + QLoRA training approach fits prototype budget; free-tier GPU provider chaining acceptable per user directive (prototype-only, learning/iteration scope); tokenizer hashes + checkpoint discipline protect against provider drift. No new decision; aligns with "GPU compute chaining feasibility" ADR.
- **Scribe** merged inbox decisions into decisions.md (3 entries: danny-prototype-scope-docs, copilot-directive on provider-chaining, copilot-directive on prototype documentation). Orchestration logs written. Session log: 2026-04-29T03:58:26Z-prototype-docs-and-model-choice.md.
- All docs staged; ready for commit.
