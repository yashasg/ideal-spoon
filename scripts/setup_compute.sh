#!/bin/sh
# Compatibility wrapper. Prefer:
#   python3 scripts/setup_training.py

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PYTHON=${PYTHON:-python3}

exec "$PYTHON" "$SCRIPT_DIR/setup_training.py" "$@"
