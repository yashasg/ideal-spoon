#!/bin/sh
# download_stage0_eval.sh - pull Stage 0 eval artifacts from a remote compute
# machine over SSH/SCP into the local repo.
#
# Mirrors the layout written by scripts/run_stage0_eval.sh:
#   - full eval JSONs   -> data/eval_runs/stage0/        (gitignored)
#   - hash-only summary -> docs/eval-runs/stage0/        (tracked)
#
# Usage:
#   ./scripts/download_stage0_eval.sh <ssh-destination> [remote-repo-path]
#
# Examples:
#   ./scripts/download_stage0_eval.sh user@gpu-box.example.com
#   ./scripts/download_stage0_eval.sh user@gpu-box ~/work/ideal-spoon
#   REMOTE_REPO=/srv/ideal-spoon ./scripts/download_stage0_eval.sh gpu-box
#
# Environment overrides:
#   SSH_DEST      ssh destination (user@host); CLI arg wins if both set
#   REMOTE_REPO   remote repo root (default: ~/ideal-spoon); CLI arg wins
#   SSH_PORT      ssh port (passed as -p / -P)
#   SSH_OPTS      extra ssh options, e.g. "-i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=accept-new"
#   SCP_OPTS      extra scp options (defaults to SSH_OPTS)
#   ONLY          one of: full | summary | both (default: both)
#   DRY_RUN       1 = print actions, do not connect or transfer
#   OVERWRITE     1 = allow overwriting existing local files (default: 0, skip)
#
# Notes:
# - Read-only on the remote (ls + scp). No remote mutations.
# - Local dirs are created if missing.
# - By default, files that already exist locally are skipped (no clobber).

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
cd "$REPO_ROOT"

usage() {
    sed -n '2,30p' "$0"
}

SSH_DEST_ARG=${1:-}
REMOTE_REPO_ARG=${2:-}

SSH_DEST=${SSH_DEST_ARG:-${SSH_DEST:-}}
REMOTE_REPO=${REMOTE_REPO_ARG:-${REMOTE_REPO:-~/ideal-spoon}}
ONLY=${ONLY:-both}
DRY_RUN=${DRY_RUN:-0}
OVERWRITE=${OVERWRITE:-0}
SSH_OPTS=${SSH_OPTS:-}
SCP_OPTS=${SCP_OPTS:-$SSH_OPTS}

if [ -z "${SSH_DEST:-}" ]; then
    echo "error: missing ssh destination (user@host)." >&2
    echo >&2
    usage >&2
    exit 2
fi

case "$ONLY" in
    full|summary|both) ;;
    *)
        echo "error: ONLY must be one of: full | summary | both (got '$ONLY')" >&2
        exit 2
        ;;
esac

# Build ssh / scp command prefixes. Keep quoting simple by using positional
# expansion via "$@"-like patterns; POSIX sh has no arrays, so we build
# strings and rely on word splitting only for the option lists.

SSH_PORT_OPT=""
SCP_PORT_OPT=""
if [ -n "${SSH_PORT:-}" ]; then
    SSH_PORT_OPT="-p $SSH_PORT"
    SCP_PORT_OPT="-P $SSH_PORT"
fi

# shellcheck disable=SC2086
run_scp() {
    src=$1
    dst=$2
    if [ "$DRY_RUN" = "1" ]; then
        echo "   + scp $SCP_PORT_OPT $SCP_OPTS $SSH_DEST:$src $dst"
        return 0
    fi
    scp $SCP_PORT_OPT $SCP_OPTS "$SSH_DEST:$src" "$dst"
}

# List remote files matching a glob under REMOTE_REPO/<subdir>. Prints
# bare filenames (one per line); empty if nothing matches.
# shellcheck disable=SC2086
list_remote() {
    subdir=$1
    pattern=$2
    # Use sh -lc so ~ in REMOTE_REPO expands on the remote side. The
    # `2>/dev/null || true` swallows "no matches" without aborting set -e.
    ssh $SSH_PORT_OPT $SSH_OPTS "$SSH_DEST" \
        "sh -lc 'cd $REMOTE_REPO/$subdir 2>/dev/null && ls -1 $pattern 2>/dev/null || true'"
}

fetch_dir() {
    label=$1
    subdir=$2
    pattern=$3

    local_dir="$REPO_ROOT/$subdir"
    mkdir -p "$local_dir"

    echo ">> $label: $SSH_DEST:$REMOTE_REPO/$subdir/$pattern -> $subdir/"

    if [ "$DRY_RUN" = "1" ]; then
        echo "   + ssh $SSH_PORT_OPT $SSH_OPTS $SSH_DEST \"sh -lc 'cd $REMOTE_REPO/$subdir && ls -1 $pattern'\""
        echo "   + scp $SCP_PORT_OPT $SCP_OPTS $SSH_DEST:$REMOTE_REPO/$subdir/$pattern $local_dir/"
        return 0
    fi

    files=$(list_remote "$subdir" "$pattern" || true)
    if [ -z "${files:-}" ]; then
        echo "   (no remote files matched)"
        return 0
    fi

    count_total=0
    count_fetched=0
    count_skipped=0
    # POSIX-friendly line iteration
    OLDIFS=$IFS
    IFS='
'
    for name in $files; do
        IFS=$OLDIFS
        count_total=$((count_total + 1))
        case "$name" in
            ''|'.'|'..') continue ;;
        esac
        dst="$local_dir/$name"
        if [ -e "$dst" ] && [ "$OVERWRITE" != "1" ]; then
            echo "   skip (exists): $subdir/$name"
            count_skipped=$((count_skipped + 1))
            IFS='
'
            continue
        fi
        run_scp "$REMOTE_REPO/$subdir/$name" "$dst"
        count_fetched=$((count_fetched + 1))
        IFS='
'
    done
    IFS=$OLDIFS

    echo "   fetched=$count_fetched skipped=$count_skipped total=$count_total"
}

echo ">> remote: $SSH_DEST:$REMOTE_REPO"
echo ">> local : $REPO_ROOT"
echo ">> mode  : ONLY=$ONLY DRY_RUN=$DRY_RUN OVERWRITE=$OVERWRITE"

case "$ONLY" in
    full|both)
        fetch_dir "full eval reports" "data/eval_runs/stage0" "*__stage0_base_eval.json"
        ;;
esac

case "$ONLY" in
    summary|both)
        fetch_dir "tracked summaries"  "docs/eval-runs/stage0" "*__stage0_base_eval_summary.json"
        ;;
esac

echo
echo "done."
