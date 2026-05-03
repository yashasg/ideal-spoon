#!/usr/bin/env python3
"""Stage-2 Bible verse-id candidate builder (Frank, issue #16).

Reads parsed verse JSONL from both sides of the pinned (haw, eng) Bible
edition pair and emits ``data/stage2/candidates/bible.jsonl`` — one row
per shared verse id, shaped to pass
``scripts/320_build_stage2_manifest.py --check`` schema validation.

This script is the **adapter contract** half of issue #16. It is fed
either by the live raw fetch (``scripts/206_fetch_baibala_raw.py``,
gated on Linus' edition pin) or by the small in-tree test fixtures
under ``code/tests/fixtures/bible/`` via ``--fixture-dir``.

Inputs (one of):

  * ``--fixture-dir DIR`` (preferred for tests / dry-run on a fresh
    checkout): expects ``DIR/haw/<BOOK>_<CHAPTER>.txt`` and
    ``DIR/eng/<BOOK>_<CHAPTER>.txt`` files where each line is
    ``<verse_number>: <verse text>`` (lines starting with ``#`` are
    comments). UTF-8 only.
  * ``--from-raw <YYYYMMDD>``: reads pre-parsed verse JSONL produced by
    the live HTML parser (TODO; see ``scripts/206_fetch_baibala_raw.py``)
    at ``data/raw/<source_id>/<YYYYMMDD>/verses.jsonl``.

Output (gitignored):

  * ``data/stage2/candidates/bible.jsonl`` — Stage-2 manifest-shaped
    JSONL. One row per verse-id present on BOTH sides.

Stdlib only. NFC + ʻokina canonicalization (U+02BB) is applied per
``code/llm_hawaii/data.py::normalize_text`` semantics; we do not import
the package because this script is stdlib-self-contained for CI.

Exit codes: 0 success, 2 misuse, 3 input error.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import importlib.util
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Iterable

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
REGISTRY_PATH = REPO_ROOT / "data-sources" / "bible" / "source_registry.json"
DATA_ROOT = REPO_ROOT / "data"
DEFAULT_OUT = DATA_ROOT / "stage2" / "candidates" / "bible.jsonl"

MANIFEST_SCHEMA_VERSION = "stage2.v0"

# Common ʻokina mis-encodings the policy checks for; we normalize the
# canonical curly mark U+2018 / U+2019 / ASCII apostrophe to U+02BB on
# the Hawaiian side BEFORE hashing so verse-id pair hashes are stable
# across upstream rendering quirks. This mirrors the policy in
OKINA = "\u02bb"


def _utcnow_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today_compact_utc() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d")


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Normalization (NFC + ʻokina canonicalization)
# ---------------------------------------------------------------------------


def normalize_haw(text: str) -> str:
    return stage2_canonical_haw(text)


def normalize_en(text: str) -> str:
    return stage2_canonical_en(text)


def sha256_text(text: str) -> str:
    return stage2_sha256_text(text)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def compute_pair_hash(sha256_en_clean: str, sha256_haw_clean: str) -> str:
    return stage2_compute_pair_hash(sha256_en_clean, sha256_haw_clean)


# ---------------------------------------------------------------------------
# Fixture / verse-jsonl readers
# ---------------------------------------------------------------------------


_VERSE_RX = re.compile(r"^\s*(\d+)\s*[:.\)]\s*(.+?)\s*$")


def parse_verse_txt(path: Path) -> dict[int, tuple[str, bytes]]:
    """Read a fixture/raw text file. Returns {verse_no: (text, raw_bytes_of_line)}.

    Format: ``<verse_no>: <text>`` per line. Lines beginning with ``#``
    or blank lines are ignored. The ``raw_bytes_of_line`` is the
    UTF-8-encoded line as it appears in the file (no normalization);
    used to compute ``sha256_*_raw``.
    """
    out: dict[int, tuple[str, bytes]] = {}
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        m = _VERSE_RX.match(s)
        if not m:
            continue
        v = int(m.group(1))
        body = m.group(2)
        out[v] = (body, line.encode("utf-8"))
    return out


def iter_fixture_chapters(fixture_dir: Path) -> Iterable[tuple[str, int, Path, Path]]:
    """Yield (book_code, chapter, haw_path, eng_path) for chapters present on BOTH sides."""
    haw_root = fixture_dir / "haw"
    eng_root = fixture_dir / "eng"
    if not haw_root.exists() or not eng_root.exists():
        raise SystemExit(
            f"fixture dir missing haw/ or eng/ subdir: {fixture_dir}"
        )
    rx = re.compile(r"^([A-Z0-9]{3})_(\d+)\.txt$")
    haw_keys: dict[tuple[str, int], Path] = {}
    eng_keys: dict[tuple[str, int], Path] = {}
    for p in sorted(haw_root.glob("*.txt")):
        m = rx.match(p.name)
        if m:
            haw_keys[(m.group(1), int(m.group(2)))] = p
    for p in sorted(eng_root.glob("*.txt")):
        m = rx.match(p.name)
        if m:
            eng_keys[(m.group(1), int(m.group(2)))] = p
    shared = sorted(set(haw_keys) & set(eng_keys))
    for book, chapter in shared:
        yield book, chapter, haw_keys[(book, chapter)], eng_keys[(book, chapter)]


# ---------------------------------------------------------------------------
# Row builder
# ---------------------------------------------------------------------------


def build_rows_for_chapter(
    *,
    registry: dict[str, Any],
    book_code: str,
    chapter: int,
    haw_path: Path,
    eng_path: Path,
    fetch_date: str,
) -> list[dict[str, Any]]:
    haw_verses = parse_verse_txt(haw_path)
    eng_verses = parse_verse_txt(eng_path)
    shared = sorted(set(haw_verses) & set(eng_verses))

    haw_side = registry["sides"]["haw"]
    eng_side = registry["sides"]["eng"]
    align = registry["alignment_defaults"]
    template_haw = haw_side["url_template"]
    template_eng = eng_side["url_template"]

    # Look up per-book greenstone OID for the haw URL template.
    books_index = {b["code"]: b for b in registry["books"]}
    greenstone_oid = books_index.get(book_code, {}).get("greenstone_oid", "")

    # Chapter-level raw sha256s (file contents) — every verse in the
    # chapter shares the same chapter-level raw sha (we are pairing at
    # verse granularity but the raw fetch unit is the chapter HTML).
    sha_haw_raw_chapter = sha256_bytes(haw_path.read_bytes())
    sha_eng_raw_chapter = sha256_bytes(eng_path.read_bytes())

    rows: list[dict[str, Any]] = []
    for v in shared:
        haw_text_raw, _ = haw_verses[v]
        eng_text_raw, _ = eng_verses[v]
        haw_clean = normalize_haw(haw_text_raw)
        eng_clean = normalize_en(eng_text_raw)
        if not haw_clean or not eng_clean:
            continue
        sha_haw_clean = sha256_text(haw_clean)
        sha_en_clean = sha256_text(eng_clean)
        sha_pair = compute_pair_hash(sha_en_clean, sha_haw_clean)

        haw_tokens = len(haw_clean.split()) or 1
        en_tokens = len(eng_clean.split()) or 1
        length_ratio = haw_tokens / en_tokens

        pair_id = f"bible:{book_code}:{chapter}:{v}"
        record_id = f"{book_code}:{chapter}:{v}"
        url_haw = template_haw.format(book_code=book_code, chapter=chapter, greenstone_oid=greenstone_oid)
        url_eng = template_eng.format(book_code=book_code, chapter=chapter, greenstone_oid=greenstone_oid)

        row: dict[str, Any] = {
            "pair_id": pair_id,
            "source": haw_side["source_id"],
            "source_url_en": url_eng,
            "source_url_haw": url_haw,
            "fetch_date": fetch_date,
            "sha256_en_raw": sha_eng_raw_chapter,
            "sha256_haw_raw": sha_haw_raw_chapter,
            "sha256_en_clean": sha_en_clean,
            "sha256_haw_clean": sha_haw_clean,
            "sha256_pair": sha_pair,
            "record_id_en": record_id,
            "record_id_haw": record_id,
            "text_en": eng_clean,
            "text_haw": haw_clean,
            "text_en_path": None,
            "text_haw_path": None,
            "alignment_type": align["alignment_type"],
            "alignment_method": align["alignment_method"],
            "alignment_model": None,
            "alignment_score": align["alignment_score"],
            "alignment_review_required": align["alignment_review_required"],
            "length_ratio_haw_over_en": length_ratio,
            "lang_id_en": "eng",
            "lang_id_en_confidence": 1.0,
            "lang_id_haw": "haw",
            "lang_id_haw_confidence": 1.0,
            "direction_original": align["direction_original"],
            "register": align["register"],
            "edition_or_version": haw_side["edition_or_version"],
            "synthetic": align["synthetic"],
            "synthetic_source_model": None,
            "license_observed_en": eng_side["license_observed"],
            "license_observed_haw": haw_side["license_observed"],
            "license_inferred": None,
            "tos_snapshot_id": None,
            "prototype_only": align["prototype_only"],
            "release_eligible": align["release_eligible"],
            "dedup_cluster_id": pair_id,
            "crosslink_stage1_overlap": False,
            "split": "train",
            "notes": "stage2 verse-id bible adapter (issue #16); intended_use=prototype_private",
            "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        }
        rows.append(row)
    return rows


def _load_fetch_module():
    """Dynamic-load scripts/206_fetch_baibala_raw.py (numeric-prefix module)."""
    if "fetch_baibala_raw" in sys.modules:
        return sys.modules["fetch_baibala_raw"]
    p = REPO_ROOT / "scripts" / "206_fetch_baibala_raw.py"
    spec = importlib.util.spec_from_file_location("fetch_baibala_raw", p)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["fetch_baibala_raw"] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_usfm_parser_module():
    """Dynamic-load scripts/206b_parse_eng_usfm.py."""
    if "parse_eng_usfm" in sys.modules:
        return sys.modules["parse_eng_usfm"]
    p = REPO_ROOT / "scripts" / "206b_parse_eng_usfm.py"
    spec = importlib.util.spec_from_file_location("parse_eng_usfm", p)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["parse_eng_usfm"] = mod
    spec.loader.exec_module(mod)
    return mod


def iter_raw_haw_chapters(
    haw_raw_dir: Path,
    *,
    book_filter: "set[str] | None" = None,
) -> "Iterable[tuple[str, int, Path]]":
    """Yield (book_code, chapter, html_path) for raw chapter HTML files.

    Filename convention written by ``206_fetch_baibala_raw.py``:
    ``<BOOK_CODE>_<chapter:03d>.html`` (e.g. ``GEN_001.html``).

    ``book_filter``: when given, only yield chapters whose book code is in
    the set (e.g. ``{"GEN","EXO","LEV","NUM","DEU"}`` for a Pentateuch run).
    """
    rx = re.compile(r"^([A-Z0-9]{3})_(\d+)\.html$")
    for p in sorted(haw_raw_dir.glob("*.html")):
        m = rx.match(p.name)
        if not m:
            continue
        book_code = m.group(1)
        if book_filter is not None and book_code not in book_filter:
            continue
        yield book_code, int(m.group(2)), p


def build_rows_from_raw_haw(
    *,
    registry: dict[str, Any],
    haw_raw_dir: Path,
    eng_fixture_dir: Path,
    fetch_date: str,
    book_filter: "set[str] | None" = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Pair raw haw HTML chapters with eng fixture text → manifest rows.

    Returns ``(rows, summary)``. Chapters present on the haw raw side but
    missing on the eng side are skipped (logged in summary).
    """
    fetch_mod = _load_fetch_module()
    books_index = {b["code"]: b for b in registry["books"]}
    eng_root = eng_fixture_dir / "eng"
    if not eng_root.exists():
        raise SystemExit(f"missing eng fixture dir: {eng_root}")
    eng_rx = re.compile(r"^([A-Z0-9]{3})_(\d+)\.txt$")
    eng_keys: dict[tuple[str, int], Path] = {}
    for p in sorted(eng_root.glob("*.txt")):
        m = eng_rx.match(p.name)
        if m:
            eng_keys[(m.group(1), int(m.group(2)))] = p

    rows: list[dict[str, Any]] = []
    haw_chapters_seen = 0
    paired_chapters = 0
    skipped_no_eng: list[str] = []

    haw_side = registry["sides"]["haw"]
    eng_side = registry["sides"]["eng"]
    align = registry["alignment_defaults"]
    template_haw = haw_side["url_template"]
    template_eng = eng_side["url_template"]

    for book_code, chapter, html_path in iter_raw_haw_chapters(haw_raw_dir, book_filter=book_filter):
        haw_chapters_seen += 1
        book = books_index.get(book_code)
        if book is None:
            continue
        eng_path = eng_keys.get((book_code, chapter))
        if eng_path is None:
            skipped_no_eng.append(f"{book_code}:{chapter}")
            continue
        html_bytes = html_path.read_bytes()
        haw_records = fetch_mod.parse_baibala_chapter_html(
            html_bytes,
            book_code=book_code,
            chapter=chapter,
            book_name_lower=book.get("book_name_lower"),
        )
        if not haw_records:
            continue
        haw_verses_by_no: dict[int, str] = {r["verse"]: r["text"] for r in haw_records}
        eng_verses = parse_verse_txt(eng_path)
        shared = sorted(set(haw_verses_by_no) & set(eng_verses))
        if not shared:
            continue

        sha_haw_raw_chapter = sha256_bytes(html_bytes)
        sha_eng_raw_chapter = sha256_bytes(eng_path.read_bytes())
        greenstone_oid = book.get("greenstone_oid", "")

        for v in shared:
            haw_clean = haw_records  # placeholder for type
            haw_clean = haw_verses_by_no[v]  # already normalized by parser
            eng_text_raw, _ = eng_verses[v]
            eng_clean = normalize_en(eng_text_raw)
            if not haw_clean or not eng_clean:
                continue
            sha_haw_clean = sha256_text(haw_clean)
            sha_en_clean = sha256_text(eng_clean)
            sha_pair = compute_pair_hash(sha_en_clean, sha_haw_clean)

            haw_tokens = len(haw_clean.split()) or 1
            en_tokens = len(eng_clean.split()) or 1
            length_ratio = haw_tokens / en_tokens

            pair_id = f"bible:{book_code}:{chapter}:{v}"
            record_id = f"{book_code}:{chapter}:{v}"
            url_haw = template_haw.format(book_code=book_code, chapter=chapter, greenstone_oid=greenstone_oid)
            url_eng = template_eng.format(book_code=book_code, chapter=chapter, greenstone_oid=greenstone_oid)

            rows.append({
                "pair_id": pair_id,
                "source": haw_side["source_id"],
                "source_url_en": url_eng,
                "source_url_haw": url_haw,
                "fetch_date": fetch_date,
                "sha256_en_raw": sha_eng_raw_chapter,
                "sha256_haw_raw": sha_haw_raw_chapter,
                "sha256_en_clean": sha_en_clean,
                "sha256_haw_clean": sha_haw_clean,
                "sha256_pair": sha_pair,
                "record_id_en": record_id,
                "record_id_haw": record_id,
                "text_en": eng_clean,
                "text_haw": haw_clean,
                "text_en_path": None,
                "text_haw_path": None,
                "alignment_type": align["alignment_type"],
                "alignment_method": align["alignment_method"],
                "alignment_model": None,
                "alignment_score": align["alignment_score"],
                "alignment_review_required": align["alignment_review_required"],
                "length_ratio_haw_over_en": length_ratio,
                "lang_id_en": "eng",
                "lang_id_en_confidence": 1.0,
                "lang_id_haw": "haw",
                "lang_id_haw_confidence": 1.0,
                "direction_original": align["direction_original"],
                "register": align["register"],
                "edition_or_version": haw_side["edition_or_version"],
                "synthetic": align["synthetic"],
                "synthetic_source_model": None,
                "license_observed_en": eng_side["license_observed"],
                "license_observed_haw": haw_side["license_observed"],
                "license_inferred": None,
                "tos_snapshot_id": None,
                "prototype_only": align["prototype_only"],
                "release_eligible": align["release_eligible"],
                "dedup_cluster_id": pair_id,
                "crosslink_stage1_overlap": False,
                "split": "train",
                "notes": "stage2 verse-id bible adapter (issue #16); intended_use=prototype_private; src=raw_html",
                "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
            })
        paired_chapters += 1

    summary = {
        "haw_raw_dir": str(haw_raw_dir),
        "eng_fixture_dir": str(eng_fixture_dir),
        "haw_chapters_seen": haw_chapters_seen,
        "chapters_paired": paired_chapters,
        "rows_emitted": len(rows),
        "skipped_no_eng_match": skipped_no_eng,
    }
    return rows, summary


def build_rows_from_usfm_eng(
    *,
    registry: dict[str, Any],
    haw_raw_dir: Path,
    eng_usfm_verses: dict[tuple[str, int], dict[int, str]],
    fetch_date: str,
    eng_usfm_source_path: str = "",
    book_filter: "set[str] | None" = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Pair raw haw HTML chapters with USFM-parsed English verses.

    ``eng_usfm_verses`` is a ``{(book_code, chapter): {verse_no: text}}``
    mapping produced by ``_load_usfm_parser_module().verses_by_chapter()``.

    ``book_filter``: when given, only process chapters whose book code is in
    the set.  Passed through to :func:`iter_raw_haw_chapters`.

    Returns ``(rows, summary)``.  Chapters with no matching eng USFM
    coverage are skipped and noted in the summary.
    """
    fetch_mod = _load_fetch_module()
    books_index = {b["code"]: b for b in registry["books"]}

    rows: list[dict[str, Any]] = []
    haw_chapters_seen = 0
    paired_chapters = 0
    skipped_no_eng: list[str] = []

    haw_side = registry["sides"]["haw"]
    eng_side = registry["sides"]["eng"]
    align = registry["alignment_defaults"]
    template_haw = haw_side["url_template"]
    template_eng = eng_side["url_template"]

    for book_code, chapter, html_path in iter_raw_haw_chapters(haw_raw_dir, book_filter=book_filter):
        haw_chapters_seen += 1
        book = books_index.get(book_code)
        if book is None:
            continue
        eng_verses = eng_usfm_verses.get((book_code, chapter))
        if not eng_verses:
            skipped_no_eng.append(f"{book_code}:{chapter}")
            continue
        html_bytes = html_path.read_bytes()
        haw_records = fetch_mod.parse_baibala_chapter_html(
            html_bytes,
            book_code=book_code,
            chapter=chapter,
            book_name_lower=book.get("book_name_lower"),
        )
        if not haw_records:
            continue
        haw_verses_by_no: dict[int, str] = {r["verse"]: r["text"] for r in haw_records}
        shared = sorted(set(haw_verses_by_no) & set(eng_verses))
        if not shared:
            continue

        sha_haw_raw_chapter = sha256_bytes(html_bytes)
        sha_eng_raw_chapter = sha256_text(eng_usfm_source_path or "usfm")
        greenstone_oid = book.get("greenstone_oid", "")

        for v in shared:
            haw_clean = haw_verses_by_no[v]
            eng_clean = normalize_en(eng_verses[v])
            if not haw_clean or not eng_clean:
                continue
            sha_haw_clean = sha256_text(haw_clean)
            sha_en_clean = sha256_text(eng_clean)
            sha_pair = compute_pair_hash(sha_en_clean, sha_haw_clean)

            haw_tokens = len(haw_clean.split()) or 1
            en_tokens = len(eng_clean.split()) or 1
            length_ratio = haw_tokens / en_tokens

            pair_id = f"bible:{book_code}:{chapter}:{v}"
            record_id = f"{book_code}:{chapter}:{v}"
            url_haw = template_haw.format(book_code=book_code, chapter=chapter, greenstone_oid=greenstone_oid)
            url_eng = template_eng.format(book_code=book_code, chapter=chapter, greenstone_oid=greenstone_oid)

            rows.append({
                "pair_id": pair_id,
                "source": haw_side["source_id"],
                "source_url_en": url_eng,
                "source_url_haw": url_haw,
                "fetch_date": fetch_date,
                "sha256_en_raw": sha_eng_raw_chapter,
                "sha256_haw_raw": sha_haw_raw_chapter,
                "sha256_en_clean": sha_en_clean,
                "sha256_haw_clean": sha_haw_clean,
                "sha256_pair": sha_pair,
                "record_id_en": record_id,
                "record_id_haw": record_id,
                "text_en": eng_clean,
                "text_haw": haw_clean,
                "text_en_path": None,
                "text_haw_path": None,
                "alignment_type": align["alignment_type"],
                "alignment_method": align["alignment_method"],
                "alignment_model": None,
                "alignment_score": align["alignment_score"],
                "alignment_review_required": align["alignment_review_required"],
                "length_ratio_haw_over_en": length_ratio,
                "lang_id_en": "eng",
                "lang_id_en_confidence": 1.0,
                "lang_id_haw": "haw",
                "lang_id_haw_confidence": 1.0,
                "direction_original": align["direction_original"],
                "register": align["register"],
                "edition_or_version": haw_side["edition_or_version"],
                "synthetic": align["synthetic"],
                "synthetic_source_model": None,
                "license_observed_en": eng_side["license_observed"],
                "license_observed_haw": haw_side["license_observed"],
                "license_inferred": None,
                "tos_snapshot_id": None,
                "prototype_only": align["prototype_only"],
                "release_eligible": align["release_eligible"],
                "dedup_cluster_id": pair_id,
                "crosslink_stage1_overlap": False,
                "split": "train",
                "notes": (
                    "stage2 verse-id bible adapter (issue #16); "
                    "intended_use=prototype_private; src=raw_html+usfm_eng"
                ),
                "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
            })
        paired_chapters += 1

    summary = {
        "haw_raw_dir": str(haw_raw_dir),
        "eng_usfm_source": eng_usfm_source_path,
        "haw_chapters_seen": haw_chapters_seen,
        "chapters_paired": paired_chapters,
        "rows_emitted": len(rows),
        "skipped_no_eng_match": skipped_no_eng,
    }
    return rows, summary


# ---------------------------------------------------------------------------
# Book index map helper
# ---------------------------------------------------------------------------


def _build_book_index_map(registry: dict[str, Any]) -> dict[str, str]:
    """Build ``{two_digit_prefix: book_code}`` from the registry books list.

    The KJV TSV ``orig_book_index`` field uses a 2-digit 1-based position
    followed by ``O`` (Old Testament) or ``N`` (New Testament), e.g.
    ``01O`` → GEN (position 1), ``40N`` → MAT (position 40), ``66N`` → REV.
    We use only the leading 2 digits; the O/N suffix is informational.
    """
    return {f"{i:02d}": b["code"] for i, b in enumerate(registry["books"], 1)}


# ---------------------------------------------------------------------------
# KJV TSV parser
# ---------------------------------------------------------------------------

_KJV_TSV_HEADER = (
    "orig_book_index", "orig_chapter", "orig_verse",
    "orig_subverse", "order_by", "text",
)


def parse_kjv_tsv(
    tsv_path: Path,
    *,
    book_index_map: dict[str, str],
    book_filter: "set[str] | None" = None,
) -> "tuple[dict[tuple[str, int], dict[int, str]], dict[str, Any]]":
    """Parse ``data/raw/kjv/kjv.usfm`` (which is actually a TSV) into a verse map.

    Header must be tab-separated:
        ``orig_book_index  orig_chapter  orig_verse  orig_subverse  order_by  text``

    Returns ``({(book_code, chapter): {verse: text}}, summary)``.
    Malformed rows (bad column count, non-integer chapter/verse, unknown book
    index prefix, empty text) are skipped and tallied in ``summary``.
    """
    raw_bytes = tsv_path.read_bytes()
    lines = raw_bytes.decode("utf-8").splitlines()
    if not lines:
        raise ValueError(f"KJV TSV is empty: {tsv_path}")
    # Validate header (tab-separated)
    header_fields = tuple(lines[0].rstrip("\r").split("\t"))
    if header_fields[:6] != _KJV_TSV_HEADER:
        raise ValueError(
            f"KJV TSV header mismatch:\n  expected {_KJV_TSV_HEADER!r}\n"
            f"  got     {header_fields[:6]!r}"
        )

    out: dict[tuple[str, int], dict[int, str]] = {}
    total_read = 0
    malformed = 0
    for raw in lines[1:]:
        raw = raw.rstrip("\r")
        if not raw:
            continue
        cols = raw.split("\t")
        if len(cols) < 6:
            malformed += 1
            continue
        orig_book_index = cols[0]
        orig_ch, orig_v = cols[1], cols[2]
        # cols[3] = orig_subverse, cols[4] = order_by
        text = "\t".join(cols[5:])
        total_read += 1

        numeric_prefix = orig_book_index[:2]
        book_code = book_index_map.get(numeric_prefix)
        if book_code is None:
            malformed += 1
            total_read -= 1
            continue
        if book_filter is not None and book_code not in book_filter:
            total_read -= 1
            continue
        try:
            chapter = int(orig_ch)
            verse = int(orig_v)
        except ValueError:
            malformed += 1
            total_read -= 1
            continue
        text = text.strip()
        if not text:
            malformed += 1
            total_read -= 1
            continue
        key = (book_code, chapter)
        if key not in out:
            out[key] = {}
        if verse not in out[key]:
            out[key][verse] = normalize_en(text)

    verses_total = sum(len(v) for v in out.values())
    summary: dict[str, Any] = {
        "path": str(tsv_path),
        "total_rows_read": total_read,
        "malformed_skipped": malformed,
        "verses_parsed": verses_total,
        "books_found_count": len({k[0] for k in out}),
    }
    return out, summary


# ---------------------------------------------------------------------------
# haw1868 USFM directory parser
# ---------------------------------------------------------------------------

_HAW1868_FNAME_RX = re.compile(r"^\d+-([A-Z0-9]{3})haw1868\.usfm$", re.IGNORECASE)


def parse_haw1868_usfm_dir(
    usfm_dir: Path,
    *,
    book_filter: "set[str] | None" = None,
) -> "tuple[dict[tuple[str, int], dict[int, str]], dict[str, bytes]]":
    """Parse all haw1868 USFM files in *usfm_dir*.

    Filename convention: ``DD-BOOKhaw1868.usfm`` (e.g. ``02-GENhaw1868.usfm``).
    Hawaiian text is normalised via :func:`normalize_haw` before storage.

    Returns:
        ``(verses_map, file_bytes_map)`` where ``verses_map`` is
        ``{(book_code, chapter): {verse: text}}`` and ``file_bytes_map`` is
        ``{book_code: raw_file_bytes}`` for sha256 computation.
    """
    usfm_mod = _load_usfm_parser_module()
    verses_map: dict[tuple[str, int], dict[int, str]] = {}
    file_bytes_map: dict[str, bytes] = {}
    for path in sorted(usfm_dir.glob("*.usfm")):
        m = _HAW1868_FNAME_RX.match(path.name)
        if not m:
            continue
        book_code = m.group(1).upper()
        if book_filter is not None and book_code not in book_filter:
            continue
        raw_bytes = path.read_bytes()
        file_bytes_map[book_code] = raw_bytes
        text = raw_bytes.decode("utf-8")
        recs = usfm_mod.parse_usfm_text(text, source_book_code=book_code)
        for r in recs:
            ch = r["chapter"]
            v = r["verse"]
            haw_text = normalize_haw(r["text"])
            if not haw_text:
                continue
            key = (book_code, ch)
            if key not in verses_map:
                verses_map[key] = {}
            if v not in verses_map[key]:
                verses_map[key][v] = haw_text
    return verses_map, file_bytes_map


# ---------------------------------------------------------------------------
# haw1868 USFM + KJV TSV row builder
# ---------------------------------------------------------------------------

_HAW1868_SOURCE_ID = "baibala-hemolele-1868"
_HAW1868_EDITION = "haw1868-usfm+kjv-tsv"
_HAW1868_LICENSE_HAW = (
    "Public domain — 1868 Hawaiian Bible (Baibala Hemolele 1868), "
    "pre-1925 US work."
)
_KJV_LICENSE_EN = (
    "Public domain — King James Version 1611 (pre-1925, US public domain)."
)


def build_rows_from_haw1868_kjv_tsv(
    *,
    registry: dict[str, Any],
    haw_usfm_dir: Path,
    kjv_tsv_path: Path,
    fetch_date: str,
    book_filter: "set[str] | None" = None,
) -> "tuple[list[dict[str, Any]], dict[str, Any]]":
    """Pair haw1868 USFM verses with KJV TSV anchor → manifest-shaped rows.

    Returns ``(rows, summary)`` where summary contains verse counts for
    both sides, shared-key count, rows emitted, missing-side counts,
    source paths, and fetch_date. Suitable for dry-run JSON printing.
    """
    book_index_map = _build_book_index_map(registry)
    books_index = {b["code"]: b for b in registry["books"]}
    align = registry["alignment_defaults"]

    haw_verses, haw_file_bytes = parse_haw1868_usfm_dir(
        haw_usfm_dir, book_filter=book_filter
    )
    kjv_verses, kjv_summary = parse_kjv_tsv(
        kjv_tsv_path, book_index_map=book_index_map, book_filter=book_filter
    )

    sha_kjv_raw = sha256_bytes(kjv_tsv_path.read_bytes())

    haw_verse_count = sum(len(v) for v in haw_verses.values())
    eng_verse_count = kjv_summary["verses_parsed"]

    haw_keys: set[tuple[str, int, int]] = {
        (book, ch, v)
        for (book, ch), vs in haw_verses.items()
        for v in vs
    }
    eng_keys: set[tuple[str, int, int]] = {
        (book, ch, v)
        for (book, ch), vs in kjv_verses.items()
        for v in vs
    }

    shared_keys = sorted(haw_keys & eng_keys)
    missing_haw = len(eng_keys - haw_keys)
    missing_eng = len(haw_keys - eng_keys)

    rows: list[dict[str, Any]] = []
    for book_code, chapter, v in shared_keys:
        haw_clean = haw_verses[(book_code, chapter)][v]
        eng_clean = kjv_verses[(book_code, chapter)][v]
        if not haw_clean or not eng_clean:
            continue
        sha_haw_clean = sha256_text(haw_clean)
        sha_en_clean = sha256_text(eng_clean)
        sha_pair = compute_pair_hash(sha_en_clean, sha_haw_clean)

        haw_tokens = len(haw_clean.split()) or 1
        en_tokens = len(eng_clean.split()) or 1
        length_ratio = haw_tokens / en_tokens

        pair_id = f"bible:{book_code}:{chapter}:{v}"
        record_id = f"{book_code}:{chapter}:{v}"
        sha_haw_raw = sha256_bytes(haw_file_bytes.get(book_code, b""))

        rows.append({
            "pair_id": pair_id,
            "source": _HAW1868_SOURCE_ID,
            "source_url_en": "",
            "source_url_haw": "",
            "fetch_date": fetch_date,
            "sha256_en_raw": sha_kjv_raw,
            "sha256_haw_raw": sha_haw_raw,
            "sha256_en_clean": sha_en_clean,
            "sha256_haw_clean": sha_haw_clean,
            "sha256_pair": sha_pair,
            "record_id_en": record_id,
            "record_id_haw": record_id,
            "text_en": eng_clean,
            "text_haw": haw_clean,
            "text_en_path": None,
            "text_haw_path": None,
            "alignment_type": align["alignment_type"],
            "alignment_method": align["alignment_method"],
            "alignment_model": None,
            "alignment_score": align["alignment_score"],
            "alignment_review_required": align["alignment_review_required"],
            "length_ratio_haw_over_en": length_ratio,
            "lang_id_en": "eng",
            "lang_id_en_confidence": 1.0,
            "lang_id_haw": "haw",
            "lang_id_haw_confidence": 1.0,
            "direction_original": align["direction_original"],
            "register": align["register"],
            "edition_or_version": _HAW1868_EDITION,
            "synthetic": align["synthetic"],
            "synthetic_source_model": None,
            "license_observed_en": _KJV_LICENSE_EN,
            "license_observed_haw": _HAW1868_LICENSE_HAW,
            "license_inferred": None,
            "tos_snapshot_id": None,
            "prototype_only": align["prototype_only"],
            "release_eligible": align["release_eligible"],
            "dedup_cluster_id": pair_id,
            "crosslink_stage1_overlap": False,
            "split": "train",
            "notes": (
                "stage2 verse-id bible adapter; src=haw1868-usfm+kjv-tsv; "
                "intended_use=prototype_private"
            ),
            "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        })

    summary: dict[str, Any] = {
        "haw_usfm_dir": str(haw_usfm_dir),
        "kjv_tsv_path": str(kjv_tsv_path),
        "fetch_date": fetch_date,
        "haw_verses": haw_verse_count,
        "eng_verses": eng_verse_count,
        "shared_keys": len(shared_keys),
        "rows_emitted": len(rows),
        "missing_haw_side": missing_haw,
        "missing_eng_side": missing_eng,
        "kjv_malformed_skipped": kjv_summary["malformed_skipped"],
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "started_utc": _utcnow_iso(),
    }
    return rows, summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=(
            "Stage-2 Bible verse-id candidate builder (issue #16). Emits "
            "data/stage2/candidates/bible.jsonl from --fixture-dir, "
            "--from-raw, --haw-raw-dir + USFM eng inputs, or the "
            "--haw-usfm-dir + --eng-kjv-tsv-file local-file mode."
        ),
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true",
                      help="Build rows in-memory and print summary; do not write the JSONL. Default if neither flag given.")
    mode.add_argument("--execute", action="store_true",
                      help="Write rows to data/stage2/candidates/bible.jsonl.")

    src = p.add_mutually_exclusive_group()
    src.add_argument("--fixture-dir", type=Path,
                     default=REPO_ROOT / "code" / "tests" / "fixtures" / "bible",
                     help="Fixture directory with haw/ and eng/ subdirs (default: in-tree test fixtures).")
    src.add_argument("--from-raw", default=None,
                     help="YYYYMMDD subdir under data/raw/<haw_source_id>/ to read raw chapter HTML from. "
                          "Pairs against eng side from --eng-fixture-dir or --eng-usfm-file/zip.")
    src.add_argument("--haw-raw-dir", type=Path, default=None,
                     help="Explicit path to a directory of raw haw chapter HTML files (overrides "
                          "--from-raw path construction; useful for tests).")
    src.add_argument("--haw-usfm-dir", type=Path, default=None,
                     help="Directory of haw1868 USFM files (e.g. data/raw/haw1868/haw1868_usfm/). "
                          "Must be paired with --eng-kjv-tsv-file.")

    p.add_argument("--eng-fixture-dir", type=Path,
                   default=REPO_ROOT / "code" / "tests" / "fixtures" / "bible",
                   help="When pairing raw haw HTML (no USFM), read eng/<BOOK>_<chapter>.txt from this dir "
                        "(default: in-tree test fixture).")

    eng_usfm = p.add_mutually_exclusive_group()
    eng_usfm.add_argument("--eng-usfm-file", type=Path, default=None,
                          help="Path to a single English .usfm file. Overrides --eng-fixture-dir "
                               "when pairing raw haw HTML.")
    eng_usfm.add_argument("--eng-usfm-zip", type=Path, default=None,
                          help="Path to a .zip of English .usfm files. Overrides --eng-fixture-dir "
                               "when pairing raw haw HTML.")
    eng_usfm.add_argument("--eng-kjv-tsv-file", type=Path, default=None,
                          help="Path to the KJV TSV file (e.g. data/raw/kjv/kjv.usfm). "
                               "Tab-separated with header: orig_book_index, orig_chapter, "
                               "orig_verse, orig_subverse, order_by, text. "
                               "Required when --haw-usfm-dir is given.")

    p.add_argument("--out", type=Path, default=DEFAULT_OUT,
                   help=f"Output path (default {DEFAULT_OUT.relative_to(REPO_ROOT)}).")
    p.add_argument("--registry", type=Path, default=REGISTRY_PATH)
    p.add_argument("--fetch-date", default=None,
                   help="Override fetch_date (YYYYMMDD). Default: today UTC.")
    p.add_argument("--books", default=None,
                   help="Comma-separated book codes to process (e.g. GEN,EXO,LEV,NUM,DEU). "
                        "When set, only chapters for these books are included; all others are "
                        "skipped. Useful for bounded/safe runs when additional books have been "
                        "concurrently fetched but are not yet ready for this pass.")
    args = p.parse_args(argv)

    registry = load_registry(args.registry)
    fetch_date = args.fetch_date or _today_compact_utc()

    # Build book filter set from --books if given.
    book_filter: set[str] | None = None
    if args.books:
        book_filter = {c.strip().upper() for c in args.books.split(",")}

    # Resolve source mode.
    haw_raw_dir: Path | None = args.haw_raw_dir
    if args.from_raw is not None and haw_raw_dir is None:
        if not re.fullmatch(r"\d{8}", args.from_raw):
            print(f"--from-raw must be YYYYMMDD, got {args.from_raw!r}", file=sys.stderr)
            return 2
        haw_source_id = registry["sides"]["haw"]["source_id"]
        haw_raw_dir = REPO_ROOT / "data" / "raw" / haw_source_id / args.from_raw

    rows: list[dict[str, Any]] = []
    summary: dict[str, Any]

    if args.haw_usfm_dir is not None:
        # ----------------------------------------------------------------
        # haw1868 USFM + KJV TSV local-file mode
        # ----------------------------------------------------------------
        if args.eng_kjv_tsv_file is None:
            print(
                "--haw-usfm-dir requires --eng-kjv-tsv-file",
                file=sys.stderr,
            )
            return 2
        if not args.haw_usfm_dir.exists():
            print(f"haw USFM dir does not exist: {args.haw_usfm_dir}", file=sys.stderr)
            return 3
        if not args.eng_kjv_tsv_file.exists():
            print(f"KJV TSV file not found: {args.eng_kjv_tsv_file}", file=sys.stderr)
            return 3
        try:
            rows, summary = build_rows_from_haw1868_kjv_tsv(
                registry=registry,
                haw_usfm_dir=args.haw_usfm_dir,
                kjv_tsv_path=args.eng_kjv_tsv_file,
                fetch_date=fetch_date,
                book_filter=book_filter,
            )
        except Exception as exc:
            print(f"error building haw1868+KJV rows: {exc}", file=sys.stderr)
            return 3
        if book_filter is not None:
            summary["book_filter"] = sorted(book_filter)

    elif haw_raw_dir is not None:
        if not haw_raw_dir.exists():
            print(f"haw raw dir does not exist: {haw_raw_dir}", file=sys.stderr)
            return 3
        if not args.fetch_date:
            if args.from_raw:
                fetch_date = args.from_raw

        # Prefer USFM eng source over fixture txt when provided.
        if args.eng_usfm_file or args.eng_usfm_zip:
            usfm_path: Path = args.eng_usfm_file or args.eng_usfm_zip
            if not usfm_path.exists():
                print(f"USFM source not found: {usfm_path}", file=sys.stderr)
                return 3
            usfm_mod = _load_usfm_parser_module()
            try:
                if args.eng_usfm_file:
                    usfm_recs = usfm_mod.parse_usfm_file(usfm_path)
                else:
                    by_book = usfm_mod.parse_usfm_zip(usfm_path)
                    usfm_recs = [r for recs in by_book.values() for r in recs]
            except Exception as exc:
                print(f"error parsing USFM: {exc}", file=sys.stderr)
                return 3
            eng_usfm_verses = usfm_mod.verses_by_chapter(usfm_recs)
            rows, summary = build_rows_from_usfm_eng(
                registry=registry,
                haw_raw_dir=haw_raw_dir,
                eng_usfm_verses=eng_usfm_verses,
                fetch_date=fetch_date,
                eng_usfm_source_path=str(usfm_path),
                book_filter=book_filter,
            )
        else:
            rows, summary = build_rows_from_raw_haw(
                registry=registry,
                haw_raw_dir=haw_raw_dir,
                eng_fixture_dir=args.eng_fixture_dir,
                fetch_date=fetch_date,
                book_filter=book_filter,
            )
        summary["fetch_date"] = fetch_date
        summary["manifest_schema_version"] = MANIFEST_SCHEMA_VERSION
        summary["started_utc"] = _utcnow_iso()
        if book_filter is not None:
            summary["book_filter"] = sorted(book_filter)
    else:
        fixture_dir: Path = args.fixture_dir
        if not fixture_dir.exists():
            print(f"fixture dir does not exist: {fixture_dir}", file=sys.stderr)
            return 3
        chapter_count = 0
        for book_code, chapter, haw_path, eng_path in iter_fixture_chapters(fixture_dir):
            rows.extend(build_rows_for_chapter(
                registry=registry,
                book_code=book_code,
                chapter=chapter,
                haw_path=haw_path,
                eng_path=eng_path,
                fetch_date=fetch_date,
            ))
            chapter_count += 1
        summary = {
            "fixture_dir": str(fixture_dir.relative_to(REPO_ROOT)) if fixture_dir.is_relative_to(REPO_ROOT) else str(fixture_dir),
            "chapters_paired": chapter_count,
            "rows_emitted": len(rows),
            "fetch_date": fetch_date,
            "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
            "started_utc": _utcnow_iso(),
        }

    if not args.execute:
        print(f"[DRY-RUN] {json.dumps(summary, ensure_ascii=False)}")
        if rows:
            print(f"[DRY-RUN] sample row: {json.dumps(rows[0], ensure_ascii=False)}")
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"[EXECUTE] wrote {len(rows)} rows -> {args.out.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
