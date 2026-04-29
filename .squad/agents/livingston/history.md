# Livingston — History

## Core Context

- **Project:** A plan for training an open-source LLM focused on the Hawaiian language, including data, model choices, infrastructure, evaluation, and costs.
- **Role:** Cost Strategist
- **Joined:** 2026-04-29T01:38:35.143Z

## Learnings

### README Update (2026-04-29)
- Budget tier analysis ($1k–$5k lean, $10k–$30k practical, $50k–$150k serious) adopted in README with detailed cost breakdowns.
- Vendor recommendation (Lambda, RunPod, Vast, CoreWeave for GPU; Hugging Face for release) captured.
- Key tradeoff ratified: invest first in corpus quality, licensing, and Hawaiian-speaker evaluation; GPU costs are manageable, data quality is differentiator.

### Azure Credit Sub-Budget Guidance (2026-04-29)
- User context: $150/mo Azure credits, ~$50–60 typically left late in month, plus local RTX 2080 (8GB).
- Framing adopted: leftover monthly credit is **exploratory / plan-validation budget**, not a training-run budget. Does not alter README's $10k–$30k practical tier.
- Good uses on Azure at this scale: tokenizer audits (CPU VM), short spot-GPU smoke tests (T4/V100), baseline inference on candidate models, cheap Blob storage for manifests.
- Avoid: H100/ND-series, always-on VMs, premium disks, public endpoints, long training runs.
- Required guardrails: Cost Management budget alerts, auto-shutdown, Spot VMs, one RG per experiment, `project=hawaiian-llm` tag.
- RTX 2080 division of labor: all data/tokenizer/manifest work + 4-bit inference on 7B + LoRA on 1B–3B locally; reserve Azure for ≥24GB VRAM or A100-class needs.
- Microsoft employee caveat: did NOT claim knowledge of internal policy. Flagged questions for user to resolve internally (credit usage terms, RAI/data policy, IP/OSS release, cultural-data review, tenant separation).
- Decision note: `.squad/decisions/inbox/livingston-azure-credit-budget.md`.

### Free / Low-Cost Compute Research (2026-04-29)
- Researched free GPU services for QLoRA experiments on Hawaiian LLM. Findings:
  - **Kaggle Notebooks**: ~30 hr/week free, P100 16GB or 2×T4 (32GB total), 9hr session cap. Most generous reliably-free tier; fits QLoRA 7B comfortably.
  - **Google Colab Free**: ~100 compute units/mo (~40 T4 hr), ~12hr sessions, idle disconnects. Pro $10–13/mo (~255 T4 hr). Useful for prototyping, unreliable for long runs.
  - **Lightning AI Studio**: ~22 free monthly credits (changed since older blogs); good IDE; not enough for full training.
  - **Hugging Face ZeroGPU (PRO $9/mo)**: A100 access but inference-oriented (short function runtime); useful for demos/eval, not training.
  - **SageMaker Studio Lab**: Still free, T4, 4hr GPU sessions, queue. Marginal for QLoRA.
  - **Paperspace Gradient free**: older M4000, weak for LLMs.
- Credit/grant programs (approval-based, not reliable for timeline):
  - Google Cloud Research Credits (rolling, academic), AWS Cloud Credits for Research / Activate, Azure for Research, MS Founders Hub ($150k for startups). Real money but require qualifying entity + proposal.
  - HF community grants (case-by-case Spaces hardware upgrades).
  - NSF/NEH DEL, ANA Esther Martinez, Endangered Language Fund Language Legacies, BIA Living Languages — relevant for Hawaiian; multi-month cycles, partner with UH or a Native-Hawaiian-serving org.
- Microsoft employee Azure credit caveat: personal/non-commercial only; do NOT host project services on employee benefit; fine for personal QLoRA experiments but not as durable infra.
- Model recommendation for QLoRA on Hawaiian: top candidates are **Gemma 2 9B**, **Llama 3.1 8B**, **Qwen2.5 7B**. Selection blocked on Rusty's tokenizer audit (diacritics: ʻokina, kahakō). All three are open-weight, run in QLoRA on a single 16GB GPU (Kaggle P100 / Colab T4 borderline at 7B; 2×T4 on Kaggle is the comfortable choice).
- Practical stance: Kaggle for QLoRA iteration → cheap rented A100/H100 hours (Lambda/RunPod/Vast) for the final candidate run, paid from the $10k–$30k practical tier. Don't gate the project on grants; pursue grants in parallel.

### Cross-agent: prototype-vs-release split (2026-04-29T03:01:58Z)
- Budget framing unchanged. Prototype scope reduces pressure on the upper-tier full-fine-tune contingency since release-quality runs are now explicitly gated separately.
- Qwen2.5-0.5B smoke test remains the right first artifact under prototype scope.
