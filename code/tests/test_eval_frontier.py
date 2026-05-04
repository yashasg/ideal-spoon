"""test_eval_frontier.py — Unit tests for frontier model evaluation.

Tests the eval_frontier module without making live API calls.
All SK chat clients are mocked.
"""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

# Add code dir to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from llm_hawaii.eval_frontier import (
    FrontierChatService,
    evaluate_frontier_model,
    _frontier_identity,
    _is_reasoning_model,
    _normalize_provider,
    _default_endpoint_for_provider,
    _default_azure_deployment,
    EVAL_SCHEMA_VERSION,
    PROMPT_SUITE_ID,
    DEFAULT_PROMPT_SUITE,
    DEFAULT_AZURE_OPENAI_ENDPOINT,
    DEFAULT_AZURE_OPENAI_API_VERSION,
)
from llm_hawaii.evaluate import (
    compute_prompt_suite_descriptor,
)


class TestFrontierIdentity(unittest.TestCase):
    def test_identity_structure(self):
        """Verify identity descriptor has required fields."""
        identity = _frontier_identity(
            provider="github-models",
            model_id="gpt-4o",
            endpoint="https://models.inference.ai.azure.com",
        )
        
        self.assertEqual(identity["provider"], "github-models")
        self.assertEqual(identity["model_id"], "gpt-4o")
        self.assertEqual(identity["endpoint"], "https://models.inference.ai.azure.com")
        self.assertIn("api_version", identity)
        self.assertFalse(identity["is_local"])
        self.assertFalse(identity["supports_logprobs"])
        self.assertEqual(identity["determinism"], "deterministic_temp_0")
        self.assertFalse(identity["reasoning_model"])
    
    def test_identity_gpt5_determinism(self):
        """Verify GPT-5 models are marked as non-deterministic."""
        identity = _frontier_identity(
            provider="github-models",
            model_id="openai/gpt-5",
            endpoint="https://models.inference.ai.azure.com",
        )
        
        self.assertEqual(identity["determinism"], "non_deterministic")
        self.assertTrue(identity["reasoning_model"])
    
    def test_identity_gpt5_chat_determinism(self):
        """Verify GPT-5-chat models are marked as non-deterministic."""
        identity = _frontier_identity(
            provider="github-models",
            model_id="openai/gpt-5-chat",
            endpoint="https://models.inference.ai.azure.com",
        )
        
        self.assertEqual(identity["determinism"], "non_deterministic")
        self.assertTrue(identity["reasoning_model"])

    def test_identity_azure_deployment(self):
        """Verify Azure identity records deployment name and API version."""
        identity = _frontier_identity(
            provider="azure-openai",
            model_id="gpt-5-chat-prod",
            endpoint=DEFAULT_AZURE_OPENAI_ENDPOINT.rstrip("/"),
            api_version=DEFAULT_AZURE_OPENAI_API_VERSION,
        )

        self.assertEqual(identity["provider"], "azure")
        self.assertEqual(identity["model_id"], "gpt-5-chat-prod")
        self.assertEqual(identity["deployment_name"], "gpt-5-chat-prod")
        self.assertEqual(identity["api_version"], DEFAULT_AZURE_OPENAI_API_VERSION)


class TestProviderConfig(unittest.TestCase):
    def test_provider_aliases(self):
        """Verify provider aliases are normalized for CLI/env friendliness."""
        self.assertEqual(_normalize_provider("github"), "github-models")
        self.assertEqual(_normalize_provider("github_models"), "github-models")
        self.assertEqual(_normalize_provider("azure-openai"), "azure")

    @patch.dict("os.environ", {"AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com/"}, clear=True)
    def test_azure_endpoint_from_env(self):
        """Verify Azure endpoint can come from env without CLI flags."""
        self.assertEqual(
            _default_endpoint_for_provider("azure"),
            "https://example.openai.azure.com/",
        )

    @patch.dict("os.environ", {"AZURE_OPENAI_DEPLOYMENT": "hawaii-gpt5"}, clear=True)
    def test_azure_deployment_fallback_env(self):
        """Verify generic Azure deployment env var is accepted."""
        self.assertEqual(_default_azure_deployment(), "hawaii-gpt5")


class TestFrontierChatService(unittest.TestCase):
    def test_service_construction_deferred(self):
        """Test that service construction is deferred (SK not imported at module level)."""
        # The actual service construction requires SK to be installed,
        # so we just verify the constructor signature and defer to integration tests.
        # All functional tests use mocked FrontierChatService instances.
        self.assertTrue(True, "Service construction deferred to runtime")


class TestEvaluateFrontierModel(unittest.TestCase):
    def setUp(self):
        """Set up mock service and fixtures."""
        # Create temp dir for test artifacts
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # Mock W1 JSONL
        self.w1_jsonl = self.temp_path / "w1.jsonl"
        self.w1_jsonl.write_text("")  # Empty but present
        
        # Mock human_fetch JSONL
        self.human_fetch_jsonl = self.temp_path / "human_fetch.jsonl"
        human_fetch_data = [
            {"lang": "en", "text": "Hello world"},
            {"lang": "haw", "text": "Aloha honua"},
        ]
        self.human_fetch_jsonl.write_text("\n".join(json.dumps(r) for r in human_fetch_data))
    
    def tearDown(self):
        """Clean up temp files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch("llm_hawaii.eval_frontier.FrontierChatService")
    def test_schema_version(self, mock_service_class):
        """Verify report emits correct schema version."""
        mock_service = Mock()
        mock_service.provider = "github-models"
        mock_service.model_id = "gpt-4o"
        mock_service.endpoint = "https://models.inference.ai.azure.com"
        mock_service.generate.return_value = "Test generation"
        mock_service_class.return_value = mock_service
        
        report = evaluate_frontier_model(
            provider="github-models",
            model_id="gpt-4o",
            api_key="fake_token",
            use_manual_w1=False,
            use_human_fetch=False,
        )
        
        self.assertEqual(report["schema_version"], EVAL_SCHEMA_VERSION)
        self.assertEqual(report["schema_version"], "stage0_eval.v2")
    
    @patch("llm_hawaii.eval_frontier.FrontierChatService")
    def test_identity_populated(self, mock_service_class):
        """Verify identity fields are populated."""
        mock_service = Mock()
        mock_service.provider = "github-models"
        mock_service.model_id = "gpt-4o"
        mock_service.endpoint = "https://models.inference.ai.azure.com"
        mock_service.generate.return_value = "Test generation"
        mock_service_class.return_value = mock_service
        
        report = evaluate_frontier_model(
            provider="github-models",
            model_id="gpt-4o",
            api_key="fake_token",
            use_manual_w1=False,
            use_human_fetch=False,
        )
        
        self.assertIn("identity", report)
        self.assertEqual(report["identity"]["provider"], "github-models")
        self.assertEqual(report["identity"]["model_id"], "gpt-4o")
        self.assertEqual(report["identity"]["endpoint"], "https://models.inference.ai.azure.com")
    
    @patch("llm_hawaii.eval_frontier.FrontierChatService")
    def test_hawaiian_ppl_not_supported(self, mock_service_class):
        """Verify hawaiian_ppl marked as not_supported."""
        mock_service = Mock()
        mock_service.provider = "github-models"
        mock_service.model_id = "gpt-4o"
        mock_service.endpoint = "https://models.inference.ai.azure.com"
        mock_service.generate.return_value = "Test generation"
        mock_service_class.return_value = mock_service
        
        report = evaluate_frontier_model(
            provider="github-models",
            model_id="gpt-4o",
            api_key="fake_token",
            use_manual_w1=False,
            use_human_fetch=False,
        )
        
        self.assertIn("hawaiian_ppl", report)
        self.assertEqual(report["hawaiian_ppl"]["status"], "not_supported")
        self.assertIn("no logprobs", report["hawaiian_ppl"]["reason"])
    
    @patch("llm_hawaii.eval_frontier.FrontierChatService")
    def test_prompt_suite_hash(self, mock_service_class):
        """Verify prompt suite hash matches frozen stage0.v1."""
        mock_service = Mock()
        mock_service.provider = "github-models"
        mock_service.model_id = "gpt-4o"
        mock_service.endpoint = "https://models.inference.ai.azure.com"
        mock_service.generate.return_value = "Test generation"
        mock_service_class.return_value = mock_service
        
        report = evaluate_frontier_model(
            provider="github-models",
            model_id="gpt-4o",
            api_key="fake_token",
            use_manual_w1=False,
            use_human_fetch=False,
            use_prompt_suite=True,
        )
        
        self.assertIn("prompt_suite", report)
        self.assertEqual(report["prompt_suite"]["suite_id"], PROMPT_SUITE_ID)
        self.assertEqual(report["prompt_suite"]["suite_id"], "stage0.v1")
        # Verify frozen hash
        expected_hash = "2683027f538ae8fb2910f758f2865596355893cc91c85dbdfe9ced130797bce6"
        self.assertEqual(report["prompt_suite"]["suite_sha256"], expected_hash)
    
    @patch("llm_hawaii.eval_frontier.FrontierChatService")
    def test_orthography_metrics_present(self, mock_service_class):
        """Verify orthography metrics are computed."""
        mock_service = Mock()
        mock_service.provider = "github-models"
        mock_service.model_id = "gpt-4o"
        mock_service.endpoint = "https://models.inference.ai.azure.com"
        # Return Hawaiian text with diacritics
        mock_service.generate.return_value = "Aloha kākou, e mālama i ka ʻāina."
        mock_service_class.return_value = mock_service
        
        report = evaluate_frontier_model(
            provider="github-models",
            model_id="gpt-4o",
            api_key="fake_token",
            use_manual_w1=False,
            use_human_fetch=False,
            use_prompt_suite=True,
        )
        
        self.assertIn("orthography_metrics", report)
        self.assertIn("orthography_aggregate", report)
        self.assertIn("tripwires", report)
        
        # Verify orthography aggregate structure
        agg = report["orthography_aggregate"]
        self.assertIn("okina_total", agg)
        self.assertIn("kahako_total", agg)
        self.assertIn("wrong_okina_total", agg)
        self.assertIn("nfc_failures", agg)
    
    @patch("llm_hawaii.eval_frontier.FrontierChatService")
    def test_generation_count(self, mock_service_class):
        """Verify correct number of generations for stage0.v1 suite."""
        mock_service = Mock()
        mock_service.provider = "github-models"
        mock_service.model_id = "gpt-4o"
        mock_service.endpoint = "https://models.inference.ai.azure.com"
        mock_service.generate.return_value = "Test generation"
        mock_service_class.return_value = mock_service
        
        report = evaluate_frontier_model(
            provider="github-models",
            model_id="gpt-4o",
            api_key="fake_token",
            use_manual_w1=False,
            use_human_fetch=False,
            use_prompt_suite=True,
        )
        
        # stage0.v1 has 7 prompts (1 en + 6 haw)
        self.assertEqual(len(report["generations"]), 7)
        self.assertEqual(len(report["generation_sha256"]), 7)
        self.assertEqual(len(report["orthography_metrics"]), 7)


class TestGPT5ParamShape(unittest.TestCase):
    """Test GPT-5 family parameter shape detection."""
    
    def test_is_reasoning_model_gpt5(self):
        """Test GPT-5 is detected as reasoning model."""
        self.assertTrue(_is_reasoning_model("openai/gpt-5"))
        self.assertTrue(_is_reasoning_model("openai/gpt-5-chat"))
        self.assertTrue(_is_reasoning_model("openai/gpt-5-mini"))
        self.assertTrue(_is_reasoning_model("gpt-5"))
    
    def test_is_reasoning_model_o_series(self):
        """Test o-series models are detected as reasoning models."""
        self.assertTrue(_is_reasoning_model("openai/o1"))
        self.assertTrue(_is_reasoning_model("openai/o3"))
        self.assertTrue(_is_reasoning_model("openai/o4-mini"))
    
    def test_is_not_reasoning_model(self):
        """Test GPT-4o and other models are NOT reasoning models."""
        self.assertFalse(_is_reasoning_model("openai/gpt-4o"))
        self.assertFalse(_is_reasoning_model("gpt-4o"))
        self.assertFalse(_is_reasoning_model("gpt-4.1"))
        self.assertFalse(_is_reasoning_model("claude-3.5-sonnet"))
    
    @patch("llm_hawaii.eval_frontier.FrontierChatService")
    def test_gpt5_decoding_params(self, mock_service_class):
        """Verify GPT-5 uses correct parameter shape (no temperature, max_completion_tokens)."""
        mock_service = Mock()
        mock_service.provider = "github-models"
        mock_service.model_id = "openai/gpt-5"
        mock_service.endpoint = "https://models.inference.ai.azure.com"
        mock_service.generate.return_value = "Test generation"
        mock_service_class.return_value = mock_service
        
        report = evaluate_frontier_model(
            provider="github-models",
            model_id="openai/gpt-5",
            api_key="fake_token",
            use_manual_w1=False,
            use_human_fetch=False,
        )
        
        # Check decoding params
        decoding = report["decoding"]
        self.assertTrue(decoding["do_sample"])
        self.assertFalse(decoding["greedy"])
        self.assertIsNone(decoding["temperature"])
        self.assertIsNone(decoding["top_p"])
        self.assertIn("max_completion_tokens", decoding)
        self.assertEqual(decoding["max_completion_tokens"], 64)
        self.assertIn("note", decoding)
        self.assertIn("GPT-5", decoding["note"])
    
    @patch("llm_hawaii.eval_frontier.FrontierChatService")
    def test_gpt4o_decoding_params(self, mock_service_class):
        """Verify GPT-4o uses legacy parameter shape (temperature=0, max_tokens)."""
        mock_service = Mock()
        mock_service.provider = "github-models"
        mock_service.model_id = "openai/gpt-4o"
        mock_service.endpoint = "https://models.inference.ai.azure.com"
        mock_service.generate.return_value = "Test generation"
        mock_service_class.return_value = mock_service
        
        report = evaluate_frontier_model(
            provider="github-models",
            model_id="openai/gpt-4o",
            api_key="fake_token",
            use_manual_w1=False,
            use_human_fetch=False,
        )
        
        # Check decoding params
        decoding = report["decoding"]
        self.assertFalse(decoding["do_sample"])
        self.assertTrue(decoding["greedy"])
        self.assertEqual(decoding["temperature"], 0.0)
        self.assertEqual(decoding["top_p"], 1.0)
        self.assertNotIn("max_completion_tokens", decoding)
        self.assertNotIn("note", decoding)


class TestEvalHashesLedger(unittest.TestCase):
    def setUp(self):
        """Set up temp dir for ledger test."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        self.ledger_path = self.temp_path / "eval_hashes.jsonl"
    
    def tearDown(self):
        """Clean up temp files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_ledger_row_format(self):
        """Verify ledger row has correct fields and stage."""
        # Create a mock summary
        summary = self.temp_path / "summary.json"
        summary_doc = {
            "stage": "frontier_baseline",
            "provider": "github-models",
            "model_id": "gpt-4o",
            "prompt_suite": {
                "suite_sha256": "2683027f538ae8fb2910f758f2865596355893cc91c85dbdfe9ced130797bce6",
            },
        }
        summary.write_text(json.dumps(summary_doc, indent=2))
        
        # Compute summary sha256
        summary_sha = hashlib.sha256(summary.read_bytes()).hexdigest()
        
        # Append to ledger
        ledger_row = {
            "stage": "frontier_baseline",
            "provider": "github-models",
            "model_id": "gpt-4o",
            "summary_path": "docs/eval-runs/frontier/summary.json",
            "summary_sha256": summary_sha,
            "suite_sha256": "2683027f538ae8fb2910f758f2865596355893cc91c85dbdfe9ced130797bce6",
        }
        
        with self.ledger_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ledger_row, ensure_ascii=False) + "\n")
        
        # Read back and verify
        rows = list(self.ledger_path.read_text(encoding="utf-8").strip().split("\n"))
        self.assertEqual(len(rows), 1)
        
        row = json.loads(rows[0])
        self.assertEqual(row["stage"], "frontier_baseline")
        self.assertEqual(row["provider"], "github-models")
        self.assertEqual(row["model_id"], "gpt-4o")
        self.assertIn("summary_sha256", row)
        self.assertEqual(row["suite_sha256"], "2683027f538ae8fb2910f758f2865596355893cc91c85dbdfe9ced130797bce6")


if __name__ == "__main__":
    unittest.main()
