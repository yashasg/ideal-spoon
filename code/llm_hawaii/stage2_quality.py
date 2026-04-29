"""Stage 2 alignment scoring + quality-filter policy (prototype, stdlib only).

Issue #12. This module is the small reusable surface that Stage 2 manifest
builders (Linus' `scripts/3xx_build_stage2_*.py`) and SFT JSONL emitters
(Basher's bidirectional emitter, issue #14) call to turn a *candidate*
en↔haw pair into:

  * an alignment confidence tier (`accept` / `review` / `reject`),
  * a list of quality flags (machine-readable tokens),
  * a list of manual-review reasons (human-readable strings),
  * the per-row fields that drop directly into the Stage 2 manifest schema
    documented in `docs/data-pipeline.md` § "Stage 2 manifest schema".

Design notes (durable):

  * **Stdlib only.** Optional LaBSE/LASER scores are accepted as a
    pre-computed `alignment_score` on input; this module never imports
    a model. That keeps it cheap to call from any builder and free of
    network/GPU coupling. Real LID and embedding alignment land later
    behind the same `score_pair()` surface.
  * **Per-row scoring is durable.** Thresholds change; per-row
    `alignment_score`, `alignment_score_components`, and `quality_flags`
    are baked into the manifest so re-filtering does not require
    re-aligning. See `docs/data-pipeline.md` § "Stage 2 transformation
    pipeline" note on the alignment threshold knob.
  * **Fail-conservative.** When a signal is missing (e.g., no
    `alignment_score` on a comparable-aligned pair) the tier degrades
    to `review`, never silently to `accept`.
  * **Compatible with the documented field vocabulary.** Fields emitted
    here are a strict superset of the Stage 2 manifest schema. New
    fields are scoped under `alignment_*`, `quality_*`, and
    `policy_version` to avoid colliding with Linus' manifest builder
    (#11) or Basher's SFT emitter (#14).

Usage::

    from llm_hawaii.stage2_quality import (
        PolicyConfig, score_pair, POLICY_VERSION,
    )

    cfg = PolicyConfig()  # defaults
    annotation = score_pair(candidate_pair, cfg)
    # `annotation` is a dict that merges into the manifest row.
"""

from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass, field, asdict
from typing import Any


# ---------------------------------------------------------------------------
# Policy version
# ---------------------------------------------------------------------------

# Bump this when a threshold, flag name, or tier rule changes in a way
# that would alter the manifest output for an unchanged input pair.
# The manifest writer should record this string per-row so old rows are
# explainable.
POLICY_VERSION = "stage2-quality-v0.1"


# ---------------------------------------------------------------------------
# Alignment-method classes
# ---------------------------------------------------------------------------

# Methods whose alignment is deterministic from an external key (verse ID,
# TMX line index, paired filename). For these, `alignment_score` is null
# and the alignment tier is driven by the *content* checks below, not by
# an embedding cosine.
DETERMINISTIC_METHODS: frozenset[str] = frozenset(
    {"verse-id", "tmx-line", "filename-pair", "manual"}
)

# Methods that require a numeric `alignment_score` (cosine similarity from
# an embedding aligner). Missing score → review-pending, never accept.
EMBEDDING_METHODS: frozenset[str] = frozenset({"laser", "labse"})

# Allowed `alignment_type` values, mirroring the manifest schema.
ALIGNMENT_TYPES: frozenset[str] = frozenset(
    {
        "parallel-verse",
        "parallel-sentence",
        "parallel-doc",
        "comparable-aligned",
        "dictionary-example",
        "synthetic-bt",
        "synthetic-ft",
    }
)


# ---------------------------------------------------------------------------
# Hawaiian orthography constants
# ---------------------------------------------------------------------------

OKINA = "\u02BB"           # canonical ʻokina
KAHAKO = set("āēīōūĀĒĪŌŪ")  # precomposed (NFC) long vowels
# Common ʻokina mis-encodings we expect the Stage-1 normalizer to have
# already canonicalized. Their presence on the Hawaiian side at scoring
# time is a flag: either the normalizer didn't run or this row bypassed
# it. See `scripts/301_build_stage1_dataset.py::normalize_hawaiian`.
OKINA_MISENCODINGS: tuple[str, ...] = ("\u2018", "\u2019", "\u02BC", "\u0060", "'")

# Hawaiian alphabet (consonants + vowels, in modern orthography).
HAW_LETTERS_LOWER: frozenset[str] = frozenset("aeiouāēīōūhklmnpw" + OKINA)


# ---------------------------------------------------------------------------
# Policy configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PolicyConfig:
    """Tunable thresholds for the Stage 2 quality policy.

    Defaults are deliberately conservative for a private prototype.
    Bump `POLICY_VERSION` when changing these.
    """

    # --- Embedding-alignment thresholds (cosine similarity) ---
    # Pairs at or above `accept_min` are eligible for `accept` (subject
    # to the content checks below). Pairs in [review_min, accept_min)
    # land in `review`. Pairs below `review_min` are rejected.
    accept_min: float = 0.75
    review_min: float = 0.55

    # --- Length-ratio gate (Hawaiian / English in tokens) ---
    # Hawaiian is on average longer in characters but comparable to
    # slightly shorter in whitespace tokens for many genres; a wide
    # band keeps the gate honest without being noisy.
    length_ratio_min: float = 0.5
    length_ratio_max: float = 2.5
    # Below this many tokens on either side, the pair is too short to
    # carry meaningful translation signal (likely a header, verse
    # number, or fragment).
    min_tokens_per_side: int = 3
    # Above this many tokens, the pair is suspiciously long for SFT and
    # is sent to review (likely a paragraph-level mis-alignment).
    max_tokens_per_side: int = 256

    # --- Hawaiian-side orthography gate ---
    # If the Hawaiian side is ≥ this many letters yet contains *zero*
    # ʻokina and *zero* kahakō, it's almost certainly mis-tagged or
    # OCR'd to oblivion.
    diacritic_required_min_len: int = 60
    # Share of non-Hawaiian-alphabet letters tolerated on the Hawaiian
    # side before flagging.
    nonhaw_letter_share_max: float = 0.10

    # --- Language-ID confidence ---
    lid_haw_min_confidence: float = 0.50
    lid_en_min_confidence: float = 0.50

    # --- Provenance ---
    # If true, missing source URLs for both sides downgrade the tier to
    # `review`. Synthetic pairs are exempt (they have no URL by design).
    require_source_url: bool = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def _ws_tokens(text: str) -> int:
    return len(text.split())


def _letters(text: str) -> list[str]:
    return [c for c in text if c.isalpha()]


def _haw_orthography_signals(haw_text: str) -> dict[str, Any]:
    """Cheap orthography fingerprint of the Hawaiian side.

    Returns counts and shares — no judgement calls. The policy decides
    what to do with these.
    """
    if not haw_text:
        return {
            "letters": 0,
            "okina_count": 0,
            "kahako_count": 0,
            "okina_misencoding_count": 0,
            "nonhaw_letter_share": 0.0,
            "is_nfc": True,
        }
    nfc = _nfc(haw_text)
    is_nfc = nfc == haw_text
    letters = _letters(nfc)
    n = len(letters) or 1
    nonhaw = sum(1 for c in letters if c.lower() not in HAW_LETTERS_LOWER)
    return {
        "letters": len(letters),
        "okina_count": nfc.count(OKINA),
        "kahako_count": sum(1 for c in nfc if c in KAHAKO),
        "okina_misencoding_count": sum(nfc.count(v) for v in OKINA_MISENCODINGS),
        "nonhaw_letter_share": nonhaw / n,
        "is_nfc": is_nfc,
    }


def _length_ratio(haw_tokens: int, en_tokens: int) -> float:
    if en_tokens <= 0:
        return math.inf
    return haw_tokens / en_tokens


# ---------------------------------------------------------------------------
# Quality-flag tokens (stable vocabulary — write to manifest as-is)
# ---------------------------------------------------------------------------

# These string tokens are the contract with downstream consumers. Add
# new tokens by extending this list; do not rename. (Renames force a
# `POLICY_VERSION` bump and a manifest re-write.)
QUALITY_FLAGS: frozenset[str] = frozenset(
    {
        # Structural / emptiness
        "empty_side",
        "duplicate_pair_text",
        # Length
        "side_too_short",
        "side_too_long",
        "length_ratio_extreme",
        # Hawaiian orthography
        "haw_no_diacritics",
        "haw_okina_misencoding",
        "haw_nfc_drift",
        "haw_nonhaw_letters_high",
        # Language ID
        "lid_haw_low",
        "lid_en_low",
        "lid_haw_wrong_label",
        "lid_en_wrong_label",
        # Alignment
        "alignment_score_missing",
        "alignment_score_below_review",
        "alignment_score_below_accept",
        "alignment_method_unknown",
        "alignment_type_unknown",
        # Provenance / source
        "source_url_missing",
        "synthetic_uncapped",
    }
)


def _flag_to_reason(flag: str) -> str:
    """Map machine flag → human-readable manual-review reason."""
    return {
        "empty_side": "One side of the pair is empty after normalization.",
        "duplicate_pair_text": "Hawaiian and English sides are identical text.",
        "side_too_short": "At least one side is below the minimum token count.",
        "side_too_long": "At least one side exceeds the maximum token count.",
        "length_ratio_extreme": "Hawaiian/English token ratio is outside the configured band.",
        "haw_no_diacritics": "Hawaiian side is long enough but contains no ʻokina or kahakō.",
        "haw_okina_misencoding": "Hawaiian side contains an ʻokina mis-encoding (e.g., U+2018/U+2019/ASCII apostrophe).",
        "haw_nfc_drift": "Hawaiian side is not in NFC form.",
        "haw_nonhaw_letters_high": "Hawaiian side contains a high share of letters outside the Hawaiian alphabet.",
        "lid_haw_low": "LID confidence on the Hawaiian side is below the configured floor.",
        "lid_en_low": "LID confidence on the English side is below the configured floor.",
        "lid_haw_wrong_label": "LID returned a non-Hawaiian label for the Hawaiian side.",
        "lid_en_wrong_label": "LID returned a non-English label for the English side.",
        "alignment_score_missing": "Embedding alignment score is missing for an embedding-method pair.",
        "alignment_score_below_review": "Alignment score is below the reject threshold.",
        "alignment_score_below_accept": "Alignment score is between review and accept thresholds.",
        "alignment_method_unknown": "Alignment method is not in the documented vocabulary.",
        "alignment_type_unknown": "Alignment type is not in the documented vocabulary.",
        "source_url_missing": "Source URL is missing on at least one side and the pair is not synthetic.",
        "synthetic_uncapped": "Pair is synthetic; verify Stage-2 synthetic-cap accounting before training.",
    }.get(flag, flag)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def score_pair(pair: dict[str, Any], config: PolicyConfig | None = None) -> dict[str, Any]:
    """Score one candidate Stage-2 pair and return manifest-shaped fields.

    Input `pair` is a dict with at minimum:

      * `text_haw`, `text_en`              — the Hawaiian/English strings
      * `alignment_type`                   — one of `ALIGNMENT_TYPES`
      * `alignment_method`                 — one of `DETERMINISTIC_METHODS ∪ EMBEDDING_METHODS`

    Optional fields read when present:

      * `alignment_score` (float, required for embedding methods)
      * `alignment_model` (string)
      * `lang_id_haw`, `lang_id_haw_confidence`
      * `lang_id_en`,  `lang_id_en_confidence`
      * `source_url_en`, `source_url_haw`
      * `synthetic` (bool)

    The output dict carries the alignment + quality fields the Stage 2
    manifest schema expects, plus three policy fields:
      `alignment_confidence_tier`, `quality_flags`, `manual_review_reasons`.

    The function never raises on malformed input; it produces a
    `reject` tier with explicit flags so the caller can decide whether
    to skip or quarantine the row.
    """
    cfg = config or PolicyConfig()

    haw = _nfc(pair.get("text_haw") or "")
    en = (pair.get("text_en") or "").strip()
    flags: list[str] = []
    components: dict[str, Any] = {}

    # ---- Structural ----
    if not haw.strip() or not en:
        flags.append("empty_side")
    if haw.strip() and en and haw.strip() == en:
        flags.append("duplicate_pair_text")

    # ---- Length ----
    haw_tokens = _ws_tokens(haw)
    en_tokens = _ws_tokens(en)
    components["haw_tokens"] = haw_tokens
    components["en_tokens"] = en_tokens
    if haw_tokens and en_tokens:
        if haw_tokens < cfg.min_tokens_per_side or en_tokens < cfg.min_tokens_per_side:
            flags.append("side_too_short")
        if haw_tokens > cfg.max_tokens_per_side or en_tokens > cfg.max_tokens_per_side:
            flags.append("side_too_long")
        ratio = _length_ratio(haw_tokens, en_tokens)
        components["length_ratio_haw_over_en"] = round(ratio, 4) if math.isfinite(ratio) else None
        if not (cfg.length_ratio_min <= ratio <= cfg.length_ratio_max):
            flags.append("length_ratio_extreme")
    else:
        components["length_ratio_haw_over_en"] = None

    # ---- Hawaiian orthography ----
    ortho = _haw_orthography_signals(haw)
    components["haw_orthography"] = ortho
    if ortho["letters"] >= cfg.diacritic_required_min_len and ortho["okina_count"] == 0 and ortho["kahako_count"] == 0:
        flags.append("haw_no_diacritics")
    if ortho["okina_misencoding_count"] > 0:
        flags.append("haw_okina_misencoding")
    if not ortho["is_nfc"]:
        flags.append("haw_nfc_drift")
    if ortho["nonhaw_letter_share"] > cfg.nonhaw_letter_share_max:
        flags.append("haw_nonhaw_letters_high")

    # ---- Language ID ----
    lid_haw = pair.get("lang_id_haw")
    lid_haw_conf = pair.get("lang_id_haw_confidence")
    lid_en = pair.get("lang_id_en")
    lid_en_conf = pair.get("lang_id_en_confidence")
    if lid_haw is not None and lid_haw not in {"haw", "haw_Latn", "hawaiian"}:
        flags.append("lid_haw_wrong_label")
    if lid_en is not None and lid_en not in {"en", "eng", "eng_Latn", "english"}:
        flags.append("lid_en_wrong_label")
    if isinstance(lid_haw_conf, (int, float)) and lid_haw_conf < cfg.lid_haw_min_confidence:
        flags.append("lid_haw_low")
    if isinstance(lid_en_conf, (int, float)) and lid_en_conf < cfg.lid_en_min_confidence:
        flags.append("lid_en_low")

    # ---- Alignment vocabulary ----
    a_type = pair.get("alignment_type")
    a_method = pair.get("alignment_method")
    a_score = pair.get("alignment_score")
    a_model = pair.get("alignment_model")

    if a_type not in ALIGNMENT_TYPES:
        flags.append("alignment_type_unknown")
    if a_method not in (DETERMINISTIC_METHODS | EMBEDDING_METHODS):
        flags.append("alignment_method_unknown")

    # ---- Alignment score (only meaningful for embedding methods) ----
    score_tier: str
    if a_method in EMBEDDING_METHODS:
        if not isinstance(a_score, (int, float)):
            flags.append("alignment_score_missing")
            score_tier = "review"
        elif a_score < cfg.review_min:
            flags.append("alignment_score_below_review")
            score_tier = "reject"
        elif a_score < cfg.accept_min:
            flags.append("alignment_score_below_accept")
            score_tier = "review"
        else:
            score_tier = "accept"
    elif a_method in DETERMINISTIC_METHODS:
        # Deterministic alignment: trust the key, defer to content checks.
        score_tier = "accept"
    else:
        # Unknown method handled above; treat as review.
        score_tier = "review"

    # ---- Provenance ----
    is_synthetic = bool(pair.get("synthetic", False))
    if cfg.require_source_url and not is_synthetic:
        if not (pair.get("source_url_en") or pair.get("source_url_haw")):
            flags.append("source_url_missing")
    if is_synthetic:
        flags.append("synthetic_uncapped")

    # ---- Tier composition ----
    # `reject` if any structural / hard flag is present, otherwise the
    # worst of (score_tier, content_tier) wins. `content_tier` is
    # `review` if any soft flag is present, else `accept`.
    hard_flags = {
        "empty_side",
        "duplicate_pair_text",
        "side_too_short",
        "alignment_score_below_review",
        "alignment_type_unknown",
        "alignment_method_unknown",
    }
    soft_flags = {
        "side_too_long",
        "length_ratio_extreme",
        "haw_no_diacritics",
        "haw_okina_misencoding",
        "haw_nfc_drift",
        "haw_nonhaw_letters_high",
        "lid_haw_low",
        "lid_en_low",
        "lid_haw_wrong_label",
        "lid_en_wrong_label",
        "alignment_score_below_accept",
        "alignment_score_missing",
        "source_url_missing",
        "synthetic_uncapped",
    }

    flag_set = set(flags)
    if flag_set & hard_flags:
        tier = "reject"
    else:
        content_tier = "review" if (flag_set & soft_flags) else "accept"
        # `accept < review < reject` ordering.
        order = {"accept": 0, "review": 1, "reject": 2}
        tier = max(score_tier, content_tier, key=lambda t: order[t])

    reasons = [_flag_to_reason(f) for f in flags]

    annotation: dict[str, Any] = {
        # Existing manifest schema fields (passed through / computed):
        "alignment_type": a_type,
        "alignment_method": a_method,
        "alignment_model": a_model,
        "alignment_score": a_score if isinstance(a_score, (int, float)) else None,
        "length_ratio_haw_over_en": components.get("length_ratio_haw_over_en"),
        "alignment_review_required": tier in {"review", "reject"},
        # Policy additions:
        "alignment_confidence_tier": tier,
        "alignment_score_components": components,
        "quality_flags": flags,
        "manual_review_reasons": reasons,
        "policy_version": POLICY_VERSION,
    }
    return annotation


def policy_summary(config: PolicyConfig | None = None) -> dict[str, Any]:
    """Return the active policy as a dict, for run-report logging."""
    cfg = config or PolicyConfig()
    return {
        "policy_version": POLICY_VERSION,
        "config": asdict(cfg),
        "deterministic_methods": sorted(DETERMINISTIC_METHODS),
        "embedding_methods": sorted(EMBEDDING_METHODS),
        "alignment_types": sorted(ALIGNMENT_TYPES),
        "quality_flags": sorted(QUALITY_FLAGS),
    }


__all__ = [
    "POLICY_VERSION",
    "ALIGNMENT_TYPES",
    "DETERMINISTIC_METHODS",
    "EMBEDDING_METHODS",
    "QUALITY_FLAGS",
    "PolicyConfig",
    "score_pair",
    "policy_summary",
]
