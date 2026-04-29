#!/usr/bin/env python3
"""Hawaiian Wikipedia (`hawwiki`) source-specific collection plan (Frank).

Replaces the broad ``101_collect_rightslight.py`` planner. Each Hawaiian
source now has its own ``10X_collect_<source>.py`` script that owns the
shape of its own collection plan, because each source has its own
formatting and fetch contract (Wikimedia dump SHA1 manifest, MediaWiki
API page enumeration, archive.org item IDs, …) and forcing them through
one schema lost too much per-source detail.

This script emits a small JSON plan describing the dump-shaped fetch
that ``scripts/201_fetch_rightslight_raw.py --source hawwiki`` will
perform. It writes only metadata — no corpus text — and never makes
network calls. The plan is the input contract for ``201``.

Output (gitignored):
    data/local/hawwiki/collect_plan.json

Usage::

    python scripts/101_collect_hawwiki.py            # write plan
    python scripts/101_collect_hawwiki.py --print    # also pretty-print

Exit codes: 0 success, 2 I/O error.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "data" / "local" / "hawwiki"

SOURCE_ID = "hawwiki"
SOURCE_NAME = "Hawaiian Wikipedia"
WIKIMEDIA_TOS = "https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use"
WIKIMEDIA_LICENSE = "CC BY-SA 4.0 + GFDL (per-revision; see Wikimedia Terms)"


def _utcnow_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_plan() -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "generated_by": "scripts/101_collect_hawwiki.py (frank)",
        "generated_at_utc": _utcnow_iso(),
        "source_id": SOURCE_ID,
        "source_name": SOURCE_NAME,
        "fetch_shape": "wikimedia-dump",
        "fetcher_script": "scripts/201_fetch_rightslight_raw.py --source hawwiki",
        "rights_status_hint": "open_license_candidate",
        "license_observed": WIKIMEDIA_LICENSE,
        "tos_or_license_url": WIKIMEDIA_TOS,
        "metadata_artifacts": [
            {
                "kind": "sha1sums",
                "url": "https://dumps.wikimedia.org/hawwiki/latest/hawwiki-latest-sha1sums.txt",
                "ext": "txt",
                "license_observed": "Wikimedia infrastructure metadata",
                "notes": "Used to pin SHA1 of the dated dump file before any corpus pull.",
            },
            {
                "kind": "dumpstatus",
                "url_template": "https://dumps.wikimedia.org/hawwiki/{YYYYMMDD}/dumpstatus.json",
                "ext": "json",
                "license_observed": "Wikimedia infrastructure metadata",
                "notes": (
                    "dumpstatus.json is only published under the dated path, not "
                    "/latest/. 201 resolves the date by parsing dated filenames "
                    "in the sha1sums manifest."
                ),
            },
        ],
        "corpus_artifacts": [
            {
                "kind": "pages-articles-xml-bz2",
                "url": "https://dumps.wikimedia.org/hawwiki/latest/hawwiki-latest-pages-articles.xml.bz2",
                "ext": "xml.bz2",
                "license_observed": WIKIMEDIA_LICENSE,
                "sha1sums_suffix": "-pages-articles.xml.bz2",
                "extraction_method": "wiki-xml-stream",
                "notes": "Multi-MB; only fetched when 201 is invoked with --execute.",
            },
        ],
        "token_estimate_haw": {
            "conservative": 1_500_000,
            "base": 2_250_000,
            "upside": 3_000_000,
            "rationale": (
                ".squad/agents/frank/history.md (2026-04-29 token-yield pass): "
                "hawwiki dominates the publishable Stage-1 backbone."
            ),
        },
        "blockers": [],
        "storage_policy": {
            "raw_root": "data/raw/hawwiki/",
            "git_ignored": True,
            "rationale": "docs/data-pipeline.md §80; raw bytes never committed.",
        },
        "downstream_contract": {
            "fetch_jsonl_path": "data/raw/hawwiki/fetch.jsonl",
            "schema_owner": "scripts/201_fetch_rightslight_raw.py:ProvenanceRecord",
        },
        "issue": "https://github.com/yashasg/ideal-spoon/issues/1",
    }


def write_plan(plan: dict[str, Any], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "collect_plan.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)
        f.write("\n")
    readme = out_dir / "README.txt"
    if not readme.exists():
        readme.write_text(
            "This directory is gitignored. It holds the hawwiki collection\n"
            "plan (collect_plan.json) consumed by\n"
            "scripts/201_fetch_rightslight_raw.py --source hawwiki.\n"
            "Do not commit any file under data/.\n",
            encoding="utf-8",
        )
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Output directory (default: {OUTPUT_DIR.relative_to(REPO_ROOT)}).",
    )
    parser.add_argument(
        "--print",
        dest="print_plan",
        action="store_true",
        help="Pretty-print the plan to stdout in addition to writing it.",
    )
    args = parser.parse_args(argv)

    plan = build_plan()
    try:
        out_path = write_plan(plan, args.out)
    except OSError as e:
        print(f"error: failed to write plan: {e!r}", file=sys.stderr)
        return 2

    print(f"wrote hawwiki collect plan: {out_path.relative_to(REPO_ROOT)}")
    print(f"  fetcher_script : {plan['fetcher_script']}")
    print(f"  fetch_shape    : {plan['fetch_shape']}")
    est = plan["token_estimate_haw"]
    print(
        "  token_est_haw  : "
        f"cons={est['conservative']:,} base={est['base']:,} upside={est['upside']:,}"
    )
    if args.print_plan:
        print()
        print(json.dumps(plan, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
