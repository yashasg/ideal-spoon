# Rusty — History

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
