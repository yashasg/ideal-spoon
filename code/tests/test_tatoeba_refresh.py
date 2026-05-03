"""Tests for gated Tatoeba refresh adapter."""
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


adapter = _load_script("tatoeba_refresh", SCRIPTS_DIR / "349_refresh_tatoeba_candidates.py")


class TestTatoebaRefresh(unittest.TestCase):
    def setUp(self) -> None:
        self.work = REPO_ROOT / "data" / "test_tatoeba_refresh"
        shutil.rmtree(self.work, ignore_errors=True)
        self.work.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.work, ignore_errors=True)

    def test_threshold_gating(self):
        self.assertFalse(adapter.threshold_allows(existing_pair_count=100, delta_pair_count=4, new_sentence_count=499))
        self.assertTrue(adapter.threshold_allows(existing_pair_count=100, delta_pair_count=5, new_sentence_count=0))
        self.assertTrue(adapter.threshold_allows(existing_pair_count=100, delta_pair_count=0, new_sentence_count=500))

    def test_schema(self):
        rows, haw_count = adapter.build_refresh_rows(
            adapter._SELF_HAW,
            adapter._SELF_LINKS,
            adapter._SELF_ENG,
            edition_date="2026-05-02",
            existing_ids=set(),
        )
        self.assertEqual(haw_count, 3)
        self.assertEqual(len(rows), 3)
        row = rows[0]
        self.assertEqual(row["source"], "tatoeba")
        self.assertEqual(row["alignment_type"], "parallel-sentence")
        self.assertEqual(row["alignment_method"], "manual")
        self.assertEqual(row["license_observed_haw"], "CC-BY 2.0 FR")
        self.assertEqual(len(row["sha256_pair"]), 64)
        scored = adapter._STAGE2.apply_policy(dict(row))
        self.assertEqual(adapter._STAGE2.validate_row(scored), [])

    def test_okina(self):
        rows, _ = adapter.build_refresh_rows(
            adapter._SELF_HAW,
            adapter._SELF_LINKS,
            adapter._SELF_ENG,
            edition_date="2026-05-02",
            existing_ids=set(),
        )
        self.assertIn("ʻO Hawaiʻi", rows[0]["text_haw"])
        self.assertNotIn("'O Hawai'i", rows[0]["text_haw"])

    def test_dedup_vs_existing_edition(self):
        rows, new_haw_count = adapter.build_refresh_rows(
            adapter._SELF_HAW,
            adapter._SELF_LINKS,
            adapter._SELF_ENG,
            edition_date="2026-05-02",
            existing_ids={"1001-2001", "1002-2002"},
        )
        self.assertEqual(new_haw_count, 1)
        self.assertEqual([r["tatoeba_id"] for r in rows], ["1003-2003"])

    def test_existing_ids_from_existing_candidate_file(self):
        path = self.work / "tatoeba.jsonl"
        path.write_text(
            json.dumps({"tatoeba_sentence_id_haw": "111", "tatoeba_sentence_id_en": "222"}) + "\n" +
            json.dumps({"tatoeba_id": "333-444"}) + "\n",
            encoding="utf-8",
        )
        self.assertEqual(adapter.existing_tatoeba_ids(path), {"111-222", "333-444"})

    def test_source_id_format(self):
        self.assertEqual(adapter.source_id_for("1001", "2001", "2026-05-02"), "tatoeba:1001-2001:rev:2026-05-02")
        rows, _ = adapter.build_refresh_rows(adapter._SELF_HAW, adapter._SELF_LINKS, adapter._SELF_ENG, edition_date="2026-05-02", existing_ids=set())
        self.assertEqual(rows[0]["source_id"], "tatoeba:1001-2001:rev:2026-05-02")

    def test_self_test(self):
        self.assertEqual(adapter.self_test(), 0)


if __name__ == "__main__":
    unittest.main()
