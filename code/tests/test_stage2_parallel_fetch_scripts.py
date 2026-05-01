"""Tests for Stage-2 100/200 source planning and raw fetch helpers.

Stdlib-only; no network requests are made.
"""

from __future__ import annotations

import importlib.util
import sys
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


collect = _load_script("collect_stage2_parallel", SCRIPTS_DIR / "107_collect_stage2_parallel.py")
fetch = _load_script("fetch_stage2_parallel_raw", SCRIPTS_DIR / "207_fetch_stage2_parallel_raw.py")


class TestCollectStage2Parallel(unittest.TestCase):
    def setUp(self):
        self.inventory_path = REPO_ROOT / "data-sources" / "stage2-parallel-fetch-plan.json"
        self.inventory = collect.load_inventory(self.inventory_path)

    def test_default_target_is_80k_sft_rows_40k_pairs(self):
        plan = collect.build_plan(
            self.inventory,
            inventory_path=self.inventory_path,
            include_eval=False,
        )
        target = plan["stage2_target"]
        self.assertEqual(target["sft_rows"], 80_000)
        self.assertEqual(target["canonical_pair_target"], 40_000)
        self.assertEqual(target["directions_per_pair"], 2)

    def test_default_plan_excludes_eval_only_sources(self):
        plan = collect.build_plan(
            self.inventory,
            inventory_path=self.inventory_path,
            include_eval=False,
        )
        source_ids = {s["source_id"] for s in plan["sources"]}
        self.assertNotIn("global-piqa-parallel-haw", source_ids)
        self.assertNotIn("taxi1500-haw", source_ids)
        skipped = {s["source_id"]: s["reason"] for s in plan["skipped_sources"]}
        self.assertEqual(skipped["global-piqa-parallel-haw"], "eval_only")

    def test_excluded_sources_never_enter_plan(self):
        plan = collect.build_plan(
            self.inventory,
            inventory_path=self.inventory_path,
            include_eval=True,
        )
        source_ids = {s["source_id"] for s in plan["sources"]}
        self.assertNotIn("jw300-haw", source_ids)

    def test_static_download_source_records_artifacts(self):
        plan = collect.build_plan(
            self.inventory,
            inventory_path=self.inventory_path,
            include_eval=False,
        )
        by_id = {s["source_id"]: s for s in plan["sources"]}
        tatoeba = by_id["tatoeba-haw-eng"]
        self.assertEqual(tatoeba["fetch_kind"], "static-download")
        self.assertGreaterEqual(len(tatoeba["download_artifacts"]), 3)
        filenames = {a["filename"] for a in tatoeba["download_artifacts"]}
        self.assertIn("eng_sentences_detailed.tsv.bz2", filenames)
        self.assertEqual(tatoeba["source_specific_adapter"], "data-sources/tatoeba/fetch.py")

    def test_gated_static_source_records_gates(self):
        plan = collect.build_plan(
            self.inventory,
            inventory_path=self.inventory_path,
            include_eval=False,
        )
        by_id = {s["source_id"]: s for s in plan["sources"]}
        opus = by_id["opus-haw-subsets"]
        self.assertEqual(opus["fetch_kind"], "static-download")
        self.assertIn("rights_review_required", opus["fetch_gates"])
        self.assertIn("endpoint_check_required", opus["fetch_gates"])
        filenames = [a["filename"] for a in opus["download_artifacts"]]
        self.assertEqual(len(filenames), len(set(filenames)))


class TestFetchStage2ParallelRaw(unittest.TestCase):
    def setUp(self):
        inventory_path = REPO_ROOT / "data-sources" / "stage2-parallel-fetch-plan.json"
        inventory = collect.load_inventory(inventory_path)
        self.plan = collect.build_plan(
            inventory,
            inventory_path=inventory_path,
            include_eval=True,
        )
        self.by_id = {s["source_id"]: s for s in self.plan["sources"]}

    def test_tatoeba_is_executable_without_extra_gates(self):
        reasons = fetch.execute_gate_reasons(
            self.by_id["tatoeba-haw-eng"],
            include_eval=False,
            allow_rights_review=False,
            allow_pending_endpoint=False,
            allow_blocked=False,
        )
        self.assertEqual(reasons, [])

    def test_opus_requires_rights_and_endpoint_flags(self):
        reasons = fetch.execute_gate_reasons(
            self.by_id["opus-haw-subsets"],
            include_eval=False,
            allow_rights_review=False,
            allow_pending_endpoint=False,
            allow_blocked=False,
        )
        self.assertIn("requires --allow-rights-review", reasons)
        self.assertIn("requires --allow-pending-endpoint", reasons)

    def test_eval_source_requires_include_eval(self):
        reasons = fetch.execute_gate_reasons(
            self.by_id["global-piqa-parallel-haw"],
            include_eval=False,
            allow_rights_review=False,
            allow_pending_endpoint=True,
            allow_blocked=False,
        )
        self.assertIn("requires --include-eval", reasons)

    def test_non_static_sources_are_not_executable_by_generic_fetcher(self):
        reasons = fetch.execute_gate_reasons(
            self.by_id["wiki-haw-en-langlinks"],
            include_eval=False,
            allow_rights_review=False,
            allow_pending_endpoint=False,
            allow_blocked=False,
        )
        self.assertIn("not_static_download:template-or-api-adapter-needed", reasons)

    def test_limit_zero_means_uncapped(self):
        self.assertIsNone(fetch._limit_or_none(0))
        self.assertEqual(fetch._limit_or_none(3), 3)


if __name__ == "__main__":
    unittest.main()
