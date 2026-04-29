#!/usr/bin/env python3
"""Hawaiian Wiktionary (`hawwiktionary`) source-specific collection plan (Frank).

Replaces the broad ``101_collect_rightslight.py`` planner for Hawaiian
Wiktionary. ``hawwiktionary`` is one of the dump-shaped sources handled
by ``scripts/201_fetch_rightslight_raw.py`` so it gets its own
``10X_collect_<source>.py`` peer to ``101_collect_hawwiki.py``.

Status note: at the time of writing, Wikimedia is **404-ing**
``hawwiktionary-latest-sha1sums.txt``. The fetcher fails loudly on this
source by design — the plan still records the canonical URLs and the
upstream blocker so we re-check before any bulk run.

Output (gitignored):
    data/local/hawwiktionary/collect_plan.json

Usage::

    python scripts/103_collect_hawwiktionary.py            # write plan
    python scripts/103_collect_hawwiktionary.py --print    # also pretty-print

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
OUTPUT_DIR = REPO_ROOT / "data" / "local" / "hawwiktionary"

SOURCE_ID = "hawwiktionary"
SOURCE_NAME = "Hawaiian Wiktionary"
WIKIMEDIA_TOS = "https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use"
WIKIMEDIA_LICENSE = "CC BY-SA 4.0 + GFDL (per-revision; see Wikimedia Terms)"


def _utcnow_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_plan() -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "generated_by": "scripts/103_collect_hawwiktionary.py (frank)",
        "generated_at_utc": _utcnow_iso(),
        "source_id": SOURCE_ID,
        "source_name": SOURCE_NAME,
        "fetch_shape": "wikimedia-dump",
        "fetcher_script": "scripts/201_fetch_rightslight_raw.py --source hawwiktionary",
        "rights_status_hint": "open_license_candidate",
        "license_observed": WIKIMEDIA_LICENSE,
        "tos_or_license_url": WIKIMEDIA_TOS,
        "metadata_artifacts": [
            {
                "kind": "sha1sums",
                "url": "https://dumps.wikimedia.org/hawwiktionary/latest/hawwiktionary-latest-sha1sums.txt",
                "ext": "txt",
                "license_observed": "Wikimedia infrastructure metadata",
                "notes": "Currently upstream 404 — see blockers.",
            },
        ],
        "corpus_artifacts": [
            {
                "kind": "pages-articles-xml-bz2",
                "url": "https://dumps.wikimedia.org/hawwiktionary/latest/hawwiktionary-latest-pages-articles.xml.bz2",
                "ext": "xml.bz2",
                "license_observed": WIKIMEDIA_LICENSE,
                "sha1sums_suffix": "-pages-articles.xml.bz2",
                "extraction_method": "wiki-xml-stream",
                "notes": "Multi-MB; only fetched when 201 is invoked with --execute.",
            },
        ],
        "token_estimate_haw": {
            "conservative": 50_000,
            "base": 100_000,
            "upside": 150_000,
            "rationale": (
                ".squad/agents/frank/history.md (2026-04-29 token-yield pass): "
                "small lexicon; primary value is ʻokina/kahakō audit, not bulk volume."
            ),
        },
        "blockers": [
            "Wikimedia is currently 404-ing hawwiktionary-latest-sha1sums.txt; "
            "the 201 fetcher exits with code 3 on this source. "
            "Re-check upstream before any bulk run "
            "(history.md 2026-04-29 fetch script note).",
        ],
        "storage_policy": {
            "raw_root": "data/raw/hawwiktionary/",
            "git_ignored": True,
            "rationale": "docs/data-pipeline.md §80; raw bytes never committed.",
        },
        "downstream_contract": {
            "fetch_jsonl_path": "data/raw/hawwiktionary/fetch.jsonl",
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
            "This directory is gitignored. It holds the hawwiktionary collection\n"
            "plan (collect_plan.json) consumed by\n"
            "scripts/201_fetch_rightslight_raw.py --source hawwiktionary.\n"
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

    print(f"wrote hawwiktionary collect plan: {out_path.relative_to(REPO_ROOT)}")
    print(f"  fetcher_script : {plan['fetcher_script']}")
    print(f"  fetch_shape    : {plan['fetch_shape']}")
    est = plan["token_estimate_haw"]
    print(
        "  token_est_haw  : "
        f"cons={est['conservative']:,} base={est['base']:,} upside={est['upside']:,}"
    )
    for blk in plan["blockers"]:
        print(f"  BLOCKER        : {blk}")
    if args.print_plan:
        print()
        print(json.dumps(plan, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
