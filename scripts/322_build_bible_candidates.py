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
REGISTRY_PATH = REPO_ROOT / "data-sources" / "bible" / "source_registry.json"
DATA_ROOT = REPO_ROOT / "data"
DEFAULT_OUT = DATA_ROOT / "stage2" / "candidates" / "bible.jsonl"

MANIFEST_SCHEMA_VERSION = "stage2.v0"

# Common ʻokina mis-encodings the policy checks for; we normalize the
# canonical curly mark U+2018 / U+2019 / ASCII apostrophe to U+02BB on
# the Hawaiian side BEFORE hashing so verse-id pair hashes are stable
# across upstream rendering quirks. This mirrors the policy in
# code/llm_hawaii/stage2_quality.py::OKINA_MISENCODINGS.
OKINA = "\u02bb"
OKINA_MISENCODINGS = ("\u2018", "\u2019", "'")


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
    """NFC + canonicalize ʻokina mis-encodings to U+02BB on the haw side."""
    nfc = unicodedata.normalize("NFC", text)
    for bad in OKINA_MISENCODINGS:
        nfc = nfc.replace(bad, OKINA)
    return nfc.strip()


def normalize_en(text: str) -> str:
    """NFC + strip whitespace on the English side."""
    return unicodedata.normalize("NFC", text).strip()


def sha256_text(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def compute_pair_hash(sha256_en_clean: str, sha256_haw_clean: str) -> str:
    return hashlib.sha256(
        (sha256_en_clean + "\u2016" + sha256_haw_clean).encode("utf-8")
    ).hexdigest()


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


def iter_raw_haw_chapters(haw_raw_dir: Path) -> Iterable[tuple[str, int, Path]]:
    """Yield (book_code, chapter, html_path) for raw chapter HTML files.

    Filename convention written by ``206_fetch_baibala_raw.py``:
    ``<BOOK_CODE>_<chapter:03d>.html`` (e.g. ``GEN_001.html``).
    """
    rx = re.compile(r"^([A-Z0-9]{3})_(\d+)\.html$")
    for p in sorted(haw_raw_dir.glob("*.html")):
        m = rx.match(p.name)
        if not m:
            continue
        yield m.group(1), int(m.group(2)), p


def build_rows_from_raw_haw(
    *,
    registry: dict[str, Any],
    haw_raw_dir: Path,
    eng_fixture_dir: Path,
    fetch_date: str,
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

    for book_code, chapter, html_path in iter_raw_haw_chapters(haw_raw_dir):
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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=(
            "Stage-2 Bible verse-id candidate builder (issue #16). Emits "
            "data/stage2/candidates/bible.jsonl from --fixture-dir or "
            "--from-raw inputs."
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
                          "Pairs against eng side from --eng-fixture-dir.")
    src.add_argument("--haw-raw-dir", type=Path, default=None,
                     help="Explicit path to a directory of raw haw chapter HTML files (overrides "
                          "--from-raw path construction; useful for tests).")

    p.add_argument("--eng-fixture-dir", type=Path,
                   default=REPO_ROOT / "code" / "tests" / "fixtures" / "bible",
                   help="When pairing raw haw HTML, read eng/<BOOK>_<chapter>.txt from this dir "
                        "(default: in-tree test fixture).")

    p.add_argument("--out", type=Path, default=DEFAULT_OUT,
                   help=f"Output path (default {DEFAULT_OUT.relative_to(REPO_ROOT)}).")
    p.add_argument("--registry", type=Path, default=REGISTRY_PATH)
    p.add_argument("--fetch-date", default=None,
                   help="Override fetch_date (YYYYMMDD). Default: today UTC.")
    args = p.parse_args(argv)

    registry = load_registry(args.registry)
    fetch_date = args.fetch_date or _today_compact_utc()

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

    if haw_raw_dir is not None:
        if not haw_raw_dir.exists():
            print(f"haw raw dir does not exist: {haw_raw_dir}", file=sys.stderr)
            return 3
        if not args.fetch_date:
            # Prefer the on-disk fetch date if --from-raw used.
            if args.from_raw:
                fetch_date = args.from_raw
        rows, summary = build_rows_from_raw_haw(
            registry=registry,
            haw_raw_dir=haw_raw_dir,
            eng_fixture_dir=args.eng_fixture_dir,
            fetch_date=fetch_date,
        )
        summary["fetch_date"] = fetch_date
        summary["manifest_schema_version"] = MANIFEST_SCHEMA_VERSION
        summary["started_utc"] = _utcnow_iso()
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
