#!/usr/bin/env python3
"""Stage-2 Hawaiian Phrase Book (1881) candidate builder (Frank).

Reads the Internet Archive djvu OCR of Bishop's 1881 *Hawaiian Phrase Book.
Na Huaolelo a me na Olelo Kikeke ma ka Olelo Beritania, a me ka Olelo
Hawaii* (item ``hawaiianphrasebo00bishrich``) at::

    data/raw/ulukau-family-sft-candidates/<YYYYMMDD>/
        hawaiianphrasebo00bishrich/hawaiianphrasebo00bishrich_djvu.txt

and extracts EN→HAW phrase pairs from the book's two-column layout
(English on the left, Hawaiian on the right). If Internet Archive's
``*_djvu.xml`` coordinate OCR is present beside ``*_djvu.txt``, it is used as
the primary extraction path; the flattened text block parser remains the
fallback.

The OCR is column-stripped: physical pages contain a section heading
followed by ~30 short phrase rows. The OCR dump arrives in two
recoverable shapes:

  (a) Each phrase is a blank-separated block. EN blocks come first,
      then HAW blocks for the same section. (Common for short, single-
      line phrases.)
  (b) One side is "packed" — many phrase lines glued together with no
      blank between them — while the opposing side stays in shape (a).
      Packed blocks are split iff *every* line ends with terminator
      punctuation ``.!?`` (so we never split a wrapped multi-line
      phrase by mistake).

Pairing algorithm (precision-first):

  1. Read djvu.txt; drop running-head / page-number lines (e.g. ``8
     HAWAIIAN PHRASES.``, ``NA OLELO KIKEKE.`` and known OCR variants
     ``HAWAUAN``, ``HAWAHAN``, ``NA OLBLO``, ``KIKEHE``).
  2. Group remaining lines into blank-separated *blocks*.
  3. For each block: if it has >=2 lines and every line ends with a
     sentence terminator, expand it into N one-line blocks (the
     packed-column case).
  4. Classify each block by language (EN vs HAW vs ambiguous) using a
     conservative letter-set heuristic.
  5. Coalesce consecutive blocks of the same language into a *run*.
  6. Pair each (EN-run, HAW-run) of equal block count and emit one row
     per index. Mismatched runs are skipped (we never invent pairings).

Conservative quality gates per emitted row:

  * Both sides non-empty after NFC normalization and whitespace collapse.
  * EN side: contains at least one alpha token and is dominated by
    English/Latin letters (>=20% letters from ``[bcdfgrstvxyz]`` or
    contains common EN function words).
  * HAW side: every alpha token is composed of letters from a
    permissive Hawaiian-OCR set (the 13-letter Hawaiian alphabet plus
    ``b f g r t`` for documented loanwords like ``berena``, ``fiku``,
    ``roke``, ``tabu``); reject if any token has 3 consecutive
    consonants from the strict Hawaiian set (OCR garbage proxy).
  * Token count: 1..40 per side.
  * Length ratio HAW/EN ∈ [0.25, 4.0] (loose because phrases are short
    and one-token answers are common).
  * Not page furniture / not pure digits / no ``$ % ~ | < > ^`` chars.
  * Dedupe by ``sha256_pair``.

Provenance preserved on every row:

  * ``source = "ia-hawaiian-phrase-book-1881"``
  * ``source_url_en = source_url_haw =
    https://archive.org/details/hawaiianphrasebo00bishrich``
  * ``edition_or_version = "Bishop 1881 Hawaiian Phrase Book, 4th ed.
    (IA hawaiianphrasebo00bishrich)"``
  * ``record_id_*`` = ``phrase-book-1881:<block_index>``
  * ``sha256_*`` over raw and clean text, plus ``sha256_pair``
  * ``djvu_sha256``, ``djvu_url`` in ``notes``
  * ``license_observed_*`` = "Public Domain (pre-1928, U.S.; IA
    declared NOT_IN_COPYRIGHT)"
  * ``release_eligible = True`` (PD), ``prototype_only = False``
  * ``alignment_review_required = True`` (OCR + 1881 orthography)
  * ``alignment_type = "phrase-pair"``
  * ``alignment_method`` = ``two-column-djvu-xml-coordinate-pairing-v1`` when
    coordinate OCR is available, otherwise ``two-column-djvu-block-pairing-v1``.

Rights: Bishop 1881 is U.S. public domain (pre-1928). IA metadata records
``possible-copyright-status = NOT_IN_COPYRIGHT``.

If pairing produces zero safe rows the script exits 4 with a clear
blocker report rather than emit anything.

Output (gitignored):

    data/stage2/candidates/phrase_book_1881.jsonl
    data/stage2/reports/phrase_book_1881_build_report_<YYYYMMDD>.json

Usage::

    python3 scripts/328_build_phrase_book_candidates.py --dry-run
    python3 scripts/328_build_phrase_book_candidates.py --execute

Exit codes: 0 success, 2 misuse, 3 input error, 4 zero-rows blocker.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any

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
RAW_ROOT = REPO_ROOT / "data" / "raw" / "ulukau-family-sft-candidates"
DEFAULT_OUT = REPO_ROOT / "data" / "stage2" / "candidates" / "phrase_book_1881.jsonl"
DEFAULT_REPORT_DIR = REPO_ROOT / "data" / "stage2" / "reports"

SOURCE_ID = "ia-hawaiian-phrase-book-1881"
IA_ITEM_ID = "hawaiianphrasebo00bishrich"
ITEM_DIRNAME = IA_ITEM_ID
DJVU_FILENAME = f"{IA_ITEM_ID}_djvu.txt"
DJVU_XML_FILENAME = f"{IA_ITEM_ID}_djvu.xml"
SOURCE_URL = f"https://archive.org/details/{IA_ITEM_ID}"
DJVU_URL = f"https://archive.org/download/{IA_ITEM_ID}/{DJVU_FILENAME}"
DJVU_XML_URL = f"https://archive.org/download/{IA_ITEM_ID}/{DJVU_XML_FILENAME}"

LICENSE = "Public Domain (pre-1928, U.S.; IA NOT_IN_COPYRIGHT)"
EDITION = "Bishop 1881 Hawaiian Phrase Book, 4th ed. (IA hawaiianphrasebo00bishrich)"
MANIFEST_SCHEMA_VERSION = "stage2.v0"

OKINA = "\u02bb"

# Running-head / page-furniture detection (case-insensitive). Matches OCR
# variants observed in the dump.
RUNNING_HEAD_RX = re.compile(
    r"^\s*\d*\s*("
    r"HAWAIIAN\s+PHRASES?"
    r"|HAWAUAN\s+PHRASES?"
    r"|HAWAHAN\s+PHRASES?"
    r"|HAWAIIAN\s+PHRASE\s+BOOK"
    r"|NA\s+OL[EB]LO\s+KIKE[KH]E"
    r"|ENGLISH\s+AND\s+HAWAIIAN\s+PHRASE\s+BOOK"
    r")\.?\s*\d*\s*$",
    re.IGNORECASE,
)
PAGE_NUMBER_RX = re.compile(r"^\s*\d{1,4}\s*$")
ROMAN_NUM_RX = re.compile(r"^\s*[ivxlIVXL]+\s*$")
TERMINATOR_RX = re.compile(r"[.!?][)\"']?\s*$")

# A line is sentence-terminator-ended if it ends with .!? optionally followed
# by quote/paren and trailing whitespace. Used to detect "packed" blocks.

# Hawaiian alphabet (lowercased). The bare 13-letter set (plus ʻokina) is
# strict; OCR loanwords also use b/f/g/r/t (e.g. berena, fiku, roke, tabu).
HAW_STRICT = set("aeiouhklmnpw" + OKINA)
HAW_OCR_PERMISSIVE = HAW_STRICT | set("bdfgrt")

# Letters that strongly indicate English (never appear in Hawaiian core or
# documented loan set). We exclude ``d`` because Hawaiian loanwords like
# ``dala`` (dollar) and ``Diabolo`` use it.
EN_ONLY_LETTERS = set("cjqsvxyz")

# English function / closed-class words. Strong EN signal because none of
# these are valid Hawaiian words, and they all appear extremely often in
# English phrase-book rows. We deliberately omit "a" and "i" — both are
# real Hawaiian words ("a"=and/until/of, "i"=in/to/at) and would mis-flag
# many Hawaiian rows as English.
EN_FUNCTION_TOKENS = {
    "the", "an", "of", "and", "to", "is", "in", "on", "at", "or",
    "are", "was", "be", "by", "for", "with", "this", "that", "it", "do",
    "have", "has", "you", "we", "they", "she", "my", "your",
    "what", "where", "when", "how", "why", "who", "from", "as",
    "but", "not", "no", "yes", "if", "so", "all", "some", "any",
    "there", "here",
}

# Hawaiian core consonants (strict alphabet, sans vowels and ʻokina).
HAW_CORE_CONSONANTS = set("hklmnpw")
# All consonants that may legitimately appear in OCR-permissive Hawaiian
# (core + documented loanword letters).
HAW_ANY_CONSONANTS = HAW_CORE_CONSONANTS | set("bdfgrt")
HAW_VOWELS = set("aeiou")

PROHIBITED_CHARS = set("$%~|<>^&*=#\\")
XML_HEADING_RX = re.compile(
    r"\b(ENGLISH|HAWAIIAN|PHRASE\s+BOOK|OLELO\s+KIKE|HUAOLELO)\b",
    re.IGNORECASE,
)


def _today_compact_utc() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d")


def sha256_text(text: str) -> str:
    return stage2_sha256_text(text)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def compute_pair_hash(sha_en: str, sha_haw: str) -> str:
    return stage2_compute_pair_hash(sha_en, sha_haw)


def normalize_text(text: str, *, lang: str = "haw") -> str:
    return stage2_canonical_en(text) if lang == "en" else stage2_canonical_haw(text)


def _resolve_djvu(fetch_date: str | None) -> Path:
    if fetch_date:
        p = RAW_ROOT / fetch_date / ITEM_DIRNAME / DJVU_FILENAME
        if not p.exists():
            raise SystemExit(f"missing: {p}")
        return p
    candidates = sorted(
        p for p in RAW_ROOT.glob(f"*/{ITEM_DIRNAME}/{DJVU_FILENAME}") if p.is_file()
    )
    if not candidates:
        raise SystemExit(
            f"no phrase book djvu under {RAW_ROOT}/<date>/{ITEM_DIRNAME}/"
            f"{DJVU_FILENAME}"
        )
    return candidates[-1]


def _resolve_djvu_xml(djvu_path: Path) -> Path | None:
    xml_path = djvu_path.with_name(DJVU_XML_FILENAME)
    return xml_path if xml_path.exists() else None


def _strip_furniture(line: str) -> str | None:
    """Return cleaned line, or None if it's page furniture and should drop."""
    s = line.strip()
    if not s:
        return ""
    if PAGE_NUMBER_RX.match(s):
        return None
    if ROMAN_NUM_RX.match(s) and len(s) <= 4:
        return None
    if RUNNING_HEAD_RX.match(s):
        return None
    # OCR sometimes glues page number + running head: "8                  HAWAIIAN PHRASES."
    # The regex above already tolerates leading digits.
    return s


def _build_blocks(text: str) -> list[list[str]]:
    """Split into blocks separated by blank lines, after furniture strip."""
    blocks: list[list[str]] = []
    cur: list[str] = []
    for raw in text.splitlines():
        cleaned = _strip_furniture(raw)
        if cleaned is None:
            # Treat furniture as a hard separator.
            if cur:
                blocks.append(cur)
                cur = []
            continue
        if cleaned == "":
            if cur:
                blocks.append(cur)
                cur = []
            continue
        # Collapse internal multi-spaces (OCR pads aggressively).
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if cleaned:
            cur.append(cleaned)
    if cur:
        blocks.append(cur)
    return blocks


def _split_packed(block: list[str]) -> list[list[str]]:
    """If block has >=2 lines and every line ends with .!? expand to one-line blocks."""
    if len(block) < 2:
        return [block]
    if all(TERMINATOR_RX.search(ln) for ln in block):
        return [[ln] for ln in block]
    return [block]


def _is_single_line(block: list[str]) -> bool:
    return len(block) == 1


def _join_wrap(lines: list[str]) -> str:
    """Concatenate wrap lines, fixing trailing-hyphen joins."""
    out: list[str] = []
    for i, ln in enumerate(lines):
        if i == 0:
            out.append(ln)
            continue
        prev = out[-1]
        if prev.endswith("-") and not prev.endswith(" -"):
            # hyphen wrap: pun- + ish -> punish
            out[-1] = prev[:-1] + ln
        else:
            out[-1] = prev + " " + ln
    return out[0] if out else ""


def _haw_strict_morphology_ok(token: str) -> bool:
    """Token passes STRICT Hawaiian shape: only the 13-letter alphabet
    (no loan letters), open-syllable, vowel-final, no clusters, has a vowel.
    """
    if not token:
        return False
    low = token.lower()
    for c in low:
        if c == OKINA:
            continue
        if c in HAW_VOWELS:
            continue
        if c in HAW_CORE_CONSONANTS:
            continue
        return False  # any non-strict letter -> reject
    if not any(c in HAW_VOWELS for c in low):
        return False
    if low[-1] not in HAW_VOWELS:
        return False
    prev_consonant = False
    for c in low:
        is_cons = c in HAW_CORE_CONSONANTS or c == OKINA
        if is_cons and prev_consonant:
            return False
        prev_consonant = is_cons
    return True


def _haw_permissive_morphology_ok(token: str) -> bool:
    """Token passes Hawaiian shape using the OCR-permissive alphabet
    (core + loan b/f/g/r/t). Loanword-shaped tokens like ``fiku`` qualify."""
    if not token:
        return False
    low = token.lower()
    if any(c not in HAW_OCR_PERMISSIVE for c in low):
        return False
    if not any(c in HAW_VOWELS for c in low):
        return False
    if low[-1] not in HAW_VOWELS:
        return False
    prev_consonant = False
    for c in low:
        is_cons = c in HAW_ANY_CONSONANTS or c == OKINA
        if is_cons and prev_consonant:
            return False
        prev_consonant = is_cons
    return True


def _classify(text: str) -> str:
    """Return 'en', 'haw', or 'amb'.

    Per-token rules (only tokens with len>=2 vote; single letters are
    ambiguous because Hawaiian particles ``a``/``e``/``i``/``o``/``u``
    coincide with English ``a``/``I`` and would dominate short rows):

      * has any letter in EN_ONLY_LETTERS               -> EN signal
      * lowercased token in EN_FUNCTION_TOKENS          -> EN signal
      * passes STRICT Hawaiian morphology               -> HAW signal
      * fails permissive Hawaiian morphology            -> EN signal
      * else (loanword-shaped, e.g. ``fiku``, ``rope``) -> ambiguous

    Verdict is the majority of voters; ties prefer EN (it is safer to
    skip a Hawaiian row than to mispair an English row as Hawaiian).
    """
    if not text:
        return "amb"
    tokens = re.findall(r"[A-Za-z" + OKINA + r"]+", text)
    if not tokens:
        return "amb"
    en_signals = 0
    haw_signals = 0
    for tok in tokens:
        low = tok.lower()
        if len(low) < 2:
            continue
        if any(c in EN_ONLY_LETTERS for c in low):
            en_signals += 1
            continue
        if low in EN_FUNCTION_TOKENS:
            en_signals += 1
            continue
        if _haw_strict_morphology_ok(tok):
            haw_signals += 1
            continue
        if not _haw_permissive_morphology_ok(tok):
            en_signals += 1
            continue
        # Otherwise loanword-shaped: ambiguous, no vote.
    if en_signals == 0 and haw_signals == 0:
        return "amb"
    if en_signals >= haw_signals:
        return "en"
    return "haw"


def _has_prohibited_chars(text: str) -> bool:
    return any(c in PROHIBITED_CHARS for c in text)


def _haw_quality_ok(text: str) -> bool:
    """Reject obvious OCR garbage on the Hawaiian side."""
    if _has_prohibited_chars(text):
        return False
    tokens = re.findall(r"[A-Za-z" + OKINA + r"]+", text)
    if not tokens:
        return False
    for tok in tokens:
        low = tok.lower()
        # No EN-only letter (cdjqsvxyz). Loanword exceptions live outside this set.
        if any(c in EN_ONLY_LETTERS for c in low):
            return False
        # Reject 3+ consecutive consonants from the strict Hawaiian set
        # (real Hawaiian is C-V-C-V; clusters are OCR artifacts like "JMa").
        run = 0
        for c in low:
            if c in HAW_STRICT and c not in "aeiou" + OKINA:
                run += 1
                if run >= 3:
                    return False
            else:
                run = 0
        # Reject 4+ identical letters in a row.
        for j in range(len(low) - 3):
            if low[j] == low[j + 1] == low[j + 2] == low[j + 3]:
                return False
    return True


def _en_quality_ok(text: str) -> bool:
    if _has_prohibited_chars(text):
        return False
    tokens = re.findall(r"[A-Za-z]+", text)
    if not tokens:
        return False
    return True


def _is_furniture_text(text: str) -> bool:
    s = text.strip().rstrip(".").strip()
    if not s:
        return True
    if PAGE_NUMBER_RX.match(s):
        return True
    if RUNNING_HEAD_RX.match(s):
        return True
    return False


def parse_pairs(text: str) -> tuple[list[tuple[str, str, dict]], dict]:
    """Return list of (en, haw, meta) and a stats dict."""
    stats: Counter[str] = Counter()

    # The book splits into two regimes:
    #   * Front section (vocabulary + short phrases): clean two-column,
    #     each phrase fits on one OCR line. This is the safe region.
    #   * Back section (Conversation with a Native Woman, In the Kitchen,
    #     letters, etc.): phrases wrap across multiple OCR lines and the
    #     two-column layout is broken by speaker turns. Block-pairing
    #     cannot reliably align these.
    # We hard-cut at the first occurrence of the conversation anchor.
    cut_anchors = (
        "A    Conversation    with",
        "A   Conversation   with",
        "A  Conversation  with",
        "A Conversation with",
    )
    cut_idx = -1
    for anchor in cut_anchors:
        i = text.find(anchor)
        if i != -1:
            cut_idx = i
            break
    if cut_idx > 0:
        stats["front_section_chars"] = cut_idx
        stats["dropped_back_section_chars"] = len(text) - cut_idx
        text = text[:cut_idx]
    else:
        stats["front_section_chars"] = len(text)
        stats["dropped_back_section_chars"] = 0

    raw_blocks = _build_blocks(text)
    stats["raw_blocks"] = len(raw_blocks)

    # Expand packed blocks
    expanded: list[list[str]] = []
    for blk in raw_blocks:
        for sub in _split_packed(blk):
            expanded.append(sub)
    stats["expanded_blocks"] = len(expanded)

    # Build block records: phrase string + classification.  Multi-line
    # blocks that survived packed-split are wrap-blocks (one phrase
    # broken across OCR lines, with internal blanks). They are
    # ambiguous to align in dialogue sections, so we drop them entirely
    # — precision over recall.
    #
    # We additionally require each surviving single-line block to end
    # with a sentence terminator. This removes column-wrap fragments
    # ("A bankrupt will soon lose") that would otherwise pair with the
    # wrong opposite-column fragment in correspondence/dialogue
    # sections at the back of the book.
    records: list[dict] = []
    for blk in expanded:
        if not _is_single_line(blk):
            stats["dropped_multiline_blocks"] += 1
            continue
        line = blk[0]
        if not TERMINATOR_RX.search(line):
            stats["dropped_no_terminator"] += 1
            continue
        phrase = _join_wrap(blk)
        phrase_norm = normalize_text(phrase)
        if not phrase_norm or _is_furniture_text(phrase_norm):
            continue
        cls = _classify(phrase_norm)
        records.append({"text": phrase_norm, "lang": cls, "lines": len(blk)})
    stats["classified_blocks"] = len(records)
    stats["lang_en"] = sum(1 for r in records if r["lang"] == "en")
    stats["lang_haw"] = sum(1 for r in records if r["lang"] == "haw")
    stats["lang_amb"] = sum(1 for r in records if r["lang"] == "amb")

    # Coalesce into runs of same language. Ambiguous blocks break the run.
    runs: list[dict] = []
    cur_lang: str | None = None
    cur_items: list[dict] = []
    for r in records:
        if r["lang"] == "amb":
            if cur_items:
                runs.append({"lang": cur_lang, "items": cur_items})
                cur_items = []
                cur_lang = None
            continue
        if r["lang"] != cur_lang:
            if cur_items:
                runs.append({"lang": cur_lang, "items": cur_items})
            cur_lang = r["lang"]
            cur_items = [r]
        else:
            cur_items.append(r)
    if cur_items:
        runs.append({"lang": cur_lang, "items": cur_items})
    stats["runs"] = len(runs)

    # Pair adjacent (en, haw) runs of equal block count.
    pairs: list[tuple[str, str, dict]] = []
    i = 0
    while i + 1 < len(runs):
        a, b = runs[i], runs[i + 1]
        if a["lang"] == "en" and b["lang"] == "haw":
            if len(a["items"]) == len(b["items"]):
                for k, (ea, hb) in enumerate(zip(a["items"], b["items"])):
                    pairs.append((
                        ea["text"], hb["text"],
                        {"run_index": len(pairs), "block_index_in_run": k,
                         "run_size": len(a["items"])},
                    ))
                stats["paired_runs"] += 1
                i += 2
                continue
            else:
                stats["mismatched_runs"] += 1
                stats[f"mismatch_en{len(a['items'])}_haw{len(b['items'])}"] += 1
                i += 2
                continue
        # Skip lone runs (e.g., HAW first or unpaired EN at start/end)
        i += 1

    return pairs, dict(stats)


def _xml_page_lines(page: ET.Element) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for line in page.findall(".//LINE"):
        words = line.findall(".//WORD")
        if not words:
            continue
        text = normalize_text(" ".join((w.text or "") for w in words))
        if not text:
            continue
        if PAGE_NUMBER_RX.match(text) or RUNNING_HEAD_RX.match(text):
            continue
        if XML_HEADING_RX.search(text):
            continue

        xs: list[int] = []
        ys: list[int] = []
        for word in words:
            coords = word.attrib.get("coords")
            if not coords:
                continue
            try:
                x1, y1, x2, y2 = [int(v) for v in coords.split(",")]
            except ValueError:
                continue
            xs.extend([x1, x2])
            ys.extend([y1, y2])
        if not xs or not ys:
            continue
        lines.append({
            "text": text,
            "x1": min(xs),
            "x2": max(xs),
            "y1": min(ys),
            "y2": max(ys),
        })
    return lines


def _xml_column_groups(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not lines:
        return []
    sorted_lines = sorted(lines, key=lambda item: (item["y1"], item["x1"]))
    x_starts = sorted(item["x1"] for item in sorted_lines)
    start_threshold = x_starts[min(len(x_starts) - 1, max(0, int(len(x_starts) * 0.1)))] + 70

    groups: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in sorted_lines:
        starts_row = line["x1"] <= start_threshold
        vertical_gap = line["y1"] - current["y2"] if current else 999
        if current is None or starts_row or vertical_gap > 100:
            if current:
                groups.append(current)
            current = {"lines": [line], "y1": line["y1"], "y2": line["y2"]}
        else:
            current["lines"].append(line)
            current["y2"] = max(current["y2"], line["y2"])
    if current:
        groups.append(current)

    for group in groups:
        group["text"] = normalize_text(" ".join(line["text"] for line in group["lines"]))
    return [
        group
        for group in groups
        if group["text"] and not XML_HEADING_RX.search(group["text"])
    ]


def parse_pairs_xml(xml_path: Path) -> tuple[list[tuple[str, str, dict]], dict]:
    """Extract two-column phrase pairs from IA DjVu XML word coordinates."""
    root = ET.parse(xml_path).getroot()
    pages = root.findall(".//OBJECT")
    stats: Counter[str] = Counter()
    pairs: list[tuple[str, str, dict]] = []

    for page_idx, page in enumerate(pages):
        # First phrase-book content page in this IA item; earlier pages are
        # cover/front matter and produce title/ornament false positives.
        if page_idx < 8:
            stats["xml_pages_front_matter_skipped"] += 1
            continue

        try:
            page_width = int(page.attrib.get("width") or 0)
        except ValueError:
            page_width = 0
        if page_width <= 0:
            stats["xml_pages_missing_width"] += 1
            continue
        mid = page_width / 2

        lines = _xml_page_lines(page)
        left_lines = [
            line
            for line in lines
            if line["x1"] < mid - 20 and line["x2"] < mid + 150
        ]
        right_lines = [
            line
            for line in lines
            if line["x1"] > mid - 150
        ]
        left_groups = _xml_column_groups(left_lines)
        right_groups = _xml_column_groups(right_lines)
        stats["xml_pages_seen"] += 1
        stats["xml_left_groups"] += len(left_groups)
        stats["xml_right_groups"] += len(right_groups)

        used_right: set[int] = set()
        page_pairs = 0
        for left in left_groups:
            best_idx: int | None = None
            best_delta = 999
            for right_idx, right in enumerate(right_groups):
                if right_idx in used_right:
                    continue
                delta = abs(left["y1"] - right["y1"])
                if delta < best_delta:
                    best_idx = right_idx
                    best_delta = delta
            if best_idx is None or best_delta > 90:
                stats["xml_unmatched_left_group"] += 1
                continue
            used_right.add(best_idx)
            right = right_groups[best_idx]
            pairs.append((
                left["text"],
                right["text"],
                {
                    "page_index": page_idx,
                    "xml_y_delta": best_delta,
                    "block_index_in_run": page_pairs,
                    "run_size": min(len(left_groups), len(right_groups)),
                    "alignment_method": "two-column-djvu-xml-coordinate-pairing-v1",
                },
            ))
            page_pairs += 1
        stats["xml_pairs_by_y"] += page_pairs
        stats["xml_unmatched_right_group"] += len(right_groups) - len(used_right)

    return pairs, dict(stats)


def build_rows(djvu_path: Path, fetch_date: str) -> tuple[list[dict[str, Any]], dict]:
    raw_bytes = djvu_path.read_bytes()
    raw_sha256 = sha256_bytes(raw_bytes)
    text = raw_bytes.decode("utf-8", errors="replace")

    xml_path = _resolve_djvu_xml(djvu_path)
    xml_sha256 = None
    if xml_path:
        xml_sha256 = sha256_bytes(xml_path.read_bytes())
        pairs, stats = parse_pairs_xml(xml_path)
        stats["parser"] = "djvu_xml_coordinates"
        stats["djvu_xml_path"] = str(xml_path)
        stats["djvu_xml_sha256"] = xml_sha256
    else:
        pairs, stats = parse_pairs(text)
        stats["parser"] = "djvu_text_blocks"
    stats["pairs_proposed"] = len(pairs)

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    rejects: Counter[str] = Counter()

    for idx, (en_raw, haw_raw, meta) in enumerate(pairs):
        en_clean = normalize_text(en_raw, lang="en")
        haw_clean = normalize_text(haw_raw, lang="haw")
        if not en_clean or not haw_clean:
            rejects["empty_side"] += 1
            continue
        if not _en_quality_ok(en_clean):
            rejects["en_quality"] += 1
            continue
        if not _haw_quality_ok(haw_clean):
            rejects["haw_quality"] += 1
            continue
        # Re-confirm classification on cleaned text.
        if _classify(en_clean) != "en":
            rejects["en_misclass"] += 1
            continue
        if _classify(haw_clean) != "haw":
            rejects["haw_misclass"] += 1
            continue
        en_tokens = len(en_clean.split())
        haw_tokens = len(haw_clean.split())
        if not (1 <= en_tokens <= 40):
            rejects["en_tokens_out_of_band"] += 1
            continue
        if not (1 <= haw_tokens <= 40):
            rejects["haw_tokens_out_of_band"] += 1
            continue
        ratio = haw_tokens / en_tokens
        if not (0.25 <= ratio <= 4.0):
            rejects["ratio_out_of_band"] += 1
            continue
        sha_en_raw = sha256_text(en_raw)
        sha_haw_raw = sha256_text(haw_raw)
        sha_en_clean = sha256_text(en_clean)
        sha_haw_clean = sha256_text(haw_clean)
        sha_pair = compute_pair_hash(sha_en_clean, sha_haw_clean)
        if sha_pair in seen:
            rejects["dup_pair"] += 1
            continue
        seen.add(sha_pair)

        record_id = f"phrase-book-1881:row{idx:04d}"
        pair_id = f"phrase-book-1881-{idx:04d}-{sha_pair[:12]}"
        alignment_method = meta.get(
            "alignment_method",
            "two-column-djvu-block-pairing-v1",
        )
        note_bits = [
            f"Bishop 1881 Hawaiian Phrase Book (IA {IA_ITEM_ID})",
            f"alignment_method={alignment_method}",
            "1881 orthography (no kahakō / OCR-stripped ʻokina)",
            f"djvu_sha256={raw_sha256}",
            f"djvu_url={DJVU_URL}",
            f"run_size={meta['run_size']}",
            f"block_in_run={meta['block_index_in_run']}",
        ]
        if xml_sha256:
            note_bits.extend([
                f"djvu_xml_sha256={xml_sha256}",
                f"djvu_xml_url={DJVU_XML_URL}",
                f"xml_page_index={meta.get('page_index')}",
                f"xml_y_delta={meta.get('xml_y_delta')}",
            ])
        rows.append({
            "pair_id": pair_id,
            "source": SOURCE_ID,
            "source_url_en": SOURCE_URL,
            "source_url_haw": SOURCE_URL,
            "fetch_date": fetch_date,
            "sha256_en_raw": sha_en_raw,
            "sha256_haw_raw": sha_haw_raw,
            "sha256_en_clean": sha_en_clean,
            "sha256_haw_clean": sha_haw_clean,
            "sha256_pair": sha_pair,
            "record_id_en": record_id,
            "record_id_haw": record_id,
            "text_en": en_clean,
            "text_haw": haw_clean,
            "text_en_path": None,
            "text_haw_path": None,
            "alignment_type": "phrase-pair",
            "alignment_method": alignment_method,
            "alignment_model": None,
            "alignment_score": None,
            "alignment_review_required": True,
            "length_ratio_haw_over_en": round(ratio, 4),
            "lang_id_en": "en",
            "lang_id_en_confidence": 1.0,
            "lang_id_haw": "haw",
            "lang_id_haw_confidence": 1.0,
            "direction_original": "en->haw",
            "register": "phrase-book",
            "edition_or_version": EDITION,
            "synthetic": False,
            "synthetic_source_model": None,
            "license_observed_en": LICENSE,
            "license_observed_haw": LICENSE,
            "license_inferred": "PD-pre-1928-US",
            "tos_snapshot_id": None,
            "prototype_only": False,
            "release_eligible": True,
            "dedup_cluster_id": pair_id,
            "crosslink_stage1_overlap": False,
            "split": "review-pending",
            "quality_flags": [],
            "notes": "; ".join(note_bits) + ".",
            "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
            "phrase_book_ia_item_id": IA_ITEM_ID,
            "phrase_book_djvu_sha256": raw_sha256,
            "phrase_book_djvu_xml_sha256": xml_sha256,
        })

    stats["rows_emitted"] = len(rows)
    for k, v in rejects.items():
        stats[f"reject_{k}"] = v
    return rows, stats


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--execute", action="store_true")
    p.add_argument("--fetch-date", default=None)
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR))
    args = p.parse_args(argv)

    djvu_path = _resolve_djvu(args.fetch_date)
    fetch_date = args.fetch_date or djvu_path.parent.parent.name
    print(f"[phrase-book] djvu: {djvu_path}", file=sys.stderr)

    rows, stats = build_rows(djvu_path, fetch_date)
    print(f"[phrase-book] proposed pairs: {stats.get('pairs_proposed', 0)}", file=sys.stderr)
    print(f"[phrase-book] emitted rows:   {len(rows)}", file=sys.stderr)
    for k in sorted(stats):
        if k.startswith("reject_") or k.startswith("mismatch_"):
            print(f"[phrase-book]   {k}: {stats[k]}", file=sys.stderr)

    if not rows:
        print(
            "[phrase-book] BLOCKER: zero pairs survived gates. Refusing to "
            "emit empty candidates. Inspect parser stats and OCR layout.",
            file=sys.stderr,
        )
        # Still write the report so the blocker is auditable.
        if args.execute:
            report_path = Path(args.report_dir) / f"phrase_book_1881_build_report_{_today_compact_utc()}.json"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps({
                "report_type": "phrase_book_1881_build",
                "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
                "source_id": SOURCE_ID,
                "ia_item_id": IA_ITEM_ID,
                "djvu_path": str(djvu_path),
                "fetch_date": fetch_date,
                "blocker": "zero_rows_after_gates",
                "stats": stats,
            }, indent=2, ensure_ascii=False))
        return 4

    if args.dry_run:
        for r in rows[:8]:
            print(f"[phrase-book] sample: {r['text_en']!r} -> {r['text_haw']!r}", file=sys.stderr)
        return 0

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[phrase-book] wrote {len(rows)} rows -> {out_path}", file=sys.stderr)

    report_path = Path(args.report_dir) / f"phrase_book_1881_build_report_{_today_compact_utc()}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "report_type": "phrase_book_1881_build",
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "source_id": SOURCE_ID,
        "ia_item_id": IA_ITEM_ID,
        "djvu_path": str(djvu_path),
        "djvu_url": DJVU_URL,
        "fetch_date": fetch_date,
        "out_path": str(out_path),
        "license": LICENSE,
        "rights_status": "PD-pre-1928-US",
        "release_eligible": True,
        "prototype_only": False,
        "alignment_method": stats.get("parser", "djvu_text_blocks"),
        "rows_emitted": len(rows),
        "stats": stats,
        "samples": [
            {"text_en": r["text_en"], "text_haw": r["text_haw"]}
            for r in rows[:10]
        ],
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"[phrase-book] wrote report -> {report_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
