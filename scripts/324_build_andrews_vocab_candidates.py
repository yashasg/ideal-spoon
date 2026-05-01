#!/usr/bin/env python3
"""Stage-2 Andrews 1865 English-Hawaiian vocabulary appendix candidate builder (Frank).

Reads the Internet Archive djvu OCR of Andrews' 1865 *A Dictionary of the
Hawaiian Language* (item ``cu31924026916167``) at
``data/raw/andrews-1865-en-haw-vocab-appendix/<YYYYMMDD>/cu31924026916167_djvu.txt``
and extracts ``EN-headword -> haw-gloss`` rows ONLY from the
**English-Hawaiian Vocabulary** appendix at the back of the volume.

Precision-first policy (this OCR is noisy):

  * Only the appendix region is scanned. The Hawaiian-English main
    dictionary is excluded — it is haw->en, headwords with English
    glosses interleaved with Hawaiian definitions, and not safe to
    parse without dedicated logic.
  * The appendix start anchor is the literal line
    ``ENGLISH-HAWAIIAN  VOCABULARY.`` near line ~93852.
  * Only entries matching the strict regex
    ``^([A-Z][a-z]+(?:-[a-z]+)*),  (.+?)\\.$`` (after whitespace
    collapse) are considered, where the headword side is plausibly
    clean ASCII English (capitalized, hyphen-syllabified) and the
    Hawaiian side ends with ``.``
  * The dehyphenated English headword MUST validate against the system
    English wordlist (``/usr/share/dict/words``). When that wordlist is
    unavailable (non-Unix CI), the script refuses to emit rows rather
    than risk shipping OCR errors like ``Acqnire``/``Accorse`` as
    training-grade English. This is a precision-over-availability
    trade-off; downstream consumers should treat the lack of output on
    a non-Unix host as an environment issue, not a data issue.
  * The Hawaiian gloss is rejected if it contains any character
    outside the conservative Hawaiian-OCR-clean alphabet
    ``[aeiouhklmnpwAEIOUHKLMNPW '.,;-]`` (no digits, no ``&``, ``<``,
    ``>``, ``^``, ``$``, ``%``, ``~``, ``|`` or any other OCR garbage).
  * Empty / whitespace-only sides, or sides that look like English
    fragments (e.g., contain ``the``, ``and``, ``of`` as standalone
    tokens) are rejected on the Hawaiian side.
  * Deduplicated by canonical (en_clean, haw_clean) pair hash.

Skipped rows are NOT translated, NOT inferred, NOT fabricated. We
prefer to emit a small, defensible set than a large, OCR-corrupted one.

Rights: Andrews 1865 is U.S. public domain (pre-1928). The IA OCR
djvu derivative is in IA's public domain mirror.

Output (gitignored):

    data/stage2/candidates/andrews_1865_vocab.jsonl

Usage::

    python3 scripts/324_build_andrews_vocab_candidates.py --dry-run
    python3 scripts/324_build_andrews_vocab_candidates.py --execute

Exit codes: 0 success, 2 misuse, 3 input error.
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
RAW_ROOT = REPO_ROOT / "data" / "raw" / "andrews-1865-en-haw-vocab-appendix"
DEFAULT_OUT = REPO_ROOT / "data" / "stage2" / "candidates" / "andrews_1865_vocab.jsonl"

SOURCE_ID = "andrews-1865-en-haw-vocab-appendix"
IA_ITEM_ID = "cu31924026916167"
DUMP_FILENAME = f"{IA_ITEM_ID}_djvu.txt"
MANIFEST_SCHEMA_VERSION = "stage2.v0"
LICENSE = "Public Domain (pre-1928, U.S.)"
SOURCE_URL = f"https://archive.org/details/{IA_ITEM_ID}"
DJVU_URL = f"https://archive.org/download/{IA_ITEM_ID}/{IA_ITEM_ID}_djvu.txt"

APPENDIX_ANCHOR = "ENGLISH-HAWAIIAN  VOCABULARY."

SYSTEM_WORDLIST = Path("/usr/share/dict/words")


def _load_english_wordlist() -> set[str] | None:
    if not SYSTEM_WORDLIST.exists():
        return None
    out: set[str] = set()
    for line in SYSTEM_WORDLIST.read_text(encoding="utf-8", errors="replace").splitlines():
        w = line.strip().lower()
        if w and w.isalpha() and w.isascii():
            out.add(w)
    return out


_ENGLISH_LEXICON: set[str] | None = None


def _is_english_word(token: str) -> bool:
    """Validate an English headword against the system wordlist (lazy-loaded)."""
    global _ENGLISH_LEXICON
    if _ENGLISH_LEXICON is None:
        _ENGLISH_LEXICON = _load_english_wordlist() or set()
    return token.lower() in _ENGLISH_LEXICON


OKINA = "\u02bb"
OKINA_MISENCODINGS = ("\u2018", "\u2019", "'")

# Allowed characters in a clean Hawaiian gloss after OCR. Andrews' OCR
# strips diacritics (no ʻokina, no kahakō macrons), so we permit only
# the bare 13-letter Hawaiian alphabet, plus space, comma, period, and
# semicolon (used to separate alternate glosses), and the ʻokina just in
# case OCR retains it.
HAW_OCR_ALLOWED = set("aeiouhklmnpwAEIOUHKLMNPW '.,;-" + OKINA)

# Hawaiian gloss must not contain English filler words (OCR slip indicators).
EN_NOISE_TOKENS = {"the", "and", "of", "to", "for", "with", "is", "was", "be",
                   "in", "on", "at", "by", "from", "that", "this", "it", "or",
                   "as", "an", "but", "not", "are", "were", "have", "has", "had"}

# Strict appendix entry pattern. Headword: capitalized English word,
# optionally syllable-hyphenated (``A-bun-dance``). Body: Hawaiian gloss
# terminated by a period.
ENTRY_RX = re.compile(
    r"^([A-Z][a-z]+(?:-[a-z]+)*),\s+(.+?)\.\s*$"
)


def _today_compact_utc() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d")


def normalize_haw(text: str) -> str:
    nfc = unicodedata.normalize("NFC", text)
    for bad in OKINA_MISENCODINGS:
        nfc = nfc.replace(bad, OKINA)
    return nfc.strip()


def normalize_en(text: str) -> str:
    return unicodedata.normalize("NFC", text).strip()


def sha256_text(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def compute_pair_hash(sha256_en_clean: str, sha256_haw_clean: str) -> str:
    return hashlib.sha256(
        (sha256_en_clean + "\u2016" + sha256_haw_clean).encode("utf-8")
    ).hexdigest()


def _resolve_djvu(fetch_date: str | None) -> Path:
    if fetch_date:
        p = RAW_ROOT / fetch_date / DUMP_FILENAME
        if not p.exists():
            raise SystemExit(f"missing: {p}")
        return p
    candidates = sorted(p for p in RAW_ROOT.glob("*/" + DUMP_FILENAME) if p.is_file())
    if not candidates:
        raise SystemExit(
            f"no Andrews djvu under {RAW_ROOT}/<date>/{DUMP_FILENAME}; "
            f"run scripts/207_fetch_stage2_parallel_raw.py --execute --source {SOURCE_ID} first"
        )
    return candidates[-1]


def _find_appendix(text: str) -> str:
    """Return the appendix substring starting at the second occurrence of the anchor.

    The anchor string also appears once in the front-matter table of contents.
    The actual appendix body is the second (and any later) occurrence — we take
    everything from the first appearance after the main body.
    """
    # Look for the anchor; the appendix section begins after the LAST occurrence
    # whose surrounding lines are short (i.e., the section heading), but more
    # simply: the appendix header appears very late in the file (line ~93852 of
    # ~102258). We split at the LAST occurrence which is the section heading.
    idx = text.rfind(APPENDIX_ANCHOR)
    if idx < 0:
        raise SystemExit(f"could not locate appendix anchor {APPENDIX_ANCHOR!r}")
    return text[idx + len(APPENDIX_ANCHOR):]


def _looks_like_clean_haw(s: str) -> bool:
    if not s:
        return False
    if any(ch not in HAW_OCR_ALLOWED for ch in s):
        return False
    tokens = re.findall(r"[A-Za-z" + OKINA + r"]+", s)
    if not tokens:
        return False
    # Hawaiian alphabet is consonant-light; reject if any token contains
    # consonant clusters not allowed in Hawaiian (every consonant must be
    # followed by a vowel). Approximate by rejecting tokens with two
    # adjacent consonants from the Hawaiian set.
    cons = set("hklmnpwHKLMNPW")
    for tok in tokens:
        for i in range(len(tok) - 1):
            if tok[i] in cons and tok[i + 1] in cons:
                return False
        # Reject standalone single-consonant tokens (OCR slip; Hawaiian
        # function words are vowels: e, i, a, o, u, but never bare h/k/p/etc.)
        if len(tok) == 1 and tok in cons:
            return False
        # Reject tokens with 4+ identical letters in a row (OCR repeat
        # artifact, e.g. "laaaa").
        for j in range(len(tok) - 3):
            if tok[j] == tok[j + 1] == tok[j + 2] == tok[j + 3]:
                return False
    # Reject if token list contains English noise words.
    lowered = {t.lower() for t in tokens}
    if lowered & EN_NOISE_TOKENS:
        return False
    # Require at least one obvious Hawaiian token (length>=2, has a vowel).
    vowels = set("aeiouAEIOU")
    if not any(len(t) >= 2 and any(ch in vowels for ch in t) for t in tokens):
        return False
    return True


def _looks_like_clean_en_headword(s: str) -> bool:
    """Headword: 2..40 chars, Capitalized, optionally hyphen-syllable form,
    AND the dehyphenated form is in the system English wordlist."""
    if not (2 <= len(s) <= 40):
        return False
    if not re.fullmatch(r"[A-Z][a-z]+(?:-[a-z]+)*", s):
        return False
    return _is_english_word(s.replace("-", ""))


def dehyphenate_headword(h: str) -> str:
    """``A-bun-dance`` -> ``Abundance``."""
    return h.replace("-", "")


def parse_appendix(appendix_text: str) -> list[tuple[str, str]]:
    """Return list of (en_headword_clean, haw_gloss_clean) tuples (strict)."""
    pairs: list[tuple[str, str]] = []
    for raw_line in appendix_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        # Collapse repeated whitespace inside the line.
        line = re.sub(r"\s+", " ", line)
        m = ENTRY_RX.match(line)
        if not m:
            continue
        en_part, haw_part = m.group(1), m.group(2)
        if not _looks_like_clean_en_headword(en_part):
            continue
        if not _looks_like_clean_haw(haw_part):
            continue
        en_clean = dehyphenate_headword(en_part)
        haw_clean = haw_part.strip()
        # Reject if Hawaiian gloss is suspiciously short (single letter or
        # single 2-char token) — likely OCR artifact, not a usable gloss.
        if len(haw_clean) < 3:
            continue
        pairs.append((en_clean, haw_clean))
    return pairs


def build_rows(djvu_path: Path, fetch_date: str) -> list[dict[str, Any]]:
    raw_bytes = djvu_path.read_bytes()
    raw_sha256 = sha256_bytes(raw_bytes)
    text = raw_bytes.decode("utf-8", errors="replace")
    appendix = _find_appendix(text)
    pairs = parse_appendix(appendix)

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for en_raw, haw_raw in pairs:
        haw_clean = normalize_haw(haw_raw)
        en_clean = normalize_en(en_raw)
        sha_haw_clean = sha256_text(haw_clean)
        sha_en_clean = sha256_text(en_clean)
        sha_pair = compute_pair_hash(sha_en_clean, sha_haw_clean)
        if sha_pair in seen:
            continue
        seen.add(sha_pair)

        haw_tokens = len(haw_clean.split()) or 1
        en_tokens = len(en_clean.split()) or 1
        length_ratio = round(haw_tokens / en_tokens, 4)

        pair_id = f"andrews1865:{en_clean.lower()}:{sha_pair[:12]}"
        record_id = en_clean.lower()
        rows.append({
            "pair_id": pair_id,
            "source": SOURCE_ID,
            "source_url_en": SOURCE_URL,
            "source_url_haw": SOURCE_URL,
            "fetch_date": fetch_date,
            "sha256_en_raw": sha256_text(en_raw),
            "sha256_haw_raw": sha256_text(haw_raw),
            "sha256_en_clean": sha_en_clean,
            "sha256_haw_clean": sha_haw_clean,
            "sha256_pair": sha_pair,
            "record_id_en": record_id,
            "record_id_haw": record_id,
            "text_en": en_clean,
            "text_haw": haw_clean,
            "text_en_path": None,
            "text_haw_path": None,
            "alignment_type": "dictionary-example",
            "alignment_method": "manual",
            "alignment_model": None,
            "alignment_score": None,
            "alignment_review_required": True,
            "length_ratio_haw_over_en": length_ratio,
            "lang_id_en": "en",
            "lang_id_en_confidence": 1.0,
            "lang_id_haw": "haw",
            "lang_id_haw_confidence": 1.0,
            "direction_original": "en->haw",
            "register": "dictionary-example",
            "edition_or_version": "Andrews 1865 (IA cu31924026916167)",
            "synthetic": False,
            "synthetic_source_model": None,
            "license_observed_en": LICENSE,
            "license_observed_haw": LICENSE,
            "license_inferred": None,
            "tos_snapshot_id": None,
            "prototype_only": True,
            "release_eligible": False,
            "dedup_cluster_id": pair_id,
            "crosslink_stage1_overlap": False,
            "split": "review-pending",
            "notes": (
                "Andrews 1865 English-Hawaiian Vocabulary appendix "
                "(IA djvu OCR). Strict-precision parse; OCR is noisy, "
                "diacritics absent, alignment_review_required=true. "
                f"djvu_sha256={raw_sha256}. djvu_url={DJVU_URL}."
            ),
            "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
            "andrews_ia_item_id": IA_ITEM_ID,
            "andrews_djvu_sha256": raw_sha256,
        })
    return rows


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true", help="parse + count, do not write")
    g.add_argument("--execute", action="store_true", help="write candidate JSONL")
    p.add_argument("--fetch-date", default=None, help="raw fetch date subdir; default newest")
    p.add_argument("--out", default=str(DEFAULT_OUT), help=f"output JSONL (default {DEFAULT_OUT})")
    args = p.parse_args(argv)

    djvu_path = _resolve_djvu(args.fetch_date)
    fetch_date = args.fetch_date or djvu_path.parent.name
    print(f"[andrews] using djvu: {djvu_path}", file=sys.stderr)
    rows = build_rows(djvu_path, fetch_date)
    print(f"[andrews] extracted {len(rows)} strict-precision EN-HAW rows", file=sys.stderr)

    if args.dry_run:
        for r in rows[:5]:
            print("[andrews] sample:", r["text_en"], "->", r["text_haw"], file=sys.stderr)
        return 0

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[andrews] wrote {len(rows)} rows -> {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
