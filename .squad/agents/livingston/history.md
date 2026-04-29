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

### Free-GPU Chaining Feasibility (2026-04-29)
- Question: can free GPU tiers (Kaggle 30hr/wk, Colab ~40hr/mo, Lightning ~20hr/mo, Modal $30/mo, SMSL 4hr/day, ZeroGPU) be chained into one big training budget by transferring weights between hops?
- Verdict: **technically yes, practically only for QLoRA iteration; never for a release run.** Combined ceiling ≈ 85 T4-hr-equiv/week with high friction.
- Required mechanics: HF Hub as checkpoint bus; save adapter + optimizer + scheduler + RNG + global_step; pin env (torch/transformers/peft/bnb/accelerate); keep effective batch constant across different GPUs; reproducible/seeded data.
- ToS: multi-accounting ONE provider (e.g., burner Kaggles) violates Kaggle ToS → ban risk. Using DIFFERENT providers under one real identity is fine.
- ZeroGPU is NOT a training target (per-call ~60s default, configurable to a couple minutes; quota is minutes/day). Use it for eval/inference only.
- SageMaker Studio Lab's 4hr/24hr cap makes it a poor primary; OK as overflow.
- Footguns: idle disconnects, no-GPU-guarantee on Colab free, bnb/CUDA kernel drift between providers, optimizer-state upload size, and engineering tax of every hop (~15–60 min).
- Recommendation: iterate on Kaggle alone (30 hr/wk P100 or 2×T4 is enough for QLoRA 7B); add Colab/Lightning/Modal only when a single experiment overflows; for the release run, pay $10–$40 for ~10–20 hr A100/H100 spot on Vast/RunPod/Lambda — current floors: Vast 3090 ~$0.05–0.13/hr, A100 80GB ~$0.29–0.73/hr; RunPod A100 40GB ~$0.42/hr spot.
- Doesn't change README's $10k–$30k practical tier or Azure-credit framing; this clarifies the bottom of the stack.
- Decision adopted: `.squad/decisions.md` (section "Chaining Free GPU Providers for LLM Training") — cost model, provider matrix, and recommendations consolidated with Basher's technical analysis.
- Session log: `.squad/log/2026-04-29T03-46-05Z-gpu-free-tier-chaining.md`.

### Paid GPU Subscription Research (2026-04-29)
- User asked: best paid subscription for GPU compute on this prototype.
- Current pricing snapshot (verified via web, late-2025/early-2026):
  - **Colab Pro** ~$9.99–$12.67/mo, 100 compute units, T4/L4 priority, sessions up to 24h but no guaranteed background execution; CUs ≈ 50 T4-hr or 8–10 A100-hr; 90-day rollover.
  - **Colab Pro+** $49.99/mo, 500 CU, **background execution up to 24h**, A100/L4 priority. Roughly 40–50 A100-hr-equivalent if everything goes A100; closer to 250 T4-hr in practice.
  - **Colab Pay-as-you-go** $9.99 / 100 CU, no subscription commitment.
  - **Lightning AI**: Free 15 credits/mo (~80 hr T4/L4 spot, 4-hr studio restart), **Pro $50/mo + 40 credits, 24/7 studios, multi-GPU, 2TB storage, A100 from ~$1.29/hr, H100 from ~$1.99/hr on spot**. Best "subscription" feel for serious iteration.
  - **Paperspace (DigitalOcean) Gradient**: Pro $8/mo + hourly, Growth $39/mo + hourly. Subscription only buys priority/storage; you still pay hourly for any real GPU. A100 ~$3.09/hr, H100 ~$5.95/hr — uncompetitive vs RunPod/Vast/Lambda.
  - **Modal**: Starter $0/mo with **$30 free compute credits each month**, per-second billing, T4 ~$0.59/hr, A100-40 ~$2.10/hr, H100 ~$3.95/hr. Serverless — great for eval/inference, idle = $0; long training is awkward (preemption, no persistent box).
  - **RunPod**: no subscription. Community A100 80GB ~$1.39–$1.49/hr, H100 $1.99–$2.99/hr; secure cloud higher. Persistent volumes, Docker, easy checkpoint to S3/HF Hub.
  - **Vast.ai**: spot/peer marketplace, no subscription. A100 $0.29–$0.67/hr, H100 $1.49–$1.87/hr. Cheapest, least reliable, ToS = trust the host; do not put sensitive data on random hosts.
  - **Lambda Cloud**: no subscription, on-demand A100 80GB SXM $1.79–$2.79/hr, H100 SXM $2.99–$3.99/hr; reservations cheaper. Reliable, premium, no spot.
  - **Kaggle**: still free (~30 hr/wk P100/2×T4, 9-hr session, no background). No paid tier; in 2026 you can link Colab Pro to Kaggle for a boost.
  - **HF Pro $9/mo + ZeroGPU**: inference/Spaces only, NOT a training target.
- Effective cost for one 7B QLoRA prototype run (~15–25 GPU-hr on A100 80GB): Vast ~$5–17, RunPod ~$21–37, Lambda ~$50–70, Modal ~$32–53, Colab Pro+ "free" within the $50 sub if you ride A100 priority, Paperspace $46–77 on top of subscription. Eval/short scripts: Modal's $30 free is effectively free.
- Subscription recommendation:
  - **Best low-cost subscription:** **Colab Pro+ $49.99/mo** for one-window-iteration, *or* **Lightning AI Pro $50/mo** if you want a real persistent IDE/disk. Lightning wins on engineering ergonomics, Colab wins on "just works" notebooks and 24h background.
  - **Best pay-as-you-go:** **RunPod community cloud** for actual training (predictable, persistent volumes, Dockerable). **Vast.ai** if cost is the only axis and the data is non-sensitive. **Modal** for short eval/inference and CI-style jobs (the $30/mo free credit is meaningful).
  - **Best serious one-off run:** **Lambda on-demand A100/H100** or **RunPod secure cloud** — pay $50–$200, get a clean environment, no marketplace risk. Not a subscription.
  - **What to avoid:** Paperspace Gradient (subscription buys very little, hourly is 2–4× the market); SageMaker Studio Lab (4-hr GPU caps); HF ZeroGPU for training; multi-accounting Kaggle/Colab to "stack" free tiers (ToS violation, ban risk).
- Caveats: spot prices on Vast/RunPod move daily; Colab CU-to-GPU mapping is opaque and Google has changed it before; Lightning credit allowance has changed historically; treat all numbers above as ±25% and re-check the pricing pages before committing.

### Chinese GPU Provider Pricing Research (2026-04-29)
- User asked whether Chinese GPU providers are cheaper for this prototype (7B/8B QLoRA, A100/4090/A800-class, checkpointed, HF sync).
- Pricing snapshot (verified via web search, late-2025 / early-2026; RMB→USD at ~7.2):
  - **AutoDL** (autodl.com) — RTX 4090 24GB ~¥1.98/hr (~$0.27); A100 40GB ~¥3.45/hr (~$0.48); A100/A800 80GB ~¥4.98/hr (~$0.69). Sources: autodl.com, neurowave.tech, sohu.com, idcsp.com.
  - **Featurize** (featurize.cn) — 4090 ~¥1.87–3/hr (~$0.26–0.42). A100 not consistently listed; market ~¥10/hr (~$1.40). Source: featurize.cn/vm/available.
  - **OpenBayes** (openbayes.com) — 4090 normal ¥2.3–2.5/hr (~$0.32–0.35); promo as low as ¥1.15/hr. A800 ~¥4.98/hr in market. Sources: openbayes.com/pricing, segmentfault, bilibili.
  - **Luchen Cloud** (cloud.luchentech.com) — 4090 reportedly ¥1/hr floor; A800 ¥4+/hr.
  - **Alibaba Cloud PAI/ECS gn7e** (China region, list) — A100 80GB ¥34.74/hr (~$4.80); A10 24GB ~¥12.71/hr (~$1.77); V100 ~¥26.46/hr (~$3.68). Enterprise list price; sustained-use/promos discount up to 30–50%. Source: aliyunbaike.com, hostol.com, cloudgputracker.com.
  - **Tencent / Huawei / Baidu Cloud** — comparable list-price tier to Alibaba; not competitive for hourly prototype work.
- Comparison vs prior recommendations (per Basher's advisory):
  - 4090: RunPod community $0.34–0.44 vs AutoDL $0.27 vs Featurize $0.26 → **~20–40% cheaper on Chinese commodity platforms**, but Vast.ai spot ($0.11–0.31) is in the same range or cheaper.
  - A100 40GB: RunPod community $1.19, Lambda $1.29 vs AutoDL ~$0.48 → **~50–60% cheaper** on AutoDL nominally.
  - A100/A800 80GB: RunPod $1.39 vs AutoDL ~$0.69 → ~50% cheaper.
  - Big enterprise clouds (Alibaba/Tencent/Huawei/Baidu) at list price are **2–4× more expensive** than RunPod/Lambda — not cheaper.
- Access constraints for a US-based individual (the actual story):
  - **Phone/ID:** AutoDL, Featurize, OpenBayes, Alibaba require **+86 mobile** for SMS verification at signup; full real-name (实名认证) typically wants a **Chinese ID card (身份证)**. Foreign passports are inconsistently supported; many features (top-up amount, model-hub access) gate behind real-name. Without a collaborator in China, registration is a dead end on most platforms.
  - **Payment:** RMB billing via **Alipay / WeChat Pay / UnionPay**; Alipay Tour Pass works for foreign cards but has caps and may be rejected for cloud top-ups; international credit cards usually not accepted directly.
  - **Great Firewall:** **Hugging Face is blocked or throttled** from mainland networks. Mirrors (hf-mirror.com, ModelScope) work for downloads but break `huggingface_hub` push/sync without proxy. **GitHub** is reachable but slow/intermittent; `git clone` often needs a mirror or proxy. Our pipeline assumes HF Hub as the checkpoint bus → significant friction.
  - **Export controls:** A100/H100 are restricted from China. What you actually rent is **A800 (NVLink 400 vs 600 GB/s), H800 (NVLink 300 vs 900 GB/s, FP16 ~250 vs 700+ TFLOPS), L20, H20**. For single-GPU 7B QLoRA the NVLink cap **does not matter** (we don't multi-GPU at this scope). For an 8×H800 release-scale run it would matter. Specs unchanged: per-card compute and VRAM are roughly equivalent for our prototype workload.
  - **Region/ICP:** Hosting public services on China-region Alibaba/Tencent requires ICP filing (备案) for a domain, which a foreign individual cannot get without a Chinese entity. Irrelevant for headless training, blocking for any inference endpoint.
  - **Documentation/support:** AutoDL/Featurize/OpenBayes UIs and docs are **Chinese-only**; English support is sparse. Alibaba Cloud International has English docs but its pricing is not the cheap China-region tier.
  - **Data sensitivity:** Hawaiian-language cultural corpus (per Linus's provenance work) on a PRC commercial cloud raises governance issues that have no upside for this learning project.
  - **MS employee context:** putting employer-adjacent or personal-research workloads on PRC commercial cloud is a separate policy minefield; user should not assume it's neutral.
- Recommendation:
  - **Do not move this prototype to Chinese providers.** The headline savings (~$0.20–0.70/hr × ~15–25 prototype hours = $3–18) are **dwarfed** by registration impossibility (no +86 phone / Chinese ID), HF Hub friction, language/support barrier, and data-governance optics on a Hawaiian cultural corpus.
  - **When Chinese providers WOULD be cheaper and worth it:** team member physically in China with real-name verification; sustained months of 4090-class iteration (AutoDL monthly is meaningfully under RunPod); workload that does not need HF Hub; non-sensitive data.
  - **When they're NOT worth it (this project):** US-based individual, prototype scope, HF Hub-centric checkpointing, sensitive cultural data, current plan already at RunPod community / Lambda / Azure-credits floor.
  - **Big Chinese enterprise clouds (Alibaba/Tencent/Huawei/Baidu) are NOT cheaper** than RunPod/Lambda at list price — that "China is cheaper" intuition only holds for the AutoDL/Featurize/OpenBayes-tier marketplaces.
- Decision note: advisory only; written to `.squad/decisions/inbox/livingston-china-gpu-pricing.md` for team awareness. Does not change the README budget or vendor recommendations.

### Data Storage for Prototype (2026-04-29)
- Question: GitHub repo vs Git LFS vs HF Datasets vs S3/R2/B2 vs local disk for tens of GB of WARC/OCR/native.
- Verdict: **hybrid**. Git for code + schemas + URL inventories + small configs; local external disk as primary working store for `data/`; off-site backup of `data/raw/` (immutable, SHA-256 keyed) on Azure Blob Hot LRS while leftover credits last (<$2/mo, fits inside the existing $50–60/mo experiment envelope), migrating to **Backblaze B2** (cheapest) or **Cloudflare R2** (zero egress, best when shipping shards to rented GPUs) once Azure access ends.
- Rejected: GitHub repo (file/repo size caps, public-by-default risk), Git LFS (bandwidth-priced data packs are hostile to dataset workloads), HF Datasets private (third-party platform for a rights-sensitive cultural corpus before Linus's licensing review = wrong order), AWS S3 standard (egress kills it once we pull shards to GPU rentals).
- Reuses existing `.gitignore` (`data/` already excluded) and `docs/data-pipeline.md` invariant #4 ("Raw archive is immutable, SHA-256 keyed, and not in git. Storage location TBD") — this note closes that gap.
- Guardrails: private bucket, SHA-256 object keys (not URLs/titles), no CDN, manifests carry license/provenance not blob names, sources of uncertain redistributability stay local-only until Linus clears them.
- HF Hub stays reserved for adapter/checkpoint bus and eventual *releasable* derived artifacts — never the raw corpus at prototype scope.
- Decision note: `.squad/decisions/inbox/livingston-data-storage-prototype.md`.

### Scribe orchestration: China GPU research (2026-04-29T04:40:54Z)

- Livingston China GPU pricing research (2026-04-29T04:40:54Z) documented in orchestration log.
- Decision advisory merged into `.squad/decisions.md` alongside Basher's technical fit analysis.
- Inbox files deleted post-merge.
- Cross-agent: Basher affirmed HF Hub push reliability is now part of provider-fit checklist (alongside CUDA pinning). This hardens our checkpoint-contract ADR.

## 2026-04-29T10:46:19Z — Basher learning skeleton complete; framework ADR remains gate for serious eval harness

**From:** Scribe (Cross-agent context)

**Update:** Basher delivered learning skeleton and Llama-3.1-8B config; all decisions now in main.

**Skeleton implications for your eval work:**
- `code/llm_hawaii/evaluate.py` is learning-scope template with TODO for run-report writer (matching `docs/eval_pipeline.md` §8).
- Your run-report schema and checkpoint evaluation harness remain unchanged. Basher's module is a learning skeleton, not your infrastructure.
- Manual micro-eval (Rusty + Linus) and FineWeb-2 slicing remain the real eval surface for prototype training.

**Framework ADR still gates serious code:**
- Basher's skeleton uses PyTorch + HF as learning path, but framework is not yet pinned for production. ADR remains gate before any real training eval loop is wired.
- Smoke-tier baseline measurement (Qwen2.5-0.5B) can proceed without framework ADR (it's local sanity). Serious runs wait on framework decision.

**Reference:** `.squad/decisions.md` → "Decision: PyTorch + Hugging Face for the Learning Skeleton under `code/`".

## 2026-04-29T10:49:36Z — Vendor observation: Lightning AI unlimited sessions with L40S availability

**From:** Scribe (Cross-agent context)

**Update:** User flagged Lightning AI Free plan: L40S has unlimited session time (vs 4-hr cap on A100/H100), 15 credits/mo free, pay-as-you-go overage.

**Your verification requested:**
- **Credit burn on L40S at typical prototype batch:** ~15/mo at current rates → estimate actual training hours before overage kicks in (likely 4–8 hrs for a full 7B Stage-1 run). Is that within prototype iteration budget?
- **Idle timeout / background execution limits:** Does free tier cap session duration differently from "unlimited"? (Common friction on Colab/Modal.) Will long-running training get killed by provider, or is it truly 24/7-capable?
- **Storage/egress for HF Hub sync:** Lightning advertises 2TB storage on Pro; confirm free tier doesn't throttle egress (critical for checkpoint pushes to HF Hub mid-training).
- **Exact SKU confirmation:** L40S 48GB, not a downgrade variant? SKU drift happens.
- **Preemption risk:** Does free tier guarantee preemption-free execution, or do interruptions happen? (Affects reproducibility.)

**Advisory framing:** If L40S checks out (credit efficiency, no edge-case timeouts, stable CUDA/bnb compat per Basher), it's a practical mid-tier option for iteration **at lower cost than A100 spot.** Current recommendation stays: Kaggle for cheap iteration + RunPod/Lambda A100 for final runs. Lightning L40S would slot between them if details pan out.

**Do NOT adopt without cost/limit verification.** Unlimited session time ≠ unlimited credit.

**Reference:** `.squad/decisions.md` → "Vendor Observation: Lightning AI Free Plan (2026-04-29T10-49-36Z)"

## 2026-04-29T14:00:00Z — Prototype Journey Compute Factcheck

**Deliverable:** `docs/prototype-journey-compute-factcheck.md` — a concise reference for Danny and the Coordinator on the three-provider handoff strategy, checkpoint portability contract, why provider hopping works for prototypes but is fragile for release, and the real blocker (tokenizer audit, not infrastructure).

**Scope covered:**
- Why checkpoint bus (HF Hub) enables provider hopping + the fragility knots (bnb kernel drift, fp16 rounding, FA2 variance).
- Portability contract: model ID, tokenizer SHA, adapter format, env.lock, dataset manifest SHA, eval-hashes SHA, RNG seed, optimizer/scheduler state.
- Contamination guard: CPU-runnable, model-dependent on tokenizer ID but not a provider-hopping blocker.
- Why tracking provider SKU names and CUDA versions in run reports enables forensics.
- Slide-ready framing for free/low-cost GPU provider chaining.
- Open questions: tokenizer audit access (gated Llama, human gate), Provider 2 vendor selection (decision pending), contamination guard remains human-owned.

**Key message:** Provider hopping is safe between stages and frees us from committing $500+ upfront to a subscription. The three-provider split buys fault isolation, cost reduction, and reproducibility validation. The real blocker is the tokenizer audit gate and the go/no-go decision, not infrastructure.

**Note:** Document is PowerPoint-ready, includes no tool internals or SQL, and avoids claiming production-grade readiness.
