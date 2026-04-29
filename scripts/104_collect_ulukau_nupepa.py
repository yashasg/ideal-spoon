#!/usr/bin/env python3
"""Ulukau/Nupepa newspaper OCR source-specific collection plan.

This is the 100-phase planner for Hawaiian-language newspapers hosted by
Ulukau/Nupepa. It writes a local, gitignored document plan that
``scripts/204_fetch_ulukau_nupepa_raw.py`` can consume.

Important posture:

* The nūpepa source is prototype-only and rights-gated. It is useful for
  private experiments, not for public release of corpora, weights, tokenizer,
  or demos.
* Public Nupepa pages currently present a Cloudflare challenge to non-browser
  fetches. This script does not bypass that; it only writes fetch candidates.
* There is no documented bulk OCR endpoint in this adapter yet. Bulk ingest
  requires a legitimate export/API, permissioned bulk access, or manually
  supplied document IDs/HTML exports.
* The document plan contains URLs and metadata only; it never contains OCR
  text or corpus payloads.

Output (gitignored):
    data/local/ulukau_nupepa/collect_plan.json
    data/local/ulukau_nupepa/document_plan.jsonl

Usage::

    # Write source plan plus the built-in smoke-test seed document:
    python scripts/104_collect_ulukau_nupepa.py

    # Add explicit Nupepa document IDs:
    python scripts/104_collect_ulukau_nupepa.py --doc-id TPL18920521.2.1

    # Parse document IDs from a manually saved Nupepa search/browse HTML file:
    python scripts/104_collect_ulukau_nupepa.py --search-html /path/to/search.html

Exit codes: 0 success, 2 misuse/I/O error.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "data" / "local" / "ulukau_nupepa"

SOURCE_ID = "ulukau_nupepa"
SOURCE_NAME = "Ulukau — Hawaiian-language newspapers (nūpepa)"
FETCHER_SCRIPT = "scripts/204_fetch_ulukau_nupepa_raw.py"

NUPEPA_BASE_URL = "https://www.nupepa.org/gsdl2.7/cgi-bin/nupepa"
DOC_URL_TEMPLATE = NUPEPA_BASE_URL + "?a=d&d={doc_id}"
ULUKAU_HOME_URL = "https://ulukau.org/?l=en"
LICENSE_OBSERVED = (
    "unknown/not machine-verified; item-level rights and Ulukau/Nupepa terms "
    "must be reviewed before any non-private use"
)

# Publicly visible example URL shape from Nupepa search snippets and pages.
DEFAULT_SEED_DOC_IDS = ("TPL18920521.2.1",)

DOC_ID_RE = re.compile(r"(?:[?&]d=|\\bd=)([A-Za-z0-9_.-]+)")


def _utcnow_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_doc_id_file(path: Path) -> list[str]:
    ids: list[str] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            ids.append(stripped.split()[0])
    return ids


def _doc_ids_from_search_html(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return [m.group(1) for m in DOC_ID_RE.finditer(text)]


def _dedupe_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        value = value.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _document_url(doc_id: str) -> str:
    return DOC_URL_TEMPLATE.format(doc_id=doc_id)


def build_collect_plan(doc_ids: list[str], document_plan_path: Path) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "generated_by": "scripts/104_collect_ulukau_nupepa.py (frank)",
        "generated_at_utc": _utcnow_iso(),
        "source_id": SOURCE_ID,
        "source_name": SOURCE_NAME,
        "fetch_shape": "greenstone-document-html",
        "fetcher_script": FETCHER_SCRIPT,
        "rights_status_hint": "rights_gated_prototype_only",
        "license_observed": LICENSE_OBSERVED,
        "tos_or_license_url": ULUKAU_HOME_URL,
        "document_plan_path": str(document_plan_path.relative_to(REPO_ROOT)),
        "planning_volume": {
            "planned_document_count": len(doc_ids),
            "raw_token_count": None,
            "notes": (
                "100-phase planning records document candidates only. Actual "
                "raw whitespace token counts are measured by 204 after OCR/text "
                "bytes are fetched or ingested."
            ),
        },
        "access_status": {
            "public_page_pattern": DOC_URL_TEMPLATE,
            "observed_blocker": "cloudflare_challenge_for_non_browser_requests",
            "blocker_policy": (
                "Do not bypass anti-bot/challenge pages. Use a legitimate bulk "
                "export/API, permissioned access, or local manual exports."
            ),
        },
        "quality_status": {
            "content_kind": "OCR-derived newspaper text",
            "expected_noise": "high",
            "required_downstream_filters": [
                "boilerplate removal",
                "paragraph-level Hawaiian language ID",
                "OCR quality sampling",
                "manual review before bulk training",
            ],
        },
        "storage_policy": {
            "raw_root": f"data/raw/{SOURCE_ID}/",
            "git_ignored": True,
            "rationale": "Raw OCR/HTML payloads stay local and are never committed.",
        },
        "downstream_contract": {
            "fetch_jsonl_path": f"data/raw/{SOURCE_ID}/fetch.jsonl",
            "schema_owner": f"{FETCHER_SCRIPT}:ProvenanceRecord",
            "current_stage1_status": (
                "204 writes raw HTML and extracted text provenance. 301 still "
                "needs a Nupepa-specific cleaner before this source should be "
                "packed for training."
            ),
        },
        "blockers": [
            "No documented public bulk OCR endpoint has been wired into this adapter.",
            "Public Nupepa document pages may return Cloudflare 403/challenge to scripted fetches.",
            "Rights and ToS are not machine-cleared; keep all outputs private/prototype-only.",
        ],
        "issue": "https://github.com/yashasg/ideal-spoon/issues/1",
    }


def build_document_rows(doc_ids: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for doc_id in doc_ids:
        rows.append(
            {
                "schema_version": "1.0.0",
                "source_id": SOURCE_ID,
                "doc_id": doc_id,
                "source_url": _document_url(doc_id),
                "api_url": None,
                "rights_status_hint": "rights_gated_prototype_only",
                "license_observed": LICENSE_OBSERVED,
                "tos_or_license_url": ULUKAU_HOME_URL,
                "content_kind": "greenstone-document-html-with-ocr-text-if-present",
                "prototype_only": True,
                "release_eligible": False,
                "notes": (
                    "Fetch candidate only. 204 must detect challenge pages and "
                    "must not claim OCR text unless text bytes are actually present."
                ),
            }
        )
    return rows


def write_outputs(
    out_dir: Path,
    collect_plan: dict[str, Any],
    document_rows: list[dict[str, Any]],
    *,
    dry_run: bool,
) -> tuple[Path, Path]:
    collect_path = out_dir / "collect_plan.json"
    document_path = out_dir / "document_plan.jsonl"

    if dry_run:
        print(f"[dry-run] would write {collect_path}")
        print(f"[dry-run] would write {document_path} ({len(document_rows)} rows)")
        return collect_path, document_path

    out_dir.mkdir(parents=True, exist_ok=True)
    with collect_path.open("w", encoding="utf-8") as f:
        json.dump(collect_plan, f, indent=2, ensure_ascii=False)
        f.write("\n")
    with document_path.open("w", encoding="utf-8") as f:
        for row in document_rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    readme = out_dir / "README.txt"
    if not readme.exists():
        readme.write_text(
            "This directory is gitignored. It holds the Ulukau/Nupepa\n"
            "collection plan and document_plan.jsonl consumed by\n"
            "scripts/204_fetch_ulukau_nupepa_raw.py.\n"
            "Do not commit any file under data/.\n",
            encoding="utf-8",
        )
    return collect_path, document_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Write the Ulukau/Nupepa 100-phase collection plan."
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Output directory (default: {OUTPUT_DIR.relative_to(REPO_ROOT)}).",
    )
    parser.add_argument(
        "--doc-id",
        action="append",
        default=[],
        help="Nupepa document ID to include (repeatable), e.g. TPL18920521.2.1.",
    )
    parser.add_argument(
        "--doc-id-file",
        type=Path,
        action="append",
        default=[],
        help="UTF-8 text file with one Nupepa document ID per line.",
    )
    parser.add_argument(
        "--search-html",
        type=Path,
        action="append",
        default=[],
        help=(
            "Manually saved Nupepa search/browse HTML file to scan for "
            "'?a=d&d=<doc_id>' links. Does not fetch the site."
        ),
    )
    parser.add_argument(
        "--no-seed-sample",
        action="store_true",
        help="Do not include the built-in one-document smoke-test seed.",
    )
    parser.add_argument(
        "--print",
        action="store_true",
        dest="do_print",
        help="Pretty-print the source-level plan after writing.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print output paths and counts without writing files.",
    )
    args = parser.parse_args(argv)

    try:
        doc_ids: list[str] = []
        if not args.no_seed_sample:
            doc_ids.extend(DEFAULT_SEED_DOC_IDS)
        doc_ids.extend(args.doc_id)
        for path in args.doc_id_file:
            doc_ids.extend(_read_doc_id_file(path))
        for path in args.search_html:
            doc_ids.extend(_doc_ids_from_search_html(path))
        doc_ids = _dedupe_preserve_order(doc_ids)

        document_plan_path = args.out / "document_plan.jsonl"
        collect_plan = build_collect_plan(doc_ids, document_plan_path)
        rows = build_document_rows(doc_ids)
        collect_path, document_path = write_outputs(
            args.out,
            collect_plan,
            rows,
            dry_run=args.dry_run,
        )
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print("ideal-spoon Ulukau/Nupepa collection plan")
    print(f"  source              : {SOURCE_ID}")
    print(f"  planned documents   : {len(doc_ids)}")
    print(f"  collect_plan        : {collect_path}")
    print(f"  document_plan       : {document_path}")
    print("  corpus text in plan : no")
    print("  release eligible    : no (prototype-only, rights-gated)")
    if doc_ids:
        print("  first doc URL       : " + _document_url(doc_ids[0]))
    if args.do_print:
        print()
        print(json.dumps(collect_plan, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
