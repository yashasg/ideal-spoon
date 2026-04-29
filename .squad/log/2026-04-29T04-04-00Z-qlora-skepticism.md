# Session: QLoRA Skepticism Challenge — 2026-04-29T04:04:00Z

## Challenge

User questioned: "QLoRA accuracy drops make long training ineffective — is this true?"

## Team Consensus

**Rusty (NLP Researcher):** Tokenizer (ʻokina/kahakō), register skew (Bible/OCR), data quality, eval methodology are larger bottlenecks than QLoRA quantization. Proposed 6 A/B test hooks.

**Basher (Training Engineer):** QLoRA quantizes only the frozen base; adapters/optimizer remain bf16/8-bit. Measured gap negligible vs rank/corpus/tokenizer/LR. Failure modes are specific and debuggable. Proposed 4-test falsification protocol.

## Outcome

- No ADR needed (advisory only).
- Both agents recommend: **measure empirically** before rejecting QLoRA.
- Smoke-test NF4 vs fp16 LoRA on Qwen2.5-0.5B; if gap < 2%, proceed with QLoRA prototype.
- QLoRA remains the correct cost-optimization tool at current budget ($50–60/mo Azure + Kaggle).

## Next Action

Run tokenizer audit + smoke QLoRA/LoRA A/B on 0.5B before Stage 1 launch on Kaggle 7B.
