# Rusty — History

## 2026-04-30T08:29:53Z — W1 Stage 0 JSONL-only review [APPROVED]

**Subject:** W1 Stage 0 JSONL-only implementation (Linus).

**Reviewer role:** Background gate (approves or requires revision).

**Review scope:** Verified JSONL-only wiring, strict accepted-row orthographic gates, hash stability, exit-code propagation, docs/test alignment, validation re-run.

**Spot checks:**
- ✅ JSONL-only wiring: `evaluate.py:58` defines `DEFAULT_MANUAL_W1_JSONL`; `evaluate.py:1003-1019` exposes `--manual-w1-jsonl` only (no `--manual-w1-tsv`); legacy TSV symbols removed.
- ✅ Report fields: `jsonl_sha256`, `jsonl_size_bytes`, `schema_version_seen="manual-w1-jsonl-v1"` (JSONL-specific).
- ✅ Accepted-row gate: NFC required, ʻokina orthography strict (U+02BB only), combining macron forbidden, item_id required; drafts/reviewed rows loose.
- ✅ Hash stability: `w1_suite_sha256` over sorted `(item_id, sha256_normalized)` pairs; stable under row reorder, flips on accepted-set changes.
- ✅ Exit propagation: exit 2 on invalid, 0 otherwise; report writes before exit.
- ✅ Docs/tests: `code/README.md`, `docs/eval_pipeline.md` describe JSONL-only; all 50/50 tests pass.

**Validation re-run:** ✅ py_compile clean, ✅ sh -n clean, ✅ 50/50 tests green, ✅ git diff --check clean.

**Verdict:** ✅ APPROVED. W1 JSONL-only revision is production-ready.

---

## 2026-04-30 — W1 Stage 0 contract (pre-rerun)

**Trigger:** yashasg, "let's figure this out before we run Stage 0 again."
W1/manual TSV validation isn't wired into Stage 0; `manual_w1` is a
hard-coded `not_configured` placeholder at `evaluate.py:522`; populated/
accepted off-git rows are invisible to the tracked summary.

**Action:** Read-only pass over `data-sources/manual-eval/README.md`,
the W1 template, `scripts/315_hash_manual_w1_eval.py`,
`code/llm_hawaii/evaluate.py`, `scripts/run_stage0_eval.sh`, and
`docs/eval_pipeline.md`. Approved wiring W1 into Stage 0 via a 5-state
machine (`absent` / `invalid` / `draft_only` / `evaluated` / `harness_error`)
keyed off off-git inputs at `data/evals/manual_w1/`. Decision at
`.squad/decisions/inbox/rusty-w1-stage0-contract.md`. No implementation files
edited.

**Durable learnings:**
- A single `not_configured` literal cannot stand in for four real states
  (file absent, file present-but-draft, file invalid, file evaluated). Drift
  comparison requires a status discriminator + counts + input SHA; otherwise
  "we never had W1" and "W1 silently broke" look identical in the summary.
- Reuse the validator, don't fork it. `scripts/315_hash_manual_w1_eval.py`
  already enforces NFC, U+02BB-only ʻokina, no combining macron, density
  consistency, and dup-`item_id`. Stage 0's loader must call into the same
  rules, not re-implement them; otherwise Stage 0 and the hash ledger can
  disagree on whether a row is valid.
- For now the only mechanically-scorable W1 categories are
  `okina_survival`, `kahako_retention`, `unicode_nfc`, and
  `tokenizer_survival`. `generation_sanity` stays `not_configured` until a
  rubric or judge exists — auto-scoring open-ended Hawaiian generations
  without a Hawaiian-literate human in the loop would be a fabricated
  benchmark.
- `tokenizer_survival` does not need model inference: tokenize-decode-NFC
  round-trip on `reference` is a pure tokenizer probe and runs even when
  the model load fails. Useful as an independent signal.
- `overall_pass_rate` must exclude `generation_sanity` rows from the
  denominator and emit `null` when there are zero mechanically-scorable
  rows. Do not synthesize a passing rate from a current-run baseline —
  that's self-referential.
- Off-Git posture for the tracked summary: status, reason, file path,
  file SHA, schema version, counts, bins, `item_id`s,
  `sha256_normalized`s, mechanical pass counts, tripwires. Never raw
  prompt/reference/notes/author. Apply the same redaction to error
  strings ("line N: prompt is not NFC", not the prompt itself).
- Recommend a `w1_suite_sha256` over the sorted (item_id, sha256_normalized)
  pairs of the *accepted* set — independent of file SHA, so we detect
  "different accepted items, same file size" and "same accepted items, file
  resaved with different bytes" as distinct events.

**Hand-off:** Basher implements `_load_w1` + `_evaluate_w1` and
`code/tests/test_evaluate.py` cases for all five status values; Linus
checks the `run_stage0_eval.sh` projection survives unchanged; I (Rusty)
re-review high-bin items before any row flips to `accepted`, using the
same audit checklist as the `stage0.v1` prompt-suite review.

---

## 2026-04-30 — Stage 0 eval reviews: prompt suite + drift-coverage checklist

**Actions:**
1. **Prompt suite review** (`stage0.v1`) — APPROVED for freeze. Verified all 7 prompts: NFC throughout, every ʻokina is U+02BB (never ASCII, U+2018, U+2019, U+02BC), zero wrong-ʻokina seeds, density bins match labels. Hawaiian phrasing natural and grammatical. Tripwire `kahako_collapse_on_high_diacritic` approved as a count-based (0–N) drift signal given that both high-bin prompts explicitly instruct the model to use kahakō — so zero kahakō in a non-trivial generation is fused instruction-following + orthographic failure. Suite-design invariant documented: any future high-diacritic prompt must explicitly request kahakō or the tripwire's weight weakens.

2. **Drift-coverage checklist** — Assessed what every Stage 0 summary must capture for cross-checkpoint comparison to be sound. Sectioned into A–H (identity headers, distributional orthography, fixed suite shape, PPL slices, tokenizer behavior, W1 status, slice fields, machine-checked tripwires). Current baseline PPL (7.9152) is usable anchor; the summary is insufficient for per-signal drift detection. Checklist now in decisions.md as the contract for Stage 1 aggregator.

**Critical corrections flagged (not blocking v2 freeze, but blocking Stage 1 gate):**
- `evaluate.py:59` hard-codes `torch.float16`; A100 training runs bf16 → at least `identity.model_dtype` is now visible in every summary so the mismatch is *observable*, but the actual fix (bf16 default, fp16 only as Turing fallback) is a separate Basher item.
- `evaluate.py:84` per-source/register PPL slice TODO unresolved → Section D checklist depends on this.
- No English-PPL probe → `english_ppl_up_gt_20pct` tripwire and Section D baseline are unmeasurable until wired.
- `run_stage0_eval.sh` exercises one prompt → Section C requires ≥5–10 spanning density bins before Stage 1 comparison.
- Current orthography is n=1 → Section B distributional baseline must replace single-sample before Stage 1 checkpoint comparison is meaningful.

**Lessons for future work:**
- Suite-design invariant is a property of the *prompts*, not the *code* — if a high-bin prompt doesn't instruct kahakō use, zero kahakō in the response is no longer evidence of model failure. Future suite bumps must respect this or add a parallel tripwire indexed over the kahakō-instructing subset only.
- Self-referential high-density prompts (asking the model in Hawaiian to write Hawaiian "with all the kahakō and ʻokina") are good design — they fuse instruction-following and orthography into one signal.
- Tripwires are signals, not gates — reporting `kahako_collapse_on_high_diacritic` as an integer 0–N keeps it interpretable and tractable for false-positive filtering.

**Non-blocking follow-ups:**
- Symmetric `okina_collapse_on_high_diacritic` counter is cheap (data already exists); suggest as Stage 1 additive (no SHA churn).

---

## 2026-04-30 — Stage 0 prompt suite review: `stage0.v1` approved for freeze

Reviewed Basher's `stage0_eval.v2` drift-signal bundle for Hawaiian-language
correctness — 7 fixed prompts in `code/llm_hawaii/evaluate.py:60`
(`PROMPT_SUITE_ID="stage0.v1"`, `suite_sha256=2683027f…7bce6`) plus the
`kahako_collapse_on_high_diacritic` tripwire. **Approved.** Mechanically verified each
prompt: every Hawaiian prompt is NFC, every ʻokina is U+02BB (no ASCII `'`, no
U+2018/U+2019, no U+02BC), zero wrong-ʻokina seeds, density bins match labels
(low: 1/2 diacritics; medium: 3/3; high: 13/12). Phrasing is grammatical and natural
across registers — `Aloha mai kākou`, `Pehea ʻoe i kēia lā?`, `He aha ka mōʻaukala o
Hawaiʻi?`, plus two self-referential high-bin instructional prompts that ask for
kahakō+ʻokina.

Tripwire approved as a **count** (not boolean) drift signal because both `haw_high_*`
prompts explicitly instruct the model to use kahakō — so `kahako==0` in a non-trivial
generation is fused instruction-following + orthographic failure, exactly the failure
mode global PPL misses. Recorded one suite-design invariant for any future bump:
high-density slot prompts must explicitly request kahakō, otherwise the tripwire's
weight silently weakens; document at change-time, don't redefine. Non-blocking
follow-ups noted: cheap symmetric `okina_collapse_on_high_diacritic` sibling counter
for Stage 1 (data already there); fp16 hardcode at `evaluate.py:162` is now at least
*visible* via `identity.model_dtype` per the drift-coverage checklist, but the actual
bf16/fp16 fix is a separate Basher item, not part of this prompt review. Verdict at
`.squad/decisions/inbox/rusty-stage0-prompt-review.md`. No file edits.

### Durable learnings

- **Suite-design invariant for diacritic-collapse tripwires:** the tripwire's
  interpretive weight is a property of the *prompts*, not the *code*. If a high-bin
  prompt doesn't instruct the model to use kahakō (or ʻokina), zero kahakō in the
  response is no longer evidence of model failure. Future suite versions must respect
  this or add a parallel tripwire indexed only over the kahakō-instructing subset.
- **Self-referential high-density prompts are good design.** Asking the model in
  Hawaiian to write Hawaiian "with all the kahakō and ʻokina" gives one signal that
  fuses instruction-following and orthography — both fail or both pass, and the same
  counter catches it cheaply.
- **Prompt audit checklist is mechanical, not vibes:** NFC pass; ʻokina codepoint ==
  U+02BB on every prompt; wrong-ʻokina detector returns 0 on every prompt (a suite
  that itself trips `wrong_okina_nonzero` cannot be a baseline); per-prompt diacritic
  count agrees with the bin label; `count_hawaiian_diacritics` is the contract, not
  prose counts in inbox notes.
- **Tripwires are signals, not gates.** Reporting `kahako_collapse_on_high_diacritic`
  as an integer 0–N rather than a boolean keeps it interpretable when N > 1 and
  short-generation false-positives become tractable. Keep this pattern for the
  symmetric ʻokina counter when wired.

---

## Core Context

- **Project:** A plan for training an open-source LLM focused on the Hawaiian language, including data, model choices, infrastructure, evaluation, and costs.
- **Role:** NLP Researcher
- **Joined:** 2026-04-29T01:38:35.141Z

## 2026-04-30 — Tokenizer-audit slice shape proposed for `human_fetch.md`

Reviewed `data/raw/ulukau_nupepa/human_fetch.md` as a candidate tokenizer-audit slice. It's a bilingual EN/HW Ulukau/Hoʻolaupaʻi blurb, ~95 Hawaiian words, already NFC-ish with U+02BB ʻokina and kahakō intact — solid high-diacritic stress material. Proposed minimum input shape for the planned tokenizer-audit test: JSONL of `{id, text(NFC+U+02BB), source, lang, is_high_diacritic}` per sample, with TXT paragraph-split fallback; harness must split by `# English` / `# Hawaiian` headings and exclude English from Hawaiian metrics. Caveats logged: file alone is far below the ≥1,500 words / ≥10 high-diacritic gate minimums (one contributing slice, not the gate); "likely native-speaker" is fine for tokenizer stress but is **not** W1/eval data and must not be hashed into `eval_hashes.jsonl` without separate Hawaiian-literate review. Did not modify code; Linus owns conversion. Existing `code/tests/test_tokenizer_audit.py` is still a Qwen smoke stub — when Linus writes the real test it should consume the JSONL shape against the canonical Llama-3.1-8B tokenizer; gate thresholds and fingerprint requirements are unchanged from the frozen decisions.md entry. Decision written to `.squad/decisions/inbox/rusty-tokenizer-audit-slice-shape.md`.

---

## 2026-04-29 — Tokenizer audit gate path landed (#8)

Added `scripts/040_tokenizer_audit.py` as the Stage-0 local-only tokenizer audit for `meta-llama/Llama-3.1-8B`. It supports JSONL/JSON/TSV/CSV/text samples, NFC + conservative U+02BB ʻokina canonicalization, source/path accounting, overall and high-diacritic slices, explicit byte fallback plus byte/proxy rates, tokenizer fingerprint SHA-256, and go/no-go reporting under ignored `data/tokenizer_audit/`.

Docs now point Stage 0 at the script from `docs/training-pipeline.md`, `docs/eval_pipeline.md`, `docs/implementation_plan.md`, and the manual-eval README. Default spend gate is intentionally conservative: ≥1,500 words, ≥10 high-diacritic samples, overall tokens/word ≤2.50, high-diacritic tokens/word ≤3.25, explicit byte fallback 0, proxy ≤1%, standalone diacritic chars ≤2 tokens. Missing `transformers` or gated HF access fails with install/login instructions; no fake audit numbers.

Verification: `python3 -m py_compile scripts/040_tokenizer_audit.py` and `python3 scripts/040_tokenizer_audit.py --help` passed. Did not run a real Llama audit because local HF gated access/sample availability was not established in this task.

---

## 2026-04-29T12:40:50Z — Orchestration Log Capture

**From:** Scribe (Session logger)

**Summary:** Batch spawn for tokenizer audit (#8) consolidated with Linus (#2/#3), Basher (#6), and Stage2 Squad (#9–#14). Orchestration logs created; 3 inbox decisions merged into canonical decisions.md (tokenizer audit gate, eval-hash ledger, Stage 1 manifest). No regressions.

**Your related decision now in canonical decisions.md:**
- Stage-0 tokenizer audit gate for Llama-3.1-8B: `scripts/040_tokenizer_audit.py` is local-only, no-spend gate path; intentionally fails with install/login instructions if transformers missing or HF gated access unavailable; default thresholds (≥1,500 words, ≥10 high-diacritic samples, tokens/word ≤2.50 overall, ≤3.25 high-diacritic, byte fallback=0, proxy ≤1%, diacritic chars ≤2 tokens); any miss = `no_go`.
- Basher's `code/configs/llama31_8b_a100.json` blocked pending real audit `go` + frozen tokenizer/model SHA.

**Next steps:** Basher and trainers wait for real audit decision before Stage 1 spend.

## 2026-04-29 — W1 manual micro-eval local path (#7)

Added `scripts/315_hash_manual_w1_eval.py` for local/off-git W1 validation and eval-hash ledger updates. It validates the TSV schema, NFC, wrong-ʻokina substitutions, diacritic-density counts, categories, and duplicate hashes; default ledger updates include only `review_status=accepted`, with an explicit `--include-draft-for-local-ledger` escape hatch that marks non-accepted rows `eval_consumable=false`.

Generated a local ignored draft at `data/evals/manual_w1/w1-haw-micro-eval.tsv` with 5 prototype rows covering `okina_survival`, `kahako_retention`, `unicode_nfc`, `tokenizer_survival`, and `generation_sanity`. These are not reviewed, not accepted, not benchmark rows; human review remains before W1 can be final eval input. Local ledger now includes 5 `origin=manual_w1` draft rows under ignored `data/evals/eval_hashes.jsonl` for contamination preflight.

Docs/templates now expose the W1 categories, hash material (`NFC(prompt) + LF + NFC(reference)`), JSONL ledger fields, and `diacritic_density_bin` slices. `metrics.py` now has reusable diacritic count/bin helpers for the future harness.

Validation: `python3 -m py_compile scripts/315_hash_manual_w1_eval.py code/llm_hawaii/metrics.py`; `--help`; `--print-schema`; `--init-draft --execute --force`; default `--dry-run`; `--dry-run --include-draft-for-local-ledger`; `--execute --include-draft-for-local-ledger`. `git check-ignore -v` confirms the local TSV, manifest, and ledger are covered by `/data/`.

---

## 2026-04-30T01:42:25Z — Team Update: Basher script removal + gate policy frozen

**From:** Scribe (Session logger)

**Update:** `scripts/040_tokenizer_audit.py` deleted per user directive. Tokenizer audit gate (#8) remains open as policy; audit will return as a **test** (implementation pending). Your gate thresholds and fingerprint requirements are frozen in canonical decisions.md; no changes to audit path or acceptance criteria.

## 2026-04-30 — Llama-3.1-8B audit: `no_go` is a proxy-heuristic mismatch, not a tokenizer blocker

Reviewed `data/tokenizer_audit/official/20260430T033208Z__meta-llama_Llama-3.1-8B.json`. Overall tokens/word **2.474 (pass)**, explicit byte fallback **0.0 (pass)**, byte-fallback-or-proxy rate **0.193 (fail, sole blocker)**; high-diacritic and diacritic-chars slices `not_evaluated`; tokenizer SHA / fingerprint / model repo SHA all `null`.

Key NLP read: the proxy rule (`len(stripped)==1 and ord>127` after stripping `▁Ġ `) was designed for SentencePiece+byte-fallback tokenizers. Llama-3 is **byte-level BPE (tiktoken family)** — every multi-byte UTF-8 char (ʻokina = 3 bytes, kahakō vowels = 2 bytes) is encoded as a sequence of byte-chars from the GPT-2 byte-to-unicode map, all `ord>127`. Unmerged byte-chars are **lossless**, not fallback. The heuristic therefore flags normal byte-level BPE pieces. Two clinching signals: (a) explicit byte fallback is structurally 0 (no `<0xXX>` vocab in Llama-3), so the cross-check that would catch real fragmentation is inapplicable here; (b) tokens/word at 2.47 wouldn't survive 19% true fragmentation on diacritic-heavy text — it'd blow past 3.0.

That said, fingerprint/SHAs missing and high-diacritic/diac-char slices unevaluated are **real** gate gaps independent of the heuristic; gate stands.

Concrete next step recommended: on the same `kaehuikimanoopuuloa.jsonl` slice, dump per-token id / piece / `tokenizer.decode([id])` for ~5 ʻokina+kahakō sentences and verify (i) every flagged piece round-trips to non-empty UTF-8 (lossless), (ii) `decode(all_ids) == NFC(text)`. If both hold, file a harness change making the proxy metric tokenizer-family-aware (skip/redefine for byte-level BPE, keep for SentencePiece+byte-fallback) — Linus owns; populate fingerprint + slices; re-run. No threshold changes, no data changes, no eval/training promotion of the audit slice. Decision written to `.squad/decisions/inbox/rusty-llama31-audit-proxy-heuristic-mismatch.md`.

---

## 2026-04-30T033611Z — Tokenizer audit review + pipeline gate confirmed

**From:** Scribe (Orchestration logger)

**Summary:** Rusty and Basher joint assessment of `data/tokenizer_audit/official/20260430T033208Z__meta-llama_Llama-3.1-8B.json` concluded:
- Gate status: **no-go** (remains)
- Root cause: proxy fallback failure likely reflects byte-level BPE harness mismatch, not proof Llama is unsuitable for Hawaiian
- Next milestone: round-trip / token-piece inspection + tokenizer-family-aware proxy heuristic, then re-run with hashes and high-diacritic/diacritic-char sections populated
- GPU freeze enforced until clean audit exists (per Basher)

**Your related orchestration log:** `.squad/orchestration-log/20260430T033611Z-rusty.md`  
**Session log:** `.squad/log/20260430T033611Z-llama-tokenizer-audit-review.md`

---

## 2026-04-30 — Kaʻehuikimanōopuʻuloa pages assessed as tokenizer-audit slice

Reviewed `data/raw/ulukau_nupepa/human_fetch_book_pages.txt` (Moses Manu moʻolelo, 3,223 Hawaiian words, 21 paragraphs, all NFC, ʻokina at U+02BB ×756, kahakō vowels ×614, every paragraph clears the ʻokina+kahakō ≥3 high-diacritic floor). Strong tokenizer-audit candidate: alone it meets the frozen Stage-0 minimums (≥1,500 words, ≥10 high-diacritic samples) and pairs cleanly with the earlier `human_fetch.md` landing-copy slice. Bright line held: tokenizer audit only — not W1, not eval, not training, not hashed into `eval_hashes.jsonl` without separate Hawaiian-literate review; provenance/licensing of the digitized edition still to confirm before any non-local use. Flagged single-genre stress — all one author/register — and gave practical target guidance (~5–6k words across ≥3 genres: nūpepa, modern prose, place-name/proper-noun heavy) so audit numbers are defensible, not just passing. No threshold/fingerprint changes; Linus owns conversion to the JSONL slice shape under `data/tokenizer_audit/ulukau_nupepa/`. Decision written to `.squad/decisions/inbox/rusty-kaehuikimanoopuuloa-audit-assessment.md`.

## 2026-04-30 — Harness cleanup plan (tokenizer/NLP side)

Produced the NLP-side cleanup plan for the tokenizer audit harness in response to "how do we clean the harness." Core position unchanged from the Llama-3.1-8B `no_go` review: the proxy heuristic is SentencePiece-shaped and misfires on byte-level BPE. Cleanup is **harness logic + reporting**, not threshold relaxation.

### Learnings (durable)

- **Tokenizer-family detection must come from the tokenizer object, not the model id.** Reliable signals (in priority order): (1) `tokenizer.backend_tokenizer.model.__class__.__name__` from `tokenizers` (BPE / Unigram / WordPiece); (2) presence of an `sp_model` attr or `<0xXX>` tokens in the vocab → SentencePiece+byte-fallback family; (3) presence of the GPT-2 byte-to-unicode map (256 single "byte chars" like `Ġ`, `Ċ`, `ł`, `Ń`…) covering vocab → byte-level BPE (Llama-3, GPT-2/4, Qwen2). Hard-coding by `model_id` is brittle — Llama-2 is SentencePiece, Llama-3 is tiktoken-style byte-level BPE; same family name, different math.
- **Llama-3 has no `<0xXX>` vocab.** `explicit_byte_fallback_rate` is structurally 0 for byte-level BPE and carries no signal; reporting it is fine (audit trail) but it cannot pass/fail a byte-level model on its own.
- **`tokens_per_word` is the cross-check.** True fragmentation on diacritic-heavy Hawaiian (ʻokina + kahakō) cannot sit at 2.47 with 19% real byte fallback — it would be ≥3. When proxy rate and tokens/word disagree, trust tokens/word + round-trip; the proxy is wrong.
- **The current proxy rule** (`len(stripped)==1 and ord(stripped)>127` after stripping `▁Ġ `) double-counts byte-level BPE: every multi-byte UTF-8 char (ʻokina = 3 bytes, kahakō vowels = 2 bytes) decomposes to byte-chars all with `ord>127`. Lossless, not fallback.
- **Round-trip is the ground truth, not piece shape.** Two cheap invariants: (a) `decode(all_ids) == NFC(text)` over the whole slice; (b) for any flagged piece, `decode([id])` returns non-empty UTF-8 and the concatenation of `decode([id])` over flagged pieces, when reattached to neighbors, reproduces the original substring. If both hold, byte-fallback is definitionally not happening regardless of piece appearance.
- **Debug dump for auditability:** per-slice JSONL with `{sample_id, sentence, ids:[…], pieces:[…], piece_decoded:[…], piece_byte_lens:[…], is_byte_level_bpe_piece:[…], is_explicit_byte_fallback:[…], roundtrip_ok:bool, decoded==NFC(text):bool}` for ≥5 ʻokina+kahakō sentences, plus an aggregate `{tokenizer_family, byte_to_unicode_coverage, has_0xXX_vocab, sp_model:bool, vocab_size}`. Keeps decisions reproducible without re-running.
- **Thresholds: no change.** `tokens_per_word ≤ 2.50` overall and `≤ 3.25` high-diacritic remain the real spend gate. `explicit_byte_fallback_rate = 0` stays — it's free signal where applicable. `byte_fallback_or_proxy_rate ≤ 0.01` stays for SentencePiece/byte-fallback families and is **not evaluated** (status field, like `high_diacritic` today) for byte-level BPE; round-trip `==` becomes the byte-level BPE replacement check (must be true; no numeric threshold needed).

## 2026-04-30T03:47:33Z — Tokenizer-family-aware proxy handling decision

**From:** Scribe (session logger + orchestration)

**Sync task:** Defined tokenizer-family-aware proxy handling for harness cleanup.

**Summary:** Coordinated cleanup with Linus (code/harness lead). Rusty scope: detect tokenizer family from vocab (byte_level_bpe, sentencepiece_byte_fallback, wordpiece, unigram, other), make proxy check family-aware (not_evaluated + reason for byte_level_bpe; keep threshold ≤0.01 for SentencePiece/unigram/wordpiece), add round-trip lossless check as structural integrity gate (all families, replaces proxy for byte_level_bpe), write debug dump (samples.debug.jsonl + tokenizer.fingerprint.json for auditability), fix reporting (passed=null + status=not_evaluated must not appear in blocking_reasons).

**Key insight:** Llama-3 `no_go` is a harness bug, not a threshold problem. Byte-level BPE pieces are lossless; the 19% proxy flag is dominated by `▁<diacritic>` patterns that are structurally correct, not fallback. Round-trip check is the real gate for BPE; proxy remains applicable for SentencePiece.

**Thresholds:** Frozen (no changes). Acceptance: Llama-3.1-8B re-run should yield tokenizer_family=byte_level_bpe, byte_fallback_or_proxy_rate=not_evaluated (excluded), roundtrip_lossless=true, overall_tokens/word~2.47 (passed), recommendation=go (pending high-diacritic/diacritic-chars coverage).

**Decision:** `.squad/decisions/inbox/rusty-harness-cleanup-tokenizer-family-aware.md` (now merged to decisions.md).

---

## 2026-04-30T04:05:58Z — Tokenizer audit decisions finalized and merged

**From:** Scribe (Session logger)

**Summary:** Rusty tokenizer audit decisions consolidated and merged to canonical decisions.md:

**1. Kaʻehuikimanōopuʻuloa as tokenizer-audit slice (assessment + Linus conversion task):**
- Volume: 3,223 Hawaiian words, 21 paragraphs, 756 ʻokina, 614 kahakō, diacritic density ≈0.1254
- Gate compatibility: ✅ Meets Stage-0 minimums alone (≥1,500 words, ≥10 high-diacritic samples)
- NFC + U+02BB clean: canonicalization should be no-op (good control for harness)
- Caveats: audit-only (not W1/eval/training), license unverified, single-genre (one author/moʻolelo/register)
- Practical target for audit defensibility: collect 3–5 additional varied-genre slices (~150–500 words each) to reach ~5–6k words across ≥3 genres

**2. Llama-3.1-8B audit analysis: proxy-heuristic mismatch vs. tokenizer blocker (NLP assessment):**
- Core finding: `byte_fallback_or_proxy_rate = 0.1928` (fails 1% gate) but this is **harness mismatch, not tokenizer blocker**
- Proxy rule designed for SentencePiece+byte-fallback; Llama-3 uses byte-level BPE (tiktoken family)
- In byte-level BPE, multi-byte UTF-8 chars (ʻokina=3 bytes, kahakō=2 bytes) decompose to byte-chars all `ord>127`; unmerged pieces are **lossless**, not fallback
- Clinching signals: (a) `explicit_byte_fallback_rate=0` is structurally always 0 for byte-level BPE (no `<0xXX>` vocab), so cannot be blocker; (b) `tokens_per_word=2.47` would not survive 19% real fragmentation on diacritic-heavy text (would blow to ≥3.0)
- **Real gate gaps remain:** missing fingerprint/SHAs, unevaluated high-diacritic and diacritic-chars sections
- Recommendation: produce round-trip evidence (5 ʻokina+kahakō sentences, verify `decode(all_ids)==NFC(text)` and each flagged piece is lossless), then file harness fix (tokenizer-family-aware proxy handling), populate SHAs + slices, re-run

**3. Outcomes:**
- No threshold changes. Frozen gate stands: overall tokens/word ≤2.50, high-diac ≤3.25, explicit byte fallback=0, proxy ≤1%, diac chars ≤2, fingerprint required
- No data changes, no eval/training promotion of audit slice (audit-only)
- GPU freeze enforced until clean audit with all sections populated

**Orchestration logs:** `.squad/orchestration-log/2026-04-30T04:05:58Z-linus.md`  
**Related decisions:** Merged to `.squad/decisions.md` under:
- "Added 2026-04-30: Rusty — Kaʻehuikimanōopuʻuloa as tokenizer-audit candidate slice (assessment)"
- "Added 2026-04-30: Rusty — Llama-3.1-8B audit no_go is proxy-heuristic mismatch, not tokenizer blocker (analysis)"

**Key ask:** Linus round-trip inspection + tokenizer-family-aware proxy heuristic for harness cleanup.

## 2026-04-30T04:20:10Z — Tokenizer-cleanup semantics finalized (harness, not thresholds)

**From:** Scribe (session logger)

**Summary:** Rusty produced the NLP-side cleanup plan for tokenizer audit harness in response to Llama-3.1-8B proxy-heuristic false positive. Core insight unchanged: proxy rule is SentencePiece-shaped and misfires on byte-level BPE. Cleanup is **harness logic + reporting**, not threshold relaxation.

**Merged to decisions.md:**
- `tokenizer_family` detection (byte_level_bpe / sentencepiece_byte_fallback / wordpiece / unknown)
- Per-check `applicability` field (byte_fallback_or_proxy_rate is `not_applicable` for byte-level BPE, excluded from blocking)
- `roundtrip_lossless` check (structural integrity gate for all families; replaces proxy for byte-level BPE)
- Fix `not_evaluated` vs `not_applicable` vs `insufficient_samples` distinctions; `passed=null` must not appear in `blocking_reasons`
- No threshold changes (all current limits **stand unchanged**)

**Expected outcome on Llama-3.1-8B re-run:**
- `tokenizer_family = "byte_level_bpe"`
- `byte_fallback_or_proxy_rate = 0.193` with `applicability=not_applicable, passed=null` (excluded from blocking)
- `roundtrip_lossless = true` (expected; must verify)
- `overall_tokens_per_word = 2.47` ✅
- `recommendation = "go"` IFF high-diacritic/diacritic-chars clear; else `no_go` with **correct** reasons (coverage/fragmentation), not phantom proxy failure

**Key asks:**
- Linus to implement harness (7-phase plan now in decisions.md)
- Coordinator to route Phase 2 (family-aware proxy) back through Rusty for sign-off before Linus codes

**Orchestration log:** `.squad/orchestration-log/2026-04-30T04-20-10Z-rusty-tokenizer-cleanup.md`  
**Session log:** `.squad/log/2026-04-30T04-20-10Z-tokenizer-cleanup-plan.md`


## 2026-04-30T04:44:24Z — Linus implemented tokenizer-family-aware harness cleanup (phases 1–6 complete)

**From:** Scribe (orchestration logger)

**Summary:** Linus completed implementation of the tokenizer-family-aware harness cleanup. All phases 1–6 deployed; 33 unit tests passing, 1 smoke skipped (transformers env limitation). Your design for family detection, proxy applicability fixing, and roundtrip gate is now live in `code/llm_hawaii/tokenizer_audit_helpers.py` and tested in `code/tests/test_tokenizer_audit.py`.

**Implemented per your spec:**
- ✅ `detect_tokenizer_family()`: byte_level_bpe, sentencepiece_byte_fallback, unknown (4-tier heuristic per your design)
- ✅ `byte_fallback_or_proxy_rate` → `status=not_applicable` for byte-level BPE (threshold 0.01 preserved; excluded from blocking_reasons)
- ✅ `roundtrip_lossless` check: structural integrity gate (exact after NFC normalization; required when text+tokenizer present)
- ✅ `high_diacritic` evaluator: paragraph filter + min 10 samples/1,500 words gate per your definition
- ✅ `diacritic_chars` evaluator: ʻ ā ē ī ō ū (+ uppercase), pass ≤2 tokens each
- ✅ `checks[*].status` explicit (evaluated, not_applicable, not_evaluated, insufficient_samples)
- ✅ `blocking_reasons` fixed: never includes `passed=null` or `not_evaluated` items

**Test coverage:** 33 unit (metadata, family detection, proxy semantics, roundtrip, high-diacritic, diacritic-chars), 1 smoke (Llama, skipped)

**Next milestone (Phase 7):** Re-run Llama-3.1-8B audit against helpers. Expected outcomes per your prior decision:
- `tokenizer_family = "byte_level_bpe"` ✅
- `byte_fallback_or_proxy_rate = 0.193` with `status=not_applicable` (excluded) ✅
- `roundtrip_lossless = true` (requires verification on actual Llama tokens)
- `overall_tokens_per_word ≈ 2.47` ✅
- High-diacritic + diacritic-chars sections populated (not_evaluated → evaluated or insufficient_samples)
- `recommendation = "go"` IFF all sections clear; else correct blocking reasons (coverage/fragmentation), not phantom proxy failure

**Ready for:** Your round-trip inspection on 5 ʻokina+kahakō sentences to verify `decode(all_ids)==NFC(text)` and each flagged piece is lossless (per your earlier decision). When ready, re-run will finalize gate assessment.

**Schema:** Remains v1 (backward-compatible). v2 + `run_kind` deferred per existing decisions.md.

**Orchestration log:** `.squad/orchestration-log/2026-04-30T04:44:24Z-linus-tokenizer-audit-cleanup-implementation.md`

---

## 2026-04-30 — Between-checkpoint signal contract (read-only assessment)

User asked: "what will we check between checkpoints, how do we know from the eval if the model is improving or getting worse." Wrote a focused signal map for Stage-1 cheap-eval (Hawaiian held-out PPL on FineWeb-2 dev + W1 manual micro-eval once accepted), grounded in `docs/eval_pipeline.md` §3.1/§3.2/§3.4, §4 (cheap cadence), §5 (slicing), §6 (attribution).

Key points to remember:
- Stage-0 base summary at `docs/eval-runs/stage0/20260430T063118Z__stage0_base_eval_summary.json` is a *single-prompt* baseline (`prompt_count: 1`, `generation_count: 1`, hawaiian_ppl=7.915 on `data/evals/fineweb2_haw/dev.jsonl`). It anchors PPL only; the orthography numbers (okina=15, wrong_okina=0, kahako=9, density_bin=high, is_nfc=true) are from one generation and are illustrative, not a full orthography distribution. Per-checkpoint cheap eval needs the full dev slice, not n=1.
- Improvement = held-out Hawaiian PPL drops on the same `eval_file_sha256` AND ʻokina survival rate stays at 1.0 with `wrong_okina=0`, kahakō retention vs reference doesn't drop, NFC stays true, English-PPL delta doesn't blow past +20% (forgetting threshold from §6), tokens/word and byte-fallback don't drift up on outputs, and W1 per-category pass-rates (okina_survival, kahako_retention, unicode_nfc, tokenizer_survival, generation_sanity) are flat-or-up.
- Warning signs *even when PPL improves*: ʻokina collapses to U+2018/U+0027 (hard fail at Stage 1 gate), kahakō stripping or NFD drift, English PPL up >20% rel, train↔dev gap widening with dev↔holdout flat (overfit), dev↔holdout gap widening (cluster leak), generation degeneracy (repetition / English collapse / register collapse) on open-ended sanity probes, n-gram overlap with `eval_hashes.jsonl` rising on outputs, hallucination rate on real-Hawaiian-entity probes climbing, high-diacritic-density slice degrading while low-density improves (orthography fingerprint), tokens/word rising on inputs (tokenizer pathology), provider-to-provider score divergence on the same checkpoint.
- Held-out PPL alone is not sufficient. Single-global-metric framing is rejected per §5. Comparisons only valid at fixed `eval_suite_sha` + `eval_file_sha256` (SHA already captured in the Stage-0 summary).
- W1 manual micro-eval is currently template-only / draft — until #7 closes (Hawaiian-literate review → `accepted`), W1 results are wiring-only and must not be reported as benchmark numbers. The independent (non-FineWeb-2) orthography signal is therefore *not yet live* even though the design slot exists.

Decision written: `.squad/decisions/inbox/rusty-eval-checkpoints.md`.
Did not modify code or docs. One critical correction reported: do not generalize the Stage-0 summary's orthography block (n=1 generation) into a per-checkpoint orthography baseline; the cheap-eval loop needs the full dev slice (and W1 once accepted) before deltas are interpretable.

## 2026-04-30: Checkpoint eval signals finalized

Joint advisory with Basher on per-checkpoint Hawaiian LLM evaluation signals. Delivered:
- Six signal families: hawaiian_ppl per-slice, english_ppl_delta, orthography (okina survival, kahako retention, NFC), tokenizer behavior (tokens/word, byte-fallback), generation sanity (no repetition/code-switch/register flip), contamination integrity (overlap, hallucination rate).
- Improvement = conjunction across all families (asymmetric)
- Regression = any one tripwire sufficient (asymmetric): okina collapse to U+2018/U+0027 is Stage-1 hard-fail
- Slicing required: source/register, diacritic density, length, tokenizer bin, split, W1 category (once accepted)
- Critical: Stage-0 orthography baseline is n=1 sample, not distributional; per-checkpoint must use full dev slice (621 rows)

Outcome: `.squad/decisions.md` entry, orchestration logs, session log recorded. Ready for Stage-1 monitoring implementation.

---

## 2026-04-30 — Stage 0 eval drift-coverage acceptance checklist

Read-only coverage pass (parallel to Basher's implementation) on whether the Stage 0 eval summary captures enough to detect Hawaiian regressions between checkpoints. Reviewed `docs/eval_pipeline.md`, `data-sources/manual-eval/README.md` + template TSV, `code/llm_hawaii/evaluate.py`, `code/llm_hawaii/metrics.py`, and `docs/eval-runs/stage0/20260430T063118Z__stage0_base_eval_summary.json` against the canonical 2026-04-30T07:00:17Z signals decision.

Verdict: current Stage 0 artifact is a usable **PPL anchor only** (`hawaiian_ppl=7.9152`, `eval_file_sha256` frozen). It is **not** a drift baseline: orthography is n=1 (one prompt, one generation), no eval-suite SHA / tokenizer SHA / eval dtype / prompt-set SHA / ledger SHA, no per-source or English PPL slices, no tokens/word or roundtrip_lossless on outputs, no W1 status fields, no slice keys (source/length/tokenizer-behavior/split/w1_category), and tripwires are not serialized as machine-checkable booleans. Restated the six canonical corrections (fp16 hardcode, missing per-source slice, missing English PPL, single-prompt run script, partial run-report schema, n=1 orthography) as acceptance criteria on the artifact.

Output: full A–H checklist (identity header / orthography distributional / fixed prompt suite shape / PPL slices / tokenizer-on-outputs / W1 status / mandatory slice fields / serialized tripwires) written to `.squad/decisions/inbox/rusty-stage0-drift-coverage.md`. No implementation files modified — corrections reported, not edited, per task scope. Hand-off: Basher's implementation pass picks up the six corrections; W1 status fields stay `draft_only` / `eval_consumable_count=0` until #7 acceptance lands.

## 2026-04-30 — W1 Stage 0 implementation review (verdict: reject, small revision)

Read-only review of Basher's `manual_w1_status()` in `code/llm_hawaii/evaluate.py` against my prior contract (`.squad/decisions/inbox/rusty-w1-stage0-contract.md`). Tests 25/25 green, no raw text leakage, scoring_status=not_wired correctly disclaims accuracy, 5-status enum present (with `not_configured` reserved for the explicit-disable path — an improvement over contract's conflation).

Rejected for four contract gaps that the cross-checkpoint diff posture depends on:
1. `accepted_item_hashes` missing — sorted sha256_normalized list over accepted rows. Without it, `tsv_sha256` only signals "file changed", not "accepted set changed".
2. `w1_suite_sha256` missing — sha over sorted (item_id, sha256_normalized) pairs of accepted rows. Discriminator #4 in contract.
3. `schema_version_seen` missing — hardcode `manual-w1-tsv-v1` for now; reserves the field for JSONL switch.
4. NFC/ʻokina/combining-macron failures on accepted rows must flip `status=invalid` with `error_count`+line/field-only `first_errors`, not be buried in `nfc_normalized_false_count`. Drafts may stay loose.

Non-blocking: JSONL-first preferred (carries sha256_normalized + schema version natively); harness_error correctly deferred until scoring wires; naming drift (missing↔absent, tsv_sha256↔input_sha256, accepted_*_counts↔accepted_by_*) — pick one document and reconcile.

Recommended Basher to revise (same author justified: additive gaps, not domain misunderstanding) and Linus to re-confirm summary projection. Verdict written to `.squad/decisions/inbox/rusty-w1-implementation-review.md`. No code edited.

Lesson: when writing contracts that prefer JSONL but allow TSV fallback, spell out which contract fields the TSV path must compute itself (here: per-row sha256_normalized via the same formula as `scripts/315_hash_manual_w1_eval.py`). Otherwise the implementer reasonably assumes "TSV does not carry it ⇒ field omitted".

## Learnings

### 2026-04-30 — W1 / Stage 0 revision review (Linus)

**Outcome:** APPROVE. Verdict at
`.squad/decisions/inbox/rusty-w1-linus-revision-review.md`.

- All four blockers from `rusty-w1-implementation-review.md` are
  closed: `accepted_item_hashes` (sorted SHA list) + `w1_suite_sha256`
  (sha256 over sorted `(item_id, sha256_normalized)` pairs) + `schema_version_seen`
  (`"manual-w1-tsv-v1"` only on TSV-capable statuses) are emitted on
  the right branches with no raw prompt/reference text leakage.
- Accepted-row strict gate now flips `manual_w1.status = "invalid"`
  on NFC failure / U+0304 / wrong-ʻokina / `nfc_normalized != "true"`
  / empty `item_id`; drafts/reviewed rows stay loose.
  `first_errors` is line+field-only, capped at 10, with `error_count`
  carrying the true total.
- `evaluate._cli_exit_code` returns 2 on invalid W1 (else 0); CLI
  always prints the report JSON before returning the rc.
  `scripts/run_stage0_eval.sh` captures rc, writes the tracked
  summary projection unconditionally (verbatim `manual_w1` pass-through,
  so new safe fields aren't silently dropped), then propagates non-zero.
  `set -eu` is preserved by the `&& … || EVAL_RC=$?` capture pattern.
- Corrected source directive: trusted W1 source is
  `data/raw/ulukau_nupepa/human_fetch.txt`; the converter
  `scripts/_convert_ulukau_human_fetch.py` is parser/normalizer
  context only. File exists on disk with `# English` / `# Hawaiian`
  sections; `data/` is gitignored, so neither the raw text nor the
  populated W1 TSV can leak into tracked summaries.
- Validation (`py_compile`, `sh -n`, `unittest tests.test_evaluate
  tests.test_metrics`) re-ran clean: 42/42 green, matching Linus's
  numbers.
- JSONL switch (read `sha256_normalized` + `MANUAL_W1_JSONL_SCHEMA_VERSION`
  per row, drop the mirrored hash helper, retire the TSV path) remains
  the natural follow-up; explicitly reserved-only today, not
  prematurely implemented.

### 2026-04-30 — W1 JSONL-only revision review (Linus)

**Outcome:** APPROVE. Verdict at
`.squad/decisions/inbox/rusty-w1-jsonl-only-review.md`.

- Stage 0 W1 input is JSONL-only end-to-end:
  `evaluate.DEFAULT_MANUAL_W1_JSONL = "data/evals/manual_w1/w1-haw-micro-eval.jsonl"`,
  `--manual-w1-jsonl` / `MANUAL_W1_JSONL` wiring, `--no-manual-w1` /
  `USE_MANUAL_W1=0` disables. No `DEFAULT_MANUAL_W1_TSV` /
  `--manual-w1-tsv` / `MANUAL_W1_HEADER` / `MANUAL_W1_TSV_SCHEMA_VERSION`
  symbols remain in `evaluate.py`; their absence is pinned by
  `test_evaluate.py:482-487`.
- Report fields are JSONL-specific: `jsonl_sha256`, `jsonl_size_bytes`,
  `schema_version_seen = "manual-w1-jsonl-v1"` on
  `evaluated` / `draft_only`; `None` on `not_configured` / `missing` /
  `invalid`. `scoring_status` stays `not_wired`. No raw prompt /
  reference / notes / author / text leaks on any branch.
- Accepted JSONL rows correctly support `item_id` with `id` alias,
  `category`, `prompt`, `reference` (falling back to `text` for hash
  material), `review_status`, `nfc_normalized` (bool or `"true"`/`"false"`),
  `diacritic_density` + `diacritic_density_bin`, and optional
  `sha256_normalized` (used verbatim when 64-hex, else canonical
  `sha256(NFC(prompt) + LF + NFC(reference))` fallback that mirrors
  `scripts/315_hash_manual_w1_eval.py:compute_hash` byte-for-byte).
- Accepted-row strict gate: NFC failure on `prompt` / `reference` /
  `text`, U+0304 combining macron, wrong-ʻokina codepoint
  (U+2018/U+2019/U+0027/U+02BC), `nfc_normalized != "true"`, or empty
  `item_id` flips `manual_w1.status = "invalid"`,
  `eval_consumable_count = 0`, `accepted_item_hashes = []`,
  `w1_suite_sha256 = null`, `schema_version_seen = null`, with
  `first_errors` capped at 10 line+field-only strings and
  `error_count` carrying the true total. Drafts/reviewed rows stay
  loose via the `if rs != "accepted": continue` guard.
- `w1_suite_sha256` is stable under row reorder (sorted
  `(item_id, sha256_normalized)` pairs) and flips on accepted-set
  churn; both behaviors pinned by tests.
- `evaluate._cli_exit_code` returns 2 iff `manual_w1.status == "invalid"`,
  always after writing the report JSON. `scripts/run_stage0_eval.sh`
  captures rc with `&& EVAL_RC=0 || EVAL_RC=$?`, writes the tracked
  summary projection unconditionally (verbatim `manual_w1` pass-through),
  then propagates the non-zero exit. `set -eu` preserved.
- Docs (`code/README.md`, `docs/eval_pipeline.md`,
  `data-sources/manual-eval/README.md`) consistently describe Stage 0
  as JSONL-only and call out the TSV solely as the local authoring
  source consumed by
  `python3 scripts/315_hash_manual_w1_eval.py --execute --jsonl-only`.
- `data/raw/ulukau_nupepa/human_fetch.txt` remains the named trusted
  source directive; `_convert_ulukau_human_fetch.py` self-describes as
  parser/normalizer (not the source) and writes only under ignored
  `data/tokenizer_audit/`. The W1 TSV/JSONL paths are gitignored, so
  raw local data cannot leak into tracked summaries.
- Validation: `py_compile`, `sh -n`, `unittest tests.test_evaluate
  tests.test_metrics` all clean — **50/50 tests green**.
  `git --no-pager diff --check` clean.

Linus is locked out of the next revision cycle on this scope (verdict is
APPROVE; no rejection-driven re-spawn needed).

## 2026-04-30 — human_fetch bidirectional translation probe review [APPROVED]

**Subject:** Linus's `human_fetch_translation_probe` (en→haw + haw→en) wired
into every checkpoint eval as part of the Stage-0-as-checkpoint-0 series.

**Verdict:** ✅ APPROVED. Re-ran 73/73 tests, py_compile + sh -n clean.
Spot-checked all 10 review criteria against `evaluate.py:502-743,1089-1135,1295-1326`,
`scripts/_convert_ulukau_human_fetch.py:30-125`, `scripts/run_stage0_eval.sh:33-131,143-266`,
the regenerated JSONL on disk, and `docs/eval_pipeline.md:230`.

**Durable learnings:**

- **"Safe-to-miss" probe contract is now skill-codified** at
  `.squad/skills/eval-probe-safe-to-miss/SKILL.md` — apply the same
  status enum (`not_configured` | `missing` | `invalid` | `ready` |
  `evaluated`), early-return on missing, hash-only report shape, stable
  top-level `report[<probe>]` key even when disabled, and explicit
  `eval_eligible` / `training_eligible` policy fields to every future
  off-git probe. Missing-key vs. `not_configured`-status disambiguation
  is what lets the cross-checkpoint aggregator stay honest.

- **Direction separation is a property of the report shape, not of
  the metric.** Even a baseline char-F can be made misleading by
  averaging en→haw and haw→en into a single number; the contract is to
  emit `directions.en_to_haw` and `directions.haw_to_en` as sibling
  dicts so an asymmetric collapse (e.g. checkpoint forgets to copy
  English back, or starts producing English when asked for Hawaiian) is
  immediately visible. Future bidirectional probes (Stage 1+) must
  preserve this shape.

- **Metric honesty matters more than metric sophistication for a
  Stage 0 baseline.** `char_ngram_f1_baseline` is a string-overlap drift
  signal, not translation quality, and the docstring/README/eval_pipeline
  all say so explicitly. A pure-stdlib char-bigram F is the right
  abstraction here: deterministic, dependency-free, checkpoint-comparable,
  and orthography-sensitive (a kahakō collapse or wrong-ʻokina
  substitution will visibly drop the score). Production translation
  metrics (chrF++, BLEU, COMET) are a Stage 1+ concern when we have a
  larger eval set; any future swap must keep the baseline visible
  alongside, not replace it silently.

- **NFC + U+02BB enforcement belongs upstream at the converter, not
  inline at every probe.** The converter folds U+2018/U+2019/U+02BC/`
  to U+02BB and NFC-normalizes once; downstream probes can NFC-normalize
  defensively but should not silently re-fold ʻokina variants — that
  would mask a hand-edited JSONL that introduced a wrong codepoint.
  Future hardening: probes loading off-git Hawaiian JSONL should
  *assert* `wrong_okina_count == 0` on `haw` rows and flip to
  `status="invalid"` if not, mirroring the W1 accepted-row gate. Logged
  as a non-blocking follow-up.

- **`note` (free-prose advisory) is the one weak point in a hash-only
  contract.** It's harmless today (no corpus text), but the tracked
  summary projection has to defensively strip it. The cleaner long-run
  shape is to push advisory prose into a sibling registry (e.g.
  `eval_pipeline.md` §8.1 already carries it) and keep the in-report
  dict literally hash-only. Non-blocking.

## 2026-04-30T08:55:56Z — human_fetch bidirectional translation probe review [APPROVED]

**Subject:** human_fetch bidirectional translation probe for checkpoint evals (Linus).

**Reviewer role:** Sync reviewer gate (10-point checklist, approves or requires revision).

**Review scope:** Verified Stage 0 = checkpoint 0 (no special case), safe-to-miss semantics, bidirectional direction separation (no averaging), honest baseline metric framing, no raw text leaks, Hawaiian orthography appropriate, converter metadata truthful, W1 invalid-gate intact, CLI/env compatibility preserved, tests/validation sufficient and reproducible.

**10-point checklist:** All PASS
1. ✅ Stage 0 = checkpoint 0 (wired in `evaluate_checkpoint()` every call, no if-stage-0 branches)
2. ✅ Safe to disable/miss (missing → status="missing", no exit-code flip)
3. ✅ Directions strictly separate (en_to_haw and haw_to_en distinct keys, never averaged)
4. ✅ Metric honestly framed ("baseline char-bigram F1", not "translation quality")
5. ✅ No raw text leaks (sha256 hashes only, test `test_hash_only_fields_no_raw_text` recursive-scans)
6. ✅ Hawaiian orthography appropriate (NFC + U+02BB-only ʻokina, kahakō retained, drift signal asymmetric)
7. ✅ Converter metadata truthful (eval_eligible: true, training_eligible: false, translation_probe_eligible: true)
8. ✅ W1 invalid-gate intact (exit 2 only on manual_w1.status == "invalid", not probe)
9. ✅ CLI/env compatibility preserved (new flags additive, env vars follow W1 pattern)
10. ✅ Tests/validation sufficient (73/73 green, 23 new tests covering all status states and edge cases)

**Validation re-run:** ✅ py_compile clean, ✅ sh -n clean, ✅ 73/73 tests green, ✅ git diff --check clean.

**Non-blocking observations:**
- Probe does not re-enforce single-ʻokina codepoint at probe time (fine for now, future hardening could add wrong-ʻokina-count assertion)
- hawaiian_ppl null-handling pre-existing wart
- note field is only free-prose string (wrapper strips; could drop from output in future)

**Verdict:** ✅ APPROVED. Implementation faithfully delivers Stage 0 as checkpoint 0 in unified eval series. Ready to land.

---

## 2026-04-30T09:15:54Z — Orchestration checkpoint: Stage 1 readiness APPROVED + merged

**Orchestration context:** Scribe checkpoint after Linus audit + Basher runner prep. All decisions merged into `.squad/decisions.md`.

**Status:** ✅ Stage 1 training pipeline ready.
- Linus: Training input `data/stage1/fineweb2_haw/train.jsonl` (95,507 rows) audited and approved
- Basher: Training runner durable contracts established (config-relative paths, `--preflight`, run report v1, test fix for unit tests)
- Coordinator validation: compile clean, 103 tests green, git diff --check clean
- Orchestration logs + session log written to `.squad/`
- Decision inbox merged and archived

**Key decisions recorded:**
- Training input path: `data/stage1/fineweb2_haw/train.jsonl`; eval: `data/evals/fineweb2_haw/dev.jsonl`
- Eval strategy: `eval_strategy="steps"` + `eval_steps=200` (conditional on both params non-null)
- Config-relative paths contract: paths in JSON resolve from config file location
- Run report durable schema (training-run-report.v1) with git commit, file hashes, row counts

**Validator role:** No action needed; readiness checkpoint complete. Ready for compute environment preflight + Stage 1 CPT run.


---

## 2026-05-01 — Stage 0 Baseline Confirmed + T4x2 Ready

**Scribe orchestration checkpoint:** Stage 0 eval summary reviewed and finalized. Team approved for Stage 1 launch.

**Eval Outcome:**
- Hawaiian PPL: 7.92 (clean, reproducible baseline)
- Orthography tripwires: ✅ all green
- W1/English/per-source metrics: not yet reportable
- Future eval summaries should pin immutable HF revision

**Baseline Quality:** Sufficient for proceeding to Stage 1. Hawaiian text modeling established as baseline; launch with T4x2 config from Basher.

**Status:** Ready for Stage 1 training. Monitor checkpoint evals; cross-reference future metrics against this baseline (7.92 Hawaiian PPL).

---

## 2026-05-02 — GPU VRAM Optimization Analysis (Kaggle T4x2)

**Request:** Evaluate unused VRAM (8–10 GB across T4x2) and recommend allocation strategy: larger seq_len, batch, LoRA rank, or headroom?

**Analysis:**
- Current memory: ~6.5–7.5 GB/GPU = 24–28 GB total, leaving 8–10 GB headroom (realistic).
- Reviewed 4 options:
  1. **max_seq_len 2048→3072+**: Best option. Hawaiian benefits from longer context (topic coherence, rare-word patterns). Memory impact linear + predictable. Risk manageable for prototype.
  2. **per_device_batch_size 1→2**: Reject. Won't improve throughput (not DDP, only 1 GPU active). QLoRA already effective at batch=1 + grad_accum=16.
  3. **lora_rank 32→64+**: Deferred. CPT doesn't justify rank expansion; defer to Stage 2 downstream evals if needed. Overfitting risk on small corpus.
  4. **Leave headroom**: Safe but wastes capacity. Not aligned with "use all VRAM."

**Recommendation:** **Primary: max_seq_len 2048 → 3072 (50% expansion, conservative).** Adjust `gradient_accumulation_steps` 16 → 11 to keep effective batch ~32K tokens/update. Monitor first 10 steps for VRAM; revert to 2048 if OOM spike. Secondary: defer LoRA rank to Stage 2.

**Deliverable:** Decision written to `.squad/decisions/inbox/rusty-vram-tradeoff.md` with implementation path, memory breakdown, and conditional fallback strategy.

**Status:** ✅ Complete. Team can proceed with Stage 1 training and optionally apply seq_len increase for better Hawaiian language modeling quality.

---

## 2026-05-02 — Stage 2 eval gate landed (issue #23)

**Trigger:** yashasg ralph-loop dispatch on issue #23 (Stage 2 chrF/chrF++ both
directions + leakage + orthography retention).

**Files touched:**

- `code/llm_hawaii/stage2_eval.py` — new module: `chrf_corpus`,
  `chrf_both_directions`, `TranslationPair`, `load_translation_pairs`,
  `leakage_check`, `orthography_retention`, `Stage2EvalConfig`,
  `run_stage2_eval`. Schema label `stage2_eval.v1`.
- `scripts/410_stage2_eval.py` — CLI; `--self-test` smoke contract.
- `code/tests/test_stage2_eval.py` — 29 tests (chrF correctness incl. sacrebleu
  parity when available, direction separation, leakage states pass/fail/
  skipped/missing, orthography tripwires, end-to-end orchestrator, CLI smoke).
- `code/tests/fixtures/stage2_eval/{eval_pairs,predictions}.jsonl` — 5-row
  bilingual fixture (3 en→haw, 2 haw→en) with intentional wrong-ʻokina to
  exercise the retention tripwire.
- `code/llm_hawaii/__init__.py` — re-export `stage2_eval`.
- `code/llm_hawaii/evaluate.py` — flipped the stage2-chrf TODO into a pointer
  to the implementation.
- `docs/eval_pipeline.md` — chrF row now names the module + CLI.

**Architecture decisions / durable learnings:**

- **Generation is decoupled from scoring.** The gate consumes a predictions
  JSONL keyed by `pair_id` rather than loading a model. Tests run with
  zero ML deps; the CLI is a pure scorer. Whoever owns generation (Basher
  for the Stage 2 SFT runner) feeds in `{pair_id, hypothesis}`. This
  matches the W1 pattern and keeps the gate exercisable on a laptop.
- **Direction separation is structural, not a convention.** The
  `TranslationPair` dataclass validates `direction ∈ {en_to_haw,
  haw_to_en}` at construction; `chrf_both_directions` returns sibling
  dicts; nowhere does the module average across directions. This pins
  `docs/eval_pipeline.md` §3.3's "never averaged" contract in code.
- **chrF backend choice is recorded in the report**: `backend` field
  in each chrF dict carries either `pure_python_v1` or
  `sacrebleu_<version>`. Cross-run comparability requires this — a
  silent backend switch could otherwise look like a model regression.
- **sacrebleu is not pinned as a hard dep.** The pure-Python fallback
  mirrors sacrebleu's corpus-level chrF formula (clipped overlap →
  per-order P/R → F-beta=2 → arithmetic mean over effective orders).
  Verified by the `test_pure_python_matches_sacrebleu_when_available`
  parity test (skipped locally when sacrebleu absent). For
  release-tier eval, pin sacrebleu and drop the fallback; documented
  inline in the module docstring.
- **Effective-order behavior matches sacrebleu**: orders where the
  corpus has zero reference n-grams (e.g. char 6-gram on a 5-char
  reference) are dropped from the average rather than scored as 0.
  Tested explicitly.
- **Leakage check fails closed.** Missing ledger or manifest files do
  NOT silently report `pass` — the verdict becomes `fail` with status
  `missing`. `None` paths report `skipped` so cron summaries can
  distinguish "we checked and it was clean" from "we never checked".
  Also reads multiple manifest hash fields (`sha256_pair`,
  `sha256_normalized`, `sha256_normalized_haw/en`) so it survives
  Linus's manifest schema evolution.
- **Retention probe is en→haw only.** haw→en pairs would measure
  *English* orthography on the hypothesis; nonsensical for ʻokina /
  kahakō survival. Pinned by `test_haw_to_en_excluded`.
- **Wrong-ʻokina is hypothesis-side only.** A model that injects
  U+0027 / U+2018 / U+2019 / U+02BC between letters fires the
  `wrong_okina_introduced` tripwire even if the reference has none.
  Symmetric tracking would mask the regression.
- **No blocking thresholds.** Per issue #23 acceptance, numbers are
  advisory at prototype tier; the report carries an explicit advisory
  string saying so. Gate promotion to release tier is a separate
  decision.

**Validation:** 29/29 new tests green. Full suite 192/192 minus the
pre-existing torch-missing error (`test_check_runtime_capability`).
`python3 scripts/410_stage2_eval.py --self-test` exits 0 and prints a
sample report with all four chrF numbers + leakage verdict +
retention tripwires.

**Hand-off:** Basher's Stage 2 SFT runner needs to emit a predictions
JSONL keyed by `pair_id`; pointer the runner at this gate. Linus's
manifest schema for #11 already provides the hash fields the leakage
check consumes.

---

## 2026-05-01T00:19:05Z — Stage 2 Readiness Checkpoint (Eval Gate Landed)

**Team Orchestration:** Scribe session; Ralph Round 1 concluded.

**Your outcome:** Stage-2 eval gate live (issue #23). chrF + chrF++ for both en→haw and haw→en (never averaged), leakage/contamination check, Hawaiian orthography retention tripwires, 29 tests pass, full suite green.

**Team outcomes:** Frank landed Bible adapter (18 tests), Linus landed Tatoeba adapter (41 tests), Basher landed SFT trainer + Colab assessment.

**Decisions merged:** Eval gate live (generation decoupled, chrF backend recorded, direction separation structural, leakage check fails closed, no blocking CI thresholds), SFT custom collator (no TRL), Tatoeba alignment/register, Bible edition pin in JSON, Colab GPU conditional.

**Team integration points:**
- Basher (issue #11/#14) must emit SFT predictions keyed by `pair_id`.
- Linus must preserve manifest schema fields: `sha256_pair`, `sha256_normalized`, `sha256_normalized_haw`, `sha256_normalized_en` (eval gate reads these for leakage check).
- Your gate's API: takes `predictions.jsonl` keyed by `pair_id`, returns report with chrF numbers + leakage verdict + retention tripwires.

**Next:** Await SFT runner predictions from Basher; validate leakage check against pinned manifest hashes.


---

## 2026-05-01 — Stage 2 Readiness handoff [PENDING REVIEW]

**Orchestration:** Ralph's Stage 2 readiness sweep identified one remaining blocker (#19) and routed to you.

**Context:**
- Issues #18/#20/#24 complete (Linus manifest/templates, Basher lineage CI).
- **Linus flagged:** Two `haw->en` templates are in Hawaiian; please review orthography before release.
- **Frank coordination:** If Bible adapter produces new candidates, rebuild manifest with `scripts/320_build_stage2_manifest.py --execute`.

**Action needed:** Assess issue #19 and determine if it blocks Stage 2 go/no-go.

## Learnings — 2026-05 (Stage 2 scorer × manifest wiring, issue #19)

- Wired `llm_hawaii.stage2_quality.score_pair` into `scripts/320_build_stage2_manifest.py` via a new `apply_policy()` helper. Every ingested candidate now gets `alignment_confidence_tier`, `alignment_review_required`, `quality_flags`, `manual_review_reasons`, `alignment_score_components`, and `policy_version` baked onto the manifest row before schema validation.
- Manifest schema now declares those six fields as required (see MANIFEST_FIELDS). Adapter outputs (Bible, Tatoeba) intentionally do *not* carry them — the manifest builder is the single point that merges policy, so `validate_row` only ever runs against scored rows. Adjusted both adapter tests to apply the policy before validating, which matches the new contract.
- Tier→split contract: `review` and `reject` both force `split="review-pending"`, regardless of whatever the candidate originally claimed. This is the durable kill-switch that keeps the SFT emitter (`330_emit_stage2_sft_jsonl.py`) from training on quarantined rows — it already filters `alignment_review_required=true` and skips splits outside the requested set, so `review-pending` is double-belted out.
- Persisted `data/stage2/score_summary.json` from `summarise_policy()` on every `--execute`. Tier counts + flag counts + the active `policy_summary()` give the run-level diagnostic surface called out in #19's acceptance criteria.
- Hawaiian template review (Linus's flag from #20): the haw->en paraphrase `"Unuhi i kēia ʻōlelo Pelekānia mai ka ʻōlelo Hawaiʻi."` had source/target reversed — it literally reads "Translate this English speech FROM the Hawaiian language", which is grammatical nonsense for an instruction whose *input is Hawaiian*. Replaced both in `code/tests/fixtures/stage2/templates.json` and in `DEFAULT_INSTRUCTIONS` inside `scripts/330_emit_stage2_sft_jsonl.py`. Surviving haw->en paraphrases use `kēia ʻōlelo Hawaiʻi … i ka ʻōlelo Pelekānia` (Hawaiian→English direction expressed correctly), all NFC, all preserving ʻokina (U+02BB) and kahakō.
- `_make_valid_row` in `test_stage2_manifest.py` originally used 2-token sides ("Aloha honua." / "Hello world."). Once the policy gate is wired in, those trip `side_too_short` and tier=reject. Bumped to 5-token NFC phrases. If you ever see new manifest tests fail on `side_too_short` after a refactor, check the fixture token counts before the policy.
- Defaults `accept_min=0.75` / `review_min=0.55` are still appropriate for the deterministic-method sources we have (Bible verse-id, Tatoeba tmx-line both land at `accept`). Embedding-aligned sources will arrive later; the threshold knob lives in `PolicyConfig` and a bump should come with a `POLICY_VERSION` bump and a manifest re-write per the existing decisions.

## 2026-05-01 — Stage 2 Alignment-Quality Policy Integrated (Issue #19)

**Status:** IMPLEMENTED — Reviewed by Danny, merged

Rusty completed the alignment-quality policy integration into the manifest builder. Policy fields are now computed at build time, not at adapter output. Tier-to-split contract ensures review/reject rows are quarantined to `review-pending` and excluded from training. Hawaiian template fixture corrected. Policy version tracking enables future threshold changes with explainability.

**Agents notified:** Linus, Basher, Frank, Danny

---

## 2026-05-02 — Baibala 1839 historical-orthography policy review

**Task:** Decide whether 1839 Baibala rows flagged `haw_no_diacritics` stay review-pending or get a carve-out. Output: `.squad/decisions/inbox/rusty-baibala-orthography-policy.md`.

**Data points:**
- 5,823 Bible candidates in current manifest. Tiers: accept=1,732 / review=4,071 / reject=20.
- 3,956 (~68 %) flagged `haw_no_diacritics`; **3,897 carry only that flag** (no length / LID / alignment issues).
- Sampled rows confirm genuine 1839 Andrews/Bingham register (`papaaina`, `hookuu`, `hookaawale`) — pre-Pukui-Elbert convention, not OCR drift.

**Recommendation:** Narrow source-pinned, train-only carve-out. Promote review→accept iff `source==baibala-hemolele-1839` AND only flag is `haw_no_diacritics` AND no other quality issues. Force `split=train`. Tag with new `historical_orthography_exception=true` + `orthography_era="pre-pukui-elbert"`. Keep the `haw_no_diacritics` flag on the row — accept *despite* it, not by suppressing it. Bump POLICY_VERSION to v0.2.

**Guardrails:**
- Source-pinned: Tatoeba/Wiktionary/etc with `haw_no_diacritics` still go to review (extraction loss for those sources).
- Sub-cap inside the existing 30 % Bible token cap: historical-orthography rows ≤ 50 % of accepted Bible train rows AND ≤ 15 % of total parallel-train tokens. Enforced deterministically by `pair_id` hash so reruns are reproducible.
- Dev/test exclusion is non-negotiable — my eval gate's ʻokina/kahakō retention tripwires would falsely report regressions if no-diacritic references leaked in.
- Off-switch flag: `PolicyConfig.allow_historical_orthography_exception` (default True for prototype, False for release).

**Why this generalizes:** Same per-source interpretation will apply to future historical Hawaiian sources (nūpepa OCR, pre-1925 government docs). Pattern — "keep the diagnostic flag, gate the *acceptance decision* on source + register + flag-set" — is reusable. Don't add per-flag global suppressions; that path loses signal.

**Hand-off:** Linus owns the manifest-builder + scorer change. No code touched in this review by request.


## 2026-05-02 — Baibala 1839 historical-orthography policy review (COMPLETE)

**Decision:** `.squad/decisions/inbox/rusty-baibala-orthography-policy.md` → merged to `.squad/decisions.md`

**Outcome:** Recommended narrow source-pinned carve-out (train-only, no-diacritics diagnostic preserved, sub-cap + kill-switch + per-row metadata). Hand-off to Linus for implementation.

**Manifest impact:** 5,823 Bible candidates; 3,897 carry only `haw_no_diacritics` flag. Carve-out promotes review→accept under strict conditions; sub-cap ensures model still sees modern-orthography Bible signal.

**Implementation by Linus:** Completed as commit 50b89c0; POLICY_VERSION → v0.2; 1,071 historical-orthography rows accepted + 3,791 deterministically dropped by sub-cap.

**Status:** Policy merged; ready for eval-gate re-validation + diacritic retention tripwire check.

## 2026-05-03 — Stage 2 review-pending promotion gate

**Task:** Independently validate what can honestly be promoted from `split=review-pending` to `train` for the Stage 2 prototype SFT blend, without claiming a human Hawaiian line-by-line review.

**Decision artifact:** `.squad/decisions/inbox/rusty-review-pending-policy.md`

**Manifest state read (not modified):**
- 11,828 rows total; 7,148 review-pending across 4 sources.
- Andrews 1865 (1,194, all reject), Bible 1839 (5,790 rp), Kaikki (139 rp), Tatoeba (25 rp).
- Not-yet-merged candidates on disk: bible_haw1868_kjv (31,101), hk_statutes_1897 (1,103), hooilina (68).

**Per-source dispositions (durable):**
- **Andrews 1865:** stay rejected. 1–4 token headword fragments are SFT poison — collapses model into glossary mode. If we want the data, repackage as a dictionary-lookup instruction adapter, separate from the parallel pair blend.
- **Kaikki:** narrow promotion (≥3 tokens both sides, ratio in band, no `haw_nonhaw_letters_high`, no `haw_no_diacritics`). Wiktionary diacritic-stripping is *not* covered by the 1839 Baibala carve-out — different provenance, different risk.
- **Tatoeba:** promote conversational-short rows (≥2 tokens both sides, ratio in band, no other flag). The 3-token floor is too aggressive for conversational register. The 15 dev rows are frozen — eval gate's leakage check depends on it.
- **Hoʻoilina:** stay review-pending. Filename-pair alignment at paragraph level (600–3,400 HAW tokens) is too coarse for SFT supervision; KS editorial layer is `prototype_only=True / release_eligible=False`. Need a sentence-level re-segmentation adapter before training.
- **HK statutes 1897:** filtered promotion under legal sub-cap. Tighter ratio `[0.6, 1.6]`, HAW length `[25, 600]`, regex blacklist for OCR section markers (`$`, `§`, `S<digit>`). 1850/1869 pair stays inventory-only (Linus's year-mismatch).
- **Bible 1839:** no change — v0.2 historical-orthography carve-out already handled the easy promotions.
- **Bible 1868 × KJV:** merge with verse-key dedup against 1839, then subsample under the 30 % token cap.

**Acceptance criteria (reusable for future review-pending passes):**
- tier=accept OR matches a named source-pinned promotion rule.
- both sides ≥2 tokens (≥3 for dictionary sources).
- length_ratio in `[0.5, 2.5]` (legal `[0.6, 1.6]`).
- `haw_nonhaw_letters_high` clear — single best signal that HAW side is OCR garbage or English leakage.
- `haw_no_diacritics` clear, except for the source-pinned 1839 Baibala carve-out.
- prototype_only sources train under sub-caps with `release_eligible=False`, never dev/test.

**Bible cap method (the durable bit):**
1. Compute non-Bible accepted-train tokens `T_nb`.
2. `T_bible_max = (0.30 / 0.70) * T_nb` — enforces ≤30 % exactly.
3. Pool 1839-accept ∪ 1868-accept-after-dedup; sort by `sha256_pair`; take in order until budget filled.
4. Dropped rows stay in manifest with `manual_review_reasons += "dropped-by-bible-cap-v1"` so a future cap relaxation is a config change, not a re-pull.

This pattern — deterministic-hash-ordered subsample with reasoned drops kept in-manifest — generalizes to any future cap (legal, synthetic, dictionary).

**Risks I refuse to ship under:**
1. OCR section markers leaking into HK statute rows (`$2`, `S3 … feloni ame haraima` visible in row [0]–[2] of the candidate file).
2. Dictionary fragments collapsing the model to headword mode — the dominant Hawaiian-LLM regression in earlier prototypes.
3. HK 1850/1869 unresolved year-mismatch — different legislative sessions, section-id pairing would manufacture false alignments.
4. Bible cap dominance — naive 1868 merge would push Bible to ~80 % of train tokens; mitigated by step 4 above.

**Honest yield projection:** ~7,300–10,000 parallel-train pairs after this gate. Directional ≈ 2×. Does not reach 80k; NLLB mined + synthetic BT still required (matches Linus's read).

**What I did NOT claim:**
- No native-speaker line-by-line review.
- Hoʻoilina sentence-level alignment unverified.
- HK statutes not re-OCR'd; filter is triage, not a fix.
- Stratified ~50-row-per-source native-speaker sample still owed before any release-tier checkpoint.

**Hand-off:**
- Linus: owns manifest builder change + `score_summary.json` emission. I did not modify the data artifact.
- Basher: re-run Stage 2 eval gate post-promotion; confirm leakage check + ʻokina/kahakō retention green on dev.
- Frank: unblocked; nothing here depends on new acquisitions.

**Reusable pattern for future review-pending passes:** named `promotion_rule_id` per row, source-pinned promotion rules, deterministic-hash subsample for caps, drops kept in-manifest with reasons. Same shape will work for NLLB mined LaBSE thresholds and synthetic BT caps.

---

## 2026-05-02 — Stage 2 Review-Pending Promotion Policy (ACCEPTED)

**Decision filed:** `.squad/decisions.md` / Stage 2 Review-Pending Promotion Policy section

**Task:** Define deterministic source-pinned gate for Stage 2 review-pending promotion without claiming human Hawaiian line-by-line review.

**Output:** `rusty-review-pending-policy.md` (comprehensive policy doc) — filed to decisions.md as **ACCEPTED**.

### Key Policy Decisions

1. **Andrews 1865:** Stay rejected (dictionary fragments → glossary-mode failure)
2. **Kaikki:** Promote narrow subset (≥3 tokens, 0.5 ≤ ratio ≤ 2.5)
3. **Tatoeba:** Promote ~20 of 25 review rows; **dev frozen** (hard rule)
4. **Hoʻoilina:** Stay review-pending (need sentence-level re-segmentation)
5. **HK 1897:** Promote ~500–700 after OCR/legal-register filter
6. **Bible 1839/1868:** Merge 1868, subsample both under 30% cap

### Counting Algorithm (§4)

- T_nonbible = non-Bible accepted tokens
- T_bible_max = (0.30/0.70) × T_nonbible
- Bible subsample via sha256_pair order; drop excess → "dropped-by-bible-cap-v1"
- HK legal ≤ 15% of (T_nonbible + T_bible_kept)
- Dictionary ≤ 5k rows combined
- Synthetic ≤ 15% directional

Expected yield: ~7.3–10k parallel pairs (~14.6–20k directional). NLLB + synthetic BT required for 80k target.

### Handed to

- **Linus:** manifest builder implementation
- **Basher:** eval gate re-run post-promotion
- **Coordinator:** policy→implementation divergence check

**Status:** Policy ACCEPTED; implementation pending.

## 2026-05-02T00:56:01Z — Final Review Verdicts Finalized (No Action Required)

**Milestone:** Stage 2 final review verdicts completed by Danny + Basher.

**What you need to know:**
- All 33,551 review-pending rows now carry explicit `final_review_verdict` values.
- Danny's policy *consumes* your review-pending definitions; it does not amend any Rusty review rules.
- Your review gates (quality flags, alignment_review_required, source-level rights checks) are all honored in the verdict assignment.
- **No action required.** Your work is integrated and locked into the final artifact.

## 2026-05-02T04:02:17Z — Cross-agent recap: OPUS QED langid bug flagged for LaBSE pre-filter

**From:** Scribe orchestration log

**Frank OPUS finding:** QED (v2.0a, 16 pairs) is a textbook OPUS langid bug — entire en column is Russian, entire haw column is Danish. Confirmed by Frank's langid check.

**Your ask (from frank-opus decision):**
Add script-block + Hawaiian-alphabet sanity check to any future LaBSE pre-filter. Do not whitelist OPUS pairs by source-corpus alone. This prevents similar silent failures in Tier-B pipeline downstream.

