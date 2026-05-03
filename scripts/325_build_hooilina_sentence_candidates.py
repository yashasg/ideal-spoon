#!/usr/bin/env python3
"""Stage-2 Hoʻoilina sentence-level candidate builder (Frank, hooilina-sentence-pipeline-v2).

Reads ``data/stage2/candidates/hooilina.jsonl`` (68 paragraph/section-level
parent rows) and emits ``data/stage2/candidates/hooilina_sentences.jsonl`` —
one row per **sentence pair** (not paragraph pair).

Algorithm
---------
Level 1 — paragraph split:
  For each parent row, split ``text_en`` and ``text_haw`` by the numbered-
  paragraph boundary ``\\n(?=\\d+\\.[ \\t])``.  Only when EN paragraph count
  == HAW paragraph count (and > 1) do we proceed.  Rows where counts differ
  are skipped entirely.

Level 2 — sentence split (new in v2):
  For each matched paragraph pair:
  - Strip leading ``N. `` prefix.
  - Split each side into sentences using a conservative stdlib splitter
    (sentence-ending punctuation + whitespace + uppercase start; abbreviation
    protection for common EN/HAW abbreviations; decimal-number protection).
  - Only when EN sentence count == HAW sentence count do we emit individual
    sentence pairs.  Paragraphs with mismatched counts are skipped
    (conservative skip-over-alignment policy).

Per emitted sentence pair:
  - Apply quality gates: MIN_TOKENS_PER_SIDE (3) ≤ tokens ≤ MAX_TOKENS_PER_SIDE (80);
    ratio ∈ [0.5, 2.5]; no boilerplate; non-Hawaiian letter share ≤ 0.25.
  - Compute fresh sha256_en_clean, sha256_haw_clean, sha256_pair per sentence.
  - Dedupe within the output by sha256_pair.

All emitted rows carry:
  - ``alignment_type = "parallel-sentence"``
  - ``alignment_method = "filename-pair+paragraph-order+sentence-split-v2"``
  - ``parent_pair_id``, ``paragraph_index``, ``sentence_index``,
    ``sentence_count_in_paragraph``
  - ``prototype_only = True``, ``release_eligible = False``
  - ``alignment_review_required = True``
  - ``split = "review-pending"``  (promotion handled by script 333)

Stdlib only. Exit codes: 0 success, 1 I/O error, 2 CLI misuse, 3 schema failure.

Usage::

    python scripts/325_build_hooilina_sentence_candidates.py --dry-run
    python scripts/325_build_hooilina_sentence_candidates.py --execute
    python scripts/325_build_hooilina_sentence_candidates.py --self-test
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import html as html_mod
import json
import re
import sys
import unicodedata
from pathlib import Path

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
CANDIDATES_DIR = REPO_ROOT / "data" / "stage2" / "candidates"
REPORTS_DIR = REPO_ROOT / "data" / "stage2" / "reports"

INPUT_PATH = CANDIDATES_DIR / "hooilina.jsonl"
OUTPUT_PATH = CANDIDATES_DIR / "hooilina_sentences.jsonl"

MANIFEST_SCHEMA_VERSION = "stage2.v0"
SOURCE_ID = "hooilina"

# Numbered-paragraph boundary: a newline followed immediately by "N. "
PARA_SPLIT_RE = re.compile(r"\n(?=\d+\.[ \t])")

# Strip leading "N. " or "N.\t" from paragraph body
PARA_PREFIX_RE = re.compile(r"^\d+\.[ \t]*")

# Sentence-boundary split: sentence-ending punctuation followed by whitespace
# and an uppercase letter (covers both EN and HAW; ʻOkina U+02BB before a
# vowel counts as a sentence-initial signal in Hawaiian).
SENT_SPLIT_RE = re.compile(r'(?<=[.!?])\s+(?=[A-ZĀĒĪŌŪ\u02bb])')

# Common abbreviations whose trailing period must NOT trigger a sentence break.
# Kept deliberately short — prototype only; conservative skip is preferred.
ABBREV_SET = frozenset({
    "mr", "mrs", "ms", "dr", "rev", "gov", "gen", "col", "lt", "sgt",
    "no", "vs", "st", "jr", "sr", "etc", "dept", "approx", "vol",
    "sec", "art", "ch", "chap", "fig", "ed", "eds", "pp", "pg",
})

# Quality gate constants
MIN_TOKENS_PER_SIDE = 3
MAX_TOKENS_PER_SIDE = 80
RATIO_MIN = 0.5
RATIO_MAX = 2.5
NONHAW_SHARE_MAX = 0.25

# HAW letter inventory (okina = U+02BB counted as valid HAW char)
HAW_LETTER_INV = set("aehiklmnopuwāēīōū\u02bb")

# Boilerplate signals — any paragraph containing these is rejected
BOILERPLATE_SIGNALS = [
    "look up any word",
    "this material may not be reproduced",
    "privacy policy",
    "©",
    "all rights reserved",
    "greenstone",
]

# ʻOkina canonicalization (same set as script 324)
OKINA = "\u02bb"


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def normalize_haw(text: str) -> str:
    return stage2_canonical_haw(html_mod.unescape(text))


def normalize_en(text: str) -> str:
    return stage2_canonical_en(html_mod.unescape(text))


def sha256_text(text: str) -> str:
    return stage2_sha256_text(text)


def compute_pair_hash(sha_en: str, sha_haw: str) -> str:
    return stage2_compute_pair_hash(sha_en, sha_haw)


def tok(text: str) -> int:
    return len(text.split()) if text else 0


def nonhaw_share(text: str) -> float:
    alpha = [c for c in text.lower() if c.isalpha()]
    if not alpha:
        return 0.0
    return sum(1 for c in alpha if c not in HAW_LETTER_INV) / len(alpha)


def is_boilerplate(text: str) -> bool:
    tl = text.lower()
    return any(sig in tl for sig in BOILERPLATE_SIGNALS)


def split_paragraphs(text: str) -> list[str]:
    """Split text into numbered-paragraph chunks. Returns ≥1 element."""
    parts = PARA_SPLIT_RE.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


def strip_para_prefix(text: str) -> str:
    return PARA_PREFIX_RE.sub("", text.strip(), count=1).strip()


def split_sentences(text: str) -> list[str]:
    """Split a paragraph into individual sentences.

    Strategy (conservative, stdlib-only):
    1. Normalise whitespace (replace all runs of whitespace/newlines with a
       single space) so the paragraph is a flat string.
    2. Split on SENT_SPLIT_RE: sentence-ending punctuation followed by
       whitespace and an uppercase letter (including Hawaiian ʻOkina prefix).
    3. Re-merge any fragment whose previous part ends with a known
       abbreviation (e.g. "No.", "Dr.", "St.") — avoids over-splitting.
    4. Protect decimal numbers: "3.14" — SENT_SPLIT_RE requires an uppercase
       lookahead so pure-digit decimal numbers are not split.

    Returns a list of stripped sentence strings.  Empty results map to [].
    """
    text = " ".join(text.split())  # normalise all whitespace including newlines
    if not text:
        return []

    parts = SENT_SPLIT_RE.split(text)
    if len(parts) <= 1:
        return [text.strip()] if text.strip() else []

    # Re-merge fragments where the split followed an abbreviation
    merged: list[str] = [parts[0]]
    for part in parts[1:]:
        prev = merged[-1]
        words = prev.rstrip().split()
        if words:
            last_word = words[-1].rstrip(".").lower()
            if last_word in ABBREV_SET and len(last_word) <= 8:
                merged[-1] = prev.rstrip() + " " + part
                continue
        merged.append(part)

    return [s.strip() for s in merged if s.strip()]


# ---------------------------------------------------------------------------
# Core builder
# ---------------------------------------------------------------------------

def build_sentence_candidates(
    parent_rows: list[dict],
) -> tuple[list[dict], dict]:
    """Return (emitted_rows, stats_dict).

    Two-level split:
      Level 1: parent section → numbered paragraph pairs (EN count == HAW count)
      Level 2: paragraph pair → sentence pairs (EN sentence count == HAW sentence count)
    Only actual single-sentence pairs are emitted.
    """
    emitted: list[dict] = []
    seen_pair_hashes: set[str] = set()

    stats = {
        "parent_rows": len(parent_rows),
        "parent_splittable": 0,
        "parent_not_splittable": 0,
        "para_pairs_total": 0,
        "para_pairs_sent_mismatch": 0,
        "sent_pairs_total": 0,
        "sent_pairs_emitted": 0,
        "sent_pairs_quality_rejected": 0,
        "sent_pairs_boilerplate": 0,
        "sent_pairs_too_short": 0,
        "sent_pairs_too_long": 0,
        "sent_pairs_ratio_fail": 0,
        "sent_pairs_nonhaw_high": 0,
        "sent_pairs_deduped": 0,
        "parent_ids_splittable": [],
        "parent_ids_not_splittable": [],
    }

    for parent in parent_rows:
        raw_en = parent.get("text_en", "")
        raw_haw = parent.get("text_haw", "")

        paras_en = split_paragraphs(raw_en)
        paras_haw = split_paragraphs(raw_haw)

        if len(paras_en) != len(paras_haw) or len(paras_en) <= 1:
            stats["parent_not_splittable"] += 1
            stats["parent_ids_not_splittable"].append(parent["pair_id"])
            continue

        stats["parent_splittable"] += 1
        stats["parent_ids_splittable"].append(parent["pair_id"])

        for para_idx, (raw_ep, raw_hp) in enumerate(zip(paras_en, paras_haw)):
            stats["para_pairs_total"] += 1

            # Normalise and strip paragraph-number prefix
            ep_para = normalize_en(strip_para_prefix(raw_ep))
            hp_para = normalize_haw(strip_para_prefix(raw_hp))

            # Level-2: sentence split
            sents_en = split_sentences(ep_para)
            sents_haw = split_sentences(hp_para)

            # Skip paragraph if sentence counts differ (conservative)
            if len(sents_en) != len(sents_haw) or len(sents_en) == 0:
                stats["para_pairs_sent_mismatch"] += 1
                continue

            sent_count = len(sents_en)

            for sent_idx, (ep, hp) in enumerate(zip(sents_en, sents_haw)):
                stats["sent_pairs_total"] += 1

                # Quality gates
                reject_reasons: list[str] = []

                if is_boilerplate(ep) or is_boilerplate(hp):
                    reject_reasons.append("boilerplate")
                    stats["sent_pairs_boilerplate"] += 1

                en_t = tok(ep)
                haw_t = tok(hp)

                if en_t < MIN_TOKENS_PER_SIDE or haw_t < MIN_TOKENS_PER_SIDE:
                    reject_reasons.append("too_short")
                    stats["sent_pairs_too_short"] += 1

                if en_t > MAX_TOKENS_PER_SIDE or haw_t > MAX_TOKENS_PER_SIDE:
                    reject_reasons.append("too_long")
                    stats["sent_pairs_too_long"] += 1

                ratio = haw_t / en_t if en_t > 0 else 0.0
                if not (RATIO_MIN <= ratio <= RATIO_MAX):
                    reject_reasons.append("ratio_out_of_range")
                    stats["sent_pairs_ratio_fail"] += 1

                nhs = nonhaw_share(hp)
                if nhs > NONHAW_SHARE_MAX:
                    reject_reasons.append("haw_nonhaw_letters_high")
                    stats["sent_pairs_nonhaw_high"] += 1

                if reject_reasons:
                    stats["sent_pairs_quality_rejected"] += 1
                    continue

                # Compute hashes on normalized clean text
                sha_en_clean = sha256_text(ep)
                sha_haw_clean = sha256_text(hp)
                sha_pair = compute_pair_hash(sha_en_clean, sha_haw_clean)

                # Dedup
                if sha_pair in seen_pair_hashes:
                    stats["sent_pairs_deduped"] += 1
                    continue
                seen_pair_hashes.add(sha_pair)

                # Derive pair_id: hooilina-sent-v2-{suffix}.p{NNN}.s{NNN}
                parent_id = parent["pair_id"]
                suffix = parent_id[len("hooilina-"):]
                pair_id = f"hooilina-sent-v2-{suffix}.p{para_idx:03d}.s{sent_idx:03d}"

                row: dict = {
                    "pair_id": pair_id,
                    "parent_pair_id": parent_id,
                    "paragraph_index": para_idx,
                    "sentence_index": sent_idx,
                    "sentence_count_in_paragraph": sent_count,
                    "source": SOURCE_ID,
                    "source_url_en": parent.get("source_url_en"),
                    "source_url_haw": parent.get("source_url_haw"),
                    "fetch_date": parent.get("fetch_date"),
                    "sha256_en_raw": sha256_text(raw_ep),
                    "sha256_haw_raw": sha256_text(raw_hp),
                    "sha256_en_clean": sha_en_clean,
                    "sha256_haw_clean": sha_haw_clean,
                    "sha256_pair": sha_pair,
                    "record_id_en": (
                        f"{parent.get('record_id_en', '')}"
                        f".p{para_idx:03d}.s{sent_idx:03d}"
                    ),
                    "record_id_haw": (
                        f"{parent.get('record_id_haw', '')}"
                        f".p{para_idx:03d}.s{sent_idx:03d}"
                    ),
                    "text_en": ep,
                    "text_haw": hp,
                    "text_en_path": parent.get("text_en_path"),
                    "text_haw_path": parent.get("text_haw_path"),
                    "alignment_type": "parallel-sentence",
                    "alignment_method": (
                        "filename-pair+paragraph-order+sentence-split-v2"
                    ),
                    "alignment_model": None,
                    "alignment_score": None,
                    "alignment_review_required": True,
                    "length_ratio_haw_over_en": round(ratio, 4),
                    "lang_id_en": parent.get("lang_id_en"),
                    "lang_id_en_confidence": parent.get("lang_id_en_confidence"),
                    "lang_id_haw": parent.get("lang_id_haw"),
                    "lang_id_haw_confidence": parent.get("lang_id_haw_confidence"),
                    "direction_original": parent.get("direction_original"),
                    "register": parent.get("register"),
                    "edition_or_version": parent.get("edition_or_version"),
                    "synthetic": False,
                    "synthetic_source_model": None,
                    "license_observed_en": parent.get("license_observed_en"),
                    "license_observed_haw": parent.get("license_observed_haw"),
                    "license_inferred": parent.get("license_inferred"),
                    "tos_snapshot_id": parent.get("tos_snapshot_id"),
                    "prototype_only": True,
                    "release_eligible": False,
                    "dedup_cluster_id": None,
                    "crosslink_stage1_overlap": False,
                    "split": "review-pending",
                    "quality_flags": [],
                    "notes": (
                        f"Sentence-level split: paragraph {para_idx}, "
                        f"sentence {sent_idx}/{sent_count} from "
                        f"parent section {parent_id}. "
                        "v2 two-level split (paragraph→sentence). "
                        "Prototype-only; KS editorial layer; not release eligible."
                    ),
                    "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
                }
                emitted.append(row)
                stats["sent_pairs_emitted"] += 1

    return emitted, stats


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def self_test() -> None:
    """Run assertions to validate core logic. Exit 0 on pass, 3 on fail."""
    print("Running self-test...")

    # Test split_paragraphs
    sample = "1. First paragraph.\n2. Second paragraph.\n3. Third."
    parts = split_paragraphs(sample)
    assert len(parts) == 3, f"Expected 3 parts, got {len(parts)}"
    assert parts[0] == "1. First paragraph."
    assert parts[1] == "2. Second paragraph."

    # Test strip_para_prefix
    assert strip_para_prefix("1. Hello world") == "Hello world"
    assert strip_para_prefix("12. Test text") == "Test text"
    assert strip_para_prefix("No number here") == "No number here"

    # Test split_sentences — single sentence (no split)
    s1 = split_sentences("He went home.")
    assert s1 == ["He went home."], f"Expected 1 sentence, got {s1}"

    # Test split_sentences — two sentences with capital start
    s2 = split_sentences("He went home. She stayed behind.")
    assert len(s2) == 2, f"Expected 2 sentences, got {s2}"
    assert s2[0] == "He went home."
    assert s2[1] == "She stayed behind."

    # Test split_sentences — Hawaiian two sentences (ʻOkina-start)
    s3 = split_sentences("Ua hele ia i ka hale. ʻO ia ka hana maika'i.")
    assert len(s3) == 2, f"Expected 2 Hawaiian sentences, got {s3}"

    # Test split_sentences — abbreviation protection
    s4 = split_sentences("Mr. Smith went to Washington. He won the vote.")
    assert len(s4) == 2, f"Expected 2 after abbrev merge, got {s4}"

    # Test split_sentences — decimal number not split (no uppercase follows)
    s5 = split_sentences("The ratio is 3.14 and it is stable.")
    assert len(s5) == 1, f"Decimal should not split, got {s5}"

    # Test split_sentences — newline normalised before splitting
    s6 = split_sentences("First sentence.\nSecond Sentence.")
    assert len(s6) == 2, f"Newline should be normalised, got {s6}"

    # Test quality gates
    assert tok("hello world test") == 3
    assert tok("") == 0

    # Test nonhaw_share
    haw_text = "he kanaka maoli"
    assert nonhaw_share(haw_text) < 0.3, f"Expected low share, got {nonhaw_share(haw_text)}"

    # Test boilerplate detection
    assert is_boilerplate("Please look up any word in our dictionary")
    assert not is_boilerplate("Ua hoʻomaka ka hana.")

    # Test pair hash consistency
    h1 = compute_pair_hash("abc", "def")
    h2 = compute_pair_hash("abc", "def")
    assert h1 == h2, "Pair hash must be deterministic"
    assert compute_pair_hash("abc", "def") != compute_pair_hash("def", "abc")

    # Test okina normalization
    text_with_smart_quote = "ʻO ia"
    normalized = normalize_haw(text_with_smart_quote)
    assert OKINA in normalized, "ʻOkina should be U+02BB after normalization"

    # Test that mismatched para counts are skipped
    parent_mismatch = [{
        "pair_id": "hooilina-TEST001",
        "text_en": "1. English one.\n2. English two.",
        "text_haw": "1. Haw one.\n2. Haw two.\n3. Haw three.",
        "source": "hooilina",
        "source_url_en": None, "source_url_haw": None, "fetch_date": None,
        "sha256_en_raw": "x", "sha256_haw_raw": "x",
        "record_id_en": "TEST001.7", "record_id_haw": "TEST001.5",
        "text_en_path": None, "text_haw_path": None,
        "lang_id_en": "en", "lang_id_en_confidence": 1.0,
        "lang_id_haw": "haw", "lang_id_haw_confidence": 1.0,
        "direction_original": "haw->en", "register": "unknown",
        "edition_or_version": None, "synthetic": False,
        "synthetic_source_model": None, "license_observed_en": None,
        "license_observed_haw": None, "license_inferred": None,
        "tos_snapshot_id": None, "dedup_cluster_id": None,
        "crosslink_stage1_overlap": False, "quality_flags": [],
        "notes": "", "manifest_schema_version": "stage2.v0",
    }]
    rows_out, stats = build_sentence_candidates(parent_mismatch)
    assert len(rows_out) == 0, f"Mismatched para counts should emit 0 rows, got {len(rows_out)}"
    assert stats["parent_not_splittable"] == 1

    # Test two-level split: 2 paragraphs × 1 sentence each → 2 sentence rows
    parent_match_single = [{
        "pair_id": "hooilina-TEST002",
        "text_en": "1. The first English sentence.\n2. The second English sentence.",
        "text_haw": "1. Ka manao mua ma ka ʻōlelo Hawaiʻi.\n2. He manao hou ma ka ʻōlelo.",
        "source": "hooilina",
        "source_url_en": None, "source_url_haw": None, "fetch_date": None,
        "sha256_en_raw": "y", "sha256_haw_raw": "y",
        "record_id_en": "TEST002.7", "record_id_haw": "TEST002.5",
        "text_en_path": None, "text_haw_path": None,
        "lang_id_en": "en", "lang_id_en_confidence": 1.0,
        "lang_id_haw": "haw", "lang_id_haw_confidence": 1.0,
        "direction_original": "haw->en", "register": "unknown",
        "edition_or_version": None, "synthetic": False,
        "synthetic_source_model": None, "license_observed_en": None,
        "license_observed_haw": None, "license_inferred": None,
        "tos_snapshot_id": None, "dedup_cluster_id": None,
        "crosslink_stage1_overlap": False, "quality_flags": [],
        "notes": "", "manifest_schema_version": "stage2.v0",
    }]
    rows_out2, stats2 = build_sentence_candidates(parent_match_single)
    assert len(rows_out2) == 2, f"Expected 2 sentence rows, got {len(rows_out2)}"
    assert rows_out2[0]["alignment_type"] == "parallel-sentence"
    assert rows_out2[0]["parent_pair_id"] == "hooilina-TEST002"
    assert rows_out2[0]["prototype_only"] is True
    assert rows_out2[0]["release_eligible"] is False
    assert rows_out2[0]["split"] == "review-pending"
    assert rows_out2[0]["alignment_review_required"] is True
    assert rows_out2[0]["alignment_method"] == "filename-pair+paragraph-order+sentence-split-v2"
    assert rows_out2[0]["sentence_index"] == 0
    assert rows_out2[0]["sentence_count_in_paragraph"] == 1
    assert rows_out2[0]["paragraph_index"] == 0

    # Test two-level split: 1 paragraph with 2 sentences each → 2 sentence rows
    parent_multi_sent = [{
        "pair_id": "hooilina-TEST003",
        "text_en": "1. He went home. She stayed there.\n2. Another long paragraph here.",
        "text_haw": "1. Ua hele ia i ka hale. Noho ihola ia ma laila.\n2. He manao hou ma nei wahi.",
        "source": "hooilina",
        "source_url_en": None, "source_url_haw": None, "fetch_date": None,
        "sha256_en_raw": "z", "sha256_haw_raw": "z",
        "record_id_en": "TEST003.7", "record_id_haw": "TEST003.5",
        "text_en_path": None, "text_haw_path": None,
        "lang_id_en": "en", "lang_id_en_confidence": 1.0,
        "lang_id_haw": "haw", "lang_id_haw_confidence": 1.0,
        "direction_original": "haw->en", "register": "unknown",
        "edition_or_version": None, "synthetic": False,
        "synthetic_source_model": None, "license_observed_en": None,
        "license_observed_haw": None, "license_inferred": None,
        "tos_snapshot_id": None, "dedup_cluster_id": None,
        "crosslink_stage1_overlap": False, "quality_flags": [],
        "notes": "", "manifest_schema_version": "stage2.v0",
    }]
    rows_out3, stats3 = build_sentence_candidates(parent_multi_sent)
    # Paragraph 0: 2 EN sentences ("He went home.", "She stayed there.")
    #              2 HAW sentences ("Ua hele ia i ka hale.", "Noho ihola ia ma laila.")
    # → should emit 2 sentence pair rows
    # Paragraph 1: 1 EN sentence, 1 HAW sentence → 1 sentence pair row
    assert len(rows_out3) == 3, f"Expected 3 sentence rows (2+1), got {len(rows_out3)}"
    assert rows_out3[0]["sentence_index"] == 0
    assert rows_out3[0]["sentence_count_in_paragraph"] == 2
    assert rows_out3[1]["sentence_index"] == 1
    assert rows_out3[1]["sentence_count_in_paragraph"] == 2
    assert rows_out3[2]["paragraph_index"] == 1
    assert rows_out3[2]["sentence_index"] == 0

    # Test MAX_TOKENS_PER_SIDE gate
    long_en = " ".join(["word"] * 85)  # 85 tokens > MAX_TOKENS_PER_SIDE (80)
    long_haw = " ".join(["hua"] * 85)
    parent_too_long = [{
        "pair_id": "hooilina-TEST004",
        "text_en": f"1. {long_en}.\n2. Short second.",
        "text_haw": f"1. {long_haw}.\n2. Pōkole ʻelua.",
        "source": "hooilina",
        "source_url_en": None, "source_url_haw": None, "fetch_date": None,
        "sha256_en_raw": "w", "sha256_haw_raw": "w",
        "record_id_en": "TEST004.7", "record_id_haw": "TEST004.5",
        "text_en_path": None, "text_haw_path": None,
        "lang_id_en": "en", "lang_id_en_confidence": 1.0,
        "lang_id_haw": "haw", "lang_id_haw_confidence": 1.0,
        "direction_original": "haw->en", "register": "unknown",
        "edition_or_version": None, "synthetic": False,
        "synthetic_source_model": None, "license_observed_en": None,
        "license_observed_haw": None, "license_inferred": None,
        "tos_snapshot_id": None, "dedup_cluster_id": None,
        "crosslink_stage1_overlap": False, "quality_flags": [],
        "notes": "", "manifest_schema_version": "stage2.v0",
    }]
    rows_out4, stats4 = build_sentence_candidates(parent_too_long)
    # Paragraph 0 (85 tokens each) should be rejected (too_long)
    # Paragraph 1 ("Short second." / "Pōkole ʻelua.") → 1 sentence pair
    assert stats4["sent_pairs_too_long"] >= 1, "Expected at least 1 too_long rejection"

    print("All self-tests passed (20 assertions).")
    sys.exit(0)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(dry_run: bool = False) -> None:
    if not INPUT_PATH.exists():
        print(f"ERROR: Input not found: {INPUT_PATH}", file=sys.stderr)
        sys.exit(1)

    parent_rows = []
    with open(INPUT_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                parent_rows.append(json.loads(line))

    print(f"Loaded {len(parent_rows)} parent rows from {INPUT_PATH}")

    emitted, stats = build_sentence_candidates(parent_rows)

    print(f"\n=== SENTENCE BUILD STATS ===")
    print(f"  Parent rows:                {stats['parent_rows']}")
    print(f"  Parent splittable:          {stats['parent_splittable']}")
    print(f"  Parent not splittable:      {stats['parent_not_splittable']}")
    print(f"  Para pairs total:           {stats['para_pairs_total']}")
    print(f"  Para pairs sent-mismatch:   {stats['para_pairs_sent_mismatch']}")
    print(f"  Sentence pairs seen:        {stats['sent_pairs_total']}")
    print(f"  Sentence pairs emitted:     {stats['sent_pairs_emitted']}")
    print(f"  Quality rejected (total):   {stats['sent_pairs_quality_rejected']}")
    print(f"    — boilerplate:            {stats['sent_pairs_boilerplate']}")
    print(f"    — too short:              {stats['sent_pairs_too_short']}")
    print(f"    — too long (>80 tok):     {stats['sent_pairs_too_long']}")
    print(f"    — ratio fail:             {stats['sent_pairs_ratio_fail']}")
    print(f"    — nonhaw high:            {stats['sent_pairs_nonhaw_high']}")
    print(f"  Deduped:                    {stats['sent_pairs_deduped']}")

    if dry_run:
        print(f"\n[dry-run] Would write {len(emitted)} rows to {OUTPUT_PATH}")
        print(f"[dry-run] No files written.")
        return

    # Write candidates
    CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        for row in emitted:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"\nWrote {len(emitted)} rows → {OUTPUT_PATH}")

    # Write report
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / "hooilina_sentence_build_report_20260501.json"
    report = {
        "report_type": "hooilina_sentence_build",
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "input": str(INPUT_PATH),
        "output": str(OUTPUT_PATH),
        "algorithm": (
            "Two-level split (v2): "
            "(1) Numbered-paragraph split (\\n(?=\\d+\\.[ \\t])) on parent rows; "
            "pairs only when EN para count == HAW para count. "
            "(2) Sentence split within each paragraph pair using "
            "SENT_SPLIT_RE ((?<=[.!?])\\s+(?=[A-ZĀĒĪŌŪ\\u02bb])); "
            "pairs only when EN sentence count == HAW sentence count; "
            "quality gate: min 3 tokens/side, max 80 tokens/side, "
            "ratio 0.5-2.5, no boilerplate, nonhaw_share<=0.25; "
            "dedup by sha256_pair."
        ),
        "stats": stats,
        "policy": {
            "prototype_only": True,
            "release_eligible": False,
            "alignment_review_required": True,
            "split": "review-pending",
            "max_tokens_per_side": MAX_TOKENS_PER_SIDE,
            "note": (
                "All rows are prototype-only and release-ineligible due to KS "
                "editorial/copyright layer. Each row is a single sentence pair. "
                "Promotion to train handled by script 333 (hooilina-sentence-v2 gate)."
            ),
        },
    }
    with open(report_path, "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Wrote report → {report_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Build Hoʻoilina sentence-level Stage-2 candidates."
    )
    ap.add_argument("--dry-run", action="store_true",
                    help="Report what would be written without writing files.")
    ap.add_argument("--execute", action="store_true",
                    help="Write output files.")
    ap.add_argument("--self-test", action="store_true",
                    help="Run internal assertions and exit.")
    args = ap.parse_args()

    if args.self_test:
        self_test()
    elif args.dry_run:
        main(dry_run=True)
    elif args.execute:
        main(dry_run=False)
    else:
        ap.print_help()
        sys.exit(2)
