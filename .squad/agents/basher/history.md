# Basher — History

## Core Context

- **Project:** A plan for training an open-source LLM focused on the Hawaiian language, including data, model choices, infrastructure, evaluation, and costs.
- **Role:** Training Engineer
- **Joined:** 2026-04-29T01:38:35.143Z

## Learnings

### README Update (2026-04-29)
- Infrastructure recommendation adopted in README: QLoRA on 1x A100/H100/L40S or 2x RTX 4090 with Axolotl/TRL + bitsandbytes. Multi-GPU (FSDP/DeepSpeed) deferred until recipe stabilizes.
- Emphasis on optimizing data/eval loop before scaling GPUs aligns with low-resource language strategy.
