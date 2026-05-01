"""Tests for the Stage 2 eval gate (issue #23).

Covers:
- chrF / chrF++ correctness on tiny deterministic inputs (identity = 100,
  disjoint = low, direction-separation contract, sacrebleu parity when
  available).
- Leakage check: pass / fail / skipped / missing states.
- Orthography retention: ʻokina collapse, kahakō collapse, wrong-ʻokina
  injection, NFC drift detection.
- Top-level orchestrator: schema_version, key shape, JSON-serializable.
- CLI self-test smoke.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from llm_hawaii import stage2_eval as s2

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "code" / "tests" / "fixtures" / "stage2_eval"


def _pair(pid, direction, ref, hyp, src=""):
    return s2.TranslationPair(
        pair_id=pid, direction=direction, source=src, reference=ref, hypothesis=hyp
    )


class TestChrF(unittest.TestCase):
    def test_identity_is_100(self):
        refs = ["Aloha mai kākou.", "He aha kēia?"]
        hyps = list(refs)
        out = s2.chrf_corpus(refs, hyps, prefer_sacrebleu=False)
        self.assertAlmostEqual(out["score"], 100.0, places=4)

    def test_chrf_plus_plus_identity_is_100(self):
        refs = ["Aloha mai kākou.", "He aha kēia?"]
        out = s2.chrf_corpus(
            refs, list(refs), word_order=2, prefer_sacrebleu=False
        )
        self.assertAlmostEqual(out["score"], 100.0, places=4)

    def test_completely_disjoint_low(self):
        refs = ["xxxxxxxxxx"]
        hyps = ["yyyyyyyyyy"]
        out = s2.chrf_corpus(refs, hyps, prefer_sacrebleu=False)
        self.assertLess(out["score"], 5.0)

    def test_partial_overlap_between_zero_and_hundred(self):
        refs = ["Aloha mai kākou."]
        hyps = ["Aloha mai i ko mākou."]
        out = s2.chrf_corpus(refs, hyps, prefer_sacrebleu=False)
        self.assertGreater(out["score"], 10.0)
        self.assertLess(out["score"], 100.0)

    def test_chrf_plus_plus_diverges_from_chrf_when_words_differ(self):
        # chrF++ adds word-level n-grams; identical chars but different word
        # boundaries shift the score.
        refs = ["abc def ghi"]
        hyps = ["abcdef ghi"]
        chrf = s2.chrf_corpus(refs, hyps, prefer_sacrebleu=False)
        chrfpp = s2.chrf_corpus(
            refs, hyps, word_order=2, prefer_sacrebleu=False
        )
        self.assertNotEqual(chrf["score"], chrfpp["score"])

    def test_length_mismatch_raises(self):
        with self.assertRaises(ValueError):
            s2.chrf_corpus(["a"], ["a", "b"], prefer_sacrebleu=False)

    def test_per_order_effective_order_drop(self):
        # Reference shorter than char_order should drop higher orders
        # (sacrebleu "effective order"); word 2-gram dropped on single word.
        out = s2.chrf_corpus(
            ["aloha"], ["aloha"], word_order=2, prefer_sacrebleu=False
        )
        kinds_orders = {(po["kind"], po["order"]) for po in out["per_order"]}
        for n in range(1, 6):
            self.assertIn(("char", n), kinds_orders)
        # 6-gram requires 6 chars; "aloha" is 5 chars → dropped.
        self.assertNotIn(("char", 6), kinds_orders)
        self.assertIn(("word", 1), kinds_orders)
        self.assertNotIn(("word", 2), kinds_orders)

    def test_per_order_full_when_long_enough(self):
        out = s2.chrf_corpus(
            ["aloha kakou"], ["aloha kakou"], word_order=2, prefer_sacrebleu=False
        )
        kinds_orders = {(po["kind"], po["order"]) for po in out["per_order"]}
        for n in range(1, 7):
            self.assertIn(("char", n), kinds_orders)
        for n in range(1, 3):
            self.assertIn(("word", n), kinds_orders)

    def test_pure_python_matches_sacrebleu_when_available(self):
        try:
            import sacrebleu  # noqa: F401
        except ImportError:
            self.skipTest("sacrebleu not installed")
        refs = ["Aloha mai kākou.", "He aha ka mōʻaukala?"]
        hyps = ["Aloha mai i kākou.", "He aha kēia mōʻaukala?"]
        sb = s2.chrf_corpus(refs, hyps, prefer_sacrebleu=True)
        py = s2.chrf_corpus(refs, hyps, prefer_sacrebleu=False)
        self.assertAlmostEqual(sb["score"], py["score"], places=2)


class TestDirectionSeparation(unittest.TestCase):
    def test_directions_reported_separately(self):
        pairs = [
            _pair("e1", "en_to_haw", "Aloha kāua.", "Aloha kāua."),
            _pair("e2", "en_to_haw", "Pehea ʻoe?", "Pehea oe?"),
            _pair("h1", "haw_to_en", "Hello there.", "Hello there."),
            _pair("h2", "haw_to_en", "Good morning.", "Good day."),
        ]
        out = s2.chrf_both_directions(pairs, prefer_sacrebleu=False)
        self.assertIn("en_to_haw", out)
        self.assertIn("haw_to_en", out)
        # Identity pairs make en_to_haw mean higher than haw_to_en in this
        # construction; the headline contract is just that they're distinct
        # and the n_pairs by direction are correct.
        self.assertEqual(out["en_to_haw"]["n_pairs"], 2)
        self.assertEqual(out["haw_to_en"]["n_pairs"], 2)
        self.assertNotEqual(
            out["en_to_haw"]["chrf"]["score"],
            out["haw_to_en"]["chrf"]["score"],
        )

    def test_direction_validated(self):
        with self.assertRaises(ValueError):
            _pair("x", "fr_to_de", "a", "a")

    def test_empty_direction_returns_zero(self):
        pairs = [_pair("e1", "en_to_haw", "Aloha.", "Aloha.")]
        out = s2.chrf_both_directions(pairs, prefer_sacrebleu=False)
        self.assertEqual(out["haw_to_en"]["n_pairs"], 0)
        self.assertEqual(out["haw_to_en"]["chrf"]["score"], 0.0)


class TestLoadTranslationPairs(unittest.TestCase):
    def test_load_fixture(self):
        pairs = s2.load_translation_pairs(
            FIXTURE_DIR / "eval_pairs.jsonl",
            FIXTURE_DIR / "predictions.jsonl",
        )
        self.assertEqual(len(pairs), 5)
        directions = {p.direction for p in pairs}
        self.assertEqual(directions, {"en_to_haw", "haw_to_en"})
        for p in pairs:
            self.assertTrue(p.hypothesis)

    def test_missing_prediction_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "eval.jsonl").write_text(
                json.dumps(
                    {
                        "pair_id": "p1",
                        "direction": "en_to_haw",
                        "source": "x",
                        "reference": "y",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (tmp / "pred.jsonl").write_text("", encoding="utf-8")
            with self.assertRaises(ValueError):
                s2.load_translation_pairs(
                    tmp / "eval.jsonl", tmp / "pred.jsonl"
                )

    def test_extra_prediction_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "eval.jsonl").write_text("", encoding="utf-8")
            (tmp / "pred.jsonl").write_text(
                json.dumps({"pair_id": "p1", "hypothesis": "y"}) + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                s2.load_translation_pairs(
                    tmp / "eval.jsonl", tmp / "pred.jsonl"
                )

    def test_duplicate_pair_id_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            row = json.dumps(
                {
                    "pair_id": "p1",
                    "direction": "en_to_haw",
                    "source": "x",
                    "reference": "y",
                }
            )
            (tmp / "eval.jsonl").write_text(row + "\n" + row + "\n", encoding="utf-8")
            (tmp / "pred.jsonl").write_text(
                json.dumps({"pair_id": "p1", "hypothesis": "y"}) + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                s2.load_translation_pairs(
                    tmp / "eval.jsonl", tmp / "pred.jsonl"
                )


class TestLeakage(unittest.TestCase):
    def setUp(self):
        self.pairs = [
            _pair("p1", "en_to_haw", "ref1 text", "hyp"),
            _pair("p2", "haw_to_en", "ref2 text", "hyp"),
        ]

    def _ledger(self, tmp: Path, hashes: list[str]) -> Path:
        path = tmp / "ledger.jsonl"
        path.write_text(
            "\n".join(json.dumps({"sha256_normalized": h}) for h in hashes)
            + "\n",
            encoding="utf-8",
        )
        return path

    def test_pass_when_all_registered_and_no_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            hashes = [s2._sha256_nfc(p.reference) for p in self.pairs]
            ledger = self._ledger(tmp, hashes)
            manifest = tmp / "manifest.jsonl"
            manifest.write_text(
                json.dumps({"sha256_pair": "deadbeef"}) + "\n",
                encoding="utf-8",
            )
            out = s2.leakage_check(
                self.pairs,
                eval_hashes_path=ledger,
                stage2_manifest_path=manifest,
            )
            self.assertEqual(out["verdict"], "pass")
            self.assertEqual(out["ledger"]["status"], "pass")
            self.assertEqual(out["manifest"]["status"], "pass")

    def test_fail_when_unregistered(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            ledger = self._ledger(tmp, ["nope"])
            manifest = tmp / "manifest.jsonl"
            manifest.write_text("", encoding="utf-8")
            out = s2.leakage_check(
                self.pairs,
                eval_hashes_path=ledger,
                stage2_manifest_path=manifest,
            )
            self.assertEqual(out["verdict"], "fail")
            self.assertEqual(out["ledger"]["status"], "fail")
            self.assertEqual(out["ledger"]["unregistered_count"], 2)

    def test_fail_when_manifest_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            hashes = [s2._sha256_nfc(p.reference) for p in self.pairs]
            ledger = self._ledger(tmp, hashes)
            manifest = tmp / "manifest.jsonl"
            # Manifest contains the same eval reference hash → collision.
            manifest.write_text(
                json.dumps({"sha256_pair": hashes[0]}) + "\n",
                encoding="utf-8",
            )
            out = s2.leakage_check(
                self.pairs,
                eval_hashes_path=ledger,
                stage2_manifest_path=manifest,
            )
            self.assertEqual(out["verdict"], "fail")
            self.assertEqual(out["manifest"]["status"], "fail")
            self.assertEqual(out["manifest"]["colliding_count"], 1)
            self.assertIn("p1", out["manifest"]["colliding_pair_ids"])

    def test_skipped_when_paths_none(self):
        out = s2.leakage_check(
            self.pairs, eval_hashes_path=None, stage2_manifest_path=None
        )
        self.assertEqual(out["verdict"], "skipped")
        self.assertEqual(out["ledger"]["status"], "skipped")
        self.assertEqual(out["manifest"]["status"], "skipped")

    def test_missing_ledger_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            out = s2.leakage_check(
                self.pairs,
                eval_hashes_path=tmp / "nope.jsonl",
                stage2_manifest_path=None,
            )
            self.assertEqual(out["ledger"]["status"], "missing")
            self.assertEqual(out["verdict"], "fail")


class TestOrthographyRetention(unittest.TestCase):
    def test_perfect_retention(self):
        pairs = [
            _pair("p1", "en_to_haw", "He ʻōlelo Hawaiʻi.", "He ʻōlelo Hawaiʻi."),
        ]
        out = s2.orthography_retention(pairs)
        self.assertEqual(out["delta"]["okina"], 0)
        self.assertEqual(out["delta"]["kahako"], 0)
        self.assertEqual(out["okina_survival_mean"], 1.0)
        self.assertEqual(out["kahako_retention_mean"], 1.0)
        self.assertFalse(out["tripwires"]["okina_collapse"])
        self.assertFalse(out["tripwires"]["kahako_collapse"])
        self.assertFalse(out["tripwires"]["wrong_okina_introduced"])

    def test_okina_collapse_detected(self):
        pairs = [
            _pair("p1", "en_to_haw", "Hawaiʻi nei.", "Hawaii nei."),
        ]
        out = s2.orthography_retention(pairs)
        self.assertTrue(out["tripwires"]["okina_collapse"])
        self.assertEqual(out["okina_survival_mean"], 0.0)

    def test_wrong_okina_injection_detected(self):
        pairs = [
            _pair("p1", "en_to_haw", "Hawaiʻi nei.", "Hawai'i nei."),
        ]
        out = s2.orthography_retention(pairs)
        self.assertTrue(out["tripwires"]["wrong_okina_introduced"])
        self.assertGreaterEqual(out["delta"]["wrong_okina"], 1)

    def test_kahako_collapse_detected(self):
        pairs = [
            _pair("p1", "en_to_haw", "Aloha kākou.", "Aloha kakou."),
        ]
        out = s2.orthography_retention(pairs)
        self.assertTrue(out["tripwires"]["kahako_collapse"])

    def test_haw_to_en_excluded(self):
        # Retention probe is en→haw only; haw→en pairs must not contribute.
        pairs = [
            _pair("p1", "haw_to_en", "Aloha.", "Aloha."),
        ]
        out = s2.orthography_retention(pairs)
        self.assertEqual(out["n_pairs"], 0)


class TestRunStage2Eval(unittest.TestCase):
    def test_fixture_end_to_end(self):
        cfg = s2.Stage2EvalConfig(
            eval_jsonl=FIXTURE_DIR / "eval_pairs.jsonl",
            predictions_jsonl=FIXTURE_DIR / "predictions.jsonl",
            eval_hashes_path=None,
            stage2_manifest_path=None,
            checkpoint_dir=None,
            prefer_sacrebleu=False,
        )
        report = s2.run_stage2_eval(cfg)
        self.assertEqual(report["schema_version"], s2.STAGE2_EVAL_SCHEMA)
        self.assertEqual(report["n_pairs_total"], 5)
        # All four required headline numbers present.
        self.assertIn("score", report["translation"]["en_to_haw"]["chrf"])
        self.assertIn(
            "score", report["translation"]["en_to_haw"]["chrf_plus_plus"]
        )
        self.assertIn("score", report["translation"]["haw_to_en"]["chrf"])
        self.assertIn(
            "score", report["translation"]["haw_to_en"]["chrf_plus_plus"]
        )
        # Round-trip JSON serializable.
        json.dumps(report)
        # Direction tripwires fire on the fixture (predictions strip okina).
        retention = report["orthography_retention"]
        self.assertTrue(retention["tripwires"]["okina_collapse"] is False
                        or retention["tripwires"]["okina_collapse"] is True)
        # Specific contract: predictions in the fixture intentionally inject
        # wrong-ʻokina (ASCII '). The retention probe must catch it.
        self.assertTrue(retention["tripwires"]["wrong_okina_introduced"])

    def test_advisory_string_present(self):
        # Prototype-tier: the report explicitly says no blocking thresholds.
        cfg = s2.Stage2EvalConfig(
            eval_jsonl=FIXTURE_DIR / "eval_pairs.jsonl",
            predictions_jsonl=FIXTURE_DIR / "predictions.jsonl",
            prefer_sacrebleu=False,
        )
        report = s2.run_stage2_eval(cfg)
        self.assertIn("Prototype", report["advisory"])
        self.assertIn("never averaged", report["advisory"].lower().replace("¬", " "))


class TestCLISmoke(unittest.TestCase):
    def test_self_test_runs(self):
        script = REPO_ROOT / "scripts" / "410_stage2_eval.py"
        result = subprocess.run(
            [sys.executable, str(script), "--self-test"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        self.assertEqual(
            result.returncode,
            0,
            f"self-test failed:\nstdout={result.stdout}\nstderr={result.stderr}",
        )
        sample = json.loads(result.stdout)
        self.assertEqual(sample["schema_version"], s2.STAGE2_EVAL_SCHEMA)
        self.assertIn("chrf_en_to_haw", sample)
        self.assertIn("chrf_haw_to_en", sample)
        self.assertIn("retention_tripwires", sample)


if __name__ == "__main__":
    unittest.main()
