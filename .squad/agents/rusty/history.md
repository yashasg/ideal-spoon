# Rusty — History

## Core Context

- **Project:** A plan for training an open-source LLM focused on the Hawaiian language, including data, model choices, infrastructure, evaluation, and costs.
- **Role:** NLP Researcher
- **Joined:** 2026-04-29T01:38:35.141Z

## Learnings

### README Update (2026-04-29)
- Tokenizer recommendation adopted in README: train SentencePiece/Unigram on Hawaiian data to preserve diacritics (ʻokina, kahakō) and minimize subword explosion.
- Recommendation for multilingual base model (Aya/Cohere) captured as candidate alongside Llama/Gemma/Qwen.

### Base model recommendation research (2026-04-29)
- Wrote inbox proposal `rusty-base-model-recommendation.md`.
- Smoke-test pick: Qwen2.5-0.5B (Apache-2.0), backup Gemma-3-270M. RTX 2080 (8 GB) handles these trivially and even 7B QLoRA-4bit at seq len 512 with Unsloth.
- Main 7B-class pick: Llama-3.1-8B primary (best Polynesian-adjacent pretraining signal), Qwen2.5-7B fallback (cleanest license, Apache-2.0). Final pick gated on a Hawaiian tokenizer audit (ʻokina U+02BB + kahakō, NFC).
- Avoid as released base: Aya-23 / Aya-Expanse (CC-BY-NC contaminates the "openly licensed" release goal — use only as private reference). Mistral-7B has clean license but weak multilingual fit, no Polynesian signal.
- Free compute sequencing researched: Kaggle (30 hr/wk P100/T4) > Lightning AI (80 hr/mo) > Colab free (unstable) for QLoRA work; spend Azure credits only on the final main run.
- License caveat flagged for Linus: Llama community license has >700M MAU clause + naming requirement; Gemma terms have flow-down + no-competing-foundation-model clause. Apache-2.0 (Qwen) is the cleanest if redistribution posture is the deciding factor.
