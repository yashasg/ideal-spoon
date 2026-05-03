"""Tests for Global-PIQA haw_Latn eval-only ingester."""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"


def _load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ingester = _load_script("global_piqa_ingester", SCRIPTS_DIR / "347_ingest_global_piqa_haw.py")


class TestGlobalPIQAIngester(unittest.TestCase):
    def setUp(self) -> None:
        self.work = REPO_ROOT / "data" / "test_global_piqa_ingester"
        shutil.rmtree(self.work, ignore_errors=True)
        self.work.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.work, ignore_errors=True)

    def _rows(self):
        return ingester.parse_tsv(ingester._SELFTEST_TSV)

    def test_license_filter_requires_cc_by_sa_eval_only(self):
        rows = self._rows()
        ok = {"license_spdx": "CC-BY-SA-4.0", "eval_only": True, "dataset_revision": ingester.DATASET_REVISION}
        self.assertEqual(len(ingester.build_ledger_entries(rows, metadata=ok, fetched_at="2026-05-03T00:00:00Z")), 3)
        with self.assertRaises(ValueError):
            ingester.build_ledger_entries(rows, metadata={"license_spdx": "CC-BY-SA-4.0", "eval_only": False}, fetched_at="x")
        with self.assertRaises(ValueError):
            ingester.build_ledger_entries(rows, metadata={"license_spdx": "MIT", "eval_only": True}, fetched_at="x")

    def test_ledger_schema(self):
        entry = ingester.build_ledger_entries(
            self._rows()[:1],
            metadata={"license_spdx": "CC-BY-SA-4.0", "eval_only": True, "dataset_revision": ingester.DATASET_REVISION},
            fetched_at="2026-05-03T00:00:00Z",
        )[0]
        self.assertEqual(set(entry), {"source", "item_id", "content_sha256", "license_spdx", "license_url", "dataset_revision", "fetched_at", "eval_only"})
        self.assertEqual(entry["source"], "global-piqa:haw_Latn")
        self.assertTrue(entry["eval_only"])
        self.assertEqual(len(entry["content_sha256"]), 64)

    def test_hash_determinism(self):
        row = self._rows()[0]
        rec1 = ingester.build_eval_record(row, row_index=1)
        rec2 = ingester.build_eval_record(dict(row), row_index=1)
        self.assertEqual(rec1["content_sha256"], rec2["content_sha256"])
        row2 = dict(row)
        row2["prompt"] = row2["prompt"].replace("ho'omaka", "hoʻomaka")
        rec3 = ingester.build_eval_record(row2, row_index=1)
        self.assertEqual(rec1["content_sha256"], rec3["content_sha256"])

    def test_refuse_to_write_to_train_candidates(self):
        train_path = REPO_ROOT / "data" / "stage2" / "candidates" / "global_piqa.jsonl"
        with self.assertRaises(ValueError):
            ingester.append_ledger([], train_path)

    def test_self_test_writes_three_hashes(self):
        ledger = self.work / "eval_hashes.jsonl"
        self.assertEqual(ingester.self_test(ledger), 0)
        rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(row["eval_only"] is True for row in rows))


if __name__ == "__main__":
    unittest.main()
