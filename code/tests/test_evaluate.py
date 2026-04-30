"""Tests for Stage 0 eval drift-signal helpers (no ML deps)."""

import unittest

from llm_hawaii import evaluate as ev


class TestPromptSuiteDescriptor(unittest.TestCase):
    def test_default_suite_descriptor_is_stable(self):
        d1 = ev.compute_prompt_suite_descriptor()
        d2 = ev.compute_prompt_suite_descriptor()
        self.assertEqual(d1["suite_sha256"], d2["suite_sha256"])
        self.assertEqual(d1["suite_id"], "stage0.v1")
        self.assertEqual(len(d1["items"]), len(ev.DEFAULT_PROMPT_SUITE))

    def test_default_suite_spans_density_bins(self):
        d = ev.compute_prompt_suite_descriptor()
        bins = {item["diacritic_density_bin"] for item in d["items"]}
        # Must include high/medium/low for orthography drift coverage.
        for required in ("high", "medium", "low"):
            self.assertIn(required, bins, f"missing density bin: {required}")

    def test_suite_changes_change_hash(self):
        d1 = ev.compute_prompt_suite_descriptor()
        suite2 = list(ev.DEFAULT_PROMPT_SUITE) + [("extra_x", "aloha mai")]
        d2 = ev.compute_prompt_suite_descriptor(suite2)
        self.assertNotEqual(d1["suite_sha256"], d2["suite_sha256"])

    def test_items_carry_no_raw_prompt_text(self):
        d = ev.compute_prompt_suite_descriptor()
        for item in d["items"]:
            self.assertIn("prompt_sha256", item)
            self.assertNotIn("prompt", item)
            self.assertNotIn("text", item)


class TestOrthographyAggregate(unittest.TestCase):
    def test_aggregate_counts_and_tripwires(self):
        # Two clean Hawaiian samples + one with a wrong-okina substitution
        # and one with combining macron (NFD).
        per_sample = {
            "sample_0": {
                "is_nfc": True,
                "okina": 1,
                "wrong_okina": 0,
                "kahako": 2,
                "diacritic_density": 3,
                "diacritic_density_bin": "medium",
                "combining_macron": 0,
                "len": 20,
            },
            "sample_1": {
                "is_nfc": True,
                "okina": 0,
                "wrong_okina": 1,
                "kahako": 0,
                "diacritic_density": 0,
                "diacritic_density_bin": "none",
                "combining_macron": 0,
                "len": 10,
            },
            "sample_2": {
                "is_nfc": False,
                "okina": 1,
                "wrong_okina": 0,
                "kahako": 0,
                "diacritic_density": 1,
                "diacritic_density_bin": "low",
                "combining_macron": 1,
                "len": 5,
            },
        }
        suite = {"suite_id": "x", "suite_sha256": "deadbeef", "items": []}
        agg = ev._orthography_aggregate(per_sample, suite)
        self.assertEqual(agg["n"], 3)
        self.assertEqual(agg["okina_total"], 2)
        self.assertEqual(agg["wrong_okina_total"], 1)
        self.assertEqual(agg["kahako_total"], 2)
        self.assertEqual(agg["combining_macron_total"], 1)
        self.assertEqual(agg["nfc_failures"], 1)
        self.assertEqual(agg["kahako_collapse_on_high_diacritic"], 0)

        tw = ev._tripwires(agg, suite, generation_count=3)
        self.assertTrue(tw["wrong_okina_nonzero"])
        self.assertEqual(tw["nfc_failures"], 1)
        self.assertTrue(tw["combining_macron_nonzero"])
        self.assertEqual(tw["generation_count"], 3)
        self.assertEqual(tw["prompt_suite_sha256"], "deadbeef")

    def test_kahako_collapse_on_high_diacritic_prompt(self):
        # High-density prompt → generation with zero kahakō should
        # register as a kahakō-collapse tripwire.
        per_sample = {
            "sample_0": {
                "is_nfc": True,
                "okina": 0,
                "wrong_okina": 0,
                "kahako": 0,
                "diacritic_density": 0,
                "diacritic_density_bin": "none",
                "combining_macron": 0,
                "len": 5,
            },
        }
        suite = {
            "suite_id": "x",
            "suite_sha256": "abc",
            "items": [
                {
                    "id": "haw_high_1",
                    "prompt_sha256": "p",
                    "prompt_len_chars": 50,
                    "prompt_diacritics": 12,
                    "diacritic_density_bin": "high",
                }
            ],
        }
        agg = ev._orthography_aggregate(per_sample, suite)
        self.assertEqual(agg["kahako_collapse_on_high_diacritic"], 1)


class TestSchemaVersion(unittest.TestCase):
    def test_schema_version_is_v2(self):
        self.assertEqual(ev.EVAL_SCHEMA_VERSION, "stage0_eval.v2")


if __name__ == "__main__":
    unittest.main()
