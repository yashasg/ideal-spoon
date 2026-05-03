#!/usr/bin/env python3
"""Stage-2 kaikki Hawaiian Wiktionary candidate builder (Frank).

Reads the kaikki.org Hawaiian Wiktionary JSONL dump fetched into
``data/raw/kaikki-haw-en-wiktionary/<YYYYMMDD>/`` and emits dictionary-example
candidate rows where each row is an ``(haw, en)`` example pair extracted from
``senses[].examples[]`` — i.e., the entry sense provides an explicit Hawaiian
example sentence with an English translation.

Precision policy:

  * Only emit rows where the example has BOTH ``text`` (Hawaiian) and
    ``english`` (translation) fields populated and non-trivial (>=2 chars
    each, not identical).
  * Monolingual definitions (sense glosses without examples) are NOT
    converted into parallel rows. Glosses are NOT translations of
    headwords in the manifest sense.
  * Duplicate (haw_clean, en_clean) example pairs collapse to the first
    occurrence (later occurrences would only differ by entry/sense
    metadata, not by content).

Rights: Wiktionary content is dual-licensed CC-BY-SA-4.0 / GFDL-1.3+.
The kaikki dump packages that content; provenance URL is the per-entry
Wiktionary page reconstructed from ``word``.

Output (gitignored):

    data/stage2/candidates/kaikki_wiktionary.jsonl

Usage::

    python3 scripts/323_build_kaikki_candidates.py --dry-run
    python3 scripts/323_build_kaikki_candidates.py --execute
    python3 scripts/323_build_kaikki_candidates.py --execute --fetch-date 20260501

Exit codes: 0 success, 2 misuse, 3 input error.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
import unicodedata
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
CODE_ROOT = REPO_ROOT / "code"
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))
from llm_hawaii.stage2_canonical import (  # noqa: E402
    canonical_en as stage2_canonical_en,
    canonical_haw as stage2_canonical_haw,
    compute_pair_hash as stage2_compute_pair_hash,
    sha256_text as stage2_sha256_text,
)
RAW_ROOT = REPO_ROOT / "data" / "raw" / "kaikki-haw-en-wiktionary"
DEFAULT_OUT = REPO_ROOT / "data" / "stage2" / "candidates" / "kaikki_wiktionary.jsonl"

SOURCE_ID = "kaikki-haw-en-wiktionary"
MANIFEST_SCHEMA_VERSION = "stage2.v0"
LICENSE = "CC-BY-SA-4.0 / GFDL-1.3+"
DUMP_FILENAME = "kaikki.org-dictionary-Hawaiian.jsonl"

OKINA = "\u02bb"


def normalize_haw(text: str) -> str:
    return stage2_canonical_haw(text)


def normalize_en(text: str) -> str:
    return stage2_canonical_en(text)


def sha256_text(text: str) -> str:
    return stage2_sha256_text(text)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def compute_pair_hash(sha256_en_clean: str, sha256_haw_clean: str) -> str:
    return stage2_compute_pair_hash(sha256_en_clean, sha256_haw_clean)


def _today_compact_utc() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d")


def _resolve_dump_path(fetch_date: str | None) -> Path:
    if fetch_date:
        return RAW_ROOT / fetch_date / DUMP_FILENAME
    candidates = sorted(p for p in RAW_ROOT.glob("*/" + DUMP_FILENAME) if p.is_file())
    if not candidates:
        raise SystemExit(
            f"no kaikki dump found under {RAW_ROOT}/<date>/{DUMP_FILENAME} ; "
            f"run scripts/207_fetch_stage2_parallel_raw.py --execute --source kaikki-haw-en-wiktionary first"
        )
    return candidates[-1]


def _wiktionary_url(word: str) -> str:
    from urllib.parse import quote
    return f"https://en.wiktionary.org/wiki/{quote(word)}#Hawaiian"


def iter_example_pairs(dump_path: Path) -> Iterable[tuple[dict[str, Any], dict[str, Any], int]]:
    """Yield (entry, example, sense_index) for senses with bilingual examples."""
    with dump_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("lang_code") != "haw":
                continue
            for si, sense in enumerate(entry.get("senses", []) or []):
                for ex in sense.get("examples", []) or []:
                    haw_text = ex.get("text")
                    en_text = ex.get("english")
                    if not haw_text or not en_text:
                        continue
                    yield entry, {"text": haw_text, "english": en_text,
                                  "type": ex.get("type"), "ref": ex.get("ref"),
                                  "sense_index": si}, si


def build_candidate_row(
    entry: dict[str, Any],
    example: dict[str, Any],
    fetch_date: str,
    raw_sha256: str,
) -> dict[str, Any] | None:
    haw_raw = example["text"]
    en_raw = example["english"]
    haw_clean = normalize_haw(haw_raw)
    en_clean = normalize_en(en_raw)
    if len(haw_clean) < 2 or len(en_clean) < 2:
        return None
    if haw_clean == en_clean:
        return None

    sha_haw_clean = sha256_text(haw_clean)
    sha_en_clean = sha256_text(en_clean)
    sha_pair = compute_pair_hash(sha_en_clean, sha_haw_clean)
    sha_haw_raw = sha256_text(haw_raw)
    sha_en_raw = sha256_text(en_raw)

    haw_tokens = len(haw_clean.split()) or 1
    en_tokens = len(en_clean.split()) or 1
    length_ratio = round(haw_tokens / en_tokens, 4)

    word = entry.get("word", "")
    si = example["sense_index"]
    pair_id = f"kaikki:{word}:{si}:{sha_pair[:12]}"
    record_id = f"{word}:{si}"

    notes_bits = [f"kaikki haw Wiktionary entry word={word!r}",
                  f"pos={entry.get('pos','?')}",
                  f"sense_index={si}"]
    ref = example.get("ref")
    if ref:
        notes_bits.append(f"ref={ref!r}")
    notes_bits.append(f"License: {LICENSE}.")

    row = {
        "pair_id": pair_id,
        "source": SOURCE_ID,
        "source_url_en": _wiktionary_url(word),
        "source_url_haw": _wiktionary_url(word),
        "fetch_date": fetch_date,
        "sha256_en_raw": sha_en_raw,
        "sha256_haw_raw": sha_haw_raw,
        "sha256_en_clean": sha_en_clean,
        "sha256_haw_clean": sha_haw_clean,
        "sha256_pair": sha_pair,
        "record_id_en": record_id,
        "record_id_haw": record_id,
        "text_en": en_clean,
        "text_haw": haw_clean,
        "text_en_path": None,
        "text_haw_path": None,
        "alignment_type": "dictionary-example",
        "alignment_method": "manual",
        "alignment_model": None,
        "alignment_score": None,
        "alignment_review_required": False,
        "length_ratio_haw_over_en": length_ratio,
        "lang_id_en": "en",
        "lang_id_en_confidence": 1.0,
        "lang_id_haw": "haw",
        "lang_id_haw_confidence": 1.0,
        "direction_original": "unknown",
        "register": "dictionary-example",
        "edition_or_version": None,
        "synthetic": False,
        "synthetic_source_model": None,
        "license_observed_en": LICENSE,
        "license_observed_haw": LICENSE,
        "license_inferred": None,
        "tos_snapshot_id": None,
        "prototype_only": True,
        "release_eligible": False,
        "dedup_cluster_id": pair_id,
        "crosslink_stage1_overlap": False,
        "split": "review-pending",
        "notes": " ".join(notes_bits),
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "kaikki_word": word,
        "kaikki_pos": entry.get("pos"),
        "kaikki_sense_index": si,
        "kaikki_dump_sha256": raw_sha256,
    }
    return row


def build_rows(dump_path: Path, fetch_date: str) -> list[dict[str, Any]]:
    raw_sha256 = sha256_bytes(dump_path.read_bytes())
    rows: list[dict[str, Any]] = []
    seen_pair_hashes: set[str] = set()
    for entry, example, _si in iter_example_pairs(dump_path):
        row = build_candidate_row(entry, example, fetch_date, raw_sha256)
        if row is None:
            continue
        if row["sha256_pair"] in seen_pair_hashes:
            continue
        seen_pair_hashes.add(row["sha256_pair"])
        rows.append(row)
    return rows


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true", help="parse + count, do not write")
    g.add_argument("--execute", action="store_true", help="write candidate JSONL")
    p.add_argument("--fetch-date", default=None,
                   help="raw fetch date subdir (YYYYMMDD); default = newest available")
    p.add_argument("--out", default=str(DEFAULT_OUT), help=f"output JSONL (default {DEFAULT_OUT})")
    args = p.parse_args(argv)

    dump_path = _resolve_dump_path(args.fetch_date)
    fetch_date = args.fetch_date or dump_path.parent.name
    print(f"[kaikki] using dump: {dump_path}", file=sys.stderr)
    rows = build_rows(dump_path, fetch_date)
    print(f"[kaikki] extracted {len(rows)} bilingual example rows", file=sys.stderr)

    if args.dry_run:
        if rows:
            print("[kaikki] sample row:", json.dumps(rows[0], ensure_ascii=False)[:300], file=sys.stderr)
        return 0

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"[kaikki] wrote {len(rows)} rows -> {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
