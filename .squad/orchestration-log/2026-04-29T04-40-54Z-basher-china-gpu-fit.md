# Orchestration Log — Basher (China GPU Technical Fit)

**Timestamp:** 2026-04-29T04:40:54Z  
**Agent:** Basher (Training Engineer)  
**Task:** Chinese GPU provider technical fit for Hawaiian LLM QLoRA prototype  
**Mode:** Background  
**Status:** Completed

## Outcome Summary

**Headline:** 4090/4090D/A800/L20/H800 can all run CUDA/PyTorch/bitsandbytes/flash-attn QLoRA unchanged, but HF Hub push through the GFW is unreliable, payment/real-name barriers are hard gates for US individuals, support is Chinese-only, and data-governance concerns make China providers a poor fit. Ascend 910B is not viable — different kernel ecosystem, no bnb NF4, no flash-attn 2.

**Recommendation:** Keep existing Kaggle + RunPod + Lightning + Azure-credit stack. Do not switch to Chinese providers for this prototype.

## Technical Analysis

### Hardware Fit

| GPU | NF4/bnb | flash-attn 2 | bf16 | Fits 7B QLoRA? | Notes |
|---|---|---|---|---|---|
| RTX 4090 | ✅ | ✅ | ✅ | ✅ comfortably | Best $/hr on CN platforms. ~⅕ A100 cost, ~⅔ throughput. |
| RTX 4090D | ✅ | ✅ | ✅ | ✅ | China-export SKU; ~5–10% slower than 4090. Not a real blocker. |
| A800 80GB | ✅ | ✅ | ✅ | ✅ overkill | Ampere, NVLink-throttled; doesn't matter for single-GPU QLoRA. |
| H800 80GB | ✅ | ✅ | ✅ | ✅ overkill | Hopper, same caveat. FP8 is gated; we don't use it through bnb. |
| L20 / L40S 48GB | ✅ | ✅ | ✅ | ✅ | Ada Pro; solid A100 40GB alternative. |
| Ascend 910B | ❌ | ❌ | ✅ | ❌ | **Hard no.** CANN/torch_npu, not CUDA. No bnb NF4, no FA2. Multi-week port for worse $/result. |

### What Works on AutoDL / China Providers

- **CUDA/Drivers:** CUDA 11.8 / 12.1 / 12.4 with PyTorch 2.x preinstalled. Drivers 535+. bitsandbytes 0.43+ NF4 and flash-attn 2 install from wheels clean.
- **Storage:** AutoDL gives 50 GB /root + persistent volumes. Better than RunPod community on this dimension.
- **Checkpointing:** 30–60 min HF Hub sync works as long as egress holds.
- **Preemption:** AutoDL on-demand does not preempt; interruptible tier available for discount.

## Technical Red Flags

1. **HF Hub push unreliability (BLOCKING):** `huggingface.co` is intermittently throttled/blocked from mainland. Mirrors (hf-mirror.com) handle *pulls* fine; *pushes* (our checkpoint bus) are unreliable. Workarounds: relay from outside China, S3 backup, or accept losing portable checkpoints.
2. **GitHub:** Reachable but slow (50–500 KB/s); large clones can stall. Use `--depth 1`, prefer `pip install` over `git+`.
3. **PyPI:** Slow. Switch to Tsinghua/Aliyun mirror (`-i https://pypi.tuna.tsinghua.edu.cn/simple`).
4. **Payment/Real-Name Gate:** AutoDL, Featurize, Gpushare, MatPool, Dbcloud all require Chinese mobile + Alipay/WeChat + real-name (实名认证) with PRC ID. Foreign credit cards do not work. **Registration is impossible for US individuals without a proxy account holder.**
5. **Data Sensitivity:** Our corpus (Hawaiian + licensed material) on a PRC-hosted instance is subject to PIPL/DSL. For a learning prototype with public-domain data, acceptable; for release, we'd avoid it anyway per existing ADR.
6. **Language/Support:** AutoDL has passable English UI. Featurize/MatPool/Gpushare/Dbcloud are Chinese-only. Support tickets in English answered slowly.
7. **Latency:** SSH/VS Code Remote from US West Coast is 150–200 ms RTT, occasionally spiky. Tolerable for SSH/terminal; painful for interactive Jupyter.
8. **Driver Pinning on Hyperscalers:** Alibaba/Tencent/Huawei abstract the driver (managed PAI/TI/ModelArts). Same pinning concern as Colab/Lightning.

### Ascend 910B: Why It Doesn't Work

- **Not CUDA:** Ascend 910B/910C run CANN + MindSpore / PyTorch-NPU (torch_npu plugin). Different kernel ecosystem.
- **No bnb NF4:** Experimental "MindIE" 4-bit exists; it's not bnb, not NF4, invalidates our quantization-boundary discipline.
- **No flash-attn 2:** Huawei ships `npu_fusion_attention` instead — different kernel, our throughput/memory numbers don't transfer.
- **HF Transformers Support Lags:** PEFT QLoRA on NPU is a rough edge as of late 2025; 2–6 month lag behind CUDA.
- **ROI:** Multi-week port for *worse* $/result than a 4090 on AutoDL. Wrong tool for a learning prototype.

Ascend only interesting if we leave QLoRA, need multi-node bf16 full fine-tune, and had budget for a porting sprint. None apply here.

## Comparison to Existing Stack

| Dimension | AutoDL 4090 | RunPod comm. A100 40GB | Lambda A100 40GB | Lightning Pro L4 |
|---|---|---|---|---|
| $/hr | ~$0.27 | $1.19 | $1.29 | ~$0.50 |
| CUDA pinning | ✅ image-level | ✅ | ✅ | ❌ abstracted |
| bnb/FA2 ready | ✅ | ✅ | ✅ | ✅ |
| HF Hub push reliable | ⚠️ flaky from CN | ✅ | ✅ | ✅ |
| GitHub reliable | ⚠️ slow | ✅ | ✅ | ✅ |
| Foreign card payment | ❌ | ✅ | ✅ | ✅ |
| English support | ⚠️ partial | ✅ | ✅ | ✅ |
| Provider-hop friendly | ❌ HF-push seam | ✅ | ✅ | ✅ |

## Implications

- HF Hub push reliability is now part of the provider-fit checklist alongside CUDA pinning and wheel availability.
- Chinese providers break our checkpoint-contract ADR (provider-hop property depends on HF push working).
- Release-candidate run remains pinned to non-PRC provider regardless of price.

## Recommendations

1. **Keep existing stack:** Kaggle + RunPod community A100 40GB for Stage 1 + Lightning Pro (Studio) for dev + Azure credits for release-candidate.
2. **If user has Alipay + Chinese mobile:** AutoDL 4090D is genuinely cheapest; pin CUDA 12.1/PyTorch 2.3, set `HF_ENDPOINT=https://hf-mirror.com`, route pushes through US relay or accept losing portable checkpoints.
3. **Do not use Ascend 910B for this prototype.**
4. **Do not use Alibaba/Tencent/Huawei Cloud on-demand:** Hyperscaler pricing without cheap-headline savings. RunPod/Lambda dominate.
5. **Hard rule:** Release-candidate run is non-PRC, single provider, pinned driver. No Chinese providers for release regardless.

## Cross-Agent Handoffs

- **Livingston:** No change to cost ceiling. Rejected on technical-fit grounds, not cost grounds.
- **Linus:** PIPL/DSL awareness. Public-domain corpus not affected; would matter if scope expands.
- **Rusty:** No change to tokenizer/FA2/bf16 plan.

## Sources

- AutoDL: autodl.com (CUDA images, pricing, persistent storage)
- Featurize: featurize.cn (pricing, GPU availability)
- Gpushare/MatPool/Dbcloud: Chinese marketplace aggregators (CNBlogs, Zhihu), 2025–2026
- Alibaba/Tencent/Huawei: PAI/TI/ModelArts docs, PAI pricing, cloud tracker sites
- HF mirror: hf-mirror.com community convention, HuggingFace Discussions
- Ascend: Huawei torch_npu repo, CANN release notes (late 2025), PEFT issues
- Export controls: NVIDIA Ampere/Hopper data, US BIS Oct-2022/Oct-2023 rules
