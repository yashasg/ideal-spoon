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
# PROMPT is optional. When unset, evaluate.py runs its built-in fixed
# prompt suite (low/medium/high diacritic density + English control) so
# orthography drift can be tracked across checkpoints. Set PROMPT=... to
# add an additional ad-hoc prompt; set USE_SUITE=0 to skip the suite.
PROMPT=${PROMPT:-}
USE_SUITE=${USE_SUITE:-1}
MANUAL_W1_JSONL=${MANUAL_W1_JSONL:-data/evals/manual_w1/w1-haw-micro-eval.jsonl}
USE_MANUAL_W1=${USE_MANUAL_W1:-1}
# human_fetch parallel pair JSONL for the bidirectional translation probe.
# Regenerate locally with: python3 scripts/_convert_ulukau_human_fetch.py
# If absent, the probe reports status=missing and does not fail the eval.
HUMAN_FETCH_JSONL=${HUMAN_FETCH_JSONL:-data/tokenizer_audit/ulukau_nupepa/human_fetch.jsonl}
USE_HUMAN_FETCH=${USE_HUMAN_FETCH:-1}
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
echo ">> prompt suite: $([ "$USE_SUITE" = "1" ] && echo "default (stage0.v1)" || echo "disabled")"
if [ "$USE_MANUAL_W1" = "1" ]; then
    if [ -f "$MANUAL_W1_JSONL" ]; then
        echo ">> W1 manual JSONL: $MANUAL_W1_JSONL (present)"
    else
        echo ">> W1 manual JSONL: $MANUAL_W1_JSONL (missing — status will be 'missing')"
    fi
else
    echo ">> W1 manual JSONL: disabled (status=not_configured)"
fi
if [ "$USE_HUMAN_FETCH" = "1" ]; then
    if [ -f "$HUMAN_FETCH_JSONL" ]; then
        echo ">> human_fetch JSONL: $HUMAN_FETCH_JSONL (present)"
    else
        echo ">> human_fetch JSONL: $HUMAN_FETCH_JSONL (missing — translation probe will report 'missing')"
    fi
else
    echo ">> human_fetch JSONL: disabled (status=not_configured)"
fi
[ -n "$PROMPT" ] && echo ">> extra prompt: $PROMPT"

build_cmd() {
    echo "PYTHONPATH=code $PYTHON -m llm_hawaii.evaluate \\"
    echo "  --checkpoint '$CHECKPOINT' \\"
    echo "  --eval-file '$EVAL_FILE' \\"
    if [ "$USE_SUITE" != "1" ]; then
        echo "  --no-prompt-suite \\"
    fi
    if [ -n "$PROMPT" ]; then
        echo "  --prompt '$PROMPT' \\"
    fi
    if [ "$USE_MANUAL_W1" != "1" ]; then
        echo "  --no-manual-w1 \\"
    elif [ -n "$MANUAL_W1_JSONL" ]; then
        echo "  --manual-w1-jsonl '$MANUAL_W1_JSONL' \\"
    fi
    if [ "$USE_HUMAN_FETCH" != "1" ]; then
        echo "  --no-human-fetch"
    elif [ -n "$HUMAN_FETCH_JSONL" ]; then
        echo "  --human-fetch-jsonl '$HUMAN_FETCH_JSONL'"
    fi
}

if [ "$DRY_RUN" = "1" ]; then
    echo ">> dry run command:"
    build_cmd
    exit 0
fi

# Build argv for python; keep it POSIX-shell-safe.
set -- --checkpoint "$CHECKPOINT" --eval-file "$EVAL_FILE"
if [ "$USE_SUITE" != "1" ]; then
    set -- "$@" --no-prompt-suite
fi
if [ -n "$PROMPT" ]; then
    set -- "$@" --prompt "$PROMPT"
fi
if [ "$USE_MANUAL_W1" != "1" ]; then
    set -- "$@" --no-manual-w1
elif [ -n "$MANUAL_W1_JSONL" ]; then
    set -- "$@" --manual-w1-jsonl "$MANUAL_W1_JSONL"
fi
if [ "$USE_HUMAN_FETCH" != "1" ]; then
    set -- "$@" --no-human-fetch
elif [ -n "$HUMAN_FETCH_JSONL" ]; then
    set -- "$@" --human-fetch-jsonl "$HUMAN_FETCH_JSONL"
fi

PYTHONPATH=code "$PYTHON" -m llm_hawaii.evaluate "$@" > "$TMP_OUTPUT" && EVAL_RC=0 || EVAL_RC=$?

cat "$TMP_OUTPUT"
mv "$TMP_OUTPUT" "$OUTPUT"
trap - EXIT HUP INT TERM

if [ "$EVAL_RC" -ne 0 ]; then
    echo ">> evaluate.py exited non-zero (rc=$EVAL_RC); writing tracked summary anyway." >&2
fi

"$PYTHON" - "$OUTPUT" "$SUMMARY" "$CHECKPOINT" "$EVAL_FILE" "$PROMPT" "$USE_SUITE" "$USE_MANUAL_W1" "$MANUAL_W1_JSONL" "$USE_HUMAN_FETCH" "$HUMAN_FETCH_JSONL" <<'PY'
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
use_suite = sys.argv[6] == "1"
use_manual_w1 = sys.argv[7] == "1"
manual_w1_jsonl = sys.argv[8]
use_human_fetch = sys.argv[9] == "1"
human_fetch_jsonl = sys.argv[10]

report = json.loads(output.read_text(encoding="utf-8"))
generations = report.get("generations") or []

command = [
    "python",
    "-m",
    "llm_hawaii.evaluate",
    "--checkpoint",
    checkpoint,
    "--eval-file",
    str(eval_file),
]
if not use_suite:
    command.append("--no-prompt-suite")
if prompt:
    command.extend(["--prompt", prompt])
if not use_manual_w1:
    command.append("--no-manual-w1")
elif manual_w1_jsonl:
    command.extend(["--manual-w1-jsonl", manual_w1_jsonl])
if not use_human_fetch:
    command.append("--no-human-fetch")
elif human_fetch_jsonl:
    command.extend(["--human-fetch-jsonl", human_fetch_jsonl])

# Sanitise the human_fetch_translation probe for the hash-only summary:
# strip any fields that could carry raw text (there should be none by
# contract, but we defensively exclude 'note', 'path', and 'reason').
def _safe_translation_probe(probe):
    if not isinstance(probe, dict):
        return {"status": "absent"}
    safe = {
        k: v for k, v in probe.items()
        if k not in ("note",)
    }
    # Each direction dict is already hash-only; pass through as-is.
    return safe

# Hash-only summary: keep generations text out (full artifact has it).
summary_doc = {
    "stage": "stage0",
    "schema_version": report.get("schema_version", "unknown"),
    "checkpoint": checkpoint,
    "eval_file": str(eval_file),
    "eval_file_sha256": sha256_file(eval_file),
    "full_artifact": str(output),
    "full_artifact_sha256": sha256_file(output),
    "source_git_commit": git_commit(),
    "command": command,
    "identity": report.get("identity", {"status": "absent"}),
    "decoding": report.get("decoding", {"status": "absent"}),
    "ppl_config": report.get("ppl_config", {"status": "absent"}),
    "eval_set": report.get("eval_set", {"status": "absent"}),
    "prompt_suite": report.get(
        "prompt_suite", {"status": "absent"}
    ),
    "prompt_count": len(generations),
    "generation_count": len(generations),
    "generation_sha256": report.get("generation_sha256")
    or {f"sample_{i}": sha256_text(g) for i, g in enumerate(generations)},
    "metrics": {
        "hawaiian_ppl": report.get("hawaiian_ppl"),
        "hawaiian_ppl_by_source": report.get(
            "hawaiian_ppl_by_source", {"status": "absent"}
        ),
        "english_ppl": report.get("english_ppl", {"status": "absent"}),
        "manual_w1": report.get("manual_w1", {"status": "absent"}),
        "human_fetch_translation": _safe_translation_probe(
            report.get("human_fetch_translation", {"status": "absent"})
        ),
        "orthography_metrics": report.get("orthography_metrics"),
        "orthography_aggregate": report.get(
            "orthography_aggregate", {"status": "absent"}
        ),
    },
    "tripwires": report.get("tripwires", {"status": "absent"}),
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

# Linus posture: invalid W1 inputs (orthographic failure on accepted rows,
# header mismatch, etc.) flip evaluate.py to exit 2 *after* writing the
# report. Propagate that here so a bad W1 file doesn't silently land as a
# green Stage 0 run. The artifact and the tracked summary are still on
# disk for inspection.
if [ "${EVAL_RC:-0}" -ne 0 ]; then
    echo "warning: evaluate.py exited rc=$EVAL_RC; see manual_w1 status in the artifact." >&2
    exit "$EVAL_RC"
fi
