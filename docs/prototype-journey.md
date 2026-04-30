# Hawaiian LLM Prototype Journey

This is the living journey note for the Hawaiian LLM prototype. It records the decisions, questions, and clarifications that came up while building the project so the story can later be turned into slides or a narrative without losing the reasoning behind each choice.

## Project posture

This is a private prototype and learning project. The goal is not to release model weights, adapters, datasets, benchmark claims, an API, or a public demo. The value of the work is the learning path: how to responsibly adapt an existing model toward Hawaiian, how to evaluate progress, and how to avoid overstating results.

## Goal clarification: Stage 1 vs. the overall prototype

The current training plan has two different kinds of goals:

| Level | Goal | What success means |
|---|---|---|
| **Stage 1 training goal** | Hawaiian language adaptation | The base model becomes more Hawaiian-aware: better at Hawaiian spelling, vocabulary, phrase patterns, ʻokina/kahakō handling, and Hawaiian text continuation. |
| **Stage 2 training goal** | Instruction and task behavior | The adapted model learns task formats such as answering in Hawaiian, translating English ↔ Hawaiian, explaining grammar, or following bilingual prompts. |
| **Overall prototype goal** | Learn whether a small adapted open model can become useful for Hawaiian-language tasks | Evals show which bottleneck matters most: data quality, tokenizer behavior, model size, training setup, or lack of instruction/parallel data. |

The important distinction is that **Stage 1 is not the translator stage**. Stage 1 is closer to "make the model more Hawaiian-aware" through cleaned monolingual Hawaiian text. That should help the model recognize and generate Hawaiian-like text, but it does not by itself guarantee reliable conversation or translation.

Conversation and translation become explicit prototype goals only once Stage 2 adds the right instruction and bilingual data:

| Capability | Where it belongs | Notes |
|---|---|---|
| **Converse in Hawaiian** | Stage 2 / instruction tuning | Needs Hawaiian chat-style prompts, response examples, and human-reviewed evals. |
| **English → Hawaiian translation** | Stage 2 / parallel or instruction data | Needs curated bilingual pairs and direction-specific evals. |
| **Hawaiian → English translation** | Stage 2 / parallel or instruction data | Needs bilingual pairs and careful evals; likely easier to validate than English → Hawaiian for a non-fluent builder. |
| **General Hawaiian text adaptation** | Stage 1 | Current core training objective. |

The current practical framing is:

> **Hawaiian language adaptation first, task behavior second.**

That means Stage 1 tells us whether the model can absorb Hawaiian signal from cleaned text. Stage 2 tells us whether that adapted model can be shaped into a useful assistant, tutor, or translator.

## Model-size decision context

An 8B-class model is still a reasonable starting point for this prototype because the project is focused, budget-conscious, and iteration-heavy. It is not intended to compete with frontier general assistants. Bigger models may help later, but they should be treated as an escalation only after evals show that model capacity is the bottleneck rather than data quality, tokenizer behavior, or training setup.

## Current north star

The prototype is not trying to prove "we trained a Hawaiian ChatGPT." It is trying to answer a more disciplined question:

> Can a carefully cleaned Hawaiian corpus, strict eval hygiene, tokenizer auditing, and staged fine-tuning make an existing open model measurably more useful for Hawaiian-language work?

If the answer is yes, later work can decide whether the best product shape is a Hawaiian conversation assistant, a translation helper, a language-learning tutor, or a research demo. If the answer is no, the journey should still identify why.
