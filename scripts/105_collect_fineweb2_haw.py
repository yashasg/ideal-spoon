#!/usr/bin/env python3
"""FineWeb-2 ``haw_Latn`` source-specific collection plan (Frank).

100-phase planner for the Hawaiian-language slice of HuggingFaceFW/fineweb-2
(`haw_Latn` config). Writes a small, deterministic JSON plan that
``scripts/205_fetch_fineweb2_haw_raw.py`` consumes. This script does **not**
download corpus text; it records the dataset coordinates, verified row counts,
parquet/rows-API URLs, license posture, and ingest caveats.

Verified facts (frozen via direct HF probe; see Frank's history.md
2026-04-29 FineWeb-2 re-verification):

* Dataset id        : ``HuggingFaceFW/fineweb-2``
* Config            : ``haw_Latn``
* Gated/private     : both ``false`` — anonymous access works
* License (wrapper) : ``odc-by`` (per HF dataset card; underlying CommonCrawl
                      URLs carry their own third-party rights — Linus owes a
                      per-URL allow-list ruling before any non-private use)
* Splits / rows     : ``train`` 95,507 rows · ``test`` 887 rows  (``partial:false``)
* Per-row schema    : ``text, id, dump, url, date, file_path, language,
                      language_score, language_script, top_langs``
* Bulk shape        : 2 parquet files (1 per split) under the
                      ``refs/convert/parquet`` auto-conversion ref
* Lightweight shape : datasets-server ``/rows`` JSON API (paginated)

Known caveat: rows classified as Hawaiian by FineWeb-2's LID can still contain
English boilerplate / nav / ads (e.g. ``staradvertiser.com`` Kauakūkalahale
columns). The 200-phase fetcher preserves raw text + provenance only; final
LID re-gating, dedup, and cleanup are downstream concerns (301 / Linus).

Output (gitignored)::

    data/local/fineweb2_haw/collect_plan.json

Usage::

    python scripts/105_collect_fineweb2_haw.py            # write plan
    python scripts/105_collect_fineweb2_haw.py --print    # also pretty-print
    python scripts/105_collect_fineweb2_haw.py --dry-run  # no file writes

Exit codes: 0 success, 2 I/O / misuse error.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "data" / "local" / "fineweb2_haw"

SOURCE_ID = "fineweb2_haw"
SOURCE_NAME = "FineWeb-2 — Hawaiian (`haw_Latn`)"
FETCHER_SCRIPT = "scripts/205_fetch_fineweb2_haw_raw.py"

HF_DATASET_ID = "HuggingFaceFW/fineweb-2"
HF_CONFIG = "haw_Latn"

DATASET_HOMEPAGE = f"https://huggingface.co/datasets/{HF_DATASET_ID}"
LICENSE_TAG = "odc-by"
LICENSE_OBSERVED = (
    "odc-by (HF dataset wrapper). Underlying texts come from CommonCrawl WET "
    "and carry independent third-party rights per source URL; do not assume "
    "the wrapper licence covers reuse of source-site content."
)
TOS_OR_LICENSE_URL = "https://opendatacommons.org/licenses/by/1-0/"

# Verified row counts — frozen here so 205 can sanity-check what it observes
# against what 105 expected. Update only if HF re-verification shows a real
# upstream change (e.g. a new dataset revision).
EXPECTED_ROWS: dict[str, int] = {
    "train": 95_507,
    "test": 887,
}

PER_ROW_FIELDS: tuple[str, ...] = (
    "text",
    "id",
    "dump",
    "url",
    "date",
    "file_path",
    "language",
    "language_score",
    "language_script",
    "top_langs",
)
TEXT_FIELD = "text"

# HF parquet auto-conversion endpoint. Stable, ungated, single file per split.
# The ``refs%2Fconvert%2Fparquet`` ref is HF's canonical converted-parquet ref;
# do not substitute the user-facing ``main`` ref — that path layout differs.
PARQUET_URL_TEMPLATE = (
    "https://huggingface.co/datasets/"
    f"{HF_DATASET_ID}"
    "/resolve/refs%2Fconvert%2Fparquet/"
    f"{HF_CONFIG}"
    "/{split}/0000.parquet"
)

# datasets-server paginated rows API. Stdlib-friendly path used by 205 by
# default so the prototype does not require pyarrow / huggingface_hub yet.
ROWS_API_URL_TEMPLATE = (
    "https://datasets-server.huggingface.co/rows"
    f"?dataset={HF_DATASET_ID.replace('/', '%2F')}"
    f"&config={HF_CONFIG}"
    "&split={split}&offset={offset}&length={length}"
)


def _utcnow_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parquet_url(split: str) -> str:
    return PARQUET_URL_TEMPLATE.format(split=split)


def build_plan() -> dict[str, Any]:
    splits = []
    for split, n in EXPECTED_ROWS.items():
        splits.append(
            {
                "split": split,
                "expected_row_count": n,
                "parquet_url": _parquet_url(split),
                "rows_api_url_template": ROWS_API_URL_TEMPLATE.format(
                    split=split, offset=0, length=100
                ),
                "expected_parquet_files": 1,
                "notes": (
                    "Single parquet shard per split under HF's "
                    "refs/convert/parquet auto-conversion ref."
                ),
            }
        )

    return {
        "schema_version": "1.0.0",
        "generated_by": "scripts/105_collect_fineweb2_haw.py (frank)",
        "generated_at_utc": _utcnow_iso(),
        "source_id": SOURCE_ID,
        "source_name": SOURCE_NAME,
        "fetch_shape": "huggingface-parquet-or-rows-api",
        "fetcher_script": FETCHER_SCRIPT,
        "dataset": {
            "hf_dataset_id": HF_DATASET_ID,
            "hf_config": HF_CONFIG,
            "homepage": DATASET_HOMEPAGE,
            "gated": False,
            "private": False,
            "verified_via": (
                "HF datasets-server /rows + /api/datasets metadata "
                "(see .squad/agents/frank/history.md, 2026-04-29 entry)"
            ),
        },
        "rights_status_hint": "open_license_candidate_pending_per_url_review",
        "license_tag": LICENSE_TAG,
        "license_observed": LICENSE_OBSERVED,
        "tos_or_license_url": TOS_OR_LICENSE_URL,
        "splits": splits,
        "per_row_schema": {
            "fields": list(PER_ROW_FIELDS),
            "text_field": TEXT_FIELD,
            "notes": (
                "Provenance (`url`, `dump`, `date`, `file_path`) is in-row; "
                "preserve verbatim on the 205 raw record."
            ),
        },
        "planning_volume": {
            "planned_row_count_total": sum(EXPECTED_ROWS.values()),
            "planned_row_count_train": EXPECTED_ROWS["train"],
            "planned_row_count_test": EXPECTED_ROWS["test"],
            "raw_token_count": None,
            "notes": (
                "100-phase planning records dataset coordinates only. Actual "
                "raw whitespace token counts are measured by 205 from "
                "fetched row text, not estimated here."
            ),
        },
        "quality_status": {
            "content_kind": "CommonCrawl WET, LID-classified Hawaiian",
            "expected_noise": "medium-high",
            "known_caveats": [
                "English boilerplate/nav/ads can appear inside Hawaiian-classified rows.",
                "FineWeb-2 applies LID + minhash; no toxicity/quality filter at this tier.",
                "Wrapper licence (odc-by) does not pass through to underlying source-site rights.",
            ],
            "required_downstream_filters": [
                "paragraph-level Hawaiian language ID",
                "ʻokina/kahakō density gate",
                "MinHash dedup against hawwiki / hawwikisource / Ulukau",
                "per-source-URL rights review (Linus)",
            ],
        },
        "storage_policy": {
            "raw_root": f"data/raw/{SOURCE_ID}/",
            "git_ignored": True,
            "rationale": (
                "docs/data-pipeline.md §80 / .gitignore /data/. Raw bytes "
                "and per-row JSONL never committed."
            ),
        },
        "downstream_contract": {
            "fetch_jsonl_path": f"data/raw/{SOURCE_ID}/fetch.jsonl",
            "schema_owner": f"{FETCHER_SCRIPT}:ProvenanceRecord",
            "current_stage1_status": (
                "205 writes raw row text + per-row provenance. Stage-1 "
                "cleanup (LID re-gate, dedup, register tagging) lives in 301."
            ),
        },
        "fetcher_hints": {
            "default_path": "datasets-server-rows-api",
            "stdlib_only_path": True,
            "optional_parquet_path": {
                "enabled_by_flag": "--use-parquet",
                "requires": ["pyarrow"],
                "rationale": (
                    "Bulk pull of 95,507 train rows is more efficient via the "
                    "single parquet shard. pyarrow is not yet in "
                    "requirements.txt; gating behind a flag keeps the "
                    "default path stdlib-only pending Linus's dep call."
                ),
            },
            "rows_api_max_length": 100,
            "polite_rate_limit_seconds_default": 1.0,
        },
        "blockers": [],
        "issue": "https://github.com/yashasg/ideal-spoon/issues/1",
    }


def write_plan(plan: dict[str, Any], out_dir: Path, *, dry_run: bool) -> Path:
    out_path = out_dir / "collect_plan.json"
    if dry_run:
        print(f"[dry-run] would write {out_path}")
        return out_path
    out_dir.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)
        f.write("\n")
    readme = out_dir / "README.txt"
    if not readme.exists():
        readme.write_text(
            "This directory is gitignored. It holds the FineWeb-2 haw_Latn\n"
            "collection plan (collect_plan.json) consumed by\n"
            "scripts/205_fetch_fineweb2_haw_raw.py.\n"
            "Do not commit any file under data/.\n",
            encoding="utf-8",
        )
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the FineWeb-2 haw_Latn 100-phase collection plan.")
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
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be written without touching disk.",
    )
    args = parser.parse_args(argv)

    plan = build_plan()
    try:
        out_path = write_plan(plan, args.out, dry_run=args.dry_run)
    except OSError as e:
        print(f"error: failed to write plan: {e!r}", file=sys.stderr)
        return 2

    print("ideal-spoon FineWeb-2 haw_Latn collection plan")
    print(f"  source              : {SOURCE_ID}")
    print(f"  hf_dataset          : {HF_DATASET_ID} (config={HF_CONFIG})")
    print(f"  fetch_shape         : {plan['fetch_shape']}")
    print(f"  license_tag         : {LICENSE_TAG}")
    print(
        "  expected rows       : "
        f"train={EXPECTED_ROWS['train']:,} test={EXPECTED_ROWS['test']:,}"
    )
    print(f"  raw_token_count     : null (measured by 205, not estimated)")
    print(f"  collect_plan        : {out_path}")
    print(f"  fetcher_script      : {FETCHER_SCRIPT}")
    if args.print_plan:
        print()
        print(json.dumps(plan, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
