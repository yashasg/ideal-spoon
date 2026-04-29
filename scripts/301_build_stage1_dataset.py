#!/usr/bin/env python3
"""Stage-1 dataset builder (prototype).

Consumes Frank-style provenance written by ``scripts/201_fetch_rightslight_raw.py``.
The fetcher's ledger lives at ``data/raw/{source}/fetch.jsonl`` (one row per
artefact), with raw bytes parked under ``data/raw/{source}/{YYYYMMDD}/{sha}.{ext}``.
A legacy nested layout (``data/raw/{source}/{fetch_date}/fetch.jsonl``) is
still supported for backward-compatibility with older fixtures.

Emits, under local-only ignored paths:

    data/extracted/{source}/{fetch_date}/extracted.jsonl.gz
    data/stage1/stage1_manifest.jsonl   (one row per surviving doc)
    data/stage1/stage1.jsonl.gz         (trainer-facing fields only)

Two extractors are wired up:

  * ``wiki-xml-stream`` — Wikimedia ``<mediawiki>`` XML dumps (used by
    ``hawwiki`` / ``hawwiktionary``). Streams pages out of the bz2/gz/raw
    XML artefact written by ``201_fetch_rightslight_raw.py``.
  * ``wikisource-pagetext`` — per-page Hawaiian Wikisource records written
    by the dedicated Wikisource fetcher (sibling of 201, e.g.
    ``202_fetch_hawwikisource_raw.py``). Each ``fetch.jsonl`` row points
    at a per-page artefact under
    ``data/raw/hawwikisource/<YYYYMMDD>/<sha>.<ext>`` with one of the
    supported shapes:

      - plain text (``.txt`` / ``content_type: text/plain``),
      - raw wikitext (``.wiki`` / ``.wikitext`` / ``content_type:
        text/x-wiki``) — run through the same crude de-wiki + ʻokina
        normalization as the dump path,
      - per-page MediaWiki API JSON (``.json`` ``action=parse`` or
        ``action=query&prop=revisions`` payload),
      - bundled NDJSON (``.jsonl`` / ``.jsonl.gz`` / ``.ndjson`` /
        ``content_type: application/x-ndjson``) where each line is
        ``{"page_id":..., "title":..., "wikitext"|"text": ...}``.

Other content types are recorded as ``skipped`` with a reason so the
manifest stays honest. No corpus text is ever written into the repo —
outputs all sit under ``data/`` which is gitignored.

Design notes (durable, see decisions inbox):
  * Stdlib only. JSONL manifest first; Parquet is a separate follow-up that
    can read this manifest 1:1 once ``pyarrow`` is justified.
  * Quality gates are *fail-conservative*: a record missing license_observed,
    raw path, or sha256_raw is skipped with a recorded reason, not silently
    dropped or guessed.
  * Splits are deterministic: ``sha256_clean`` -> SHA-256 -> int -> mod 100.
    Stable across reruns; no RNG state to track.
  * Hawaiian-ish heuristic is intentionally *placeholder*: kahakō/ʻokina
    presence is a positive signal, ASCII-only Latin text is downgraded.
    Real LID wires in later; this only exists to flag obvious junk.

Usage:
    python scripts/301_build_stage1_dataset.py --dry-run
    python scripts/301_build_stage1_dataset.py --source hawwiki --limit 5
    python scripts/301_build_stage1_dataset.py --strict
    python scripts/301_build_stage1_dataset.py --show-targets

Exit codes:
    0 success (incl. dry-run)
    1 I/O / schema error
    2 strict-mode quality gate failure (incl. token-volume gate below
      conservative right-clearable target)
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import sys
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = REPO_ROOT / "data" / "raw"
DATA_EXTRACTED = REPO_ROOT / "data" / "extracted"
DATA_STAGE1 = REPO_ROOT / "data" / "stage1"

# Deterministic split bands on hash(sha256_clean) % 100.
SPLIT_BANDS = [("train", 0, 90), ("dev", 90, 95), ("test", 95, 100)]

# Source share warning thresholds (token-share). Stage-1 ADR caps Bible-like
# religious/archaic at <=10%; we just warn here and let release gating bite.
SOURCE_SHARE_WARN = 0.60       # any single source above 60% of tokens
BAIBALA_TOKEN_CAP = 0.10       # placeholder cap; no Bible source in slice yet

# Stage-1 train-token volume targets (right-clearable monolingual Hawaiian).
# Numbers track docs/data-pipeline.md and the Stage-1 planning ADR.
# Conservative is the honest go/no-go gate for kicking off DAPT.
TOKEN_TARGETS: dict[str, int] = {
    "conservative": 2_500_000,
    "base": 4_500_000,
    "upside": 7_000_000,
}
DEFAULT_TOKEN_TARGET = "conservative"

# Wikimedia "mediawiki" XML namespaces vary by dump version. Strip them.
_WIKI_NS_PREFIX_RE_TAGS = ("page", "title", "ns", "id", "revision", "text")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha256_text(t: str) -> str:
    return _sha256_bytes(t.encode("utf-8"))


# ---------- Provenance loader ----------

@dataclass
class FetchRecord:
    source: str
    fetch_date: str
    raw_path: Path
    source_url: str
    http_status: int | None
    sha256_raw: str | None
    content_type: str | None
    license_observed: str | None
    tos_snapshot_id: str | None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def doc_seed(self) -> str:
        # Pre-clean stable id; refined to sha256_clean once we have text.
        return f"{self.source}::{self.sha256_raw or self.raw_path.name}"


def _coerce_record(
    obj: dict[str, Any],
    source_dir_name: str,
    manifest_path: Path,
) -> FetchRecord:
    """Map an on-disk JSONL row to FetchRecord, accommodating both 201's
    actual schema (ProvenanceRecord: raw_sha256, raw_storage_path,
    tos_or_license_url, fetch_timestamp_utc) and the older expected
    schema (sha256_raw, path/raw_path/filename, tos_snapshot_id).
    """
    sha256_raw = obj.get("sha256_raw") or obj.get("raw_sha256")

    # Resolve raw artefact path. 201 writes ``raw_storage_path`` relative to
    # REPO_ROOT; older fixtures may use ``path``/``raw_path``/``filename``
    # relative to the manifest's directory.
    raw_storage = obj.get("raw_storage_path")
    if raw_storage:
        p = Path(raw_storage)
        raw_path = p if p.is_absolute() else (REPO_ROOT / p)
    else:
        rel = obj.get("path") or obj.get("raw_path") or obj.get("filename") or ""
        if rel:
            p = Path(rel)
            raw_path = p if p.is_absolute() else (manifest_path.parent / p).resolve()
        else:
            raw_path = manifest_path.parent

    # Derive fetch_date: explicit field, else parent dir of raw artefact
    # (201 stores under data/raw/<source>/<YYYYMMDD>/), else timestamp.
    fetch_date = obj.get("fetch_date")
    if not fetch_date:
        try:
            parent = raw_path.parent.name
            if parent.isdigit() and len(parent) == 8:
                fetch_date = parent
        except Exception:
            pass
    if not fetch_date:
        ts = obj.get("fetch_timestamp_utc") or ""
        if len(ts) >= 10 and ts[4] == "-" and ts[7] == "-":
            fetch_date = ts[:10].replace("-", "")
    if not fetch_date:
        fetch_date = "unknown"

    tos = obj.get("tos_snapshot_id") or obj.get("tos_or_license_url")

    consumed = {
        "path", "raw_path", "filename", "raw_storage_path",
        "source_url", "http_status", "sha256_raw", "raw_sha256",
        "content_type", "license_observed", "tos_snapshot_id",
        "tos_or_license_url", "fetch_date", "fetch_timestamp_utc",
    }
    return FetchRecord(
        source=source_dir_name,
        fetch_date=fetch_date,
        raw_path=raw_path,
        source_url=obj.get("source_url", ""),
        http_status=obj.get("http_status"),
        sha256_raw=sha256_raw,
        content_type=obj.get("content_type"),
        license_observed=obj.get("license_observed"),
        tos_snapshot_id=tos,
        extra={k: v for k, v in obj.items() if k not in consumed},
    )


def _iter_manifest_paths(source_dir: Path) -> Iterator[Path]:
    """Yield fetch.jsonl manifest paths for one source dir.

    201 writes ``data/raw/<source>/fetch.jsonl`` (source-level). Older
    fixtures sometimes put one under each ``<fetch_date>/`` subdir; we
    accept both so a partial migration doesn't break the build.
    """
    top = source_dir / "fetch.jsonl"
    if top.exists():
        yield top
    for sub in sorted(source_dir.iterdir()):
        if not sub.is_dir():
            continue
        nested = sub / "fetch.jsonl"
        if nested.exists():
            yield nested


def iter_fetch_records(sources: list[str] | None) -> Iterator[FetchRecord]:
    """Walk ``data/raw/<source>/[<fetch_date>/]fetch.jsonl`` and yield records."""
    if not DATA_RAW.exists():
        return
    for source_dir in sorted(DATA_RAW.iterdir()):
        if not source_dir.is_dir():
            continue
        if sources and source_dir.name not in sources:
            continue
        for manifest in _iter_manifest_paths(source_dir):
            with manifest.open("r", encoding="utf-8") as fh:
                for ln, line in enumerate(fh, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError as e:
                        print(
                            f"warn: {manifest}:{ln} bad JSON ({e}); skipping",
                            file=sys.stderr,
                        )
                        continue
                    yield _coerce_record(obj, source_dir.name, manifest)


# ---------- Wiki XML extractor ----------

def _strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def extract_wiki_pages(xml_fh) -> Iterator[tuple[str, str, str]]:
    """Yield (page_id, title, wikitext) from a Wikimedia <mediawiki> dump.

    Streaming via iterparse so we don't load multi-GB dumps. We do *not*
    attempt to clean wiki markup beyond a couple of obvious strips; that's
    a downstream concern and gets its own pass once we settle on a parser.
    """
    context = ET.iterparse(xml_fh, events=("end",))
    page_id = title = text = None
    in_revision = False
    for _ev, elem in context:
        tag = _strip_ns(elem.tag)
        if tag == "title":
            title = elem.text or ""
        elif tag == "revision":
            in_revision = False
        elif tag == "id" and not in_revision and page_id is None:
            page_id = elem.text or ""
        elif tag == "text":
            text = elem.text or ""
        elif tag == "page":
            if title and text is not None:
                yield (page_id or "", title, text)
            page_id = title = text = None
            elem.clear()


# ---------- Wikisource page-text extractor ----------
#
# Contract (see decisions/inbox/linus-wikisource-handoff.md):
#   The Wikisource fetcher writes one ProvenanceRecord row per artefact to
#   ``data/raw/hawwikisource/fetch.jsonl``. Each row's ``raw_storage_path``
#   points at *either* a single per-page file (.txt / .wiki / .wikitext /
#   .json) *or* a bundled NDJSON file (.jsonl / .jsonl.gz / .ndjson) of
#   many pages. Per-page identifiers (page_id, title, revision_id,
#   namespace) ride in ``source_specific_ids`` on the provenance row for
#   single-page artefacts, and inline on each NDJSON line for bundles.
#
# Output shape matches ``extract_wiki_pages``: (page_id, title, body,
# is_wikitext). ``is_wikitext`` decides whether to run ``_crude_dewiki``
# before normalization.

_WIKITEXT_EXTS = (".wiki", ".wikitext")
_PLAINTEXT_EXTS = (".txt",)
_BUNDLE_EXTS = (".jsonl", ".jsonl.gz", ".ndjson")


def _open_text_artefact(path: Path):
    """Open .txt/.wiki/.wikitext/.json/.jsonl[.gz]/.ndjson as a text stream."""
    name = path.name.lower()
    if name.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    if name.endswith(".bz2"):
        import bz2
        return bz2.open(path, "rt", encoding="utf-8", errors="replace")
    return path.open("r", encoding="utf-8", errors="replace")


def _coerce_page_dict(obj: dict[str, Any]) -> tuple[str, str, str, bool] | None:
    """Best-effort map of a page-shaped dict to (page_id, title, body, is_wikitext).

    Accepts:
      * Plain shape: {"page_id"|"pageid"|"id", "title", "wikitext"|"text"|"body"}
      * MediaWiki action=parse: {"parse": {"pageid", "title", "wikitext": {"*": ...}}}
      * MediaWiki action=query revisions: {"query": {"pages": {"<id>": {
          "pageid", "title", "revisions": [{"slots": {"main": {"*"|"content": ...}}}]}}}}
    """
    parse = obj.get("parse")
    if isinstance(parse, dict):
        wt = parse.get("wikitext")
        body = wt.get("*") if isinstance(wt, dict) else (wt if isinstance(wt, str) else "")
        if body:
            return (
                str(parse.get("pageid", "") or ""),
                str(parse.get("title", "") or ""),
                body,
                True,
            )

    query = obj.get("query")
    if isinstance(query, dict):
        pages = query.get("pages") or {}
        if isinstance(pages, dict):
            page_iter: Iterable[dict] = pages.values()
        else:
            page_iter = pages if isinstance(pages, list) else []
        for page in page_iter:
            if not isinstance(page, dict):
                continue
            revs = page.get("revisions") or []
            if not revs:
                continue
            rev = revs[0]
            slots = rev.get("slots") or {}
            main = slots.get("main") if isinstance(slots, dict) else None
            body = ""
            if isinstance(main, dict):
                body = main.get("*") or main.get("content") or ""
            if not body:
                body = rev.get("*") or rev.get("content") or ""
            if body:
                return (
                    str(page.get("pageid", "") or ""),
                    str(page.get("title", "") or ""),
                    body,
                    True,
                )

    body = obj.get("wikitext") or obj.get("text") or obj.get("body") or ""
    if not body:
        return None
    is_wikitext = "wikitext" in obj or obj.get("format") == "wikitext"
    page_id = str(obj.get("page_id") or obj.get("pageid") or obj.get("id") or "")
    title = str(obj.get("title") or "")
    return (page_id, title, body, is_wikitext)


def extract_wikisource_pages(
    rec: "FetchRecord",
) -> Iterator[tuple[str, str, str, bool]]:
    """Yield (page_id, title, body, is_wikitext) for one Wikisource artefact.

    Single-page artefacts yield exactly one tuple; bundled NDJSON yields
    one tuple per line. The caller normalizes / scores / splits each.
    """
    path = rec.raw_path
    name = path.name.lower()
    ssids = (rec.extra.get("source_specific_ids") or {}) if isinstance(rec.extra, dict) else {}
    rec_page_id = str(ssids.get("page_id") or ssids.get("pageid") or "")
    rec_title = str(ssids.get("title") or "")

    is_bundle = any(name.endswith(ext) for ext in _BUNDLE_EXTS) or name.endswith(".ndjson.gz")
    is_json = name.endswith(".json")
    is_wikitext = any(name.endswith(ext) for ext in _WIKITEXT_EXTS)
    is_plaintext = any(name.endswith(ext) for ext in _PLAINTEXT_EXTS)

    if is_bundle:
        with _open_text_artefact(path) as fh:
            for ln, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as e:
                    print(f"warn: {path}:{ln} bad NDJSON ({e}); skipping", file=sys.stderr)
                    continue
                coerced = _coerce_page_dict(obj) if isinstance(obj, dict) else None
                if coerced is None:
                    continue
                yield coerced
        return

    if is_json:
        with _open_text_artefact(path) as fh:
            try:
                obj = json.load(fh)
            except json.JSONDecodeError as e:
                print(f"warn: {path}: bad JSON ({e}); skipping", file=sys.stderr)
                return
        if isinstance(obj, dict):
            coerced = _coerce_page_dict(obj)
            if coerced is not None:
                pid, title, body, is_wt = coerced
                yield (pid or rec_page_id, title or rec_title, body, is_wt)
        return

    if is_wikitext or is_plaintext:
        with _open_text_artefact(path) as fh:
            body = fh.read()
        if body.strip():
            yield (rec_page_id, rec_title, body, is_wikitext)
        return

    # Unknown extension: caller already gated on this; nothing to yield.
    return


def _crude_dewiki(text: str) -> str:
    # Prototype-grade only: strip refs, templates outermost, html-ish tags,
    # link pipes. Real cleanup is a separate task.
    import re
    text = re.sub(r"<ref[^>]*?/>", "", text, flags=re.S)
    text = re.sub(r"<ref[^>]*?>.*?</ref>", "", text, flags=re.S)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    # remove templates non-greedily, repeated until stable
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r"\{\{[^{}]*\}\}", "", text, flags=re.S)
    # [[link|display]] -> display ; [[link]] -> link
    text = re.sub(r"\[\[([^\]\|]+)\|([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"'''?", "", text)
    return text.strip()


# ---------- Normalization ----------

# U+2018 / U+2019 / U+0027 / U+02BC are common ʻokina mis-encodings.
_OKINA_VARIANTS = ("\u2018", "\u2019", "\u02BC", "\u0060")

def normalize_hawaiian(text: str) -> tuple[str, dict[str, int]]:
    """NFC + ʻokina canonicalization to U+02BB. Kahakō untouched.

    We only swap a curly/back apostrophe to ʻ when it sits between two
    Latin letters, which is the conservative "looks like ʻokina" context.
    A standalone ASCII apostrophe in English-quoted boilerplate is left
    alone; a downstream pass can refine this once we have LID per-paragraph.
    """
    counts: dict[str, int] = Counter()
    text = unicodedata.normalize("NFC", text)
    out: list[str] = []
    for i, ch in enumerate(text):
        if ch in _OKINA_VARIANTS:
            prev_c = text[i - 1] if i > 0 else ""
            next_c = text[i + 1] if i + 1 < len(text) else ""
            if prev_c.isalpha() and next_c.isalpha():
                out.append("\u02BB")
                counts["okina_canonicalized"] += 1
                continue
        out.append(ch)
    return unicodedata.normalize("NFC", "".join(out)), dict(counts)


# ---------- Heuristic LID placeholder ----------

_HAWAIIAN_VOWELS = set("aeiouāēīōūAEIOUĀĒĪŌŪ")
_KAHAKO = set("āēīōūĀĒĪŌŪ")

def hawaiian_score(text: str) -> tuple[float, str]:
    """Cheap, fail-conservative heuristic. Real LID lands later.

    Returns (confidence_in_haw, reason). Reason is set when we *fail* the
    heuristic so the manifest can record why.
    """
    if not text:
        return 0.0, "empty"
    sample = text[:4000]
    letters = [c for c in sample if c.isalpha()]
    if not letters:
        return 0.0, "no_letters"
    n = len(letters)
    vowel_share = sum(c in _HAWAIIAN_VOWELS for c in letters) / n
    kahako_present = any(c in _KAHAKO for c in sample)
    okina_present = "\u02BB" in sample
    consonants = {c.lower() for c in letters if not c.isspace()} - {"a", "e", "i", "o", "u", "ā", "ē", "ī", "ō", "ū"}
    foreign = consonants - set("hklmnpw")
    if vowel_share < 0.40:
        return 0.2, f"vowel_share_low={vowel_share:.2f}"
    score = vowel_share
    if kahako_present:
        score = min(1.0, score + 0.15)
    if okina_present:
        score = min(1.0, score + 0.10)
    if foreign:
        score *= 0.7
    if score < 0.55:
        return score, f"score_below_threshold={score:.2f}"
    return score, ""


# ---------- Split assignment ----------

def assign_split(sha256_clean: str) -> str:
    n = int(hashlib.sha256(sha256_clean.encode("ascii")).hexdigest()[:8], 16) % 100
    for name, lo, hi in SPLIT_BANDS:
        if lo <= n < hi:
            return name
    return "train"


# ---------- Pipeline ----------

@dataclass
class Skip:
    reason: str
    record: FetchRecord


def process_record(rec: FetchRecord, limit_pages: int | None) -> tuple[list[dict], list[Skip]]:
    docs: list[dict] = []
    skips: list[Skip] = []

    if not rec.license_observed:
        skips.append(Skip("missing_license_observed", rec))
        return docs, skips
    if not rec.sha256_raw:
        skips.append(Skip("missing_sha256_raw", rec))
        return docs, skips
    if not rec.raw_path or not rec.raw_path.exists():
        skips.append(Skip(f"missing_raw_path:{rec.raw_path}", rec))
        return docs, skips

    ct = (rec.content_type or "").lower()
    name = rec.raw_path.name.lower()
    is_wiki_xml = (
        "xml" in ct
        or name.endswith(".xml")
        or name.endswith(".xml.bz2")
        or name.endswith(".xml.gz")
        or "pages-articles" in name
    )
    is_wikisource_pagetext = (
        not is_wiki_xml
        and (
            rec.source == "hawwikisource"
            or ct.startswith("text/x-wiki")
            or ct == "application/x-ndjson"
        )
        and (
            ct.startswith("text/")
            or ct in ("application/json", "application/x-ndjson")
            or name.endswith(_PLAINTEXT_EXTS)
            or name.endswith(_WIKITEXT_EXTS)
            or name.endswith(_BUNDLE_EXTS)
            or name.endswith(".json")
            or name.endswith(".ndjson.gz")
        )
    )

    if is_wiki_xml:
        extraction_method = "wiki-xml-stream"
        if name.endswith(".bz2"):
            import bz2
            fh = bz2.open(rec.raw_path, "rb")
        elif name.endswith(".gz"):
            fh = gzip.open(rec.raw_path, "rb")
        else:
            fh = rec.raw_path.open("rb")
        try:
            pages: Iterable[tuple[str, str, str, bool]] = (
                (pid, title, wt, True) for pid, title, wt in extract_wiki_pages(fh)
            )
            return _emit_pages(rec, pages, extraction_method, limit_pages, skips, docs)
        finally:
            fh.close()

    if is_wikisource_pagetext:
        extraction_method = "wikisource-pagetext"
        return _emit_pages(
            rec,
            extract_wikisource_pages(rec),
            extraction_method,
            limit_pages,
            skips,
            docs,
        )

    skips.append(Skip(f"unsupported_content_type:{rec.content_type}", rec))
    return docs, skips


def _emit_pages(
    rec: FetchRecord,
    pages: Iterable[tuple[str, str, str, bool]],
    extraction_method: str,
    limit_pages: int | None,
    skips: list["Skip"],
    docs: list[dict],
) -> tuple[list[dict], list["Skip"]]:
    for page_id, title, raw_body, is_wikitext in pages:
        if limit_pages is not None and len(docs) >= limit_pages:
            break
        if not raw_body:
            continue
        cleaned = _crude_dewiki(raw_body) if is_wikitext else raw_body.strip()
        if not cleaned:
            continue
        normalized, norm_counts = normalize_hawaiian(cleaned)
        sha_clean = _sha256_text(normalized)
        score, why = hawaiian_score(normalized)
        doc = {
            "doc_id": f"{rec.source}::{page_id or sha_clean[:12]}",
            "source": rec.source,
            "source_url": rec.source_url,
            "fetch_date": rec.fetch_date,
            "fetch_http_status": rec.http_status,
            "sha256_raw": rec.sha256_raw,
            "sha256_clean": sha_clean,
            "content_type": rec.content_type,
            "extraction_method": extraction_method,
            "ocr_confidence_mean": None,
            "language_id": "haw" if not why else "unknown",
            "language_id_confidence": round(score, 4),
            "language_id_reason": why,
            "char_count": len(normalized),
            "token_count_est": max(1, len(normalized.split())),
            "unicode_normalized": True,
            "unicode_changes": norm_counts,
            "register_tag": "encyclopedic" if rec.source.startswith("hawwiki") else "unknown",
            "cultural_flag": "none",
            "dedup_cluster_id": sha_clean,  # placeholder; MinHash is its own pass
            "split": assign_split(sha_clean),
            "license_observed": rec.license_observed,
            "license_inferred": None,
            "tos_snapshot_id": rec.tos_snapshot_id,
            "prototype_only": True,
            "release_eligible": False,
            "title": title,
            "text": normalized,
            "notes": "",
        }
        docs.append(doc)
    return docs, skips


def compute_train_tokens(docs: list[dict]) -> int:
    """Sum estimated tokens for trainer-eligible rows: split=train, lang=haw."""
    return sum(
        int(d.get("token_count_est") or 0)
        for d in docs
        if d.get("split") == "train" and d.get("language_id") == "haw"
    )


def token_volume_report(docs: list[dict], target_name: str) -> dict[str, Any]:
    """Build a report comparing current train tokens to Stage-1 targets."""
    train_tokens = compute_train_tokens(docs)
    target = TOKEN_TARGETS[target_name]
    gap = max(0, target - train_tokens)
    pct = (train_tokens / target) if target else 0.0
    return {
        "train_tokens_est": train_tokens,
        "target_name": target_name,
        "target_tokens": target,
        "gap_to_target": gap,
        "pct_of_target": round(pct, 4),
        "all_targets": dict(TOKEN_TARGETS),
        "below_conservative": train_tokens < TOKEN_TARGETS["conservative"],
    }


def quality_gates(
    docs: list[dict],
    strict: bool,
    token_target: str = DEFAULT_TOKEN_TARGET,
) -> list[str]:
    """Return list of failures; strict mode escalates to non-zero exit."""
    failures: list[str] = []

    train = {d["sha256_clean"] for d in docs if d["split"] == "train"}
    eval_ = {d["sha256_clean"] for d in docs if d["split"] in ("dev", "test")}
    overlap = train & eval_
    if overlap:
        failures.append(f"train_eval_overlap:{len(overlap)}")

    by_source_tokens: Counter = Counter()
    for d in docs:
        by_source_tokens[d["source"]] += d["token_count_est"]
    total = sum(by_source_tokens.values()) or 1
    for src, toks in by_source_tokens.items():
        share = toks / total
        if share > SOURCE_SHARE_WARN:
            failures.append(f"source_share_warn:{src}={share:.2f}")
        if "bible" in src.lower() or "baibala" in src.lower():
            if share > BAIBALA_TOKEN_CAP:
                failures.append(f"baibala_cap_exceeded:{src}={share:.2f}")

    for d in docs:
        if not d.get("sha256_clean"):
            failures.append(f"missing_sha_clean:{d.get('doc_id')}")
        if not d.get("license_observed"):
            failures.append(f"missing_license:{d.get('doc_id')}")

    # Stage-1 train-token volume gate. Conservative target is the honest
    # go/no-go for kicking off DAPT; below that we should not pretend
    # Stage-1 is ready, regardless of pipeline mechanics being green.
    train_tokens = compute_train_tokens(docs)
    conservative = TOKEN_TARGETS["conservative"]
    if train_tokens < conservative:
        failures.append(
            f"token_volume_below_conservative:"
            f"have={train_tokens},need>={conservative},"
            f"gap={conservative - train_tokens}"
        )
    target_n = TOKEN_TARGETS.get(token_target, conservative)
    if token_target != "conservative" and train_tokens < target_n:
        failures.append(
            f"token_volume_below_{token_target}:"
            f"have={train_tokens},target={target_n},"
            f"gap={target_n - train_tokens}"
        )

    return failures


# ---------- Writers ----------

MANIFEST_FIELDS = [
    "doc_id", "source", "source_url", "fetch_date", "fetch_http_status",
    "sha256_raw", "sha256_clean", "content_type", "extraction_method",
    "ocr_confidence_mean", "language_id", "language_id_confidence",
    "language_id_reason", "char_count", "token_count_est",
    "unicode_normalized", "unicode_changes", "register_tag",
    "cultural_flag", "dedup_cluster_id", "split", "license_observed",
    "license_inferred", "tos_snapshot_id", "prototype_only",
    "release_eligible", "notes",
]
TRAINER_FIELDS = ["doc_id", "text", "source", "register_tag", "split", "prototype_only"]


def write_outputs(docs: list[dict], dry_run: bool) -> dict[str, str]:
    written: dict[str, str] = {}
    if dry_run:
        return written

    DATA_STAGE1.mkdir(parents=True, exist_ok=True)
    manifest_path = DATA_STAGE1 / "stage1_manifest.jsonl"
    train_path = DATA_STAGE1 / "stage1.jsonl.gz"

    with manifest_path.open("w", encoding="utf-8") as mfh:
        for d in docs:
            row = {k: d.get(k) for k in MANIFEST_FIELDS}
            mfh.write(json.dumps(row, ensure_ascii=False) + "\n")
    written["manifest"] = str(manifest_path)

    with gzip.open(train_path, "wt", encoding="utf-8") as tfh:
        for d in docs:
            if d["split"] != "train":
                continue
            if d.get("language_id") != "haw":
                continue
            row = {k: d.get(k if k != "register_tag" else "register_tag") for k in TRAINER_FIELDS}
            row["register"] = row.pop("register_tag")
            tfh.write(json.dumps(row, ensure_ascii=False) + "\n")
    written["train_jsonl_gz"] = str(train_path)

    # Per-(source,fetch_date) extracted dump for downstream re-use.
    by_bucket: dict[tuple[str, str], list[dict]] = {}
    for d in docs:
        by_bucket.setdefault((d["source"], d["fetch_date"]), []).append(d)
    for (src, fd), bucket in by_bucket.items():
        out_dir = DATA_EXTRACTED / src / fd
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / "extracted.jsonl.gz"
        with gzip.open(out, "wt", encoding="utf-8") as fh:
            for d in bucket:
                fh.write(json.dumps({
                    "doc_id": d["doc_id"],
                    "sha256_raw": d["sha256_raw"],
                    "sha256_clean": d["sha256_clean"],
                    "title": d.get("title"),
                    "text": d["text"],
                    "extraction_method": d["extraction_method"],
                    "source_url": d["source_url"],
                    "fetch_date": d["fetch_date"],
                }, ensure_ascii=False) + "\n")
        written[f"extracted::{src}/{fd}"] = str(out)
    return written


# ---------- CLI ----------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Build Stage-1 dataset from Frank-style provenance.")
    p.add_argument("--source", action="append", default=None,
                   help="Restrict to source dir name(s). Repeatable.")
    p.add_argument("--limit", type=int, default=None,
                   help="Cap pages per raw artifact (debug aid).")
    p.add_argument("--dry-run", action="store_true",
                   help="Run pipeline but do not write outputs.")
    p.add_argument("--strict", action="store_true",
                   help="Exit non-zero on any quality-gate failure (incl. "
                        "train-token volume below the conservative target).")
    p.add_argument("--token-target", choices=sorted(TOKEN_TARGETS.keys()),
                   default=DEFAULT_TOKEN_TARGET,
                   help="Stage-1 train-token target tier (default: conservative). "
                        "Reported in the summary; in --strict mode, falling "
                        "below the chosen tier (or below conservative) fails.")
    p.add_argument("--show-targets", action="store_true",
                   help="Print Stage-1 train-token targets and the current gap "
                        "(based on whatever raw data is on disk) and exit. "
                        "Does not require a corpus download.")
    args = p.parse_args(argv)

    if args.show_targets:
        # Cheap, no-corpus-needed view of where we stand vs targets.
        all_docs_preview: list[dict] = []
        try:
            for rec in iter_fetch_records(args.source):
                # Don't decode bytes; just project a placeholder doc so the
                # report has structure even when extraction hasn't run.
                all_docs_preview.append({
                    "split": "train",
                    "language_id": "haw" if rec.license_observed else "unknown",
                    "token_count_est": 0,
                    "source": rec.source,
                    "sha256_clean": rec.sha256_raw or "",
                })
        except Exception:
            pass
        report = token_volume_report(all_docs_preview, args.token_target)
        out = {
            "mode": "show-targets",
            "token_targets": dict(TOKEN_TARGETS),
            "selected_target": args.token_target,
            "current_train_tokens_est": report["train_tokens_est"],
            "gap_to_selected_target": report["gap_to_target"],
            "below_conservative": report["below_conservative"],
            "note": (
                "Token counts only become non-zero after extraction "
                "(run without --show-targets). Conservative target "
                f"= {TOKEN_TARGETS['conservative']:,} train tokens is the "
                "Stage-1 go/no-go gate; below this, --strict will exit 2."
            ),
        }
        json.dump(out, sys.stdout, ensure_ascii=False, indent=2, default=str)
        sys.stdout.write("\n")
        return 0

    started = _utcnow_iso()
    all_docs: list[dict] = []
    all_skips: list[Skip] = []
    seen_records = 0

    for rec in iter_fetch_records(args.source):
        seen_records += 1
        try:
            docs, skips = process_record(rec, args.limit)
        except Exception as e:  # noqa: BLE001
            all_skips.append(Skip(f"exception:{type(e).__name__}:{e}", rec))
            continue
        all_docs.extend(docs)
        all_skips.extend(skips)

    failures = quality_gates(all_docs, args.strict, args.token_target)
    written = write_outputs(all_docs, args.dry_run)
    tokens_report = token_volume_report(all_docs, args.token_target)

    summary = {
        "started_utc": started,
        "finished_utc": _utcnow_iso(),
        "fetch_records_seen": seen_records,
        "docs_emitted": len(all_docs),
        "docs_skipped": len(all_skips),
        "skip_reasons": Counter(s.reason.split(":", 1)[0] for s in all_skips),
        "split_counts": Counter(d["split"] for d in all_docs),
        "source_counts": Counter(d["source"] for d in all_docs),
        "token_volume": tokens_report,
        "quality_failures": failures,
        "outputs": written,
        "dry_run": args.dry_run,
        "strict": args.strict,
    }
    json.dump(summary, sys.stdout, ensure_ascii=False, indent=2, default=str)
    sys.stdout.write("\n")

    if tokens_report["below_conservative"]:
        print(
            f"warn: stage-1 train tokens (est) = "
            f"{tokens_report['train_tokens_est']:,} is below the conservative "
            f"right-clearable target of {TOKEN_TARGETS['conservative']:,}. "
            f"Gap = {TOKEN_TARGETS['conservative'] - tokens_report['train_tokens_est']:,} tokens. "
            "Stage-1 should not be declared ready until this is closed "
            "(do not patch by adding rights-heavy sources).",
            file=sys.stderr,
        )

    if seen_records == 0:
        print("note: no fetch.jsonl found under data/raw/. Frank's fetcher hasn't run yet, "
              "or no sources match --source filter.", file=sys.stderr)
    if args.strict and failures:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
