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
