# Agent History Summaries

> Quick reference guide for large agent history files (>12KB). Each agent's full history is in `.squad/agents/{agent}/history.md`.

---

## Linus (Data Engineer) — Stage-2 Canonicalization & Adapter Consolidation

**Latest:** Round 17 canonical helper consolidation (2026-05-03)

**Recent focus:**
- **R17:** Consolidated canonicalization rules into single source of truth (`code/llm_hawaii/stage2_canonical.py`); 25 files refactored; 60/60 tests pass
- **R16:** Locked EN-side hash determinism contract; 7 explicit canonicalization tests; FLORES+ and Common Voice probed RED/SKIP
- **R15:** Hardened Stage-2 dedup edge cases; near-dupe invisible control stripping; fallback exact-pair ordering now canonical-source aware
- **R14:** Wired train-side eval-contamination filter; `--eval-hashes` enforcing gate before dedup

**Key artifacts:**
- `code/llm_hawaii/stage2_canonical.py` — Locked canonicalization API (canonical_en, canonical_haw, canonical_pair)
- `scripts/320_build_stage2_manifest.py` — Manifest builder with backward-compatible wrapper APIs
- Adapters: Weblate (scripts/346), Global-PIQA (347), Taxi1500 (348), Tatoeba refresh (349)
- Test suite: 60/60 passing; manifest dry-run stable at 37,084 rows

**Decision locked:** Future Stage-2 adapters MUST import canonical helpers from `stage2_canonical.py`. No local canonicalization.

---

## Basher (ML Infrastructure) — A100 Training Telemetry & Setup

**Latest:** Stage-1 A100 loss plateau diagnosis (2026-05-03)

**Recent focus:**
- **R-latest:** A100 loss telemetry near epoch 1 (loss ~1.17–1.23, grad_norm ~0.35) is expected local movement, not a plateau. Current config more conservative than documented recipe.
- **Setup:** Kaggle environment pip conflict handling; CPU torch wheel detection and replacement; HF Trainer eval batch sizing on memory-constrained hardware
- **CLM collator:** Fixed variable-length `labels` batch padding issue; wrapper strips pre-tokenized labels before HF collator derivation

**Key learnings (11 major):**
- CPU torch trap on Kaggle: detect `+cpu` suffix in `torch.__version__`, replace with CUDA wheel
- HF Trainer eval default batch=8 OOMs Llama-3.1-8B (vocab 128k, seq 2048); set `per_device_eval_batch_size=1`
- `pip check` strictness pattern: `strict_pip_check = args.strict_pip_check or (not args.no_venv)` — venv strict, shared-env lenient
- Fake inner collator pattern for testing: replace with minimal fake that implements real pad+label semantics, not just mock interception

**Key files:** `scripts/setup_training.py`, `docs/kaggle-t4x2-setup.md`, `code/tests/test_data.py`

---

## Rusty (Review & Eval) — W1 JSONL Evaluation & Contamination

**Latest:** W1 Stage 0 JSONL-only implementation review [APPROVED] (2026-04-30)

**Recent focus:**
- **W1 JSONL:** Strict accepted-row gates (NFC, U+02BB ʻokina only, item_id required); JSONL-specific report fields (`jsonl_sha256`, `schema_version_seen`)
- **Hash stability:** `w1_suite_sha256` over sorted (item_id, sha256_normalized) pairs; stable under row reorder
- **Contamination:** Reviewing eval ledger schemas and cross-project contamination patterns

**Key learnings (5 major):**
- W1 JSONL field validation chain and exit code propagation (exit 2 invalid, 0 otherwise)
- Normalized hash stability across sorted pair sequences
- Strict ʻokina orthography gates for accepted rows vs. loose drafts/reviewed

**Spot checks:** JSONL-only wiring, orthographic gates, hash stability, exit propagation, docs/test alignment — all ✅

---

## Frank (Data Collection & Curation) — Hawaiian Data Source Exploration

**Latest:** Cross-agent Stage-2 dedup policy update (2026-05-03)

**Recent focus:**
- **Source exploration:** License probes, feasibility assessments, rights/availability tracking
- **Source hierarchy:** Hoʻoilina > Bible, Wikimedia CX > OPUS-Wikimedia, Tatoeba (canonical) > OPUS-Tatoeba, Baibala 1868 > other editions
- **Adapters:** Weblate (permissive-only), Global-PIQA (eval-only), Taxi1500 (eval-only), Tatoeba refresh
- **Contamination:** Understanding cross-edition and cross-source dedup rules

**Key learnings (28 major):**
- License-first probes: YELLOW (conditional), RED (blocked), EVAL-only (restricted routing) verdicts
- Source priority rules for dedup: provenance (CX > mirrors), diversity (Hoʻoilina > Bible), standardization (newer editions)
- Permissive-only policies: MIT, Apache, BSD, MPL, CC0, CC-BY; GPL/AGPL/LGPL/CC-BY-SA/missing blocked
- Network-gated adapters: TOS snapshot pinning, exact dataset pins, local-file-only execute gates

**Tech stack:** Python data tooling (requests, trafilatura, scrapy, yt-dlp, datasketch, cdx_toolkit, internetarchive)

---

## Danny (SFT Templates & Policy) — SFT & Model Training Policy

**Latest:** SFT template finalization & review (recent)

**Recent focus:**
- **SFT generation:** 25 template styles, 11 finalizer tests, final-review-verdict policy gates
- **Training policy:** Stage-1 base CPT/DAPT, Stage-2 SFT merge with contamination filtering, review-pending caps
- **Ledger routing:** Final-review-verdicts on non-Bible rows, promotion gates for review-tier candidates

**Key learnings (15 major):**
- SFT template emission with TF syntax; template indexing and collation
- Stage-1 loss expectations: constant_with_warmup scheduler, bf16, LoRA r32/α64, ~1.2 late-epoch train loss is normal
- Non-Bible growth constraint: 31,679 review-pending Bible rows cannot promote until non-Bible grows ~2.3×

---

## File Sizes & Recommendations

| Agent | History Size | Entries | Status |
|-------|-------------|---------|--------|
| Linus | 36 KB | 20 | Active — R17 canonical consolidation |
| Basher | 84 KB | 29 | Active — A100 training diagnostics |
| Rusty | 140 KB | 38 | Active — W1 JSONL eval review |
| Frank | 168 KB | 46 | Active — Source exploration & curation |
| Danny | 36 KB | 7 | Active — SFT policy finalization |
| Livingston | 24 KB | 12 | Recent — compute cost tracking |

---

## Next Actions (From History)

1. **Linus:** End-to-end dry-run smoke harness or source-coverage gap analysis (post-R17)
2. **Basher:** Finish A100 2-epoch run, evaluate Stage-1 gates before Stage-2 decision
3. **Rusty:** Continue W1 eval ledger schema validation across projects
4. **Frank:** Execute TOS snapshot pinning and discovery runs for Weblate + Tatoeba refresh
5. **Danny:** Finalize non-Bible growth strategy to unblock Bible promotion tier
