"""Stage 2 eval gate: chrF / chrF++ (both directions, never averaged), eval
leakage check, and Hawaiian orthography retention probe.

Prototype-tier scope. Per `docs/eval_pipeline.md` §3.3 / §5 and issue #23,
this module surfaces:

- ``chrF`` and ``chrF++`` for ``en→haw`` and ``haw→en``, **reported separately**.
- A leakage / contamination verdict against the canonical eval-hash ledger
  (`data/evals/eval_hashes.jsonl`) and against `data/stage2/stage2_manifest.jsonl`.
- A Hawaiian orthography retention delta (ʻokina survival, kahakō retention,
  NFC drift, wrong-ʻokina rate) computed pre vs post on the Hawaiian side.

Heavy ML deps are not required to *score* — this module operates on
pre-generated `(reference, hypothesis)` pairs. A separate caller (the CLI in
`scripts/410_stage2_eval.py` or a notebook) is responsible for producing
generations from a checkpoint; tests pass predictions in directly via fixtures
so the gate is exercisable on a laptop with nothing installed.

Design notes
------------
chrF / chrF++ implementation: sacrebleu is the canonical reference, but it is
not currently a project dependency (see `requirements-compute.txt`). We
therefore ship a small deterministic pure-Python implementation that mirrors
sacrebleu's corpus-level chrF formula:

- Character n-grams of order 1..6 (chrF default).
- chrF++ adds word n-grams of order 1..2 to the same averaging pool.
- F-beta with beta=2 (recall-favoring), per chrF / chrF++ standard.
- Counts aggregated across the corpus, then a single P/R/F per order.
- Orders with zero reference n-grams across the corpus are dropped
  (sacrebleu's "effective order" behavior).
- Final score is the arithmetic mean of per-order F values, scaled to 0..100.

If `sacrebleu` is importable in the runtime environment, we prefer it and
record the implementation backend in the report so the score is attributable.
The pure-Python path matches sacrebleu within rounding on small fixtures and
is documented as a *prototype* implementation; production / release-tier eval
should pin a sacrebleu version.

Direction separation is structural in this module: every public function that
returns a chrF number takes a `direction` label (``"en_to_haw"`` or
``"haw_to_en"``) and the report keys are siblings. There is no path that
averages across directions.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

from . import metrics as metrics_mod

STAGE2_EVAL_SCHEMA = "stage2_eval.v1"
CHRF_CHAR_ORDER = 6
CHRF_WORD_ORDER = 2  # chrF++ word n-gram cap
CHRF_BETA = 2.0

DIRECTIONS = ("en_to_haw", "haw_to_en")


# ---------------------------------------------------------------------------
# chrF / chrF++
# ---------------------------------------------------------------------------


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def _char_ngrams(text: str, n: int) -> Counter:
    if len(text) < n:
        return Counter()
    return Counter(text[i : i + n] for i in range(len(text) - n + 1))


def _word_ngrams(text: str, n: int) -> Counter:
    # sacrebleu uses whitespace tokenization for chrF++ word n-grams.
    words = text.split()
    if len(words) < n:
        return Counter()
    return Counter(
        " ".join(words[i : i + n]) for i in range(len(words) - n + 1)
    )


def _f_beta(precision: float, recall: float, beta: float) -> float:
    denom = (beta * beta) * precision + recall
    if denom <= 0.0:
        return 0.0
    return (1.0 + beta * beta) * precision * recall / denom


def _per_order_pr_counts(
    refs: Sequence[str],
    hyps: Sequence[str],
    order: int,
    *,
    ngram_fn,
) -> tuple[int, int, int]:
    """Aggregate clipped overlap, hyp total, ref total across a corpus."""
    overlap = 0
    hyp_total = 0
    ref_total = 0
    for ref, hyp in zip(refs, hyps):
        ref_ng = ngram_fn(_nfc(ref), order)
        hyp_ng = ngram_fn(_nfc(hyp), order)
        overlap += sum((ref_ng & hyp_ng).values())
        ref_total += sum(ref_ng.values())
        hyp_total += sum(hyp_ng.values())
    return overlap, hyp_total, ref_total


def _chrf_pure_python(
    refs: Sequence[str],
    hyps: Sequence[str],
    *,
    char_order: int,
    word_order: int,
    beta: float,
) -> dict:
    """Corpus-level chrF / chrF++ in pure Python.

    Mirrors sacrebleu's averaging: arithmetic mean of per-order F-beta scores
    over all included char and word orders, scaled to 0..100. Orders where the
    corpus has zero reference n-grams are dropped (effective order).
    """
    if len(refs) != len(hyps):
        raise ValueError(
            f"chrF: refs/hyps length mismatch ({len(refs)} vs {len(hyps)})"
        )
    f_values: list[float] = []
    per_order: list[dict] = []

    for n in range(1, char_order + 1):
        overlap, hyp_total, ref_total = _per_order_pr_counts(
            refs, hyps, n, ngram_fn=_char_ngrams
        )
        if ref_total == 0:
            continue
        precision = overlap / hyp_total if hyp_total > 0 else 0.0
        recall = overlap / ref_total
        f = _f_beta(precision, recall, beta)
        f_values.append(f)
        per_order.append(
            {
                "kind": "char",
                "order": n,
                "precision": round(precision, 6),
                "recall": round(recall, 6),
                "f": round(f, 6),
            }
        )

    for n in range(1, word_order + 1):
        overlap, hyp_total, ref_total = _per_order_pr_counts(
            refs, hyps, n, ngram_fn=_word_ngrams
        )
        if ref_total == 0:
            continue
        precision = overlap / hyp_total if hyp_total > 0 else 0.0
        recall = overlap / ref_total
        f = _f_beta(precision, recall, beta)
        f_values.append(f)
        per_order.append(
            {
                "kind": "word",
                "order": n,
                "precision": round(precision, 6),
                "recall": round(recall, 6),
                "f": round(f, 6),
            }
        )

    score = 100.0 * (sum(f_values) / len(f_values)) if f_values else 0.0
    return {
        "score": round(score, 4),
        "char_order": char_order,
        "word_order": word_order,
        "beta": beta,
        "n_pairs": len(refs),
        "per_order": per_order,
        "backend": "pure_python_v1",
    }


def _chrf_sacrebleu(
    refs: Sequence[str],
    hyps: Sequence[str],
    *,
    char_order: int,
    word_order: int,
    beta: float,
) -> dict | None:
    """Use sacrebleu if available. Returns None if import fails."""
    try:
        import sacrebleu  # type: ignore
    except ImportError:
        return None
    refs_nfc = [_nfc(r) for r in refs]
    hyps_nfc = [_nfc(h) for h in hyps]
    result = sacrebleu.corpus_chrf(
        hyps_nfc,
        [refs_nfc],
        char_order=char_order,
        word_order=word_order,
        beta=beta,
    )
    return {
        "score": round(float(result.score), 4),
        "char_order": char_order,
        "word_order": word_order,
        "beta": beta,
        "n_pairs": len(refs),
        "per_order": [],
        "backend": f"sacrebleu_{getattr(sacrebleu, '__version__', 'unknown')}",
    }


def chrf_corpus(
    refs: Sequence[str],
    hyps: Sequence[str],
    *,
    word_order: int = 0,
    char_order: int = CHRF_CHAR_ORDER,
    beta: float = CHRF_BETA,
    prefer_sacrebleu: bool = True,
) -> dict:
    """Corpus-level chrF (word_order=0) or chrF++ (word_order=2).

    Always returns a dict; never averages across directions (the caller is
    responsible for keeping en→haw and haw→en in separate report keys).
    """
    if prefer_sacrebleu:
        sb = _chrf_sacrebleu(
            refs, hyps, char_order=char_order, word_order=word_order, beta=beta
        )
        if sb is not None:
            return sb
    return _chrf_pure_python(
        refs, hyps, char_order=char_order, word_order=word_order, beta=beta
    )


def chrf_both_directions(
    pairs: Sequence["TranslationPair"],
    *,
    prefer_sacrebleu: bool = True,
) -> dict:
    """Compute chrF and chrF++ for both directions, separately.

    Returns a dict with keys ``en_to_haw`` and ``haw_to_en``, each mapping to
    ``{"chrf": {...}, "chrf_plus_plus": {...}, "n_pairs": int}``.
    """
    out: dict = {}
    for direction in DIRECTIONS:
        dir_pairs = [p for p in pairs if p.direction == direction]
        refs = [p.reference for p in dir_pairs]
        hyps = [p.hypothesis for p in dir_pairs]
        out[direction] = {
            "n_pairs": len(dir_pairs),
            "chrf": chrf_corpus(
                refs, hyps, word_order=0, prefer_sacrebleu=prefer_sacrebleu
            ),
            "chrf_plus_plus": chrf_corpus(
                refs,
                hyps,
                word_order=CHRF_WORD_ORDER,
                prefer_sacrebleu=prefer_sacrebleu,
            ),
        }
    return out


# ---------------------------------------------------------------------------
# Translation pair container
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TranslationPair:
    """One eval pair with a model hypothesis attached.

    `direction` is the *generation* direction:
    - ``"en_to_haw"``: source is English, reference and hypothesis are Hawaiian.
    - ``"haw_to_en"``: source is Hawaiian, reference and hypothesis are English.
    """

    pair_id: str
    direction: str
    source: str
    reference: str
    hypothesis: str

    def __post_init__(self) -> None:
        if self.direction not in DIRECTIONS:
            raise ValueError(
                f"direction must be one of {DIRECTIONS}, got {self.direction!r}"
            )


def load_translation_pairs(
    eval_jsonl: Path | str,
    predictions_jsonl: Path | str,
) -> list[TranslationPair]:
    """Load eval pairs + predictions and zip them by ``pair_id``.

    Eval JSONL row schema (minimum):
        ``{"pair_id": str, "direction": "en_to_haw"|"haw_to_en",
           "source": str, "reference": str}``

    Predictions JSONL row schema (minimum):
        ``{"pair_id": str, "hypothesis": str}``

    Predictions without a matching eval row, or eval rows without a matching
    prediction, raise ``ValueError`` — silent dropouts hide direction collapse.
    """
    eval_rows = {}
    for line in Path(eval_jsonl).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        for key in ("pair_id", "direction", "source", "reference"):
            if key not in row:
                raise ValueError(
                    f"eval row missing required key {key!r}: {row}"
                )
        if row["pair_id"] in eval_rows:
            raise ValueError(f"duplicate pair_id in eval set: {row['pair_id']!r}")
        eval_rows[row["pair_id"]] = row

    pred_rows: dict[str, str] = {}
    for line in Path(predictions_jsonl).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if "pair_id" not in row or "hypothesis" not in row:
            raise ValueError(
                f"prediction row missing pair_id/hypothesis: {row}"
            )
        if row["pair_id"] in pred_rows:
            raise ValueError(
                f"duplicate pair_id in predictions: {row['pair_id']!r}"
            )
        pred_rows[row["pair_id"]] = row["hypothesis"]

    missing_preds = sorted(set(eval_rows) - set(pred_rows))
    extra_preds = sorted(set(pred_rows) - set(eval_rows))
    if missing_preds:
        raise ValueError(
            f"{len(missing_preds)} eval pair(s) have no prediction: "
            f"{missing_preds[:5]}{'...' if len(missing_preds) > 5 else ''}"
        )
    if extra_preds:
        raise ValueError(
            f"{len(extra_preds)} prediction(s) have no matching eval pair: "
            f"{extra_preds[:5]}{'...' if len(extra_preds) > 5 else ''}"
        )

    pairs = []
    for pid, row in eval_rows.items():
        pairs.append(
            TranslationPair(
                pair_id=pid,
                direction=row["direction"],
                source=row["source"],
                reference=row["reference"],
                hypothesis=pred_rows[pid],
            )
        )
    return pairs


# ---------------------------------------------------------------------------
# Leakage / contamination check
# ---------------------------------------------------------------------------


def _sha256_nfc(text: str) -> str:
    return hashlib.sha256(_nfc(text).encode("utf-8")).hexdigest()


def _read_jsonl_field(path: Path, field_name: str) -> set[str]:
    """Collect a string field from every row of a JSONL file. Missing file
    returns an empty set — leakage check then has nothing to compare against
    and is reported as such by the caller."""
    if not path.exists():
        return set()
    out: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        val = row.get(field_name)
        if isinstance(val, str) and val:
            out.add(val)
    return out


def leakage_check(
    pairs: Sequence[TranslationPair],
    *,
    eval_hashes_path: Path | str | None,
    stage2_manifest_path: Path | str | None,
) -> dict:
    """Verify Stage 2 eval pairs are not contaminated.

    Two checks, both build-time:

    1. Each eval reference (NFC-hashed) MUST be present in
       ``data/evals/eval_hashes.jsonl``: this confirms the eval set is
       registered in the canonical ledger that the train deduper consumes.
       Missing references mean the deduper never excluded them from train —
       that's a contamination risk and the check fails closed.
    2. Each eval reference hash MUST NOT appear among
       ``stage2_manifest.jsonl`` row hashes (``sha256_pair`` or per-side
       hashes when present): a row in the manifest with the same hash means
       the eval pair is also a training candidate.

    Returns a structured verdict; the caller decides how to surface it.
    Both ledger paths may be ``None`` — in that case the corresponding check
    is reported as ``"skipped"`` rather than ``"pass"`` so cron summaries can
    distinguish "we checked and it was clean" from "we never checked".
    """
    pair_hashes = {p.pair_id: _sha256_nfc(p.reference) for p in pairs}

    # Check 1: eval ledger membership
    if eval_hashes_path is None:
        ledger_status = "skipped"
        ledger_missing: list[str] = []
        ledger_size = 0
    else:
        path = Path(eval_hashes_path)
        ledger_hashes = _read_jsonl_field(path, "sha256_normalized")
        ledger_size = len(ledger_hashes)
        if not path.exists():
            ledger_status = "missing"
            ledger_missing = sorted(pair_hashes)
        else:
            unregistered = sorted(
                pid for pid, h in pair_hashes.items() if h not in ledger_hashes
            )
            ledger_missing = unregistered
            ledger_status = "pass" if not unregistered else "fail"

    # Check 2: manifest collision
    if stage2_manifest_path is None:
        manifest_status = "skipped"
        manifest_collisions: list[str] = []
        manifest_size = 0
    else:
        path = Path(stage2_manifest_path)
        manifest_hashes: set[str] = set()
        for f in (
            "sha256_pair",
            "sha256_normalized_haw",
            "sha256_normalized_en",
            "sha256_normalized",
        ):
            manifest_hashes |= _read_jsonl_field(path, f)
        manifest_size = len(manifest_hashes)
        if not path.exists():
            manifest_status = "missing"
            manifest_collisions = []
        else:
            collisions = sorted(
                pid for pid, h in pair_hashes.items() if h in manifest_hashes
            )
            manifest_collisions = collisions
            manifest_status = "pass" if not collisions else "fail"

    overall = "pass"
    if "fail" in (ledger_status, manifest_status):
        overall = "fail"
    elif ledger_status == "missing" or manifest_status == "missing":
        overall = "fail"
    elif "skipped" in (ledger_status, manifest_status):
        overall = "skipped"

    return {
        "verdict": overall,
        "n_eval_pairs": len(pairs),
        "ledger": {
            "status": ledger_status,
            "ledger_size": ledger_size,
            "unregistered_pair_ids": ledger_missing[:50],
            "unregistered_count": len(ledger_missing),
        },
        "manifest": {
            "status": manifest_status,
            "manifest_hash_count": manifest_size,
            "colliding_pair_ids": manifest_collisions[:50],
            "colliding_count": len(manifest_collisions),
        },
    }


# ---------------------------------------------------------------------------
# Hawaiian orthography retention
# ---------------------------------------------------------------------------


def _orthography_aggregate_for_strings(texts: Iterable[str]) -> dict:
    okina = 0
    wrong_okina = 0
    kahako = 0
    combining_macron = 0
    nfc_ok = 0
    n = 0
    char_count = 0
    for t in texts:
        n += 1
        char_count += len(t)
        if metrics_mod.is_nfc(t):
            nfc_ok += 1
        okina += metrics_mod.count_okina(t)
        wrong_okina += metrics_mod.count_wrong_okina(t)
        kahako += metrics_mod.count_kahako(t)
        combining_macron += metrics_mod.count_combining_macron(t)
    return {
        "n": n,
        "char_count": char_count,
        "okina": okina,
        "wrong_okina": wrong_okina,
        "kahako": kahako,
        "combining_macron": combining_macron,
        "nfc_pass_rate": round(nfc_ok / n, 6) if n > 0 else None,
    }


def orthography_retention(pairs: Sequence[TranslationPair]) -> dict:
    """Hawaiian-side orthography accounting on the en→haw direction.

    Compares aggregate counts on the *reference* Hawaiian text versus the
    *hypothesis* Hawaiian text. For each marker (ʻokina, kahakō, combining
    macron, NFC pass rate) we report:

    - the raw aggregate on each side,
    - a per-pair survival rate (``min(gen / ref, 1.0)`` averaged across
      pairs where ``ref > 0``),
    - a delta = hypothesis_aggregate - reference_aggregate.

    Wrong-ʻokina is reported as a hypothesis-side count: a model that
    introduces U+2018 / U+2019 / U+02BC / U+0027 between letters is
    *injecting* a regression even if the reference has none.
    """
    en_to_haw = [p for p in pairs if p.direction == "en_to_haw"]
    refs = [p.reference for p in en_to_haw]
    hyps = [p.hypothesis for p in en_to_haw]

    ref_agg = _orthography_aggregate_for_strings(refs)
    hyp_agg = _orthography_aggregate_for_strings(hyps)

    okina_survival = []
    kahako_survival = []
    for p in en_to_haw:
        if metrics_mod.count_okina(p.reference) > 0:
            okina_survival.append(
                metrics_mod.okina_survival_rate(p.hypothesis, p.reference)
            )
        if metrics_mod.count_kahako(p.reference) > 0:
            kahako_survival.append(
                metrics_mod.kahako_retention_rate(p.hypothesis, p.reference)
            )

    def _mean(xs: list[float]) -> float | None:
        return round(sum(xs) / len(xs), 6) if xs else None

    return {
        "direction": "en_to_haw",
        "n_pairs": len(en_to_haw),
        "reference": ref_agg,
        "hypothesis": hyp_agg,
        "okina_survival_mean": _mean(okina_survival),
        "okina_survival_n": len(okina_survival),
        "kahako_retention_mean": _mean(kahako_survival),
        "kahako_retention_n": len(kahako_survival),
        "delta": {
            "okina": hyp_agg["okina"] - ref_agg["okina"],
            "wrong_okina": hyp_agg["wrong_okina"] - ref_agg["wrong_okina"],
            "kahako": hyp_agg["kahako"] - ref_agg["kahako"],
            "combining_macron": (
                hyp_agg["combining_macron"] - ref_agg["combining_macron"]
            ),
        },
        "tripwires": {
            "wrong_okina_introduced": hyp_agg["wrong_okina"] > ref_agg["wrong_okina"],
            "combining_macron_introduced": (
                hyp_agg["combining_macron"] > ref_agg["combining_macron"]
            ),
            "okina_collapse": (
                ref_agg["okina"] > 0 and hyp_agg["okina"] == 0
            ),
            "kahako_collapse": (
                ref_agg["kahako"] > 0 and hyp_agg["kahako"] == 0
            ),
        },
    }


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------


@dataclass
class Stage2EvalConfig:
    eval_jsonl: Path
    predictions_jsonl: Path
    eval_hashes_path: Path | None = None
    stage2_manifest_path: Path | None = None
    checkpoint_dir: Path | None = None
    prefer_sacrebleu: bool = True


def run_stage2_eval(cfg: Stage2EvalConfig) -> dict:
    """Run the full Stage 2 prototype gate and return a serializable report."""
    pairs = load_translation_pairs(cfg.eval_jsonl, cfg.predictions_jsonl)

    chrf_report = chrf_both_directions(
        pairs, prefer_sacrebleu=cfg.prefer_sacrebleu
    )
    leakage = leakage_check(
        pairs,
        eval_hashes_path=cfg.eval_hashes_path,
        stage2_manifest_path=cfg.stage2_manifest_path,
    )
    retention = orthography_retention(pairs)

    return {
        "schema_version": STAGE2_EVAL_SCHEMA,
        "n_pairs_total": len(pairs),
        "n_pairs_by_direction": {
            d: sum(1 for p in pairs if p.direction == d) for d in DIRECTIONS
        },
        "checkpoint_dir": str(cfg.checkpoint_dir) if cfg.checkpoint_dir else None,
        "translation": chrf_report,
        "leakage": leakage,
        "orthography_retention": retention,
        "advisory": (
            "Prototype-tier numbers. No blocking thresholds in CI per "
            "issue #23 / docs/eval_pipeline.md §3.3. Direction-separated "
            "by contract: en→haw and haw→en are NEVER averaged."
        ),
    }
