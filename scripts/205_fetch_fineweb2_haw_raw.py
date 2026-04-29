#!/usr/bin/env python3
"""FineWeb-2 ``haw_Latn`` raw-data fetcher (Frank, 200-phase).

Companion to ``scripts/105_collect_fineweb2_haw.py``. Consumes the
``data/local/fineweb2_haw/collect_plan.json`` plan and writes raw row
records under ``data/raw/fineweb2_haw/`` plus a ``fetch.jsonl``
provenance ledger compatible (in spirit) with the other 200-phase
fetchers in this repo.

Two fetch paths::

  * Default: HF datasets-server `/rows` JSON API. Stdlib + ``urllib`` only.
    Polite, paginated, ideal for tiny verification (``--limit 2``) and
    for prototype-scale ingest where bulk speed is not critical.

  * Optional: parquet shard (``--use-parquet``). Single file per split
    under HF's ``refs/convert/parquet`` ref. Requires ``pyarrow`` (not
    in requirements.txt yet; gated behind the flag and fails loudly if
    missing — Linus owns the dep call).

Safety posture:

* **Dry-run by default.** Without ``--execute`` no row text is downloaded
  and no files are written.
* The plan from 105 is the source of truth: dataset id, config, splits,
  expected row counts, parquet/rows-API URLs, license posture.
* Raw row records and any downloaded parquet land under
  ``data/raw/fineweb2_haw/`` which is gitignored.
* Provenance includes per-row source URL (``url``), CC dump
  (``dump``), date, FineWeb-2 LID score, and our fetch metadata.
* Actual raw whitespace token counts are computed from fetched ``text``
  only. No estimates.
* Large raw text is **never** echoed to stdout; only counts and field
  names are summarized.
* Schema mismatch (missing ``text``, missing expected fields) fails loudly.

Usage::

    python scripts/105_collect_fineweb2_haw.py
    python scripts/205_fetch_fineweb2_haw_raw.py --dry-run
    python scripts/205_fetch_fineweb2_haw_raw.py --execute --split test --limit 2
    python scripts/205_fetch_fineweb2_haw_raw.py --execute --split train --limit 100

    # Optional bulk parquet path (requires pyarrow, not installed by default):
    python scripts/205_fetch_fineweb2_haw_raw.py --execute --use-parquet --split test

Exit codes: 0 success, 2 misuse, 3 fetch / schema failure.
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
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_ROOT = REPO_ROOT / "data" / "raw"
DEFAULT_PLAN_PATH = REPO_ROOT / "data" / "local" / "fineweb2_haw" / "collect_plan.json"

SOURCE_ID = "fineweb2_haw"
SOURCE_NAME = "FineWeb-2 — Hawaiian (`haw_Latn`)"

FETCHER_TOOL = "urllib.request (stdlib); script=scripts/205_fetch_fineweb2_haw_raw.py"
FETCHER_VERSION = "0.1.0"
USER_AGENT = (
    f"ideal-spoon/{FETCHER_VERSION} (frank fineweb2_haw adapter; "
    "contact via github.com/yashasg/ideal-spoon issue #1)"
)

# Hard cap to keep a misconfigured run from accidentally pulling the whole
# corpus during prototyping. Plan total is 96,394 rows; this cap is set
# above that so a deliberate full pull is allowed but a typo is not.
MAX_TOTAL_ROWS = 200_000

ROWS_API_MAX_LENGTH = 100  # datasets-server /rows hard cap per call

REQUIRED_PLAN_KEYS = ("dataset", "splits", "per_row_schema", "fetcher_hints")


class FetchError(RuntimeError):
    pass


@dataclass
class ProvenanceRecord:
    """One JSONL row per fetched FineWeb-2 row. Schema mirrors 201/202/204."""

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


def _utcnow_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d")


def _relative_display(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _sleep_backoff(attempt: int, base: float = 1.5, cap: float = 45.0) -> None:
    delay = min(cap, base * (2 ** (attempt - 1))) + random.uniform(0, 0.5)
    time.sleep(delay)


def _load_plan(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FetchError(
            f"collect plan not found: {_relative_display(path)}. "
            "Run scripts/105_collect_fineweb2_haw.py first."
        )
    try:
        with path.open("r", encoding="utf-8") as f:
            plan = json.load(f)
    except json.JSONDecodeError as exc:
        raise FetchError(f"{path}: invalid JSON: {exc}") from exc
    missing = [k for k in REQUIRED_PLAN_KEYS if k not in plan]
    if missing:
        raise FetchError(f"{path}: plan missing required keys: {missing!r}")
    return plan


def _split_block(plan: dict[str, Any], split: str) -> dict[str, Any]:
    for entry in plan.get("splits", []):
        if entry.get("split") == split:
            return entry
    raise FetchError(
        f"split={split!r} not in plan; "
        f"available={[e.get('split') for e in plan.get('splits', [])]}"
    )


def _http_get(
    url: str,
    *,
    accept: str,
    timeout: float = 60.0,
    max_attempts: int = 4,
) -> tuple[int, str, bytes, str, dict[str, str]]:
    last_exc: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        req = urllib.request.Request(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": accept},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = int(resp.status)
                content_type = resp.headers.get(
                    "Content-Type", "application/octet-stream"
                )
                body = resp.read()
                headers = {str(k).lower(): str(v) for k, v in resp.headers.items()}
                return status, content_type, body, resp.geturl(), headers
        except urllib.error.HTTPError as exc:
            status = int(exc.code)
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


def _rows_api_url(plan: dict[str, Any], split: str, offset: int, length: int) -> str:
    template = plan["fetcher_hints"].get("rows_api_url_template")
    if template:
        return template.format(split=split, offset=offset, length=length)
    split_block = _split_block(plan, split)
    base_template = split_block["rows_api_url_template"]
    # The template stored in plan has fixed offset/length placeholders baked
    # in via .format already; reconstruct using the canonical pattern.
    return base_template.replace(
        "&offset=0&length=100",
        f"&offset={offset}&length={length}",
    )


def _iter_rows_api(
    plan: dict[str, Any],
    *,
    split: str,
    limit: int,
    rate_limit_seconds: float,
    start_offset: int = 0,
) -> Iterable[dict[str, Any]]:
    """Yield raw row dicts from the HF datasets-server `/rows` endpoint."""
    split_block = _split_block(plan, split)
    template = split_block["rows_api_url_template"]
    fetched = 0
    offset = start_offset
    while fetched < limit:
        length = min(ROWS_API_MAX_LENGTH, limit - fetched)
        url = template.replace(
            "&offset=0&length=100", f"&offset={offset}&length={length}"
        )
        status, content_type, body, _final, _headers = _http_get(
            url, accept="application/json"
        )
        if "application/json" not in content_type.lower():
            raise FetchError(
                f"unexpected content-type from rows API: {content_type!r} "
                f"(url={url})"
            )
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FetchError(f"rows API returned non-JSON: {exc}") from exc
        rows = payload.get("rows")
        if rows is None:
            raise FetchError(
                "rows API payload missing `rows` key; "
                f"keys present: {sorted(payload.keys())!r}"
            )
        if not rows:
            return  # end of split
        for entry in rows:
            row = entry.get("row") if isinstance(entry, dict) else None
            if row is None:
                raise FetchError(
                    "rows API entry missing `row`; "
                    f"keys present: {sorted(entry.keys()) if isinstance(entry, dict) else type(entry).__name__!r}"
                )
            yield row
            fetched += 1
            if fetched >= limit:
                return
        offset += len(rows)
        if rate_limit_seconds > 0 and fetched < limit:
            time.sleep(rate_limit_seconds)


def _iter_rows_parquet(
    plan: dict[str, Any],
    *,
    split: str,
    limit: int,
    raw_dir: Path,
) -> Iterable[dict[str, Any]]:
    """Yield raw row dicts by downloading and reading the split's parquet shard.

    Requires ``pyarrow``. Fails loudly if not installed.
    """
    try:
        import pyarrow.parquet as pq  # noqa: F401  (lazy import; optional dep)
        import pyarrow as pa  # noqa: F401
    except ImportError as exc:
        raise FetchError(
            "--use-parquet requires pyarrow, which is not in requirements.txt. "
            "Either install pyarrow locally, or use the default rows-API path. "
            "(Adding pyarrow to requirements.txt is Linus's dependency call.)"
        ) from exc

    import pyarrow.parquet as pq

    split_block = _split_block(plan, split)
    parquet_url = split_block["parquet_url"]
    raw_dir.mkdir(parents=True, exist_ok=True)
    local_path = raw_dir / f"{split}-0000.parquet"
    if not local_path.exists():
        status, content_type, body, _final, _headers = _http_get(
            parquet_url, accept="application/octet-stream", timeout=600.0
        )
        if status != 200:
            raise FetchError(f"HTTP {status} fetching parquet {parquet_url}")
        local_path.write_bytes(body)

    table = pq.read_table(local_path)
    cols = table.column_names
    if "text" not in cols:
        raise FetchError(
            f"parquet at {local_path} missing `text` column; columns={cols!r}"
        )
    yielded = 0
    for batch in table.to_batches():
        for i in range(batch.num_rows):
            if yielded >= limit:
                return
            row: dict[str, Any] = {}
            for j, name in enumerate(batch.schema.names):
                row[name] = batch.column(j)[i].as_py()
            yield row
            yielded += 1


def _validate_row_schema(row: dict[str, Any], expected_fields: tuple[str, ...]) -> None:
    missing = [f for f in expected_fields if f not in row]
    if missing:
        raise FetchError(
            f"row schema mismatch: missing fields {missing!r}; "
            f"row keys: {sorted(row.keys())!r}"
        )
    if not isinstance(row.get("text"), str):
        raise FetchError(
            f"row `text` field is not a string (got {type(row.get('text')).__name__})"
        )


def _raw_whitespace_tokens(text: str) -> int:
    return len(text.split())


def _store_record_jsonl(
    rows_dir: Path,
    *,
    split: str,
    record: dict[str, Any],
) -> Path:
    rows_dir.mkdir(parents=True, exist_ok=True)
    out_path = rows_dir / f"{split}.jsonl"
    with out_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return out_path


def _append_provenance(base: Path, rec: ProvenanceRecord) -> None:
    base.mkdir(parents=True, exist_ok=True)
    ledger = base / "fetch.jsonl"
    with ledger.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(rec), ensure_ascii=False, sort_keys=True) + "\n")


def _build_raw_record(
    row: dict[str, Any],
    *,
    plan: dict[str, Any],
    split: str,
    fetch_path: str,
    extraction_method: str,
) -> dict[str, Any]:
    text = row["text"]
    return {
        "schema_version": "1.0.0",
        "source_id": SOURCE_ID,
        "split": split,
        "fineweb2_row_id": row.get("id"),
        "source_url": row.get("url"),
        "cc_dump": row.get("dump"),
        "cc_date": row.get("date"),
        "cc_file_path": row.get("file_path"),
        "language": row.get("language"),
        "language_score": row.get("language_score"),
        "language_script": row.get("language_script"),
        "top_langs": row.get("top_langs"),
        "text": text,
        "raw_whitespace_token_count": _raw_whitespace_tokens(text),
        "char_count": len(text),
        "extraction_method": extraction_method,
        "fetched_via": fetch_path,
        "fetched_at_utc": _utcnow_iso(),
        "license_observed": plan.get("license_observed"),
        "license_tag": plan.get("license_tag"),
        "tos_or_license_url": plan.get("tos_or_license_url"),
        "prototype_only": True,
        "release_eligible": False,
    }


def _provenance_for_row(
    *,
    raw_record: dict[str, Any],
    raw_path: Path,
    raw_sha256: str,
    raw_bytes_len: int,
    plan: dict[str, Any],
    split: str,
    extraction_method: str,
) -> ProvenanceRecord:
    return ProvenanceRecord(
        source_id=f"{SOURCE_NAME} — {split}",
        source_url=str(raw_record.get("source_url") or ""),
        fetch_timestamp_utc=raw_record["fetched_at_utc"],
        http_status=200,
        content_type="application/json; charset=utf-8",
        content_length=raw_bytes_len,
        raw_sha256=raw_sha256,
        raw_storage_path=str(raw_path.relative_to(REPO_ROOT)),
        tos_or_license_url=str(plan.get("tos_or_license_url") or ""),
        license_observed=str(plan.get("license_observed") or ""),
        fetcher_user_agent=USER_AGENT,
        fetcher_tool_and_version=f"{FETCHER_TOOL} v{FETCHER_VERSION}",
        source_specific_ids={
            "source_id": SOURCE_ID,
            "hf_dataset_id": plan["dataset"]["hf_dataset_id"],
            "hf_config": plan["dataset"]["hf_config"],
            "split": split,
            "fineweb2_row_id": raw_record.get("fineweb2_row_id"),
            "cc_dump": raw_record.get("cc_dump"),
            "cc_date": raw_record.get("cc_date"),
            "language_score": raw_record.get("language_score"),
            "raw_whitespace_token_count": raw_record["raw_whitespace_token_count"],
            "char_count": raw_record["char_count"],
            "extraction_method": extraction_method,
            "prototype_only": True,
            "release_eligible": False,
        },
        notes=(
            "FineWeb-2 haw_Latn raw row preserved verbatim (no cleanup); "
            "downstream LID re-gate and dedup required before training use."
        ),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch raw FineWeb-2 haw_Latn rows from a 105 plan.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--plan",
        type=Path,
        default=DEFAULT_PLAN_PATH,
        help=(
            "Input collect_plan.json from 105 "
            f"(default: {DEFAULT_PLAN_PATH.relative_to(REPO_ROOT)})."
        ),
    )
    parser.add_argument(
        "--split",
        choices=("train", "test"),
        default="test",
        help="Which split to fetch from. Default: test (smaller, safer).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum row count to fetch from the chosen split. Default: 10.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually fetch and write raw row records. Without this, dry-run only.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Force dry-run even if --execute is present.",
    )
    parser.add_argument(
        "--rate-limit-seconds",
        type=float,
        default=1.0,
        help="Polite delay between rows-API pages. Default: 1.0.",
    )
    parser.add_argument(
        "--use-parquet",
        action="store_true",
        help=(
            "Bulk-fetch the split's parquet shard via pyarrow instead of the "
            "rows API. Requires pyarrow; fails loudly if not installed."
        ),
    )
    parser.add_argument(
        "--parquet-url",
        type=str,
        default=None,
        help=(
            "Override the parquet URL for the chosen split (only honored "
            "with --use-parquet). Useful for pinned mirrors."
        ),
    )
    parser.add_argument(
        "--start-offset",
        type=int,
        default=0,
        help=(
            "Resume offset for the rows API path (skips that many rows). "
            "Use after a 429/transient failure to avoid re-fetching what's "
            "already on disk. Ignored with --use-parquet."
        ),
    )
    args = parser.parse_args(argv)

    if args.limit < 1:
        print("error: --limit must be >= 1", file=sys.stderr)
        return 2
    if args.limit > MAX_TOTAL_ROWS:
        print(
            f"error: --limit {args.limit} exceeds safety cap {MAX_TOTAL_ROWS}",
            file=sys.stderr,
        )
        return 2
    if args.rate_limit_seconds < 0:
        print("error: --rate-limit-seconds must be >= 0", file=sys.stderr)
        return 2

    try:
        plan = _load_plan(args.plan)
    except FetchError as exc:
        print(f"FETCH ERROR: {exc}", file=sys.stderr)
        return 3

    split_block = None
    try:
        split_block = _split_block(plan, args.split)
    except FetchError as exc:
        print(f"FETCH ERROR: {exc}", file=sys.stderr)
        return 3

    if args.parquet_url:
        if not args.use_parquet:
            print(
                "error: --parquet-url requires --use-parquet",
                file=sys.stderr,
            )
            return 2
        split_block["parquet_url"] = args.parquet_url

    dry_run = args.dry_run or not args.execute
    expected_fields = tuple(plan["per_row_schema"]["fields"])

    print("ideal-spoon FineWeb-2 haw_Latn raw fetcher")
    print(f"  fetcher              : {FETCHER_TOOL} v{FETCHER_VERSION}")
    print(f"  user-agent           : {USER_AGENT}")
    print(f"  plan                 : {_relative_display(args.plan)}")
    print(f"  hf_dataset           : {plan['dataset']['hf_dataset_id']} (config={plan['dataset']['hf_config']})")
    print(f"  split                : {args.split} (expected {split_block['expected_row_count']:,} rows total)")
    print(f"  limit                : {args.limit}")
    print(f"  fetch_path           : {'parquet' if args.use_parquet else 'rows-api'}")
    print(f"  rate_limit_seconds   : {args.rate_limit_seconds}")
    print(f"  execute              : {args.execute}")
    print(f"  dry_run              : {dry_run}")
    print(f"  raw root             : {RAW_ROOT / SOURCE_ID} (gitignored)")
    print(f"  expected_fields      : {list(expected_fields)}")
    print(f"  license_observed     : {plan.get('license_observed')}")
    print()

    if dry_run:
        if args.use_parquet:
            print(f"[dry-run] would download {split_block['parquet_url']}")
        else:
            sample_url = _rows_api_url(plan, args.split, 0, min(ROWS_API_MAX_LENGTH, args.limit))
            print(f"[dry-run] would GET {sample_url}")
        print("[dry-run] would write raw JSONL + provenance under "
              f"{(RAW_ROOT / SOURCE_ID).relative_to(REPO_ROOT)}/")
        print("Pass --execute to fetch and write raw row records.")
        return 0

    base = RAW_ROOT / SOURCE_ID
    rows_dir = base / _today()
    rows_dir.mkdir(parents=True, exist_ok=True)

    extraction_method = (
        "fineweb2-parquet" if args.use_parquet else "fineweb2-rows-api"
    )
    fetch_path = "huggingface_parquet" if args.use_parquet else "datasets_server_rows_api"

    iterator: Iterable[dict[str, Any]]
    if args.use_parquet:
        iterator = _iter_rows_parquet(
            plan, split=args.split, limit=args.limit, raw_dir=rows_dir
        )
    else:
        iterator = _iter_rows_api(
            plan,
            split=args.split,
            limit=args.limit,
            rate_limit_seconds=args.rate_limit_seconds,
            start_offset=args.start_offset,
        )

    n_written = 0
    total_tokens = 0
    total_chars = 0
    rows_jsonl_path: Path | None = None
    try:
        for raw_row in iterator:
            _validate_row_schema(raw_row, expected_fields)
            raw_record = _build_raw_record(
                raw_row,
                plan=plan,
                split=args.split,
                fetch_path=fetch_path,
                extraction_method=extraction_method,
            )
            line = json.dumps(raw_record, ensure_ascii=False, sort_keys=True)
            line_bytes = (line + "\n").encode("utf-8")
            sha = hashlib.sha256(line_bytes).hexdigest()
            rows_jsonl_path = _store_record_jsonl(
                rows_dir, split=args.split, record=raw_record
            )
            prov = _provenance_for_row(
                raw_record=raw_record,
                raw_path=rows_jsonl_path,
                raw_sha256=sha,
                raw_bytes_len=len(line_bytes),
                plan=plan,
                split=args.split,
                extraction_method=extraction_method,
            )
            _append_provenance(base, prov)
            n_written += 1
            total_tokens += raw_record["raw_whitespace_token_count"]
            total_chars += raw_record["char_count"]
    except FetchError as exc:
        print(f"FETCH ERROR: {exc}", file=sys.stderr)
        return 3

    print(f"  rows written          : {n_written}")
    print(f"  raw whitespace tokens : {total_tokens}")
    print(f"  raw chars             : {total_chars}")
    if rows_jsonl_path is not None:
        print(f"  rows jsonl            : {_relative_display(rows_jsonl_path)}")
    print(f"  provenance ledger     : {_relative_display(base / 'fetch.jsonl')}")
    if n_written == 0:
        print("warning: no rows written (limit may be 0 or split exhausted)", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
