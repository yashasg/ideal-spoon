#!/usr/bin/env python3
"""Build Stage-2 candidate pairs from Wikimedia Content Translation revision bodies.

Reads pre-fetched MediaWiki API parse responses under
``data/raw/wikimedia-cx-en-haw-published/20260501/revisions/`` and the
``api.php`` metadata index, then emits cleaned paragraph-level candidate
pairs to ``data/stage2/candidates/wikimedia_cx_en_haw.jsonl``.

Alignment strategy (conservative):
- **Positional**: when n_en == n_haw (exact para count match) — one pair per
  paragraph position. Applied to 2 articles in the current dataset.
- **Lead-only**: for all other articles — one pair using the first body
  paragraph from each side. This is the canonical CX stub pattern: HAW articles
  created via CX are often stubs containing only the translated intro paragraph.

Provenance: translationId, sourceRevisionId, targetRevisionId, source/target
URLs, license_observed, stats.human/stats.mt are propagated to every row.

All rows are emitted as:
  prototype_only=True, release_eligible=False, split="review-pending",
  alignment_review_required=True, direction_original="en->haw",
  register="encyclopedic", license=CC BY-SA 4.0 / GFDL.

Usage::

    python3 scripts/326_build_wikimedia_cx_candidates.py --self-test
    python3 scripts/326_build_wikimedia_cx_candidates.py --dry-run
    python3 scripts/326_build_wikimedia_cx_candidates.py --execute

Exit codes: 0 success, 1 I/O error, 2 CLI misuse, 3 schema failure.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
CODE_ROOT = REPO_ROOT / "code"
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))
from llm_hawaii.stage2_canonical import (  # noqa: E402
    canonical_en as stage2_canonical_en,
    canonical_haw as stage2_canonical_haw,
    compute_pair_hash as stage2_compute_pair_hash,
    sha256_text as stage2_sha256_text,
)
RAW_DIR = REPO_ROOT / "data" / "raw" / "wikimedia-cx-en-haw-published" / "20260501"
REVISIONS_DIR = RAW_DIR / "revisions"
API_INDEX = RAW_DIR / "api.php"

STAGE2_DIR = REPO_ROOT / "data" / "stage2"
CANDIDATES_DIR = STAGE2_DIR / "candidates"
REPORTS_DIR = STAGE2_DIR / "reports"

OUTPUT_CANDIDATES = CANDIDATES_DIR / "wikimedia_cx_en_haw.jsonl"
OUTPUT_REPORT = REPORTS_DIR / "wikimedia_cx_en_haw_report.json"

SOURCE_ID = "wikimedia-cx-en-haw"
SCHEMA_VERSION = "stage2.v0"
FETCH_DATE = "20260501"

LICENSE_EN = (
    "Wikipedia content CC BY-SA 4.0; en.wikipedia.org revision "
    "linked by sourceRevisionId. Attribution intrinsic via revision history."
)
LICENSE_HAW = (
    "Wikipedia content CC BY-SA 4.0; haw.wikipedia.org revision "
    "linked by targetRevisionId. Attribution intrinsic via revision history."
)

# HAW diacritic characters used for quality check
HAW_DIACRITICS = set("āēīōūĀĒĪŌŪ\u02bb")

# Minimum word count for a candidate paragraph
MIN_WORDS = 5
# Length ratio bounds (haw/en)
MIN_RATIO = 0.08
MAX_RATIO = 12.0

# Okina variants to normalise to canonical U+02BB


# ── text cleaning ─────────────────────────────────────────────────────────────

def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def normalize_haw(text: str) -> str:
    return stage2_canonical_haw(text)


def _strip_templates(text: str) -> str:
    """Remove {{...}} templates iteratively (handles multi-line and nested)."""
    # First pass: remove multi-line templates with DOTALL
    for _ in range(6):
        prev = text
        text = re.sub(r"\{\{[^{}]*\}\}", "", text, flags=re.DOTALL)
        if text == prev:
            break
    return text


def _strip_refs(text: str) -> str:
    text = re.sub(r"<ref[^>]*/>\s*", "", text)
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.DOTALL)
    return text


def _strip_wikilinks(text: str) -> str:
    """[[Link|Display]] → Display; [[Link]] → Link."""
    return re.sub(r"\[\[(?:[^|\]]+\|)?([^\]]*)\]\]", r"\1", text)


def _strip_bold_italic(text: str) -> str:
    return re.sub(r"'{2,}", "", text)


def _is_markup_line(line: str) -> bool:
    """Return True for lines that are purely table/template/category markup."""
    if not line:
        return True
    first = line[0]
    if first in "{|!}<":
        return True
    if re.match(r"^\[\[(Category|File|Image):", line, re.IGNORECASE):
        return True
    return False


def extract_paragraphs(wikitext: str) -> list[str]:
    """Extract non-empty body text paragraphs from raw wikitext.

    Strategy:
    - Strip multi-line templates (infoboxes, flat lists, etc.) from full text
      BEFORE splitting into paragraph blocks.
    - Split on double newlines (MediaWiki paragraph breaks).
    - Per block: strip table rows, refs, wikilinks, markup.
    - Discard section headers (== ... ==).
    - Discard blocks with fewer than MIN_WORDS words.
    """
    # Pre-strip multi-line templates and refs from the full wikitext
    cleaned_wt = _strip_templates(wikitext)
    cleaned_wt = _strip_refs(cleaned_wt)

    paragraphs: list[str] = []
    for block in re.split(r"\n\n+", cleaned_wt):
        lines: list[str] = []
        for raw in block.split("\n"):
            line = raw.strip()
            if _is_markup_line(line):
                continue
            if re.match(r"^==.*==$", line):
                continue
            line = _strip_wikilinks(line)
            line = _strip_bold_italic(line)
            # Strip leading list markers (keep content)
            line = re.sub(r"^[*#:;]+\s*", "", line)
            line = line.strip()
            if line:
                lines.append(line)
        if not lines:
            continue
        text = " ".join(lines).strip()
        text = re.sub(r"\s{2,}", " ", text).strip()
        if len(text.split()) >= MIN_WORDS:
            paragraphs.append(text)
    return paragraphs


# ── hashing helpers ───────────────────────────────────────────────────────────

def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def compute_pair_hash(sha256_en_clean: str, sha256_haw_clean: str) -> str:
    return stage2_compute_pair_hash(sha256_en_clean, sha256_haw_clean)


# ── metadata loading ──────────────────────────────────────────────────────────

def load_metadata(api_path: Path) -> dict[str, dict]:
    """Load translationId → metadata from api.php index."""
    raw = json.loads(api_path.read_text(encoding="utf-8"))
    translations = raw["result"]["translations"]
    return {t["translationId"]: t for t in translations}


def _stat(t: dict, key: str) -> float:
    v = t.get("stats", {}).get(key)
    return 0.0 if v is None else float(v)


def survivors(meta: dict[str, dict]) -> list[dict]:
    """Apply the same gate as the fetcher: stats.mt < 0.5 AND stats.human > 0."""
    return [t for t in meta.values() if _stat(t, "mt") < 0.5 and _stat(t, "human") > 0]


def load_revision(revisions_dir: Path, tid: str, side: str) -> dict | None:
    """Load parse JSON for one side; return None on missing/error revision."""
    files = list(revisions_dir.glob(f"{tid}.{side}.*.json"))
    if not files:
        return None
    d = json.loads(files[0].read_text(encoding="utf-8"))
    if "parse" not in d:
        return None
    return d


# ── candidate row builder ─────────────────────────────────────────────────────

def build_row(
    *,
    tid: str,
    meta: dict,
    en_rev: dict,
    haw_rev: dict,
    en_text: str,
    haw_text: str,
    para_idx: int,
    alignment_mode: str,  # "positional" | "lead-only"
    n_en_paras: int,
    n_haw_paras: int,
) -> dict[str, Any]:
    en_url = "https:" + meta["sourceURL"].replace(" ", "_")
    haw_url = "https:" + meta["targetURL"].replace(" ", "_")
    src_rev_id = meta["sourceRevisionId"]
    tgt_rev_id = meta["targetRevisionId"]
    stats_human = _stat(meta, "human")
    stats_mt = _stat(meta, "mt")

    en_clean = stage2_canonical_en(en_text)
    haw_clean = normalize_haw(haw_text)

    sha_en_raw = _sha256(en_text)
    sha_haw_raw = _sha256(haw_text)
    sha_en_clean = stage2_sha256_text(en_clean)
    sha_haw_clean = stage2_sha256_text(haw_clean)
    sha_pair = compute_pair_hash(sha_en_clean, sha_haw_clean)

    pair_id = f"{SOURCE_ID}-{tid}-p{para_idx}"

    en_words = len(en_clean.split())
    haw_words = len(haw_clean.split())
    ratio = haw_words / en_words if en_words > 0 else 0.0

    notes_parts = [
        f"translationId={tid}",
        f"sourceRevisionId={src_rev_id}",
        f"targetRevisionId={tgt_rev_id}",
        f"stats.human={stats_human:.4f}",
        f"stats.mt={stats_mt:.4f}",
        f"alignment_mode={alignment_mode}",
        f"n_en_paras={n_en_paras}",
        f"n_haw_paras={n_haw_paras}",
        f"para_idx={para_idx}",
    ]

    return {
        "pair_id": pair_id,
        "source": SOURCE_ID,
        "source_url_en": en_url,
        "source_url_haw": haw_url,
        "fetch_date": FETCH_DATE,
        "sha256_en_raw": sha_en_raw,
        "sha256_haw_raw": sha_haw_raw,
        "sha256_en_clean": sha_en_clean,
        "sha256_haw_clean": sha_haw_clean,
        "sha256_pair": sha_pair,
        "record_id_en": f"en-rev-{src_rev_id}-p{para_idx}",
        "record_id_haw": f"haw-rev-{tgt_rev_id}-p{para_idx}",
        "text_en": en_clean,
        "text_haw": haw_clean,
        "text_en_path": None,
        "text_haw_path": None,
        "alignment_type": "parallel-sentence",
        "alignment_method": "filename-pair",
        "alignment_model": None,
        "alignment_score": None,
        "alignment_review_required": True,
        "length_ratio_haw_over_en": round(ratio, 6),
        "lang_id_en": "en",
        "lang_id_en_confidence": 1.0,
        "lang_id_haw": "haw",
        "lang_id_haw_confidence": 1.0,
        "direction_original": "en->haw",
        "register": "encyclopedic",
        "edition_or_version": (
            f"haw.wikipedia.org rev {tgt_rev_id} "
            f"(CX from en.wikipedia.org rev {src_rev_id})"
        ),
        "synthetic": False,
        "synthetic_source_model": None,
        "license_observed_en": LICENSE_EN,
        "license_observed_haw": LICENSE_HAW,
        "license_inferred": None,
        "tos_snapshot_id": None,
        "prototype_only": True,
        "release_eligible": False,
        "dedup_cluster_id": pair_id,
        "crosslink_stage1_overlap": False,
        "split": "review-pending",
        "notes": "; ".join(notes_parts),
        "manifest_schema_version": SCHEMA_VERSION,
    }


# ── quality gate ──────────────────────────────────────────────────────────────

def _has_haw_chars(text: str) -> bool:
    return any(c in HAW_DIACRITICS for c in text)


def passes_quality(en_text: str, haw_text: str) -> tuple[bool, str]:
    """Return (pass, reason). reason is '' when passing."""
    en_w = len(en_text.split())
    haw_w = len(haw_text.split())
    if en_w < MIN_WORDS:
        return False, f"en_too_short ({en_w}w)"
    if haw_w < MIN_WORDS:
        return False, f"haw_too_short ({haw_w}w)"
    ratio = haw_w / en_w
    if ratio < MIN_RATIO or ratio > MAX_RATIO:
        return False, f"ratio_out_of_range ({ratio:.3f})"
    # Note: we do NOT require HAW diacritics — some legitimate articles may
    # lack them (e.g., proper nouns, code-switching). Record but don't gate.
    return True, ""


# ── main processing ───────────────────────────────────────────────────────────

def process_all(
    revisions_dir: Path,
    meta_all: dict[str, dict],
    *,
    verbose: bool = False,
) -> tuple[list[dict], dict]:
    """Return (candidate_rows, stats_dict)."""
    surv = survivors(meta_all)
    stats: dict[str, Any] = {
        "total_translations_in_index": len(meta_all),
        "survivors_gate": len(surv),
        "both_revisions_ok": 0,
        "en_missing_or_error": 0,
        "haw_missing_or_error": 0,
        "both_missing_or_error": 0,
        "articles_positional": 0,
        "articles_lead_only": 0,
        "articles_skipped_quality": 0,
        "pairs_emitted": 0,
        "pairs_skipped_quality": 0,
        "pairs_no_haw_diacritics": 0,
        "per_article": {},
    }

    rows: list[dict] = []

    for t in surv:
        tid = t["translationId"]
        en_rev = load_revision(revisions_dir, tid, "en")
        haw_rev = load_revision(revisions_dir, tid, "haw")

        if en_rev is None and haw_rev is None:
            stats["both_missing_or_error"] += 1
            stats["per_article"][tid] = {"status": "both_error"}
            continue
        if en_rev is None:
            stats["en_missing_or_error"] += 1
            stats["per_article"][tid] = {"status": "en_error"}
            continue
        if haw_rev is None:
            stats["haw_missing_or_error"] += 1
            stats["per_article"][tid] = {"status": "haw_error"}
            continue

        stats["both_revisions_ok"] += 1

        en_paras = extract_paragraphs(en_rev["parse"]["wikitext"])
        haw_paras = extract_paragraphs(haw_rev["parse"]["wikitext"])
        n_en = len(en_paras)
        n_haw = len(haw_paras)

        if n_en == 0 or n_haw == 0:
            stats["articles_skipped_quality"] += 1
            stats["per_article"][tid] = {"status": "empty_after_cleaning"}
            continue

        # Alignment decision: positional only when counts match exactly
        if n_en == n_haw:
            alignment_mode = "positional"
            stats["articles_positional"] += 1
            candidate_pairs = list(zip(en_paras, haw_paras))
        else:
            alignment_mode = "lead-only"
            stats["articles_lead_only"] += 1
            candidate_pairs = [(en_paras[0], haw_paras[0])]

        article_rows: list[dict] = []
        article_skipped = 0

        for para_idx, (en_text, haw_text) in enumerate(candidate_pairs):
            ok, reason = passes_quality(en_text, haw_text)
            if not ok:
                stats["pairs_skipped_quality"] += 1
                article_skipped += 1
                if verbose:
                    print(
                        f"  skip {tid} p{para_idx}: {reason}",
                        file=sys.stderr,
                    )
                continue

            if not _has_haw_chars(haw_text):
                stats["pairs_no_haw_diacritics"] += 1

            row = build_row(
                tid=tid,
                meta=t,
                en_rev=en_rev,
                haw_rev=haw_rev,
                en_text=en_text,
                haw_text=haw_text,
                para_idx=para_idx,
                alignment_mode=alignment_mode,
                n_en_paras=n_en,
                n_haw_paras=n_haw,
            )
            article_rows.append(row)
            stats["pairs_emitted"] += 1

        rows.extend(article_rows)
        stats["per_article"][tid] = {
            "status": "ok",
            "sourceTitle": t.get("sourceTitle", ""),
            "targetTitle": t.get("targetTitle", ""),
            "alignment_mode": alignment_mode,
            "n_en_paras": n_en,
            "n_haw_paras": n_haw,
            "pairs_emitted": len(article_rows),
            "pairs_skipped": article_skipped,
            "stats_human": _stat(t, "human"),
            "stats_mt": _stat(t, "mt"),
        }

    return rows, stats


# ── self-test ─────────────────────────────────────────────────────────────────

def _self_test() -> None:
    """In-memory smoke tests — no filesystem I/O."""
    # 1. extract_paragraphs strips tables and templates
    wt1 = (
        "{{Infobox person|name=Test}}\n\n"
        "This is a body paragraph about something notable.\n\n"
        "== Section ==\n\n"
        "Second paragraph with enough words here.\n\n"
        "{| class=wikitable\n|-\n| cell\n|}\n\n"
        "[[Category:Test]]\n"
    )
    paras1 = extract_paragraphs(wt1)
    assert len(paras1) == 2, f"expected 2 paras, got {len(paras1)}: {paras1}"
    assert "body paragraph" in paras1[0], paras1
    assert "Second paragraph" in paras1[1], paras1

    # 2. extract_paragraphs strips refs and wikilinks
    wt2 = "'''Hualani''' was a [[Chiefess|High Chiefess]] of [[Molokai]].<ref>Source</ref>\n"
    paras2 = extract_paragraphs(wt2)
    assert len(paras2) == 1, paras2
    assert "[[" not in paras2[0], paras2
    assert "<ref>" not in paras2[0], paras2
    assert "High Chiefess" in paras2[0], paras2

    # 3. normalize_haw folds okina variants
    raw_haw = "\u2018O ia.\u2019"
    normalized = normalize_haw(raw_haw)
    assert normalized == "\u02bbO ia.\u02bb", repr(normalized)

    # 4. pair hash mirrors manifest helper
    en_clean = "Test sentence in English."
    haw_clean = normalize_haw("He māmā kēia.")
    sha_en = stage2_sha256_text(stage2_canonical_en(en_clean))
    sha_haw = stage2_sha256_text(haw_clean)
    expected_pair = stage2_compute_pair_hash(sha_en, sha_haw)
    assert compute_pair_hash(sha_en, sha_haw) == expected_pair

    # 5. passes_quality gate
    assert passes_quality("Hello this is a long sentence here", "He māmā kēia paha nei nō")[0] is True
    assert passes_quality("Hi", "He")[0] is False  # too short
    assert passes_quality("word " * 5, "w " * 200)[0] is False  # ratio too high

    # 6. build_row produces required schema fields
    fake_meta = {
        "translationId": "99999",
        "sourceTitle": "Test",
        "targetTitle": "Kōkōkō",
        "sourceRevisionId": "123456",
        "targetRevisionId": "789",
        "sourceURL": "//en.wikipedia.org/wiki/Test",
        "targetURL": "//haw.wikipedia.org/wiki/K%C5%8Dk%C5%8Dk%C5%8D",
        "stats": {"human": 0.9, "mt": 0.1},
    }
    fake_en_rev = {"parse": {"revid": 123456}}
    fake_haw_rev = {"parse": {"revid": 789}}
    row = build_row(
        tid="99999",
        meta=fake_meta,
        en_rev=fake_en_rev,
        haw_rev=fake_haw_rev,
        en_text="This is a test sentence in English for the adapter.",
        haw_text="ʻO kēia he māmā hoʻāʻo no ka mea hana.",
        para_idx=0,
        alignment_mode="lead-only",
        n_en_paras=5,
        n_haw_paras=1,
    )
    required = [
        "pair_id", "source", "sha256_pair", "text_en", "text_haw",
        "alignment_type", "alignment_method", "prototype_only",
        "release_eligible", "split", "manifest_schema_version",
    ]
    for f in required:
        assert f in row, f"missing field: {f}"
    assert row["prototype_only"] is True
    assert row["release_eligible"] is False
    assert row["split"] == "review-pending"
    assert row["alignment_review_required"] is True
    assert row["direction_original"] == "en->haw"
    assert row["register"] == "encyclopedic"
    # Verify pair hash
    ep = compute_pair_hash(row["sha256_en_clean"], row["sha256_haw_clean"])
    assert row["sha256_pair"] == ep, "pair hash mismatch"

    print("self-test: 7 assertions OK")


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build Stage-2 Wikimedia CX candidates."
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true", help="Report what would be written; no file I/O.")
    g.add_argument("--execute", action="store_true", help="Write candidates + report.")
    g.add_argument("--self-test", action="store_true", help="Run in-memory smoke tests and exit.")
    p.add_argument("--verbose", "-v", action="store_true", help="Print per-row skip reasons.")
    return p.parse_args()


def main() -> int:
    args = _parse_args()

    if args.self_test:
        _self_test()
        return 0

    # Validate input paths
    if not REVISIONS_DIR.exists():
        print(f"error: revisions directory not found: {REVISIONS_DIR}", file=sys.stderr)
        return 1
    if not API_INDEX.exists():
        print(f"error: api.php index not found: {API_INDEX}", file=sys.stderr)
        return 1

    meta_all = load_metadata(API_INDEX)
    print(f"Loaded {len(meta_all)} translation records from api.php")

    rows, stats = process_all(REVISIONS_DIR, meta_all, verbose=args.verbose)

    surv = stats["survivors_gate"]
    emitted = stats["pairs_emitted"]
    skipped_q = stats["pairs_skipped_quality"]
    no_diac = stats["pairs_no_haw_diacritics"]

    print(f"Survivors (mt<0.5 AND human>0): {surv}")
    print(f"Both revisions OK:              {stats['both_revisions_ok']}")
    print(f"HAW revision missing/error:     {stats['haw_missing_or_error']}")
    print(f"EN revision missing/error:      {stats['en_missing_or_error']}")
    print(f"Both missing/error:             {stats['both_missing_or_error']}")
    print(f"Articles (positional align):    {stats['articles_positional']}")
    print(f"Articles (lead-only align):     {stats['articles_lead_only']}")
    print(f"Articles (skipped empty):       {stats['articles_skipped_quality']}")
    print(f"Pairs emitted:                  {emitted}")
    print(f"Pairs skipped (quality gate):   {skipped_q}")
    print(f"Pairs with no HAW diacritics:   {no_diac}")

    if args.dry_run:
        print(f"\ndry-run: {emitted} rows would be written to {OUTPUT_CANDIDATES.relative_to(REPO_ROOT)}")
        print(f"dry-run: report would be written to {OUTPUT_REPORT.relative_to(REPO_ROOT)}")
        return 0

    # --execute: write outputs
    CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    with OUTPUT_CANDIDATES.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"\nWrote {emitted} rows → {OUTPUT_CANDIDATES.relative_to(REPO_ROOT)}")

    report = {
        "script": "scripts/326_build_wikimedia_cx_candidates.py",
        "generated_at_utc": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_id": SOURCE_ID,
        "raw_data_date": FETCH_DATE,
        "stats": stats,
        "alignment_policy": {
            "positional_trigger": "n_en_paras == n_haw_paras (exact match)",
            "lead_only_trigger": "n_en_paras != n_haw_paras (typical CX stub pattern)",
            "min_words_per_side": MIN_WORDS,
            "min_ratio_haw_over_en": MIN_RATIO,
            "max_ratio_haw_over_en": MAX_RATIO,
        },
        "quality_notes": [
            "alignment_review_required=True on all rows (Wikipedia encyclopedic text, CX partial translations)",
            "prototype_only=True; release_eligible=False; CC BY-SA 4.0 / GFDL — not PD",
            "split=review-pending; no rows are train-ready without further review",
            "HAW diacritics present on most rows but not enforced as gate (proper nouns may lack them)",
        ],
        "blocker": None,
    }
    with OUTPUT_REPORT.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(f"Wrote report  → {OUTPUT_REPORT.relative_to(REPO_ROOT)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
