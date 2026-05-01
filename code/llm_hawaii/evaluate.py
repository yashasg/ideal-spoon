"""Checkpoint evaluation CLI.

Implement this file in this order:
1. Load a checkpoint and tokenizer without generating anything.
2. Compute held-out perplexity on a tiny eval JSONL.
3. Add a few fixed prompts and save the generations.
4. Run `metrics.py` checks on each generation so orthography regressions are
   visible, not buried in average loss.
5. Keep checkpoint-dev and final-holdout separate: dev is for frequent
   diagnostics; final is for major milestone checks.

Two things this should report at minimum:

  1. Held-out perplexity on a Hawaiian eval JSONL.
  2. A small batch of generations + Hawaiian text-quality checks
     (ʻokina survival, kahakō retention, NFC integrity) from
     `metrics.py`.

The output dict is also designed as a checkpoint *drift bundle*: it
captures eval-run identity (eval-file SHA, decoding config, dtype/device,
tokenizer/model identity), an orthography aggregate + tripwires across a
fixed prompt suite, and a `prompt_suite_sha256` so future checkpoints can
be compared without leaking raw text into tracked summaries. See
`docs/eval_pipeline.md` §8.

Heavy ML deps are lazy-imported. The file parses without them.

Run:

    python -m llm_hawaii.evaluate \
        --checkpoint runs/smoke \
        --eval-file examples/eval.jsonl.example
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

from . import metrics as metrics_mod

# Default off-git location for the populated W1 hand-authored Hawaiian
# micro-eval JSONL. The file lives under the gitignored `data/` tree (see
# `data-sources/manual-eval/README.md`); presence here is optional and
# the harness reports an explicit `missing` status when absent.
#
# Per user directive (.squad/decisions/inbox/copilot-directive-20260430T081137Z.md),
# Stage 0 W1 input is JSONL-only. The TSV is the local authoring/source
# format consumed by `scripts/315_hash_manual_w1_eval.py`; the JSONL it
# emits is the eval-consumable artifact.
DEFAULT_MANUAL_W1_JSONL = "data/evals/manual_w1/w1-haw-micro-eval.jsonl"

# Default local path for the Ulukau human_fetch parallel pair JSONL.
# Regenerate with: python3 scripts/_convert_ulukau_human_fetch.py
# If absent, the probe reports status="missing" and does not fail the eval.
DEFAULT_HUMAN_FETCH_JSONL = (
    "data/tokenizer_audit/ulukau_nupepa/human_fetch.jsonl"
)

# Probe schema label — bump if the report shape or metric formula changes.
HUMAN_FETCH_PROBE_SCHEMA = "human-fetch-translation-probe-v1"

# Translation prompt templates for the human_fetch probe.
# Baked into the probe descriptor hash: changing either template must
# also bump HUMAN_FETCH_PROBE_SCHEMA so cross-checkpoint diffs stay valid.
HUMAN_FETCH_EN_TO_HAW_TEMPLATE = "Translate to Hawaiian:\n{text}"
HUMAN_FETCH_HAW_TO_EN_TEMPLATE = "Translate to English:\n{text}"

# Bumped whenever the report shape changes in a way that would break
# cross-checkpoint summary diffing. Stage 0 drift bundle = v2.
EVAL_SCHEMA_VERSION = "stage0_eval.v2"

# Stable schema label for the W1 manual JSONL input. Each JSONL row also
# carries `schema_version` = "manual-w1-jsonl-v1" written by
# `scripts/315_hash_manual_w1_eval.py:build_eval_jsonl_record`; we
# hardcode the same literal here so `manual_w1.schema_version_seen`
# stays stable on cross-checkpoint diffs.
MANUAL_W1_JSONL_SCHEMA_VERSION = "manual-w1-jsonl-v1"

# Canonical hash material for W1 accepted rows. This MUST match
# `scripts/315_hash_manual_w1_eval.py:hash_material/compute_hash`
# byte-for-byte: NFC-normalize, then sha256 of `prompt + U+000A + reference`.
# We mirror the formula instead of importing because the script's filename
# (leading digit, hyphenated) is not a legal Python module identifier and
# loading it via runpy would re-execute its CLI side effects. The pinning
# is enforced by a unit test (`test_evaluate.py`) and documented in
# `.squad/decisions/inbox/basher-w1-contract-revision.md`.
MANUAL_W1_HASH_MATERIAL_SPEC = "NFC(prompt) + U+000A + NFC(reference)"

# Fixed prompt suite for checkpoint drift monitoring. Spans low/medium/high
# Hawaiian diacritic density per `metrics.diacritic_density_bin`, plus one
# English control to catch English-collapse regressions cheaply.
#
# DO NOT renumber or reword these in place: changing a prompt changes
# `prompt_suite_sha256` and breaks comparability with prior checkpoints.
# Add new prompts at the end and bump `PROMPT_SUITE_ID` instead.
PROMPT_SUITE_ID = "stage0.v1"
DEFAULT_PROMPT_SUITE: list[tuple[str, str]] = [
    (
        "en_control_1",
        "Write one short paragraph in English describing a typical morning.",
    ),
    (
        "haw_low_1",
        "Aloha mai kākou.",
    ),
    (
        "haw_low_2",
        "Aloha kāua i kēia kakahiaka.",
    ),
    (
        "haw_medium_1",
        "He aha ka mōʻaukala o Hawaiʻi?",
    ),
    (
        "haw_medium_2",
        "Pehea ʻoe i kēia lā?",
    ),
    (
        "haw_high_1",
        "E kākau i hoʻokahi paukū pōkole ma ka ʻōlelo Hawaiʻi e pili ana i ka ʻohana, "
        "e hoʻohana ana i nā kahakō a me nā ʻokina a pau.",
    ),
    (
        "haw_high_2",
        "E hōʻike mai i kekahi moʻolelo pōkole ma ka ʻōlelo Hawaiʻi e pili ana i ka "
        "lā mua o ka makahiki, me nā ʻokina a me nā kahakō a pau.",
    ),
]


def _require(pkg: str, install_hint: str) -> Any:
    try:
        return __import__(pkg)
    except ImportError as e:
        raise RuntimeError(
            f"Missing optional dependency '{pkg}'. Install with: {install_hint}"
        ) from e


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _manual_w1_hash_material(prompt: str, reference: str) -> str:
    """NFC-normalized hash material for a W1 row.

    Mirrors `scripts/315_hash_manual_w1_eval.py:hash_material` exactly.
    """
    return unicodedata.normalize("NFC", f"{prompt}\n{reference}")


def _manual_w1_sha256_normalized(prompt: str, reference: str) -> str:
    """Canonical W1 row hash. Mirrors
    `scripts/315_hash_manual_w1_eval.py:compute_hash` byte-for-byte.
    """
    return hashlib.sha256(
        _manual_w1_hash_material(prompt, reference).encode("utf-8")
    ).hexdigest()


def _length_bin_from_tokens(n_tokens: int) -> str:
    if n_tokens <= 128:
        return "short"
    if n_tokens <= 512:
        return "medium"
    return "long"


def compute_prompt_suite_descriptor(
    suite: list[tuple[str, str]] | None = None,
) -> dict:
    """Hash-only descriptor of a fixed prompt suite (no raw prompt text in
    tracked summaries). Used to confirm two checkpoints saw the same prompts.
    """
    items_in = suite if suite is not None else DEFAULT_PROMPT_SUITE
    items: list[dict] = []
    h = hashlib.sha256()
    h.update(PROMPT_SUITE_ID.encode("utf-8"))
    h.update(b"\n")
    for pid, ptext in items_in:
        ptext_nfc = unicodedata.normalize("NFC", ptext)
        psha = _sha256_text(ptext_nfc)
        diacritics = metrics_mod.count_hawaiian_diacritics(ptext_nfc)
        items.append(
            {
                "id": pid,
                "prompt_sha256": psha,
                "prompt_len_chars": len(ptext_nfc),
                "prompt_diacritics": diacritics,
                "diacritic_density_bin": metrics_mod.diacritic_density_bin(
                    diacritics
                ),
            }
        )
        h.update(pid.encode("utf-8"))
        h.update(b"\t")
        h.update(psha.encode("utf-8"))
        h.update(b"\n")
    return {
        "suite_id": PROMPT_SUITE_ID,
        "suite_sha256": h.hexdigest(),
        "items": items,
    }


def _parse_jsonl_bool(value: Any) -> bool | None:
    """Lenient bool coercion for a W1 JSONL field. Accepts native bools
    or the strings 'true'/'false' (case-insensitive). Returns None for
    anything else so the caller can treat it as a contract failure.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v == "true":
            return True
        if v == "false":
            return False
    return None


def manual_w1_status(
    jsonl_path: str | Path | None,
    *,
    enabled: bool = True,
) -> dict:
    """Read-only metadata/validation probe for the W1 hand-authored
    Hawaiian micro-eval JSONL.

    Status semantics (kept stable for cross-checkpoint summary diffs):

    * ``not_configured`` — explicitly disabled via ``enabled=False``.
    * ``missing``        — JSONL not present at the resolved path.
    * ``invalid``        — file present but unreadable / malformed JSON /
                           accepted row fails the orthographic gate.
                           Eval-consumable count is 0.
    * ``draft_only``     — JSONL parsed; zero ``review_status=accepted``
                           rows. Drafts/reviewed rows are NOT eval
                           results.
    * ``evaluated``      — accepted rows present and validated. The
                           ``scoring_status`` sub-field stays
                           ``not_wired`` until the actual W1 model-
                           scoring harness lands; until then this means
                           "metadata/validation evaluated", *not* task
                           accuracy.

    Raw JSONL text (prompts, references, notes, author) is never
    returned. Only counts, a whole-file SHA256, category/density-bin
    counts on accepted rows, a coarse ``nfc_normalized=false`` row
    count, and — on the ``evaluated`` path — sorted canonical row
    hashes plus a stable ``w1_suite_sha256`` over
    ``(item_id, sha256_normalized)`` pairs so cross-checkpoint diffs
    can detect accepted-set churn without shipping raw Hawaiian text
    into git.
    """
    if not enabled:
        return {
            "status": "not_configured",
            "reason": "W1 manual micro-eval check disabled (--no-manual-w1)",
            "scoring_status": "not_wired",
            "schema_version_seen": None,
        }

    p = Path(jsonl_path) if jsonl_path else Path(DEFAULT_MANUAL_W1_JSONL)
    out: dict[str, Any] = {
        "path": str(p),
        "scoring_status": "not_wired",
        "scoring_reason": (
            "W1 row-level model scoring not wired; metadata/validation "
            "only — accepted_count is NOT a task-accuracy benchmark"
        ),
        "schema_version_seen": None,
    }
    if not p.exists():
        out["status"] = "missing"
        out["reason"] = (
            f"W1 JSONL not found at {p}; populate locally per "
            "data-sources/manual-eval/README.md (off-git) by running "
            "`python3 scripts/315_hash_manual_w1_eval.py --execute --jsonl-only`"
        )
        return out

    try:
        raw_bytes = p.read_bytes()
    except OSError as e:
        out["status"] = "invalid"
        out["reason"] = f"read_failed: {e}"
        return out

    out["jsonl_sha256"] = hashlib.sha256(raw_bytes).hexdigest()
    out["jsonl_size_bytes"] = len(raw_bytes)

    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as e:
        out["status"] = "invalid"
        out["reason"] = f"utf8_decode_failed: {e}"
        return out

    rows: list[dict[str, Any]] = []
    parse_errors: list[str] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            parse_errors.append(f"line {line_no}: invalid JSON ({e.msg})")
            continue
        if not isinstance(obj, dict):
            parse_errors.append(f"line {line_no}: expected JSON object")
            continue
        obj["_line_no"] = line_no
        rows.append(obj)

    if parse_errors:
        out["status"] = "invalid"
        out["reason"] = "jsonl_parse_failed"
        out["error_count"] = len(parse_errors)
        out["first_errors"] = parse_errors[:10]
        out["row_count"] = len(rows)
        return out

    review_counts: Counter[str] = Counter()
    accepted_categories: Counter[str] = Counter()
    accepted_density_bins: Counter[str] = Counter()
    nfc_false = 0
    accepted_errors: list[str] = []
    accepted_pairs: list[tuple[str, str]] = []
    for r in rows:
        line_no = int(r.get("_line_no", 0) or 0)
        rs = (r.get("review_status") or "")
        rs = rs.strip() if isinstance(rs, str) else ""
        review_counts[rs] += 1
        nfc_bool = _parse_jsonl_bool(r.get("nfc_normalized"))
        if nfc_bool is not True:
            nfc_false += 1
        if rs != "accepted":
            continue

        # --- accepted-row strict path --------------------------------
        item_id_raw = r.get("item_id") if r.get("item_id") is not None else r.get("id")
        item_id = (item_id_raw or "")
        item_id = item_id.strip() if isinstance(item_id, str) else ""
        prompt = r.get("prompt") or ""
        # Accept either `reference` or `text` as the second hash material;
        # `reference` matches the W1 contract, `text` is the JSONL convenience
        # field (NFC(prompt) + LF + NFC(reference)).
        reference = r.get("reference")
        if reference is None:
            reference = r.get("text") or ""
        if not isinstance(prompt, str):
            prompt = str(prompt)
        if not isinstance(reference, str):
            reference = str(reference)

        cat = r.get("category") or ""
        cat = cat.strip() if isinstance(cat, str) else ""
        cat = cat or "unknown"
        accepted_categories[cat] += 1

        density_val = r.get("diacritic_density")
        density: int | None
        if isinstance(density_val, bool):
            density = None
        elif isinstance(density_val, int):
            density = density_val
        elif isinstance(density_val, str) and density_val.strip():
            try:
                density = int(density_val.strip())
            except ValueError:
                density = None
        else:
            density = None

        bin_field = r.get("diacritic_density_bin")
        if isinstance(bin_field, str) and bin_field.strip() in (
            "none",
            "low",
            "medium",
            "high",
        ):
            accepted_density_bins[bin_field.strip()] += 1
        elif density is not None:
            accepted_density_bins[
                metrics_mod.diacritic_density_bin(density)
            ] += 1
        else:
            # Derive from prompt+reference if neither field is usable.
            derived = metrics_mod.count_hawaiian_diacritics(
                f"{prompt}\n{reference}"
            )
            accepted_density_bins[
                metrics_mod.diacritic_density_bin(derived)
            ] += 1

        # Orthographic gate: an accepted row that fails NFC, carries a
        # combining macron, or uses a wrong-ʻokina codepoint is a
        # contract violation by the human reviewer and must fail loud,
        # not be silently rolled into a count. Drafts/reviewed rows
        # (handled above by the `continue`) stay loose on purpose.
        if nfc_bool is not True:
            accepted_errors.append(
                f"line {line_no}: nfc_normalized field is not true "
                "on accepted row"
            )
        text_field = r.get("text")
        gate_targets: list[tuple[str, str]] = [
            ("prompt", prompt),
            ("reference", reference),
        ]
        if isinstance(text_field, str) and text_field:
            gate_targets.append(("text", text_field))
        for field_name, body in gate_targets:
            if not metrics_mod.is_nfc(body):
                accepted_errors.append(
                    f"line {line_no}: {field_name} is not NFC-normalized"
                )
            if metrics_mod.count_combining_macron(body):
                accepted_errors.append(
                    f"line {line_no}: {field_name} contains combining "
                    "macron U+0304"
                )
            if metrics_mod.count_wrong_okina(body):
                accepted_errors.append(
                    f"line {line_no}: {field_name} contains wrong "
                    "ʻokina/apostrophe codepoint"
                )

        if not item_id:
            accepted_errors.append(
                f"line {line_no}: item_id is empty on accepted row"
            )
        else:
            # Prefer the row's `sha256_normalized` if it's present and
            # well-formed; otherwise compute the canonical NFC(prompt)+LF
            # +NFC(reference) hash so suite-hash stability is independent
            # of whether the producer wrote the field.
            sha = r.get("sha256_normalized")
            if not (
                isinstance(sha, str) and len(sha) == 64 and all(
                    c in "0123456789abcdef" for c in sha
                )
            ):
                sha = _manual_w1_sha256_normalized(prompt, reference)
            accepted_pairs.append((item_id, sha))

    accepted = review_counts.get("accepted", 0)
    out["row_count"] = len(rows)
    out["review_status_counts"] = dict(review_counts)
    out["accepted_count"] = accepted
    out["eval_consumable_count"] = accepted
    out["nfc_normalized_false_count"] = nfc_false
    out["accepted_category_counts"] = dict(accepted_categories)
    out["accepted_diacritic_density_bin_counts"] = dict(accepted_density_bins)

    if accepted_errors:
        out["status"] = "invalid"
        out["reason"] = "accepted_row_orthographic_validation_failed"
        out["error_count"] = len(accepted_errors)
        # line+field only — never the row contents.
        out["first_errors"] = accepted_errors[:10]
        out["eval_consumable_count"] = 0
        out["accepted_item_hashes"] = []
        out["w1_suite_sha256"] = None
        # schema_version_seen stays None on invalid: an invalid file
        # cannot be claimed to conform to the schema label.
        return out

    out["schema_version_seen"] = MANUAL_W1_JSONL_SCHEMA_VERSION

    if accepted > 0:
        pairs_sorted = sorted(accepted_pairs)
        out["accepted_item_hashes"] = sorted(sha for _, sha in pairs_sorted)
        suite_h = hashlib.sha256()
        for item_id, sha in pairs_sorted:
            suite_h.update(item_id.encode("utf-8"))
            suite_h.update(b"\t")
            suite_h.update(sha.encode("utf-8"))
            suite_h.update(b"\n")
        out["w1_suite_sha256"] = suite_h.hexdigest()
        out["status"] = "evaluated"
    else:
        out["accepted_item_hashes"] = []
        out["w1_suite_sha256"] = None
        out["status"] = "draft_only"
        out["reason"] = (
            "no review_status=accepted rows; drafts/reviewed rows are "
            "not reportable as eval results"
        )
    return out


def _char_ngram_f1(reference: str, hypothesis: str, n: int = 2) -> dict:
    """Baseline character n-gram F1 (bigram by default). Pure Python, no deps.

    This is a simple string-overlap drift metric, **not** a production chrF
    implementation.  It is documented here as a *baseline character-F score*:
    precision and recall are computed over NFC-normalized character n-grams
    clipped to reference counts, then combined as F1.

    Directions are always kept separate: en→haw and haw→en are never averaged
    into a single number (see constraint in docs/eval_pipeline.md §3.3 and §5).

    Args:
        reference:  The gold reference string (NFC-normalized before n-gram
                    extraction).
        hypothesis: The model generation (NFC-normalized before n-gram
                    extraction).
        n:          N-gram order (default 2 = character bigrams).

    Returns a dict with keys ``char_f1``, ``char_precision``, ``char_recall``
    (floats, rounded to 6 decimal places), and ``ngram_order``.
    """
    ref_nfc = unicodedata.normalize("NFC", reference)
    hyp_nfc = unicodedata.normalize("NFC", hypothesis)

    def _ngrams(text: str, order: int) -> "Counter[str]":
        return Counter(
            text[i : i + order] for i in range(max(0, len(text) - order + 1))
        )

    ref_counts = _ngrams(ref_nfc, n)
    hyp_counts = _ngrams(hyp_nfc, n)
    ref_total = sum(ref_counts.values())
    hyp_total = sum(hyp_counts.values())

    if ref_total == 0 or hyp_total == 0:
        return {
            "char_f1": 0.0,
            "char_precision": 0.0,
            "char_recall": 0.0,
            "ngram_order": n,
        }

    # Clipped overlap: each n-gram counted at most min(ref_count, hyp_count)
    overlap = sum((ref_counts & hyp_counts).values())
    precision = overlap / hyp_total
    recall = overlap / ref_total
    f1 = (
        2.0 * precision * recall / (precision + recall)
        if (precision + recall) > 0.0
        else 0.0
    )
    return {
        "char_f1": round(f1, 6),
        "char_precision": round(precision, 6),
        "char_recall": round(recall, 6),
        "ngram_order": n,
    }


def human_fetch_translation_probe(
    jsonl_path: str | Path | None,
    *,
    enabled: bool = True,
    model: Any = None,
    tokenizer: Any = None,
    max_new_tokens: int = 64,
) -> dict:
    """Bidirectional translation probe using the Ulukau human_fetch parallel pair.

    This is a **prototype/learning checkpoint eval probe**.  It reads the local
    JSONL at ``jsonl_path`` (default: ``DEFAULT_HUMAN_FETCH_JSONL``), extracts
    the English and Hawaiian text fields, and — when a model/tokenizer are
    provided — runs greedy generation for both en→haw and haw→en directions
    with a simple char-bigram F1 score against the reference.

    Purpose: measure the model's translation behaviour at a zero-training
    Stage 0 baseline and track drift across checkpoints.  The single parallel
    pair from Ulukau is the stable local reference; it is **never** training
    data (``training_eligible = False`` in the JSONL policy field).

    The probe is "safe to miss": if the JSONL is absent it reports
    ``status="missing"`` and does not block the eval.

    Status semantics:
    * ``not_configured`` — explicitly disabled via ``enabled=False``.
    * ``missing``        — JSONL not found at the resolved path.
    * ``invalid``        — file present but unreadable, malformed, or missing
                           the required en/haw lang pair.
    * ``ready``          — pair parsed; no model provided — generation not run.
    * ``evaluated``      — both directions generated and scored.

    **No raw text is returned**: source text, reference text, and generation
    text never enter the returned dict.  Only hashes and numeric metrics.
    """
    if not enabled:
        return {
            "status": "not_configured",
            "reason": "human-fetch translation probe disabled (--no-human-fetch)",
            "schema": HUMAN_FETCH_PROBE_SCHEMA,
        }

    p = Path(jsonl_path) if jsonl_path else Path(DEFAULT_HUMAN_FETCH_JSONL)
    out: dict[str, Any] = {
        "schema": HUMAN_FETCH_PROBE_SCHEMA,
        "path": str(p),
        "eval_eligible": True,
        "training_eligible": False,
        "note": (
            "prototype/learning checkpoint eval probe; single parallel pair "
            "from Ulukau human_fetch (data/tokenizer_audit/ulukau_nupepa/); "
            "measures zero-training Stage 0 baseline and checkpoint drift; "
            "never training data"
        ),
    }

    if not p.exists():
        out["status"] = "missing"
        out["reason"] = (
            f"human_fetch JSONL not found at {p}; regenerate with "
            "`python3 scripts/_convert_ulukau_human_fetch.py` "
            "(requires data/raw/ulukau_nupepa/human_fetch.txt)"
        )
        return out

    try:
        raw_bytes = p.read_bytes()
    except OSError as e:
        out["status"] = "invalid"
        out["reason"] = f"read_failed: {e}"
        return out

    out["source_jsonl_sha256"] = hashlib.sha256(raw_bytes).hexdigest()
    out["source_jsonl_size_bytes"] = len(raw_bytes)

    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as e:
        out["status"] = "invalid"
        out["reason"] = f"utf8_decode_failed: {e}"
        return out

    en_text: str | None = None
    haw_text: str | None = None
    parse_errors: list[str] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            parse_errors.append(f"line {line_no}: {e.msg}")
            continue
        if not isinstance(obj, dict):
            parse_errors.append(f"line {line_no}: expected JSON object")
            continue
        lang = obj.get("lang") or ""
        body = obj.get("text") or ""
        if not isinstance(body, str):
            continue
        body_nfc = unicodedata.normalize("NFC", body)
        if lang == "en" and en_text is None:
            en_text = body_nfc
        elif lang == "haw" and haw_text is None:
            haw_text = body_nfc

    if parse_errors:
        out["status"] = "invalid"
        out["reason"] = "jsonl_parse_failed"
        out["parse_error_count"] = len(parse_errors)
        out["first_parse_errors"] = parse_errors[:5]
        return out

    if en_text is None or haw_text is None:
        out["status"] = "invalid"
        out["reason"] = (
            "missing_lang_pair: expected at least one lang='en' row and one "
            f"lang='haw' row; found en={'yes' if en_text else 'no'}, "
            f"haw={'yes' if haw_text else 'no'}"
        )
        return out

    out["pair_count"] = 1
    # Hash-only reference to the source texts — no raw text in the report.
    out["pair_sha256"] = {
        "en": _sha256_text(en_text),
        "haw": _sha256_text(haw_text),
    }
    # Template hashes let the aggregator detect template drift across checkpoints.
    out["template_sha256"] = {
        "en_to_haw": _sha256_text(HUMAN_FETCH_EN_TO_HAW_TEMPLATE),
        "haw_to_en": _sha256_text(HUMAN_FETCH_HAW_TO_EN_TEMPLATE),
    }

    # Build prompts — raw text never returned to caller.
    en_to_haw_prompt = HUMAN_FETCH_EN_TO_HAW_TEMPLATE.format(text=en_text)
    haw_to_en_prompt = HUMAN_FETCH_HAW_TO_EN_TEMPLATE.format(text=haw_text)

    if model is None or tokenizer is None:
        out["status"] = "ready"
        out["reason"] = "pair parsed; no model provided — generation not run"
        out["directions"] = {
            "en_to_haw": {
                "status": "not_run",
                "prompt_sha256": _sha256_text(en_to_haw_prompt),
                "reference_sha256": _sha256_text(haw_text),
            },
            "haw_to_en": {
                "status": "not_run",
                "prompt_sha256": _sha256_text(haw_to_en_prompt),
                "reference_sha256": _sha256_text(en_text),
            },
        }
        return out

    # Deterministic greedy generation for both directions.
    gens = sample_generations(
        model,
        tokenizer,
        [en_to_haw_prompt, haw_to_en_prompt],
        max_new_tokens=max_new_tokens,
    )
    gen_en_to_haw = unicodedata.normalize("NFC", gens[0])
    gen_haw_to_en = unicodedata.normalize("NFC", gens[1])

    out["directions"] = {
        "en_to_haw": {
            "prompt_sha256": _sha256_text(en_to_haw_prompt),
            "generation_sha256": _sha256_text(gen_en_to_haw),
            "reference_sha256": _sha256_text(haw_text),
            "metric": "char_ngram_f1_baseline",
            **_char_ngram_f1(haw_text, gen_en_to_haw, n=2),
        },
        "haw_to_en": {
            "prompt_sha256": _sha256_text(haw_to_en_prompt),
            "generation_sha256": _sha256_text(gen_haw_to_en),
            "reference_sha256": _sha256_text(en_text),
            "metric": "char_ngram_f1_baseline",
            **_char_ngram_f1(en_text, gen_haw_to_en, n=2),
        },
    }
    out["status"] = "evaluated"
    return out


def load_checkpoint(checkpoint_dir: str):
    """Load a (possibly LoRA-adapter) checkpoint + its tokenizer."""
    transformers = _require("transformers", "pip install transformers")
    peft = _require("peft", "pip install peft")
    torch = _require("torch", "pip install torch")

    tokenizer = transformers.AutoTokenizer.from_pretrained(checkpoint_dir, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model_kwargs = {"dtype": torch.float16}
    if torch.cuda.is_available():
        model_kwargs["device_map"] = "auto"

    # If the checkpoint contains a peft adapter, load it on top of its
    # recorded base model. Otherwise treat it as a plain causal LM.
    adapter_cfg_path = Path(checkpoint_dir) / "adapter_config.json"
    if adapter_cfg_path.exists():
        with adapter_cfg_path.open("r", encoding="utf-8") as f:
            adapter_cfg = json.load(f)
        base_id = adapter_cfg["base_model_name_or_path"]
        base = transformers.AutoModelForCausalLM.from_pretrained(base_id, **model_kwargs)
        model = peft.PeftModel.from_pretrained(base, checkpoint_dir)
    else:
        model = transformers.AutoModelForCausalLM.from_pretrained(
            checkpoint_dir, **model_kwargs
        )
    model.eval()
    return model, tokenizer


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_eval_set_metadata(
    tokenizer,
    eval_file: str,
    max_length: int = 1024,
) -> dict:
    """Tokenize-once pass over the eval JSONL to capture slice metadata
    for drift comparison: counts, token counts, length bins, diacritic
    density bins, and any source/register fields present on records.

    Raw record text is NOT returned; only counts and bins.
    """
    from .data import iter_jsonl, normalize_text

    record_count = 0
    scored_record_count = 0
    total_tokens = 0
    length_bin_counts: dict[str, int] = {"short": 0, "medium": 0, "long": 0}
    density_bin_counts: dict[str, int] = {
        "none": 0,
        "low": 0,
        "medium": 0,
        "high": 0,
    }
    source_counts: dict[str, int] = {}
    register_counts: dict[str, int] = {}
    total_chars = 0

    for ex in iter_jsonl(eval_file):
        record_count += 1
        text = normalize_text(ex.get("text", ""), form="NFC")
        if not text:
            continue
        scored_record_count += 1
        ids = tokenizer(text, truncation=True, max_length=max_length)["input_ids"]
        n_tokens = len(ids)
        total_tokens += n_tokens
        total_chars += len(text)
        length_bin_counts[_length_bin_from_tokens(n_tokens)] += 1
        bin_name = metrics_mod.diacritic_density_bin(
            metrics_mod.count_hawaiian_diacritics(text)
        )
        density_bin_counts[bin_name] = density_bin_counts.get(bin_name, 0) + 1
        src = ex.get("source")
        if src is not None:
            source_counts[str(src)] = source_counts.get(str(src), 0) + 1
        reg = ex.get("register")
        if reg is not None:
            register_counts[str(reg)] = register_counts.get(str(reg), 0) + 1

    meta: dict[str, Any] = {
        "path": str(eval_file),
        "sha256": _sha256_file(Path(eval_file)),
        "record_count": record_count,
        "scored_record_count": scored_record_count,
        "total_tokens": total_tokens,
        "total_chars": total_chars,
        "length_bin_counts_tokens": length_bin_counts,
        "diacritic_density_bin_counts": density_bin_counts,
        "max_length_used": max_length,
    }
    if source_counts:
        meta["source_counts"] = source_counts
    else:
        meta["source_counts"] = {"status": "field_absent"}
    if register_counts:
        meta["register_counts"] = register_counts
    else:
        meta["register_counts"] = {"status": "field_absent"}
    return meta


def perplexity(model, tokenizer, eval_file: str, max_length: int = 1024) -> float:
    """Token-weighted perplexity on a Hawaiian held-out JSONL.

    TODO(slicing): The eval pipeline doc requires per-source/register
    slicing (docs/eval_pipeline.md §5). Start with the global number,
    then add slices once the JSONL records carry a `source` field.
    """
    torch = _require("torch", "pip install torch")
    from .data import iter_jsonl, normalize_text

    total_loss = 0.0
    total_tokens = 0
    device = next(model.parameters()).device

    with torch.no_grad():
        for idx, ex in enumerate(iter_jsonl(eval_file), start=1):
            text = normalize_text(ex.get("text", ""), form="NFC")
            if not text:
                continue
            enc = tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=max_length,
            )
            input_ids = enc["input_ids"].to(device)
            labels = input_ids.clone()
            out = model(input_ids=input_ids, labels=labels)
            n_tokens = int(input_ids.numel())
            total_loss += float(out.loss) * n_tokens
            total_tokens += n_tokens
            if idx == 1 or idx % 25 == 0:
                print(
                    f"[eval] scored {idx} records ({total_tokens} tokens)",
                    file=sys.stderr,
                    flush=True,
                )

    if total_tokens == 0:
        raise ValueError(f"No eval tokens scored from {eval_file}")
    return math.exp(total_loss / total_tokens)


def sample_generations(
    model,
    tokenizer,
    prompts: list[str],
    max_new_tokens: int = 64,
) -> list[str]:
    """Greedy generations for a small list of prompts."""
    torch = _require("torch", "pip install torch")
    device = next(model.parameters()).device
    outputs: list[str] = []
    with torch.no_grad():
        for p in prompts:
            enc = tokenizer(p, return_tensors="pt").to(device)
            gen = model.generate(
                **enc,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id,
            )
            outputs.append(tokenizer.decode(gen[0], skip_special_tokens=True))
    return outputs


def _model_identity(model, tokenizer, checkpoint_dir: str) -> dict:
    """Best-effort identity capture for fair cross-checkpoint comparison.

    Pulls dtype, device, device_map, quantization-ish config, tokenizer
    name/class/vocab size, model class, and library versions. Failures
    inside this helper must never break eval — fall back to "unknown".
    """
    info: dict[str, Any] = {"checkpoint": checkpoint_dir}
    try:
        torch = __import__("torch")
        info["torch_version"] = getattr(torch, "__version__", "unknown")
        info["cuda_available"] = bool(torch.cuda.is_available())
    except Exception:
        info["torch_version"] = "unknown"
        info["cuda_available"] = False
    try:
        transformers = __import__("transformers")
        info["transformers_version"] = getattr(
            transformers, "__version__", "unknown"
        )
    except Exception:
        info["transformers_version"] = "unknown"

    try:
        info["model_class"] = type(model).__name__
    except Exception:
        info["model_class"] = "unknown"
    try:
        first_param = next(model.parameters())
        info["model_dtype"] = str(first_param.dtype)
        info["model_device"] = str(first_param.device)
    except Exception:
        info["model_dtype"] = "unknown"
        info["model_device"] = "unknown"

    # peft adapter detection
    adapter_cfg_path = Path(checkpoint_dir) / "adapter_config.json"
    if adapter_cfg_path.exists():
        info["is_adapter"] = True
        try:
            with adapter_cfg_path.open("r", encoding="utf-8") as f:
                ad = json.load(f)
            info["base_model"] = ad.get("base_model_name_or_path")
        except Exception:
            info["base_model"] = "unknown"
    else:
        info["is_adapter"] = False
        info["base_model"] = checkpoint_dir

    # device_map (if peft/transformers exposed it)
    base = getattr(model, "base_model", None)
    target = base if base is not None else model
    info["device_map"] = str(getattr(target, "hf_device_map", "single_device"))

    # quantization-ish config
    qc = None
    try:
        cfg = getattr(target, "config", None)
        qc_raw = getattr(cfg, "quantization_config", None)
        if qc_raw is not None:
            qc = (
                qc_raw.to_dict()
                if hasattr(qc_raw, "to_dict")
                else dict(getattr(qc_raw, "__dict__", {}))
            )
    except Exception:
        qc = None
    info["quantization_config"] = qc if qc is not None else {"status": "absent"}

    # tokenizer identity
    try:
        info["tokenizer_class"] = type(tokenizer).__name__
        info["tokenizer_name_or_path"] = getattr(
            tokenizer, "name_or_path", "unknown"
        )
        info["tokenizer_vocab_size"] = int(getattr(tokenizer, "vocab_size", 0))
    except Exception:
        info["tokenizer_class"] = "unknown"
        info["tokenizer_name_or_path"] = "unknown"
        info["tokenizer_vocab_size"] = 0

    return info


def _orthography_aggregate(
    orth_per_sample: dict[str, dict],
    suite_descriptor: dict | None,
) -> dict:
    """Aggregate orthography signals + tripwires across the prompt suite.

    No raw text consumed here — only the per-sample dicts produced by
    `metrics.orthography_report` plus the suite descriptor (for
    high-density prompt detection).
    """
    n = len(orth_per_sample)
    okina_total = 0
    wrong_okina_total = 0
    kahako_total = 0
    combining_macron_total = 0
    nfc_failures = 0
    bin_counts: dict[str, int] = {}
    for r in orth_per_sample.values():
        okina_total += int(r.get("okina", 0))
        wrong_okina_total += int(r.get("wrong_okina", 0))
        kahako_total += int(r.get("kahako", 0))
        combining_macron_total += int(r.get("combining_macron", 0))
        if not r.get("is_nfc", True):
            nfc_failures += 1
        b = r.get("diacritic_density_bin", "none")
        bin_counts[b] = bin_counts.get(b, 0) + 1

    # Kahakō collapse on high-diacritic prompts: prompt was high-density,
    # generation contains zero kahakō. Indexed by suite item position.
    kahako_collapse_high_density = 0
    if suite_descriptor is not None:
        items = suite_descriptor.get("items", [])
        for i, item in enumerate(items):
            if item.get("diacritic_density_bin") != "high":
                continue
            key = f"sample_{i}"
            r = orth_per_sample.get(key)
            if r is None:
                continue
            if int(r.get("kahako", 0)) == 0:
                kahako_collapse_high_density += 1

    return {
        "n": n,
        "okina_total": okina_total,
        "wrong_okina_total": wrong_okina_total,
        "kahako_total": kahako_total,
        "combining_macron_total": combining_macron_total,
        "nfc_failures": nfc_failures,
        "diacritic_density_bin_counts": bin_counts,
        "kahako_collapse_on_high_diacritic": kahako_collapse_high_density,
    }


def _tripwires(
    orth_aggregate: dict,
    suite_descriptor: dict,
    generation_count: int,
) -> dict:
    return {
        "wrong_okina_nonzero": orth_aggregate.get("wrong_okina_total", 0) > 0,
        "nfc_failures": orth_aggregate.get("nfc_failures", 0),
        "combining_macron_nonzero": orth_aggregate.get("combining_macron_total", 0)
        > 0,
        "kahako_collapse_on_high_diacritic": orth_aggregate.get(
            "kahako_collapse_on_high_diacritic", 0
        ),
        "generation_count": generation_count,
        "prompt_suite_sha256": suite_descriptor.get("suite_sha256"),
        "prompt_suite_id": suite_descriptor.get("suite_id"),
    }


def evaluate_checkpoint(
    checkpoint_dir: str,
    eval_file: str | None,
    prompts: list[str] | None = None,
    *,
    use_prompt_suite: bool = True,
    max_length: int = 1024,
    max_new_tokens: int = 64,
    manual_w1_jsonl: str | None = None,
    use_manual_w1: bool = True,
    human_fetch_jsonl: str | None = None,
    use_human_fetch: bool = True,
) -> dict:
    """Run PPL + generation + Hawaiian text checks. Returns a dict.

    The shape is intentionally compatible with (a subset of) the
    run-report schema in docs/eval_pipeline.md §8 *plus* the Stage 0
    drift bundle (eval-set slice metadata, prompt-suite descriptor,
    orthography aggregate, tripwires).

    ``human_fetch_translation`` is included on every call so the
    cross-checkpoint aggregator always has the same key structure.
    """
    model, tokenizer = load_checkpoint(checkpoint_dir)
    report: dict = {
        "schema_version": EVAL_SCHEMA_VERSION,
        "checkpoint": checkpoint_dir,
    }
    report["identity"] = _model_identity(model, tokenizer, checkpoint_dir)
    report["decoding"] = {
        "do_sample": False,
        "max_new_tokens": max_new_tokens,
        "temperature": None,
        "top_p": None,
        "greedy": True,
    }
    report["ppl_config"] = {"max_length": max_length}

    # Probes that need their own harness — surface them as explicit
    # placeholders so summaries don't silently lose the field.
    report["english_ppl"] = {
        "status": "not_configured",
        "reason": "english held-out PPL harness not wired (eval_pipeline.md §3.2)",
    }
    report["manual_w1"] = manual_w1_status(
        manual_w1_jsonl, enabled=use_manual_w1
    )
    # Bidirectional translation probe on the human_fetch parallel pair.
    # Runs on every checkpoint (including Stage 0 no-training baseline) so
    # en→haw and haw→en drift is visible from the very first eval.
    report["human_fetch_translation"] = human_fetch_translation_probe(
        human_fetch_jsonl,
        enabled=use_human_fetch,
        model=model,
        tokenizer=tokenizer,
        max_new_tokens=max_new_tokens,
    )

    if eval_file:
        try:
            report["eval_set"] = collect_eval_set_metadata(
                tokenizer, eval_file, max_length=max_length
            )
        except Exception as e:  # pragma: no cover - defensive
            report["eval_set"] = {
                "path": str(eval_file),
                "status": "metadata_failed",
                "error": str(e),
            }
        report["hawaiian_ppl"] = perplexity(
            model, tokenizer, eval_file, max_length=max_length
        )
        # Per-source slice PPL is still TODO (see perplexity()); record an
        # explicit placeholder so downstream summary diff doesn't break.
        report["hawaiian_ppl_by_source"] = {
            "status": "not_configured",
            "reason": "per-source slicing TODO (evaluate.py:perplexity)",
        }
    else:
        # Keep `hawaiian_ppl` shape consistent with the other probes: emit
        # an explicit status object instead of a bare null/absent value, so
        # summary diffs don't silently swallow a missing eval file.
        report["hawaiian_ppl"] = {
            "status": "not_configured",
            "reason": "no --eval-file provided; held-out PPL not run",
        }

    # Prompt assembly: prefer explicit --prompt(s); otherwise use the
    # built-in suite if enabled. Backwards compatible: if --prompt is
    # given, behavior matches the legacy CLI exactly.
    suite_used: list[tuple[str, str]] | None = None
    if prompts:
        prompts_to_run = list(prompts)
        prompt_ids = [f"user_{i}" for i in range(len(prompts_to_run))]
    elif use_prompt_suite:
        suite_used = list(DEFAULT_PROMPT_SUITE)
        prompt_ids = [pid for pid, _ in suite_used]
        prompts_to_run = [ptext for _, ptext in suite_used]
    else:
        prompts_to_run = []
        prompt_ids = []

    if prompts_to_run:
        # Always record a hash-only descriptor of *what was asked*, even
        # for ad-hoc --prompt invocations, so checkpoints can be compared
        # without leaking raw prompt text to tracked summaries.
        descriptor_input = (
            suite_used
            if suite_used is not None
            else list(zip(prompt_ids, prompts_to_run))
        )
        suite_descriptor = compute_prompt_suite_descriptor(descriptor_input)
        report["prompt_suite"] = suite_descriptor

        gens = sample_generations(
            model, tokenizer, prompts_to_run, max_new_tokens=max_new_tokens
        )
        report["generations"] = gens
        report["generation_sha256"] = {
            f"sample_{i}": _sha256_text(g) for i, g in enumerate(gens)
        }
        # Pure-Python checks — no ML deps needed.
        orth = {
            f"sample_{i}": metrics_mod.orthography_report(g)
            for i, g in enumerate(gens)
        }
        report["orthography_metrics"] = orth
        report["orthography_aggregate"] = _orthography_aggregate(
            orth, suite_descriptor
        )
        report["tripwires"] = _tripwires(
            report["orthography_aggregate"],
            suite_descriptor,
            generation_count=len(gens),
        )
    return report


# ---------------- TODOs for the learner ----------------
#
# TODO(stage2-chrf): For Stage 2 translation eval, add chrF/chrF++ by
#   direction (en→haw and haw→en, never averaged). Use sacrebleu.
#   IMPLEMENTED in `code/llm_hawaii/stage2_eval.py` (issue #23). The CLI
#   front-end is `scripts/410_stage2_eval.py`. sacrebleu is preferred
#   when available; a deterministic pure-Python fallback ships with the
#   module so prototype tests run without compute deps.
#
# TODO(leakage-check): Recompute the SHA-256 of every eval reference in
#   NFC and assert none appear in the training shards. See
#   docs/eval_pipeline.md §3.4.
#
# TODO(run-report): Promote this dict to the full run-report schema and
#   write it next to the checkpoint as `run_report.json`.


def _cli_exit_code(report: dict) -> int:
    """Translate a Stage 0 eval report into a process exit code.

    Linus posture (`.squad/decisions/inbox/linus-w1-revision.md`):
    a W1 manual micro-eval that resolves to ``status="invalid"`` (header
    mismatch, NFC/ʻokina/combining-macron failures on accepted rows, etc.)
    must surface as a non-zero exit even after the report JSON has been
    written. Otherwise an orthographically broken accepted row could
    silently land as a "successful" Stage 0 run in CI / cron.

    The report JSON is always emitted first (so the failing artifact is
    inspectable). The shell wrapper (`scripts/run_stage0_eval.sh`) is
    responsible for still writing the tracked summary projection before
    propagating this exit code.
    """
    w1 = report.get("manual_w1") or {}
    if isinstance(w1, dict) and w1.get("status") == "invalid":
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hawaiian LLM eval (skeleton).")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--eval-file", default=None, help="JSONL with a 'text' field.")
    parser.add_argument(
        "--prompt",
        action="append",
        default=None,
        help="Prompt(s) to generate from. Repeatable. Disables built-in suite.",
    )
    parser.add_argument(
        "--no-prompt-suite",
        action="store_true",
        help="Skip the built-in fixed prompt suite when no --prompt is given.",
    )
    parser.add_argument(
        "--max-length",
        type=int,
        default=1024,
        help="Max tokens for held-out PPL scoring.",
    )
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=64,
        help="Max new tokens for generation.",
    )
    parser.add_argument(
        "--manual-w1-jsonl",
        default=None,
        help=(
            "Path to local W1 manual micro-eval JSONL. Defaults to "
            f"{DEFAULT_MANUAL_W1_JSONL} (off-git). Status reported in "
            "report['manual_w1']."
        ),
    )
    parser.add_argument(
        "--no-manual-w1",
        action="store_true",
        help=(
            "Disable the W1 manual micro-eval status probe; emits "
            "status=not_configured."
        ),
    )
    parser.add_argument(
        "--human-fetch-jsonl",
        default=None,
        help=(
            "Path to the human_fetch parallel pair JSONL used for the "
            "bidirectional translation probe. "
            f"Defaults to {DEFAULT_HUMAN_FETCH_JSONL} (off-git). "
            "Regenerate with `python3 scripts/_convert_ulukau_human_fetch.py`. "
            "Override with env var HUMAN_FETCH_JSONL=... in the shell wrapper."
        ),
    )
    parser.add_argument(
        "--no-human-fetch",
        action="store_true",
        help=(
            "Disable the human_fetch bidirectional translation probe; emits "
            "status=not_configured in report['human_fetch_translation']."
        ),
    )
    ns = parser.parse_args(argv)

    report = evaluate_checkpoint(
        ns.checkpoint,
        eval_file=ns.eval_file,
        prompts=ns.prompt,
        use_prompt_suite=not ns.no_prompt_suite,
        max_length=ns.max_length,
        max_new_tokens=ns.max_new_tokens,
        manual_w1_jsonl=ns.manual_w1_jsonl,
        use_manual_w1=not ns.no_manual_w1,
        human_fetch_jsonl=ns.human_fetch_jsonl,
        use_human_fetch=not ns.no_human_fetch,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return _cli_exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main())
