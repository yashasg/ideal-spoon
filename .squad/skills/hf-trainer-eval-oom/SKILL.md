# SKILL: hf-trainer-eval-oom-on-constrained-gpu

## Pattern

HuggingFace Trainer's `per_device_eval_batch_size` defaults to **8**. On large-vocab models (Llama-3 family: vocab=128,256) with long sequences this allocates enormous logit tensors during eval:

```
batch × seq_len × vocab × dtype_bytes
8     × 2048    × 128256 × 2 (fp16)  ≈ 4.2 GiB per eval step
```

On a memory-constrained GPU that already holds training state (activations, optimizer state, model weights), this will OOM even though training itself is stable.

## Diagnosis signals

- OOM occurs in `_maybe_log_save_evaluate`, not during a train step
- Stack trace shows `lm_head` or equivalent output projection
- Crash at first eval trigger (e.g. step 100) with no checkpoint written
- Allocation size ~N × 500 MB where N = eval batch size

## Fix

Set in `TrainConfig` / JSON config:

```json
"per_device_eval_batch_size": 1,
"eval_accumulation_steps": 1
```

`per_device_eval_batch_size=1` reduces logits from ~4.2 GiB to ~500 MB.  
`eval_accumulation_steps=1` releases GPU logit tensors to CPU after each step rather than accumulating all eval outputs on GPU before moving.

## Cadence fix (no checkpoint before OOM)

When `eval_steps == save_steps`, Trainer evaluates *before* saving. An OOM during eval means no checkpoint is written. Fix: set `eval_steps > save_steps`:

```json
"save_steps": 100,
"eval_steps": 500
```

This ensures multiple checkpoints exist before the first eval fires. Eval is still performed periodically for perplexity tracking.

## Code wiring (this project)

- `TrainConfig` fields: `per_device_eval_batch_size: Optional[int] = None`, `eval_accumulation_steps: Optional[int] = None`
- `build_training_args()` in `train.py`: forwarded to `TrainingArguments` only when not None
- Applied to: `code/configs/stage1_fineweb2_haw_kaggle_t4x2.json`

## Applies to

Any constrained GPU (T4 16GB, V100 16GB) running Llama-2/3 or other large-vocab models (vocab ≥ 32K) with `max_seq_len ≥ 1024`.
