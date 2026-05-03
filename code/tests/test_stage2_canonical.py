from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = CODE_ROOT.parent
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

from llm_hawaii import eval_contamination as ec
from llm_hawaii.stage2_canonical import (
    PAIR_DELIM,
    canonical_en,
    canonical_haw,
    canonical_pair,
    canonicalize_clean_text,
    compute_pair_hash,
    sha256_text,
)


def _load_manifest():
    path = REPO_ROOT / "scripts" / "320_build_stage2_manifest.py"
    spec = importlib.util.spec_from_file_location("stage2_manifest_for_canonical_tests", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


manifest = _load_manifest()


class TestStage2Canonical(unittest.TestCase):
    def test_api_surface_and_known_folds(self):
        self.assertEqual(canonical_en("don\u2019t"), "don't")
        self.assertEqual(canonical_en("co\u2010op\u00a0 now"), "co-op now")
        self.assertEqual(canonical_en("Hawai\u02bbi"), "Hawai\u02bbi")
        self.assertEqual(canonical_haw("Hawai'i \u2018olelo"), "Hawaiʻi ʻolelo")
        self.assertEqual(canonical_pair("Don\u2019t", "Hawai'i"), "Don't" + PAIR_DELIM + "Hawaiʻi")

    def test_idempotency(self):
        en = " \t \u201cHello\u201d\u00a0co\u2011op  "
        haw = " Hawai'i  \u2018olelo\u200b "
        self.assertEqual(canonical_en(canonical_en(en)), canonical_en(en))
        self.assertEqual(canonical_haw(canonical_haw(haw)), canonical_haw(haw))
        pair = canonical_pair(en, haw)
        self.assertEqual(canonical_pair(*pair.split(PAIR_DELIM, 1)), pair)

    def test_manifest_wrapper_uses_same_helper(self):
        self.assertEqual(manifest.canonicalize_clean_text("don\u2019t", lang="en"), canonical_en("don\u2019t"))
        self.assertEqual(manifest.canonicalize_clean_text("Hawai'i", lang="haw"), canonical_haw("Hawai'i"))
        en_hash = sha256_text("don\u2019t", lang="en")
        haw_hash = sha256_text("Hawai'i", lang="haw")
        self.assertEqual(manifest.sha256_text("don\u2019t", lang="en"), en_hash)
        self.assertEqual(manifest.compute_pair_hash(en_hash, haw_hash), compute_pair_hash(en_hash, haw_hash))

    def test_eval_contamination_pair_round_trip(self):
        row = {"text_en": "Don\u2019t fold Hawai\u02bbi", "text_haw": "Hawai'i"}
        content = ec.canonical_content(row)
        self.assertEqual(content, canonical_pair(row["text_en"], row["text_haw"]))
        self.assertEqual(ec.canonical_content_sha256(row), sha256_text(content))


if __name__ == "__main__":
    unittest.main()
