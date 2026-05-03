#!/usr/bin/env bash
# Watch a training run dir and upload completed checkpoint-* folders to a private HF repo.
#
# A checkpoint is uploaded only after it has been observed on a previous poll
# (one-cycle defer), so the trainer is unlikely to still be writing it. This
# means the "latest" checkpoint gets uploaded the next time the watcher wakes
# up — we don't need a newer checkpoint to appear first.
#
# Idempotent: each uploaded checkpoint is recorded under
#   $RUN_DIR/.hf-upload-state/<name>.done
# Per-cycle observation markers are recorded under
#   $RUN_DIR/.hf-upload-state/<name>.seen
#
# Required env:
#   RUN_DIR           e.g. /root/ideal-spoon/runs/llama31-8b-stage1-multisource
#   HF_REPO           e.g. RainbowMassacre/llama31-hawaii-checkpoints
#   HF_UPLOAD_TOKEN   hf_... (write scope) — or HF_TOKEN as fallback
# Optional env:
#   POLL_SECONDS      default 60
#   REMOTE_PREFIX     default "checkpoints" (path inside the HF repo)
#
# Run:
#   export RUN_DIR=...; export HF_REPO=...; export HF_UPLOAD_TOKEN=...
#   bash scripts/watch_and_upload_checkpoints.sh

set -euo pipefail

POLL_SECONDS="${POLL_SECONDS:-60}"
RUN_DIR="${RUN_DIR:?set RUN_DIR first}"
HF_REPO="${HF_REPO:?set HF_REPO first}"
HF_UPLOAD_TOKEN="${HF_UPLOAD_TOKEN:-${HF_TOKEN:?set HF_UPLOAD_TOKEN or HF_TOKEN first}}"
REMOTE_PREFIX="${REMOTE_PREFIX:-checkpoints}"

UPLOAD_STATE_DIR="$RUN_DIR/.hf-upload-state"
mkdir -p "$UPLOAD_STATE_DIR"

# Prefer modern `hf`; fall back to `huggingface-cli`.
if command -v hf >/dev/null 2>&1; then
  HF=hf
elif command -v huggingface-cli >/dev/null 2>&1; then
  HF=huggingface-cli
else
  echo "neither 'hf' nor 'huggingface-cli' found; pip install -U huggingface_hub" >&2
  exit 2
fi

log() { printf '[%s] %s\n' "$(date -u +%FT%TZ)" "$*"; }

upload_one() {
  local ckpt_dir="$1"
  local name; name="$(basename "$ckpt_dir")"
  local marker="$UPLOAD_STATE_DIR/$name.done"

  [[ -f "$marker" ]] && { log "skip $name (already uploaded)"; return 0; }

  # Readiness: config.json + at least one weight shard
  [[ -f "$ckpt_dir/config.json" ]] || { log "skip $name (no config.json yet)"; return 0; }
  if ! compgen -G "$ckpt_dir/*.safetensors" >/dev/null \
     && ! compgen -G "$ckpt_dir/pytorch_model*.bin" >/dev/null; then
    log "skip $name (no weight shards yet)"
    return 0
  fi

  log "uploading $name -> $HF_REPO:$REMOTE_PREFIX/$name"
  if "$HF" upload "$HF_REPO" "$ckpt_dir" "$REMOTE_PREFIX/$name" \
        --repo-type model \
        --token "$HF_UPLOAD_TOKEN" \
        --commit-message "Upload $name" \
        --exclude "*.tmp" --exclude "*.lock"; then
    touch "$marker"
    log "✅ $name uploaded"
  else
    log "❌ upload failed for $name (will retry next poll)"
  fi
}

trap 'log "stopped"; exit 0' INT TERM

log "watching $RUN_DIR every ${POLL_SECONDS}s -> $HF_REPO:$REMOTE_PREFIX (one-cycle defer)"

while true; do
  log "scanning $RUN_DIR for checkpoint-*"

  mapfile -t checkpoints < <(
    find "$RUN_DIR" -maxdepth 1 -type d -name "checkpoint-*" 2>/dev/null \
      | sort -V
  )
  count="${#checkpoints[@]}"

  if [[ "$count" -eq 0 ]]; then
    log "found 0 checkpoint(s)"
  else
    # Upload any checkpoint we observed on a previous poll. Newly-appeared
    # checkpoints are only marked .seen this cycle and uploaded next wake.
    for ckpt in "${checkpoints[@]}"; do
      name="$(basename "$ckpt")"
      if [[ -f "$UPLOAD_STATE_DIR/$name.seen" ]]; then
        upload_one "$ckpt"
      else
        log "defer $name (first sighting; will upload next poll)"
        touch "$UPLOAD_STATE_DIR/$name.seen"
      fi
    done
  fi

  log "sleeping ${POLL_SECONDS}s"
  sleep "$POLL_SECONDS"
done
