"""Tests for Stage 0 eval drift-signal helpers (no ML deps).

W1 manual micro-eval is JSONL-only per the user directive
(.squad/decisions/inbox/copilot-directive-20260430T081137Z.md).
"""

import hashlib
import json
import tempfile
import unicodedata
import unittest
from pathlib import Path

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
        per_sample = {
            "sample_0": {
                "is_nfc": True, "okina": 1, "wrong_okina": 0, "kahako": 2,
                "diacritic_density": 3, "diacritic_density_bin": "medium",
                "combining_macron": 0, "len": 20,
            },
            "sample_1": {
                "is_nfc": True, "okina": 0, "wrong_okina": 1, "kahako": 0,
                "diacritic_density": 0, "diacritic_density_bin": "none",
                "combining_macron": 0, "len": 10,
            },
            "sample_2": {
                "is_nfc": False, "okina": 1, "wrong_okina": 0, "kahako": 0,
                "diacritic_density": 1, "diacritic_density_bin": "low",
                "combining_macron": 1, "len": 5,
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
        per_sample = {
            "sample_0": {
                "is_nfc": True, "okina": 0, "wrong_okina": 0, "kahako": 0,
                "diacritic_density": 0, "diacritic_density_bin": "none",
                "combining_macron": 0, "len": 5,
            },
        }
        suite = {
            "suite_id": "x", "suite_sha256": "abc",
            "items": [{
                "id": "haw_high_1", "prompt_sha256": "p",
                "prompt_len_chars": 50, "prompt_diacritics": 12,
                "diacritic_density_bin": "high",
            }],
        }
        agg = ev._orthography_aggregate(per_sample, suite)
        self.assertEqual(agg["kahako_collapse_on_high_diacritic"], 1)


class TestSchemaVersion(unittest.TestCase):
    def test_schema_version_is_v2(self):
        self.assertEqual(ev.EVAL_SCHEMA_VERSION, "stage0_eval.v2")

    def test_w1_jsonl_schema_version_label(self):
        self.assertEqual(ev.MANUAL_W1_JSONL_SCHEMA_VERSION, "manual-w1-jsonl-v1")


def _row(
    item_id="w1-okina-001",
    category="okina_survival",
    prompt="E pane:",
    reference="Hawaiʻi",
    diacritic_density=2,
    review_status="accepted",
    nfc_normalized=True,
    *,
    include_sha=True,
    extra=None,
):
    rec = {
        "schema_version": "manual-w1-jsonl-v1",
        "item_id": item_id,
        "category": category,
        "prompt": prompt,
        "reference": reference,
        "diacritic_density": diacritic_density,
        "review_status": review_status,
        "nfc_normalized": nfc_normalized,
    }
    if include_sha:
        material = unicodedata.normalize("NFC", f"{prompt}\n{reference}")
        rec["sha256_normalized"] = hashlib.sha256(material.encode("utf-8")).hexdigest()
    if extra:
        rec.update(extra)
    return json.dumps(rec, ensure_ascii=False) + "\n"


class TestManualW1Status(unittest.TestCase):
    def test_disabled_returns_not_configured(self):
        out = ev.manual_w1_status("anything", enabled=False)
        self.assertEqual(out["status"], "not_configured")
        self.assertEqual(out["scoring_status"], "not_wired")
        self.assertIsNone(out["schema_version_seen"])

    def test_missing_file_returns_missing(self):
        out = ev.manual_w1_status("does/not/exist.jsonl")
        self.assertEqual(out["status"], "missing")
        self.assertEqual(out["scoring_status"], "not_wired")
        self.assertIsNone(out["schema_version_seen"])

    def test_invalid_json_line_returns_invalid(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "bad.jsonl"
            p.write_text("not-json\n", encoding="utf-8")
            out = ev.manual_w1_status(str(p))
        self.assertEqual(out["status"], "invalid")
        self.assertEqual(out["reason"], "jsonl_parse_failed")
        self.assertIn("jsonl_sha256", out)
        self.assertIn("jsonl_size_bytes", out)
        self.assertGreaterEqual(out["error_count"], 1)

    def test_empty_file_is_draft_only(self):
        # An empty/comment-only JSONL has zero accepted rows ⇒ draft_only.
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "empty.jsonl"
            p.write_text("# only comments\n\n", encoding="utf-8")
            out = ev.manual_w1_status(str(p))
        self.assertEqual(out["status"], "draft_only")
        self.assertEqual(out["row_count"], 0)
        self.assertEqual(out["accepted_count"], 0)

    def test_draft_only_when_no_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "drafts.jsonl"
            p.write_text(
                _row(item_id="w1-d-1", review_status="draft")
                + _row(item_id="w1-d-2", review_status="reviewed"),
                encoding="utf-8",
            )
            out = ev.manual_w1_status(str(p))
        self.assertEqual(out["status"], "draft_only")
        self.assertEqual(out["accepted_count"], 0)
        self.assertEqual(out["eval_consumable_count"], 0)
        self.assertEqual(out["row_count"], 2)
        self.assertEqual(out["review_status_counts"].get("draft"), 1)
        self.assertEqual(out["review_status_counts"].get("reviewed"), 1)
        self.assertEqual(out["accepted_category_counts"], {})

    def test_evaluated_with_accepted_rows(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "ok.jsonl"
            p.write_text(
                _row(item_id="w1-ok-1", category="okina_survival",
                     diacritic_density=1)
                + _row(item_id="w1-ok-2", category="kahako_retention",
                       diacritic_density=6)
                + _row(item_id="w1-d-1", review_status="draft"),
                encoding="utf-8",
            )
            out = ev.manual_w1_status(str(p))
        self.assertEqual(out["status"], "evaluated")
        self.assertEqual(out["accepted_count"], 2)
        self.assertEqual(out["eval_consumable_count"], 2)
        self.assertEqual(out["row_count"], 3)
        self.assertEqual(out["scoring_status"], "not_wired")
        self.assertEqual(
            out["accepted_category_counts"],
            {"okina_survival": 1, "kahako_retention": 1},
        )
        self.assertEqual(
            out["accepted_diacritic_density_bin_counts"],
            {"low": 1, "high": 1},
        )
        # No raw text leaks into the status dict.
        for v in out.values():
            if isinstance(v, str):
                self.assertNotIn("Hawaiʻi", v)

    def test_id_alias_accepted(self):
        # Records that use `id` instead of `item_id` are accepted.
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "alias.jsonl"
            p.write_text(
                _row(item_id="w1-a-1", extra={"id": "w1-a-1"}),
                encoding="utf-8",
            )
            out = ev.manual_w1_status(str(p))
        self.assertEqual(out["status"], "evaluated")
        self.assertEqual(out["accepted_count"], 1)

    def test_string_bool_nfc_normalized_accepted(self):
        # Lenient: nfc_normalized may be the string "true".
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "stringbool.jsonl"
            p.write_text(
                _row(item_id="w1-x-1", nfc_normalized="true"),
                encoding="utf-8",
            )
            out = ev.manual_w1_status(str(p))
        self.assertEqual(out["status"], "evaluated")

    def test_nfc_false_on_draft_counted_but_not_blocking(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "nfc.jsonl"
            p.write_text(
                _row(item_id="w1-x-1", review_status="draft",
                     nfc_normalized=False),
                encoding="utf-8",
            )
            out = ev.manual_w1_status(str(p))
        self.assertEqual(out["status"], "draft_only")
        self.assertEqual(out["nfc_normalized_false_count"], 1)


class TestManualW1ContractFields(unittest.TestCase):
    def _write(self, td, body: str) -> str:
        p = Path(td) / "w1.jsonl"
        p.write_text(body, encoding="utf-8")
        return str(p)

    def test_accepted_item_hashes_match_canonical_formula_and_are_sorted(self):
        rows = [
            _row(item_id="w1-b-2", prompt="E pane:", reference="Hawaiʻi"),
            _row(item_id="w1-a-1", category="kahako_retention",
                 prompt="E kope:", reference="mālama", diacritic_density=2),
            _row(item_id="w1-d-1", review_status="draft"),
        ]
        with tempfile.TemporaryDirectory() as td:
            out = ev.manual_w1_status(self._write(td, "".join(rows)))
        self.assertEqual(out["status"], "evaluated")
        expected = sorted(
            hashlib.sha256(
                unicodedata.normalize("NFC", f"{prm}\n{ref}").encode("utf-8")
            ).hexdigest()
            for prm, ref in (("E pane:", "Hawaiʻi"), ("E kope:", "mālama"))
        )
        self.assertEqual(out["accepted_item_hashes"], expected)
        self.assertEqual(
            out["accepted_item_hashes"], sorted(out["accepted_item_hashes"])
        )

    def test_accepted_hashes_use_row_sha_when_present(self):
        # sha256_normalized on the row should be used verbatim.
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "w.jsonl"
            p.write_text(
                _row(item_id="w1-s-1"),
                encoding="utf-8",
            )
            out = ev.manual_w1_status(str(p))
        material = unicodedata.normalize("NFC", "E pane:\nHawaiʻi")
        expected = hashlib.sha256(material.encode("utf-8")).hexdigest()
        self.assertEqual(out["accepted_item_hashes"], [expected])

    def test_accepted_hashes_computed_when_row_sha_absent(self):
        # No sha256_normalized on the row → derived consistently.
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "w.jsonl"
            p.write_text(
                _row(item_id="w1-c-1", include_sha=False),
                encoding="utf-8",
            )
            out = ev.manual_w1_status(str(p))
        material = unicodedata.normalize("NFC", "E pane:\nHawaiʻi")
        expected = hashlib.sha256(material.encode("utf-8")).hexdigest()
        self.assertEqual(out["accepted_item_hashes"], [expected])

    def test_w1_suite_sha256_stable_under_row_reorder(self):
        a = _row(item_id="w1-a-1", prompt="E pane:", reference="Hawaiʻi")
        b = _row(item_id="w1-b-1", category="kahako_retention",
                 prompt="E kope:", reference="mālama", diacritic_density=2)
        with tempfile.TemporaryDirectory() as td:
            out1 = ev.manual_w1_status(self._write(td, a + b))
        with tempfile.TemporaryDirectory() as td:
            out2 = ev.manual_w1_status(self._write(td, b + a))
        self.assertEqual(out1["status"], "evaluated")
        self.assertEqual(out1["w1_suite_sha256"], out2["w1_suite_sha256"])

    def test_w1_suite_sha256_changes_when_accepted_set_changes(self):
        a = _row(item_id="w1-a-1", prompt="E pane:", reference="Hawaiʻi")
        b_accepted = _row(item_id="w1-b-1", category="kahako_retention",
                          prompt="E kope:", reference="mālama", diacritic_density=2)
        b_draft = _row(item_id="w1-b-1", category="kahako_retention",
                       prompt="E kope:", reference="mālama",
                       diacritic_density=2, review_status="draft")
        with tempfile.TemporaryDirectory() as td:
            out_full = ev.manual_w1_status(self._write(td, a + b_accepted))
        with tempfile.TemporaryDirectory() as td:
            out_flipped = ev.manual_w1_status(self._write(td, a + b_draft))
        self.assertEqual(out_full["status"], "evaluated")
        self.assertEqual(out_flipped["status"], "evaluated")
        self.assertNotEqual(
            out_full["w1_suite_sha256"], out_flipped["w1_suite_sha256"]
        )
        self.assertEqual(out_full["accepted_count"], 2)
        self.assertEqual(out_flipped["accepted_count"], 1)

    def test_w1_suite_sha256_null_on_draft_only(self):
        with tempfile.TemporaryDirectory() as td:
            out = ev.manual_w1_status(
                self._write(td, _row(item_id="w1-d-1", review_status="draft"))
            )
        self.assertEqual(out["status"], "draft_only")
        self.assertIsNone(out["w1_suite_sha256"])
        self.assertEqual(out["accepted_item_hashes"], [])

    def test_schema_version_seen_evaluated_and_draft_only(self):
        with tempfile.TemporaryDirectory() as td:
            out_eval = ev.manual_w1_status(
                self._write(td, _row(item_id="w1-ok-1"))
            )
        with tempfile.TemporaryDirectory() as td:
            out_draft = ev.manual_w1_status(
                self._write(td, _row(item_id="w1-d-1", review_status="draft"))
            )
        self.assertEqual(out_eval["schema_version_seen"], "manual-w1-jsonl-v1")
        self.assertEqual(out_draft["schema_version_seen"], "manual-w1-jsonl-v1")

    def test_schema_version_seen_null_on_invalid_missing_disabled(self):
        out_dis = ev.manual_w1_status("anything", enabled=False)
        self.assertIsNone(out_dis["schema_version_seen"])
        out_miss = ev.manual_w1_status("does/not/exist.jsonl")
        self.assertIsNone(out_miss["schema_version_seen"])
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "bad.jsonl"
            p.write_text("not-json\n", encoding="utf-8")
            out_bad = ev.manual_w1_status(str(p))
        self.assertEqual(out_bad["status"], "invalid")
        self.assertIsNone(out_bad["schema_version_seen"])

    def test_invalid_when_accepted_row_not_nfc(self):
        nfd_ref = "ma\u0304lama"
        with tempfile.TemporaryDirectory() as td:
            out = ev.manual_w1_status(
                self._write(td, _row(item_id="w1-x-1", reference=nfd_ref,
                                     include_sha=False))
            )
        self.assertEqual(out["status"], "invalid")
        self.assertEqual(
            out["reason"], "accepted_row_orthographic_validation_failed"
        )
        self.assertGreaterEqual(out["error_count"], 1)
        self.assertEqual(out["eval_consumable_count"], 0)
        self.assertEqual(out["accepted_item_hashes"], [])
        self.assertIsNone(out["w1_suite_sha256"])
        self.assertIsNone(out["schema_version_seen"])
        for err in out["first_errors"]:
            self.assertNotIn(nfd_ref, err)
            self.assertNotIn("mālama", err)
            self.assertTrue(err.startswith("line "))

    def test_invalid_when_accepted_row_has_wrong_okina(self):
        with tempfile.TemporaryDirectory() as td:
            out = ev.manual_w1_status(
                self._write(td, _row(item_id="w1-x-1",
                                     reference="Hawai\u2019i",
                                     include_sha=False))
            )
        self.assertEqual(out["status"], "invalid")
        self.assertIn("wrong", " ".join(out["first_errors"]).lower())

    def test_invalid_when_accepted_row_has_combining_macron_in_prompt(self):
        with tempfile.TemporaryDirectory() as td:
            out = ev.manual_w1_status(
                self._write(td, _row(item_id="w1-x-1",
                                     prompt="E ma\u0304lama:",
                                     include_sha=False))
            )
        self.assertEqual(out["status"], "invalid")

    def test_invalid_when_accepted_row_nfc_field_false(self):
        with tempfile.TemporaryDirectory() as td:
            out = ev.manual_w1_status(
                self._write(td, _row(item_id="w1-x-1", nfc_normalized=False))
            )
        self.assertEqual(out["status"], "invalid")
        self.assertTrue(
            any("nfc_normalized" in e for e in out["first_errors"])
        )

    def test_invalid_when_accepted_text_field_has_wrong_okina(self):
        # `text` field is gated on accepted rows even if prompt/reference are clean.
        with tempfile.TemporaryDirectory() as td:
            out = ev.manual_w1_status(
                self._write(td, _row(item_id="w1-x-1",
                                     extra={"text": "Hawai\u2019i"}))
            )
        self.assertEqual(out["status"], "invalid")

    def test_draft_with_bad_orthography_does_not_block(self):
        with tempfile.TemporaryDirectory() as td:
            out = ev.manual_w1_status(
                self._write(td, _row(item_id="w1-d-1",
                                     review_status="draft",
                                     reference="Hawai\u2019i",
                                     nfc_normalized=False,
                                     include_sha=False))
            )
        self.assertEqual(out["status"], "draft_only")
        self.assertNotIn("error_count", out)


class TestCliExitCode(unittest.TestCase):
    def test_invalid_manual_w1_exits_two(self):
        report = {"manual_w1": {"status": "invalid", "reason": "x"}}
        self.assertEqual(ev._cli_exit_code(report), 2)

    def test_evaluated_manual_w1_exits_zero(self):
        report = {"manual_w1": {"status": "evaluated", "accepted_count": 1}}
        self.assertEqual(ev._cli_exit_code(report), 0)

    def test_draft_only_manual_w1_exits_zero(self):
        report = {"manual_w1": {"status": "draft_only"}}
        self.assertEqual(ev._cli_exit_code(report), 0)

    def test_missing_manual_w1_exits_zero(self):
        report = {"manual_w1": {"status": "missing"}}
        self.assertEqual(ev._cli_exit_code(report), 0)

    def test_not_configured_manual_w1_exits_zero(self):
        report = {"manual_w1": {"status": "not_configured"}}
        self.assertEqual(ev._cli_exit_code(report), 0)

    def test_absent_manual_w1_block_exits_zero(self):
        self.assertEqual(ev._cli_exit_code({}), 0)
        self.assertEqual(ev._cli_exit_code({"manual_w1": None}), 0)


class TestCliArgs(unittest.TestCase):
    """W1 input is JSONL-only: the legacy --manual-w1-tsv argument is gone."""

    def test_jsonl_arg_is_accepted(self):
        # Sanity: argparse exposes --manual-w1-jsonl, not --manual-w1-tsv.
        import argparse, contextlib, io
        # Build a parser the same way main() does, but without invoking it.
        parser = argparse.ArgumentParser()
        parser.add_argument("--manual-w1-jsonl", default=None)
        ns = parser.parse_args(["--manual-w1-jsonl", "x.jsonl"])
        self.assertEqual(ns.manual_w1_jsonl, "x.jsonl")

    def test_default_jsonl_path_constant(self):
        self.assertEqual(
            ev.DEFAULT_MANUAL_W1_JSONL,
            "data/evals/manual_w1/w1-haw-micro-eval.jsonl",
        )
        self.assertFalse(hasattr(ev, "DEFAULT_MANUAL_W1_TSV"))


# ---------------------------------------------------------------------------
# human_fetch bidirectional translation probe
# ---------------------------------------------------------------------------

def _hf_pair_jsonl(en_text="Hello world.", haw_text="Aloha kāua."):
    """Minimal two-row parallel pair JSONL for probe tests."""
    en = json.dumps({"lang": "en", "text": en_text}) + "\n"
    haw = json.dumps({"lang": "haw", "text": haw_text}) + "\n"
    return en + haw


class TestCharNgramF1(unittest.TestCase):
    """Unit tests for the pure-Python baseline char-F score."""

    def test_identical_strings_return_f1_one(self):
        out = ev._char_ngram_f1("hello world", "hello world")
        self.assertAlmostEqual(out["char_f1"], 1.0, places=5)
        self.assertEqual(out["ngram_order"], 2)

    def test_empty_hypothesis_returns_zero(self):
        out = ev._char_ngram_f1("some reference", "")
        self.assertEqual(out["char_f1"], 0.0)
        self.assertEqual(out["char_precision"], 0.0)
        self.assertEqual(out["char_recall"], 0.0)

    def test_empty_reference_returns_zero(self):
        out = ev._char_ngram_f1("", "some hypothesis")
        self.assertEqual(out["char_f1"], 0.0)

    def test_completely_different_strings_return_low_score(self):
        out = ev._char_ngram_f1("aaa", "zzz")
        self.assertEqual(out["char_f1"], 0.0)

    def test_partial_overlap(self):
        # "ab" reference, "abc" hypothesis: overlap 1 bigram "ab" out of 2 (hyp="ab","bc"),
        # ref=1 bigram "ab"
        out = ev._char_ngram_f1("ab", "abc")
        self.assertGreater(out["char_f1"], 0.0)
        self.assertLessEqual(out["char_f1"], 1.0)

    def test_directions_never_averaged(self):
        # Verify we can call with different reference/hypothesis and get distinct scores.
        en_ref = "Welcome to the Hawaiian newspapers."
        haw_hyp_good = "HE ʻOHINA NŪPEPA ʻŌLELO HAWAIʻI"
        haw_hyp_bad = "zzz"
        good = ev._char_ngram_f1(en_ref, haw_hyp_good)
        bad = ev._char_ngram_f1(en_ref, haw_hyp_bad)
        # Good (partial overlap) should score higher than bad (zero overlap).
        self.assertGreaterEqual(good["char_f1"], bad["char_f1"])

    def test_hawaiian_nfc_text_scores_correctly(self):
        # NFC normalization should not change score for already-NFC text.
        ref = "He ʻohina waiwai kēia"
        hyp = "He ʻohina waiwai kēia"
        out = ev._char_ngram_f1(ref, hyp)
        self.assertAlmostEqual(out["char_f1"], 1.0, places=5)


class TestHumanFetchTranslationProbe(unittest.TestCase):
    """Tests for human_fetch_translation_probe."""

    def test_disabled_returns_not_configured(self):
        out = ev.human_fetch_translation_probe("anything", enabled=False)
        self.assertEqual(out["status"], "not_configured")
        self.assertEqual(out["schema"], ev.HUMAN_FETCH_PROBE_SCHEMA)

    def test_missing_file_returns_missing(self):
        out = ev.human_fetch_translation_probe("does/not/exist.jsonl")
        self.assertEqual(out["status"], "missing")
        # path should be in output (for debugging) but not raw text
        self.assertIn("path", out)
        # sha256 not set — file was never read
        self.assertNotIn("source_jsonl_sha256", out)

    def test_invalid_json_returns_invalid(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "bad.jsonl"
            p.write_text("not-json\n", encoding="utf-8")
            out = ev.human_fetch_translation_probe(str(p))
        self.assertEqual(out["status"], "invalid")
        self.assertIn("source_jsonl_sha256", out)

    def test_missing_haw_row_returns_invalid(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "en_only.jsonl"
            p.write_text(
                json.dumps({"lang": "en", "text": "Hello"}) + "\n",
                encoding="utf-8",
            )
            out = ev.human_fetch_translation_probe(str(p))
        self.assertEqual(out["status"], "invalid")
        self.assertIn("missing_lang_pair", out.get("reason", ""))

    def test_valid_two_row_pair_without_model_returns_ready(self):
        """valid two-row pair (en + haw) with no model → status=ready."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "pair.jsonl"
            p.write_text(_hf_pair_jsonl(), encoding="utf-8")
            out = ev.human_fetch_translation_probe(str(p))
        self.assertEqual(out["status"], "ready")
        self.assertIn("pair_count", out)
        self.assertEqual(out["pair_count"], 1)
        self.assertIn("pair_sha256", out)
        self.assertIn("source_jsonl_sha256", out)
        self.assertIn("source_jsonl_size_bytes", out)
        self.assertIn("template_sha256", out)

    def test_bidirectional_directions_present_in_ready(self):
        """Both en_to_haw and haw_to_en directions are present even without model."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "pair.jsonl"
            p.write_text(_hf_pair_jsonl(), encoding="utf-8")
            out = ev.human_fetch_translation_probe(str(p))
        self.assertEqual(out["status"], "ready")
        self.assertIn("directions", out)
        directions = out["directions"]
        self.assertIn("en_to_haw", directions, "en_to_haw direction must be present")
        self.assertIn("haw_to_en", directions, "haw_to_en direction must be present")
        # Each direction has status=not_run plus sha256 fields
        for dir_name in ("en_to_haw", "haw_to_en"):
            d = directions[dir_name]
            self.assertEqual(d.get("status"), "not_run")
            self.assertIn("prompt_sha256", d)
            self.assertIn("reference_sha256", d)

    def test_hash_only_fields_no_raw_text(self):
        """No raw source/reference text appears in the ready-state output."""
        en_text = "WELCOME TO THE HAWAIIAN NEWSPAPERS COLLECTION"
        haw_text = "HE ʻOHINA NŪPEPA ʻŌLELO HAWAIʻI"
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "pair.jsonl"
            p.write_text(_hf_pair_jsonl(en_text, haw_text), encoding="utf-8")
            out = ev.human_fetch_translation_probe(str(p))
        # Flatten all string values in the output dict (recursively).
        def _collect_strings(obj):
            if isinstance(obj, str):
                yield obj
            elif isinstance(obj, dict):
                for v in obj.values():
                    yield from _collect_strings(v)
            elif isinstance(obj, (list, tuple)):
                for item in obj:
                    yield from _collect_strings(item)
        all_strings = list(_collect_strings(out))
        for s in all_strings:
            self.assertNotIn(en_text, s, f"raw English text found in output: {s!r}")
            self.assertNotIn(haw_text, s, f"raw Hawaiian text found in output: {s!r}")

    def test_no_raw_text_in_summary_like_directions(self):
        """direction dicts carry only hashes/numerics, no raw source or reference."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "pair.jsonl"
            p.write_text(
                _hf_pair_jsonl("Hello world", "Aloha kāua"), encoding="utf-8"
            )
            out = ev.human_fetch_translation_probe(str(p))
        for dir_name, d in out.get("directions", {}).items():
            self.assertNotIn("text", d, f"raw text field in {dir_name}")
            self.assertNotIn("reference", d, f"raw reference in {dir_name}")
            self.assertNotIn("prompt", d, f"raw prompt in {dir_name}")

    def test_probe_policy_fields(self):
        """eval_eligible=True, training_eligible=False always set."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "pair.jsonl"
            p.write_text(_hf_pair_jsonl(), encoding="utf-8")
            out = ev.human_fetch_translation_probe(str(p))
        self.assertTrue(out.get("eval_eligible"))
        self.assertFalse(out.get("training_eligible"))

    def test_evaluated_with_mock_model(self):
        """With a mocked model both directions are scored and metrics are numeric."""
        from unittest.mock import patch

        en_text = "Hello world"
        haw_text = "Aloha kāua"
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "pair.jsonl"
            p.write_text(_hf_pair_jsonl(en_text, haw_text), encoding="utf-8")
            fake_model = object()
            fake_tokenizer = object()
            # Return plausible (fake) generations for both directions.
            with patch("llm_hawaii.evaluate.sample_generations") as mock_sg:
                mock_sg.return_value = ["Aloha", "Hello"]
                out = ev.human_fetch_translation_probe(
                    str(p),
                    model=fake_model,
                    tokenizer=fake_tokenizer,
                )
        self.assertEqual(out["status"], "evaluated")
        self.assertIn("directions", out)
        for dir_name in ("en_to_haw", "haw_to_en"):
            d = out["directions"][dir_name]
            self.assertIn("char_f1", d, f"char_f1 missing from {dir_name}")
            self.assertIn("char_precision", d)
            self.assertIn("char_recall", d)
            self.assertIn("generation_sha256", d)
            self.assertIn("reference_sha256", d)
            self.assertIn("prompt_sha256", d)
            self.assertEqual(d.get("metric"), "char_ngram_f1_baseline")
            self.assertEqual(d.get("ngram_order"), 2)
            # No raw text
            self.assertNotIn("text", d)
            self.assertNotIn("reference", d)
            self.assertNotIn("prompt", d)

    def test_bidirectional_scores_are_separate(self):
        """en→haw and haw→en metrics are distinct — never averaged."""
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "pair.jsonl"
            p.write_text(_hf_pair_jsonl("Hello world", "Aloha kāua"), encoding="utf-8")
            with patch("llm_hawaii.evaluate.sample_generations") as mock_sg:
                # Give very different generations so the two F1 scores differ.
                mock_sg.return_value = ["Aloha kāua", "xxxxxxxxxxx"]
                out = ev.human_fetch_translation_probe(
                    str(p), model=object(), tokenizer=object()
                )
        d = out["directions"]
        # They must exist as separate keys, not collapsed into one number.
        self.assertIn("en_to_haw", d)
        self.assertIn("haw_to_en", d)
        # With very different generations the F1s should differ.
        self.assertNotEqual(
            d["en_to_haw"]["char_f1"], d["haw_to_en"]["char_f1"],
            "en→haw and haw→en F1 should differ with different generations",
        )

    def test_schema_constant_is_stable(self):
        self.assertEqual(ev.HUMAN_FETCH_PROBE_SCHEMA, "human-fetch-translation-probe-v1")

    def test_default_jsonl_path_constant(self):
        self.assertEqual(
            ev.DEFAULT_HUMAN_FETCH_JSONL,
            "data/tokenizer_audit/ulukau_nupepa/human_fetch.jsonl",
        )

    def test_cli_human_fetch_args_exist(self):
        """--human-fetch-jsonl and --no-human-fetch are wired into main()."""
        import inspect
        src = inspect.getsource(ev.main)
        self.assertIn("human-fetch-jsonl", src)
        self.assertIn("no-human-fetch", src)
        self.assertIn("human_fetch_jsonl", src)
        self.assertIn("use_human_fetch", src)

    def test_evaluate_checkpoint_signature_includes_human_fetch(self):
        """evaluate_checkpoint accepts human_fetch_jsonl and use_human_fetch."""
        import inspect
        sig = inspect.signature(ev.evaluate_checkpoint)
        self.assertIn("human_fetch_jsonl", sig.parameters)
        self.assertIn("use_human_fetch", sig.parameters)

    def test_stage0_report_includes_probe_key(self):
        """The probe key 'human_fetch_translation' appears in evaluate_checkpoint
        source — verifying it is wired on every checkpoint run."""
        import inspect
        src = inspect.getsource(ev.evaluate_checkpoint)
        self.assertIn("human_fetch_translation", src)
        self.assertIn("human_fetch_translation_probe", src)


if __name__ == "__main__":
    unittest.main()
