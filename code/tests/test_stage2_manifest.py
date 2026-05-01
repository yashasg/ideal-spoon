"""Tests for Stage-2 manifest builder candidate ingestion (issue #18).

Tests:
- assign_split determinism and distribution
- iter_candidate_files path resolution
- ingest_candidates: schema validation, split replacement, per-source counts
- default_candidate_paths: empty when dir absent
- CLI --dry-run with synthetic candidate
- CLI --execute writes manifest and build_manifest.json

Stdlib + unittest only. No network. All fixtures are synthetic.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
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


m = _load_script("build_stage2_manifest", SCRIPTS_DIR / "320_build_stage2_manifest.py")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_valid_row(pair_id: str = "test-haw1-en1", split: str = "review-pending") -> dict:
    """Minimal schema-valid candidate row.

    Phrases are long enough (≥3 tokens per side) to clear the
    Stage-2 alignment-quality `side_too_short` policy gate (issue #19).
    """
    import unicodedata
    text_en = "Hello to the wide world."
    text_haw = "Aloha i ka honua nui."
    en_nfc = unicodedata.normalize("NFC", text_en)
    haw_nfc = unicodedata.normalize("NFC", text_haw)
    sha_en_raw = hashlib.sha256(text_en.encode()).hexdigest()
    sha_haw_raw = hashlib.sha256(text_haw.encode()).hexdigest()
    sha_en_clean = hashlib.sha256(en_nfc.encode()).hexdigest()
    sha_haw_clean = hashlib.sha256(haw_nfc.encode()).hexdigest()
    sha_pair = m.compute_pair_hash(sha_en_clean, sha_haw_clean)
    return {
        "pair_id": pair_id,
        "source": "test-source",
        "source_url_en": "https://example.com/en/1",
        "source_url_haw": "https://example.com/haw/1",
        "fetch_date": "20250501",
        "sha256_en_raw": sha_en_raw,
        "sha256_haw_raw": sha_haw_raw,
        "sha256_en_clean": sha_en_clean,
        "sha256_haw_clean": sha_haw_clean,
        "sha256_pair": sha_pair,
        "record_id_en": "en-1",
        "record_id_haw": "haw-1",
        "text_en": text_en,
        "text_haw": text_haw,
        "alignment_type": "parallel-sentence",
        "alignment_method": "manual",
        "alignment_score": None,
        "alignment_review_required": False,
        "length_ratio_haw_over_en": len(text_haw.split()) / len(text_en.split()),
        "lang_id_en": "en",
        "lang_id_en_confidence": 1.0,
        "lang_id_haw": "haw",
        "lang_id_haw_confidence": 1.0,
        "direction_original": "unknown",
        "register": "unknown",
        "synthetic": False,
        "license_observed_en": "public-domain",
        "license_observed_haw": "public-domain",
        "license_inferred": None,
        "prototype_only": True,
        "release_eligible": False,
        "dedup_cluster_id": pair_id,
        "crosslink_stage1_overlap": False,
        "split": split,
        "manifest_schema_version": "stage2.v0",
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# assign_split
# ---------------------------------------------------------------------------

class TestAssignSplit(unittest.TestCase):

    def test_deterministic_same_input(self):
        s1 = m.assign_split("test-pair-123")
        s2 = m.assign_split("test-pair-123")
        self.assertEqual(s1, s2)

    def test_returns_valid_split(self):
        for i in range(50):
            result = m.assign_split(f"pair-{i}")
            self.assertIn(result, {"train", "dev"})

    def test_approximately_10_percent_dev(self):
        """With default modulus 10, roughly 10% of pairs should land in dev."""
        splits = [m.assign_split(f"corpus-pair-{i:06d}") for i in range(1000)]
        dev_count = splits.count("dev")
        # Allow generous range for a hash-based 1-in-10 assignment.
        self.assertGreater(dev_count, 50, "Expected >5% dev")
        self.assertLess(dev_count, 200, "Expected <20% dev")

    def test_custom_modulus_changes_fraction(self):
        splits_20 = [m.assign_split(f"pair-{i}", dev_modulus=20) for i in range(200)]
        dev_count = splits_20.count("dev")
        # ~5% dev with modulus 20
        self.assertGreater(dev_count, 2)
        self.assertLess(dev_count, 40)


# ---------------------------------------------------------------------------
# iter_candidate_files
# ---------------------------------------------------------------------------

class TestIterCandidateFiles(unittest.TestCase):

    def test_existing_paths_returned(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "a.jsonl"
            p.write_text("{}\n", encoding="utf-8")
            result = m.iter_candidate_files([p])
            self.assertEqual(result, [p])

    def test_missing_path_skipped(self):
        result = m.iter_candidate_files([Path("/nonexistent/path.jsonl")])
        self.assertEqual(result, [])

    def test_deduplication(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "a.jsonl"
            p.write_text("{}\n", encoding="utf-8")
            result = m.iter_candidate_files([p, p, p])
            self.assertEqual(len(result), 1)

    def test_empty_input(self):
        result = m.iter_candidate_files([])
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# ingest_candidates
# ---------------------------------------------------------------------------

class TestIngestCandidates(unittest.TestCase):

    def test_review_pending_replaced(self):
        row = _make_valid_row(split="review-pending")
        with tempfile.TemporaryDirectory() as tmpdir:
            cpath = Path(tmpdir) / "test.jsonl"
            _write_jsonl(cpath, [row])
            rows, violations, prov = m.ingest_candidates([cpath])
        self.assertEqual(len(violations), 0)
        self.assertEqual(len(rows), 1)
        self.assertIn(rows[0]["split"], {"train", "dev"})
        self.assertNotEqual(rows[0]["split"], "review-pending")

    def test_existing_split_preserved(self):
        row = _make_valid_row(split="train")
        with tempfile.TemporaryDirectory() as tmpdir:
            cpath = Path(tmpdir) / "test.jsonl"
            _write_jsonl(cpath, [row])
            rows, violations, prov = m.ingest_candidates([cpath])
        self.assertEqual(rows[0]["split"], "train")

    def test_per_source_counts(self):
        rows_in = [_make_valid_row(f"p-{i}") for i in range(5)]
        with tempfile.TemporaryDirectory() as tmpdir:
            cpath = Path(tmpdir) / "test-source.jsonl"
            _write_jsonl(cpath, rows_in)
            rows_out, _, prov = m.ingest_candidates([cpath])
        self.assertEqual(prov["per_source_row_counts"]["test-source"], 5)
        self.assertEqual(prov["total_candidates_ingested"], 5)

    def test_candidate_file_sha_recorded(self):
        row = _make_valid_row()
        with tempfile.TemporaryDirectory() as tmpdir:
            cpath = Path(tmpdir) / "test.jsonl"
            _write_jsonl(cpath, [row])
            _, _, prov = m.ingest_candidates([cpath])
        self.assertIn(str(cpath), prov["candidate_files"])
        sha = prov["candidate_files"][str(cpath)]
        self.assertEqual(len(sha), 64)  # hex SHA-256

    def test_schema_violations_recorded(self):
        bad_row = {"pair_id": "bad-row", "split": "review-pending"}  # missing many required fields
        with tempfile.TemporaryDirectory() as tmpdir:
            cpath = Path(tmpdir) / "bad.jsonl"
            _write_jsonl(cpath, [bad_row])
            rows, violations, _ = m.ingest_candidates([cpath], strict=False)
        # Row still included when strict=False
        self.assertEqual(len(rows), 1)
        self.assertGreater(len(violations), 0)

    def test_strict_skips_violating_rows(self):
        bad_row = {"pair_id": "bad-row", "split": "review-pending"}
        with tempfile.TemporaryDirectory() as tmpdir:
            cpath = Path(tmpdir) / "bad.jsonl"
            _write_jsonl(cpath, [bad_row])
            rows, violations, _ = m.ingest_candidates([cpath], strict=True)
        # Row skipped under strict
        self.assertEqual(len(rows), 0)
        self.assertGreater(len(violations), 0)

    def test_empty_candidate_dir_yields_empty(self):
        rows, violations, prov = m.ingest_candidates([])
        self.assertEqual(rows, [])
        self.assertEqual(violations, [])
        self.assertEqual(prov["total_candidates_ingested"], 0)

    def test_split_determinism_across_multiple_files(self):
        """Same pair_id from two files gets the same split."""
        row_a = _make_valid_row("stable-pair-id", split="review-pending")
        with tempfile.TemporaryDirectory() as tmpdir:
            cp_a = Path(tmpdir) / "a.jsonl"
            cp_b = Path(tmpdir) / "b.jsonl"
            _write_jsonl(cp_a, [row_a])
            _write_jsonl(cp_b, [dict(row_a)])
            rows_a, _, _ = m.ingest_candidates([cp_a])
            rows_b, _, _ = m.ingest_candidates([cp_b])
        self.assertEqual(rows_a[0]["split"], rows_b[0]["split"])


# ---------------------------------------------------------------------------
# CLI dry-run
# ---------------------------------------------------------------------------

class TestCLIDryRun(unittest.TestCase):

    def test_dry_run_with_valid_candidate(self):
        row = _make_valid_row()
        with tempfile.TemporaryDirectory() as tmpdir:
            cpath = Path(tmpdir) / "candidates.jsonl"
            _write_jsonl(cpath, [row])
            rc = m.main(["--dry-run", "--candidates", str(cpath)])
        self.assertEqual(rc, 0)

    def test_dry_run_no_candidates_returns_zero(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Point at an empty dir that exists but has no *.jsonl
            rc = m.main(["--dry-run"])
        self.assertEqual(rc, 0)


# ---------------------------------------------------------------------------
# CLI --execute writes files
# ---------------------------------------------------------------------------

class TestCLIExecute(unittest.TestCase):

    def test_execute_writes_manifest_and_build_manifest(self):
        rows_in = [_make_valid_row(f"pair-{i}") for i in range(10)]
        with tempfile.TemporaryDirectory() as tmpdir:
            cpath = Path(tmpdir) / "candidates.jsonl"
            _write_jsonl(cpath, rows_in)

            # Write directly to data/stage2/ (gitignored) to avoid patching globals.
            # Restore originals after test.
            orig_data_stage2 = m.DATA_STAGE2
            orig_manifest = m.DEFAULT_STAGE2_MANIFEST
            orig_build = m.DEFAULT_BUILD_MANIFEST
            stage2_dir = Path(tmpdir) / "s2"
            m.DATA_STAGE2 = stage2_dir
            m.DEFAULT_STAGE2_MANIFEST = stage2_dir / "stage2_manifest.jsonl"
            m.DEFAULT_BUILD_MANIFEST = stage2_dir / "build_manifest.json"
            try:
                rc = m.main(["--execute", "--candidates", str(cpath)])
            finally:
                m.DATA_STAGE2 = orig_data_stage2
                m.DEFAULT_STAGE2_MANIFEST = orig_manifest
                m.DEFAULT_BUILD_MANIFEST = orig_build

            self.assertEqual(rc, 0)
            manifest_path = stage2_dir / "stage2_manifest.jsonl"
            self.assertTrue(manifest_path.exists())
            written_rows = list(m.read_jsonl(manifest_path))
            self.assertEqual(len(written_rows), 10)
            build_path = stage2_dir / "build_manifest.json"
            self.assertTrue(build_path.exists())
            with build_path.open() as f:
                build_data = json.load(f)
            self.assertEqual(build_data["rows_emitted"], 10)
            self.assertIn("ingest", build_data)


# ---------------------------------------------------------------------------
# Alignment-quality policy wiring (issue #19)
# ---------------------------------------------------------------------------

class TestPolicyWiring(unittest.TestCase):
    """Every ingested row must carry the six policy fields, and review/
    reject tiers must be quarantined into split=review-pending so the
    SFT emitter skips them by default.
    """

    def _ingest_one(self, row: dict) -> dict:
        with tempfile.TemporaryDirectory() as tmpdir:
            cpath = Path(tmpdir) / "candidates.jsonl"
            _write_jsonl(cpath, [row])
            rows, _violations, _prov = m.ingest_candidates([cpath])
        self.assertEqual(len(rows), 1)
        return rows[0]

    def _assert_policy_fields_present(self, row: dict) -> None:
        for field in (
            "alignment_confidence_tier",
            "alignment_review_required",
            "quality_flags",
            "manual_review_reasons",
            "alignment_score_components",
            "policy_version",
        ):
            self.assertIn(field, row, f"missing policy field: {field}")
        self.assertIn(row["alignment_confidence_tier"], {"accept", "review", "reject"})
        self.assertIsInstance(row["quality_flags"], list)
        self.assertIsInstance(row["manual_review_reasons"], list)
        self.assertIsInstance(row["alignment_score_components"], dict)

    # --- Accepted deterministic rows -----------------------------------

    def test_verse_id_row_accepts_and_keeps_train_split(self):
        row = _make_valid_row("bible-john-3-16", split="review-pending")
        row["alignment_type"] = "parallel-verse"
        row["alignment_method"] = "verse-id"
        out = self._ingest_one(row)
        self._assert_policy_fields_present(out)
        self.assertEqual(out["alignment_confidence_tier"], "accept")
        self.assertFalse(out["alignment_review_required"])
        self.assertIn(out["split"], {"train", "dev"})
        self.assertEqual(out["policy_version"], m.POLICY_VERSION)

    def test_tmx_line_row_accepts_and_keeps_train_split(self):
        row = _make_valid_row("tatoeba-42", split="review-pending")
        row["alignment_type"] = "parallel-sentence"
        row["alignment_method"] = "tmx-line"
        out = self._ingest_one(row)
        self._assert_policy_fields_present(out)
        self.assertEqual(out["alignment_confidence_tier"], "accept")
        self.assertIn(out["split"], {"train", "dev"})

    # --- Review / reject quarantine ------------------------------------

    def test_review_tier_forced_to_review_pending(self):
        # Embedding-aligned pair with score in the [review_min, accept_min)
        # band — policy lands at `review`.
        row = _make_valid_row("comp-review-1", split="train")
        row["alignment_type"] = "comparable-aligned"
        row["alignment_method"] = "labse"
        row["alignment_model"] = "LaBSE@dummy"
        row["alignment_score"] = 0.62  # between defaults review=0.55 / accept=0.75
        out = self._ingest_one(row)
        self._assert_policy_fields_present(out)
        self.assertEqual(out["alignment_confidence_tier"], "review")
        self.assertTrue(out["alignment_review_required"])
        self.assertEqual(out["split"], "review-pending",
                         "review tier must override existing split")

    def test_reject_tier_forced_to_review_pending(self):
        # Embedding-aligned pair with score below review_min — policy
        # lands at `reject` (hard flag alignment_score_below_review).
        row = _make_valid_row("comp-reject-1", split="train")
        row["alignment_type"] = "comparable-aligned"
        row["alignment_method"] = "labse"
        row["alignment_model"] = "LaBSE@dummy"
        row["alignment_score"] = 0.10
        out = self._ingest_one(row)
        self._assert_policy_fields_present(out)
        self.assertEqual(out["alignment_confidence_tier"], "reject")
        self.assertTrue(out["alignment_review_required"])
        self.assertEqual(out["split"], "review-pending")
        self.assertIn("alignment_score_below_review", out["quality_flags"])

    def test_empty_side_rejects_and_quarantines(self):
        row = _make_valid_row("empty-haw", split="train")
        row["text_haw"] = ""
        # sha256_haw_clean must still be present for the schema check;
        # we keep the original hashes — the test targets policy behaviour,
        # not schema. Schema violation is allowed (not strict).
        out = self._ingest_one(row)
        self.assertEqual(out["alignment_confidence_tier"], "reject")
        self.assertEqual(out["split"], "review-pending")
        self.assertIn("empty_side", out["quality_flags"])

    # --- policy_version + summary --------------------------------------

    def test_policy_version_recorded_on_every_row(self):
        rows_in = [
            _make_valid_row(f"row-{i}", split="review-pending")
            for i in range(5)
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            cpath = Path(tmpdir) / "candidates.jsonl"
            _write_jsonl(cpath, rows_in)
            rows, _, prov = m.ingest_candidates([cpath])
        self.assertEqual(len(rows), 5)
        for r in rows:
            self.assertEqual(r["policy_version"], m.POLICY_VERSION)
        self.assertEqual(prov["policy_version"], m.POLICY_VERSION)
        self.assertIn("tier_counts", prov)
        # All five accept (clean phrases, manual alignment).
        self.assertEqual(prov["tier_counts"].get("accept", 0), 5)

    def test_summarise_policy_aggregates_tiers(self):
        accept = _make_valid_row("ok-1")
        accept["alignment_method"] = "verse-id"
        accept["alignment_type"] = "parallel-verse"
        m.apply_policy(accept)

        reject = _make_valid_row("bad-1")
        reject["alignment_type"] = "comparable-aligned"
        reject["alignment_method"] = "labse"
        reject["alignment_score"] = 0.1
        m.apply_policy(reject)

        summary = m.summarise_policy([accept, reject])
        self.assertEqual(summary["row_count"], 2)
        self.assertEqual(summary["tier_counts"].get("accept"), 1)
        self.assertEqual(summary["tier_counts"].get("reject"), 1)
        self.assertEqual(summary["policy"]["policy_version"], m.POLICY_VERSION)


# ---------------------------------------------------------------------------
# CLI --execute writes score_summary.json (issue #19)
# ---------------------------------------------------------------------------

class TestCLIExecuteScoreSummary(unittest.TestCase):

    def test_execute_writes_score_summary(self):
        rows_in = [_make_valid_row(f"pair-{i}") for i in range(3)]
        with tempfile.TemporaryDirectory() as tmpdir:
            cpath = Path(tmpdir) / "candidates.jsonl"
            _write_jsonl(cpath, rows_in)

            orig_data_stage2 = m.DATA_STAGE2
            orig_manifest = m.DEFAULT_STAGE2_MANIFEST
            orig_build = m.DEFAULT_BUILD_MANIFEST
            stage2_dir = Path(tmpdir) / "s2"
            m.DATA_STAGE2 = stage2_dir
            m.DEFAULT_STAGE2_MANIFEST = stage2_dir / "stage2_manifest.jsonl"
            m.DEFAULT_BUILD_MANIFEST = stage2_dir / "build_manifest.json"
            try:
                rc = m.main(["--execute", "--candidates", str(cpath)])
            finally:
                m.DATA_STAGE2 = orig_data_stage2
                m.DEFAULT_STAGE2_MANIFEST = orig_manifest
                m.DEFAULT_BUILD_MANIFEST = orig_build

            self.assertEqual(rc, 0)
            score_summary_path = stage2_dir / "score_summary.json"
            self.assertTrue(score_summary_path.exists(),
                            "score_summary.json must be persisted under data/stage2/")
            with score_summary_path.open() as f:
                summary = json.load(f)
            self.assertEqual(summary["row_count"], 3)
            self.assertEqual(summary["policy"]["policy_version"], m.POLICY_VERSION)
            # Manifest must echo policy fields per row.
            with (stage2_dir / "stage2_manifest.jsonl").open() as f:
                first = json.loads(f.readline())
            self.assertIn("alignment_confidence_tier", first)
            self.assertIn("policy_version", first)


if __name__ == "__main__":
    unittest.main()