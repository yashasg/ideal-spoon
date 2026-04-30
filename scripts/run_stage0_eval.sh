#!/bin/sh
# run_stage0_eval.sh — run the Stage 0 base-model eval with project defaults.
#
# This wraps `python -m llm_hawaii.evaluate` with the current Stage 0 baseline
# inputs: frozen base checkpoint, FineWeb-2 Hawaiian dev JSONL, and one fixed
# Hawaiian generation prompt. Full output is written under ignored data/eval_runs/.
# A small hash-only summary is written under docs/eval-runs/ for git.
#
# Usage:
#   ./scripts/run_stage0_eval.sh
#   CHECKPOINT=meta-llama/Llama-3.1-8B ./scripts/run_stage0_eval.sh
#   EVAL_FILE=data/evals/fineweb2_haw/dev.jsonl ./scripts/run_stage0_eval.sh
#   PROMPT="E kākau ..." ./scripts/run_stage0_eval.sh
#   DRY_RUN=1 ./scripts/run_stage0_eval.sh

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
cd "$REPO_ROOT"

PYTHON=${PYTHON:-python3}
CHECKPOINT=${CHECKPOINT:-meta-llama/Llama-3.1-8B}
EVAL_FILE=${EVAL_FILE:-data/evals/fineweb2_haw/dev.jsonl}
OUTPUT_DIR=${OUTPUT_DIR:-data/eval_runs/stage0}
SUMMARY_DIR=${SUMMARY_DIR:-docs/eval-runs/stage0}
PROMPT=${PROMPT:-E kākau i hoʻokahi paukū pōkole ma ka ʻōlelo Hawaiʻi e pili ana i ka ʻohana.}
DRY_RUN=${DRY_RUN:-0}

if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "error: '$PYTHON' not found on PATH. Activate the training venv or set PYTHON=..." >&2
    exit 1
fi

if [ ! -f "$EVAL_FILE" ]; then
    echo "error: eval file not found: $EVAL_FILE" >&2
    echo "Restore the local eval artifacts before running Stage 0 eval." >&2
    exit 1
fi

mkdir -p "$OUTPUT_DIR"
mkdir -p "$SUMMARY_DIR"
STAMP=$(date -u +"%Y%m%dT%H%M%SZ")
OUTPUT=${OUTPUT:-"$OUTPUT_DIR/${STAMP}__stage0_base_eval.json"}
SUMMARY=${SUMMARY:-"$SUMMARY_DIR/${STAMP}__stage0_base_eval_summary.json"}
TMP_OUTPUT="$OUTPUT.tmp.$$"
trap 'rm -f "$TMP_OUTPUT"' EXIT HUP INT TERM

echo ">> checkpoint: $CHECKPOINT"
echo ">> eval file:  $EVAL_FILE"
echo ">> output:     $OUTPUT"
echo ">> summary:    $SUMMARY"

if [ "$DRY_RUN" = "1" ]; then
    echo ">> dry run command:"
    echo "PYTHONPATH=code $PYTHON -m llm_hawaii.evaluate \\"
    echo "  --checkpoint '$CHECKPOINT' \\"
    echo "  --eval-file '$EVAL_FILE' \\"
    echo "  --prompt '$PROMPT'"
    exit 0
fi

PYTHONPATH=code "$PYTHON" -m llm_hawaii.evaluate \
    --checkpoint "$CHECKPOINT" \
    --eval-file "$EVAL_FILE" \
    --prompt "$PROMPT" \
    > "$TMP_OUTPUT"

cat "$TMP_OUTPUT"
mv "$TMP_OUTPUT" "$OUTPUT"
trap - EXIT HUP INT TERM

"$PYTHON" - "$OUTPUT" "$SUMMARY" "$CHECKPOINT" "$EVAL_FILE" "$PROMPT" <<'PY'
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def git_commit():
    out = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        stderr=subprocess.DEVNULL,
        text=True,
    )
    return out.strip()


output = Path(sys.argv[1])
summary = Path(sys.argv[2])
checkpoint = sys.argv[3]
eval_file = Path(sys.argv[4])
prompt = sys.argv[5]

report = json.loads(output.read_text(encoding="utf-8"))
generations = report.get("generations") or []

summary_doc = {
    "stage": "stage0",
    "checkpoint": checkpoint,
    "eval_file": str(eval_file),
    "eval_file_sha256": sha256_file(eval_file),
    "full_artifact": str(output),
    "full_artifact_sha256": sha256_file(output),
    "source_git_commit": git_commit(),
    "command": [
        "python",
        "-m",
        "llm_hawaii.evaluate",
        "--checkpoint",
        checkpoint,
        "--eval-file",
        str(eval_file),
        "--prompt",
        prompt,
    ],
    "prompt_count": 1,
    "generation_count": len(generations),
    "generation_sha256": {
        f"sample_{i}": sha256_text(g) for i, g in enumerate(generations)
    },
    "metrics": {
        "hawaiian_ppl": report.get("hawaiian_ppl"),
        "orthography_metrics": report.get("orthography_metrics"),
    },
}

summary.parent.mkdir(parents=True, exist_ok=True)
summary.write_text(
    json.dumps(summary_doc, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)
PY

echo
echo "done. Stage 0 eval report written to:"
echo "    $OUTPUT"
echo "tracked Stage 0 summary written to:"
echo "    $SUMMARY"
