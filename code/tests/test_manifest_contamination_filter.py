from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import shutil
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "code" / "tests" / "fixtures" / "stage2_contamination"
WORK_DIR = REPO_ROOT / "data" / "test_manifest_contamination_filter"


def load_builder():
    path = REPO_ROOT / "scripts" / "320_build_stage2_manifest.py"
    spec = importlib.util.spec_from_file_location("stage2_manifest_builder_test", path)
    if not spec or not spec.loader:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestManifestContaminationFilter(unittest.TestCase):
    def setUp(self) -> None:
        shutil.rmtree(WORK_DIR, ignore_errors=True)
        (WORK_DIR / "stage2").mkdir(parents=True, exist_ok=True)
        self.builder = load_builder()
        self.builder.DATA_STAGE2 = WORK_DIR / "stage2"
        self.builder.DEFAULT_STAGE2_MANIFEST = self.builder.DATA_STAGE2 / "stage2_manifest.jsonl"
        self.builder.DEFAULT_BUILD_MANIFEST = self.builder.DATA_STAGE2 / "build_manifest.json"
        self.builder.DEFAULT_SCORE_SUMMARY = self.builder.DATA_STAGE2 / "score_summary.json"
        self.builder.DEFAULT_CONTAMINATION_REPORT = self.builder.DATA_STAGE2 / "contamination_report.json"

    def tearDown(self) -> None:
        shutil.rmtree(WORK_DIR, ignore_errors=True)

    def test_eval_hashes_drop_rows_before_manifest_write(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            rc = self.builder.main([
                "--execute",
                "--candidates", str(FIXTURE_DIR / "candidates.jsonl"),
                "--eval-hashes", str(FIXTURE_DIR / "eval_hashes.jsonl"),
            ])
        self.assertEqual(rc, 0, stderr.getvalue())

        manifest_rows = [json.loads(line) for line in self.builder.DEFAULT_STAGE2_MANIFEST.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(manifest_rows), 2)
        self.assertEqual({r["pair_id"] for r in manifest_rows}, {"fixture-clean-1", "fixture-clean-2"})

        report = json.loads(self.builder.DEFAULT_CONTAMINATION_REPORT.read_text(encoding="utf-8"))
        self.assertEqual(report["ledger_path"], str(FIXTURE_DIR / "eval_hashes.jsonl"))
        self.assertEqual(report["ledger_size"], 3)
        self.assertEqual(report["total_dropped"], 3)
        self.assertEqual(report["per_source_dropped"], {"fixture-full": 1, "fixture-haw": 1, "fixture-en": 1})
        self.assertEqual(report["per_match_type"], {"full_pair": 1, "single_side_en": 1, "single_side_haw": 1})
        self.assertEqual(report["drop_reasons"], {
            "contamination:fixture-full": 1,
            "contamination:fixture-haw": 1,
            "contamination:fixture-en": 1,
        })

        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["rows_emitted"], 2)
        self.assertEqual(payload["eval_contamination_dropped"], 3)
        self.assertEqual(payload["ingest"]["contamination_filter"]["drop_reasons"], report["drop_reasons"])

    def test_missing_eval_hashes_is_error(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            rc = self.builder.main([
                "--dry-run",
                "--candidates", str(FIXTURE_DIR / "candidates.jsonl"),
                "--eval-hashes", str(FIXTURE_DIR / "missing-ledger.jsonl"),
            ])
        self.assertNotEqual(rc, 0)
        self.assertIn("eval-hashes ledger not found", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
