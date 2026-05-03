#!/usr/bin/env python3
"""Discover public Weblate EN↔HAW components behind a permissive-only gate.

No network is attempted unless --execute is supplied with all legal gates:
  * --instance (hosted, fedora, or all)
  * --confirm-license-allowlist equal to ALLOWLIST_SPDX_RE
  * --tos-snapshot path to a local TOS snapshot file

The executable path writes a TSV inventory under data/raw/weblate-discovery/;
that directory is gitignored. Tests should inject a mocked opener.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_OUT = REPO_ROOT / "data" / "raw" / "weblate-discovery"
ALLOWLIST_SPDX_RE = r"^(MIT|Apache-2\.0|BSD-2-Clause|BSD-3-Clause|MPL-2\.0|CC0-1\.0|CC-BY-4\.0)$"
ALLOWLIST_SPDX = re.compile(ALLOWLIST_SPDX_RE)
USER_AGENT = "ideal-spoon/0.1.0 (stage2 Weblate discovery; contact via github.com/yashasg/ideal-spoon; prototype-only)"
DEFAULT_SLEEP_SECONDS = 2.0
DEFAULT_MAX_REQUESTS_PER_MINUTE = 30

INSTANCES: dict[str, str] = {
    "hosted": "https://hosted.weblate.org",
    "fedora": "https://translate.fedoraproject.org",
}

TSV_FIELDS = [
    "instance", "base_url", "project_slug", "component_slug", "source_language",
    "target_language", "license_spdx", "license_url", "accepted", "project_api_url",
    "component_api_url", "download_tmx_url", "fetched_at", "tos_snapshot_sha256",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def is_license_allowed(spdx: str | None) -> bool:
    return bool(spdx and ALLOWLIST_SPDX.fullmatch(spdx.strip()))


def _sleep_interval(max_requests_per_minute: int, min_sleep_seconds: float) -> float:
    if max_requests_per_minute < 1:
        raise ValueError("max_requests_per_minute must be >= 1")
    return max(min_sleep_seconds, 60.0 / max_requests_per_minute)


def fetch_json(url: str, *, opener: Callable[..., Any] = urllib.request.urlopen, sleep_fn: Callable[[float], None] = time.sleep, sleep_seconds: float = DEFAULT_SLEEP_SECONDS) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with opener(req, timeout=120) as resp:
        body = resp.read()
    sleep_fn(sleep_seconds)
    return json.loads(body.decode("utf-8"))


def paged_results(url: str, *, opener: Callable[..., Any] = urllib.request.urlopen, sleep_fn: Callable[[float], None] = time.sleep, sleep_seconds: float = DEFAULT_SLEEP_SECONDS) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    next_url: str | None = url
    while next_url:
        payload = fetch_json(next_url, opener=opener, sleep_fn=sleep_fn, sleep_seconds=sleep_seconds)
        if isinstance(payload.get("results"), list):
            rows.extend(payload["results"])
            next_url = payload.get("next")
        elif isinstance(payload, list):
            rows.extend(payload)
            next_url = None
        else:
            rows.append(payload)
            next_url = None
    return rows


def _slug_from_url(url: str) -> str:
    parts = [p for p in urllib.parse.urlparse(url).path.split("/") if p]
    return parts[-1] if parts else ""


def discover_instance(instance: str, base_url: str, *, tos_snapshot_sha256: str, opener: Callable[..., Any] = urllib.request.urlopen, sleep_fn: Callable[[float], None] = time.sleep, sleep_seconds: float = DEFAULT_SLEEP_SECONDS) -> list[dict[str, str]]:
    fetched_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    components_url = f"{base_url.rstrip('/')}/api/components/?language=haw"
    components = paged_results(components_url, opener=opener, sleep_fn=sleep_fn, sleep_seconds=sleep_seconds)
    project_cache: dict[str, dict[str, Any]] = {}
    out: list[dict[str, str]] = []

    for component in components:
        project_obj = component.get("project") or {}
        project_slug = str(component.get("project_slug") or project_obj.get("slug") or _slug_from_url(str(project_obj.get("url") or "")))
        component_slug = str(component.get("slug") or _slug_from_url(str(component.get("url") or "")))
        if not project_slug or not component_slug:
            continue
        if project_slug not in project_cache:
            project_url = f"{base_url.rstrip('/')}/api/projects/{urllib.parse.quote(project_slug)}/"
            project_cache[project_slug] = fetch_json(project_url, opener=opener, sleep_fn=sleep_fn, sleep_seconds=sleep_seconds)
        project = project_cache[project_slug]
        src_lang = component.get("source_language") or project.get("source_language") or {}
        src_code = str(src_lang.get("code") if isinstance(src_lang, dict) else src_lang or "")
        license_spdx = str(component.get("license") or project.get("license") or "").strip()
        license_url = str(component.get("license_url") or project.get("license_url") or "")
        accepted = is_license_allowed(license_spdx) and src_code in {"en", "eng", "en_US", "en_GB"}
        download_tmx_url = f"{base_url.rstrip('/')}/download/{project_slug}/{component_slug}/haw/?format=tmx"
        out.append({
            "instance": instance,
            "base_url": base_url.rstrip("/"),
            "project_slug": project_slug,
            "component_slug": component_slug,
            "source_language": src_code,
            "target_language": "haw",
            "license_spdx": license_spdx,
            "license_url": license_url,
            "accepted": "true" if accepted else "false",
            "project_api_url": f"{base_url.rstrip('/')}/api/projects/{project_slug}/",
            "component_api_url": str(component.get("url") or ""),
            "download_tmx_url": download_tmx_url,
            "fetched_at": fetched_at,
            "tos_snapshot_sha256": tos_snapshot_sha256,
        })
    return out


def write_inventory(rows: list[dict[str, str]], out_dir: Path = RAW_OUT) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = out_dir / f"weblate_haw_inventory_{stamp}.tsv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=TSV_FIELDS, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def _validate_execute_gates(args: argparse.Namespace) -> tuple[bool, str]:
    if not args.execute:
        return False, "refusing: discovery performs live HTTP only with --execute and legal gates"
    if args.instance not in {"hosted", "fedora", "all"}:
        return False, "refusing: --instance must be hosted, fedora, or all"
    if args.confirm_license_allowlist != ALLOWLIST_SPDX_RE:
        return False, "refusing: --confirm-license-allowlist must exactly match the permissive SPDX allowlist"
    if not args.tos_snapshot:
        return False, "refusing: --tos-snapshot local file is required before HTTP discovery"
    if not Path(args.tos_snapshot).is_file():
        return False, "refusing: --tos-snapshot does not exist as a local file"
    return True, "ok"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Discover permissive-only Weblate EN↔HAW components.")
    ap.add_argument("--execute", action="store_true", help="Enable live Weblate API discovery after gates pass.")
    ap.add_argument("--instance", choices=["hosted", "fedora", "all"], default="all")
    ap.add_argument("--confirm-license-allowlist", default="")
    ap.add_argument("--tos-snapshot", default="")
    ap.add_argument("--sleep-seconds", type=float, default=DEFAULT_SLEEP_SECONDS)
    ap.add_argument("--max-requests-per-minute", type=int, default=DEFAULT_MAX_REQUESTS_PER_MINUTE)
    args = ap.parse_args(argv)

    ok, msg = _validate_execute_gates(args)
    if not ok:
        print(msg, file=sys.stderr)
        return 2

    sleep_seconds = _sleep_interval(args.max_requests_per_minute, args.sleep_seconds)
    tos_sha = sha256_file(Path(args.tos_snapshot))
    keys = ["hosted", "fedora"] if args.instance == "all" else [args.instance]
    rows: list[dict[str, str]] = []
    for key in keys:
        rows.extend(discover_instance(key, INSTANCES[key], tos_snapshot_sha256=tos_sha, sleep_seconds=sleep_seconds))
    out = write_inventory(rows)
    accepted = sum(1 for row in rows if row["accepted"] == "true")
    print(f"wrote {len(rows)} rows ({accepted} accepted) -> {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
