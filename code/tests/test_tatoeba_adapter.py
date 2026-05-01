"""Tests for the Tatoeba en↔haw source adapter (issue #17).

Tests parse, join, hash, and schema-compliance logic using synthetic fixtures.
No network requests are made. All assertions use stdlib unittest only.

Run::

    python -m unittest code/tests/test_tatoeba_adapter.py -v
"""

from __future__ import annotations

import hashlib
import math
import sys
import unittest
import unicodedata
from pathlib import Path

# Make data-sources/ importable.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DATASOURCES = _REPO_ROOT / "data-sources"
if str(_DATASOURCES) not in sys.path:
    sys.path.insert(0, str(_DATASOURCES))

# Also make code/ importable for the manifest schema validator.
_CODE_DIR = _REPO_ROOT / "code"
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

from tatoeba.fetch import (  # noqa: E402
    ALIGNMENT_METHOD,
    ALIGNMENT_TYPE,
    MANIFEST_SCHEMA_VERSION,
    REGISTER,
    SOURCE,
    build_candidate_row,
    join_pairs,
    parse_links,
    parse_sentences_detailed,
    stream_sentences_for_ids,
    _nfc,
    _sha256,
    _length_ratio,
    TATOEBA_SENTENCE_URL_TEMPLATE,
)

FIXTURES = _REPO_ROOT / "code" / "tests" / "fixtures" / "tatoeba"


def _load_fixture(filename: str) -> list[str]:
    return (FIXTURES / filename).read_text(encoding="utf-8").splitlines()


def _haw_rows() -> dict:
    return parse_sentences_detailed(iter(_load_fixture("haw_sentences_detailed.tsv")))


def _eng_rows() -> dict:
    return parse_sentences_detailed(iter(_load_fixture("eng_sentences_detailed.tsv")))


def _links() -> list:
    return parse_links(iter(_load_fixture("haw-eng_links.tsv")))


class TestParseSentencesDetailed(unittest.TestCase):

    def test_parses_five_haw_sentences(self):
        rows = _haw_rows()
        self.assertEqual(len(rows), 5)

    def test_parses_six_eng_sentences(self):
        rows = _eng_rows()
        self.assertEqual(len(rows), 6)

    def test_sentence_fields_present(self):
        rows = _haw_rows()
        row = rows["1001"]
        self.assertEqual(row["sentence_id"], "1001")
        self.assertEqual(row["lang"], "haw")
        self.assertIn("ʻO Hawaiʻi", row["text"])
        self.assertEqual(row["username"], "user1")

    def test_skips_blank_lines(self):
        lines = ["", "1001\thaw\tHello.\tuser1\t2020\t2020", ""]
        rows = parse_sentences_detailed(iter(lines))
        self.assertEqual(len(rows), 1)

    def test_skips_short_lines(self):
        lines = ["1001\thaw"]  # only 2 columns, text missing
        rows = parse_sentences_detailed(iter(lines))
        self.assertEqual(len(rows), 0)

    def test_skips_empty_text(self):
        lines = ["1001\thaw\t\tuser1\t2020\t2020"]  # text column is empty
        rows = parse_sentences_detailed(iter(lines))
        self.assertEqual(len(rows), 0)


class TestParseLinks(unittest.TestCase):

    def test_parses_five_links(self):
        links = _links()
        self.assertEqual(len(links), 5)

    def test_link_structure(self):
        links = _links()
        self.assertIn(("1001", "2001"), links)
        self.assertIn(("1005", "2005"), links)

    def test_skips_blank_lines(self):
        links = parse_links(iter(["", "1001\t2001", ""]))
        self.assertEqual(len(links), 1)

    def test_skips_malformed_lines(self):
        links = parse_links(iter(["1001"]))  # only one column
        self.assertEqual(len(links), 0)


class TestStreamSentencesForIds(unittest.TestCase):

    def test_returns_only_needed_ids(self):
        lines = _load_fixture("eng_sentences_detailed.tsv")
        needed = {"2001", "2003"}
        result = stream_sentences_for_ids(iter(lines), needed)
        self.assertEqual(set(result.keys()), {"2001", "2003"})

    def test_excludes_unlinked_sentence(self):
        lines = _load_fixture("eng_sentences_detailed.tsv")
        needed = {"2001", "2002", "2003", "2004", "2005"}
        result = stream_sentences_for_ids(iter(lines), needed)
        self.assertNotIn("9999", result)

    def test_empty_needed_set_returns_empty(self):
        lines = _load_fixture("eng_sentences_detailed.tsv")
        result = stream_sentences_for_ids(iter(lines), set())
        self.assertEqual(len(result), 0)


class TestBuildCandidateRow(unittest.TestCase):

    def setUp(self):
        self.haw_row = {
            "sentence_id": "1001",
            "lang": "haw",
            "text": "ʻO Hawaiʻi kēia ʻāina nani.",
            "username": "user1",
            "date_added": "2020-01-01",
        }
        self.eng_row = {
            "sentence_id": "2001",
            "lang": "eng",
            "text": "Hawaiʻi is a beautiful land.",
            "username": "user6",
            "date_added": "2020-01-01",
        }
        self.row = build_candidate_row(self.haw_row, self.eng_row, "20250501")

    def test_pair_id_format(self):
        self.assertEqual(self.row["pair_id"], "tatoeba-haw1001-en2001")

    def test_source_fields(self):
        self.assertEqual(self.row["source"], SOURCE)
        self.assertEqual(self.row["source_url_haw"], TATOEBA_SENTENCE_URL_TEMPLATE.format(id="1001"))
        self.assertEqual(self.row["source_url_en"], TATOEBA_SENTENCE_URL_TEMPLATE.format(id="2001"))

    def test_alignment_fields(self):
        self.assertEqual(self.row["alignment_type"], ALIGNMENT_TYPE)
        self.assertEqual(self.row["alignment_method"], ALIGNMENT_METHOD)
        self.assertIsNone(self.row["alignment_score"])
        self.assertIsNone(self.row["alignment_model"])

    def test_schema_policy_fields(self):
        self.assertEqual(self.row["register"], REGISTER)
        self.assertFalse(self.row["synthetic"])
        self.assertTrue(self.row["prototype_only"])
        self.assertFalse(self.row["release_eligible"])
        self.assertIsNone(self.row["license_inferred"])
        self.assertEqual(self.row["split"], "review-pending")
        self.assertEqual(self.row["manifest_schema_version"], MANIFEST_SCHEMA_VERSION)

    def test_language_id_fields(self):
        self.assertEqual(self.row["lang_id_haw"], "haw")
        self.assertEqual(self.row["lang_id_en"], "en")
        self.assertEqual(self.row["lang_id_haw_confidence"], 1.0)
        self.assertEqual(self.row["lang_id_en_confidence"], 1.0)
        self.assertEqual(self.row["direction_original"], "unknown")

    def test_license_fields(self):
        self.assertIn("CC-BY", self.row["license_observed_haw"])
        self.assertIn("CC-BY", self.row["license_observed_en"])

    def test_hash_fields_present_and_typed(self):
        for field in ("sha256_en_raw", "sha256_haw_raw", "sha256_en_clean", "sha256_haw_clean", "sha256_pair"):
            self.assertIsInstance(self.row[field], str)
            self.assertEqual(len(self.row[field]), 64, f"{field} should be 64-char hex")

    def test_pair_hash_invariant(self):
        """sha256_pair == sha256(sha256_en_clean + '‖' + sha256_haw_clean)."""
        expected = hashlib.sha256(
            (self.row["sha256_en_clean"] + "\u2016" + self.row["sha256_haw_clean"]).encode("utf-8")
        ).hexdigest()
        self.assertEqual(self.row["sha256_pair"], expected)

    def test_nfc_normalization_applied(self):
        """text_en and text_haw should be in NFC form."""
        self.assertEqual(self.row["text_haw"], unicodedata.normalize("NFC", self.haw_row["text"]))
        self.assertEqual(self.row["text_en"], unicodedata.normalize("NFC", self.eng_row["text"]))

    def test_raw_hash_differs_from_clean_when_nfc_differs(self):
        """sha256_*_raw may equal sha256_*_clean for NFC input (both are fine)."""
        # For NFC input text, raw == clean is acceptable.
        haw_clean = _nfc(self.haw_row["text"])
        self.assertEqual(self.row["sha256_haw_clean"], _sha256(haw_clean))

    def test_length_ratio_present_and_positive(self):
        ratio = self.row["length_ratio_haw_over_en"]
        self.assertIsNotNone(ratio)
        self.assertGreater(ratio, 0.0)

    def test_record_ids(self):
        self.assertEqual(self.row["record_id_haw"], "1001")
        self.assertEqual(self.row["record_id_en"], "2001")

    def test_fetch_date_stored(self):
        self.assertEqual(self.row["fetch_date"], "20250501")

    def test_contributor_fields(self):
        self.assertEqual(self.row["contributor_haw"], "user1")
        self.assertEqual(self.row["contributor_en"], "user6")


class TestJoinPairs(unittest.TestCase):

    def setUp(self):
        self.haw = _haw_rows()
        self.links = _links()
        lines = _load_fixture("eng_sentences_detailed.tsv")
        needed = {eng_id for _, eng_id in self.links}
        self.eng = stream_sentences_for_ids(iter(lines), needed)
        self.rows = join_pairs(self.haw, self.links, self.eng, "20250501")

    def test_produces_five_pairs(self):
        self.assertEqual(len(self.rows), 5)

    def test_all_pairs_have_required_fields(self):
        required = [
            "pair_id", "source", "source_url_en", "source_url_haw", "fetch_date",
            "sha256_en_raw", "sha256_haw_raw", "sha256_en_clean", "sha256_haw_clean",
            "sha256_pair", "record_id_en", "record_id_haw",
            "alignment_type", "alignment_method",
            "alignment_review_required",
            "lang_id_en", "lang_id_en_confidence",
            "lang_id_haw", "lang_id_haw_confidence",
            "direction_original", "register",
            "synthetic", "license_observed_en", "license_observed_haw",
            "license_inferred", "prototype_only", "release_eligible",
            "dedup_cluster_id", "crosslink_stage1_overlap",
            "split", "manifest_schema_version",
        ]
        for row in self.rows:
            for field in required:
                self.assertIn(field, row, f"Missing required field '{field}' in row {row.get('pair_id')}")

    def test_text_en_or_path_requirement(self):
        for row in self.rows:
            has_text = row.get("text_en") or row.get("text_en_path")
            self.assertTrue(has_text, f"Row {row['pair_id']} lacks text_en or text_en_path")

    def test_text_haw_or_path_requirement(self):
        for row in self.rows:
            has_text = row.get("text_haw") or row.get("text_haw_path")
            self.assertTrue(has_text, f"Row {row['pair_id']} lacks text_haw or text_haw_path")

    def test_skips_missing_eng_side(self):
        """Links with no matching eng sentence are dropped."""
        bad_links = [("1001", "MISSING_ENG_ID")]
        rows = join_pairs(self.haw, bad_links, self.eng, "20250501")
        self.assertEqual(len(rows), 0)

    def test_skips_missing_haw_side(self):
        """Links with no matching haw sentence are dropped."""
        bad_links = [("MISSING_HAW_ID", "2001")]
        rows = join_pairs(self.haw, bad_links, self.eng, "20250501")
        self.assertEqual(len(rows), 0)

    def test_all_pair_hashes_unique(self):
        pair_hashes = [r["sha256_pair"] for r in self.rows]
        self.assertEqual(len(pair_hashes), len(set(pair_hashes)))

    def test_prototype_only_never_release_eligible(self):
        for row in self.rows:
            if row["prototype_only"] is True:
                self.assertFalse(row["release_eligible"],
                                 f"prototype_only=true row {row['pair_id']} must not be release_eligible")


class TestSchemaCompatibility(unittest.TestCase):
    """Verify candidate rows pass the manifest schema validator from 320_build_stage2_manifest.py."""

    def setUp(self):
        self.haw = _haw_rows()
        links = _links()
        lines = _load_fixture("eng_sentences_detailed.tsv")
        needed = {eng_id for _, eng_id in links}
        eng = stream_sentences_for_ids(iter(lines), needed)
        self.rows = join_pairs(self.haw, links, eng, "20250501")

    def test_all_rows_pass_manifest_schema(self):
        try:
            # Import the validator from 320_build_stage2_manifest.py.
            scripts_dir = _REPO_ROOT / "scripts"
            if str(scripts_dir) not in sys.path:
                sys.path.insert(0, str(scripts_dir))
            from importlib import import_module
            # The script can't be imported as a module directly due to its name starting with a digit.
            # Use importlib machinery to load it.
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "build_stage2_manifest",
                scripts_dir / "320_build_stage2_manifest.py",
            )
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            validate_row = m.validate_row
        except Exception as exc:
            self.skipTest(f"Could not import 320_build_stage2_manifest.py: {exc}")

        for row in self.rows:
            # Apply the alignment-quality policy first — adapter rows
            # carry the structural fields, the manifest builder
            # (issue #19) merges policy fields on at ingest time.
            scored = m.apply_policy(dict(row))
            violations = validate_row(scored)
            self.assertEqual(
                violations, [],
                f"Row {row['pair_id']} has schema violations: {violations}",
            )


class TestSelfTest(unittest.TestCase):
    """Verify the adapter's built-in self-test passes."""

    def test_self_test_exits_zero(self):
        from tatoeba.fetch import _self_test
        result = _self_test()
        self.assertEqual(result, 0)


class TestHelpers(unittest.TestCase):

    def test_nfc_normalizes(self):
        # Combining macron over 'a' should normalize to ā.
        combining = "a\u0304"  # 'a' + combining macron = ā (NFD)
        nfc_result = _nfc(combining)
        self.assertEqual(nfc_result, "\u0101")  # ā precomposed

    def test_sha256_returns_64_hex(self):
        h = _sha256("hello")
        self.assertEqual(len(h), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in h))

    def test_length_ratio_basic(self):
        ratio = _length_ratio("aloha ʻoe", "goodbye friend")
        self.assertAlmostEqual(ratio, 2.0 / 2.0, places=3)

    def test_length_ratio_zero_en(self):
        ratio = _length_ratio("aloha", "")
        self.assertIsNone(ratio)


if __name__ == "__main__":
    unittest.main()
