"""Canonical text helpers for Stage-2 candidate hashing.

This module is the single source of truth for Stage-2 clean-text
canonicalization.  Adapters, audit scripts, contamination ledgers, and the
manifest builder should import these helpers instead of open-coding text folds.
"""
from __future__ import annotations

import hashlib
import unicodedata

INVISIBLE_FORMAT_CONTROLS = str.maketrans("", "", "\u00ad\u200b\u200c\u200d\ufeff")
EN_PUNCT_FOLD = str.maketrans({
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2010": "-",
    "\u2011": "-",
})
HAW_OKINA_FOLD = str.maketrans({"'": "ʻ", "‘": "ʻ", "’": "ʻ", "`": "ʻ", "\u02bc": "ʻ"})
PAIR_DELIM = "\u2016"


def _base(text: object) -> str:
    return unicodedata.normalize("NFC", str(text or "")).translate(INVISIBLE_FORMAT_CONTROLS)


def canonical_en(s: object) -> str:
    """Return the Stage-2 canonical English side text before hashing."""
    return " ".join(_base(s).translate(EN_PUNCT_FOLD).split())


def canonical_haw(s: object) -> str:
    """Return the Stage-2 canonical Hawaiian side text before hashing."""
    return " ".join(_base(s).translate(HAW_OKINA_FOLD).split())


def canonical_pair(en: object, haw: object) -> str:
    """Return the canonical eval-ledger pair text: EN + U+2016 + HAW."""
    return canonical_en(en) + PAIR_DELIM + canonical_haw(haw)


def canonicalize_clean_text(text: object, *, lang: str = "en") -> str:
    if lang == "en":
        return canonical_en(text)
    if lang == "haw":
        return canonical_haw(text)
    raise ValueError(f"unsupported Stage-2 hash language: {lang!r}")


def sha256_text(text: object, *, lang: str | None = None) -> str:
    if lang is not None:
        text = canonicalize_clean_text(text, lang=lang)
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def compute_pair_hash(sha256_en_clean: str, sha256_haw_clean: str) -> str:
    return hashlib.sha256((sha256_en_clean + PAIR_DELIM + sha256_haw_clean).encode("utf-8")).hexdigest()
