#!/usr/bin/env python3
"""Stage-2 parallel-pair manifest builder (Linus, 300-phase).

Companion to ``301_build_stage1_dataset.py`` and ``310_split_dedupe_fineweb2_haw.py``.
Owns issues:

  * #11 Stage-2 manifest builder + schema checks (this script).
  * #13 Split-isolation / dedup expectations compatible with the Stage-1
        contamination policy. CI-style assertions live in :func:`run_checks`
        and run via ``--check``.
  * #18 Wire source adapters into execute path — ingests candidate JSONL
        files from ``data/stage2/candidates/*.jsonl`` (or explicit paths)
        and assigns deterministic splits.

**Out of scope (explicitly):** issue #4 — the training-loader contamination
guard. Squad:Yashas owns wiring the runtime guard inside the trainer dataloader;
this script only emits the manifest + ledger artefacts that guard will read.
Do not import this from a training loop.

Adapter contract (issue #18): each adapter in ``data-sources/<src>/fetch.py``
produces a ``data/stage2/candidates/<src>.jsonl`` file where every row
conforms to the Stage-2 manifest schema (all required fields except ``split``
which may be ``"review-pending"``). The manifest builder validates, replaces
``"review-pending"`` splits with a deterministic train/dev assignment, then
writes ``stage2_manifest.jsonl``.

  * Validates each ingested row against the schema (types, enums, required
    fields, dependent fields) — fail-conservative like Stage 1.
  * Runs Stage-2 split-isolation / dedup expectations against an existing
    manifest in ``--check`` mode without touching training loops.

Outputs (all under ``data/`` — gitignored, prototype-only):

    data/stage2/stage2_manifest.jsonl   one row per canonical pair; canonical
                                        prototype artifact (any future Parquet
                                        mirror must be derived from this JSONL)
    data/stage2/build_manifest.json     run-level provenance: timestamp,
                                        source registry snapshot, row counts,
                                        check results

Usage::

    python scripts/320_build_stage2_manifest.py --dry-run
    python scripts/320_build_stage2_manifest.py --execute
    python scripts/320_build_stage2_manifest.py --execute --candidates data/stage2/candidates/tatoeba.jsonl
    python scripts/320_build_stage2_manifest.py --check
    python scripts/320_build_stage2_manifest.py --check --strict
    python scripts/320_build_stage2_manifest.py --print-schema

Exit codes::

    0 success (incl. dry-run, no rows yet)
    2 misuse (e.g. neither --dry-run nor --execute nor --check)
    3 schema / check failure under --strict
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_STAGE2 = REPO_ROOT / "data" / "stage2"
DATA_EVALS = REPO_ROOT / "data" / "evals"
DATA_FINAL = REPO_ROOT / "data" / "final"
CANDIDATES_DIR = DATA_STAGE2 / "candidates"
DEFAULT_STAGE2_MANIFEST = DATA_STAGE2 / "stage2_manifest.jsonl"
DEFAULT_BUILD_MANIFEST = DATA_STAGE2 / "build_manifest.json"
DEFAULT_SCORE_SUMMARY = DATA_STAGE2 / "score_summary.json"

# Make `code/` importable so the scorer module loads without packaging.
_CODE_DIR = REPO_ROOT / "code"
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

from llm_hawaii.stage2_quality import (  # noqa: E402
    POLICY_VERSION,
    BAIBALA_1839_SOURCE_ID,
    PolicyConfig,
    policy_summary,
    score_pair,
)

# Fraction of candidate pairs assigned to dev split deterministically.
# Hash of pair_id mod DEV_MODULUS == 0 → dev; else train.
# At 10% (modulus 10) a 1,000-pair corpus yields ~100 dev pairs.
_DEV_MODULUS = 10

MANIFEST_SCHEMA_VERSION = "stage2.v0"

# Canonical Stage-2 manifest schema. Mirrors docs/data-pipeline.md §"Stage 2
# manifest schema". Tuple shape: (field, type, required, allowed_values_or_None).
# ``type`` accepts a Python type or a tuple of types (None means "may be null").
MANIFEST_FIELDS: list[tuple[str, Any, bool, Any]] = [
    ("pair_id",                       str,   True,  None),
    ("source",                        str,   True,  None),
    ("source_url_en",                 str,   True,  None),
    ("source_url_haw",                str,   True,  None),
    ("fetch_date",                    str,   True,  None),  # YYYYMMDD
    ("sha256_en_raw",                 str,   True,  None),
    ("sha256_haw_raw",                str,   True,  None),
    ("sha256_en_clean",               str,   True,  None),
    ("sha256_haw_clean",              str,   True,  None),
    ("sha256_pair",                   str,   True,  None),  # primary contam key
    ("record_id_en",                  str,   True,  None),
    ("record_id_haw",                 str,   True,  None),
    # Optional in-line text. Either text_* OR text_*_path must be populated;
    # Basher's bidirectional JSONL emitter (`scripts/330_emit_stage2_sft_jsonl.py`)
    # resolves the path refs to on-disk text. Field names match
    # `docs/training-pipeline.md` §4.3.1 and the emitter's resolver.
    ("text_en",                       (str, type(None)),  False, None),
    ("text_haw",                      (str, type(None)),  False, None),
    ("text_en_path",                  (str, type(None)),  False, None),
    ("text_haw_path",                 (str, type(None)),  False, None),
    ("alignment_type",                str,   True, {
        "parallel-verse", "parallel-sentence", "parallel-doc",
        "comparable-aligned", "dictionary-example",
        "synthetic-bt", "synthetic-ft",
    }),
    ("alignment_method",              str,   True, {
        "verse-id", "tmx-line", "filename-pair", "laser", "labse", "manual",
    }),
    ("alignment_model",               (str, type(None)),  False, None),
    ("alignment_score",               (float, int, type(None)),  False, None),
    ("alignment_review_required",     bool,  True,  None),
    ("length_ratio_haw_over_en",      (float, int),  True,  None),
    ("lang_id_en",                    str,   True,  None),
    ("lang_id_en_confidence",         (float, int),  True,  None),
    ("lang_id_haw",                   str,   True,  None),
    ("lang_id_haw_confidence",        (float, int),  True,  None),
    ("direction_original",            str,   True, {"en->haw", "haw->en", "unknown"}),
    ("register",                      str,   True, {
        "religious", "software-l10n", "encyclopedic", "educational",
        "news", "dictionary-example", "unknown",
    }),
    ("edition_or_version",            (str, type(None)),  False, None),
    ("synthetic",                     bool,  True,  None),
    ("synthetic_source_model",        (str, type(None)),  False, None),
    ("license_observed_en",           str,   True,  None),
    ("license_observed_haw",          str,   True,  None),
    ("license_inferred",              type(None),  True,  None),  # always null
    ("tos_snapshot_id",               (str, type(None)),  False, None),
    ("prototype_only",                bool,  True,  None),  # default true
    ("release_eligible",              bool,  True,  None),  # default false
    ("dedup_cluster_id",              str,   True,  None),
    ("crosslink_stage1_overlap",      bool,  True,  None),
    ("split",                         str,   True, {
        "train", "dev", "test", "held-out", "review-pending",
    }),
    ("notes",                         (str, type(None)),  False, None),
    ("manifest_schema_version",       str,   True,  None),
    # ---- Stage-2 alignment-quality policy fields (issue #19) ----
    # Merged onto every manifest row by `apply_policy()` during ingest.
    # See `code/llm_hawaii/stage2_quality.py` and
    # `docs/stage2-alignment-quality.md` for the contract.
    ("alignment_confidence_tier",     str,   True, {"accept", "review", "reject"}),
    ("quality_flags",                 list,  True,  None),
    ("manual_review_reasons",         list,  True,  None),
    ("alignment_score_components",    dict,  True,  None),
    ("policy_version",                str,   True,  None),
]

REQUIRED_FIELDS: list[str] = [name for (name, _t, req, _e) in MANIFEST_FIELDS if req]
ALLOWED_SPLITS = {"train", "dev", "test", "held-out", "review-pending"}
EVAL_SPLITS = {"dev", "test", "held-out"}


# ---------- helpers ----------

def _utcnow_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_text(t: str) -> str:
    """SHA-256 of NFC-normalized UTF-8 text (caller is responsible for NFC)."""
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def compute_pair_hash(sha256_en_clean: str, sha256_haw_clean: str) -> str:
    """Primary Stage-2 contamination key: hash(en_clean ‖ haw_clean)."""
    return hashlib.sha256(
        (sha256_en_clean + "\u2016" + sha256_haw_clean).encode("utf-8")
    ).hexdigest()


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as fh:
        for ln, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                print(f"warn: {path}:{ln} bad JSON ({e}); skipping", file=sys.stderr)
                continue


# ---------- schema check ----------

def validate_row(row: dict[str, Any]) -> list[str]:
    """Return list of schema-violation strings for one manifest row.

    Conservative: missing required field, wrong type, or out-of-enum value
    each produce a single short violation tag. Caller decides strictness.
    """
    violations: list[str] = []

    for name, typ, required, enum in MANIFEST_FIELDS:
        if name not in row:
            if required:
                violations.append(f"missing:{name}")
            continue
        val = row[name]
        if not isinstance(val, typ):
            violations.append(f"type:{name}={type(val).__name__}")
            continue
        if enum is not None and val is not None and val not in enum:
            violations.append(f"enum:{name}={val!r}")

    # Dependent-field rules.
    if row.get("synthetic") is True and not row.get("synthetic_source_model"):
        violations.append("dep:synthetic_requires_source_model")
    if row.get("license_inferred") is not None:
        violations.append("dep:license_inferred_must_be_null")
    if row.get("prototype_only") is True and row.get("release_eligible") is True:
        violations.append("dep:prototype_not_release_eligible")
    if not (row.get("text_en") or row.get("text_en_path")):
        violations.append("dep:text_en_or_ref_required")
    if not (row.get("text_haw") or row.get("text_haw_path")):
        violations.append("dep:text_haw_or_ref_required")
    # Dev/test forbid non-`parallel-*` and forbid Stage-1 cross-link.
    if row.get("split") in EVAL_SPLITS:
        atype = row.get("alignment_type", "")
        if not str(atype).startswith("parallel-"):
            violations.append(f"split:{row.get('split')}_requires_parallel_alignment")
        if row.get("crosslink_stage1_overlap") is True:
            violations.append(f"split:{row.get('split')}_forbids_stage1_crosslink")

    # Pair-hash invariant: sha256_pair == hash(en_clean ‖ haw_clean).
    en_c = row.get("sha256_en_clean")
    hw_c = row.get("sha256_haw_clean")
    pair = row.get("sha256_pair")
    if isinstance(en_c, str) and isinstance(hw_c, str) and isinstance(pair, str):
        if compute_pair_hash(en_c, hw_c) != pair:
            violations.append("dep:sha256_pair_mismatch")

    return violations


# ---------- alignment-quality policy (issue #19) ----------

# Manifest fields owned by the policy. `apply_policy` overwrites these
# on every ingested row so the manifest is the single source of truth
# for the policy verdict — re-running the builder against the same
# candidates yields identical fields.
_POLICY_OUTPUT_FIELDS = (
    "alignment_confidence_tier",
    "alignment_review_required",
    "quality_flags",
    "manual_review_reasons",
    "alignment_score_components",
    "policy_version",
    "historical_orthography_exception",  # new in v0.2
    "orthography_era",                   # new in v0.2
)

# Policy tiers that disqualify a row from train/dev assignment. Such
# rows are forced to `split="review-pending"` so the SFT emitter skips
# them by default (it filters split ∉ requested set, and any review-
# required row is dropped regardless).
_NON_TRAIN_TIERS = frozenset({"review", "reject"})


def apply_policy(
    row: dict[str, Any],
    config: PolicyConfig | None = None,
) -> dict[str, Any]:
    """Merge alignment-quality policy fields onto a candidate row.

    Returns the same row dict (mutated) for convenience. The policy
    output fields are *always* overwritten; non-policy fields are left
    untouched.
    """
    annotation = score_pair(row, config)
    for k in _POLICY_OUTPUT_FIELDS:
        if k in annotation:
            row[k] = annotation[k]
    # `alignment_score` may have been canonicalised by the scorer
    # (None for non-numeric inputs). Preserve that canonicalisation
    # only when the row didn't already carry a numeric score.
    if not isinstance(row.get("alignment_score"), (int, float)):
        row["alignment_score"] = annotation.get("alignment_score")
    return row


def summarise_policy(rows: Iterable[dict[str, Any]],
                     config: PolicyConfig | None = None) -> dict[str, Any]:
    """Aggregate tier + flag counts across scored manifest rows."""
    tier_counts: Counter[str] = Counter()
    flag_counts: Counter[str] = Counter()
    n = 0
    for r in rows:
        n += 1
        tier_counts[r.get("alignment_confidence_tier", "<missing>")] += 1
        for f in r.get("quality_flags") or ():
            flag_counts[f] += 1
    return {
        "row_count": n,
        "tier_counts": dict(tier_counts),
        "flag_counts": dict(flag_counts),
        "policy": policy_summary(config),
    }


# ---------- contamination / split-isolation checks (issue #13) ----------

def load_eval_hashes(eval_hashes_paths: list[Path]) -> set[str]:
    """Union of every eval hash currently on disk (Stage-1 and Stage-2 alike).

    Reads the canonical JSONL ledger emitted today
    (``data/evals/eval_hashes.jsonl``). Transitional per-source JSONL
    ledgers are accepted only when explicitly present. Each row should carry
    ``sha256_normalized``; legacy rows may carry ``sha256_text``,
    ``sha256_en_clean``, ``sha256_haw_clean``, or ``sha256_pair``. All are unioned because at
    Stage-2 contamination time they all matter (see
    docs/data-pipeline.md §"Stage 2 contamination & eval guards").
    """
    hashes: set[str] = set()
    for path in eval_hashes_paths:
        if not path.exists():
            continue
        for row in read_jsonl(path):
            for k in ("sha256_text", "sha256_en_clean", "sha256_haw_clean",
                      "sha256_pair", "sha256_normalized", "sha256_clean"):
                v = row.get(k)
                if isinstance(v, str) and v:
                    hashes.add(v)
    return hashes


def run_checks(
    manifest_rows: list[dict[str, Any]],
    eval_hashes: set[str],
) -> dict[str, Any]:
    """Stage-2 split-isolation + dedup expectations (issue #13).

    Compatible with the Stage-1 contamination policy in
    ``docs/data-pipeline.md`` (single ``eval_hashes`` ledger;
    ``train ∩ eval_hashes = ∅`` is the canonical invariant). This function
    is **not** a training-loader guard — that's issue #4, owned by
    Squad:Yashas. We only validate the manifest artefact at build time so
    the runtime guard has something honest to check against.
    """
    schema_violations: list[tuple[str, list[str]]] = []
    for row in manifest_rows:
        viol = validate_row(row)
        if viol:
            schema_violations.append((row.get("pair_id", "<no-pair-id>"), viol))

    by_split: dict[str, list[dict[str, Any]]] = {}
    for row in manifest_rows:
        by_split.setdefault(row.get("split", "<missing>"), []).append(row)

    train = by_split.get("train", [])
    eval_rows = [r for s in EVAL_SPLITS for r in by_split.get(s, [])]

    train_pair_hashes = {r.get("sha256_pair") for r in train if r.get("sha256_pair")}
    train_en_hashes = {r.get("sha256_en_clean") for r in train if r.get("sha256_en_clean")}
    train_haw_hashes = {r.get("sha256_haw_clean") for r in train if r.get("sha256_haw_clean")}

    eval_pair_hashes = {r.get("sha256_pair") for r in eval_rows if r.get("sha256_pair")}
    eval_en_hashes = {r.get("sha256_en_clean") for r in eval_rows if r.get("sha256_en_clean")}
    eval_haw_hashes = {r.get("sha256_haw_clean") for r in eval_rows if r.get("sha256_haw_clean")}

    # 1. Internal manifest split isolation: train must not share any of
    #    pair / en-side / haw-side hashes with dev/test/held-out.
    intra_pair = train_pair_hashes & eval_pair_hashes
    intra_en = train_en_hashes & eval_en_hashes
    intra_haw = train_haw_hashes & eval_haw_hashes

    # 2. External ledger isolation: train must not collide with anything
    #    in the canonical eval-hashes ledger (Stage-1 + Stage-2 union).
    ledger_pair = train_pair_hashes & eval_hashes
    ledger_en = train_en_hashes & eval_hashes
    ledger_haw = train_haw_hashes & eval_hashes

    # 3. Group/cluster-level isolation: a dedup_cluster_id must not span
    #    train and eval splits — small parallel corpora memorize whole
    #    clusters even if individual hashes differ (paraphrases, OCR
    #    variants of the same verse, etc.).
    cluster_to_splits: dict[str, set[str]] = {}
    for row in manifest_rows:
        cid = row.get("dedup_cluster_id")
        sp = row.get("split")
        if not cid or not sp:
            continue
        cluster_to_splits.setdefault(cid, set()).add(sp)
    cluster_leaks = sorted(
        cid for cid, sps in cluster_to_splits.items()
        if "train" in sps and (sps & EVAL_SPLITS)
    )

    # 4. Cross-stage flag: rows with crosslink_stage1_overlap=true are
    #    allowed in train but banned from dev/test/held-out. Also
    #    surfaced by the per-row schema check; this is the aggregate.
    crosslink_in_eval = sum(
        1 for r in eval_rows if r.get("crosslink_stage1_overlap") is True
    )

    # 5. Lineage gate (mechanical placeholder): refuse to claim
    #    release-eligibility on any pair flagged prototype_only=true.
    lineage_violations = sum(
        1 for r in manifest_rows
        if r.get("prototype_only") is True and r.get("release_eligible") is True
    )

    return {
        "rows_total": len(manifest_rows),
        "rows_by_split": {k: len(v) for k, v in by_split.items()},
        "schema_violations": [
            {"pair_id": pid, "violations": v} for pid, v in schema_violations
        ],
        "split_isolation": {
            "intra_manifest": {
                "pair_overlap": sorted(h for h in intra_pair if h),
                "en_overlap": sorted(h for h in intra_en if h),
                "haw_overlap": sorted(h for h in intra_haw if h),
            },
            "external_ledger": {
                "pair_overlap": sorted(h for h in ledger_pair if h),
                "en_overlap": sorted(h for h in ledger_en if h),
                "haw_overlap": sorted(h for h in ledger_haw if h),
            },
            "cluster_leaks": cluster_leaks,
            "crosslink_stage1_overlap_in_eval": crosslink_in_eval,
            "lineage_violations": lineage_violations,
        },
        "invariants": [
            "stage2_train_pairs ∩ eval_hashes = ∅ (pair, en-side, haw-side)",
            "stage2_train ∩ stage1_eval_hashes = ∅ (haw side carried forward)",
            "crosslink_stage1_overlap=true allowed in train, banned from dev/test/held-out",
            "dedup_cluster_id never spans train and dev/test/held-out",
            "prototype_only=true ⇒ release_eligible=false",
        ],
        "out_of_scope": (
            "Training-loader contamination guard (issue #4) is owned by "
            "Squad:Yashas; this script validates the manifest artefact only."
        ),
    }


def checks_failed(report: dict[str, Any]) -> bool:
    if report["schema_violations"]:
        return True
    iso = report["split_isolation"]
    if any(iso["intra_manifest"][k] for k in iso["intra_manifest"]):
        return True
    if any(iso["external_ledger"][k] for k in iso["external_ledger"]):
        return True
    if iso["cluster_leaks"]:
        return True
    if iso["crosslink_stage1_overlap_in_eval"]:
        return True
    if iso["lineage_violations"]:
        return True
    return False


# ---------- split assignment (issue #18) ----------

def assign_split(pair_id: str, dev_modulus: int = _DEV_MODULUS) -> str:
    """Deterministically assign a split from pair_id.

    Uses the first 8 hex characters of the SHA-256 of the pair_id string.
    ``bucket = int(hex8, 16) % dev_modulus``; bucket 0 → "dev", else "train".
    With the default modulus of 10 this yields ≈10% dev, ≈90% train.
    This must be stable across runs — do not change the modulus after the
    first manifest write for a corpus (it will silently reclassify pairs).
    """
    h = int(hashlib.sha256(pair_id.encode("utf-8")).hexdigest()[:8], 16)
    return "dev" if (h % dev_modulus) == 0 else "train"


# ---------- candidate ingestion (issue #18) ----------

def iter_candidate_files(candidate_paths: list[Path]) -> list[Path]:
    """Resolve candidate JSONL paths, expanding globs if needed.

    Returns an empty list (not an error) when no candidates are found —
    the empty-manifest case is valid during initial scaffolding.
    """
    resolved: list[Path] = []
    for p in candidate_paths:
        if p.exists():
            resolved.append(p)
        else:
            # Allow callers to pass a glob string as a Path; expand manually.
            import glob as _glob
            expanded = sorted(_glob.glob(str(p)))
            resolved.extend(Path(e) for e in expanded)
    seen: set[Path] = set()
    deduped: list[Path] = []
    for p in resolved:
        if p not in seen:
            seen.add(p)
            deduped.append(p)
    return deduped


def ingest_candidates(
    candidate_paths: list[Path],
    dev_modulus: int = _DEV_MODULUS,
    strict: bool = False,
    policy_config: PolicyConfig | None = None,
) -> tuple[list[dict[str, Any]], list[tuple[str, list[str]]], dict[str, Any]]:
    """Read candidate JSONL files and return (rows, per_row_violations, provenance).

    For each candidate row:
    - Runs the Stage-2 alignment-quality scorer (issue #19) and merges
      policy fields onto the row (`alignment_confidence_tier`,
      `alignment_review_required`, `quality_flags`,
      `manual_review_reasons`, `alignment_score_components`,
      `policy_version`).
    - Rows whose tier is `review` or `reject` are forced to
      ``split="review-pending"`` regardless of what the candidate
      originally carried. The SFT emitter
      (``scripts/330_emit_stage2_sft_jsonl.py``) skips that split by
      default and additionally honours `alignment_review_required`.
    - Rows whose tier is `accept` keep an explicit train/dev/test/
      held-out split if the candidate already supplied one; an
      ``"review-pending"`` placeholder is replaced with a deterministic
      train/dev assignment from `assign_split(pair_id)`.
    - Validates schema; logs violations; skips violating rows if strict=True.

    Returns:
        rows: validated manifest rows
        per_row_violations: list of (pair_id, [violation, ...])
        provenance: dict with per-source counts and candidate-file SHAs
    """
    rows: list[dict[str, Any]] = []
    per_row_violations: list[tuple[str, list[str]]] = []
    per_source: dict[str, int] = {}
    candidate_file_shas: dict[str, str] = {}
    tier_counts: Counter[str] = Counter()

    for cpath in candidate_paths:
        file_sha = _file_sha256(cpath)
        candidate_file_shas[str(cpath)] = file_sha
        file_row_count = 0

        for row in read_jsonl(cpath):
            # Run the alignment-quality scorer first so split assignment
            # can honour the policy tier.
            apply_policy(row, policy_config)
            tier = row.get("alignment_confidence_tier", "review")
            tier_counts[tier] += 1

            if tier in _NON_TRAIN_TIERS:
                # Quarantine: force review-pending so the SFT emitter
                # skips the row regardless of upstream split intent.
                row["split"] = "review-pending"
            elif row.get("split") == "review-pending":
                # Accept tier with no explicit split: deterministic
                # train/dev assignment from pair_id.
                pair_id = row.get("pair_id") or row.get("sha256_pair", "")
                assigned = assign_split(pair_id, dev_modulus)
                # Only parallel-* alignment types are eligible for dev/test/held-out.
                # dictionary-example, comparable-aligned, synthetic-bt, and
                # synthetic-ft rows are train-only regardless of hash bucket.
                atype = row.get("alignment_type", "")
                if assigned in EVAL_SPLITS and not str(atype).startswith("parallel-"):
                    assigned = "train"
                row["split"] = assigned

            # Historical-orthography exception rows must never enter eval splits.
            # The exception already sets tier=accept so the quarantine branch
            # above is skipped; we additionally guard the deterministic dev
            # assignment in case a row already carried a non-review-pending split.
            if row.get("historical_orthography_exception") and row.get("split") in EVAL_SPLITS:
                row["split"] = "train"

            viol = validate_row(row)
            if viol:
                per_row_violations.append((row.get("pair_id", "<no-pair-id>"), viol))
                if strict:
                    continue  # skip violating rows under --strict

            rows.append(row)
            file_row_count += 1
            src = row.get("source", "<unknown>")
            per_source[src] = per_source.get(src, 0) + 1

        if file_row_count == 0:
            print(f"warn: {cpath} yielded no rows", file=sys.stderr)

    # Apply historical-orthography sub-cap after all rows are scored and split.
    hist_orth_cap_stats = _apply_historical_orthography_cap(rows, policy_config)

    provenance: dict[str, Any] = {
        "candidate_files": candidate_file_shas,
        "per_source_row_counts": per_source,
        "total_candidates_ingested": len(rows),
        "total_violations": len(per_row_violations),
        "dev_modulus": dev_modulus,
        "policy_version": POLICY_VERSION,
        "tier_counts": dict(tier_counts),
        "historical_orthography": hist_orth_cap_stats,
    }
    return rows, per_row_violations, provenance


def _file_sha256(path: Path) -> str:
    """SHA-256 of a file's raw bytes — for build provenance."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _apply_historical_orthography_cap(
    rows: list[dict[str, Any]],
    config: PolicyConfig | None = None,
) -> dict[str, Any]:
    """Enforce historical-orthography sub-cap in-place; return cap statistics.

    After scoring, caps the number of accepted train rows with
    ``historical_orthography_exception=True`` to the tighter of:

      - **Bible 50 % cap**: hist rows ≤ non-hist accepted Baibala 1839 train rows
        (equivalently, hist rows ≤ 50 % of all accepted Baibala 1839 train rows).
      - **Train-share cap**: hist rows ≤
        ``config.historical_orthography_train_token_share_max`` of total accepted
        train rows — implemented as a *row-count proxy* because exact subword-token
        counting requires a tokenizer. Revisit once the SFT tokenizer is pinned.

    Excess rows are demoted to ``split="review-pending"`` and have
    ``"historical_orthography_sub_cap_reached"`` appended to
    ``manual_review_reasons``. Down-sampling is deterministic: rows are
    sorted by SHA-256 hash of ``pair_id`` (ascending) and the lowest-hash
    rows are kept so re-runs with the same candidates yield the same result.

    Returns a dict written to ``build_manifest.json::ingest.historical_orthography``.

    LIMITATION: the 15 % cap uses whitespace-token row counts as a proxy for
    subword-token counts. Actual token counts depend on the tokenizer and may
    differ by ±10–15 %. Revisit when the SFT tokenizer is pinned.
    """
    cfg = config or PolicyConfig()

    hist_train_idxs: list[int] = [
        i for i, r in enumerate(rows)
        if r.get("historical_orthography_exception") and r.get("split") == "train"
    ]
    non_hist_bible_train: list[dict[str, Any]] = [
        r for r in rows
        if r.get("source") == BAIBALA_1839_SOURCE_ID
        and r.get("split") == "train"
        and not r.get("historical_orthography_exception")
    ]
    all_train: list[dict[str, Any]] = [r for r in rows if r.get("split") == "train"]

    n_hist = len(hist_train_idxs)

    # 50 % Bible cap: at most as many hist rows as non-hist accepted Bible rows.
    cap_by_bible = len(non_hist_bible_train)

    # Train-share cap (row-count proxy for the token-share ceiling).
    # Solve: hist / total_train = share_max → cap = total_train * share_max.
    cap_by_train_share = int(len(all_train) * cfg.historical_orthography_train_token_share_max)

    # Apply whichever ceiling is tighter.
    effective_cap = min(cap_by_bible, cap_by_train_share)

    n_dropped = 0
    if n_hist > effective_cap:
        def _hash_key(idx: int) -> int:
            pair_id = rows[idx].get("pair_id", "")
            return int(hashlib.sha256(pair_id.encode("utf-8")).hexdigest()[:8], 16)

        sorted_idxs = sorted(hist_train_idxs, key=_hash_key)
        keep_set = set(sorted_idxs[:effective_cap])
        for idx in hist_train_idxs:
            if idx not in keep_set:
                rows[idx]["split"] = "review-pending"
                reasons: list = rows[idx].setdefault("manual_review_reasons", [])
                reasons.append("historical_orthography_sub_cap_reached")
                n_dropped += 1

    return {
        "effective_cap": effective_cap,
        "cap_by_bible_rows": cap_by_bible,
        "cap_by_train_share_rows": cap_by_train_share,
        "accepted_rows": n_hist - n_dropped,
        "dropped_rows": n_dropped,
        "token_cap_is_row_proxy": True,
        "token_share_max": cfg.historical_orthography_train_token_share_max,
    }


# ---------- source registry (issue #18) ----------

def default_candidate_paths() -> list[Path]:
    """Glob data/stage2/candidates/*.jsonl for registered adapter outputs."""
    if not CANDIDATES_DIR.exists():
        return []
    return sorted(CANDIDATES_DIR.glob("*.jsonl"))


# ---------- writers ----------

def write_manifest(rows: list[dict[str, Any]], dry_run: bool) -> dict[str, str]:
    out_path = DEFAULT_STAGE2_MANIFEST
    written: dict[str, str] = {}
    if dry_run:
        print(f"[DRY-RUN] would write {len(rows)} rows → {out_path}")
        return written
    DATA_STAGE2.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    written["manifest"] = str(out_path)
    return written


def write_build_manifest(payload: dict[str, Any], dry_run: bool) -> str | None:
    out_path = DEFAULT_BUILD_MANIFEST
    if dry_run:
        return None
    DATA_STAGE2.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    return str(out_path)


def write_score_summary(summary: dict[str, Any], dry_run: bool) -> str | None:
    """Persist the run-level alignment-quality summary (issue #19).

    Writes to ``data/stage2/score_summary.json`` (gitignored). Skipped
    under --dry-run. Resolves the path against ``DATA_STAGE2`` at call
    time so tests that monkey-patch the data directory take effect.
    """
    if dry_run:
        return None
    out_path = DATA_STAGE2 / "score_summary.json"
    DATA_STAGE2.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    return str(out_path)


# ---------- CLI ----------

def _default_eval_hash_paths() -> list[Path]:
    """Best-effort enumeration of on-disk eval-hash JSONL ledgers."""
    candidates: list[Path] = []
    canonical = DATA_EVALS / "eval_hashes.jsonl"
    if canonical.exists():
        candidates.append(canonical)
    for root in (DATA_EVALS, DATA_FINAL):
        if not root.exists():
            continue
        for p in root.rglob("eval_hashes.jsonl"):
            if p != canonical:
                candidates.append(p)
    return candidates


def _rel(path: Path) -> str:
    """Return path relative to REPO_ROOT when possible, else absolute str."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Stage-2 parallel-pair manifest builder (issues #11/#13/#18).",
    )
    p.add_argument("--dry-run", action="store_true",
                   help="Run pipeline but do not write outputs.")
    p.add_argument("--execute", action="store_true",
                   help="Write outputs to disk under data/stage2/.")
    p.add_argument("--check", action="store_true",
                    help="Run schema + split-isolation + dedup expectations "
                         f"against an existing {_rel(DEFAULT_STAGE2_MANIFEST)}. "
                         "Does not touch training loops (issue #4 is out of scope).")
    p.add_argument("--strict", action="store_true",
                   help="Exit non-zero on any schema or contamination "
                        "violation. Use in CI.")
    p.add_argument("--manifest-in", type=Path, default=None,
                    help="Override manifest path for --check "
                         f"(default: {_rel(DEFAULT_STAGE2_MANIFEST)}).")
    p.add_argument("--eval-hashes", type=Path, action="append", default=None,
                   help="Path(s) to eval-hashes JSONL ledgers. Repeatable. "
                        "Default: data/evals/eval_hashes.jsonl plus legacy per-source ledgers if present.")
    p.add_argument("--candidates", type=Path, action="append", default=None,
                   metavar="PATH",
                   help="Candidate JSONL path(s) to ingest (repeatable). "
                        f"Default: all *.jsonl in {_rel(CANDIDATES_DIR)}/. "
                        "Pass explicit paths to restrict to specific adapters.")
    p.add_argument("--dev-modulus", type=int, default=_DEV_MODULUS,
                   help=f"Split dev fraction = 1/N (default: {_DEV_MODULUS} → ~10%% dev).")
    p.add_argument("--print-schema", action="store_true",
                   help="Print the canonical Stage-2 manifest schema and exit.")
    args = p.parse_args(argv)

    if args.print_schema:
        schema = [
            {
                "field": name,
                "type": (typ.__name__ if isinstance(typ, type)
                         else [t.__name__ for t in typ]),
                "required": req,
                "enum": sorted(enum) if isinstance(enum, set) else None,
            }
            for name, typ, req, enum in MANIFEST_FIELDS
        ]
        json.dump(
            {"schema_version": MANIFEST_SCHEMA_VERSION, "fields": schema},
            sys.stdout, ensure_ascii=False, indent=2,
        )
        sys.stdout.write("\n")
        return 0

    if not (args.dry_run or args.execute or args.check):
        print("error: must pass one of --dry-run, --execute, --check.", file=sys.stderr)
        return 2

    started = _utcnow_iso()
    eval_hash_paths = list(args.eval_hashes) if args.eval_hashes else _default_eval_hash_paths()

    if args.check:
        manifest_in = args.manifest_in or DEFAULT_STAGE2_MANIFEST
        if not manifest_in.exists():
            print(f"error: manifest not found: {manifest_in}", file=sys.stderr)
            return 3 if args.strict else 0
        rows = list(read_jsonl(manifest_in))
        eval_hashes = load_eval_hashes(eval_hash_paths)
        report = run_checks(rows, eval_hashes)
        out = {
            "mode": "check",
            "started_utc": started,
            "manifest_in": str(manifest_in),
            "eval_hash_ledgers": [str(p) for p in eval_hash_paths],
            "eval_hashes_loaded": len(eval_hashes),
            "report": report,
        }
        json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        if args.strict and checks_failed(report):
            return 3
        return 0

    # Build path (issue #18): ingest candidate JSONL files from registered adapters.
    candidate_paths = (
        list(args.candidates) if args.candidates else default_candidate_paths()
    )
    resolved = iter_candidate_files(candidate_paths)
    if not resolved:
        print(
            f"info: no candidate files found under {CANDIDATES_DIR}; "
            "manifest will be empty.",
            file=sys.stderr,
        )

    rows, per_row_violations, ingest_provenance = ingest_candidates(
        resolved, dev_modulus=args.dev_modulus, strict=args.strict,
    )

    eval_hashes = load_eval_hashes(eval_hash_paths)
    report = run_checks(rows, eval_hashes)

    score_summary = summarise_policy(rows)
    score_summary_path = write_score_summary(score_summary, args.dry_run)

    written = write_manifest(rows, args.dry_run)
    payload = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "started_utc": started,
        "finished_utc": _utcnow_iso(),
        "rows_emitted": len(rows),
        "rows_skipped_violations": len(per_row_violations),
        "eval_hash_ledgers": [str(p) for p in eval_hash_paths],
        "eval_hashes_loaded": len(eval_hashes),
        "ingest": ingest_provenance,
        "report": report,
        "score_summary": score_summary,
        "outputs": written,
        "dry_run": args.dry_run,
        "strict": args.strict,
    }
    build_manifest_path = write_build_manifest(payload, args.dry_run)
    if build_manifest_path:
        payload["outputs"]["build_manifest"] = build_manifest_path
    if score_summary_path:
        payload["outputs"]["score_summary"] = score_summary_path

    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")

    if args.strict and (per_row_violations or checks_failed(report)):
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
