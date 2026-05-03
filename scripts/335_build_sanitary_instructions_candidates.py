#!/usr/bin/env python3
"""Build Stage-2 candidates from Sanitary Instructions for Hawaiians (1881).

This source has paired public-domain English and Hawaiian volumes. The OCR
paragraph counts diverge, so deterministic paragraph-index pairing is unsafe.
This builder uses a real LaBSE sentence-transformer model and accepts only
mutual-nearest paragraph pairs above a conservative score threshold.

Usage:
    python3 scripts/335_build_sanitary_instructions_candidates.py --dry-run
    python3 scripts/335_build_sanitary_instructions_candidates.py --execute
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

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

SOURCE_ID = "sanitary-instructions-1881"
EDITION_ID = "sanitary-instructions-1881-ia-nlm-paired"
MODEL_ID = "sentence-transformers/LaBSE"
POLICY_ID = "sanitary-1881-labse-mutual-nearest-v1"
SCHEMA_VERSION = "stage2.v0"

EN_DEFAULT = (
    REPO_ROOT
    / "data/raw/ulukau-family-sft-candidates/20260501/"
    / "63140380R.nlm.nih.gov/63140380R_djvu.txt"
)
HAW_DEFAULT = (
    REPO_ROOT
    / "data/raw/sanitary-instructions-1881/20260502/63140370R_djvu.txt"
)
OUT_DEFAULT = REPO_ROOT / "data/stage2/candidates/sanitary_instructions_1881.jsonl"
REPORT_DEFAULT = (
    REPO_ROOT
    / "data/stage2/reports/sanitary_instructions_1881_candidates_report.json"
)

SOURCE_URL_EN = "https://archive.org/details/63140380R.nlm.nih.gov"
SOURCE_URL_HAW = "https://archive.org/details/63140370R.nlm.nih.gov"
LICENSE = "Public Domain (1881 U.S. imprint; IA/NLM scan)"

MIN_WORDS = 8
MAX_WORDS = 130
MIN_CHARS = 40
MAX_CHARS = 800
MIN_SCORE = 0.70
MIN_RATIO = 0.40
MAX_RATIO = 2.50
MAX_PARAGRAPH_INDEX_DELTA = 500

OKINA = "\u02bb"


def sha256_text(text: str) -> str:
    return stage2_sha256_text(text)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def pair_hash(sha_en: str, sha_haw: str) -> str:
    return stage2_compute_pair_hash(sha_en, sha_haw)


def normalize_text(text: str, *, lang: str = "haw") -> str:
    text = re.sub(r"(?m)^\s*\d+\s*$", "", text)
    if lang == "en":
        return stage2_canonical_en(text)
    return stage2_canonical_haw(text)


def paragraph_records(path: Path, *, lang: str) -> list[dict[str, Any]]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    records: list[dict[str, Any]] = []
    for idx, block in enumerate(re.split(r"\n\s*\n", raw)):
        text = normalize_text(block, lang=lang)
        if not (MIN_CHARS <= len(text) <= MAX_CHARS):
            continue
        words = text.split()
        if not (MIN_WORDS <= len(words) <= MAX_WORDS):
            continue
        upper = text.upper()
        if any(
            marker in upper
            for marker in (
                "UNIVERSITY OF CALIFORNIA",
                "NATIONAL LIBRARY",
                "DIGITIZED BY",
                "GOOGLE",
            )
        ):
            continue
        letters = re.findall(r"[A-Za-zĀĒĪŌŪāēīōūʻ]+", text)
        if len(letters) < 5:
            continue
        records.append({
            "paragraph_index": idx,
            "text": text,
            "tokens": len(words),
        })
    return records


def self_test() -> int:
    assert normalize_text("Aloha  \n  kākou") == "Aloha kākou"
    assert normalize_text("ka'u") == f"ka{OKINA}u"
    assert pair_hash("a", "b") == hashlib.sha256("a\u2016b".encode("utf-8")).hexdigest()
    print("self-test OK")
    return 0


def assert_execute_preconditions(confirm_edition: str | None, tos_snapshot: str | None) -> None:
    if confirm_edition != EDITION_ID:
        raise SystemExit(
            "--execute requires --confirm-edition "
            f"{EDITION_ID!r} for the pinned paired IA/NLM edition"
        )
    if not tos_snapshot:
        raise SystemExit("--execute requires --tos-snapshot pointing at the saved IA ToS snapshot")
    tos_path = Path(tos_snapshot)
    if not tos_path.exists() or not tos_path.is_file():
        raise SystemExit(f"--tos-snapshot not found: {tos_path}")


def build_rows_from_scores(
    en_records: list[dict[str, Any]],
    haw_records: list[dict[str, Any]],
    scores: list[list[float]],
    *,
    en_path: Path,
    haw_path: Path,
    en_sha: str,
    haw_sha: str,
    fetch_date: str,
    model_id: str,
    min_score: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Select mutual-nearest LaBSE paragraph pairs and build schema-valid rows."""
    if len(scores) != len(en_records):
        raise ValueError("score matrix row count must match English records")
    if any(len(row) != len(haw_records) for row in scores):
        raise ValueError("score matrix column count must match Hawaiian records")

    en_best = [max(range(len(row)), key=row.__getitem__) for row in scores]
    en_score = [row[haw_idx] for row, haw_idx in zip(scores, en_best)]
    haw_best = [
        max(range(len(en_records)), key=lambda en_idx: scores[en_idx][haw_idx])
        for haw_idx in range(len(haw_records))
    ] if haw_records else []

    rows: list[dict[str, Any]] = []
    rejects = {
        "not_mutual_nearest": 0,
        "score_below_threshold": 0,
        "ratio_out_of_band": 0,
        "paragraph_index_delta_out_of_band": 0,
    }

    for en_idx, haw_idx in enumerate(en_best):
        if haw_best[haw_idx] != en_idx:
            rejects["not_mutual_nearest"] += 1
            continue
        score = float(en_score[en_idx])
        if score < min_score:
            rejects["score_below_threshold"] += 1
            continue
        en_rec = en_records[en_idx]
        haw_rec = haw_records[haw_idx]
        ratio = haw_rec["tokens"] / max(en_rec["tokens"], 1)
        if not (MIN_RATIO <= ratio <= MAX_RATIO):
            rejects["ratio_out_of_band"] += 1
            continue
        index_delta = abs(en_rec["paragraph_index"] - haw_rec["paragraph_index"])
        if index_delta > MAX_PARAGRAPH_INDEX_DELTA:
            rejects["paragraph_index_delta_out_of_band"] += 1
            continue

        text_en = en_rec["text"]
        text_haw = haw_rec["text"]
        sha_en_clean = sha256_text(text_en)
        sha_haw_clean = sha256_text(text_haw)
        sha_pair = pair_hash(sha_en_clean, sha_haw_clean)
        pair_id = (
            f"sanitary-1881-labse-{en_rec['paragraph_index']:04d}-"
            f"{haw_rec['paragraph_index']:04d}-{sha_pair[:12]}"
        )
        record_id = (
            f"sanitary-1881:en{en_rec['paragraph_index']}:"
            f"haw{haw_rec['paragraph_index']}"
        )
        rows.append({
            "pair_id": pair_id,
            "source": SOURCE_ID,
            "source_url_en": SOURCE_URL_EN,
            "source_url_haw": SOURCE_URL_HAW,
            "fetch_date": fetch_date,
            "sha256_en_raw": sha_en_clean,
            "sha256_haw_raw": sha_haw_clean,
            "sha256_en_clean": sha_en_clean,
            "sha256_haw_clean": sha_haw_clean,
            "sha256_pair": sha_pair,
            "record_id_en": record_id,
            "record_id_haw": record_id,
            "text_en": text_en,
            "text_haw": text_haw,
            "text_en_path": str(en_path.relative_to(REPO_ROOT)),
            "text_haw_path": str(haw_path.relative_to(REPO_ROOT)),
            "alignment_type": "comparable-aligned",
            "alignment_method": "labse",
            "alignment_model": model_id,
            "alignment_score": round(score, 6),
            "alignment_review_required": True,
            "length_ratio_haw_over_en": round(ratio, 4),
            "lang_id_en": "en",
            "lang_id_en_confidence": 1.0,
            "lang_id_haw": "haw",
            "lang_id_haw_confidence": 1.0,
            "direction_original": "en->haw",
            "register": "unknown",
            "edition_or_version": "Sanitary Instructions for Hawaiians, 1881 paired IA/NLM imprints",
            "synthetic": False,
            "synthetic_source_model": None,
            "license_observed_en": LICENSE,
            "license_observed_haw": LICENSE,
            "license_inferred": None,
            "tos_snapshot_id": "data/raw/sanitary-instructions-1881/20260502/ia_tos_snapshot.html",
            "prototype_only": True,
            "release_eligible": False,
            "dedup_cluster_id": pair_id,
            "crosslink_stage1_overlap": False,
            "split": "review-pending",
            "notes": (
                f"{POLICY_ID}; score={score:.6f}; min_score={min_score}; "
                f"en_paragraph_index={en_rec['paragraph_index']}; "
                f"haw_paragraph_index={haw_rec['paragraph_index']}; "
                f"paragraph_index_delta={index_delta}; "
                f"en_raw_sha256={en_sha}; haw_raw_sha256={haw_sha}."
            ),
            "manifest_schema_version": SCHEMA_VERSION,
            "alignment_confidence_tier": "accept",
            "quality_flags": [],
            "manual_review_reasons": [
                f"{POLICY_ID}: LaBSE mutual-nearest comparable paragraph pair, "
                f"score>={min_score}, token ratio in [{MIN_RATIO},{MAX_RATIO}], "
                f"paragraph-index delta <= {MAX_PARAGRAPH_INDEX_DELTA}."
            ],
            "alignment_score_components": {"labse_cosine": round(score, 6)},
            "policy_version": POLICY_ID,
            "sanitary_en_paragraph_index": en_rec["paragraph_index"],
            "sanitary_haw_paragraph_index": haw_rec["paragraph_index"],
            "sanitary_paragraph_index_delta": index_delta,
            "sanitary_en_raw_sha256": en_sha,
            "sanitary_haw_raw_sha256": haw_sha,
        })

    report = {
        "source_id": SOURCE_ID,
        "policy_id": POLICY_ID,
        "model_id": model_id,
        "min_score": min_score,
        "min_ratio": MIN_RATIO,
        "max_ratio": MAX_RATIO,
        "max_paragraph_index_delta": MAX_PARAGRAPH_INDEX_DELTA,
        "en_path": str(en_path.relative_to(REPO_ROOT)),
        "haw_path": str(haw_path.relative_to(REPO_ROOT)),
        "en_raw_sha256": en_sha,
        "haw_raw_sha256": haw_sha,
        "en_paragraphs_considered": len(en_records),
        "haw_paragraphs_considered": len(haw_records),
        "rows_emitted": len(rows),
        "rejects": rejects,
        "score_summary": {
            "min": min((r["alignment_score"] for r in rows), default=None),
            "max": max((r["alignment_score"] for r in rows), default=None),
        },
        "samples": [
            {"text_en": r["text_en"], "text_haw": r["text_haw"], "score": r["alignment_score"]}
            for r in rows[:5]
        ],
    }
    return rows, report


def build_rows(
    en_path: Path,
    haw_path: Path,
    *,
    model_id: str,
    min_score: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        import numpy as np
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise SystemExit(
            "sentence-transformers and numpy are required. Install compute deps "
            "or run from the temporary aligner venv used for this pass."
        ) from exc

    en_records = paragraph_records(en_path, lang="en")
    haw_records = paragraph_records(haw_path, lang="haw")
    model = SentenceTransformer(model_id)

    en_emb = model.encode(
        [r["text"] for r in en_records],
        batch_size=64,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    haw_emb = model.encode(
        [r["text"] for r in haw_records],
        batch_size=64,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    scores = np.matmul(en_emb, haw_emb.T).tolist()
    return build_rows_from_scores(
        en_records,
        haw_records,
        scores,
        en_path=en_path,
        haw_path=haw_path,
        en_sha=sha256_file(en_path),
        haw_sha=sha256_file(haw_path),
        fetch_date=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d"),
        model_id=model_id,
        min_score=min_score,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-test", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--en", default=str(EN_DEFAULT))
    parser.add_argument("--haw", default=str(HAW_DEFAULT))
    parser.add_argument("--out", default=str(OUT_DEFAULT))
    parser.add_argument("--report", default=str(REPORT_DEFAULT))
    parser.add_argument("--model-id", default=MODEL_ID)
    parser.add_argument("--min-score", type=float, default=MIN_SCORE)
    parser.add_argument("--confirm-edition")
    parser.add_argument("--tos-snapshot")
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()
    if args.execute:
        assert_execute_preconditions(args.confirm_edition, args.tos_snapshot)

    en_path = Path(args.en)
    haw_path = Path(args.haw)
    if not en_path.exists():
        raise SystemExit(f"missing English OCR: {en_path}")
    if not haw_path.exists():
        raise SystemExit(f"missing Hawaiian OCR: {haw_path}")

    rows, report = build_rows(
        en_path,
        haw_path,
        model_id=args.model_id,
        min_score=args.min_score,
    )
    print(f"[sanitary] emitted candidate rows: {len(rows)}", file=sys.stderr)
    print(json.dumps({
        "rows_emitted": len(rows),
        "score_summary": report["score_summary"],
        "rejects": report["rejects"],
    }, indent=2), file=sys.stderr)

    if args.dry_run:
        return 0

    out_path = Path(args.out)
    report_path = Path(args.report)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"[sanitary] wrote {out_path}", file=sys.stderr)
    print(f"[sanitary] wrote {report_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
