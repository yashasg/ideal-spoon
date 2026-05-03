"""Tests for the Sanitary Instructions 1881 Stage-2 adapter."""

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


sanitary = _load_script(
    "build_sanitary_instructions_candidates",
    SCRIPTS_DIR / "335_build_sanitary_instructions_candidates.py",
)
stage2_manifest = _load_script(
    "stage2_manifest_for_sanitary_tests",
    SCRIPTS_DIR / "320_build_stage2_manifest.py",
)


class TestSanitaryInstructionsAdapter(unittest.TestCase):
    def test_build_rows_from_scores_emits_schema_valid_review_rows(self):
        en_records = [
            {
                "paragraph_index": 10,
                "text": "Keep houses clean and let fresh air pass through every room daily.",
                "tokens": 12,
            },
            {
                "paragraph_index": 20,
                "text": "This unrelated paragraph should not be selected by mutual nearest scoring.",
                "tokens": 10,
            },
        ]
        haw_records = [
            {
                "paragraph_index": 11,
                "text": "E hoomaemae i na hale a e hookomo i ka ea hou i na la a pau.",
                "tokens": 16,
            },
            {
                "paragraph_index": 21,
                "text": "He pauku okoa keia no ka hoao ana i ke koho kokoke loa.",
                "tokens": 13,
            },
        ]
        scores = [
            [0.82, 0.10],
            [0.20, 0.60],
        ]

        rows, report = sanitary.build_rows_from_scores(
            en_records,
            haw_records,
            scores,
            en_path=REPO_ROOT / "data/raw/sanitary-test/en.txt",
            haw_path=REPO_ROOT / "data/raw/sanitary-test/haw.txt",
            en_sha="en-raw-sha",
            haw_sha="haw-raw-sha",
            fetch_date="20260503",
            model_id="fake-labse",
            min_score=0.70,
        )

        self.assertEqual(report["rows_emitted"], 1)
        row = rows[0]
        self.assertEqual(row["alignment_type"], "comparable-aligned")
        self.assertEqual(row["alignment_method"], "labse")
        self.assertTrue(row["alignment_review_required"])
        self.assertEqual(row["register"], "unknown")
        self.assertIsNone(row["license_inferred"])
        self.assertTrue(row["prototype_only"])
        self.assertFalse(row["release_eligible"])
        self.assertEqual(row["alignment_score_components"], {"labse_cosine": 0.82})
        self.assertEqual(row["sha256_pair"], stage2_manifest.compute_pair_hash(
            row["sha256_en_clean"], row["sha256_haw_clean"]
        ))
        self.assertEqual(stage2_manifest.validate_row(row), [])

    def test_execute_preconditions_require_pinned_edition_and_tos(self):
        with self.assertRaises(SystemExit):
            sanitary.assert_execute_preconditions(None, None)
        with self.assertRaises(SystemExit):
            sanitary.assert_execute_preconditions(sanitary.EDITION_ID, "missing-tos.html")
        note = REPO_ROOT / ".squad/decisions/inbox/linus-sanitary-schema-gate.md"
        sanitary.assert_execute_preconditions(sanitary.EDITION_ID, str(note))

    def test_self_test_returns_success(self):
        self.assertEqual(sanitary.self_test(), 0)


if __name__ == "__main__":
    unittest.main()
