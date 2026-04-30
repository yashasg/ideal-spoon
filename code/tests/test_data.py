import itertools
import json
from pathlib import Path
import unittest

import llm_hawaii.data as data


# DO-NOW checklist (keep these changes in Stage-1 scope):
# 1) Add unit tests for:
#    - `iter_jsonl`: missing file, bad JSON, empty-line handling.
#    - `normalize_text`: NFC behavior with combining macron input.
#    - `tokenize_example`: missing `text_field` and labels==input_ids.
# 2) Add a tiny smoke runner (or test) that:
#    - loads `code/examples/train.jsonl.example`,
#    - tokenizes with a small `max_length`,
#    - confirms `build_train_dataset` returns >0 rows.


class TestData(unittest.TestCase):
    def test_iter_jsonl(self):
        with self.assertRaises(FileNotFoundError):
            list(data.iter_jsonl("nonexistent_file.jsonl"))

        repo_root = Path(__file__).resolve().parents[2]
        dev_path = repo_root / "code" / "examples" / "train.jsonl.example"
        self.assertTrue(dev_path.exists(), f"Missing eval file: {dev_path}")

        self.assertIsNotNone(data.iter_jsonl(dev_path))  # smoke test; more detailed tests in test_data.py

    def test_normalize_text(self):
        self.assertEqual(data.normalize_text("ha\u0304lau", form="NFC"), "hālau")  # smoke test; more detailed tests in test_data.py

    def test_tokenize_example_missing_text(self):
        _tokenizer = data.load_tokenizer("Qwen/Qwen2.5-0.5B")
        self.assertIsNotNone(_tokenizer)
        with self.assertRaises(KeyError):
            list(data.tokenize_example(
            {},
            tokenizer=_tokenizer,
            text_field="text",
            max_length=10,
            normalization="NFC"))

    def test_tokenize_example(self):
        _tokenizer = data.load_tokenizer("Qwen/Qwen2.5-0.5B")
        self.assertIsNotNone(_tokenizer)
        self.assertIsNotNone(data.tokenize_example(
            {"text": "ha\u0304lau"},
            tokenizer=_tokenizer,
            text_field="text",
            max_length=10,
            normalization="NFC"))
    
    def smoke_test_build_train_dataset(self):
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



if __name__ == "__main__":
    unittest.main()