#!/usr/bin/env python3
"""Gated Tatoeba haw↔eng refresh adapter.

Dry-run/self-test mode uses inline fixtures only. Live refresh requires
``--execute`` plus exact edition date, CC-BY-2.0-FR confirmation, and a local
ToS snapshot. The adapter fetches public Tatoeba exports politely (custom UA,
>=2s sleep), dedupes against the existing pinned Tatoeba candidate file by
Tatoeba id, and writes only a new refresh JSONL under data/stage2/candidates/.

Default refresh threshold: run only when the deduped pair delta is at least 5%
of existing direct Tatoeba pairs OR the new Hawaiian sentence count is at least
500. Override with ``--min-pair-delta-pct`` and ``--min-new-sentences``.
"""
from __future__ import annotations

import argparse
import bz2
import csv
import datetime as dt
import hashlib
import importlib.util
import json
import math
import re
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path
from typing import Any, Callable, Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
EXISTING_TATOEBA = REPO_ROOT / "data" / "stage2" / "candidates" / "tatoeba.jsonl"
OUT_TEMPLATE = REPO_ROOT / "data" / "stage2" / "candidates" / "tatoeba_refresh_{date}.jsonl"
PINNED_DUMP = REPO_ROOT / "data-sources" / "tatoeba" / "PINNED_DUMP.json"
LICENSE_CONFIRM = "CC-BY-2.0-FR"
LICENSE_OBSERVED = "CC-BY 2.0 FR"
LICENSE_URL = "https://tatoeba.org/en/terms_of_use"
SOURCE = "tatoeba"
MANIFEST_SCHEMA_VERSION = "stage2.v0"
USER_AGENT = "ideal-spoon/0.1.0 (Tatoeba refresh adapter; contact via github.com/yashasg/ideal-spoon; prototype-only)"
DEFAULT_SLEEP_SECONDS = 2.0
DEFAULT_MIN_PAIR_DELTA_PCT = 0.05
DEFAULT_MIN_NEW_SENTENCES = 500
OKINA = "\u02bb"
OKINA_MISENCODINGS = ("\u2018", "\u2019", "'")

HAW_SENTENCES_URL = "https://downloads.tatoeba.org/exports/per_language/haw/haw_sentences_detailed.tsv.bz2"
LINKS_URL = "https://downloads.tatoeba.org/exports/per_language/haw/haw-eng_links.tsv.bz2"
ENG_SENTENCES_URL = "https://downloads.tatoeba.org/exports/per_language/eng/eng_sentences_detailed.tsv.bz2"


def _load_stage2_manifest() -> Any:
    path = REPO_ROOT / "scripts" / "320_build_stage2_manifest.py"
    spec = importlib.util.spec_from_file_location("stage2_manifest_for_tatoeba_refresh", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


_STAGE2 = _load_stage2_manifest()
compute_pair_hash = _STAGE2.compute_pair_hash
sha256_text = _STAGE2.sha256_text


def current_pinned_edition() -> str:
    if not PINNED_DUMP.exists():
        return "unknown"
    return str(json.loads(PINNED_DUMP.read_text(encoding="utf-8")).get("dump_date", "unknown"))


def normalize_en(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


def normalize_haw(text: str) -> str:
    out = unicodedata.normalize("NFC", text)
    for bad in OKINA_MISENCODINGS:
        out = out.replace(bad, OKINA)
    return " ".join(unicodedata.normalize("NFC", out).split())


def length_ratio(haw: str, en: str) -> float:
    return round(len(haw) / max(1, len(en)), 6)


def parse_sentences_detailed(text: str, *, lang_filter: str | None = None) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 3:
            continue
        sid, lang, sent = parts[0].strip(), parts[1].strip(), parts[2].strip()
        if not sid or not sent or (lang_filter and lang != lang_filter):
            continue
        rows[sid] = {
            "sentence_id": sid,
            "lang": lang,
            "text": sent,
            "username": parts[3].strip() if len(parts) > 3 else "",
            "date_added": parts[4].strip() if len(parts) > 4 else "",
        }
    return rows


def parse_links(text: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        # Tatoeba per-language links are TSV; accept CSV fixtures too.
        dialect = csv.excel_tab if "\t" in raw else csv.excel
        fields = next(csv.reader([raw], dialect=dialect))
        if len(fields) >= 2 and fields[0].strip() and fields[1].strip():
            pairs.append((fields[0].strip(), fields[1].strip()))
    return pairs


def tatoeba_id(haw_id: str, eng_id: str) -> str:
    return f"{haw_id}-{eng_id}"


def source_id_for(haw_id: str, eng_id: str, date: str) -> str:
    return f"tatoeba:{tatoeba_id(haw_id, eng_id)}:rev:{date}"


def build_candidate_row(haw_row: dict[str, str], eng_row: dict[str, str], *, edition_date: str) -> dict[str, Any]:
    haw_id = haw_row["sentence_id"]
    eng_id = eng_row["sentence_id"]
    tid = tatoeba_id(haw_id, eng_id)
    sid = source_id_for(haw_id, eng_id, edition_date)
    haw_raw = haw_row["text"]
    en_raw = eng_row["text"]
    haw_clean = normalize_haw(haw_raw)
    en_clean = normalize_en(en_raw)
    sha_en_raw = sha256_text(unicodedata.normalize("NFC", en_raw))
    sha_haw_raw = sha256_text(unicodedata.normalize("NFC", haw_raw))
    sha_en_clean = sha256_text(en_clean)
    sha_haw_clean = sha256_text(haw_clean)
    fetch_date = edition_date.replace("-", "")
    return {
        "pair_id": sid,
        "source_id": sid,
        "source": SOURCE,
        "source_url_en": f"https://tatoeba.org/sentences/show/{eng_id}",
        "source_url_haw": f"https://tatoeba.org/sentences/show/{haw_id}",
        "fetch_date": fetch_date,
        "sha256_en_raw": sha_en_raw,
        "sha256_haw_raw": sha_haw_raw,
        "sha256_en_clean": sha_en_clean,
        "sha256_haw_clean": sha_haw_clean,
        "sha256_pair": compute_pair_hash(sha_en_clean, sha_haw_clean),
        "record_id_en": eng_id,
        "record_id_haw": haw_id,
        "text_en": en_clean,
        "text_haw": haw_clean,
        "text_en_path": None,
        "text_haw_path": None,
        "alignment_type": "parallel-sentence",
        "alignment_method": "manual",
        "alignment_model": None,
        "alignment_score": None,
        "alignment_review_required": False,
        "length_ratio_haw_over_en": length_ratio(haw_clean, en_clean),
        "lang_id_en": "en",
        "lang_id_en_confidence": 1.0,
        "lang_id_haw": "haw",
        "lang_id_haw_confidence": 1.0,
        "direction_original": "unknown",
        "register": "unknown",
        "edition_or_version": f"tatoeba-refresh:{edition_date}; previous_pin={current_pinned_edition()}; license={LICENSE_OBSERVED}",
        "synthetic": False,
        "synthetic_source_model": None,
        "license_observed_en": LICENSE_OBSERVED,
        "license_observed_haw": LICENSE_OBSERVED,
        "license_url": LICENSE_URL,
        "license_inferred": None,
        "tos_snapshot_id": "tatoeba_terms_snapshot",
        "prototype_only": True,
        "release_eligible": False,
        "dedup_cluster_id": sid,
        "crosslink_stage1_overlap": False,
        "split": "review-pending",
        "notes": f"Tatoeba refresh {edition_date}; contributors haw={haw_row.get('username','')!r} en={eng_row.get('username','')!r}; license={LICENSE_OBSERVED}.",
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "alignment_confidence_tier": None,
        "quality_flags": None,
        "manual_review_reasons": None,
        "alignment_score_components": None,
        "policy_version": None,
        "tatoeba_id": tid,
        "tatoeba_sentence_id_haw": haw_id,
        "tatoeba_sentence_id_en": eng_id,
        "contributor_haw": haw_row.get("username", ""),
        "contributor_en": eng_row.get("username", ""),
    }


def existing_tatoeba_ids(path: Path = EXISTING_TATOEBA) -> set[str]:
    ids: set[str] = set()
    if not path.exists():
        return ids
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("tatoeba_id"):
                ids.add(str(row["tatoeba_id"]))
                continue
            haw = row.get("tatoeba_sentence_id_haw") or row.get("record_id_haw")
            en = row.get("tatoeba_sentence_id_en") or row.get("record_id_en")
            if haw and en:
                ids.add(tatoeba_id(str(haw), str(en)))
    return ids


def build_refresh_rows(haw_text: str, links_text: str, eng_text: str, *, edition_date: str, existing_ids: set[str]) -> tuple[list[dict[str, Any]], int]:
    haw = parse_sentences_detailed(haw_text, lang_filter="haw")
    eng = parse_sentences_detailed(eng_text, lang_filter="eng")
    existing_haw_ids = {tid.split("-", 1)[0] for tid in existing_ids if "-" in tid}
    new_haw_sentence_count = len(set(haw) - existing_haw_ids)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for haw_id, eng_id in parse_links(links_text):
        tid = tatoeba_id(haw_id, eng_id)
        if tid in existing_ids or tid in seen:
            continue
        if haw_id not in haw or eng_id not in eng:
            continue
        rows.append(build_candidate_row(haw[haw_id], eng[eng_id], edition_date=edition_date))
        seen.add(tid)
    return rows, new_haw_sentence_count


def threshold_allows(*, existing_pair_count: int, delta_pair_count: int, new_sentence_count: int, min_pair_delta_pct: float = DEFAULT_MIN_PAIR_DELTA_PCT, min_new_sentences: int = DEFAULT_MIN_NEW_SENTENCES) -> bool:
    if existing_pair_count <= 0:
        pair_threshold = 1
    else:
        pair_threshold = max(1, math.ceil(existing_pair_count * min_pair_delta_pct))
    return delta_pair_count >= pair_threshold or new_sentence_count >= min_new_sentences


def _fetch_bz2_text(url: str, *, opener: Callable[..., Any] = urllib.request.urlopen, sleep_fn: Callable[[float], None] = time.sleep, sleep_seconds: float = DEFAULT_SLEEP_SECONDS) -> str:
    if sleep_seconds < DEFAULT_SLEEP_SECONDS:
        raise ValueError("sleep_seconds must be at least 2.0 for Tatoeba refresh")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/x-bzip2,application/octet-stream,*/*"})
    with opener(req, timeout=180) as resp:
        raw = resp.read()
    sleep_fn(sleep_seconds)
    return bz2.decompress(raw).decode("utf-8")


def _validate_execute(args: argparse.Namespace) -> tuple[bool, str]:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.edition_date or ""):
        return False, "refusing: --edition-date must be YYYY-MM-DD"
    if args.edition_date == current_pinned_edition():
        return False, "refusing: --edition-date must be newer than the current pinned Tatoeba edition"
    if args.confirm_license != LICENSE_CONFIRM:
        return False, f"refusing: --confirm-license must be exactly {LICENSE_CONFIRM}"
    if not args.tos_snapshot or not args.tos_snapshot.is_file():
        return False, "refusing: --tos-snapshot local file is required"
    if args.sleep_seconds < DEFAULT_SLEEP_SECONDS:
        return False, "refusing: --sleep-seconds must be >=2.0"
    return True, "ok"


_SELF_HAW = """1001\thaw\t'O Hawai'i kēia.\tuser1\t2020\t2020
1002\thaw\tAloha kākou.\tuser2\t2020\t2020
1003\thaw\tHe puke kēia.\tuser3\t2020\t2020
"""
_SELF_ENG = """2001\teng\tThis is Hawaii.\tuser4\t2020\t2020
2002\teng\tHello everyone.\tuser5\t2020\t2020
2003\teng\tThis is a book.\tuser6\t2020\t2020
"""
_SELF_LINKS = """1001\t2001
1002\t2002
1003\t2003
"""


def self_test() -> int:
    existing = {"1002-2002"}
    rows, haw_count = build_refresh_rows(_SELF_HAW, _SELF_LINKS, _SELF_ENG, edition_date="2026-05-02", existing_ids=existing)
    assert haw_count == 2
    assert len(rows) == 2
    assert rows[0]["source_id"] == "tatoeba:1001-2001:rev:2026-05-02"
    assert "ʻO Hawaiʻi" in rows[0]["text_haw"]
    assert threshold_allows(existing_pair_count=20, delta_pair_count=1, new_sentence_count=0, min_pair_delta_pct=0.05) is True
    assert threshold_allows(existing_pair_count=100, delta_pair_count=4, new_sentence_count=499) is False
    for row in rows:
        scored = _STAGE2.apply_policy(dict(row))
        violations = _STAGE2.validate_row(scored)
        assert violations == [], violations
    print("self-test: Tatoeba refresh fixture deduped and canonical rows built", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Refresh Tatoeba haw↔eng candidates from a newly pinned export edition.")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-test", action="store_true")
    mode.add_argument("--execute", action="store_true")
    ap.add_argument("--edition-date", default="")
    ap.add_argument("--confirm-license", default="")
    ap.add_argument("--tos-snapshot", type=Path)
    ap.add_argument("--sleep-seconds", type=float, default=DEFAULT_SLEEP_SECONDS)
    ap.add_argument("--min-pair-delta-pct", type=float, default=DEFAULT_MIN_PAIR_DELTA_PCT)
    ap.add_argument("--min-new-sentences", type=int, default=DEFAULT_MIN_NEW_SENTENCES)
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    ok, msg = _validate_execute(args)
    if not ok:
        print(msg, file=sys.stderr)
        return 2

    existing_ids = existing_tatoeba_ids()
    haw_text = _fetch_bz2_text(HAW_SENTENCES_URL, sleep_seconds=args.sleep_seconds)
    links_text = _fetch_bz2_text(LINKS_URL, sleep_seconds=args.sleep_seconds)
    eng_text = _fetch_bz2_text(ENG_SENTENCES_URL, sleep_seconds=args.sleep_seconds)
    rows, haw_sentence_count = build_refresh_rows(haw_text, links_text, eng_text, edition_date=args.edition_date, existing_ids=existing_ids)
    if not threshold_allows(existing_pair_count=len(existing_ids), delta_pair_count=len(rows), new_sentence_count=haw_sentence_count, min_pair_delta_pct=args.min_pair_delta_pct, min_new_sentences=args.min_new_sentences):
        print(
            f"refusing: refresh threshold not met (delta_pairs={len(rows)}, existing_pairs={len(existing_ids)}, haw_sentences={haw_sentence_count}, min_pair_delta_pct={args.min_pair_delta_pct}, min_new_sentences={args.min_new_sentences})",
            file=sys.stderr,
        )
        return 2
    out = Path(str(OUT_TEMPLATE).format(date=args.edition_date))
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"wrote {len(rows)} Tatoeba refresh rows -> {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
