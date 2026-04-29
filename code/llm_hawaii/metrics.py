"""Pure-Python Hawaiian text quality checks.

Implement this file first.

What to do here:
1. Run these helpers directly in a Python REPL with tiny strings.
2. Add unit tests before changing model/training code; this file has no ML deps.
3. Keep the checks simple and explainable: count ʻokina, wrong apostrophes,
   kahakō, combining macrons, and NFC status.
4. Use these checks from `evaluate.py` so every checkpoint gets an orthography
   sanity report.

No ML dependencies — these are unit-testable on a laptop. The point is to make
orthography failures *legible*: a model that strips ʻokina or substitutes a
typewriter apostrophe is broken in a way average loss won't reveal.

References:
- ʻokina is U+02BB (MODIFIER LETTER TURNED COMMA).
- Common WRONG substitutions: U+0027 ('), U+2018 (‘), U+2019 (’),
  U+02BC (modifier letter apostrophe — close but not the standard).
- Kahakō are precomposed long vowels: ā ē ī ō ū / Ā Ē Ī Ō Ū.
- Project Unicode form: NFC.
"""

from __future__ import annotations

import unicodedata

OKINA = "\u02BB"
WRONG_OKINA_CHARS = ("\u0027", "\u2018", "\u2019", "\u02BC")

KAHAKO_VOWELS = (
    "\u0101",  # ā
    "\u0113",  # ē
    "\u012B",  # ī
    "\u014D",  # ō
    "\u016B",  # ū
    "\u0100",  # Ā
    "\u0112",  # Ē
    "\u012A",  # Ī
    "\u014C",  # Ō
    "\u016A",  # Ū
)

# Combining macron — its presence in NFC form means a kahakō was emitted
# as base+combining instead of precomposed. That's a normalization bug.
COMBINING_MACRON = "\u0304"


def is_nfc(text: str) -> bool:
    return unicodedata.normalize("NFC", text) == text


def count_okina(text: str) -> int:
    return text.count(OKINA)


def count_wrong_okina(text: str) -> int:
    return sum(text.count(c) for c in WRONG_OKINA_CHARS)


def count_kahako(text: str) -> int:
    return sum(text.count(c) for c in KAHAKO_VOWELS)


def count_combining_macron(text: str) -> int:
    return text.count(COMBINING_MACRON)


def okina_survival_rate(generated: str, reference: str) -> float:
    """Fraction of reference ʻokina that survived in the generation.

    Returns 1.0 when reference has no ʻokina — survival is undefined,
    but reporting NaN tends to break downstream aggregations.
    """
    ref_count = count_okina(reference)
    if ref_count == 0:
        return 1.0
    gen_count = count_okina(generated)
    return min(gen_count / ref_count, 1.0)


def kahako_retention_rate(generated: str, reference: str) -> float:
    """Fraction of reference kahakō vowels that survived in generation."""
    ref_count = count_kahako(reference)
    if ref_count == 0:
        return 1.0
    gen_count = count_kahako(generated)
    return min(gen_count / ref_count, 1.0)


def orthography_report(text: str) -> dict:
    """Cheap per-string diagnostic. Useful per-generation in eval."""
    return {
        "is_nfc": is_nfc(text),
        "okina": count_okina(text),
        "wrong_okina": count_wrong_okina(text),
        "kahako": count_kahako(text),
        "combining_macron": count_combining_macron(text),
        "len": len(text),
    }


# ---------------- TODOs for the learner ----------------
#
# TODO(tokens-per-word): Tokens/word and byte-fallback rate require a
#   tokenizer to compute and so don't belong here (they live in the
#   tokenizer audit). But you may want a thin wrapper in evaluate.py
#   that calls into a tokenizer and reports those alongside this dict.
#
# TODO(diacritic-density-bins): For diagnostic slicing, bin items by
#   ʻokina + kahakō count per 100 chars (low/mid/high). The eval doc
#   uses these bins to expose orthography-handling regressions.
