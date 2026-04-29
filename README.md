# ideal-spoon

> A learning project that works through what it would take to train a small **LLM** focused on the Hawaiian language — data, model choices, infrastructure, evaluation, and costs.

⚠️ **This repository is a prototype and learning project, not a release effort.**
There is no dataset checked in, no training code, no model weights, and no benchmark results. There is no plan to publicly release a model, hosted service, or dataset out of this repo. What lives here is a design exercise — ADRs and team notes that work through the problem so we (and anyone reading along) learn from the trade-offs, not a roadmap toward shipping a product.

---

## Goals

- Work through what a small, openly licensed LLM for **ʻŌlelo Hawaiʻi** (Hawaiian) would actually require — orthography, diacritics (ʻokina, kahakō), and culturally appropriate usage included.
- Practice **reproducible, provenance-honest** design: every training document traceable to a source with a known license and, where relevant, community consent.
- Reason about a **practical budget tier of roughly $10k–$30k** (compute + data work), per Livingston's cost analysis, even though we don't intend to spend it.
- Learn in public: keep the design, ADRs, and trade-offs documented so the process is useful to others, even though no weights, tokenizer, or dataset are planned for release.

## Non-Goals

- Building a frontier-scale general-purpose model.
- Scraping the open web indiscriminately for Hawaiian-looking text.
- Claiming production readiness, fluency guarantees, or cultural authority. This is a learning project.
- Shipping a chat product, hosted API, or model release out of this repo. None of that is on the roadmap.

## Approach

The team's working consensus is to **adapt an existing multilingual base model** rather than train from scratch:

- Hawaiian is a low-resource language; from-scratch pretraining at our budget would underperform a careful adaptation.
- Adaptation lets us focus effort on the parts that actually matter for quality: **data curation, tokenization, and evaluation.**
- Basher's recommendation: start with **QLoRA-style parameter-efficient fine-tuning** on a 7B–9B multilingual base before considering full fine-tunes or larger models.

Headline trade-off (see ADR in `.squad/decisions.md`): adapt-vs-scratch resolves to *adapt* given budget and corpus realities. Data quality and eval rigor — not GPU spend — are expected to be the bottleneck.

## Data & Provenance

All data sources below are **planned**, not acquired. Nothing is committed to this repo yet.

Linus's guidance drives this section:

- Maintain a **per-document provenance manifest**: source, license, collection date, consent status, and any community-specific usage notes.
- Prefer curated, attributable sources (digitized newspapers, public-domain texts, openly licensed educational material, government records) over undercurated web scrapes.
- For any source where community consent or cultural sensitivity is unclear, **default to exclusion** until reviewed.
- Track the corpus as data + manifest, never as a raw blob; reproducibility depends on the manifest.

Candidate source categories under consideration (subject to licensing review):

- Public-domain Hawaiian-language newspapers (e.g., 19th-century archives held by libraries/universities).
- Openly licensed educational and governmental materials.
- Bilingual / parallel corpora where Hawaiian is paired with English, for evaluation and alignment.

## Tokenization & Orthography

Rusty owns this area. Key constraints:

- **Preserve diacritics**: the ʻokina (glottal stop) and kahakō (macron) are phonemically and semantically meaningful. A tokenizer that strips or normalizes them away is unacceptable.
- **Audit the base model's tokenizer** for how it segments Hawaiian text *before* committing to a base model. Pathological segmentation (e.g., byte-fallback explosion on every diacritic) is a strong signal to swap models or extend the vocabulary.
- Consider **vocabulary extension or a learned Hawaiian-specific BPE/Unigram piece set** if the base tokenizer is wasteful, balanced against the embedding-table cost.
- Normalize Unicode carefully (NFC vs. NFD) and pin the choice; mixing forms silently corrupts training and eval.

## Model & Training

Working plan, not commitments:

- **Base model:** an openly licensed multilingual 7B–9B model with reasonable Polynesian / Austronesian coverage in pretraining. Final selection blocked on tokenizer audit (above).
- **Method:** **QLoRA first** (Basher). 4-bit quantized base with LoRA adapters keeps memory and cost low, lets us iterate quickly, and produces small distributable adapters.
- **Scale up only when justified:** move to full fine-tunes or larger bases only if QLoRA results saturate against eval, and only if the corpus has grown enough to support it.
- **Track everything**: data version, tokenizer version, base-model checkpoint, training config, seed, eval suite version. No untracked runs.

## Evaluation

Evaluation is treated as a **first-class deliverable**, not an afterthought. Operational details — cadence, metrics, diagnostic slicing, attribution matrix, run-report schema — live in [`docs/eval_pipeline.md`](./docs/eval_pipeline.md).

- Build a small, **curated Hawaiian eval set** with held-out items: comprehension, generation, basic grammaticality, diacritic preservation, code-switching with English.
- Include **human review** by speakers/learners for at least a sampled subset; automatic metrics alone are not trusted for a low-resource language.
- Track regressions across runs. A run is not "better" until the eval suite says so on the same harness version.
- The eval harness is intended to live alongside the rest of the design as a learning artifact; there are no weights to pair it with, and none planned.

## Budget & Infrastructure

Livingston's framing: aim for the **$10k–$30k practical tier**.

- **Lower end (~$10k):** rented GPU hours on a budget cloud or community provider; QLoRA on a 7B base; modest data-curation labor.
- **Mid (~$15k–$20k):** more curation labor, a second training pass with improved data, broader eval, possible larger base.
- **Upper (~$30k):** room for a full fine-tune attempt, more rigorous human eval, contingency for failed runs.

Vendor / infra trade-offs to weigh per run:

- **Hyperscalers (AWS / GCP / Azure):** reliable, expensive, painful spot interruptions for long runs.
- **Specialty GPU clouds (Lambda, RunPod, CoreWeave, etc.):** cheaper per-GPU-hour, more variable availability, fewer managed niceties.
- **Academic / community compute:** cheapest when accessible, slowest to schedule.
- Spend on **data and eval labor** before spending on bigger GPUs. A better corpus beats a bigger model at this scale.

## Roadmap (sketch, ~7 weeks)

This is a sketch, not a sprint plan. Weeks are nominal.

1. **Week 1 — Foundations.** Lock licensing posture, finalize source shortlist, draft provenance manifest schema, audit candidate base-model tokenizers on Hawaiian text.
2. **Week 2 — Corpus v0.** Acquire and clean an initial corpus from the highest-confidence sources. Land the manifest. Establish Unicode normalization policy.
3. **Week 3 — Eval v0.** Build the first eval set and harness. Establish baselines from the un-finetuned base model.
4. **Week 4 — Training v0.** First QLoRA run on corpus v0. Compare against baseline on eval v0. Triage failure modes.
5. **Week 5 — Iterate data.** Expand corpus where eval shows weakness. Improve curation. Re-run.
6. **Week 6 — Iterate training.** Tune LoRA rank, learning rate, data mix. Possibly extend tokenizer. Re-evaluate.
7. **Week 7 — Package & document.** If the prior weeks produced anything coherent, freeze a candidate adapter *internally*, document training/eval, and draft an honest model card with limitations — as a learning artifact. **No public release of weights, datasets, or hosted services is planned.**

Each step has a clear exit criterion: an artifact (manifest, eval suite, run report) checked in, not a vibe.

## Repository Layout

Most of these directories do not exist yet; they are the intended shape as work lands.

```
.
├── README.md                # this file (planning artifact)
├── .squad/
│   ├── decisions.md         # ADRs (incl. README ADR, default-model ADR)
│   ├── team.md              # team roster and project context
│   └── agents/<name>/       # per-agent charters and history
├── data/                    # (planned) manifests only; no raw corpora committed
├── tokenizer/               # (planned) tokenizer audits, vocab artifacts
├── training/                # (planned) configs, adapters, run reports
├── eval/                    # (planned) eval harness, eval sets, baselines
├── code/                    # prototype training/eval code; learning skeleton
│                            # under code/llm_hawaii/ uses PyTorch + Hugging
│                            # Face as the educational path. ML deps are
│                            # lazy-imported and NOT pinned in root
│                            # requirements.txt. Final framework choice for
│                            # any production run remains gated by an ADR.
└── docs/                    # (planned) model cards, methodology notes
```

## Contributing

This is an early-stage planning repo. Useful contributions right now look like:

- Pointers to **openly licensed Hawaiian-language sources** with clear provenance.
- Tokenizer audits of candidate base models against representative Hawaiian text (with diacritics intact).
- Review of the eval design from speakers, learners, or linguists.
- Critique of the budget plan from anyone who has actually trained adapters at this scale.

Please do not open PRs that add scraped corpora, undocumented data dumps, or claims of model performance that aren't backed by a checked-in eval run.

When proposing a change that affects direction (data policy, model choice, training method, budget tier), please reference or extend `.squad/decisions.md` rather than burying the rationale in a commit message.

## License (intent)

This is a learning project, so the license posture is scoped accordingly:

- Code, configs, eval harness, and documentation: a **permissive open-source license** (e.g., Apache-2.0 or MIT) when a `LICENSE` file lands. The repo is meant to be readable and reusable as a design reference.
- Model weights, adapters, tokenizer artifacts, and raw corpora: **not planned for release.** If that ever changed, it would require the separate clearance pass described in the prototype-vs-release ADR (`.squad/decisions.md`) — a future decision, not a current commitment.
- Data **manifests** (if they end up in the repo) would point at upstream sources and their licenses, never bundle the data itself.

The final license file is not yet committed; it will be added when the first concrete code/config artifacts land.
