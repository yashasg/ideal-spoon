#!/usr/bin/env python3
"""Normalize legacy Stage-2 candidate JSONL files to the canonical schema.

This is an apply-by-explicit-flag patcher for candidate artifacts under
``data/stage2/candidates``. It never touches raw data. When ``--apply`` is
used, each changed file is copied to ``<name>.bak`` before the normalized
JSONL is written in place.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import sys
import unicodedata
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CANDIDATES = REPO_ROOT / "data" / "stage2" / "candidates"
REGISTER_MAP = {
    "phrase-book": "educational",
    "legal": "unknown",
    "conversational": "unknown",
    "educational-subtitles": "educational",
}
ALIGNMENT_TYPE_MAP = {
    "phrase-pair": "parallel-sentence",
}
ALIGNMENT_METHOD_MAP = {
    "section-id": "manual",
    "two-column-djvu-xml-coordinate-pairing-v1": "manual",
    "filename-pair+paragraph-order+sentence-split-v2": "filename-pair",
}
SOURCE_REGISTER_DEFAULTS = {
    "wiki-haw-en-langlinks": "encyclopedic",
    "weblate-en-haw": "software-l10n",
    "ia-hawaiian-phrase-book-1881": "educational",
    "hk_constitution_1852": "unknown",
    "gospel_john_1854": "religious",
}
SOURCE_LICENSE_DEFAULTS = {
    "wiki-haw-en-langlinks": "CC BY-SA 4.0 / GFDL (Wikipedia)",
}


def _load_manifest_builder():
    path = REPO_ROOT / "scripts" / "320_build_stage2_manifest.py"
    spec = importlib.util.spec_from_file_location("stage2_manifest_builder_320", path)
    if not spec or not spec.loader:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


_manifest = _load_manifest_builder()
from llm_hawaii.stage2_canonical import canonical_haw, sha256_text as stage2_sha256_text  # noqa: E402


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def normalize_haw(text: str) -> str:
    return canonical_haw(text)


def sha256_text(text: str) -> str:
    return stage2_sha256_text(text)


def length_ratio(haw: str, en: str) -> float:
    en_n = max(1, len(en.split()))
    return round(len(haw.split()) / en_n, 4)


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc


def candidate_paths(args: argparse.Namespace) -> list[Path]:
    if args.candidates:
        paths = [Path(p) for p in args.candidates]
    else:
        paths = sorted(DEFAULT_CANDIDATES.glob("*.jsonl"))
    return [p if p.is_absolute() else (REPO_ROOT / p) for p in paths]


def _first_str(row: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        val = row.get(key)
        if isinstance(val, str) and val:
            return val
    return None


def _append_note(row: dict[str, Any], note: str) -> None:
    existing = row.get("notes")
    if isinstance(existing, str) and existing:
        if note not in existing:
            row["notes"] = f"{existing}; {note}"
    else:
        row["notes"] = note


def canonicalize_row(row_in: dict[str, Any]) -> dict[str, Any]:
    row = dict(row_in)

    if "source" not in row and isinstance(row.get("source_id"), str):
        row["source"] = row["source_id"]
    if "pair_id" not in row and isinstance(row.get("source_pair_id"), str):
        row["pair_id"] = row["source_pair_id"]
    if "manifest_schema_version" not in row and isinstance(row.get("schema_version"), str):
        row["manifest_schema_version"] = row["schema_version"]
    row.setdefault("manifest_schema_version", "stage2.v0")

    source = row.get("source") if isinstance(row.get("source"), str) else "legacy-stage2"
    row.setdefault("source", source)
    row.setdefault("pair_id", _first_str(row, "dedup_cluster_id", "tm_unit_id") or f"{source}-{sha256_text(json.dumps(row_in, sort_keys=True, ensure_ascii=False))[:16]}")

    en_original = row.get("text_en") if isinstance(row.get("text_en"), str) else ""
    haw_original = row.get("text_haw") if isinstance(row.get("text_haw"), str) else ""
    en = nfc(en_original)
    haw = normalize_haw(haw_original)
    if en_original:
        row["text_en"] = en
    if haw_original:
        row["text_haw"] = haw

    row.setdefault("text_en_path", None)
    row.setdefault("text_haw_path", None)

    source_url = _first_str(row, "source_url")
    row.setdefault("source_url_en", _first_str(row, "source_url_en", "url_en") or source_url or "unknown")
    row.setdefault("source_url_haw", _first_str(row, "source_url_haw", "url_haw") or source_url or "unknown")
    row.setdefault("fetch_date", "unknown")

    en_raw_hash = sha256_text(nfc(en_original)) if en_original else None
    haw_raw_hash = sha256_text(nfc(haw_original)) if haw_original else None
    en_clean_hash = sha256_text(en) if en else _first_str(row, "sha256_en_clean", "text_en_sha256")
    haw_clean_hash = sha256_text(haw) if haw else _first_str(row, "sha256_haw_clean", "text_haw_sha256")

    row["sha256_en_raw"] = row.get("sha256_en_raw") if isinstance(row.get("sha256_en_raw"), str) else (en_raw_hash or en_clean_hash or "unknown")
    row["sha256_haw_raw"] = row.get("sha256_haw_raw") if isinstance(row.get("sha256_haw_raw"), str) else (haw_raw_hash or haw_clean_hash or "unknown")
    if en_clean_hash:
        row["sha256_en_clean"] = en_clean_hash
    elif isinstance(row.get("text_en_sha256"), str):
        row["sha256_en_clean"] = row["text_en_sha256"]
    if haw_clean_hash:
        row["sha256_haw_clean"] = haw_clean_hash
    elif isinstance(row.get("text_haw_sha256"), str):
        row["sha256_haw_clean"] = row["text_haw_sha256"]
    if isinstance(row.get("sha256_en_clean"), str) and isinstance(row.get("sha256_haw_clean"), str):
        row["sha256_pair"] = _manifest.compute_pair_hash(row["sha256_en_clean"], row["sha256_haw_clean"])

    row.setdefault("record_id_en", _first_str(row, "source_document_id_en", "tm_unit_id") or f"{row['pair_id']}:en")
    row.setdefault("record_id_haw", _first_str(row, "source_document_id_haw", "tm_unit_id") or f"{row['pair_id']}:haw")

    if row.get("alignment_type") in ALIGNMENT_TYPE_MAP:
        _append_note(row, f"legacy alignment_type={row['alignment_type']}")
        row["alignment_type"] = ALIGNMENT_TYPE_MAP[row["alignment_type"]]
    if row.get("alignment_method") in ALIGNMENT_METHOD_MAP:
        _append_note(row, f"legacy alignment_method={row['alignment_method']}")
        row["alignment_method"] = ALIGNMENT_METHOD_MAP[row["alignment_method"]]
    row.setdefault("alignment_type", "parallel-sentence")
    row.setdefault("alignment_method", "manual")
    row.setdefault("alignment_model", None)
    row.setdefault("alignment_score", None)
    row.setdefault("alignment_review_required", True)

    if not isinstance(row.get("length_ratio_haw_over_en"), (int, float)):
        row["length_ratio_haw_over_en"] = length_ratio(haw, en) if en and haw else 1.0
    row.setdefault("lang_id_en", "en")
    row.setdefault("lang_id_haw", "haw")
    if not isinstance(row.get("lang_id_en_confidence"), (int, float)):
        row["lang_id_en_confidence"] = 1.0
    if not isinstance(row.get("lang_id_haw_confidence"), (int, float)):
        row["lang_id_haw_confidence"] = 1.0
    row.setdefault("direction_original", "unknown")

    register = row.get("register")
    if register in REGISTER_MAP:
        _append_note(row, f"legacy register={register}")
        row["register"] = REGISTER_MAP[register]
    row.setdefault("register", SOURCE_REGISTER_DEFAULTS.get(source, "unknown"))

    row.setdefault("edition_or_version", None)
    row.setdefault("synthetic", False)
    row.setdefault("synthetic_source_model", None)
    observed = _first_str(row, "license_observed", "license") or SOURCE_LICENSE_DEFAULTS.get(source, "unknown")
    row.setdefault("license_observed_en", observed)
    row.setdefault("license_observed_haw", observed)
    row["license_inferred"] = None
    row.setdefault("tos_snapshot_id", None)

    row.setdefault("prototype_only", True)
    row.setdefault("release_eligible", False)
    if row.get("prototype_only") is True and row.get("release_eligible") is True:
        row["release_eligible"] = False
    if not isinstance(row.get("dedup_cluster_id"), str):
        row["dedup_cluster_id"] = row["pair_id"]
    row.setdefault("crosslink_stage1_overlap", False)
    row.setdefault("split", "review-pending")
    if not isinstance(row.get("quality_flags"), list):
        row["quality_flags"] = []

    _manifest.apply_policy(row)
    return row


def normalize_file(path: Path, *, apply: bool = False) -> dict[str, Any]:
    rows = list(read_jsonl(path))
    normalized = [canonicalize_row(row) for row in rows]
    changed = normalized != rows
    before_violations = sum(len(_manifest.validate_row(dict(row))) for row in rows)
    after_violations = sum(len(_manifest.validate_row(dict(row))) for row in normalized)

    if apply and changed:
        backup = path.with_suffix(path.suffix + ".bak")
        if not backup.exists():
            shutil.copy2(path, backup)
        staged = path.with_suffix(path.suffix + ".normalized")
        with staged.open("w", encoding="utf-8") as fh:
            for row in normalized:
                fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        staged.replace(path)

    return {
        "path": str(path.relative_to(REPO_ROOT)),
        "rows": len(rows),
        "changed": changed,
        "before_raw_schema_violations": before_violations,
        "after_raw_schema_violations": after_violations,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", nargs="*", help="Candidate JSONL files; defaults to data/stage2/candidates/*.jsonl")
    parser.add_argument("--apply", action="store_true", help="Rewrite changed candidate files in place after creating .bak copies")
    args = parser.parse_args(argv)

    paths = candidate_paths(args)
    report = {"applied": args.apply, "files": [normalize_file(path, apply=args.apply) for path in paths]}
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
