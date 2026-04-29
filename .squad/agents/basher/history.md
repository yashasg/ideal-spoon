# Basher — History

## Core Context

- **Project:** A plan for training an open-source LLM focused on the Hawaiian language, including data, model choices, infrastructure, evaluation, and costs.
- **Role:** Training Engineer
- **Joined:** 2026-04-29T01:38:35.143Z

## Learnings

### README Update (2026-04-29)
- Infrastructure recommendation adopted in README: QLoRA on 1x A100/H100/L40S or 2x RTX 4090 with Axolotl/TRL + bitsandbytes. Multi-GPU (FSDP/DeepSpeed) deferred until recipe stabilizes.
- Emphasis on optimizing data/eval loop before scaling GPUs aligns with low-resource language strategy.

### Credit-Fit Advisory (2026-04-29)
- User constraint: ~$50–$60/mo of Azure credits remaining + local RTX 2080.
- Decision shape: keep all data/tokenizer/eval/baseline work local; spend credits only on a single 7B QLoRA run on A100 40GB / L4 / A10.
- Budget reality: one real run + maybe a partial retry. Not enough for the README's iterative Weeks 5–6 unless credits accumulate across months or vendor switches (RunPod/Lambda).
- Guardrails that matter most: Azure auto-shutdown, spot VMs for non-final runs, checkpoint to blob, budget alerts at 50/80%, validate the full pipeline locally before the VM ever spins up.
- Open question: 2080 (8GB) vs 2080 Ti (11GB) changes what local 7B QLoRA debugging is feasible.
- Artifact: `.squad/decisions/inbox/basher-credit-fit.md`.

### Free / low-cost compute scoping (2026-04-29)
- RTX 2080 (8GB): viable for QLoRA on ≤7B 4-bit with bs=1, seq≤512, gradient checkpointing, Unsloth. 9B is borderline-OOM; 13B not viable.
- Kaggle (T4/P100 16GB, 30 GPU-h/wk, 9–12h sessions, persistent storage, background exec) is the strongest free tier for real fine-tune jobs.
- Colab free is good for prototyping only (~40 unit-h/mo, no background, 30-min idle disconnects). Lightning AI free ~22 GPU-h/mo, useful as a workstation but limited hours.
- Azure spot pricing: NC24ads_A100_v4 (1×A100 80GB) ~$0.68/hr spot → ~$50 buys ~70 spot-hours of A100 80GB; T4 spot ~$0.15–0.30/hr. Always use spot + checkpoint frequently.
- Final 7B QLoRA on a real corpus is realistic on Kaggle T4×2 + occasional Azure A100 spot bursts. 9B QLoRA realistically wants A100 spot.
- Guardrails: budget alerts at $30/$45, auto-shutdown VMs, never run on-demand A100, store data/checkpoints in cheap blob not on VM disk.
