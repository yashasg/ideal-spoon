import itertools
import json
from pathlib import Path
import unittest

import llm_hawaii.metrics as metrics


class TestMetrics(unittest.TestCase):
    def test_is_nfc_true_and_false(self):
        self.assertTrue(metrics.is_nfc("hālau"))            # precomposed ā
        self.assertFalse(metrics.is_nfc("ha\u0304lau"))     # a + combining macron

    def test_okina_counts(self):
        text = f"He {metrics.OKINA}ōlelo Hawai{metrics.OKINA}i."
        self.assertEqual(metrics.count_okina(text), 2)

    def test_wrong_okina_counts(self):
        text = "He 'olelo Hawai‘i Hawai’i Hawaiʼi."
        self.assertEqual(metrics.count_wrong_okina(text), 4)

    def test_kahako_counts(self):
        text = "ā ē ī ō ū Ā Ē Ī Ō Ū"
        self.assertEqual(metrics.count_kahako(text), 10)
    def test_hawaiian_diacritic_count(self):
        text = f"He {metrics.OKINA}ōlelo Hawai{metrics.OKINA}i: ā ē"
        self.assertEqual(metrics.count_hawaiian_diacritics(text), 5)  # 2 okina + 3 kahakō

    def test_diacritic_density_bin_boundaries(self):
        self.assertEqual(metrics.diacritic_density_bin(0), "none")
        self.assertEqual(metrics.diacritic_density_bin(1), "low")
        self.assertEqual(metrics.diacritic_density_bin(2), "low")
        self.assertEqual(metrics.diacritic_density_bin(3), "medium")
        self.assertEqual(metrics.diacritic_density_bin(5), "medium")
        self.assertEqual(metrics.diacritic_density_bin(6), "high")

    def test_count_combining_macron(self):
        text = f"ha{metrics.COMBINING_MACRON}lau ma{metrics.COMBINING_MACRON}ka"
        self.assertEqual(metrics.count_combining_macron(text), 2)
    def test_okina_survival_rate(self):
        ref = f"He {metrics.OKINA}ōlelo Hawai{metrics.OKINA}i."
        gen_same = ref
        gen_less = f"He ōlelo Hawaii."
        gen_more = f"He {metrics.OKINA}{metrics.OKINA}ōlelo Hawai{metrics.OKINA}i."
        self.assertEqual(metrics.okina_survival_rate(gen_same, ref), 1.0)
        self.assertEqual(metrics.okina_survival_rate(gen_less, ref), 0.0)
        self.assertEqual(metrics.okina_survival_rate(gen_more, ref), 1.0)  # capped at 1.0
        self.assertEqual(metrics.okina_survival_rate("anything", "no okina here"), 1.0)

    def test_kahako_retention_rate(self):
        ref = "hālau ʻōlelo"
        self.assertEqual(metrics.kahako_retention_rate("halau olelo", ref), 0.0)
        self.assertEqual(metrics.kahako_retention_rate("hālau ʻōlelo", ref), 1.0)
        self.assertEqual(metrics.kahako_retention_rate("hāālau ʻōōlelo", ref), 1.0)  # capped
        self.assertEqual(metrics.kahako_retention_rate("anything", "plain"), 1.0)

    def test_orthography_report_shape_and_values(self):
        text = "ha\u0304lau 'ōlelo"
        rep = metrics.orthography_report(text)
        expected_keys = {
            "is_nfc",
            "okina",
            "wrong_okina",
            "kahako",
            "diacritic_density",
            "diacritic_density_bin",
            "combining_macron",
            "len",
        }
        self.assertEqual(set(rep.keys()), expected_keys)
        self.assertFalse(rep["is_nfc"])
        self.assertEqual(rep["combining_macron"], 1)
        self.assertEqual(rep["wrong_okina"], 1)  # apostrophe '
        self.assertEqual(rep["len"], len(text))

    def test_metrics_over_dev_jsonl(self):
        repo_root = Path(__file__).resolve().parents[2]
        dev_path = repo_root / "data" / "evals" / "fineweb2_haw" / "dev.jsonl"
        self.assertTrue(dev_path.exists(), f"Missing eval file: {dev_path}")

        totals = {
            "rows": 0,
            "text_rows": 0,
            "wrong_okina": 0,
            "combining_macron": 0,
            "non_nfc_rows": 0,
        }

        with dev_path.open("r", encoding="utf-8") as f:
            for line in itertools.islice(f, 300):  # keep test fast
                row = json.loads(line)
                totals["rows"] += 1
                text = row.get("text", "")
                if not text:
                    continue
                totals["text_rows"] += 1
                rep = metrics.orthography_report(text)
                totals["wrong_okina"] += rep["wrong_okina"]
                totals["combining_macron"] += rep["combining_macron"]
                totals["non_nfc_rows"] += int(not rep["is_nfc"])

        self.assertGreater(totals["rows"], 0)
        self.assertGreater(totals["text_rows"], 0)
        self.assertGreaterEqual(totals["wrong_okina"], 0)
        self.assertGreaterEqual(totals["combining_macron"], 0)
        self.assertGreaterEqual(totals["non_nfc_rows"], 0)


if __name__ == "__main__":
    unittest.main()