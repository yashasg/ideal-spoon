#!/usr/bin/env python3
"""Rights-light raw-data fetcher — Wikimedia *dump* sources (Frank, issue #1).

Concrete companion to the source-specific 100-phase collection scripts:

  * ``scripts/101_collect_hawwiki.py``       → input plan for ``hawwiki``
  * ``scripts/103_collect_hawwiktionary.py`` → input plan for ``hawwiktionary``

(There is no longer a single broad ``101_collect_rightslight.py``
planner — each source owns its own collection script because the fetch
shape and per-source metadata are not interchangeable.)

This script actually pulls bytes for the dump-shaped Wikimedia sources only:

  * ``hawwiki``        — Hawaiian Wikipedia XML dump + checksum manifest
  * ``hawwiktionary``  — Hawaiian Wiktionary XML dump + checksum manifest

Hawaiian Wikisource (``hawwikisource``) lives in a sibling adapter,
``scripts/202_fetch_hawwikisource_raw.py``, with its own 100-phase
collection script ``scripts/102_collect_hawwikisource.py`` that emits
a per-page fetch plan; its fetch shape is fundamentally different —
there is no single dump file to verify against a ``sha1sums`` manifest;
instead the corpus is enumerated and pulled page-by-page through the
MediaWiki API, with rate limiting and a namespace allow-list. Keeping
the two shapes in separate scripts keeps this file's allow-list and
verify-then-store logic small and obvious.

Anything outside that allow-list (Baibala, nūpepa OCR, OHA/DOE/UH,
Awaiaulu, OPUS/NLLB, FLORES, JW300, …) is intentionally not reachable
through this script. To extend the allow-list, add a new
``10X_collect_<source>.py`` collection script and have the team review.

Scope vs. the Stage-1 token target
----------------------------------
This script covers the dump-shaped slice only. The publishable Stage-1
train-token target (~2.5M conservative / ~4.5M base / ~7M upside
Hawaiian tokens, post-clean) is **not** reachable from this script
alone — see token estimates in each source's ``collect_plan.json``
emitted by the 100-phase scripts. Closing the gap requires landing the
right-clearable expansion paths (Wikisource bulk page text via
``scripts/202_fetch_hawwikisource_raw.py``, Wikipedia interlanguage
API, Tatoeba haw), each of which needs its own adapter pass.
Rights-heavy sources are NOT used to backfill the gap.

Safety posture
--------------
* Dry-run by default. Corpus-bearing dump files (the multi-MB
  ``*-pages-articles.xml.bz2``) are downloaded **only** when
  ``--execute`` is passed. Without ``--execute`` the script prints what
  it would do and may pull tiny metadata artefacts (checksum manifest,
  dumpstatus JSON, API page listings).
* ``--metadata-only`` / ``--smoke`` force the metadata-only path even
  with ``--execute``: useful for CI or a first run.
* ``--source`` defaults to ``hawwiki`` so users can validate the
  vertical slice on the smallest, cleanest source before bulk pulling.
* Raw bytes land under ``data/raw/<source>/<fetch_date>/<sha256>.<ext>``
  which is gitignored. No corpus text in git, ever.
* Each artefact appends one JSONL line to ``data/raw/<source>/fetch.jsonl``
  with a stable schema (see ``ProvenanceRecord``) for Linus's
  downstream registration/LID/extraction workflow.
* Polite retry/backoff (stdlib, exponential w/ jitter) on transient
  HTTP errors. Partial/short downloads fail loudly — never silently
  truncated.

Stdlib only — no new requirements.

Usage
-----
::

    # Plan only — show what would be fetched for hawwiki, no bytes:
    python scripts/201_fetch_rightslight_raw.py --source hawwiki --dry-run

    # Pull only the small metadata manifests (safe smoke):
    python scripts/201_fetch_rightslight_raw.py --source hawwiki --smoke

    # Real corpus dump pull (multi-MB), explicit opt-in required:
    python scripts/201_fetch_rightslight_raw.py --source hawwiki --execute

    # All dump-shaped allow-listed sources, metadata only:
    python scripts/201_fetch_rightslight_raw.py --source all --metadata-only

    # For Hawaiian Wikisource use the sibling adapter:
    python scripts/202_fetch_hawwikisource_raw.py --metadata-only --limit 50

Exit codes: 0 success, 2 misuse / disallowed source, 3 fetch failure
(network, short read, checksum mismatch).
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

FETCHER_TOOL = "urllib.request (stdlib); script=scripts/201_fetch_rightslight_raw.py"
FETCHER_VERSION = "0.1.0"
USER_AGENT = (
    f"ideal-spoon/{FETCHER_VERSION} (frank rights-light raw fetcher; "
    "contact via github.com/yashasg/ideal-spoon issue #1)"
)
WIKIMEDIA_TOS = "https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use"
WIKIMEDIA_LICENSE = "CC BY-SA 4.0 + GFDL (per-revision; see Wikimedia Terms)"

# Allow-list. Mirrors the dump-shaped sources owned by 101/103 collect scripts.
# Keys here are short CLI-friendly source IDs; values describe each
# artefact this script knows how to pull.
ALLOWED_SOURCES: dict[str, dict[str, Any]] = {
    "hawwiki": {
        "source_name": "Hawaiian Wikipedia",
        "wiki_slug": "hawwiki",
        "metadata_artifacts": [
            {
                "kind": "sha1sums",
                "url": "https://dumps.wikimedia.org/hawwiki/latest/hawwiki-latest-sha1sums.txt",
                "ext": "txt",
                "license_observed": "Wikimedia infrastructure metadata",
            },
            # dumpstatus.json is only published under the dated dir
            # (e.g. /hawwiki/20260401/dumpstatus.json), not under
            # /latest/. The dated URL is resolved at runtime from the
            # sha1sums manifest, so it is *not* listed statically here.
        ],
        "corpus_artifacts": [
            {
                "kind": "pages-articles-xml-bz2",
                "url": "https://dumps.wikimedia.org/hawwiki/latest/hawwiki-latest-pages-articles.xml.bz2",
                "ext": "xml.bz2",
                "license_observed": WIKIMEDIA_LICENSE,
                # Manifest lists the dump under its dated name
                # (e.g. hawwiki-20260401-pages-articles.xml.bz2). We
                # match by suffix at verify time.
                "sha1sums_suffix": "-pages-articles.xml.bz2",
            },
        ],
    },
    "hawwiktionary": {
        "source_name": "Hawaiian Wiktionary",
        "wiki_slug": "hawwiktionary",
        "metadata_artifacts": [
            {
                "kind": "sha1sums",
                "url": "https://dumps.wikimedia.org/hawwiktionary/latest/hawwiktionary-latest-sha1sums.txt",
                "ext": "txt",
                "license_observed": "Wikimedia infrastructure metadata",
            },
        ],
        "corpus_artifacts": [
            {
                "kind": "pages-articles-xml-bz2",
                "url": "https://dumps.wikimedia.org/hawwiktionary/latest/hawwiktionary-latest-pages-articles.xml.bz2",
                "ext": "xml.bz2",
                "license_observed": WIKIMEDIA_LICENSE,
                "sha1sums_suffix": "-pages-articles.xml.bz2",
            },
        ],
    },
    # NOTE: hawwikisource intentionally lives in
    # scripts/202_fetch_hawwikisource_raw.py — its fetch shape (paginated
    # MediaWiki API enumeration + per-page wikitext, rate-limited) does not
    # belong in this dump-and-verify allow-list. Adding it back here would
    # mix two unrelated control flows.
}


# ---------------------------------------------------------------------------
# Provenance schema (stable for Linus's downstream consumers)
# ---------------------------------------------------------------------------


@dataclass
class ProvenanceRecord:
    """One JSONL row per fetched artefact under data/raw/<source>/fetch.jsonl.

    Schema is intentionally flat and obvious. Add fields at the end;
    do not rename existing fields without coordinating with Linus.
    """

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
    """GET with polite retry. Returns (status, content_type, body).

    Raises FetchError on non-2xx terminal status, short read, or
    repeated transient failures.
    """
    last_exc: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "*/*",
                # MediaWiki etiquette: keeps replicas from serving stale.
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
    # Unreachable, but keep type-checkers happy.
    raise FetchError(f"GET failed: {url}: {last_exc!r}")


# ---------------------------------------------------------------------------
# Storage + provenance
# ---------------------------------------------------------------------------


def _source_dirs(source: str) -> tuple[Path, Path]:
    base = RAW_ROOT / source
    fetch_dir = base / _today_compact_utc()
    fetch_dir.mkdir(parents=True, exist_ok=True)
    base.mkdir(parents=True, exist_ok=True)
    return base, fetch_dir


def _write_readme(base: Path) -> None:
    readme = base / "README.txt"
    if not readme.exists():
        readme.write_text(
            "This directory is gitignored (see /data/ rule in .gitignore).\n"
            "It holds rights-light raw fetches for a single source.\n"
            "fetch.jsonl is the per-artefact provenance ledger consumed\n"
            "by downstream registration/extraction (see Linus's plan in\n"
            ".squad/orchestration-log/).\n"
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
    # Atomic-ish write: tmp then rename, prevents half-written files on crash.
    tmp_path = raw_path.with_suffix(raw_path.suffix + ".part")
    tmp_path.write_bytes(body)
    tmp_path.replace(raw_path)
    return raw_path, sha


# ---------------------------------------------------------------------------
# Wikimedia SHA1 manifest parsing (used to verify corpus pulls)
# ---------------------------------------------------------------------------


def _parse_sha1sums(text: str) -> dict[str, str]:
    """Parse a Wikimedia ``*-sha1sums.txt`` body into {filename: sha1hex}."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        sha1, name = parts[0], parts[1].strip()
        if len(sha1) == 40 and all(c in "0123456789abcdefABCDEF" for c in sha1):
            out[name] = sha1.lower()
    return out


def _sha1_hex(body: bytes) -> str:
    return hashlib.sha1(body).hexdigest()


# ---------------------------------------------------------------------------
# Per-source fetch logic
# ---------------------------------------------------------------------------


def _fetch_metadata(
    source: str,
    spec: dict[str, Any],
    *,
    aplimit: int,
    dry_run: bool,
) -> tuple[list[ProvenanceRecord], dict[str, str]]:
    """Pull metadata-shaped artefacts for one source. Returns
    (provenance records written, sha1sums table if any)."""
    base, fetch_dir = _source_dirs(source)
    _write_readme(base)
    records: list[ProvenanceRecord] = []
    sha1sums: dict[str, str] = {}
    dump_date: str | None = None  # discovered from sha1sums filenames

    artefacts = list(spec.get("metadata_artifacts", []))

    for art in artefacts:
        if "url" in art:
            url = art["url"]
        elif "url_template" in art:
            url = art["url_template"].format(aplimit=aplimit)
        else:
            continue

        if dry_run:
            print(f"  [dry-run] would GET metadata: {url}")
            continue

        status, ctype, body = _http_get(url)
        raw_path, sha = _store_bytes(fetch_dir, body, art["ext"])

        source_specific_ids: dict[str, Any] = {"artifact_kind": art["kind"]}
        if art["kind"] == "sha1sums":
            sha1sums = _parse_sha1sums(body.decode("utf-8", errors="replace"))
            source_specific_ids["files_listed"] = sorted(sha1sums.keys())
            # Derive the dump date from any dated filename in the manifest.
            wiki_slug = spec.get("wiki_slug")
            if wiki_slug:
                for fname in sha1sums:
                    parts = fname.split("-")
                    if len(parts) >= 2 and parts[0] == wiki_slug and parts[1].isdigit():
                        dump_date = parts[1]
                        break
            source_specific_ids["dump_date"] = dump_date
        elif art["kind"] == "allpages-api":
            try:
                payload = json.loads(body.decode("utf-8"))
                pages = payload.get("query", {}).get("allpages", [])
                source_specific_ids["allpages_count"] = len(pages)
                source_specific_ids["aplimit_requested"] = aplimit
            except Exception:
                pass

        rec = ProvenanceRecord(
            source_id=f"{spec['source_name']} — {art['kind']}",
            source_url=url,
            fetch_timestamp_utc=_utcnow_iso(),
            http_status=status,
            content_type=ctype,
            content_length=len(body),
            raw_sha256=sha,
            raw_storage_path=str(raw_path.relative_to(REPO_ROOT)),
            tos_or_license_url=WIKIMEDIA_TOS,
            license_observed=art["license_observed"],
            fetcher_user_agent=USER_AGENT,
            fetcher_tool_and_version=f"{FETCHER_TOOL} v{FETCHER_VERSION}",
            source_specific_ids=source_specific_ids,
            notes="metadata-only artefact; not corpus text",
        )
        _append_provenance(base, rec)
        records.append(rec)
        print(
            f"  metadata ok: {url}\n"
            f"    sha256={sha} bytes={len(body)} status={status}\n"
            f"    stored at {rec.raw_storage_path}"
        )

    # Wikimedia publishes dumpstatus.json only under the dated path,
    # not under /latest/. Resolve and fetch it now if we learned the date.
    wiki_slug = spec.get("wiki_slug")
    if wiki_slug and dump_date and not dry_run:
        ds_url = f"https://dumps.wikimedia.org/{wiki_slug}/{dump_date}/dumpstatus.json"
        try:
            status, ctype, body = _http_get(ds_url)
        except FetchError as e:
            print(f"  (dumpstatus optional fetch failed, continuing): {e}")
        else:
            raw_path, sha = _store_bytes(fetch_dir, body, "json")
            ssids: dict[str, Any] = {
                "artifact_kind": "dumpstatus",
                "dump_date": dump_date,
            }
            try:
                ds = json.loads(body.decode("utf-8"))
                ssids["dump_jobs"] = sorted(ds.get("jobs", {}).keys())
            except Exception:
                pass
            rec = ProvenanceRecord(
                source_id=f"{spec['source_name']} — dumpstatus",
                source_url=ds_url,
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
                source_specific_ids=ssids,
                notes="metadata-only artefact; not corpus text",
            )
            _append_provenance(base, rec)
            records.append(rec)
            print(
                f"  metadata ok: {ds_url}\n"
                f"    sha256={sha} bytes={len(body)} status={status}\n"
                f"    stored at {rec.raw_storage_path}"
            )

    return records, sha1sums


def _fetch_corpus(
    source: str,
    spec: dict[str, Any],
    *,
    sha1sums: dict[str, str],
    dry_run: bool,
) -> list[ProvenanceRecord]:
    base, fetch_dir = _source_dirs(source)
    records: list[ProvenanceRecord] = []

    artefacts: Iterable[dict[str, Any]] = spec.get("corpus_artifacts", [])
    if not artefacts:
        print(f"  (no corpus artefacts wired for source={source!r}; skipping)")
        return records

    for art in artefacts:
        url = art["url"]
        if dry_run:
            print(f"  [dry-run] would GET corpus: {url}")
            continue

        status, ctype, body = _http_get(url, timeout=300.0)
        # Hard-fail on SHA1 mismatch when we have a manifest entry.
        sha1_expected: str | None = None
        manifest_match: str | None = None
        if "sha1sums_key" in art:
            sha1_expected = sha1sums.get(art["sha1sums_key"])
            manifest_match = art["sha1sums_key"] if sha1_expected else None
        elif "sha1sums_suffix" in art:
            suffix = art["sha1sums_suffix"]
            for fname, h in sha1sums.items():
                if fname.endswith(suffix):
                    sha1_expected = h
                    manifest_match = fname
                    break
        sha1_actual = _sha1_hex(body)
        if sha1_expected and sha1_expected != sha1_actual:
            raise FetchError(
                f"SHA1 mismatch for {url}: "
                f"expected {sha1_expected} (manifest entry {manifest_match!r}), "
                f"got {sha1_actual}. "
                "Refusing to write a corrupt/partial dump."
            )
        raw_path, sha = _store_bytes(fetch_dir, body, art["ext"])

        rec = ProvenanceRecord(
            source_id=f"{spec['source_name']} — {art['kind']}",
            source_url=url,
            fetch_timestamp_utc=_utcnow_iso(),
            http_status=status,
            content_type=ctype,
            content_length=len(body),
            raw_sha256=sha,
            raw_storage_path=str(raw_path.relative_to(REPO_ROOT)),
            tos_or_license_url=WIKIMEDIA_TOS,
            license_observed=art["license_observed"],
            fetcher_user_agent=USER_AGENT,
            fetcher_tool_and_version=f"{FETCHER_TOOL} v{FETCHER_VERSION}",
            source_specific_ids={
                "artifact_kind": art["kind"],
                "dump_filename": manifest_match,
                "sha1_expected_from_manifest": sha1_expected,
                "sha1_actual": sha1_actual,
            },
            notes="corpus-bearing dump; verified against sha1sums manifest when available",
        )
        _append_provenance(base, rec)
        records.append(rec)
        print(
            f"  corpus ok: {url}\n"
            f"    sha256={sha} sha1={sha1_actual} bytes={len(body)} status={status}\n"
            f"    stored at {rec.raw_storage_path}"
        )
    return records


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _resolve_sources(arg: str) -> list[str]:
    if arg == "all":
        return list(ALLOWED_SOURCES.keys())
    if arg not in ALLOWED_SOURCES:
        raise SystemExit(
            f"error: --source={arg!r} is not in the rights-light allow-list "
            f"({sorted(ALLOWED_SOURCES.keys())}). "
            "Extending the allow-list requires adding a new "
            "scripts/10X_collect_<source>.py collection script and team "
            "review per issue #1."
        )
    return [arg]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Rights-light raw-data fetcher (Frank, issue #1).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--source",
        default="hawwiki",
        help="Source ID to fetch. One of: "
        f"{sorted(ALLOWED_SOURCES.keys())} or 'all'. Default: hawwiki "
        "(smallest, cleanest vertical slice).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Cap for enumerative metadata calls (reserved for future "
        "API-shaped sources; unused by the current dump-only allow-list). "
        "Default: 50.",
    )
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="Fetch only metadata/checksum/manifest artefacts. "
        "No corpus dump bodies are downloaded even with --execute.",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Alias for --metadata-only with a tight limit. "
        "Safe to run in CI; pulls only tiny rights-clear metadata.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Required to actually download corpus-bearing dump files. "
        "Without this flag the script is a dry run for corpus artefacts "
        "(metadata may still be fetched if --metadata-only or --smoke).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Force full dry-run: print planned URLs, fetch nothing.",
    )
    args = parser.parse_args(argv)

    if args.smoke:
        args.metadata_only = True
        args.limit = min(args.limit, 50)

    sources = _resolve_sources(args.source)

    print("ideal-spoon rights-light raw fetcher")
    print(f"  fetcher           : {FETCHER_TOOL} v{FETCHER_VERSION}")
    print(f"  user-agent        : {USER_AGENT}")
    print(f"  sources           : {sources}")
    print(f"  metadata_only     : {args.metadata_only}")
    print(f"  execute (corpus)  : {args.execute}")
    print(f"  dry_run           : {args.dry_run}")
    print(f"  limit             : {args.limit}")
    print(f"  raw root          : {RAW_ROOT.relative_to(REPO_ROOT)} (gitignored)")
    print()

    fetch_corpus = args.execute and not args.metadata_only

    overall_ok = True
    for source in sources:
        spec = ALLOWED_SOURCES[source]
        print(f"== source: {source} ({spec['source_name']}) ==")
        try:
            _, sha1sums = _fetch_metadata(
                source, spec, aplimit=args.limit, dry_run=args.dry_run
            )
            if fetch_corpus:
                _fetch_corpus(source, spec, sha1sums=sha1sums, dry_run=args.dry_run)
            elif spec.get("corpus_artifacts"):
                for art in spec["corpus_artifacts"]:
                    print(
                        f"  [skipped corpus] {art['url']}\n"
                        f"    pass --execute (and not --metadata-only/--smoke) "
                        "to download."
                    )
        except FetchError as e:
            overall_ok = False
            print(f"  FETCH ERROR for source={source}: {e}", file=sys.stderr)
        print()

    if not overall_ok:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
