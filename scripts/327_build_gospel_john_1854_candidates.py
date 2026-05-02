#!/usr/bin/env python3
"""Stage-2 Gospel of John 1854 verse-level candidate builder (Linus).

Reads the 1854 Mission Press parallel-column edition:
  gospelaccordingt00hawarich_djvu.txt   (in ulukau-family dir)

The djvu.txt OCR renders two-column pages by interleaving EN and HAW text.
Verse numbers (Arabic) appear at the start of verse-content lines for both
languages. Chapter markers:
  EN : "CHAP. N." or "CHAP. N. MOKUNA N." (chapters 5+)
  HAW: "MOKUNA N." (Roman numerals, sometimes merged with EN header)

Alignment strategy:
  1. Parse the file into verse-sized chunks (lines starting with digit(s)+space).
  2. Detect language of each chunk using Hawaiian vs English closed-class word
     scoring (both languages' verses are present; OCR mixes them on each page).
  3. Track current chapter for each language stream.
  4. Pair EN verse (chapter, verse_num) with HAW verse (chapter, verse_num).

Policy:
  - register = "religious"  (counts toward Bible ≤30% cap)
  - source = "gospel_john_1854"  (distinct from baibala-hemolele-1839/1868)
  - prototype_only = True, release_eligible = True (PD pre-1925)
  - alignment_review_required = True  (OCR fragile; lang detection heuristic)
  - dedup: Bible cap check uses verse key "JHN.{chapter}.{verse}" to deduplicate
    against the 1839 and 1868 Baibala editions (verse key stored in record_id_en).

Quality gates:
  min_tokens_per_side = 4
  length_ratio_max    = 3.5   (short verses may differ in wordiness)
  nonhaw_share_max    = 0.45  (1854 text; no diacritics expected)

OCR normalization:
  - Collapse double/triple spaces to single (two-column OCR artifact)
  - Join hyphen-broken words across line endings

Known issues:
  - Verse 1 in many chapters is unnumbered in the OCR (printed without leading
    digit in original); these pairs are NOT captured.
  - MOKUNA IIL = MOKUNA III (OCR l→L substitution)
  - Some verses have text mixed across the EN/HAW boundary on the same OCR line.

Outputs:
  data/stage2/candidates/gospel_john_1854.jsonl
  data/stage2/reports/gospel_john_1854_report.json

Stdlib only. Exit codes: 0 success, 1 I/O error, 2 CLI misuse, 3 schema error.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
ULUKAU_DIR = REPO_ROOT / "data" / "raw" / "ulukau-family-sft-candidates" / "20260501"
OUT_CANDIDATES = REPO_ROOT / "data" / "stage2" / "candidates" / "gospel_john_1854.jsonl"
OUT_REPORT = REPO_ROOT / "data" / "stage2" / "reports" / "gospel_john_1854_report.json"

ITEM_ID = "gospelaccordingt00hawarich"
DJVU_TXT = ULUKAU_DIR / ITEM_ID / f"{ITEM_ID}_djvu.txt"
IA_URL = f"https://archive.org/details/{ITEM_ID}"

SCHEMA_VERSION = "stage2.v0"
SOURCE = "gospel_john_1854"
FETCH_DATE = "20260501"

MIN_TOKENS = 4
RATIO_MAX = 3.5
NONHAW_SHARE_MAX = 0.45

# Roman numeral → chapter number
_ROMAN = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7,
    "VIII": 8, "IX": 9, "X": 10, "XI": 11, "XII": 12, "XIII": 13,
    "XIV": 14, "XV": 15, "XVI": 16, "XVII": 17, "XVIII": 18, "XIX": 19,
    "XX": 20, "XXI": 21,
    # OCR variants: I → L substitution
    "L": 1, "LL": 2, "LLL": 3, "LV": 4, "VL": 6, "VLL": 7, "VLLL": 8,
    "XL": 11, "XLL": 12, "XLLL": 13, "XLIV": 14, "XLV": 15, "XLVI": 16,
    "XLVII": 17, "XLVIII": 18, "XLIX": 19, "XXL": 21,
    # Other OCR variants
    "IIL": 3, "IIIL": 3, "IH": 3,
    "Xl": 11, "Xll": 12, "Xl1": 11, "XIL": 11, "XIl": 11,
    ",XVH": 17, "XVH": 17, "XVl": 16, "XVll": 17,
}

# Lines indicating a chapter change (EN)
_EN_CHAP_RE = re.compile(r"CHAP\.\s+([IVXLivxl]+)", re.IGNORECASE)
# HAW chapter marker
_HAW_CHAP_RE = re.compile(r"MOKUNA\s+([IVXLivxl,]+)", re.IGNORECASE)

# Verse-start: line beginning with 1-3 digits (possibly with OCR noise) and a space
_VERSE_START_RE = re.compile(r"^(\d{1,3})\s{1,4}\S")

# HAW closed-class words (distinctive from English in this text)
_HAW_MARKERS = frozenset({
    "ka", "ke", "na", "ia", "la", "ua", "mai", "aku", "ai", "ana", "iho",
    "hoi", "oia", "nae", "nei", "hiki", "hele", "lakou", "noloko", "mahope",
    "makou", "mea", "keia", "kela", "ike", "olelo", "hana", "akua",
    "logou", "ioane", "lesu", "loane", "makou", "loaa", "iho", "pono",
    "aole", "oia", "imua", "iloko", "maluna", "malalo", "malaila", "kona",
    "no", "ae", "o", "e",
})

# EN closed-class words (distinctive from Hawaiian in this text)
_EN_MARKERS = frozenset({
    "jesus", "john", "said", "unto", "thou", "thy", "thee", "lord",
    "saith", "behold", "father", "verily", "therefore", "brethren",
    "wherefore", "wherein", "whatsoever", "whosoever", "know", "because",
    "therefore", "answered", "came", "went", "shall", "were", "been",
    "with", "from", "they", "this", "that", "which", "there", "their",
    "have", "him", "his", "not", "for", "but", "the", "and", "of", "to",
    "in", "a", "he", "it", "is", "at", "as", "by", "if", "or", "be",
    "all", "ye", "us", "me", "we", "my", "so", "an", "no",
})

# Characters considered valid Hawaiian letters
_HAW_ALPHA = set("aehiklmnopuw\u02bb")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def _tok(text: str) -> int:
    return len(text.split())


def _ratio(en_tok: int, haw_tok: int) -> float:
    if en_tok == 0:
        return 99.0
    return haw_tok / en_tok


def _nonhaw_share(text: str) -> float:
    alpha = [c for c in text.lower() if c.isalpha()]
    if not alpha:
        return 0.0
    return sum(1 for c in alpha if c not in _HAW_ALPHA) / len(alpha)


def _normalize_ocr(text: str) -> str:
    """Normalize two-column OCR artifacts: collapse spaces, join hyphen breaks."""
    # Join hyphen-broken words across line endings
    text = re.sub(r"-\s*\n\s*", "", text)
    # Collapse 2+ spaces to single
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def _roman_to_int(roman: str) -> int | None:
    roman = roman.strip(" .,").upper()
    return _ROMAN.get(roman)


def _score_lang(tokens: list[str]) -> str:
    """Return 'haw' or 'en' based on vocabulary scoring."""
    lower = [t.lower().strip(".,;:!?()[]'\"") for t in tokens]
    haw_score = sum(1 for t in lower if t in _HAW_MARKERS)
    en_score = sum(1 for t in lower if t in _EN_MARKERS)
    total = max(len(lower), 1)
    if haw_score >= en_score and (haw_score / total) >= 0.10:
        return "haw"
    if en_score > haw_score and (en_score / total) >= 0.10:
        return "en"
    # Tie-break: nonhaw_share < 0.20 suggests HAW letters
    nhs = _nonhaw_share(" ".join(lower))
    return "haw" if nhs < 0.20 else "en"


def _parse_verses(path: Path) -> tuple[dict, dict]:
    """
    Returns:
      en_verses: {(chapter, verse_num): text}
      haw_verses: {(chapter, verse_num): text}
    """
    text = path.read_text(encoding="utf-8", errors="replace")

    en_verses: dict[tuple, str] = {}
    haw_verses: dict[tuple, str] = {}

    # Skip boilerplate: find the actual Gospel title
    start_m = re.search(r"THE\s+GOSPEL\s+ACCORDING", text)
    if start_m:
        text = text[start_m.start():]

    lines = text.split("\n")

    # Accumulate state
    # Use a single chapter counter updated by EITHER CHAP. or MOKUNA markers.
    # MOKUNA is more reliable (HAW chapter headers are consistent).
    # CHAP. markers also tracked but OCR I→L substitutions handled.
    current_chapter = 0
    current_verse_num: int | None = None
    current_lang: str | None = None  # 'en' or 'haw'
    current_text_parts: list[str] = []

    def flush_current():
        nonlocal current_verse_num, current_lang, current_text_parts
        if current_verse_num is not None and current_lang is not None and current_text_parts:
            body = _normalize_ocr(" ".join(current_text_parts))
            if body:
                key = (current_chapter, current_verse_num)
                if current_lang == "haw":
                    if key not in haw_verses:
                        haw_verses[key] = body
                else:
                    if key not in en_verses:
                        en_verses[key] = body
        current_verse_num = None
        current_lang = None
        current_text_parts = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Primary chapter tracker: MOKUNA N. (HAW, reliable)
        haw_chap_m = _HAW_CHAP_RE.search(stripped)
        if haw_chap_m:
            flush_current()
            num = _roman_to_int(haw_chap_m.group(1))
            if num:
                current_chapter = num
            continue

        # Secondary chapter tracker: CHAP. N. (EN, less reliable OCR)
        en_chap_m = _EN_CHAP_RE.search(stripped)
        if en_chap_m:
            flush_current()
            num = _roman_to_int(en_chap_m.group(1))
            if num and current_chapter == 0:
                current_chapter = num  # Only set if MOKUNA hasn't set it yet
            elif num and abs(num - current_chapter) <= 1:
                current_chapter = num  # Accept small corrections
            continue

        # Ignore page headers
        if re.match(r"^(JOHN|IOANE)\.\s*$", stripped):
            continue

        if current_chapter == 0:
            continue  # Haven't found a chapter yet

        # Check for verse-start: 1-3 digits + 1-4 spaces + text
        vm = _VERSE_START_RE.match(stripped)
        if vm:
            flush_current()
            verse_num = int(vm.group(1))
            # Content is rest of line after the verse number and leading spaces
            rest = stripped[len(vm.group(1)):].lstrip()
            # Language-score using the first 12 tokens
            seed_tokens = rest.split()[:12]
            lang = _score_lang(seed_tokens)
            current_verse_num = verse_num
            current_lang = lang
            current_text_parts = [rest] if rest else []
        elif current_verse_num is not None:
            # Continuation line for current verse
            current_text_parts.append(stripped)

    flush_current()
    return en_verses, haw_verses


def build_candidates(dry_run: bool = False) -> tuple[list[dict[str, Any]], dict]:
    if not DJVU_TXT.exists():
        print(f"ERROR: File not found: {DJVU_TXT}", file=sys.stderr)
        sys.exit(1)

    print(f"Parsing: {DJVU_TXT.name}")
    en_verses, haw_verses = _parse_verses(DJVU_TXT)
    print(f"  EN verses found: {len(en_verses)}")
    print(f"  HAW verses found: {len(haw_verses)}")

    # Pair by (chapter, verse_num)
    common_keys = sorted(set(en_verses) & set(haw_verses))
    print(f"  Alignable verse pairs: {len(common_keys)}")

    candidates: list[dict[str, Any]] = []
    stats = {
        "aligned": len(common_keys),
        "rejected_too_short": 0,
        "rejected_ratio": 0,
        "rejected_nonhaw": 0,
        "emitted": 0,
    }
    seen_hashes: set[str] = set()

    for (chap, vnum) in common_keys:
        en_text = _nfc(en_verses[(chap, vnum)])
        haw_text = _nfc(haw_verses[(chap, vnum)])

        en_tok = _tok(en_text)
        haw_tok = _tok(haw_text)
        ratio = _ratio(en_tok, haw_tok)
        nonhaw = _nonhaw_share(haw_text)

        if en_tok < MIN_TOKENS or haw_tok < MIN_TOKENS:
            stats["rejected_too_short"] += 1
            continue
        if ratio > RATIO_MAX or ratio < (1.0 / RATIO_MAX):
            stats["rejected_ratio"] += 1
            continue
        if nonhaw > NONHAW_SHARE_MAX:
            stats["rejected_nonhaw"] += 1
            continue

        sha_en = _sha256(en_text)
        sha_haw = _sha256(haw_text)
        sha_pair = _sha256(sha_en + sha_haw)

        if sha_pair in seen_hashes:
            continue
        seen_hashes.add(sha_pair)

        verse_key = f"JHN.{chap}.{vnum}"

        row: dict[str, Any] = {
            "pair_id": f"{SOURCE}-{verse_key}",
            "source": SOURCE,
            "source_url_en": IA_URL,
            "source_url_haw": IA_URL,
            "fetch_date": FETCH_DATE,
            "sha256_en_raw": None,
            "sha256_haw_raw": None,
            "sha256_en_clean": sha_en,
            "sha256_haw_clean": sha_haw,
            "sha256_pair": sha_pair,
            # record_id_en encodes the verse key for Bible dedup
            "record_id_en": verse_key,
            "record_id_haw": verse_key,
            "text_en": en_text,
            "text_haw": haw_text,
            "text_en_path": None,
            "text_haw_path": None,
            "alignment_type": "parallel-verse",
            "alignment_method": "verse-id",
            "alignment_model": None,
            "alignment_score": None,
            "alignment_review_required": True,
            "length_ratio_haw_over_en": round(ratio, 4),
            "lang_id_en": "en",
            "lang_id_en_confidence": 0.80,
            "lang_id_haw": "haw",
            "lang_id_haw_confidence": 0.80,
            "direction_original": "en->haw",
            "register": "religious",
            "edition_or_version": "1854",
            "synthetic": False,
            "synthetic_source_model": None,
            "license_observed_en": "public-domain-US-pre1929",
            "license_observed_haw": "public-domain-US-pre1929",
            "license_inferred": "PD_pre1925",
            "tos_snapshot_id": "ia_terms",
            "prototype_only": True,
            "release_eligible": True,
            "dedup_cluster_id": f"{SOURCE}-{verse_key}",
            "crosslink_stage1_overlap": False,
            # Bible dedup: verse_key stored for cross-edition check against 1839/1868
            "quality_flags": ["haw_no_diacritics", "bible_cross_edition_dedup_required"],
            "schema_version": SCHEMA_VERSION,
            "split": "review-pending",
        }
        candidates.append(row)
        stats["emitted"] += 1

    return candidates, stats


def _self_test() -> None:
    assert _roman_to_int("I") == 1
    assert _roman_to_int("XXI") == 21
    assert _roman_to_int("IIL") == 3
    assert _score_lang(["ka", "ke", "ia", "la", "ua", "mai"]) == "haw"
    assert _score_lang(["Jesus", "said", "unto", "him", "the"]) == "en"
    assert _normalize_ocr("mana-\ntua") == "manatua"
    assert _normalize_ocr("a  b   c") == "a b c"
    print("Self-test: 7 assertions OK")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        _self_test()
        return

    dry_run = not args.execute

    print(f"=== Gospel of John 1854 Candidate Builder ({'dry-run' if dry_run else 'execute'}) ===")
    candidates, stats = build_candidates(dry_run=dry_run)

    print(f"\n=== STATS ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    if not candidates:
        print("WARNING: No candidates generated!", file=sys.stderr)
        sys.exit(3)

    print(f"\nTotal emitted: {len(candidates)} candidates")

    if dry_run:
        print("[dry-run] Sample candidate (first):")
        if candidates:
            c = candidates[0]
            print(f"  pair_id: {c['pair_id']}")
            print(f"  text_en[:80]: {c['text_en'][:80]}")
            print(f"  text_haw[:80]: {c['text_haw'][:80]}")
        print("\n[dry-run: no files written]")
        return

    OUT_CANDIDATES.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)

    with open(OUT_CANDIDATES, "w") as f:
        for row in candidates:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"\nWrote: {OUT_CANDIDATES}  ({len(candidates)} rows)")

    chapters_covered = sorted(set(
        pid.split("-JHN.")[1].split(".")[0]
        for pid in (row["pair_id"] for row in candidates)
        if "-JHN." in pid
    ), key=lambda x: int(x))
    report = {
        "source": SOURCE,
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "item_id": ITEM_ID,
        "en_verses_parsed": stats["aligned"],  # before filtering
        "haw_verses_parsed": stats["aligned"],
        "aligned_pairs": stats["aligned"],
        "rejected_too_short": stats["rejected_too_short"],
        "rejected_ratio": stats["rejected_ratio"],
        "rejected_nonhaw": stats["rejected_nonhaw"],
        "emitted": stats["emitted"],
        "quality_flags_applied": ["haw_no_diacritics", "bible_cross_edition_dedup_required"],
        "alignment_review_required": True,
        "notes": [
            "Counts toward Bible ≤30% cap (register=religious, verse-level).",
            "record_id_en stores 'JHN.{ch}.{v}' for cross-edition dedup vs 1839/1868.",
            "Verse 1 of many chapters is unnumbered in OCR; those pairs not captured.",
            "OCR double-space artifacts normalized; hyphen line-breaks joined.",
            "Language detection is heuristic (closed-class word scoring); review required.",
            "1854 text predates Pukui-Elbert; no diacritics expected (haw_no_diacritics flag).",
            "Manifest builder must dedup verse keys against baibala-hemolele-1839/1868 pools.",
        ],
    }
    with open(OUT_REPORT, "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Wrote: {OUT_REPORT}")


if __name__ == "__main__":
    main()
