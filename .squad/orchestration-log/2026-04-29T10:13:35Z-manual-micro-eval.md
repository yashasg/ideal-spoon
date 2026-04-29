# Orchestration Log: W1 Manual Micro-Eval TSV (2026-04-29T10:13:35Z)

## Context

User directive (2026-04-29T10:09:47Z): Add a W1 manual micro-eval TSV to the eval mix — hand-authored ~50–100 prompts for ʻokina/kahakō survival, Unicode/NFC, and simple generation sanity.

## Execution

### Rusty (`rusty-manual-micro-eval`)
- **Authored:** Minimal TSV spec at `.squad/decisions/inbox/rusty-manual-micro-eval.md`
- **Scope:** ~80-item target (range 50–100), hand-authored + human-reviewed
- **Categories (target counts):** `orth_okina` 15, `orth_kahako` 15, `nfc_roundtrip` 10, `tokenizer_survival` 10, `gen_completion` 10, `gen_register` 5, `codeswitch_resist` 10, `closed_qa_trivial` 5
- **Columns:** `item_id`, `category`, `task_type`, `prompt`, `reference`, `expected_chars`, `forbidden_chars`, `notes`, `author`, `reviewed_by`, `review_date`, `license`, `is_holdout`, `train_leak_check` (SHA-256 of NFC `prompt+reference`)
- **Scoring:** Automatic every checkpoint (NFC, ʻokina codepoint U+02BB vs. forbidden U+0027/U+2018/U+2019/U+02BC, kahakō precomposed U+0101 etc., PPL, cloze EM, tokenizer round-trip). Manual at milestone-only: `gen_*` and `codeswitch_resist` outputs reviewed by Rusty + Hawaiian-literate reviewer.
- **Holdout discipline:** ~20% frozen (`is_holdout=true`), never used for tuning; same rule as FineWeb-2 test holdout. Touched only at Stage-1 final report + Stage-2 entry gate.
- **Leakage gate:** Every item's NFC SHA-256 added to `data/eval/eval_hashes.parquet`; `301_build_stage1_dataset.py` excludes training rows matching it. No items lifted from `hawwiki`, FineWeb-2, Baibala, or nūpepa; authors paraphrase/compose.
- **Ownership clarification:** Rusty = NLP Researcher / author. Linus = data engineer / loader implementation. Eval architect (Livingston/Basher) = cadence config placement.
- **Status:** Spec locked; row drafting unblocked off-git; accepted-status promotion awaits Hawaiian-literate reviewer (team gap).

### Linus (`linus-manual-micro-eval`)
- **Authored:** Decision proposal at `.squad/decisions/inbox/linus-manual-micro-eval.md`
- **Scope:** Repo scaffolding + docs without fabricating Hawaiian content
- **Files changed:**
  - `data-sources/manual-eval/w1-haw-micro-eval.template.tsv` (new, header-only TSV template)
  - `data-sources/manual-eval/README.md` (new, schema + hard rules + integration plan)
  - `docs/eval_pipeline.md` §3.1 (one-paragraph pointer to new source)
- **Hard rules (repo-facing):**
  1. Hand-authored or rights-cleared, per-row citation in `notes`
  2. No fabricated Hawaiian: `review_status=draft` until Hawaiian-literate reviewer marks `accepted`
  3. NFC-normalized (`nfc_normalized=true` required); loader rejects U+2018/U+0027 in ʻokina slot or NFD kahakō
  4. Never training data; all `accepted` hashes → `eval_hashes.parquet` before any other use
  5. Frozen once shipped; changing rows bumps eval-suite SHA per `docs/eval_pipeline.md` §4
- **Off-git:** Populated rows at `data/eval/manual_w1/w1-haw-micro-eval.tsv` (covered by `/data/` gitignore)
- **Independence:** Does not block on FineWeb-2 fetch; authoring can start in parallel
- **Status:** Schema + template + integration plan committed; harness wiring awaits eval-harness code (Rusty/Livingston/Basher scope); authoring drafts unblocked.

## Status Summary

| Phase | Status | Blocker |
|-------|--------|---------|
| **Spec** | ✅ Locked | None |
| **Repo scaffold** | ✅ Committed | None |
| **Row drafting** | ⏸ Unblocked off-git | Hawaiian-literate reviewer needed for `accepted` promotion |
| **Harness wiring** | ⏸ Awaiting harness code | Rusty/Livingston/Basher eval-harness scope |
| **Integration to train gate** | ⏸ Trivial when hashes ledger exists | No blocker — flows from `301_build_stage1_dataset.py` existing contamination CI |

## Decisions Merged into `.squad/decisions.md`

- `copilot-directive-2026-04-29T10-09-47Z-manual-micro-eval.md` → "W1 Manual Micro-Eval TSV" section
- `rusty-manual-micro-eval.md` → "W1 Manual Micro-Eval TSV Spec" section
- `linus-manual-micro-eval.md` → "W1 Manual Micro-Eval TSV (independent eval source)" section

Deduplicated: all three decisions are complementary (user request → Rusty spec → Linus implementation plan). No conflicting guidance.

## Cross-Agent Updates

- **Rusty:** History appended with spec lock + row drafting unblocked + next steps (Hawaiian-literate review)
- **Linus:** History appended with repo scaffold completion + next steps (harness wiring, awaiting Rusty/Livingston/Basher)
- **Frank:** No update needed; manual eval is independent of FineWeb-2 fetch

## Git Commit

Staged and committed `.squad/` state:
- Orchestration log (this file)
- Session log
- Merged decisions into `.squad/decisions.md`
- Deleted inbox files
- Updated agent histories

No project files (`data-sources/`, `docs/`, `data/`) staged by Scribe.

---

**Scribe note:** W1 manual micro-eval is now part of team record. Row authoring and harness wiring are unblocked, with clear ownership and constraints documented for the next phase.
