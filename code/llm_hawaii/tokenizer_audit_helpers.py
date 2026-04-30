"""Reusable helpers for the tokenizer audit (test-driven, no scripts).

Pulled out of ``code/tests/test_tokenizer_audit.py`` so the test file stays a
thin smoke/unit harness and the orchestration/metric logic can be exercised by
unit tests with fake tokenizers.

Public entry points used by tests and the smoke harness:

- ``tokenizer_metadata_from_model_and_tokenizer(model_id, tokenizer)``
- ``detect_tokenizer_family(tokenizer)``
- ``compute_high_diacritic_metrics(text, tokenizer, ...)``
- ``compute_standalone_diacritic_chars(tokenizer, ...)``
- ``check_roundtrip_lossless(text, tokenizer)``
- ``tokenizer_audit_output_from_encoding(enc, ...)`` — orchestrator

Schema preserved at ``tokenizer_audit_report.v1``. The cleanup is additive:

* ``model.tokenizer_family`` is added.
* ``checks[*]`` may include ``status`` ∈ {``evaluated``, ``not_applicable``,
  ``not_evaluated``}; non-evaluated/not-applicable checks must not appear in
  ``recommendation.blocking_reasons``.
* ``high_diacritic`` is populated from the provided text instead of being
  hard-coded to ``not_evaluated``.
* ``diacritic_chars`` is populated per-character with decode correctness and a
  max-token-count gate.

No SHA256 computation is performed anywhere in this module.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable


BYTE_FALLBACK_RE = re.compile(r"^<0x[0-9A-Fa-f]{2}>$")


DEFAULT_THRESHOLDS = {
    "min_words": 1500,
    "min_high_diacritic_samples": 10,
    "overall_tokens_per_word_max": 2.50,
    "explicit_byte_fallback_rate_max": 0.0,
    "byte_fallback_or_proxy_rate_max": 0.01,
    "high_diacritic_tokens_per_word_max": 3.25,
    "high_diacritic_byte_fallback_or_proxy_rate_max": 0.01,
    "standalone_diacritic_char_max_tokens": 2,
}


# Hawaiian diacritics covered by the audit. Lowercase + uppercase, plus the
# ʻokina (U+02BB). NFC-normalized.
HAWAIIAN_DIACRITIC_CHARS = (
    "\u02bb",  # ʻ ʻokina
    "\u0101",  # ā
    "\u0113",  # ē
    "\u012b",  # ī
    "\u014d",  # ō
    "\u016b",  # ū
    "\u0100",  # Ā
    "\u0112",  # Ē
    "\u012a",  # Ī
    "\u014c",  # Ō
    "\u016a",  # Ū
)


# Tokenizer classes that are byte-level BPE by construction. Includes the
# ``TokenizersBackend`` wrapper that fast HF tokenizers expose and the common
# Llama-3 / GPT-2 / Qwen2 fast tokenizer classes.
BYTE_LEVEL_BPE_CLASSES = frozenset(
    {
        "TokenizersBackend",
        "GPT2Tokenizer",
        "GPT2TokenizerFast",
        "LlamaTokenizerFast",
        "Qwen2Tokenizer",
        "Qwen2TokenizerFast",
    }
)


def _as_list(value):
    if hasattr(value, "tolist"):
        value = value.tolist()
    return list(value)


def _is_byte_fallback(piece):
    return bool(BYTE_FALLBACK_RE.match(piece))


def _is_byte_fallback_or_proxy(piece):
    if _is_byte_fallback(piece):
        return True

    stripped = piece.lstrip("\u2581\u0120 ")  # ▁, Ġ, space
    return len(stripped) == 1 and ord(stripped) > 127


# ---------------- Metadata ----------------

HF_TOKENIZER_CACHE_FILES = (
    "tokenizer_config.json",
    "tokenizer.json",
    "special_tokens_map.json",
    "config.json",
)


def _iter_tokenizer_metadata_sources(tokenizer):
    """Yield a tokenizer and common nested tokenizer/backend objects once."""
    seen = set()
    pending = [tokenizer]
    while pending:
        source = pending.pop(0)
        if source is None:
            continue
        source_id = id(source)
        if source_id in seen:
            continue
        seen.add(source_id)
        yield source

        for attr in ("_tokenizer", "tokenizer", "backend_tokenizer"):
            child = getattr(source, attr, None)
            if child is not None and child is not source:
                pending.append(child)


def _looks_like_hf_model_id(model_id):
    if not isinstance(model_id, str) or not model_id:
        return False
    if model_id.startswith((".", "/", "~")) or "\\" in model_id:
        return False

    parts = model_id.split("/")
    return 1 <= len(parts) <= 2 and all(parts)


def _commit_sha_from_cached_path(cached_path):
    if not isinstance(cached_path, (str, Path)):
        return None

    parts = Path(cached_path).parts
    try:
        snapshots_index = parts.index("snapshots")
    except ValueError:
        return None
    if snapshots_index + 1 < len(parts):
        return parts[snapshots_index + 1]

    return None


def _hf_commit_sha_from_cached_snapshot(model_id):
    """Return the cached HF snapshot commit for a loaded model, if available."""
    if not _looks_like_hf_model_id(model_id):
        return None

    try:
        from huggingface_hub import try_to_load_from_cache
    except ImportError:
        return None

    for filename in HF_TOKENIZER_CACHE_FILES:
        cached_path = try_to_load_from_cache(
            model_id,
            filename,
            repo_type="model",
        )
        commit_sha = _commit_sha_from_cached_path(cached_path)
        if commit_sha:
            return commit_sha

    return None


def _first_tokenizer_name_or_path(tokenizer):
    for source in _iter_tokenizer_metadata_sources(tokenizer):
        name_or_path = getattr(source, "name_or_path", None)
        if name_or_path:
            return name_or_path

        init_kwargs = getattr(source, "init_kwargs", None)
        if isinstance(init_kwargs, dict):
            name_or_path = init_kwargs.get("name_or_path")
            if name_or_path:
                return name_or_path

    return None


def _first_tokenizer_commit_sha(model_id, tokenizer):
    for source in _iter_tokenizer_metadata_sources(tokenizer):
        commit_sha = getattr(source, "_commit_hash", None)
        if commit_sha:
            return commit_sha

        init_kwargs = getattr(source, "init_kwargs", None)
        if isinstance(init_kwargs, dict):
            commit_sha = init_kwargs.get("_commit_hash")
            if commit_sha:
                return commit_sha

    # Late binding: tests monkeypatch the module-level lookup.
    return _hf_commit_sha_from_cached_snapshot(model_id)


def _first_tokenizer_is_fast(tokenizer):
    for source in _iter_tokenizer_metadata_sources(tokenizer):
        is_fast = getattr(source, "is_fast", None)
        if is_fast is not None:
            return bool(is_fast)
    return None


def _first_tokenizer_vocab_size(tokenizer):
    for source in _iter_tokenizer_metadata_sources(tokenizer):
        try:
            return len(source)
        except TypeError:
            pass

        vocab_size = getattr(source, "vocab_size", None)
        if vocab_size is not None:
            return vocab_size

        get_vocab_size = getattr(source, "get_vocab_size", None)
        if callable(get_vocab_size):
            return get_vocab_size()

    return None


def tokenizer_metadata_from_model_and_tokenizer(model_id, tokenizer):
    """Derive a small metadata dict from ``model_id`` and a tokenizer object.

    See module docstring. No SHA256 computation. When ``tokenizer`` is ``None``
    the function still returns a dict with ``model_id`` populated and the rest
    set to ``None`` rather than raising. ``tokenizer_family`` is populated via
    :func:`detect_tokenizer_family`.
    """
    metadata = {
        "model_id": model_id,
        "tokenizer_name_or_path": None,
        "hf_commit_sha": None,
        "tokenizer_class": None,
        "tokenizer_family": None,
        "is_fast": None,
        "vocab_size": None,
    }
    if tokenizer is None:
        return metadata

    metadata["tokenizer_name_or_path"] = _first_tokenizer_name_or_path(tokenizer)
    metadata["hf_commit_sha"] = _first_tokenizer_commit_sha(model_id, tokenizer)

    metadata["tokenizer_class"] = type(tokenizer).__name__
    metadata["tokenizer_family"] = detect_tokenizer_family(tokenizer)
    metadata["is_fast"] = _first_tokenizer_is_fast(tokenizer)
    metadata["vocab_size"] = _first_tokenizer_vocab_size(tokenizer)

    return metadata


# ---------------- Tokenizer family detection ----------------

def _gpt2_byte_to_unicode_chars():
    """The 256 byte-level-BPE byte chars from the GPT-2 byte_to_unicode map.

    This is the canonical mapping used by GPT-2/3/4, Llama-3, and Qwen2
    byte-level BPE tokenizers. We compute it inline so we don't depend on
    ``transformers`` being installed.
    """
    bs = (
        list(range(ord("!"), ord("~") + 1))
        + list(range(ord("\u00a1"), ord("\u00ac") + 1))
        + list(range(ord("\u00ae"), ord("\u00ff") + 1))
    )
    cs = list(bs)
    n = 0
    for b in range(2 ** 8):
        if b not in bs:
            bs.append(b)
            cs.append(2 ** 8 + n)
            n += 1
    return [chr(c) for c in cs]


_GPT2_BYTE_CHARS_CACHE: tuple[str, ...] | None = None


def _gpt2_byte_chars_cached():
    global _GPT2_BYTE_CHARS_CACHE
    if _GPT2_BYTE_CHARS_CACHE is None:
        _GPT2_BYTE_CHARS_CACHE = tuple(_gpt2_byte_to_unicode_chars())
    return _GPT2_BYTE_CHARS_CACHE


def detect_tokenizer_family(tokenizer):
    """Classify a tokenizer's family for proxy-rule applicability.

    Returns one of:

    * ``"byte_level_bpe"`` — Llama-3, GPT-2/4, Qwen2-style. The proxy rule
      (``ord(piece) > 127``) is *not* applicable here: byte-level BPE encodes
      every multi-byte UTF-8 char via the GPT-2 byte-to-unicode map, which is
      lossless rather than fallback.
    * ``"sentencepiece_byte_fallback"`` — SentencePiece tokenizers with
       ``byte_fallback=True``. Proxy rule applicable, blocking.
    * ``"unknown"`` — fall-through. Proxy rule applicable (conservative).

    Detection order:

    1. Explicit ``<0xNN>`` byte-fallback tokens in vocab → SentencePiece BF.
    2. Class name on tokenizer or any nested source ∈ ``BYTE_LEVEL_BPE_CLASSES``.
    3. GPT-2 byte-to-unicode probe: ≥ 200/256 byte chars in vocab.
    """
    if tokenizer is None:
        return None

    vocab = _safe_get_vocab(tokenizer)

    if isinstance(vocab, dict) and any(
        BYTE_FALLBACK_RE.match(tok) for tok in vocab.keys()
    ):
        return "sentencepiece_byte_fallback"

    for source in _iter_tokenizer_metadata_sources(tokenizer):
        cls_name = type(source).__name__
        if cls_name in BYTE_LEVEL_BPE_CLASSES:
            return "byte_level_bpe"
        family_attr = getattr(source, "tokenizer_family", None)
        if isinstance(family_attr, str) and family_attr:
            return family_attr

    if isinstance(vocab, dict):
        gpt2_chars = _gpt2_byte_chars_cached()
        hits = sum(1 for c in gpt2_chars if c in vocab)
        if hits >= 200:
            return "byte_level_bpe"

    return "unknown"


def _safe_get_vocab(tokenizer):
    for source in _iter_tokenizer_metadata_sources(tokenizer):
        get_vocab = getattr(source, "get_vocab", None)
        if callable(get_vocab):
            try:
                vocab = get_vocab()
            except Exception:
                continue
            if isinstance(vocab, dict):
                return vocab
        vocab_attr = getattr(source, "vocab", None)
        if isinstance(vocab_attr, dict):
            return vocab_attr
    return None


# ---------------- Roundtrip ----------------

def _normalize_for_roundtrip(text):
    return unicodedata.normalize("NFC", text)


def check_roundtrip_lossless(text, tokenizer):
    """Encode ``text`` with ``tokenizer`` and verify decoding reproduces it.

    Returns ``(passed: bool, decoded: str | None)``. Comparison is exact after
    NFC normalization; whitespace changes are real audit failures.

    Raises nothing — any tokenizer error is treated as a failed roundtrip.
    """
    if text is None or tokenizer is None:
        return None, None

    try:
        enc = tokenizer(text, add_special_tokens=False)
    except TypeError:
        try:
            enc = tokenizer(text)
        except Exception:
            return False, None
    except Exception:
        return False, None

    ids = enc["input_ids"] if isinstance(enc, dict) else getattr(enc, "input_ids", None)
    if ids is None:
        return False, None
    ids = _as_list(ids)

    decode = getattr(tokenizer, "decode", None)
    if not callable(decode):
        return False, None
    try:
        decoded = decode(ids, skip_special_tokens=True)
    except TypeError:
        try:
            decoded = decode(ids)
        except Exception:
            return False, None
    except Exception:
        return False, None

    if not isinstance(decoded, str):
        return False, decoded

    passed = _normalize_for_roundtrip(decoded) == _normalize_for_roundtrip(text)
    return passed, decoded


# ---------------- High-diacritic + per-char ----------------

_HAW_DIACRITIC_SET = frozenset(HAWAIIAN_DIACRITIC_CHARS)


def _split_candidate_spans(text):
    if not text:
        return []
    chunks = re.split(r"\n\s*\n+|\n+|(?<=[.!?])\s+", text)
    out = []
    for chunk in chunks:
        chunk = chunk.strip()
        if chunk:
            out.append(chunk)
    if not out and text.strip():
        out = [text.strip()]
    return out


def _has_hawaiian_diacritic(span):
    return any(ch in _HAW_DIACRITIC_SET for ch in span)


def _encode_pieces(tokenizer, text, *, add_special_tokens=False):
    """Encode ``text`` and return ``(ids, pieces)``. Best-effort across HF and
    fake tokenizer shapes. Raises on tokenizer error so the caller can mark
    the slice ``not_evaluated`` cleanly.
    """
    try:
        enc = tokenizer(text, add_special_tokens=add_special_tokens)
    except TypeError:
        enc = tokenizer(text)

    if isinstance(enc, dict):
        ids = _as_list(enc["input_ids"])
        pieces = enc.get("tokens") or enc.get("pieces")
    else:
        ids = _as_list(getattr(enc, "input_ids"))
        pieces = getattr(enc, "tokens", None)
        if callable(pieces):
            pieces = pieces()

    if pieces is None:
        convert = getattr(tokenizer, "convert_ids_to_tokens", None)
        if callable(convert):
            pieces = convert(ids)
    if pieces is not None:
        pieces = _as_list(pieces)
    return ids, pieces


def compute_high_diacritic_metrics(text, tokenizer, *, family=None, thresholds=None):
    """Compute aggregated metrics over spans that carry Hawaiian diacritics.

    Returns a dict shaped like::

        {
            "status": "evaluated" | "insufficient_samples" | "not_evaluated",
            "sample_count": int,
            "word_count": int,
            "token_count": int,
            "tokens_per_word": float | None,
            "explicit_byte_fallback_rate": float | None,
            "byte_fallback_or_proxy_rate": float | None,   # null for byte_level_bpe
            "byte_fallback_or_proxy_status": "evaluated" | "not_applicable",
            "roundtrip_lossless": bool | None,
        }
    """
    thresholds = thresholds or DEFAULT_THRESHOLDS

    if text is None or tokenizer is None:
        return {
            "status": "not_evaluated",
            "sample_count": 0,
            "word_count": 0,
            "token_count": 0,
            "tokens_per_word": None,
            "explicit_byte_fallback_rate": None,
            "byte_fallback_or_proxy_rate": None,
            "byte_fallback_or_proxy_status": "not_evaluated",
            "roundtrip_lossless": None,
        }

    spans = [
        span for span in _split_candidate_spans(text) if _has_hawaiian_diacritic(span)
    ]
    sample_count = len(spans)
    min_samples = thresholds.get(
        "min_high_diacritic_samples",
        DEFAULT_THRESHOLDS["min_high_diacritic_samples"],
    )

    if sample_count == 0:
        return {
            "status": "insufficient_samples",
            "sample_count": 0,
            "sample_count_threshold": min_samples,
            "word_count": 0,
            "token_count": 0,
            "tokens_per_word": None,
            "explicit_byte_fallback_rate": None,
            "byte_fallback_or_proxy_rate": None,
            "byte_fallback_or_proxy_status": (
                "not_applicable" if family == "byte_level_bpe" else "not_evaluated"
            ),
            "roundtrip_lossless": None,
        }

    total_tokens = 0
    total_words = 0
    total_explicit = 0
    total_proxy = 0
    roundtrip_ok = True
    for span in spans:
        try:
            ids, pieces = _encode_pieces(tokenizer, span)
        except Exception:
            return {
                "status": "not_evaluated",
                "sample_count": sample_count,
                "word_count": 0,
                "token_count": 0,
                "tokens_per_word": None,
                "explicit_byte_fallback_rate": None,
                "byte_fallback_or_proxy_rate": None,
                "byte_fallback_or_proxy_status": "not_evaluated",
                "roundtrip_lossless": None,
            }
        total_tokens += len(ids)
        total_words += len(span.split())
        if pieces is not None:
            total_explicit += sum(_is_byte_fallback(p) for p in pieces)
            total_proxy += sum(_is_byte_fallback_or_proxy(p) for p in pieces)

        rt_passed, _ = check_roundtrip_lossless(span, tokenizer)
        if rt_passed is False:
            roundtrip_ok = False

    tokens_per_word = total_tokens / max(total_words, 1) if total_words else None
    explicit_rate = total_explicit / max(total_tokens, 1) if total_tokens else None
    proxy_rate = total_proxy / max(total_tokens, 1) if total_tokens else None

    if family == "byte_level_bpe":
        proxy_rate_out = None
        proxy_status = "not_applicable"
    else:
        proxy_rate_out = proxy_rate
        proxy_status = "evaluated"

    return {
        "status": (
            "evaluated" if sample_count >= min_samples else "insufficient_samples"
        ),
        "sample_count": sample_count,
        "sample_count_threshold": min_samples,
        "word_count": total_words,
        "token_count": total_tokens,
        "tokens_per_word": tokens_per_word,
        "explicit_byte_fallback_rate": explicit_rate,
        "byte_fallback_or_proxy_rate": proxy_rate_out,
        "byte_fallback_or_proxy_status": proxy_status,
        "roundtrip_lossless": roundtrip_ok,
    }


def compute_standalone_diacritic_chars(tokenizer, *, chars=None, thresholds=None):
    """Encode each Hawaiian diacritic char standalone and report token counts.

    Each item is::

        {
            "char": "ʻ", "codepoint": "U+02BB",
            "ids": [...], "pieces": [...] | None,
            "token_count": N, "decode_ok": bool, "passed": bool,
        }

    A char ``passed`` iff ``decode_ok`` AND ``token_count`` ≤
    ``thresholds["standalone_diacritic_char_max_tokens"]``.
    """
    thresholds = thresholds or DEFAULT_THRESHOLDS
    chars = tuple(chars) if chars is not None else HAWAIIAN_DIACRITIC_CHARS
    max_tokens = thresholds.get(
        "standalone_diacritic_char_max_tokens",
        thresholds.get(
            "diacritic_char_max_token_count",
            DEFAULT_THRESHOLDS["standalone_diacritic_char_max_tokens"],
        ),
    )

    if tokenizer is None:
        return {"status": "tokenizer_unavailable", "items": []}

    items = []
    for ch in chars:
        codepoint = "U+%04X" % ord(ch)
        try:
            ids, pieces = _encode_pieces(tokenizer, ch)
        except Exception:
            items.append(
                {
                    "char": ch,
                    "codepoint": codepoint,
                    "ids": [],
                    "pieces": None,
                    "token_count": 0,
                    "decode_ok": False,
                    "passed": False,
                }
            )
            continue

        decode = getattr(tokenizer, "decode", None)
        decoded = None
        if callable(decode):
            try:
                decoded = decode(ids, skip_special_tokens=True)
            except TypeError:
                try:
                    decoded = decode(ids)
                except Exception:
                    decoded = None
            except Exception:
                decoded = None
        decode_ok = (
            isinstance(decoded, str)
            and _normalize_for_roundtrip(decoded) == _normalize_for_roundtrip(ch)
        )

        token_count = len(ids)
        passed = bool(decode_ok and token_count <= max_tokens)
        items.append(
            {
                "char": ch,
                "codepoint": codepoint,
                "ids": ids,
                "pieces": pieces,
                "token_count": token_count,
                "decode_ok": decode_ok,
                "passed": passed,
            }
        )

    return {"status": "evaluated", "items": items}


# ---------------- Orchestrator ----------------

def _build_check(name, value, threshold, *, status="evaluated", reason=None):
    if status == "evaluated":
        if value is None:
            passed = None
            status = "not_evaluated"
        else:
            passed = value <= threshold if threshold is not None else None
    else:
        passed = None
    out = {
        "name": name,
        "value": value,
        "threshold": threshold,
        "passed": passed,
        "status": status,
    }
    if reason:
        out["reason"] = reason
    return out


def _build_min_check(name, value, threshold, *, status="evaluated", reason=None):
    if status == "evaluated":
        if value is None:
            passed = None
            status = "not_evaluated"
        else:
            passed = value >= threshold if threshold is not None else None
    else:
        passed = None
    out = {
        "name": name,
        "value": value,
        "threshold": threshold,
        "passed": passed,
        "status": status,
    }
    if reason:
        out["reason"] = reason
    return out


def _build_bool_check(name, *, value, status="evaluated", reason=None):
    """Boolean check (e.g., roundtrip_lossless). ``value`` is bool|None."""
    if status == "evaluated":
        if value is None:
            passed = None
            status = "not_evaluated"
        else:
            passed = bool(value)
    else:
        passed = None
    out = {
        "name": name,
        "value": value,
        "threshold": True,
        "passed": passed,
        "status": status,
    }
    if reason:
        out["reason"] = reason
    return out


def tokenizer_audit_output_from_encoding(
    enc,
    *,
    text=None,
    tokenizer=None,
    model_id=None,
    dry_run=True,
    thresholds=None,
):
    """Format a tokenizer audit report from one overall encoding.

    The orchestrator:

    * Pulls metadata via :func:`tokenizer_metadata_from_model_and_tokenizer`.
    * Computes overall metrics from ``enc`` (and ``text`` for ``word_count``).
    * Marks ``byte_fallback_or_proxy_rate`` ``not_applicable`` for
      ``byte_level_bpe`` tokenizers (rate value preserved for forensics).
    * Adds ``roundtrip_lossless`` as a blocking check when both ``text`` and
      ``tokenizer`` are provided.
    * Populates ``high_diacritic`` from spans of ``text`` carrying
      Hawaiian diacritics.
    * Populates ``diacritic_chars`` per-character with decode + max-token gate.
    * Builds ``recommendation.blocking_reasons`` from ``passed is False`` only.
      Not-applicable / not-evaluated checks are *never* added.
    """
    thresholds = thresholds or DEFAULT_THRESHOLDS
    ids = _as_list(enc["input_ids"])
    pieces = enc.get("tokens") or enc.get("pieces")
    if pieces is None and tokenizer is not None:
        convert = getattr(tokenizer, "convert_ids_to_tokens", None)
        if callable(convert):
            pieces = convert(ids)

    token_count = len(ids)
    word_count = len(text.split()) if text is not None else enc.get("word_count")
    tokens_per_word = (
        token_count / max(word_count, 1) if word_count is not None else None
    )

    explicit_byte_fallback_count = None
    byte_fallback_or_proxy_count = None
    if pieces is not None:
        pieces = _as_list(pieces)
        explicit_byte_fallback_count = sum(_is_byte_fallback(p) for p in pieces)
        byte_fallback_or_proxy_count = sum(
            _is_byte_fallback_or_proxy(p) for p in pieces
        )

    explicit_byte_fallback_rate = (
        explicit_byte_fallback_count / max(token_count, 1)
        if explicit_byte_fallback_count is not None
        else None
    )
    byte_fallback_or_proxy_rate = (
        byte_fallback_or_proxy_count / max(token_count, 1)
        if byte_fallback_or_proxy_count is not None
        else None
    )

    model_section = tokenizer_metadata_from_model_and_tokenizer(model_id, tokenizer)
    family = model_section.get("tokenizer_family")

    # ---- checks ----
    checks = []
    checks.append(
        _build_min_check(
            "minimum_word_count",
            word_count,
            thresholds.get("min_words"),
        )
    )
    checks.append(
        _build_check(
            "overall_tokens_per_word",
            tokens_per_word,
            thresholds["overall_tokens_per_word_max"],
        )
    )
    checks.append(
        _build_check(
            "explicit_byte_fallback_rate",
            explicit_byte_fallback_rate,
            thresholds["explicit_byte_fallback_rate_max"],
        )
    )

    if family == "byte_level_bpe":
        checks.append(
            _build_check(
                "byte_fallback_or_proxy_rate",
                byte_fallback_or_proxy_rate,
                thresholds["byte_fallback_or_proxy_rate_max"],
                status="not_applicable",
                reason="byte-level BPE: byte-pieces are lossless, not fallback",
            )
        )
    else:
        checks.append(
            _build_check(
                "byte_fallback_or_proxy_rate",
                byte_fallback_or_proxy_rate,
                thresholds["byte_fallback_or_proxy_rate_max"],
            )
        )

    # ---- roundtrip ----
    if text is not None and tokenizer is not None:
        rt_passed, _decoded = check_roundtrip_lossless(text, tokenizer)
        checks.append(_build_bool_check("roundtrip_lossless", value=rt_passed))

    # ---- high_diacritic ----
    high_diacritic = compute_high_diacritic_metrics(
        text, tokenizer, family=family, thresholds=thresholds
    )

    if high_diacritic["status"] in {"evaluated", "insufficient_samples"}:
        checks.append(
            _build_min_check(
                "high_diacritic_sample_count",
                high_diacritic["sample_count"],
                high_diacritic.get("sample_count_threshold"),
            )
        )
        checks.append(
            _build_check(
                "high_diacritic_tokens_per_word",
                high_diacritic["tokens_per_word"],
                thresholds.get("high_diacritic_tokens_per_word_max"),
            )
        )
        checks.append(
            _build_check(
                "high_diacritic_explicit_byte_fallback_rate",
                high_diacritic["explicit_byte_fallback_rate"],
                thresholds.get("explicit_byte_fallback_rate_max"),
            )
        )
        if high_diacritic["byte_fallback_or_proxy_status"] == "not_applicable":
            checks.append(
                _build_check(
                    "high_diacritic_byte_fallback_or_proxy_rate",
                    high_diacritic["byte_fallback_or_proxy_rate"],
                    thresholds.get(
                        "high_diacritic_byte_fallback_or_proxy_rate_max"
                    ),
                    status="not_applicable",
                    reason="byte-level BPE: byte-pieces are lossless, not fallback",
                )
            )
        else:
            checks.append(
                _build_check(
                    "high_diacritic_byte_fallback_or_proxy_rate",
                    high_diacritic["byte_fallback_or_proxy_rate"],
                    thresholds.get(
                        "high_diacritic_byte_fallback_or_proxy_rate_max"
                    ),
                )
            )

    # ---- diacritic_chars ----
    diacritic_chars = compute_standalone_diacritic_chars(
        tokenizer, thresholds=thresholds
    )
    if diacritic_chars["status"] == "evaluated" and diacritic_chars["items"]:
        all_passed = all(item["passed"] for item in diacritic_chars["items"])
        checks.append(
            _build_bool_check("standalone_diacritic_chars", value=all_passed)
        )

    # ---- blocking reasons: only explicit failures ----
    blocking_reasons = [c["name"] for c in checks if c["passed"] is False]

    return {
        "schema_version": "tokenizer_audit_report.v1",
        "dry_run": dry_run,
        "model": model_section,
        "thresholds": thresholds,
        "overall": {
            "token_count": token_count,
            "word_count": word_count,
            "tokens_per_word": tokens_per_word,
            "explicit_byte_fallback_count": explicit_byte_fallback_count,
            "explicit_byte_fallback_rate": explicit_byte_fallback_rate,
            "byte_fallback_or_proxy_count": byte_fallback_or_proxy_count,
            "byte_fallback_or_proxy_rate": byte_fallback_or_proxy_rate,
        },
        "high_diacritic": high_diacritic,
        "diacritic_chars": diacritic_chars,
        "checks": checks,
        "recommendation": {
            "decision": "no_go" if blocking_reasons else "go",
            "blocking_reasons": blocking_reasons,
        },
        "errors": [],
    }
