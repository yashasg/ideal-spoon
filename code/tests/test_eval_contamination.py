"""Tests for eval-ledger contamination helper."""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CODE_ROOT = REPO_ROOT / "code"
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

from llm_hawaii import eval_contamination as ec


class TestEvalContamination(unittest.TestCase):
    def setUp(self) -> None:
        self.work = REPO_ROOT / "data" / "test_eval_contamination"
        shutil.rmtree(self.work, ignore_errors=True)
        self.work.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.work, ignore_errors=True)

    def test_load_ledger_content_hashes(self):
        h = ec.canonical_content_sha256("E wehe i ka puka")
        ledger = self.work / "eval_hashes.jsonl"
        ledger.write_text(json.dumps({"content_sha256": h}) + "\n", encoding="utf-8")
        self.assertEqual(ec.load_eval_hashes(ledger), {h})

    def test_haw_okina_normalization_equivalence(self):
        ascii_hash = ec.canonical_content_sha256("ka ho'omaka ana")
        okina_hash = ec.canonical_content_sha256("ka hoʻomaka ana")
        self.assertEqual(ascii_hash, okina_hash)

    def test_is_contaminated_boolean(self):
        row = {"text_en": "Open John's book", "text_haw": "E wehe i ko John puke"}
        hashes = {ec.canonical_content_sha256(row)}
        self.assertTrue(ec.is_contaminated(row, hashes))
        self.assertFalse(ec.is_contaminated({"text_en": "Other", "text_haw": "Kekahi"}, hashes))

    def test_filter_candidates_drops_matches(self):
        contaminated = {"pair_id": "drop", "text_haw": "He aha ka hana?"}
        clean = {"pair_id": "keep", "text_haw": "Aloha kakou"}
        hashes = {ec.canonical_content_sha256("He aha ka hana?")}
        kept_iter, dropped = ec.filter_candidates([contaminated, clean], hashes)
        kept = list(kept_iter)
        self.assertEqual(dropped, 1)
        self.assertEqual([r["pair_id"] for r in kept], ["keep"])


if __name__ == "__main__":
    unittest.main()
