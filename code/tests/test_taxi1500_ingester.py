"""Tests for Taxi1500 haw_Latn eval-only ingester."""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
CODE_ROOT = REPO_ROOT / "code"
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

from llm_hawaii import eval_contamination as ec


def _load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ingester = _load_script("taxi1500_ingester", SCRIPTS_DIR / "348_ingest_taxi1500_haw.py")


class TestTaxi1500Ingester(unittest.TestCase):
    def setUp(self) -> None:
        self.work = REPO_ROOT / "data" / "test_taxi1500_ingester"
        shutil.rmtree(self.work, ignore_errors=True)
        self.work.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.work, ignore_errors=True)

    def _rows(self):
        return ingester.parse_rows(ingester._SELFTEST_TSV, input_format="tsv")

    def test_license_filter_requires_apache_eval_only(self):
        ok = {"license_spdx": "Apache-2.0", "eval_only": True, "dataset_pin": "cisnlp/Taxi1500/" + "a" * 40}
        self.assertEqual(len(ingester.build_ledger_entries(self._rows(), metadata=ok, fetched_at="2026-05-03T00:00:00Z")), 3)
        with self.assertRaises(ValueError):
            ingester.build_ledger_entries(self._rows(), metadata={"license_spdx": "Apache-2.0", "eval_only": False}, fetched_at="x")
        with self.assertRaises(ValueError):
            ingester.build_ledger_entries(self._rows(), metadata={"license_spdx": "MIT", "eval_only": True}, fetched_at="x")

    def test_schema(self):
        entry = ingester.build_ledger_entries(
            self._rows()[:1],
            metadata={"license_spdx": "Apache-2.0", "eval_only": True, "dataset_pin": "cisnlp/Taxi1500/" + "a" * 40},
            fetched_at="2026-05-03T00:00:00Z",
        )[0]
        self.assertEqual(entry["source"], "taxi1500:haw_Latn")
        self.assertEqual(set(entry), {"source", "item_id", "verse_text", "label", "content_sha256", "license_spdx", "license_url", "dataset_pin", "fetched_at", "eval_only", "bible_overlap_candidate"})
        self.assertTrue(entry["eval_only"])
        self.assertTrue(entry["bible_overlap_candidate"])
        self.assertIn(entry["label"], ingester.TOPIC_LABELS)
        self.assertEqual(len(entry["content_sha256"]), 64)

    def test_hash_determinism(self):
        row = self._rows()[0]
        rec1 = ingester.build_eval_record(row, row_index=1)
        rec2 = ingester.build_eval_record(dict(row), row_index=1)
        self.assertEqual(rec1["content_sha256"], rec2["content_sha256"])
        row2 = dict(row)
        row2["verse_text"] = row2["verse_text"].replace("'", "ʻ")
        rec3 = ingester.build_eval_record(row2, row_index=1)
        self.assertEqual(rec1["content_sha256"], rec3["content_sha256"])

    def test_refuse_train_write(self):
        train_path = REPO_ROOT / "data" / "stage2" / "candidates" / "taxi1500.jsonl"
        with self.assertRaises(ValueError):
            ingester.append_ledger([], train_path)

    def test_single_side_contamination_match(self):
        ledger = self.work / "eval_hashes.jsonl"
        haw = "Ua aloha ke Akua i ko ke ao nei."
        h = ec.canonical_content_sha256(haw)
        ledger.write_text(json.dumps({"content_sha256": h, "bible_overlap_candidate": True}) + "\n", encoding="utf-8")
        hashes = ec.load_eval_hashes(ledger)
        candidate = {"text_en": "For God loved the world.", "text_haw": haw}
        self.assertTrue(ec.is_contaminated(candidate, hashes))

    def test_self_test_writes_three_hashes(self):
        ledger = self.work / "eval_hashes.jsonl"
        self.assertEqual(ingester.self_test(ledger), 0)
        rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(row["eval_only"] is True for row in rows))


if __name__ == "__main__":
    unittest.main()
