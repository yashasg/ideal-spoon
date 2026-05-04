#!/bin/sh
# run_frontier_eval.sh — run frontier model eval via GitHub Models/Azure + Semantic Kernel.
#
# This wraps `python -m llm_hawaii.eval_frontier` with the frozen Stage 0
# eval contract (stage0.v1 prompt suite, W1 manual micro-eval metadata probe,
# human_fetch translation probe).
#
# Outputs written to:
#   data/eval_runs/frontier/<stamp>__frontier_<provider>_<model>_eval.json (ignored)
#   docs/eval-runs/frontier/<stamp>__frontier_<provider>_<model>_eval_summary.json (tracked)
#
# Usage:
#   ./scripts/run_frontier_eval.sh
#   MODELS="gpt-4o,claude-opus-4" ./scripts/run_frontier_eval.sh
#   FRONTIER_PROVIDER=azure ./scripts/run_frontier_eval.sh
#   DRY_RUN=1 ./scripts/run_frontier_eval.sh
#   GITHUB_TOKEN=gho_... ./scripts/run_frontier_eval.sh
#   AZURE_OPENAI_API_KEY=... FRONTIER_PROVIDER=azure ./scripts/run_frontier_eval.sh

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
cd "$REPO_ROOT"

PYTHON=${PYTHON:-python3}
ENV_FILE=${ENV_FILE:-data/.env}

load_local_env() {
    env_file="$1"
    [ -f "$env_file" ] || return 0
    while IFS= read -r line || [ -n "$line" ]; do
        case "$line" in
            ""|\#*) continue ;;
        esac
        key=${line%%=*}
        value=${line#*=}
        [ "$key" != "$line" ] || continue
        case "$key" in
            FRONTIER_PROVIDER|PROVIDER|MODELS|ENDPOINT|GITHUB_MODELS_ENDPOINT|GITHUB_TOKEN|GH_TOKEN|AZURE_OPENAI_ENDPOINT|AZURE_OPENAI_API_KEY|AZURE_OPENAI_GPT5_DEPLOYMENT|AZURE_OPENAI_DEPLOYMENT|AZURE_OPENAI_API_VERSION)
                case "$value" in
                    \"*\") value=${value#\"}; value=${value%\"} ;;
                    \'*\') value=${value#\'}; value=${value%\'} ;;
                esac
                case "$key" in
                    FRONTIER_PROVIDER) current=${FRONTIER_PROVIDER:-} ;;
                    PROVIDER) current=${PROVIDER:-} ;;
                    MODELS) current=${MODELS:-} ;;
                    ENDPOINT) current=${ENDPOINT:-} ;;
                    GITHUB_MODELS_ENDPOINT) current=${GITHUB_MODELS_ENDPOINT:-} ;;
                    GITHUB_TOKEN) current=${GITHUB_TOKEN:-} ;;
                    GH_TOKEN) current=${GH_TOKEN:-} ;;
                    AZURE_OPENAI_ENDPOINT) current=${AZURE_OPENAI_ENDPOINT:-} ;;
                    AZURE_OPENAI_API_KEY) current=${AZURE_OPENAI_API_KEY:-} ;;
                    AZURE_OPENAI_GPT5_DEPLOYMENT) current=${AZURE_OPENAI_GPT5_DEPLOYMENT:-} ;;
                    AZURE_OPENAI_DEPLOYMENT) current=${AZURE_OPENAI_DEPLOYMENT:-} ;;
                    AZURE_OPENAI_API_VERSION) current=${AZURE_OPENAI_API_VERSION:-} ;;
                esac
                if [ -z "$current" ]; then
                    export "$key=$value"
                fi
                ;;
        esac
    done < "$env_file"
    echo ">> loaded local env: $env_file (secrets redacted)"
}

load_local_env "$ENV_FILE"

PROVIDER=${FRONTIER_PROVIDER:-${PROVIDER:-github-models}}
# Default model sweep — curated for GitHub Models catalog (best-effort).
# User should verify these models are available at the endpoint before
# running in production.
case "$PROVIDER" in
    azure|azure-openai)
        PROVIDER=azure
        MODELS=${MODELS:-${AZURE_OPENAI_GPT5_DEPLOYMENT:-${AZURE_OPENAI_DEPLOYMENT:-gpt-5-chat}}}
        ENDPOINT=${ENDPOINT:-${AZURE_OPENAI_ENDPOINT:-https://aifoundry672407977528-resource.openai.azure.com/}}
        ;;
    github|github-model|github-models)
        PROVIDER=github-models
        MODELS=${MODELS:-gpt-4o,claude-3.5-sonnet,claude-opus-4}
        ENDPOINT=${ENDPOINT:-${GITHUB_MODELS_ENDPOINT:-https://models.github.ai/inference/chat/completions}}
        ;;
    *)
        echo "error: unsupported provider '$PROVIDER' (expected github-models or azure)" >&2
        exit 1
        ;;
esac
OUTPUT_DIR=${OUTPUT_DIR:-data/eval_runs/frontier}
SUMMARY_DIR=${SUMMARY_DIR:-docs/eval-runs/frontier}
MANUAL_W1_JSONL=${MANUAL_W1_JSONL:-data/evals/manual_w1/w1-haw-micro-eval.jsonl}
USE_MANUAL_W1=${USE_MANUAL_W1:-1}
HUMAN_FETCH_JSONL=${HUMAN_FETCH_JSONL:-data/tokenizer_audit/ulukau_nupepa/human_fetch.jsonl}
USE_HUMAN_FETCH=${USE_HUMAN_FETCH:-1}
DRY_RUN=${DRY_RUN:-0}
EVAL_HASHES_LEDGER=${EVAL_HASHES_LEDGER:-data/evals/eval_hashes.jsonl}

if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "error: '$PYTHON' not found on PATH. Activate venv or set PYTHON=..." >&2
    exit 1
fi

GH_TOKEN_VALUE=""
if [ "$PROVIDER" = "github-models" ]; then
    if [ -n "${GITHUB_TOKEN:-}" ]; then
        GH_TOKEN_VALUE="$GITHUB_TOKEN"
    elif [ -n "${GH_TOKEN:-}" ]; then
        GH_TOKEN_VALUE="$GH_TOKEN"
    elif command -v gh >/dev/null 2>&1; then
        GH_TOKEN_VALUE=$(gh auth token 2>/dev/null || echo "")
    fi

    if [ -z "$GH_TOKEN_VALUE" ]; then
        echo "error: GitHub token not found. Set GITHUB_TOKEN env var or run:" >&2
        echo "  gh auth refresh -s models:read" >&2
        echo "  export GITHUB_TOKEN=\$(gh auth token)" >&2
        exit 1
    fi
elif [ -z "${AZURE_OPENAI_API_KEY:-}" ]; then
    echo "error: Azure OpenAI key not found. Set AZURE_OPENAI_API_KEY or add it to data/.env" >&2
    exit 1
fi

mkdir -p "$OUTPUT_DIR"
mkdir -p "$SUMMARY_DIR"
STAMP=$(date -u +"%Y%m%dT%H%M%SZ")

echo ">> provider:   $PROVIDER"
echo ">> endpoint:   $ENDPOINT"
echo ">> models:     $MODELS"
echo ">> output_dir: $OUTPUT_DIR"
echo ">> summary_dir: $SUMMARY_DIR"
echo ">> prompt suite: stage0.v1 (frozen)"
if [ "$USE_MANUAL_W1" = "1" ]; then
    if [ -f "$MANUAL_W1_JSONL" ]; then
        echo ">> W1 manual JSONL: $MANUAL_W1_JSONL (present)"
    else
        echo ">> W1 manual JSONL: $MANUAL_W1_JSONL (missing — status will be 'missing')"
    fi
else
    echo ">> W1 manual JSONL: disabled"
fi
if [ "$USE_HUMAN_FETCH" = "1" ]; then
    if [ -f "$HUMAN_FETCH_JSONL" ]; then
        echo ">> human_fetch JSONL: $HUMAN_FETCH_JSONL (present)"
    else
        echo ">> human_fetch JSONL: $HUMAN_FETCH_JSONL (missing — translation probe will report 'missing')"
    fi
else
    echo ">> human_fetch JSONL: disabled"
fi

build_cmd() {
    local model_id="$1"
    local output="$2"
    if [ "$PROVIDER" = "azure" ]; then
        echo "PYTHONPATH=code FRONTIER_PROVIDER=azure AZURE_OPENAI_ENDPOINT='$ENDPOINT' AZURE_OPENAI_API_KEY=<redacted> $PYTHON -m llm_hawaii.eval_frontier \\"
    else
        echo "PYTHONPATH=code GITHUB_TOKEN=<redacted> $PYTHON -m llm_hawaii.eval_frontier \\"
    fi
    echo "  --provider '$PROVIDER' \\"
    echo "  --model-id '$model_id' \\"
    echo "  --endpoint '$ENDPOINT' \\"
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
    echo "  > '$output'"
}

if [ "$DRY_RUN" = "1" ]; then
    echo ">> dry run: planned invocations:"
    echo
    OLD_IFS="$IFS"
    IFS=","
    for model_id in $MODELS; do
        model_safe=$(echo "$model_id" | tr '/' '_' | tr -cd '[:alnum:]_-')
        output="$OUTPUT_DIR/${STAMP}__frontier_${PROVIDER}_${model_safe}_eval.json"
        build_cmd "$model_id" "$output"
        echo
    done
    IFS="$OLD_IFS"
    exit 0
fi

# Run eval for each model
OLD_IFS="$IFS"
IFS=","
for model_id in $MODELS; do
    model_safe=$(echo "$model_id" | tr '/' '_' | tr -cd '[:alnum:]_-')
    output="$OUTPUT_DIR/${STAMP}__frontier_${PROVIDER}_${model_safe}_eval.json"
    summary="$SUMMARY_DIR/${STAMP}__frontier_${PROVIDER}_${model_safe}_eval_summary.json"
    tmp_output="$output.tmp.$$"
    trap 'rm -f "$tmp_output"' EXIT HUP INT TERM
    
    echo
    echo ">> running frontier eval for: $model_id"
    echo ">>   output: $output"
    echo ">>   summary: $summary"
    
    set -- --provider "$PROVIDER" --model-id "$model_id" --endpoint "$ENDPOINT"
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
    
    if [ "$PROVIDER" = "azure" ]; then
        PYTHONPATH=code FRONTIER_PROVIDER=azure AZURE_OPENAI_ENDPOINT="$ENDPOINT" "$PYTHON" -m llm_hawaii.eval_frontier "$@" > "$tmp_output" && EVAL_RC=0 || EVAL_RC=$?
    else
        PYTHONPATH=code GITHUB_TOKEN="$GH_TOKEN_VALUE" "$PYTHON" -m llm_hawaii.eval_frontier "$@" > "$tmp_output" && EVAL_RC=0 || EVAL_RC=$?
    fi
    
    cat "$tmp_output"
    mv "$tmp_output" "$output"
    trap - EXIT HUP INT TERM
    
    if [ "$EVAL_RC" -ne 0 ]; then
        echo ">> eval_frontier.py exited non-zero (rc=$EVAL_RC); writing summary anyway." >&2
    fi
    
    # Write tracked summary
    "$PYTHON" - "$output" "$summary" "$PROVIDER" "$model_id" "$EVAL_HASHES_LEDGER" <<'PY'
import hashlib
import json
import sys
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


output = Path(sys.argv[1])
summary = Path(sys.argv[2])
provider = sys.argv[3]
model_id = sys.argv[4]
ledger_path = Path(sys.argv[5])

report = json.loads(output.read_text(encoding="utf-8"))
generations = report.get("generations") or []

# Hash-only summary
summary_doc = {
    "stage": "frontier_baseline",
    "schema_version": report.get("schema_version", "stage0_eval.v2"),
    "provider": provider,
    "model_id": model_id,
    "endpoint": report.get("identity", {}).get("endpoint"),
    "full_artifact": str(output),
    "full_artifact_sha256": sha256_file(output),
    "identity": report.get("identity", {"status": "absent"}),
    "decoding": report.get("decoding", {"status": "absent"}),
    "prompt_suite": report.get("prompt_suite", {"status": "absent"}),
    "generation_count": len(generations),
    "generation_sha256": report.get("generation_sha256") or {},
    "metrics": {
        "hawaiian_ppl": report.get("hawaiian_ppl"),
        "hawaiian_ppl_by_source": report.get("hawaiian_ppl_by_source", {"status": "absent"}),
        "english_ppl": report.get("english_ppl", {"status": "absent"}),
        "manual_w1": report.get("manual_w1", {"status": "absent"}),
        "human_fetch_translation": {
            k: v for k, v in report.get("human_fetch_translation", {}).items()
            if k not in ("note",)
        },
        "orthography_metrics": report.get("orthography_metrics"),
        "orthography_aggregate": report.get("orthography_aggregate", {"status": "absent"}),
    },
    "tripwires": report.get("tripwires", {"status": "absent"}),
}

summary.parent.mkdir(parents=True, exist_ok=True)
summary.write_text(
    json.dumps(summary_doc, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)

# Append to eval_hashes ledger
summary_sha = sha256_file(summary)
ledger_row = {
    "stage": "frontier_baseline",
    "provider": provider,
    "model_id": model_id,
    "summary_path": str(summary.relative_to(Path.cwd())),
    "summary_sha256": summary_sha,
    "suite_sha256": report.get("prompt_suite", {}).get("suite_sha256"),
}

if ledger_path.exists():
    with ledger_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(ledger_row, ensure_ascii=False) + "\n")
else:
    print(f"warning: eval_hashes ledger not found at {ledger_path}; skipping append", file=sys.stderr)

print(f">> summary written: {summary}", file=sys.stderr)
print(f">> summary sha256: {summary_sha}", file=sys.stderr)
PY

done
IFS="$OLD_IFS"

echo
echo "done. Frontier eval reports written to: $OUTPUT_DIR/"
echo "tracked summaries written to: $SUMMARY_DIR/"
