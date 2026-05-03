from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "340_audit_stage2_candidate_normalization.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("audit_stage2_candidate_normalization", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


audit_mod = _load_script()


class TestStage2CandidateNormalizationAudit(unittest.TestCase):
    def test_hawaiian_okina_folds_but_english_apostrophe_is_preserved(self):
        self.assertEqual(audit_mod.normalize_haw("Hawai'i ‘olelo ’aina"), "Hawaiʻi ʻolelo ʻaina")
        self.assertEqual(audit_mod.text_key("don't change John's", haw=False), "don't change john's")
        self.assertNotEqual(
            audit_mod.text_key("Hawai'i", haw=False),
            audit_mod.text_key("Hawaiʻi", haw=False),
        )

    def test_text_key_removes_invisible_format_controls(self):
        self.assertEqual(audit_mod.text_key("abc\u200bdef", haw=False), "abcdef")
        self.assertEqual(audit_mod.text_key("hoo\u00adponopono", haw=True), "hooponopono")

    def test_pair_hash_uses_manifest_helper_separator(self):
        en_hash = audit_mod.sha256_text("hello")
        haw_hash = audit_mod.sha256_text("aloha")
        self.assertEqual(audit_mod.pair_hash(en_hash, haw_hash), audit_mod._manifest.compute_pair_hash(en_hash, haw_hash))

    def test_jaccard_near_duplicate_score(self):
        a = {"i", "kinohi", "hana", "akua"}
        b = {"i", "kinohi", "hana", "ke", "akua"}
        self.assertGreaterEqual(audit_mod.jaccard(a, b), 0.70)


if __name__ == "__main__":
    unittest.main()
