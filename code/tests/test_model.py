# ---------------- TODOs for the learner ----------------
#
# TODO(merge-stage1): For the two-stage plan, after Stage 1 you need to
#   merge the LoRA into an fp16 base (`peft_model.merge_and_unload()`)
#   before starting Stage 2. Don't stack adapters for release.
#
# TODO(checkpoint-resume): When training on a free-tier GPU, sessions
#   die. Wire `transformers.Trainer(resume_from_checkpoint=...)` into
#   train.py and verify a kill -9 mid-run resumes cleanly.

import itertools
import json
from pathlib import Path
import unittest

import llm_hawaii.model as model




class Testmodel(unittest.TestCase):

    def test_bnb_compute_dtype_name_bf16(self):
        self.assertEqual(model._bnb_compute_dtype_name(bf16=True, fp16=False), "bfloat16")

    def test_bnb_compute_dtype_name_fp16(self):
        self.assertEqual(model._bnb_compute_dtype_name(bf16=False, fp16=True), "float16")

    def test_bnb_compute_dtype_name_fp32(self):
        self.assertEqual(model._bnb_compute_dtype_name(bf16=False, fp16=False), "float32")

    def test_bnb_compute_dtype_name_bf16_takes_priority(self):
        # bf16 wins if both flags are set (should not normally happen)
        self.assertEqual(model._bnb_compute_dtype_name(bf16=True, fp16=True), "bfloat16")

    def test_check_runtime_capability(self):
        info = model.check_runtime_capability(use_qlora=True, want_bf16=True)
        print(info)
        self.assertIsInstance(info, dict)
        self.assertIn("cuda_available", info)
        self.assertIn("device_count", info)
        self.assertIn("bf16_supported", info)
        self.assertIn("device_name", info)
        self.assertIn("compute_capability", info)
    



if __name__ == "__main__":
    unittest.main()