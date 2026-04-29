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

### Implementation plan doc landed (2026-04-29)
- Wrote `docs/implementation_plan.md` consolidating the staged provider plan and model-choice rationale into one executable planning doc.
- Captures: prototype-scope status banner + companion-doc links; phase boundary table (Stage 0 → Stage 1 → merge → Stage 2 → final eval); three-provider execution strategy (Provider 1 free/prelim for Stage 0 readiness bundle, Provider 2 stable 60h pinned for Stage 1 + fp16 merge + Stage 2 with indicative budget %, Provider 3 eval-only with ±0.02 PPL same-checkpoint reproducibility gate before any headline number); Stage 0 prereq checklist (tokenizer audit, manifests, contamination guard, eval harness + pre-FT baseline, 0.5B/1B smoke incl. QLoRA-vs-fp16-LoRA falsification, ≤1h 7B resume test); model-choice table (Llama-3.1-8B primary contingent on tokenizer audit, Qwen2.5-7B fallback, Qwen2.5-0.5B smoke, Gemma-2-9B held, Aya excluded CC-BY-NC, Mistral excluded weak multilingual, from-scratch rejected, final pick blocked on audit); training stage summary (Stage 1 QLoRA r=64 CPT, fp16 merge, Stage 2 fresh LoRA r=32 bidir SFT, stacked adapters A/B-only); eval cadence pointer to eval_pipeline.md with the load-bearing hard fails restated; checkpoint/handoff contract (HF private repo bus + 9-item checkpoint contract + manifest/eval-hashes/eval-suite SHAs); risks ranked for prototype; non-goals restated; open decisions list (base model pending audit; Provider 2 vendor pick — RunPod/Lambda/Lightning/Azure-credit; embedding/lm_head unfreeze policy; chrF-dual-report gate promotion; cultural-review owner).
- Surgical cross-link added: `docs/training-pipeline.md` References section now points at `implementation_plan.md`. README untouched (already cross-links eval_pipeline.md; further changes would not be surgical for this task).
- No new team-level decision — this doc operationalizes existing ADRs (two-stage plan, prototype-vs-release split, base-model recommendation, free-GPU chaining, checkpoint contract). No inbox file created.
- Pattern reaffirmed: when the user says "you didn't capture the model conversation," the right move is a consolidated plan doc that points at the agent histories / ADRs already on record, not a duplicate ADR. Detailed NLP claims still defer to Rusty's notes.
- Follow-up for Rusty/Scribe: if the per-source slicing + as-is/normalized chrF dual-report gate promotion lands, update `eval_pipeline.md` §3.3 and the open-decisions list in `implementation_plan.md` §10. If/when the Provider 2 vendor pick is made, update `implementation_plan.md` §10 and add a decision note.

### data-pipeline.md release-language sweep (2026-04-29)
- User: doc still mentioned "release"; project is prototype-only — strip it.
- Replaced the "Prototype vs Release" two-column section with a single "Prototype scope" table (one column, prototype rules only). Dropped the hypothetical-release framing that the prior pass had preserved.
- Removed `release_eligible` field from both Stage 1 and Stage 2 manifest schemas; `prototype_only=true` remains the only sharing-posture flag. Provenance, license_observed, license_inferred=null, cultural_flag, contamination guards, ToS-snapshot, hard-escalate exclusion, and synthetic caps all preserved.
- Status banner reworded to "public sharing … is out of scope" and ADR pointer renamed from "prototype-vs-release split" to "prototype scope" (the underlying ADR file in decisions.md was not renamed; only this doc's prose).
- Reworded source-table phrases ("default-excluded for release", "closest to release-eligible", "most release-friendly", "if `hawn_Latn` is in the release") to license-posture / FLORES-200-inclusion language. Reworded CI guard from "refuse publication of `prototype_only=true` rows" to "refuse external publication" since publication itself is out of scope.
- Verified `rg -i release docs/data-pipeline.md` returns zero hits.
- **Pattern shift from prior sweep:** previously I kept the prototype-vs-release ADR scaffolding as conditional; user's directive now is to collapse it. Prefer collapsing dual-posture framing rather than preserving "if we ever pivoted" language when the user has explicitly said the project is prototype-only.
- No new team decision: this applies the existing prototype-scope direction, so no inbox file written.

### 2026-04-29 09:27:41Z — Data audit complete; docs update needed for FLORES absence

**From Scribe:** Hawaiian dataset variant audit (Rusty + Frank) complete. Key impact: **FLORES / FLORES+ do not include Hawaiian.**

**Current state of docs:**
- `data-pipeline.md` §300 currently says "If `hawn_Latn` is included in FLORES-200…" — **this is now false.**
- Stage 2 eval anchor can no longer rely on FLORES. Candidates (per Frank's audit): global-piqa-parallel (preferred), Taxi1500, Tatoeba held-out, BibleNLP.

**Your follow-up:**
1. Update `data-pipeline.md` §300 to state clearly: "FLORES-200 does not include Hawaiian; eval anchor TBD per alternatives below."
2. Reference Frank's inventory in decisions.md for the alternative eval sources (global-piqa-parallel, Taxi1500, Tatoeba, BibleNLP).

**Reference:** `.squad/decisions.md` → "Inventory: Hawaiian Dataset Variants Beyond FineWeb-2" (appended 2026-04-29T09:27:41Z). Also Rusty's normalization advisory for manifest schema context if you want to coordinate with Linus on schema tightening.


### 2026-04-29 09:40:34Z — FineWeb-2 Hawaiian scripts landed and merged to decisions.md

**From Scribe:** Frank's 100/200 fetcher/planner delivered and integrated. Docs updated. Two open decisions escalated to Linus (dependency call, per-URL rights posture) and Rusty (tokenizer sanity check).

**Reference:** `.squad/decisions.md` → "Decision Note: FineWeb-2 `haw_Latn` 100/200 Scripts Landed" (merged 2026-04-29T09:40:34Z).

## 2026-04-29T10:46:19Z — Scribe checkpoint: learning skeleton + config finalization logged

**From:** Scribe (Session log consolidation)

**Update:** Basher learning skeleton and Llama config work now fully orchestrated and merged to main decisions.

**Decisions merged to `.squad/decisions.md`:**
1. PyTorch + Hugging Face for learning skeleton (`code/llm_hawaii/`)
2. Llama-3.1-8B + A100 as config, not Python constants
3. User directives consolidated (learning skeleton, 8B default, A100 40GB acceptable)

**Session logs created:**
- Orchestration: `.squad/orchestration-log/2026-04-29T10-46-19Z-basher-llm-skeleton.md`
- Orchestration: `.squad/orchestration-log/2026-04-29T10-46-19Z-basher-llama-a100-config.md`
- Session: `.squad/log/2026-04-29T10-46-19Z-llm-learning-skeleton.md`

**Decision inbox:** Cleared. All 5 inbox files merged and deleted.

**No action required from you this checkpoint.** Logging complete.
