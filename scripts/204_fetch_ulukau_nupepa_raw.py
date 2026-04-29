#!/usr/bin/env python3
"""Ulukau/Nupepa raw-data fetcher.

This is the 200-phase companion to ``scripts/104_collect_ulukau_nupepa.py``.
It consumes ``data/local/ulukau_nupepa/document_plan.jsonl`` and writes raw
HTML plus extracted visible text under ``data/raw/ulukau_nupepa/``.

The current public Nupepa site may return a Cloudflare challenge for scripted
requests. This fetcher detects challenge responses and fails loudly; it does
not try to bypass anti-bot controls. If a legitimate bulk export/API or
permissioned mirror becomes available, wire it in here as a separate fetch
shape rather than disguising browser automation as a data adapter.

Safety posture:

* Dry-run by default. Pass ``--execute`` to write any raw corpus bytes.
* Reads source candidates from the 104 document plan.
* Stores local, gitignored raw bytes only; nothing in ``data/`` is committed.
* Emits actual raw whitespace token counts for extracted text records only.
* Marks all rows prototype-only and release-ineligible in provenance notes.

Usage::

    python scripts/104_collect_ulukau_nupepa.py --doc-id TPL18920521.2.1
    python scripts/204_fetch_ulukau_nupepa_raw.py --dry-run
    python scripts/204_fetch_ulukau_nupepa_raw.py --execute --limit 1

    # Ingest manually saved HTML exports instead of network fetches:
    python scripts/204_fetch_ulukau_nupepa_raw.py --execute --local-html-dir /path/to/html

Exit codes: 0 success, 2 misuse, 3 fetch/extraction failure.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import html
import json
import random
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_ROOT = REPO_ROOT / "data" / "raw"
DEFAULT_DOCUMENT_PLAN_PATH = (
    REPO_ROOT / "data" / "local" / "ulukau_nupepa" / "document_plan.jsonl"
)

SOURCE_ID = "ulukau_nupepa"
SOURCE_NAME = "Ulukau — Hawaiian-language newspapers (nūpepa)"
NUPEPA_BASE_URL = "https://www.nupepa.org/gsdl2.7/cgi-bin/nupepa"
DOC_URL_TEMPLATE = NUPEPA_BASE_URL + "?a=d&d={doc_id}"
ULUKAU_HOME_URL = "https://ulukau.org/?l=en"
LICENSE_OBSERVED_DEFAULT = (
    "unknown/not machine-verified; item-level rights and Ulukau/Nupepa terms "
    "must be reviewed before any non-private use"
)

FETCHER_TOOL = "urllib.request (stdlib); script=scripts/204_fetch_ulukau_nupepa_raw.py"
FETCHER_VERSION = "0.1.0"
USER_AGENT = (
    f"ideal-spoon/{FETCHER_VERSION} (frank ulukau_nupepa adapter; "
    "contact via github.com/yashasg/ideal-spoon issue #1)"
)

MAX_TOTAL_DOCS = 50_000


@dataclass
class ProvenanceRecord:
    """One JSONL row per fetched artefact. Schema-compatible with 201/202."""

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


class FetchError(RuntimeError):
    pass


def _utcnow_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d")


def _sleep_backoff(attempt: int, base: float = 1.5, cap: float = 45.0) -> None:
    delay = min(cap, base * (2 ** (attempt - 1))) + random.uniform(0, 0.5)
    time.sleep(delay)


def _relative_display(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _append_provenance(base: Path, rec: ProvenanceRecord) -> None:
    base.mkdir(parents=True, exist_ok=True)
    ledger = base / "fetch.jsonl"
    with ledger.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(rec), ensure_ascii=False, sort_keys=True) + "\n")


def _store_bytes(fetch_dir: Path, body: bytes, ext: str) -> tuple[Path, str]:
    sha = hashlib.sha256(body).hexdigest()
    safe_ext = ext.lstrip(".")
    path = fetch_dir / f"{sha}.{safe_ext}"
    if not path.exists():
        path.write_bytes(body)
    return path, sha


def _source_dirs() -> tuple[Path, Path]:
    base = RAW_ROOT / SOURCE_ID
    fetch_dir = base / _today()
    fetch_dir.mkdir(parents=True, exist_ok=True)
    return base, fetch_dir


def _document_url(doc_id: str) -> str:
    return DOC_URL_TEMPLATE.format(doc_id=doc_id)


def _load_document_plan(path: Path, limit: int | None) -> list[dict[str, Any]]:
    if not path.exists():
        raise FetchError(
            f"document plan not found: {_relative_display(path)}. "
            "Run scripts/104_collect_ulukau_nupepa.py first."
        )

    docs: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise FetchError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
            doc_id = str(obj.get("doc_id") or "").strip()
            if not doc_id:
                raise FetchError(f"{path}:{line_no}: missing doc_id")
            obj.setdefault("source_url", _document_url(doc_id))
            docs.append(obj)
            if limit is not None and len(docs) >= limit:
                break

    if len(docs) > MAX_TOTAL_DOCS:
        raise FetchError(f"refusing to fetch {len(docs)} docs; cap is {MAX_TOTAL_DOCS}")
    return docs


def _headers_dict(headers: Any) -> dict[str, str]:
    return {str(k).lower(): str(v) for k, v in headers.items()}


def _looks_like_cloudflare_challenge(
    *,
    status: int,
    content_type: str,
    headers: dict[str, str],
    body: bytes,
) -> bool:
    lowered = body[:16_384].decode("utf-8", errors="replace").lower()
    return (
        headers.get("cf-mitigated", "").lower() == "challenge"
        or "challenges.cloudflare.com" in lowered
        or ("just a moment" in lowered and "cloudflare" in lowered)
        or (
            status in {403, 503}
            and "text/html" in content_type.lower()
            and "cloudflare" in lowered
        )
    )


def _http_get(
    url: str,
    *,
    timeout: float = 60.0,
    max_attempts: int = 4,
) -> tuple[int, str, bytes, str]:
    last_exc: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.5",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = int(resp.status)
                content_type = resp.headers.get("Content-Type", "application/octet-stream")
                body = resp.read()
                headers = _headers_dict(resp.headers)
                if _looks_like_cloudflare_challenge(
                    status=status,
                    content_type=content_type,
                    headers=headers,
                    body=body,
                ):
                    raise FetchError(
                        "blocked_by_cloudflare_challenge: Nupepa returned an "
                        "anti-bot challenge. Not bypassing; use approved bulk "
                        "access or local manual exports."
                    )
                return status, content_type, body, resp.geturl()
        except urllib.error.HTTPError as exc:
            status = int(exc.code)
            content_type = exc.headers.get("Content-Type", "application/octet-stream")
            body = exc.read()
            headers = _headers_dict(exc.headers)
            if _looks_like_cloudflare_challenge(
                status=status,
                content_type=content_type,
                headers=headers,
                body=body,
            ):
                raise FetchError(
                    f"blocked_by_cloudflare_challenge: HTTP {status} from {url}. "
                    "Not bypassing; use approved bulk access or local manual exports."
                ) from exc
            if status in {429, 500, 502, 503, 504} and attempt < max_attempts:
                last_exc = exc
                _sleep_backoff(attempt)
                continue
            raise FetchError(f"HTTP {status} for {url}") from exc
        except urllib.error.URLError as exc:
            last_exc = exc
            if attempt < max_attempts:
                _sleep_backoff(attempt)
                continue
            raise FetchError(f"network error for {url}: {exc}") from exc
    raise FetchError(f"failed to fetch {url}: {last_exc!r}")


class VisibleTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        if tag.lower() in {"p", "br", "div", "tr", "li", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
        if tag.lower() in {"p", "div", "tr", "li"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if data.strip():
            self.parts.append(data)

    def text(self) -> str:
        raw = html.unescape(" ".join(self.parts))
        lines = []
        for line in raw.splitlines():
            collapsed = re.sub(r"[ \t\r\f\v]+", " ", line).strip()
            if collapsed:
                lines.append(collapsed)
        return "\n".join(lines).strip()


def _extract_visible_text(body: bytes, content_type: str) -> str:
    charset = "utf-8"
    match = re.search(r"charset=([^;\s]+)", content_type, flags=re.I)
    if match:
        charset = match.group(1).strip("\"'")
    decoded = body.decode(charset, errors="replace")
    parser = VisibleTextExtractor()
    parser.feed(decoded)
    return parser.text()


def _raw_whitespace_tokens(text: str) -> int:
    return len(text.split())


def _local_html_candidates(doc_id: str, local_html_dir: Path) -> Iterable[Path]:
    safe_doc_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", doc_id)
    yield local_html_dir / f"{doc_id}.html"
    yield local_html_dir / f"{safe_doc_id}.html"
    yield local_html_dir / f"{doc_id}.htm"
    yield local_html_dir / f"{safe_doc_id}.htm"


def _read_local_html(doc_id: str, local_html_dir: Path) -> tuple[int, str, bytes, str]:
    for candidate in _local_html_candidates(doc_id, local_html_dir):
        if candidate.exists():
            return 200, "text/html; charset=utf-8", candidate.read_bytes(), candidate.as_uri()
    raise FetchError(
        f"local HTML for doc_id={doc_id!r} not found under {_relative_display(local_html_dir)}; "
        f"expected files like {doc_id}.html"
    )


def _record_for_artifact(
    *,
    row: dict[str, Any],
    source_url: str,
    status: int,
    content_type: str,
    body: bytes,
    raw_path: Path,
    raw_sha: str,
    artifact_kind: str,
    extra_ids: dict[str, Any],
    notes: str,
) -> ProvenanceRecord:
    return ProvenanceRecord(
        source_id=f"{SOURCE_NAME} — {artifact_kind}",
        source_url=source_url,
        fetch_timestamp_utc=_utcnow_iso(),
        http_status=status,
        content_type=content_type,
        content_length=len(body),
        raw_sha256=raw_sha,
        raw_storage_path=str(raw_path.relative_to(REPO_ROOT)),
        tos_or_license_url=str(row.get("tos_or_license_url") or ULUKAU_HOME_URL),
        license_observed=str(row.get("license_observed") or LICENSE_OBSERVED_DEFAULT),
        fetcher_user_agent=USER_AGENT,
        fetcher_tool_and_version=f"{FETCHER_TOOL} v{FETCHER_VERSION}",
        source_specific_ids={
            "doc_id": row["doc_id"],
            "source_id": SOURCE_ID,
            "artifact_kind": artifact_kind,
            "prototype_only": True,
            "release_eligible": False,
            **extra_ids,
        },
        notes=notes,
    )


def _fetch_one(
    row: dict[str, Any],
    *,
    fetch_dir: Path,
    local_html_dir: Path | None,
    min_text_chars: int,
) -> list[ProvenanceRecord]:
    doc_id = str(row["doc_id"])
    requested_url = str(row.get("source_url") or _document_url(doc_id))

    if local_html_dir is not None:
        status, content_type, body, final_url = _read_local_html(doc_id, local_html_dir)
    else:
        status, content_type, body, final_url = _http_get(requested_url)

    headers: dict[str, str] = {}
    if _looks_like_cloudflare_challenge(
        status=status,
        content_type=content_type,
        headers=headers,
        body=body,
    ):
        raise FetchError(
            f"blocked_by_cloudflare_challenge for doc_id={doc_id}. "
            "Not storing challenge HTML as corpus."
        )

    html_path, html_sha = _store_bytes(fetch_dir, body, "html")
    html_rec = _record_for_artifact(
        row=row,
        source_url=final_url or requested_url,
        status=status,
        content_type=content_type,
        body=body,
        raw_path=html_path,
        raw_sha=html_sha,
        artifact_kind="document-html",
        extra_ids={"requested_url": requested_url},
        notes=(
            "raw Nupepa document HTML; prototype-only, rights-gated; "
            "not release-eligible"
        ),
    )

    text = _extract_visible_text(body, content_type)
    token_count = _raw_whitespace_tokens(text)
    records = [html_rec]
    if len(text) >= min_text_chars:
        text_body = (text + "\n").encode("utf-8")
        text_path, text_sha = _store_bytes(fetch_dir, text_body, "txt")
        text_rec = _record_for_artifact(
            row=row,
            source_url=final_url or requested_url,
            status=status,
            content_type="text/plain; charset=utf-8",
            body=text_body,
            raw_path=text_path,
            raw_sha=text_sha,
            artifact_kind="visible-text-extract",
            extra_ids={
                "requested_url": requested_url,
                "html_sha256": html_sha,
                "extraction_method": "html-visible-text-stdlib",
                "raw_whitespace_token_count": token_count,
                "char_count": len(text),
            },
            notes=(
                "visible text extracted from raw Nupepa HTML; may include OCR "
                "noise and boilerplate; prototype-only, rights-gated; not "
                "release-eligible"
            ),
        )
        records.append(text_rec)
    else:
        html_rec.source_specific_ids["text_extract_status"] = "too_short_or_absent"
        html_rec.source_specific_ids["text_extract_char_count"] = len(text)
        html_rec.source_specific_ids["raw_whitespace_token_count"] = token_count
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch or ingest raw Ulukau/Nupepa document HTML from a 104 plan.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--document-plan",
        type=Path,
        default=DEFAULT_DOCUMENT_PLAN_PATH,
        help=(
            "Input JSONL plan from 104 "
            f"(default: {DEFAULT_DOCUMENT_PLAN_PATH.relative_to(REPO_ROOT)})."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum document rows to process from the plan. Default: 10.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually fetch/ingest and write raw bytes. Without this, dry-run only.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Force dry-run even if --execute is present.",
    )
    parser.add_argument(
        "--rate-limit-seconds",
        type=float,
        default=5.0,
        help="Delay between network fetches. Ignored for --local-html-dir. Default: 5.0.",
    )
    parser.add_argument(
        "--local-html-dir",
        type=Path,
        default=None,
        help=(
            "Directory of manually saved HTML files named <doc_id>.html. "
            "When set, no network requests are made."
        ),
    )
    parser.add_argument(
        "--min-text-chars",
        type=int,
        default=200,
        help="Minimum visible-text length before writing a .txt extract. Default: 200.",
    )
    args = parser.parse_args(argv)

    if args.limit < 1:
        print("error: --limit must be >= 1", file=sys.stderr)
        return 2
    if args.rate_limit_seconds < 0:
        print("error: --rate-limit-seconds must be >= 0", file=sys.stderr)
        return 2

    try:
        docs = _load_document_plan(args.document_plan, args.limit)
    except FetchError as exc:
        print(f"FETCH ERROR: {exc}", file=sys.stderr)
        return 3

    dry_run = args.dry_run or not args.execute
    print("ideal-spoon Ulukau/Nupepa raw fetcher")
    print(f"  fetcher              : {FETCHER_TOOL} v{FETCHER_VERSION}")
    print(f"  user-agent           : {USER_AGENT}")
    print(f"  document_plan        : {_relative_display(args.document_plan)}")
    print(f"  documents selected   : {len(docs)}")
    print(f"  execute              : {args.execute}")
    print(f"  dry_run              : {dry_run}")
    print(f"  local_html_dir       : {_relative_display(args.local_html_dir) if args.local_html_dir else None}")
    print(f"  rate_limit_seconds   : {args.rate_limit_seconds}")
    print(f"  raw root             : {RAW_ROOT / SOURCE_ID} (gitignored)")
    print()

    if dry_run:
        for row in docs:
            doc_id = str(row["doc_id"])
            print(f"[dry-run] doc_id={doc_id} url={row.get('source_url') or _document_url(doc_id)}")
        if docs:
            print()
            print("Pass --execute to fetch/ingest. Challenge pages will fail, not be bypassed.")
        return 0

    base, fetch_dir = _source_dirs()
    overall_ok = True
    total_text_tokens = 0
    total_text_records = 0
    for idx, row in enumerate(docs, start=1):
        doc_id = str(row["doc_id"])
        try:
            records = _fetch_one(
                row,
                fetch_dir=fetch_dir,
                local_html_dir=args.local_html_dir,
                min_text_chars=args.min_text_chars,
            )
            for rec in records:
                _append_provenance(base, rec)
                if rec.source_specific_ids.get("artifact_kind") == "visible-text-extract":
                    total_text_records += 1
                    total_text_tokens += int(
                        rec.source_specific_ids.get("raw_whitespace_token_count") or 0
                    )
            print(f"  ok doc_id={doc_id}")
            for rec in records:
                kind = rec.source_specific_ids.get("artifact_kind")
                token_suffix = ""
                if kind == "visible-text-extract":
                    token_suffix = (
                        " raw_whitespace_tokens="
                        f"{rec.source_specific_ids.get('raw_whitespace_token_count')}"
                    )
                print(f"    {kind}: {rec.raw_storage_path}{token_suffix}")
        except FetchError as exc:
            overall_ok = False
            print(f"  FETCH ERROR doc_id={doc_id}: {exc}", file=sys.stderr)
            break

        if args.local_html_dir is None and idx < len(docs):
            time.sleep(args.rate_limit_seconds)

    print()
    print(f"  text records written       : {total_text_records}")
    print(f"  raw whitespace tokens seen : {total_text_tokens}")
    if not overall_ok:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
