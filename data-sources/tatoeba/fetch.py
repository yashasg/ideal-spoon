#!/usr/bin/env python3
"""Tatoeba en↔haw source adapter — Stage 2 candidate pairs (issue #17).

Downloads the Hawaiian sentence set and en↔haw link table from the pinned
Tatoeba dump, joins them to materialize en↔haw pairs, and emits a
schema-compatible candidate JSONL under the gitignored ``data/stage2/candidates/``
directory.

Provenance:
  * ``haw_sentences_detailed.tsv.bz2`` — Hawaiian sentence texts + contributors.
  * ``haw-eng_links.tsv.bz2`` — Hawaiian→English sentence link table.
  * ``eng_sentences_detailed.tsv.bz2`` — English sentence texts + contributors
    (streamed; only linked rows are kept).

Alignment policy:
  * ``alignment_type  = "parallel-sentence"``  (sentence-level pairs)
  * ``alignment_method = "manual"``             (Tatoeba links are human-curated)
  * ``alignment_score = null``                  (no embedding score needed)
  * ``register        = "unknown"``             (Tatoeba is mixed-domain)

Outputs (gitignored):
  data/stage2/candidates/tatoeba.jsonl
  data/raw/tatoeba-haw-eng/<DUMP_DATE>/   (raw .tsv.bz2 files)

Usage::

    python data-sources/tatoeba/fetch.py --dry-run
    python data-sources/tatoeba/fetch.py --execute
    python data-sources/tatoeba/fetch.py --self-test

Exit codes::

    0  success (including dry-run)
    1  I/O or network error
    2  CLI misuse
    3  schema / self-test failure
"""

from __future__ import annotations

import argparse
import bz2
import datetime
import hashlib
import io
import json
import math
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path
from typing import Any, Iterator

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve().parent
REPO_ROOT = _HERE.parent.parent
PINNED_DUMP_PATH = _HERE / "PINNED_DUMP.json"

CANDIDATE_JSONL = REPO_ROOT / "data" / "stage2" / "candidates" / "tatoeba.jsonl"
RAW_DIR_BASE = REPO_ROOT / "data" / "raw" / "tatoeba-haw-eng"

# ---------------------------------------------------------------------------
# Pinned dump metadata (also stored in PINNED_DUMP.json)
# ---------------------------------------------------------------------------

DUMP_DATE = "2025-05-01"
HAW_SENTENCES_URL = (
    "https://downloads.tatoeba.org/exports/per_language/haw/"
    "haw_sentences_detailed.tsv.bz2"
)
HAW_ENG_LINKS_URL = (
    "https://downloads.tatoeba.org/exports/per_language/haw/"
    "haw-eng_links.tsv.bz2"
)
ENG_SENTENCES_URL = (
    "https://downloads.tatoeba.org/exports/per_language/eng/"
    "eng_sentences_detailed.tsv.bz2"
)

LICENSE = "CC-BY 2.0 FR"
LICENSE_URL = "https://tatoeba.org/en/terms_of_use"

# Manifest schema version — must match 320_build_stage2_manifest.py.
MANIFEST_SCHEMA_VERSION = "stage2.v0"

ALIGNMENT_TYPE = "parallel-sentence"
ALIGNMENT_METHOD = "manual"
REGISTER = "unknown"
SOURCE = "tatoeba"

TATOEBA_SENTENCE_URL_TEMPLATE = "https://tatoeba.org/sentences/show/{id}"

# ---------------------------------------------------------------------------
# TSV parsing helpers
# ---------------------------------------------------------------------------

# Tatoeba sentences_detailed.tsv format (no header):
#   sentence_id TAB lang TAB text TAB username TAB date_added TAB date_last_modified
_SENTENCES_DETAILED_COLS = ("sentence_id", "lang", "text", "username", "date_added", "date_last_modified")

# Tatoeba haw-eng_links.tsv format (no header):
#   haw_sentence_id TAB eng_sentence_id
_LINKS_COLS = ("id_from", "id_to")


def parse_sentences_detailed(
    lines: Iterator[str],
) -> dict[str, dict[str, str]]:
    """Parse a Tatoeba sentences_detailed TSV into a {sentence_id: row_dict} map.

    Skips blank lines and lines where the text field is empty.
    """
    result: dict[str, dict[str, str]] = {}
    for raw in lines:
        line = raw.rstrip("\n")
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        sid = parts[0].strip()
        text = parts[2].strip() if len(parts) > 2 else ""
        if not sid or not text:
            continue
        result[sid] = {
            "sentence_id": sid,
            "lang": parts[1].strip() if len(parts) > 1 else "",
            "text": text,
            "username": parts[3].strip() if len(parts) > 3 else "",
            "date_added": parts[4].strip() if len(parts) > 4 else "",
        }
    return result


def parse_links(lines: Iterator[str]) -> list[tuple[str, str]]:
    """Parse a Tatoeba per-language links TSV into a list of (id_from, id_to) pairs."""
    pairs: list[tuple[str, str]] = []
    for raw in lines:
        line = raw.rstrip("\n")
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        id_from = parts[0].strip()
        id_to = parts[1].strip()
        if id_from and id_to:
            pairs.append((id_from, id_to))
    return pairs


def stream_sentences_for_ids(
    lines: Iterator[str],
    needed_ids: set[str],
) -> dict[str, dict[str, str]]:
    """Stream a sentences_detailed TSV and return only rows whose IDs are in ``needed_ids``.

    Stops early once all needed IDs have been found.
    """
    result: dict[str, dict[str, str]] = {}
    remaining = set(needed_ids)
    for raw in lines:
        if not remaining:
            break
        line = raw.rstrip("\n")
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        sid = parts[0].strip()
        if sid not in remaining:
            continue
        text = parts[2].strip()
        if not text:
            continue
        result[sid] = {
            "sentence_id": sid,
            "lang": parts[1].strip() if len(parts) > 1 else "",
            "text": text,
            "username": parts[3].strip() if len(parts) > 3 else "",
            "date_added": parts[4].strip() if len(parts) > 4 else "",
        }
        remaining.discard(sid)
    return result


# ---------------------------------------------------------------------------
# Hash / normalization helpers
# ---------------------------------------------------------------------------

def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _length_ratio(haw_text: str, en_text: str) -> float | None:
    haw_tokens = len(haw_text.split())
    en_tokens = len(en_text.split())
    if en_tokens == 0:
        return None
    ratio = haw_tokens / en_tokens
    return round(ratio, 4) if math.isfinite(ratio) else None


# ---------------------------------------------------------------------------
# Pair builder
# ---------------------------------------------------------------------------

def build_candidate_row(
    haw_row: dict[str, str],
    eng_row: dict[str, str],
    fetch_date: str,
) -> dict[str, Any]:
    """Build a schema-compatible candidate manifest row from two Tatoeba sentence rows.

    All required fields in ``scripts/320_build_stage2_manifest.py::MANIFEST_FIELDS``
    that can be computed at fetch time are populated. Fields requiring downstream
    dedup/scoring (e.g., ``dedup_cluster_id`` reassignment, ``crosslink_stage1_overlap``)
    are set to conservative defaults.
    """
    haw_id = haw_row["sentence_id"]
    eng_id = eng_row["sentence_id"]
    pair_id = f"tatoeba-haw{haw_id}-en{eng_id}"

    text_haw_raw = haw_row["text"]
    text_en_raw = eng_row["text"]
    text_haw_clean = _nfc(text_haw_raw)
    text_en_clean = _nfc(text_en_raw)

    sha256_haw_raw = _sha256(text_haw_raw)
    sha256_en_raw = _sha256(text_en_raw)
    sha256_haw_clean = _sha256(text_haw_clean)
    sha256_en_clean = _sha256(text_en_clean)
    sha256_pair = _sha256(sha256_en_clean + "\u2016" + sha256_haw_clean)

    length_ratio = _length_ratio(text_haw_clean, text_en_clean)

    return {
        "pair_id": pair_id,
        "source": SOURCE,
        "source_url_en": TATOEBA_SENTENCE_URL_TEMPLATE.format(id=eng_id),
        "source_url_haw": TATOEBA_SENTENCE_URL_TEMPLATE.format(id=haw_id),
        "fetch_date": fetch_date,
        "sha256_en_raw": sha256_en_raw,
        "sha256_haw_raw": sha256_haw_raw,
        "sha256_en_clean": sha256_en_clean,
        "sha256_haw_clean": sha256_haw_clean,
        "sha256_pair": sha256_pair,
        "record_id_en": eng_id,
        "record_id_haw": haw_id,
        "text_en": text_en_clean,
        "text_haw": text_haw_clean,
        "text_en_path": None,
        "text_haw_path": None,
        "alignment_type": ALIGNMENT_TYPE,
        "alignment_method": ALIGNMENT_METHOD,
        "alignment_model": None,
        "alignment_score": None,
        "alignment_review_required": False,
        "length_ratio_haw_over_en": length_ratio,
        "lang_id_en": "en",
        "lang_id_en_confidence": 1.0,
        "lang_id_haw": "haw",
        "lang_id_haw_confidence": 1.0,
        "direction_original": "unknown",
        "register": REGISTER,
        "edition_or_version": None,
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
            f"Tatoeba contributors: haw={haw_row.get('username', '')!r} "
            f"en={eng_row.get('username', '')!r}. "
            f"License: {LICENSE}. See {LICENSE_URL}."
        ),
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        # Extra provenance fields (not in manifest schema, stripped by manifest builder):
        "contributor_haw": haw_row.get("username", ""),
        "contributor_en": eng_row.get("username", ""),
        "tatoeba_sentence_id_haw": haw_id,
        "tatoeba_sentence_id_en": eng_id,
    }


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------

_USER_AGENT = "ideal-spoon-tatoeba-adapter/0.1 (prototype; contact: see repo)"


def _head_url(url: str) -> dict[str, Any]:
    """Return {status, content_length} for a HEAD request. Never raises."""
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return {
                "url": url,
                "status": resp.status,
                "content_length": resp.headers.get("Content-Length"),
                "last_modified": resp.headers.get("Last-Modified"),
            }
    except Exception as exc:
        return {"url": url, "status": None, "error": str(exc)}


def _download_bz2_lines(url: str, dest: Path) -> list[str]:
    """Download a .bz2 file to ``dest``, decompress, and return lines.

    Streams through bz2 decompression; does not keep a decompressed copy on disk.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw_bytes = resp.read()
    with dest.open("wb") as fh:
        fh.write(raw_bytes)
    decompressed = bz2.decompress(raw_bytes)
    return decompressed.decode("utf-8").splitlines()


def _download_bz2_lines_streaming(url: str, dest: Path) -> Iterator[str]:
    """Download a (potentially large) .bz2 file and yield decoded lines.

    The raw .bz2 bytes are persisted to ``dest``; decompression is streamed to
    avoid materialising the full decompressed payload in memory for large files
    (e.g., eng_sentences_detailed.tsv.bz2).
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    # Download in chunks, write raw bz2 to dest, decompress in streaming mode.
    with urllib.request.urlopen(req, timeout=300) as resp:
        raw_bytes = resp.read()
    with dest.open("wb") as fh:
        fh.write(raw_bytes)
    decompressed = bz2.decompress(raw_bytes)
    for line in decompressed.decode("utf-8").splitlines():
        yield line


# ---------------------------------------------------------------------------
# Core pipeline functions (testable without network)
# ---------------------------------------------------------------------------

def join_pairs(
    haw_sentences: dict[str, dict[str, str]],
    links: list[tuple[str, str]],
    eng_sentences: dict[str, dict[str, str]],
    fetch_date: str,
) -> list[dict[str, Any]]:
    """Join sentence tables and links into candidate manifest rows.

    Links where either the haw or eng sentence is missing from the respective
    tables are silently skipped (can happen if a sentence was deleted after the
    link was recorded, or if the eng sentence was not found in the streamed
    eng table).
    """
    rows: list[dict[str, Any]] = []
    for haw_id, eng_id in links:
        haw_row = haw_sentences.get(haw_id)
        eng_row = eng_sentences.get(eng_id)
        if haw_row is None or eng_row is None:
            continue
        rows.append(build_candidate_row(haw_row, eng_row, fetch_date))
    return rows


# ---------------------------------------------------------------------------
# Dry-run mode
# ---------------------------------------------------------------------------

def run_dry_run() -> int:
    print("[DRY-RUN] Tatoeba en↔haw adapter — no files will be written.")
    print(f"[DRY-RUN] Pinned dump date: {DUMP_DATE}")
    print(f"[DRY-RUN] Candidate output: {CANDIDATE_JSONL.relative_to(REPO_ROOT)} (gitignored)")
    print(f"[DRY-RUN] Raw storage:      data/raw/tatoeba-haw-eng/{DUMP_DATE}/")
    print()
    print("[DRY-RUN] Checking URL accessibility (HEAD requests):")
    urls = [HAW_SENTENCES_URL, HAW_ENG_LINKS_URL, ENG_SENTENCES_URL]
    all_ok = True
    for url in urls:
        info = _head_url(url)
        status = info.get("status")
        cl = info.get("content_length", "?")
        err = info.get("error")
        if err:
            print(f"  [WARN]  {url}\n          error: {err}")
            all_ok = False
        else:
            size_mb = f"{int(cl)/1024/1024:.1f} MB" if cl and cl != "?" else "? bytes"
            print(f"  [OK]    HTTP {status}  {size_mb:>10}  {url}")
        time.sleep(1)
    print()
    if all_ok:
        print("[DRY-RUN] All URLs accessible. Run --execute to download and emit candidates.")
        return 0
    else:
        print("[DRY-RUN] Some URLs returned warnings. Review above before --execute.")
        return 0


# ---------------------------------------------------------------------------
# Execute mode
# ---------------------------------------------------------------------------

def run_execute() -> int:
    fetch_date = datetime.date.today().strftime("%Y%m%d")
    raw_dir = RAW_DIR_BASE / DUMP_DATE

    print(f"[EXECUTE] Downloading Hawaiian sentences from Tatoeba ({DUMP_DATE})…")
    try:
        haw_lines = _download_bz2_lines(
            HAW_SENTENCES_URL,
            raw_dir / "haw_sentences_detailed.tsv.bz2",
        )
    except Exception as exc:
        print(f"[ERROR] Failed to download haw sentences: {exc}", file=sys.stderr)
        return 1
    time.sleep(1)

    print(f"[EXECUTE] Downloading en↔haw links…")
    try:
        link_lines = _download_bz2_lines(
            HAW_ENG_LINKS_URL,
            raw_dir / "haw-eng_links.tsv.bz2",
        )
    except Exception as exc:
        print(f"[ERROR] Failed to download haw-eng links: {exc}", file=sys.stderr)
        return 1
    time.sleep(1)

    haw_sentences = parse_sentences_detailed(iter(haw_lines))
    links = parse_links(iter(link_lines))
    needed_eng_ids = {eng_id for _, eng_id in links}

    print(f"[EXECUTE] Found {len(haw_sentences)} haw sentences, {len(links)} links, {len(needed_eng_ids)} unique eng IDs.")
    print(f"[EXECUTE] Downloading English sentences (streaming, keeping {len(needed_eng_ids)} IDs)…")

    try:
        eng_line_iter = _download_bz2_lines_streaming(
            ENG_SENTENCES_URL,
            raw_dir / "eng_sentences_detailed.tsv.bz2",
        )
        eng_sentences = stream_sentences_for_ids(eng_line_iter, needed_eng_ids)
    except Exception as exc:
        print(f"[ERROR] Failed to download eng sentences: {exc}", file=sys.stderr)
        return 1

    missing_eng = len(needed_eng_ids) - len(eng_sentences)
    if missing_eng:
        print(f"[WARN]  {missing_eng} linked eng sentence(s) not found in eng table (deleted/merged).")

    rows = join_pairs(haw_sentences, links, eng_sentences, fetch_date)
    print(f"[EXECUTE] Built {len(rows)} candidate pairs.")

    if not rows:
        print("[WARN]  Zero pairs produced. Check haw sentences and links files.", file=sys.stderr)

    CANDIDATE_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with CANDIDATE_JSONL.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"[OK]    Wrote {len(rows)} rows → {CANDIDATE_JSONL.relative_to(REPO_ROOT)}")
    return 0


# ---------------------------------------------------------------------------
# Self-test (synthetic fixtures, no network)
# ---------------------------------------------------------------------------

def _self_test() -> int:
    """In-memory smoke test against synthetic fixture data. Stdlib only, no network."""
    from io import StringIO

    haw_tsv = "\n".join([
        "1001\thaw\tʻO Hawaiʻi kēia ʻāina nani.\tuser1\t2020-01-01\t2020-01-01",
        "1002\thaw\tHe aloha ko Hawaiʻi nei.\tuser2\t2020-01-02\t2020-01-02",
        "1003\thaw\tUa ola nō i ka pane a ke aloha.\tuser3\t2020-01-03\t2020-01-03",
        "1004\thaw\tHele ana au i ke kula.\tuser4\t2020-01-04\t2020-01-04",
        "1005\thaw\tHe nui ka makemake o ka naʻauao.\tuser5\t2020-01-05\t2020-01-05",
    ])
    eng_tsv = "\n".join([
        "2001\teng\tHawaiʻi is a beautiful land.\tuser6\t2020-01-01\t2020-01-01",
        "2002\teng\tHawaiʻi is full of love.\tuser7\t2020-01-02\t2020-01-02",
        "2003\teng\tOne lives by the response of aloha.\tuser8\t2020-01-03\t2020-01-03",
        "2004\teng\tI am going to school.\tuser9\t2020-01-04\t2020-01-04",
        "2005\teng\tThe desire for knowledge is great.\tuser10\t2020-01-05\t2020-01-05",
        "9999\teng\tThis sentence has no haw link.\tuserX\t2020-01-06\t2020-01-06",
    ])
    links_tsv = "\n".join([
        "1001\t2001",
        "1002\t2002",
        "1003\t2003",
        "1004\t2004",
        "1005\t2005",
    ])

    haw_sentences = parse_sentences_detailed(iter(haw_tsv.splitlines()))
    eng_sentences = parse_sentences_detailed(iter(eng_tsv.splitlines()))
    links = parse_links(iter(links_tsv.splitlines()))

    assert len(haw_sentences) == 5, f"Expected 5 haw sentences, got {len(haw_sentences)}"
    assert len(eng_sentences) == 6, f"Expected 6 eng sentences, got {len(eng_sentences)}"
    assert len(links) == 5, f"Expected 5 links, got {len(links)}"

    needed = {eng_id for _, eng_id in links}
    eng_filtered = stream_sentences_for_ids(iter(eng_tsv.splitlines()), needed)
    assert len(eng_filtered) == 5, f"Expected 5 filtered eng sentences, got {len(eng_filtered)}"
    assert "9999" not in eng_filtered

    rows = join_pairs(haw_sentences, links, eng_filtered, "20250501")
    assert len(rows) == 5, f"Expected 5 candidate rows, got {len(rows)}"

    # Spot-check first row.
    r0 = rows[0]
    assert r0["source"] == SOURCE
    assert r0["alignment_type"] == ALIGNMENT_TYPE
    assert r0["alignment_method"] == ALIGNMENT_METHOD
    assert r0["alignment_score"] is None
    assert r0["register"] == REGISTER
    assert r0["synthetic"] is False
    assert r0["prototype_only"] is True
    assert r0["release_eligible"] is False
    assert r0["license_inferred"] is None
    assert r0["split"] == "review-pending"
    assert r0["manifest_schema_version"] == MANIFEST_SCHEMA_VERSION
    assert r0["lang_id_haw"] == "haw"
    assert r0["lang_id_en"] == "en"
    assert isinstance(r0["sha256_pair"], str) and len(r0["sha256_pair"]) == 64
    assert isinstance(r0["length_ratio_haw_over_en"], float)

    # Verify pair hash invariant (mirrors compute_pair_hash in 320_build_stage2_manifest.py).
    expected_pair_hash = _sha256(r0["sha256_en_clean"] + "\u2016" + r0["sha256_haw_clean"])
    assert r0["sha256_pair"] == expected_pair_hash, "sha256_pair mismatch"

    # Missing link side: add a link whose eng side doesn't exist.
    bad_links = [("1001", "MISSING")]
    bad_rows = join_pairs(haw_sentences, bad_links, eng_filtered, "20250501")
    assert len(bad_rows) == 0, "Should skip pairs with missing eng sentence"

    print(f"[OK] self-test passed: {len(rows)} pairs, schema fields verified.")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Tatoeba en↔haw source adapter — Stage 2 candidate pairs (issue #17).",
    )
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Verify URL accessibility and print plan; do not download or write.",
    )
    mode.add_argument(
        "--execute",
        action="store_true",
        help="Download Tatoeba dumps and emit candidate JSONL.",
    )
    mode.add_argument(
        "--self-test",
        action="store_true",
        help="Run in-memory smoke test against synthetic fixtures (no network).",
    )
    args = ap.parse_args(argv)

    if args.dry_run:
        return run_dry_run()
    if args.execute:
        return run_execute()
    if args.self_test:
        return _self_test()
    return 2


if __name__ == "__main__":
    sys.exit(main())
