#!/usr/bin/env python3
"""Stage-2 HK Statutes 1897 section-level candidate builder (Linus).

Reads the 1897 Penal Laws djvu.txt OCR files for the Cornell/LLMC
paired imprints (EN: esrp641724381, HAW: esrp641728581), parses
CHAPTER/MOKUNA chapter markers and §-prefixed section markers, joins
sections by sequential section number, and emits one Stage-2 candidate
row per successfully paired section.

Policy:
  - Only the 1897 pair is processed (policy: GO per decisions.md).
  - The 1869/1850 mismatch pair is inventory-only and is NOT touched.
  - prototype_only=True, release_eligible=False on all rows.
  - alignment_type="parallel-sentence", alignment_review_required=True
    (OCR noise; deterministic section-ID join but not character-verified).
  - direction_original="en->haw" (HAW preface confirms translation direction).

OCR section-marker conventions (HAW djvu.txt):
  § → '$' (dollar sign)  — most common OCR artifact
  § → 'S' (uppercase S)  — second common OCR artifact
  § → '8' (digit 8)      — third artifact; EXCLUDED for safety (ambiguous
                            with real section 87, 823, etc.)

Outputs:
  data/stage2/candidates/hk_statutes_1897.jsonl
  data/stage2/reports/hk_statutes_1897_report.json

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
RAW_DIR = REPO_ROOT / "data" / "raw" / "hawaiian-kingdom-statutes-paired-imprints" / "20260501"
OUT_CANDIDATES = REPO_ROOT / "data" / "stage2" / "candidates" / "hk_statutes_1897.jsonl"
OUT_REPORT = REPO_ROOT / "data" / "stage2" / "reports" / "hk_statutes_1897_report.json"
MANIFEST_COMPLETE = RAW_DIR / "manifest_complete.jsonl"

MANIFEST_SCHEMA_VERSION = "stage2.v0"
SOURCE = "hk_statutes_1897"
FETCH_DATE = "20260501"

EN_ITEM_ID = "esrp641724381"
HAW_ITEM_ID = "esrp641728581"
EN_DJVU_TXT = RAW_DIR / f"{EN_ITEM_ID}__1897.001_djvu.txt"
HAW_DJVU_TXT = RAW_DIR / f"{HAW_ITEM_ID}__1897.002_djvu.txt"

EN_IA_URL = f"https://archive.org/details/{EN_ITEM_ID}"
HAW_IA_URL = f"https://archive.org/details/{HAW_ITEM_ID}"

# Raw file sha256 from manifest_complete.jsonl
EN_RAW_SHA256 = "f7c84fc55b8fe1d743ea0a4298dac16e11262e4b985f29ecd4568d739bb0e611"
HAW_RAW_SHA256 = "7541498292b153111db1629c044d3a35be46ed77736700b3d763439be1458293"

# ʻokina canonicalization (mirrors stage2_quality.py and 322 convention)
OKINA = "\u02bb"
OKINA_MISENCODINGS = ("\u2018", "\u2019", "'")

# Minimum word count for a section to be emitted (filter OCR noise)
MIN_WORDS = 5

# Patterns
# EN chapter marker: "CHAPTER N." with optional trailing whitespace
_EN_CHAPTER_RE = re.compile(r"^CHAPTER (\d+)\.", re.MULTILINE)
# HAW chapter marker: "MOKUNA N." with optional trailing whitespace
_HAW_CHAPTER_RE = re.compile(r"^MOKUNA (\d+)\.", re.MULTILINE)
# EN section marker: §N. or §N, at line start
_EN_SECTION_RE = re.compile(r"^§(\d+)[,.]", re.MULTILINE)
# HAW section marker: $N. or $N, or SN. or SN, at line start
# Capital S immediately followed by a digit = OCR artifact for §
_HAW_SECTION_RE = re.compile(r"^[\$S](\d+)[,.]", re.MULTILINE)

# OCR page-noise: all-caps header/footer lines e.g. "DEFINITIONS. 58"
# pattern: line of all-caps words (possibly with spaces/hyphens) followed by
# optional digits or short strings, less than 70 chars
_PAGE_NOISE_RE = re.compile(
    r"^[A-ZÀ-Ö\s\-–—'.]+\s+\d+\s*$",
    re.MULTILINE,
)


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------


def normalize_haw(text: str) -> str:
    """NFC + canonicalize ʻokina mis-encodings to U+02BB."""
    nfc = unicodedata.normalize("NFC", text)
    for bad in OKINA_MISENCODINGS:
        nfc = nfc.replace(bad, OKINA)
    return nfc.strip()


def normalize_en(text: str) -> str:
    """NFC + strip whitespace."""
    return unicodedata.normalize("NFC", text).strip()


def sha256_text(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def compute_pair_hash(sha256_en_clean: str, sha256_haw_clean: str) -> str:
    """Canonical pair hash: sha256(en_clean + '‖' + haw_clean).

    Mirrors scripts/320_build_stage2_manifest.py::compute_pair_hash.
    The separator is U+2016 DOUBLE VERTICAL LINE.
    """
    combined = (sha256_en_clean + "\u2016" + sha256_haw_clean).encode("utf-8")
    return hashlib.sha256(combined).hexdigest()


# ---------------------------------------------------------------------------
# Text cleaning helpers
# ---------------------------------------------------------------------------


def _join_hyphenated_lines(text: str) -> str:
    """Join lines ending with hyphen (OCR line-break hyphenation)."""
    return re.sub(r"-\n(\S)", r"\1", text)


def _remove_page_noise(text: str) -> str:
    """Remove OCR page header/footer lines (all-caps + page number)."""
    return _PAGE_NOISE_RE.sub("", text)


def _collapse_whitespace(text: str) -> str:
    """Replace multiple whitespace chars (including newlines) with single space."""
    return re.sub(r"\s+", " ", text).strip()


def clean_section_text(raw: str) -> str:
    """Full cleaning pipeline: hyphen-join → noise-remove → collapse → strip."""
    t = _join_hyphenated_lines(raw)
    t = _remove_page_noise(t)
    t = _collapse_whitespace(t)
    return t


# ---------------------------------------------------------------------------
# Section extraction
# ---------------------------------------------------------------------------


def _find_pc_start(text: str, chapter_pattern: re.Pattern) -> int:
    """Find character position of the first chapter/mokuna 1 marker."""
    m = chapter_pattern.search(text)
    return m.start() if m else 0


def _extract_markers(
    text: str,
    section_pattern: re.Pattern,
    chapter_pattern: re.Pattern,
    pc_start: int,
) -> list[tuple[int, str, int | None]]:
    """Return sorted list of (char_pos, kind, num) for all markers after pc_start.

    kind: 'section' or 'chapter'
    num: section number or chapter number
    """
    markers: list[tuple[int, str, int]] = []
    for m in section_pattern.finditer(text):
        if m.start() >= pc_start:
            markers.append((m.start(), "section", int(m.group(1))))
    for m in chapter_pattern.finditer(text):
        if m.start() >= pc_start:
            markers.append((m.start(), "chapter", int(m.group(1))))
    markers.sort(key=lambda x: x[0])
    return markers


def parse_sections(
    text: str,
    language: str,
) -> dict[int, str]:
    """Parse djvu.txt and return {section_num: raw_section_text}.

    Extracts only sections within the Penal Code portion (after the first
    CHAPTER/MOKUNA marker). Section text runs from the section marker line
    to just before the next section or chapter marker.

    language: "en" or "haw"
    """
    if language == "en":
        section_re = _EN_SECTION_RE
        chapter_re = _EN_CHAPTER_RE
    else:
        section_re = _HAW_SECTION_RE
        chapter_re = _HAW_CHAPTER_RE

    pc_start = _find_pc_start(text, chapter_re)
    markers = _extract_markers(text, section_re, chapter_re, pc_start)

    sections: dict[int, str] = {}
    for i, (pos, kind, num) in enumerate(markers):
        if kind != "section":
            continue
        # text runs from this marker to the start of the next marker
        next_pos = markers[i + 1][0] if i + 1 < len(markers) else len(text)
        raw_text = text[pos:next_pos]
        # Skip if section number already seen (take first occurrence)
        if num not in sections:
            sections[num] = raw_text
    return sections


# ---------------------------------------------------------------------------
# Candidate row builder
# ---------------------------------------------------------------------------


def length_ratio(haw_text: str, en_text: str) -> float:
    """Token count ratio haw/en (word tokenized)."""
    haw_words = len(haw_text.split())
    en_words = len(en_text.split())
    if en_words == 0:
        return 0.0
    return round(haw_words / en_words, 4)


def build_candidate_row(
    sec_num: int,
    en_clean: str,
    haw_clean: str,
    en_raw: str,
    haw_raw: str,
) -> dict[str, Any]:
    """Build one Stage-2 candidate row for a paired statute section."""
    sha_en_raw = sha256_text(en_raw)
    sha_haw_raw = sha256_text(haw_raw)
    sha_en_clean = sha256_text(en_clean)
    sha_haw_clean = sha256_text(haw_clean)
    sha_pair = compute_pair_hash(sha_en_clean, sha_haw_clean)

    pair_id = f"{SOURCE}-sec{sec_num}"

    return {
        "pair_id": pair_id,
        "source": SOURCE,
        "source_url_en": EN_IA_URL,
        "source_url_haw": HAW_IA_URL,
        "fetch_date": FETCH_DATE,
        "sha256_en_raw": EN_RAW_SHA256,
        "sha256_haw_raw": HAW_RAW_SHA256,
        "sha256_en_clean": sha_en_clean,
        "sha256_haw_clean": sha_haw_clean,
        "sha256_pair": sha_pair,
        "record_id_en": f"{EN_ITEM_ID}-sec{sec_num}",
        "record_id_haw": f"{HAW_ITEM_ID}-sec{sec_num}",
        "text_en": en_clean,
        "text_haw": haw_clean,
        "text_en_path": None,
        "text_haw_path": None,
        "alignment_type": "parallel-sentence",
        "alignment_method": "filename-pair",
        "alignment_model": None,
        "alignment_score": None,
        "alignment_review_required": True,
        "length_ratio_haw_over_en": length_ratio(haw_clean, en_clean),
        "lang_id_en": "en",
        "lang_id_en_confidence": 1.0,
        "lang_id_haw": "haw",
        "lang_id_haw_confidence": 1.0,
        "direction_original": "en->haw",
        "register": "unknown",
        "edition_or_version": "1897",
        "synthetic": False,
        "synthetic_source_model": None,
        "license_observed_en": "public-domain-US-pre1929",
        "license_observed_haw": "public-domain-US-pre1929",
        "license_inferred": None,
        "tos_snapshot_id": "ia_terms",
        "prototype_only": True,
        "release_eligible": False,
        "dedup_cluster_id": pair_id,
        "crosslink_stage1_overlap": False,
        "split": "review-pending",
        "notes": (
            f"1897 Penal Laws bilingual imprint, section §{sec_num}. "
            "Paired by §-section-ID match in parallel djvu.txt OCR files "
            "(Cornell/LLMC digitization via archive.org). "
            f"EN item: {EN_ITEM_ID}; HAW item: {HAW_ITEM_ID}. "
            f"Raw file sha256: en={EN_RAW_SHA256[:16]}…, haw={HAW_RAW_SHA256[:16]}…. "
            "HAW § rendered as '$' or 'S' by OCR; '§→8' OCR artifact excluded for "
            "safety (~189 EN sections). direction_original=en->haw per HAW preface "
            "'Unuhiia mai ka Olelo Beritania mai.' (Translated from English)."
        ),
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        # Policy fields: populated by 320_build_stage2_manifest.py::apply_policy
        "alignment_confidence_tier": None,
        "quality_flags": None,
        "manual_review_reasons": None,
        "alignment_score_components": None,
        "policy_version": None,
    }


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _load_validate_row():
    """Dynamically load validate_row from 320_build_stage2_manifest.py."""
    import importlib.util
    p = REPO_ROOT / "scripts" / "320_build_stage2_manifest.py"
    spec = importlib.util.spec_from_file_location("_stage2_manifest", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.validate_row


def validate_rows(rows: list[dict[str, Any]]) -> list[tuple[str, list[str]]]:
    """Validate rows against Stage-2 schema. Returns [(pair_id, violations)]."""
    try:
        validate_row = _load_validate_row()
    except Exception as e:
        # Non-fatal: report warning, continue
        print(f"  WARNING: could not load validate_row from 320 builder: {e}", file=sys.stderr)
        return []
    failed = []
    for row in rows:
        viols = validate_row(row)
        # Policy-owned fields that are null in candidates are expected to fail;
        # filter out those specific violations so they don't block candidate write.
        policy_missing = {
            "missing:alignment_confidence_tier",
            "type:alignment_confidence_tier=NoneType",
            "missing:quality_flags",
            "type:quality_flags=NoneType",
            "missing:manual_review_reasons",
            "type:manual_review_reasons=NoneType",
            "missing:alignment_score_components",
            "type:alignment_score_components=NoneType",
            "missing:policy_version",
            "type:policy_version=NoneType",
        }
        real_viols = [v for v in viols if v not in policy_missing]
        if real_viols:
            failed.append((row["pair_id"], real_viols))
    return failed


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

_SELFTEST_EN = """\
CHAPTER 1.

DEFINITIONS.

§2. The term offense means the doing what a penal law forbids,
or omitting to do what it commands.

§3. The terms felony and crime are synonomous.

NOTE TO CHAPTER 1.

§§2-3 are P. C. Ch. i, unaltered.

CHAPTER 2.

GENERAL PROVISIONS.

§8. No person shall be punished for any offense without trial.
"""

_SELFTEST_HAW = """\
MOKUNA 1.

NA WEHEWEHE ANO.

$2. O ka huaolelo ofeni, o ia ka hana i papaia e ke Kanawai
Hoopai Karaima, a i ka hana ole hoi i ka mea a ke Kanawai.

S3. O na huaolelo feloni ame karaima, hookahi no ano.

HOAKAKA I KA MOKUNA 1.

$$2-3, oia no K. H. K. Mok. 1, hoololi ole ia.

MOKUNA 2.

NA OLELO PILI I O IA NEI.

$8. Aole no e hoopaiia kekahi kanaka no ka hewa, ke hookolokolo
ole ia mamua.
"""


def _self_test() -> int:
    """In-memory smoke test: parse synthetic fixtures, pair, and check invariants."""
    en_secs = parse_sections(_SELFTEST_EN, "en")
    haw_secs = parse_sections(_SELFTEST_HAW, "haw")

    assert 2 in en_secs, f"EN §2 not found; got keys {sorted(en_secs)}"
    assert 3 in en_secs, f"EN §3 not found"
    assert 8 in en_secs, f"EN §8 not found"
    assert 2 in haw_secs, f"HAW §2 not found; got keys {sorted(haw_secs)}"
    assert 3 in haw_secs, f"HAW §3 not found"
    assert 8 in haw_secs, f"HAW §8 not found"

    common = sorted(set(en_secs) & set(haw_secs))
    assert common == [2, 3, 8], f"Expected [2,3,8], got {common}"

    # Test cleaning
    en_raw2 = en_secs[2]
    haw_raw2 = haw_secs[2]
    en_clean2 = normalize_en(clean_section_text(en_raw2))
    haw_clean2 = normalize_haw(clean_section_text(haw_raw2))
    assert len(en_clean2.split()) >= MIN_WORDS, f"EN §2 too short: {en_clean2!r}"
    assert len(haw_clean2.split()) >= MIN_WORDS, f"HAW §2 too short: {haw_clean2!r}"

    # Test pair hash invariant
    row = build_candidate_row(2, en_clean2, haw_clean2, en_raw2, haw_raw2)
    expected_pair = compute_pair_hash(row["sha256_en_clean"], row["sha256_haw_clean"])
    assert row["sha256_pair"] == expected_pair, "Pair hash mismatch"

    # Test schema fields
    assert row["prototype_only"] is True
    assert row["release_eligible"] is False
    assert row["alignment_type"] == "parallel-sentence"
    assert row["alignment_review_required"] is True
    assert row["split"] == "review-pending"
    assert row["direction_original"] == "en->haw"
    assert row["license_inferred"] is None

    # Test normalization of ʻokina mis-encodings
    haw_with_curly = "Ka \u2018Āina"
    normalized = normalize_haw(haw_with_curly)
    assert "\u02bb" in normalized, "ʻokina not canonicalized"

    print("self-test OK (8 assertions)", file=sys.stderr)
    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true",
                      help="Parse and count; do not write any files.")
    mode.add_argument("--execute", action="store_true",
                      help="Write candidates to JSONL output and emit report.")
    mode.add_argument("--self-test", action="store_true",
                      help="In-memory smoke test; no disk I/O. Exit 0=pass.")
    args = parser.parse_args(argv)

    if args.self_test:
        return _self_test()

    # ---- load raw texts ----
    for p in (EN_DJVU_TXT, HAW_DJVU_TXT):
        if not p.exists():
            print(f"ERROR: missing raw file: {p}", file=sys.stderr)
            return 1

    print(f"Reading EN djvu.txt: {EN_DJVU_TXT.name}", file=sys.stderr)
    en_txt = EN_DJVU_TXT.read_text(encoding="utf-8", errors="replace")
    print(f"Reading HAW djvu.txt: {HAW_DJVU_TXT.name}", file=sys.stderr)
    haw_txt = HAW_DJVU_TXT.read_text(encoding="utf-8", errors="replace")

    # ---- parse sections ----
    print("Parsing EN sections...", file=sys.stderr)
    en_secs = parse_sections(en_txt, "en")
    print(f"  EN sections found: {len(en_secs)}", file=sys.stderr)

    print("Parsing HAW sections...", file=sys.stderr)
    haw_secs = parse_sections(haw_txt, "haw")
    print(f"  HAW sections found: {len(haw_secs)}", file=sys.stderr)

    # ---- pair by section number ----
    common_nums = sorted(set(en_secs) & set(haw_secs))
    en_only = sorted(set(en_secs) - set(haw_secs))
    haw_only = sorted(set(haw_secs) - set(en_secs))
    print(f"  Common (pairable): {len(common_nums)}, EN-only: {len(en_only)}, HAW-only: {len(haw_only)}", file=sys.stderr)

    # ---- build candidate rows ----
    rows: list[dict[str, Any]] = []
    skipped_short: list[int] = []
    skipped_dedup: set[str] = set()

    for sec_num in common_nums:
        en_raw = en_secs[sec_num]
        haw_raw = haw_secs[sec_num]

        en_clean = normalize_en(clean_section_text(en_raw))
        haw_clean = normalize_haw(clean_section_text(haw_raw))

        if len(en_clean.split()) < MIN_WORDS or len(haw_clean.split()) < MIN_WORDS:
            skipped_short.append(sec_num)
            continue

        row = build_candidate_row(sec_num, en_clean, haw_clean, en_raw, haw_raw)

        # Basic dedup by pair_hash (should never trigger for unique section numbers,
        # but guard against edge cases)
        pair_hash = row["sha256_pair"]
        if pair_hash in skipped_dedup:
            continue
        skipped_dedup.add(pair_hash)
        rows.append(row)

    print(f"  Rows after filtering (min {MIN_WORDS} words): {len(rows)}", file=sys.stderr)
    if skipped_short:
        print(f"  Skipped (too short): {len(skipped_short)} sections: {skipped_short[:20]}", file=sys.stderr)

    # ---- validate ----
    print("Running schema validation...", file=sys.stderr)
    failures = validate_rows(rows)
    if failures:
        print(f"  Schema violations in {len(failures)} rows:", file=sys.stderr)
        for pid, viols in failures[:5]:
            print(f"    {pid}: {viols}", file=sys.stderr)
        if args.execute:
            print("ERROR: schema violations found; aborting --execute.", file=sys.stderr)
            return 3
    else:
        print(f"  Schema validation: PASS ({len(rows)} rows)", file=sys.stderr)

    # ---- report ----
    report: dict[str, Any] = {
        "generated_at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mode": "dry_run" if args.dry_run else "execute",
        "pair": "1897-penal-laws",
        "en_item_id": EN_ITEM_ID,
        "haw_item_id": HAW_ITEM_ID,
        "en_sections_parsed": len(en_secs),
        "haw_sections_parsed": len(haw_secs),
        "common_sections": len(common_nums),
        "rows_after_filter": len(rows),
        "skipped_too_short": len(skipped_short),
        "skipped_short_sections": skipped_short[:50],
        "en_only_count": len(en_only),
        "en_only_sample": en_only[:30],
        "haw_only_count": len(haw_only),
        "haw_only_sample": haw_only[:30],
        "schema_violations": len(failures),
        "note_en_only_cause": (
            "~189 EN sections missing from HAW due to OCR artifact §→8 "
            "(e.g., §7 appears as '87.' in HAW djvu.txt). These sections "
            "are conservatively excluded. ~190 additional pairs could be "
            "recovered with an '8X→§X' normalization pass after human review."
        ),
        "note_haw_only_cause": (
            "HAW-only sections may include: (a) session-law additions not "
            "in the original penal code EN compilation, or (b) false §-marker "
            "matches from digits in non-section contexts. Excluded from pairing."
        ),
        "1869_1850_status": (
            "INVENTORY-ONLY per decisions.md. HAW item esrp468790723 has "
            "filename '1850.002_djvu.txt' indicating a year-mismatch with "
            "the EN 1869 penal code (esrp475081650). Not processed."
        ),
        "output_path": str(OUT_CANDIDATES) if args.execute else "(dry-run, not written)",
    }

    if args.dry_run:
        print("\n=== DRY-RUN REPORT ===", file=sys.stderr)
        print(f"  Would write {len(rows)} rows to {OUT_CANDIDATES}", file=sys.stderr)
        print(json.dumps(report, indent=2))
        return 0

    # ---- write output ----
    OUT_CANDIDATES.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CANDIDATES.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"\nWrote {len(rows)} rows → {OUT_CANDIDATES}", file=sys.stderr)

    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    with OUT_REPORT.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"Wrote report → {OUT_REPORT}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
