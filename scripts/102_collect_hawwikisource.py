#!/usr/bin/env python3
"""Hawaiian Wikisource (`hawwikisource`) source-specific collection plan (Frank).

Replaces the broad ``101_collect_rightslight.py`` planner for Hawaiian
Wikisource. Hawaiian Wikisource has no single Wikimedia dump or dedicated
``haw.wikisource.org`` wiki database in the rights-light path; Hawaiian
pages live on multilingual Wikisource and are grouped by
``Category:ʻŌlelo Hawaiʻi``. The corpus is enumerated from that category
and pulled page-by-page through the MediaWiki API. So the collection plan
for this source is not a list of dump URLs — it is a **per-page fetch
plan** that ``scripts/202_fetch_hawwikisource_raw.py`` consumes.

This script writes two artefacts under ``data/local/hawwikisource/``
(gitignored):

* ``collect_plan.json``  — source-level metadata (rights, ToS, API
  endpoint, fetcher script, token estimates). Always written. No
  network access required.
* ``page_plan.jsonl``    — one JSON object per page that 202 should
  fetch. Fields per row: ``ns``, ``page_id``, ``title``, ``source_url``
  (canonical wiki page URL), ``api_url`` (the MediaWiki revisions API
  URL 202 will GET), ``rights_status_hint``, ``license_observed``,
  ``tos_or_license_url``. Written only when ``--enumerate`` is passed,
  which uses the small ``list=categorymembers`` MediaWiki API
  (metadata-only, no per-page wikitext) to populate it.

Default behaviour is metadata-safe: no ``--enumerate`` means no network
calls; just the source-level plan and an empty/header ``page_plan.jsonl``
placeholder so downstream consumers see a deterministic path.

The page-plan is **only** a list of pages to fetch — it never contains
corpus text. 202 reads each row, GETs the per-page wikitext via the
MediaWiki API, and writes the raw JSON envelope to
``data/raw/hawwikisource/<YYYYMMDD>/<sha>.json``.

Namespace allow-list mirrors 202: main namespace (0) by default;
``--namespaces`` accepts only 0/104/106 (Page/Index). Talk/User/Special
namespaces are rejected at parse time.

Usage::

    # Plan only — no network, writes collect_plan.json + empty page_plan.jsonl:
    python scripts/102_collect_hawwikisource.py

    # Enumerate up to 50 main-namespace pages via the categorymembers API:
    python scripts/102_collect_hawwikisource.py --enumerate --limit 50

    # Dry-run enumeration: prints the URLs it would call, writes nothing.
    python scripts/102_collect_hawwikisource.py --enumerate --dry-run --limit 50

Exit codes: 0 success, 2 misuse, 3 fetch failure (network, short read).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "data" / "local" / "hawwikisource"

SOURCE_ID = "hawwikisource"
SOURCE_NAME = "Hawaiian Wikisource"
WIKIMEDIA_TOS = "https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use"
WIKIMEDIA_LICENSE = "CC BY-SA 4.0 wrapper over PD source texts (per-revision)"
API_ENDPOINT = "https://wikisource.org/w/api.php"
WIKI_PAGE_URL_TEMPLATE = "https://wikisource.org/wiki/{title}"
HAWAIIAN_CATEGORY_TITLE = "Category:ʻŌlelo Hawaiʻi"

DEFAULT_NAMESPACES = (0,)
ALLOWED_NAMESPACES = {0, 104, 106}

MAX_TOTAL_PAGES = 5000
MAX_BATCH = 500

USER_AGENT = (
    "ideal-spoon/0.1.0 (frank hawwikisource collector; "
    "contact via github.com/yashasg/ideal-spoon issue #1)"
)


def _utcnow_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sleep_backoff(attempt: int, base: float = 1.5, cap: float = 30.0) -> None:
    delay = min(cap, base * (2 ** (attempt - 1))) + random.uniform(0, 0.5)
    time.sleep(delay)


class FetchError(RuntimeError):
    pass


def _http_get(url: str, *, timeout: float = 60.0, max_attempts: int = 4) -> bytes:
    last_exc: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json, */*;q=0.5",
                "Api-User-Agent": USER_AGENT,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = int(resp.status)
                declared_len_hdr = resp.headers.get("Content-Length")
                declared_len = int(declared_len_hdr) if declared_len_hdr else None
                body = resp.read()
            if status >= 400:
                raise FetchError(f"HTTP {status} for {url}")
            if declared_len is not None and len(body) != declared_len:
                raise FetchError(
                    f"short read for {url}: got {len(body)} bytes, "
                    f"declared {declared_len}"
                )
            return body
        except (urllib.error.URLError, TimeoutError, FetchError) as e:
            last_exc = e
            transient = isinstance(e, (urllib.error.URLError, TimeoutError)) or (
                isinstance(e, FetchError) and "short read" in str(e)
            )
            if attempt < max_attempts and transient:
                _sleep_backoff(attempt)
                continue
            raise FetchError(f"GET failed after {attempt} attempt(s): {url}: {e!r}") from e
    raise FetchError(f"GET failed: {url}: {last_exc!r}")


def _categorymembers_url(*, ns: int, cmlimit: int, cmcontinue: str | None) -> str:
    params: dict[str, Any] = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": HAWAIIAN_CATEGORY_TITLE,
        "cmnamespace": ns,
        "cmlimit": cmlimit,
        "format": "json",
        "formatversion": 2,
    }
    if cmcontinue:
        params["cmcontinue"] = cmcontinue
    return f"{API_ENDPOINT}?{urllib.parse.urlencode(params)}"


def _page_revisions_url(*, page_id: int) -> str:
    params: dict[str, Any] = {
        "action": "query",
        "prop": "revisions",
        "pageids": page_id,
        "rvprop": "ids|timestamp|content|flags",
        "rvslots": "main",
        "format": "json",
        "formatversion": 2,
    }
    return f"{API_ENDPOINT}?{urllib.parse.urlencode(params)}"


def _wiki_page_url(title: str) -> str:
    return WIKI_PAGE_URL_TEMPLATE.format(title=urllib.parse.quote(title.replace(" ", "_")))


def _parse_namespaces(arg: str) -> tuple[int, ...]:
    out: list[int] = []
    for tok in arg.split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            ns = int(tok)
        except ValueError as e:
            raise SystemExit(f"error: --namespaces token {tok!r} is not numeric") from e
        if ns not in ALLOWED_NAMESPACES:
            raise SystemExit(
                f"error: namespace {ns} not on the allow-list. "
                f"Allowed: {sorted(ALLOWED_NAMESPACES)} (main, Page, Index)."
            )
        out.append(ns)
    return tuple(out) if out else DEFAULT_NAMESPACES


def build_source_plan(*, namespaces: tuple[int, ...], limit: int, batch_size: int) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "generated_by": "scripts/102_collect_hawwikisource.py (frank)",
        "generated_at_utc": _utcnow_iso(),
        "source_id": SOURCE_ID,
        "source_name": SOURCE_NAME,
        "fetch_shape": "mediawiki-api-pagetext",
        "fetcher_script": "scripts/202_fetch_hawwikisource_raw.py",
        "rights_status_hint": "open_license_candidate",
        "license_observed": WIKIMEDIA_LICENSE,
        "tos_or_license_url": WIKIMEDIA_TOS,
        "api_endpoint": API_ENDPOINT,
        "wiki_page_url_template": WIKI_PAGE_URL_TEMPLATE,
        "category_title": HAWAIIAN_CATEGORY_TITLE,
        "default_namespaces": list(namespaces),
        "namespace_allowlist": sorted(ALLOWED_NAMESPACES),
        "page_plan": {
            "path": "data/local/hawwikisource/page_plan.jsonl",
            "row_schema": {
                "ns": "int — MediaWiki namespace ID",
                "page_id": "int — stable MediaWiki page ID",
                "title": "str — wiki title (spaces, not underscores)",
                "source_url": "str — canonical wiki page URL",
                "api_url": "str — MediaWiki revisions API URL 202 will GET",
                "rights_status_hint": "str — inherits source-level posture",
                "license_observed": "str — inherits source-level license",
                "tos_or_license_url": "str — inherits source-level ToS",
            },
            "consumed_by": "scripts/202_fetch_hawwikisource_raw.py --page-plan",
            "limit_requested": limit,
            "batch_size_requested": batch_size,
        },
        "token_estimate_haw": {
            "conservative": 500_000,
            "base": 1_000_000,
            "upside": 1_500_000,
            "rationale": (
                ".squad/agents/frank/history.md (2026-04-29 token-yield pass): "
                "Hawaiian Wikisource is the second-largest right-clearable "
                "Hawaiian text source after hawwiki."
            ),
        },
        "blockers": [
            "Per-page wikitext bulk pulls still need a Linus-side extracted-text "
            "contract (NFC, ʻokina canonicalization) before any large run.",
        ],
        "storage_policy": {
            "raw_root": "data/raw/hawwikisource/",
            "git_ignored": True,
            "rationale": "docs/data-pipeline.md §80; raw bytes never committed.",
        },
        "downstream_contract": {
            "fetch_jsonl_path": "data/raw/hawwikisource/fetch.jsonl",
            "schema_owner": "scripts/202_fetch_hawwikisource_raw.py:ProvenanceRecord",
        },
        "issue": "https://github.com/yashasg/ideal-spoon/issues/1",
    }


def enumerate_pages(
    *,
    namespaces: tuple[int, ...],
    limit: int,
    batch_size: int,
    rate_limit_seconds: float,
    dry_run: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ns in namespaces:
        cmcontinue: str | None = None
        while len(rows) < limit:
            remaining = limit - len(rows)
            this_batch = max(1, min(batch_size, remaining))
            url = _categorymembers_url(ns=ns, cmlimit=this_batch, cmcontinue=cmcontinue)
            if dry_run:
                print(f"  [dry-run] would GET categorymembers: {url}")
                break
            body = _http_get(url)
            try:
                payload = json.loads(body.decode("utf-8"))
            except Exception as e:
                raise FetchError(f"categorymembers payload not JSON for {url}: {e!r}") from e
            batch_pages = payload.get("query", {}).get("categorymembers", []) or []
            for p in batch_pages:
                if len(rows) >= limit:
                    break
                title = p["title"]
                page_id = int(p["pageid"])
                rows.append({
                    "ns": ns,
                    "page_id": page_id,
                    "title": title,
                    "source_url": _wiki_page_url(title),
                    "api_url": _page_revisions_url(page_id=page_id),
                    "rights_status_hint": "open_license_candidate",
                    "license_observed": WIKIMEDIA_LICENSE,
                    "tos_or_license_url": WIKIMEDIA_TOS,
                })
            print(f"  enumerated ns={ns} batch={len(batch_pages)} total={len(rows)}")
            cont = payload.get("continue", {})
            cmcontinue = cont.get("cmcontinue")
            if not cmcontinue:
                break
            time.sleep(rate_limit_seconds)
    return rows


def write_outputs(
    plan: dict[str, Any],
    pages: list[dict[str, Any]] | None,
    out_dir: Path,
    *,
    enumerate_requested: bool,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    plan_path = out_dir / "collect_plan.json"
    with plan_path.open("w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)
        f.write("\n")

    page_plan_path = out_dir / "page_plan.jsonl"
    if pages is not None:
        with page_plan_path.open("w", encoding="utf-8") as f:
            for row in pages:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    elif not page_plan_path.exists():
        # Touch a header-comment-free empty file so 202 has a deterministic
        # path even before --enumerate has been run.
        page_plan_path.touch()
    elif enumerate_requested:
        # --enumerate ran in dry-run; do not clobber an existing real plan.
        pass

    readme = out_dir / "README.txt"
    if not readme.exists():
        readme.write_text(
            "This directory is gitignored. It holds the hawwikisource\n"
            "collection plan (collect_plan.json) and the per-page fetch plan\n"
            "(page_plan.jsonl) consumed by\n"
            "scripts/202_fetch_hawwikisource_raw.py --page-plan.\n"
            "Do not commit any file under data/.\n",
            encoding="utf-8",
        )
    return plan_path, page_plan_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Hawaiian Wikisource collection plan (Frank).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Output directory (default: {OUTPUT_DIR.relative_to(REPO_ROOT)}).",
    )
    parser.add_argument(
        "--namespaces",
        default="0",
        help=f"Comma-separated namespace IDs. Default: 0. Allowed: {sorted(ALLOWED_NAMESPACES)}.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help=f"Max pages to enumerate. Default: 50. Hard cap: {MAX_TOTAL_PAGES}.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help=f"cmlimit per categorymembers request (max {MAX_BATCH}). Default: 50.",
    )
    parser.add_argument(
        "--rate-limit-seconds",
        type=float,
        default=1.0,
        help="Sleep between paginated categorymembers calls. Default: 1.0s.",
    )
    parser.add_argument(
        "--enumerate",
        action="store_true",
        help="Hit the MediaWiki list=categorymembers API to populate page_plan.jsonl. "
        "Without this flag the script writes only the source-level plan.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="With --enumerate, print URLs that would be called and write no pages.",
    )
    args = parser.parse_args(argv)

    if args.limit < 1 or args.limit > MAX_TOTAL_PAGES:
        raise SystemExit(f"error: --limit must be in [1, {MAX_TOTAL_PAGES}]")
    if args.batch_size < 1 or args.batch_size > MAX_BATCH:
        raise SystemExit(f"error: --batch-size must be in [1, {MAX_BATCH}]")
    if args.rate_limit_seconds < 0.0 or args.rate_limit_seconds > 60.0:
        raise SystemExit("error: --rate-limit-seconds must be in [0.0, 60.0]")

    namespaces = _parse_namespaces(args.namespaces)
    plan = build_source_plan(namespaces=namespaces, limit=args.limit, batch_size=args.batch_size)

    pages: list[dict[str, Any]] | None = None
    if args.enumerate:
        try:
            pages = enumerate_pages(
                namespaces=namespaces,
                limit=args.limit,
                batch_size=args.batch_size,
                rate_limit_seconds=args.rate_limit_seconds,
                dry_run=args.dry_run,
            )
        except FetchError as e:
            print(f"  FETCH ERROR during enumeration: {e}", file=sys.stderr)
            return 3
        if args.dry_run:
            pages = None  # do not write a real page_plan in dry-run mode
    plan_path, page_plan_path = write_outputs(
        plan, pages, args.out, enumerate_requested=args.enumerate
    )

    print(f"wrote hawwikisource collect plan: {plan_path.relative_to(REPO_ROOT)}")
    print(f"  fetcher_script : {plan['fetcher_script']}")
    print(f"  fetch_shape    : {plan['fetch_shape']}")
    if pages is not None:
        print(
            f"  page_plan      : {page_plan_path.relative_to(REPO_ROOT)} "
            f"({len(pages)} page(s))"
        )
    else:
        if args.enumerate and args.dry_run:
            print("  page_plan      : skipped (dry-run)")
        else:
            print(
                f"  page_plan      : {page_plan_path.relative_to(REPO_ROOT)} "
                "(empty; pass --enumerate to populate)"
            )
    est = plan["token_estimate_haw"]
    print(
        "  token_est_haw  : "
        f"cons={est['conservative']:,} base={est['base']:,} upside={est['upside']:,}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
