# Session Log — China GPU Provider Research

**Timestamp:** 2026-04-29T04:40:54Z

## Summary

Two agents (Livingston, Basher) completed parallel investigation of Chinese GPU providers (AutoDL, Featurize, OpenBayes, Alibaba/Tencent/Huawei, Ascend 910B) for Hawaiian LLM 7B/8B QLoRA prototype.

## Findings

**Livingston (Cost):** AutoDL/Featurize/OpenBayes are 30–60% cheaper per GPU-hour than RunPod (~$0.27/hr vs $0.34–1.19/hr), but US-individual registration (require +86 phone + Chinese ID), Great Firewall friction on HF Hub push, and small absolute savings ($3–18 across 15–25 GPU-hr prototype) make them not worth switching. Big enterprise clouds (Alibaba/Tencent/Huawei/Baidu) are 2–4× *more* expensive than RunPod at list price.

**Basher (Training):** Hardware (4090/4090D/A800/H800/L20) all run QLoRA (CUDA/bnb NF4/flash-attn 2) unchanged on AutoDL. But HF Hub push (our checkpoint bus) is unreliable from inside GFW, breaking provider-hop contract. Ascend 910B is hard no — CANN/torch_npu ecosystem, no bnb NF4, no flash-attn 2, multi-week port. Alibaba/Tencent abstract drivers (Colab/Lightning problem), no cheap-headline savings.

## Recommendation

**Do not switch to Chinese GPU providers.** Keep existing stack: Kaggle + RunPod community + Lightning Pro + Azure credits. Revisit AutoDL only if a trusted Chinese collaborator can handle +86, real-name verification, RMB payment, and non-HF checkpoint flow.

## Orchestration Logs

- `.squad/orchestration-log/2026-04-29T04-40-54Z-livingston-china-gpu-pricing.md`
- `.squad/orchestration-log/2026-04-29T04-40-54Z-basher-china-gpu-fit.md`

## Artifacts Produced

- `.squad/decisions/inbox/livingston-china-gpu-pricing.md` (pricing snapshot + access constraints)
- `.squad/decisions/inbox/basher-china-gpu-fit.md` (hardware fit + red flags + Ascend analysis)
