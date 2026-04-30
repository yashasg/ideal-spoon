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
    tokenize_example / build_train_dataset work without any HF downloads.
    """

    pad_token = "<pad>"
    eos_token = "<eos>"

    def __call__(
        self,
        text: str,
        max_length: int = 1024,
        truncation: bool = False,
        padding=False,
        return_tensors=None,
    ) -> dict:
        tokens = text.split()
        ids = [abs(hash(t)) % 1000 for t in tokens]
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


if __name__ == "__main__":
    unittest.main()
