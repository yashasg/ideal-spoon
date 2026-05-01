"""Tests for Stage-2 SFT emitter template loading and rotation (issue #20).

Tests:
- load_templates: absent file, valid file, malformed file, NFC normalization
- pick_template: determinism, rotation coverage, all pair_ids land in range
- resolve_instructions: no-templates falls back to DEFAULT, with-templates rotates
- build_directional_row: instruction comes from templates when loaded
- CLI --templates wiring: emitter uses fixture templates

Stdlib + unittest only. No network. Fixtures under code/tests/fixtures/stage2/.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
FIXTURE_TEMPLATES = REPO_ROOT / "code" / "tests" / "fixtures" / "stage2" / "templates.json"


def _load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


e = _load_script("emit_stage2_sft", SCRIPTS_DIR / "330_emit_stage2_sft_jsonl.py")


# ---------------------------------------------------------------------------
# load_templates
# ---------------------------------------------------------------------------

class TestLoadTemplates(unittest.TestCase):

    def test_absent_file_returns_none(self):
        result = e.load_templates(Path("/nonexistent/templates.json"))
        self.assertIsNone(result)

    def test_valid_fixture_loads(self):
        result = e.load_templates(FIXTURE_TEMPLATES)
        self.assertIsNotNone(result)
        self.assertIn("en->haw", result)
        self.assertIn("haw->en", result)
        self.assertGreaterEqual(len(result["en->haw"]), 2)
        self.assertGreaterEqual(len(result["haw->en"]), 2)

    def test_nfc_normalized_on_load(self):
        """Templates loaded from disk must be NFC-normalized."""
        result = e.load_templates(FIXTURE_TEMPLATES)
        self.assertIsNotNone(result)
        for direction, tlist in result.items():
            for t in tlist:
                self.assertEqual(t, unicodedata.normalize("NFC", t),
                                 f"Template not NFC in direction {direction!r}: {t!r}")

    def test_okina_u02bb_preserved(self):
        """ʻokina (U+02BB) in Hawaiian-side templates must survive load."""
        result = e.load_templates(FIXTURE_TEMPLATES)
        self.assertIsNotNone(result)
        haw_templates = result["haw->en"]
        haw_joined = " ".join(haw_templates)
        # At least one template should contain ʻokina or kahakō from the fixture.
        self.assertTrue(
            "\u02bb" in haw_joined or "\u0101" in haw_joined or "\u0113" in haw_joined,
            "Expected Hawaiian orthography characters in haw->en templates",
        )

    def test_malformed_json_returns_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "bad.json"
            p.write_text("not json at all", encoding="utf-8")
            result = e.load_templates(p)
        self.assertIsNone(result)

    def test_wrong_schema_returns_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "bad.json"
            p.write_text('["list", "not", "object"]', encoding="utf-8")
            result = e.load_templates(p)
        self.assertIsNone(result)

    def test_empty_direction_list_returns_none(self):
        data = {"en->haw": [], "haw->en": ["Something."]}
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "bad.json"
            p.write_text(json.dumps(data), encoding="utf-8")
            result = e.load_templates(p)
        self.assertIsNone(result)

    def test_missing_direction_returns_none(self):
        data = {"en->haw": ["Only one direction."]}
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "bad.json"
            p.write_text(json.dumps(data), encoding="utf-8")
            result = e.load_templates(p)
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# pick_template
# ---------------------------------------------------------------------------

class TestPickTemplate(unittest.TestCase):

    def test_deterministic_same_pair_id(self):
        templates = ["A", "B", "C"]
        t1 = e.pick_template(templates, "pair-abc")
        t2 = e.pick_template(templates, "pair-abc")
        self.assertEqual(t1, t2)

    def test_in_range(self):
        templates = ["A", "B", "C"]
        for i in range(100):
            result = e.pick_template(templates, f"pair-{i}")
            self.assertIn(result, templates)

    def test_all_templates_reachable(self):
        """With enough diverse pair_ids, all templates should be selected."""
        templates = ["A", "B", "C", "D", "E"]
        seen = set()
        for i in range(500):
            seen.add(e.pick_template(templates, f"diverse-pair-{i:05d}"))
        self.assertEqual(seen, set(templates), "All templates should be reachable")

    def test_single_template_always_returned(self):
        result = e.pick_template(["Only one."], "any-pair-id")
        self.assertEqual(result, "Only one.")

    def test_different_pair_ids_may_differ(self):
        templates = ["A", "B", "C"]
        results = {e.pick_template(templates, f"p-{i}") for i in range(30)}
        self.assertGreater(len(results), 1, "Different pair_ids should yield different templates")


# ---------------------------------------------------------------------------
# resolve_instructions
# ---------------------------------------------------------------------------

class TestResolveInstructions(unittest.TestCase):

    def test_no_templates_returns_defaults(self):
        instr = e.resolve_instructions(None, "some-pair-id")
        self.assertEqual(instr["en->haw"], e.DEFAULT_INSTRUCTIONS["en->haw"])
        self.assertEqual(instr["haw->en"], e.DEFAULT_INSTRUCTIONS["haw->en"])

    def test_with_templates_rotates(self):
        templates = {
            "en->haw": ["Tmpl-A", "Tmpl-B", "Tmpl-C"],
            "haw->en": ["Tmpl-X", "Tmpl-Y", "Tmpl-Z"],
        }
        instr = e.resolve_instructions(templates, "some-pair-id")
        self.assertIn(instr["en->haw"], templates["en->haw"])
        self.assertIn(instr["haw->en"], templates["haw->en"])

    def test_rotation_is_deterministic(self):
        templates = {
            "en->haw": ["A", "B"],
            "haw->en": ["X", "Y"],
        }
        r1 = e.resolve_instructions(templates, "deterministic-pair")
        r2 = e.resolve_instructions(templates, "deterministic-pair")
        self.assertEqual(r1, r2)

    def test_different_pairs_may_get_different_templates(self):
        templates = {
            "en->haw": ["A", "B", "C"],
            "haw->en": ["X", "Y", "Z"],
        }
        instrs = [e.resolve_instructions(templates, f"pair-{i}")["en->haw"] for i in range(30)]
        self.assertGreater(len(set(instrs)), 1)


# ---------------------------------------------------------------------------
# build_directional_row uses templates
# ---------------------------------------------------------------------------

class TestBuildDirectionalRowTemplates(unittest.TestCase):

    def _make_cfg(self, templates):
        return e.EmitConfig(
            splits={"train"},
            directions={"en->haw", "haw->en"},
            min_alignment_score=None,
            allow_review_required=False,
            allow_synthetic=False,
            instructions=dict(e.DEFAULT_INSTRUCTIONS),
            templates=templates,
        )

    def _make_pair(self):
        return e.ResolvedPair(
            text_en="Hello world.", text_haw="Aloha honua.",
            en_inline=True, haw_inline=True,
        )

    def _make_row(self, pair_id="test-pair"):
        return {
            "pair_id": pair_id,
            "split": "train",
            "source": "test-source",
            "alignment_type": "parallel-sentence",
            "alignment_method": "manual",
        }

    def test_without_templates_uses_default(self):
        cfg = self._make_cfg(None)
        row = self._make_row()
        result = e.build_directional_row(row, "en->haw", self._make_pair(), cfg)
        self.assertEqual(result["instruction"], e.DEFAULT_INSTRUCTIONS["en->haw"])

    def test_with_templates_instruction_in_list(self):
        templates = {
            "en->haw": ["Option A.", "Option B.", "Option C."],
            "haw->en": ["Haw A.", "Haw B.", "Haw C."],
        }
        cfg = self._make_cfg(templates)
        row = self._make_row()
        result = e.build_directional_row(row, "en->haw", self._make_pair(), cfg)
        self.assertIn(result["instruction"], templates["en->haw"])

    def test_template_rotation_deterministic_per_pair(self):
        templates = {
            "en->haw": ["A", "B", "C"],
            "haw->en": ["X", "Y", "Z"],
        }
        cfg = self._make_cfg(templates)
        pair = self._make_pair()
        row = self._make_row("stable-pair-id-xyz")
        r1 = e.build_directional_row(row, "en->haw", pair, cfg)
        r2 = e.build_directional_row(row, "en->haw", pair, cfg)
        self.assertEqual(r1["instruction"], r2["instruction"])


# ---------------------------------------------------------------------------
# CLI --templates wiring
# ---------------------------------------------------------------------------

class TestCLITemplatesWiring(unittest.TestCase):
    """Smoke-test that CLI wires --templates into the emitter."""

    def _make_manifest_row(self, pair_id: str = "cli-pair") -> dict:
        text_en = "The sky is blue."
        text_haw = "ʻUliʻuli ke lani."
        en_nfc = unicodedata.normalize("NFC", text_en)
        haw_nfc = unicodedata.normalize("NFC", text_haw)
        sha_en_c = hashlib.sha256(en_nfc.encode()).hexdigest()
        sha_haw_c = hashlib.sha256(haw_nfc.encode()).hexdigest()
        sha_pair = hashlib.sha256(
            (sha_en_c + "\u2016" + sha_haw_c).encode()
        ).hexdigest()
        return {
            "pair_id": pair_id,
            "source": "test",
            "source_url_en": "https://example.com/en",
            "source_url_haw": "https://example.com/haw",
            "fetch_date": "20250501",
            "sha256_en_raw": hashlib.sha256(text_en.encode()).hexdigest(),
            "sha256_haw_raw": hashlib.sha256(text_haw.encode()).hexdigest(),
            "sha256_en_clean": sha_en_c,
            "sha256_haw_clean": sha_haw_c,
            "sha256_pair": sha_pair,
            "record_id_en": "1",
            "record_id_haw": "1",
            "text_en": text_en,
            "text_haw": text_haw,
            "alignment_type": "parallel-sentence",
            "alignment_method": "manual",
            "alignment_score": None,
            "alignment_review_required": False,
            "length_ratio_haw_over_en": 1.0,
            "lang_id_en": "en",
            "lang_id_en_confidence": 1.0,
            "lang_id_haw": "haw",
            "lang_id_haw_confidence": 1.0,
            "direction_original": "unknown",
            "register": "unknown",
            "synthetic": False,
            "license_observed_en": "cc0",
            "license_observed_haw": "cc0",
            "license_inferred": None,
            "prototype_only": True,
            "release_eligible": False,
            "dedup_cluster_id": pair_id,
            "crosslink_stage1_overlap": False,
            "split": "train",
            "manifest_schema_version": "stage2.v0",
        }

    def test_cli_with_fixture_templates_runs_and_emits(self):
        row = self._make_manifest_row()
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "manifest.jsonl"
            out_path = Path(tmpdir) / "sft.jsonl"
            with manifest_path.open("w", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            rc = e.main([
                "--manifest", str(manifest_path),
                "--out", str(out_path),
                "--splits", "train",
                "--directions", "both",
                "--templates", str(FIXTURE_TEMPLATES),
                "--allow-empty",
            ])
        self.assertEqual(rc, 0)

    def test_cli_no_templates_flag_uses_defaults(self):
        row = self._make_manifest_row()
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "manifest.jsonl"
            out_path = Path(tmpdir) / "sft.jsonl"
            with manifest_path.open("w", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            rc = e.main([
                "--manifest", str(manifest_path),
                "--out", str(out_path),
                "--splits", "train",
                "--no-templates",
                "--allow-empty",
            ])
            self.assertEqual(rc, 0)
            out_rows = []
            with out_path.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        out_rows.append(json.loads(line))
        en_haw_rows = [r for r in out_rows if r["direction"] == "en->haw"]
        self.assertEqual(
            en_haw_rows[0]["instruction"],
            e.DEFAULT_INSTRUCTIONS["en->haw"],
        )

    def test_cli_explicit_bad_templates_path_exits_1(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "manifest.jsonl"
            manifest_path.write_text("{}\n", encoding="utf-8")
            rc = e.main([
                "--manifest", str(manifest_path),
                "--out", str(Path(tmpdir) / "sft.jsonl"),
                "--splits", "train",
                "--templates", str(Path(tmpdir) / "nonexistent_templates.json"),
                "--allow-empty",
            ])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
