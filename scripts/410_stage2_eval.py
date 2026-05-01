#!/usr/bin/env python3
"""Stage 2 eval gate CLI (issue #23).

Computes chrF and chrF++ for both ``en→haw`` and ``haw→en`` (reported
separately, never averaged), runs a leakage / contamination check against
the canonical eval-hash ledger and the Stage 2 manifest, and reports
Hawaiian orthography retention on the en→haw side.

This script does **not** load a model. Generation is the caller's job:
provide a predictions JSONL with one ``{"pair_id": ..., "hypothesis": ...}``
row per eval pair. Decoupling generation from scoring keeps the gate
runnable on a laptop and matches the contract used by `code/tests/`.

Output: a JSON report at ``runs/<run>/stage2_eval.json`` (or wherever
``--output`` points). The report shape is ``stage2_eval.v1`` (see
``code/llm_hawaii/stage2_eval.py::STAGE2_EVAL_SCHEMA``).

Smoke contract: ``python3 scripts/410_stage2_eval.py --self-test``
runs end-to-end on the bundled fixture and writes a report into a
temp directory.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

# Allow running from the repo root without installing the package.
REPO_ROOT = Path(__file__).resolve().parents[1]
CODE_ROOT = REPO_ROOT / "code"
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

from llm_hawaii.stage2_eval import (  # noqa: E402
    Stage2EvalConfig,
    run_stage2_eval,
)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--eval-jsonl",
        type=Path,
        help="Eval pairs JSONL (pair_id, direction, source, reference).",
    )
    p.add_argument(
        "--predictions-jsonl",
        type=Path,
        help="Model predictions JSONL (pair_id, hypothesis).",
    )
    p.add_argument(
        "--eval-hashes",
        type=Path,
        default=REPO_ROOT / "data/evals/eval_hashes.jsonl",
        help="Canonical eval-hash ledger. Default: data/evals/eval_hashes.jsonl",
    )
    p.add_argument(
        "--stage2-manifest",
        type=Path,
        default=REPO_ROOT / "data/stage2/stage2_manifest.jsonl",
        help="Stage 2 manifest JSONL. Default: data/stage2/stage2_manifest.jsonl",
    )
    p.add_argument(
        "--checkpoint",
        type=Path,
        default=None,
        help="Checkpoint dir under runs/<run>/ (recorded for provenance only).",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Where to write the report JSON. Default: runs/<run>/stage2_eval.json "
        "if --checkpoint is given, otherwise stdout.",
    )
    p.add_argument(
        "--no-sacrebleu",
        action="store_true",
        help="Force pure-Python chrF backend even if sacrebleu is installed.",
    )
    p.add_argument(
        "--no-eval-hashes",
        action="store_true",
        help="Skip the eval-hashes ledger check (verdict reported as 'skipped').",
    )
    p.add_argument(
        "--no-stage2-manifest",
        action="store_true",
        help="Skip the Stage 2 manifest collision check.",
    )
    p.add_argument(
        "--self-test",
        action="store_true",
        help="Run against the bundled tiny fixture; smoke contract for issue #23.",
    )
    return p


def _self_test() -> int:
    fixture_dir = REPO_ROOT / "code" / "tests" / "fixtures" / "stage2_eval"
    eval_path = fixture_dir / "eval_pairs.jsonl"
    pred_path = fixture_dir / "predictions.jsonl"
    if not eval_path.exists() or not pred_path.exists():
        print(
            f"self-test: fixture missing under {fixture_dir} — "
            "run from repo root and check the working tree.",
            file=sys.stderr,
        )
        return 2
    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "stage2_eval.json"
        cfg = Stage2EvalConfig(
            eval_jsonl=eval_path,
            predictions_jsonl=pred_path,
            eval_hashes_path=None,
            stage2_manifest_path=None,
            checkpoint_dir=None,
            prefer_sacrebleu=False,
        )
        report = run_stage2_eval(cfg)
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        sample = {
            "schema_version": report["schema_version"],
            "n_pairs_total": report["n_pairs_total"],
            "n_pairs_by_direction": report["n_pairs_by_direction"],
            "chrf_en_to_haw": report["translation"]["en_to_haw"]["chrf"]["score"],
            "chrf_pp_en_to_haw": report["translation"]["en_to_haw"][
                "chrf_plus_plus"
            ]["score"],
            "chrf_haw_to_en": report["translation"]["haw_to_en"]["chrf"]["score"],
            "chrf_pp_haw_to_en": report["translation"]["haw_to_en"][
                "chrf_plus_plus"
            ]["score"],
            "leakage_verdict": report["leakage"]["verdict"],
            "retention_tripwires": report["orthography_retention"]["tripwires"],
        }
        print(json.dumps(sample, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.self_test:
        return _self_test()

    if not args.eval_jsonl or not args.predictions_jsonl:
        print(
            "error: --eval-jsonl and --predictions-jsonl are required "
            "(or pass --self-test).",
            file=sys.stderr,
        )
        return 2

    cfg = Stage2EvalConfig(
        eval_jsonl=args.eval_jsonl,
        predictions_jsonl=args.predictions_jsonl,
        eval_hashes_path=None if args.no_eval_hashes else args.eval_hashes,
        stage2_manifest_path=(
            None if args.no_stage2_manifest else args.stage2_manifest
        ),
        checkpoint_dir=args.checkpoint,
        prefer_sacrebleu=not args.no_sacrebleu,
    )
    report = run_stage2_eval(cfg)

    output = args.output
    if output is None and args.checkpoint is not None:
        output = args.checkpoint / "stage2_eval.json"
    if output is None:
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
