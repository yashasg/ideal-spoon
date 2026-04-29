#!/usr/bin/env python3
"""Validate and hash the local W1 Hawaiian manual micro-eval.

The populated W1 TSV is local-only under ``data/evals/manual_w1/``. This
script validates rows, summarizes categories/slices for the future eval
harness, and updates the canonical JSONL contamination ledger with
``origin=manual_w1`` rows.

Default behavior hashes only ``review_status=accepted`` rows. Use
``--include-draft-for-local-ledger`` only for local prototype contamination
preflight; draft rows are never eval-consumable.
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import hashlib
import json
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
CODE_DIR = REPO_ROOT / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from llm_hawaii.metrics import (  # noqa: E402
    WRONG_OKINA_CHARS,
    count_combining_macron,
    count_hawaiian_diacritics,
    count_wrong_okina,
    diacritic_density_bin,
    is_nfc,
)

SOURCE_ID = "manual_w1"
NORMALIZATION_METHOD = "NFC"
EVAL_HASH_SCHEMA_VERSION = "eval-hashes-jsonl-v1"
DEFAULT_INPUT = Path("data/evals/manual_w1/w1-haw-micro-eval.tsv")
DEFAULT_LEDGER = Path("data/evals/eval_hashes.jsonl")
DEFAULT_MANIFEST = Path("data/evals/manual_w1/w1-hash-manifest.json")
HEADER = [
    "item_id",
    "category",
    "prompt",
    "reference",
    "diacritic_density",
    "notes",
    "author",
    "review_status",
    "nfc_normalized",
]
CATEGORIES = (
    "okina_survival",
    "kahako_retention",
    "unicode_nfc",
    "tokenizer_survival",
    "generation_sanity",
)
REVIEW_STATUSES = ("draft", "reviewed", "accepted")

DRAFT_ROWS = [
    {
        "item_id": "w1-okina-001",
        "category": "okina_survival",
        "prompt": "E kope pololei i kēia huaʻōlelo:",
        "reference": "Hawaiʻi",
        "diacritic_density": "4",
        "notes": "PROTOTYPE LOCAL DRAFT ONLY; tests U+02BB ʻokina survival; pending Hawaiian-literate review.",
        "author": "rusty-ai-draft",
        "review_status": "draft",
        "nfc_normalized": "true",
    },
    {
        "item_id": "w1-kahako-001",
        "category": "kahako_retention",
        "prompt": "E kope pololei i kēia mau hua me nā kahakō:",
        "reference": "mālama i ka ʻōlelo Hawaiʻi",
        "diacritic_density": "7",
        "notes": "PROTOTYPE LOCAL DRAFT ONLY; tests precomposed kahakō retention; pending Hawaiian-literate review.",
        "author": "rusty-ai-draft",
        "review_status": "draft",
        "nfc_normalized": "true",
    },
    {
        "item_id": "w1-unicode-001",
        "category": "unicode_nfc",
        "prompt": "NFC check:",
        "reference": "ā ē ī ō ū ʻ",
        "diacritic_density": "6",
        "notes": "PROTOTYPE LOCAL DRAFT ONLY; verifies NFC precomposed vowels plus U+02BB; pending review.",
        "author": "rusty-ai-draft",
        "review_status": "draft",
        "nfc_normalized": "true",
    },
    {
        "item_id": "w1-tokenizer-001",
        "category": "tokenizer_survival",
        "prompt": "Tokenizer round-trip probe:",
        "reference": "ʻĀā ʻĒē ʻĪī ʻŌō ʻŪū",
        "diacritic_density": "15",
        "notes": "PROTOTYPE LOCAL DRAFT ONLY; stresses tokenizer round-trip on Hawaiian diacritics; pending review.",
        "author": "rusty-ai-draft",
        "review_status": "draft",
        "nfc_normalized": "true",
    },
    {
        "item_id": "w1-generation-001",
        "category": "generation_sanity",
        "prompt": "E pane pōkole ma ka ʻōlelo Hawaiʻi no ke aloha ʻohana.",
        "reference": "",
        "diacritic_density": "5",
        "notes": "PROTOTYPE LOCAL DRAFT ONLY; open-ended generation sanity prompt; requires human scoring/review.",
        "author": "rusty-ai-draft",
        "review_status": "draft",
        "nfc_normalized": "true",
    },
]


@dataclass(frozen=True)
class ManualW1Row:
    item_id: str
    category: str
    prompt: str
    reference: str
    diacritic_density: int
    notes: str
    author: str
    review_status: str
    nfc_normalized: bool
    line_no: int


def utcnow_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def normalize_for_hash(text: str) -> str:
    return unicodedata.normalize(NORMALIZATION_METHOD, text)


def hash_material(prompt: str, reference: str) -> str:
    return normalize_for_hash(f"{prompt}\n{reference}")


def compute_hash(prompt: str, reference: str) -> str:
    material = hash_material(prompt, reference)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def write_jsonl(records: list[dict[str, Any]], path: Path, dry_run: bool) -> None:
    if dry_run:
        print(f"[DRY-RUN] Would write {len(records)} records to {display_path(path)}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"[WRITE] {len(records)} records → {display_path(path)}")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.exists():
        return records
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{display_path(path)}:{line_no}: invalid JSONL: {exc}") from exc
            if not isinstance(obj, dict):
                raise ValueError(f"{display_path(path)}:{line_no}: expected JSON object")
            records.append(obj)
    return records


def update_eval_hash_ledger(
    records: list[dict[str, Any]],
    path: Path,
    *,
    dry_run: bool,
) -> dict[str, int]:
    existing = load_jsonl(path)
    kept = [r for r in existing if r.get("origin") != SOURCE_ID]
    combined = kept + records
    stats = {
        "existing_rows": len(existing),
        "preserved_rows": len(kept),
        "replaced_origin_rows": len(existing) - len(kept),
        "new_origin_rows": len(records),
        "combined_rows": len(combined),
    }
    if dry_run:
        print(
            "[DRY-RUN] Would update "
            f"{display_path(path)}: preserve {stats['preserved_rows']} non-{SOURCE_ID} rows, "
            f"replace {stats['replaced_origin_rows']} {SOURCE_ID} rows, "
            f"write {stats['combined_rows']} total rows"
        )
        return stats
    write_jsonl(combined, path, dry_run=False)
    return stats


def parse_bool(value: str) -> bool | None:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    return None


def read_tsv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        filtered = [
            (line_no, line)
            for line_no, line in enumerate(f, start=1)
            if line.strip() and not line.lstrip().startswith("#")
        ]
    if not filtered:
        return [], [f"{display_path(path)}: no TSV header found"]

    reader = csv.DictReader((line for _, line in filtered), delimiter="\t")
    errors: list[str] = []
    fieldnames = reader.fieldnames or []
    if fieldnames != HEADER:
        missing = [name for name in HEADER if name not in fieldnames]
        extra = [name for name in fieldnames if name not in HEADER]
        errors.append(
            f"{display_path(path)}:{filtered[0][0]}: header must be exactly {HEADER}; "
            f"missing={missing}, extra={extra}"
        )

    raw_rows: list[dict[str, str]] = []
    for row_index, row in enumerate(reader, start=1):
        source_line = filtered[row_index][0] if row_index < len(filtered) else filtered[-1][0]
        clean = {key: (value or "") for key, value in row.items() if key is not None}
        clean["_line_no"] = str(source_line)
        raw_rows.append(clean)
    return raw_rows, errors


def coerce_rows(raw_rows: list[dict[str, str]]) -> tuple[list[ManualW1Row], list[str]]:
    rows: list[ManualW1Row] = []
    errors: list[str] = []
    seen_ids: set[str] = set()

    for raw in raw_rows:
        line_no = int(raw.get("_line_no", "0"))
        item_id = raw.get("item_id", "").strip()
        category = raw.get("category", "").strip()
        prompt = raw.get("prompt", "")
        reference = raw.get("reference", "")
        notes = raw.get("notes", "").strip()
        author = raw.get("author", "").strip()
        review_status = raw.get("review_status", "").strip()
        nfc_bool = parse_bool(raw.get("nfc_normalized", ""))

        if not item_id:
            errors.append(f"line {line_no}: item_id is required")
        elif item_id in seen_ids:
            errors.append(f"line {line_no}: duplicate item_id={item_id}")
        else:
            seen_ids.add(item_id)
        if item_id and not item_id.startswith("w1-"):
            errors.append(f"line {line_no}: item_id must start with 'w1-'")
        if category not in CATEGORIES:
            errors.append(f"line {line_no}: category must be one of {CATEGORIES}; got {category!r}")
        if review_status not in REVIEW_STATUSES:
            errors.append(
                f"line {line_no}: review_status must be one of {REVIEW_STATUSES}; got {review_status!r}"
            )
        if nfc_bool is not True:
            errors.append(f"line {line_no}: nfc_normalized must be true before hashing")
        if not notes:
            errors.append(f"line {line_no}: notes are required")
        if not author:
            errors.append(f"line {line_no}: author is required")
        if not prompt:
            errors.append(f"line {line_no}: prompt is required")

        for field_name, text in (("prompt", prompt), ("reference", reference)):
            if not is_nfc(text):
                errors.append(f"line {line_no}: {field_name} is not NFC-normalized")
            if count_combining_macron(text):
                errors.append(f"line {line_no}: {field_name} contains combining macron U+0304")
            wrong_okina_count = count_wrong_okina(text)
            if wrong_okina_count:
                chars = "".join(ch for ch in WRONG_OKINA_CHARS if ch in text)
                errors.append(
                    f"line {line_no}: {field_name} contains wrong ʻokina/apostrophe chars {chars!r}"
                )

        try:
            density = int(raw.get("diacritic_density", ""))
        except ValueError:
            errors.append(f"line {line_no}: diacritic_density must be an integer")
            density = -1
        actual_density = count_hawaiian_diacritics(f"{prompt}\n{reference}")
        if density != actual_density:
            errors.append(
                f"line {line_no}: diacritic_density={density} but prompt+reference has {actual_density}"
            )

        if not errors or not any(error.startswith(f"line {line_no}:") for error in errors):
            rows.append(
                ManualW1Row(
                    item_id=item_id,
                    category=category,
                    prompt=prompt,
                    reference=reference,
                    diacritic_density=density,
                    notes=notes,
                    author=author,
                    review_status=review_status,
                    nfc_normalized=bool(nfc_bool),
                    line_no=line_no,
                )
            )

    return rows, errors


def build_eval_hash_record(row: ManualW1Row, input_path: Path) -> dict[str, Any]:
    material = hash_material(row.prompt, row.reference)
    accepted = row.review_status == "accepted"
    return {
        "schema_version": EVAL_HASH_SCHEMA_VERSION,
        "sha256_normalized": compute_hash(row.prompt, row.reference),
        "hash_method": "sha256",
        "normalization_method": NORMALIZATION_METHOD,
        "origin": SOURCE_ID,
        "stage": "eval-only",
        "division": "evals",
        "split": "w1" if accepted else row.review_status,
        "row_id": row.item_id,
        "category": row.category,
        "review_status": row.review_status,
        "eval_consumable": accepted,
        "prototype_local": not accepted,
        "diacritic_density": row.diacritic_density,
        "diacritic_density_bin": diacritic_density_bin(row.diacritic_density),
        "hash_material": "NFC(prompt) + U+000A + NFC(reference)",
        "char_count_normalized": len(material),
        "source_path": display_path(input_path),
    }


def summarize_rows(rows: list[ManualW1Row]) -> dict[str, Any]:
    return {
        "rows": len(rows),
        "by_category": dict(sorted(Counter(row.category for row in rows).items())),
        "by_review_status": dict(sorted(Counter(row.review_status for row in rows).items())),
        "by_diacritic_density_bin": dict(
            sorted(Counter(diacritic_density_bin(row.diacritic_density) for row in rows).items())
        ),
    }


def write_manifest(
    path: Path,
    *,
    input_path: Path,
    ledger_path: Path,
    rows: list[ManualW1Row],
    included_rows: list[ManualW1Row],
    ledger_stats: dict[str, int],
    include_draft_for_local_ledger: bool,
    dry_run: bool,
) -> None:
    manifest = {
        "pipeline_stage": "315_hash_manual_w1_eval",
        "timestamp": utcnow_iso(),
        "source_id": SOURCE_ID,
        "input": display_path(input_path),
        "eval_hashes": display_path(ledger_path),
        "schema_version": EVAL_HASH_SCHEMA_VERSION,
        "normalization_method": NORMALIZATION_METHOD,
        "hash_material": "NFC(prompt) + U+000A + NFC(reference)",
        "default_included_statuses": ["accepted"],
        "include_draft_for_local_ledger": include_draft_for_local_ledger,
        "all_rows": summarize_rows(rows),
        "ledger_rows": summarize_rows(included_rows),
        "ledger_update": ledger_stats,
        "categories": list(CATEGORIES),
        "diacritic_density_bins": ["none", "low", "medium", "high"],
        "note": "Rows with review_status != accepted are prototype-local and not eval-consumable.",
    }
    if dry_run:
        print(f"[DRY-RUN] Would write manifest to {display_path(path)}")
        print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)[:1200])
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    print(f"[WRITE] Manifest → {display_path(path)}")


def write_draft_file(path: Path, dry_run: bool, force: bool) -> int:
    if path.exists() and not force:
        print(f"[SKIP] {display_path(path)} already exists; use --force to overwrite.")
        return 0
    if dry_run:
        print(f"[DRY-RUN] Would write {len(DRAFT_ROWS)} draft rows to {display_path(path)}")
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write("# PROTOTYPE LOCAL DRAFT — pending Hawaiian-literate human review.\n")
        f.write("# Do not publish, benchmark, or treat these draft rows as accepted eval items.\n")
        f.write("# Generated by scripts/315_hash_manual_w1_eval.py --init-draft.\n")
        writer = csv.DictWriter(f, fieldnames=HEADER, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(DRAFT_ROWS)
    print(f"[WRITE] Draft W1 TSV → {display_path(path)}")
    return 0


def print_schema() -> None:
    schema = {
        "tsv_header": HEADER,
        "categories": list(CATEGORIES),
        "review_statuses": list(REVIEW_STATUSES),
        "diacritic_density": "Count of U+02BB ʻokina plus precomposed kahakō vowels in NFC(prompt + LF + reference).",
        "hash_ledger": {
            "canonical_path": str(DEFAULT_LEDGER),
            "schema_version": EVAL_HASH_SCHEMA_VERSION,
            "origin": SOURCE_ID,
            "division": "evals",
            "stage": "eval-only",
            "hash_material": "NFC(prompt) + U+000A + NFC(reference)",
            "default_included_statuses": ["accepted"],
            "local_draft_flag": "--include-draft-for-local-ledger",
        },
        "slices": {
            "category": list(CATEGORIES),
            "diacritic_density_bin": ["none", "low", "medium", "high"],
            "review_status": list(REVIEW_STATUSES),
        },
    }
    print(json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate/hash local W1 Hawaiian manual micro-eval rows.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help=f"Input TSV (default: {DEFAULT_INPUT}).")
    parser.add_argument(
        "--ledger",
        type=Path,
        default=DEFAULT_LEDGER,
        help=f"Canonical eval hash JSONL ledger (default: {DEFAULT_LEDGER}).",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help=f"Local hash manifest output (default: {DEFAULT_MANIFEST}).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate and summarize without writing ledger outputs.")
    parser.add_argument("--execute", action="store_true", help="Write ledger/manifest outputs.")
    parser.add_argument(
        "--init-draft",
        action="store_true",
        help="Create a local prototype draft TSV under data/evals/manual_w1/.",
    )
    parser.add_argument("--force", action="store_true", help="Allow --init-draft to overwrite an existing local TSV.")
    parser.add_argument(
        "--include-draft-for-local-ledger",
        action="store_true",
        help=(
            "Hash draft/reviewed rows too for local contamination preflight. "
            "Ledger rows are marked eval_consumable=false unless accepted."
        ),
    )
    parser.add_argument("--print-schema", action="store_true", help="Print the TSV/ledger schema contract and exit.")

    args = parser.parse_args(argv)
    if args.print_schema:
        print_schema()
        return 0
    if not args.dry_run and not args.execute:
        print("[ERROR] Must specify --dry-run or --execute.", file=sys.stderr)
        return 2

    input_path = resolve_repo_path(args.input)
    ledger_path = resolve_repo_path(args.ledger)
    manifest_path = resolve_repo_path(args.manifest)
    dry_run = args.dry_run or not args.execute

    if args.init_draft:
        return write_draft_file(input_path, dry_run=dry_run, force=args.force)

    if not input_path.exists():
        if dry_run:
            print(f"[DRY-RUN] Input TSV is not present: {display_path(input_path)}")
            print("[DRY-RUN] Create a local prototype with: python3 scripts/315_hash_manual_w1_eval.py --init-draft --execute")
            return 0
        print(f"[ERROR] Input TSV not found: {display_path(input_path)}", file=sys.stderr)
        return 3

    raw_rows, header_errors = read_tsv(input_path)
    rows, row_errors = coerce_rows(raw_rows)
    errors = header_errors + row_errors
    if errors:
        print("[ERROR] W1 TSV validation failed:", file=sys.stderr)
        for error in errors[:50]:
            print(f"  - {error}", file=sys.stderr)
        if len(errors) > 50:
            print(f"  ... {len(errors) - 50} more errors", file=sys.stderr)
        return 3

    print(f"[LOAD] {len(rows)} valid W1 rows from {display_path(input_path)}")
    print(f"[SUMMARY] All rows: {json.dumps(summarize_rows(rows), ensure_ascii=False, sort_keys=True)}")

    missing_categories = [category for category in CATEGORIES if category not in {row.category for row in rows}]
    if missing_categories:
        print(f"[WARN] W1 categories missing from local TSV: {missing_categories}", file=sys.stderr)

    included_statuses = set(REVIEW_STATUSES if args.include_draft_for_local_ledger else ("accepted",))
    included_rows = [row for row in rows if row.review_status in included_statuses]
    print(f"[HASH] Included statuses for ledger: {sorted(included_statuses)}")
    print(f"[HASH] Rows selected for ledger: {len(included_rows)}")

    if not included_rows:
        print("[HASH] No rows selected; ledger is unchanged.")
        return 0

    hash_records = [build_eval_hash_record(row, input_path) for row in included_rows]
    duplicate_hashes = len(hash_records) - len({record["sha256_normalized"] for record in hash_records})
    if duplicate_hashes:
        print(f"[ERROR] Duplicate W1 hashes detected: {duplicate_hashes}", file=sys.stderr)
        return 3

    ledger_stats = update_eval_hash_ledger(hash_records, ledger_path, dry_run=dry_run)
    write_manifest(
        manifest_path,
        input_path=input_path,
        ledger_path=ledger_path,
        rows=rows,
        included_rows=included_rows,
        ledger_stats=ledger_stats,
        include_draft_for_local_ledger=args.include_draft_for_local_ledger,
        dry_run=dry_run,
    )
    print("[SUCCESS] W1 manual eval hash path complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
