#!/usr/bin/env python3
"""Stage-2 HK Constitution + Laws 1852 section-level candidate builder (Linus).

Reads the 1852 paired imprints:
  EN: constitutionand00hawagoog_djvu.txt   (in ulukau-family dir)
  HAW: hekumukanawaiam00hawagoog_djvu.txt  (in hk-statutes dir, reused)

Aligns by article/section number:
  EN marker : "Art. N."  (Art. 1. through Art. 105.)
  HAW marker: "Pauku N." variants (Pauku/Paukc/Pauk€ etc.)

Only the Constitution portion is processed (Art. 1–105 / Pauku 1–105).
Session Laws after Art. 105 have per-act numbering resets and are excluded.

Policy:
  - register = "legal"  (counts toward ≤15% HK-legal cap in manifest builder)
  - prototype_only = True, release_eligible = False
  - alignment_review_required = True  (W→AV OCR artifacts in HAW; line-break hyphens)
  - direction_original = "en->haw" (EN printing predates HAW)

OCR known issues in HAW file:
  - W often rendered as "AV" (e.g. KUMUKANAAVAI for KUMUKANAWAI)
  - Section marker variants: Paukc, Pauk€, Pauko, Pauke (all OCR for ū/u)
  - No ʻokina or macrons (expected for 1852 text; flag haw_no_diacritics)

Quality gates:
  min_tokens_per_side = 5
  length_ratio_max    = 3.0   (legal sections can be verbose on one side)
  nonhaw_share_max    = 0.40  (1852 text lacks diacritics; HAW chars include aehiklmnopuw)

Outputs:
  data/stage2/candidates/hk_constitution_1852.jsonl
  data/stage2/reports/hk_constitution_1852_report.json

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
HK_DIR = REPO_ROOT / "data" / "raw" / "hawaiian-kingdom-statutes-paired-imprints" / "20260501"
OUT_CANDIDATES = REPO_ROOT / "data" / "stage2" / "candidates" / "hk_constitution_1852.jsonl"
OUT_REPORT = REPO_ROOT / "data" / "stage2" / "reports" / "hk_constitution_1852_report.json"

SCHEMA_VERSION = "stage2.v0"
SOURCE = "hk_constitution_1852"
FETCH_DATE = "20260501"

EN_ITEM_ID = "constitutionand00hawagoog"
HAW_ITEM_ID = "hekumukanawaiam00hawagoog"

EN_DJVU_TXT = ULUKAU_DIR / EN_ITEM_ID / f"{EN_ITEM_ID}_djvu.txt"
HAW_DJVU_TXT = HK_DIR / f"{HAW_ITEM_ID}__{HAW_ITEM_ID}_djvu.txt"

EN_IA_URL = f"https://archive.org/details/{EN_ITEM_ID}"
HAW_IA_URL = f"https://archive.org/details/{HAW_ITEM_ID}"

MIN_TOKENS = 5
RATIO_MAX = 3.0
NONHAW_SHARE_MAX = 0.40
MAX_ARTICLE = 105

# EN section marker: "Art. N." at line start
_EN_ART_RE = re.compile(r"^Art\.\s+(\d+)\.", re.MULTILINE)

# HAW section marker: "Pauku N." variants
# Covers Paukū, Paukc, Pauk€, Pauko, Pauke, and lines with leading ". " noise.
# Period after number NOT required (OCR produces «, \., ?, etc.).
_HAW_PAU_RE = re.compile(r"^[. ]{0,3}Pauk.?\s+(\d+)", re.MULTILINE)

# HAW "NA KANAWAI" / "HE KANAWAI" marker — constitution ends here
_HAW_LAWS_RE = re.compile(r"^NA KANAWAI|^HE KANAWAI", re.MULTILINE)

# OCR page noise: all-caps header lines with trailing page numbers
_NOISE_RE = re.compile(r"^[A-Z .'\-]{4,}\s+\d+\s*$", re.MULTILINE)

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


def _clean_body(raw: str) -> str:
    """Normalize OCR body text: collapse hyphen line-breaks, normalize whitespace."""
    # Join hyphen-broken words: "mana-\ntua" → "manantua"
    # Conservative: only join if the hyphen is at end of a line (not mid-word dash)
    text = re.sub(r"-\n\s*", "", raw)
    # Collapse multiple spaces/tabs to single space
    text = re.sub(r"[ \t]+", " ", text)
    # Collapse multiple newlines to single
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def _remove_noise(text: str) -> str:
    """Remove all-caps page header/footer noise lines."""
    lines = []
    for line in text.split("\n"):
        # Skip short all-caps lines that look like page headers
        stripped = line.strip()
        if re.match(r"^[A-Z .''`\-]{5,}\s*(\d+)?\s*$", stripped) and len(stripped) < 70:
            continue
        lines.append(line)
    return "\n".join(lines)


def _parse_sections(text: str, marker_re: re.Pattern, max_num: int) -> dict[int, str]:
    """
    Parse sections from OCR text.
    Returns {section_number: body_text} for sections 1..max_num.
    Takes only the FIRST occurrence of each number (handles OCR duplicates).
    """
    matches = list(marker_re.finditer(text))
    sections: dict[int, str] = {}
    for i, m in enumerate(matches):
        num = int(m.group(1))
        if num > max_num:
            continue
        if num in sections:
            continue  # take first occurrence only
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end]
        body = _remove_noise(body)
        body = _clean_body(body)
        # Prepend the section number tag for context
        body = f"[Art. {num}] " + body if marker_re is _EN_ART_RE else f"[Pauku {num}] " + body
        sections[num] = body
    return sections


def _parse_en_sections(path: Path) -> dict[int, str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    # Find the first "Art. 1." — everything before is boilerplate
    m = re.search(r"^DECLARATION OF RIGHTS", text, re.MULTILINE)
    start = m.start() if m else 0
    # Find "SESSION LAWS" — constitution ends there
    end_m = re.search(r"^SESSION LAWS", text[start:], re.MULTILINE)
    end = start + end_m.start() if end_m else len(text)
    constitution_text = text[start:end]
    return _parse_sections(constitution_text, _EN_ART_RE, MAX_ARTICLE)


def _parse_haw_sections(path: Path) -> dict[int, str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    # Find "KUMUKANAWAI" title — start of constitution
    m = re.search(r"^KUMUKANA", text, re.MULTILINE)
    start = m.start() if m else 0
    # Find "NA KANAWAI" — constitution ends there
    end_m = _HAW_LAWS_RE.search(text[start:])
    end = start + end_m.start() if end_m else len(text)
    constitution_text = text[start:end]
    return _parse_sections(constitution_text, _HAW_PAU_RE, MAX_ARTICLE)


def build_candidates(dry_run: bool = False) -> list[dict[str, Any]]:
    if not EN_DJVU_TXT.exists():
        print(f"ERROR: EN file not found: {EN_DJVU_TXT}", file=sys.stderr)
        sys.exit(1)
    if not HAW_DJVU_TXT.exists():
        print(f"ERROR: HAW file not found: {HAW_DJVU_TXT}", file=sys.stderr)
        sys.exit(1)

    print(f"Parsing EN: {EN_DJVU_TXT.name}")
    en_sections = _parse_en_sections(EN_DJVU_TXT)
    print(f"  Found {len(en_sections)} EN articles (max={max(en_sections) if en_sections else 0})")

    print(f"Parsing HAW: {HAW_DJVU_TXT.name}")
    haw_sections = _parse_haw_sections(HAW_DJVU_TXT)
    print(f"  Found {len(haw_sections)} HAW sections (max={max(haw_sections) if haw_sections else 0})")

    common_nums = sorted(set(en_sections) & set(haw_sections))
    print(f"  Alignable section numbers: {len(common_nums)}")

    candidates: list[dict[str, Any]] = []
    stats = {
        "aligned": 0,
        "skipped_not_in_haw": 0,
        "skipped_not_in_en": 0,
        "rejected_too_short": 0,
        "rejected_ratio": 0,
        "rejected_nonhaw": 0,
        "emitted": 0,
    }

    seen_hashes: set[str] = set()

    for num in common_nums:
        en_text = _nfc(en_sections[num])
        haw_text = _nfc(haw_sections[num])
        stats["aligned"] += 1

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

        row: dict[str, Any] = {
            "pair_id": f"{SOURCE}-art{num}",
            "source": SOURCE,
            "source_url_en": EN_IA_URL,
            "source_url_haw": HAW_IA_URL,
            "fetch_date": FETCH_DATE,
            "sha256_en_raw": None,
            "sha256_haw_raw": None,
            "sha256_en_clean": sha_en,
            "sha256_haw_clean": sha_haw,
            "sha256_pair": sha_pair,
            "record_id_en": f"{EN_ITEM_ID}-art{num}",
            "record_id_haw": f"{HAW_ITEM_ID}-art{num}",
            "text_en": en_text,
            "text_haw": haw_text,
            "text_en_path": None,
            "text_haw_path": None,
            "alignment_type": "parallel-sentence",
            "alignment_method": "section-id",
            "alignment_model": None,
            "alignment_score": None,
            "alignment_review_required": True,
            "length_ratio_haw_over_en": round(ratio, 4),
            "lang_id_en": "en",
            "lang_id_en_confidence": 1.0,
            "lang_id_haw": "haw",
            "lang_id_haw_confidence": 0.85,
            "direction_original": "en->haw",
            "register": "legal",
            "edition_or_version": "1852",
            "synthetic": False,
            "synthetic_source_model": None,
            "license_observed_en": "public-domain-US-pre1929",
            "license_observed_haw": "public-domain-US-pre1929",
            "license_inferred": "PD_pre1925_sovereign_edicts",
            "tos_snapshot_id": "ia_terms",
            "prototype_only": True,
            "release_eligible": False,
            "dedup_cluster_id": f"{SOURCE}-art{num}",
            "crosslink_stage1_overlap": False,
            "quality_flags": ["haw_no_diacritics"],
            "schema_version": SCHEMA_VERSION,
            "split": "review-pending",
        }
        candidates.append(row)
        stats["emitted"] += 1

    stats["skipped_not_in_haw"] = len([n for n in en_sections if n not in haw_sections])
    stats["skipped_not_in_en"] = len([n for n in haw_sections if n not in en_sections])
    return candidates, stats


def _self_test() -> None:
    # Basic unit tests for helper functions
    assert _tok("hello world foo") == 3
    assert _ratio(4, 8) == 2.0
    assert abs(_nonhaw_share("ka ke ia la ua") - 0.0) < 0.01  # all HAW letters
    assert _nonhaw_share("xyz123 7 8 9 dollar") > 0.3  # non-HAW chars
    body = _clean_body("mana-\ntua ia  la   ke  akua")
    assert "  " not in body
    assert "-\n" not in body
    print("Self-test: 5 assertions OK")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="Parse and report without writing output")
    ap.add_argument("--self-test", action="store_true", help="Run unit tests and exit")
    ap.add_argument("--execute", action="store_true", help="Write outputs (default: dry-run)")
    args = ap.parse_args()

    if args.self_test:
        _self_test()
        return

    dry_run = not args.execute

    print(f"=== HK Constitution 1852 Candidate Builder ({'dry-run' if dry_run else 'execute'}) ===")
    candidates, stats = build_candidates(dry_run=dry_run)

    print(f"\n=== STATS ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    if not candidates:
        print("WARNING: No candidates generated!", file=sys.stderr)
        sys.exit(3)

    print(f"\nTotal emitted: {len(candidates)} candidates")

    if dry_run:
        print("[dry-run] Sample candidate:")
        print(json.dumps(candidates[0], ensure_ascii=False, indent=2)[:600])
        print("\n[dry-run: no files written]")
        return

    OUT_CANDIDATES.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)

    with open(OUT_CANDIDATES, "w") as f:
        for row in candidates:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"\nWrote: {OUT_CANDIDATES}  ({len(candidates)} rows)")

    report = {
        "source": SOURCE,
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "en_item_id": EN_ITEM_ID,
        "haw_item_id": HAW_ITEM_ID,
        "constitution_articles_parsed_en": stats["aligned"] + stats["skipped_not_in_haw"],
        "constitution_sections_parsed_haw": stats["aligned"] + stats["skipped_not_in_en"],
        "aligned_pairs": stats["aligned"],
        "rejected_too_short": stats["rejected_too_short"],
        "rejected_ratio": stats["rejected_ratio"],
        "rejected_nonhaw": stats["rejected_nonhaw"],
        "emitted": stats["emitted"],
        "quality_flags_applied": ["haw_no_diacritics"],
        "alignment_review_required": True,
        "notes": [
            "Only constitution articles (Art. 1-105 / Pauku 1-105) processed.",
            "Session Laws (post-Art.105) excluded: per-act numbering resets prevent deterministic alignment.",
            "HAW OCR known issues: W→AV substitutions; section marker variants (Paukc, Pauk€ etc).",
            "All rows flagged haw_no_diacritics (expected: 1852 text predates Pukui-Elbert convention).",
            "Counts toward combined HK-legal cap (≤15% of final train tokens) alongside hk_statutes_1897.",
        ],
    }
    with open(OUT_REPORT, "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Wrote: {OUT_REPORT}")


if __name__ == "__main__":
    main()
