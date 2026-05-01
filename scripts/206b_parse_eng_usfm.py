#!/usr/bin/env python3
"""English Bible USFM parser — Stage-2 adapter helper (issue #16).

Parses KJV / ASV / WEB USFM text from ``.usfm`` files or ``.zip`` archives
into verse-keyed records for use with
``scripts/322_build_bible_candidates.py``.

USFM (Unified Standard Format Markers) structure handled:

  ``\\id BOOKCODE`` — book identifier (e.g. ``GEN``, ``MAT``)
  ``\\c N``         — chapter marker
  ``\\v N text``    — verse N (inline text on same line; may be empty if the
                       next non-blank, non-marker line carries the text)
  ``\\p``, ``\\q1``, ``\\q2``, ``\\b``, ``\\m``, ``\\pi``, ``\\mi`` etc.
                    — paragraph / poetry markers (do not start a new verse;
                       any trailing plain text on the same line is appended
                       to the current verse)

Inline character markers (``\\wj … \\wj*``, ``\\nd … \\nd*``, ``\\add``,
``\\add*``, etc.) are stripped, leaving only plain text content.

Output schema per verse record::

    {
        "book":    "GEN",   # 3-letter USFM book code
        "chapter": 1,       # int
        "verse":   1,       # int
        "text":    "...",   # NFC-normalised, inline markers stripped, stripped
        "source":  "usfm",  # provenance tag
    }

Stdlib only — no new requirements.

CLI::

    # Self-test (no disk I/O):
    python scripts/206b_parse_eng_usfm.py --self-test

    # Parse a single .usfm file → verse JSONL:
    python scripts/206b_parse_eng_usfm.py \\
        --usfm-file data/raw/english-bible-web/GEN.usfm \\
        --out-jsonl data/raw/english-bible-web/GEN_verses.jsonl

    # Parse a .zip of .usfm files → combined verse JSONL:
    python scripts/206b_parse_eng_usfm.py \\
        --usfm-zip  data/raw/english-bible-web/web.zip \\
        --out-jsonl data/raw/english-bible-web/verses.jsonl

Exit codes::

    0  success
    1  self-test failed
    2  misuse (bad CLI args)
    3  parse / IO error
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
import zipfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Inline-marker stripping
# ---------------------------------------------------------------------------

# USFM character (inline) markers and their closing forms.
# Pattern: \ + one or more lowercase letters/digits/+ → strip the marker token.
# e.g. \wj, \wj*, \nd, \nd*, \+wj, \add, \add*, \f, \f*  …
_INLINE_MARKER_RX = re.compile(r"\\[+]?[a-zA-Z][a-zA-Z0-9]*\*?")

# USFM \w word|attributes\w* — eBible KJV/ASV annotated-word markup.
# Captures the bare word before the | and drops all attribute pairs.
# Example: \w beginning|strong="H7225"\w*  →  beginning
_WORD_ATTR_RX = re.compile(r"\\w\s+([^|\s\\]+)\s*\|[^\\]*?\\w\*")

# Belt-and-suspenders: strip any remaining |attr="..." pipe-attribute fragment
# that was not caught above (e.g. a \w marker on a broken/truncated line).
_ATTR_FRAGMENT_RX = re.compile(r'\|[a-zA-Z0-9_-]+=(?:"[^"]*"|\S+)')

# USFM note blocks: \f ... \f*  (footnotes), \fe ... \fe*  (end-notes),
# \x ... \x*  (cross-references).  The entire block including its content
# must be discarded — stripping only the marker tokens leaves the raw
# footnote text (e.g. "1.4 the ligh…") in the verse.
_NOTE_BLOCK_RX = re.compile(r"\\(?:f|fe|x)\b.*?\\(?:f|fe|x)\*", re.DOTALL)

# Paragraph / section markers that may appear at the start of a line but
# should NOT generate text output — we extract any trailing plain text
# fragment after the marker token on the same line instead.
_PARA_MARKER_RX = re.compile(r"^\\[a-zA-Z][a-zA-Z0-9]*(?:\d*)?\s*")

# ``\v N`` line (verse marker with optional verse number bridge ``\v 1-2`` or
# alternate verse tag ``\va 1 \va*``).  We only handle simple integer verses.
_VERSE_MARKER_RX = re.compile(r"^\\v\s+(\d+)\s*(.*)$", re.DOTALL)

# ``\c N`` chapter marker
_CHAP_MARKER_RX = re.compile(r"^\\c\s+(\d+)")

# ``\id BOOKCODE …`` book identifier marker
_ID_MARKER_RX = re.compile(r"^\\id\s+([A-Z0-9]{3})\b")


def _strip_inline_markers(text: str) -> str:
    """Remove USFM inline character markers and word attributes from a text fragment.

    Applied in four passes:
    0. Drop entire note blocks (``\\f … \\f*``, ``\\x … \\x*``, ``\\fe … \\fe*``)
       so that footnote / cross-reference content never leaks into verse text.
    1. Extract bare word from ``\\w word|attrs\\w*`` (eBible KJV/ASV markup).
    2. Strip remaining ``\\marker`` / ``\\marker*`` tokens.
    3. Drop any leftover ``|attr="..."`` pipe-attribute fragments.
    """
    text = _NOTE_BLOCK_RX.sub("", text)
    text = _WORD_ATTR_RX.sub(r"\1", text)
    text = _INLINE_MARKER_RX.sub("", text)
    text = _ATTR_FRAGMENT_RX.sub("", text)
    return text


def _normalise_eng(text: str) -> str:
    """NFC normalise and strip leading/trailing whitespace."""
    return unicodedata.normalize("NFC", re.sub(r"\s+", " ", text)).strip()


# ---------------------------------------------------------------------------
# Core parser
# ---------------------------------------------------------------------------


def parse_usfm_text(
    text: str,
    *,
    source_book_code: str | None = None,
) -> list[dict[str, Any]]:
    """Parse USFM text into a list of verse records.

    ``source_book_code`` overrides the ``\\id`` token if provided.
    Records where text is empty after stripping are silently dropped.
    """
    book_code: str | None = source_book_code
    chapter: int = 0
    verse_no: int | None = None
    verse_buf: list[str] = []
    records: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()  # (chapter, verse) — keep first

    def _flush() -> None:
        nonlocal verse_no
        if verse_no is None or chapter == 0 or book_code is None:
            return
        raw = " ".join(verse_buf)
        clean = _normalise_eng(_strip_inline_markers(raw))
        if clean:
            key = (chapter, verse_no)
            if key not in seen:
                seen.add(key)
                records.append({
                    "book": book_code,
                    "chapter": chapter,
                    "verse": verse_no,
                    "text": clean,
                    "source": "usfm",
                })
        verse_buf.clear()
        verse_no = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Book identifier
        m_id = _ID_MARKER_RX.match(line)
        if m_id:
            if source_book_code is None:
                _flush()
                book_code = m_id.group(1)
            continue

        # Chapter marker
        m_chap = _CHAP_MARKER_RX.match(line)
        if m_chap:
            _flush()
            chapter = int(m_chap.group(1))
            verse_no = None
            continue

        # Verse marker
        m_verse = _VERSE_MARKER_RX.match(line)
        if m_verse:
            _flush()
            verse_no = int(m_verse.group(1))
            tail = m_verse.group(2).strip()
            verse_buf.clear()
            if tail:
                verse_buf.append(tail)
            continue

        # Paragraph / section markers (\\p, \\q1, \\q2, \\b, \\m, \\s …)
        # Any trailing text after the marker is appended to the current verse.
        if line.startswith("\\"):
            tail = _PARA_MARKER_RX.sub("", line).strip()
            if tail and verse_no is not None:
                verse_buf.append(tail)
            continue

        # Plain text continuation line (rare in modern USFM; belt-and-suspenders)
        if verse_no is not None:
            verse_buf.append(line)

    _flush()
    return records


def parse_usfm_file(path: Path) -> list[dict[str, Any]]:
    """Read a ``.usfm`` file and return its verse records."""
    text = path.read_text(encoding="utf-8", errors="replace")
    return parse_usfm_text(text)


def parse_usfm_zip(
    zip_path: Path,
    *,
    book_codes: set[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Parse all ``.usfm`` / ``.SFM`` files inside a zip archive.

    Returns ``{book_code: [verse_record, …]}``.  Files whose parsed book code
    is not in ``book_codes`` (when given) are skipped.
    """
    out: dict[str, list[dict[str, Any]]] = {}
    with zipfile.ZipFile(zip_path, "r") as zf:
        for name in zf.namelist():
            if not name.lower().endswith((".usfm", ".sfm")):
                continue
            raw = zf.read(name).decode("utf-8", errors="replace")
            recs = parse_usfm_text(raw)
            if not recs:
                continue
            bk = recs[0]["book"]
            if book_codes is not None and bk not in book_codes:
                continue
            out.setdefault(bk, []).extend(recs)
    return out


def verses_as_key_map(
    records: list[dict[str, Any]],
) -> dict[tuple[str, int, int], str]:
    """Return ``{(book, chapter, verse): text}`` index for fast lookup."""
    return {(r["book"], r["chapter"], r["verse"]): r["text"] for r in records}


def verses_by_chapter(
    records: list[dict[str, Any]],
) -> dict[tuple[str, int], dict[int, str]]:
    """Return ``{(book, chapter): {verse: text}}`` nested index."""
    out: dict[tuple[str, int], dict[int, str]] = {}
    for r in records:
        key = (r["book"], r["chapter"])
        out.setdefault(key, {})[r["verse"]] = r["text"]
    return out


# ---------------------------------------------------------------------------
# Self-test (no disk I/O)
# ---------------------------------------------------------------------------

_SELF_TEST_USFM = """\
\\id GEN FIXTURE
\\c 1
\\p
\\v 1 In the beginning God created the heavens.
\\v 2 \\wj Now the earth \\wj* was without form.
\\q1 A poetic fragment here.
\\v 3 And God said, Let there be light.
\\c 2
\\p
\\v 1 Thus the heavens and the earth were finished.
"""

_SELF_TEST_EXPECTED: list[tuple[str, int, int, str]] = [
    ("GEN", 1, 1, "In the beginning God created the heavens."),
    ("GEN", 1, 2, "Now the earth was without form. A poetic fragment here."),
    ("GEN", 1, 3, "And God said, Let there be light."),
    ("GEN", 2, 1, "Thus the heavens and the earth were finished."),
]


def self_test() -> bool:
    """Run in-memory assertions. Returns True on pass."""
    recs = parse_usfm_text(_SELF_TEST_USFM)
    if len(recs) != len(_SELF_TEST_EXPECTED):
        print(
            f"FAIL: expected {len(_SELF_TEST_EXPECTED)} records, got {len(recs)}",
            file=sys.stderr,
        )
        for r in recs:
            print(f"  {r}", file=sys.stderr)
        return False
    for i, (rec, (bk, ch, vs, tx)) in enumerate(
        zip(recs, _SELF_TEST_EXPECTED)
    ):
        for attr, got, want in (
            ("book", rec["book"], bk),
            ("chapter", rec["chapter"], ch),
            ("verse", rec["verse"], vs),
            ("text", rec["text"], tx),
        ):
            if got != want:
                print(
                    f"FAIL row {i} {attr}: got {got!r}, want {want!r}",
                    file=sys.stderr,
                )
                return False

    # source_book_code override
    recs2 = parse_usfm_text(_SELF_TEST_USFM, source_book_code="EXO")
    if any(r["book"] != "EXO" for r in recs2):
        print("FAIL: source_book_code override not respected", file=sys.stderr)
        return False

    # verse source tag
    if any(r["source"] != "usfm" for r in recs):
        print("FAIL: source tag not 'usfm'", file=sys.stderr)
        return False

    print("self-test PASSED", file=sys.stderr)
    return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=(
            "English Bible USFM parser helper — Stage-2 adapter (issue #16). "
            "Parses KJV/ASV/WEB .usfm files or .zip archives into verse JSONL."
        ),
    )
    p.add_argument("--self-test", action="store_true",
                   help="Run in-memory self-test and exit (no disk I/O).")

    src = p.add_mutually_exclusive_group()
    src.add_argument("--usfm-file", type=Path,
                     help="Path to a single .usfm file to parse.")
    src.add_argument("--usfm-zip", type=Path,
                     help="Path to a .zip archive containing .usfm files.")

    p.add_argument("--out-jsonl", type=Path, default=None,
                   help="Write parsed verse records as JSONL to this path. "
                        "If omitted, prints a summary to stdout.")
    p.add_argument("--book-codes", default=None,
                   help="Comma-separated book codes to include (e.g. GEN,EXO). "
                        "Default: all books found.")
    args = p.parse_args(argv)

    if args.self_test:
        return 0 if self_test() else 1

    if args.usfm_file is None and args.usfm_zip is None:
        print("error: one of --usfm-file or --usfm-zip is required", file=sys.stderr)
        return 2

    book_filter: set[str] | None = None
    if args.book_codes:
        book_filter = {c.strip().upper() for c in args.book_codes.split(",")}

    records: list[dict[str, Any]] = []
    try:
        if args.usfm_file:
            if not args.usfm_file.exists():
                print(f"error: file not found: {args.usfm_file}", file=sys.stderr)
                return 3
            all_recs = parse_usfm_file(args.usfm_file)
            records = [r for r in all_recs
                       if book_filter is None or r["book"] in book_filter]
        else:
            if not args.usfm_zip.exists():
                print(f"error: zip not found: {args.usfm_zip}", file=sys.stderr)
                return 3
            by_book = parse_usfm_zip(args.usfm_zip, book_codes=book_filter)
            for recs in by_book.values():
                records.extend(recs)
            records.sort(key=lambda r: (r["book"], r["chapter"], r["verse"]))
    except Exception as exc:
        print(f"error parsing USFM: {exc}", file=sys.stderr)
        return 3

    if args.out_jsonl:
        args.out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        with args.out_jsonl.open("w", encoding="utf-8") as fh:
            for r in records:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"wrote {len(records)} verse records → {args.out_jsonl}")
    else:
        books = sorted({r["book"] for r in records})
        print(f"parsed {len(records)} verse records across {len(books)} book(s): {books}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
