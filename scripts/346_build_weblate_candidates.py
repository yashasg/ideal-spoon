#!/usr/bin/env python3
"""Build Stage-2 candidate rows from permissive-only Weblate TMX inventory.

Default safe path is --self-test only: it parses a tiny inline TMX fixture and
performs no network or data writes. Live downloads require --execute plus three
explicit gates: inventory path, exact SPDX allowlist confirmation, and a local
TOS snapshot file.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import importlib.util
import json
import re
import sys
import time
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable, Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "data" / "stage2" / "candidates" / "weblate.jsonl"
ALLOWLIST_SPDX_RE = r"^(MIT|Apache-2\.0|BSD-2-Clause|BSD-3-Clause|MPL-2\.0|CC0-1\.0|CC-BY-4\.0)$"
ALLOWLIST_SPDX = re.compile(ALLOWLIST_SPDX_RE)
SOURCE = "weblate"
MANIFEST_SCHEMA_VERSION = "stage2.v0"
TOS_SNAPSHOT_ID = "weblate_tos_snapshot"
USER_AGENT = "ideal-spoon/0.1.0 (stage2 Weblate TMX adapter; contact via github.com/yashasg/ideal-spoon; prototype-only)"
DEFAULT_SLEEP_SECONDS = 2.0
DEFAULT_MAX_REQUESTS_PER_MINUTE = 30
OKINA = "\u02bb"
OKINA_MISENCODINGS = ("\u2018", "\u2019", "'")


def _load_stage2_manifest() -> Any:
    path = REPO_ROOT / "scripts" / "320_build_stage2_manifest.py"
    spec = importlib.util.spec_from_file_location("stage2_manifest_for_weblate", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod

_STAGE2 = _load_stage2_manifest()
compute_pair_hash = _STAGE2.compute_pair_hash
sha256_text = _STAGE2.sha256_text


def normalize_en(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


def normalize_haw(text: str) -> str:
    out = unicodedata.normalize("NFC", text)
    for bad in OKINA_MISENCODINGS:
        out = out.replace(bad, OKINA)
    return " ".join(unicodedata.normalize("NFC", out).split())


def length_ratio(haw: str, en: str) -> float:
    return round(len(haw) / max(1, len(en)), 6)


def is_license_allowed(spdx: str | None) -> bool:
    return bool(spdx and ALLOWLIST_SPDX.fullmatch(spdx.strip()))


def _lang_matches(lang: str, wanted: set[str]) -> bool:
    lang_norm = lang.replace("_", "-").casefold()
    return lang_norm in {x.replace("_", "-").casefold() for x in wanted}


def parse_tmx(tmx_text: str) -> list[dict[str, str]]:
    root = ET.fromstring(tmx_text)
    rows: list[dict[str, str]] = []
    for idx, tu in enumerate(root.findall(".//tu")):
        tu_id = str(tu.get("tuid") or tu.get("id") or f"tu{idx + 1}")
        en = ""
        haw = ""
        for tuv in tu.findall("tuv"):
            lang = str(tuv.get("{http://www.w3.org/XML/1998/namespace}lang") or tuv.get("lang") or "")
            seg_el = tuv.find("seg")
            seg = "" if seg_el is None else "".join(seg_el.itertext())
            if _lang_matches(lang, {"en", "eng", "en-US", "en-GB"}):
                en = seg
            elif _lang_matches(lang, {"haw"}):
                haw = seg
        if en.strip() and haw.strip():
            rows.append({"tu_id": tu_id, "en": en, "haw": haw})
    return rows


def source_id_for(instance: str, project_slug: str, component_slug: str, tu_id: str) -> str:
    safe = lambda s: re.sub(r"[^A-Za-z0-9_.:-]+", "-", s.strip())
    return f"weblate:{safe(instance)}:{safe(project_slug)}:{safe(component_slug)}:{safe(tu_id)}"


def build_candidate_row(unit: dict[str, str], inventory: dict[str, str], raw_tmx_sha256: str) -> dict[str, Any] | None:
    license_spdx = inventory.get("license_spdx", "").strip()
    if not is_license_allowed(license_spdx):
        return None
    en_raw = unit["en"]
    haw_raw = unit["haw"]
    en_clean = normalize_en(en_raw)
    haw_clean = normalize_haw(haw_raw)
    if not en_clean or not haw_clean:
        return None
    sha_en_raw = sha256_text(unicodedata.normalize("NFC", en_raw))
    sha_haw_raw = sha256_text(unicodedata.normalize("NFC", haw_raw))
    sha_en_clean = sha256_text(en_clean)
    sha_haw_clean = sha256_text(haw_clean)
    sid = source_id_for(inventory["instance"], inventory["project_slug"], inventory["component_slug"], unit["tu_id"])
    source_url = inventory.get("download_tmx_url") or f"{inventory.get('base_url','').rstrip('/')}/projects/{inventory['project_slug']}/{inventory['component_slug']}/haw/"
    fetched = inventory.get("fetched_at") or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fetch_date = fetched[:10].replace("-", "") if len(fetched) >= 10 else dt.date.today().strftime("%Y%m%d")
    return {
        "pair_id": sid,
        "source_id": sid,
        "source": SOURCE,
        "source_url_en": source_url,
        "source_url_haw": source_url,
        "fetch_date": fetch_date,
        "sha256_en_raw": sha_en_raw,
        "sha256_haw_raw": sha_haw_raw,
        "sha256_en_clean": sha_en_clean,
        "sha256_haw_clean": sha_haw_clean,
        "sha256_pair": compute_pair_hash(sha_en_clean, sha_haw_clean),
        "record_id_en": f"{sid}:en",
        "record_id_haw": f"{sid}:haw",
        "text_en": en_clean,
        "text_haw": haw_clean,
        "text_en_path": None,
        "text_haw_path": None,
        "alignment_type": "parallel-sentence",
        "alignment_method": "tmx-line",
        "alignment_model": None,
        "alignment_score": None,
        "alignment_review_required": True,
        "length_ratio_haw_over_en": length_ratio(haw_clean, en_clean),
        "lang_id_en": "en",
        "lang_id_en_confidence": 1.0,
        "lang_id_haw": "haw",
        "lang_id_haw_confidence": 1.0,
        "direction_original": "en->haw",
        "register": "software-l10n",
        "edition_or_version": f"{inventory.get('instance')}@{inventory.get('project_slug')}/{inventory.get('component_slug')}/haw; license={license_spdx}",
        "synthetic": False,
        "synthetic_source_model": None,
        "license_observed_en": license_spdx,
        "license_observed_haw": license_spdx,
        "license_url": inventory.get("license_url", ""),
        "license_inferred": None,
        "tos_snapshot_id": TOS_SNAPSHOT_ID,
        "prototype_only": True,
        "release_eligible": False,
        "dedup_cluster_id": sid,
        "crosslink_stage1_overlap": False,
        "split": "review-pending",
        "notes": f"Weblate public TMX unit; raw_tmx_sha256={raw_tmx_sha256}; component license={license_spdx}; permissive-only allowlist gate applied.",
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "alignment_confidence_tier": None,
        "quality_flags": None,
        "manual_review_reasons": None,
        "alignment_score_components": None,
        "policy_version": None,
    }


def read_inventory(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def accepted_inventory_rows(rows: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    out = []
    for row in rows:
        if row.get("accepted") == "true" and is_license_allowed(row.get("license_spdx")):
            out.append(row)
    return out


def fetch_bytes(url: str, *, opener: Callable[..., Any] = urllib.request.urlopen, sleep_fn: Callable[[float], None] = time.sleep, sleep_seconds: float = DEFAULT_SLEEP_SECONDS) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/x-tmx+xml,application/xml,text/xml,*/*"})
    with opener(req, timeout=120) as resp:
        body = resp.read()
    sleep_fn(sleep_seconds)
    return body


def build_rows_from_inventory(inventory_rows: list[dict[str, str]], *, opener: Callable[..., Any] = urllib.request.urlopen, sleep_fn: Callable[[float], None] = time.sleep, sleep_seconds: float = DEFAULT_SLEEP_SECONDS) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for inv in accepted_inventory_rows(inventory_rows):
        url = inv.get("download_tmx_url")
        if not url:
            continue
        body = fetch_bytes(url, opener=opener, sleep_fn=sleep_fn, sleep_seconds=sleep_seconds)
        raw_sha = hashlib.sha256(body).hexdigest()
        for unit in parse_tmx(body.decode("utf-8")):
            row = build_candidate_row(unit, inv, raw_sha)
            if row is not None:
                rows.append(row)
    return rows


def _validate_execute_gates(args: argparse.Namespace) -> tuple[bool, str]:
    if not args.execute:
        return False, "refusing: content fetch/write requires --execute; use --self-test for dry-run validation"
    if not args.inventory or not Path(args.inventory).is_file():
        return False, "refusing: --inventory TSV is required and must exist"
    if args.confirm_license_allowlist != ALLOWLIST_SPDX_RE:
        return False, "refusing: --confirm-license-allowlist must exactly match the permissive SPDX allowlist"
    if not args.tos_snapshot or not Path(args.tos_snapshot).is_file():
        return False, "refusing: --tos-snapshot local file is required before fetching TMX"
    return True, "ok"


def _sleep_interval(max_requests_per_minute: int, min_sleep_seconds: float) -> float:
    if max_requests_per_minute < 1:
        raise ValueError("max_requests_per_minute must be >= 1")
    return max(min_sleep_seconds, 60.0 / max_requests_per_minute)


_SELFTEST_TMX = """<?xml version='1.0' encoding='UTF-8'?>
<tmx version='1.4'><body>
  <tu tuid='menu.open'><tuv xml:lang='en'><seg>Open settings</seg></tuv><tuv xml:lang='haw'><seg>E wehe i na ho'onohonoho</seg></tuv></tu>
  <tu tuid='empty'><tuv xml:lang='en'><seg>Exit</seg></tuv><tuv xml:lang='haw'><seg></seg></tuv></tu>
</body></tmx>
"""


def self_test() -> int:
    assert is_license_allowed("MIT")
    assert is_license_allowed("Apache-2.0")
    assert not is_license_allowed("GPL-3.0-or-later")
    units = parse_tmx(_SELFTEST_TMX)
    assert len(units) == 1
    inv = {
        "instance": "hosted",
        "base_url": "https://hosted.weblate.org",
        "project_slug": "demo",
        "component_slug": "app",
        "license_spdx": "MIT",
        "license_url": "https://spdx.org/licenses/MIT.html",
        "download_tmx_url": "https://hosted.weblate.org/download/demo/app/haw/?format=tmx",
        "fetched_at": "2026-05-03T00:00:00Z",
        "accepted": "true",
    }
    row = build_candidate_row(units[0], inv, hashlib.sha256(_SELFTEST_TMX.encode()).hexdigest())
    assert row is not None
    assert row["pair_id"] == "weblate:hosted:demo:app:menu.open"
    assert "hoʻonohonoho" in row["text_haw"]
    assert row["sha256_pair"] == compute_pair_hash(row["sha256_en_clean"], row["sha256_haw_clean"])
    real_violations = [v for v in _STAGE2.validate_row(row) if not v.startswith("type:alignment_") and v not in {"type:quality_flags=NoneType", "type:manual_review_reasons=NoneType", "type:policy_version=NoneType"}]
    assert real_violations == [], real_violations
    print("self-test: Weblate TMX fixture parsed and canonical row built", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build Stage-2 Weblate candidates from a permissive inventory TSV.")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-test", action="store_true")
    mode.add_argument("--execute", action="store_true")
    ap.add_argument("--inventory", default="")
    ap.add_argument("--confirm-license-allowlist", default="")
    ap.add_argument("--tos-snapshot", default="")
    ap.add_argument("--sleep-seconds", type=float, default=DEFAULT_SLEEP_SECONDS)
    ap.add_argument("--max-requests-per-minute", type=int, default=DEFAULT_MAX_REQUESTS_PER_MINUTE)
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    ok, msg = _validate_execute_gates(args)
    if not ok:
        print(msg, file=sys.stderr)
        return 2

    rows = build_rows_from_inventory(read_inventory(Path(args.inventory)), sleep_seconds=_sleep_interval(args.max_requests_per_minute, args.sleep_seconds))
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} rows -> {OUT_PATH}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
