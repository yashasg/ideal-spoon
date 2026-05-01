#!/usr/bin/env python3
"""Stage-2 static raw-data fetcher (200-phase).

Consumes ``data/local/stage2_parallel/collect_plan.json`` from
``scripts/107_collect_stage2_parallel.py`` and fetches static downloadable
artifacts from Stage-2 sources into ``data/raw/<source_id>/<YYYYMMDD>/``.

This is deliberately a raw-byte fetcher, not a candidate-row builder. Sources
that need source-specific parsing/alignment still flow through 300-phase
adapters (for example ``data-sources/tatoeba/fetch.py`` and
``scripts/322_build_bible_candidates.py``).

Safety posture:

* Dry-run by default; no network or file writes unless ``--execute`` or
  ``--check-headers`` is passed.
* ``--execute`` refuses gated sources until the relevant explicit
  acknowledgement flags are present.
* Eval-only sources require ``--include-eval`` even if they are present in the
  collect plan.
* Raw bytes and provenance ledgers are written only under gitignored
  ``data/raw/``.

Usage::

    python scripts/107_collect_stage2_parallel.py
    python scripts/207_fetch_stage2_parallel_raw.py --dry-run
    python scripts/207_fetch_stage2_parallel_raw.py --check-headers --source tatoeba-haw-eng
    python scripts/207_fetch_stage2_parallel_raw.py --execute --source tatoeba-haw-eng
    python scripts/207_fetch_stage2_parallel_raw.py --execute --source opus-haw-subsets \
        --allow-rights-review --allow-pending-endpoint

Exit codes: 0 success, 2 misuse / gated source, 3 fetch failure.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as _dt
import hashlib
import json
import random
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PLAN = REPO_ROOT / "data" / "local" / "stage2_parallel" / "collect_plan.json"
RAW_ROOT = REPO_ROOT / "data" / "raw"

FETCHER_TOOL = "urllib.request (stdlib); script=scripts/207_fetch_stage2_parallel_raw.py"
FETCHER_VERSION = "0.1.0"
USER_AGENT = (
    f"ideal-spoon/{FETCHER_VERSION} (stage2 static raw fetcher; "
    "contact via github.com/yashasg/ideal-spoon)"
)

DEFAULT_LIMIT_FILES = 10
MAX_LIMIT_FILES = 1_000


class FetchError(RuntimeError):
    pass


@dataclasses.dataclass
class ProvenanceRecord:
    """One JSONL row per fetched static artifact."""

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
    source_specific_ids: dict[str, Any] = dataclasses.field(default_factory=dict)
    notes: str = ""


def _utcnow_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today_compact_utc() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d")


def _relative_display(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _sleep_backoff(attempt: int, base: float = 1.5, cap: float = 45.0) -> None:
    delay = min(cap, base * (2 ** (attempt - 1))) + random.uniform(0, 0.5)
    time.sleep(delay)


def load_plan(path: Path = DEFAULT_PLAN) -> dict[str, Any]:
    if not path.exists():
        raise FetchError(
            f"collect plan not found: {_relative_display(path)}. "
            "Run scripts/107_collect_stage2_parallel.py first."
        )
    try:
        with path.open("r", encoding="utf-8") as fh:
            plan = json.load(fh)
    except json.JSONDecodeError as exc:
        raise FetchError(f"collect plan is not valid JSON: {path}: {exc}") from exc
    if plan.get("schema_version") != "stage2-parallel-collect-plan.v1":
        raise FetchError(
            "unexpected collect-plan schema_version: "
            f"{plan.get('schema_version')!r}"
        )
    if not isinstance(plan.get("sources"), list):
        raise FetchError("collect plan missing list field `sources`")
    return plan


def _selected_sources(plan: dict[str, Any], source_selectors: list[str]) -> list[dict[str, Any]]:
    sources = list(plan.get("sources") or [])
    if not source_selectors or source_selectors == ["all"]:
        return sources

    wanted = set(source_selectors)
    out = [s for s in sources if s.get("source_id") in wanted]
    missing = sorted(wanted - {str(s.get("source_id")) for s in out})
    if missing:
        raise FetchError(f"unknown source(s) in plan: {', '.join(missing)}")
    return out


def execute_gate_reasons(
    source: dict[str, Any],
    *,
    include_eval: bool,
    allow_rights_review: bool,
    allow_pending_endpoint: bool,
    allow_blocked: bool,
) -> list[str]:
    """Return reasons this source cannot be executed under current flags."""
    reasons: list[str] = []
    if source.get("fetch_kind") != "static-download":
        reasons.append(f"not_static_download:{source.get('fetch_kind')}")
    if not source.get("download_artifacts"):
        reasons.append("no_download_artifacts")

    for gate in source.get("fetch_gates") or []:
        if gate == "eval_only" and not include_eval:
            reasons.append("requires --include-eval")
        elif gate == "rights_review_required" and not allow_rights_review:
            reasons.append("requires --allow-rights-review")
        elif gate == "endpoint_check_required" and not allow_pending_endpoint:
            reasons.append("requires --allow-pending-endpoint")
        elif gate.startswith("blocked_until:") and not allow_blocked:
            reasons.append(f"requires --allow-blocked ({gate})")
    return reasons


def iter_fetch_items(
    sources: list[dict[str, Any]],
    *,
    include_eval: bool,
    allow_rights_review: bool,
    allow_pending_endpoint: bool,
    allow_blocked: bool,
    strict_gates: bool,
) -> list[dict[str, Any]]:
    """Flatten eligible source artifacts into fetch items."""
    items: list[dict[str, Any]] = []
    gate_errors: list[str] = []

    for source in sources:
        reasons = execute_gate_reasons(
            source,
            include_eval=include_eval,
            allow_rights_review=allow_rights_review,
            allow_pending_endpoint=allow_pending_endpoint,
            allow_blocked=allow_blocked,
        )
        if reasons:
            msg = f"{source.get('source_id')}: {', '.join(reasons)}"
            if strict_gates:
                gate_errors.append(msg)
            continue
        for artifact in source.get("download_artifacts") or []:
            items.append({"source": source, "artifact": artifact})

    if gate_errors:
        raise FetchError("gated sources refused: " + " | ".join(gate_errors))
    return items


def _http_request(
    url: str,
    *,
    method: str,
    timeout: float = 60.0,
    max_attempts: int = 4,
) -> tuple[int, str, bytes, dict[str, str]]:
    last_exc: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        req = urllib.request.Request(
            url,
            method=method,
            headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = int(resp.status)
                content_type = resp.headers.get("Content-Type", "application/octet-stream")
                headers = {str(k).lower(): str(v) for k, v in resp.headers.items()}
                body = b"" if method == "HEAD" else resp.read()
                if status >= 400:
                    raise FetchError(f"HTTP {status} for {url}")
                declared_len = headers.get("content-length")
                if method != "HEAD" and declared_len is not None:
                    expected = int(declared_len)
                    if len(body) != expected:
                        raise FetchError(
                            f"short read for {url}: got {len(body)} bytes, "
                            f"Content-Length declared {expected}"
                        )
                return status, content_type, body, headers
        except (urllib.error.URLError, TimeoutError, FetchError) as exc:
            last_exc = exc
            if attempt < max_attempts:
                _sleep_backoff(attempt)
                continue
            raise FetchError(f"{method} failed after {attempt} attempt(s): {url}: {exc}") from exc
    raise FetchError(f"{method} failed: {url}: {last_exc!r}")


def _safe_filename(name: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return cleaned or fallback


def _artifact_path(
    *,
    source_id: str,
    fetch_date: str,
    filename: str,
    index: int,
) -> Path:
    safe = _safe_filename(filename, f"artifact-{index}.raw")
    return RAW_ROOT / source_id / fetch_date / safe


def write_provenance(source_id: str, rec: ProvenanceRecord) -> None:
    ledger = RAW_ROOT / source_id / "fetch.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(dataclasses.asdict(rec), ensure_ascii=False, sort_keys=True) + "\n")


def fetch_item(
    item: dict[str, Any],
    *,
    fetch_date: str,
    index: int,
    overwrite: bool,
) -> ProvenanceRecord:
    source = item["source"]
    artifact = item["artifact"]
    source_id = str(source["source_id"])
    url = str(artifact["url"])
    out_path = _artifact_path(
        source_id=source_id,
        fetch_date=fetch_date,
        filename=str(artifact.get("filename") or ""),
        index=index,
    )

    if out_path.exists() and not overwrite:
        body = out_path.read_bytes()
        status = 200
        content_type = "application/octet-stream"
    else:
        status, content_type, body, _headers = _http_request(url, method="GET")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(body)

    sha = hashlib.sha256(body).hexdigest()
    target = item.get("target") or {}
    return ProvenanceRecord(
        source_id=source_id,
        source_url=url,
        fetch_timestamp_utc=_utcnow_iso(),
        http_status=status,
        content_type=content_type,
        content_length=len(body),
        raw_sha256=sha,
        raw_storage_path=_relative_display(out_path),
        tos_or_license_url=str(source.get("tos_or_license_url") or ""),
        license_observed=str(source.get("license_observed") or "unknown"),
        fetcher_user_agent=USER_AGENT,
        fetcher_tool_and_version=f"{FETCHER_TOOL} v{FETCHER_VERSION}",
        source_specific_ids={
            "artifact_id": artifact.get("artifact_id"),
            "artifact_filename": artifact.get("filename"),
            "source_name": source.get("name"),
            "tier": source.get("tier"),
            "alignment_type": source.get("alignment_type"),
            "rights_status_hint": source.get("rights_status_hint"),
            "verification_status": source.get("verification_status"),
            "target_sft_rows": target.get("sft_rows"),
            "target_canonical_pairs": target.get("canonical_pair_target"),
        },
        notes="stage2 static raw fetch; prototype_only=true; not a public artifact",
    )


def check_headers(items: list[dict[str, Any]], *, limit: int | None, rate_limit: float) -> int:
    checked = 0
    for item in items[:limit]:
        source_id = item["source"]["source_id"]
        artifact = item["artifact"]
        url = artifact["url"]
        try:
            status, content_type, _body, headers = _http_request(url, method="HEAD")
        except FetchError as exc:
            print(f"[WARN] {source_id} HEAD failed: {url}: {exc}")
        else:
            clen = headers.get("content-length", "?")
            print(f"[OK]   {source_id} HTTP {status} {content_type} bytes={clen} {url}")
        checked += 1
        if rate_limit:
            time.sleep(rate_limit)
    print(f"checked {checked} header(s)")
    return 0


def _limit_or_none(limit_files: int) -> int | None:
    if limit_files < 0 or limit_files > MAX_LIMIT_FILES:
        raise FetchError(f"--limit-files must be between 0 and {MAX_LIMIT_FILES}")
    return None if limit_files == 0 else limit_files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true",
                      help="Print eligible artifacts without network/file writes. Default.")
    mode.add_argument("--check-headers", action="store_true",
                      help="Issue HEAD requests for eligible artifacts; do not write files.")
    mode.add_argument("--execute", action="store_true",
                      help="Download eligible artifacts and append provenance ledgers.")

    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--source", action="append", default=None,
                        help="Source ID to consider. Repeatable. Default: all.")
    parser.add_argument("--include-eval", action="store_true",
                        help="Allow eval-only sources if present in the plan.")
    parser.add_argument("--allow-rights-review", action="store_true",
                        help="Acknowledge rights_review_required sources for private prototype fetch.")
    parser.add_argument("--allow-pending-endpoint", action="store_true",
                        help="Acknowledge pending_endpoint_check sources.")
    parser.add_argument("--allow-blocked", action="store_true",
                        help="Override do_not_invoke_until blockers. Use only after the owner resolves them.")
    parser.add_argument("--limit-files", type=int, default=DEFAULT_LIMIT_FILES,
                        help=f"Max artifacts this run; 0 means no cap (default {DEFAULT_LIMIT_FILES}).")
    parser.add_argument("--fetch-date", default=None,
                        help="Override fetch date directory (YYYYMMDD). Default: today UTC.")
    parser.add_argument("--rate-limit-seconds", type=float, default=1.0)
    parser.add_argument("--overwrite", action="store_true",
                        help="Re-fetch even when the target raw file already exists.")
    args = parser.parse_args(argv)

    try:
        limit = _limit_or_none(args.limit_files)
        plan = load_plan(args.plan)
        sources = _selected_sources(plan, args.source or ["all"])
        strict_gates = bool(args.execute or args.check_headers)
        items = iter_fetch_items(
            sources,
            include_eval=args.include_eval,
            allow_rights_review=args.allow_rights_review,
            allow_pending_endpoint=args.allow_pending_endpoint,
            allow_blocked=args.allow_blocked,
            strict_gates=strict_gates,
        )
    except FetchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    # Carry target math through to provenance without duplicating source JSON.
    for item in items:
        item["target"] = plan.get("stage2_target") or {}

    selected = items[:limit]
    if not args.execute and not args.check_headers:
        print("[DRY-RUN] Stage-2 static raw fetcher; no network/files.")
        print(f"[DRY-RUN] plan: {_relative_display(args.plan)}")
        print(f"[DRY-RUN] eligible artifacts: {len(items)} (showing {len(selected)})")
        for i, item in enumerate(selected, start=1):
            source = item["source"]
            artifact = item["artifact"]
            print(
                f"  {i:03d}. {source['source_id']} "
                f"{artifact.get('filename')} <- {artifact.get('url')}"
            )
        if len(items) > len(selected):
            print(f"[DRY-RUN] {len(items) - len(selected)} more hidden by --limit-files")
        return 0

    if args.check_headers:
        return check_headers(selected, limit=limit, rate_limit=args.rate_limit_seconds)

    fetch_date = args.fetch_date or _today_compact_utc()
    if not re.fullmatch(r"\d{8}", fetch_date):
        print(f"error: --fetch-date must be YYYYMMDD, got {fetch_date!r}", file=sys.stderr)
        return 2

    fetched = 0
    for i, item in enumerate(selected, start=1):
        source_id = item["source"]["source_id"]
        try:
            rec = fetch_item(item, fetch_date=fetch_date, index=i, overwrite=args.overwrite)
        except FetchError as exc:
            print(f"fetch failed: {source_id}: {exc}", file=sys.stderr)
            return 3
        write_provenance(source_id, rec)
        fetched += 1
        print(f"[OK] {source_id}: {rec.raw_storage_path} ({rec.content_length} bytes)")
        if args.rate_limit_seconds:
            time.sleep(args.rate_limit_seconds)

    print(f"[EXECUTE] fetched {fetched} artifact(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
