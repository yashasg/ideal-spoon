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

## 2026-04-30 — Kaʻehuikimanōopuʻuloa pages assessed as tokenizer-audit slice

Reviewed `data/raw/ulukau_nupepa/human_fetch_book_pages.txt` (Moses Manu moʻolelo, 3,223 Hawaiian words, 21 paragraphs, all NFC, ʻokina at U+02BB ×756, kahakō vowels ×614, every paragraph clears the ʻokina+kahakō ≥3 high-diacritic floor). Strong tokenizer-audit candidate: alone it meets the frozen Stage-0 minimums (≥1,500 words, ≥10 high-diacritic samples) and pairs cleanly with the earlier `human_fetch.md` landing-copy slice. Bright line held: tokenizer audit only — not W1, not eval, not training, not hashed into `eval_hashes.jsonl` without separate Hawaiian-literate review; provenance/licensing of the digitized edition still to confirm before any non-local use. Flagged single-genre stress — all one author/register — and gave practical target guidance (~5–6k words across ≥3 genres: nūpepa, modern prose, place-name/proper-noun heavy) so audit numbers are defensible, not just passing. No threshold/fingerprint changes; Linus owns conversion to the JSONL slice shape under `data/tokenizer_audit/ulukau_nupepa/`. Decision written to `.squad/decisions/inbox/rusty-kaehuikimanoopuuloa-audit-assessment.md`.
