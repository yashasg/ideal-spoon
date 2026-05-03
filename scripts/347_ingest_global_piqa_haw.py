#!/usr/bin/env python3
"""Eval-only Global-PIQA haw_Latn ledger ingester.

No live network is performed. ``--self-test`` uses an inline 3-row fixture and
writes only an eval-hash ledger. ``--execute`` requires a local TSV plus three
explicit rights gates: exact dataset pin, exact SPDX license confirmation, and a
local ToS/license snapshot path. This script refuses Stage-2 train candidate
paths by construction.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
CODE_ROOT = REPO_ROOT / "code"
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

from llm_hawaii.eval_contamination import canonical_content_sha256  # noqa: E402

SOURCE = "global-piqa:haw_Latn"
DATASET_REPO = "mrlbenchmarks/global-piqa-parallel"
DATASET_REVISION = "a350910e9cfc8b0b57cb55aa8261780deabb6568"
DATASET_PIN = f"{DATASET_REPO}@{DATASET_REVISION}"
LICENSE_SPDX = "CC-BY-SA-4.0"
LICENSE_URL = "https://creativecommons.org/licenses/by-sa/4.0/deed.en"
DEFAULT_LEDGER = REPO_ROOT / "data" / "evals" / "eval_hashes.jsonl"
SELFTEST_LEDGER = REPO_ROOT / "data" / "evals" / "global_piqa_haw_selftest_eval_hashes.jsonl"
TRAIN_CANDIDATES_DIR = (REPO_ROOT / "data" / "stage2" / "candidates").resolve()


def _utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _field(row: dict[str, str], *names: str) -> str:
    for name in names:
        if name in row and row[name] != "":
            return row[name]
    return ""


def parse_tsv(tsv_text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(tsv_text.splitlines(), delimiter="\t"))


def build_eval_record(row: dict[str, str], *, row_index: int) -> dict[str, Any]:
    choices = [_field(row, f"solution{i}", f"choice{i}") for i in range(4)]
    prompt = _field(row, "prompt", "haw_prompt")
    item_id = _field(row, "example_id", "id", "item_id") or f"row-{row_index:06d}"
    label = _field(row, "label", "gold", "answer")
    gold: int | str
    try:
        gold = int(label)
    except ValueError:
        gold = label
    if not prompt or any(choice == "" for choice in choices):
        raise ValueError(f"row {item_id}: prompt and four choices are required")
    return {
        "source": SOURCE,
        "item_id": item_id,
        "prompt": prompt,
        "choices": choices,
        "gold": gold,
        "content_sha256": canonical_content_sha256({"prompt": prompt, "choices": choices}),
    }


def metadata_allows_eval_only(metadata: dict[str, Any]) -> bool:
    return metadata.get("license_spdx") == LICENSE_SPDX and metadata.get("eval_only") is True


def ledger_entry(record: dict[str, Any], *, dataset_revision: str, fetched_at: str) -> dict[str, Any]:
    return {
        "source": record["source"],
        "item_id": record["item_id"],
        "content_sha256": record["content_sha256"],
        "license_spdx": LICENSE_SPDX,
        "license_url": LICENSE_URL,
        "dataset_revision": dataset_revision,
        "fetched_at": fetched_at,
        "eval_only": True,
    }


def build_ledger_entries(rows: Iterable[dict[str, str]], *, metadata: dict[str, Any], fetched_at: str) -> list[dict[str, Any]]:
    if not metadata_allows_eval_only(metadata):
        raise ValueError("Global-PIQA requires license_spdx=CC-BY-SA-4.0 and eval_only=true")
    revision = str(metadata.get("dataset_revision") or DATASET_REVISION)
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(rows, 1):
        rec = build_eval_record(row, row_index=idx)
        out.append(ledger_entry(rec, dataset_revision=revision, fetched_at=fetched_at))
    return out


def refuse_train_path(path: Path) -> None:
    resolved = path.resolve()
    if resolved == TRAIN_CANDIDATES_DIR or TRAIN_CANDIDATES_DIR in resolved.parents:
        raise ValueError("refusing to write eval-only Global-PIQA hashes under data/stage2/candidates/")


def append_ledger(entries: Iterable[dict[str, Any]], ledger_path: Path) -> int:
    refuse_train_path(ledger_path)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with ledger_path.open("a", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    return count


_SELFTEST_TSV = """example_id\tprompt\tsolution0\tsolution1\tsolution2\tsolution3\tlabel\tlanguage\tcategories
piqa-haw-001\tHe aha ka mea pono no ka ho'omaka ana?\tE heluhelu mua i na kuhikuhi.\tE kiola i ka puke.\tE pani i ka puka.\tE hiamoe koke.\t0\thaw_Latn\tcommonsense
piqa-haw-002\tPehea e malama ai i ka wai anu?\tWaiho ma ka la.\tHookomo i loko o ka pahu hau.\tHoomahana ma ke ahi.\tNinini ma ka lepo.\t1\thaw_Latn\tcommonsense
piqa-haw-003\tNo ke aha e holoi ai na lima?\tI maemae a palekana.\tI pelapela hou.\tI lilo ai ka wai.\tI nalo ka kopa.\t0\thaw_Latn\tcommonsense
"""


def self_test(ledger_path: Path = SELFTEST_LEDGER) -> int:
    if ledger_path.exists():
        ledger_path.unlink()
    entries = build_ledger_entries(
        parse_tsv(_SELFTEST_TSV),
        metadata={"license_spdx": LICENSE_SPDX, "eval_only": True, "dataset_revision": DATASET_REVISION},
        fetched_at="2026-05-03T00:00:00Z",
    )
    assert len(entries) == 3
    assert len({e["content_sha256"] for e in entries}) == 3
    wrote = append_ledger(entries, ledger_path)
    assert wrote == 3
    assert ledger_path.exists()
    print(f"self-test: wrote {wrote} eval-only hashes -> {ledger_path}", file=sys.stderr)
    return 0


def _validate_execute(args: argparse.Namespace) -> tuple[bool, str]:
    if args.dataset_pin != DATASET_PIN:
        return False, f"refusing: --dataset-pin must be exactly {DATASET_PIN}"
    if args.confirm_license_spdx != LICENSE_SPDX:
        return False, f"refusing: --confirm-license-spdx must be exactly {LICENSE_SPDX}"
    if not args.tos_snapshot or not args.tos_snapshot.is_file():
        return False, "refusing: --tos-snapshot local file is required"
    if not args.input_tsv or not args.input_tsv.is_file():
        return False, "refusing: --input-tsv local TSV is required; no live fetch is implemented"
    try:
        refuse_train_path(args.ledger)
    except ValueError as exc:
        return False, str(exc)
    return True, "ok"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ingest Global-PIQA haw_Latn into eval_hashes.jsonl only.")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-test", action="store_true")
    mode.add_argument("--execute", action="store_true")
    ap.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    ap.add_argument("--input-tsv", type=Path)
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

    rows = parse_tsv(args.input_tsv.read_text(encoding="utf-8"))
    fetched_at = _utcnow()
    entries = build_ledger_entries(
        rows,
        metadata={"license_spdx": LICENSE_SPDX, "eval_only": True, "dataset_revision": DATASET_REVISION},
        fetched_at=fetched_at,
    )
    wrote = append_ledger(entries, args.ledger)
    print(f"wrote {wrote} eval-only Global-PIQA hashes -> {args.ledger}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
