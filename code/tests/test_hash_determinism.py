from __future__ import annotations

import importlib.util
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


manifest = _load_script("build_stage2_manifest_hash_contract", SCRIPTS_DIR / "320_build_stage2_manifest.py")


class TestStage2HashDeterminism(unittest.TestCase):
    def canonical_en(self, text: str) -> str:
        return manifest.canonicalize_clean_text(text, lang="en")

    def en_side_hash(self, text: str) -> str:
        return manifest.sha256_text(text, lang="en")

    def pair_hash_for_en(self, text: str) -> str:
        haw_hash = manifest.sha256_text("aloha", lang="haw")
        return manifest.compute_pair_hash(self.en_side_hash(text), haw_hash)

    def test_en_apostrophe_policy_folds_curly_but_not_modifier_apostrophe(self):
        self.assertEqual(self.canonical_en("don't"), "don't")
        self.assertEqual(self.canonical_en("don\u2019t"), "don't")
        self.assertEqual(self.canonical_en("don\u02bct"), "don\u02bct")
        self.assertEqual(self.pair_hash_for_en("don't"), self.pair_hash_for_en("don\u2019t"))
        self.assertNotEqual(self.pair_hash_for_en("don't"), self.pair_hash_for_en("don\u02bct"))

    def test_en_double_quote_policy_folds_curly_to_straight(self):
        self.assertEqual(self.canonical_en('"hello"'), '"hello"')
        self.assertEqual(self.canonical_en("\u201chello\u201d"), '"hello"')
        self.assertEqual(self.pair_hash_for_en('"hello"'), self.pair_hash_for_en("\u201chello\u201d"))

    def test_en_hyphen_policy_folds_hyphen_and_nonbreaking_hyphen(self):
        self.assertEqual(self.canonical_en("co-op"), "co-op")
        self.assertEqual(self.canonical_en("co\u2010op"), "co-op")
        self.assertEqual(self.canonical_en("co\u2011op"), "co-op")
        self.assertEqual(self.pair_hash_for_en("co-op"), self.pair_hash_for_en("co\u2010op"))
        self.assertEqual(self.pair_hash_for_en("co-op"), self.pair_hash_for_en("co\u2011op"))

    def test_en_dash_policy_keeps_em_dash_double_hyphen_and_spaced_hyphen_distinct(self):
        self.assertEqual(self.canonical_en("\u2014"), "\u2014")
        self.assertEqual(self.canonical_en("--"), "--")
        self.assertEqual(self.canonical_en(" - "), "-")
        self.assertNotEqual(self.pair_hash_for_en("\u2014"), self.pair_hash_for_en("--"))
        self.assertNotEqual(self.pair_hash_for_en("\u2014"), self.pair_hash_for_en(" - "))
        self.assertNotEqual(self.pair_hash_for_en("--"), self.pair_hash_for_en(" - "))

    def test_whitespace_policy_trims_and_collapses_runs_to_ascii_space(self):
        messy = "\t hello\u00a0  wide\nworld \t"
        self.assertEqual(self.canonical_en(messy), "hello wide world")
        self.assertEqual(self.canonical_en("hello wide world"), "hello wide world")
        self.assertEqual(self.pair_hash_for_en(messy), self.pair_hash_for_en("hello wide world"))

    def test_case_policy_preserves_case(self):
        self.assertEqual(self.canonical_en("Aloha"), "Aloha")
        self.assertEqual(self.canonical_en("aloha"), "aloha")
        self.assertNotEqual(self.pair_hash_for_en("Aloha"), self.pair_hash_for_en("aloha"))

    def test_hawaiian_okina_policy_is_language_scoped(self):
        self.assertEqual(manifest.canonicalize_clean_text("Hawai'i", lang="en"), "Hawai'i")
        self.assertEqual(manifest.canonicalize_clean_text("Hawai'i", lang="haw"), "Hawaiʻi")
        self.assertNotEqual(manifest.sha256_text("Hawai'i", lang="en"), manifest.sha256_text("Hawai'i", lang="haw"))


if __name__ == "__main__":
    unittest.main()
