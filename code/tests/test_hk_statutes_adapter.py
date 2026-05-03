"""Tests for the Hawaiian Kingdom statutes Stage-2 adapter."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"


def _load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


hk = _load_script("build_hk_statutes_candidates", SCRIPTS_DIR / "325_build_hk_statutes_candidates.py")
stage2_manifest = _load_script("stage2_manifest_for_hk_tests", SCRIPTS_DIR / "320_build_stage2_manifest.py")


class _FakeResponse:
    status = 200
    headers = {"Content-Type": "text/plain"}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return b"ok"


class TestHKStatutesAdapter(unittest.TestCase):
    def test_1897_fixture_builds_schema_valid_rows(self):
        rows, report = hk.build_rows_from_texts(
            hk._SELFTEST_EN_1897,
            hk._SELFTEST_HAW_1897,
            hk.EDITIONS["1897"],
        )

        self.assertEqual(report["common_sections"], 3)
        self.assertEqual(len(rows), 3)
        row = rows[0]
        self.assertEqual(row["source"], "hk_statutes_1897")
        self.assertEqual(row["alignment_method"], "filename-pair")
        self.assertEqual(row["register"], "unknown")
        self.assertEqual(row["tos_snapshot_id"], "ia_terms")
        self.assertIsNone(row["license_inferred"])
        self.assertEqual(
            row["sha256_pair"],
            stage2_manifest.compute_pair_hash(row["sha256_en_clean"], row["sha256_haw_clean"]),
        )
        policy_missing = {
            "type:alignment_confidence_tier=NoneType",
            "type:quality_flags=NoneType",
            "type:manual_review_reasons=NoneType",
            "type:alignment_score_components=NoneType",
            "type:policy_version=NoneType",
        }
        real_violations = [v for v in stage2_manifest.validate_row(row) if v not in policy_missing]
        self.assertEqual(real_violations, [])

    def test_non_executable_edition_parses_but_emits_no_rows(self):
        rows, report = hk.build_rows_from_texts(
            hk._SELFTEST_EN_NUMERIC,
            hk._SELFTEST_HAW_NUMERIC,
            hk.EDITIONS["1859"],
        )

        self.assertEqual(report["common_sections"], 2)
        self.assertFalse(hk.EDITIONS["1859"].executable)
        self.assertEqual(rows, [])
        self.assertIn("dryrun", hk.EDITIONS["1859"].status)

    def test_fetch_helper_uses_user_agent_and_rate_limit_with_mocked_http(self):
        captured = {}

        def fake_opener(req, timeout):
            captured["url"] = req.full_url
            captured["ua"] = req.get_header("User-agent")
            captured["timeout"] = timeout
            return _FakeResponse()

        sleep = mock.Mock()
        status, ctype, body = hk.fetch_url(
            "https://archive.org/robots.txt",
            opener=fake_opener,
            sleep_fn=sleep,
            rate_limit_seconds=1.25,
        )

        self.assertEqual(status, 200)
        self.assertEqual(ctype, "text/plain")
        self.assertEqual(body, b"ok")
        self.assertEqual(captured["url"], "https://archive.org/robots.txt")
        self.assertIn("ideal-spoon", captured["ua"])
        self.assertEqual(captured["timeout"], 120)
        sleep.assert_called_once_with(1.25)

    def test_self_test_returns_success(self):
        self.assertEqual(hk.self_test(), 0)


if __name__ == "__main__":
    unittest.main()
