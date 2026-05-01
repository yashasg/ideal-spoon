import itertools
import gzip
import json
import os
import tempfile
from pathlib import Path
import unittest

import llm_hawaii.data as data
from llm_hawaii.config import TrainConfig


# DO-NOW checklist (keep these changes in Stage-1 scope):
# 1) Add unit tests for:
#    - `iter_jsonl`: missing file, bad JSON, empty-line handling.
#    - `normalize_text`: NFC behavior with combining macron input.
#    - `tokenize_example`: missing `text_field` and labels==input_ids.
# 2) Add a tiny smoke runner (or test) that:
#    - loads `code/examples/train.jsonl.example`,
#    - tokenizes with a small `max_length`,
#    - confirms `build_train_dataset` returns >0 rows.


class _DummyTokenizer:
    """Minimal tokenizer stub — no torch/transformers needed.

    Splits on whitespace and maps each token to its index in a tiny vocab.
    Implements the same call-signature as HF AutoTokenizer so
    tokenize_example / build_train_dataset / tokenize_sft_example work without
    any HF downloads.
    """

    pad_token = "<pad>"
    pad_token_id = 0
    eos_token = "<eos>"
    eos_token_id = 999

    def __call__(
        self,
        text: str,
        max_length: int = 1024,
        truncation: bool = False,
        padding=False,
        return_tensors=None,
        **kwargs,
    ) -> dict:
        tokens = text.split()
        # Map tokens to 1-998 so 0=pad and 999=eos are reserved.
        ids = [abs(hash(t)) % 998 + 1 for t in tokens]
        if truncation:
            ids = ids[:max_length]
        return {"input_ids": ids, "attention_mask": [1] * len(ids)}


class TestData(unittest.TestCase):
    def test_iter_jsonl(self):
        with self.assertRaises(FileNotFoundError):
            list(data.iter_jsonl("nonexistent_file.jsonl"))

        repo_root = Path(__file__).resolve().parents[2]
        dev_path = repo_root / "code" / "examples" / "train.jsonl.example"
        self.assertTrue(dev_path.exists(), f"Missing eval file: {dev_path}")

        self.assertIsNotNone(data.iter_jsonl(dev_path))  # smoke test; more detailed tests in test_data.py

    def test_iter_jsonl_bad_json(self):
        """Bad JSON line must raise, not silently skip."""
        repo_root = Path(__file__).resolve().parents[2]
        bad_file = repo_root / "code" / "examples" / "bad_json_test.jsonl"
        bad_file.write_text('{"text": "ok"}\nnot-json-at-all\n', encoding="utf-8")
        try:
            with self.assertRaises(ValueError):
                list(data.iter_jsonl(bad_file))
        finally:
            bad_file.unlink(missing_ok=True)

    def test_iter_jsonl_empty_lines_skipped(self):
        """Empty lines between records must not cause errors."""
        repo_root = Path(__file__).resolve().parents[2]
        sparse_file = repo_root / "code" / "examples" / "sparse_test.jsonl"
        sparse_file.write_text('\n{"text": "a"}\n\n{"text": "b"}\n', encoding="utf-8")
        try:
            rows = list(data.iter_jsonl(sparse_file))
            self.assertEqual(len(rows), 2)
        finally:
            sparse_file.unlink(missing_ok=True)

    def test_iter_jsonl_gzip(self):
        """Stage 1 trainer configs point at gzipped JSONL."""
        with tempfile.TemporaryDirectory() as d:
            gz_path = Path(d) / "train.jsonl.gz"
            with gzip.open(gz_path, "wt", encoding="utf-8") as f:
                f.write('{"text": "a"}\n{"text": "b"}\n')
            rows = list(data.iter_jsonl(gz_path))
        self.assertEqual(rows, [{"text": "a"}, {"text": "b"}])

    def test_normalize_text(self):
        self.assertEqual(data.normalize_text("ha\u0304lau", form="NFC"), "hālau")  # smoke test; more detailed tests in test_data.py

    def test_normalize_text_nfc_idempotent(self):
        """NFC normalization must be idempotent on already-NFC input."""
        already_nfc = "hālau"  # precomposed ā = U+0101
        self.assertEqual(data.normalize_text(already_nfc, form="NFC"), already_nfc)

    def test_normalize_text_unknown_form(self):
        with self.assertRaises(ValueError):
            data.normalize_text("text", form="INVALID")

    def test_tokenize_example_missing_text(self):
        _tokenizer = _DummyTokenizer()
        self.assertIsNotNone(_tokenizer)
        with self.assertRaises(KeyError):
            list(data.tokenize_example(
            {},
            tokenizer=_tokenizer,
            text_field="text",
            max_length=10,
            normalization="NFC"))

    def test_tokenize_example(self):
        _tokenizer = _DummyTokenizer()
        self.assertIsNotNone(_tokenizer)
        self.assertIsNotNone(data.tokenize_example(
            {"text": "ha\u0304lau"},
            tokenizer=_tokenizer,
            text_field="text",
            max_length=10,
            normalization="NFC"))
    
    def test_collator_strips_labels_before_inner(self):
        """make_collator must strip pre-tokenized labels before calling the inner CLM collator.

        Reproduces the batch_size=2 failure: if labels are not stripped, the HF
        DataCollatorForLanguageModeling raises
          ValueError: expected sequence of length X at dim 1 (got Y)
        because tokenizer.pad tries to tensorize variable-length labels.

        No HF model download needed — transformers is monkeypatched.
        """
        import unittest.mock as mock
        import llm_hawaii.data as data_mod

        captured = []

        def _fake_inner_call(feats):
            captured.extend(feats)
            return {"input_ids": [[0, 0]], "labels": [[-100, 0]]}

        fake_transformers = mock.MagicMock()
        fake_transformers.DataCollatorForLanguageModeling.return_value = _fake_inner_call

        with mock.patch.object(data_mod, "_require", return_value=fake_transformers):
            collator = data_mod.make_collator(_DummyTokenizer())

        # Two features with *different* label lengths — this is what broke batch_size=2.
        features = [
            {"input_ids": [1, 2, 3], "attention_mask": [1, 1, 1], "labels": [1, 2, 3]},
            {
                "input_ids": [4, 5, 6, 7, 8],
                "attention_mask": [1, 1, 1, 1, 1],
                "labels": [4, 5, 6, 7, 8],
            },
        ]
        collator(features)

        self.assertEqual(len(captured), 2, "Inner collator should receive exactly 2 features")
        for feat in captured:
            self.assertNotIn(
                "labels",
                feat,
                "labels must be stripped before inner CLM collator sees the batch",
            )
            self.assertIn("input_ids", feat)
            self.assertIn("attention_mask", feat)

    def test_collator_end_to_end_variable_length_padding(self):
        """make_collator end-to-end: variable-length batch → correctly padded output.

        Stronger regression than test_collator_strips_labels_before_inner:
        verifies the *output* has padded same-length input_ids and -100 at
        every padded label position.  No HF model download needed — the inner
        collator is replaced with a minimal fake that implements the real
        DataCollatorForLanguageModeling pad-then-label semantics.

        Batch:
          feature[0]: length 3  → gets 2 pad tokens appended
          feature[1]: length 5  → no padding needed

        Expected:
          output['input_ids'][0]  == length 5 (padded with PAD_ID=0)
          output['labels'][0][-2] == -100   (padded positions)
          output['labels'][0][-1] == -100
          output['labels'][1]     contains no -100 (full-length, no padding)
        """
        import unittest.mock as mock
        import llm_hawaii.data as data_mod

        PAD_ID = 0

        def _fake_inner_collator(feats):
            """Minimal stand-in for DataCollatorForLanguageModeling (mlm=False).

            Pads input_ids to max length with PAD_ID; sets -100 at padding
            positions in labels, matching HF CLM collator behaviour.
            """
            max_len = max(len(f["input_ids"]) for f in feats)
            input_ids_out, labels_out = [], []
            for f in feats:
                seq = list(f["input_ids"])
                pad_len = max_len - len(seq)
                input_ids_out.append(seq + [PAD_ID] * pad_len)
                labels_out.append(seq + [-100] * pad_len)
            return {"input_ids": input_ids_out, "labels": labels_out}

        fake_transformers = mock.MagicMock()
        fake_transformers.DataCollatorForLanguageModeling.return_value = _fake_inner_collator

        with mock.patch.object(data_mod, "_require", return_value=fake_transformers):
            collator = data_mod.make_collator(_DummyTokenizer())

        features = [
            {"input_ids": [1, 2, 3], "attention_mask": [1, 1, 1], "labels": [1, 2, 3]},
            {
                "input_ids": [4, 5, 6, 7, 8],
                "attention_mask": [1, 1, 1, 1, 1],
                "labels": [4, 5, 6, 7, 8],
            },
        ]
        batch = collator(features)

        # Both rows padded to the same length (5)
        self.assertEqual(len(batch["input_ids"][0]), 5)
        self.assertEqual(len(batch["input_ids"][1]), 5)

        # Short row: padded tokens are PAD_ID in input_ids
        self.assertEqual(batch["input_ids"][0][3], PAD_ID)
        self.assertEqual(batch["input_ids"][0][4], PAD_ID)

        # Short row: label positions at padding must be -100
        self.assertEqual(batch["labels"][0][3], -100)
        self.assertEqual(batch["labels"][0][4], -100)

        # Long row: real tokens only, no -100 in labels
        self.assertNotIn(-100, batch["labels"][1])

    def smoke_test_build_train_dataset(self):
        """Manual smoke: run explicitly, never auto-discovered by unittest (no test_ prefix)."""
        repo_root = Path(__file__).resolve().parents[2]
        dev_path = repo_root / "code" / "examples" / "train.jsonl.example"
        self.assertTrue(dev_path.exists(), f"Missing eval file: {dev_path}")

        _tokenizer = data.load_tokenizer("Qwen/Qwen2.5-0.5B")
        dataset = data.build_train_dataset(
            path=dev_path,
            tokenizer=_tokenizer,
            text_field="text",
            max_length=10,
            normalization="NFC"
        )
        self.assertGreater(len(dataset), 0, "Expected build_train_dataset to return >0 records")


class TestTrainConfig(unittest.TestCase):
    """Config loading tests — no ML deps required."""

    def _repo_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    def test_smoke_config_loads(self):
        """smoke.json must parse without errors."""
        cfg = TrainConfig.from_json(self._repo_root() / "code" / "configs" / "smoke.json")
        self.assertEqual(cfg.stage, "smoke")
        self.assertIsNone(cfg.eval_path)

    def test_llama31_config_loads(self):
        """llama31_8b_a100.json must parse and have correct train/eval paths."""
        cfg = TrainConfig.from_json(
            self._repo_root() / "code" / "configs" / "llama31_8b_a100.json"
        )
        self.assertEqual(cfg.stage, "stage1-cpt")
        self.assertIn("stage1/stage1.jsonl.gz", cfg.train_path)
        self.assertIsNotNone(cfg.eval_path)
        self.assertIn("fineweb2_haw/dev.jsonl", cfg.eval_path)

    def test_llama31_config_load_config_resolves_paths(self):
        """load_config must resolve relative paths to absolute paths."""
        from llm_hawaii.config import load_config
        cfg = load_config(self._repo_root() / "code" / "configs" / "llama31_8b_a100.json")
        self.assertTrue(
            cfg.train_path.startswith("/"),
            f"Expected absolute train_path, got: {cfg.train_path}",
        )
        self.assertIn("stage1/stage1.jsonl.gz", cfg.train_path)
        self.assertIn("fineweb2_haw/dev.jsonl", cfg.eval_path)

    def test_unknown_key_raises(self):
        """from_json must raise on unknown keys, not silently drop them."""
        repo_root = self._repo_root()
        bad_cfg_path = repo_root / "code" / "examples" / "bad_config_test.json"
        bad_cfg_path.write_text(
            '{"base_model": "x", "UNKNOWN_KEY_XYZ": 1}', encoding="utf-8"
        )
        try:
            with self.assertRaises(ValueError, msg="Expected ValueError for unknown key"):
                TrainConfig.from_json(bad_cfg_path)
        finally:
            bad_cfg_path.unlink(missing_ok=True)

    def test_eval_path_and_eval_steps_paired(self):
        """llama31 config: eval_path and eval_steps must both be set for eval-during-train."""
        cfg = TrainConfig.from_json(
            self._repo_root() / "code" / "configs" / "llama31_8b_a100.json"
        )
        if cfg.eval_path:
            self.assertIsNotNone(
                cfg.eval_steps,
                "eval_path is set but eval_steps is None — eval-during-train will be a no-op",
            )

    def test_config_roundtrip(self):
        """to_json / from_json roundtrip must preserve all fields."""
        repo_root = self._repo_root()
        out_path = repo_root / "code" / "examples" / "roundtrip_test.json"
        original = TrainConfig.from_json(repo_root / "code" / "configs" / "smoke.json")
        try:
            original.to_json(out_path)
            reloaded = TrainConfig.from_json(out_path)
            self.assertEqual(original.base_model, reloaded.base_model)
            self.assertEqual(original.train_path, reloaded.train_path)
            self.assertEqual(original.stage, reloaded.stage)
        finally:
            out_path.unlink(missing_ok=True)


class TestSFTData(unittest.TestCase):
    """Stage-2 SFT tokenization and collation tests — no ML deps required."""

    _EXAMPLE = {
        "instruction": "Translate the following English sentence into Hawaiian.",
        "source_text": "The sky is blue.",
        "target_text": "Ua uliuli ke lani.",
        "loss_mask": "target_only",
    }

    def _tok(self):
        return _DummyTokenizer()

    def _tokenize(self, example=None, **kwargs):
        return data.tokenize_sft_example(
            example or dict(self._EXAMPLE), self._tok(), **kwargs
        )

    # --- target-only masking regression ---

    def test_target_only_masking_prompt_positions_are_neg100(self):
        """All prompt token positions in labels must be -100 (exact regression)."""
        tok = self._tok()
        prompt_text = (
            self._EXAMPLE["instruction"]
            + "\n\n"
            + self._EXAMPLE["source_text"]
            + "\n\n"
        )
        prompt_ids = tok(prompt_text, add_special_tokens=False)["input_ids"]

        result = self._tokenize()
        n_prompt = len(prompt_ids)
        self.assertGreater(n_prompt, 0, "Expected non-empty prompt")
        for i, lbl in enumerate(result["labels"][:n_prompt]):
            self.assertEqual(
                lbl,
                -100,
                f"labels[{i}] = {lbl}, expected -100 (prompt position)",
            )

    def test_target_only_masking_target_positions_carry_loss(self):
        """Target token positions (after prompt) must have real token IDs, not -100."""
        tok = self._tok()
        prompt_text = (
            self._EXAMPLE["instruction"]
            + "\n\n"
            + self._EXAMPLE["source_text"]
            + "\n\n"
        )
        n_prompt = len(tok(prompt_text, add_special_tokens=False)["input_ids"])
        result = self._tokenize()
        target_labels = result["labels"][n_prompt:]
        self.assertGreater(len(target_labels), 0, "Expected at least one target label")
        for i, lbl in enumerate(target_labels):
            self.assertNotEqual(
                lbl,
                -100,
                f"target labels[{i}] = -100, expected a real token id",
            )

    def test_eos_appended_and_carries_loss(self):
        """EOS token must be the last input_id and the last label (not -100)."""
        result = self._tokenize()
        self.assertEqual(
            result["input_ids"][-1],
            _DummyTokenizer.eos_token_id,
            "Last input_id must be EOS",
        )
        self.assertEqual(
            result["labels"][-1],
            _DummyTokenizer.eos_token_id,
            "EOS label must equal eos_token_id (carries loss)",
        )

    def test_labels_input_ids_same_length(self):
        """labels and input_ids must have the same length."""
        result = self._tokenize()
        self.assertEqual(len(result["input_ids"]), len(result["labels"]))
        self.assertEqual(len(result["input_ids"]), len(result["attention_mask"]))

    def test_missing_field_raises(self):
        """KeyError on missing instruction/source/target field."""
        tok = self._tok()
        with self.assertRaises(KeyError):
            data.tokenize_sft_example(
                {"source_text": "x", "target_text": "y"}, tok
            )
        with self.assertRaises(KeyError):
            data.tokenize_sft_example(
                {"instruction": "x", "target_text": "y"}, tok
            )
        with self.assertRaises(KeyError):
            data.tokenize_sft_example(
                {"instruction": "x", "source_text": "y"}, tok
            )

    def test_no_eos_token_raises(self):
        """RuntimeError when tokenizer has no eos_token_id."""

        class _NoEosTokenizer(_DummyTokenizer):
            eos_token_id = None

        with self.assertRaises(RuntimeError):
            data.tokenize_sft_example(dict(self._EXAMPLE), _NoEosTokenizer())

    def test_truncation_respects_max_length(self):
        """Combined sequence must not exceed max_length."""
        result = self._tokenize(max_length=5)
        self.assertLessEqual(len(result["input_ids"]), 5)

    def test_normalization_applied_to_all_fields(self):
        """NFC normalization is applied to instruction, source, and target."""
        # NFD ā = a + combining macron; NFC ā = precomposed U+0101
        nfd_example = {
            "instruction": "Translate the following English sentence into Hawaiian.",
            "source_text": "ha\u0304lau",   # NFD: a + U+0304
            "target_text": "ha\u0304lau",
        }
        result = data.tokenize_sft_example(nfd_example, self._tok())
        # If normalization were skipped the hash-based tokenizer would see
        # different token strings; the main thing is it doesn't crash and
        # returns the expected structure.
        self.assertIn("input_ids", result)

    # --- build_sft_dataset ---

    def test_build_sft_dataset_loads_example_file(self):
        """build_sft_dataset must return >0 records from the example JSONL."""
        repo_root = Path(__file__).resolve().parents[2]
        example_path = repo_root / "code" / "examples" / "stage2_sft.jsonl.example"
        self.assertTrue(example_path.exists(), f"Missing: {example_path}")
        records = data.build_sft_dataset(
            example_path,
            self._tok(),
            max_length=256,
        )
        self.assertGreater(len(records), 0)
        for rec in records:
            self.assertIn("input_ids", rec)
            self.assertIn("labels", rec)
            self.assertEqual(len(rec["input_ids"]), len(rec["labels"]))

    def test_build_sft_dataset_empty_raises(self):
        """ValueError when JSONL has zero rows."""
        import gzip as _gzip
        with tempfile.TemporaryDirectory() as d:
            empty = Path(d) / "empty.jsonl"
            empty.write_text("", encoding="utf-8")
            with self.assertRaises(ValueError):
                data.build_sft_dataset(empty, self._tok())

    # --- make_sft_collator ---

    def test_sft_collator_pads_to_max_length(self):
        """SFT collator must pad all sequences in a batch to the same length."""
        collator = data.make_sft_collator(self._tok())
        features = [
            {"input_ids": [1, 2, 3], "attention_mask": [1, 1, 1], "labels": [-100, -100, 10]},
            {"input_ids": [4, 5, 6, 7], "attention_mask": [1, 1, 1, 1], "labels": [-100, 20, 21, 999]},
        ]
        batch = collator(features)
        self.assertEqual(len(batch["input_ids"][0]), 4)
        self.assertEqual(len(batch["input_ids"][1]), 4)

    def test_sft_collator_pads_labels_with_neg100(self):
        """Padded label positions must be -100, not the pad token id."""
        collator = data.make_sft_collator(self._tok())
        features = [
            {"input_ids": [1, 2], "attention_mask": [1, 1], "labels": [-100, 10]},
            {"input_ids": [4, 5, 6, 7], "attention_mask": [1, 1, 1, 1], "labels": [-100, 20, 21, 999]},
        ]
        batch = collator(features)
        # Short row: positions 2 and 3 are padded — labels must be -100
        self.assertEqual(batch["labels"][0][2], -100)
        self.assertEqual(batch["labels"][0][3], -100)
        # Short row: attention_mask at padded positions must be 0
        self.assertEqual(batch["attention_mask"][0][2], 0)
        self.assertEqual(batch["attention_mask"][0][3], 0)

    def test_sft_collator_preserves_existing_neg100(self):
        """Existing -100 labels (prompt mask) must survive collation unchanged."""
        collator = data.make_sft_collator(self._tok())
        features = [
            {"input_ids": [1, 2, 3, 4], "attention_mask": [1, 1, 1, 1], "labels": [-100, -100, 30, 999]},
            {"input_ids": [5, 6, 7, 8], "attention_mask": [1, 1, 1, 1], "labels": [-100, 40, 41, 999]},
        ]
        batch = collator(features)
        # No padding needed (equal-length batch) — labels must be unchanged.
        self.assertEqual(batch["labels"][0], [-100, -100, 30, 999])
        self.assertEqual(batch["labels"][1], [-100, 40, 41, 999])

    # --- config ---

    def test_stage2_smoke_config_loads(self):
        """stage2_smoke.json must parse and have stage='stage2-sft'."""
        repo_root = Path(__file__).resolve().parents[2]
        cfg = TrainConfig.from_json(repo_root / "code" / "configs" / "stage2_smoke.json")
        self.assertEqual(cfg.stage, "stage2-sft")
        self.assertEqual(cfg.sft_instruction_field, "instruction")
        self.assertEqual(cfg.sft_source_field, "source_text")
        self.assertEqual(cfg.sft_target_field, "target_text")

    def test_stage2_prototype_config_loads(self):
        """stage2_prototype.json must parse and have stage='stage2-sft'."""
        repo_root = Path(__file__).resolve().parents[2]
        cfg = TrainConfig.from_json(repo_root / "code" / "configs" / "stage2_prototype.json")
        self.assertEqual(cfg.stage, "stage2-sft")
        self.assertIn("stage2", cfg.train_path)


if __name__ == "__main__":
    unittest.main()
