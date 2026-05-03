#!/usr/bin/env python3
"""
Patch a Stage 1 training checkpoint for resume with NEW hyperparameters.

Background:
HuggingFace Trainer's --resume-from-checkpoint reloads training_args.bin and
scheduler.pt from disk, silently overriding the values in the config JSON.
This script removes those files (moving to .bak) so Trainer rebuilds from the
current config on resume.

Usage:
    python3 scripts/patch_checkpoint_for_resume.py \
        --hf-repo RainbowMassacre/llama31-hawaii-checkpoints \
        --checkpoint checkpoint-4200 \
        --local-dir runs/llama31-8b-stage1-multisource \
        --config code/configs/stage1_fineweb2_haw.json \
        [--remote-prefix checkpoints] \
        [--hf-token-env HF_UPLOAD_TOKEN] \
        [--dry-run]
"""

import argparse
import json
import os
import sys
from pathlib import Path


def log(msg):
    """Print with prefix."""
    print(f"[patch-checkpoint] {msg}")


def resolve_token(token_env_name, dry_run):
    """Resolve HF token from environment, or fall back to cached `hf auth login`."""
    token = os.getenv(token_env_name) or os.getenv("HF_TOKEN")
    if not token and not dry_run:
        log(f"No {token_env_name}/HF_TOKEN env var set — falling back to cached `hf auth login` credentials.")
    return token  # None is fine: huggingface_hub will use ~/.cache/huggingface/token


def download_checkpoint(hf_repo, checkpoint, local_dir, remote_prefix, token, dry_run):
    """Download checkpoint from HF hub."""
    pattern = f"{remote_prefix}/{checkpoint}/**"
    resolved_local = Path(local_dir) / remote_prefix / checkpoint
    
    if dry_run:
        log(f"--dry-run: Skipping download, verifying local path exists: {resolved_local}")
        if not resolved_local.exists():
            log(f"❌ --dry-run: Path {resolved_local} does not exist. Cannot proceed.")
            sys.exit(3)
    else:
        try:
            from huggingface_hub import snapshot_download
        except ImportError:
            log("❌ huggingface_hub is not installed. Run: pip install huggingface_hub")
            sys.exit(4)
        
        log(f"Downloading {hf_repo}/{remote_prefix}/{checkpoint} to {local_dir}...")
        try:
            snapshot_download(
                repo_id=hf_repo,
                allow_patterns=[pattern],
                local_dir=local_dir,
                token=token,
                repo_type="model"
            )
            log(f"✓ Downloaded to {resolved_local}")
        except Exception as e:
            log(f"❌ Download failed: {e}")
            sys.exit(4)
    
    return resolved_local


def verify_checkpoint(checkpoint_path):
    """Verify checkpoint has required files."""
    trainer_state = checkpoint_path / "trainer_state.json"
    if not trainer_state.exists():
        log(f"❌ Missing trainer_state.json in {checkpoint_path}")
        sys.exit(3)
    
    model_files = [
        "pytorch_model.bin",
        "model.safetensors",
        "model.safetensors.index.json",
        "adapter_model.safetensors",
        "adapter_model.bin"
    ]
    
    has_model = any((checkpoint_path / f).exists() for f in model_files)
    if not has_model:
        log(f"❌ No model files found in {checkpoint_path}")
        log(f"   Expected at least one of: {', '.join(model_files)}")
        sys.exit(3)
    
    log(f"✓ Checkpoint validated: {checkpoint_path}")


def print_before_state(checkpoint_path):
    """Print checkpoint state BEFORE patching."""
    log("\n=== BEFORE STATE ===")
    
    # Read trainer_state.json
    trainer_state_path = checkpoint_path / "trainer_state.json"
    with open(trainer_state_path) as f:
        trainer_state = json.load(f)
    
    log(f"global_step: {trainer_state.get('global_step', 'N/A')}")
    log(f"epoch: {trainer_state.get('epoch', 'N/A')}")
    
    # Read training_args.bin if exists
    training_args_path = checkpoint_path / "training_args.bin"
    if training_args_path.exists():
        log("\ntraining_args.bin (will override config on resume):")
        try:
            import torch
            training_args = torch.load(training_args_path, map_location="cpu", weights_only=False)
            log(f"  learning_rate: {getattr(training_args, 'learning_rate', 'N/A')}")
            log(f"  lr_scheduler_type: {getattr(training_args, 'lr_scheduler_type', 'N/A')}")
            log(f"  num_train_epochs: {getattr(training_args, 'num_train_epochs', 'N/A')}")
            log(f"  warmup_ratio: {getattr(training_args, 'warmup_ratio', 'N/A')}")
            log(f"  warmup_steps: {getattr(training_args, 'warmup_steps', 'N/A')}")
            log(f"  per_device_train_batch_size: {getattr(training_args, 'per_device_train_batch_size', 'N/A')}")
            log(f"  gradient_accumulation_steps: {getattr(training_args, 'gradient_accumulation_steps', 'N/A')}")
        except ImportError:
            log(f"  ⚠️  torch not available, cannot load training_args.bin")
        except Exception as e:
            log(f"  ⚠️  Failed to load: {e}")
    else:
        log("\ntraining_args.bin: NOT FOUND (already patched?)")
    
    # Check scheduler.pt
    scheduler_path = checkpoint_path / "scheduler.pt"
    if scheduler_path.exists():
        size_mb = scheduler_path.stat().st_size / 1024 / 1024
        log(f"\nscheduler.pt: {size_mb:.2f} MB")
    else:
        log("\nscheduler.pt: NOT FOUND (already patched?)")
    
    # Check optimizer.pt
    optimizer_path = checkpoint_path / "optimizer.pt"
    if optimizer_path.exists():
        size_mb = optimizer_path.stat().st_size / 1024 / 1024
        log(f"optimizer.pt: {size_mb:.2f} MB (will be preserved)")


def print_config_values(config_path):
    """Print NEW hyperparameters from config."""
    log("\n=== CONFIG (NEW VALUES) ===")
    
    with open(config_path) as f:
        config = json.load(f)
    
    log(f"learning_rate: {config.get('learning_rate', 'N/A')}")
    log(f"lr_scheduler_type: {config.get('lr_scheduler_type', 'N/A')}")
    log(f"num_train_epochs: {config.get('num_train_epochs', 'N/A')}")
    log(f"warmup_ratio: {config.get('warmup_ratio', 'N/A')}")
    log(f"warmup_steps: {config.get('warmup_steps', 'N/A')}")
    log(f"per_device_train_batch_size: {config.get('per_device_train_batch_size', 'N/A')}")
    log(f"gradient_accumulation_steps: {config.get('gradient_accumulation_steps', 'N/A')}")
    
    return config


def patch_checkpoint(checkpoint_path, dry_run):
    """Move training_args.bin and scheduler.pt to .bak."""
    log("\n=== PATCHING ===")
    
    files_to_patch = ["training_args.bin", "scheduler.pt"]
    patched = []
    
    for filename in files_to_patch:
        src = checkpoint_path / filename
        dst = checkpoint_path / f"{filename}.bak"
        
        if src.exists():
            if dry_run:
                log(f"--dry-run: Would move {filename} → {filename}.bak")
                patched.append(filename)
            else:
                try:
                    src.rename(dst)
                    log(f"✓ Moved {filename} → {filename}.bak")
                    patched.append(filename)
                except Exception as e:
                    log(f"❌ Failed to move {filename}: {e}")
                    sys.exit(4)
        elif dst.exists():
            log(f"✓ {filename} already patched (found {filename}.bak)")
            patched.append(filename)
        else:
            log(f"  {filename}: not found (nothing to patch)")
    
    if not patched:
        log("⚠️  No files were patched. Checkpoint may already be patched or incomplete.")
    
    return patched


def print_after_state(config, config_path, checkpoint_path):
    """Print AFTER state and resume command."""
    log("\n=== AFTER STATE ===")
    log("✅ Patched. On resume, Trainer will use config values:")
    log(f"   learning_rate     = {config.get('learning_rate', 'N/A')}")
    log(f"   lr_scheduler_type = {config.get('lr_scheduler_type', 'N/A')}")
    log(f"   num_train_epochs  = {config.get('num_train_epochs', 'N/A')}")
    log(f"   warmup_ratio      = {config.get('warmup_ratio', 'N/A')}")
    
    log("\nResume with:")
    log(f"   PYTHONPATH=code python3 -m llm_hawaii.train \\")
    log(f"     --config {config_path} \\")
    log(f"     --resume-from-checkpoint {checkpoint_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Patch a training checkpoint for resume with new hyperparameters",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("--hf-repo", required=True,
                        help="HuggingFace repo (e.g., RainbowMassacre/llama31-hawaii-checkpoints)")
    parser.add_argument("--checkpoint", required=True,
                        help="Checkpoint name (e.g., checkpoint-4200)")
    parser.add_argument("--local-dir", required=True,
                        help="Local directory for download (e.g., runs/llama31-8b-stage1-multisource)")
    parser.add_argument("--config", required=True,
                        help="Path to config JSON with new hyperparameters")
    parser.add_argument("--remote-prefix", default="checkpoints",
                        help="Remote path prefix (default: checkpoints)")
    parser.add_argument("--hf-token-env", default="HF_UPLOAD_TOKEN",
                        help="Environment variable name for HF token (default: HF_UPLOAD_TOKEN)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Don't download or modify files, just show what would happen")
    
    args = parser.parse_args()

    # Early path validation — fail fast with clear errors before any download/HF work
    config_path = Path(args.config)
    if not config_path.is_file():
        log(f"❌ --config path does not exist or is not a file: {args.config}")
        log(f"   cwd: {Path.cwd()}")
        log(f"   Tip: check for typos, missing quotes, or stray newlines in the path.")
        sys.exit(2)

    local_dir = Path(args.local_dir)
    if not local_dir.exists():
        log(f"❌ --local-dir does not exist: {args.local_dir}")
        log(f"   cwd: {Path.cwd()}")
        log(f"   Create it first (mkdir -p) or fix the path.")
        sys.exit(2)
    if not local_dir.is_dir():
        log(f"❌ --local-dir is not a directory: {args.local_dir}")
        sys.exit(2)

    # 1. Resolve token
    token = resolve_token(args.hf_token_env, args.dry_run)
    
    # 2. Download checkpoint
    checkpoint_path = download_checkpoint(
        args.hf_repo, args.checkpoint, args.local_dir,
        args.remote_prefix, token, args.dry_run
    )
    
    # 3. Verify checkpoint
    verify_checkpoint(checkpoint_path)
    
    # 4. Print BEFORE state
    print_before_state(checkpoint_path)
    
    # 5. Print config values
    config = print_config_values(args.config)
    
    # 6. Patch
    patch_checkpoint(checkpoint_path, args.dry_run)
    
    # 7. Print AFTER state
    print_after_state(config, args.config, checkpoint_path)
    
    log("\n✅ Done.")
    sys.exit(0)


if __name__ == "__main__":
    main()
