#!/usr/bin/env python3
"""Stage-2 bidirectional SFT JSONL emitter (skeleton).

Reads a Stage-2 manifest (JSONL) — one row per canonical en↔haw pair —
and emits trainer-facing JSONL examples under an ignored ``data/`` path.
Each surviving manifest row produces up to two directional rows
(``en->haw`` and ``haw->en``) per the Stage-2 output JSONL contract in
``docs/data-pipeline.md`` §"Stage 2 output JSONL" and the bidirectional
SFT recipe in ``docs/training-pipeline.md`` §4.

Design notes (durable, see decisions inbox):
  * Skeleton, stdlib only. Mirrors the conventions of
    ``scripts/301_build_stage1_dataset.py`` (JSONL manifest first; any
    future Parquet mirror is derived only after ``pyarrow`` is justified).
  * Inputs: a Stage-2 manifest JSONL where each row carries pair-level
    provenance + alignment metadata, plus *either* inline text fields
    (``text_en``, ``text_haw``) *or* text refs (``text_en_path``,
    ``text_haw_path`` relative to repo root or absolute). If neither is
    resolvable the row is skipped with a recorded reason — emitting a
    placeholder would silently poison SFT.
  * Filters are *fail-conservative*: rows with ``alignment_review_required``
    true, ``split`` outside the requested set, ``alignment_score`` below
    the configured floor, or with empty/whitespace text after NFC
    normalization are skipped with a counted reason.
  * Loss mask is **target-only** for directional rows, matching the
    Stage-2 ADR (`labels=-100` on prompt tokens — non-negotiable). The
    JSONL records the directive; the trainer enforces it.
  * Contamination guard (#4) is intentionally *not* implemented here.
    A separate pass against ``data/evals/eval_hashes.jsonl`` runs
    before any training read; this script must not pretend to gate.
  * Splits are passed through verbatim from the manifest. We never
    re-split here — split assignment is the manifest's job.

Usage:
    python scripts/330_emit_stage2_sft_jsonl.py --dry-run
    python scripts/330_emit_stage2_sft_jsonl.py \
        --manifest data/stage2/stage2_manifest.jsonl \
        --out data/stage2/stage2_sft.jsonl \
        --splits train,dev \
        --directions both \
        --min-alignment-score 0.75

Exit codes:
    0 success (incl. dry-run)
    1 I/O / schema error
    2 nothing emitted under requested filters (likely a config bug;
      a deliberate empty emit can pass with --allow-empty)
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_STAGE2 = REPO_ROOT / "data" / "stage2"

DEFAULT_MANIFEST = DATA_STAGE2 / "stage2_manifest.jsonl"
DEFAULT_OUTPUT = DATA_STAGE2 / "stage2_sft.jsonl"

# Default instruction templates. Mirrored from docs/data-pipeline.md
# §"Stage 2 output JSONL". Real runs swap in ~5 paraphrases per
# direction loaded from data/stage2/templates.json — wired as a TODO.
DEFAULT_INSTRUCTIONS: dict[str, str] = {
    "en->haw": "Translate the following English sentence into Hawaiian.",
    "haw->en": "Unuhi i kēia ʻōlelo Pelekānia mai ka ʻōlelo Hawaiʻi.",
}

# Alignment types accepted into directional SFT. Retention-slice
# (haw-mono) rows are out of scope for this script — they come from the
# Stage-1 builder and are merged into the Stage-2 JSONL by a separate
# step, see docs/data-pipeline.md §"Stage 2 output JSONL" notes.
DIRECTIONAL_ALIGNMENT_TYPES = {
    "parallel-verse",
    "parallel-sentence",
    "parallel-doc",
    "comparable-aligned",
    "dictionary-example",
    "synthetic-bt",
    "synthetic-ft",
}

# Keys we copy verbatim from the manifest into each emitted row as
# provenance. Kept narrow on purpose — anything heavier lives in the
# manifest, queryable by pair_id.
PROVENANCE_KEYS = (
    "pair_id",
    "source",
    "register",
    "alignment_type",
    "alignment_method",
    "alignment_score",
    "synthetic",
    "synthetic_source_model",
    "edition_or_version",
    "prototype_only",
    "release_eligible",
    "dedup_cluster_id",
    "crosslink_stage1_overlap",
)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


# ---------- I/O ----------

def iter_manifest(path: Path) -> Iterator[dict]:
    """Yield manifest rows, failing loudly on bad JSON.

    Mirrors ``code/llm_hawaii/data.iter_jsonl`` — silent skips would
    hide corpus problems. Empty lines are tolerated.
    """
    if not path.exists():
        raise FileNotFoundError(f"Stage-2 manifest not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"Bad JSON at {path}:{lineno}: {e}") from e


# ---------- Text resolution ----------

@dataclass
class ResolvedPair:
    text_en: str
    text_haw: str
    en_inline: bool
    haw_inline: bool


def _resolve_side(row: dict, side: str) -> tuple[str | None, bool, str | None]:
    """Return (text, was_inline, error) for one side ('en' or 'haw').

    Order of resolution:
      1. inline ``text_<side>`` field on the row,
      2. ``text_<side>_path`` ref (absolute or relative to REPO_ROOT),
      3. unresolved → return error reason; caller decides skip vs fail.
    """
    inline_key = f"text_{side}"
    path_key = f"text_{side}_path"

    inline = row.get(inline_key)
    if isinstance(inline, str) and inline.strip():
        return _nfc(inline), True, None

    ref = row.get(path_key)
    if isinstance(ref, str) and ref.strip():
        p = Path(ref)
        if not p.is_absolute():
            p = (REPO_ROOT / p).resolve()
        if not p.exists():
            return None, False, f"text_ref_missing:{side}:{ref}"
        try:
            text = p.read_text(encoding="utf-8")
        except OSError as e:
            return None, False, f"text_ref_unreadable:{side}:{e}"
        if not text.strip():
            return None, False, f"text_ref_empty:{side}"
        return _nfc(text), False, None

    return None, False, f"text_missing:{side}"


def resolve_pair(row: dict) -> tuple[ResolvedPair | None, str | None]:
    en_text, en_inline, en_err = _resolve_side(row, "en")
    haw_text, haw_inline, haw_err = _resolve_side(row, "haw")
    if en_err or haw_err:
        # TODO(text-refs): wire a content-addressed loader once the
        # Stage-2 pipeline emits sha256_*_clean -> blob mappings. For
        # now refs are file paths only.
        return None, en_err or haw_err
    assert en_text is not None and haw_text is not None
    return ResolvedPair(en_text, haw_text, en_inline, haw_inline), None


# ---------- Filtering ----------

@dataclass
class EmitConfig:
    splits: set[str]
    directions: set[str]              # subset of {"en->haw", "haw->en"}
    min_alignment_score: float | None
    allow_review_required: bool
    allow_synthetic: bool
    instructions: dict[str, str]


def _passes_filters(row: dict, cfg: EmitConfig) -> tuple[bool, str | None]:
    split = row.get("split")
    if split not in cfg.splits:
        return False, f"split_filtered:{split}"

    if not cfg.allow_review_required and bool(row.get("alignment_review_required")):
        return False, "alignment_review_required"

    if not cfg.allow_synthetic and bool(row.get("synthetic")):
        return False, "synthetic_excluded"

    atype = row.get("alignment_type")
    if atype not in DIRECTIONAL_ALIGNMENT_TYPES:
        return False, f"alignment_type_filtered:{atype}"

    if cfg.min_alignment_score is not None:
        score = row.get("alignment_score")
        # Deterministic alignments (verse-id, tmx-line, etc.) carry a
        # null score by convention — admit them; the floor only gates
        # embedding-aligned rows.
        if score is not None:
            try:
                if float(score) < cfg.min_alignment_score:
                    return False, "alignment_score_below_floor"
            except (TypeError, ValueError):
                return False, "alignment_score_unparseable"

    return True, None


# ---------- Row construction ----------

def _provenance(row: dict) -> dict[str, Any]:
    return {k: row[k] for k in PROVENANCE_KEYS if k in row}


def build_directional_row(
    row: dict,
    direction: str,
    pair: ResolvedPair,
    cfg: EmitConfig,
) -> dict[str, Any]:
    """Build one en->haw or haw->en SFT example for a manifest pair.

    Row shape mirrors docs/data-pipeline.md §"Stage 2 output JSONL"
    exactly so the trainer's reader stays a thin map.
    """
    if direction == "en->haw":
        source_lang, target_lang = "en", "haw"
        source_text, target_text = pair.text_en, pair.text_haw
        suffix = "en2haw"
    elif direction == "haw->en":
        source_lang, target_lang = "haw", "en"
        source_text, target_text = pair.text_haw, pair.text_en
        suffix = "haw2en"
    else:
        raise ValueError(f"Unknown direction: {direction}")

    pair_id = row.get("pair_id") or row.get("sha256_pair") or "unknown-pair"
    out: dict[str, Any] = {
        "example_id": f"{pair_id}:{suffix}",
        "pair_id": pair_id,
        "direction": direction,
        "instruction": cfg.instructions[direction],
        "source_lang": source_lang,
        "target_lang": target_lang,
        "source_text": source_text,
        "target_text": target_text,
        "loss_mask": "target_only",
        "split": row.get("split"),
    }
    out.update(_provenance(row))
    return out


# ---------- Emitter ----------

@dataclass
class EmitStats:
    rows_in: int = 0
    rows_emitted: int = 0
    pairs_kept: int = 0
    pairs_skipped: int = 0
    skip_reasons: Counter = field(default_factory=Counter)


def emit(
    manifest: Path,
    out_path: Path,
    cfg: EmitConfig,
    dry_run: bool = False,
) -> EmitStats:
    stats = EmitStats()
    out_fp = None
    if not dry_run:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_fp = out_path.open("w", encoding="utf-8")

    try:
        for row in iter_manifest(manifest):
            stats.rows_in += 1

            ok, reason = _passes_filters(row, cfg)
            if not ok:
                stats.pairs_skipped += 1
                stats.skip_reasons[reason or "unknown"] += 1
                continue

            pair, err = resolve_pair(row)
            if pair is None:
                stats.pairs_skipped += 1
                stats.skip_reasons[err or "text_unresolved"] += 1
                continue

            stats.pairs_kept += 1
            for direction in ("en->haw", "haw->en"):
                if direction not in cfg.directions:
                    continue
                example = build_directional_row(row, direction, pair, cfg)
                stats.rows_emitted += 1
                if out_fp is not None:
                    out_fp.write(json.dumps(example, ensure_ascii=False) + "\n")
    finally:
        if out_fp is not None:
            out_fp.close()
    return stats


# ---------- CLI ----------

def _parse_directions(s: str) -> set[str]:
    s = s.strip().lower()
    if s in {"both", "bi", "bidirectional"}:
        return {"en->haw", "haw->en"}
    if s in {"en2haw", "en->haw", "en-haw"}:
        return {"en->haw"}
    if s in {"haw2en", "haw->en", "haw-en"}:
        return {"haw->en"}
    raise argparse.ArgumentTypeError(f"unknown direction selector: {s!r}")


def _parse_splits(s: str) -> set[str]:
    parts = [p.strip() for p in s.split(",") if p.strip()]
    if not parts:
        raise argparse.ArgumentTypeError("--splits cannot be empty")
    return set(parts)


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Emit Stage-2 bidirectional SFT JSONL from a Stage-2 manifest.",
    )
    p.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help=f"Stage-2 manifest JSONL (default: {DEFAULT_MANIFEST.relative_to(REPO_ROOT)}).",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output JSONL path under data/ (default: {DEFAULT_OUTPUT.relative_to(REPO_ROOT)}).",
    )
    p.add_argument(
        "--splits",
        type=_parse_splits,
        default={"train"},
        help="Comma-separated splits to emit (default: train).",
    )
    p.add_argument(
        "--directions",
        type=_parse_directions,
        default={"en->haw", "haw->en"},
        help="Direction selector: both | en2haw | haw2en (default: both).",
    )
    p.add_argument(
        "--min-alignment-score",
        type=float,
        default=None,
        help="Floor on alignment_score for embedding-aligned rows. "
             "Deterministic alignments (null score) are always admitted.",
    )
    p.add_argument(
        "--allow-review-required",
        action="store_true",
        help="Include rows with alignment_review_required=true (off by default).",
    )
    p.add_argument(
        "--allow-synthetic",
        action="store_true",
        help="Include synthetic rows (off by default; cap is enforced upstream).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Read and filter the manifest; do not write the output JSONL.",
    )
    p.add_argument(
        "--allow-empty",
        action="store_true",
        help="Exit 0 even when zero rows survive filters (default: exit 2).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_argparser().parse_args(argv)

    cfg = EmitConfig(
        splits=args.splits,
        directions=args.directions,
        min_alignment_score=args.min_alignment_score,
        allow_review_required=args.allow_review_required,
        allow_synthetic=args.allow_synthetic,
        instructions=dict(DEFAULT_INSTRUCTIONS),
    )

    started = _utcnow_iso()
    try:
        stats = emit(args.manifest, args.out, cfg, dry_run=args.dry_run)
    except (FileNotFoundError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    finished = _utcnow_iso()
    summary = {
        "manifest": str(args.manifest),
        "out": str(args.out) if not args.dry_run else None,
        "dry_run": args.dry_run,
        "splits": sorted(cfg.splits),
        "directions": sorted(cfg.directions),
        "min_alignment_score": cfg.min_alignment_score,
        "rows_in": stats.rows_in,
        "pairs_kept": stats.pairs_kept,
        "pairs_skipped": stats.pairs_skipped,
        "rows_emitted": stats.rows_emitted,
        "skip_reasons": dict(stats.skip_reasons),
        "started": started,
        "finished": finished,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if stats.rows_emitted == 0 and not args.allow_empty:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
