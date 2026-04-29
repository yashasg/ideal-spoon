#!/usr/bin/env python3
"""Score Stage-2 candidate pairs against the alignment / quality policy.

Issue #12. Reads a JSONL of *candidate* en↔haw pairs and emits an
annotated JSONL plus a small summary report. Stdlib only.

Input format (one object per line) — minimum fields:

    {
      "pair_id":         "bible-ioane-3-16",
      "text_haw":        "No ka mea, ua aloha nui mai ke Akua ...",
      "text_en":         "For God so loved the world ...",
      "alignment_type":   "parallel-verse",
      "alignment_method": "verse-id"
    }

Optional fields are passed through and consulted when present
(`alignment_score`, `alignment_model`, `lang_id_*`, `lang_id_*_confidence`,
`source_url_*`, `synthetic`, ...). See `code/llm_hawaii/stage2_quality.py`
for the full contract.

Output:

  * `<output>.jsonl` — one row per input, original fields plus the
    annotation dict from `score_pair()`. Non-destructive: existing keys
    on input are preserved unless overwritten by the policy (e.g.,
    `alignment_review_required` is recomputed).
  * `<output>.summary.json` — counts per tier, per flag, plus the
    serialized active policy for the run report.

Outputs are written under the local-only ignored ``data/`` tree by
default. No corpus text is committed.

Usage::

    python scripts/321_score_stage2_alignment.py \
        --input  data/stage2/_candidates/bible.jsonl \
        --output data/stage2/_scored/bible
    python scripts/321_score_stage2_alignment.py --self-test

Exit codes:
    0  success
    2  CLI misuse
    3  processing failure
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

# Make `code/` importable so the script can be run from the repo root
# without packaging.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_CODE_DIR = _REPO_ROOT / "code"
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

from llm_hawaii.stage2_quality import (  # noqa: E402
    POLICY_VERSION,
    PolicyConfig,
    policy_summary,
    score_pair,
)


def _iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield line_no, json.loads(line)
            except json.JSONDecodeError as e:
                print(f"[ERROR] Bad JSON at {path}:{line_no}: {e}", file=sys.stderr)
                sys.exit(3)


def _write_jsonl(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def run(input_path: Path, output_stem: Path, config: PolicyConfig) -> int:
    annotated: list[dict] = []
    tier_counts: Counter[str] = Counter()
    flag_counts: Counter[str] = Counter()

    for _, pair in _iter_jsonl(input_path):
        ann = score_pair(pair, config)
        out = dict(pair)
        out.update(ann)
        annotated.append(out)
        tier_counts[ann["alignment_confidence_tier"]] += 1
        for f in ann["quality_flags"]:
            flag_counts[f] += 1

    out_jsonl = output_stem.with_suffix(".jsonl")
    out_summary = output_stem.with_suffix(".summary.json")
    _write_jsonl(annotated, out_jsonl)

    summary = {
        "input": str(input_path),
        "output": str(out_jsonl),
        "row_count": len(annotated),
        "tier_counts": dict(tier_counts),
        "flag_counts": dict(flag_counts),
        "policy": policy_summary(config),
    }
    out_summary.parent.mkdir(parents=True, exist_ok=True)
    with out_summary.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"[OK] policy={POLICY_VERSION} rows={len(annotated)} tiers={dict(tier_counts)}")
    print(f"[OK] wrote {out_jsonl}")
    print(f"[OK] wrote {out_summary}")
    return 0


def _self_test() -> int:
    """In-memory smoke against synthetic fixtures. Stdlib only."""
    fixtures = [
        # 1. Clean verse-aligned pair → accept.
        {
            "pair_id": "fx-bible-1",
            "text_haw": "No ka mea, ua aloha nui mai ke Akua i ko ke ao nei.",
            "text_en":  "For God so loved the world.",
            "alignment_type": "parallel-verse",
            "alignment_method": "verse-id",
            "source_url_en": "https://example.org/bible/en/john3-16",
            "source_url_haw": "https://example.org/bible/haw/john3-16",
        },
        # 2. Embedding-aligned, score in review band → review.
        {
            "pair_id": "fx-comp-1",
            "text_haw": "ʻO Hawaiʻi kēia ʻāina nani.",
            "text_en":  "Hawaiʻi is a beautiful land.",
            "alignment_type": "comparable-aligned",
            "alignment_method": "labse",
            "alignment_model": "LaBSE@dummy",
            "alignment_score": 0.62,
            "source_url_en": "https://example.org/a",
            "source_url_haw": "https://example.org/b",
        },
        # 3. Embedding-aligned, score below review_min → reject.
        {
            "pair_id": "fx-comp-2",
            "text_haw": "He nūpepa kēia.",
            "text_en":  "Quantum chromodynamics is complicated.",
            "alignment_type": "comparable-aligned",
            "alignment_method": "labse",
            "alignment_model": "LaBSE@dummy",
            "alignment_score": 0.10,
            "source_url_en": "https://example.org/a",
            "source_url_haw": "https://example.org/b",
        },
        # 4. Empty Hawaiian side → reject (hard flag).
        {
            "pair_id": "fx-empty",
            "text_haw": "",
            "text_en":  "Anything.",
            "alignment_type": "parallel-sentence",
            "alignment_method": "tmx-line",
        },
        # 5. Long Hawaiian side with no diacritics → review.
        {
            "pair_id": "fx-no-diacritics",
            "text_haw": "Aole loa e hiki ke kakau i keia paukuolelo me ka pono ole o na kahako a me ka okina ma ka mea kakau ana.",
            "text_en":  "It is impossible to write this paragraph correctly without proper kahako and okina from the writer.",
            "alignment_type": "parallel-sentence",
            "alignment_method": "manual",
            "source_url_en": "https://example.org/a",
            "source_url_haw": "https://example.org/b",
        },
    ]
    cfg = PolicyConfig()
    expected_tiers = ["accept", "review", "reject", "reject", "review"]
    seen = []
    for fx, expected in zip(fixtures, expected_tiers):
        ann = score_pair(fx, cfg)
        seen.append(ann["alignment_confidence_tier"])
        assert ann["policy_version"] == POLICY_VERSION
    if seen != expected_tiers:
        print(f"[FAIL] expected={expected_tiers} got={seen}", file=sys.stderr)
        return 3
    print(f"[OK] self-test passed: tiers={seen}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--input", type=Path, help="Input JSONL of candidate pairs.")
    ap.add_argument(
        "--output",
        type=Path,
        help="Output stem; writes <stem>.jsonl and <stem>.summary.json.",
    )
    ap.add_argument(
        "--accept-min", type=float, default=PolicyConfig.accept_min,
        help="Override embedding-alignment accept threshold.",
    )
    ap.add_argument(
        "--review-min", type=float, default=PolicyConfig.review_min,
        help="Override embedding-alignment review threshold.",
    )
    ap.add_argument(
        "--self-test", action="store_true",
        help="Run an in-memory smoke against synthetic fixtures and exit.",
    )
    args = ap.parse_args()

    if args.self_test:
        return _self_test()

    if not args.input or not args.output:
        ap.error("--input and --output are required (or pass --self-test)")
    if not args.input.exists():
        print(f"[ERROR] input not found: {args.input}", file=sys.stderr)
        return 2

    cfg = PolicyConfig(accept_min=args.accept_min, review_min=args.review_min)
    return run(args.input, args.output, cfg)


if __name__ == "__main__":
    sys.exit(main())
