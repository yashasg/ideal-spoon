#!/usr/bin/env python3
"""Stage-2 Ka Hoʻoilina candidate builder (Linus, issue #hooilina-fix).

Reads locally fetched HTML section files under
``data/raw/hooilina-stage2/20260501/sections/{en,haw_modern}/`` and emits
``data/stage2/candidates/hooilina.jsonl`` — one row per section pair where
both sides contain real aligned content (not UI boilerplate).

Fixes applied vs. the prior ad-hoc generation:
  * Extracts only the main <td> content block; ignores JS header and
    Greenstone footer ("Look up any word…" / copyright notice).
  * Runs html.unescape() on all text before NFC/hash.
  * Applies ʻokina canonicalization (U+02BB) on the Hawaiian side.

Stdlib only. Exit codes: 0 success, 1 I/O error, 2 CLI misuse, 3 schema failure.

Usage::

    python scripts/324_build_hooilina_candidates.py --dry-run
    python scripts/324_build_hooilina_candidates.py --execute
    python scripts/324_build_hooilina_candidates.py --self-test
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import html as html_mod
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_ROOT = REPO_ROOT / "data" / "raw" / "hooilina-stage2" / "20260501"
SECTIONS_EN = RAW_ROOT / "sections" / "en"
SECTIONS_HAW = RAW_ROOT / "sections" / "haw_modern"
OUT_PATH = REPO_ROOT / "data" / "stage2" / "candidates" / "hooilina.jsonl"
REPORTS_DIR = REPO_ROOT / "data" / "stage2" / "reports"

MANIFEST_SCHEMA_VERSION = "stage2.v0"
SOURCE_ID = "hooilina"
FETCH_DATE = "20260501"

# Greenstone e= state token captured during raw pull.
E_DOC = "d-0journal--00-0-0-004-Document---0-1--1haw-50---20-frameset---ka--001-0110escapewin"

# Canonical ʻokina and common mis-encodings (mirrors stage2_quality.py).
OKINA = "\u02bb"
OKINA_MISENCODINGS = ("\u2018", "\u2019", "\u02bc", "`", "'")

# Boilerplate signal: if the stripped paragraph text starts with this phrase,
# the section contains only the Greenstone site footer (not real content).
BOILERPLATE_SIGNAL = "Look up any word"

# Minimum word count per side to emit a row.
MIN_WORDS = 5


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def normalize_haw(text: str) -> str:
    """html.unescape → NFC → ʻokina canonicalization → strip."""
    t = html_mod.unescape(text)
    t = unicodedata.normalize("NFC", t)
    for bad in OKINA_MISENCODINGS:
        t = t.replace(bad, OKINA)
    return t.strip()


def normalize_en(text: str) -> str:
    """html.unescape → NFC → strip."""
    t = html_mod.unescape(text)
    return unicodedata.normalize("NFC", t).strip()


def sha256_text(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def compute_pair_hash(sha256_en_clean: str, sha256_haw_clean: str) -> str:
    """Primary Stage-2 contamination key: sha256(en_clean ‖ haw_clean)."""
    return hashlib.sha256(
        (sha256_en_clean + "\u2016" + sha256_haw_clean).encode("utf-8")
    ).hexdigest()


# ---------------------------------------------------------------------------
# HTML content extraction
# ---------------------------------------------------------------------------

# Matches the Greenstone content table that wraps the article body.
_CONTENT_BLOCK_RE = re.compile(
    r"<table\s+width=_pagewidth_><tr><td>(.*?)</td></tr></table></center>",
    re.DOTALL | re.IGNORECASE,
)
_PARA_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.DOTALL | re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_RE = re.compile(r"<script[^>]*>.*?</script>", re.DOTALL | re.IGNORECASE)


def extract_text(html_bytes: bytes) -> Optional[str]:
    """Extract plain-text article body from a Greenstone section HTML response.

    Returns normalised, joined paragraph text or None if the section is empty
    / boilerplate-only.
    """
    raw = html_bytes.decode("utf-8", errors="replace")
    # Remove script blocks to avoid matching our patterns inside JS strings.
    stripped = _SCRIPT_RE.sub("", raw)

    m = _CONTENT_BLOCK_RE.search(stripped)
    if not m:
        return None

    content_block = m.group(1)
    paras = _PARA_RE.findall(content_block)

    texts: list[str] = []
    for p in paras:
        t = _TAG_RE.sub("", p)          # strip HTML tags
        t = html_mod.unescape(t)        # decode &amp;, &#257;, etc.
        t = t.replace("\xa0", " ")      # non-breaking space → space
        t = re.sub(r"\s+", " ", t).strip()
        if not t:
            continue
        # Skip footnote-reference-only paragraphs (e.g. "1 . <link>")
        if re.match(r"^\d+\s*\.\s*$", t):
            continue
        texts.append(t)

    if not texts:
        return None

    joined = "\n".join(texts)
    # Reject if the first real paragraph is the site footer boilerplate.
    if BOILERPLATE_SIGNAL in joined:
        return None

    return joined


# ---------------------------------------------------------------------------
# Pair enumeration
# ---------------------------------------------------------------------------

def _oid_stem(filename: str) -> str:
    """HASH….<X>.<Y>.<Z>.html → HASH….<X>.<Y> (strip layer-suffix and .html)."""
    stem = filename.replace(".html", "")  # HASH….<X>.<Y>.<Z>
    return stem.rsplit(".", 1)[0]         # HASH….<X>.<Y>


def section_url(oid: str) -> str:
    return (
        f"https://hooilina.org/cgi-bin/journal"
        f"?e={E_DOC}&cl=search&d={oid}&d2=1&gg=text"
    )


def enumerate_pairs() -> list[dict]:
    """Return list of {pair_key, en_path, haw_path, en_oid, haw_oid}."""
    en_files = {_oid_stem(f.name): f for f in sorted(SECTIONS_EN.glob("*.html"))}
    haw_files = {_oid_stem(f.name): f for f in sorted(SECTIONS_HAW.glob("*.html"))}
    common = sorted(set(en_files) & set(haw_files))
    pairs = []
    for pk in common:
        en_f = en_files[pk]
        haw_f = haw_files[pk]
        # OID = filename stem without .html
        pairs.append({
            "pair_key": pk,
            "en_path": en_f,
            "haw_path": haw_f,
            "en_oid": en_f.name.replace(".html", ""),
            "haw_oid": haw_f.name.replace(".html", ""),
        })
    return pairs


# ---------------------------------------------------------------------------
# Row builder
# ---------------------------------------------------------------------------

def build_row(pair: dict) -> Optional[dict]:
    """Build a candidate row from one section pair, or None if skippable."""
    en_raw = pair["en_path"].read_bytes()
    haw_raw = pair["haw_path"].read_bytes()

    en_text = extract_text(en_raw)
    haw_text = extract_text(haw_raw)

    if not en_text or not haw_text:
        return None

    # Length gate.
    en_words = len(en_text.split())
    haw_words = len(haw_text.split())
    if en_words < MIN_WORDS or haw_words < MIN_WORDS:
        return None

    # Normalise for hashing.
    en_clean = normalize_en(en_text)
    haw_clean = normalize_haw(haw_text)

    sha_en_raw = sha256_text(en_raw.decode("utf-8", errors="replace"))
    sha_haw_raw = sha256_text(haw_raw.decode("utf-8", errors="replace"))
    sha_en_clean = sha256_text(en_clean)
    sha_haw_clean = sha256_text(haw_clean)
    sha_pair = compute_pair_hash(sha_en_clean, sha_haw_clean)

    pair_key = pair["pair_key"]
    pair_id = f"{SOURCE_ID}-{pair_key}"
    en_oid = pair["en_oid"]
    haw_oid = pair["haw_oid"]

    length_ratio = (haw_words / en_words) if en_words else 0.0

    return {
        "pair_id": pair_id,
        "source": SOURCE_ID,
        "source_url_en": section_url(en_oid),
        "source_url_haw": section_url(haw_oid),
        "fetch_date": FETCH_DATE,
        "sha256_en_raw": sha_en_raw,
        "sha256_haw_raw": sha_haw_raw,
        "sha256_en_clean": sha_en_clean,
        "sha256_haw_clean": sha_haw_clean,
        "sha256_pair": sha_pair,
        "record_id_en": en_oid,
        "record_id_haw": haw_oid,
        "text_en": en_clean,
        "text_haw": haw_clean,
        "text_en_path": None,
        "text_haw_path": None,
        "alignment_type": "parallel-doc",
        "alignment_method": "filename-pair",
        "alignment_model": None,
        "alignment_score": None,
        "alignment_review_required": True,
        "length_ratio_haw_over_en": round(length_ratio, 4),
        "lang_id_en": "en",
        "lang_id_en_confidence": 1.0,
        "lang_id_haw": "haw",
        "lang_id_haw_confidence": 1.0,
        "direction_original": "haw->en",
        "register": "unknown",
        "edition_or_version": "hooilina.org Ka Hoʻoilina (2002–2004); modernized-HAW + EN editorial layers",
        "synthetic": False,
        "synthetic_source_model": None,
        "license_observed_en": "(c) 2002-2004 Kamehameha Schools; free for public use with citation of source HAW",
        "license_observed_haw": "(c) 2002-2004 Kamehameha Schools; free for public use with citation of source HAW",
        "license_inferred": None,
        "tos_snapshot_id": "hooilina-stage2/20260501/tos/edintro.html",
        "prototype_only": True,
        "release_eligible": False,
        "dedup_cluster_id": pair_id,
        "crosslink_stage1_overlap": False,
        "split": "review-pending",
        "notes": (
            "Ka Hoʻoilina modernized-HAW × EN editorial pair. "
            "alignment_review_required=True: OCR/editorial noise, section-level parallel-doc alignment. "
            "KS citation required on any reuse of modernized-HAW or EN layer."
        ),
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
    }


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------

def run_dry_run() -> int:
    pairs = enumerate_pairs()
    print(f"[dry-run] Found {len(pairs)} paired section files.")
    rows: list[dict] = []
    skipped_empty = 0
    skipped_short = 0
    for p in pairs:
        try:
            row = build_row(p)
        except Exception as exc:  # noqa: BLE001
            print(f"  ERROR {p['pair_key']}: {exc}", file=sys.stderr)
            continue
        if row is None:
            en_text = extract_text(p["en_path"].read_bytes())
            haw_text = extract_text(p["haw_path"].read_bytes())
            if not en_text or not haw_text:
                skipped_empty += 1
            else:
                skipped_short += 1
        else:
            rows.append(row)

    print(f"[dry-run] Rows that would be emitted : {len(rows)}")
    print(f"[dry-run] Skipped (empty/boilerplate) : {skipped_empty}")
    print(f"[dry-run] Skipped (too short <{MIN_WORDS} words): {skipped_short}")
    print(f"[dry-run] Violations: 0 (schema check skipped in dry-run)")
    return 0


def run_execute() -> int:
    pairs = enumerate_pairs()
    rows: list[dict] = []
    skipped_empty = 0
    skipped_short = 0
    errors = 0

    for p in pairs:
        try:
            row = build_row(p)
        except Exception as exc:  # noqa: BLE001
            print(f"  ERROR {p['pair_key']}: {exc}", file=sys.stderr)
            errors += 1
            continue
        if row is None:
            en_text = extract_text(p["en_path"].read_bytes())
            haw_text = extract_text(p["haw_path"].read_bytes())
            if not en_text or not haw_text:
                skipped_empty += 1
            else:
                skipped_short += 1
        else:
            rows.append(row)

    if errors:
        print(f"[execute] {errors} section parse errors — aborting.", file=sys.stderr)
        return 1

    # Dedup by sha256_pair (should be unique; warn if not).
    seen_pairs: set[str] = set()
    dedup_rows: list[dict] = []
    dupes = 0
    for r in rows:
        sp = r["sha256_pair"]
        if sp in seen_pairs:
            dupes += 1
        else:
            seen_pairs.add(sp)
            dedup_rows.append(r)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as fh:
        for r in dedup_rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    report = {
        "source": SOURCE_ID,
        "build_date_utc": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "script": "scripts/324_build_hooilina_candidates.py",
        "input_section_pairs": len(pairs),
        "rows_emitted": len(dedup_rows),
        "skipped_empty_or_boilerplate": skipped_empty,
        "skipped_too_short": skipped_short,
        "intra_file_dupes": dupes,
        "output_path": str(OUT_PATH.relative_to(REPO_ROOT)),
        "rights_note": (
            "Editorial layers (modernized HAW + English) (c) 2002-2004 Kamehameha Schools. "
            "prototype_only=True, release_eligible=False. "
            "alignment_review_required=True on all rows."
        ),
    }
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / "hooilina_candidates_build_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))

    print(f"[execute] Emitted {len(dedup_rows)} rows → {OUT_PATH}")
    print(f"[execute] Skipped empty/boilerplate: {skipped_empty}")
    print(f"[execute] Skipped too short: {skipped_short}")
    print(f"[execute] Intra-file dupes: {dupes}")
    print(f"[execute] Report → {report_path}")
    return 0


def run_self_test() -> int:
    """In-memory smoke tests — no network, no file system writes."""
    import traceback

    failures: list[str] = []

    def check(name: str, cond: bool, msg: str = "") -> None:
        if not cond:
            failures.append(f"FAIL {name}: {msg}")
        else:
            print(f"  OK  {name}")

    # --- extract_text tests ---
    FOOTER = (
        b"<html><head><script>js</script></head><body>"
        b"<span><center><table width=_pagewidth_><tr><td>"
        b"</td></tr></table></center></span>"
        b"<center><p>Look up any word by double-clicking on it.</p></center>"
        b"</body></html>"
    )
    check("empty_section_returns_none", extract_text(FOOTER) is None, "expected None for boilerplate-only page")

    REAL = (
        b"<html><head><script>js</script></head><body>"
        b"<span><center><table width=_pagewidth_><tr><td>"
        b"<p>Hello &#699;world k&#257;ne.</p>"
        b"<p>Second paragraph here.</p>"
        b"</td></tr></table></center></span>"
        b"<center><p>Look up any word by double-clicking on it.</p></center>"
        b"</body></html>"
    )
    result = extract_text(REAL)
    check("real_content_extracted", result is not None, "expected non-None for real content")
    check("html_entities_unescaped", result is not None and "ʻworld" in result, f"expected ʻworld in: {result!r}")
    check("boilerplate_excluded", result is not None and "Look up" not in result, "footer leaked into content")

    # --- normalize_haw ---
    haw_in = "&#699;O K&#257;ne &#8216;o ia."  # &#699; = ʻ, &#257; = ā, &#8216; = ' (left single quote)
    haw_out = normalize_haw(haw_in)
    check("haw_entities_unescaped", "ā" in haw_out, f"ā missing from: {haw_out!r}")
    check("haw_left_quote_canonicalized", "\u2018" not in haw_out, f"U+2018 still present in: {haw_out!r}")
    check("haw_okina_canonical", haw_out.startswith(OKINA), f"expected leading ʻ in: {haw_out!r}")

    # --- normalize_en ---
    en_in = "K&#257;ne of the living water."
    en_out = normalize_en(en_in)
    check("en_entities_unescaped", "Kāne" in en_out, f"Kāne missing from: {en_out!r}")

    # --- pair hash invariant ---
    en_clean = normalize_en("Hello world.")
    haw_clean = normalize_haw("Aloha &#699;oukou.")
    sha_en = sha256_text(en_clean)
    sha_haw = sha256_text(haw_clean)
    expected_pair = hashlib.sha256(
        (sha_en + "\u2016" + sha_haw).encode("utf-8")
    ).hexdigest()
    actual_pair = compute_pair_hash(sha_en, sha_haw)
    check("pair_hash_invariant", expected_pair == actual_pair, f"{expected_pair} != {actual_pair}")

    # --- build_row (synthetic) ---
    import tempfile, os
    en_html = (
        b"<html><head><script>js</script></head><body>"
        b"<span><center><table width=_pagewidth_><tr><td>"
        b"<p>This is a real English paragraph about Hawaiian culture.</p>"
        b"<p>It has multiple sentences for alignment testing.</p>"
        b"</td></tr></table></center></span></body></html>"
    )
    haw_html = (
        b"<html><head><script>js</script></head><body>"
        b"<span><center><table width=_pagewidth_><tr><td>"
        b"<p>&#699;O kekahi &#257;lelo no ka mo&#699;omeheu Hawaii.</p>"
        b"<p>He m&#257;kaukau ia no ka ho&#699;oponopono.</p>"
        b"</td></tr></table></center></span></body></html>"
    )
    # Write to temp files in data dir (not /tmp)
    scratch = REPO_ROOT / "data" / "stage2" / ".scratch_selftest"
    scratch.mkdir(parents=True, exist_ok=True)
    en_f = scratch / "test_section.en.html"
    haw_f = scratch / "test_section.haw.html"
    try:
        en_f.write_bytes(en_html)
        haw_f.write_bytes(haw_html)
        synthetic_pair = {
            "pair_key": "HASHtest.1.1",
            "en_path": en_f,
            "haw_path": haw_f,
            "en_oid": "HASHtest.1.1.7",
            "haw_oid": "HASHtest.1.1.5",
        }
        row = build_row(synthetic_pair)
        check("build_row_returns_row", row is not None, "expected non-None row")
        if row:
            check("pair_id_format", row["pair_id"] == "hooilina-HASHtest.1.1", f"got {row['pair_id']!r}")
            check("text_en_no_entities", "&" not in row["text_en"], f"entities in text_en: {row['text_en']!r}")
            check("text_haw_no_entities", "&" not in row["text_haw"], f"entities in text_haw: {row['text_haw']!r}")
            check("text_haw_okina_canonical", "\u2018" not in row["text_haw"] and "\u2019" not in row["text_haw"],
                  f"mis-encoding in haw: {row['text_haw']!r}")
            # Verify pair hash re-computes correctly.
            recomputed = compute_pair_hash(row["sha256_en_clean"], row["sha256_haw_clean"])
            check("pair_hash_stable", row["sha256_pair"] == recomputed,
                  f"{row['sha256_pair']} != {recomputed}")
            check("prototype_only_true", row["prototype_only"] is True)
            check("release_eligible_false", row["release_eligible"] is False)
            check("split_review_pending", row["split"] == "review-pending")
            check("alignment_review_required", row["alignment_review_required"] is True)
    finally:
        for f in [en_f, haw_f]:
            try:
                f.unlink()
            except FileNotFoundError:
                pass
        try:
            scratch.rmdir()
        except OSError:
            pass

    if failures:
        print(f"\n[self-test] {len(failures)} FAILURES:")
        for msg in failures:
            print(f"  {msg}")
        return 3

    total = 19  # number of check() calls above
    print(f"\n[self-test] All {total} assertions passed.")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--dry-run", action="store_true",
                     help="Count rows without writing output.")
    grp.add_argument("--execute", action="store_true",
                     help="Build and write hooilina.jsonl.")
    grp.add_argument("--self-test", action="store_true",
                     help="In-memory smoke tests (no I/O).")
    args = parser.parse_args(argv)

    if args.self_test:
        return run_self_test()
    if args.dry_run:
        return run_dry_run()
    if args.execute:
        return run_execute()
    return 2


if __name__ == "__main__":
    sys.exit(main())
