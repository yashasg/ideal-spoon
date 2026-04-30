#!/usr/bin/env python3
"""Hawaiian Wikisource quality=4 (Validated) eval-candidate scan (Frank).

Metadata-first scan to find Validated (`Page:` namespace, quality_text ==
"Validated") records reachable from the Hawaiian main-namespace pages
already enumerated in ``data/local/hawwikisource/page_plan.jsonl``.

This is intentionally a one-off, *additive*, eval-candidate-only path:

* Does NOT touch ``data/raw/hawwikisource/`` (the existing W1/Stage 1
  hawwikisource ingest). Output goes under
  ``data/raw/hawwikisource_quality4_candidates/<YYYYMMDD>/`` (gitignored
  via the blanket ``/data/`` rule).
* Treats every found row as eval-candidate only — emits provenance and a
  manifest, never inserts into the W1 ledger.
* Two stages (both polite, MediaWiki API only):

    1. **Transclusion walk** — for each main-ns page in the existing
       page_plan, ask ``prop=templates&tlnamespace=104`` for the set of
       Page: subpages it transcludes. Page: titles are deduped across
       main pages.
    2. **Quality probe** — batch ``prop=proofread`` (50 ids/call) over
       the unique Page: titles. Records every page's quality and keeps
       only ``quality_text == "Validated"`` rows.

Optional content fetch (off by default):

    --fetch-content      For each Validated Page: id, GET
                         ``prop=revisions|proofread&rvprop=content``
                         (one batched call per 50 ids) and write the raw
                         wikitext to a per-page JSON envelope. Capped by
                         ``--max-content`` to keep prototype-safe.

Counts and a manifest are always written. Raw content is only written
when ``--fetch-content`` is passed and the validated count is under the
cap. No corpus text is ever printed to stdout.

Usage::

    python scripts/106_scan_hawwikisource_quality4.py                # metadata only
    python scripts/106_scan_hawwikisource_quality4.py --fetch-content
    python scripts/106_scan_hawwikisource_quality4.py --dry-run

Exit codes: 0 success (incl. zero-validated-rows reports), 2 misuse,
3 fetch failure.
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

REPO_ROOT = Path(__file__).resolve().parents[1]
PAGE_PLAN_PATH = REPO_ROOT / "data" / "local" / "hawwikisource" / "page_plan.jsonl"
OUT_ROOT = REPO_ROOT / "data" / "raw" / "hawwikisource_quality4_candidates"

API_ENDPOINT = "https://wikisource.org/w/api.php"

USER_AGENT = (
    "ideal-spoon/0.1.0 (frank hawwikisource quality4 eval-candidate scan; "
    "contact via github.com/yashasg/ideal-spoon issue #1)"
)

PROOFREAD_BATCH = 50
TEMPLATES_TLLIMIT = 500
DEFAULT_MAX_MAIN_PAGES = 200
DEFAULT_MAX_PAGE_NS = 5000
DEFAULT_MAX_CONTENT = 1000


def _utcnow_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today_compact() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d")


def _sleep_backoff(attempt: int, base: float = 1.5, cap: float = 30.0) -> None:
    delay = min(cap, base * (2 ** (attempt - 1))) + random.uniform(0, 0.5)
    time.sleep(delay)


class FetchError(RuntimeError):
    pass


def _http_get_json(url: str, *, timeout: float = 60.0, max_attempts: int = 6) -> dict[str, Any]:
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
                body = resp.read()
            if status >= 400:
                raise FetchError(f"HTTP {status} for {url}")
            return json.loads(body.decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_exc = e
            if e.code == 429 and attempt < max_attempts:
                retry_after = e.headers.get("Retry-After") if e.headers else None
                try:
                    wait = float(retry_after) if retry_after else 0.0
                except ValueError:
                    wait = 0.0
                wait = max(wait, min(60.0, 5.0 * (2 ** (attempt - 1))))
                print(f"  429 from API; sleeping {wait:.1f}s (attempt {attempt})", flush=True)
                time.sleep(wait + random.uniform(0, 0.5))
                continue
            if attempt < max_attempts and 500 <= e.code < 600:
                _sleep_backoff(attempt)
                continue
            raise FetchError(f"GET failed after {attempt} attempt(s): {url}: {e!r}") from e
        except (urllib.error.URLError, TimeoutError, FetchError, json.JSONDecodeError) as e:
            last_exc = e
            transient = not isinstance(e, json.JSONDecodeError)
            if attempt < max_attempts and transient:
                _sleep_backoff(attempt)
                continue
            raise FetchError(f"GET failed after {attempt} attempt(s): {url}: {e!r}") from e
    raise FetchError(f"GET failed: {url}: {last_exc!r}")


def _build_url(params: dict[str, Any]) -> str:
    return API_ENDPOINT + "?" + urllib.parse.urlencode(params, doseq=True)


def _templates_url(*, page_id: int, tlcontinue: str | None) -> str:
    params: dict[str, Any] = {
        "action": "query",
        "prop": "templates",
        "pageids": str(page_id),
        "tlnamespace": 104,
        "tllimit": TEMPLATES_TLLIMIT,
        "format": "json",
        "formatversion": 2,
    }
    if tlcontinue:
        params["tlcontinue"] = tlcontinue
    return _build_url(params)


def _proofread_batch_url(*, titles: list[str]) -> str:
    params: dict[str, Any] = {
        "action": "query",
        "prop": "proofread|info",
        "titles": "|".join(titles),
        "format": "json",
        "formatversion": 2,
    }
    return _build_url(params)


def _content_batch_url(*, page_ids: list[int]) -> str:
    params: dict[str, Any] = {
        "action": "query",
        "prop": "revisions|proofread|info",
        "pageids": "|".join(str(pid) for pid in page_ids),
        "rvprop": "ids|timestamp|content|flags",
        "rvslots": "main",
        "format": "json",
        "formatversion": 2,
    }
    return _build_url(params)


def _load_main_pages(limit: int) -> list[dict[str, Any]]:
    if not PAGE_PLAN_PATH.exists():
        raise FetchError(f"missing page_plan.jsonl at {PAGE_PLAN_PATH}")
    rows: list[dict[str, Any]] = []
    with PAGE_PLAN_PATH.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if int(row.get("ns", -1)) == 0:
                rows.append(row)
            if len(rows) >= limit:
                break
    return rows


def walk_transclusions(
    main_pages: list[dict[str, Any]],
    *,
    rate_limit_seconds: float,
    dry_run: bool,
    max_page_ns: int,
) -> tuple[dict[str, list[int]], list[dict[str, Any]]]:
    """Return (page_title -> [originating_main_page_ids], per_main_stats)."""
    page_titles: dict[str, list[int]] = {}
    per_main: list[dict[str, Any]] = []
    for i, row in enumerate(main_pages, 1):
        page_id = int(row["page_id"])
        title = row["title"]
        local_titles: set[str] = set()
        tlcontinue: str | None = None
        calls = 0
        while True:
            url = _templates_url(page_id=page_id, tlcontinue=tlcontinue)
            calls += 1
            if dry_run:
                print(f"  [dry-run] would GET {url}")
                break
            data = _http_get_json(url)
            pages = data.get("query", {}).get("pages") or []
            for p in pages:
                for tpl in (p.get("templates") or []):
                    if int(tpl.get("ns", -1)) == 104:
                        local_titles.add(tpl["title"])
            cont = data.get("continue", {}).get("tlcontinue")
            if not cont:
                break
            tlcontinue = cont
            time.sleep(rate_limit_seconds)
        for t in local_titles:
            page_titles.setdefault(t, []).append(page_id)
        per_main.append(
            {
                "main_page_id": page_id,
                "main_title": title,
                "transcluded_page_ns_count": len(local_titles),
                "api_calls": calls,
            }
        )
        if not dry_run:
            print(
                f"  [{i}/{len(main_pages)}] main_id={page_id} "
                f"title={title!r} transcluded_Page:={len(local_titles)} "
                f"unique_so_far={len(page_titles)}",
                flush=True,
            )
            if len(page_titles) >= max_page_ns:
                print(
                    f"  cap reached: unique Page: titles >= max_page_ns={max_page_ns}; "
                    f"stopping transclusion walk",
                    flush=True,
                )
                break
            time.sleep(rate_limit_seconds)
    return page_titles, per_main


def probe_quality(
    page_titles: list[str],
    *,
    rate_limit_seconds: float,
    dry_run: bool,
) -> list[dict[str, Any]]:
    """Return per-Page: dicts with quality, quality_text, page_id, rev_id."""
    results: list[dict[str, Any]] = []
    for start in range(0, len(page_titles), PROOFREAD_BATCH):
        batch = page_titles[start : start + PROOFREAD_BATCH]
        url = _proofread_batch_url(titles=batch)
        if dry_run:
            print(f"  [dry-run] would GET {url}")
            continue
        data = _http_get_json(url)
        for p in (data.get("query", {}).get("pages") or []):
            pr = p.get("proofread") or {}
            results.append(
                {
                    "title": p.get("title"),
                    "page_id": p.get("pageid"),
                    "ns": p.get("ns"),
                    "missing": bool(p.get("missing", False)),
                    "quality": pr.get("quality"),
                    "quality_text": pr.get("quality_text"),
                }
            )
        print(
            f"  proofread batch {start//PROOFREAD_BATCH + 1}: "
            f"queried={len(batch)} cumulative_results={len(results)}",
            flush=True,
        )
        time.sleep(rate_limit_seconds)
    return results


def fetch_content(
    page_ids: list[int],
    out_dir: Path,
    *,
    rate_limit_seconds: float,
    dry_run: bool,
) -> tuple[int, int, int]:
    """Return (records_written, total_chars, total_bytes)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    total_chars = 0
    total_bytes = 0
    for start in range(0, len(page_ids), PROOFREAD_BATCH):
        batch = page_ids[start : start + PROOFREAD_BATCH]
        url = _content_batch_url(page_ids=batch)
        if dry_run:
            print(f"  [dry-run] would GET {url}")
            continue
        data = _http_get_json(url)
        for p in (data.get("query", {}).get("pages") or []):
            pr = p.get("proofread") or {}
            revs = p.get("revisions") or []
            content = ""
            rev_id = None
            timestamp = None
            if revs:
                rev = revs[0]
                rev_id = rev.get("revid")
                timestamp = rev.get("timestamp")
                slot = (rev.get("slots") or {}).get("main") or {}
                content = slot.get("content") or rev.get("*") or ""
            envelope = {
                "fetched_at_utc": _utcnow_iso(),
                "source": "hawwikisource_quality4_candidates",
                "eval_candidate_only": True,
                "title": p.get("title"),
                "page_id": p.get("pageid"),
                "ns": p.get("ns"),
                "rev_id": rev_id,
                "rev_timestamp": timestamp,
                "proofread_quality": pr.get("quality"),
                "proofread_quality_text": pr.get("quality_text"),
                "source_url": (
                    f"https://wikisource.org/wiki/"
                    f"{urllib.parse.quote(p.get('title') or '', safe='')}"
                ),
                "api_url": url,
                "license_observed": "CC BY-SA 4.0 wrapper over PD source texts",
                "tos_or_license_url": "https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use",
                "content_wikitext": content,
                "content_chars": len(content),
                "content_bytes": len(content.encode("utf-8")),
            }
            pid = p.get("pageid")
            out_path = out_dir / f"page_{pid}.json"
            out_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")
            written += 1
            total_chars += envelope["content_chars"]
            total_bytes += envelope["content_bytes"]
        print(
            f"  content batch {start//PROOFREAD_BATCH + 1}: "
            f"wrote_so_far={written} chars_so_far={total_chars}",
            flush=True,
        )
        time.sleep(rate_limit_seconds)
    return written, total_chars, total_bytes


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-main-pages",
        type=int,
        default=DEFAULT_MAX_MAIN_PAGES,
        help=f"Cap on main-ns pages walked. Default: {DEFAULT_MAX_MAIN_PAGES}.",
    )
    parser.add_argument(
        "--max-page-ns",
        type=int,
        default=DEFAULT_MAX_PAGE_NS,
        help=f"Cap on unique Page: titles probed. Default: {DEFAULT_MAX_PAGE_NS}.",
    )
    parser.add_argument(
        "--max-content",
        type=int,
        default=DEFAULT_MAX_CONTENT,
        help=f"Cap on validated Page: rows whose wikitext is fetched. "
             f"Default: {DEFAULT_MAX_CONTENT}.",
    )
    parser.add_argument(
        "--rate-limit-seconds",
        type=float,
        default=0.6,
        help="Sleep between API calls. Default: 0.6.",
    )
    parser.add_argument(
        "--fetch-content",
        action="store_true",
        help="Also fetch wikitext for validated Page: rows (capped).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print URLs only; write nothing.",
    )
    args = parser.parse_args(argv)

    if args.rate_limit_seconds < 0.0 or args.rate_limit_seconds > 60.0:
        print("error: --rate-limit-seconds must be in [0.0, 60.0]", file=sys.stderr)
        return 2

    started_at = _utcnow_iso()
    print(f"frank/106 quality4 scan starting at {started_at}", flush=True)
    print(f"  endpoint        : {API_ENDPOINT}", flush=True)
    print(f"  user-agent      : {USER_AGENT}", flush=True)
    print(f"  page_plan       : {PAGE_PLAN_PATH}", flush=True)

    main_pages = _load_main_pages(args.max_main_pages)
    print(f"  main_ns pages loaded: {len(main_pages)} (cap={args.max_main_pages})", flush=True)

    print("step 1/3: transclusion walk (ns=0 -> ns=104)", flush=True)
    page_titles_map, per_main = walk_transclusions(
        main_pages,
        rate_limit_seconds=args.rate_limit_seconds,
        dry_run=args.dry_run,
        max_page_ns=args.max_page_ns,
    )
    unique_titles = sorted(page_titles_map.keys())
    print(f"  unique Page: titles discovered: {len(unique_titles)}", flush=True)

    print("step 2/3: prop=proofread quality probe", flush=True)
    quality_rows = probe_quality(
        unique_titles,
        rate_limit_seconds=args.rate_limit_seconds,
        dry_run=args.dry_run,
    )
    quality_hist: dict[str, int] = {}
    validated: list[dict[str, Any]] = []
    for r in quality_rows:
        key = str(r.get("quality_text"))
        quality_hist[key] = quality_hist.get(key, 0) + 1
        if r.get("quality") == 4 and r.get("quality_text") == "Validated":
            validated.append(r)
    print(f"  quality histogram: {quality_hist}", flush=True)
    print(f"  validated (q=4) Page: rows: {len(validated)}", flush=True)

    out_dir = OUT_ROOT / _today_compact()
    content_dir = out_dir / "content"
    written = 0
    total_chars = 0
    total_bytes = 0

    if args.fetch_content and not args.dry_run:
        print("step 3/3: fetching wikitext for validated Page: rows", flush=True)
        if len(validated) > args.max_content:
            print(
                f"  validated count {len(validated)} exceeds --max-content "
                f"{args.max_content}; stopping at metadata. Manifest will be "
                f"written without content.",
                flush=True,
            )
        else:
            ids = [int(v["page_id"]) for v in validated if v.get("page_id") is not None]
            written, total_chars, total_bytes = fetch_content(
                ids,
                content_dir,
                rate_limit_seconds=args.rate_limit_seconds,
                dry_run=False,
            )
    else:
        print("step 3/3: skipped (no --fetch-content or --dry-run)", flush=True)

    finished_at = _utcnow_iso()

    rough_token_estimate = total_chars // 4 if total_chars else 0

    manifest: dict[str, Any] = {
        "generated_by": "scripts/106_scan_hawwikisource_quality4.py (frank)",
        "started_at_utc": started_at,
        "finished_at_utc": finished_at,
        "endpoint": API_ENDPOINT,
        "user_agent": USER_AGENT,
        "method": (
            "transclusion-walk: for each main-ns page in page_plan.jsonl, "
            "GET prop=templates&tlnamespace=104; aggregate unique Page: "
            "titles; batch GET prop=proofread (titles=...) in 50/batch; "
            "filter quality_text=='Validated'."
        ),
        "non_replacement_policy": (
            "Output is eval-candidate only. Does NOT mutate "
            "data/raw/hawwikisource/fetch.jsonl, page_plan.jsonl, W1 TSVs, "
            "or any Stage 1 ledgers. Treat as new data per user directive."
        ),
        "params": {
            "max_main_pages": args.max_main_pages,
            "max_page_ns": args.max_page_ns,
            "max_content": args.max_content,
            "rate_limit_seconds": args.rate_limit_seconds,
            "fetch_content": bool(args.fetch_content),
            "dry_run": bool(args.dry_run),
        },
        "counts": {
            "main_ns_pages_inspected": len(main_pages),
            "unique_page_ns_titles_discovered": len(unique_titles),
            "page_ns_quality_rows_probed": len(quality_rows),
            "quality_histogram": quality_hist,
            "validated_q4_count": len(validated),
            "content_records_written": written,
            "total_content_chars": total_chars,
            "total_content_bytes": total_bytes,
            "rough_token_estimate_chars_div_4": rough_token_estimate,
        },
        "per_main_page_stats_path": "per_main_stats.jsonl",
        "validated_index_path": "validated_pages.jsonl",
        "content_dir": "content/",
        "eval_candidate_only": True,
    }

    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
        with (out_dir / "per_main_stats.jsonl").open("w", encoding="utf-8") as fh:
            for row in per_main:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        with (out_dir / "validated_pages.jsonl").open("w", encoding="utf-8") as fh:
            for row in validated:
                origins = page_titles_map.get(row.get("title"), [])
                row_with_origin = dict(row)
                row_with_origin["originating_main_page_ids"] = origins
                fh.write(json.dumps(row_with_origin, ensure_ascii=False) + "\n")
        with (out_dir / "all_quality_rows.jsonl").open("w", encoding="utf-8") as fh:
            for row in quality_rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        (out_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (out_dir / "README.txt").write_text(
            "Hawaiian Wikisource quality=4 (Validated) eval-candidate scan.\n"
            "Local-only artifact (gitignored under /data/).\n"
            "Eval-candidate only; does NOT replace existing W1/Stage 1 data.\n",
            encoding="utf-8",
        )
        print(f"manifest written: {out_dir / 'manifest.json'}", flush=True)

    print("DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
