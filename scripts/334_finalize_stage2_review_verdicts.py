#!/usr/bin/env python3
"""
334_finalize_stage2_review_verdicts.py

Finalize review verdicts for every row in reviewed_stage2_manifest_final_capped.jsonl.

Adds four fields to every row:
  - final_review_status   : "accepted" | "finalized_excluded" | "finalized_deferred"
  - final_review_verdict  : source-specific verdict token (no row may be empty/pending)
  - final_review_reason   : human-readable reason string
  - final_review_pass_id  : "stage2-finalized-reviews-20260501"

Review-pending verdict logic (per source):
  Bible 1839:
    - alignment_confidence_tier == "reject"  → bible-quality-reject
    - otherwise (accept / review tier)       → bible-cap-overflow
  Bible 1868 (no confidence tier):
    - all                                    → bible-cap-overflow
  HK 1897:
    - "dropped-by-hk-legal-cap" in manual_review_reasons → hk-legal-cap-overflow
    - else                                               → hk-quality-reject
  Andrews:   → andrews-dictionary-fragment-rejected
  Hoʻoilina: → hooilina-alignment-pending  (finalized_deferred)
  Kaikki:    → kaikki-quality-reject
  Tatoeba:   → tatoeba-quality-reject

Output:
  data/stage2/reviewed_stage2_manifest_finalized_reviews.jsonl
  data/stage2/reports/stage2_finalized_review_verdicts_20260501.json
"""

import json
import pathlib
import datetime
from collections import Counter

PASS_ID = "stage2-finalized-reviews-20260501"

MANIFEST_IN  = pathlib.Path("data/stage2/reviewed_stage2_manifest_final_capped.jsonl")
MANIFEST_OUT = pathlib.Path("data/stage2/reviewed_stage2_manifest_finalized_reviews.jsonl")
REPORT_OUT   = pathlib.Path("data/stage2/reports/stage2_finalized_review_verdicts_20260501.json")

# ── per-source verdict helpers ─────────────────────────────────────────────

def _verdict_bible_1839(row):
    tier = row.get("alignment_confidence_tier")
    if tier == "reject":
        return (
            "finalized_excluded",
            "bible-quality-reject",
            "Excluded: alignment_confidence_tier=reject (quality gate: side_too_short / "
            "length_ratio_extreme / haw_nonhaw_letters_high). Cap would also exclude this row.",
        )
    # accept or review tier — cap is the binding constraint
    return (
        "finalized_excluded",
        "bible-cap-overflow",
        "Excluded: passed quality tier='{}' but exceeds fixed-point Bible cap "
        "(≤30% of final train tokens; B_max=6N/11). Sorted by sha256_pair; "
        "this row fell outside the kept prefix.".format(tier or "unknown"),
    )


def _verdict_bible_1868(row):
    return (
        "finalized_excluded",
        "bible-cap-overflow",
        "Excluded: Bible 1868 verse-id adapter row; exceeds fixed-point Bible cap "
        "(≤30% of final train tokens; B_max=6N/11). Only 25 of 20,852 net-new "
        "1868 verses fit within cap.",
    )


def _verdict_hk(row):
    reasons = row.get("manual_review_reasons") or []
    reasons_str = " ".join(reasons)
    if any("dropped-by-hk-legal-cap" in r for r in reasons):
        return (
            "finalized_excluded",
            "hk-legal-cap-overflow",
            "Excluded: row passed hk1897-legal-clean-v1 quality filter but exceeds "
            "fixed-point HK legal-register cap (≤15% of final train tokens; H_max=3N/11). "
            "Only 5 of 747 eligible HK rows fit within cap.",
        )
    # quality filter failure
    return (
        "finalized_excluded",
        "hk-quality-reject",
        "Excluded: failed hk1897 quality filters ({}). "
        "Did not reach cap-evaluation stage.".format(reasons_str or "no reasons recorded"),
    )


def _verdict_andrews(row):
    flags = ", ".join(row.get("quality_flags") or []) or "none recorded"
    return (
        "finalized_excluded",
        "andrews-dictionary-fragment-rejected",
        "Rejected under Rusty §1.1 quality gate: Andrews 1865 entries are "
        "dictionary-fragment alignment type; unsuitable for SFT. "
        "Quality flags: {}. All 1,194 Andrews rows rejected — "
        "0 meet minimum token count for SFT pairing.".format(flags),
    )


def _verdict_hooilina(row):
    alignment_type = row.get("alignment_type", "")
    if alignment_type == "parallel-sentence":
        # Sentence-level row that didn't pass promotion gate
        flags = ", ".join(row.get("quality_flags") or []) or "none recorded"
        return (
            "finalized_excluded",
            "hooilina-sentence-quality-reject",
            "Excluded: Hoʻoilina sentence-level paragraph pair failed promotion gate "
            "(min tokens / ratio / dedup). "
            "Quality flags: {}. Prototype-only; re-alignment may recover.".format(flags),
        )
    # Default: paragraph/section-level row — deferred pending W1 native review
    return (
        "finalized_deferred",
        "hooilina-para-deferred",
        "Deferred: Hoʻoilina paragraph/section-level row superseded by sentence-level "
        "candidate pipeline. Original section alignment not verified at sentence level. "
        "Requires Hawaiian-literate (W1) native review per Rusty §1.4 before any "
        "train promotion. 68 rows held; release_eligible=false (KS editorial layer).",
    )


def _verdict_kaikki(row):
    flags = ", ".join(row.get("quality_flags") or []) or "none recorded"
    tier  = row.get("alignment_confidence_tier") or "unknown"
    return (
        "finalized_excluded",
        "kaikki-quality-reject",
        "Excluded: Kaikki/Wiktionary entry failed stage2 quality gate "
        "(tier={}, flags={}). Does not meet Rusty §1.1 minimum token / "
        "diacritic / ratio criteria for SFT inclusion.".format(tier, flags),
    )


def _verdict_tatoeba(row):
    flags = ", ".join(row.get("quality_flags") or []) or "none recorded"
    return (
        "finalized_excluded",
        "tatoeba-quality-reject",
        "Excluded: Tatoeba sentence pair failed stage2 quality gate "
        "(tier=reject, flags={}). Does not meet minimum token / "
        "diacritic criteria.".format(flags),
    )


def _verdict_phrase_book(row):
    flags = ", ".join(row.get("quality_flags") or []) or "none recorded"
    reasons = " ".join(row.get("manual_review_reasons") or [])
    return (
        "finalized_excluded",
        "phrase-book-1881-quality-reject",
        "Excluded: Bishop 1881 Hawaiian Phrase Book row failed "
        "phrase-book-1881-clean-v1 promotion gate "
        "(alignment_type / token band / ratio / nonhaw / dedup). "
        "Quality flags: {}. Reasons: {}.".format(flags, reasons or "none"),
    )


def _verdict_hk_constitution_1852(row):
    reasons = row.get("manual_review_reasons") or []
    if any("dropped-by-hk-legal-cap" in r for r in reasons):
        return (
            "finalized_excluded",
            "hk-legal-cap-overflow",
            "Excluded: row passed hk1852-legal-clean-v1 quality filter but exceeds "
            "fixed-point HK legal-register cap (≤15% of final train tokens; H_max=3N/11). "
            "HK 1852 constitution rows compete with HK 1897 statutes rows within shared cap.",
        )
    return (
        "finalized_excluded",
        "hk-quality-reject",
        "Excluded: HK Constitution 1852 row failed quality filters ({}). "
        "Did not reach cap-evaluation stage.".format(
            " ".join(reasons) or "no reasons recorded"
        ),
    )


def _verdict_gospel_john_1854(row):
    reasons = row.get("manual_review_reasons") or []
    if any("dropped-by-bible-cap" in r for r in reasons):
        return (
            "finalized_excluded",
            "bible-cap-overflow",
            "Excluded: Gospel of John 1854 verse-id adapter row exceeds fixed-point "
            "Bible cap (≤30% of final train tokens; B_max=6N/11). Row competes in shared "
            "Bible pool with Baibala 1839/1868.",
        )
    return (
        "finalized_excluded",
        "gospel-john-1854-quality-reject",
        "Excluded: Gospel of John 1854 row failed quality filters ({}). "
        "Did not reach cap-evaluation stage.".format(
            " ".join(reasons) or "no reasons recorded"
        ),
    )


# ── verdict dispatch for train/dev ─────────────────────────────────────────

_TRAIN_REASONS = {
    "baibala-hemolele-1839":            "Promoted to train: Bible 1839 verse accepted by quality gate and selected within fixed-point Bible cap (B_max=6N/11, ≤30% share).",
    "baibala-hemolele-1868":            "Promoted to train: Bible 1868 verse-id adapter; accepted within fixed-point Bible cap (≤30% share).",
    "hk_statutes_1897":                 "Promoted to train: HK 1897 statute pair passed hk1897-legal-clean-v1 quality filter and selected within fixed-point HK cap (H_max=3N/11, ≤15% share). alignment_review_required overridden by promotion rule.",
    "hk_constitution_1852":             "Promoted to train: HK 1852 constitution section passed hk1852-legal-clean-v1 quality filter and selected within shared fixed-point HK legal cap (H_max=3N/11, ≤15% share pooled with hk_statutes_1897). prototype_only=true.",
    "gospel_john_1854":                 "Promoted to train: Gospel of John 1854 verse passed gospel-john-1854-verse-id-v1 quality filter (verse-key deduped against Baibala 1839/1868) and selected within fixed-point Bible cap (B_max=6N/11, ≤30% share).",
    "kaikki-haw-en-wiktionary":         "Promoted to train: Kaikki/Wiktionary entry passed stage2 quality gate (Rusty §1.1); accepted without cap constraint.",
    "tatoeba":                          "Promoted to train: Tatoeba sentence pair passed stage2 quality gate; accepted without cap constraint.",
    "andrews-1865-en-haw-vocab-appendix": "ERROR: Andrews row in train — not expected.",
    "hooilina":                         "Promoted to train: Hoʻoilina actual sentence pair passed hooilina-sentence-v2 quality gate (alignment_type=parallel-sentence, haw_tok in [3,80], en_tok in [3,80], ratio[0.5,2.5]). Prototype-only; KS editorial layer; alignment_review_required=true.",
    "ia-hawaiian-phrase-book-1881":     "Promoted to train: Bishop 1881 Hawaiian Phrase Book phrase pair passed phrase-book-1881-clean-v1 quality gate (alignment_type=phrase-pair, single-line + sentence-terminator + Hawaiian-morphology gate, haw_tok in [1,40] en_tok in [1,40] ratio[0.25,4.0] nonhaw<=10%). U.S. public domain (pre-1928); release_eligible=true; uncapped non-Bible/non-HK source. alignment_review_required=true (1881 orthography, OCR-stripped diacritics).",
}

_DEV_REASONS = {
    "tatoeba": "Frozen dev: Tatoeba sentence pair; dev split frozen per Rusty §1.4. No promoted rows may enter dev.",
}


# ── main ───────────────────────────────────────────────────────────────────

def finalize_row(row):
    row = dict(row)  # shallow copy
    split  = row["split"]
    source = row["source"]

    if split == "train":
        row["final_review_status"]  = "accepted"
        row["final_review_verdict"] = "train-ready"
        row["final_review_reason"]  = _TRAIN_REASONS.get(source, "Promoted to train.")
        row["final_review_pass_id"] = PASS_ID

    elif split == "dev":
        row["final_review_status"]  = "accepted"
        row["final_review_verdict"] = "frozen-dev"
        row["final_review_reason"]  = _DEV_REASONS.get(source, "Frozen in dev split.")
        row["final_review_pass_id"] = PASS_ID

    elif split == "review-pending":
        if source == "baibala-hemolele-1839":
            status, verdict, reason = _verdict_bible_1839(row)
        elif source == "baibala-hemolele-1868":
            status, verdict, reason = _verdict_bible_1868(row)
        elif source == "hk_statutes_1897":
            status, verdict, reason = _verdict_hk(row)
        elif source == "andrews-1865-en-haw-vocab-appendix":
            status, verdict, reason = _verdict_andrews(row)
        elif source == "hooilina":
            status, verdict, reason = _verdict_hooilina(row)
        elif source == "kaikki-haw-en-wiktionary":
            status, verdict, reason = _verdict_kaikki(row)
        elif source == "tatoeba":
            status, verdict, reason = _verdict_tatoeba(row)
        elif source == "ia-hawaiian-phrase-book-1881":
            status, verdict, reason = _verdict_phrase_book(row)
        elif source == "hk_constitution_1852":
            status, verdict, reason = _verdict_hk_constitution_1852(row)
        elif source == "gospel_john_1854":
            status, verdict, reason = _verdict_gospel_john_1854(row)
        else:
            raise ValueError(f"Unknown source for review-pending row: {source!r}")

        row["final_review_status"]  = status
        row["final_review_verdict"] = verdict
        row["final_review_reason"]  = reason
        row["final_review_pass_id"] = PASS_ID

    else:
        raise ValueError(f"Unknown split value: {split!r}")

    return row


def validate(rows_out):
    """Hard-assert structural invariants; raise on first violation."""
    total = len(rows_out)
    splits   = Counter(r["split"]  for r in rows_out)
    verdicts = Counter(r["final_review_verdict"] for r in rows_out)

    # No row may be missing required fields
    for r in rows_out:
        for field in ("final_review_status", "final_review_verdict",
                      "final_review_reason", "final_review_pass_id"):
            v = r.get(field)
            assert v and v.strip(), f"Missing/empty {field} in row {r['pair_id']}"

    # No verdict may be pending/unknown
    bad_verdicts = [v for v in verdicts if v in ("", "unknown", "pending", None)]
    assert not bad_verdicts, f"Forbidden verdicts found: {bad_verdicts}"

    # Split counts are self-consistent
    assert splits["train"] > 0, "Expected at least 1 train row"
    assert splits["dev"] == 15, f"Dev count: {splits['dev']} != 15 (Tatoeba dev frozen)"
    assert splits["train"] + splits["dev"] + splits["review-pending"] == total, \
        "Split counts don't sum to total"

    # No Hoʻoilina dev rows (hard rule: prototype-only, no dev/test)
    hooilina_dev = [r for r in rows_out
                    if r["source"] == "hooilina" and r["split"] == "dev"]
    assert not hooilina_dev, f"Hoʻoilina rows must never enter dev: found {len(hooilina_dev)}"

    # All hooilina train rows must have train-ready verdict and prototype_only=True
    hooilina_train = [r for r in rows_out
                      if r["source"] == "hooilina" and r["split"] == "train"]
    for r in hooilina_train:
        assert r["final_review_verdict"] == "train-ready", \
            f"Hoʻoilina train row has non-train-ready verdict: {r['final_review_verdict']}"
        assert r.get("prototype_only") is True, \
            f"Hoʻoilina train row missing prototype_only=True: {r['pair_id']}"
        assert r.get("release_eligible") is False, \
            f"Hoʻoilina train row has release_eligible=True: {r['pair_id']}"

    # Paragraph-level hooilina rows must NOT be in train
    hooilina_para_train = [r for r in rows_out
                           if r["source"] == "hooilina"
                           and r.get("alignment_type") == "parallel-doc"
                           and r["split"] == "train"]
    assert not hooilina_para_train, \
        f"Hoʻoilina paragraph rows must never be train: found {len(hooilina_para_train)}"

    # Bible cap check: recompute from artifact
    bible_sources = {"baibala-hemolele-1839", "baibala-hemolele-1868"}
    hk_source     = "hk_statutes_1897"
    train_rows    = [r for r in rows_out if r["split"] == "train"]

    def _tok(r):
        t = r.get("text_en", "") or ""
        h = r.get("text_haw", "") or ""
        return len(t.split()) + len(h.split())

    total_train_tok = sum(_tok(r) for r in train_rows)
    bible_tok = sum(_tok(r) for r in train_rows if r["source"] in bible_sources)
    hk_tok    = sum(_tok(r) for r in train_rows if r["source"] == hk_source)

    if total_train_tok > 0:
        bible_share = bible_tok / total_train_tok
        hk_share    = hk_tok    / total_train_tok
        assert bible_share <= 0.30 + 1e-6, \
            f"Bible share {bible_share:.4%} exceeds 30% cap"
        assert hk_share    <= 0.15 + 1e-6, \
            f"HK share {hk_share:.4%} exceeds 15% cap"
    else:
        bible_share = hk_share = 0.0

    return splits, verdicts, {
        "total": total,
        "train": splits["train"],
        "dev": splits["dev"],
        "review_pending": splits["review-pending"],
        "bible_share": bible_share,
        "hk_share": hk_share,
        "hooilina_train": len(hooilina_train),
    }


def main():
    rows_in = [json.loads(l) for l in MANIFEST_IN.open()]
    print(f"Loaded {len(rows_in)} rows from {MANIFEST_IN}")

    rows_out = [finalize_row(r) for r in rows_in]
    print("Finalized verdicts.")

    # Validate
    splits, verdicts, vinfo = validate(rows_out)
    print("Validation passed.")
    print(f"  Total: {vinfo['total']}  train={vinfo['train']}  dev={vinfo['dev']}  "
          f"review-pending={vinfo['review_pending']}")

    # Write manifest
    MANIFEST_OUT.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST_OUT.open("w") as fh:
        for r in rows_out:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Wrote {len(rows_out)} rows → {MANIFEST_OUT}")

    # Build report
    verdict_breakdown = {}
    sources = sorted({r["source"] for r in rows_out})
    for src in sources:
        src_rows = [r for r in rows_out if r["source"] == src]
        by_verdict = {}
        for r in src_rows:
            v = r["final_review_verdict"]
            by_verdict[v] = by_verdict.get(v, 0) + 1
        verdict_breakdown[src] = {
            "total":    len(src_rows),
            "by_split": dict(Counter(r["split"] for r in src_rows)),
            "by_verdict": by_verdict,
        }

    report = {
        "report_type":       "stage2_finalized_review_verdicts",
        "generated_at":      datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "pass_id":           PASS_ID,
        "manifest_in":       str(MANIFEST_IN),
        "manifest_out":      str(MANIFEST_OUT),
        "total_rows":        len(rows_out),
        "split_counts":      dict(splits),
        "verdict_counts":    dict(verdicts),
        "source_breakdown":  verdict_breakdown,
        "validation": {
            "total_rows":               vinfo["total"],
            "train_count":              vinfo["train"],
            "dev_count":                vinfo["dev"],
            "review_pending_count":     vinfo["review_pending"],
            "sft_eligible_rows":        vinfo["train"] + vinfo["dev"],
            "no_missing_fields":        True,
            "no_pending_verdicts":      True,
            "no_hooilina_dev_rows":     True,
            "hooilina_train_count":     vinfo["hooilina_train"],
            "bible_actual_share":       round(vinfo["bible_share"], 6),
            "hk_actual_share":          round(vinfo["hk_share"], 6),
            "caps_pass":                True,
        },
        "verdict_legend": {
            "train-ready":                         "Accepted; included in SFT training set.",
            "frozen-dev":                          "Accepted; frozen in dev set (Rusty §1.4).",
            "bible-cap-overflow":                  "Excluded: passed quality but exceeded fixed-point Bible cap (≤30% of final train tokens).",
            "bible-quality-reject":                "Excluded: failed quality gate (alignment_confidence_tier=reject) independent of cap.",
            "hk-legal-cap-overflow":               "Excluded: passed hk1897-legal-clean-v1 filter but exceeded fixed-point HK legal-register cap (≤15%).",
            "hk-quality-reject":                   "Excluded: failed hk1897 quality filters (ratio / length bounds).",
            "andrews-dictionary-fragment-rejected": "Rejected under Rusty §1.1: dictionary-fragment SFT unsuitable; all 1,194 rows fail minimum token count.",
            "hooilina-para-deferred":               "Deferred: Hoʻoilina paragraph/section-level row superseded by sentence-level pipeline; W1 native review required (Rusty §1.4).",
            "hooilina-sentence-quality-reject":     "Excluded: Hoʻoilina sentence-level paragraph pair failed promotion gate (tokens/ratio/dedup).",
            "kaikki-quality-reject":               "Excluded: Kaikki/Wiktionary entry failed stage2 quality gate.",
            "tatoeba-quality-reject":              "Excluded: Tatoeba pair failed stage2 quality gate.",
            "phrase-book-1881-quality-reject":     "Excluded: Bishop 1881 Hawaiian Phrase Book row failed phrase-book-1881-clean-v1 promotion gate (alignment type / token band / ratio / nonhaw / dedup).",
        },
    }

    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_OUT.open("w") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    print(f"Wrote report → {REPORT_OUT}")

    # Summary table
    print()
    print("=== Verdict Summary ===")
    for v, cnt in sorted(verdicts.items(), key=lambda x: -x[1]):
        print(f"  {v:45s}  {cnt:6d}")
    print()
    print(f"  {'TOTAL':45s}  {len(rows_out):6d}")


if __name__ == "__main__":
    main()
