# Prototype Journey: Compute & Provider Strategy

> A concise reference for Danny / the Coordinator on why and how we hop GPU providers during prototype iteration without breaking the pipeline.

---

## Executive Summary

This prototype iterates through **three provider stages** by handoff, not a single paid run. Provider 1 (free) builds and validates all Stage 0 artifacts. Provider 2 (paid, 60-hour stable block) runs the model training in strict sequence — no mid-stage provider swaps. Provider 3 (fresh environment) re-validates headlines to catch silent hardware-drift bugs.

**Why it works for prototypes:** Checkpoints are portable across providers if we pin what matters (model ID, tokenizer revision, adapter format, configs, environment lock). **Why it's fragile for production:** bnb 4-bit kernels and fp16 semantics drift subtly between CUDA versions and GPU architectures; if you hop mid-stage, your loss curve becomes uninterpretable.

---

## Portability Contract: What Must Travel Between Providers

Every checkpoint that leaves one provider must carry these artifacts forward unchanged, or the next provider's eval becomes scientifically unreliable:

### **Immutable Identity**
- **Base model ID:** e.g., `meta-llama/Llama-3.1-8B` (exact repo path + revision SHA from Hugging Face)
- **Tokenizer ID + revision:** matches base-model repo tokenizer; frozen at Stage 1 start; re-validated at Stage 2 load
- **Tokenizer fingerprint SHA-256:** computed once on audit; re-check on each resume to catch silent vocab drift

### **Training Artifacts**
- **Adapter weights** (LoRA rank/alpha/target-modules frozen)
- **Optimizer state** (for resume; drop-if-restarting, but hurts reproducibility)
- **Scheduler state** (global step, learning-rate schedule phase)
- **RNG seed** (trainer seed + dataloader seed for determinism)
- **Dataloader position** (sample index / epoch to avoid data leakage on resume; or restart from epoch 0 and accept ~1% sample redraw)

### **Configuration & Environment**
- **`env.lock`** — pinned torch, transformers, bitsandbytes, accelerate, peft versions (exact, not ranges)
- **Training config** (sequence length, batch size, LoRA hyperparams, dtype flags, quantization settings)
- **Dataset manifest SHA** (Stage 1 corpus and eval-hashes contract; proves no train/eval contamination)
- **Eval-suite SHA** (harness code version; changes = different numbers)

### **Provenance & Ledger**
- **Run report metadata** (timestamp, hardware class used, wallclock hours, loss checkpoints, eval snapshots)
- **Eval ledger** (`eval_hashes.jsonl` SHA; contamination-guard input contract; must be identical across all three providers)
- **Stage-specific gate artifacts** (Stage 1 PPL baseline, Stage 2 chrF baseline; needed to judge next stage)

---

## Why Provider Hopping Works for Iteration

### **Checkpoint Bus: Hugging Face Hub as the Handoff Point**

Each provider saves every 200–300 steps to a **private Hugging Face Hub repo**. The checkpoint includes adapter + optimizer + scheduler + RNG in a standard format (.safetensors / .bin). When Provider 1 finishes Stage 0 setup and Qwen-0.5B smoke tests pass, the frozen bundle lives in HF Hub. Provider 2 pulls it, resumes, and continues. When Provider 2 finishes Stage 1 and Stage 2, the final checkpoint is available for Provider 3 eval.

**Why this is safe:**
- HF Hub push/pull is deterministic; SHA-verified downloads catch corruption.
- The checkpoint format is standardized across providers (PyTorch universal).
- The dataloader can restart from the same manifest + seed, producing deterministic batches.

**What breaks it:**
- If env.lock drift is not caught (e.g., transformers 4.40 vs 4.41 changes how rotary embeddings are cached), the resumed training diverges subtly after ~500 steps.
- If you forget the RNG seed, resumed training still trains correctly but burns old data a second time, muddying the learning curve interpretation.
- If CUDA/bnb version differs, 4-bit quantization produces slightly different values on the same input weights, and resumed training meanders.

### **Smoke Test Contract**

Before any paid provider sees the model, Provider 1 runs a micro-smoke-test on Qwen-0.5B (both Stage 1 + Stage 2 path, tiny slices):
1. Checkpoint locally on RTX 2080 (cpu-quantizable).
2. Resume from that checkpoint on Kaggle (T4 / P100, different GPU arch).
3. Confirm loss-curve shape and eval metrics match within ±0.02 PPL.

If the smoke test survives the Kaggle resume, Provider 2 and Provider 3 survive it too (same checkpoint mechanism, just larger model and real corpus).

---

## Why Provider Hopping is Fragile for Release

### **The Fragility Knots**

1. **bnb 4-bit kernel instability across CUDA versions:**
   - CUDA 11.8 + bnb 0.42 quantize `float32 → nf4` with specific rounding on Turing GPUs.
   - CUDA 12.1 + bnb 0.43 may round the same `float32` to a different `nf4` value by ±1 bit.
   - On resume after one step, the model weights are identical, but the first gradient-update lands in a different spot in loss-space. Over 1000 steps, this compounds and your loss diverges 0.5 PPL.

2. **fp16 accumulation and allreduce differ by hardware generation:**
   - Tensor Cores on A100 fuse fp16 matmul+accumulate with specific roundings.
   - NVIDIA H100 Tensor Cores have different accumulator precision; same math produces slightly different fp16 sums.
   - After provider switch mid-training, the gradient updates diverge.

3. **Flash-Attention-2 implementations vary by driver and GPU family:**
   - FA2 on A100 vs L40S produces different numerical outputs (correct mathematically, but not bitwise identical).
   - If you train Stage 1 on A100 and resume on L40S mid-epoch, attention gradients become non-deterministic and loss curve noise spikes.

4. **Checkpoint format drift (rare but real):**
   - If HF transformers library version changes how it saves/loads adapter configs between picks, resume fails silently or produces wrong behavior.

### **Release Implication**

For a production release, you **must** publish not just the checkpoint but the exact `env.lock` that produced it. Users who diverge (even slightly, e.g., transformers 4.37 → 4.38) get different results and cannot reproduce your reported eval numbers.

This prototype avoids that problem by staying **internal-only:** all three providers are under our control, env.lock is pinned by us, and the final report is an internal artifact, not a public benchmark.

---

## Tokenizer Audit: The Real Spend Gate (Not Provider Hopping)

The blocker for any serious Llama-3.1-8B Stage 1 spend is **not** provider selection — it is the **gated tokenizer audit.**

### **What Must Pass Before Serious Spend**

The tokenizer audit (a planned test; no standalone script in the repo today) must:
1. Load the real Llama-3.1-8B tokenizer (requires Hugging Face login + access grant from Meta).
2. Run on representative Hawaiian slices (≥1,500 words, ≥10 high-diacritic samples from nūpepa, Baibala, contemporary text).
3. Report:
   - **tokens/word** on overall and high-diacritic subsets (threshold: ≤2.50 overall, ≤3.25 high-diacritic).
   - **ʻokina survival rate** (do standalone ʻokina chars tokenize to ≤2 tokens? do they stay at U+02BB after model generation, or collapse to apostrophe/U+2018?).
   - **Kahakō survival** (are marked vowels preserved or split into combining sequences?).
   - **Explicit byte-fallback rate** (any `<0x..>` tokens? must be 0).
   - **Combined fallback/proxy rate** (≤1%).
   - **Recommendation decision:** `go` or `no_go`.

### **If it says `go`:**
- Base model SHA and tokenizer SHA are **frozen** in Stage 1 manifest.
- Stage 1 can proceed on Provider 2 (any of RunPod/Lambda/Azure spot, L4/A10/A100, within 60h).

### **If it says `no_go`:**
- Fallback: try Qwen-2.5-7B or Gemma-2-9B tokenizer audit.
- Or: propose vocab-surgery (extend Llama vocab with standalone Hawaiian diacritics, retrain embeddings/lm_head on Stage 1 data).
- Or: accept tokenizer-split ʻokina and commit to post-generation canonicalization in Stage 2.
- Do not fabricate an audit result; do not spend money to "see what happens."

**Current status:** The tokenizer-audit gate is defined but not yet runnable in this repo — no standalone audit script is checked in, and a tokenizer-audit test is planned. The real run (with gated Llama access) is also blocked on Hugging Face credentials. This is a human gate, not an infrastructure gate. Once credentials and the test land, the audit takes ~2 GPU-minutes (T4 sufficient), but the decision to proceed or fallback sits with Rusty and Danny.

---

## Contamination Guard: CPU-Runnable, But Model-Dependent

The contamination guard is **not** a reason to avoid provider hopping. Here's why:

### **What the Guard Does**

`eval_hashes.jsonl` contains SHA-256 hashes of every held-out eval sample (FineWeb-2 holdout + W1 manual eval), normalized to NFC. At training time, the dataloader hashes every training batch and asserts **zero intersection** with eval hashes.

### **Why it's CPU-Runnable**

Hashing is CPU-bound, not GPU-bound. The tokenizer (model-dependent) is also CPU-runnable if transformers is installed. So the guard can run on any provider's CPU node (or locally on RTX 2080) in ~minutes for a 50MB corpus.

### **The Constraint: Same Tokenizer ID**

The guard hashes **normalized text, not tokens**, so tokenizer choice does not affect hashing itself. However:
- The **manifest** (FineWeb-2 normalization audit) was built with a specific base-model tokenizer assumption (e.g., Llama-3.1-8B).
- If you switch base models (e.g., Qwen-2.5-7B tokenizer), the manifest is still valid (hashes haven't changed), but the **stage-1-to-stage-2 tokenizer continuity** breaks (Stage 2 uses a different tokenizer, so embedding/lm_head mismatch).

**Provider implication:** This doesn't prevent provider hopping. It just means **do not change the base model mid-training.** Provider 2's single GPU-class rule already enforces that.

---

## Why Tracking Provider Names & Config Knobs Matters

### **The Real-World Problem**

Different providers expose different names for the same GPU class:
- **AWS:** `g4dn.xlarge` (T4), `p3.2xlarge` (V100), `p3.8xlarge` (8×V100).
- **RunPod:** `RTX 4090`, `A100 80GB`, `H100 PCIe`.
- **Lambda:** `A100 80GB SXM`, `H100 SXM`.
- **Azure:** `Standard_NC6s_v3` (Tesla V100), `Standard_ND96amsr_A100_v4` (A100 40GB), `Standard_ND40rs_v2` (8×A100).
- **Vast.ai:** peer-listed by SKU name + VRAM, no canonical naming.

Same GPU, different names. Easy to book the wrong thing.

### **What Must Be Tracked per Provider**

In the run report, log:
- **Provider name** (RunPod, Lambda, Azure, Vast, Kaggle, etc.)
- **GPU SKU as booked** (exact name from provider's console, screenshot if ambiguous)
- **Actual GPU model** (via `nvidia-smi` in the container, e.g., `NVIDIA A100 80GB SXM4`).
- **CUDA version** (from `nvcc --version`).
- **Compute Capability** (from `nvidia-smi` SM field, e.g., SM 8.0 for A100).
- **bitsandbytes version** (from `pip show bitsandbytes`).
- **torch version** (from `torch.__version__`).
- **Number of GPUs** (1 for this proto; multi-GPU provider billing rules differ).

### **Why This Matters for Provider Hopping**

If Provider 2's A100 diverges in loss-curve compared to Provider 1's smoke test, the first debugging question is: "did the GPU actually change?" You need this metadata to answer it.

Example forensics:
- Provider 1 Kaggle: Tesla P100, SM 6.0, CUDA 11.2, bnb 0.40.9 → loss 4.52, loss_delta -0.03/step.
- Provider 2 RunPod A100: Tesla A100-PCIE, SM 8.0, CUDA 12.1, bnb 0.43.0 → loss 4.49, loss_delta -0.025/step (slower convergence).

The divergence is real hardware (SM 8.0 vs 6.0) + CUDA (12.1 vs 11.2) + bnb (0.43 vs 0.40). Would switching to a different RunPod help? Maybe if the other A100 has CUDA 11.8. You can't decide without the metadata.

---

## Slide Wording: Free/Low-Cost GPU Provider Hopping for Prototypes

**For PowerPoint / presentation:**

> ### Provider Hopping for Prototype Iteration
> 
> **Why it works:** Checkpoints are portable across free-tier and paid GPU providers if we pin the checkpoint contract (model ID, tokenizer SHA, LoRA format, env lock) and use Hugging Face Hub as a deterministic handoff point.
> 
> **The three-stage strategy:**
> 1. **Provider 1 (free):** Stage 0 smoke tests on Kaggle P100 / Colab T4 + local RTX 2080. Validates plumbing, not compute cost.
> 2. **Provider 2 (paid, 60h block):** Stage 1 CPT + fp16 merge + Stage 2 SFT on **one GPU class** (A100 / A10 / L40S — no switches mid-stage). Provider could be RunPod, Lambda, Azure spot, or Lightning. Output is frozen and uploaded to HF Hub.
> 3. **Provider 3 (eval-only):** Final eval on a different environment to catch silent hardware drift. Reproducibility gate ensures numbers are not artifacts of GPU-specific quantization quirks.
> 
> **Why it's fragile for release:** bnb 4-bit kernels, fp16 accumulation, and Flash-Attention-2 implementations vary subtly between CUDA versions and GPU architectures. Hopping **mid-stage** poisons the loss curve. Production releases require exact env.lock publication so users can reproduce. This prototype avoids that by staying internal and under our control.
> 
> **Cost implication:** Frees us from committing to one paid provider for ~60h upfront. We can iterate on Kaggle free tier, only scaling to paid A100 (~$20–50 for the full run) after Stage 0 readiness is proven. Cuts prototype risk vs committing to a $500+ three-month subscription.

---

## Open Questions & Caveats

### **Tokenizer Audit Access (Blocker)**

The gated Llama-3.1-8B tokenizer requires:
- Hugging Face account with Meta's model access grant (filled out separately).
- `huggingface-cli login` token with `read` permission.
- `transformers >= 4.36` with gated-model support.

**Unblock path:** User logs in locally, script runs, audit report is committed to ignored `data/tokenizer_audit/`. Decision (go/no_go) is human. Only after `go` does Provider 2 get a training order.

### **Provider 2 Vendor Selection (Open Decision)**

Currently under discussion: RunPod community A100, Lambda on-demand A100, or Azure A100 spot. Each has tradeoffs:
- **RunPod:** cheapest (~$1.39–1.49/h A100 80GB), easiest Docker, persistent volumes for checkpoint writes, smallest support footprint. Risk: community cloud reliability (rare crashes).
- **Lambda:** highest reliability, fast on-demand provisioning, no marketplace risk. Cost ~$2.79–2.99/h A100 80GB (2–2.5×).
- **Azure spot:** existing user credits (~$150/mo), spot pricing ~$0.50–0.80/h for A100 on US region, auto-shutdown on quota spike. Risk: zero-notice preemption.
- **Lightning AI Pro:** $50/mo subscription + $1.29/h A100, unlimited session time, best IDE ergonomics for iteration. Middle ground.

**Impact on portability:** All support HF Hub push/pull and standard PyTorch save/load. Choice does not affect checkpoint portability; only cost and time-to-provision.

### **Contamination Guard Remains Human-Owned**

The dataloader-side assertion (`train ∩ eval_hashes = ∅`) is code-checked but **not enforced by the framework**. If a training script accidentally imports eval-hashes at the wrong moment, or if the manifest update skips the eval-hash intersection check, contamination can happen silently.

**Mitigation:** CI asserts the intersection on every manifest rebuild. Unit tests force the guard to fire when handed a planted positive (an eval-hash inside the training data). Runs without a green CI pass do not promote to evaluation.

---

## Summary for Danny / Coordinator

This prototype is **architecture-level robust to provider hopping during Stage 0 and between stages**, but **not mid-stage**. The three-provider split buys us:

1. **Cost reduction:** Iterate on free Kaggle (~$0), final model on $20–50 A100 spot, total ≤$100–200 vs $500+ for a three-month subscription or a single big paid run.
2. **Fault isolation:** A Provider 1 bug (bad smoke test) doesn't burn the paid window. A Provider 2 bug (stage-1 loss spike) triggers a retry on the same provider with diagnostics, not a pivot to a new provider.
3. **Reproducibility validation:** Provider 3 proves the numbers are not a Provider 2 quirk (e.g., CUDA rounding artifact) by re-running the gate eval on a different hardware target.

The **real blocker** is not provider selection — it is the tokenizer audit gate and a human decision (go/no_go). Once that passes, the execution is rote: Provider 2 runs the 60-hour block, Provider 3 validates, and we have a prototype checkpoint and report.

Tracking provider names and hardware SKUs in every run report is hygiene, not optional; it enables forensics if Provider 2 and Provider 3 disagree.

---

*Generated 2026-04-29T14:00:00Z by Livingston (Cost Strategist)*
