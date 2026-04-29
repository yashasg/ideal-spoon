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

### Training Pipeline Doc (2026-04-29T03:21:29Z)
- Authored `docs/training-pipeline.md`: Stage 0 readiness gates → Stage 1 CPT/DAPT → fp16 merge → Stage 2 bidirectional translation SFT.
- Documented eval gates, artifact lineage, compute sequencing, and go/no-go criteria.
- Cross-linked with `docs/data-pipeline.md` (Linus) after Danny's polish.

### Free-tier GPU chaining feasibility (2026-04-29)
- User question: can we treat Kaggle (30 h/wk) + Colab + Lightning + Paperspace as one big GPU pool by hand-off?
- Verdict: **yes for LoRA/QLoRA fine-tuning, no for real multi-node pretraining.** Free tiers can only be *sequenced*, not *parallelized*; you survive preemption, you do not aggregate FLOPs across providers.
- Real risks live at the seam: bitsandbytes 4-bit non-determinism across CUDA/arch, dataloader-skip cost on mid-epoch resume (use HF stateful dataloader), GPU heterogeneity drifting the global batch size, base-model revision drift, TOS gray zone for automated relays.
- Checkpoint contract (adapter + optimizer + scheduler + RNG + dataloader state + env.lock + base-model SHA pin) is the portable unit. Storage = HF Hub private repo (most provider-agnostic).
- Save policy: every 30 min + on SIGTERM/exit + epoch end. Resume policy: recompute grad-accum to preserve *global* batch size when GPU count/size changes between providers.
- Implication for Hawaiian LLM: formalizes what we'd already planned (Kaggle for Stage 1, possible provider switch between stages). Reserve one consistent paid A100 spot for the release-candidate run so the final loss curve isn't stair-stepped by quantization-kernel drift.
- Decision adopted: `.squad/decisions.md` (section "Chaining Free GPU Providers for LLM Training") — checkpoint contract, practical workflow, and implications consolidated with Livingston's cost analysis.
- Session log: `.squad/log/2026-04-29T03-46-05Z-gpu-free-tier-chaining.md`.

## 2026-04-29T03:58:26Z — Team sync: training/compute rationale captured

**Mode:** Sync (no new decision written)

Scribe requested explanation of training/compute rationale for team memory. Confirmed:
- **Training:** 7B/8B base + QLoRA fits prototype budget and free-tier GPU constraints.
- **Smoke model:** Qwen2.5-0.5B for pipeline validation.
- **Free-tier chaining:** Acceptable for learning prototype per user directive. Provider-specific API names/resource IDs may change on switch; tokenizer hashes + checkpoint versioning protect vector-space drift.
- **Checkpoint discipline:** RNG state + optimizer state must round-trip for proper resumption.

Rationale aligns with ADR "GPU compute chaining feasibility" (2026-04-29, Basher + Livingston joint). User directive (2026-04-29T03:53:18Z) confirms free-tier chaining acceptable for prototype iteration. Orchestration log: 2026-04-29T03-58-26Z-basher.md. Session: 2026-04-29T03-58-26Z-prototype-docs-and-model-choice.md.

### Eval diagnostics methodology (2026-04-29)
- For "is QLoRA loss bigger than X?" questions, answer with a smoke-model ablation matrix (precision × rank × data slice × tokenizer × rehearsal), one knob at a time, fixed seed/data/tokenizer/base-SHA. Rank deltas; do not argue in the abstract.
- Eval cadence layers: (1) pre-FT baseline on raw base, (2) smoke per recipe change, (3) cheap per-checkpoint eval (PPL + ʻokina retention) every 30 min during long runs, (4) full gate eval at end-of-stage, (5) post-run error analysis.
- Attribution matrix has distinguishing diagnostic signals per hypothesis (quant / rank / LR / data / tokenizer / forgetting / provider drift / contamination). Curve *shape* from cheap-eval log usually picks the first row to investigate.
- Free-tier rule: cheap eval rides on the checkpoint cadence (30 min); full eval only at epoch/stage end. Eval logs go to the same HF private repo as checkpoints so session crashes don't lose the curve.

### Paid GPU subscription fit (2026-04-29)
- For 7B/8B QLoRA two-stage prototype: **hourly A100 40GB on RunPod community ($1.19/hr) or Lambda ($1.29/hr) beats every subscription on $/result.** A full Stage 1 + Stage 2 attempt ≈ 40–60 GPU-hr ≈ $50–$75, no monthly commit.
- Only subscription worth paying for at this scope is **Lightning AI Pro ($20/mo annual)** — value is the persistent Studio (bitsandbytes/flash-attn/CUDA wheels survive across sessions), not the 40 credits. A100 access requires Teams ($140/user/mo) and isn't worth it; pay RunPod hourly instead.
- Colab Pro+ ($50/mo, ~70 A100-hr) loses to RunPod hourly because (a) ephemeral disk forces bnb/FA2 reinstall every cold start, (b) A100 availability is queue-dependent, (c) 90-day unit expiry punishes intermittent users.
- Colab Pro $10/mo and Paperspace A100 ($3.09/hr) are false economy. Skip.
- H100 is wasted on 7B QLoRA — A100 wins on $/training-token; FP8 buys nothing through bnb 4-bit.
- GPU-class fit: T4/P100 = no bf16, no FA2 (Turing/Pascal SM<80) → free-tier only. L4/A10 24GB = sweet spot for Stage 2 + dev. A100 40GB = the only place A100 pays for itself, used for Stage 1 grind and release-candidate run.
- Vast.ai is cheapest on paper but driver heterogeneity routinely breaks bnb/FA2 installs; only viable with verified-CUDA host filtering.
- Provider gotcha: subscription notebooks (Colab/Lightning) hide the driver, so you can't pin CUDA — fine for prototype, real risk for the release-candidate loss curve.
- Preferred prototype setup: Lightning Pro $20/mo (Studio) + RunPod A100 hourly bursts (~$60/mo) + existing Azure $50 credit reserved for release-candidate. ~$130/mo soft cap.
- Artifact: `.squad/decisions/inbox/basher-gpu-subscription-fit.md`.

### Chinese GPU provider fit (2026-04-29)
- AutoDL/Featurize/Gpushare/MatPool/Dbcloud headline pricing is real: 4090 ~¥1.98/hr (~$0.27), A800-80G ~¥4.98/hr (~$0.69), H800 ~¥8.88/hr — roughly 30–60% under RunPod community for same GPU class. **Saves ~$30–$50 across our whole prototype, not enough to overcome friction.**
- 4090 / 4090D / A800 / H800 / L20 all run our recipe unchanged: CUDA 12.x, bnb NF4, flash-attn 2, bf16. 4090D is the China-export SKU and is ~5–10% slower than 4090 — irrelevant for QLoRA.
- **Real red flag is HF Hub push from inside the GFW.** Pulls work via `HF_ENDPOINT=https://hf-mirror.com`; pushes (our checkpoint-contract bus) are flaky. That breaks the provider-hop property of our chaining ADR. Workarounds (US-side relay, S3-compatible CN object store) all dirty the contract.
- Other gotchas: foreign cards rejected on consumer platforms (Alipay/WeChat + Chinese real-name only), GitHub clone is slow (use `--depth 1`, Tsinghua PyPI mirror), 150–200 ms SSH RTT from US, Chinese-only consoles outside AutoDL, PRC data law (PIPL/DSL) over training data.
- **Ascend 910B is a hard no for this prototype.** Different kernel ecosystem (CANN + torch_npu), no bitsandbytes NF4, no flash-attn 2; analog kernels (`npu_fusion_attention`, MindIE quant) are not what our recipe is calibrated against. Multi-week port for *worse* $/result than a 4090 on AutoDL. Reconsider only if scope leaves QLoRA.
- Alibaba/Tencent/Huawei Cloud (PAI/TI/ModelArts) are hyperscaler-priced without AutoDL's cheap-headline savings, and abstract the driver (same pinning concern as Colab/Lightning). No reason to choose them over RunPod/Lambda.
- **Recommendation: keep existing Kaggle + RunPod community + Lightning Pro + Azure-credit stack.** Chinese providers rejected on technical-fit grounds (HF push reliability, payment wall, English support), not pure cost grounds. Release-candidate run remains pinned to a non-PRC provider regardless.
- Durable rule: *cheap GPU $/hr only matters if your checkpoint bus survives the network it's on.* HF Hub push reliability is now part of the provider-fit checklist, alongside CUDA pinning and bnb/FA2 wheel availability.
- Artifact: `.squad/decisions/inbox/basher-china-gpu-fit.md`.

### Scribe orchestration: China GPU research (2026-04-29T04:40:54Z)

- Basher China GPU technical fit research (2026-04-29T04:40:54Z) documented in orchestration log.
- Decision advisory merged into `.squad/decisions.md` alongside Livingston's cost analysis.
- Inbox files deleted post-merge.
- Cross-agent: Livingston affirmed cost seams (registration, GFW friction) dwarf headline savings. HF Hub push reliability is now jointly acknowledged as a key provider-fit dimension affecting our checkpoint-contract ADR.

### Provider-switch handoff checklist (2026-04-29)
- User asked whether "push to HF / pull on next provider" is sufficient for provider switching. Answered: shape is right, but HF Hub only carries artifacts, not env or loop state.
- Portable unit is the **9-item checkpoint contract**: adapter, optimizer state, scheduler state, RNG, dataloader position, trainer_state.json, env.lock, base-model SHA pin, tokenizer SHA pin. Plus eval log alongside.
- Seams to watch on hop: bnb 4-bit kernel non-determinism across CUDA/arch, dtype (T4/P100 fp16 vs A10/A100 bf16 — don't toggle mid-stage), FA2 availability (SM≥80 only), global-batch-size preservation via recomputing grad_accum, dataloader-skip cost (use stateful dataloader), base/tokenizer revision pinning, eval-harness version pinning, provider path/secret differences, HF push reliability (PRC excluded).
- Sanity gate after resume on new provider: first cheap-eval point on B must match A's last within ±0.02 PPL; otherwise env isn't really restored — stop.
- Acceptable to switch: Stage 1 prototype, smokes, ablations, eval re-runs. Pin to one provider for: release-candidate Stage 1+2 final runs, gate-threshold-close decisions, anything FSDP/ZeRO-sharded.
- No new team-level decision; reaffirms existing "Chaining Free GPU Providers" ADR and Stage-1/Stage-2 pinning rules.

### Three-provider 60h window plan (advisory, 2026-04-29)
- User proposal: free-tier provider for prelim evals + data validation; 60h-compute provider for Stage 1 + merge + Stage 2 + evals; third provider for final eval. Approved in shape.
- Hard rule: Stage 1 + merge + Stage 2 stay pinned to one provider (one GPU class) inside the 60h. Provider switch only at stage *boundaries* with a ±0.02 PPL reproducibility gate on resume.
- Provider 1 owns the Stage-0 readiness gates: tokenizer audit, data foundation, eval harness, 0.5B smoke (local + Kaggle), pre-FT baseline on chosen 7B/8B, resume-from-HF demonstrated, ≤1h 7B warmup confirming bnb NF4 + FA2 throughput. None of this may bleed into the 60h.
- 60h budget on L4/A10/A100/4090 (NOT T4 — no bf16/FA2 on Turing): ~3% setup, ~2% smoke-resume sanity, ~40% Stage 1, ~3% Stage 1 gate, ~2% fp16 merge, ~20% Stage 2, ~3% Stage 2 gate, ~25% retries/contingency, ~2% buffer. One retry budgeted, not two.
- Provider 3 is eval-only: dtype/quant must match Provider 2; first eval point on a known checkpoint must reproduce ±0.02 PPL or eval is invalid. No training, no merging, no tweaks.
- Reaffirms existing ADRs (chaining feasibility, checkpoint contract, two-stage plan). No new durable decision required.
