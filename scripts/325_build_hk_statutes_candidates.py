#!/usr/bin/env python3
"""Stage-2 HK Statutes section-level candidate builder (Linus).

Reads already-local Internet Archive djvu.txt OCR files for pinned Hawaiian
Kingdom bilingual legal imprints, parses structural section markers, joins EN
and HAW by section key, and emits Stage-2 candidate rows.

Legal/source policy:
  - Sources are Hawaiian Kingdom government legal texts, 1846-1897 imprints.
  - Rights: public domain by US copyright term (pre-1929) and sovereign-edicts
    doctrine for legal text.
  - Host: archive.org only; IA terms snapshot id ``ia_terms`` was captured in
    data/raw/hawaiian-kingdom-statutes-paired-imprints/20260501/manifest_complete.jsonl.
  - This adapter does not perform network fetches in normal candidate mode. The
    small fetch helper exists only so tests can assert User-Agent/rate-limit
    behavior with a mocked HTTP layer.
  - --execute remains gated to the clean 1897 pair. Additional editions are
    edition-pinned and dry-run/inventory-ready, but not executable until their
    alignment blockers are resolved.

Outputs for --execute --edition 1897:
  data/stage2/candidates/hk_statutes_1897.jsonl
  data/stage2/reports/hk_statutes_1897_report.json

Stdlib only. Exit codes: 0 success, 1 I/O/precondition error, 2 CLI misuse,
3 schema error.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import re
import sys
import time
import unicodedata
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
CODE_ROOT = REPO_ROOT / "code"
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))
from llm_hawaii.stage2_canonical import (  # noqa: E402
    canonical_en as stage2_canonical_en,
    canonical_haw as stage2_canonical_haw,
    compute_pair_hash as stage2_compute_pair_hash,
    sha256_text as stage2_sha256_text,
)
RAW_DIR = REPO_ROOT / "data" / "raw" / "hawaiian-kingdom-statutes-paired-imprints" / "20260501"
MANIFEST_COMPLETE = RAW_DIR / "manifest_complete.jsonl"
OUT_DIR = REPO_ROOT / "data" / "stage2" / "candidates"
REPORT_DIR = REPO_ROOT / "data" / "stage2" / "reports"

MANIFEST_SCHEMA_VERSION = "stage2.v0"
FETCH_DATE = "20260501"
TOS_SNAPSHOT_ID = "ia_terms"
TOS_URL = "https://archive.org/about/terms.php"
USER_AGENT = (
    "ideal-spoon/0.1.0 (stage2 HK-statutes adapter; "
    "contact via github.com/yashasg/ideal-spoon; prototype-only)"
)
DEFAULT_RATE_LIMIT_SECONDS = 1.0
LICENSE_OBSERVED = "public-domain-US-pre1929"
RIGHTS_NOTE = (
    "Hawaiian Kingdom government legal text; public domain by US copyright "
    "term (pre-1929) and sovereign-edicts doctrine. archive.org ToS governs "
    "access to hosted scan/OCR bytes."
)

# ʻokina canonicalization (mirrors stage2_quality.py and 322 convention)
OKINA = "\u02bb"
MIN_WORDS = 5

_PAGE_NOISE_RE = re.compile(r"^[A-ZÀ-Ö\s\-–—'.]+\s+\d+\s*$", re.MULTILINE)
_EN_1897_CHAPTER_RE = re.compile(r"^CHAPTER (\d+)\.", re.MULTILINE)
_HAW_1897_CHAPTER_RE = re.compile(r"^MOKUNA (\d+)\.", re.MULTILINE)
_EN_1897_SECTION_RE = re.compile(r"^§(\d+)[,.]", re.MULTILINE)
_HAW_1897_SECTION_RE = re.compile(r"^[\$S](\d+)[,.]", re.MULTILINE)

# Dry-run inventory parsers for older editions. They are intentionally
# conservative: they recover numeric section/Pauku IDs only, and --execute is
# blocked until edition-specific alignment review resolves known mismatches.
_EN_NUMERIC_SECTION_RE = re.compile(r"^Section\s+(\d+)[\.,]", re.MULTILINE | re.IGNORECASE)
_HAW_PAUKU_NUMERIC_RE = re.compile(r"^Pauku\s+(\d+)[\.,]", re.MULTILINE | re.IGNORECASE)
_EN_ROMAN_SECTION_RE = re.compile(r"^Section\s+([IVXLCDM]+)[\.,]", re.MULTILINE | re.IGNORECASE)
_HAW_PAUKU_ROMAN_RE = re.compile(r"^Pauku\s+([IVXLCDM]+)[\.,]", re.MULTILINE | re.IGNORECASE)


@dataclass(frozen=True)
class EditionPin:
    edition: str
    source: str
    pair_label: str
    code_name: str
    en_item_id: str
    haw_item_id: str
    en_filename: str
    haw_filename: str
    en_raw_sha256: str
    haw_raw_sha256: str
    parse_style: str
    direction_original: str
    executable: bool
    status: str
    blocker_note: str | None = None

    @property
    def en_path(self) -> Path:
        return RAW_DIR / f"{self.en_item_id}__{self.en_filename}"

    @property
    def haw_path(self) -> Path:
        return RAW_DIR / f"{self.haw_item_id}__{self.haw_filename}"

    @property
    def en_url(self) -> str:
        return f"https://archive.org/details/{self.en_item_id}"

    @property
    def haw_url(self) -> str:
        return f"https://archive.org/details/{self.haw_item_id}"

    @property
    def edition_or_version(self) -> str:
        return f"HKS-{self.edition}-{self.pair_label}"

    @property
    def out_candidates(self) -> Path:
        return OUT_DIR / f"{self.source}.jsonl"

    @property
    def out_report(self) -> Path:
        return REPORT_DIR / f"{self.source}_report.json"


EDITIONS: dict[str, EditionPin] = {
    "1897": EditionPin(
        edition="1897",
        source="hk_statutes_1897",
        pair_label="1897-penal-laws",
        code_name="Penal Laws",
        en_item_id="esrp641724381",
        haw_item_id="esrp641728581",
        en_filename="1897.001_djvu.txt",
        haw_filename="1897.002_djvu.txt",
        en_raw_sha256="f7c84fc55b8fe1d743ea0a4298dac16e11262e4b985f29ecd4568d739bb0e611",
        haw_raw_sha256="7541498292b153111db1629c044d3a35be46ed77736700b3d763439be1458293",
        parse_style="1897_section_symbol",
        direction_original="en->haw",
        executable=True,
        status="candidate-ready",
    ),
    "1869": EditionPin(
        edition="1869",
        source="hk_statutes_1869",
        pair_label="1869-penal-code",
        code_name="Penal Code",
        en_item_id="esrp475081650",
        haw_item_id="esrp468790723",
        en_filename="1869.001_djvu.txt",
        haw_filename="1850.002_djvu.txt",
        en_raw_sha256="27a211c3f8735f1fcd1cf75771d39f2b8f3b52443e47b36f6dd68b3ff16ea3af",
        haw_raw_sha256="3ca128bb6e7e97abb250b8ce14fda5e5b3c2e1996e01664dc0f401595bb282c5",
        parse_style="numeric_section_pauku",
        direction_original="unknown",
        executable=False,
        status="blocked-content-mismatch",
        blocker_note=(
            "EN item is 1869.001 but HAW local/IA filename is 1850.002; prior "
            "sampling found content mismatch. Do not emit candidates until a true "
            "1869 Hawaiian counterpart is pinned or same-edition equivalence is proven."
        ),
    ),
    "1859": EditionPin(
        edition="1859",
        source="hk_statutes_1859",
        pair_label="1859-civil-code",
        code_name="Civil Code",
        en_item_id="civilcodehawaii00armsgoog",
        haw_item_id="hekumukanawaiam00hawagoog",
        en_filename="civilcodehawaii00armsgoog_djvu.txt",
        haw_filename="hekumukanawaiam00hawagoog_djvu.txt",
        en_raw_sha256="dcf73ea379fb7fdea9d31e339fba5fa4c468b381d63b8f39f8446b99f8b9e4df",
        haw_raw_sha256="f239401826c1ac3ab43f5002129accde0e7ffb8a47bc68325fe9946720a10a4f",
        parse_style="numeric_section_pauku",
        direction_original="unknown",
        executable=False,
        status="in-progress-dryrun-only",
        blocker_note=(
            "Pinned same-host IA pair, but previous sampling showed low section-ID "
            "overlap and uneven OCR. Keep dry-run only until manual spot-check decides "
            "which numeric Pauku range corresponds to the English Civil Code."
        ),
    ),
    "1846": EditionPin(
        edition="1846",
        source="hk_statutes_1846",
        pair_label="1846-statute-laws",
        code_name="Statute Laws",
        en_item_id="statutelawshism00ricogoog",
        haw_item_id="kanawaiikauiaek00ricogoog",
        en_filename="statutelawshism00ricogoog_djvu.txt",
        haw_filename="kanawaiikauiaek00ricogoog_djvu.txt",
        en_raw_sha256="6e053c78cc78e6110734e04551dcd29299a59a85571c75f9935fb99becaab83e",
        haw_raw_sha256="eac630ea3687ba3be38005236031c80c531cd6764d8a08390e69b416b492048b",
        parse_style="roman_or_numeric_section_pauku",
        direction_original="unknown",
        executable=False,
        status="in-progress-dryrun-only",
        blocker_note=(
            "Pinned same-host IA pair. The imprint uses repeated roman/numeric "
            "sections across many acts, so section number alone is not a safe key. "
            "Requires act/chapter segmentation before candidate emission."
        ),
    ),
}


def archive_download_url(item_id: str, filename: str) -> str:
    return f"https://archive.org/download/{item_id}/{filename}"


def fetch_url(
    url: str,
    *,
    opener: Callable[..., Any] = urllib.request.urlopen,
    sleep_fn: Callable[[float], None] = time.sleep,
    rate_limit_seconds: float = DEFAULT_RATE_LIMIT_SECONDS,
) -> tuple[int, str, bytes]:
    """Fetch helper with explicit UA and rate-limit; tests mock opener/sleep."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with opener(req, timeout=120) as resp:
        status = getattr(resp, "status", 200)
        content_type = resp.headers.get("Content-Type", "") if getattr(resp, "headers", None) else ""
        body = resp.read()
    sleep_fn(rate_limit_seconds)
    return status, content_type, body


def normalize_haw(text: str) -> str:
    return stage2_canonical_haw(text)


def normalize_en(text: str) -> str:
    return stage2_canonical_en(text)


def sha256_text(text: str) -> str:
    return stage2_sha256_text(text)


def compute_pair_hash(sha256_en_clean: str, sha256_haw_clean: str) -> str:
    return stage2_compute_pair_hash(sha256_en_clean, sha256_haw_clean)


def _join_hyphenated_lines(text: str) -> str:
    return re.sub(r"-\n(\S)", r"\1", text)


def _remove_page_noise(text: str) -> str:
    return _PAGE_NOISE_RE.sub("", text)


def _collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def clean_section_text(raw: str) -> str:
    return _collapse_whitespace(_remove_page_noise(_join_hyphenated_lines(raw)))


def _find_pc_start(text: str, chapter_pattern: re.Pattern[str]) -> int:
    m = chapter_pattern.search(text)
    return m.start() if m else 0


def _extract_markers(
    text: str,
    section_pattern: re.Pattern[str],
    chapter_pattern: re.Pattern[str] | None,
    pc_start: int,
) -> list[tuple[int, str, str]]:
    markers: list[tuple[int, str, str]] = []
    for m in section_pattern.finditer(text):
        if m.start() >= pc_start:
            markers.append((m.start(), "section", m.group(1)))
    if chapter_pattern is not None:
        for m in chapter_pattern.finditer(text):
            if m.start() >= pc_start:
                markers.append((m.start(), "chapter", m.group(1)))
    markers.sort(key=lambda x: x[0])
    return markers


def _coerce_marker_id(marker: str, occurrence: int, allow_roman: bool) -> str:
    token = marker.strip().upper()
    if token.isdigit():
        return token
    if allow_roman:
        return f"roman-{token}-occ{occurrence}"
    return token


def parse_sections(text: str, language: str, edition: str | EditionPin = "1897") -> dict[str, str]:
    """Parse djvu.txt and return {section_key: raw_section_text}."""
    pin = EDITIONS[edition] if isinstance(edition, str) else edition
    if pin.parse_style == "1897_section_symbol":
        section_re = _EN_1897_SECTION_RE if language == "en" else _HAW_1897_SECTION_RE
        chapter_re = _EN_1897_CHAPTER_RE if language == "en" else _HAW_1897_CHAPTER_RE
        pc_start = _find_pc_start(text, chapter_re)
        allow_roman = False
    elif pin.parse_style == "numeric_section_pauku":
        section_re = _EN_NUMERIC_SECTION_RE if language == "en" else _HAW_PAUKU_NUMERIC_RE
        chapter_re = None
        pc_start = 0
        allow_roman = False
    elif pin.parse_style == "roman_or_numeric_section_pauku":
        if language == "en":
            section_re = re.compile(
                r"^Section\s+([0-9]+|[IVXLCDM]+)[\.,]", re.MULTILINE | re.IGNORECASE
            )
        else:
            section_re = re.compile(
                r"^Pauku\s+([0-9]+|[IVXLCDM]+)[\.,]", re.MULTILINE | re.IGNORECASE
            )
        chapter_re = None
        pc_start = 0
        allow_roman = True
    else:
        raise ValueError(f"unknown parse_style: {pin.parse_style}")

    markers = _extract_markers(text, section_re, chapter_re, pc_start)
    sections: dict[str, str] = {}
    occurrences: dict[str, int] = {}
    for i, (pos, kind, marker) in enumerate(markers):
        if kind != "section":
            continue
        base = marker.strip().upper()
        occurrences[base] = occurrences.get(base, 0) + 1
        key = _coerce_marker_id(base, occurrences[base], allow_roman)
        if not allow_roman and key in sections:
            # For older numeric imprints, repeated OCR section numbers are unsafe;
            # keep the first and report the lost overlap via dry-run counts.
            continue
        next_pos = markers[i + 1][0] if i + 1 < len(markers) else len(text)
        sections[key] = text[pos:next_pos]
    return sections


def length_ratio(haw_text: str, en_text: str) -> float:
    en_words = len(en_text.split())
    return 0.0 if en_words == 0 else round(len(haw_text.split()) / en_words, 4)


def build_candidate_row(
    sec_key: str,
    en_clean: str,
    haw_clean: str,
    en_raw: str,
    haw_raw: str,
    pin: EditionPin | None = None,
) -> dict[str, Any]:
    pin = pin or EDITIONS["1897"]
    sha_en_clean = sha256_text(en_clean)
    sha_haw_clean = sha256_text(haw_clean)
    sha_pair = compute_pair_hash(sha_en_clean, sha_haw_clean)
    pair_id = f"{pin.source}-sec{sec_key}"
    return {
        "pair_id": pair_id,
        "source": pin.source,
        "source_url_en": pin.en_url,
        "source_url_haw": pin.haw_url,
        "fetch_date": FETCH_DATE,
        "sha256_en_raw": pin.en_raw_sha256,
        "sha256_haw_raw": pin.haw_raw_sha256,
        "sha256_en_clean": sha_en_clean,
        "sha256_haw_clean": sha_haw_clean,
        "sha256_pair": sha_pair,
        "record_id_en": f"{pin.en_item_id}-sec{sec_key}",
        "record_id_haw": f"{pin.haw_item_id}-sec{sec_key}",
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
        "direction_original": pin.direction_original,
        "register": "unknown",
        "edition_or_version": pin.edition_or_version,
        "synthetic": False,
        "synthetic_source_model": None,
        "license_observed_en": LICENSE_OBSERVED,
        "license_observed_haw": LICENSE_OBSERVED,
        "license_inferred": None,
        "tos_snapshot_id": TOS_SNAPSHOT_ID,
        "prototype_only": True,
        "release_eligible": False,
        "dedup_cluster_id": pair_id,
        "crosslink_stage1_overlap": False,
        "split": "review-pending",
        "notes": (
            f"{pin.edition} {pin.code_name} bilingual imprint, section key {sec_key}. "
            "Paired by conservative structural section key in parallel djvu.txt OCR files "
            "from archive.org. "
            f"EN item: {pin.en_item_id}; HAW item: {pin.haw_item_id}. "
            f"Raw file sha256: en={pin.en_raw_sha256[:16]}…, haw={pin.haw_raw_sha256[:16]}…. "
            f"Rights: {RIGHTS_NOTE}"
        ),
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "alignment_confidence_tier": None,
        "quality_flags": None,
        "manual_review_reasons": None,
        "alignment_score_components": None,
        "policy_version": None,
    }


def build_rows_from_texts(en_txt: str, haw_txt: str, pin: EditionPin) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    en_secs = parse_sections(en_txt, "en", pin)
    haw_secs = parse_sections(haw_txt, "haw", pin)
    common_keys = sorted(set(en_secs) & set(haw_secs), key=lambda k: (not k.isdigit(), int(k) if k.isdigit() else k))
    en_only = sorted(set(en_secs) - set(haw_secs))
    haw_only = sorted(set(haw_secs) - set(en_secs))

    rows: list[dict[str, Any]] = []
    skipped_short: list[str] = []
    seen_pairs: set[str] = set()
    if pin.executable:
        for sec_key in common_keys:
            en_raw = en_secs[sec_key]
            haw_raw = haw_secs[sec_key]
            en_clean = normalize_en(clean_section_text(en_raw))
            haw_clean = normalize_haw(clean_section_text(haw_raw))
            if len(en_clean.split()) < MIN_WORDS or len(haw_clean.split()) < MIN_WORDS:
                skipped_short.append(sec_key)
                continue
            row = build_candidate_row(sec_key, en_clean, haw_clean, en_raw, haw_raw, pin)
            if row["sha256_pair"] in seen_pairs:
                continue
            seen_pairs.add(row["sha256_pair"])
            rows.append(row)

    report = {
        "pair": pin.pair_label,
        "edition": pin.edition,
        "source": pin.source,
        "status": pin.status,
        "executable": pin.executable,
        "blocker_note": pin.blocker_note,
        "en_item_id": pin.en_item_id,
        "haw_item_id": pin.haw_item_id,
        "en_sections_parsed": len(en_secs),
        "haw_sections_parsed": len(haw_secs),
        "common_sections": len(common_keys),
        "rows_after_filter": len(rows),
        "skipped_too_short": len(skipped_short),
        "skipped_short_sections": skipped_short[:50],
        "en_only_count": len(en_only),
        "en_only_sample": en_only[:30],
        "haw_only_count": len(haw_only),
        "haw_only_sample": haw_only[:30],
    }
    return rows, report


def _load_validate_row():
    import importlib.util

    p = REPO_ROOT / "scripts" / "320_build_stage2_manifest.py"
    spec = importlib.util.spec_from_file_location("_stage2_manifest", p)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod.validate_row


def validate_rows(rows: Iterable[dict[str, Any]]) -> list[tuple[str, list[str]]]:
    try:
        validate_row = _load_validate_row()
    except Exception as e:
        print(f"  WARNING: could not load validate_row from 320 builder: {e}", file=sys.stderr)
        return []
    policy_missing = {
        "missing:alignment_confidence_tier", "type:alignment_confidence_tier=NoneType",
        "missing:quality_flags", "type:quality_flags=NoneType",
        "missing:manual_review_reasons", "type:manual_review_reasons=NoneType",
        "missing:alignment_score_components", "type:alignment_score_components=NoneType",
        "missing:policy_version", "type:policy_version=NoneType",
    }
    failed = []
    for row in rows:
        real_viols = [v for v in validate_row(row) if v not in policy_missing]
        if real_viols:
            failed.append((row["pair_id"], real_viols))
    return failed


_SELFTEST_EN_1897 = """\
CHAPTER 1.
§2. The term offense means the doing what a penal law forbids.
§3. The terms felony and crime are synonomous.
CHAPTER 2.
§8. No person shall be punished for any offense without trial.
"""

_SELFTEST_HAW_1897 = """\
MOKUNA 1.
$2. O ka huaolelo ofeni, o ia ka hana i papaia e ke Kanawai.
S3. O na huaolelo feloni ame karaima, hookahi no ano.
MOKUNA 2.
$8. Aole no e hoopaiia kekahi kanaka no ka hewa.
"""

_SELFTEST_EN_NUMERIC = """\
Section 1. Written law shall be observed by every court in the Kingdom.
Section 2. No private agreement can contravene a public law.
"""

_SELFTEST_HAW_NUMERIC = """\
Pauku 1. E malamaia ke kanawai kakauia e na aha a pau o ke Aupuni.
Pauku 2. Aole e hiki i ka olelo ae like ke kue i ke kanawai akea.
"""


def self_test() -> int:
    rows, report = build_rows_from_texts(_SELFTEST_EN_1897, _SELFTEST_HAW_1897, EDITIONS["1897"])
    assert report["common_sections"] == 3, report
    assert len(rows) == 3, report
    row = rows[0]
    assert row["source"] == "hk_statutes_1897"
    assert row["register"] == "unknown"
    assert row["license_inferred"] is None
    assert row["sha256_pair"] == compute_pair_hash(row["sha256_en_clean"], row["sha256_haw_clean"])
    assert OKINA in normalize_haw("Ka ‘Āina")

    numeric_rows, numeric_report = build_rows_from_texts(
        _SELFTEST_EN_NUMERIC, _SELFTEST_HAW_NUMERIC, EDITIONS["1859"]
    )
    assert numeric_report["common_sections"] == 2, numeric_report
    assert numeric_rows == [], "non-executable editions must stay dry-run/inventory only"
    print("self-test OK", file=sys.stderr)
    return 0


def _read_text_or_fail(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"missing raw file: {path}")
    return path.read_text(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Parse and count; do not write files.")
    mode.add_argument("--execute", action="store_true", help="Write candidate JSONL/report for executable editions only.")
    mode.add_argument("--self-test", action="store_true", help="In-memory smoke test; no disk I/O.")
    parser.add_argument("--edition", choices=sorted(EDITIONS), default="1897")
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()

    pin = EDITIONS[args.edition]
    if args.execute and not pin.executable:
        print(f"ERROR: --execute is blocked for {pin.edition}: {pin.blocker_note}", file=sys.stderr)
        return 1

    try:
        en_txt = _read_text_or_fail(pin.en_path)
        haw_txt = _read_text_or_fail(pin.haw_path)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Reading EN djvu.txt: {pin.en_path.name}", file=sys.stderr)
    print(f"Reading HAW djvu.txt: {pin.haw_path.name}", file=sys.stderr)
    rows, report = build_rows_from_texts(en_txt, haw_txt, pin)

    failures = validate_rows(rows)
    report.update({
        "generated_at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mode": "dry_run" if args.dry_run else "execute",
        "schema_violations": len(failures),
        "tos_snapshot_id": TOS_SNAPSHOT_ID,
        "tos_url": TOS_URL,
        "license_observed": LICENSE_OBSERVED,
        "rights_note": RIGHTS_NOTE,
        "output_path": str(pin.out_candidates) if args.execute else "(dry-run, not written)",
    })

    if failures:
        print(f"Schema violations in {len(failures)} rows", file=sys.stderr)
        for pid, viols in failures[:5]:
            print(f"  {pid}: {viols}", file=sys.stderr)
        if args.execute:
            return 3

    if args.dry_run:
        print("\n=== DRY-RUN REPORT ===", file=sys.stderr)
        print(f"  Would write {len(rows)} rows to {pin.out_candidates}", file=sys.stderr)
        print(json.dumps(report, indent=2))
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with pin.out_candidates.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    with pin.out_report.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"Wrote {len(rows)} rows → {pin.out_candidates}", file=sys.stderr)
    print(f"Wrote report → {pin.out_report}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
