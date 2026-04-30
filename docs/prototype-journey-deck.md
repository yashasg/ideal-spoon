# Hawaiian LLM Prototype: Your Journey
## A PowerPoint-Ready Decision & Learning Arc

---

## PREFACE

This is **your learning project's decision journey**—documented as a design artifact, not a release roadmap. Every major decision you faced is captured below with options considered, the choice made, and the trade-off accepted. The sections are structured as PowerPoint slides with speaker notes so you can tell the story of building a prototype that works through hard questions about data, models, infrastructure, and evaluation **without claiming any benchmark success or public release.**

---

## TABLE OF CONTENTS (Slide Deck Outline)

1. **Title & Context** ← You are here
2. **What is this project?** (Prototype scope)
3. **Decision #1: Train from scratch vs. adapt an existing model**
4. **Decision #2: Where to get Hawaiian text?**
5. **Decision #3: FineWeb-2 as the main Stage 1 data source**
6. **Decision #4: Why split training into two stages?**
7. **Decision #5: How to protect against eval contamination?**
8. **Decision #6: Manual Hawaiian-literate review for evaluation**
9. **Decision #7: Tokenizer audit—why it blocks spending**
10. **Decision #8: GPU provider strategy for prototypes**
11. **Decision #9: How to handle provider differences?**
12. **Decision #10: Human-owned contamination guard**
13. **Decision #11: Stage 2 parallel-data skeleton**
14. **What's done, what remains, and what you learned**
15. **Appendix: Key Artifacts & Scripts**

---

## SLIDE 1: Title Slide

**Title:**  
*Hawaiian LLM Prototype: A Learning Journey*

**Subtitle:**  
Building in public with honest trade-offs. No release planned.

**Speaker Notes:**  
This deck documents your journey building a Hawaiian-language LLM adaptation prototype over ~7 weeks. The goal was **not** to ship a model, but to think through hard questions: How do you adapt a multilingual model for a low-resource language? Where do you find Hawaiian text that you can use responsibly? How do you evaluate something that requires human judgment? What does it cost? This is the story of the decisions you made and why.

---

## SLIDE 2: What Is This Project?

**Headline:**  
A **private prototype and learning effort.** No weights, datasets, or APIs planned for public release.

**Bullets:**
- **Scope:** Design exercise + team learning
- **What exists:** Planning docs, team decisions (ADRs), infrastructure code, evaluation harness, data manifests
- **What does NOT exist:** Training code, model weights, real training runs, benchmark numbers, public API
- **Why public-learning?** Keep the design honest so others learn from the trade-offs, not just the outcome

**Speaker Notes:**  
This project lives in a repo with code, configs, and design docs, but **no real data or weights are committed or planned for release.** The value is the journey itself: working through how you'd actually do this if you had to, documenting the failures and trade-offs. This is explicitly *not* a productization roadmap. That distinction matters because it lets you make decisions based on learning, not release velocity.

---

## SLIDE 3: Decision #1 — Train from Scratch vs. Adapt?

### The Decision
**Adapt an existing multilingual model (Llama-3.1-8B, fallback Qwen2.5-7B)**

### Options Considered
| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **Train from scratch** | Full control, no upstream bias | Impossible at $10k–$30k budget; Hawaiian is low-resource | ❌ |
| **Adapt multilingual 7B–9B** | Leverages Polynesian signal from pre-training; fast to iterate; stays in budget; QLoRA keeps memory low | Tokenizer may not handle ʻokina/kahakō well; depends on audit | ✅ |
| **Use a Hawaiian-only model if it existed** | Perfect fit | Doesn't exist | N/A |

### Key Trade-Off
**Speed and cost vs. control.** You give up starting-from-scratch purity to get something you can actually build in your budget and timeframe. The upside: you can iterate faster and focus effort where it matters—tokenization, data quality, and eval rigor.

### Speaker Notes
The budget says $10k–$30k total. That's roughly 60 GPU-hours on a mid-tier cloud provider, plus data/eval labor. From-scratch pretraining on Hawaiian alone would burn most of that budget on compute and produce worse results than adapting a model that has already learned language structure from larger multilingual corpora. The bottleneck is **not GPU cost**; it's data quality, tokenizer fit, and whether you can measure progress honestly. So you adapt. The scary part? You don't get to validate the tokenizer choice until you actually run the audit, which is blockers for real spend.

---

## SLIDE 4: Decision #2 — Where to Get Hawaiian Text?

### The Decision
**Prioritize public-domain sources and openly licensed materials; default to exclusion if cultural posture is unclear.**

### The Data Landscape
| Source | License/Posture | Status | For Prototype? |
|---|---|---|---|
| **Ulukau.org nūpepa** | Publicly readable; copyright/community posture complex | Publicly available | ✓ Yes, with `prototype_only=true` tag |
| **Bible texts** (Baibala Hemolele, modern editions) | Pre-1929 = PD; modern = unclear | Mixed | ✓ PD texts, with register-balance note |
| **FineWeb-2 Hawaiian slice** | CC-0 licensed crawl | Available via Hugging Face | ✓ Main Stage 1 source |
| **JW300 parallel** | Gated; TOS unclear | Deferred | ❌ Blocked until TOS review |
| **Tatoeba** | CC-BY-2.0 pairs | Available | ⏳ Planned for Stage 2 eval anchor |
| **Named tradition-bearer oral history** | High cultural sensitivity | Exists but not digitized | ❌ Excluded; needs named consent |

### Key Trade-Off
**Inclusivity vs. safety.** You could scrape more Hawaiian text from the web, but each source comes with a cultural and legal posture question. You've chosen to be **conservative**—default to "no" until you can answer "yes" with confidence. This means slower corpus growth but honest provenance.

### Speaker Notes
This is the hardest decision architecturally. Hawaiian language revival is a cultural project, not just a technical one. You have sources like ulukau.org that are publicly readable, but "publicly readable" ≠ "OK to scrape for ML training." So you treat each source carefully: document the license, document the cultural sensitivity, tag prototype-only rows so they never leak into a release, and explicitly exclude categories (mele, oli, pule, moʻolelo from named tradition-bearers) until you have a cultural-review owner. That owner isn't assigned yet. That's a blocker for release, but for prototype-learning work, it's an explicit gap you're naming.

---

## SLIDE 5: Decision #3 — FineWeb-2 as Stage 1's Main Source

### The Decision
**Use FineWeb-2 `haw_Latn` (CC-0 crawl) as the primary Stage 1 monolingual corpus; other sources are gated/backlog.**

### Why FineWeb-2 Won
| Criterion | FineWeb-2 | Web scrape | nūpepa | Bible |
|---|---|---|---|---|
| **License clarity** | CC-0, unambiguous | High ToS risk | Complex cultural posture | Mixed (PD / unclear) |
| **Scale** | ~100k rows available | Unbounded | ~3–5k total | ~5–10k pairs |
| **Recency signal** | Modern Hawaiian | Varies | 19th-century heavy | Period/biblical register skew |
| **Coverage** | Broad web domains | Likely toxic | Curated but historical | Religious narrow |
| **Prototype-ready now** | ✓ Yes | ? Risky | ⏳ Needs audit | ⏳ Register analysis needed |

### The Numbers
- FineWeb-2 `haw_Latn` test split: **887 official test rows**
- After cleaning (removing boilerplate, exact dedupes, low-Hawaiian-score): **~79,812 rows from 95,507 seen**
- Token reduction after normalization & cleanup: **59.5M → 44.1M tokens** (26% reduction)
- Dev/holdout split: **621 dev / 266 held-out** (70/30 rule, stable deterministic split)

### Key Trade-Off
**Scope creep vs. speed.** You could spend weeks acquiring more diverse sources—nūpepa archives, Bible variants, specialized corpora. Instead, you pick FineWeb-2, clean it rigorously, split it carefully, and move on. The upside: you start Stage 1 faster. The downside: your prototype will be skewed toward modern web Hawaiian, which may not represent all registers equally.

### Speaker Notes
FineWeb-2 was a lucky find: a recent, openly licensed, Hawaiian-labeled web crawl that you can actually download and use without legal overhead. Yes, web text is noisier than curated sources. But the noise is manageable: you normalize Unicode to NFC, canonicalize ʻokina, drop boilerplate paragraphs, and dedupe exact repeats. You lose 26% of tokens in the process, but what remains is reasonably clean. The key discipline: **JSONL manifests are canonical, not raw text.** Every row records its origin, license, OCR confidence, and cultural tags. That means you can reason about the corpus later without re-doing the fetch/clean.

---

## SLIDE 6: Decision #4 — Why Two Training Stages?

### The Decision
**Stage 1: Monolingual Hawaiian CPT/DAPT. Stage 2: Bidirectional en↔haw SFT on parallel pairs.**

### The Shape
```
[Base multilingual model]
         ↓
[Stage 1: QLoRA r=64 on Hawaiian monolingual text]
         ↓
[Merge Stage 1 LoRA into fp16 base]
         ↓
[Stage 2: Fresh QLoRA r=32 on parallel en↔haw pairs + retention slice]
         ↓
[Evaluation suite]
```

### Why Two Stages, Not One?
| Aspect | One-stage SFT | Two-stage (Stage 1 + Stage 2) |
|---|---|---|
| **Monolingual signal** | Weak; base hasn't re-learned Hawaiian | Strong; base is Hawaiian-adapted before SFT |
| **Catastrophic forgetting** | Model trains on pairs only; can't speak Hawaiian monologically | Stage 1 adaptation + Stage 2 SFT means model learns Hawaiian fluency first, then learns to translate |
| **Eval clarity** | If SFT fails, you don't know if it's the pairs or the base | Stage 1 eval gates let you confirm adaptation happened *before* trying SFT |
| **Compute efficiency** | Fewer LoRA adapters | One merge; efficient reloading |
| **Debugging** | Single knob to turn; hard to diagnose | Two gates; each stage has a clear success criterion |

### Key Trade-Off
**Simplicity vs. robustness.** A one-stage SFT is simpler to code and reason about. Two stages add complexity: you need to merge adapters, validate the merge doesn't break things, reload the model. But you get a much clearer signal about what worked and what didn't. This matters for a learning project where "why" is as important as "whether."

### Speaker Notes
The two-stage split comes from the insight that **Hawaiian is a language first, and translation is a downstream task.** If you train SFT pairs directly on a base that has no Hawaiian, you're fighting forgetting the whole time. By adapting the base to Hawaiian *first* via monolingual pretraining, you give the model a foundation. Then Stage 2 SFT is about refining that foundation into a translation capability. This also buys you evaluation clarity: Stage 1 has clear gates (Hawaiian PPL drops, ʻokina survives), and Stage 2 gates measure translation quality (chrF in both directions). If either fails, you know where to look.

---

## SLIDE 7: Decision #5 — Eval Contamination Guard

### The Decision
**Build a canonical JSONL eval-hash ledger; enforce `train ∩ eval = ∅` at manifest-build time and training-loader time.**

### The Ledger
**File:** `data/evals/eval_hashes.jsonl`  
**Purpose:** Centralized record of every held-out eval item (hash, origin, split, normalization method)

**Per-row fields:**
```json
{
  "schema_version": "eval-hashes-jsonl-v1",
  "sha256_normalized": "abc123...",
  "hash_method": "sha256",
  "normalization_method": "NFC",
  "origin": "fineweb2_haw_test" | "manual_w1" | "tatoeba_haw_en" | ...,
  "stage": "eval-only",
  "division": "evals" | "final",
  "split": "dev" | "holdout" | "w1" | "test",
  "row_id": "<unique-per-source>"
}
```

### Why JSONL Is Canonical (Parquet Is Derived)
| Aspect | JSONL | Parquet |
|---|---|---|
| **Human-readable** | Yes; can grep/inspect | Binary; requires tooling |
| **Schema stability** | Text-based; easy to version | Tied to PyArrow API changes |
| **Git diff** | Line-oriented; small diffs | Opaque binary diffs |
| **Streaming** | Natural; one row at a time | Requires buffering |
| **Future use** | Easy to export to other formats | Intermediate format only |

**Decision:** JSONL is the source of truth. Any Parquet version is derived from JSONL and must **never** become a parallel source. This prevents silent deserialization bugs and keeps the lineage clear.

### Key Trade-Off
**Convenience vs. correctness.** Parquet is faster for bulk analytics. But JSONL is simpler to reason about, audit, and version-control. For a small prototype, simplicity wins. When you're sure the schema is stable and the corpus is large enough to make I/O a real bottleneck, you derive a Parquet mirror. Until then: JSONL.

### Speaker Notes
Eval contamination is *the* silent killer in ML. You train on data, test on the same data, and report amazing numbers that are just memorization. The guard has three parts: (1) every eval item is hashed and recorded in a canonical ledger *before* any training data is built; (2) at manifest-build time, train rows are deduplicated against the eval hashes; (3) at training-loader time, an explicit check fires if a row's hash is in the ledger. This is defense-in-depth. JSONL makes this auditable: you can read the ledger in plain text and verify that your test set really isn't in the training set.

---

## SLIDE 8: Decision #6 — Manual Hawaiian-Literate Review for W1 Eval

### The Decision
**Maintain a small, hand-authored W1 micro-eval set (~50–100 items) reviewed by Hawaiian-literate speakers/learners before any eval row is accepted.**

### Why Manual Review Is Required
| Challenge | Why auto-metrics fail | Why manual review helps |
|---|---|---|
| **Diacritic preservation** | Auto-metric (chars/ʻokina count) can't judge fluency | Reviewer can confirm whether the model's output *sounds* right |
| **Register** | PPL doesn't distinguish "biblically formal" from "natural modern Hawaiian" | Fluent speaker knows which register is appropriate |
| **Grammaticality** | BLEU rewards n-gram overlap, not grammatical correctness | Reviewer can judge `haw_verb_form` vs auto-metric noise |
| **Code-switching** | Embedding-based similarity can't judge English↔Hawaiian balance | Speaker knows natural vs. artificial code-switching |

### The W1 Schema
**File:** `data/evals/manual_w1/w1-haw-micro-eval.tsv`  
**Acceptance path:** `review_status ∈ {draft, accepted, rejected}`  
**Categories:** `okina_survival`, `kahako_retention`, `unicode_nfc`, `tokenizer_survival`, `generation_sanity`  
**Slicing:** by `diacritic_density_bin` (none / low / medium / high)

**Only `review_status=accepted` rows enter the canonical eval ledger.**

### Current Status
- **W1 reviewer:** Unassigned (blocker for moving draft rows into accepted)
- **Draft rows:** Seeded locally for path validation
- **CI guard:** Draft rows require explicit `--include-draft-for-local-ledger` and are marked `eval_consumable=false, prototype_local=true`
- **Never trained on:** W1 rows are **never** training data, only eval data

### Key Trade-Off
**Automation vs. judgment.** You could run LID + embedding metrics and call it "eval." But Hawaiian-literate judgment is irreplaceable for a low-resource language where traditional benchmarks don't exist. The cost is that you're blocked on finding and coordinating with reviewers. The payoff is that your eval numbers actually mean something.

### Speaker Notes
This is where the learning project shines. You're not trying to ship a product; you're trying to understand whether an adaptation is working. For that, you need people who *know* Hawaiian to review the model's outputs. That's expensive in a real product roadmap, but it's the right answer for understanding your blindspots. The scaffold exists (W1 schema, hashing pipeline, CI guard); the missing piece is the human reviewer. That's intentional—call it out as an open blocker, don't fabricate numbers.

---

## SLIDE 9: Decision #7 — Tokenizer Audit Blocks Spending

### The Decision
**Run a gated tokenizer audit on the Llama-3.1-8B base model before committing to Stage 1 GPU spend. Go/no-go decision is recorded; no spending happens without it.**

### What the Audit Measures

The tokenizer audit (a planned test; no standalone script in the repo today)
runs locally against representative Hawaiian slices, e.g.:

- inputs: `data/stage1/stage1.jsonl.gz`, `data/evals/manual_w1/w1-haw-micro-eval.tsv`
- model id: `meta-llama/Llama-3.1-8B`

**Output:** `data/tokenizer_audit/<model-id>/report.json`

**Key metrics:**
| Metric | What it catches | Threshold |
|---|---|---|
| **tokens/word (overall)** | Tokenizer fragmentation | ≤ 2.50 |
| **tokens/word (high-diacritic)** | Diacritic-specific waste | ≤ 3.25 |
| **byte-fallback rate** | Model routing through raw bytes (BAD SIGN) | = 0 |
| **byte-fallback or proxy rate** | Either raw bytes or rare-token proxies | ≤ 1% |
| **ʻokina survival** | U+02BB not munged to byte-fallback | 1 token ≤ ʻokina ≤ 2 |
| **Sample coverage** | Representative slices | ≥ 1,500 words + ≥ 10 high-diacritic items |

**Decision field:** `recommendation.decision ∈ {go, no_go}`

### Model Choices
| Model | Reason | Contingency |
|---|---|---|
| **Primary: Llama-3.1-8B** | Best Polynesian pretraining signal; Apache-2.0 | Contingent on tokenizer audit `go` |
| **Fallback: Qwen2.5-7B** | Apache-2.0 license; multilingual; audit if Llama fails | Automatic fallback |
| **Held: Gemma-2-9B** | Permissive license; only if both above fail | Reserved; not preferred |
| **Excluded: Aya-23, Mistral** | CC-BY-NC (license issue) / weak multilingual | Not options |

### Why This Blocks Spending
**You will not know if Llama-3.1-8B can handle ʻokina efficiently until you run the audit.** If it can't (e.g., if it byte-falls back on every diacritic), you've wasted Stage 1 GPU hours on a model that can never represent Hawaiian well. The audit runs locally on a CPU; it takes ~30 min; it costs nothing. Not running it and hoping is reckless.

### Current Status
- **Audit path:** Planned as a tokenizer-audit test; no standalone script in the repo today
- **Real audit result:** Pending (needs gated Hugging Face Llama-3.1-8B access + `transformers` library)
- **Placeholder results:** Do NOT substitute fabricated numbers here
- **Blocking:** Stage 1 GPU spending, embedding/lm_head unfreeze policy, vocab extension decision

### Key Trade-Off
**Upfront delay vs. wasted compute.** The audit adds ~1 day to Stage 0. But it saves 40+ GPU-hours if it says `no_go`. For a prototype where the goal is learning, not speed, that trade-off is clean.

### Speaker Notes
This is the gate that keeps you honest. You can't just assume a model will work well on Hawaiian. ʻOkina (U+02BB) and kahakō (macron vowels) are core to the language—if the tokenizer doesn't handle them, the model's gradients are being routed through messy byte-fallback tokens that don't generalize. The audit takes an hour or two on CPU and tells you definitively whether the base model is worth using. If it fails, you swap models. If it passes, you have confidence that the base is actually a reasonable starting point. This is where theory meets reality. Many projects skip this step and regret it.

---

## SLIDE 10: Decision #8 — GPU Provider Strategy

### The Decision
**Three-provider execution pattern: free/smoke (Provider 1) → paid stable training (Provider 2) → headline eval on separate infra (Provider 3).**

### The Triangle
```
Provider 1: Free / local          → Stage 0 readiness (tokenizer audit, manifests, 0.5B smoke)
    │
    └──→ Provider 2: Paid stable   → Stage 1 (40h) + merge + Stage 2 (20h) on one GPU class
            │
            └──→ Provider 3: Eval only  → Reproducibility gate + headline eval
```

### Why Three Providers?
| Phase | Provider | Why? | Risk if you skip |
|---|---|---|---|
| **Stage 0 (readiness)** | Free: Kaggle, Colab, local | No reason to spend $ on plumbing | Stage 1 fails on env surprises; wastes paid window |
| **Stage 1 + merge + Stage 2** | One paid provider, one GPU class | 4-bit quantization + fp16 dtypes are **not deterministic across CUDA archs**; switching GPU mid-stage poisons loss curve | Loss curve becomes uninterpretable; can't debug whether a metric drop is real or env noise |
| **Headline eval** | Different infra (Provider 3) | Catch silent dtype/CUDA differences on a fresh environment before reporting numbers | Headline number looks better than it really is due to inference-environment luck |

### Indicative Budget (60h at Provider 2)
| Task | % of 60h | Notes |
|---|---|---|
| Setup + resume test | 5 % | Validate checkpoint contract works |
| Stage 1 CPT/DAPT | 40 % | QLoRA r=64, ~1 epoch, with English rehearsal |
| Stage 1 gate eval | 3 % | Full eval suite on Stage 1 candidate checkpoint |
| fp16 merge | 2 % | Merge LoRA into base; sanity-check |
| Stage 2 SFT | 20 % | Fresh LoRA r=32, 2–3 epochs on parallel pairs |
| Stage 2 gate eval | 3 % | Full Stage 2 eval suite |
| Retry + buffer | 27 % | One retry budgeted; some overhead |

### Current Status
- **Provider 1 (free):** Kaggle notebooks, local RTX 2080 (8GB) for small tasks ✓
- **Provider 2 (paid, 60h):** Pending decision (RunPod vs Lambda vs Lightning AI vs Azure credit)
- **Provider 3 (eval):** Pending decision (same family as Provider 2, different machine)

### Key Trade-Off
**Simplicity vs. rigor.** You *could* use one provider for everything and save on switching overhead. But then you have no defense against "the metric only looks good because of this GPU's quantization behavior." Three providers costs more in cognitive load (env setup, checkpoint transport), but it buys you a huge reduction in the chance that your headline numbers are an illusion.

### Speaker Notes
The free-to-paid split is obvious: don't burn paid hours on discovering bugs that free infra can catch. Less obvious is the Provider 2 vs. Provider 3 split. Quantization (4-bit) and dtype (fp16 vs bf16) have subtle platform dependencies. An A100 on one cloud might produce slightly different loss curves than an A100 on another cloud due to CUDA driver versions, cuBLAS library versions, etc. These differences are small, but they're real. So you don't trust your headline eval until you can reproduce the last Stage 2 checkpoint on a different machine and get within ±0.02 PPL. That's the reproducibility gate. It costs time, but it's the only way to know your numbers are real and not luck.

---

## SLIDE 11: Decision #9 — Provider API Differences & Abstraction

### The Decision
**Record provider-specific config differences in `code/configs/<provider>.json` and maintain a checkpoint-transport contract (HF Hub private repo) that works across providers.**

### The Problem
Providers differ in small ways that matter:
- **Kaggle:** T4 / P100 GPUs; max 12h sessions; P100 has no bf16
- **Lambda Labs:** A100; on-demand hourly; reliable Nvidia driver
- **RunPod:** A100 community (variable quality); cheaper; Nvidia driver version drift
- **Lightning AI:** Managed; ProStudio has A100; Pytorch Lightning native
- **Azure:** Spot instances (preemptible); managed; large quota + regional variation

**Each provider has:**
- Different GPUs (dtype support varies: A100 has bf16+FA2, T4 does not)
- Different Nvidia driver versions → different CUDA compilation flags
- Different PyTorch installation paths
- Different object storage (S3 vs GCS vs blob)
- Different network bandwidth
- Different interruption semantics (spot vs on-demand)

### The Solution: Checkpoint Contract
**Storage:** Hugging Face Hub private repo (or S3-compatible) as the artifact bus.

**Every checkpoint carries:**
```json
{
  "base_model_sha": "...",
  "tokenizer_sha": "...",
  "env_lock": "<python-deps snapshot>",
  "adapter_path": "<path-to-adapter-weights>",
  "trainer_state.json": "<training position>",
  "optimizer_state": "<optimizer dump>",
  "rng_state": "<seeded RNG>",
  "eval_log": "<per-checkpoint metrics>"
}
```

**Resume contract:**
1. Fetch checkpoint from HF Hub
2. Verify base/tokenizer SHAs match expected (CI gate)
3. Load 4-bit base + adapter
4. Resume from `trainer_state.json` + optimizer state + RNG state
5. Sanity-eval: must match pre-pause loss within ±0.02 PPL

**If resume fails on a different provider:** environment is not truly restored; stop and debug. Do **not** continue training from scratch on that checkpoint.

### Provider Config Abstraction
**File:** `code/configs/llama31_8b_a100.json`

```json
{
  "base_model_id": "meta-llama/Llama-3.1-8B",
  "base_model_sha": "<frozen-from-audit>",
  "tokenizer_sha": "<frozen-from-audit>",
  "training": {
    "dtype": "bfloat16",
    "quantization": "nf4",
    "lora_rank": 64,
    "lora_alpha": 128
  },
  "inference": {
    "dtype": "bfloat16",
    "quantization": "nf4"
  },
  "env": {
    "cuda_device_order": "PCI_BUS_ID",
    "cudnn_benchmark": true,
    "flash_attention_v2": true,
    "pytorch_version": "2.4.0"
  },
  "provider_notes": {
    "supported_gpus": ["A100-40GB", "A100-80GB"],
    "excluded_gpus": ["T4", "P100"],
    "driver_min_version": "535.0"
  }
}
```

### Key Trade-Off
**Boilerplate vs. portability.** Defining a checkpoint contract and config abstraction adds code. But it means you can swap providers **mid-training** if the first one dies, as long as you're swapping to the same GPU class. For a prototype, that's the difference between "my run is dead" and "I move to Provider 3 and resume."

### Speaker Notes
The contract is the key. You cannot just copy a checkpoint from one cloud to another and resume training; the environments differ in ways that silently break things (dtype support, Nvidia driver quirks, PyTorch version differences). So you write down what the environment *must* provide: base SHA, tokenizer SHA, env.lock (Python dependencies), dtype, GPU class, CUDA compute capability. When you land on a new provider, you verify these match. If they don't, resume fails loudly with actionable errors instead of silently diverging. This is grunt work, but it's what makes multi-provider training reliable.

---

## SLIDE 12: Decision #10 — Human-Owned Contamination Guard

### The Decision
**Issue #4 (runtime training-loader contamination check) is assigned to you (squad:yashas) and remains out-of-scope for the team to implement. This is a deliberate choice.**

### Why This Is Hard
The training loader must, at runtime, check:
1. **No row is in both train and eval** (prevents leakage)
2. **No near-duplicate pairs** across splits (handles similar-but-not-identical rows)
3. **No cluster-overlap** if using MinHash/LSH clustering (handles semantic near-dups)

Automating this fully requires:
- Exact-hash ledger (easy, ✓ done in `eval_hashes.jsonl`)
- Near-duplicate detection (medium; needs locality-sensitive hashing)
- Semantic clustering (hard; needs embedding model + clustering infra)

### The Current State
✓ **Exact SHA-256 dedup:** `eval_hashes.jsonl` records every eval hash before training starts; manifest builder dedupes against it.

✓ **Exact repeated paragraphs:** `scripts/301_build_stage1_dataset.py` drops exact-duplicate paragraphs within FineWeb.

⏳ **Cluster-aware split isolation:** Frank's plan includes this; scripts drafted; not yet integrated into loader.

❌ **Runtime loader check:** Explicitly deferred. The scripts (320 / 330) have "out-of-scope" markers; no Squad agent touches the training loop itself.

### Why It's Your Call
The runtime guard is **policy-enforcement**, not infrastructure. It's about declaring: "We will not train on rows that hash to an eval row." That's your decision to make and enforce in the training code. Squad can scaffold the manifest and ledger. But you own the training loop and the final call on what data goes in.

### Current Gaps
1. **Near-duplicate clustering:** Frank's LSH/MinHash plan; can happen after Stage 1 if needed
2. **Cluster-aware dev/holdout split:** Dependent on clustering existing
3. **Loader integration:** Needs you to wire up the ledger check in the training loop

### Key Trade-Off
**Team abstraction vs. ownership.** The Squad agents could write a full runtime guard that you never have to think about. But then you're trusting someone else's contamination policy. By keeping this in your hands, you're saying: "I own the integrity of this training run." That's harder, but it's the right answer for a learning project where contamination discipline is critical.

### Speaker Notes
This is intentional architectural boundary-setting. The Squad can build pipeline infrastructure (fetch, normalize, manifest, hash), but the **human running the training** bears the final responsibility for not contaminating the eval set. You can automate the checks, but the policy decision—"do we accept a 0.001% near-duplicate risk?"—is yours. This is where learning projects are different from production: you're not delegating trust; you're taking it on.

---

## SLIDE 13: Decision #11 — Stage 2 Parallel-Data Skeleton

### The Decision
**Build Stage 2 manifest, quality-scoring, and SFT-emission scaffolds with a JSONL-first contract; defer real data-fetching and pair-scoring until Stage 1 is complete.**

### The Shape
```
Stage 2 Manifest (stage2_manifest.jsonl)
    ├─ Candidate source: Tatoeba, global-piqa-parallel, BibleNLP, Taxi1500, ...
    ├─ Scoring: alignment_confidence_tier (accept / review / reject)
    │   ├─ Score-tier: based on alignment_method (verse-id, manual, laser, labse, ...)
    │   ├─ Content-tier: diacritics, LID, orthography, length checks
    │   └─ Policy output: quality_flags, manual_review_reasons, alignment_score_components
    ├─ Manifest fields:
    │   ├─ Provenance: source, license, alignment_type, alignment_method, alignment_score
    │   ├─ Content: text_haw, text_en, text_haw_path, text_en_path (if external)
    │   ├─ Policy: alignment_confidence_tier, alignment_review_required, quality_flags
    │   ├─ Metadata: register, synthetic, prototype_only, release_eligible
    │   └─ Splits: train (accept only), review-pending (review tier), held-out (reject / protected)
    └─ SFT Emitter (stage2_sft.jsonl)
        ├─ Selects split=train rows (accept tier only)
        ├─ Merges 50/50 direction balance (en→haw + haw→en)
        ├─ Adds 10–20% Stage-1-style retention slice (monolingual Hawaiian)
        └─ Outputs: instruction_type, text_haw, text_en, metadata

Quality-Scoring Policy (stage2_quality.py)
    ├─ Hard rejects: empty, duplicates, too-short, unknown method, missing score
    ├─ Soft reviews: length extremes, diacritic absence, LID low-confidence, encoding drift
    └─ Accept only if no soft flags + score-tier=accept + content-tier=accept
```

### Current Status
| Component | Owner | Status | Notes |
|---|---|---|---|
| **Manifest schema** | Linus (Data) | ✓ Done | JSONL-first, fields frozen, scripts compiled |
| **Quality scorer** | Rusty (NLP) | ✓ Done | Policy rules locked; self-test passes; scripts compiled |
| **SFT emitter** | Basher (Training) | ✓ Done | Bidirectional; retention slice; scripts compiled |
| **Real data fetch** | Frank (Data) | ⏳ Pending | Blocked on Stage 1 completion; priorities: Tatoeba, global-piqa-parallel |
| **Pair scoring** | Rusty + Frank | ⏳ Pending | Blocked on data fetch |
| **Manifest population** | Linus | ⏳ Pending | Blocked on pair scoring |

### Why Scaffold Now, Data Later?
**Contracts before cargo.** You want the manifest schema, scoring policy, and emission code locked down and tested *before* you have real parallel data. This lets you:
1. Validate the pipeline with dummy/toy data (✓ already done)
2. Make policy decisions (tier thresholds, quality-flag vocabulary) without time pressure
3. Know exactly what format the data needs to be in when Frank fetches Tatoeba
4. Avoid "we have all this data but we don't know what to do with it"

### Blocked Decisions
1. **Which sources to prioritize:** Tatoeba? global-piqa-parallel? Both?
2. **LID thresholds:** If you use GlotLID to verify language identity, what confidence is "good enough"?
3. **Synthetic cap:** 25% max of train tokens for back-translations. Is that right for a prototype?
4. **Review workflow:** Who scores borderline pairs? How do you handle disputes?

### Key Trade-Off
**Completeness vs. readiness.** You could wait to build Stage 2 infrastructure until you have data. But building it now means the schema is based on learning from the policy, not guesses. When the data arrives, you just run it through the pipeline. This is evolutionary architecture: scaffold first, fill in content later.

### Speaker Notes
Stage 2 is where the learning project gets sophisticated. You're not just doing monolingual adaptation; you're trying to add a translation capability. That requires parallel data, which is rarer and harder to acquire responsibly than monolingual text. By building the manifest and scoring infrastructure now—on paper, with toy examples—you're giving yourself a clear target. When data arrives, you can evaluate it fairly and quickly. The policy (what makes a pair "accept" vs "review" vs "reject") is locked in. The quality flags are stable. The SFT emitter is tested. All you need is the data.

---

## SLIDE 14: What's Done, What Remains, What You Learned

### What's Done ✓

| Category | Artifact | Status |
|---|---|---|
| **Architecture** | README.md (planning artifact), implementation_plan.md | ✓ Locked |
| **Data pipeline** | data-pipeline.md, manifest schema, data division taxonomy | ✓ Locked |
| **Training pipeline** | training-pipeline.md, two-stage shape, provider strategy | ✓ Locked |
| **Evaluation pipeline** | eval_pipeline.md, metrics, cadence, orthography checks | ✓ Locked |
| **Stage 1 scaffolding** | FineWeb-2 scripts (100/200 fetcher, splitter, deduper, cleaner) | ✓ Landed |
| **Stage 2 scaffolding** | Manifest schema, quality scorer, SFT emitter, self-tests | ✓ Landed |
| **Tokenizer audit** | planned tokenizer-audit test (no real audit yet) | ⏳ Test pending |
| **Contamination guard** | eval_hashes.jsonl contract, manifest CI, exact-dedup enforcement | ✓ Scaffolded |
| **Team decisions** | 10+ ADRs documenting model choice, budget, data policy, release-gate split | ✓ Merged |

### What Remains ⏳

| Blocker | Owner | Impact | Notes |
|---|---|---|---|
| **Tokenizer audit go/no-go** | Rusty | Stage 1 model selection | Pending real Llama-3.1-8B access on HF + transformers install |
| **W1 Hawaiian-literate reviewer** | You | Eval row acceptance | Draft rows seeded; need human to accept/reject |
| **Provider 2 vendor selection** | You | Stage 1 training window | RunPod vs Lambda vs Lightning AI vs Azure credit |
| **Real Stage 1 training** | Basher + You | Data quality validation | Requires Stage 0 gates to pass |
| **FineWeb-2 data fetch** | Frank | Stage 1 corpus population | Scripts ready; data stays private under data/ |
| **Stage 2 source priority** | Frank + Linus | Parallel-data ingest | Tatoeba first; others on backlog |
| **Cluster-aware dedup** | Frank | Near-duplicate handling | LSH/MinHash; nice-to-have for Stage 1 follow-up |
| **Eval-score reproducibility gate** | Basher | Provider 3 validation | Checkpoint resume + sanity eval must match ±0.02 PPL |

### What You Learned

#### 1. **Scale reality**
You started asking "how would you train an LLM on Hawaiian?" and quickly learned: **from-scratch pretraining is impossible at $10k–$30k.** Adaptation is the only realistic path. This teaches you to question first-order intuitions about model training. The constraint isn't GPU; it's data quality and orthography preservation.

#### 2. **Data provenance is architecture**
Tracking source, license, cultural posture, and OCR confidence isn't optional; it's the **foundation of credible results.** A row with unknown provenance is a liability. This reframes data handling from "let's get lots of text" to "let's understand exactly what we have."

#### 3. **Hawaiian linguistics is not optional**
ʻokina (U+02BB) and kahakō (macron vowels) are phonemically meaningful. A model that confuses them is a failure mode that auto-metrics alone won't catch. You need **Hawaiian-literate human review.** This teaches you that "low-resource language" isn't just a scale problem; it's a different kind of problem requiring different expertise.

#### 4. **Tokenizer audits pay for themselves**
A 30-minute CPU audit can save 40+ GPU-hours. **Always audit before spending.** This is the highest-leverage gate in the whole pipeline.

#### 5. **Two stages unlock debugging**
One-stage SFT is simpler to reason about, but two stages (CPT → merge → SFT) let you isolate failures. Stage 1 gates tell you "we adapted to Hawaiian"; Stage 2 gates tell you "we learned translation." If either fails, you know exactly where. This is a meta-lesson about architecture: **add structure early when it's cheap; it buys clarity later.**

#### 6. **Contamination discipline is your call**
Automation (SHA-256 dedup, exact-match ledgers) buys you a lot, but the **final responsibility** for not contaminating eval is yours. That's the right place to own it as a human building a learning project.

#### 7. **Abstraction over providers**
Free → paid → eval split + checkpoint contracts + config abstraction lets you survive provider failures. The overhead of three-provider reasoning is worth the insurance. You can't predict which cloud provider will have capacity when you need it.

#### 8. **Documentation is architecture**
This repo's main artifact isn't code; it's **ADRs and pipeline docs.** Every decision is documented with alternatives and trade-offs. This makes the next experiment obvious and the failures reproducible.

### Metrics of Success (for this learning project)

| Success criterion | Status | Why it matters |
|---|---|---|
| **Design locked in before GPU spend** | ✓ | You won't discover major gaps mid-training |
| **Eval infrastructure is honest** | ✓ | You'll know whether improvements are real or contamination |
| **Data provenance is traceable** | ✓ | Someone 5 years from now can audit what went into the model |
| **Tokenizer fit is gated** | ✓ | You won't train on a base that mangles ʻokina |
| **Scaffold code compiles and self-tests pass** | ✓ | When you run real data, you won't be fighting plumbing bugs |
| **Boundaries are explicit** | ✓ | The prototype is isolated from release paths; no accidental shipping |

---

## SLIDE 15: Compact Decision Matrix

**Use this table to frame decisions in your deck.**

| Decision | Options | Choice | Trade-off | Owned by |
|---|---|---|---|---|
| **Pretrain vs. adapt** | Train from scratch / Adapt 7B–9B | Adapt | Budget vs. control | Basher, Rusty |
| **Data sources** | Scrape web / Use curated sources / Mix | FineWeb-2 + curated (deferred) | Scale vs. safety | Linus, Frank |
| **Stage 1 corpus** | FineWeb-2 only / Nūpepa + Bible / Everything | FineWeb-2 primary (80K rows cleaned) | Speed vs. diversity | Frank, Linus |
| **Training stages** | One-stage SFT / Two-stage (CPT→SFT) | Two-stage | Simplicity vs. clarity | Basher, Rusty |
| **Eval contamination** | Manual dedup / SHA-256 ledger / Clustering | SHA-256 exact + clustering planned | Speed vs. rigor | You (runtime guard owner) |
| **Manual review** | Auto-metrics only / Hand review | Hand review for W1 | Cost vs. judgment | You (W1 reviewer needed) |
| **Tokenizer choice** | Audit before spend / Trust base model | Audit gate | Time vs. risk | Rusty |
| **GPU strategy** | One provider / Three-provider split | Three-provider (free→paid→eval) | Complexity vs. portability | You, Basher, Livingston |
| **Provider abstraction** | Hardcode configs / Abstracted configs | Abstracted (json + contract) | Boilerplate vs. flexibility | Basher |
| **Contamination ownership** | Squad auto-guard / Your human oversight | Your human call in loader | Automation vs. ownership | You |
| **Stage 2 timing** | Build with data / Build before data | Build before data | Latency vs. readiness | Linus, Frank |

---

## SLIDE 16: Timeline at a Glance

```
Week 1 — Foundations
  ├─ License & cultural posture locked ✓
  ├─ FineWeb-2 sourced + scripts ready ✓
  ├─ Manifest schema drafted ✓
  └─ Tokenizer audit script ready ✓

Week 2 — Data Acquisition (Stage 0)
  ├─ FineWeb-2 fetched & cleaned (80K rows)
  ├─ Eval-hashes ledger built (887 FineWeb test rows)
  ├─ W1 manual eval scaffolding + draft rows seeded
  └─ **Blocker: Tokenizer audit result (pending HF Llama access)**

Week 3 — Evaluation Foundations
  ├─ Eval harness built
  ├─ Baseline metrics on untuned base model
  ├─ Per-checkpoint eval cadence defined
  └─ Stage 0 smoke test on Qwen2.5-0.5B (plumbing validation)

Week 4 — Stage 1 Training (pending tokenizer gate + Provider 2 setup)
  ├─ Provider 2 environment pinned + resume test
  ├─ Stage 1 CPT/DAPT: ~40h QLoRA r=64 on Hawaiian monolingual
  ├─ Per-checkpoint eval (cheap, frequent)
  └─ Stage 1 gate eval (full suite)

Week 5 — fp16 Merge & Stage 2 Start
  ├─ Merge Stage 1 LoRA into fp16 base
  ├─ Sanity eval (must match pre-merge ±0.02 PPL)
  ├─ Stage 2 SFT: ~20h QLoRA r=32 on parallel pairs + retention
  └─ Per-checkpoint eval

Week 6 — Stage 2 Refinement & Iteration
  ├─ Stage 2 gate eval (full suite)
  ├─ Post-run error analysis (diagnostics + next-experiment plan)
  ├─ Prepare checkpoint for Provider 3 eval
  └─ Iterate if needed (time permitting within 60h window)

Week 7 — Final Eval & Documentation
  ├─ Provider 3 reproducibility gate (resume + ±0.02 PPL sanity check)
  ├─ Provider 3 headline eval pass (if reproducibility passes)
  ├─ Model card draft (learning artifact, no public release)
  ├─ Run report with attribution matrix
  └─ Archival: checkpoint, configs, manifests, eval suite SHA

**Key open dates:**
- Tokenizer audit completion → Stage 1 unblock
- Provider 2 onboarding → training start
- W1 reviewer assignment → eval row acceptance
```

---

## APPENDIX: Key Artifacts & Scripts

### Core Docs (in-repo, version-controlled)
```
.squad/
  ├─ decisions.md                   # ADRs: model choice, prototype scope, two-stage plan, ...
  ├─ decisions-archive.md           # Prior ADR history
  ├─ agents/danny/history.md        # Lead architect's notes
  └─ team.md                        # Team roster & roles

docs/
  ├─ README.md                      # Project framing (learning artifact, no release)
  ├─ implementation_plan.md         # Consolidated plan with Phase boundaries & provider strategy
  ├─ data-pipeline.md               # Stage 1 + Stage 2 data transformation, manifests, guards
  ├─ training-pipeline.md           # Stage 0 gates → Stage 1 CPT → merge → Stage 2 SFT
  ├─ eval_pipeline.md               # Metrics, cadence, slicing, contamination guards
  └─ stage2-alignment-quality.md    # Quality-scoring policy for Stage 2 parallel pairs
```

### Stage 1 Scripts (under `scripts/`)
```
200_fetch_fineweb2.py
  └─ Input: FineWeb-2 API / HF dataset
  └─ Output: data/raw/fineweb2_haw_latn/ (raw rows, immutable)
  └─ Purpose: Fetch official FineWeb-2 haw_Latn test split (887 rows)

205_fineweb2_split_plan.py
  └─ Input: data/raw/fineweb2_haw_latn/
  └─ Output: data-sources/stage1-fineweb2-split-plan.json
  └─ Purpose: Produce reproducible 70/30 dev/holdout split with seeded hash ordering

210_fineweb2_clean_and_normalize.py
  └─ Input: data/raw/fineweb2_haw_latn/
  └─ Output: data/extracted/fineweb2_haw_latn_normalized/ (per-paragraph text)
  └─ Purpose: NFC Unicode, ʻokina canonicalization, boilerplate/exact-dedup removal

310_split_dedupe_fineweb2_haw.py
  └─ Input: normalized FineWeb + split plan
  └─ Output: data/evals/eval_hashes.jsonl (dev/holdout rows hashed)
  └─ Purpose: Produce canonical eval-hash ledger for contamination guard

301_build_stage1_dataset.py
  └─ Input: data/extracted/fineweb2_haw_latn_normalized/ + other monolingual sources
  └─ Output: data/stage1/stage1_manifest.jsonl, data/stage1/stage1.jsonl.gz, data/stage1/token_target_report.json
  └─ Purpose: Build training-ready corpus with manifest + token-count report
```

### Stage 2 Scripts (under `scripts/`)
```
320_build_stage2_manifest.py
  └─ Input: candidate parallel-pair sources (Tatoeba, global-piqa-parallel, etc.)
  └─ Output: data/stage2/stage2_manifest.jsonl
  └─ Purpose: Build manifest with alignment_method, alignment_score, and schema contract

321_score_stage2_alignment.py
  └─ Input: data/stage2/stage2_manifest.jsonl
  └─ Output: data/stage2/stage2_manifest.jsonl (with scoring) + stage2_manifest.summary.json
  └─ Purpose: Score pairs for quality (accept / review / reject) per quality policy

330_emit_stage2_sft_jsonl.py
  └─ Input: data/stage2/stage2_manifest.jsonl (accept rows only)
  └─ Output: data/stage2/stage2_sft.jsonl (bidirectional + retention slice)
  └─ Purpose: Emit training-ready SFT JSONL for Stage 2 trainer
```

### Eval Scripts
```
315_hash_manual_w1_eval.py
  └─ Input: data/evals/manual_w1/w1-haw-micro-eval.tsv (review_status=accepted rows)
  └─ Output: data/evals/eval_hashes.jsonl (appended with W1 rows)
  └─ Purpose: Add hand-reviewed W1 rows to canonical eval ledger

eval_harness/
  ├─ metrics/
  │   ├─ tokenizer_metrics.py       # tokens/word, byte-fallback, ʻokina survival
  │   ├─ lm_metrics.py              # PPL, English regression
  │   ├─ translation_metrics.py     # chrF both directions, tokenizer retention
  │   └─ orthography_metrics.py     # NFC check, diacritic density
  │
  ├─ slicing.py                     # Per-source, per-register, per-diacritic-density slicing
  └─ run_report.py                  # Emit structured run report with attribution matrix
```

### Config Abstraction
```
code/configs/
  ├─ llama31_8b_a100.json           # Primary config: Llama-3.1-8B, A100, bfloat16
  ├─ qwen25_7b_a100.json            # Fallback config: Qwen2.5-7B
  ├─ qwen25_0_5b_t4.json            # Smoke test config: Qwen2.5-0.5B, T4
  └─ base.json                      # Shared defaults (LoRA ranks, LR, etc.)
```

### Code Structure
```
code/llm_hawaii/
  ├─ __init__.py
  ├─ config.py                      # Config loading + provider-specific overrides
  ├─ data.py                        # JSONL loader, contamination guard integration
  ├─ model.py                       # 4-bit base + LoRA adapter setup
  ├─ training.py                    # Training loop (Stage 1 + Stage 2)
  ├─ evaluation.py                  # Per-checkpoint eval harness
  ├─ stage2_quality.py              # Quality-scoring policy for Stage 2
  └─ checkpoint.py                  # Checkpoint contract: save/load + HF Hub push/pull
```

### Data Directories (under `data/`, git-ignored)
```
data/
  ├─ raw/                           # Immutable: fetched bytes from sources
  ├─ extracted/                     # Pre-manifest: text extracted + normalized
  ├─ stage1/
  │   ├─ stage1_manifest.jsonl      # Canonical manifest (JSONL)
  │   ├─ stage1.jsonl.gz            # Pre-tokenized training JSONL (gzipped)
  │   └─ token_target_report.json
  ├─ stage2/
  │   ├─ stage2_manifest.jsonl      # Stage 2 manifest + quality scores
  │   └─ stage2_sft.jsonl           # SFT training JSONL (bidirectional)
  ├─ evals/
  │   ├─ eval_hashes.jsonl          # **CANONICAL eval ledger (JSONL)**
  │   ├─ fineweb2_haw/
  │   │   └─ dev.jsonl              # FineWeb dev split (621 rows, per-checkpoint eval)
  │   └─ manual_w1/
  │       └─ w1-haw-micro-eval.tsv  # Hand-authored eval rows
  ├─ final/
  │   ├─ fineweb2_haw/
  │   │   └─ holdout.jsonl          # FineWeb holdout (266 rows, gated milestone eval)
  │   └─ tatoeba_haw_en_test.jsonl  # (planned) held-out test split
  └─ tokenizer_audit/
      └─ llama-3.1-8b/
          └─ report.json            # Audit result (go / no_go)
```

### How to Reference These in Your Deck

1. **Data integrity slide:** Reference `data/evals/eval_hashes.jsonl` as the "source of truth" for contamination guards. Show a 5-row JSON snippet.
2. **Tokenizer audit slide:** Describe the planned tokenizer-audit test and the `recommendation.decision` output format it will emit.
3. **Stage 1 pipeline slide:** Diagram the flow: `200 → 210 → 310 → 301`, with file outputs at each step.
4. **Stage 2 skeleton slide:** Show the three-script chain: `320 (manifest) → 321 (score) → 330 (emit)`.
5. **Config abstraction slide:** Show a snippet of `code/configs/llama31_8b_a100.json` with `provider_notes` section.
6. **Architecture overview slide:** Draw the `data/` directory structure showing JSONL-first canon + derived Parquet (future).

---

## FINAL SPEAKER NOTE

**You built something uncommon here: a learning project that refuses to overstate what it has.**

No dataset checked in (and no plan to release one).  
No training code ready for production (and no claim of production readiness).  
No model weights (and no promise to ship them).  
No benchmark results (and an explicit gate against fabricating them).

What you *have* is clear thinking. Every major decision is documented with alternatives and trade-offs. The infrastructure is designed to be honest: you'll know if eval is contaminated because the ledger says so. You'll know if a model is worth using because the tokenizer audit says so. You'll know if Stage 1 worked because the gates say so.

That's the learning. **Good architecture is honest about what it doesn't know and defensive about what it does.**

---

## End of Deck

*For detailed technical reference, see the companion docs: `README.md`, `implementation_plan.md`, `data-pipeline.md`, `training-pipeline.md`, `eval_pipeline.md`, and `.squad/decisions.md`.*

