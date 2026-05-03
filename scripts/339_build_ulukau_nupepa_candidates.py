#!/usr/bin/env python3
"""Build Ulukau Nupepa candidates from raw fetch output.

Reads raw articles with user translations from data/raw/ulukau-nupepa/20260502/articles.jsonl
and emits Stage-2 candidate rows to data/stage2/candidates/ulukau_nupepa.jsonl.

Alignment strategy:
* If HTML has matching <p> counts, align paragraphs.
* Otherwise, align article-level (single pair per article).

ʻOkina canonicalization:
* Hawaiian text: U+02BB (ʻ) always (replace ASCII apostrophe, backtick, etc.).
* English text: ASCII apostrophe U+0027 (') for contractions (don't, it's).

Usage::

    # Dry-run (default): load raw fetch, report expected pairs, no write
    python scripts/339_build_ulukau_nupepa_candidates.py --dry-run

    # Execute: write candidates JSONL
    python scripts/339_build_ulukau_nupepa_candidates.py --execute
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import unicodedata
from html.parser import HTMLParser
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
DATA_RAW = REPO_ROOT / "data" / "raw" / "ulukau-nupepa" / "20260502"
DATA_STAGE2 = REPO_ROOT / "data" / "stage2"
CANDIDATES_DIR = DATA_STAGE2 / "candidates"
OUTPUT_PATH = CANDIDATES_DIR / "ulukau_nupepa.jsonl"


def compute_pair_hash(sha256_en_clean: str, sha256_haw_clean: str) -> str:
    return stage2_compute_pair_hash(sha256_en_clean, sha256_haw_clean)


def normalize_haw(text: str) -> str:
    return stage2_canonical_haw(text)


def normalize_en(text: str) -> str:
    return stage2_canonical_en(text)


class ParagraphExtractor(HTMLParser):
    """Extract paragraph text from HTML."""

    def __init__(self):
        super().__init__()
        self.paragraphs: list[str] = []
        self._current_p: list[str] = []
        self._in_p = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "p":
            self._in_p = True
            self._current_p = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "p" and self._in_p:
            self._in_p = False
            text = "".join(self._current_p).strip()
            if text:
                self.paragraphs.append(text)
            self._current_p = []

    def handle_data(self, data: str) -> None:
        if self._in_p:
            self._current_p.append(data)


def extract_paragraphs(html_text: str) -> list[str]:
    """Extract paragraph text from HTML."""
    parser = ParagraphExtractor()
    # Decode HTML entities first
    html_text = html.unescape(html_text)
    parser.feed(html_text)
    return parser.paragraphs


def sha256_text(text: str) -> str:
    return stage2_sha256_text(text)


def build_candidates(raw_articles_path: Path, output_path: Path, dry_run: bool) -> None:
    """Build Stage-2 candidates from raw articles."""
    if not raw_articles_path.exists():
        print(f"error: raw articles file not found: {raw_articles_path}", file=sys.stderr)
        sys.exit(1)

    articles = []
    with raw_articles_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                articles.append(json.loads(line))

    print(f"Loaded {len(articles)} articles with translations.", file=sys.stderr)

    candidates: list[dict[str, Any]] = []
    pair_hashes_seen: set[str] = set()

    for article in articles:
        oid = article["oid"]
        paper_code = article["paper_code"]
        issue_date = article["issue_date"]
        haw_html = article["haw_text_html"]
        en_html = article["en_translation_html"]

        # Extract paragraphs
        haw_paragraphs = extract_paragraphs(haw_html)
        en_paragraphs = extract_paragraphs(en_html)

        # Alignment strategy: if paragraph counts match, align; else article-level
        if len(haw_paragraphs) == len(en_paragraphs) and len(haw_paragraphs) > 0:
            # Paragraph-level alignment
            for idx, (haw_p, en_p) in enumerate(zip(haw_paragraphs, en_paragraphs)):
                haw_clean = normalize_haw(haw_p)
                en_clean = normalize_en(en_p)

                sha_haw = sha256_text(haw_clean)
                sha_en = sha256_text(en_clean)
                pair_hash = compute_pair_hash(sha_en, sha_haw)

                if pair_hash in pair_hashes_seen:
                    continue
                pair_hashes_seen.add(pair_hash)

                # Extract era from issue_date
                era = "unknown"
                if issue_date:
                    year = int(issue_date.split("-")[0])
                    if 1834 <= year <= 1893:
                        era = "kingdom"
                    elif 1894 <= year <= 1920:
                        era = "republic-early-territory"
                    elif 1921 <= year <= 1948:
                        era = "territory"

                candidate = {
                    "pair_id": f"ulukau-nupepa-{oid}-p{idx}",
                    "sha256_pair": pair_hash,
                    "sha256_en_clean": sha_en,
                    "sha256_haw_clean": sha_haw,
                    "text_en": en_clean,
                    "text_haw": haw_clean,
                    "alignment_type": "comparable-aligned",
                    "alignment_method": "ulukau_user_translation",
                    "alignment_score": None,
                    "alignment_review_required": False,
                    "source": "ulukau-nupepa",
                    "source_url_en": f"https://www.nupepa.org/?a=d&d={oid}",
                    "source_url_haw": f"https://www.nupepa.org/?a=d&d={oid}",
                    "register": "newspaper",
                    "era": era,
                    "direction_original": "haw-original",
                    "synthetic": False,
                    "license_observed": "ulukau_personal_use_only",
                    "license_inferred": None,
                    "prototype_only": True,
                    "release_eligible": False,
                    "attribution_required": "Ka Haka ʻUla O Keʻelikōlani College of Hawaiian Language, University of Hawaiʻi at Hilo, and ALU LIKE, Inc. via Ulukau: The Hawaiian Electronic Library (www.nupepa.org)",
                    "split": "review-pending",
                    "metadata": {
                        "oid": oid,
                        "paper_code": paper_code,
                        "issue_date": issue_date,
                        "paragraph_idx": idx,
                    },
                }
                candidates.append(candidate)
        else:
            # Article-level alignment (single pair)
            haw_full = " ".join(haw_paragraphs)
            en_full = " ".join(en_paragraphs)

            haw_clean = normalize_haw(haw_full)
            en_clean = normalize_en(en_full)

            sha_haw = sha256_text(haw_clean)
            sha_en = sha256_text(en_clean)
            pair_hash = compute_pair_hash(sha_en, sha_haw)

            if pair_hash in pair_hashes_seen:
                continue
            pair_hashes_seen.add(pair_hash)

            # Extract era from issue_date
            era = "unknown"
            if issue_date:
                year = int(issue_date.split("-")[0])
                if 1834 <= year <= 1893:
                    era = "kingdom"
                elif 1894 <= year <= 1920:
                    era = "republic-early-territory"
                elif 1921 <= year <= 1948:
                    era = "territory"

            candidate = {
                "pair_id": f"ulukau-nupepa-{oid}",
                "sha256_pair": pair_hash,
                "sha256_en_clean": sha_en,
                "sha256_haw_clean": sha_haw,
                "text_en": en_clean,
                "text_haw": haw_clean,
                "alignment_type": "comparable-aligned",
                "alignment_method": "ulukau_user_translation",
                "alignment_score": None,
                "alignment_review_required": False,
                "source": "ulukau-nupepa",
                "source_url_en": f"https://www.nupepa.org/?a=d&d={oid}",
                "source_url_haw": f"https://www.nupepa.org/?a=d&d={oid}",
                "register": "newspaper",
                "era": era,
                "direction_original": "haw-original",
                "synthetic": False,
                "license_observed": "ulukau_personal_use_only",
                "license_inferred": None,
                "prototype_only": True,
                "release_eligible": False,
                "attribution_required": "Ka Haka ʻUla O Keʻelikōlani College of Hawaiian Language, University of Hawaiʻi at Hilo, and ALU LIKE, Inc. via Ulukau: The Hawaiian Electronic Library (www.nupepa.org)",
                "split": "review-pending",
                "metadata": {
                    "oid": oid,
                    "paper_code": paper_code,
                    "issue_date": issue_date,
                    "alignment_level": "article",
                },
            }
            candidates.append(candidate)

    print(f"Generated {len(candidates)} candidate pairs.", file=sys.stderr)

    if dry_run:
        print("Dry-run complete. No output written.", file=sys.stderr)
        return

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for candidate in candidates:
            f.write(json.dumps(candidate, ensure_ascii=False) + "\n")

    print(f"Wrote {len(candidates)} candidates to {output_path}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build Ulukau Nupepa Stage-2 candidates from raw fetch output.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load raw fetch, report expected pairs, no write (default).",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Write candidates JSONL.",
    )

    args = parser.parse_args()

    # Default to dry-run if neither is specified
    if not args.dry_run and not args.execute:
        args.dry_run = True

    build_candidates(DATA_RAW / "articles.jsonl", OUTPUT_PATH, args.dry_run)


if __name__ == "__main__":
    main()
