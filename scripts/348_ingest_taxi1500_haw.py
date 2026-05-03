#!/usr/bin/env python3
"""Eval-only Taxi1500 haw_Latn ledger ingester.

No live network is performed. ``--self-test`` uses an inline 3-row fixture and
writes only an eval-hash ledger. ``--execute`` requires a local TSV/CSV/JSONL plus
three explicit rights gates: a concrete dataset pin in ``org/repo/<40hex>`` form,
exact Apache-2.0 license confirmation, and a local ToS/license snapshot path.
This script refuses Stage-2 train candidate paths by construction.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
CODE_ROOT = REPO_ROOT / "code"
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

from llm_hawaii.eval_contamination import canonical_content_sha256  # noqa: E402

SOURCE = "taxi1500:haw_Latn"
LICENSE_SPDX = "Apache-2.0"
LICENSE_URL = "https://github.com/cisnlp/Taxi1500/blob/main/LICENSE"
DATASET_PIN_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/[0-9a-f]{40}$")
DEFAULT_LEDGER = REPO_ROOT / "data" / "evals" / "eval_hashes.jsonl"
SELFTEST_LEDGER = REPO_ROOT / "data" / "evals" / "taxi1500_haw_selftest_eval_hashes.jsonl"
TRAIN_CANDIDATES_DIR = (REPO_ROOT / "data" / "stage2" / "candidates").resolve()

# Taxi1500 is a six-way topic classification diagnostic. Labels are accepted in
# either canonical text or integer-id form so the adapter is robust to upstream
# file conventions while still enforcing six classes.
TOPIC_LABELS = ("authority", "faith", "family", "grace", "love", "sin")
_TOPIC_BY_ID = {str(i): label for i, label in enumerate(TOPIC_LABELS)}


def _utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _field(row: dict[str, Any], *names: str) -> str:
    for name in names:
        value = row.get(name)
        if value is not None and str(value) != "":
            return str(value)
    return ""


def normalize_label(label: str) -> str:
    raw = label.strip()
    mapped = _TOPIC_BY_ID.get(raw, raw.lower().replace(" ", "_"))
    if mapped not in TOPIC_LABELS:
        raise ValueError(f"Taxi1500 label must be one of {', '.join(TOPIC_LABELS)} or 0-5; got {label!r}")
    return mapped


def parse_rows(text: str, *, input_format: str = "auto") -> list[dict[str, str]]:
    fmt = input_format
    stripped = text.lstrip()
    if fmt == "auto":
        if stripped.startswith("{"):
            fmt = "jsonl"
        elif "\t" in text.splitlines()[0]:
            fmt = "tsv"
        else:
            fmt = "csv"
    if fmt == "jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    delimiter = "\t" if fmt == "tsv" else ","
    return list(csv.DictReader(text.splitlines(), delimiter=delimiter))


def build_eval_record(row: dict[str, Any], *, row_index: int) -> dict[str, Any]:
    verse_text = _field(row, "verse_text", "text", "haw", "haw_text", "sentence", "content")
    item_id = _field(row, "item_id", "id", "verse_id", "example_id") or f"row-{row_index:06d}"
    label = normalize_label(_field(row, "label", "topic", "class", "category"))
    if not verse_text:
        raise ValueError(f"row {item_id}: verse_text is required")
    return {
        "source": SOURCE,
        "item_id": item_id,
        "verse_text": verse_text,
        "label": label,
        "content_sha256": canonical_content_sha256(verse_text),
    }


def metadata_allows_eval_only(metadata: dict[str, Any]) -> bool:
    return metadata.get("license_spdx") == LICENSE_SPDX and metadata.get("eval_only") is True


def ledger_entry(record: dict[str, Any], *, dataset_pin: str, fetched_at: str) -> dict[str, Any]:
    return {
        "source": record["source"],
        "item_id": record["item_id"],
        "verse_text": record["verse_text"],
        "label": record["label"],
        "content_sha256": record["content_sha256"],
        "license_spdx": LICENSE_SPDX,
        "license_url": LICENSE_URL,
        "dataset_pin": dataset_pin,
        "fetched_at": fetched_at,
        "eval_only": True,
        "bible_overlap_candidate": True,
    }


def build_ledger_entries(rows: Iterable[dict[str, Any]], *, metadata: dict[str, Any], fetched_at: str) -> list[dict[str, Any]]:
    if not metadata_allows_eval_only(metadata):
        raise ValueError("Taxi1500 requires license_spdx=Apache-2.0 and eval_only=true")
    dataset_pin = str(metadata.get("dataset_pin") or "selftest/taxi1500/" + "0" * 40)
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(rows, 1):
        rec = build_eval_record(row, row_index=idx)
        out.append(ledger_entry(rec, dataset_pin=dataset_pin, fetched_at=fetched_at))
    return out


def refuse_train_path(path: Path) -> None:
    resolved = path.resolve()
    if resolved == TRAIN_CANDIDATES_DIR or TRAIN_CANDIDATES_DIR in resolved.parents:
        raise ValueError("refusing to write eval-only Taxi1500 hashes under data/stage2/candidates/")


def append_ledger(entries: Iterable[dict[str, Any]], ledger_path: Path) -> int:
    refuse_train_path(ledger_path)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with ledger_path.open("a", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    return count


_SELFTEST_TSV = """item_id\tverse_text\tlabel
haw-verse-001\tUa aloha ke Akua i ko ke ao nei.\tlove
haw-verse-002\tE pule mau me ka pauaho ole.\tfaith
haw-verse-003\tE waiho i ka hewa a e huli mai.\tsin
"""


def self_test(ledger_path: Path = SELFTEST_LEDGER) -> int:
    if ledger_path.exists():
        ledger_path.unlink()
    entries = build_ledger_entries(
        parse_rows(_SELFTEST_TSV, input_format="tsv"),
        metadata={"license_spdx": LICENSE_SPDX, "eval_only": True, "dataset_pin": "selftest/taxi1500/" + "0" * 40},
        fetched_at="2026-05-03T00:00:00Z",
    )
    assert len(entries) == 3
    assert all(e["bible_overlap_candidate"] is True for e in entries)
    assert len({e["content_sha256"] for e in entries}) == 3
    wrote = append_ledger(entries, ledger_path)
    assert wrote == 3 and ledger_path.exists()
    print(f"self-test: wrote {wrote} Taxi1500 eval-only hashes -> {ledger_path}", file=sys.stderr)
    return 0


def _validate_execute(args: argparse.Namespace) -> tuple[bool, str]:
    if not DATASET_PIN_RE.fullmatch(args.dataset_pin or ""):
        return False, "refusing: --dataset-pin must be org/repo/<40-hex-revision-sha>"
    if args.confirm_license_spdx != LICENSE_SPDX:
        return False, f"refusing: --confirm-license-spdx must be exactly {LICENSE_SPDX}"
    if not args.tos_snapshot or not args.tos_snapshot.is_file():
        return False, "refusing: --tos-snapshot local file is required"
    if not args.input or not args.input.is_file():
        return False, "refusing: --input local TSV/CSV/JSONL is required; no live fetch is implemented"
    try:
        refuse_train_path(args.ledger)
    except ValueError as exc:
        return False, str(exc)
    return True, "ok"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ingest Taxi1500 haw_Latn into eval_hashes.jsonl only.")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-test", action="store_true")
    mode.add_argument("--execute", action="store_true")
    ap.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    ap.add_argument("--input", type=Path)
    ap.add_argument("--input-format", choices=("auto", "tsv", "csv", "jsonl"), default="auto")
    ap.add_argument("--dataset-pin", default="")
    ap.add_argument("--confirm-license-spdx", default="")
    ap.add_argument("--tos-snapshot", type=Path)
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test(args.ledger if args.ledger != DEFAULT_LEDGER else SELFTEST_LEDGER)

    ok, msg = _validate_execute(args)
    if not ok:
        print(msg, file=sys.stderr)
        return 2

    rows = parse_rows(args.input.read_text(encoding="utf-8"), input_format=args.input_format)
    entries = build_ledger_entries(
        rows,
        metadata={"license_spdx": LICENSE_SPDX, "eval_only": True, "dataset_pin": args.dataset_pin},
        fetched_at=_utcnow(),
    )
    wrote = append_ledger(entries, args.ledger)
    print(f"wrote {wrote} eval-only Taxi1500 hashes -> {args.ledger}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
