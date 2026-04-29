#!/bin/sh
# setup.sh — install raw-data-gathering dependencies into a local venv.
#
# POSIX sh, idempotent, safe to re-run.
# Playwright is intentionally skipped for now (see requirements.txt).
#
# Usage:
#   ./scripts/setup.sh            # create/refresh ./.venv and install deps
#   PYTHON=python3.11 ./scripts/setup.sh
#   VENV_DIR=.venv-data ./scripts/setup.sh

set -eu

# Resolve repo root from this script's location so it works from any cwd.
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
cd "$REPO_ROOT"

PYTHON=${PYTHON:-python3}
VENV_DIR=${VENV_DIR:-.venv}
REQ_FILE=${REQ_FILE:-requirements.txt}

if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "error: '$PYTHON' not found on PATH. Install Python 3.10+ or set PYTHON=..." >&2
    exit 1
fi

if [ ! -f "$REQ_FILE" ]; then
    echo "error: $REQ_FILE not found at $REPO_ROOT" >&2
    exit 1
fi

# Refuse to clobber a non-venv directory of the same name.
if [ -e "$VENV_DIR" ] && [ ! -f "$VENV_DIR/pyvenv.cfg" ]; then
    echo "error: $VENV_DIR exists but is not a Python venv. Refusing to touch it." >&2
    exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
    echo ">> creating venv at $VENV_DIR"
    "$PYTHON" -m venv "$VENV_DIR"
else
    echo ">> reusing existing venv at $VENV_DIR"
fi

# shellcheck disable=SC1091
. "$VENV_DIR/bin/activate"

echo ">> upgrading pip / wheel"
python -m pip install --upgrade pip wheel >/dev/null

echo ">> installing $REQ_FILE"
python -m pip install -r "$REQ_FILE"

echo
echo "done. Activate with:"
echo "    . $VENV_DIR/bin/activate"
echo
echo "Note: Playwright is intentionally not installed. If a target source"
echo "turns out to need JS rendering, add it explicitly — don't bake it in."
