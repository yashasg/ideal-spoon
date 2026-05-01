#!/usr/bin/env python3
"""Stage-2 Hawaiian Kingdom statutes DJVU/OCR raw fetcher (Frank).

Pulls the actual ``_djvu.txt`` OCR artifacts for all four paired-code imprints
listed in ``data-sources/stage2-parallel-fetch-plan.json`` under the
``hawaiian-kingdom-statutes-bilingual`` source. The 207 fetcher previously
captured only IA detail HTML pages (item landing chrome, ~230 KB each); body
text was never on disk. This script complements that pass and writes raw OCR
under the new::

    data/raw/hawaiian-kingdom-statutes-paired-imprints/<YYYYMMDD>/

per-source-id directory so that the metadata-only artifacts under
``hawaiian-kingdom-statutes-bilingual/`` remain untouched.

Item IDs and their actual IA file names (derived from the IA metadata API at
fetch time, since the ``esrp*`` items use date-based filenames rather than
``<id>_djvu.txt``)::

    esrp641724381             -> 1897.001_djvu.txt   (EN 1897 Penal Laws)
    esrp641728581             -> 1897.002_djvu.txt   (HAW 1897 Penal Laws)
    esrp475081650             -> 1869.001_djvu.txt   (EN 1869 Penal Code)
    esrp468790723             -> 1850.002_djvu.txt   (HAW side per fetch plan;
                                                     IA filename year = 1850 —
                                                     Frank flag for review)
    civilcodehawaii00armsgoog -> civilcodehawaii00armsgoog_djvu.txt (EN 1859 Civil)
    hekumukanawaiam00hawagoog -> hekumukanawaiam00hawagoog_djvu.txt (HAW 1859 Civil)
    statutelawshism00ricogoog -> statutelawshism00ricogoog_djvu.txt (EN 1846 Statute Laws)
    kanawaiikauiaek00ricogoog -> kanawaiikauiaek00ricogoog_djvu.txt (HAW 1846 Statute Laws)

Provenance: writes ``fetch.jsonl`` next to the fetched artifacts with one row
per IA item (source_url is the full ``archive.org/download/...`` URL).

Usage::

    python3 scripts/208_fetch_hk_statutes_djvu.py --dry-run
    python3 scripts/208_fetch_hk_statutes_djvu.py --execute

Exit codes: 0 success, 2 misuse, 3 fetch failure.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_ROOT = REPO_ROOT / "data" / "raw" / "hawaiian-kingdom-statutes-paired-imprints"

SOURCE_ID = "hawaiian-kingdom-statutes-paired-imprints"
LICENSE_OBSERVED = (
    "Hawaiian Kingdom government works, 1846-1897 imprints. US public domain "
    "by copyright term (pre-1929) and additionally by sovereign-edicts doctrine "
    "for the legal text itself. archive.org redistributes scans + OCR; IA ToS "
    "governs the bytes only."
)
TOS_URL = "https://archive.org/about/terms.php"
USER_AGENT = (
    "ideal-spoon/0.1.0 (stage2 HK-statutes djvu fetcher; "
    "contact via github.com/yashasg/ideal-spoon)"
)
FETCHER = "urllib.request (stdlib); script=scripts/208_fetch_hk_statutes_djvu.py v0.1.0"

# (item_id, djvu_filename, side, pair_label)
ITEMS: list[tuple[str, str, str, str]] = [
    ("esrp641724381",             "1897.001_djvu.txt",                       "en",  "1897-penal-laws"),
    ("esrp641728581",             "1897.002_djvu.txt",                       "haw", "1897-penal-laws"),
    ("esrp475081650",             "1869.001_djvu.txt",                       "en",  "1869-penal-code"),
    ("esrp468790723",             "1850.002_djvu.txt",                       "haw", "1869-penal-code"),
    ("civilcodehawaii00armsgoog", "civilcodehawaii00armsgoog_djvu.txt",     "en",  "1859-civil-code"),
    ("hekumukanawaiam00hawagoog", "hekumukanawaiam00hawagoog_djvu.txt",     "haw", "1859-civil-code"),
    ("statutelawshism00ricogoog", "statutelawshism00ricogoog_djvu.txt",     "en",  "1846-statute-laws"),
    ("kanawaiikauiaek00ricogoog", "kanawaiikauiaek00ricogoog_djvu.txt",     "haw", "1846-statute-laws"),
]

DOWNLOAD_URL = "https://archive.org/download/{item_id}/{filename}"


def _utcnow_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today_compact_utc() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d")


def _http_get(url: str, timeout: float = 120.0, attempts: int = 4) -> tuple[int, str, bytes]:
    last_exc: BaseException | None = None
    for attempt in range(1, attempts + 1):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.headers.get("Content-Type", ""), resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt < attempts:
                time.sleep(2.0 * attempt)
                last_exc = exc
                continue
            return exc.code, exc.headers.get("Content-Type", "") if exc.headers else "", b""
        except (urllib.error.URLError, TimeoutError) as exc:
            last_exc = exc
            time.sleep(2.0 * attempt)
    raise SystemExit(f"fetch failed after {attempts} attempts: {url}: {last_exc}")


def fetch_one(item_id: str, filename: str, side: str, pair_label: str,
              dest_dir: Path, prov_fh) -> dict:
    url = DOWNLOAD_URL.format(item_id=item_id, filename=filename)
    print(f"[hk-djvu] GET {url}", file=sys.stderr)
    status, ctype, body = _http_get(url)
    if status != 200 or not body:
        raise SystemExit(f"non-200 ({status}) for {url}")
    out_name = f"{item_id}__{filename}"
    out_path = dest_dir / out_name
    out_path.write_bytes(body)
    sha = hashlib.sha256(body).hexdigest()
    rec = {
        "source_id": SOURCE_ID,
        "source_url": url,
        "fetch_timestamp_utc": _utcnow_iso(),
        "http_status": status,
        "content_type": ctype,
        "content_length": len(body),
        "raw_sha256": sha,
        "raw_storage_path": str(out_path.relative_to(REPO_ROOT)),
        "tos_or_license_url": TOS_URL,
        "license_observed": LICENSE_OBSERVED,
        "fetcher_user_agent": USER_AGENT,
        "fetcher_tool_and_version": FETCHER,
        "source_specific_ids": {
            "ia_item_id": item_id,
            "ia_filename": filename,
            "side": side,
            "pair_label": pair_label,
        },
        "notes": "stage2 raw djvu OCR fetch; prototype_only=true; not a public artifact",
    }
    prov_fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
    prov_fh.flush()
    return rec


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--execute", action="store_true")
    p.add_argument("--fetch-date", default=None,
                   help="override YYYYMMDD subdir (default: today UTC)")
    args = p.parse_args(argv)

    fetch_date = args.fetch_date or _today_compact_utc()
    dest_dir = RAW_ROOT / fetch_date

    print(f"[hk-djvu] target: {dest_dir.relative_to(REPO_ROOT)} ({len(ITEMS)} items)",
          file=sys.stderr)
    for item_id, filename, side, label in ITEMS:
        url = DOWNLOAD_URL.format(item_id=item_id, filename=filename)
        print(f"  {side:>3s}  {label:18s}  {item_id:32s} -> {filename}",
              file=sys.stderr)
        if args.dry_run:
            print(f"     {url}", file=sys.stderr)

    if args.dry_run:
        return 0

    dest_dir.mkdir(parents=True, exist_ok=True)
    prov_path = RAW_ROOT / "fetch.jsonl"
    total = 0
    with prov_path.open("a", encoding="utf-8") as prov_fh:
        for item_id, filename, side, label in ITEMS:
            rec = fetch_one(item_id, filename, side, label, dest_dir, prov_fh)
            total += rec["content_length"]
            time.sleep(1.0)
    print(f"[hk-djvu] wrote {len(ITEMS)} files, {total:,} bytes total -> {dest_dir.relative_to(REPO_ROOT)}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
