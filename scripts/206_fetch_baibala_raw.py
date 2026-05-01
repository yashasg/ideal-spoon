#!/usr/bin/env python3
"""Baibala Hemolele × public-domain English Bible raw fetcher (Frank, issue #16).

First Stage-2 source adapter. Owns the raw-fetch half of the
verse-aligned (Hawaiian, English) Bible pair. Companion to:

  * ``data-sources/bible/source_registry.json`` — pinned edition pair,
    URL templates, full 66-book canon.
  * ``scripts/322_build_bible_candidates.py`` — turns the raw fetch (or
    a test fixture) into ``data/stage2/candidates/bible.jsonl`` rows
    that pass ``scripts/320_build_stage2_manifest.py --check``.

Safety posture (matches scripts/202_fetch_hawwikisource_raw.py):

  * **Dry-run by default.** Without ``--execute`` the script only enumerates
    the chapter URLs it would fetch from the registry's url_template and
    prints them. No network calls without ``--execute``.
  * ``--execute`` is gated by TWO additional preconditions to honor the
    rights-review-pending posture in
    ``data-sources/stage2-parallel-fetch-plan.json``:
      1. ``--confirm-edition <edition_or_version>`` must match the
         pinned edition in ``source_registry.json`` for the chosen side.
         The pinned edition is currently ``null`` — meaning ``--execute``
         is intentionally inert until Linus writes the pin.
      2. ``--tos-snapshot <path>`` must point at a captured ToS snapshot
         that already exists on disk under
         ``data/raw/<source_id>/<YYYYMMDD>/tos_snapshot.html``.
  * Hard caps: ``--limit`` chapters per run (default 5), polite per-side
    rate limit from the registry.
  * Raw bytes land under ``data/raw/<source_id>/<YYYYMMDD>/<book>_<chapter>.html``
    (gitignored). One JSONL line per fetched chapter appended to
    ``data/raw/<source_id>/fetch.jsonl`` using the ``ProvenanceRecord``
    shape shared with 201/202.

Stdlib only — no new requirements.

Usage::

    # Plan only (no network):
    python scripts/206_fetch_baibala_raw.py --dry-run
    python scripts/206_fetch_baibala_raw.py --dry-run --side haw --book GEN --chapters 1-3

    # Inspect the registry pin status:
    python scripts/206_fetch_baibala_raw.py --print-pin-status

    # Real fetch (only after Linus pins edition and ToS snapshot exists):
    python scripts/206_fetch_baibala_raw.py --execute --side haw \\
        --book GEN --chapters 1-3 \\
        --confirm-edition baibala-hemolele-1839 \\
        --tos-snapshot data/raw/baibala-hemolele-1839/<YYYYMMDD>/tos_snapshot.html

Exit codes::

    0 success (incl. dry-run)
    2 misuse (e.g. --execute without --confirm-edition / --tos-snapshot,
      or edition not yet pinned in the registry)
    3 fetch failure (network, short read, non-200)
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
REGISTRY_PATH = REPO_ROOT / "data-sources" / "bible" / "source_registry.json"
RAW_ROOT = REPO_ROOT / "data" / "raw"

FETCHER_TOOL = "urllib.request (stdlib); script=scripts/206_fetch_baibala_raw.py"
FETCHER_VERSION = "0.1.0"

DEFAULT_LIMIT_CHAPTERS = 5
MAX_LIMIT_CHAPTERS = 200  # hard cap so a misconfigured run cannot run away.


# ---------------------------------------------------------------------------
# Provenance schema (compatible with scripts/202_fetch_hawwikisource_raw.py)
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class ProvenanceRecord:
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
    edition_or_version: str
    source_specific_ids: dict[str, Any] = dataclasses.field(default_factory=dict)
    tos_snapshot_path: str = ""
    notes: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today_compact_utc() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d")


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def parse_chapters_spec(spec: str, max_chapter: int) -> list[int]:
    """Parse ``"1-3,5"`` style chapter specs against a book's max chapter."""
    out: list[int] = []
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", chunk)
        if not m:
            raise ValueError(f"bad chapter spec: {chunk!r}")
        a = int(m.group(1))
        b = int(m.group(2)) if m.group(2) else a
        if a < 1 or b < a or b > max_chapter:
            raise ValueError(
                f"chapter range {a}-{b} out of bounds for max_chapter={max_chapter}"
            )
        out.extend(range(a, b + 1))
    # de-dup preserving order
    seen: set[int] = set()
    uniq: list[int] = []
    for c in out:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    return uniq


def render_url(template: str, *, book_code: str, chapter: int) -> str:
    """Render a registry URL template. Supports {book_code} and {chapter[:fmt]}."""
    return template.format(book_code=book_code, chapter=chapter)


# ---------------------------------------------------------------------------
# HTTP (polite, retry-aware, stdlib only)
# ---------------------------------------------------------------------------


class FetchError(RuntimeError):
    pass


def _sleep_backoff(attempt: int, base: float = 1.5, cap: float = 30.0) -> None:
    delay = min(cap, base * (2 ** (attempt - 1))) + random.uniform(0, 0.5)
    time.sleep(delay)


def _http_get(
    url: str,
    *,
    user_agent: str,
    timeout: float = 60.0,
    max_attempts: int = 4,
) -> tuple[int, str, bytes]:
    last_exc: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        req = urllib.request.Request(url, headers={"User-Agent": user_agent})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = resp.getcode() or 0
                ctype = resp.headers.get("Content-Type", "")
                body = resp.read()
                if status != 200:
                    raise FetchError(f"HTTP {status} for {url}")
                return status, ctype, body
        except (urllib.error.URLError, FetchError, TimeoutError) as exc:
            last_exc = exc
            if attempt < max_attempts:
                _sleep_backoff(attempt)
                continue
            raise FetchError(f"giving up on {url}: {exc}") from last_exc
    raise FetchError(f"unreachable code path fetching {url}")


# ---------------------------------------------------------------------------
# Live HTML → verse parser (intentionally unimplemented; tests use fixtures)
# ---------------------------------------------------------------------------


def parse_baibala_chapter_html(html_bytes: bytes, *, book_code: str, chapter: int) -> list[dict[str, Any]]:
    """Parse one Baibala chapter HTML page into verse records.

    Contract (when implemented): returns a list of dicts shaped as
    ``{"book": <str>, "chapter": <int>, "verse": <int>, "text": <str>}``
    with ``text`` already NFC-normalized and ʻokina canonicalized to
    U+02BB. Until Frank has live HTML samples to write the parser
    against (live fetch is gated on Linus' edition pin), this raises
    NotImplementedError. The fixture-backed path in
    ``scripts/322_build_bible_candidates.py --fixture-dir`` is the
    proven extraction surface for tests.
    """
    raise NotImplementedError(
        "Live Baibala HTML parser not implemented — pending live samples after "
        "edition pin and ToS snapshot. Use --fixture-dir in 322_build_bible_candidates.py "
        "for adapter-contract tests."
    )


# ---------------------------------------------------------------------------
# Plan / fetch / pin status
# ---------------------------------------------------------------------------


def enumerate_plan(
    registry: dict[str, Any],
    *,
    side: str,
    book_codes: list[str],
    chapters_spec: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    side_cfg = registry["sides"][side]
    template = side_cfg["url_template"]
    books_index = {b["code"]: b for b in registry["books"]}
    plan: list[dict[str, Any]] = []
    for code in book_codes:
        if code not in books_index:
            raise SystemExit(f"unknown book code: {code}")
        book = books_index[code]
        max_ch = int(book["chapters"])
        chapters = (
            parse_chapters_spec(chapters_spec, max_ch)
            if chapters_spec
            else list(range(1, max_ch + 1))
        )
        for ch in chapters:
            plan.append({
                "side": side,
                "source_id": side_cfg["source_id"],
                "book_code": code,
                "book_en_name": book["en_name"],
                "book_haw_name": book.get("haw_name"),
                "chapter": ch,
                "url": render_url(template, book_code=code, chapter=ch),
                "edition_or_version": side_cfg["edition_or_version"],
                "license_observed": side_cfg["license_observed"],
                "tos_url": side_cfg["tos_url"],
                "user_agent": side_cfg["fetcher_user_agent"],
                "rate_limit_seconds": float(side_cfg["polite_rate_limit_seconds"]),
            })
            if len(plan) >= limit:
                return plan
    return plan


def assert_execute_preconditions(
    registry: dict[str, Any],
    *,
    side: str,
    confirm_edition: str | None,
    tos_snapshot: Path | None,
) -> None:
    side_cfg = registry["sides"][side]
    pinned = side_cfg.get("edition_pinned_by")
    edition = side_cfg["edition_or_version"]

    if not pinned:
        raise SystemExit(
            f"--execute refused: side={side} has no edition_pinned_by in "
            f"data-sources/bible/source_registry.json. The pin must be filled "
            f"in by Linus (data-policy review) before any live fetch. "
            f"Today's url_template_status={side_cfg.get('url_template_status')!r}."
        )
    if confirm_edition != edition:
        raise SystemExit(
            f"--execute refused: --confirm-edition={confirm_edition!r} does not match "
            f"registry edition_or_version={edition!r} for side={side}."
        )
    if tos_snapshot is None:
        raise SystemExit(
            "--execute refused: --tos-snapshot <path> is required and must point at "
            "an already-captured ToS snapshot on disk (per "
            "data-sources/stage2-parallel-fetch-plan.json acquisition_plan)."
        )
    if not tos_snapshot.exists():
        raise SystemExit(f"--execute refused: ToS snapshot not found at {tos_snapshot}")


def write_provenance(rec: ProvenanceRecord, ledger_path: Path) -> None:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(dataclasses.asdict(rec), ensure_ascii=False) + "\n")


def fetch_one(
    item: dict[str, Any],
    *,
    fetch_date: str,
    tos_snapshot: Path,
) -> ProvenanceRecord:
    user_agent = item["user_agent"]
    status, ctype, body = _http_get(item["url"], user_agent=user_agent)
    sha = hashlib.sha256(body).hexdigest()
    out_dir = RAW_ROOT / item["source_id"] / fetch_date
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{item['book_code']}_{item['chapter']:03d}.html"
    out_path.write_bytes(body)
    return ProvenanceRecord(
        source_id=item["source_id"],
        source_url=item["url"],
        fetch_timestamp_utc=_utcnow_iso(),
        http_status=status,
        content_type=ctype,
        content_length=len(body),
        raw_sha256=sha,
        raw_storage_path=str(out_path.relative_to(REPO_ROOT)),
        tos_or_license_url=item["tos_url"],
        license_observed=item["license_observed"],
        fetcher_user_agent=user_agent,
        fetcher_tool_and_version=f"{FETCHER_TOOL} v{FETCHER_VERSION}",
        edition_or_version=item["edition_or_version"],
        source_specific_ids={
            "side": item["side"],
            "book_code": item["book_code"],
            "chapter": item["chapter"],
        },
        tos_snapshot_path=str(tos_snapshot.relative_to(REPO_ROOT)) if tos_snapshot else "",
        notes="stage2 verse-aligned bible adapter (issue #16)",
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=(
            "Stage-2 Baibala Hemolele × PD English Bible raw fetcher (issue #16). "
            "Dry-run by default; --execute is gated on a registry edition pin and "
            "an on-disk ToS snapshot."
        ),
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true",
                      help="Plan only — print URLs that would be fetched. Default if neither flag given.")
    mode.add_argument("--execute", action="store_true",
                      help="Live fetch. Requires --confirm-edition and --tos-snapshot.")
    mode.add_argument("--print-pin-status", action="store_true",
                      help="Print edition-pin status for both sides and exit.")

    p.add_argument("--side", choices=("haw", "eng"), default="haw",
                   help="Which side of the pair to fetch (default: haw).")
    p.add_argument("--book", action="append", default=None,
                   help="Book code (e.g. GEN). Repeatable. Default: GEN only.")
    p.add_argument("--chapters", default="1",
                   help="Chapter spec, e.g. '1-3,5'. Default: '1'.")
    p.add_argument("--limit", type=int, default=DEFAULT_LIMIT_CHAPTERS,
                   help=f"Max chapters to fetch per run (default {DEFAULT_LIMIT_CHAPTERS}, hard cap {MAX_LIMIT_CHAPTERS}).")
    p.add_argument("--confirm-edition", default=None,
                   help="Required for --execute. Must match registry edition_or_version.")
    p.add_argument("--tos-snapshot", type=Path, default=None,
                   help="Required for --execute. Path to on-disk ToS snapshot.")
    p.add_argument("--registry", type=Path, default=REGISTRY_PATH,
                   help=f"Override registry path (default {REGISTRY_PATH.relative_to(REPO_ROOT)}).")
    args = p.parse_args(argv)

    if args.limit < 1 or args.limit > MAX_LIMIT_CHAPTERS:
        print(f"--limit must be in [1, {MAX_LIMIT_CHAPTERS}]", file=sys.stderr)
        return 2

    registry = load_registry(args.registry)

    if args.print_pin_status:
        for side, cfg in registry["sides"].items():
            print(json.dumps({
                "side": side,
                "source_id": cfg["source_id"],
                "edition_or_version": cfg["edition_or_version"],
                "edition_pinned_by": cfg.get("edition_pinned_by"),
                "edition_pinned_at_utc": cfg.get("edition_pinned_at_utc"),
                "url_template_status": cfg.get("url_template_status"),
                "rights_status_hint": cfg.get("rights_status_hint"),
            }, ensure_ascii=False))
        return 0

    book_codes = args.book or ["GEN"]
    plan = enumerate_plan(
        registry,
        side=args.side,
        book_codes=book_codes,
        chapters_spec=args.chapters,
        limit=args.limit,
    )

    if not args.execute:
        # Default: dry-run
        print(f"[DRY-RUN] side={args.side} books={book_codes} chapters={args.chapters} "
              f"-> {len(plan)} chapter URL(s) would be fetched:")
        for item in plan:
            print(f"  {item['book_code']} ch{item['chapter']:03d}  {item['url']}")
        side_cfg = registry["sides"][args.side]
        print(f"[DRY-RUN] edition_pinned_by={side_cfg.get('edition_pinned_by')!r} "
              f"url_template_status={side_cfg.get('url_template_status')!r}")
        return 0

    # Execute path
    assert_execute_preconditions(
        registry,
        side=args.side,
        confirm_edition=args.confirm_edition,
        tos_snapshot=args.tos_snapshot,
    )

    fetch_date = _today_compact_utc()
    side_cfg = registry["sides"][args.side]
    ledger_path = RAW_ROOT / side_cfg["source_id"] / "fetch.jsonl"
    rate_limit = float(side_cfg["polite_rate_limit_seconds"])

    fetched = 0
    for item in plan:
        try:
            rec = fetch_one(item, fetch_date=fetch_date, tos_snapshot=args.tos_snapshot)
        except FetchError as exc:
            print(f"fetch failed: {item['url']}: {exc}", file=sys.stderr)
            return 3
        write_provenance(rec, ledger_path)
        fetched += 1
        time.sleep(rate_limit)

    print(f"[EXECUTE] fetched {fetched} chapter(s); ledger -> {ledger_path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
