"""Tests for train.py and config path resolution.

Pure-Python only — no torch / transformers required.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path


class TestConfigPathResolution(unittest.TestCase):
    """resolve_data_paths resolves relative paths against config file directory."""

    def test_relative_path_resolved_against_config_dir(self):
        from llm_hawaii.config import TrainConfig, resolve_data_paths

        cfg = TrainConfig(train_path="examples/train.jsonl.example")
        config_path = Path("/some/project/code/configs/test.json")
        resolved = resolve_data_paths(cfg, config_path)
        expected = str((Path("/some/project/code/configs") / "examples/train.jsonl.example").resolve())
        self.assertEqual(resolved.train_path, expected)

    def test_absolute_path_unchanged(self):
        from llm_hawaii.config import TrainConfig, resolve_data_paths

        cfg = TrainConfig(train_path="/absolute/path/train.jsonl")
        config_path = Path("/some/project/code/configs/test.json")
        resolved = resolve_data_paths(cfg, config_path)
        self.assertEqual(resolved.train_path, "/absolute/path/train.jsonl")

    def test_eval_path_resolved(self):
        from llm_hawaii.config import TrainConfig, resolve_data_paths

        cfg = TrainConfig(
            train_path="../../data/train.jsonl",
            eval_path="../../data/eval.jsonl",
        )
        config_path = Path("/repo/code/configs/test.json")
        resolved = resolve_data_paths(cfg, config_path)
        expected_train = str((Path("/repo/code/configs") / "../../data/train.jsonl").resolve())
        expected_eval = str((Path("/repo/code/configs") / "../../data/eval.jsonl").resolve())
        self.assertEqual(resolved.train_path, expected_train)
        self.assertEqual(resolved.eval_path, expected_eval)

    def test_none_eval_path_unchanged(self):
        from llm_hawaii.config import TrainConfig, resolve_data_paths

        cfg = TrainConfig(train_path="train.jsonl", eval_path=None)
        config_path = Path("/repo/code/configs/test.json")
        resolved = resolve_data_paths(cfg, config_path)
        self.assertIsNone(resolved.eval_path)

    def test_load_config_resolves_paths(self):
        """load_config resolves relative paths against the config file."""
        from llm_hawaii.config import load_config

        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            cfg_data = {
                "train_path": "subdir/train.jsonl",
                "eval_path": None,
            }
            cfg_path = d / "test_cfg.json"
            cfg_path.write_text(json.dumps(cfg_data))
            cfg = load_config(cfg_path)
            expected = str((d / "subdir/train.jsonl").resolve())
            self.assertEqual(cfg.train_path, expected)

    def test_smoke_config_paths_resolve_correctly(self):
        """smoke.json train_path resolves to code/examples/train.jsonl.example."""
        from llm_hawaii.config import load_config

        repo_root = Path(__file__).resolve().parents[2]
        smoke_cfg_path = repo_root / "code" / "configs" / "smoke.json"
        self.assertTrue(smoke_cfg_path.exists(), f"Missing: {smoke_cfg_path}")

        cfg = load_config(smoke_cfg_path)
        expected = str((repo_root / "code" / "examples" / "train.jsonl.example").resolve())
        self.assertEqual(cfg.train_path, expected)


class TestPreflightChecks(unittest.TestCase):
    """run_preflight validates data paths without requiring ML deps."""

    def test_missing_train_path_reported(self):
        from llm_hawaii.config import TrainConfig
        from llm_hawaii.train import run_preflight

        cfg = TrainConfig(train_path="/nonexistent/path/train.jsonl")
        report = run_preflight(cfg)
        self.assertFalse(report["train_path_exists"])
        self.assertTrue(len(report["issues"]) > 0)
        self.assertTrue(any("train_path not found" in i for i in report["issues"]))

    def test_valid_jsonl_passes(self):
        from llm_hawaii.config import TrainConfig
        from llm_hawaii.train import run_preflight

        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            train_file = d / "train.jsonl"
            train_file.write_text(
                '{"text": "He aloha n\u014d \u02bfoe"}\n'
                '{"text": "Aloha mai k\u0101kou"}\n'
            )
            cfg = TrainConfig(
                train_path=str(train_file),
                output_dir=str(d / "runs/test"),
            )
            report = run_preflight(cfg)
            self.assertTrue(report["train_path_exists"])
            self.assertEqual(report["train_row_count"], 2)
            self.assertTrue(report["train_field_ok"])
            self.assertEqual(report["issues"], [])

    def test_missing_text_field_reported(self):
        from llm_hawaii.config import TrainConfig
        from llm_hawaii.train import run_preflight

        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            train_file = d / "train.jsonl"
            train_file.write_text('{"content": "wrong field"}\n')
            cfg = TrainConfig(
                train_path=str(train_file),
                output_dir=str(d / "runs/test"),
                text_field="text",
            )
            report = run_preflight(cfg)
            self.assertFalse(report["train_field_ok"])
            self.assertTrue(any("text_field" in i for i in report["issues"]))

    def test_configured_eval_path_missing_reported(self):
        from llm_hawaii.config import TrainConfig
        from llm_hawaii.train import run_preflight

        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            train_file = d / "train.jsonl"
            train_file.write_text('{"text": "test"}\n')
            cfg = TrainConfig(
                train_path=str(train_file),
                eval_path="/nonexistent/eval.jsonl",
                output_dir=str(d / "runs/test"),
            )
            report = run_preflight(cfg)
            self.assertFalse(report["eval_path_exists"])
            self.assertTrue(any("eval_path" in i for i in report["issues"]))

    def test_configured_eval_path_present_passes(self):
        from llm_hawaii.config import TrainConfig
        from llm_hawaii.train import run_preflight

        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            train_file = d / "train.jsonl"
            eval_file = d / "eval.jsonl"
            train_file.write_text('{"text": "train row"}\n')
            eval_file.write_text('{"text": "eval row"}\n')
            cfg = TrainConfig(
                train_path=str(train_file),
                eval_path=str(eval_file),
                output_dir=str(d / "runs/test"),
            )
            report = run_preflight(cfg)
            self.assertTrue(report["eval_path_exists"])
            self.assertEqual(report["issues"], [])

    def test_output_dir_created(self):
        from llm_hawaii.config import TrainConfig
        from llm_hawaii.train import run_preflight

        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            train_file = d / "train.jsonl"
            train_file.write_text('{"text": "hi"}\n')
            output_dir = d / "nested" / "runs" / "test"
            cfg = TrainConfig(
                train_path=str(train_file),
                output_dir=str(output_dir),
            )
            report = run_preflight(cfg)
            self.assertTrue(report["output_dir_ok"])
            self.assertTrue(output_dir.exists())


class TestRunReportMetadata(unittest.TestCase):
    """write_run_report emits required fields and no raw text."""

    def test_run_report_schema(self):
        from llm_hawaii.config import TrainConfig
        from llm_hawaii.train import write_run_report
        import time

        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            train_file = d / "train.jsonl"
            train_file.write_text('{"text": "Aloha"}\n{"text": "Mahalo"}\n')

            cfg = TrainConfig(
                train_path=str(train_file),
                output_dir=str(d / "runs"),
                stage="smoke",
                run_name="test-run",
            )
            out_dir = d / "runs"
            out_dir.mkdir(parents=True, exist_ok=True)

            t = time.time()
            report_path = write_run_report(
                out_dir, cfg, "configs/test.json", {}, t, t + 1.5
            )
            self.assertTrue(report_path.exists())

            with open(report_path) as f:
                report = json.load(f)

            required_keys = {
                "schema_version", "stage", "run_name", "config_path",
                "resolved_config", "output_dir", "train", "git_commit",
                "runtime_capability", "wallclock_seconds", "completed_at_utc",
            }
            for key in required_keys:
                self.assertIn(key, report, f"Missing key: {key}")

            self.assertEqual(report["schema_version"], "training-run-report.v1")
            self.assertEqual(report["stage"], "smoke")
            self.assertAlmostEqual(report["wallclock_seconds"], 1.5, delta=0.1)

            # train block has sha256 and row_count
            self.assertIn("sha256", report["train"])
            self.assertIn("row_count", report["train"])
            self.assertEqual(report["train"]["row_count"], 2)

            # No raw text in report
            report_text = json.dumps(report)
            self.assertNotIn("Aloha", report_text)
            self.assertNotIn("Mahalo", report_text)


class TestTrainingArgumentsCompatibility(unittest.TestCase):
    """TrainingArguments eval strategy arg changed across transformers versions."""

    def test_new_eval_strategy_keyword_is_used_when_supported(self):
        import sys
        import types
        from unittest import mock

        from llm_hawaii.config import TrainConfig

        class FakeTrainingArguments:
            def __init__(self, eval_strategy=None, **kwargs):
                self.kwargs = dict(kwargs)
                self.kwargs["eval_strategy"] = eval_strategy

        fake_transformers = types.SimpleNamespace(
            TrainingArguments=FakeTrainingArguments
        )

        with mock.patch.dict(sys.modules, {"transformers": fake_transformers}):
            from llm_hawaii.train import build_training_args

            args = build_training_args(TrainConfig(eval_steps=100), has_eval=True)

        self.assertEqual(args.kwargs["eval_strategy"], "steps")
        self.assertEqual(args.kwargs["eval_steps"], 100)
        self.assertNotIn("evaluation_strategy", args.kwargs)

    def test_legacy_evaluation_strategy_keyword_is_used_when_supported(self):
        import sys
        import types
        from unittest import mock

        from llm_hawaii.config import TrainConfig

        class FakeTrainingArguments:
            def __init__(self, evaluation_strategy=None, **kwargs):
                self.kwargs = dict(kwargs)
                self.kwargs["evaluation_strategy"] = evaluation_strategy

        fake_transformers = types.SimpleNamespace(
            TrainingArguments=FakeTrainingArguments
        )

        with mock.patch.dict(sys.modules, {"transformers": fake_transformers}):
            from llm_hawaii.train import build_training_args

            args = build_training_args(TrainConfig(eval_steps=100), has_eval=True)

        self.assertEqual(args.kwargs["evaluation_strategy"], "steps")
        self.assertEqual(args.kwargs["eval_steps"], 100)
        self.assertNotIn("eval_strategy", args.kwargs)


class TestTrainerCompatibility(unittest.TestCase):
    """Trainer tokenizer arg changed across transformers versions."""

    def test_new_processing_class_keyword_is_used_when_supported(self):
        import types

        from llm_hawaii.train import build_trainer_kwargs

        class FakeTrainer:
            def __init__(
                self,
                model=None,
                args=None,
                train_dataset=None,
                eval_dataset=None,
                data_collator=None,
                processing_class=None,
            ):
                pass

        tokenizer = object()
        fake_transformers = types.SimpleNamespace(Trainer=FakeTrainer)

        kwargs = build_trainer_kwargs(
            fake_transformers,
            model="model",
            args="args",
            train_dataset=["train"],
            eval_dataset=["eval"],
            data_collator="collator",
            tokenizer=tokenizer,
        )

        self.assertIs(kwargs["processing_class"], tokenizer)
        self.assertNotIn("tokenizer", kwargs)

    def test_legacy_tokenizer_keyword_is_used_when_supported(self):
        import types

        from llm_hawaii.train import build_trainer_kwargs

        class FakeTrainer:
            def __init__(
                self,
                model=None,
                args=None,
                train_dataset=None,
                eval_dataset=None,
                data_collator=None,
                tokenizer=None,
            ):
                pass

        tokenizer = object()
        fake_transformers = types.SimpleNamespace(Trainer=FakeTrainer)

        kwargs = build_trainer_kwargs(
            fake_transformers,
            model="model",
            args="args",
            train_dataset=["train"],
            eval_dataset=None,
            data_collator="collator",
            tokenizer=tokenizer,
        )

        self.assertIs(kwargs["tokenizer"], tokenizer)
        self.assertNotIn("processing_class", kwargs)


class TestResumeFlagWiring(unittest.TestCase):
    """CLI flags are parsed and routed without running actual training."""

    def test_resume_checkpoint_flag_parsed(self):
        import argparse
        # Replicate the parser from main() to test flag wiring in isolation.
        parser = argparse.ArgumentParser()
        parser.add_argument("--config", required=True)
        parser.add_argument("--print-config", action="store_true")
        parser.add_argument("--preflight", action="store_true")
        parser.add_argument("--resume-from-checkpoint", metavar="PATH")
        parser.add_argument("--eval-after-train", action="store_true")

        ns = parser.parse_args([
            "--config", "x.json",
            "--resume-from-checkpoint", "runs/ckpt-200",
        ])
        self.assertEqual(ns.resume_from_checkpoint, "runs/ckpt-200")

    def test_eval_after_train_flag_parsed(self):
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--config", required=True)
        parser.add_argument("--eval-after-train", action="store_true")

        ns = parser.parse_args(["--config", "x.json", "--eval-after-train"])
        self.assertTrue(ns.eval_after_train)

    def test_preflight_flag_parsed(self):
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--config", required=True)
        parser.add_argument("--preflight", action="store_true")

        ns = parser.parse_args(["--config", "x.json", "--preflight"])
        self.assertTrue(ns.preflight)


if __name__ == "__main__":
    unittest.main()
