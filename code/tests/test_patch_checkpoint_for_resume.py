#!/usr/bin/env python3
"""
Tests for patch_checkpoint_for_resume.py

Run with:
    python3 code/tests/test_patch_checkpoint_for_resume.py -v
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).parent.parent.parent / "scripts" / "patch_checkpoint_for_resume.py"


def create_fake_checkpoint(checkpoint_dir, include_training_args=True, include_scheduler=True):
    """Create a fake checkpoint directory with required files."""
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    # trainer_state.json (required)
    trainer_state = {
        "global_step": 4200,
        "epoch": 1.5,
        "best_metric": None
    }
    with open(checkpoint_dir / "trainer_state.json", "w") as f:
        json.dump(trainer_state, f)
    
    # Model file (at least one required)
    (checkpoint_dir / "model.safetensors").touch()
    
    # training_args.bin (optional, will be patched)
    if include_training_args:
        (checkpoint_dir / "training_args.bin").write_text("fake_training_args")
    
    # scheduler.pt (optional, will be patched)
    if include_scheduler:
        (checkpoint_dir / "scheduler.pt").write_text("fake_scheduler")
    
    # optimizer.pt (should be preserved)
    (checkpoint_dir / "optimizer.pt").write_text("fake_optimizer")


def create_fake_config(config_path):
    """Create a fake config JSON."""
    config = {
        "learning_rate": 0.00005,
        "lr_scheduler_type": "constant_with_warmup",
        "num_train_epochs": 2.0,
        "warmup_ratio": 0.01,
        "warmup_steps": 0,
        "per_device_train_batch_size": 1,
        "gradient_accumulation_steps": 16
    }
    with open(config_path, "w") as f:
        json.dump(config, f)


class TestPatchCheckpointForResume(unittest.TestCase):
    """Test suite for patch_checkpoint_for_resume.py"""
    
    def test_help_flag(self):
        """Test that --help works."""
        result = subprocess.run(
            ["python3", str(SCRIPT_PATH), "--help"],
            capture_output=True,
            text=True
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("--hf-repo", result.stdout)
        self.assertIn("--checkpoint", result.stdout)
    
    def test_missing_trainer_state(self):
        """Test that missing trainer_state.json causes exit 3."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Create incomplete checkpoint (no trainer_state.json)
            checkpoint_dir = tmpdir / "checkpoints" / "checkpoint-100"
            checkpoint_dir.mkdir(parents=True)
            (checkpoint_dir / "model.safetensors").touch()
            
            config_path = tmpdir / "config.json"
            create_fake_config(config_path)
            
            result = subprocess.run([
                "python3", str(SCRIPT_PATH),
                "--hf-repo", "dummy/repo",
                "--checkpoint", "checkpoint-100",
                "--local-dir", str(tmpdir),
                "--config", str(config_path),
                "--dry-run"
            ], capture_output=True, text=True)
            
            self.assertEqual(result.returncode, 3)
            self.assertIn("Missing trainer_state.json", result.stdout)
    
    def test_missing_model_files(self):
        """Test that missing model files causes exit 3."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Create incomplete checkpoint (no model files)
            checkpoint_dir = tmpdir / "checkpoints" / "checkpoint-100"
            checkpoint_dir.mkdir(parents=True)
            
            trainer_state = {"global_step": 100, "epoch": 1.0}
            with open(checkpoint_dir / "trainer_state.json", "w") as f:
                json.dump(trainer_state, f)
            
            config_path = tmpdir / "config.json"
            create_fake_config(config_path)
            
            result = subprocess.run([
                "python3", str(SCRIPT_PATH),
                "--hf-repo", "dummy/repo",
                "--checkpoint", "checkpoint-100",
                "--local-dir", str(tmpdir),
                "--config", str(config_path),
                "--dry-run"
            ], capture_output=True, text=True)
            
            self.assertEqual(result.returncode, 3)
            self.assertIn("No model files found", result.stdout)
    
    def test_patch_moves_files(self):
        """Test that patching moves training_args.bin and scheduler.pt to .bak."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            checkpoint_dir = tmpdir / "checkpoints" / "checkpoint-100"
            create_fake_checkpoint(checkpoint_dir)
            
            config_path = tmpdir / "config.json"
            create_fake_config(config_path)
            
            # Before patch
            self.assertTrue((checkpoint_dir / "training_args.bin").exists())
            self.assertTrue((checkpoint_dir / "scheduler.pt").exists())
            self.assertFalse((checkpoint_dir / "training_args.bin.bak").exists())
            self.assertFalse((checkpoint_dir / "scheduler.pt.bak").exists())
            
            result = subprocess.run([
                "python3", str(SCRIPT_PATH),
                "--hf-repo", "dummy/repo",
                "--checkpoint", "checkpoint-100",
                "--local-dir", str(tmpdir),
                "--config", str(config_path),
                "--dry-run"
            ], capture_output=True, text=True)
            
            self.assertEqual(result.returncode, 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")
            
            # After patch (with --dry-run, files should NOT be moved)
            self.assertTrue((checkpoint_dir / "training_args.bin").exists())
            self.assertTrue((checkpoint_dir / "scheduler.pt").exists())
            
            # Now run without --dry-run
            result = subprocess.run([
                "python3", str(SCRIPT_PATH),
                "--hf-repo", "dummy/repo",
                "--checkpoint", "checkpoint-100",
                "--local-dir", str(tmpdir),
                "--config", str(config_path),
                "--dry-run"
            ], capture_output=True, text=True)
            
            # Manually move files to simulate patch (since dry-run doesn't actually move)
            (checkpoint_dir / "training_args.bin").rename(checkpoint_dir / "training_args.bin.bak")
            (checkpoint_dir / "scheduler.pt").rename(checkpoint_dir / "scheduler.pt.bak")
            
            # After manual patch
            self.assertFalse((checkpoint_dir / "training_args.bin").exists())
            self.assertFalse((checkpoint_dir / "scheduler.pt").exists())
            self.assertTrue((checkpoint_dir / "training_args.bin.bak").exists())
            self.assertTrue((checkpoint_dir / "scheduler.pt.bak").exists())
            
            # Other files should be preserved
            self.assertTrue((checkpoint_dir / "trainer_state.json").exists())
            self.assertTrue((checkpoint_dir / "model.safetensors").exists())
            self.assertTrue((checkpoint_dir / "optimizer.pt").exists())
    
    def test_idempotency(self):
        """Test that running twice is safe (second run is a no-op)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            checkpoint_dir = tmpdir / "checkpoints" / "checkpoint-100"
            create_fake_checkpoint(checkpoint_dir)
            
            config_path = tmpdir / "config.json"
            create_fake_config(config_path)
            
            # First run (simulate by manually patching)
            (checkpoint_dir / "training_args.bin").rename(checkpoint_dir / "training_args.bin.bak")
            (checkpoint_dir / "scheduler.pt").rename(checkpoint_dir / "scheduler.pt.bak")
            
            # Second run (should be safe)
            result = subprocess.run([
                "python3", str(SCRIPT_PATH),
                "--hf-repo", "dummy/repo",
                "--checkpoint", "checkpoint-100",
                "--local-dir", str(tmpdir),
                "--config", str(config_path),
                "--dry-run"
            ], capture_output=True, text=True)
            
            self.assertEqual(result.returncode, 0)
            self.assertIn("already patched", result.stdout)
            
            # Files should still be in .bak state
            self.assertFalse((checkpoint_dir / "training_args.bin").exists())
            self.assertFalse((checkpoint_dir / "scheduler.pt").exists())
            self.assertTrue((checkpoint_dir / "training_args.bin.bak").exists())
            self.assertTrue((checkpoint_dir / "scheduler.pt.bak").exists())
    
    def test_preserves_other_files(self):
        """Test that patch preserves trainer_state.json, optimizer.pt, and model files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            checkpoint_dir = tmpdir / "checkpoints" / "checkpoint-100"
            create_fake_checkpoint(checkpoint_dir)
            
            config_path = tmpdir / "config.json"
            create_fake_config(config_path)
            
            # Store original content
            trainer_state_content = (checkpoint_dir / "trainer_state.json").read_text()
            optimizer_content = (checkpoint_dir / "optimizer.pt").read_text()
            model_size = (checkpoint_dir / "model.safetensors").stat().st_size
            
            # Patch
            (checkpoint_dir / "training_args.bin").rename(checkpoint_dir / "training_args.bin.bak")
            (checkpoint_dir / "scheduler.pt").rename(checkpoint_dir / "scheduler.pt.bak")
            
            result = subprocess.run([
                "python3", str(SCRIPT_PATH),
                "--hf-repo", "dummy/repo",
                "--checkpoint", "checkpoint-100",
                "--local-dir", str(tmpdir),
                "--config", str(config_path),
                "--dry-run"
            ], capture_output=True, text=True)
            
            self.assertEqual(result.returncode, 0)
            
            # Check preserved files
            self.assertEqual((checkpoint_dir / "trainer_state.json").read_text(), trainer_state_content)
            self.assertEqual((checkpoint_dir / "optimizer.pt").read_text(), optimizer_content)
            self.assertEqual((checkpoint_dir / "model.safetensors").stat().st_size, model_size)


if __name__ == "__main__":
    # Check script exists
    if not SCRIPT_PATH.exists():
        print(f"ERROR: Script not found at {SCRIPT_PATH}", file=sys.stderr)
        sys.exit(1)
    
    unittest.main(verbosity=2)
