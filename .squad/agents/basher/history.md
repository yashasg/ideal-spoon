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

### Two-stage training plan (2026-04-29)
- User directive: Stage 1 monolingual Hawaiian CPT, Stage 2 supervised translation SFT.
- Adapter convention: **merge Stage 1 LoRA into fp16 base, train a fresh Stage 2 LoRA on top.** Don't stack adapters for release artifacts — merge problems and double-quant noise. Stacking allowed only for cheap A/B experiments.
- Stage 1: causal LM, seq 2048, LoRA r=64/alpha=128 on all linear layers, LR 2e-4, 1 epoch, **5–10% English rehearsal** to fight catastrophic forgetting.
- Stage 2: instruction template, **loss masked to target tokens only**, seq 1024, LoRA r=32/alpha=64, LR 1e-4, 2–3 epochs, both directions balanced 50/50.
- Run ladder: 0.5B local smoke → 0.5B Kaggle dry-run → 7B Stage 1 on Kaggle → merge → 7B Stage 2 on Kaggle or one A100 spot.
- Gate after Stage 1: Hawaiian PPL ↓, English PPL not blown up (≤20% rel increase), qualitative Hawaiian fluency check.
- Gate after Stage 2: BLEU + chrF++ beats both base and Stage-1-only baselines in both directions, no train-leak, human Likert ≥3.5.
- Hard prereq from Linus: per-doc/per-pair provenance manifest, license whitelist, hash-checked train/dev/test split, NFC + ʻokina U+02BB confirmed. No data → no train.
- Tokenizer + base-model SHA frozen at Stage 1 start; CI check on tokenizer hash before Stage 2.
- Quantization rule: only one quant boundary per stage. Stage 1 merged into **fp16**, Stage 2 reloaded in 4-bit from fp16 merged model.
- Artifact: `.squad/decisions/inbox/basher-two-stage-training.md`.

## 2026-04-29T02:53:51Z — Two-stage implementation plan accepted

Delivered QLoRA recipe + compute mapping for the two-stage plan. Stage 1: r=64/α=128, lr 2e-4, seq 2048, 1 epoch, 5–10% English rehearsal. Stage 2: r=32/α=64, lr 1e-4, seq 1024, 2–3 epochs, masked-target loss, 50/50 direction balance. **Release adapter path adopted:** merge Stage 1 LoRA into fp16 base → train fresh Stage 2 LoRA on the merged model (avoids stacked-adapter merge headaches, double-quant noise, ambiguous active-adapter bugs at inference). One quantization, not two. Compute: 0.5B smoke local + Kaggle dry-run; 7B/8B Stage 1 on Kaggle (T4×2/P100); Stage 2 on Kaggle or single Azure A100 40GB spot. Hard gate: Linus's data foundation must pass before Stage 1 launch — data is now the long pole, not compute. See ADR "Two-stage training plan" in `.squad/decisions.md`.

### Cross-agent: prototype-vs-release split (2026-04-29T03:01:58Z)
- New ADR splits gates into prototype (private, lighter) and release (public, full clearance). Training recipe unchanged.
- Loader will enforce: `release_candidate` runs reject `prototype_private` / `unreviewed*` / `unclear` rows. Plan training jobs against the right `intended_use`.
- No prototype-tainted weights in the released chain; cleared-corpus retrain required for release.
