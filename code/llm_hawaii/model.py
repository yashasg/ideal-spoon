"""Model + LoRA/QLoRA loading.

Implement this file in this order:
1. Load a tiny causal LM without LoRA first and confirm a forward pass works.
2. Attach LoRA with `peft` and print trainable parameter counts.
3. Turn on QLoRA only after LoRA works; most failures here are CUDA /
   bitsandbytes version mismatches, not model bugs.
4. Keep hardware checks generic. Report CUDA, GPU name, bf16 support, and VRAM,
   but do not hardcode "must be A100" or "must be L40S" in Python.
5. Treat Llama-3.1-8B as a config choice. The same code should run smoke
   configs and serious prototype configs.

Lazy-imports torch / transformers / peft / bitsandbytes so this module parses
on a laptop with nothing installed. Functions raise a clear RuntimeError with
an install hint if a dep is actually missing at use.
"""
from __future__ import annotations

import warnings
from typing import Any, Tuple


def _require(pkg: str, install_hint: str) -> Any:
    try:
        return __import__(pkg)
    except ImportError as e:
        raise RuntimeError(
            f"Missing optional dependency '{pkg}'. Install with: {install_hint}"
        ) from e


def _bnb_compute_dtype_name(bf16: bool, fp16: bool) -> str:
    """Return the torch dtype name for bnb_4bit_compute_dtype based on TrainConfig flags.

    Priority: bf16 > fp16 > float32. Pure Python — no torch import needed.
    """
    if bf16:
        return "bfloat16"
    if fp16:
        return "float16"
    return "float32"


def _bnb_4bit_config(bf16: bool = False, fp16: bool = False):
    """4-bit NF4 + double-quant config (project default for QLoRA).

    compute_dtype follows TrainConfig: bf16 → bfloat16, fp16 → float16,
    else float32. Pass the same bf16/fp16 flags you set in TrainConfig.
    """
    transformers = _require("transformers", "pip install transformers")
    _require("bitsandbytes", "pip install bitsandbytes")
    torch = _require("torch", "pip install torch")
    compute_dtype = getattr(torch, _bnb_compute_dtype_name(bf16, fp16))
    return transformers.BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=compute_dtype,
    )


def load_base_model(
    base_model: str,
    use_qlora: bool = True,
    gradient_checkpointing: bool = True,
    bf16: bool = False,
    fp16: bool = False,
):
    """Load the causal-LM base.

    With `use_qlora=True`, the base is loaded in 4-bit and prepared for
    k-bit training. Otherwise it's loaded in the default dtype — fine
    for tiny smoke models on CPU/MPS, painful for anything real.
    """
    transformers = _require("transformers", "pip install transformers")
    kwargs: dict = {}
    if use_qlora:
        kwargs["quantization_config"] = _bnb_4bit_config(bf16=bf16, fp16=fp16)
        kwargs["device_map"] = "auto"
    model = transformers.AutoModelForCausalLM.from_pretrained(base_model, **kwargs)

    if use_qlora:
        peft = _require("peft", "pip install peft")
        model = peft.prepare_model_for_kbit_training(
            model, use_gradient_checkpointing=gradient_checkpointing
        )
    elif gradient_checkpointing:
        model.gradient_checkpointing_enable()
    return model


def attach_lora(
    model,
    rank: int = 32,
    alpha: int = 64,
    dropout: float = 0.05,
    target_modules: str | list[str] = "all-linear",
):
    """Wrap the base in a LoRA adapter.

    `target_modules="all-linear"` is a reasonable default for unfamiliar
    bases. Once you know the architecture, narrow this to e.g.
    ["q_proj", "k_proj", "v_proj", "o_proj"] for attention-only, or add
    MLP projections.
    """
    peft = _require("peft", "pip install peft")
    cfg = peft.LoraConfig(
        r=rank,
        lora_alpha=alpha,
        lora_dropout=dropout,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=target_modules,
    )
    return peft.get_peft_model(model, cfg)


def build_model_and_tokenizer(cfg) -> Tuple[Any, Any]:
    """Convenience: tokenizer + LoRA-wrapped base from a TrainConfig.

    Kept as a thin composition so a learner can step through each
    primitive (`load_tokenizer`, `load_base_model`, `attach_lora`) on
    its own first.
    """
    from .data import load_tokenizer

    tokenizer = load_tokenizer(cfg.tokenizer_name or cfg.base_model)
    model = load_base_model(
        cfg.base_model,
        use_qlora=cfg.use_qlora,
        gradient_checkpointing=cfg.gradient_checkpointing,
        bf16=cfg.bf16,
        fp16=cfg.fp16,
    )
    model = attach_lora(
        model,
        rank=cfg.lora_rank,
        alpha=cfg.lora_alpha,
        dropout=cfg.lora_dropout,
        target_modules=cfg.lora_target_modules,
    )
    return model, tokenizer


def check_runtime_capability(use_qlora: bool, want_bf16: bool) -> dict:
    """Generic, *non-fatal* runtime capability check.

    Returns a dict of observations rather than asserting on a specific
    GPU model. The point is to teach a learner *what to look for*
    (CUDA availability, compute capability for bf16, enough VRAM for
    your config) without hardcoding "must be A100" anywhere.

    Hardware targeting (e.g. A100, RTX 4090) belongs in config metadata
    — see `TrainConfig.hardware_profile` — not in this code path.
    """
    torch = _require("torch", "pip install torch")
    info: dict = {
        "cuda_available": bool(torch.cuda.is_available()),
        "device_count": int(torch.cuda.device_count()) if torch.cuda.is_available() else 0,
        "bf16_supported": False,
        "device_name": None,
        "compute_capability": None,
    }
    if info["cuda_available"]:
        idx = 0
        info["device_name"] = torch.cuda.get_device_name(idx)
        major, minor = torch.cuda.get_device_capability(idx)
        info["compute_capability"] = (major, minor)
        # bf16 needs Ampere (sm_80) or newer; this is a generic check,
        # not an A100-specific assertion.
        info["bf16_supported"] = major >= 8
    if use_qlora and not info["cuda_available"]:
        warnings.warn(
            "QLoRA requested but no CUDA device found. QLoRA requires a GPU; "
            "consider setting use_qlora=False for CPU/MPS experimentation."
        )
    if use_qlora and info["device_count"] == 0:
        warnings.warn(
            "QLoRA requested but no CUDA devices detected. QLoRA training will not work without a GPU."
        )
    if want_bf16 and not info["bf16_supported"]:
        warnings.warn(
            "bfloat16 requested but not supported by detected GPU. "
            "Consider using a GPU with compute capability sm_80+ (e.g. A100) or switching to fp16."
        )

    return info


# ---------------- TODOs for the learner ----------------
#
# TODO(merge-stage1): For the two-stage plan, after Stage 1 you need to
#   merge the LoRA into an fp16 base (`peft_model.merge_and_unload()`)
#   before starting Stage 2. Don't stack adapters for release.
#
# TODO(checkpoint-resume): When training on a free-tier GPU, sessions
#   die. Wire `transformers.Trainer(resume_from_checkpoint=...)` into
#   train.py and verify a kill -9 mid-run resumes cleanly.
