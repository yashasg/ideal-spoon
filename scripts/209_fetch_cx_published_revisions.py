#!/usr/bin/env python3
"""Stage-2 Wikimedia Content Translation revision body fetcher (Frank).

The 207 fetcher captured only the ``cxpublishedtranslations`` API metadata
page (68 EN->HAW translation rows with translationId, sourceRevisionId,
targetRevisionId, stats — no article bodies). This script complements that
pass: for every translation that survives the Linus-confirmed
``stats.mt < 0.5 AND stats.human > 0`` gate, it pulls

* EN source revision wikitext from en.wikipedia.org/w/api.php?action=parse&oldid=<sourceRevisionId>&prop=wikitext
* HAW target revision wikitext from haw.wikipedia.org/w/api.php?action=parse&oldid=<targetRevisionId>&prop=wikitext

and writes raw JSON responses + a ``fetch.jsonl`` provenance ledger under::

    data/raw/wikimedia-cx-en-haw-published/<YYYYMMDD>/revisions/

Filenames: ``{translationId}.{side}.{revisionId}.json``.

Rate limit: <=1 req/sec to api.php (Wikimedia public API tolerates polite bursts).

Usage::

    python3 scripts/209_fetch_cx_published_revisions.py --dry-run
    python3 scripts/209_fetch_cx_published_revisions.py --execute

Exit codes: 0 success, 2 misuse, 3 fetch failure.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_ROOT = REPO_ROOT / "data" / "raw" / "wikimedia-cx-en-haw-published"
DEFAULT_INDEX_FILENAME = "api.php"

SOURCE_ID = "wikimedia-cx-en-haw-published"
LICENSE_OBSERVED = (
    "Wikipedia content CC BY-SA 4.0 + GFDL per Wikimedia Terms; CX-published "
    "targets are real Wikipedia revisions on haw.wikipedia.org with full revision "
    "history (so attribution is intrinsic). Source revisions on en.wikipedia.org "
    "are linked by sourceRevisionId."
)
TOS_URL = "https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use"
USER_AGENT = (
    "ideal-spoon/0.1.0 (stage2 cx-revision fetcher; "
    "contact via github.com/yashasg/ideal-spoon)"
)
FETCHER = "urllib.request (stdlib); script=scripts/209_fetch_cx_published_revisions.py v0.1.0"

PARSE_URL = "https://{wiki}.wikipedia.org/w/api.php?action=parse&oldid={oldid}&prop=wikitext&format=json&formatversion=2"


def _utcnow_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today_compact_utc() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d")


def _stat(t: dict, key: str) -> float:
    v = t.get("stats", {}).get(key)
    return 0.0 if v is None else float(v)


def survivors(translations: list[dict]) -> list[dict]:
    return [
        t for t in translations
        if _stat(t, "mt") < 0.5 and _stat(t, "human") > 0
    ]


def _http_get(url: str, timeout: float = 60.0, attempts: int = 4) -> tuple[int, str, bytes]:
    last_exc: BaseException | None = None
    for attempt in range(1, attempts + 1):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.headers.get("Content-Type", ""), resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt < attempts:
                time.sleep(2.0 * attempt)
                last_exc = exc
                continue
            return exc.code, exc.headers.get("Content-Type", "") if exc.headers else "", b""
        except (urllib.error.URLError, TimeoutError) as exc:
            last_exc = exc
            time.sleep(2.0 * attempt)
    raise SystemExit(f"fetch failed after {attempts} attempts: {url}: {last_exc}")


def fetch_revision(wiki: str, oldid: int, side: str, translation_id: str,
                   dest_dir: Path, prov_fh) -> dict:
    url = PARSE_URL.format(wiki=wiki, oldid=oldid)
    print(f"[cx] GET {wiki} oldid={oldid} side={side}", file=sys.stderr)
    status, ctype, body = _http_get(url)
    if status != 200 or not body:
        rec = {
            "source_id": SOURCE_ID,
            "source_url": url,
            "fetch_timestamp_utc": _utcnow_iso(),
            "http_status": status,
            "content_type": ctype,
            "content_length": len(body),
            "raw_sha256": hashlib.sha256(body).hexdigest() if body else "",
            "raw_storage_path": "",
            "tos_or_license_url": TOS_URL,
            "license_observed": LICENSE_OBSERVED,
            "fetcher_user_agent": USER_AGENT,
            "fetcher_tool_and_version": FETCHER,
            "source_specific_ids": {
                "translation_id": translation_id,
                "wiki": wiki,
                "oldid": oldid,
                "side": side,
            },
            "notes": f"non-200 from api.php; skipped persistence (status={status})",
        }
        prov_fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
        prov_fh.flush()
        return rec
    out_name = f"{translation_id}.{side}.{oldid}.json"
    out_path = dest_dir / out_name
    out_path.write_bytes(body)
    sha = hashlib.sha256(body).hexdigest()
    rec = {
        "source_id": SOURCE_ID,
        "source_url": url,
        "fetch_timestamp_utc": _utcnow_iso(),
        "http_status": status,
        "content_type": ctype,
        "content_length": len(body),
        "raw_sha256": sha,
        "raw_storage_path": str(out_path.relative_to(REPO_ROOT)),
        "tos_or_license_url": TOS_URL,
        "license_observed": LICENSE_OBSERVED,
        "fetcher_user_agent": USER_AGENT,
        "fetcher_tool_and_version": FETCHER,
        "source_specific_ids": {
            "translation_id": translation_id,
            "wiki": wiki,
            "oldid": oldid,
            "side": side,
        },
        "notes": "stage2 raw cx-revision fetch; prototype_only=true; not a public artifact",
    }
    prov_fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
    prov_fh.flush()
    return rec


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--execute", action="store_true")
    p.add_argument("--index-fetch-date", default=None,
                   help="YYYYMMDD subdir under data/raw/wikimedia-cx-en-haw-published/ "
                        "containing the api.php metadata response (default: newest)")
    p.add_argument("--out-fetch-date", default=None,
                   help="YYYYMMDD subdir to write revisions under (default: today UTC)")
    p.add_argument("--max", type=int, default=None,
                   help="cap number of translations fetched (debug)")
    args = p.parse_args(argv)

    if args.index_fetch_date:
        index_dir = RAW_ROOT / args.index_fetch_date
    else:
        candidates = sorted(p for p in RAW_ROOT.glob("*/" + DEFAULT_INDEX_FILENAME) if p.is_file())
        if not candidates:
            raise SystemExit(f"no api.php index found under {RAW_ROOT}/<date>/")
        index_dir = candidates[-1].parent
    index_path = index_dir / DEFAULT_INDEX_FILENAME
    if not index_path.exists():
        raise SystemExit(f"index file missing: {index_path}")

    with index_path.open("rb") as fh:
        meta = json.load(fh)
    translations = meta.get("result", {}).get("translations", [])
    keep = survivors(translations)
    print(f"[cx] index={index_path.relative_to(REPO_ROOT)} total={len(translations)} survivors(mt<0.5 & human>0)={len(keep)}",
          file=sys.stderr)
    if args.max is not None:
        keep = keep[: args.max]
        print(f"[cx] capped to first {len(keep)} per --max", file=sys.stderr)

    for t in keep[:5]:
        print(f"   tid={t['translationId']:>7s} src={t['sourceRevisionId']} tgt={t['targetRevisionId']} "
              f"human={_stat(t,'human'):.3f} mt={_stat(t,'mt'):.3f} title={t.get('sourceTitle')!r}",
              file=sys.stderr)
    if len(keep) > 5:
        print(f"   ... +{len(keep)-5} more", file=sys.stderr)

    if args.dry_run:
        return 0

    out_date = args.out_fetch_date or _today_compact_utc()
    dest_dir = RAW_ROOT / out_date / "revisions"
    dest_dir.mkdir(parents=True, exist_ok=True)
    prov_path = RAW_ROOT / "fetch.jsonl"
    n_ok = 0
    n_fail = 0
    with prov_path.open("a", encoding="utf-8") as prov_fh:
        for t in keep:
            tid = str(t["translationId"])
            for wiki, side, oldid_key in (
                ("en",  "en",  "sourceRevisionId"),
                ("haw", "haw", "targetRevisionId"),
            ):
                oldid_raw = t.get(oldid_key)
                if not oldid_raw:
                    print(f"[cx] tid={tid} side={side} missing {oldid_key}; skipped", file=sys.stderr)
                    n_fail += 1
                    continue
                oldid = int(oldid_raw)
                rec = fetch_revision(wiki, oldid, side, tid, dest_dir, prov_fh)
                if rec["http_status"] == 200:
                    n_ok += 1
                else:
                    n_fail += 1
                time.sleep(1.05)
    print(f"[cx] fetched ok={n_ok} fail={n_fail} -> {dest_dir.relative_to(REPO_ROOT)}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
