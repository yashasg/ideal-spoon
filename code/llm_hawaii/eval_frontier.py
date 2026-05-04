"""eval_frontier.py — Frontier model evaluation via GitHub Models/Azure + Semantic Kernel.

Evaluates frontier chat models (OpenAI GPT, Anthropic Claude, etc.) using the
FROZEN Stage 0/1 eval contract: same `stage0.v1` prompt suite, same W1 probe,
same human_fetch translation probe, same orthography metrics. Emits the same
`stage0_eval.v2` schema as evaluate.py with these adaptations:

- `identity.provider`, `identity.model_id`, `identity.endpoint` populated
- `hawaiian_ppl` marked `not_supported` (closed APIs have no logprobs)
- Generation/translation/orthography probes work normally

Auth: GitHub Models uses `gh auth token`. Azure OpenAI uses
`AZURE_OPENAI_API_KEY` plus an Azure deployment name.

Orchestration: Semantic Kernel `OpenAIChatCompletion` connector pointed at
GitHub Models or Azure OpenAI through OpenAI-compatible clients.

DO NOT run live API calls in this session — mocked/dry-run/test only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import unicodedata
from pathlib import Path
from typing import Any

from . import metrics as metrics_mod
from .evaluate import (
    EVAL_SCHEMA_VERSION,
    PROMPT_SUITE_ID,
    DEFAULT_PROMPT_SUITE,
    compute_prompt_suite_descriptor,
    manual_w1_status,
    _sha256_text,
    _orthography_aggregate,
    _tripwires,
    _char_ngram_f1,
    DEFAULT_MANUAL_W1_JSONL,
    DEFAULT_HUMAN_FETCH_JSONL,
    HUMAN_FETCH_PROBE_SCHEMA,
    HUMAN_FETCH_EN_TO_HAW_TEMPLATE,
    HUMAN_FETCH_HAW_TO_EN_TEMPLATE,
)

# Default GitHub Models endpoint (OpenAI-compatible)
DEFAULT_GITHUB_MODELS_ENDPOINT = "https://models.github.ai/inference/chat/completions"
DEFAULT_GITHUB_MODELS_API_VERSION = "2024-12-01-preview"

# Azure OpenAI defaults for GPT-5 frontier evals. Azure uses deployment names
# in place of model names.
DEFAULT_AZURE_OPENAI_ENDPOINT = "https://aifoundry672407977528-resource.openai.azure.com/"
DEFAULT_AZURE_OPENAI_API_VERSION = "2024-10-21"
DEFAULT_AZURE_OPENAI_GPT5_DEPLOYMENT = "gpt-5-chat"

# Default frontier models to evaluate (curated for GitHub Models catalog)
# Flagged for user verification — best-effort from documented models.
DEFAULT_FRONTIER_MODELS = [
    "gpt-4o",
    "claude-3.5-sonnet",
    "claude-opus-4",
]


def _require(pkg: str, install_hint: str) -> Any:
    try:
        return __import__(pkg)
    except ImportError as e:
        raise RuntimeError(
            f"Missing optional dependency '{pkg}'. Install with: {install_hint}"
        ) from e


def _normalize_provider(provider: str | None) -> str:
    """Normalize provider aliases used by scripts/env vars."""
    value = (provider or "github-models").strip().lower().replace("_", "-")
    if value in {"github", "github-model", "github-models"}:
        return "github-models"
    if value in {"azure", "azure-openai"}:
        return "azure"
    return value


def _is_azure_provider(provider: str | None) -> bool:
    return _normalize_provider(provider) == "azure"


def _default_endpoint_for_provider(provider: str) -> str:
    if _is_azure_provider(provider):
        return os.environ.get("AZURE_OPENAI_ENDPOINT", DEFAULT_AZURE_OPENAI_ENDPOINT)
    return os.environ.get("GITHUB_MODELS_ENDPOINT", DEFAULT_GITHUB_MODELS_ENDPOINT)


def _default_api_version_for_provider(provider: str) -> str:
    if _is_azure_provider(provider):
        return os.environ.get("AZURE_OPENAI_API_VERSION", DEFAULT_AZURE_OPENAI_API_VERSION)
    return DEFAULT_GITHUB_MODELS_API_VERSION


def _default_azure_deployment() -> str:
    """Resolve the Azure OpenAI deployment name used as the model argument."""
    return (
        os.environ.get("AZURE_OPENAI_GPT5_DEPLOYMENT")
        or os.environ.get("AZURE_OPENAI_DEPLOYMENT")
        or DEFAULT_AZURE_OPENAI_GPT5_DEPLOYMENT
    )


def _get_azure_openai_key(api_key: str | None = None) -> str:
    """Get Azure OpenAI API key from explicit arg or env."""
    token = api_key or os.environ.get("AZURE_OPENAI_API_KEY")
    if token:
        return token
    raise RuntimeError("Azure OpenAI key not found. Set AZURE_OPENAI_API_KEY.")


def _get_gh_token() -> str:
    """Get GitHub token from env or gh CLI."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token
    
    # Try gh CLI
    import subprocess
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        token = result.stdout.strip()
        if token:
            return token
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    raise RuntimeError(
        "GitHub token not found. Set GITHUB_TOKEN env var or run:\n"
        "  gh auth refresh -s models:read\n"
        "  export GITHUB_TOKEN=$(gh auth token)"
    )


class FrontierChatService:
    """Wrapper around Semantic Kernel chat completion for frontier models.
    
    Provides a provider-agnostic interface for greedy chat completion.
    """
    
    def __init__(
        self,
        *,
        provider: str = "github-models",
        model_id: str,
        endpoint: str | None = None,
        api_key: str | None = None,
        api_version: str | None = None,
    ):
        self.provider = _normalize_provider(provider)
        self.model_id = model_id
        self.endpoint = (endpoint or _default_endpoint_for_provider(self.provider)).rstrip("/")
        self.api_version = api_version or _default_api_version_for_provider(self.provider)
        self.api_key = (
            _get_azure_openai_key(api_key)
            if _is_azure_provider(self.provider)
            else (api_key or _get_gh_token())
        )
        
        # Lazy-import Semantic Kernel
        self._sk = _require(
            "semantic_kernel",
            "pip install semantic-kernel>=1.13.0 (see requirements-eval-frontier.txt)",
        )
        
        # Create SK chat completion client. GitHub Models uses the generic
        # OpenAI-compatible client; Azure OpenAI requires the Azure client.
        from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion
        import openai
        
        if _is_azure_provider(self.provider):
            async_client = openai.AsyncAzureOpenAI(
                api_key=self.api_key,
                azure_endpoint=self.endpoint,
                api_version=self.api_version,
            )
        else:
            async_client = openai.AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.endpoint.replace("/chat/completions", ""),
            )
        
        self._client = OpenAIChatCompletion(
            ai_model_id=model_id,
            async_client=async_client,
        )
    
    async def generate_async(self, prompt: str, max_tokens: int = 64) -> str:
        """Generate text from a single prompt (greedy, deterministic)."""
        from semantic_kernel.contents import ChatHistory
        from semantic_kernel.connectors.ai.open_ai import OpenAIChatPromptExecutionSettings
        
        chat_history = ChatHistory()
        chat_history.add_user_message(prompt)
        
        # Model-specific parameter handling:
        # - GPT-5/o3/o4 reasoning models: use max_completion_tokens, no temperature control
        # - Other models: use max_tokens, temperature=0
        is_reasoning = _is_reasoning_model(self.model_id)
        
        if is_reasoning:
            settings = OpenAIChatPromptExecutionSettings(
                max_completion_tokens=max_tokens,
            )
        else:
            settings = OpenAIChatPromptExecutionSettings(
                temperature=0.0,
                max_tokens=max_tokens,
                top_p=1.0,
            )
        
        response = await self._client.get_chat_message_content(
            chat_history=chat_history,
            settings=settings,
        )
        
        return str(response) if response else ""
    
    def generate(self, prompt: str, max_tokens: int = 64) -> str:
        """Sync wrapper for generate_async."""
        import asyncio
        return asyncio.run(self.generate_async(prompt, max_tokens))


def _is_reasoning_model(model_id: str) -> bool:
    """Check if model is a reasoning-tier model (GPT-5/o-series)."""
    return any(
        marker in model_id.lower()
        for marker in ["gpt-5", "/o1", "/o3", "/o4"]
    )


def _frontier_identity(
    *,
    provider: str,
    model_id: str,
    endpoint: str,
    api_version: str | None = None,
) -> dict:
    """Identity descriptor for frontier model eval."""
    normalized_provider = _normalize_provider(provider)
    is_reasoning = _is_reasoning_model(model_id)
    identity = {
        "provider": normalized_provider,
        "model_id": model_id,
        "endpoint": endpoint,
        "api_version": api_version or _default_api_version_for_provider(normalized_provider),
        "is_local": False,
        "supports_logprobs": False,
        "determinism": "non_deterministic" if is_reasoning else "deterministic_temp_0",
        "reasoning_model": is_reasoning,
    }
    if _is_azure_provider(normalized_provider):
        identity["deployment_name"] = model_id
    return identity


def _human_fetch_translation_probe_frontier(
    jsonl_path: str | Path | None,
    *,
    enabled: bool = True,
    service: FrontierChatService | None = None,
    max_new_tokens: int = 64,
) -> dict:
    """Bidirectional translation probe for frontier models.
    
    Mirrors human_fetch_translation_probe from evaluate.py but uses
    FrontierChatService instead of HF model/tokenizer.
    """
    if not enabled:
        return {
            "status": "not_configured",
            "reason": "human-fetch translation probe disabled (--no-human-fetch)",
            "schema": HUMAN_FETCH_PROBE_SCHEMA,
        }
    
    p = Path(jsonl_path) if jsonl_path else Path(DEFAULT_HUMAN_FETCH_JSONL)
    out: dict[str, Any] = {
        "schema": HUMAN_FETCH_PROBE_SCHEMA,
        "path": str(p),
        "eval_eligible": True,
        "training_eligible": False,
    }
    
    if not p.exists():
        out["status"] = "missing"
        out["reason"] = (
            f"human_fetch JSONL not found at {p}; regenerate with "
            "`python3 scripts/_convert_ulukau_human_fetch.py`"
        )
        return out
    
    try:
        raw_bytes = p.read_bytes()
    except OSError as e:
        out["status"] = "invalid"
        out["reason"] = f"read_failed: {e}"
        return out
    
    out["source_jsonl_sha256"] = hashlib.sha256(raw_bytes).hexdigest()
    out["source_jsonl_size_bytes"] = len(raw_bytes)
    
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as e:
        out["status"] = "invalid"
        out["reason"] = f"utf8_decode_failed: {e}"
        return out
    
    en_text: str | None = None
    haw_text: str | None = None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            obj = json.loads(line)
            lang = obj.get("lang")
            if lang == "en":
                en_text = unicodedata.normalize("NFC", obj.get("text", ""))
            elif lang == "haw":
                haw_text = unicodedata.normalize("NFC", obj.get("text", ""))
        except (json.JSONDecodeError, KeyError):
            continue
    
    if not en_text or not haw_text:
        out["status"] = "invalid"
        out["reason"] = "missing_en_haw_pair"
        return out
    
    out["pair_count"] = 1
    out["pair_sha256"] = {
        "en": _sha256_text(en_text),
        "haw": _sha256_text(haw_text),
    }
    
    en_to_haw_prompt = HUMAN_FETCH_EN_TO_HAW_TEMPLATE.format(text=en_text)
    haw_to_en_prompt = HUMAN_FETCH_HAW_TO_EN_TEMPLATE.format(text=haw_text)
    
    out["template_sha256"] = {
        "en_to_haw": _sha256_text(HUMAN_FETCH_EN_TO_HAW_TEMPLATE),
        "haw_to_en": _sha256_text(HUMAN_FETCH_HAW_TO_EN_TEMPLATE),
    }
    
    if service is None:
        out["status"] = "ready"
        out["reason"] = "pair parsed; no service provided — generation not run"
        out["directions"] = {
            "en_to_haw": {
                "status": "not_run",
                "prompt_sha256": _sha256_text(en_to_haw_prompt),
                "reference_sha256": _sha256_text(haw_text),
            },
            "haw_to_en": {
                "status": "not_run",
                "prompt_sha256": _sha256_text(haw_to_en_prompt),
                "reference_sha256": _sha256_text(en_text),
            },
        }
        return out
    
    # Generate both directions
    gen_en_to_haw = unicodedata.normalize("NFC", service.generate(en_to_haw_prompt, max_tokens=max_new_tokens))
    gen_haw_to_en = unicodedata.normalize("NFC", service.generate(haw_to_en_prompt, max_tokens=max_new_tokens))
    
    out["directions"] = {
        "en_to_haw": {
            "prompt_sha256": _sha256_text(en_to_haw_prompt),
            "generation_sha256": _sha256_text(gen_en_to_haw),
            "reference_sha256": _sha256_text(haw_text),
            "metric": "char_ngram_f1_baseline",
            **_char_ngram_f1(haw_text, gen_en_to_haw, n=2),
        },
        "haw_to_en": {
            "prompt_sha256": _sha256_text(haw_to_en_prompt),
            "generation_sha256": _sha256_text(gen_haw_to_en),
            "reference_sha256": _sha256_text(en_text),
            "metric": "char_ngram_f1_baseline",
            **_char_ngram_f1(en_text, gen_haw_to_en, n=2),
        },
    }
    out["status"] = "evaluated"
    return out


def evaluate_frontier_model(
    *,
    provider: str = "github-models",
    model_id: str,
    endpoint: str | None = None,
    api_key: str | None = None,
    api_version: str | None = None,
    prompts: list[str] | None = None,
    use_prompt_suite: bool = True,
    max_new_tokens: int = 64,
    manual_w1_jsonl: str | None = None,
    use_manual_w1: bool = True,
    human_fetch_jsonl: str | None = None,
    use_human_fetch: bool = True,
) -> dict:
    """Evaluate a frontier chat model using the Stage 0/1 eval contract.
    
    Returns the same stage0_eval.v2 schema as evaluate.py with:
    - identity.provider/model_id/endpoint populated
    - hawaiian_ppl marked not_supported
    - generations/orthography/translation probes work normally
    """
    service = FrontierChatService(
        provider=provider,
        model_id=model_id,
        endpoint=endpoint,
        api_key=api_key,
        api_version=api_version,
    )
    
    report: dict = {
        "schema_version": EVAL_SCHEMA_VERSION,
        "provider": provider,
        "model_id": model_id,
    }
    
    report["identity"] = _frontier_identity(
        provider=service.provider,
        model_id=model_id,
        endpoint=service.endpoint,
        api_version=service.api_version,
    )
    
    is_reasoning = _is_reasoning_model(model_id)
    if is_reasoning:
        report["decoding"] = {
            "do_sample": True,  # reasoning models use default sampling
            "max_new_tokens": max_new_tokens,
            "temperature": None,  # not supported, using API default
            "top_p": None,  # not supported
            "greedy": False,  # non-deterministic
            "max_completion_tokens": max_new_tokens,
            "note": "GPT-5 family rejects temperature/top_p; uses default sampling",
        }
    else:
        report["decoding"] = {
            "do_sample": False,
            "max_new_tokens": max_new_tokens,
            "temperature": 0.0,
            "top_p": 1.0,
            "greedy": True,
        }
    
    # Hawaiian PPL not supported for closed chat APIs
    report["hawaiian_ppl"] = {
        "status": "not_supported",
        "reason": "no logprobs from chat-completions API; closed frontier models do not expose token-level probabilities",
    }
    report["hawaiian_ppl_by_source"] = {
        "status": "not_supported",
        "reason": "depends on hawaiian_ppl",
    }
    report["eval_set"] = {
        "status": "not_applicable",
        "reason": "eval_set requires tokenizer for metadata; frontier models are tokenizer-opaque",
    }
    
    # English PPL also not supported
    report["english_ppl"] = {
        "status": "not_supported",
        "reason": "no logprobs from chat-completions API",
    }
    
    # W1 manual micro-eval (metadata/validation only)
    report["manual_w1"] = manual_w1_status(
        manual_w1_jsonl, enabled=use_manual_w1
    )
    
    # Bidirectional translation probe
    report["human_fetch_translation"] = _human_fetch_translation_probe_frontier(
        human_fetch_jsonl,
        enabled=use_human_fetch,
        service=service,
        max_new_tokens=max_new_tokens,
    )
    
    # Prompt assembly
    suite_used: list[tuple[str, str]] | None = None
    if prompts:
        prompts_to_run = list(prompts)
        prompt_ids = [f"user_{i}" for i in range(len(prompts_to_run))]
    elif use_prompt_suite:
        suite_used = list(DEFAULT_PROMPT_SUITE)
        prompt_ids = [pid for pid, _ in suite_used]
        prompts_to_run = [ptext for _, ptext in suite_used]
    else:
        prompts_to_run = []
        prompt_ids = []
    
    if prompts_to_run:
        descriptor_input = (
            suite_used
            if suite_used is not None
            else list(zip(prompt_ids, prompts_to_run))
        )
        suite_descriptor = compute_prompt_suite_descriptor(descriptor_input)
        report["prompt_suite"] = suite_descriptor
        
        # Generate
        print(f"[frontier-eval] generating {len(prompts_to_run)} samples from {model_id}...", file=sys.stderr)
        gens = [service.generate(p, max_tokens=max_new_tokens) for p in prompts_to_run]
        
        report["generations"] = gens
        report["generation_sha256"] = {
            f"sample_{i}": _sha256_text(g) for i, g in enumerate(gens)
        }
        
        # Orthography checks
        orth = {
            f"sample_{i}": metrics_mod.orthography_report(g)
            for i, g in enumerate(gens)
        }
        report["orthography_metrics"] = orth
        report["orthography_aggregate"] = _orthography_aggregate(
            orth, suite_descriptor
        )
        report["tripwires"] = _tripwires(
            report["orthography_aggregate"],
            suite_descriptor,
            generation_count=len(gens),
        )
    
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate frontier chat models via GitHub Models/Azure + Semantic Kernel."
    )
    parser.add_argument(
        "--provider",
        default=os.environ.get("FRONTIER_PROVIDER", os.environ.get("PROVIDER", "github-models")),
        help="Provider: github-models or azure (default: github-models; env FRONTIER_PROVIDER)",
    )
    parser.add_argument(
        "--model-id",
        "--model",
        dest="model_id",
        required=False,
        help="Model ID or Azure deployment name (default for Azure: AZURE_OPENAI_GPT5_DEPLOYMENT or gpt-5-chat)",
    )
    parser.add_argument(
        "--endpoint",
        default=None,
        help="API endpoint (default depends on provider)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API key (default: GitHub token for github-models; AZURE_OPENAI_API_KEY for azure)",
    )
    parser.add_argument(
        "--api-version",
        default=None,
        help=f"Azure OpenAI API version (default: AZURE_OPENAI_API_VERSION or {DEFAULT_AZURE_OPENAI_API_VERSION})",
    )
    parser.add_argument(
        "--prompt",
        action="append",
        default=None,
        help="Prompt(s) to generate from. Repeatable. Disables built-in suite.",
    )
    parser.add_argument(
        "--no-prompt-suite",
        action="store_true",
        help="Skip the built-in fixed prompt suite when no --prompt is given.",
    )
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=64,
        help="Max new tokens for generation.",
    )
    parser.add_argument(
        "--manual-w1-jsonl",
        default=None,
        help=f"Path to W1 manual micro-eval JSONL (default: {DEFAULT_MANUAL_W1_JSONL}).",
    )
    parser.add_argument(
        "--no-manual-w1",
        action="store_true",
        help="Disable W1 manual micro-eval status probe.",
    )
    parser.add_argument(
        "--human-fetch-jsonl",
        default=None,
        help=f"Path to human_fetch parallel pair JSONL (default: {DEFAULT_HUMAN_FETCH_JSONL}).",
    )
    parser.add_argument(
        "--no-human-fetch",
        action="store_true",
        help="Disable human_fetch bidirectional translation probe.",
    )
    ns = parser.parse_args(argv)
    ns.provider = _normalize_provider(ns.provider)
    if not ns.model_id:
        if _is_azure_provider(ns.provider):
            ns.model_id = _default_azure_deployment()
        else:
            parser.error("--model-id/--model is required for github-models")
    
    report = evaluate_frontier_model(
        provider=ns.provider,
        model_id=ns.model_id,
        endpoint=ns.endpoint,
        api_key=ns.api_key,
        api_version=ns.api_version,
        prompts=ns.prompt,
        use_prompt_suite=not ns.no_prompt_suite,
        max_new_tokens=ns.max_new_tokens,
        manual_w1_jsonl=ns.manual_w1_jsonl,
        use_manual_w1=not ns.no_manual_w1,
        human_fetch_jsonl=ns.human_fetch_jsonl,
        use_human_fetch=not ns.no_human_fetch,
    )
    
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
