# Skill: SFT Target-Only Loss Masking (no TRL)

## Pattern

To build a Stage-2 SFT data path without TRL or DataCollatorForSeq2Seq:

### 1. Tokenize prompt and target separately

```python
enc_prompt = tokenizer(prompt_text, ..., add_special_tokens=False)
enc_target = tokenizer(target_text, ..., add_special_tokens=False)
eos_id = tokenizer.eos_token_id

prompt_ids = list(enc_prompt["input_ids"])
target_ids = list(enc_target["input_ids"]) + [eos_id]
all_ids = (prompt_ids + target_ids)[:max_length]

n_prompt = min(len(prompt_ids), len(all_ids))
labels = [-100] * n_prompt + all_ids[n_prompt:]
```

### 2. SFT collator pads labels with -100 (not pad_token_id)

```python
def _collate(features):
    max_len = max(len(f["input_ids"]) for f in features)
    batch = {"input_ids": [], "attention_mask": [], "labels": []}
    for f in features:
        n = len(f["input_ids"]); pad = max_len - n
        batch["input_ids"].append(list(f["input_ids"]) + [pad_id] * pad)
        batch["attention_mask"].append(list(f["attention_mask"]) + [0] * pad)
        batch["labels"].append(list(f["labels"]) + [-100] * pad)
    return batch
```

Key: do NOT use `DataCollatorForLanguageModeling` for SFT — it rebuilds labels from padded input_ids, overwriting the prompt mask.

### 3. Invariants to test

- `labels[:n_prompt]` all equal `-100`
- `labels[n_prompt:]` all NOT `-100` (real token ids including EOS)
- `labels[-1] == eos_token_id`
- Collator padding positions have `-100` in labels, `0` in attention_mask
- Collator preserves existing `-100` (prompt mask) unchanged

## Where it lives in this project

`code/llm_hawaii/data.py` — `tokenize_sft_example`, `build_sft_dataset`, `make_sft_collator`  
Tests: `code/tests/test_data.py::TestSFTData`
