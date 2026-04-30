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