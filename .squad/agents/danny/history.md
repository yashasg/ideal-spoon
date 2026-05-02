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

### Stage 2 integration pass (2026-04-29)

- Reviewed the Stage 2 batch (Frank fetch plan, Linus #11/#13 manifest builder + checks, Rusty #12 quality scorer + ADR, Basher #14 SFT emitter). All five Python files compile; 321 self-test passes; 320 `--dry-run`/`--execute` produces an empty manifest cleanly; 330 reads it without error.
- One real **contract mismatch**: Linus' `MANIFEST_FIELDS` declared `text_ref_en` / `text_ref_haw`, but Basher's emitter and `docs/training-pipeline.md` §4.3.1 use `text_en_path` / `text_haw_path`. Surgical rename in `scripts/320_build_stage2_manifest.py` (schema entries + the `text_*_or_ref_required` dependent-field rule) so the builder, emitter, and doc all agree on `text_{en,haw}_path`. No effect on existing rows (no real adapters wired yet).
- The five policy fields (`alignment_confidence_tier`, `alignment_score_components`, `quality_flags`, `manual_review_reasons`, `policy_version`) emitted by `code/llm_hawaii/stage2_quality.py` are not declared in `MANIFEST_FIELDS`, but `validate_row` silently allows extras and `docs/data-pipeline.md` line 433 + `docs/stage2-alignment-quality.md` §7 explicitly document them as schema *additions*. Pass-through is the documented contract; left as-is.
- Pre-existing tension (not introduced by this batch, not fixed here): `docs/data-pipeline.md` schema table no longer carries `release_eligible`, but `scripts/301_build_stage1_dataset.py` and `scripts/320_build_stage2_manifest.py` both still require it (mirroring Stage 1). Out of scope for a surgical pass; flag for the next docs/schema sweep.
- JW300: confirmed excluded — `data-sources/stage2-parallel-fetch-plan.json` carries it under `deferred_or_excluded.jw300_haw` with explicit "do not fetch" guidance, and `docs/data-pipeline.md` §"Stage 2 source tiers"/§Tier E lists it as `excluded_pending_verification`.
- Issue #4 (training-loader contamination guard) intentionally untouched — owned by squad:yashas; both 320 and 330 have explicit "out of scope" comments to that effect.
- Tracked-data sweep clean: no files under `data/` are git-tracked (`/data/` is gitignored); only docs, scripts, code, and the `data-sources/` fetch plan JSON are in-repo. Created `data/stage2/` during smoke-test, then removed it.
- No new team-level ADR — this is a field-name alignment to an existing documented contract, so no `decisions/inbox/` entry written.


### Issue closure review (#2/#3/#5–#14) (2026-04-29T13:15:04Z)
- Reviewed local uncommitted work against issue acceptance criteria without code changes. Prototype-ready closure is artifact/contract readiness, not permission for public release or GPU spend.
- Recommended READY_TO_CLOSE for #2, #3, #5, #6, #10, #12, #13, #14; BLOCKED_HUMAN_REVIEW for #7 and #8; NEEDS_FOLLOWUP for #11 and #9.
- Key blocker: Stage-2 scripts use JSONL-first `stage2_manifest.jsonl`, while `docs/data-pipeline.md` still has stale `stage2_manifest.parquet` / `stage2.jsonl.gz` references and `release_eligible` schema tension. Linus should reconcile before #11 and the #9 epic close.

### Docs consistency pass (2026-04-29)
- Updated docs to align on private-prototype posture: no public weights/adapters/tokenizer/datasets/generations/eval scores/API/demo; generated artifacts remain under ignored `data/`.
- Architecture framing to remember: JSONL is canonical for Stage 1/2 manifests and eval-hash ledger; Parquet is derived-only. Provider 2 is one paid stable GPU block for Stage 1 + merge + Stage 2; T4/P100 are smoke-only.
- Open blockers remain explicit: #7 W1 Hawaiian-literate review, #8 real gated Llama tokenizer audit, and human-owned #4 runtime loader contamination guard.

### Cross-doc consistency pass (2026-04-29T19:54:48Z)
- Completed final round-trip validation with Linus on data-doc accuracy. Updated all five docs (`implementation_plan.md`, `training-pipeline.md`, `eval_pipeline.md`, `data-pipeline.md`, `stage2-alignment-quality.md`) for private-prototype posture consistency.
- Verified no public-release promises; JSONL canonical / Parquet derived-only framing locked; FineWeb/W1/Stage-2 scaffold status confirmed on track per Frank/Linus/Rusty audits.
- Schema contracts validated across builder (320) → emitter (330) → docs; policy fields reconciled; JW300 confirmed deferred/excluded; #4 runtime guard confirmed human-owned (squad:yashas).
- Validation: py_compile + dry-run + rg sweep + git diff all clean. Decision inbox empty; all changes apply existing ADRs.
- Orchestration logs: `.squad/orchestration-log/2026-04-29T19-54-48Z-danny-docs-pass.md` + `.squad/orchestration-log/2026-04-29T19-54-48Z-linus-docs-pass.md`. Session log: `.squad/log/2026-04-29T19-54-48Z-docs-pass.md`.
- Status: ✓ Ready for merge. No commits done; user requested docs pass, not commit.

### Prototype-journey-deck documentation (2026-04-29)

**User request:** "Can you document my journey in building this, I want to make a PowerPoint of all decisions I had to make etc."

**Deliverable:** Created `docs/prototype-journey-deck.md` — a PowerPoint-ready markdown artifact structured as slide-by-slide outline with speaker notes.

**Content includes:**
1. **Slide deck outline (15 slides):** Title → Project context → 11 core decisions → What's done/remains/learned → Appendix
2. **Decision documentation format:** For each decision:
   - Headline decision (what you chose)
   - Options considered (alternatives with pros/cons)
   - Key trade-off named
   - Speaker notes with rationale
3. **11 major decision arcs covered:**
   - Train from scratch vs. adapt
   - Data source strategy (Hawaiian-language ethics)
   - FineWeb-2 as Stage 1 primary
   - Two-stage training (CPT → merge → SFT)
   - Eval contamination ledger (JSONL canonical)
   - Manual Hawaiian-literate review for W1 eval
   - Tokenizer audit as spend gate
   - Three-provider GPU strategy
   - Provider API abstraction
   - Human-owned runtime contamination guard (#4)
   - Stage 2 parallel-data skeleton
4. **Compact decision matrix table:** All decisions side-by-side with options/choice/trade-off
5. **Timeline at a glance:** 7-week sketch with blockers called out
6. **Appendix:** Core artifacts, scripts, data directories, config structure — cross-referenceable for slides
7. **Tone:** Honest learning-project framing (no release, no benchmark claims, no fabricated results)

**Key discipline applied:**
- Every decision includes at least one "blocked" or "pending" gate (W1 reviewer, tokenizer audit, Provider 2 selection)
- Trade-offs named explicitly, not hidden
- Links to supporting docs (README, implementation_plan, data-pipeline, eval_pipeline, decisions.md)
- PowerPoint-compatible markdown (short bullets, clear hierarchy, speaker notes)
- No overclaiming (prototype-ready, local, scaffold, gated language throughout)

**Rationale:** You now have a narrative arc you can present to others: "Here's what I learned building this prototype, here are the hard decisions, here's why they matter." The deck is the story; the scripts/configs/docs are the proof. All cross-linked so you can extend it with slides showing actual code/config artifacts if needed.

**No new team decision written** (this is a documentation artifact summarizing existing ADRs and decisions, not a new strategic choice). This note is logged for your future reference.

## 2026-05-01 — Stage 2 Readiness Final Review

**Status:** APPROVED — Integration complete

Danny reviewed the integrated Stage 2 readiness changeset (including Rusty's #19 policy integration). All validation passed: py_compile on changed modules, targeted integrated unittest slice, scorer self-test, stage2 eval self-test. Verdict: APPROVED for merge. Close issues #17–#24 after commit/push. Keep #15–#16 open per Danny's assessment.


## 2026-05-01T01:11:50Z — Code Review: Baibala Live HTML Parser (Issue #16)

**Status:** APPROVED — Ready for closure

### Review scope

Frank's implementation of `parse_baibala_chapter_html()` and raw Baibala candidate generation for Stage 2:
- Parser logic & boundary strategy
- 12 new tests (live parser + candidate builder)
- Manifest alignment-quality policy integration
- Documentation (parser contract, orthography canonicalization)
- CLI expansion (`--from-raw`, `--haw-raw-dir`, `--eng-fixture-dir`)

### Findings

✅ **Parser design sound.** Verse terminator at `<br />` is correct per live sample analysis. Avoids Greenstone nav table leak into final verse.

✅ **Normalization correct.** ASCII apostrophe canonicalization (`'` → U+02BB) matches haw pipeline expectations and is the primary encoding path for the 1839 imprint.

✅ **Test suite adequate.** 12 tests cover live parser edge cases, candidate builder split logic, raw provenance tagging, and fixture integrity.

✅ **Docs clear.** Parser contract well-documented; orthography decisions explained; run order and pinning strategy transparent.

✅ **Policy integration correct.** Adapter correctly omits policy fields (`alignment_confidence_tier`, `quality_flags`, etc.). Manifest builder applies them as designed.

✅ **English side deferral appropriate.** Fixture fallback maintains Stage 2 intake readiness without WEB endpoint pin. Linus will pin WEB separately; manifest rebuild follows.

### Non-blockers

- **English WEB endpoint still unpinned.** Not a blocker for prototype intake. Fixture provides coverage. When Linus pins WEB, `url_template_status` flips to `confirmed_live_<date>` and manifest rebuilds with live English side.

### Recommendation

Close issue #16 and #15. Merge into Stage 2 readiness queue. Parser is production-ready for prototype scope. Combined with coordinator validation (py_compile, test_bible_adapter, test_stage2_manifest, scorer self-test), Stage 2 is ready for final gates.

### Sign-off

- Verdict: APPROVED (no changes required)
- Date: 2026-05-01T01:11:50Z


## 2026-05-02 — Stage 2 Review Pass: Fixed-Point Cap Solution

**Status:** SHIPPED — `data/stage2/reviewed_stage2_manifest_final_capped.jsonl`

### Learnings

- **Cap math must close on the artifact, not a reference denominator.**
  Basher's `reviewed_stage2_manifest_cap_corrected.jsonl` enforced
  `bible_tokens / (T_nonbible_total + T_bible_kept) <= 0.30` and
  `hk_tokens / same_denom <= 0.15`. Self-consistent, but after the HK
  cap dropped tokens, the actual artifact showed Bible=64.8% and
  HK=32.4% of `T_final_train`. A cap that doesn't hold against the
  thing you ship isn't a cap.

- **Closed-form fixed-point for two simultaneous fractional caps.**
  For `B/T <= b_max`, `H/T <= h_max`, `T = N + H + B`:
  `H_max = h_max·N / (1 - h_max - b_max)`,
  `B_max = b_max·N / (1 - h_max - b_max)`.
  At b_max=0.30, h_max=0.15: H=3N/11, B=6N/11, T=20N/11. Exact.

- **Bootstrap reality.** With N=2,950 tokens (Kaikki+Tatoeba only), the
  cap gives at most ~1,609 Bible tokens and ~805 HK tokens. Final
  artifact: 285 train pairs / 570 directional SFT rows. The 80k target
  remains gated on NLLB-mined + synthetic BT, exactly as Rusty §4
  predicted. Anyone claiming review-pending promotion alone reaches 80k
  is producing fiction.

- **Deterministic subsampling by sha256_pair is the right primitive.**
  Reproducible across runs, no randomness, no row-order dependency in
  the manifest. After greedy selection, an artifact-verified
  drop-the-tail loop guards against rounding edge cases.

- **Two prior owners locked out for the same class of bug** (cap denominator
  drift). The pattern: pick a denominator that's stable during your
  computation, but the final artifact is computed against a different
  one. Always verify caps by re-reading the emitted file.


---

## 2026-05-02 — Stage 2 Review Pass Final Cap Solution (ACCEPTED)

**Decision filed:** `.squad/decisions.md` / Stage 2 Review Pass Final Cap Solution section

**Task:** Solve cap drift problem; enforce Bible ≤30% and HK ≤15% against final artifact tokens, not stale reference denominators.

**Outputs (canonical):**
- `data/stage2/reviewed_stage2_manifest_final_capped.jsonl` (33,851 rows, **285 canonical train**)
- `data/stage2/reports/stage2_review_pass_final_capped_20260501.json`
- `scripts/333_build_reviewed_manifest_final_capped.py`
- `data/stage2/stage2_sft_final_capped.jsonl` (570 directional rows, verification)

**Solution: Closed-Form Fixed-Point Math**

Let N = non-Bible non-HK train tokens, H = HK, B = Bible, T = N + H + B.

Constraints:
- B/T ≤ 0.30 ⇔ B ≤ (3/7)(N + H)
- H/T ≤ 0.15 ⇔ H ≤ (3/17)(N + B)

Solving simultaneous binding case:
- **H_max = 3N/11**
- **B_max = 6N/11**
- **T = 20N/11** (exact 30%/15% in artifact)

Pools sorted by sha256_pair ascending, selected greedily. After selection, recompute shares from artifact; drop tail one row at a time until both caps hold.

**Final Verified Counts**

| Source | Train | Dev | Total |
|---|---:|---:|---:|
| Bible 1839 | 5 | 0 | 10,221 |
| Bible 1868 | 25 | 0 | 20,852 |
| HK 1897 | 5 | 0 | 1,103 |
| Kaikki | 153 | 0 | 292 |
| Tatoeba | 97 | 15 | 121 |
| Andrews | 0 | 0 | 1,194 |
| Hoʻoilina | 0 | 0 | 68 |
| **TOTAL** | **285** | **15** | **33,851** |

- **Directional SFT:** **570 rows** (emitter-verified)
- **Bible share:** **29.92%** ✓
- **HK share:** **14.59%** ✓
- **Canonical stage2_manifest.jsonl:** unchanged

**Rejected Predecessors**

- **Linus (26,118 train):** Bible 91.9%, policy violations (Andrews+Hoʻoilina promotion, dev placement)
- **Basher (1,627 train):** Cap math drift (Bible 64.8%, HK 32.4% of actual tokens)

**Hand-off**

- **Linus:** Use final manifest as new source-of-truth for downstream (SFT emitter, builder)
- **Basher:** Re-run eval gate; confirm leakage + ʻokina tripwire
- **Frank:** Unblocked for NLLB-mined + synthetic BT (285 honest pairs; 80k requires non-Bible growth)

**Status:** ACCEPTED. Canonical reviewed manifest locked.


## 2026-05-03 — Stage 2 Final Review Verdict Policy

**Output:** `.squad/decisions/inbox/danny-final-review-verdict-policy.md`

### Problem

After the fixed-point cap pass, 33,551 rows in
`reviewed_stage2_manifest_final_capped.jsonl` still carry
`split=review-pending` with no further adjudication field. That single
label was doing two incompatible jobs: (1) emitter signal "not a
training row," and (2) editorial state "not yet reviewed." The second
was false for nearly every row — they had all been touched by either
the cap-enforcement pass, Rusty's review-pending policy, or Linus's
source-rights gate. Leaving them undifferentiated invited a future
reader to believe they were still promotion candidates.

### Decision

Keep `split` unchanged (preserves emitter contract and 285/15 train/dev
counts). Add three required fields to every row:
`review_status=finalized`, `review_verdict` (closed enum of 8),
`final_review_reason` (free text). Optional `final_review_repromotion_pool`
when verdict is `excluded-policy-cap`.

Verdict taxonomy:
- `accepted-train` / `accepted-dev` for the 285+15
- `excluded-quality` (failed scorer/flags) — re-extract to revisit
- `excluded-policy-cap` (the **only** re-promotable bucket; gated on N growth)
- `excluded-source-not-trainable-now` (Andrews — needs clean re-extraction)
- `future-work-realign` (different alignment strategy needed)
- `future-work-native-review` (Hoʻoilina — W1 reviewer #7 gated)
- `inventory-only` (provenance signal only)

### Source-specific rules (deterministic)

- **Bible 1839 (10,216):** quality_flags-empty + not-train ⇒ cap-overflow;
  rest ⇒ excluded-quality (`haw_no_diacritics` is *expected* for the
  1839 imprint and correctly gates these out)
- **Bible 1868 (20,827):** all `excluded-policy-cap` (largest re-promotion pool)
- **HK 1897 (1,098):** in `hk_eligible_pool` ⇒ cap-overflow (742); rest ⇒
  excluded-quality (351, failed §1.5 promotion rule)
- **Andrews (1,194):** all `excluded-source-not-trainable-now`
- **Kaikki (139):** all `excluded-quality` (no source cap exists for Kaikki)
- **Tatoeba (9):** all `excluded-quality` (`side_too_short`)
- **Hoʻoilina (68):** all `future-work-native-review` (Rusty §1.4)

### Invariants Basher must verify on the artifact

1. Every row has all three new fields (no nulls)
2. Schema split counts byte-identical (285/15/33,551)
3. Verdict ↔ split consistency (no accepted-* on review-pending)
4. Closed enum compliance
5. Cap-pool membership coherent
6. Per-source verdict distributions match §3 rules
7. Bible ≤ 30% / HK ≤ 15% still hold on re-emitted artifact
8. SFT emitter still produces 570 directional rows
9. excluded-quality and excluded-policy-cap mutually exclusive
10. Sum of `excluded-policy-cap` rows logged as the honest
    re-promotion ceiling for Frank's NLLB / synthetic-BT plan

### Trade-offs named (charter discipline)

- Reused `split=review-pending` as the emitter signal vs. introducing
  a new `split=excluded`: chose the former to limit blast radius;
  cost is field overload, mitigated by `review_status=finalized` and
  the explicit verdict.
- 8-verdict enum vs. 2-bucket binary: 8 maps onto the operational
  question "what would unblock this row?" Anything coarser loses the
  "cap-rerun is legal, re-extraction is required" distinction that
  drives Frank's planning.
- Tag pool name only (`final_review_repromotion_pool`) not per-row
  position-in-cap-pool: cheaper, reproducible from sha256_pair sort;
  cost is no resumable cap state (accept; cap pass is sub-second).

### Learnings

- **"Pending" is a smell when the work is actually done.** Once a
  pass touches every row, those rows are *adjudicated*; the schema
  must reflect that even if the operational label can't change. Add an
  editorial layer (`review_status`/`review_verdict`) on top of the
  operational layer (`split`) instead of overloading one field.
- **Re-promotion bucket is the load-bearing distinction.**
  `excluded-policy-cap` vs everything else is what keeps a future
  N-growth pass from accidentally pulling Andrews/Hoʻoilina/quality
  rejects into train. This single boundary is worth more than the
  other five verdicts combined.
- **Don't chase 80k via verdict reclassification.** The honest
  ceiling for re-promotion = sum of `excluded-policy-cap` rows. The
  policy makes that number explicit so it can't be inflated by
  silently relaxing quality or rights gates.
- **Don't change the canonical manifest.** This is editorial state on
  the *reviewed* artifact only. `stage2_manifest.jsonl` (pre-review)
  stays as ingestion truth.

### Status

Decision filed. Basher owns implementation
(`scripts/334_finalize_review_verdicts.py`). No data artifact modified
by this pass.

## 2026-05-02T00:56:01Z — Final Review Verdict Policy (Decision Filed)

**Task:** Define final verdict taxonomy and rules for all 33,551 review-pending rows.

**What I did:**
- Wrote stage 2 final review verdict policy (8 sections, 306 lines).
- Closed enum of 6 verdicts + 2 accepted verdicts: accepted-train, accepted-dev, excluded-quality, excluded-policy-cap, excluded-source-not-trainable-now, future-work-native-review, future-work-realign, inventory-only.
- Source-specific rules for 7 sources: Bible 1839/1868, HK 1897, Andrews 1865, Kaikki, Tatoeba, Hoʻoilina, inventory-only.
- 10 invariants for post-implementation compliance verification.
- Named trade-offs: verdict granularity (6 exclusion verdicts) vs. cognitive load, schema-split field reuse for emitter compatibility, closed-form pools vs. per-row provenance, no backfill of manual_review_reasons.
- Handed off to Basher (implementation) + Linus (HK validation) + Frank (NLLB/BT budget planning) + Rusty (no action; policy consumes review-pending rules).

**Status:** ACCEPTED. Policy filed in `.squad/decisions.md`. Basher owns implementation.
