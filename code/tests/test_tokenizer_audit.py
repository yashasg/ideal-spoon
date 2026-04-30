"""Tests + smoke harness for the tokenizer audit.

Helper logic lives in ``llm_hawaii.tokenizer_audit_helpers``. This file is
the test surface only:

* Smoke-only harness ``TestTokenizerAuditSmoke`` exercises the orchestrator
  against the real ``meta-llama/Llama-3.1-8B`` tokenizer when ``transformers``
  + the cached snapshot are available; otherwise it skips.
* Unit tests use the fake tokenizers below to cover metadata, family
  detection, proxy not-applicable handling, blocking-reason semantics,
  roundtrip failures, high-diacritic population, and diacritic-char gating.
"""

from __future__ import annotations

import datetime
import json
import unittest
from pathlib import Path

import sys
_REPO_CODE = Path(__file__).resolve().parents[1]
if str(_REPO_CODE) not in sys.path:
    sys.path.insert(0, str(_REPO_CODE))

from llm_hawaii import tokenizer_audit_helpers as helpers  # noqa: E402
from llm_hawaii.tokenizer_audit_helpers import (  # noqa: E402
    BYTE_FALLBACK_RE,
    DEFAULT_THRESHOLDS,
    HAWAIIAN_DIACRITIC_CHARS,
    _commit_sha_from_cached_path,
    check_roundtrip_lossless,
    compute_high_diacritic_metrics,
    compute_standalone_diacritic_chars,
    detect_tokenizer_family,
    tokenizer_audit_output_from_encoding,
    tokenizer_metadata_from_model_and_tokenizer,
)


# ---------------------------------------------------------------------------
# Smoke harness (skipped when transformers/the model snapshot are unavailable)
# ---------------------------------------------------------------------------


def _transformers_available():
    try:
        import transformers  # noqa: F401
        return True
    except Exception:
        return False


@unittest.skipUnless(
    _transformers_available(), "transformers not installed; skipping smoke run"
)
class TestTokenizerAuditSmoke(unittest.TestCase):
    def test_smoke_tokenizer_audit(self):
        import llm_hawaii.data as data

        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y%m%dT%H%M%SZ"
        )
        model_id = "meta-llama/Llama-3.1-8B"
        dry_run = False

        try:
            tokenizer = data.load_tokenizer(model_id)
        except Exception as exc:  # gated/no cache → skip, not fail
            self.skipTest(f"tokenizer unavailable: {exc}")

        repo_root = Path(__file__).resolve().parents[2]
        dev_path = (
            repo_root
            / "data"
            / "tokenizer_audit"
            / "ulukau_nupepa"
            / "kaehuikimanoopuuloa"
            / "kaehuikimanoopuuloa.jsonl"
        )
        if not dev_path.exists():
            self.skipTest(f"missing eval file: {dev_path}")

        text_record = json.loads(dev_path.read_text(encoding="utf-8"))
        self.assertIsInstance(text_record, dict)

        enc = data.tokenize_example(
            text_record,
            tokenizer=tokenizer,
            text_field="text",
            max_length=10000,
            normalization="NFC",
        )
        self.assertIsNotNone(enc)

        report = tokenizer_audit_output_from_encoding(
            enc,
            text=text_record["text"],
            tokenizer=tokenizer,
            model_id=model_id,
            dry_run=dry_run,
        )
        self.assertGreater(report["overall"]["token_count"], 0)
        self.assertGreater(report["overall"]["word_count"], 0)
        self.assertEqual(report["dry_run"], dry_run)
        self.assertEqual(report["model"]["model_id"], model_id)
        self.assertNotIn("model_repo_sha", report["model"])
        self.assertNotIn("tokenizer_sha256", report["model"])
        self.assertNotIn("tokenizer_fingerprint_sha256", report["model"])
        self.assertIn(report["recommendation"]["decision"], {"go", "no_go"})

        out_dir = repo_root / "data" / "tokenizer_audit" / (
            "dry_run" if dry_run else "official"
        )
        out_dir.mkdir(parents=True, exist_ok=True)

        out_path = out_dir / f"{timestamp}__{model_id.replace('/', '_')}.json"
        out_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Wrote report to: {out_path}")


# ---------------------------------------------------------------------------
# Fake tokenizers used by unit tests
# ---------------------------------------------------------------------------


class _FakeFastTokenizer:
    """Bare metadata-only stub used by metadata tests."""

    name_or_path = "fake-org/fake-tok"
    is_fast = True
    _commit_hash = "deadbeefcafebabe0123456789abcdef01234567"

    def __init__(self, vocab_size=128):
        self._vocab_size = vocab_size

    def __len__(self):
        return self._vocab_size


class _FakeSlowTokenizerInitKwargs:
    name_or_path = "fake-org/slow-tok"
    is_fast = False
    init_kwargs = {"_commit_hash": "feedfacefeedface00112233445566778899aabb"}

    def __len__(self):
        return 64


class _FakeUnsizedTokenizer:
    name_or_path = ""
    is_fast = True


class _FakeBackendTokenizer:
    is_fast = True

    def get_vocab_size(self):
        return 512


class _FakeWrapperWithBackendTokenizer:
    init_kwargs = {
        "name_or_path": "fake-org/wrapped-tok",
        "_commit_hash": "00112233445566778899aabbccddeeff00112233",
    }

    def __init__(self):
        self.backend_tokenizer = _FakeBackendTokenizer()


class _CharTokenizer:
    """A character-level tokenizer used to exercise the orchestrator end-to-end.

    * id 0 is reserved for unknown
    * remaining ids assigned per unique char on first encounter (stable order)
    * decode is lossless
    * not byte-level BPE; family resolves to ``unknown``
    """

    name_or_path = "fake-org/char-tok"
    is_fast = True
    _commit_hash = "1111111111111111111111111111111111111111"

    def __init__(self, family_hint=None):
        self._vocab = {"<unk>": 0}
        self._family_hint = family_hint
        if family_hint is not None:
            self.tokenizer_family = family_hint

    def _id_for(self, ch):
        if ch not in self._vocab:
            self._vocab[ch] = len(self._vocab)
        return self._vocab[ch]

    def __call__(self, text, add_special_tokens=False):
        ids = [self._id_for(ch) for ch in text]
        pieces = list(text)
        return {"input_ids": ids, "tokens": pieces, "attention_mask": [1] * len(ids)}

    def __len__(self):
        return max(len(self._vocab), 1)

    def get_vocab(self):
        return dict(self._vocab)

    def convert_ids_to_tokens(self, ids):
        inv = {v: k for k, v in self._vocab.items()}
        return [inv.get(i, "<unk>") for i in ids]

    def decode(self, ids, skip_special_tokens=True):
        inv = {v: k for k, v in self._vocab.items()}
        out = []
        for i in ids:
            piece = inv.get(i, "")
            if skip_special_tokens and piece in {"<unk>"}:
                continue
            out.append(piece)
        return "".join(out)


class _ByteLevelBPELikeTokenizer(_CharTokenizer):
    """A char tokenizer that *also* declares itself ``LlamaTokenizerFast``."""


_ByteLevelBPELikeTokenizer.__name__ = "LlamaTokenizerFast"


class _GenericFastTokenizer(_CharTokenizer):
    """A generic fast tokenizer class without GPT-2 byte chars in its vocab."""


_GenericFastTokenizer.__name__ = "PreTrainedTokenizerFast"


class _LossyTokenizer(_CharTokenizer):
    """Decode appends a sentinel char → roundtrip never matches."""

    def decode(self, ids, skip_special_tokens=True):
        s = super().decode(ids, skip_special_tokens=skip_special_tokens)
        return s + "X"


class _WhitespaceDroppingTokenizer(_CharTokenizer):
    """Decode strips whitespace so exact roundtrip should fail."""

    def decode(self, ids, skip_special_tokens=True):
        return super().decode(ids, skip_special_tokens=skip_special_tokens).strip()


class _SentencePieceLikeTokenizer:
    """Has explicit ``<0x..>`` byte-fallback tokens in vocab → SentencePiece BF."""

    name_or_path = "fake-org/spm"
    is_fast = False
    _commit_hash = "2222222222222222222222222222222222222222"

    def __init__(self):
        base = ["a", "b", "c", "▁", "ʻ", "ā"]
        self._vocab = {tok: i for i, tok in enumerate(base)}
        for b in range(256):
            self._vocab[f"<0x{b:02X}>"] = len(self._vocab)

    def get_vocab(self):
        return dict(self._vocab)

    def __len__(self):
        return len(self._vocab)


# ---------------------------------------------------------------------------
# Metadata tests (parity with prior coverage)
# ---------------------------------------------------------------------------


class TestTokenizerMetadataFromModelAndTokenizer(unittest.TestCase):
    def test_none_tokenizer_returns_model_id_with_nones(self):
        meta = tokenizer_metadata_from_model_and_tokenizer("org/model", None)
        self.assertEqual(meta["model_id"], "org/model")
        self.assertIsNone(meta["tokenizer_name_or_path"])
        self.assertIsNone(meta["hf_commit_sha"])
        self.assertIsNone(meta["tokenizer_class"])
        self.assertIsNone(meta["tokenizer_family"])
        self.assertIsNone(meta["is_fast"])
        self.assertIsNone(meta["vocab_size"])

    def test_fast_tokenizer_with_commit_hash_attr(self):
        tok = _FakeFastTokenizer(vocab_size=256)
        meta = tokenizer_metadata_from_model_and_tokenizer("org/model", tok)
        self.assertEqual(meta["model_id"], "org/model")
        self.assertEqual(meta["tokenizer_name_or_path"], "fake-org/fake-tok")
        self.assertEqual(
            meta["hf_commit_sha"], "deadbeefcafebabe0123456789abcdef01234567"
        )
        self.assertEqual(meta["tokenizer_class"], "_FakeFastTokenizer")
        self.assertTrue(meta["is_fast"])
        self.assertEqual(meta["vocab_size"], 256)

    def test_commit_hash_falls_back_to_init_kwargs(self):
        tok = _FakeSlowTokenizerInitKwargs()
        meta = tokenizer_metadata_from_model_and_tokenizer("org/slow", tok)
        self.assertEqual(
            meta["hf_commit_sha"], "feedfacefeedface00112233445566778899aabb"
        )
        self.assertFalse(meta["is_fast"])
        self.assertEqual(meta["vocab_size"], 64)

    def test_metadata_uses_wrapper_and_backend_sources(self):
        tok = _FakeWrapperWithBackendTokenizer()
        meta = tokenizer_metadata_from_model_and_tokenizer("org/wrapped", tok)
        self.assertEqual(meta["tokenizer_name_or_path"], "fake-org/wrapped-tok")
        self.assertEqual(
            meta["hf_commit_sha"], "00112233445566778899aabbccddeeff00112233"
        )
        self.assertEqual(meta["tokenizer_class"], "_FakeWrapperWithBackendTokenizer")
        self.assertTrue(meta["is_fast"])
        self.assertEqual(meta["vocab_size"], 512)

    def test_commit_hash_falls_back_to_cached_hf_snapshot(self):
        original = helpers._hf_commit_sha_from_cached_snapshot
        helpers._hf_commit_sha_from_cached_snapshot = (
            lambda model_id: "abcdef0123456789abcdef0123456789abcdef01"
        )
        try:
            tok = _FakeBackendTokenizer()
            meta = tokenizer_metadata_from_model_and_tokenizer("org/backend", tok)
        finally:
            helpers._hf_commit_sha_from_cached_snapshot = original

        self.assertEqual(
            meta["hf_commit_sha"], "abcdef0123456789abcdef0123456789abcdef01"
        )
        self.assertTrue(meta["is_fast"])
        self.assertEqual(meta["vocab_size"], 512)

    def test_cached_path_parser_reads_snapshot_commit(self):
        cached_path = (
            "/var/huggingface/hub/models--org--model/snapshots/"
            "1234567890abcdef1234567890abcdef12345678/tokenizer.json"
        )
        self.assertEqual(
            _commit_sha_from_cached_path(cached_path),
            "1234567890abcdef1234567890abcdef12345678",
        )

    def test_unsized_tokenizer_yields_none_vocab_size(self):
        tok = _FakeUnsizedTokenizer()
        meta = tokenizer_metadata_from_model_and_tokenizer("org/x", tok)
        self.assertIsNone(meta["vocab_size"])
        self.assertIsNone(meta["tokenizer_name_or_path"])
        self.assertIsNone(meta["hf_commit_sha"])
        self.assertEqual(meta["tokenizer_class"], "_FakeUnsizedTokenizer")
        self.assertTrue(meta["is_fast"])

    def test_audit_output_uses_metadata_for_model_section(self):
        tok = _FakeFastTokenizer(vocab_size=32)
        enc = {"input_ids": [1, 2, 3], "tokens": ["a", "b", "c"]}
        report = tokenizer_audit_output_from_encoding(
            enc, text="hello world", tokenizer=tok, model_id="org/model"
        )
        self.assertEqual(report["model"]["model_id"], "org/model")
        self.assertEqual(report["model"]["tokenizer_name_or_path"], "fake-org/fake-tok")
        self.assertEqual(
            report["model"]["hf_commit_sha"],
            "deadbeefcafebabe0123456789abcdef01234567",
        )
        self.assertEqual(report["model"]["tokenizer_class"], "_FakeFastTokenizer")
        self.assertTrue(report["model"]["is_fast"])
        self.assertEqual(report["model"]["vocab_size"], 32)
        self.assertNotIn("model_repo_sha", report["model"])
        self.assertNotIn("tokenizer_sha256", report["model"])
        self.assertNotIn("tokenizer_fingerprint_sha256", report["model"])

    def test_audit_output_without_tokenizer_still_carries_model_id(self):
        enc = {"input_ids": [1, 2], "tokens": ["a", "b"]}
        report = tokenizer_audit_output_from_encoding(
            enc, text="hi there", tokenizer=None, model_id="org/model"
        )
        self.assertEqual(report["model"]["model_id"], "org/model")
        self.assertIsNone(report["model"]["hf_commit_sha"])
        self.assertIsNone(report["model"]["tokenizer_class"])
        self.assertIsNone(report["model"]["tokenizer_family"])


# ---------------------------------------------------------------------------
# Family detection
# ---------------------------------------------------------------------------


class TestDetectTokenizerFamily(unittest.TestCase):
    def test_llama_class_name_classifies_as_byte_level_bpe(self):
        tok = _ByteLevelBPELikeTokenizer()
        self.assertEqual(detect_tokenizer_family(tok), "byte_level_bpe")

    def test_sentencepiece_byte_fallback_via_explicit_byte_tokens(self):
        tok = _SentencePieceLikeTokenizer()
        self.assertEqual(detect_tokenizer_family(tok), "sentencepiece_byte_fallback")

    def test_unknown_family_for_plain_char_tokenizer(self):
        tok = _CharTokenizer()
        self.assertEqual(detect_tokenizer_family(tok), "unknown")

    def test_generic_fast_class_without_byte_vocab_stays_unknown(self):
        tok = _GenericFastTokenizer()
        self.assertEqual(detect_tokenizer_family(tok), "unknown")

    def test_explicit_family_attr_is_respected(self):
        tok = _CharTokenizer(family_hint="byte_level_bpe")
        self.assertEqual(detect_tokenizer_family(tok), "byte_level_bpe")

    def test_metadata_includes_family(self):
        tok = _ByteLevelBPELikeTokenizer()
        meta = tokenizer_metadata_from_model_and_tokenizer("meta-llama/L", tok)
        self.assertEqual(meta["tokenizer_family"], "byte_level_bpe")


# ---------------------------------------------------------------------------
# Proxy applicability + blocking-reason semantics
# ---------------------------------------------------------------------------


class TestProxyApplicabilityAndBlockingReasons(unittest.TestCase):
    def test_proxy_not_applicable_for_byte_level_bpe(self):
        tok = _ByteLevelBPELikeTokenizer()
        # Build encoding with proxy-looking pieces (high-ord chars).
        text = "kahakō ʻokina"
        ids, pieces = helpers._encode_pieces(tok, text)
        enc = {"input_ids": ids, "tokens": pieces}

        report = tokenizer_audit_output_from_encoding(
            enc, text=text, tokenizer=tok, model_id="meta-llama/L"
        )
        proxy_check = next(
            c for c in report["checks"] if c["name"] == "byte_fallback_or_proxy_rate"
        )
        self.assertEqual(proxy_check["status"], "not_applicable")
        self.assertIsNone(proxy_check["passed"])
        self.assertNotIn(
            "byte_fallback_or_proxy_rate", report["recommendation"]["blocking_reasons"]
        )

    def test_proxy_blocking_for_unknown_family_when_over_threshold(self):
        # Fabricate pieces with a high proxy rate to force a failure.
        enc = {"input_ids": [1, 2, 3, 4], "tokens": ["a", "ā", "ē", "ī"]}
        # tokenizer=None → family stays None; proxy is still applicable.
        report = tokenizer_audit_output_from_encoding(
            enc,
            text="a ā ē ī",
            tokenizer=None,
            model_id="org/m",
            thresholds={
                **DEFAULT_THRESHOLDS,
                "byte_fallback_or_proxy_rate_max": 0.0,
            },
        )
        proxy_check = next(
            c for c in report["checks"] if c["name"] == "byte_fallback_or_proxy_rate"
        )
        self.assertEqual(proxy_check["status"], "evaluated")
        self.assertFalse(proxy_check["passed"])
        self.assertIn(
            "byte_fallback_or_proxy_rate", report["recommendation"]["blocking_reasons"]
        )

    def test_not_evaluated_check_does_not_appear_in_blocking_reasons(self):
        # No pieces → explicit/proxy rates are None → status not_evaluated → not blocking.
        enc = {"input_ids": [1, 2, 3]}
        report = tokenizer_audit_output_from_encoding(
            enc, text="a b c", tokenizer=None, model_id="org/m"
        )
        names = {c["name"]: c for c in report["checks"]}
        self.assertEqual(names["explicit_byte_fallback_rate"]["status"], "not_evaluated")
        self.assertEqual(names["byte_fallback_or_proxy_rate"]["status"], "not_evaluated")
        self.assertNotIn(
            "explicit_byte_fallback_rate", report["recommendation"]["blocking_reasons"]
        )
        self.assertNotIn(
            "byte_fallback_or_proxy_rate", report["recommendation"]["blocking_reasons"]
        )

    def test_explicit_byte_fallback_remains_blocking(self):
        # One explicit <0x..> piece in 4 → rate 0.25 > 0 threshold → blocks.
        enc = {"input_ids": [1, 2, 3, 4], "tokens": ["a", "<0xE2>", "b", "c"]}
        report = tokenizer_audit_output_from_encoding(
            enc, text="a b c d", tokenizer=None, model_id="org/m"
        )
        self.assertIn(
            "explicit_byte_fallback_rate",
            report["recommendation"]["blocking_reasons"],
        )


# ---------------------------------------------------------------------------
# Roundtrip
# ---------------------------------------------------------------------------


class TestRoundtripLossless(unittest.TestCase):
    def test_roundtrip_passes_for_lossless_tokenizer(self):
        tok = _CharTokenizer()
        passed, decoded = check_roundtrip_lossless("ʻōlelo Hawaiʻi", tok)
        self.assertTrue(passed)
        self.assertEqual(decoded, "ʻōlelo Hawaiʻi")

    def test_roundtrip_requires_exact_whitespace(self):
        tok = _WhitespaceDroppingTokenizer()
        passed, decoded = check_roundtrip_lossless(" ʻ ", tok)
        self.assertFalse(passed)
        self.assertEqual(decoded, "ʻ")

    def test_roundtrip_fails_for_lossy_tokenizer_and_blocks(self):
        tok = _LossyTokenizer()
        text = "ʻōlelo Hawaiʻi"
        ids, pieces = helpers._encode_pieces(tok, text)
        enc = {"input_ids": ids, "tokens": pieces}
        report = tokenizer_audit_output_from_encoding(
            enc, text=text, tokenizer=tok, model_id="org/lossy"
        )
        rt = next(c for c in report["checks"] if c["name"] == "roundtrip_lossless")
        self.assertEqual(rt["status"], "evaluated")
        self.assertFalse(rt["passed"])
        self.assertIn(
            "roundtrip_lossless", report["recommendation"]["blocking_reasons"]
        )
        self.assertEqual(report["recommendation"]["decision"], "no_go")

    def test_roundtrip_omitted_when_text_or_tokenizer_missing(self):
        enc = {"input_ids": [1, 2, 3], "tokens": ["a", "b", "c"]}
        report = tokenizer_audit_output_from_encoding(
            enc, text="a b c", tokenizer=None, model_id="org/m"
        )
        self.assertNotIn(
            "roundtrip_lossless", {c["name"] for c in report["checks"]}
        )


# ---------------------------------------------------------------------------
# High-diacritic + diacritic chars
# ---------------------------------------------------------------------------


HIGH_DIACRITIC_TEXT = (
    "Aloha kakou e na hoa.\n"
    "\n"
    "ʻO kēia ka ʻōlelo Hawaiʻi maoli — pīpī holo kaʻao,\n"
    "ē kuʻu hoa, ē hoʻomau kākou i ka ʻōlelo makuahine.\n"
    "\n"
    "He moʻolelo nō ia no ka ʻāina aloha o Hawaiʻi nei.\n"
)


class TestHighDiacriticPopulation(unittest.TestCase):
    def test_high_diacritic_uses_paragraphs_with_hawaiian_diacritics(self):
        tok = _CharTokenizer()
        metrics = compute_high_diacritic_metrics(
            HIGH_DIACRITIC_TEXT,
            tok,
            family="unknown",
            thresholds={**DEFAULT_THRESHOLDS, "min_high_diacritic_samples": 1},
        )
        self.assertEqual(metrics["status"], "evaluated")
        # First paragraph has no diacritics → excluded.
        self.assertGreaterEqual(metrics["sample_count"], 2)
        self.assertGreater(metrics["word_count"], 0)
        self.assertGreater(metrics["token_count"], 0)
        self.assertIsNotNone(metrics["tokens_per_word"])
        self.assertIsNotNone(metrics["explicit_byte_fallback_rate"])
        self.assertIsNotNone(metrics["byte_fallback_or_proxy_rate"])
        self.assertEqual(metrics["byte_fallback_or_proxy_status"], "evaluated")
        self.assertTrue(metrics["roundtrip_lossless"])

    def test_high_diacritic_proxy_rate_not_applicable_for_byte_level_bpe(self):
        tok = _ByteLevelBPELikeTokenizer()
        metrics = compute_high_diacritic_metrics(
            HIGH_DIACRITIC_TEXT,
            tok,
            family="byte_level_bpe",
            thresholds={**DEFAULT_THRESHOLDS, "min_high_diacritic_samples": 1},
        )
        self.assertEqual(metrics["status"], "evaluated")
        self.assertIsNone(metrics["byte_fallback_or_proxy_rate"])
        self.assertEqual(metrics["byte_fallback_or_proxy_status"], "not_applicable")

    def test_high_diacritic_check_appears_in_report_and_gates_threshold(self):
        tok = _CharTokenizer()
        # Force a tight threshold so the per-char tokenizer fails high-diac TPW.
        thresholds = {
            **DEFAULT_THRESHOLDS,
            "min_high_diacritic_samples": 1,
            "high_diacritic_tokens_per_word_max": 0.5,
        }
        ids, pieces = helpers._encode_pieces(tok, HIGH_DIACRITIC_TEXT)
        enc = {"input_ids": ids, "tokens": pieces}
        report = tokenizer_audit_output_from_encoding(
            enc,
            text=HIGH_DIACRITIC_TEXT,
            tokenizer=tok,
            model_id="org/m",
            thresholds=thresholds,
        )
        names = {c["name"] for c in report["checks"]}
        self.assertIn("high_diacritic_sample_count", names)
        self.assertIn("high_diacritic_tokens_per_word", names)
        self.assertIn("high_diacritic_explicit_byte_fallback_rate", names)
        self.assertIn("high_diacritic_byte_fallback_or_proxy_rate", names)
        self.assertIn(
            "high_diacritic_tokens_per_word",
            report["recommendation"]["blocking_reasons"],
        )

    def test_high_diacritic_insufficient_when_no_paragraphs_have_diacritics(self):
        tok = _CharTokenizer()
        plain = "this paragraph has no diacritics at all\n\nnor does this one"
        metrics = compute_high_diacritic_metrics(plain, tok)
        self.assertEqual(metrics["status"], "insufficient_samples")
        self.assertEqual(metrics["sample_count"], 0)
        self.assertEqual(
            metrics["sample_count_threshold"],
            DEFAULT_THRESHOLDS["min_high_diacritic_samples"],
        )


class TestDiacriticChars(unittest.TestCase):
    def test_diacritic_chars_pass_with_lossless_char_tokenizer(self):
        tok = _CharTokenizer()
        out = compute_standalone_diacritic_chars(tok)
        self.assertEqual(out["status"], "evaluated")
        self.assertEqual(len(out["items"]), len(HAWAIIAN_DIACRITIC_CHARS))
        for item in out["items"]:
            self.assertEqual(item["token_count"], 1)
            self.assertTrue(item["decode_ok"])
            self.assertTrue(item["passed"])
            self.assertTrue(item["codepoint"].startswith("U+"))

    def test_diacritic_chars_fail_when_decode_drops_char(self):
        tok = _LossyTokenizer()
        out = compute_standalone_diacritic_chars(tok)
        self.assertEqual(out["status"], "evaluated")
        # Lossy decode → decode_ok False → passed False even with token_count=1.
        for item in out["items"]:
            self.assertFalse(item["decode_ok"])
            self.assertFalse(item["passed"])

    def test_diacritic_chars_fail_when_token_count_exceeds_max(self):
        tok = _CharTokenizer()
        out = compute_standalone_diacritic_chars(
            tok,
            thresholds={**DEFAULT_THRESHOLDS, "standalone_diacritic_char_max_tokens": 0},
        )
        for item in out["items"]:
            self.assertTrue(item["decode_ok"])
            self.assertFalse(item["passed"])

    def test_standalone_diacritic_chars_check_blocks_when_any_fails(self):
        tok = _LossyTokenizer()
        text = "ʻōlelo"
        ids, pieces = helpers._encode_pieces(tok, text)
        enc = {"input_ids": ids, "tokens": pieces}
        report = tokenizer_audit_output_from_encoding(
            enc, text=text, tokenizer=tok, model_id="org/lossy"
        )
        self.assertIn(
            "standalone_diacritic_chars",
            report["recommendation"]["blocking_reasons"],
        )

    def test_diacritic_chars_status_when_tokenizer_unavailable(self):
        out = compute_standalone_diacritic_chars(None)
        self.assertEqual(out["status"], "tokenizer_unavailable")
        self.assertEqual(out["items"], [])


if __name__ == "__main__":
    unittest.main()
