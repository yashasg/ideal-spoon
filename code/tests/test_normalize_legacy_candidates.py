from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "341_normalize_legacy_candidates.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("normalize_legacy_candidates", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


m = _load_script()


class TestNormalizeLegacyCandidates(unittest.TestCase):
    def test_okina_fold_recomputes_haw_and_pair_hashes(self):
        row = {
            "pair_id": "p1",
            "source": "weblate-en-haw",
            "source_url": "https://example.invalid/unit",
            "fetch_date": "20260501",
            "text_en": "Use words",
            "text_haw": "E ho'ohana i ka 'olelo",
            "alignment_type": "parallel-sentence",
            "alignment_method": "tmx-line",
            "direction_original": "en->haw",
            "register": "software-l10n",
            "license_observed": "MIT",
            "prototype_only": True,
            "release_eligible": False,
            "split": "review-pending",
        }
        out = m.canonicalize_row(row)
        self.assertEqual(out["text_haw"], "E hoʻohana i ka ʻolelo")
        self.assertEqual(out["sha256_haw_clean"], m.sha256_text("E hoʻohana i ka ʻolelo"))
        self.assertEqual(out["sha256_pair"], m._manifest.compute_pair_hash(out["sha256_en_clean"], out["sha256_haw_clean"]))
        self.assertEqual(out["license_inferred"], None)

    def test_legacy_enums_map_to_manifest_schema(self):
        row = {
            "pair_id": "phrase-1",
            "source": "ia-hawaiian-phrase-book-1881",
            "source_url_en": "https://example.invalid/book",
            "source_url_haw": "https://example.invalid/book",
            "fetch_date": "20260501",
            "sha256_en_raw": "x",
            "sha256_haw_raw": "y",
            "text_en": "The good flower blooms.",
            "text_haw": "Mohala ka pua maikaʻi.",
            "record_id_en": "r-en",
            "record_id_haw": "r-haw",
            "alignment_type": "phrase-pair",
            "alignment_method": "two-column-djvu-xml-coordinate-pairing-v1",
            "alignment_review_required": True,
            "length_ratio_haw_over_en": 1.0,
            "lang_id_en": "en",
            "lang_id_en_confidence": 1.0,
            "lang_id_haw": "haw",
            "lang_id_haw_confidence": 1.0,
            "direction_original": "en->haw",
            "register": "phrase-book",
            "synthetic": False,
            "license_observed_en": "PD",
            "license_observed_haw": "PD",
            "license_inferred": "PD",
            "prototype_only": False,
            "release_eligible": True,
            "dedup_cluster_id": "phrase-1",
            "crosslink_stage1_overlap": False,
            "split": "review-pending",
            "manifest_schema_version": "stage2.v0",
        }
        out = m.canonicalize_row(row)
        self.assertEqual(out["alignment_type"], "parallel-sentence")
        self.assertEqual(out["alignment_method"], "manual")
        self.assertEqual(out["register"], "educational")
        self.assertNotIn("enum:alignment_type='phrase-pair'", m._manifest.validate_row(out))
        self.assertNotIn("dep:license_inferred_must_be_null", m._manifest.validate_row(out))


if __name__ == "__main__":
    unittest.main()
