#!/usr/bin/env python3
"""Watch a checkpoints dir and upload each new checkpoint-* folder to a private HF repo.

Usage:
    export HF_TOKEN=hf_...
    python3 scripts/watch_and_upload_checkpoints.py \
        --watch-dir runs/llama31-8b-stage1-multisource/checkpoints \
        --repo-id your-username/llama31-8b-stage1-haw \
        --interval 60

Notes:
- Treats a checkpoint as "ready" when it contains config.json AND a *.safetensors or pytorch_model.bin.
  This avoids partial uploads while transformers is still flushing shards.
- Records uploaded checkpoints in a local state file (.uploaded.json) inside --watch-dir
  so reruns / restarts skip already-uploaded folders.
- Each checkpoint becomes a path_in_repo equal to the folder name (e.g. checkpoint-4200/).
- Creates the repo as private if it doesn't exist.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

from huggingface_hub import HfApi, create_repo
from huggingface_hub.utils import HfHubHTTPError

CKPT_PREFIX = "checkpoint-"
STATE_FILENAME = ".uploaded.json"
READY_MARKERS = ("config.json",)
WEIGHT_GLOBS = ("*.safetensors", "pytorch_model.bin", "pytorch_model-*.bin")

log = logging.getLogger("ckpt-uploader")


def is_ready(ckpt_dir: Path) -> bool:
    if not all((ckpt_dir / m).exists() for m in READY_MARKERS):
        return False
    for pattern in WEIGHT_GLOBS:
        if any(ckpt_dir.glob(pattern)):
            return True
    return False


def load_state(state_path: Path) -> dict:
    if state_path.exists():
        try:
            return json.loads(state_path.read_text())
        except json.JSONDecodeError:
            log.warning("State file %s corrupt; starting fresh", state_path)
    return {"uploaded": {}}


def save_state(state_path: Path, state: dict) -> None:
    tmp = state_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True))
    tmp.replace(state_path)


def ensure_repo(api: HfApi, repo_id: str, token: str) -> None:
    try:
        create_repo(repo_id=repo_id, token=token, private=True, exist_ok=True)
    except HfHubHTTPError as e:
        log.error("Failed to ensure repo %s: %s", repo_id, e)
        raise


def upload_checkpoint(api: HfApi, ckpt_dir: Path, repo_id: str, token: str) -> str:
    path_in_repo = ckpt_dir.name
    log.info("Uploading %s -> %s:%s", ckpt_dir, repo_id, path_in_repo)
    commit = api.upload_folder(
        folder_path=str(ckpt_dir),
        path_in_repo=path_in_repo,
        repo_id=repo_id,
        token=token,
        commit_message=f"Upload {path_in_repo}",
        ignore_patterns=["*.tmp", "*.lock", "global_step*/optim*", ".uploaded.json"],
    )
    return getattr(commit, "oid", "") or str(commit)


def scan_once(watch_dir: Path, state: dict, api: HfApi, repo_id: str, token: str) -> int:
    uploaded = state.setdefault("uploaded", {})
    new_count = 0
    for child in sorted(watch_dir.iterdir()):
        if not child.is_dir() or not child.name.startswith(CKPT_PREFIX):
            continue
        if child.name in uploaded:
            continue
        if not is_ready(child):
            log.debug("Skipping %s — not ready yet", child.name)
            continue
        try:
            commit = upload_checkpoint(api, child, repo_id, token)
            uploaded[child.name] = {
                "uploaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "commit": commit,
            }
            save_state(watch_dir / STATE_FILENAME, state)
            new_count += 1
        except Exception:
            log.exception("Upload failed for %s; will retry next cycle", child.name)
    return new_count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watch-dir", required=True, type=Path)
    parser.add_argument("--repo-id", required=True, help="e.g. user/repo-name")
    parser.add_argument("--interval", type=float, default=60.0, help="seconds between scans")
    parser.add_argument("--once", action="store_true", help="scan once and exit")
    parser.add_argument("--token", default=os.environ.get("HF_TOKEN"),
                        help="HF token (default: $HF_TOKEN)")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if not args.token:
        try:
            from huggingface_hub import HfFolder
            args.token = HfFolder.get_token()
        except Exception:
            args.token = None
    if not args.token:
        log.error("HF token required: pass --token, set HF_TOKEN, or run `hf auth login`")
        return 2
    if not args.watch_dir.is_dir():
        log.error("Watch dir does not exist: %s", args.watch_dir)
        return 2

    api = HfApi()
    ensure_repo(api, args.repo_id, args.token)

    state_path = args.watch_dir / STATE_FILENAME
    state = load_state(state_path)

    log.info("Watching %s every %.1fs -> %s (private)", args.watch_dir, args.interval, args.repo_id)
    try:
        while True:
            n = scan_once(args.watch_dir, state, api, args.repo_id, args.token)
            if n:
                log.info("Uploaded %d new checkpoint(s)", n)
            if args.once:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        log.info("Stopped by user")
    return 0


if __name__ == "__main__":
    sys.exit(main())
