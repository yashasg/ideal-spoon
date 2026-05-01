"""Stage-2 Bible verse-id adapter tests (issue #16, Frank).

Tests the contract of:

  * ``scripts/322_build_bible_candidates.py`` — fixture-backed candidate
    JSONL emitter (verse-id alignment, NFC + ʻokina canonicalization,
    Stage-2 manifest-schema conformance).
  * ``scripts/206_fetch_baibala_raw.py`` — dry-run safety + edition-pin
    gating of ``--execute``.
  * ``data-sources/bible/source_registry.json`` — registry shape.

Stdlib + unittest only. No network, no torch, no transformers.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import unicodedata
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
FIXTURE_DIR = REPO_ROOT / "code" / "tests" / "fixtures" / "bible"
HAW_HTML_FIXTURE_DIR = FIXTURE_DIR / "haw_html"


def _load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


build = _load_script("build_bible_candidates",
                     SCRIPTS_DIR / "322_build_bible_candidates.py")
fetch = _load_script("fetch_baibala_raw",
                     SCRIPTS_DIR / "206_fetch_baibala_raw.py")
manifest = _load_script("build_stage2_manifest",
                        SCRIPTS_DIR / "320_build_stage2_manifest.py")
usfm_parser = _load_script("parse_eng_usfm",
                            SCRIPTS_DIR / "206b_parse_eng_usfm.py")

ENG_USFM_FIXTURE_DIR = FIXTURE_DIR / "eng_usfm"

class TestRegistry(unittest.TestCase):
    def test_registry_is_valid_json_with_required_sides(self):
        reg = build.load_registry()
        self.assertIn("haw", reg["sides"])
        self.assertIn("eng", reg["sides"])
        for side in ("haw", "eng"):
            cfg = reg["sides"][side]
            for key in ("source_id", "url_template", "license_observed",
                        "edition_or_version", "tos_url",
                        "fetcher_user_agent", "polite_rate_limit_seconds"):
                self.assertIn(key, cfg, f"side={side} missing {key}")

    def test_registry_books_complete_canon(self):
        reg = build.load_registry()
        self.assertEqual(len(reg["books"]), 66, "Bible canon must have 66 books")
        codes = [b["code"] for b in reg["books"]]
        self.assertEqual(len(codes), len(set(codes)), "book codes must be unique")
        # Spot-check a few canonical codes.
        for code in ("GEN", "PSA", "MAT", "REV"):
            self.assertIn(code, codes)

    def test_registry_alignment_defaults_match_issue_contract(self):
        reg = build.load_registry()
        a = reg["alignment_defaults"]
        self.assertEqual(a["alignment_type"], "parallel-verse")
        self.assertEqual(a["alignment_method"], "verse-id")
        self.assertIsNone(a["alignment_score"])
        self.assertEqual(a["register"], "religious")
        self.assertFalse(a["synthetic"])
        self.assertTrue(a["prototype_only"])
        self.assertFalse(a["release_eligible"])


class TestNormalization(unittest.TestCase):
    def test_okina_curly_canonicalized_to_u02bb(self):
        # U+2018 is a common ʻokina mis-encoding that the haw normalizer
        # must convert to U+02BB before hashing.
        out = build.normalize_haw("\u2018\u014dlelo Hawai\u2019i")  # ‘ōlelo Hawai’i
        self.assertNotIn("\u2018", out)
        self.assertNotIn("\u2019", out)
        self.assertIn(build.OKINA, out)
        self.assertEqual(out, "\u02bb\u014dlelo Hawai\u02bbi")

    def test_normalize_haw_is_nfc(self):
        # combining macron input should be folded to NFC precomposed
        out = build.normalize_haw("ha\u0304lau")  # a + U+0304
        self.assertEqual(out, "h\u0101lau")
        self.assertEqual(unicodedata.normalize("NFC", out), out)

    def test_pair_hash_matches_manifest_helper(self):
        en = build.sha256_text("hello")
        hw = build.sha256_text("aloha")
        self.assertEqual(
            build.compute_pair_hash(en, hw),
            manifest.compute_pair_hash(en, hw),
        )


class TestCandidateBuilder(unittest.TestCase):
    def setUp(self):
        self.registry = build.load_registry()
        self.rows = build.build_rows_for_chapter(
            registry=self.registry,
            book_code="GEN",
            chapter=1,
            haw_path=FIXTURE_DIR / "haw" / "GEN_1.txt",
            eng_path=FIXTURE_DIR / "eng" / "GEN_1.txt",
            fetch_date="20260501",
        )

    def test_emits_one_row_per_shared_verse(self):
        self.assertEqual(len(self.rows), 5)
        ids = [r["pair_id"] for r in self.rows]
        self.assertEqual(ids, [f"bible:GEN:1:{i}" for i in range(1, 6)])

    def test_pair_id_is_deterministic(self):
        rows2 = build.build_rows_for_chapter(
            registry=self.registry,
            book_code="GEN",
            chapter=1,
            haw_path=FIXTURE_DIR / "haw" / "GEN_1.txt",
            eng_path=FIXTURE_DIR / "eng" / "GEN_1.txt",
            fetch_date="20260501",
        )
        for a, b in zip(self.rows, rows2):
            self.assertEqual(a["pair_id"], b["pair_id"])
            self.assertEqual(a["sha256_pair"], b["sha256_pair"])
            self.assertEqual(a["sha256_haw_clean"], b["sha256_haw_clean"])

    def test_alignment_contract_per_issue_16(self):
        for r in self.rows:
            self.assertEqual(r["alignment_type"], "parallel-verse")
            self.assertEqual(r["alignment_method"], "verse-id")
            self.assertIsNone(r["alignment_score"])
            self.assertFalse(r["alignment_review_required"])
            self.assertEqual(r["register"], "religious")
            self.assertFalse(r["synthetic"])
            self.assertTrue(r["prototype_only"])
            self.assertFalse(r["release_eligible"])
            self.assertIsNone(r["license_inferred"])
            self.assertEqual(r["lang_id_haw"], "haw")
            self.assertEqual(r["lang_id_en"], "eng")
            self.assertEqual(r["split"], "train")

    def test_haw_text_is_nfc_and_uses_u02bb(self):
        for r in self.rows:
            t = r["text_haw"]
            self.assertEqual(unicodedata.normalize("NFC", t), t,
                             f"haw NFC drift in {r['pair_id']}")
            for bad in ("\u2018", "\u2019"):
                self.assertNotIn(bad, t,
                                 f"haw ʻokina mis-encoding in {r['pair_id']}")

    def test_pair_hash_invariant(self):
        for r in self.rows:
            self.assertEqual(
                r["sha256_pair"],
                manifest.compute_pair_hash(r["sha256_en_clean"], r["sha256_haw_clean"]),
            )

    def test_rows_pass_stage2_manifest_schema(self):
        for r in self.rows:
            # Adapter rows ship without alignment-quality policy fields;
            # those are merged on by the manifest builder (issue #19).
            # Apply the policy here so the test reflects the post-ingest
            # contract: scored row must validate cleanly.
            scored = manifest.apply_policy(dict(r))
            violations = manifest.validate_row(scored)
            self.assertEqual(violations, [],
                             f"schema violations on {r['pair_id']}: {violations}")


class TestLiveHtmlParser(unittest.TestCase):
    """Tests for parse_baibala_chapter_html() against the live anchor pattern.

    Uses the small synthetic HTML fixture under
    ``code/tests/fixtures/bible/haw_html/`` which mirrors the live
    ``<a name="agenesis-1-N"></a>... <br />`` structure observed on
    baibala.org Greenstone pages. **No real Bible text is committed.**
    """

    def test_parses_anchor_pattern_into_verse_dicts(self):
        html = (HAW_HTML_FIXTURE_DIR / "GEN_001.html").read_bytes()
        rows = fetch.parse_baibala_chapter_html(
            html, book_code="GEN", chapter=1, book_name_lower="genesis",
        )
        self.assertEqual(len(rows), 5)
        self.assertEqual([r["verse"] for r in rows], [1, 2, 3, 4, 5])
        for r in rows:
            self.assertEqual(r["book"], "GEN")
            self.assertEqual(r["chapter"], 1)
            self.assertIsInstance(r["text"], str)
            self.assertGreater(len(r["text"]), 0)
            # Verse number prefix must be stripped from the body.
            self.assertFalse(
                r["text"].lstrip().startswith(f"{r['verse']} "),
                f"verse-number prefix not stripped: {r['text']!r}",
            )
            # &para; (¶) must not leak into the parsed text.
            self.assertNotIn("\u00b6", r["text"])
            self.assertNotIn("&para;", r["text"])
            # No HTML tag remnants.
            self.assertNotIn("<", r["text"])
            self.assertNotIn(">", r["text"])

    def test_parsed_text_is_nfc_and_canonical_okina(self):
        html = (HAW_HTML_FIXTURE_DIR / "GEN_001.html").read_bytes()
        rows = fetch.parse_baibala_chapter_html(
            html, book_code="GEN", chapter=1, book_name_lower="genesis",
        )
        for r in rows:
            t = r["text"]
            self.assertEqual(unicodedata.normalize("NFC", t), t)
            for bad in ("\u2018", "\u2019"):
                self.assertNotIn(bad, t)

    def test_ascii_apostrophe_canonicalized_to_okina(self):
        # Live 1839 imprint uses ASCII apostrophes (e.g. "hana'i"); parser
        # must canonicalize to U+02BB so the haw side hash is stable across
        # upstream rendering quirks (matches normalize_haw policy).
        html = (
            b'<html><body>'
            b'<a name="agenesis-1-1"></a>1 hana\'i ke Akua. <br />'
            b'</body></html>'
        )
        rows = fetch.parse_baibala_chapter_html(
            html, book_code="GEN", chapter=1, book_name_lower="genesis",
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["text"], "hana\u02bbi ke Akua.")
        self.assertNotIn("'", rows[0]["text"])

    def test_chapter_filter_drops_other_chapters(self):
        html = (
            b'<html><body>'
            b'<a name="agenesis-1-1"></a>1 first. <br />'
            b'<a name="agenesis-2-1"></a>1 second. <br />'
            b'</body></html>'
        )
        rows = fetch.parse_baibala_chapter_html(
            html, book_code="GEN", chapter=1, book_name_lower="genesis",
        )
        self.assertEqual([r["verse"] for r in rows], [1])
        self.assertIn("first", rows[0]["text"])

    def test_book_name_lower_filter_drops_other_books(self):
        html = (
            b'<html><body>'
            b'<a name="agenesis-1-1"></a>1 genesis verse. <br />'
            b'<a name="aexodus-1-1"></a>1 exodus verse. <br />'
            b'</body></html>'
        )
        rows = fetch.parse_baibala_chapter_html(
            html, book_code="GEN", chapter=1, book_name_lower="genesis",
        )
        self.assertEqual(len(rows), 1)
        self.assertIn("genesis verse", rows[0]["text"])

    def test_para_marker_is_stripped(self):
        html = (
            b'<html><body>'
            b'<a name="agenesis-1-1"></a>1 &para; In the beginning. <br />'
            b'</body></html>'
        )
        rows = fetch.parse_baibala_chapter_html(
            html, book_code="GEN", chapter=1, book_name_lower="genesis",
        )
        self.assertEqual(rows[0]["text"], "In the beginning.")

    def test_parser_is_idempotent_on_repeated_anchors(self):
        # Defensive: if upstream HTML accidentally repeats an anchor
        # (Greenstone footers can echo nav), we keep only the first.
        html = (
            b'<html><body>'
            b'<a name="agenesis-1-1"></a>1 first body. <br />'
            b'<a name="agenesis-1-1"></a>1 dup body. <br />'
            b'</body></html>'
        )
        rows = fetch.parse_baibala_chapter_html(
            html, book_code="GEN", chapter=1, book_name_lower="genesis",
        )
        self.assertEqual(len(rows), 1)
        self.assertIn("first body", rows[0]["text"])


class TestRawHawCandidateBuilder(unittest.TestCase):
    """End-to-end: raw haw chapter HTML → manifest-shaped rows via 322."""

    def test_build_rows_from_raw_haw_pairs_against_eng_fixture(self):
        registry = build.load_registry()
        rows, summary = build.build_rows_from_raw_haw(
            registry=registry,
            haw_raw_dir=HAW_HTML_FIXTURE_DIR,
            eng_fixture_dir=FIXTURE_DIR,
            fetch_date="20260501",
        )
        self.assertEqual(len(rows), 5)
        self.assertEqual([r["pair_id"] for r in rows],
                         [f"bible:GEN:1:{i}" for i in range(1, 6)])
        for r in rows:
            self.assertEqual(r["alignment_method"], "verse-id")
            self.assertEqual(r["source"], "baibala-hemolele-1839")
            # Raw-source rows carry the src=raw_html provenance marker.
            self.assertIn("raw_html", r["notes"])

    def test_raw_haw_rows_pass_stage2_manifest_schema(self):
        registry = build.load_registry()
        rows, _ = build.build_rows_from_raw_haw(
            registry=registry,
            haw_raw_dir=HAW_HTML_FIXTURE_DIR,
            eng_fixture_dir=FIXTURE_DIR,
            fetch_date="20260501",
        )
        for r in rows:
            scored = manifest.apply_policy(dict(r))
            violations = manifest.validate_row(scored)
            self.assertEqual(violations, [],
                             f"schema violations on {r['pair_id']}: {violations}")

    def test_cli_haw_raw_dir_dry_run(self):
        rc = build.main([
            "--dry-run",
            "--haw-raw-dir", str(HAW_HTML_FIXTURE_DIR),
            "--eng-fixture-dir", str(FIXTURE_DIR),
            "--fetch-date", "20260501",
        ])
        self.assertEqual(rc, 0)

    def test_cli_haw_raw_dir_execute_writes_jsonl(self):
        out = REPO_ROOT / "data" / "stage2" / "candidates" / "bible.jsonl"
        if out.exists():
            out.unlink()
        rc = build.main([
            "--execute",
            "--haw-raw-dir", str(HAW_HTML_FIXTURE_DIR),
            "--eng-fixture-dir", str(FIXTURE_DIR),
            "--fetch-date", "20260501",
        ])
        self.assertEqual(rc, 0)
        self.assertTrue(out.exists())
        lines = out.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 5)
        for ln in lines:
            row = json.loads(ln)
            self.assertEqual(row["alignment_method"], "verse-id")

    def test_cli_from_raw_rejects_bad_date(self):
        rc = build.main([
            "--dry-run",
            "--from-raw", "not-a-date",
        ])
        self.assertEqual(rc, 2)


class TestFetcherSafety(unittest.TestCase):
    def test_print_pin_status_works(self):
        rc = fetch.main(["--print-pin-status"])
        self.assertEqual(rc, 0)

    def test_dry_run_emits_plan_without_network(self):
        # No --execute → no network access. We just confirm main() exits 0.
        rc = fetch.main(["--dry-run", "--side", "haw",
                         "--book", "GEN", "--chapters", "1-2"])
        self.assertEqual(rc, 0)

    def test_execute_refused_without_edition_pin(self):
        # With edition now pinned, test that --execute is refused when
        # --confirm-edition does not match the pinned edition. This is
        # the remaining safety gate enforced by assert_execute_preconditions.
        with self.assertRaises(SystemExit) as ctx:
            fetch.main([
                "--execute", "--side", "haw",
                "--book", "GEN", "--chapters", "1",
                "--confirm-edition", "wrong-edition-id",
                "--tos-snapshot", str(REPO_ROOT / "README.md"),  # any existing path
            ])
        # SystemExit message must mention edition mismatch
        self.assertIn("confirm-edition", str(ctx.exception).replace("_", "-"))

    def test_parse_chapters_spec(self):
        self.assertEqual(fetch.parse_chapters_spec("1-3,5", 50), [1, 2, 3, 5])
        self.assertEqual(fetch.parse_chapters_spec("2", 50), [2])
        with self.assertRaises(ValueError):
            fetch.parse_chapters_spec("1-1000", 50)


class TestCandidateCLI(unittest.TestCase):
    def test_dry_run_returns_zero(self):
        rc = build.main(["--dry-run", "--fixture-dir", str(FIXTURE_DIR)])
        self.assertEqual(rc, 0)

    def test_execute_writes_jsonl(self):
        out = REPO_ROOT / "data" / "stage2" / "candidates" / "bible.jsonl"
        # Clean up before; tolerate absence.
        if out.exists():
            out.unlink()
        rc = build.main(["--execute", "--fixture-dir", str(FIXTURE_DIR),
                         "--fetch-date", "20260501"])
        self.assertEqual(rc, 0)
        self.assertTrue(out.exists())
        lines = out.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 5)
        for ln in lines:
            row = json.loads(ln)
            self.assertEqual(row["alignment_method"], "verse-id")


class TestUSFMParser(unittest.TestCase):
    """Tests for ``scripts/206b_parse_eng_usfm.py`` — no disk I/O except fixture."""

    _SIMPLE_USFM = (
        "\\id GEN FIXTURE\n"
        "\\c 1\n"
        "\\p\n"
        "\\v 1 In the beginning.\n"
        "\\v 2 The earth was formless.\n"
        "\\c 2\n"
        "\\v 1 Thus the heavens were finished.\n"
    )

    def test_parses_verse_book_chapter_text(self):
        recs = usfm_parser.parse_usfm_text(self._SIMPLE_USFM)
        self.assertEqual(len(recs), 3)
        self.assertEqual(recs[0]["book"], "GEN")
        self.assertEqual(recs[0]["chapter"], 1)
        self.assertEqual(recs[0]["verse"], 1)
        self.assertEqual(recs[0]["text"], "In the beginning.")
        self.assertEqual(recs[1]["chapter"], 1)
        self.assertEqual(recs[1]["verse"], 2)
        self.assertEqual(recs[2]["chapter"], 2)
        self.assertEqual(recs[2]["verse"], 1)

    def test_source_tag_is_usfm(self):
        recs = usfm_parser.parse_usfm_text(self._SIMPLE_USFM)
        for r in recs:
            self.assertEqual(r["source"], "usfm")

    def test_inline_marker_stripped(self):
        usfm = (
            "\\id MAT\n"
            "\\c 5\n"
            "\\v 3 \\wj Blessed are the poor \\wj* in spirit.\n"
        )
        recs = usfm_parser.parse_usfm_text(usfm)
        self.assertEqual(len(recs), 1)
        self.assertNotIn("\\wj", recs[0]["text"])
        self.assertIn("Blessed are the poor", recs[0]["text"])
        self.assertIn("in spirit", recs[0]["text"])

    def test_para_marker_trailing_text_appended_to_verse(self):
        usfm = (
            "\\id PSA\n"
            "\\c 23\n"
            "\\v 1 The Lord is my shepherd.\n"
            "\\q1 I shall not want.\n"
            "\\v 2 He makes me lie down.\n"
        )
        recs = usfm_parser.parse_usfm_text(usfm)
        self.assertEqual(len(recs), 2)
        self.assertIn("I shall not want", recs[0]["text"])
        self.assertIn("He makes me lie down", recs[1]["text"])

    def test_source_book_code_override(self):
        usfm = "\\id GEN\n\\c 1\n\\v 1 Text.\n"
        recs = usfm_parser.parse_usfm_text(usfm, source_book_code="EXO")
        self.assertEqual(recs[0]["book"], "EXO")

    def test_empty_verse_dropped(self):
        usfm = "\\id GEN\n\\c 1\n\\v 1 \n\\v 2 Real text.\n"
        recs = usfm_parser.parse_usfm_text(usfm)
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["verse"], 2)

    def test_duplicate_verse_anchor_keeps_first(self):
        usfm = (
            "\\id GEN\n"
            "\\c 1\n"
            "\\v 1 First occurrence.\n"
            "\\v 1 Duplicate — should be dropped.\n"
        )
        recs = usfm_parser.parse_usfm_text(usfm)
        self.assertEqual(len(recs), 1)
        self.assertIn("First occurrence", recs[0]["text"])

    def test_output_is_nfc(self):
        combining_usfm = "\\id GEN\n\\c 1\n\\v 1 ha\u0304lau.\n"
        recs = usfm_parser.parse_usfm_text(combining_usfm)
        self.assertEqual(recs[0]["text"], "h\u0101lau.")
        self.assertEqual(
            unicodedata.normalize("NFC", recs[0]["text"]), recs[0]["text"]
        )

    def test_strong_number_attribute_stripped(self):
        """eBible KJV/ASV \\w word|strong="H7225"\\w* must not leak into text."""
        usfm = (
            "\\id GEN\n"
            "\\c 1\n"
            '\\v 1 \\w In|strong="H0430"\\w* \\w the|strong="H0853"\\w* '
            '\\w beginning|strong="H7225"\\w* God created the earth.\n'
        )
        recs = usfm_parser.parse_usfm_text(usfm)
        self.assertEqual(len(recs), 1)
        self.assertNotIn("|strong=", recs[0]["text"])
        self.assertNotIn("H7225", recs[0]["text"])
        self.assertNotIn("H0430", recs[0]["text"])
        self.assertIn("In", recs[0]["text"])
        self.assertIn("the", recs[0]["text"])
        self.assertIn("beginning", recs[0]["text"])
        self.assertIn("God created the earth", recs[0]["text"])

    def test_nested_inline_markers_with_word_attrs_stripped(self):
        """\\wj … \\wj* around \\w word|attrs\\w* must both be cleaned up."""
        usfm = (
            "\\id MAT\n"
            "\\c 5\n"
            '\\v 3 \\wj \\w Blessed|strong="H0835"\\w* are the poor \\wj* in spirit.\n'
        )
        recs = usfm_parser.parse_usfm_text(usfm)
        self.assertEqual(len(recs), 1)
        self.assertNotIn("\\wj", recs[0]["text"])
        self.assertNotIn("|strong=", recs[0]["text"])
        self.assertIn("Blessed", recs[0]["text"])
        self.assertIn("are the poor", recs[0]["text"])
        self.assertIn("in spirit", recs[0]["text"])

    def test_plain_text_verse_unchanged_by_cleanup(self):
        """Verses with no USFM attributes must pass through without alteration."""
        usfm = (
            "\\id GEN\n"
            "\\c 1\n"
            "\\v 1 In the beginning God created the heavens and the earth.\n"
            "\\v 2 And the earth was without form and void.\n"
        )
        recs = usfm_parser.parse_usfm_text(usfm)
        self.assertEqual(len(recs), 2)
        self.assertEqual(
            recs[0]["text"],
            "In the beginning God created the heavens and the earth.",
        )
        self.assertEqual(
            recs[1]["text"],
            "And the earth was without form and void.",
        )

    def test_parse_fixture_file_matches_txt_fixture(self):
        """USFM fixture verses must match the corresponding eng .txt fixture."""
        usfm_path = ENG_USFM_FIXTURE_DIR / "GEN_1.usfm"
        recs = usfm_parser.parse_usfm_file(usfm_path)
        self.assertEqual(len(recs), 5)
        # Verse 1 must match the txt fixture.
        txt_verses = build.parse_verse_txt(FIXTURE_DIR / "eng" / "GEN_1.txt")
        for r in recs:
            self.assertIn(r["verse"], txt_verses)
            txt_text = txt_verses[r["verse"]][0].strip()
            self.assertEqual(r["text"], txt_text,
                             f"verse {r['verse']}: USFM text != txt fixture")

    def test_self_test_exits_zero(self):
        rc = usfm_parser.main(["--self-test"])
        self.assertEqual(rc, 0)

    def test_cli_missing_source_returns_2(self):
        rc = usfm_parser.main([])
        self.assertEqual(rc, 2)

    def test_verses_by_chapter_index(self):
        recs = usfm_parser.parse_usfm_text(self._SIMPLE_USFM)
        idx = usfm_parser.verses_by_chapter(recs)
        self.assertIn(("GEN", 1), idx)
        self.assertEqual(idx[("GEN", 1)][1], "In the beginning.")
        self.assertEqual(idx[("GEN", 2)][1], "Thus the heavens were finished.")


class TestUSFMWiredCandidateBuilder(unittest.TestCase):
    """End-to-end: raw haw HTML + USFM eng fixture → manifest-shaped rows."""

    def _eng_usfm_verses(self):
        recs = usfm_parser.parse_usfm_file(ENG_USFM_FIXTURE_DIR / "GEN_1.usfm")
        return usfm_parser.verses_by_chapter(recs)

    def test_build_rows_from_usfm_eng_count(self):
        registry = build.load_registry()
        rows, summary = build.build_rows_from_usfm_eng(
            registry=registry,
            haw_raw_dir=HAW_HTML_FIXTURE_DIR,
            eng_usfm_verses=self._eng_usfm_verses(),
            fetch_date="20260501",
        )
        self.assertEqual(len(rows), 5)

    def test_usfm_rows_pair_ids_match_txt_path(self):
        """USFM-wired rows produce same pair_ids as the .txt fixture path."""
        registry = build.load_registry()
        txt_rows = build.build_rows_for_chapter(
            registry=registry,
            book_code="GEN",
            chapter=1,
            haw_path=FIXTURE_DIR / "haw" / "GEN_1.txt",
            eng_path=FIXTURE_DIR / "eng" / "GEN_1.txt",
            fetch_date="20260501",
        )
        usfm_rows, _ = build.build_rows_from_usfm_eng(
            registry=registry,
            haw_raw_dir=HAW_HTML_FIXTURE_DIR,
            eng_usfm_verses=self._eng_usfm_verses(),
            fetch_date="20260501",
        )
        self.assertEqual(
            [r["pair_id"] for r in usfm_rows],
            [r["pair_id"] for r in txt_rows],
        )

    def test_usfm_rows_sha256_pair_matches_txt_path(self):
        """USFM-parsed eng text → same sha256_pair as .txt path."""
        registry = build.load_registry()
        txt_rows = build.build_rows_for_chapter(
            registry=registry,
            book_code="GEN",
            chapter=1,
            haw_path=FIXTURE_DIR / "haw" / "GEN_1.txt",
            eng_path=FIXTURE_DIR / "eng" / "GEN_1.txt",
            fetch_date="20260501",
        )
        usfm_rows, _ = build.build_rows_from_usfm_eng(
            registry=registry,
            haw_raw_dir=HAW_HTML_FIXTURE_DIR,
            eng_usfm_verses=self._eng_usfm_verses(),
            fetch_date="20260501",
        )
        for t, u in zip(txt_rows, usfm_rows):
            self.assertEqual(t["sha256_en_clean"], u["sha256_en_clean"],
                             f"eng hash mismatch at {t['pair_id']}")
            self.assertEqual(t["sha256_haw_clean"], u["sha256_haw_clean"],
                             f"haw hash mismatch at {t['pair_id']}")

    def test_usfm_rows_pass_manifest_schema(self):
        registry = build.load_registry()
        rows, _ = build.build_rows_from_usfm_eng(
            registry=registry,
            haw_raw_dir=HAW_HTML_FIXTURE_DIR,
            eng_usfm_verses=self._eng_usfm_verses(),
            fetch_date="20260501",
        )
        for r in rows:
            scored = manifest.apply_policy(dict(r))
            violations = manifest.validate_row(scored)
            self.assertEqual(violations, [],
                             f"schema violations on {r['pair_id']}: {violations}")

    def test_usfm_rows_notes_carry_usfm_provenance(self):
        registry = build.load_registry()
        rows, _ = build.build_rows_from_usfm_eng(
            registry=registry,
            haw_raw_dir=HAW_HTML_FIXTURE_DIR,
            eng_usfm_verses=self._eng_usfm_verses(),
            fetch_date="20260501",
        )
        for r in rows:
            self.assertIn("usfm_eng", r["notes"])

    def test_usfm_rows_are_train_only(self):
        registry = build.load_registry()
        rows, _ = build.build_rows_from_usfm_eng(
            registry=registry,
            haw_raw_dir=HAW_HTML_FIXTURE_DIR,
            eng_usfm_verses=self._eng_usfm_verses(),
            fetch_date="20260501",
        )
        for r in rows:
            self.assertEqual(r["split"], "train")
            self.assertTrue(r["prototype_only"])
            self.assertFalse(r["release_eligible"])

    def test_cli_eng_usfm_file_dry_run(self):
        rc = build.main([
            "--dry-run",
            "--haw-raw-dir", str(HAW_HTML_FIXTURE_DIR),
            "--eng-usfm-file", str(ENG_USFM_FIXTURE_DIR / "GEN_1.usfm"),
            "--fetch-date", "20260501",
        ])
        self.assertEqual(rc, 0)

    def test_cli_eng_usfm_file_execute_writes_jsonl(self):
        out = REPO_ROOT / "data" / "stage2" / "candidates" / "bible.jsonl"
        if out.exists():
            out.unlink()
        rc = build.main([
            "--execute",
            "--haw-raw-dir", str(HAW_HTML_FIXTURE_DIR),
            "--eng-usfm-file", str(ENG_USFM_FIXTURE_DIR / "GEN_1.usfm"),
            "--fetch-date", "20260501",
        ])
        self.assertEqual(rc, 0)
        self.assertTrue(out.exists())
        lines = out.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 5)
        for ln in lines:
            row = json.loads(ln)
            self.assertIn("usfm_eng", row["notes"])


HAW_USFM_FIXTURE_DIR = FIXTURE_DIR / "haw_usfm"
KJV_TSV_FIXTURE_PATH = FIXTURE_DIR / "kjv_tsv" / "kjv_fixture.tsv"


class TestKjvTsvParser(unittest.TestCase):
    """Unit tests for parse_kjv_tsv() + _build_book_index_map()."""

    def _bim(self):
        return build._build_book_index_map(build.load_registry())

    def test_header_recognised(self):
        verses, summary = build.parse_kjv_tsv(KJV_TSV_FIXTURE_PATH, book_index_map=self._bim())
        self.assertIsInstance(verses, dict)

    def test_gen_1_1_parsed(self):
        verses, _ = build.parse_kjv_tsv(KJV_TSV_FIXTURE_PATH, book_index_map=self._bim())
        self.assertIn(("GEN", 1), verses)
        self.assertIn(1, verses[("GEN", 1)])
        self.assertIn("beginning", verses[("GEN", 1)][1])

    def test_all_5_fixture_verses_parsed(self):
        verses, summary = build.parse_kjv_tsv(KJV_TSV_FIXTURE_PATH, book_index_map=self._bim())
        self.assertEqual(summary["verses_parsed"], 5)
        self.assertEqual(summary["malformed_skipped"], 0)

    def test_bad_header_raises_value_error(self):
        bad_path = FIXTURE_DIR / "kjv_tsv" / "_bad_header.tsv"
        bad_path.write_bytes(b"wrong\theader\there\n01O\t1\t1\t\t10\ttext\n")
        try:
            with self.assertRaises(ValueError):
                build.parse_kjv_tsv(bad_path, book_index_map=self._bim())
        finally:
            bad_path.unlink(missing_ok=True)

    def test_malformed_row_skipped_counted(self):
        bad_path = FIXTURE_DIR / "kjv_tsv" / "_malformed.tsv"
        bad_path.write_bytes(
            b"orig_book_index\torig_chapter\torig_verse\torig_subverse\torder_by\ttext\n"
            b"01O\t1\t1\t\t10\tGood row.\n"
            b"TOOFE\tnotint\n"
            b"01O\t1\t2\t\t20\tAnother good row.\n"
        )
        try:
            verses, summary = build.parse_kjv_tsv(bad_path, book_index_map=self._bim())
            self.assertEqual(summary["verses_parsed"], 2)
            self.assertGreaterEqual(summary["malformed_skipped"], 1)
        finally:
            bad_path.unlink(missing_ok=True)

    def test_book_index_map_covers_all_66(self):
        bim = self._bim()
        self.assertEqual(len(bim), 66)
        self.assertEqual(bim["01"], "GEN")
        self.assertEqual(bim["66"], "REV")
        self.assertEqual(bim["40"], "MAT")

    def test_book_filter_excludes_other_books(self):
        verses, summary = build.parse_kjv_tsv(
            KJV_TSV_FIXTURE_PATH, book_index_map=self._bim(), book_filter={"EXO"}
        )
        self.assertEqual(summary["verses_parsed"], 0)


class TestHaw1868UsfmDirParser(unittest.TestCase):
    """Unit tests for parse_haw1868_usfm_dir()."""

    def test_parses_fixture_usfm_dir(self):
        verses, file_bytes = build.parse_haw1868_usfm_dir(HAW_USFM_FIXTURE_DIR)
        self.assertIn(("GEN", 1), verses)
        self.assertEqual(len(verses[("GEN", 1)]), 5)

    def test_text_is_nfc_normalized(self):
        verses, _ = build.parse_haw1868_usfm_dir(HAW_USFM_FIXTURE_DIR)
        for text in verses[("GEN", 1)].values():
            self.assertEqual(unicodedata.normalize("NFC", text), text)

    def test_file_bytes_map_populated(self):
        _, file_bytes = build.parse_haw1868_usfm_dir(HAW_USFM_FIXTURE_DIR)
        self.assertIn("GEN", file_bytes)
        self.assertIsInstance(file_bytes["GEN"], bytes)
        self.assertGreater(len(file_bytes["GEN"]), 0)

    def test_book_filter_respected(self):
        verses, _ = build.parse_haw1868_usfm_dir(
            HAW_USFM_FIXTURE_DIR, book_filter={"EXO"}
        )
        self.assertEqual(len(verses), 0)

    def test_only_haw1868_named_files_parsed(self):
        verses, _ = build.parse_haw1868_usfm_dir(HAW_USFM_FIXTURE_DIR)
        # Fixture dir has only 02-GENhaw1868.usfm → 1 book key
        self.assertEqual(len(verses), 1)


class TestHaw1868KjvTsvBuilder(unittest.TestCase):
    """End-to-end: haw1868 USFM dir + KJV TSV fixture → manifest rows."""

    def setUp(self):
        self.registry = build.load_registry()
        self.rows, self.summary = build.build_rows_from_haw1868_kjv_tsv(
            registry=self.registry,
            haw_usfm_dir=HAW_USFM_FIXTURE_DIR,
            kjv_tsv_path=KJV_TSV_FIXTURE_PATH,
            fetch_date="20260501",
        )

    def test_emits_one_row_per_shared_verse(self):
        self.assertEqual(len(self.rows), 5)

    def test_pair_ids_are_bible_format(self):
        for r in self.rows:
            self.assertTrue(r["pair_id"].startswith("bible:GEN:1:"))

    def test_dedup_cluster_id_equals_pair_id(self):
        for r in self.rows:
            self.assertEqual(r["dedup_cluster_id"], r["pair_id"])

    def test_alignment_contract_fields(self):
        for r in self.rows:
            self.assertEqual(r["alignment_type"], "parallel-verse")
            self.assertEqual(r["alignment_method"], "verse-id")
            self.assertIsNone(r["alignment_score"])
            self.assertFalse(r["alignment_review_required"])
            self.assertTrue(r["prototype_only"])
            self.assertFalse(r["release_eligible"])
            self.assertEqual(r["split"], "train")
            self.assertEqual(r["lang_id_en"], "eng")
            self.assertEqual(r["lang_id_haw"], "haw")

    def test_source_distinguishes_haw1868(self):
        for r in self.rows:
            self.assertEqual(r["source"], "baibala-hemolele-1868")
            self.assertIn("haw1868", r["edition_or_version"])
            self.assertIn("kjv", r["edition_or_version"])

    def test_notes_carry_haw1868_kjv_tsv_provenance(self):
        for r in self.rows:
            self.assertIn("haw1868-usfm+kjv-tsv", r["notes"])

    def test_haw_text_is_nfc_and_no_bad_okina(self):
        for r in self.rows:
            t = r["text_haw"]
            self.assertEqual(unicodedata.normalize("NFC", t), t)
            for bad in ("\u2018", "\u2019"):
                self.assertNotIn(bad, t)

    def test_pair_hash_invariant(self):
        for r in self.rows:
            self.assertEqual(
                r["sha256_pair"],
                manifest.compute_pair_hash(r["sha256_en_clean"], r["sha256_haw_clean"]),
            )

    def test_rows_pass_stage2_manifest_schema(self):
        for r in self.rows:
            scored = manifest.apply_policy(dict(r))
            violations = manifest.validate_row(scored)
            self.assertEqual(violations, [],
                             f"schema violations on {r['pair_id']}: {violations}")

    def test_summary_contains_required_keys(self):
        for key in ("haw_usfm_dir", "kjv_tsv_path", "fetch_date",
                    "haw_verses", "eng_verses", "shared_keys",
                    "rows_emitted", "missing_haw_side", "missing_eng_side"):
            self.assertIn(key, self.summary, f"summary missing: {key}")

    def test_summary_row_count_matches_rows(self):
        self.assertEqual(self.summary["rows_emitted"], len(self.rows))


class TestHaw1868KjvTsvCli(unittest.TestCase):
    """CLI integration: --haw-usfm-dir + --eng-kjv-tsv-file mode."""

    def test_dry_run_returns_zero(self):
        rc = build.main([
            "--dry-run",
            "--haw-usfm-dir", str(HAW_USFM_FIXTURE_DIR),
            "--eng-kjv-tsv-file", str(KJV_TSV_FIXTURE_PATH),
            "--fetch-date", "20260501",
        ])
        self.assertEqual(rc, 0)

    def test_haw_usfm_dir_without_kjv_tsv_returns_2(self):
        rc = build.main([
            "--dry-run",
            "--haw-usfm-dir", str(HAW_USFM_FIXTURE_DIR),
            "--fetch-date", "20260501",
        ])
        self.assertEqual(rc, 2)

    def test_missing_haw_usfm_dir_returns_3(self):
        rc = build.main([
            "--dry-run",
            "--haw-usfm-dir", str(HAW_USFM_FIXTURE_DIR / "nonexistent"),
            "--eng-kjv-tsv-file", str(KJV_TSV_FIXTURE_PATH),
        ])
        self.assertEqual(rc, 3)

    def test_execute_writes_jsonl(self):
        out = REPO_ROOT / "data" / "stage2" / "candidates" / "bible_haw1868_test.jsonl"
        if out.exists():
            out.unlink()
        rc = build.main([
            "--execute",
            "--haw-usfm-dir", str(HAW_USFM_FIXTURE_DIR),
            "--eng-kjv-tsv-file", str(KJV_TSV_FIXTURE_PATH),
            "--fetch-date", "20260501",
            "--out", str(out),
        ])
        self.assertEqual(rc, 0)
        self.assertTrue(out.exists())
        lines = out.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 5)
        for ln in lines:
            row = json.loads(ln)
            self.assertEqual(row["alignment_method"], "verse-id")
            self.assertEqual(row["source"], "baibala-hemolele-1868")
        out.unlink()


if __name__ == "__main__":
    unittest.main()
