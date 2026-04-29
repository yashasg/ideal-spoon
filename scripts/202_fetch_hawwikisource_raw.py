#!/usr/bin/env python3
"""Hawaiian Wikisource raw-data fetcher (Frank, sibling of 201).

Companion adapter to ``scripts/201_fetch_rightslight_raw.py``. That script
focuses on Wikimedia *dump-style* sources (``hawwiki``, ``hawwiktionary``)
where the corpus arrives as a single ``*-pages-articles.xml.bz2`` file
verified against a ``sha1sums`` manifest. Hawaiian Wikisource has no such
dump or dedicated ``haw.wikisource.org`` wiki database in the rights-light
allow-list path — instead we enumerate Hawaiian pages from
``Category:ʻŌlelo Hawaiʻi`` on multilingual Wikisource and (optionally)
pull per-page wikitext, one HTTP call per page, with polite rate limiting.

Splitting that flow into its own numbered script keeps the dump fetcher
small and avoids two very different fetch shapes sharing one allow-list.

Input plan (preferred)
----------------------
The recommended input is the per-page fetch plan emitted by
``scripts/102_collect_hawwikisource.py`` at
``data/local/hawwikisource/page_plan.jsonl``. Each line is a JSON
object with at least ``ns``, ``page_id``, and ``title`` (plus optional
``source_url``, ``api_url``, rights metadata). Pass ``--page-plan PATH``
to consume an alternate path. If the default path is empty or missing,
202 falls back to direct enumeration via the MediaWiki
``list=categorymembers`` API for backwards compatibility — this fallback
is convenient but the planned path is preferred so the 100/200 phases stay
decoupled.

Source
------
* ``hawwikisource`` — Hawaiian Wikisource pages on multilingual Wikisource
  (https://wikisource.org/wiki/Category:ʻŌlelo_Hawaiʻi). License posture:
  CC BY-SA 4.0 wrapper over (mostly) public-domain source texts. ToS:
  Wikimedia Foundation Terms of Use.

Safety posture
--------------
* **Dry-run by default.** Without ``--execute`` the script only prints
  the URLs it would call and (in metadata-only mode) may pull tiny
  ``list=categorymembers`` JSON responses to enumerate titles. Per-page
  wikitext is **never** fetched without ``--execute``.
* ``--metadata-only`` forces the title-enumeration path even with
  ``--execute`` — useful for CI smoke and for sizing the catalogue
  before any bulk pull.
* Namespace filter defaults to main namespace (``0``) only. Talk / User /
  File / MediaWiki / Template / Help / Category / Special / maintenance
  namespaces are excluded. Override with ``--namespaces`` (comma-separated
  numeric IDs) only after a per-namespace rights pass.
* Polite rate limiting between page fetches (default 1.0s, configurable
  via ``--rate-limit-seconds``). Title enumeration uses the same
  polite GET helper as 201.
* Raw bytes land under ``data/raw/hawwikisource/<YYYYMMDD>/<sha256>.<ext>``
  which is gitignored. One JSONL line per artefact appended to
  ``data/raw/hawwikisource/fetch.jsonl`` using the same
  ``ProvenanceRecord`` shape as 201 (source-level ledger; Linus's
  Stage-1 builder reads source-level ``fetch.jsonl``).
* ``--limit`` caps the total number of pages enumerated/fetched so a
  misconfigured run cannot accidentally pull the full corpus.

Stdlib only — no new requirements.

Usage
-----
::

    # Plan only — print what would be enumerated, fetch nothing:
    python scripts/202_fetch_hawwikisource_raw.py --dry-run

    # Title enumeration only (safe smoke; tiny JSON metadata):
    python scripts/202_fetch_hawwikisource_raw.py --metadata-only --limit 50

    # Consume the 102 page plan (preferred input):
    python scripts/102_collect_hawwikisource.py --enumerate --limit 50
    python scripts/202_fetch_hawwikisource_raw.py --execute  # reads page_plan.jsonl

    # Real per-page wikitext pull, capped and rate-limited:
    python scripts/202_fetch_hawwikisource_raw.py --execute --limit 25

Exit codes: 0 success, 2 misuse, 3 fetch failure (network, short read).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_ROOT = REPO_ROOT / "data" / "raw"
DEFAULT_PAGE_PLAN_PATH = REPO_ROOT / "data" / "local" / "hawwikisource" / "page_plan.jsonl"
SOURCE_ID = "hawwikisource"
SOURCE_NAME = "Hawaiian Wikisource"

FETCHER_TOOL = "urllib.request (stdlib); script=scripts/202_fetch_hawwikisource_raw.py"
FETCHER_VERSION = "0.1.0"
USER_AGENT = (
    f"ideal-spoon/{FETCHER_VERSION} (frank hawwikisource adapter; "
    "contact via github.com/yashasg/ideal-spoon issue #1)"
)
WIKIMEDIA_TOS = "https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use"
WIKIMEDIA_LICENSE = "CC BY-SA 4.0 wrapper over PD source texts (per-revision)"

API_ENDPOINT = "https://wikisource.org/w/api.php"
HAWAIIAN_CATEGORY_TITLE = "Category:ʻŌlelo Hawaiʻi"

# Namespaces we will allow by default. Main namespace only. Talk/User/
# Special/maintenance namespaces are explicitly NOT in this list and
# would have to be opted in via --namespaces with a per-ns rights pass.
DEFAULT_NAMESPACES = (0,)

# Hard caps so a misconfigured run cannot run away.
MAX_TOTAL_PAGES = 5000
MAX_BATCH = 500  # MediaWiki cmlimit hard cap for non-bot users is 500.


# ---------------------------------------------------------------------------
# Provenance schema (must match scripts/201_fetch_rightslight_raw.py)
# ---------------------------------------------------------------------------


@dataclass
class ProvenanceRecord:
    """One JSONL row per fetched artefact. Schema-compatible with 201."""

    source_id: str
    source_url: str
    fetch_timestamp_utc: str
    http_status: int
    content_type: str
    content_length: int
    raw_sha256: str
    raw_storage_path: str
    tos_or_license_url: str
    license_observed: str
    fetcher_user_agent: str
    fetcher_tool_and_version: str
    source_specific_ids: dict[str, Any] = field(default_factory=dict)
    notes: str = ""


# ---------------------------------------------------------------------------
# HTTP with polite retry/backoff (stdlib only)
# ---------------------------------------------------------------------------


class FetchError(RuntimeError):
    pass


def _utcnow_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today_compact_utc() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d")


def _sleep_backoff(attempt: int, base: float = 1.5, cap: float = 30.0) -> None:
    delay = min(cap, base * (2 ** (attempt - 1))) + random.uniform(0, 0.5)
    time.sleep(delay)


def _http_get(
    url: str,
    *,
    timeout: float = 60.0,
    max_attempts: int = 4,
) -> tuple[int, str, bytes]:
    """GET with polite retry. Returns (status, content_type, body)."""
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
                ctype = resp.headers.get("Content-Type", "")
                declared_len_hdr = resp.headers.get("Content-Length")
                declared_len = int(declared_len_hdr) if declared_len_hdr else None
                body = resp.read()
            if status >= 400:
                raise FetchError(f"HTTP {status} for {url}")
            if declared_len is not None and len(body) != declared_len:
                raise FetchError(
                    f"short read for {url}: got {len(body)} bytes, "
                    f"Content-Length declared {declared_len}"
                )
            return status, ctype, body
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


# ---------------------------------------------------------------------------
# Storage + provenance
# ---------------------------------------------------------------------------


def _source_dirs() -> tuple[Path, Path]:
    base = RAW_ROOT / SOURCE_ID
    fetch_dir = base / _today_compact_utc()
    fetch_dir.mkdir(parents=True, exist_ok=True)
    base.mkdir(parents=True, exist_ok=True)
    return base, fetch_dir


def _write_readme(base: Path) -> None:
    readme = base / "README.txt"
    if not readme.exists():
        readme.write_text(
            "This directory is gitignored (see /data/ rule in .gitignore).\n"
            "It holds rights-light raw fetches for Hawaiian Wikisource.\n"
            "Producer: scripts/202_fetch_hawwikisource_raw.py\n"
            "fetch.jsonl is the per-artefact provenance ledger consumed\n"
            "by downstream registration/extraction (Linus, 301).\n"
            "Do not commit any file under data/.\n",
            encoding="utf-8",
        )


def _append_provenance(base: Path, rec: ProvenanceRecord) -> None:
    ledger = base / "fetch.jsonl"
    with ledger.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(rec), ensure_ascii=False) + "\n")


def _store_bytes(fetch_dir: Path, body: bytes, ext: str) -> tuple[Path, str]:
    sha = hashlib.sha256(body).hexdigest()
    raw_path = fetch_dir / f"{sha}.{ext}"
    tmp_path = raw_path.with_suffix(raw_path.suffix + ".part")
    tmp_path.write_bytes(body)
    tmp_path.replace(raw_path)
    return raw_path, sha


# ---------------------------------------------------------------------------
# MediaWiki API helpers
# ---------------------------------------------------------------------------


def _build_url(params: dict[str, Any]) -> str:
    return f"{API_ENDPOINT}?{urllib.parse.urlencode(params)}"


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


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
    return _build_url(params)


def _page_content_url(*, page_id: int) -> str:
    return _page_content_batch_url(page_ids=[page_id])


def _page_content_batch_url(*, page_ids: list[int]) -> str:
    # action=query + prop=revisions rvslots=main rvprop=ids|timestamp|content
    # gives us wikitext plus revision_id in one call. pageids is preferred
    # over titles to avoid title-encoding edge cases.
    params: dict[str, Any] = {
        "action": "query",
        "prop": "revisions",
        "pageids": "|".join(str(page_id) for page_id in page_ids),
        "rvprop": "ids|timestamp|content|flags",
        "rvslots": "main",
        "format": "json",
        "formatversion": 2,
    }
    return _build_url(params)


def _page_has_content(page: dict[str, Any]) -> bool:
    revs = page.get("revisions", []) or []
    if not revs:
        return False
    slots = revs[0].get("slots", {})
    main = slots.get("main", {}) if isinstance(slots, dict) else {}
    return bool(main.get("content") or main.get("*") or revs[0].get("content") or revs[0].get("*"))


# ---------------------------------------------------------------------------
# Title enumeration
# ---------------------------------------------------------------------------


def _enumerate_titles(
    *,
    namespaces: tuple[int, ...],
    limit: int,
    batch_size: int,
    rate_limit_seconds: float,
    dry_run: bool,
    fetch_dir: Path,
    base: Path,
) -> list[dict[str, Any]]:
    """Walk list=categorymembers across the requested namespaces. Returns
    [{ns, page_id, title}, ...] up to ``limit`` total."""
    pages: list[dict[str, Any]] = []
    for ns in namespaces:
        cmcontinue: str | None = None
        while len(pages) < limit:
            remaining = limit - len(pages)
            this_batch = max(1, min(batch_size, remaining))
            url = _categorymembers_url(ns=ns, cmlimit=this_batch, cmcontinue=cmcontinue)

            if dry_run:
                print(f"  [dry-run] would GET categorymembers: {url}")
                break

            status, ctype, body = _http_get(url)
            raw_path, sha = _store_bytes(fetch_dir, body, "json")

            try:
                payload = json.loads(body.decode("utf-8"))
            except Exception as e:
                raise FetchError(f"categorymembers payload not JSON for {url}: {e!r}") from e

            batch_pages = payload.get("query", {}).get("categorymembers", []) or []
            picked: list[dict[str, Any]] = []
            for p in batch_pages:
                if len(pages) + len(picked) >= limit:
                    break
                picked.append({
                    "ns": ns,
                    "page_id": int(p["pageid"]),
                    "title": p["title"],
                })
            pages.extend(picked)

            rec = ProvenanceRecord(
                source_id=f"{SOURCE_NAME} — categorymembers-api",
                source_url=url,
                fetch_timestamp_utc=_utcnow_iso(),
                http_status=status,
                content_type=ctype,
                content_length=len(body),
                raw_sha256=sha,
                raw_storage_path=str(raw_path.relative_to(REPO_ROOT)),
                tos_or_license_url=WIKIMEDIA_TOS,
                license_observed="Wikimedia infrastructure metadata",
                fetcher_user_agent=USER_AGENT,
                fetcher_tool_and_version=f"{FETCHER_TOOL} v{FETCHER_VERSION}",
                source_specific_ids={
                    "artifact_kind": "categorymembers-api",
                    "category_title": HAWAIIAN_CATEGORY_TITLE,
                    "namespace": ns,
                    "cmlimit_requested": this_batch,
                    "cmcontinue": cmcontinue,
                    "page_ids_in_batch": [int(p["pageid"]) for p in batch_pages],
                    "titles_in_batch": [p["title"] for p in batch_pages],
                },
                notes="metadata-only artefact; not corpus text",
            )
            _append_provenance(base, rec)
            print(
                f"  enumerated ns={ns} batch={len(batch_pages)} "
                f"total={len(pages)} sha256={sha[:12]}…"
            )

            cont = payload.get("continue", {})
            cmcontinue = cont.get("cmcontinue")
            if not cmcontinue:
                break
            time.sleep(rate_limit_seconds)
    return pages


# ---------------------------------------------------------------------------
# Per-page wikitext fetch
# ---------------------------------------------------------------------------


def _fetch_page_content(
    *,
    page: dict[str, Any],
    rate_limit_seconds: float,
    dry_run: bool,
    fetch_dir: Path,
    base: Path,
) -> ProvenanceRecord | None:
    url = _page_content_url(page_id=page["page_id"])
    if dry_run:
        print(f"  [dry-run] would GET page content: {url}  ({page['title']!r})")
        return None

    status, ctype, body = _http_get(url)
    raw_path, sha = _store_bytes(fetch_dir, body, "json")

    rev_id: int | None = None
    rev_timestamp: str | None = None
    content_present = False
    try:
        payload = json.loads(body.decode("utf-8"))
        pages = payload.get("query", {}).get("pages", []) or []
        if pages:
            revs = pages[0].get("revisions", []) or []
            if revs:
                rev_id = int(revs[0].get("revid")) if revs[0].get("revid") is not None else None
                rev_timestamp = revs[0].get("timestamp")
                slots = revs[0].get("slots", {})
                main = slots.get("main", {}) if isinstance(slots, dict) else {}
                content_present = bool(main.get("content"))
    except Exception:
        pass

    rec = ProvenanceRecord(
        source_id=f"{SOURCE_NAME} — page-wikitext",
        source_url=url,
        fetch_timestamp_utc=_utcnow_iso(),
        http_status=status,
        content_type=ctype,
        content_length=len(body),
        raw_sha256=sha,
        raw_storage_path=str(raw_path.relative_to(REPO_ROOT)),
        tos_or_license_url=WIKIMEDIA_TOS,
        license_observed=WIKIMEDIA_LICENSE,
        fetcher_user_agent=USER_AGENT,
        fetcher_tool_and_version=f"{FETCHER_TOOL} v{FETCHER_VERSION}",
        source_specific_ids={
            "artifact_kind": "page-wikitext",
            "namespace": page["ns"],
            "page_id": page["page_id"],
            "title": page["title"],
            "revision_id": rev_id,
            "revision_timestamp": rev_timestamp,
            "content_present": content_present,
            "api_endpoint": API_ENDPOINT,
        },
        notes=(
            "MediaWiki action=query prop=revisions rvslots=main; "
            "raw JSON envelope stored as-is — extraction is downstream's job"
        ),
    )
    _append_provenance(base, rec)
    print(
        f"  page ok: ns={page['ns']} id={page['page_id']} "
        f"rev={rev_id} sha256={sha[:12]}… title={page['title']!r}"
    )
    time.sleep(rate_limit_seconds)
    return rec


def _fetch_page_batch(
    *,
    pages: list[dict[str, Any]],
    rate_limit_seconds: float,
    dry_run: bool,
    fetch_dir: Path,
    base: Path,
) -> ProvenanceRecord | None:
    """Fetch page wikitext for multiple page IDs and store as NDJSON.

    The downstream builder already supports bundled NDJSON records, one
    page-shaped JSON object per line. Batching keeps Wikimedia API usage
    polite and avoids the per-page request rate limit.
    """
    page_ids = [int(page["page_id"]) for page in pages]
    titles = [str(page["title"]) for page in pages]
    url = _page_content_batch_url(page_ids=page_ids)
    if dry_run:
        print(f"  [dry-run] would GET page content batch: {url}  ({len(pages)} page(s))")
        return None

    status, ctype, body = _http_get(url)

    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception as e:
        raise FetchError(f"page content batch payload not JSON for {url}: {e!r}") from e

    query_pages = payload.get("query", {}).get("pages", []) or []
    if isinstance(query_pages, dict):
        page_iter = list(query_pages.values())
    else:
        page_iter = list(query_pages) if isinstance(query_pages, list) else []

    lines: list[str] = []
    revision_ids: list[int] = []
    revision_timestamps: list[str] = []
    content_page_ids: list[int] = []
    for page in page_iter:
        if not isinstance(page, dict):
            continue
        if _page_has_content(page):
            try:
                content_page_ids.append(int(page.get("pageid")))
            except (TypeError, ValueError):
                pass
        revs = page.get("revisions", []) or []
        if revs:
            rev_id = revs[0].get("revid")
            if rev_id is not None:
                try:
                    revision_ids.append(int(rev_id))
                except (TypeError, ValueError):
                    pass
            rev_ts = revs[0].get("timestamp")
            if rev_ts:
                revision_timestamps.append(str(rev_ts))
        lines.append(json.dumps({"query": {"pages": [page]}}, ensure_ascii=False))

    if not lines:
        raise FetchError(f"page content batch contained no page records for {url}")

    ndjson = ("\n".join(lines) + "\n").encode("utf-8")
    raw_path, sha = _store_bytes(fetch_dir, ndjson, "jsonl")

    rec = ProvenanceRecord(
        source_id=f"{SOURCE_NAME} — page-wikitext-bundle",
        source_url=url,
        fetch_timestamp_utc=_utcnow_iso(),
        http_status=status,
        content_type="application/x-ndjson",
        content_length=len(ndjson),
        raw_sha256=sha,
        raw_storage_path=str(raw_path.relative_to(REPO_ROOT)),
        tos_or_license_url=WIKIMEDIA_TOS,
        license_observed=WIKIMEDIA_LICENSE,
        fetcher_user_agent=USER_AGENT,
        fetcher_tool_and_version=f"{FETCHER_TOOL} v{FETCHER_VERSION}",
        source_specific_ids={
            "artifact_kind": "page-wikitext-bundle",
            "namespace": sorted({int(page["ns"]) for page in pages}),
            "page_ids": page_ids,
            "titles": titles,
            "revision_ids": revision_ids,
            "revision_timestamps": revision_timestamps,
            "content_page_ids": content_page_ids,
            "content_present": bool(content_page_ids),
            "api_endpoint": API_ENDPOINT,
            "http_content_type": ctype,
        },
        notes=(
            "Batched MediaWiki action=query prop=revisions rvslots=main; "
            "stored as NDJSON with one page-shaped JSON object per line"
        ),
    )
    _append_provenance(base, rec)
    print(
        f"  batch ok: pages={len(page_iter)} content_pages={len(content_page_ids)} "
        f"sha256={sha[:12]}… first_title={titles[0]!r}"
    )
    time.sleep(rate_limit_seconds)
    return rec


# ---------------------------------------------------------------------------
# Page-plan loader (preferred input from scripts/102_collect_hawwikisource.py)
# ---------------------------------------------------------------------------


def _load_page_plan(path: Path, *, limit: int, namespaces: tuple[int, ...]) -> list[dict[str, Any]]:
    """Read ``page_plan.jsonl`` rows. Filters by namespace and caps at limit.

    Each row must contain at least ``ns``, ``page_id``, and ``title``.
    Other fields produced by 102 (``source_url``, ``api_url``, rights
    metadata) are accepted and ignored — 202 builds its own API URL.
    """
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for ln, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception as e:
                raise SystemExit(
                    f"error: page plan {path} line {ln}: not valid JSON ({e!r})"
                ) from e
            try:
                ns = int(obj["ns"])
                page_id = int(obj["page_id"])
                title = str(obj["title"])
            except (KeyError, TypeError, ValueError) as e:
                raise SystemExit(
                    f"error: page plan {path} line {ln}: missing/invalid "
                    f"required field (ns/page_id/title): {e!r}"
                ) from e
            if ns not in namespaces:
                continue
            rows.append({"ns": ns, "page_id": page_id, "title": title})
            if len(rows) >= limit:
                break
    return rows


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_namespaces(arg: str) -> tuple[int, ...]:
    out: list[int] = []
    for tok in arg.split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            ns = int(tok)
        except ValueError as e:
            raise SystemExit(f"error: --namespaces token {tok!r} is not a numeric ns id") from e
        # Reject Talk (odd ns), User (2/3), Special (-1), Media (-2),
        # File (6/7), MediaWiki (8/9), Template (10/11), Help (12/13).
        # Allow main (0) and Wikisource content namespaces (Page=104,
        # Index=106) which are the only ones with corpus value.
        if ns < 0 or ns % 2 == 1 or ns in {2, 6, 8, 10, 12, 14, 100, 102, 828}:
            raise SystemExit(
                f"error: namespace {ns} is excluded (Talk/User/Special/"
                "maintenance/non-content). Allowed: 0, 104, 106."
            )
        if ns not in {0, 104, 106}:
            raise SystemExit(
                f"error: namespace {ns} not on the allow-list. "
                "Allowed: 0 (main), 104 (Page), 106 (Index)."
            )
        out.append(ns)
    if not out:
        return DEFAULT_NAMESPACES
    return tuple(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Hawaiian Wikisource raw-data fetcher (Frank, sibling of 201).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help=f"Hard cap on total pages enumerated/fetched. Default: 50. Max: {MAX_TOTAL_PAGES}.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help=f"cmlimit per categorymembers request (max {MAX_BATCH}). Default: 50.",
    )
    parser.add_argument(
        "--namespaces",
        default="0",
        help="Comma-separated MediaWiki namespace IDs to enumerate. "
        "Default: 0 (main). Allow-list: 0, 104 (Page), 106 (Index). "
        "Talk/User/Special/maintenance namespaces are not selectable.",
    )
    parser.add_argument(
        "--rate-limit-seconds",
        type=float,
        default=1.0,
        help="Sleep between page fetches (and between paginated categorymembers "
        "calls). Default: 1.0s.",
    )
    parser.add_argument(
        "--page-plan",
        type=Path,
        default=DEFAULT_PAGE_PLAN_PATH,
        help=(
            "Path to a per-page fetch plan (JSONL) produced by "
            "scripts/102_collect_hawwikisource.py. Each row needs "
            "{ns, page_id, title}. If the file is missing or empty, "
            "202 falls back to direct MediaWiki list=categorymembers enumeration. "
            f"Default: {DEFAULT_PAGE_PLAN_PATH.relative_to(REPO_ROOT)}."
        ),
    )
    parser.add_argument(
        "--no-page-plan",
        action="store_true",
        help="Skip the 102 page-plan input even if present; force direct "
        "MediaWiki API enumeration.",
    )
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="Enumerate titles only; never fetch per-page wikitext "
        "even with --execute.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Required to fetch per-page wikitext. Without this flag, "
            "the script either does a dry-run or pulls only the small "
            "list=categorymembers JSON metadata.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned URLs and fetch nothing.",
    )
    args = parser.parse_args(argv)

    if args.limit < 1 or args.limit > MAX_TOTAL_PAGES:
        raise SystemExit(f"error: --limit must be in [1, {MAX_TOTAL_PAGES}]")
    if args.batch_size < 1 or args.batch_size > MAX_BATCH:
        raise SystemExit(f"error: --batch-size must be in [1, {MAX_BATCH}]")
    if args.rate_limit_seconds < 0.0 or args.rate_limit_seconds > 60.0:
        raise SystemExit("error: --rate-limit-seconds must be in [0.0, 60.0]")

    namespaces = _parse_namespaces(args.namespaces)
    fetch_pages = args.execute and not args.metadata_only

    use_plan = (
        not args.no_page_plan
        and args.page_plan is not None
        and args.page_plan.exists()
        and args.page_plan.stat().st_size > 0
    )

    print("ideal-spoon hawwikisource raw fetcher")
    print(f"  fetcher           : {FETCHER_TOOL} v{FETCHER_VERSION}")
    print(f"  user-agent        : {USER_AGENT}")
    print(f"  api endpoint      : {API_ENDPOINT}")
    print(f"  namespaces        : {namespaces}")
    print(f"  limit             : {args.limit}")
    print(f"  batch_size        : {args.batch_size}")
    print(f"  rate_limit_s      : {args.rate_limit_seconds}")
    print(f"  metadata_only     : {args.metadata_only}")
    print(f"  execute (pages)   : {args.execute}")
    print(f"  dry_run           : {args.dry_run}")
    print(
        f"  page_plan input   : {_display_path(args.page_plan) if args.page_plan else 'n/a'}"
        f"  ({'used' if use_plan else 'fallback to enumeration'})"
    )
    print(f"  raw root          : {RAW_ROOT.relative_to(REPO_ROOT)} (gitignored)")
    print()

    base, fetch_dir = _source_dirs()
    _write_readme(base)

    if use_plan:
        try:
            pages = _load_page_plan(args.page_plan, limit=args.limit, namespaces=namespaces)
        except SystemExit:
            raise
        print(
            f"  loaded page plan: {len(pages)} page(s) from "
            f"{_display_path(args.page_plan)}"
        )
        if args.dry_run and not args.execute:
            for p in pages:
                print(
                    f"  [dry-run] would GET page content: "
                    f"{_page_content_url(page_id=p['page_id'])}  ({p['title']!r})"
                )
    else:
        try:
            pages = _enumerate_titles(
                namespaces=namespaces,
                limit=args.limit,
                batch_size=args.batch_size,
                rate_limit_seconds=args.rate_limit_seconds,
                dry_run=args.dry_run,
                fetch_dir=fetch_dir,
                base=base,
            )
        except FetchError as e:
            print(f"  FETCH ERROR during enumeration: {e}", file=sys.stderr)
            return 3

        print(f"  enumeration complete: {len(pages)} page(s) collected")

    if not fetch_pages:
        if args.execute and args.metadata_only:
            print("  --metadata-only set: skipping per-page wikitext fetch.")
        elif not args.execute and not args.dry_run:
            print(
                "  per-page wikitext skipped (no --execute). "
                "Pass --execute (and not --metadata-only) to pull page content."
            )
        return 0

    try:
        content_batch_size = max(1, min(args.batch_size, MAX_BATCH))
        for start in range(0, len(pages), content_batch_size):
            _fetch_page_batch(
                pages=pages[start : start + content_batch_size],
                rate_limit_seconds=args.rate_limit_seconds,
                dry_run=args.dry_run,
                fetch_dir=fetch_dir,
                base=base,
            )
    except FetchError as e:
        print(f"  FETCH ERROR during page content pull: {e}", file=sys.stderr)
        return 3

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
