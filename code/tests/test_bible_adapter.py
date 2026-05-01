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


if __name__ == "__main__":
    unittest.main()
