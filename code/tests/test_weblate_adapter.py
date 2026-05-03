"""Tests for permissive-only Weblate Stage-2 discovery and TMX adapter."""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
import unittest
from io import StringIO
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


discovery = _load_script("weblate_discovery", SCRIPTS_DIR / "345_discover_weblate_haw_projects.py")
builder = _load_script("weblate_builder", SCRIPTS_DIR / "346_build_weblate_candidates.py")
stage2_manifest = _load_script("stage2_manifest_for_weblate_tests", SCRIPTS_DIR / "320_build_stage2_manifest.py")


class _FakeResponse:
    def __init__(self, payload: bytes):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.payload


class TestWeblateDiscovery(unittest.TestCase):
    def test_license_filter_accepts_mit_rejects_gpl(self):
        self.assertTrue(discovery.is_license_allowed("MIT"))
        self.assertTrue(discovery.is_license_allowed("Apache-2.0"))
        self.assertFalse(discovery.is_license_allowed("GPL-3.0-or-later"))
        self.assertFalse(discovery.is_license_allowed("LGPL-2.1-or-later"))
        self.assertFalse(discovery.is_license_allowed(""))

    def test_mocked_http_discovers_and_filters_components(self):
        responses = {
            "https://example.test/api/components/?language=haw": {
                "results": [
                    {"slug": "ui", "project_slug": "mitproj", "source_language": {"code": "en"}, "license": "MIT", "license_url": "https://spdx.org/licenses/MIT.html", "url": "https://example.test/api/components/mitproj/ui/"},
                    {"slug": "core", "project_slug": "gplproj", "source_language": {"code": "en"}, "license": "GPL-3.0-or-later", "license_url": "https://spdx.org/licenses/GPL-3.0-or-later.html", "url": "https://example.test/api/components/gplproj/core/"},
                ],
                "next": None,
            },
            "https://example.test/api/projects/mitproj/": {"slug": "mitproj", "license": "MIT", "license_url": "https://spdx.org/licenses/MIT.html"},
            "https://example.test/api/projects/gplproj/": {"slug": "gplproj", "license": "GPL-3.0-or-later", "license_url": "https://spdx.org/licenses/GPL-3.0-or-later.html"},
        }
        seen_uas = []

        def opener(req, timeout):
            seen_uas.append(req.get_header("User-agent"))
            return _FakeResponse(json.dumps(responses[req.full_url]).encode("utf-8"))

        sleep = mock.Mock()
        rows = discovery.discover_instance("mock", "https://example.test", tos_snapshot_sha256="abc", opener=opener, sleep_fn=sleep, sleep_seconds=2.0)
        self.assertEqual(len(rows), 2)
        by_project = {row["project_slug"]: row for row in rows}
        self.assertEqual(by_project["mitproj"]["accepted"], "true")
        self.assertEqual(by_project["gplproj"]["accepted"], "false")
        self.assertTrue(all("ideal-spoon" in ua for ua in seen_uas))
        self.assertEqual(sleep.call_count, 3)


class TestWeblateTMXAdapter(unittest.TestCase):
    def _inventory(self, license_spdx: str = "MIT") -> dict[str, str]:
        return {
            "instance": "hosted",
            "base_url": "https://hosted.weblate.org",
            "project_slug": "demo",
            "component_slug": "app",
            "license_spdx": license_spdx,
            "license_url": f"https://spdx.org/licenses/{license_spdx}.html",
            "download_tmx_url": "https://hosted.weblate.org/download/demo/app/haw/?format=tmx",
            "fetched_at": "2026-05-03T00:00:00Z",
            "accepted": "true",
        }

    def test_tmx_to_canonical_and_okina_normalization(self):
        units = builder.parse_tmx(builder._SELFTEST_TMX)
        self.assertEqual(len(units), 1)
        row = builder.build_candidate_row(units[0], self._inventory(), "rawsha")
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["source"], "weblate")
        self.assertEqual(row["pair_id"], "weblate:hosted:demo:app:menu.open")
        self.assertEqual(row["source_id"], "weblate:hosted:demo:app:menu.open")
        self.assertIn("hoʻonohonoho", row["text_haw"])
        self.assertNotIn("'", row["text_haw"])
        self.assertEqual(row["alignment_method"], "tmx-line")
        self.assertEqual(row["register"], "software-l10n")
        self.assertEqual(row["license_observed_en"], "MIT")
        self.assertEqual(row["sha256_pair"], stage2_manifest.compute_pair_hash(row["sha256_en_clean"], row["sha256_haw_clean"]))
        policy_missing = {
            "type:alignment_confidence_tier=NoneType",
            "type:quality_flags=NoneType",
            "type:manual_review_reasons=NoneType",
            "type:alignment_score_components=NoneType",
            "type:policy_version=NoneType",
        }
        real = [v for v in stage2_manifest.validate_row(row) if v not in policy_missing]
        self.assertEqual(real, [])

    def test_gpl_inventory_row_is_rejected(self):
        units = builder.parse_tmx(builder._SELFTEST_TMX)
        self.assertIsNone(builder.build_candidate_row(units[0], self._inventory("GPL-3.0-or-later"), "rawsha"))

    def test_build_rows_from_inventory_uses_mocked_http(self):
        body = builder._SELFTEST_TMX.encode("utf-8")
        captured = {}

        def opener(req, timeout):
            captured["url"] = req.full_url
            captured["ua"] = req.get_header("User-agent")
            captured["timeout"] = timeout
            return _FakeResponse(body)

        sleep = mock.Mock()
        rows = builder.build_rows_from_inventory([self._inventory()], opener=opener, sleep_fn=sleep, sleep_seconds=2.0)
        self.assertEqual(len(rows), 1)
        self.assertEqual(captured["url"], self._inventory()["download_tmx_url"])
        self.assertIn("ideal-spoon", captured["ua"])
        self.assertEqual(captured["timeout"], 120)
        sleep.assert_called_once_with(2.0)

    def test_inventory_tsv_filter_accepts_only_allowlisted_rows(self):
        text = StringIO()
        fields = ["instance", "base_url", "project_slug", "component_slug", "license_spdx", "license_url", "download_tmx_url", "fetched_at", "accepted"]
        writer = csv.DictWriter(text, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        writer.writerow(self._inventory("MIT"))
        writer.writerow(self._inventory("GPL-3.0-or-later"))
        rows = list(csv.DictReader(StringIO(text.getvalue()), delimiter="\t"))
        accepted = builder.accepted_inventory_rows(rows)
        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0]["license_spdx"], "MIT")

    def test_self_test_returns_success(self):
        self.assertEqual(builder.self_test(), 0)


if __name__ == "__main__":
    unittest.main()
