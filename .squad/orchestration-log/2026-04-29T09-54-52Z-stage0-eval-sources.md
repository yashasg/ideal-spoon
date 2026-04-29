# Orchestration Log: Stage-0 Evaluation Data Source Candidates

**Timestamp:** 2026-04-29T09:54:52Z  
**Scope:** Both Rusty (NLP Researcher) and Frank (Hawaiian Data Collector) proposals on Stage-0 eval sources.  
**Scribe:** Self-logged session coordination and decision archival.

---

## Agent Outcomes

### Rusty (NLP Researcher) — `rusty-stage0-eval`

**Task:** Propose Stage-0 Hawaiian eval sources by evaluation utility (tokenizer orthography, LID, translation sanity, religious-domain overfit detection).

**Deliverables:**
- `.squad/decisions/inbox/rusty-stage0-eval-sources.md` filed
- 17-row candidate table (rows 1–17) with priority flags: "use now", "verify next", "maybe later", "avoid"
- **Recommended Stage-0 bundle:** hand-curated micro-eval (1) + hawwiki held-out (2) + hawwiktionary (3) + FineWeb-2 test (4) + Tatoeba (5) + Baibala verse sample (6)
- **Flagged absent:** FLORES / FLORES+ / FLORES-200 have no Hawaiian; explicitly marked "do not assume"
- **Flagged out-of-scope:** JW300 (ToS-blocked), hwc (Hawaiian Pidgin, not Hawaiian), Ulukau/Nupepa (prototype-private only)

**Open questions filed:**
1. Frank's earlier question (still unresolved): `global-piqa-parallel haw` vs Tatoeba as Stage-2 dev anchor — Stage-0 will touch both
2. Linus: Baibala edition pin (Hemolele 1868 vs. modern) and matched English edition (KJV vs ASV)
3. Linus: gate on Hawaiian-reader review before any quoted Stage-0 diagnostic number?
4. Verify before promoting items 7–10: `global-piqa-parallel` row count + license, NLLB-Seed coverage, UDHR Hawaiian availability, Taxi1500 Hawaiian presence
5. Paragraph-level LID re-gate on FineWeb-2 test split at Stage 0 or defer to Stage 1?

---

### Frank (Hawaiian Data Collector) — `frank-stage0-eval`

**Task:** Check access, provenance, scriptability of Stage-0 eval sources. Identify W1 (first-wave, blockers zero or trivial) sources.

**Deliverables:**
- `.squad/decisions/inbox/frank-stage0-eval-sources.md` filed
- 12-row W1 + W2 candidate table with scriptability, rights, and wave assignment
- **W1 (do now, zero blockers):**
  1. FineWeb-2 haw_Latn test (887 rows) — datasets-server rows API, verified live
  2. hawwiki held-out slice (50–100 page IDs from existing dump)
  3. eBible haw1868 + KJV anchor — one-zip PD fetch, verse-aligned bilingual probe
  4. global-piqa-parallel TSV — commonsense QA pairs, small HF file
  5. Manual-seed micro eval — 10–50 hand-written en↔haw pairs, zero fetch, fluent-review gate
- **W2 (after W1 lands):** BibleNLP corpus (verse-aligned cross-check vs eBible), Weblate software-l10n strings, Taxi1500 classification, Tatoeba (row count unverified), Internet Archive PD slice (OCR quality risk), Hawaiian Corpus Project (unclear status)
- **Avoid:** FLORES (absent), hwc (false friend), Nupepa CGI (Cloudflare-blocked), hwc (false friend), Mozilla Common Voice haw (absent), CC-100 haw (absent)

**Ground rules reaffirmed:**
- No Cloudflare/access-control bypass (Nupepa, Papakilo, HathiTrust, Chronicling America deferred)
- No FLORES Hawaiian (does not exist)
- `hwc` ≠ Hawaiian (Hawaiian Pidgin / Hawaiʻi Creole English, ISO `haw_Latn` only)
- FineWeb-2 adapters already landed (scripts 105 / 205)
- Stage-0 eval rows hash into `eval_hashes.parquet` *before* training ingest (contamination rule)

**Open questions filed:**
1. Linus: FineWeb-2 W1 eval-only use — accept wrapper ODC-By posture without per-URL allow-list, or resolve per-URL rights first? (W1 is narrower question; W2 training side is separately blocked)
2. Rusty: minimum row count + register split for manual-seed micro eval before it's trusted signal vs. smoke test?
3. Coordinator / Linus: confirm `docs/data-pipeline.md` Stage-2 §300 gets "FLORES has no Hawaiian" fix before Stage-0 eval-hash work starts

---

## Reconciliation & Integration

### Alignment

**Rusty's recommended Stage-0 bundle (6 sources) ⊂ Frank's W1 wave (5 sources):**

| Rusty | Frank W1 | Status |
|-------|----------|--------|
| 1. Hand-curated orthography micro-eval | 5. Manual-seed micro eval | ✓ **Match** — Rusty calls it orthography micro-eval; Frank calls it manual-seed micro eval; same artifact |
| 2. hawwiki held-out slice | 2. hawwiki held-out slice | ✓ **Match** |
| 3. hawwiktionary headword + example | (not in W1, noted as "use now") | ✓ **Match** — Frank defers hawwiktionary to W2 research-gated but it's collectable; Rusty flags it "use now" |
| 4. FineWeb-2 haw_Latn test split | 1. FineWeb-2 haw_Latn test (887 rows) | ✓ **Match** — verified 887 rows, live test |
| 5. Tatoeba haw↔eng | (not in W1, noted as "verify row count") | ⚠️ **Rusty "use now"; Frank W2 (row count unverified)** — Frank's caution is justified; needs row-count confirmation before promotion |
| 6. Baibala Hemolele verse sample + KJV/ASV | 3. eBible haw1868 + KJV anchor | ✓ **Match** — PD verse-aligned bilingual probe |

**Rusty W2 / "verify next" table entries partially overlap Frank W2:**
- `global-piqa-parallel haw` (Rusty "verify next", Frank W1) — Frank confirms trivial fetch, small file; Rusty notes license needs verification; **Frank assessment is stronger**
- Taxi1500 Hawaiian (Rusty "verify next", Frank W2) — both flag as Bible-derived classification diagnostic
- BibleNLP corpus (Frank W2 listed, Rusty omitted) — Frank proposes as cross-check vs eBible via verse-ID join; Rusty does not list it

### Decision Points

1. **hawwiktionary headword + example slice:** Rusty flags "use now"; Frank defers to W2 research-gated. Action: **Collect on W1 if `103_collect_hawwiktionary.py` exists and dump is available**, else defer. (Frank notes it's "use now" in Rusty's bundle but doesn't list in W1 wave explicitly.)

2. **Tatoeba haw↔eng row count:** Rusty flags "use now"; Frank flags "verify row count" as a W2 gate. Action: **Confirm live row count before finalizing Stage-0 harness.** If n < 10 pairs, memorization risk is too high for eval; tag `register=short-tail` and hold-out aggressively.

3. **`global-piqa-parallel haw` license verification:** Both flag this. Frank's W1 assessment assumes license is OK; Rusty adds "License needs verification before Stage-0 use". Action: **Verify license before loading into harness.**

4. **Linus rights decision on FineWeb-2 W1 eval:** Frank asks — is wrapper ODC-By sufficient for eval-only use, or require per-URL allow-list first? Open for Linus.

5. **Hawaiian-reader review gate on Stage-0 quoted numbers:** Rusty asks whether hand-curated micro-eval needs a Hawaiian-reader pass before any quoted diagnostic. Open for Linus.

6. **Paragraph-level LID re-gate timing:** Rusty proposes Stage 0; open for design decision.

---

## Next Steps (Out of Scope, Coordinator Routes)

- **Linus** (Hawaiian Data Licensing Lead): FineWeb-2 eval-only rights posture, Baibala edition pin, quoted-number review gate
- **Rusty** (NLP Researcher): manual-seed micro eval minimum row count + register split, Tatoeba row-count confirmation
- **Frank** (Hawaiian Data Collector): confirm `global-piqa-parallel` license; (conditional) verify Tatoeba row count
- **Coordinator**: route paragraph-level LID re-gate decision to Livingston (eval architect) or Danny (lead)

---

## Summary

✅ **Rusty** delivered a 17-row candidate table organized by evaluation utility (tokenizer, LID, translation sanity, religious-overfit detection) with priority flags. Recommended 6-source Stage-0 bundle is lightweight and load-bearing for prototype feedback loops.

✅ **Frank** delivered a 12-row candidate table organized by wave (W1 / W2 / Avoid) with access verification, scriptability assessment, and rights caveats. W1 wave (5 sources, zero blockers) is immediately actionable.

✅ **Alignment:** Rusty's recommended bundle largely maps to Frank's W1 + "use now" flags. 3 minor tensions (hawwiktionary timing, Tatoeba row-count risk, license verification) and 1 open Linus decision (eval-only rights posture for FineWeb-2) remain. No blocking conflicts.

✅ **Avoid list** (FLORES absent, hwc false-friend, Cloudflare-gated sources, JW300 ToS-blocked) is consistent across both agents and correctly flags what *not* to pursue.

**Orchestration**: Both agents' inbox decisions merged below. Open questions routed to responsible parties. Stage-0 first wave is ready for harness integration pending Linus rights + review-gate decisions.
