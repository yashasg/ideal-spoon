#!/usr/bin/env python3
"""Stage-2 Wikipedia langlinks candidate builder (Frank, Round 2 40k push).

Reads the probed Wikipedia haw↔en langlinks manifest and fetches article
content from both haw.wikipedia.org and en.wikipedia.org via MediaWiki API.
Extracts first paragraph (or first sentence if paragraph is too long) from
each article and emits ``data/stage2/candidates/wiki_langlinks_haw_en.jsonl``
— one row per langlink pair with extracted text.

Input:
  * ``data/raw/wiki-haw-en-langlinks/<YYYYMMDD>/langlinks_manifest.jsonl``
    (53 pairs from probe; each row has haw_revid, en_revid, titles, etc.)

Output (gitignored):
  * ``data/stage2/candidates/wiki_langlinks_haw_en.jsonl`` — Stage-2
    manifest-shaped JSONL. One row per langlink pair with extracted text.

Algorithm:
  1. Read langlinks manifest
  2. For each pair, fetch article content via MediaWiki API using revids
  3. Extract first paragraph text (up to first blank line or section header)
  4. If paragraph >500 chars, extract first sentence only
  5. Apply ʻokina U+02BB canonicalization on Hawaiian text
  6. Compute pair_hash using canonical compute_pair_hash
  7. Tag alignment_type='comparable-aligned', alignment_method='labse'

Stdlib + urllib only. Triple-gated: --dry-run (default), --limit, --execute.

Exit codes: 0 success, 2 misuse, 3 input/fetch error.
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
import urllib.error
import urllib.parse
import urllib.request
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
RAW_ROOT = REPO_ROOT / "data" / "raw" / "wiki-haw-en-langlinks"
DATA_STAGE2 = REPO_ROOT / "data" / "stage2"
DEFAULT_OUT = DATA_STAGE2 / "candidates" / "wiki_langlinks_haw_en.jsonl"

MANIFEST_SCHEMA_VERSION = "stage2.v0"
SOURCE_ID = "wiki-haw-en-langlinks"

# ʻokina canonicalization (match scripts/322_build_bible_candidates.py)
OKINA = "\u02bb"

USER_AGENT = (
    "ideal-spoon/0.1.0 (Stage-2 wiki-langlinks candidate builder; "
    "github.com/yashasg/ideal-spoon)"
)
RATE_SLEEP_SECONDS = 1.2
TIMEOUT = 30

HAW_API = "https://haw.wikipedia.org/w/api.php"
EN_API = "https://en.wikipedia.org/w/api.php"


def _utcnow_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today_compact_utc() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d")


def normalize_haw(text: str) -> str:
    return stage2_canonical_haw(text)


def normalize_en(text: str) -> str:
    return stage2_canonical_en(text)


def sha256_text(text: str) -> str:
    return stage2_sha256_text(text)


def compute_pair_hash(sha256_en_clean: str, sha256_haw_clean: str) -> str:
    return stage2_compute_pair_hash(sha256_en_clean, sha256_haw_clean)


def fetch_article_text(api_url: str, revid: int, title: str) -> str:
    """Fetch article text from MediaWiki API using revid.
    
    Returns the main content text (wikitext stripped of templates/markup).
    Uses prop=extracts with exintro=1 to get lead section only.
    """
    time.sleep(RATE_SLEEP_SECONDS)
    params = {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "prop": "extracts",
        "exintro": "1",  # Lead section only
        "explaintext": "1",  # Plain text, no HTML/wiki markup
        "exsectionformat": "plain",
        "revids": str(revid),
    }
    url = f"{api_url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read())
            pages = data.get("query", {}).get("pages", [])
            if not pages:
                return ""
            page = pages[0]
            extract = page.get("extract", "")
            return extract.strip()
    except urllib.error.HTTPError as e:
        print(f"⚠️  HTTP error fetching {title} (revid {revid}): {e.code}", file=sys.stderr)
        return ""
    except Exception as e:
        print(f"⚠️  Error fetching {title} (revid {revid}): {e}", file=sys.stderr)
        return ""


def extract_first_sentence(text: str, max_chars: int = 500) -> str:
    """Extract first sentence or first paragraph if <max_chars.
    
    If the full text is ≤max_chars, return it. Otherwise, extract first sentence.
    """
    text = text.strip()
    if not text:
        return ""
    
    # If short enough, use the whole text
    if len(text) <= max_chars:
        return text
    
    # Otherwise, extract first sentence
    # Simple sentence boundary detection: period followed by space and capital letter
    sentence_rx = re.compile(r'([.!?])\s+(?=[A-Z])')
    match = sentence_rx.search(text)
    if match:
        return text[:match.end()].strip()
    
    # Fallback: truncate at max_chars at a word boundary
    if len(text) > max_chars:
        truncated = text[:max_chars]
        last_space = truncated.rfind(' ')
        if last_space > max_chars // 2:
            return truncated[:last_space].strip() + "..."
    
    return text


def read_langlinks_manifest(path: Path) -> list[dict[str, Any]]:
    """Read langlinks_manifest.jsonl from probe."""
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def build_candidate(langlink_row: dict[str, Any], fetch_date: str) -> dict[str, Any] | None:
    """Build a Stage-2 candidate row from a langlinks manifest row.
    
    Returns None if text extraction fails on either side.
    """
    haw_title = langlink_row["haw_title"]
    en_title = langlink_row["en_title_resolved"]
    haw_revid = langlink_row["haw_revid"]
    en_revid = langlink_row["en_revid"]
    haw_pageid = langlink_row["haw_pageid"]
    en_pageid = langlink_row["en_pageid"]
    
    # Fetch article text
    print(f"  Fetching haw: {haw_title} (revid {haw_revid})...")
    haw_text = fetch_article_text(HAW_API, haw_revid, haw_title)
    if not haw_text:
        print(f"    ⚠️  Empty haw text, skipping pair")
        return None
    
    print(f"  Fetching en: {en_title} (revid {en_revid})...")
    en_text = fetch_article_text(EN_API, en_revid, en_title)
    if not en_text:
        print(f"    ⚠️  Empty en text, skipping pair")
        return None
    
    # Extract first sentence/paragraph
    haw_extract = extract_first_sentence(haw_text, max_chars=500)
    en_extract = extract_first_sentence(en_text, max_chars=500)
    
    if not haw_extract or not en_extract:
        print(f"    ⚠️  Empty extract after sentence extraction, skipping")
        return None
    
    # Normalize
    haw_clean = normalize_haw(haw_extract)
    en_clean = normalize_en(en_extract)
    
    # Compute hashes
    sha256_haw_raw = sha256_text(haw_extract)
    sha256_en_raw = sha256_text(en_extract)
    sha256_haw_clean = sha256_text(haw_clean)
    sha256_en_clean = sha256_text(en_clean)
    sha256_pair = compute_pair_hash(sha256_en_clean, sha256_haw_clean)
    
    # Build candidate row
    row = {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "source_id": SOURCE_ID,
        "source_pair_id": f"wiki-haw-en::{haw_pageid}::{en_pageid}",
        "sha256_pair": sha256_pair,
        "sha256_en_raw": sha256_en_raw,
        "sha256_haw_raw": sha256_haw_raw,
        "sha256_en_clean": sha256_en_clean,
        "sha256_haw_clean": sha256_haw_clean,
        "text_en": en_clean,
        "text_haw": haw_clean,
        "text_en_path": None,
        "text_haw_path": None,
        "alignment_type": "comparable-aligned",
        "alignment_method": "labse",
        "split": "review-pending",
        "prototype_only": True,
        "release_eligible": False,
        "license_inferred": None,
        "crosslink_stage1_overlap": False,
        "synthetic": False,
        "synthetic_source_model": None,
        "source_document_id_en": f"en.wikipedia::pageid={en_pageid}::revid={en_revid}",
        "source_document_id_haw": f"haw.wikipedia::pageid={haw_pageid}::revid={haw_revid}",
        "source_url_en": langlink_row["en_url"],
        "source_url_haw": langlink_row["haw_url"],
        "fetch_date": fetch_date,
        "provenance_notes": (
            f"Wikipedia interlanguage link: {haw_title} ↔ {en_title}. "
            f"Extracted first paragraph/sentence (lead section). "
            f"Haw revid {haw_revid}, en revid {en_revid}."
        ),
    }
    
    print(f"    ✓ Candidate built: {len(en_clean)} en chars, {len(haw_clean)} haw chars")
    return row


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build Stage-2 candidates from Wikipedia langlinks probe.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--fetch-date",
        default=None,
        help="Fetch date (YYYYMMDD) for raw manifest. Defaults to latest in data/raw/wiki-haw-en-langlinks/.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Output path (default: {DEFAULT_OUT}).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Process only first N langlink pairs (for testing).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Dry-run mode: process first 3 pairs, do not write output (default).",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute mode: process all pairs, write output. Overrides --dry-run.",
    )
    args = parser.parse_args()
    
    # Resolve fetch date
    if args.fetch_date:
        fetch_date = args.fetch_date
    else:
        # Find latest date in raw dir
        date_dirs = sorted([d.name for d in RAW_ROOT.iterdir() if d.is_dir() and d.name.isdigit()])
        if not date_dirs:
            print("❌ No date dirs found in data/raw/wiki-haw-en-langlinks/", file=sys.stderr)
            sys.exit(3)
        fetch_date = date_dirs[-1]
    
    manifest_path = RAW_ROOT / fetch_date / "langlinks_manifest.jsonl"
    if not manifest_path.exists():
        print(f"❌ Manifest not found: {manifest_path}", file=sys.stderr)
        sys.exit(3)
    
    # Triple-gate check
    is_dry_run = args.dry_run and not args.execute
    if is_dry_run:
        print(f"[DRY-RUN] Processing first 3 pairs from {manifest_path.name}")
        print(f"[DRY-RUN] No output will be written. Use --execute to write.")
    else:
        print(f"[EXECUTE] Processing {manifest_path}")
        print(f"[EXECUTE] Output: {args.output}")
    
    # Load langlinks manifest
    langlinks = read_langlinks_manifest(manifest_path)
    print(f"✅ Loaded {len(langlinks)} langlink pairs from {manifest_path.name}")
    
    # Apply limit
    if is_dry_run and not args.limit:
        limit = 3
    elif args.limit:
        limit = args.limit
    else:
        limit = None
    
    if limit:
        langlinks = langlinks[:limit]
        print(f"🔬 Processing first {len(langlinks)} pairs (limit: {limit})")
    
    # Build candidates
    candidates = []
    for i, langlink_row in enumerate(langlinks, 1):
        print(f"\n[{i}/{len(langlinks)}] Processing {langlink_row['haw_title']} ↔ {langlink_row['en_title_resolved']}")
        candidate = build_candidate(langlink_row, fetch_date)
        if candidate:
            candidates.append(candidate)
    
    print(f"\n📊 Built {len(candidates)} candidates from {len(langlinks)} langlink pairs")
    print(f"   Success rate: {len(candidates)}/{len(langlinks)} ({100*len(candidates)/len(langlinks):.1f}%)")
    
    # Write output if --execute
    if not is_dry_run:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8") as f:
            for row in candidates:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"\n✅ Wrote {len(candidates)} candidates to {args.output}")
    else:
        print(f"\n🔬 [DRY-RUN] No output written. Use --execute to write.")
    
    print("\n✅ Wikipedia langlinks candidate extraction complete!")


if __name__ == "__main__":
    main()
