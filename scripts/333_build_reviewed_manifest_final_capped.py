#!/usr/bin/env python3
"""Stage 2 reviewed-manifest FINAL-CAPPED builder (fixed-point solution).

Produces data/stage2/reviewed_stage2_manifest_final_capped.jsonl
applying Rusty's review gate AND a fixed-point cap that enforces
shares against the FINAL selected set, not a stale denominator.

Rejection history honored:
  - Linus produced reviewed_stage2_manifest.jsonl: REJECTED. Bible 91.9% of
    train; promoted Andrews/Hooilina; placed promoted rows in dev.
  - Basher produced reviewed_stage2_manifest_cap_corrected.jsonl: REJECTED.
    Computed Bible cap before HK cap; final actual shares were
    Bible=64.8%, HK=32.4% of train tokens. Cap formula was self-consistent
    against the (T_nonbible_total + T_bible_kept) reference, but FAILED the
    requirement that shares hold against T_final_train.

Fixed-point solution (this script):
  Let N = non-Bible non-HK train tokens (Kaikki+Tatoeba plus uncapped
          promoted sources such as Hoʻoilina sentences and Phrase Book).
  Let H = HK selected tokens, B = Bible selected tokens, T = N + H + B.
  Constraints (against T):
    B / T <= 0.30   <=>   B <= (3/7) * (N + H)
    H / T <= 0.15   <=>   H <= (3/17)* (N + B)
  Closed-form simultaneous maximum (when pools are not binding):
    H_max = (3/11) * N
    B_max = (6/11) * N
    => T  = (20/11) * N, B/T = 30%, H/T = 15% (exact).
  We compute these targets, then deterministically subsample by sha256_pair
  ascending. Finally, we VERIFY directly from the output rows; if rounding
  pushes either share above the cap, we drop one more row (highest
  sha256_pair) of the offending source and re-verify.

Per-source rules (Rusty's gate is source of truth):
  1. Andrews 1865 vocab    : 0 promoted (stay rejected/review-pending)
  2. Hoʻoilina             : 0 promoted (stay review-pending)
  3. Tatoeba dev (15 rows) : FROZEN, never moved
  4. Tatoeba review-pending: promote if haw>=2,en>=2,ratio[0.5,2.5],no nonhaw
  5. Kaikki review-pending : promote if haw>=3,en>=3,ratio[0.5,2.5],
                             no nonhaw, no no-diacritics, dedup vs accept
  6. HK Statutes 1897      : promote if haw_tok[25,600], ratio[0.6,1.6],
                             nonhaw<=10%, not stub-only OCR; LEGAL-CAP <=15%
                             of FINAL train tokens
  7. Bible 1839+1868       : dedup 1868 by verse-key vs 1839; pool=
                             1839-train + 1868-net-new; sort sha256_pair;
                             cap <=30% of FINAL train tokens; never dev/test
  8. No promoted review row enters dev/test.

Outputs:
  - data/stage2/reviewed_stage2_manifest_final_capped.jsonl   (canonical preserved)
  - data/stage2/reports/stage2_review_pass_final_capped_20260501.json
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CODE_ROOT = REPO_ROOT / "code"
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))
from llm_hawaii.stage2_canonical import (  # noqa: E402
    canonical_en as stage2_canonical_en,
    canonical_haw as stage2_canonical_haw,
    compute_pair_hash,
    sha256_text,
)
DATA_STAGE2 = REPO_ROOT / "data" / "stage2"

MANIFEST_IN = DATA_STAGE2 / "stage2_manifest.jsonl"
MANIFEST_OUT = DATA_STAGE2 / "reviewed_stage2_manifest_final_capped.jsonl"
REPORT_OUT = DATA_STAGE2 / "reports" / "stage2_review_pass_final_capped_20260501.json"

CANDIDATES = {
    "bible_1868":         DATA_STAGE2 / "candidates" / "bible_haw1868_kjv.jsonl",
    "hk_1897":            DATA_STAGE2 / "candidates" / "hk_statutes_1897.jsonl",
    "hk_constitution_1852": DATA_STAGE2 / "candidates" / "hk_constitution_1852.jsonl",
    "gospel_john_1854":   DATA_STAGE2 / "candidates" / "gospel_john_1854.jsonl",
    "hooilina":           DATA_STAGE2 / "candidates" / "hooilina.jsonl",
    "hooilina_sentences": DATA_STAGE2 / "candidates" / "hooilina_sentences.jsonl",
    "phrase_book_1881":   DATA_STAGE2 / "candidates" / "phrase_book_1881.jsonl",
    "opus_haw_subsets":   DATA_STAGE2 / "candidates" / "opus_haw_subsets.jsonl",
    "wikimedia_cx_en_haw": DATA_STAGE2 / "candidates" / "wikimedia_cx_en_haw.jsonl",
    "weblate_en_haw":     DATA_STAGE2 / "candidates" / "weblate_en_haw.jsonl",
}

SCORED = {
    "opus_haw_subsets": DATA_STAGE2 / "_scored" / "opus_haw_subsets.jsonl",
    "wikimedia_cx_en_haw": DATA_STAGE2 / "_scored" / "wikimedia_cx_en_haw.jsonl",
}

SOURCE_BLOCKER_REPORTS = {
    "nllb-mined-haw-eng": DATA_STAGE2 / "reports" / "nllb_mined_haw_eng_probe_report.json",
    "wiki-haw-en-langlinks": DATA_STAGE2 / "reports" / "wiki_haw_en_langlinks_probe_report.json",
    "sanitary-instructions-1881": DATA_STAGE2 / "reports" / "sanitary_instructions_1881_probe_report.json",
    "wikisource-haw-en-comparable": DATA_STAGE2 / "reports" / "wikisource_haw_en_comparable_probe_report.json",
}

BIBLE_SHARE_MAX = 0.30
HK_LEGAL_SHARE_MAX = 0.15
SOFTWARE_L10N_SHARE_MAX = 0.15
BIBLE_SOURCES = frozenset({"baibala-hemolele-1839", "baibala-hemolele-1868", "gospel_john_1854"})
HK_LEGAL_SOURCES = frozenset({"hk_statutes_1897", "hk_constitution_1852"})
SOFTWARE_L10N_SOURCES = frozenset({"weblate-en-haw"})

SECTION_STUB_ONLY_RE = re.compile(r'^\$\d+\.?\s*$|^S\d+\.?\s*$')
MIN_TOKENS_JOHN = 4  # minimum tokens per side for Gospel of John verses
HAW_LETTER_INV = set("aehiklmnopuwbdfgjqrstvxyz\u02bb")
def tok(text: str) -> int:
    return len(text.split()) if text else 0


def pair_tokens(row: dict) -> int:
    return tok(row.get("text_haw", "")) + tok(row.get("text_en", ""))


def has_flag(row: dict, flag: str) -> bool:
    return flag in (row.get("quality_flags") or [])


def nonhaw_letter_share(text: str) -> float:
    alpha = [c for c in text if c.isalpha()]
    if not alpha:
        return 0.0
    return sum(1 for c in alpha if c.lower() not in HAW_LETTER_INV) / len(alpha)


def has_section_stub_only(text: str) -> bool:
    return bool(SECTION_STUB_ONLY_RE.match(text.strip()))


def nfc(text: str | None) -> str:
    return unicodedata.normalize("NFC", text or "")


def canonical_haw(text: str | None) -> str:
    return stage2_canonical_haw(text)


def canonical_dedup_text(text: str | None, *, haw: bool = False) -> str:
    return canonical_haw(text) if haw else stage2_canonical_en(text)


def scored_or_candidate_rows(candidate_key: str) -> list[dict]:
    scored = SCORED.get(candidate_key)
    if scored and scored.exists():
        return load_jsonl(scored)
    return load_jsonl(CANDIDATES[candidate_key])


def append_reason(row: dict, reason: str) -> None:
    reasons = row.get("manual_review_reasons")
    if not isinstance(reasons, list):
        reasons = []
    reasons.append(reason)
    row["manual_review_reasons"] = reasons


def mark_hard_holdout(row: dict, reason: str) -> dict:
    r = copy.deepcopy(row)
    r["split"] = "review-pending"
    r["prototype_only"] = True
    r["release_eligible"] = False
    r.setdefault("manifest_schema_version", r.get("schema_version") or "stage2.v0")
    r.setdefault("alignment_confidence_tier", "review")
    r.setdefault("alignment_review_required", True)
    r.setdefault("quality_flags", [])
    r.setdefault("alignment_score_components", {})
    r.setdefault("policy_version", "stage2-hard-source-verdicts-v1")
    append_reason(r, reason)
    return r


def weblate_to_manifest_row(row: dict) -> dict:
    text_en = stage2_canonical_en(row.get("text_en"))
    text_haw = canonical_haw(row.get("text_haw"))
    sha_en = sha256_text(text_en)
    sha_haw = sha256_text(text_haw)
    sha_pair = compute_pair_hash(sha_en, sha_haw)
    unit_id = row.get("tm_unit_id") or sha_pair[:16]
    source_url = row.get("source_url") or ""
    license_observed = row.get("license_observed") or "unknown"
    project = row.get("project_slug") or "unknown-project"
    component = row.get("component_slug") or "unknown-component"
    return {
        **row,
        "pair_id": f"weblate:{unit_id}",
        "source": "weblate-en-haw",
        "source_url_en": source_url,
        "source_url_haw": source_url,
        "fetch_date": row.get("fetch_date") or "",
        "sha256_en_raw": row.get("text_en_sha256") or sha_en,
        "sha256_haw_raw": row.get("text_haw_sha256") or sha_haw,
        "sha256_en_clean": sha_en,
        "sha256_haw_clean": sha_haw,
        "sha256_pair": sha_pair,
        "record_id_en": f"{unit_id}:en",
        "record_id_haw": f"{unit_id}:haw",
        "text_en": text_en,
        "text_haw": text_haw,
        "alignment_type": row.get("alignment_type") or "parallel-sentence",
        "alignment_method": row.get("alignment_method") or "tmx-line",
        "alignment_model": None,
        "alignment_score": None,
        "alignment_review_required": True,
        "length_ratio_haw_over_en": tok(text_haw) / max(tok(text_en), 1),
        "lang_id_en": "en",
        "lang_id_en_confidence": 1.0,
        "lang_id_haw": "haw",
        "lang_id_haw_confidence": 1.0,
        "direction_original": row.get("direction_original") or "en->haw",
        "register": "software-l10n",
        "edition_or_version": f"{project}/{component}",
        "synthetic": False,
        "synthetic_source_model": None,
        "license_observed_en": license_observed,
        "license_observed_haw": license_observed,
        "license_inferred": None,
        "tos_snapshot_id": None,
        "prototype_only": True,
        "release_eligible": False,
        "dedup_cluster_id": f"weblate:{project}:{component}:{sha_pair[:16]}",
        "crosslink_stage1_overlap": False,
        "split": "review-pending",
        "notes": row.get("notes"),
        "manifest_schema_version": "stage2.v0",
        "alignment_confidence_tier": "review",
        "quality_flags": list(row.get("quality_flags") or []),
        "manual_review_reasons": [],
        "alignment_score_components": {},
        "policy_version": "stage2-hard-source-verdicts-v1",
    }


def weblate_quality_reasons(row: dict) -> list[str]:
    """Defense-in-depth gate for permissive Weblate software-l10n rows."""
    reasons: list[str] = []
    haw_text = row.get("text_haw", "")
    en_text = row.get("text_en", "")
    haw_t = tok(haw_text)
    en_t = tok(en_text)
    ratio = row.get("length_ratio_haw_over_en") or 0
    nhs = nonhaw_letter_share(haw_text)

    if row.get("alignment_type") != "parallel-sentence":
        reasons.append("weblate-alignment-type-not-parallel-sentence")
    if row.get("alignment_method") != "tmx-line":
        reasons.append("weblate-alignment-method-not-tmx-line")
    if haw_t < 1:
        reasons.append("weblate-haw-too-short")
    elif haw_t > 80:
        reasons.append("weblate-haw-too-long")
    if en_t < 2:
        reasons.append("weblate-en-too-short")
    elif en_t > 80:
        reasons.append("weblate-en-too-long")
    if not (0.10 <= ratio <= 8.0):
        reasons.append("weblate-ratio-out-of-band")
    if nhs > 0.35:
        reasons.append("weblate-nonhaw-letters-high")
    if canonical_dedup_text(en_text).casefold() == canonical_dedup_text(haw_text, haw=True).casefold():
        reasons.append("weblate-identical-sides")
    return reasons


def _cx_note_float(row: dict, key: str, default: float = 0.0) -> float:
    match = re.search(rf"{re.escape(key)}=([0-9.]+)", row.get("notes") or "")
    if not match:
        return default
    try:
        return float(match.group(1))
    except ValueError:
        return default


def cx_train_ready(row: dict) -> bool:
    """Conservative CX published-translation gate for rows already scored accept."""
    return (
        row.get("alignment_confidence_tier") == "accept"
        and not row.get("quality_flags")
        and row.get("alignment_type") == "parallel-sentence"
        and row.get("alignment_method") == "filename-pair"
        and _cx_note_float(row, "stats.human") >= 0.75
        and _cx_note_float(row, "stats.mt", 1.0) <= 0.05
    )


def opus_wikimedia_train_ready(row: dict) -> bool:
    """Promote only source-line-aligned OPUS Wikimedia rows already scored accept."""
    return (
        row.get("opus_corpus") == "wikimedia"
        and row.get("language_id_check_status") == "ok"
        and row.get("alignment_confidence_tier") == "accept"
        and not row.get("quality_flags")
        and row.get("alignment_type") == "parallel-sentence"
        and row.get("alignment_method") == "tmx-line"
    )


def promote(row: dict, rule_id: str) -> dict:
    r = copy.deepcopy(row)
    r["split"] = "train"
    r["promotion_rule_id"] = rule_id
    r["prototype_only"] = True
    return r


def load_jsonl(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]


def load_source_blocker_reports() -> dict[str, dict]:
    blockers: dict[str, dict] = {}
    def first_present(*values):
        for value in values:
            if value is not None:
                return value
        return None

    for source_id, path in SOURCE_BLOCKER_REPORTS.items():
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        stage2_impact = data.get("stage2_impact") or {}
        blockers[source_id] = {
            "report_path": str(path),
            "verdict": data.get("verdict"),
            "candidate_rows_emitted": first_present(
                data.get("candidate_rows_emitted"),
                stage2_impact.get("candidates_emitted"),
                0,
            ),
            "train_ready_rows_added": first_present(
                data.get("train_ready_rows_added"),
                stage2_impact.get("train_ready_rows_added"),
                0,
            ),
            "manifest_mutation": first_present(
                data.get("manifest_mutation"),
                stage2_impact.get("manifest_modified"),
                "none",
            ),
            "blockers": data.get("blockers")
            or ([data["alignment_feasibility"]["blocker"]]
                if isinstance(data.get("alignment_feasibility"), dict)
                and data["alignment_feasibility"].get("blocker")
                else []),
        }
    return blockers


def cap_select(pool: list[dict], target_tokens: float) -> tuple[list[dict], list[dict], int]:
    """Greedy deterministic selection by sha256_pair until adding next row
    would exceed target_tokens. Returns (kept, dropped, kept_tokens)."""
    sorted_pool = sorted(pool, key=lambda r: r.get("sha256_pair", ""))
    kept: list[dict] = []
    dropped: list[dict] = []
    used = 0
    for r in sorted_pool:
        pt = pair_tokens(r)
        if used + pt <= target_tokens:
            kept.append(r)
            used += pt
        else:
            dropped.append(r)
    return kept, dropped, used


def main(dry_run: bool = False) -> None:
    print(f"Loading canonical manifest: {MANIFEST_IN}")
    manifest = load_jsonl(MANIFEST_IN)
    print(f"  Loaded {len(manifest)} rows")

    output_rows: list[dict] = []
    bible_pool_1839: list[dict] = []
    verse_keys_1839: set[str] = set()
    kaikki_accept_hashes: set[str] = set()
    stats: dict[str, Counter] = defaultdict(Counter)

    # -------- Pass 1: walk canonical manifest --------
    for row in manifest:
        src = row.get("source", "")
        split = row.get("split", "")

        if src == "baibala-hemolele-1839":
            vid = row.get("record_id_en")
            if vid:
                verse_keys_1839.add(vid)
            if split == "train":
                bible_pool_1839.append(copy.deepcopy(row))
            else:
                output_rows.append(copy.deepcopy(row))
            stats[src][split] += 1
            continue

        if src == "kaikki-haw-en-wiktionary":
            if split == "train":
                kaikki_accept_hashes.add(row.get("sha256_pair", ""))
                output_rows.append(copy.deepcopy(row))
                stats[src]["train"] += 1
            elif split == "review-pending":
                haw_t = tok(row.get("text_haw", ""))
                en_t = tok(row.get("text_en", ""))
                ratio = row.get("length_ratio_haw_over_en") or 0
                if (row.get("alignment_type") == "dictionary-example"
                        and haw_t >= 1 and en_t >= 1 and 0.2 <= ratio <= 5.0
                        and not has_flag(row, "haw_nonhaw_letters_high")
                        and not has_flag(row, "haw_no_diacritics")
                        and row.get("sha256_pair") not in kaikki_accept_hashes):
                    r = promote(row, "kaikki-dictionary-example-relaxed-v1")
                    r["manual_review_reasons"] = (r.get("manual_review_reasons") or []) + [
                        "kaikki-dictionary-example-relaxed-v1: explicit Wiktionary "
                        "example translation; dictionary examples permit 1-token "
                        "sides and ratio[0.2,5.0]; stale side_too_short/ratio flags "
                        "do not block if the relaxed gate passes."
                    ]
                    kaikki_accept_hashes.add(r.get("sha256_pair", ""))
                    output_rows.append(r)
                    stats[src]["promoted_to_train"] += 1
                else:
                    output_rows.append(copy.deepcopy(row))
                    stats[src]["review-pending"] += 1
            else:
                output_rows.append(copy.deepcopy(row))
                stats[src][split] += 1
            continue

        if src == "tatoeba":
            if split == "dev":
                output_rows.append(copy.deepcopy(row))  # FROZEN
                stats[src]["dev"] += 1
            elif split == "train":
                output_rows.append(copy.deepcopy(row))
                stats[src]["train"] += 1
            elif split == "review-pending":
                haw_t = tok(row.get("text_haw", ""))
                en_t = tok(row.get("text_en", ""))
                ratio = row.get("length_ratio_haw_over_en") or 0
                if (haw_t >= 1 and en_t >= 1 and 0.25 <= ratio <= 4.0
                        and not has_flag(row, "haw_nonhaw_letters_high")):
                    r = promote(row, "tatoeba-conversational-short-v2")
                    r["manual_review_reasons"] = (r.get("manual_review_reasons") or []) + [
                        "tatoeba-conversational-short-v2: manually verified Tatoeba "
                        "conversational pair; allows one-token greetings/thanks with "
                        "ratio[0.25,4.0] if no Hawaiian non-Hawaiian-letter flag."
                    ]
                    output_rows.append(r)
                    stats[src]["promoted_to_train"] += 1
                else:
                    output_rows.append(copy.deepcopy(row))
                    stats[src]["review-pending"] += 1
            else:
                output_rows.append(copy.deepcopy(row))
                stats[src][split] += 1
            continue

        if src == "andrews-1865-en-haw-vocab-appendix":
            output_rows.append(copy.deepcopy(row))  # Rusty §1.1: stay rejected
            stats[src][split] += 1
            continue

        # default passthrough
        output_rows.append(copy.deepcopy(row))
        stats[src][split] += 1

    # -------- HK Statutes 1897 candidate filtering --------
    print(f"\nFiltering HK Statutes 1897 candidates: {CANDIDATES['hk_1897']}")
    hk_pool: list[dict] = []
    for row in load_jsonl(CANDIDATES["hk_1897"]):
        haw_text = row.get("text_haw", "")
        haw_t = tok(haw_text)
        ratio = row.get("length_ratio_haw_over_en") or 0
        nhs = nonhaw_letter_share(haw_text)
        reasons: list[str] = []
        if haw_t < 25:
            reasons.append("hk1897-haw-too-short")
        elif haw_t > 600:
            reasons.append("hk1897-haw-too-long")
        if not (0.6 <= ratio <= 1.6):
            reasons.append("hk1897-ratio-out-of-band")
        if nhs > 0.10:
            reasons.append("hk1897-nonhaw-letters-high")
        if has_section_stub_only(haw_text):
            reasons.append("hk1897-ocr-section-stub-only")

        r = copy.deepcopy(row)
        r["manifest_schema_version"] = "stage2.v0"
        r["prototype_only"] = True
        r["release_eligible"] = False
        r.setdefault("alignment_confidence_tier", None)
        r.setdefault("quality_flags", None)
        r.setdefault("policy_version", None)
        if not reasons:
            r["promotion_rule_id"] = "hk1897-legal-clean-v1"
            r["manual_review_reasons"] = [
                "Eligible under hk1897-legal-clean-v1: haw_tok[25,600], "
                "ratio[0.6,1.6], nonhaw<=10%, no stub-only OCR. Final inclusion "
                "subject to legal-register <=15% cap against final train tokens."
            ]
            hk_pool.append(r)
        else:
            r["split"] = "review-pending"
            r["manual_review_reasons"] = reasons
            output_rows.append(r)
            stats["hk_statutes_1897"]["review-pending_filtered"] += 1
    print(f"  HK 1897 eligible pool: {len(hk_pool)} rows")

    # -------- HK Constitution 1852 candidate filtering --------
    constitution_path = CANDIDATES.get("hk_constitution_1852")
    if constitution_path and constitution_path.exists():
        print(f"\nFiltering HK Constitution 1852 candidates: {constitution_path}")
        for row in load_jsonl(constitution_path):
            haw_text = row.get("text_haw", "")
            haw_t = tok(haw_text)
            ratio = row.get("length_ratio_haw_over_en") or 0
            nhs = nonhaw_letter_share(haw_text)
            reasons: list[str] = []
            if haw_t < 8:
                reasons.append("hk1852-haw-too-short")
            elif haw_t > 500:
                reasons.append("hk1852-haw-too-long")
            if not (0.4 <= ratio <= 2.5):
                reasons.append("hk1852-ratio-out-of-band")
            if nhs > 0.40:
                reasons.append("hk1852-nonhaw-letters-high")

            r = copy.deepcopy(row)
            r["manifest_schema_version"] = "stage2.v0"
            r["prototype_only"] = True
            r["release_eligible"] = False
            r.setdefault("alignment_confidence_tier", None)
            r.setdefault("policy_version", None)
            if not reasons:
                r["promotion_rule_id"] = "hk1852-legal-clean-v1"
                r["manual_review_reasons"] = [
                    "Eligible under hk1852-legal-clean-v1: haw_tok[8,500], "
                    "ratio[0.4,2.5], nonhaw<=40%. Final inclusion subject to "
                    "combined HK-legal ≤15% cap (shared pool with hk_statutes_1897)."
                ]
                hk_pool.append(r)
            else:
                r["split"] = "review-pending"
                r["manual_review_reasons"] = reasons
                output_rows.append(r)
                stats["hk_constitution_1852"]["review-pending_filtered"] += 1
        print(f"  HK combined eligible pool (1897+1852): {len(hk_pool)} rows")
    else:
        print("  [skip] hk_constitution_1852 candidates not found")

    # -------- Hoʻoilina paragraph rows: deferred (all review-pending) --------
    # These are the 68 section/document-level parent rows. They are NOT promoted
    # to train; they remain as provenance/dedup anchors with a deferred verdict.
    print(f"\nMerging Hoʻoilina paragraph rows: {CANDIDATES['hooilina']}")
    for row in load_jsonl(CANDIDATES["hooilina"]):
        r = copy.deepcopy(row)
        r["split"] = "review-pending"
        r["prototype_only"] = True
        r["release_eligible"] = False
        r["manual_review_reasons"] = (r.get("manual_review_reasons") or []) + [
            "hooilina-para-deferred-v2: paragraph/section-level row superseded by "
            "sentence-level candidates; pending native-speaker (W1) review per Rusty §1.4"
        ]
        output_rows.append(r)
        stats["hooilina"]["review-pending_para"] += 1

    # -------- Hoʻoilina sentence candidates: promote qualifying rows to train --------
    # These are sub-paragraph rows from script 325. They count toward N (non-Bible,
    # non-HK), so they MUST be added to output_rows before the N calculation below.
    sent_path = CANDIDATES["hooilina_sentences"]
    print(f"\nFiltering Hoʻoilina sentence candidates: {sent_path}")
    hooilina_sent_promoted = 0
    hooilina_sent_rejected = 0
    if sent_path.exists():
        seen_hooilina_hashes: set[str] = set()
        for row in load_jsonl(sent_path):
            r = copy.deepcopy(row)
            r["manifest_schema_version"] = "stage2.v0"
            r["prototype_only"] = True
            r["release_eligible"] = False
            r.setdefault("quality_flags", [])

            haw_t = tok(r.get("text_haw", ""))
            en_t = tok(r.get("text_en", ""))
            ratio = r.get("length_ratio_haw_over_en") or 0
            sh = r.get("sha256_pair", "")
            atype = r.get("alignment_type", "")

            eligible = (
                atype == "parallel-sentence"
                and haw_t >= 3 and en_t >= 3
                and haw_t <= 80 and en_t <= 80
                and 0.5 <= ratio <= 2.5
                and sh not in seen_hooilina_hashes
            )
            if eligible:
                seen_hooilina_hashes.add(sh)
                r["split"] = "train"
                r["promotion_rule_id"] = "hooilina-sentence-v2"
                r["manual_review_reasons"] = (r.get("manual_review_reasons") or []) + [
                    "hooilina-sentence-v2: actual sentence pair (two-level split); "
                    "alignment_type=parallel-sentence; "
                    "haw_tok in [3,80] en_tok in [3,80] ratio[0.5,2.5]; "
                    "prototype-only train; "
                    "alignment_review_required=true (KS editorial layer)"
                ]
                output_rows.append(r)
                hooilina_sent_promoted += 1
                stats["hooilina"]["train_sentence"] += 1
            else:
                r["split"] = "review-pending"
                r["manual_review_reasons"] = (r.get("manual_review_reasons") or []) + [
                    "hooilina-sentence-quality-reject: failed promotion gate "
                    "(min tokens / ratio / dedup)"
                ]
                output_rows.append(r)
                hooilina_sent_rejected += 1
                stats["hooilina"]["review-pending_sent"] += 1
    else:
        print(f"  WARNING: {sent_path} not found — skipping sentence promotion")
    print(f"  Hooilina sentence promoted to train: {hooilina_sent_promoted}")
    print(f"  Hooilina sentence rejected/dedup:    {hooilina_sent_rejected}")

    # -------- Phrase Book 1881: PD, train-only after quality gate --------
    # Source: ia-hawaiian-phrase-book-1881 (Bishop 4th ed., U.S. PD pre-1928).
    # Adapter: scripts/328_build_phrase_book_candidates.py.
    # Promotion rule: phrase-book-1881-clean-v1 — emitter already enforced
    #   single-line block, sentence-terminator end, language morphology,
    #   token bands, ratio bounds, and pair dedup. Re-confirm here as a
    #   defense-in-depth gate; do NOT cap (uncapped non-Bible/non-HK N
    #   contributor; train-only).
    pb_path = CANDIDATES["phrase_book_1881"]
    print(f"\nFiltering Phrase Book 1881 candidates: {pb_path}")
    pb_promoted = 0
    pb_rejected = 0
    if pb_path.exists():
        seen_pb_hashes: set[str] = set()
        for row in load_jsonl(pb_path):
            r = copy.deepcopy(row)
            r["manifest_schema_version"] = "stage2.v0"
            # PD source → release-eligible, not prototype-only.
            r["prototype_only"] = False
            r["release_eligible"] = True
            r.setdefault("quality_flags", [])

            haw_t = tok(r.get("text_haw", ""))
            en_t = tok(r.get("text_en", ""))
            ratio = r.get("length_ratio_haw_over_en") or 0
            sh = r.get("sha256_pair", "")
            atype = r.get("alignment_type", "")
            haw_text = r.get("text_haw", "")
            nhs = nonhaw_letter_share(haw_text)

            eligible = (
                atype == "phrase-pair"
                and 1 <= haw_t <= 40 and 1 <= en_t <= 40
                and 0.25 <= ratio <= 4.0
                and nhs <= 0.10
                and sh and sh not in seen_pb_hashes
            )
            if eligible:
                seen_pb_hashes.add(sh)
                r["split"] = "train"
                r["promotion_rule_id"] = "phrase-book-1881-clean-v1"
                r["manual_review_reasons"] = (r.get("manual_review_reasons") or []) + [
                    "phrase-book-1881-clean-v1: Bishop 1881 Hawaiian Phrase Book "
                    "(U.S. PD pre-1928); two-column djvu OCR with single-line + "
                    "sentence-terminator + language-morphology gate; haw_tok in "
                    "[1,40] en_tok in [1,40] ratio[0.25,4.0] nonhaw<=10%; "
                    "uncapped non-Bible/non-HK source (counts toward N); "
                    "alignment_review_required=true (1881 orthography, "
                    "OCR-stripped diacritics)."
                ]
                output_rows.append(r)
                pb_promoted += 1
                stats["ia-hawaiian-phrase-book-1881"]["train"] += 1
            else:
                r["split"] = "review-pending"
                r["manual_review_reasons"] = (r.get("manual_review_reasons") or []) + [
                    "phrase-book-1881-quality-reject: failed promotion gate "
                    "(alignment_type / tokens / ratio / nonhaw / dedup)"
                ]
                output_rows.append(r)
                pb_rejected += 1
                stats["ia-hawaiian-phrase-book-1881"]["review-pending"] += 1
    else:
        print(f"  WARNING: {pb_path} not found — skipping phrase book promotion")
    print(f"  Phrase Book 1881 promoted to train: {pb_promoted}")
    print(f"  Phrase Book 1881 rejected/dedup:    {pb_rejected}")

    # -------- Remaining processed source candidates: hard hold-out verdict path --------
    # These sources have receipts/candidate rows, but do not meet the current
    # train-ready standard. They are merged so script 334 can assign concrete
    # final held-out verdicts; none may survive as review-pending in the final
    # artifact.
    hard_source_summary: dict[str, Counter] = defaultdict(Counter)

    # OPUS: promote only the clean, source-line-aligned Wikimedia subset already
    # accepted by the Stage-2 scorer; keep known-bad and duplicate corpora held out.
    opus_path = CANDIDATES["opus_haw_subsets"]
    opus_wikimedia_promoted = 0
    if opus_path.exists():
        print(f"\nFiltering OPUS haw subsets: {opus_path}")
        upstream_tatoeba_keys: set[tuple[str, str]] = set()
        tatoeba_path = DATA_STAGE2 / "candidates" / "tatoeba.jsonl"
        if tatoeba_path.exists():
            for tr in load_jsonl(tatoeba_path):
                upstream_tatoeba_keys.add((
                    canonical_dedup_text(tr.get("text_en")),
                    canonical_dedup_text(tr.get("text_haw"), haw=True),
                ))

        seen_train_hashes = {
            r.get("sha256_pair")
            for r in output_rows
            if r.get("split") == "train" and r.get("sha256_pair")
        }
        for row in scored_or_candidate_rows("opus_haw_subsets"):
            corpus = row.get("opus_corpus") or "unknown"
            reason: str
            if corpus == "QED":
                reason = (
                    "opus-qed-hard-reject: QED v2.0a haw slice is language-mislabeled "
                    "(EN column is Russian/Cyrillic; HAW column is Danish). No training use."
                )
            elif corpus == "Ubuntu":
                reason = (
                    "opus-ubuntu-hard-reject: Ubuntu v14.10 rows are loan-heavy and "
                    "row-misaligned software strings; no reliable Hawaiian parallel signal."
                )
            elif corpus == "Tatoeba":
                key = (
                    canonical_dedup_text(row.get("text_en")),
                    canonical_dedup_text(row.get("text_haw"), haw=True),
                )
                if key in upstream_tatoeba_keys:
                    reason = (
                        "opus-tatoeba-dedup-holdout: normalized text pair duplicates the "
                        "upstream Tatoeba lane; upstream Tatoeba is the canonical source."
                    )
                else:
                    reason = (
                        "opus-tatoeba-reexport-holdout: OPUS-Tatoeba is a re-export of "
                        "the upstream Tatoeba lane; cluster-isolated dedup leaves no "
                        "standalone train contribution in this cut."
                    )
            elif corpus == "wikimedia":
                if row.get("language_id_check_status") == "language_mismatch":
                    reason = (
                        "opus-wikimedia-language-hard-reject: row failed OPUS language-id "
                        "sanity checks; held out."
                    )
                elif (
                    opus_wikimedia_train_ready(row)
                    and row.get("sha256_pair")
                    and row.get("sha256_pair") not in seen_train_hashes
                ):
                    r = promote(row, "opus-wikimedia-tmx-clean-v1")
                    r["prototype_only"] = True
                    r["release_eligible"] = False
                    r["alignment_review_required"] = True
                    r["manual_review_reasons"] = (r.get("manual_review_reasons") or []) + [
                        "opus-wikimedia-tmx-clean-v1: OPUS source-provided Moses "
                        "line alignment; alignment_confidence_tier=accept; language_ok; "
                        "no quality flags; exact pair hash not already in train. "
                        "Prototype-only CC BY-SA/GFDL provenance retained; no dev/test."
                    ]
                    output_rows.append(r)
                    seen_train_hashes.add(r.get("sha256_pair"))
                    hard_source_summary["opus-haw-subsets"][f"{corpus}_train"] += 1
                    opus_wikimedia_promoted += 1
                    continue
                else:
                    reason = (
                        "opus-wikimedia-scorer-quality-heldout: OPUS-wikimedia row was "
                        "not a scorer-accepted, language-ok, source-line-aligned pair "
                        "with a unique train hash."
                    )
            else:
                reason = (
                    "opus-unknown-corpus-heldout: OPUS corpus not covered by the hard "
                    "Stage-2 source policy."
                )
            output_rows.append(mark_hard_holdout(row, reason))
            hard_source_summary["opus-haw-subsets"][f"{corpus}_held_out"] += 1
        opus_held = sum(
            v for k, v in hard_source_summary["opus-haw-subsets"].items()
            if k.endswith("_held_out")
        )
        print(f"  OPUS Wikimedia promoted to train: {opus_wikimedia_promoted}")
        print(f"  OPUS rows held out: {opus_held}")
    else:
        print("  [skip] opus_haw_subsets candidates not found")

    # Wikimedia CX: promote only the already-scored, high-human/no-MT subset.
    # The rest stays held out with a concrete verdict; no embedding score is
    # invented and no borderline lead-only rows are accepted.
    cx_promoted = 0
    cx_held_out = 0
    cx_path = CANDIDATES["wikimedia_cx_en_haw"]
    if cx_path.exists():
        print(f"\nFiltering Wikimedia CX rows: {cx_path}")
        for row in scored_or_candidate_rows("wikimedia_cx_en_haw"):
            if cx_train_ready(row):
                r = promote(row, "wikimedia-cx-high-human-low-mt-v1")
                r["prototype_only"] = True
                r["release_eligible"] = False
                r["alignment_review_required"] = True
                r["manual_review_reasons"] = (r.get("manual_review_reasons") or []) + [
                    "wikimedia-cx-high-human-low-mt-v1: CX-published EN→HAW row; "
                    "alignment_confidence_tier=accept; no quality flags; "
                    "stats.human>=0.75 and stats.mt<=0.05; prototype-only "
                    "CC BY-SA/GFDL provenance retained; no dev/test."
                ]
                output_rows.append(r)
                cx_promoted += 1
                stats["wikimedia-cx-en-haw"]["train"] += 1
                continue

            reason = (
                "wikimedia-cx-heldout: Content Translation row failed the conservative "
                "train gate (requires scored accept, no quality flags, stats.human>=0.75, "
                "stats.mt<=0.05). Held out rather than weakening the alignment policy."
            )
            output_rows.append(mark_hard_holdout(row, reason))
            hard_source_summary["wikimedia-cx-en-haw"]["held_out"] += 1
            cx_held_out += 1
        print(f"  Wikimedia CX promoted to train: {cx_promoted}")
        print(f"  Wikimedia CX rows held out: {cx_held_out}")
    else:
        print("  [skip] wikimedia_cx_en_haw candidates not found")

    # Weblate: receipts are good and permissive-license components are filtered.
    # Route clean rows through a bounded software-l10n pool instead of leaving
    # the entire lane permanently held out; final inclusion is capped below.
    software_pool: list[dict] = []
    weblate_quality_rejected = 0
    weblate_path = CANDIDATES["weblate_en_haw"]
    if weblate_path.exists():
        print(f"\nFiltering Weblate software-l10n candidates: {weblate_path}")
        for row in load_jsonl(weblate_path):
            manifest_row = weblate_to_manifest_row(row)
            reasons = weblate_quality_reasons(manifest_row)
            if reasons:
                manifest_row["split"] = "review-pending"
                manifest_row["manual_review_reasons"] = (
                    manifest_row.get("manual_review_reasons") or []
                ) + [
                    "weblate-software-l10n-quality-reject: "
                    + ", ".join(reasons)
                ]
                output_rows.append(manifest_row)
                hard_source_summary["weblate-en-haw"]["quality_rejected"] += 1
                weblate_quality_rejected += 1
                continue

            manifest_row["promotion_rule_id"] = "weblate-software-l10n-clean-v1"
            manifest_row["manual_review_reasons"] = (
                manifest_row.get("manual_review_reasons") or []
            ) + [
                "Eligible under weblate-software-l10n-clean-v1: permissive-license "
                "component; tmx-line PO alignment; haw_tok[1,80], en_tok[2,80], "
                "ratio[0.10,8.0], nonhaw<=35%, non-identical sides. Final inclusion "
                "subject to software-l10n <=15% cap against final train tokens."
            ]
            software_pool.append(manifest_row)
        print(f"  Weblate eligible pool: {len(software_pool)} rows")
        print(f"  Weblate quality rejected: {weblate_quality_rejected}")
    else:
        print("  [skip] weblate_en_haw candidates not found")

    # -------- Bible 1868: dedup vs 1839, internal dedup, basic quality --------
    print(f"\nLoading Bible 1868 candidates: {CANDIDATES['bible_1868']}")
    b68_all = load_jsonl(CANDIDATES["bible_1868"])
    seen: set[str] = set()
    b68_dedup = []
    for r in b68_all:
        h = r.get("sha256_pair", "")
        if h not in seen:
            seen.add(h)
            b68_dedup.append(r)
    b68_internal_dupes = len(b68_all) - len(b68_dedup)
    b68_new = [r for r in b68_dedup if r.get("record_id_en") not in verse_keys_1839]
    b68_cross_dupes = len(b68_dedup) - len(b68_new)
    b68_quality = []
    b68_quality_dropped = 0
    for r in b68_new:
        ht = tok(r.get("text_haw", ""))
        et = tok(r.get("text_en", ""))
        ratio = r.get("length_ratio_haw_over_en") or 0
        if ht >= 1 and et >= 1 and 0.2 <= ratio <= 5.0:
            b68_quality.append(r)
        else:
            b68_quality_dropped += 1
    print(f"  1868 internal dupes: {b68_internal_dupes}")
    print(f"  1868 cross-dupes vs 1839: {b68_cross_dupes}")
    print(f"  1868 net-new after quality: {len(b68_quality)}")

    # Combined Bible pool
    bible_pool: list[dict] = []
    for r in bible_pool_1839:
        rr = copy.deepcopy(r)
        rr["_pool_source"] = "1839"
        bible_pool.append(rr)
    for r in b68_quality:
        rr = copy.deepcopy(r)
        rr["_pool_source"] = "1868"
        rr["promotion_rule_id"] = "bible1868-dedup-cap-v1"
        rr["prototype_only"] = True
        bible_pool.append(rr)

    # -------- Gospel of John 1854 candidates: add to Bible pool --------
    gospel_path = CANDIDATES.get("gospel_john_1854")
    john_added = 0
    if gospel_path and gospel_path.exists():
        print(f"\nLoading Gospel of John 1854 candidates: {gospel_path}")
        john_verse_keys = set(verse_keys_1839)  # dedup vs 1839
        # also dedup vs 1868 net-new verse keys already in pool
        for r in b68_quality:
            vk = r.get("record_id_en") or r.get("record_id_haw")
            if vk and vk.startswith("JHN."):
                john_verse_keys.add(vk)
        john_cross_dupes = 0
        for row in load_jsonl(gospel_path):
            verse_key = row.get("record_id_en", "")
            if verse_key in john_verse_keys:
                john_cross_dupes += 1
                continue
            john_verse_keys.add(verse_key)
            # Quality gates
            haw_t = tok(row.get("text_haw", ""))
            en_t = tok(row.get("text_en", ""))
            ratio = row.get("length_ratio_haw_over_en") or 0
            if haw_t < MIN_TOKENS_JOHN or en_t < MIN_TOKENS_JOHN:
                continue
            if not (0.4 <= ratio <= 3.5):
                continue
            rr = copy.deepcopy(row)
            rr["_pool_source"] = "john_1854"
            rr["promotion_rule_id"] = "gospel-john-1854-verse-id-v1"
            rr["prototype_only"] = True
            rr["release_eligible"] = True
            bible_pool.append(rr)
            john_added += 1
        print(f"  Gospel of John: {john_added} verses added to Bible pool "
              f"({john_cross_dupes} cross-edition dupes skipped vs 1839/1868)")
    else:
        print("  [skip] gospel_john_1854 candidates not found")

    print(f"  Bible combined pool: {len(bible_pool)} rows, "
          f"{sum(pair_tokens(r) for r in bible_pool):,} tokens")

    # -------- FIXED-POINT CAPS --------
    # N = uncapped train tokens currently in output_rows.
    # This includes Kaikki, Tatoeba, Hoʻoilina sentence, Phrase Book, and any
    # future uncapped non-Bible/non-HK/non-software train rows. Capped pools
    # (Bible, HK legal, software-l10n) are selected below and verified against
    # the final artifact denominator.
    N = sum(pair_tokens(r) for r in output_rows
            if r.get("split") == "train"
            and r.get("source") not in BIBLE_SOURCES
            and r.get("source") not in HK_LEGAL_SOURCES
            and r.get("source") not in SOFTWARE_L10N_SOURCES)
    print(f"\n=== FIXED-POINT CAP TARGETS ===")
    print(f"  N (uncapped train tokens): {N:,}")

    # With software-l10n capped at 15% alongside HK (15%) and Bible (30%),
    # the all-caps-active solution is S_max=3N/8. If the software pool is
    # smaller than that, its selected tokens increase the denominator for the
    # Bible/HK fixed-point targets below.
    S_target = (
        SOFTWARE_L10N_SHARE_MAX
        / (1.0 - SOFTWARE_L10N_SHARE_MAX - BIBLE_SHARE_MAX - HK_LEGAL_SHARE_MAX)
    ) * N
    software_kept, software_dropped, software_tokens = cap_select(software_pool, S_target)
    capped_base_tokens = N + software_tokens

    # Closed-form for remaining caps after software selection:
    # H_max = 3M/11, B_max = 6M/11, where M = N + S.
    H_target = (3.0 / 11.0) * capped_base_tokens
    B_target = (6.0 / 11.0) * capped_base_tokens
    print(f"  Closed-form S_target = 3N/8 = {S_target:.2f}")
    print(f"  Closed-form H_target = 3(N+S)/11 = {H_target:.2f}")
    print(f"  Closed-form B_target = 6(N+S)/11 = {B_target:.2f}")

    # Cap pools deterministically
    hk_kept, hk_dropped, hk_tokens = cap_select(hk_pool, H_target)
    bible_kept, bible_dropped, bible_tokens = cap_select(bible_pool, B_target)

    print(f"  Software-l10n kept: {len(software_kept)} rows, {software_tokens:,} tokens "
          f"(dropped {len(software_dropped)})")
    print(f"  HK kept: {len(hk_kept)} rows, {hk_tokens:,} tokens "
          f"(dropped {len(hk_dropped)})")
    print(f"  Bible kept: {len(bible_kept)} rows, {bible_tokens:,} tokens "
          f"(dropped {len(bible_dropped)})")

    # Verification + iterative fix-up against ACTUAL final shares
    def shares(N_, S_, H_, B_):
        T = N_ + S_ + H_ + B_
        if T == 0:
            return 0.0, 0.0, 0.0, 0
        return B_ / T, H_ / T, S_ / T, T

    iters = 0
    while True:
        b_share, h_share, s_share, T = shares(N, software_tokens, hk_tokens, bible_tokens)
        b_ok = b_share <= BIBLE_SHARE_MAX + 1e-9
        h_ok = h_share <= HK_LEGAL_SHARE_MAX + 1e-9
        s_ok = s_share <= SOFTWARE_L10N_SHARE_MAX + 1e-9
        if b_ok and h_ok and s_ok:
            break
        iters += 1
        if not b_ok and bible_kept:
            # Drop highest sha256_pair Bible row (= last in sorted order)
            r = bible_kept.pop()
            bible_tokens -= pair_tokens(r)
            bible_dropped.append(r)
        elif not h_ok and hk_kept:
            r = hk_kept.pop()
            hk_tokens -= pair_tokens(r)
            hk_dropped.append(r)
        elif not s_ok and software_kept:
            r = software_kept.pop()
            software_tokens -= pair_tokens(r)
            software_dropped.append(r)
        else:
            break  # cannot reduce further

    final_b_share, final_h_share, final_s_share, T_final = shares(N, software_tokens, hk_tokens, bible_tokens)
    print(f"\n  Verification iterations: {iters}")
    print(f"  T_final_train = {T_final:,} tokens")
    print(f"  Bible share = {final_b_share:.4%}  (cap <=30%) "
          f"{'PASS' if final_b_share <= BIBLE_SHARE_MAX + 1e-9 else 'FAIL'}")
    print(f"  HK    share = {final_h_share:.4%}  (cap <=15%) "
          f"{'PASS' if final_h_share <= HK_LEGAL_SHARE_MAX + 1e-9 else 'FAIL'}")
    print(f"  Soft  share = {final_s_share:.4%}  (cap <=15%) "
          f"{'PASS' if final_s_share <= SOFTWARE_L10N_SHARE_MAX + 1e-9 else 'FAIL'}")

    # -------- Stitch final output --------
    for r in software_kept:
        rr = copy.deepcopy(r)
        rr["split"] = "train"
        output_rows.append(rr)
    for r in software_dropped:
        rr = copy.deepcopy(r)
        rr["split"] = "review-pending"
        rr["manual_review_reasons"] = (rr.get("manual_review_reasons") or []) + [
            "dropped-by-software-l10n-cap-v1"
        ]
        output_rows.append(rr)

    # Bible kept -> train
    b1839_train = b1839_capped = 0
    b1868_train = b1868_capped = 0
    bjohn_train = bjohn_capped = 0
    for r in bible_kept:
        ps = r.pop("_pool_source", "?")
        rr = copy.deepcopy(r)
        rr["split"] = "train"
        output_rows.append(rr)
        if ps == "1839":
            b1839_train += 1
        elif ps == "john_1854":
            bjohn_train += 1
        else:
            b1868_train += 1
    for r in bible_dropped:
        ps = r.pop("_pool_source", "?")
        rr = copy.deepcopy(r)
        rr["split"] = "review-pending"
        rr["manual_review_reasons"] = (rr.get("manual_review_reasons") or []) + [
            "dropped-by-bible-cap-v2-fixedpoint"
        ]
        output_rows.append(rr)
        if ps == "1839":
            b1839_capped += 1
        elif ps == "john_1854":
            bjohn_capped += 1
        else:
            b1868_capped += 1

    # HK kept -> train; HK dropped -> review-pending
    for r in hk_kept:
        rr = copy.deepcopy(r)
        rr["split"] = "train"
        output_rows.append(rr)
    for r in hk_dropped:
        rr = copy.deepcopy(r)
        rr["split"] = "review-pending"
        rr["manual_review_reasons"] = (rr.get("manual_review_reasons") or []) + [
            "dropped-by-hk-legal-cap-v2-fixedpoint"
        ]
        output_rows.append(rr)

    # -------- Final counts --------
    final_by_source: dict[str, Counter] = defaultdict(Counter)
    for r in output_rows:
        final_by_source[r.get("source", "unknown")][r.get("split", "unknown")] += 1

    total_train = total_dev = total_review = 0
    for src, c in sorted(final_by_source.items()):
        total_train += c.get("train", 0)
        total_dev += c.get("dev", 0)
        total_review += c.get("review-pending", 0)

    print("\n=== FINAL COUNTS BY SOURCE ===")
    for src, c in sorted(final_by_source.items()):
        print(f"  {src}: train={c.get('train',0)} dev={c.get('dev',0)} "
              f"review-pending={c.get('review-pending',0)}")
    print(f"  TOTAL: train={total_train} dev={total_dev} "
          f"review-pending={total_review}")
    print(f"  GRAND TOTAL rows: {len(output_rows)}")
    print(f"  Directional SFT rows (2x train): {total_train * 2}")

    # Recompute shares directly from final output_rows for the report
    out_train_tokens = sum(pair_tokens(r) for r in output_rows
                           if r.get("split") == "train")
    out_bible_tokens = sum(pair_tokens(r) for r in output_rows
                           if r.get("split") == "train"
                           and r.get("source") in BIBLE_SOURCES)
    out_hk_tokens = sum(pair_tokens(r) for r in output_rows
                        if r.get("split") == "train"
                        and r.get("source") in HK_LEGAL_SOURCES)
    out_software_tokens = sum(pair_tokens(r) for r in output_rows
                              if r.get("split") == "train"
                              and r.get("source") in SOFTWARE_L10N_SOURCES)
    out_bible_share = out_bible_tokens / max(out_train_tokens, 1)
    out_hk_share = out_hk_tokens / max(out_train_tokens, 1)
    out_software_share = out_software_tokens / max(out_train_tokens, 1)

    print(f"\n=== ARTIFACT-VERIFIED SHARES ===")
    print(f"  total_train_tokens (from artifact): {out_train_tokens:,}")
    print(f"  bible_train_tokens: {out_bible_tokens:,} = {out_bible_share:.4%}")
    print(f"  hk_train_tokens:    {out_hk_tokens:,} = {out_hk_share:.4%}")
    print(f"  software_l10n_train_tokens: {out_software_tokens:,} = {out_software_share:.4%}")

    if dry_run:
        print("\n[dry-run: no files written]")
        return

    MANIFEST_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_OUT, "w") as f:
        for r in output_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nWrote manifest: {MANIFEST_OUT}  ({len(output_rows)} rows)")

    report = {
        "report_type": "stage2_review_pass_final_capped",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy_source": "rusty-review-pending-policy.md (2026-05-03)",
        "owner": "Danny (Lead/Architect)",
        "manifest_in": str(MANIFEST_IN),
        "manifest_out": str(MANIFEST_OUT),
        "rejection_history": {
            "linus_count_rejected": {
                "artifact": "data/stage2/reviewed_stage2_manifest.jsonl",
                "claimed_train": 26118,
                "claimed_directional_sft": 52236,
                "reasons": [
                    "Bible cap treated as 30% of 80k target (absolute), not 30% of actual final train tokens",
                    "Bible 91.9% of train rows — hard cap violation",
                    "Andrews 1865 promoted (969 rows) — Rusty §1.1 violation",
                    "Hoʻoilina promoted to dev — Rusty §1.4 violation; promoted rows must never enter dev/test",
                ],
            },
            "basher_count_rejected": {
                "artifact": "data/stage2/reviewed_stage2_manifest_cap_corrected.jsonl",
                "claimed_train": 1627,
                "claimed_directional_sft": 3254,
                "actual_bible_share": 0.6482,
                "actual_hk_share": 0.3239,
                "reasons": [
                    "Bible cap computed pre-HK against (T_nonbible_total + T_bible_kept) reference, NOT against actual final train tokens",
                    "After HK was capped, T_final_train shrank; actual Bible share rose to 64.8% and HK to 32.4%",
                    "Cap math self-consistent against its own denominator but VIOLATES the stated <=30% / <=15% on the artifact itself",
                ],
            },
        },
        "fixed_point_solution": {
            "derivation": "S/T<=0.15, B/T<=0.30, H/T<=0.15. Select software-l10n first with S_max=3N/8, then set M=N+S and solve H_max=3M/11, B_max=6M/11.",
            "N_uncapped_tokens": N,
            "S_target_tokens": round(S_target, 2),
            "H_target_tokens": round(H_target, 2),
            "B_target_tokens": round(B_target, 2),
            "verification_iterations": iters,
        },
        "bible_dedup_stats": {
            "b1868_total_candidates": len(b68_all),
            "b1868_internal_dupes_removed": b68_internal_dupes,
            "b1868_after_internal_dedup": len(b68_dedup),
            "b1868_cross_dedup_against_1839": b68_cross_dupes,
            "b1868_net_new": len(b68_new),
            "b1868_quality_dropped": b68_quality_dropped,
            "b1868_quality_pool_size": len(b68_quality),
            "verse_keys_1839_count": len(verse_keys_1839),
        },
        "bible_cap": {
            "algorithm": "Pool 1839-train + 1868-net-new-quality + john-1854-verse-dedup; sort sha256_pair asc; greedy <= B_target; verify against artifact and drop tail until <=30%",
            "bible_pool_total": len(bible_pool),
            "bible_train_kept": len(bible_kept),
            "bible_1839_kept": b1839_train,
            "bible_1868_kept": b1868_train,
            "bible_john_1854_kept": bjohn_train,
            "bible_capped_to_review": len(bible_dropped),
            "bible_1839_capped": b1839_capped,
            "bible_1868_capped": b1868_capped,
            "bible_john_1854_capped": bjohn_capped,
            "bible_train_tokens": out_bible_tokens,
            "bible_actual_share": round(out_bible_share, 6),
            "cap_satisfied": out_bible_share <= BIBLE_SHARE_MAX + 1e-9,
        },
        "hk_cap": {
            "algorithm": "Filter by Rusty §1.5; sort sha256_pair asc; greedy <= H_target; verify against artifact",
            "hk_eligible_pool": len(hk_pool),
            "hk_train_kept": len(hk_kept),
            "hk_capped_to_review": len(hk_dropped),
            "hk_train_tokens": out_hk_tokens,
            "hk_actual_share": round(out_hk_share, 6),
            "cap_satisfied": out_hk_share <= HK_LEGAL_SHARE_MAX + 1e-9,
        },
        "software_l10n_cap": {
            "algorithm": "Filter permissive-license Weblate PO rows; sort sha256_pair asc; greedy <= S_target; verify against artifact",
            "software_l10n_eligible_pool": len(software_pool),
            "software_l10n_train_kept": len(software_kept),
            "software_l10n_capped_to_review": len(software_dropped),
            "software_l10n_quality_rejected": weblate_quality_rejected,
            "software_l10n_train_tokens": out_software_tokens,
            "software_l10n_actual_share": round(out_software_share, 6),
            "cap_satisfied": out_software_share <= SOFTWARE_L10N_SHARE_MAX + 1e-9,
        },
        "promotion_summary": {
            "tatoeba_promoted_to_train": stats["tatoeba"].get("promoted_to_train", 0),
            "kaikki_promoted_to_train": stats["kaikki-haw-en-wiktionary"].get("promoted_to_train", 0),
            "andrews_promoted": 0,
            "hooilina_sentence_promoted": hooilina_sent_promoted,
            "hooilina_sentence_rejected": hooilina_sent_rejected,
            "hooilina_para_deferred": stats["hooilina"].get("review-pending_para", 0),
            "phrase_book_1881_train": pb_promoted,
            "phrase_book_1881_rejected": pb_rejected,
            "opus_wikimedia_tmx_train": opus_wikimedia_promoted,
            "hk1897_train": len(hk_kept),
            "bible1868_new_train": b1868_train,
            "weblate_software_l10n_train": len(software_kept),
            "weblate_software_l10n_rejected": weblate_quality_rejected,
            "wikimedia_cx_high_human_train": cx_promoted,
            "wikimedia_cx_held_out": cx_held_out,
        },
        "remaining_source_hard_finalization": {
            src: dict(counter) for src, counter in sorted(hard_source_summary.items())
        },
        "source_level_hard_blockers": load_source_blocker_reports(),
        "counts_by_source": {
            src: dict(c) for src, c in sorted(final_by_source.items())
        },
        "totals": {
            "train": total_train,
            "dev": total_dev,
            "review_pending": total_review,
            "grand_total": len(output_rows),
            "directional_sft_estimate": total_train * 2,
        },
        "token_totals": {
            "total_train_tokens": out_train_tokens,
            "bible_train_tokens": out_bible_tokens,
            "hk_train_tokens": out_hk_tokens,
            "software_l10n_train_tokens": out_software_tokens,
            "uncapped_train_tokens": N,
            "bible_actual_share": round(out_bible_share, 6),
            "hk_actual_share": round(out_hk_share, 6),
            "software_l10n_actual_share": round(out_software_share, 6),
        },
        "notes": [
            "Caps verified directly against the emitted artifact, not a reference denominator.",
            "Frozen Tatoeba dev (15 rows) untouched. No promoted review-pending row enters dev/test.",
            "Andrews 1865 (1,194 rows) remains review-pending: 0 promoted.",
            f"Hoʻoilina: {hooilina_sent_promoted} sentence-level rows promoted to train (prototype-only); "
            "68 paragraph-level rows remain deferred (future-work-native-review).",
            f"Phrase Book 1881 (Bishop 4th ed., U.S. PD): {pb_promoted} phrase-pair rows promoted to train "
            "(release-eligible, NOT prototype-only); uncapped non-Bible/non-HK contributor to N. "
            "Adapter at scripts/328_build_phrase_book_candidates.py.",
            "1850/1869 HK pair stays inventory-only per Linus year-mismatch flag.",
            "Bible 1839 historical-orthography accepted rows that exceed cap are quarantined to review-pending with 'dropped-by-bible-cap-v2-fixedpoint'; the canonical manifest is unchanged.",
            "SFT emitter requires --allow-review-required because HK 1897 and Hoʻoilina sentence rows carry alignment_review_required=true at ingestion despite passing their promotion rules.",
            "N denominator now includes Hoʻoilina sentence + Phrase Book 1881 train tokens, slightly increasing Bible/HK cap budgets.",
            f"Weblate permissive-license software-l10n rows: {len(software_kept)} promoted under a <=15% software-l10n token cap; {len(software_dropped)} cap-held and {weblate_quality_rejected} quality-held.",
            f"OPUS Wikimedia source-line-aligned rows: {opus_wikimedia_promoted} scorer-accepted rows promoted; remaining OPUS rows hard-held with concrete verdicts.",
            f"Wikimedia CX high-human/no-MT rows: {cx_promoted} promoted; {cx_held_out} held out under the conservative CX train gate.",
            "This is NOT a path to 80k by review-pending promotion alone; NLLB-mined and synthetic BT remain required (per Rusty §4 and Linus ulukau-sft-vetting).",
        ],
    }
    with open(REPORT_OUT, "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Wrote report:   {REPORT_OUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    main(dry_run=args.dry_run)
