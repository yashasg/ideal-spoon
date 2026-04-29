# Orchestration Log — Livingston (China GPU Pricing)

**Timestamp:** 2026-04-29T04:40:54Z  
**Agent:** Livingston (Cost Strategist)  
**Task:** Chinese GPU provider pricing and technical fit for Hawaiian LLM QLoRA prototype  
**Mode:** Background  
**Status:** Completed

## Outcome Summary

**Headline:** Chinese marketplace GPU prices are genuinely cheaper on paper (AutoDL/Featurize/OpenBayes: $0.27–$0.35/hr for 4090, $0.48–$0.69/hr for A100/A800 vs RunPod $0.34–$1.19/hr), but US access/payment/GFW/HF checkpoint friction and small absolute savings ($3–$18 across 15–25 GPU-hour prototype) make them not worth switching to for this project.

**Key Finding:** Big Chinese enterprise clouds (Alibaba/Tencent/Huawei/Baidu) are **not cheaper** at list price — 2–4× more expensive than RunPod and Lambda.

**Recommendation:** Do not move this prototype to Chinese providers. Keep existing stack: Kaggle + RunPod community + Lightning Pro + Azure credits.

## Research Artifacts

- **Input:** Pricing inquiry from user about Chinese GPU providers (AutoDL, Featurize, OpenBayes, Alibaba Cloud, etc.)
- **Output:** Comprehensive pricing snapshot + access-constraint analysis + recommendation written to `.squad/decisions/inbox/livingston-china-gpu-pricing.md`

## Details

### Pricing Snapshot (RMB→USD ~7.2)

| Provider | GPU | RMB/hr | USD/hr |
|---|---|---|---|
| AutoDL | RTX 4090 24GB | ¥1.98 | $0.27 |
| AutoDL | A100/A800 80GB | ¥4.98 | $0.69 |
| Featurize | RTX 4090 24GB | ¥1.87–3.0 | $0.26–0.42 |
| OpenBayes | RTX 4090 24GB | ¥2.3–2.5 | $0.32–0.35 |
| Alibaba Cloud (list) | A100 80GB | ¥34.74 | $4.80 |

**vs. Existing Stack:**
- RunPod A100 40GB: $1.19/hr
- Lambda A100 40GB: $1.29/hr
- Azure spot A100 80GB: ~$0.68/hr

### Access Constraints (Binding for US individual)

1. **Phone/ID:** +86 mobile + Chinese ID (身份证) for signup; foreign passports inconsistently accepted. **Registration dead-end without Chinese collaborator.**
2. **Payment:** RMB (Alipay/WeChat Pay). Foreign credit cards rejected on most consumer platforms.
3. **Great Firewall:** HF Hub push is flaky from mainland. Breaks checkpoint-sync contract.
4. **GitHub:** Reachable but slow; mirror needed for large clones.
5. **Data jurisdiction:** PRC (PIPL/DSL) — governance red flag for Hawaiian cultural corpus.

### Effective Cost for Prototype

- 7B QLoRA: ~15–25 GPU-hr
- RunPod A100 40GB: ~$18–30 total
- AutoDL A100: ~$7–12 total
- **Savings: $10–18** — dwarfed by registration/HF-push friction and language barrier.

## Implications

- README $10k–$30k practical tier remains unchanged.
- Basher's GPU subscription recommendation stands.
- Revisit only if a trusted collaborator in China can handle +86, real-name, RMB payment, and non-HF checkpoint flow.

## Cross-Agent Handoffs

- **Basher:** HF Hub push reliability now part of provider-fit checklist alongside CUDA/bnb/FA2.
- **Linus:** PIPL/DSL note for team awareness; public-domain corpus not affected, but would matter if scope expanded.

## Sources

- AutoDL: autodl.com, neurowave.tech, sohu.com, idcsp.com (late-2025 / early-2026)
- Featurize: featurize.cn/vm/available
- OpenBayes: openbayes.com/pricing
- Alibaba: aliyunbaike.com, hostol.com, cloudgputracker.com
- HF mirror: hf-mirror.com community convention
- Export rules: NVIDIA + US BIS Oct-2022/Oct-2023 (A800/H800/L20/H20 specs)
