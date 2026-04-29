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
    data/stage1/token_target_report.json (token-volume gate report)
    data/stage1/fineweb2_haw/cleaning_report.json

Three extractors are wired up:

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
  * ``fineweb2-paragraph-regate`` — the accepted FineWeb-2 train JSONL
    emitted by ``310_split_dedupe_fineweb2_haw.py``. The fetcher/splitter keep
    raw rows; this pass does paragraph-level language re-gating, boilerplate
    removal, Unicode/diacritic reporting, and raw-vs-clean token counts.

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
    python scripts/301_build_stage1_dataset.py --print-schema

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
import re
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
TOKEN_REPORT_PATH = DATA_STAGE1 / "token_target_report.json"
FINEWEB2_STAGE1_DIR = DATA_STAGE1 / "fineweb2_haw"
FINEWEB2_STAGE1_TRAIN = FINEWEB2_STAGE1_DIR / "train.jsonl"
FINEWEB2_CLEANING_REPORT_PATH = FINEWEB2_STAGE1_DIR / "cleaning_report.json"

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
STAGE1_MANIFEST_SCHEMA_VERSION = "stage1_manifest_jsonl_v1"

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
        if sources is not None and source_dir.name not in sources:
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
_OKINA_VARIANTS = ("\u2018", "\u2019", "\u02BC", "\u0060", "\u0027")
_HAWAIIAN_VOWELS = set("aeiouāēīōūAEIOUĀĒĪŌŪ")
_KAHAKO = set("āēīōūĀĒĪŌŪ")
_HAWAIIAN_ALPHA = _HAWAIIAN_VOWELS | set("hklmnpwHKLMNPW")
_OKINA_BOUNDARY_CHARS = set(" \t\r\n\"“”‘’([{<-/—–")


def _is_hawaiian_alpha(ch: str) -> bool:
    return ch in _HAWAIIAN_ALPHA

def normalize_hawaiian(text: str) -> tuple[str, dict[str, int]]:
    """NFC + ʻokina canonicalization to U+02BB. Kahakō untouched.

    We only swap apostrophe-like variants when the neighboring letters look
    Hawaiian, which avoids most English contractions while recovering common
    ``Hawai'i`` / ``'O`` spellings in FineWeb rows.
    """
    counts: dict[str, int] = Counter()
    text = unicodedata.normalize("NFC", text)
    out: list[str] = []
    for i, ch in enumerate(text):
        if ch in _OKINA_VARIANTS:
            prev_c = text[i - 1] if i > 0 else ""
            next_c = text[i + 1] if i + 1 < len(text) else ""
            if _is_hawaiian_alpha(next_c) and (
                _is_hawaiian_alpha(prev_c)
                or not prev_c
                or prev_c in _OKINA_BOUNDARY_CHARS
            ):
                out.append("\u02BB")
                counts["okina_canonicalized"] += 1
                counts[f"okina_variant_U+{ord(ch):04X}"] += 1
                continue
        out.append(ch)
    return unicodedata.normalize("NFC", "".join(out)), dict(counts)


# ---------- Heuristic LID placeholder ----------

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


# ---------- FineWeb-2 paragraph cleaning ----------

_FINEWEB2_MIN_PARAGRAPH_CHARS = 24
_FINEWEB2_MIN_PARAGRAPH_TOKENS = 4
_FINEWEB2_REPEAT_FINGERPRINT_MIN_CHARS = 80
_FINEWEB2_REPEAT_FINGERPRINT_MIN_TOKENS = 8
_CONTROL_CHARS_RE = re.compile(r"[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]")
_SPACE_RE = re.compile(r"[ \t\r\f\v]+")
_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.I)
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
_FINGERPRINT_DROP_RE = re.compile(
    r"https?://\S+|www\.\S+|\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b",
    re.I,
)
_FINGERPRINT_KEEP_RE = re.compile(r"[^0-9A-Za-zāēīōūĀĒĪŌŪʻ]+")
_FINEWEB2_BOILERPLATE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "boilerplate_timestamp",
        re.compile(
            r"^(for\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
            r"\b|^(posted|published|last updated|updated)\s*:",
            re.I,
        ),
    ),
    ("english_synopsis", re.compile(r"^synopsis\s*:", re.I)),
    (
        "navigation_menu",
        re.compile(
            r"^(home|menu|search|skip to content|previous|next|older posts|newer posts|"
            r"read more|continue reading|back to top|archives?|categories)\b",
            re.I,
        ),
    ),
    (
        "advertising_tracking",
        re.compile(
            r"\b(advertisement|advertising|sponsored|cookies?|privacy policy|terms of use|"
            r"subscribe|newsletter|share this|follow us|comments? (are )?closed|powered by|"
            r"all rights reserved|copyright)\b",
            re.I,
        ),
    ),
    (
        "social_widget",
        re.compile(r"^(facebook|twitter|instagram|youtube|rss|pinterest|tumblr|linkedin)\b", re.I),
    ),
)


def _token_count(text: str) -> int:
    return len(text.split())


def _reason_key(reason: str) -> str:
    return reason.split("=", 1)[0].split(":", 1)[0]


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _clean_spaces_and_controls(text: str) -> str:
    text = _CONTROL_CHARS_RE.sub(" ", text)
    lines = [_SPACE_RE.sub(" ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _split_paragraphs(text: str) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", stripped) if p.strip()]
    if len(paragraphs) <= 1:
        paragraphs = [p.strip() for p in stripped.splitlines() if p.strip()]
    return paragraphs


def _boilerplate_reason(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return "empty_after_normalization"
    for reason, pattern in _FINEWEB2_BOILERPLATE_PATTERNS:
        if pattern.search(stripped):
            return reason
    if len(stripped) <= 140 and sum(stripped.count(sep) for sep in ("|", "»", "›", "•", "·")) >= 3:
        return "navigation_separator_list"
    urls = _URL_RE.findall(stripped)
    emails = _EMAIL_RE.findall(stripped)
    if urls and (len(urls) >= 2 or sum(len(u) for u in urls) / max(1, len(stripped)) > 0.12):
        return "url_heavy"
    if emails:
        return "email_or_contact_boilerplate"
    letters = sum(ch.isalpha() for ch in stripped)
    if len(stripped) >= 40 and letters / max(1, len(stripped)) < 0.25:
        return "low_alpha_density"
    return ""


def _paragraph_fingerprint(text: str) -> str:
    folded = unicodedata.normalize("NFC", text).lower()
    folded = _FINGERPRINT_DROP_RE.sub(" ", folded)
    folded = _FINGERPRINT_KEEP_RE.sub(" ", folded)
    folded = " ".join(folded.split())
    if (
        len(folded) < _FINEWEB2_REPEAT_FINGERPRINT_MIN_CHARS
        or len(folded.split()) < _FINEWEB2_REPEAT_FINGERPRINT_MIN_TOKENS
    ):
        return ""
    return _sha256_text(folded)


def diacritic_profile(text: str) -> dict[str, Any]:
    tokens = _token_count(text)
    chars = len(text)
    okina = text.count("\u02BB")
    kahako = sum(ch in _KAHAKO for ch in text)
    combining_macron = text.count("\u0304")
    remaining_okina_variants = sum(text.count(ch) for ch in _OKINA_VARIANTS)
    diacritics = okina + kahako
    return {
        "okina_count": okina,
        "kahako_count": kahako,
        "combining_macron_count": combining_macron,
        "remaining_okina_variant_count": remaining_okina_variants,
        "diacritic_count": diacritics,
        "tokens": tokens,
        "chars": chars,
        "diacritics_per_token": round(diacritics / tokens, 6) if tokens else 0.0,
        "diacritics_per_100_chars": round((diacritics / chars) * 100, 6) if chars else 0.0,
    }


def _new_fineweb2_cleaning_report(path: Path) -> dict[str, Any]:
    return {
        "schema_version": "fineweb2_stage1_cleaning_report_v1",
        "generated_utc": None,
        "input_path": _display_path(path),
        "output_paths": {
            "stage1_manifest": "data/stage1/stage1_manifest.jsonl",
            "stage1_train_jsonl_gz": "data/stage1/stage1.jsonl.gz",
            "cleaning_report": "data/stage1/fineweb2_haw/cleaning_report.json",
        },
        "policy": {
            "normalization": "NFC; likely Hawaiian ʻokina variants canonicalized to U+02BB",
            "paragraph_language_gate": "hawaiian_score() per paragraph; reject paragraphs below threshold",
            "boilerplate_gate": "drop timestamp/synopsis/navigation/ad/social/url-heavy boilerplate paragraphs",
            "repeated_template_gate": "drop exact normalized paragraph fingerprints after first sighting",
            "near_duplicate_minhash_status": (
                "planned: build MinHash/LSH signatures over cleaned paragraphs/docs after "
                "hawwiki and hawwikisource cleaned manifests exist; any cluster touching "
                "eval/final remains held out"
            ),
        },
        "rows": {"seen": 0, "accepted": 0, "rejected": 0},
        "row_reject_reasons": Counter(),
        "paragraphs": {"seen": 0, "kept": 0, "rejected": 0},
        "paragraph_reject_reasons": Counter(),
        "tokens": {
            "raw_rows_seen": 0,
            "raw_rows_accepted": 0,
            "raw_rows_rejected": 0,
            "clean_rows_accepted": 0,
            "raw_paragraphs_seen": 0,
            "raw_paragraphs_kept": 0,
            "raw_paragraphs_rejected": 0,
            "clean_paragraphs_kept": 0,
        },
        "chars": {
            "raw_rows_seen": 0,
            "raw_rows_accepted": 0,
            "raw_rows_rejected": 0,
            "clean_rows_accepted": 0,
        },
        "unicode": Counter(),
        "diacritics": {
            "okina_count": 0,
            "kahako_count": 0,
            "diacritic_count": 0,
            "diacritics_per_token": 0.0,
            "diacritics_per_100_chars": 0.0,
        },
    }


class FineWeb2Cleaner:
    def __init__(self, input_path: Path) -> None:
        self.report = _new_fineweb2_cleaning_report(input_path)
        self._seen_paragraph_fingerprints: set[str] = set()

    def _reject_paragraph(self, reason: str, raw_para: str) -> None:
        reason = _reason_key(reason)
        raw_tokens = _token_count(raw_para)
        self.report["paragraphs"]["rejected"] += 1
        self.report["paragraph_reject_reasons"][reason] += 1
        self.report["tokens"]["raw_paragraphs_rejected"] += raw_tokens

    def _clean_paragraph(
        self,
        raw_para: str,
        row_fingerprints: set[str],
    ) -> tuple[str, str, dict[str, Any]]:
        raw_tokens = _token_count(raw_para)
        normalized, norm_counts = normalize_hawaiian(raw_para)
        cleaned = _clean_spaces_and_controls(normalized)
        clean_tokens = _token_count(cleaned)
        profile = diacritic_profile(cleaned)
        para_report = {
            "raw_token_count": raw_tokens,
            "clean_token_count": clean_tokens,
            "raw_char_count": len(raw_para),
            "clean_char_count": len(cleaned),
            "unicode_changes": norm_counts,
            "diacritic_profile": profile,
        }

        if norm_counts:
            self.report["unicode"].update(norm_counts)
        if raw_para.count("\u0304"):
            self.report["unicode"]["raw_combining_macron_seen"] += raw_para.count("\u0304")

        if not cleaned:
            return "", "empty_after_normalization", para_report
        if "\ufffd" in cleaned:
            return "", "unicode_replacement_char", para_report
        if "\u0304" in cleaned:
            return "", "kahako_not_precomposed_after_nfc", para_report
        if len(cleaned) < _FINEWEB2_MIN_PARAGRAPH_CHARS or clean_tokens < _FINEWEB2_MIN_PARAGRAPH_TOKENS:
            return "", "too_short", para_report

        boilerplate = _boilerplate_reason(cleaned)
        if boilerplate:
            return "", boilerplate, para_report

        score, why = hawaiian_score(cleaned)
        para_report["language_id_confidence"] = round(score, 4)
        if why:
            return "", f"paragraph_language_{_reason_key(why)}", para_report

        fp = _paragraph_fingerprint(cleaned)
        if fp:
            if fp in row_fingerprints:
                return "", "duplicate_paragraph_in_row", para_report
            if fp in self._seen_paragraph_fingerprints:
                return "", "repeated_template_exact", para_report
            row_fingerprints.add(fp)
            self._seen_paragraph_fingerprints.add(fp)

        return cleaned, "", para_report

    def clean_row(self, raw_text: str, raw_token_count: int) -> tuple[str, dict[str, Any], str]:
        self.report["rows"]["seen"] += 1
        self.report["tokens"]["raw_rows_seen"] += raw_token_count
        self.report["chars"]["raw_rows_seen"] += len(raw_text)

        raw_paragraphs = _split_paragraphs(raw_text)
        row_fingerprints: set[str] = set()
        row_reject_reasons: Counter = Counter()
        row_unicode: Counter = Counter()
        kept: list[str] = []
        raw_kept_tokens = 0

        for raw_para in raw_paragraphs:
            self.report["paragraphs"]["seen"] += 1
            self.report["tokens"]["raw_paragraphs_seen"] += _token_count(raw_para)
            cleaned, reject_reason, para_report = self._clean_paragraph(raw_para, row_fingerprints)
            row_unicode.update(para_report.get("unicode_changes") or {})
            if reject_reason:
                reason = _reason_key(reject_reason)
                row_reject_reasons[reason] += 1
                self._reject_paragraph(reason, raw_para)
                continue
            kept.append(cleaned)
            raw_kept_tokens += int(para_report["raw_token_count"])
            self.report["paragraphs"]["kept"] += 1
            self.report["tokens"]["raw_paragraphs_kept"] += int(para_report["raw_token_count"])
            self.report["tokens"]["clean_paragraphs_kept"] += int(para_report["clean_token_count"])

        cleaned_text = "\n\n".join(kept).strip()
        clean_tokens = _token_count(cleaned_text)
        row_profile = diacritic_profile(cleaned_text)
        row_report = {
            "raw_token_count": raw_token_count,
            "clean_token_count": clean_tokens,
            "raw_char_count": len(raw_text),
            "clean_char_count": len(cleaned_text),
            "raw_paragraph_count": len(raw_paragraphs),
            "kept_paragraph_count": len(kept),
            "rejected_paragraph_count": sum(row_reject_reasons.values()),
            "paragraph_reject_reasons": dict(sorted(row_reject_reasons.items())),
            "unicode_changes": dict(sorted(row_unicode.items())),
            "diacritic_profile": row_profile,
            "raw_kept_paragraph_token_count": raw_kept_tokens,
        }

        if not kept:
            reason = "all_paragraphs_rejected"
            if row_reject_reasons:
                reason = f"all_paragraphs_rejected__top_{row_reject_reasons.most_common(1)[0][0]}"
            self.report["rows"]["rejected"] += 1
            self.report["row_reject_reasons"][reason] += 1
            self.report["tokens"]["raw_rows_rejected"] += raw_token_count
            self.report["chars"]["raw_rows_rejected"] += len(raw_text)
            return "", row_report, reason

        row_score, row_why = hawaiian_score(cleaned_text)
        row_report["language_id_confidence"] = round(row_score, 4)
        if row_why:
            reason = f"row_language_{_reason_key(row_why)}"
            self.report["rows"]["rejected"] += 1
            self.report["row_reject_reasons"][reason] += 1
            self.report["tokens"]["raw_rows_rejected"] += raw_token_count
            self.report["chars"]["raw_rows_rejected"] += len(raw_text)
            return "", row_report, reason

        self.report["rows"]["accepted"] += 1
        self.report["tokens"]["raw_rows_accepted"] += raw_token_count
        self.report["tokens"]["clean_rows_accepted"] += clean_tokens
        self.report["chars"]["raw_rows_accepted"] += len(raw_text)
        self.report["chars"]["clean_rows_accepted"] += len(cleaned_text)
        for key in ("okina_count", "kahako_count", "diacritic_count"):
            self.report["diacritics"][key] += int(row_profile[key])
        return cleaned_text, row_report, ""

    def finalize(self) -> dict[str, Any]:
        self.report["generated_utc"] = _utcnow_iso()
        self.report["distinct_kept_paragraph_fingerprints"] = len(self._seen_paragraph_fingerprints)
        clean_tokens = int(self.report["tokens"]["clean_rows_accepted"])
        clean_chars = int(self.report["chars"]["clean_rows_accepted"])
        diacritics = int(self.report["diacritics"]["diacritic_count"])
        self.report["diacritics"]["diacritics_per_token"] = (
            round(diacritics / clean_tokens, 6) if clean_tokens else 0.0
        )
        self.report["diacritics"]["diacritics_per_100_chars"] = (
            round((diacritics / clean_chars) * 100, 6) if clean_chars else 0.0
        )
        return self.report


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


def _date_from_timestamp(ts: str | None) -> str:
    if ts and len(ts) >= 10 and ts[4] == "-" and ts[7] == "-":
        return ts[:10].replace("-", "")
    return "unknown"


def _fineweb2_synthetic_record(path: Path) -> FetchRecord:
    return FetchRecord(
        source="fineweb2_haw",
        fetch_date="unknown",
        raw_path=path,
        source_url="",
        http_status=None,
        sha256_raw=None,
        content_type="application/jsonl",
        license_observed=None,
        tos_snapshot_id=None,
        extra={},
    )


def process_fineweb2_stage1_jsonl(
    path: Path,
    limit_rows: int | None,
) -> tuple[list[dict], list[Skip], int, dict[str, Any]]:
    """Read the accepted FineWeb-2 Stage-1 train slice emitted by script 310.

    The raw FineWeb-2 fetch ledger has one provenance row per source row, but
    all rows point at split-level aggregate JSONL files. Reading that through
    ``process_record`` would re-open the 400MB train file once per row. Script
    310 owns the eval-dedupe split; 301 consumes its accepted train JSONL once.
    """
    docs: list[dict] = []
    skips: list[Skip] = []
    rows_seen = 0
    rec = _fineweb2_synthetic_record(path)
    cleaner = FineWeb2Cleaner(path)

    if not path.exists():
        if (DATA_RAW / "fineweb2_haw" / "fetch.jsonl").exists():
            skips.append(Skip("fineweb2_stage1_train_missing:run_310_split_dedupe", rec))
        elif any((DATA_RAW / "fineweb2_haw").glob("*/train.jsonl")):
            skips.append(Skip("fineweb2_stage1_train_missing:run_310_split_dedupe", rec))
        else:
            skips.append(Skip("fineweb2_raw_train_missing:run_205_fetch_train_then_310", rec))
        return docs, skips, rows_seen, cleaner.finalize()

    with path.open("r", encoding="utf-8") as fh:
        for ln, line in enumerate(fh, 1):
            if limit_rows is not None and rows_seen >= limit_rows:
                break
            line = line.strip()
            if not line:
                continue
            rows_seen += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError as e:
                skips.append(Skip(f"bad_fineweb2_json:{path}:{ln}:{e}", rec))
                continue
            raw_text = row.get("text")
            if not isinstance(raw_text, str) or not raw_text.strip():
                skips.append(Skip(f"fineweb2_missing_text:{path}:{ln}", rec))
                continue
            license_observed = row.get("license_observed")
            if not license_observed:
                skips.append(Skip(f"fineweb2_missing_license:{path}:{ln}", rec))
                continue

            try:
                raw_token_count = int(row.get("raw_whitespace_token_count") or _token_count(raw_text))
            except (TypeError, ValueError):
                raw_token_count = _token_count(raw_text)
            cleaned_text, cleaning_changes, row_reject_reason = cleaner.clean_row(
                raw_text.strip(),
                raw_token_count,
            )
            if row_reject_reason:
                skips.append(Skip(f"fineweb2_row_rejected:{row_reject_reason}:{path}:{ln}", rec))
                continue

            sha_clean = _sha256_text(cleaned_text)
            sha_raw = _sha256_text(raw_text)
            score = float(cleaning_changes.get("language_id_confidence") or hawaiian_score(cleaned_text)[0])
            row_id = str(row.get("fineweb2_row_id") or row.get("id") or sha_clean[:12])
            row_id = row_id.strip("<>")
            lang_score = row.get("language_score")
            notes = (
                "fineweb2_haw accepted train row from 310_split_dedupe; cleaned by "
                "301 fineweb2-paragraph-regate-v1; "
                f"source_language_config=haw_Latn; language_score={lang_score}; "
                f"raw_tokens={raw_token_count}; clean_tokens={cleaning_changes['clean_token_count']}"
            )
            doc = {
                "doc_id": f"fineweb2_haw::{row_id}",
                "source": "fineweb2_haw",
                "source_url": str(row.get("source_url") or ""),
                "fetch_date": _date_from_timestamp(row.get("fetched_at_utc")),
                "fetch_http_status": 200,
                "sha256_raw": sha_raw,
                "sha256_clean": sha_clean,
                "content_type": "text/plain; source=fineweb2_haw",
                "extraction_method": "fineweb2-paragraph-regate-v1",
                "ocr_confidence_mean": None,
                "language_id": "haw",
                "language_id_confidence": round(score, 4),
                "language_id_reason": "",
                "char_count": int(cleaning_changes["clean_char_count"]),
                "token_count_est": max(1, int(cleaning_changes["clean_token_count"])),
                "raw_char_count": int(cleaning_changes["raw_char_count"]),
                "raw_token_count_est": raw_token_count,
                "unicode_normalized": True,
                "unicode_changes": cleaning_changes.get("unicode_changes") or {},
                "cleaning_method": "fineweb2-paragraph-regate-v1",
                "cleaning_changes": cleaning_changes,
                "diacritic_profile": cleaning_changes.get("diacritic_profile") or {},
                "register_tag": "web",
                "cultural_flag": "none",
                "dedup_cluster_id": sha_clean,
                "split": assign_split(sha_clean),
                "license_observed": str(license_observed),
                "license_inferred": None,
                "tos_snapshot_id": row.get("tos_or_license_url"),
                "prototype_only": bool(row.get("prototype_only", True)),
                "release_eligible": bool(row.get("release_eligible", False)),
                "title": "",
                "text": cleaned_text,
                "notes": notes,
            }
            docs.append(doc)
    return docs, skips, rows_seen, cleaner.finalize()


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
        raw_token_count = _token_count(raw_body)
        clean_token_count = _token_count(normalized)
        profile = diacritic_profile(normalized)
        cleaning_method = (
            "crude-dewiki+normalize-v1" if is_wikitext else "plaintext-normalize-v1"
        )
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
            "token_count_est": max(1, clean_token_count),
            "raw_char_count": len(raw_body),
            "raw_token_count_est": raw_token_count,
            "unicode_normalized": True,
            "unicode_changes": norm_counts,
            "cleaning_method": cleaning_method,
            "cleaning_changes": {
                "raw_token_count": raw_token_count,
                "clean_token_count": clean_token_count,
                "raw_char_count": len(raw_body),
                "clean_char_count": len(normalized),
                "unicode_changes": norm_counts,
            },
            "diacritic_profile": profile,
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


def _raw_token_count_for_doc(doc: dict[str, Any]) -> int:
    return int(doc.get("raw_token_count_est") or doc.get("token_count_est") or 0)


def compute_raw_train_tokens(docs: list[dict]) -> int:
    return sum(
        _raw_token_count_for_doc(d)
        for d in docs
        if d.get("split") == "train" and d.get("language_id") == "haw"
    )


def token_volume_report(docs: list[dict], target_name: str) -> dict[str, Any]:
    """Build a report comparing current train tokens to Stage-1 targets."""
    train_tokens = compute_train_tokens(docs)
    raw_train_tokens = compute_raw_train_tokens(docs)
    target = TOKEN_TARGETS[target_name]
    gap = max(0, target - train_tokens)
    pct = (train_tokens / target) if target else 0.0
    return {
        "train_tokens_est": train_tokens,
        "raw_train_tokens_est": raw_train_tokens,
        "clean_train_tokens_est": train_tokens,
        "target_name": target_name,
        "target_tokens": target,
        "gap_to_target": gap,
        "pct_of_target": round(pct, 4),
        "all_targets": dict(TOKEN_TARGETS),
        "below_conservative": train_tokens < TOKEN_TARGETS["conservative"],
    }


def _token_summary_by_field(docs: list[dict], field: str) -> dict[str, dict[str, int]]:
    rows: Counter = Counter()
    raw_tokens: Counter = Counter()
    clean_tokens: Counter = Counter()
    for d in docs:
        key = str(d.get(field) or "unknown")
        rows[key] += 1
        raw_tokens[key] += _raw_token_count_for_doc(d)
        clean_tokens[key] += int(d.get("token_count_est") or 0)
    return {
        key: {
            "rows": int(rows[key]),
            "raw_tokens_est": int(raw_tokens[key]),
            "clean_tokens_est": int(clean_tokens[key]),
        }
        for key in sorted(rows)
    }


def _source_register_token_summary(docs: list[dict]) -> dict[str, dict[str, dict[str, int]]]:
    nested: dict[str, dict[str, dict[str, int]]] = {}
    for d in docs:
        source = str(d.get("source") or "unknown")
        register = str(d.get("register_tag") or "unknown")
        bucket = nested.setdefault(source, {}).setdefault(
            register,
            {"rows": 0, "raw_tokens_est": 0, "clean_tokens_est": 0},
        )
        bucket["rows"] += 1
        bucket["raw_tokens_est"] += _raw_token_count_for_doc(d)
        bucket["clean_tokens_est"] += int(d.get("token_count_est") or 0)
    return {
        source: {register: nested[source][register] for register in sorted(nested[source])}
        for source in sorted(nested)
    }


def token_report_payload(docs: list[dict], target_name: str) -> dict[str, Any]:
    """Report enough aggregate token stats to make go/no-go honest."""
    base = token_volume_report(docs, target_name)
    split_tokens: Counter = Counter()
    split_raw_tokens: Counter = Counter()
    source_tokens: Counter = Counter()
    source_raw_tokens: Counter = Counter()
    trainer_rows = 0
    for d in docs:
        toks = int(d.get("token_count_est") or 0)
        raw_toks = _raw_token_count_for_doc(d)
        split_tokens[d.get("split") or "unknown"] += toks
        split_raw_tokens[d.get("split") or "unknown"] += raw_toks
        source_tokens[d.get("source") or "unknown"] += toks
        source_raw_tokens[d.get("source") or "unknown"] += raw_toks
        if d.get("split") == "train" and d.get("language_id") == "haw":
            trainer_rows += 1
    return {
        "schema_version": "stage1_token_report_v1",
        "generated_utc": _utcnow_iso(),
        **base,
        "trainer_rows": trainer_rows,
        "docs_emitted": len(docs),
        "split_tokens_est": dict(sorted(split_tokens.items())),
        "split_raw_tokens_est": dict(sorted(split_raw_tokens.items())),
        "source_tokens_est": dict(sorted(source_tokens.items())),
        "source_raw_tokens_est": dict(sorted(source_raw_tokens.items())),
        "source_token_summary": _token_summary_by_field(docs, "source"),
        "register_token_summary": _token_summary_by_field(docs, "register_tag"),
        "source_register_token_summary": _source_register_token_summary(docs),
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


def dedupe_docs(docs: list[dict]) -> tuple[list[dict], int]:
    """Exact text de-duplication by sha256_clean; keep first deterministic row."""
    out: list[dict] = []
    seen: set[str] = set()
    removed = 0
    for d in docs:
        key = str(d.get("sha256_clean") or "")
        if key and key in seen:
            removed += 1
            continue
        if key:
            seen.add(key)
        out.append(d)
    return out, removed


def skip_detail_key(reason: str) -> str:
    parts = reason.split(":")
    if reason.startswith("fineweb2_row_rejected:") and len(parts) >= 2:
        return f"{parts[0]}:{parts[1]}"
    if reason.startswith("bad_fineweb2_json:"):
        return "bad_fineweb2_json"
    if reason.startswith("missing_raw_path:"):
        return "missing_raw_path"
    if reason.startswith("exception:") and len(parts) >= 2:
        return f"{parts[0]}:{parts[1]}"
    return parts[0]


# ---------- Writers ----------

MANIFEST_FIELDS = [
    "doc_id", "source", "source_url", "fetch_date", "fetch_http_status",
    "sha256_raw", "sha256_clean", "content_type", "extraction_method",
    "ocr_confidence_mean", "language_id", "language_id_confidence",
    "language_id_reason", "char_count", "token_count_est",
    "raw_char_count", "raw_token_count_est", "unicode_normalized",
    "unicode_changes", "cleaning_method", "cleaning_changes",
    "diacritic_profile", "register_tag",
    "cultural_flag", "dedup_cluster_id", "split", "license_observed",
    "license_inferred", "tos_snapshot_id", "prototype_only",
    "release_eligible", "notes",
]
TRAINER_FIELDS = ["doc_id", "text", "source", "register_tag", "split", "prototype_only"]


FIELD_TYPES: dict[str, str] = {
    "doc_id": "string",
    "source": "string",
    "source_url": "string",
    "fetch_date": "string",
    "fetch_http_status": "integer|null",
    "sha256_raw": "sha256",
    "sha256_clean": "sha256",
    "content_type": "string|null",
    "extraction_method": "string",
    "ocr_confidence_mean": "number|null",
    "language_id": "string",
    "language_id_confidence": "number",
    "language_id_reason": "string",
    "char_count": "integer",
    "token_count_est": "integer",
    "raw_char_count": "integer",
    "raw_token_count_est": "integer",
    "unicode_normalized": "boolean",
    "unicode_changes": "object",
    "cleaning_method": "string",
    "cleaning_changes": "object",
    "diacritic_profile": "object",
    "register_tag": "string",
    "cultural_flag": "string",
    "dedup_cluster_id": "string",
    "split": "string",
    "license_observed": "string",
    "license_inferred": "string|null",
    "tos_snapshot_id": "string|null",
    "prototype_only": "boolean",
    "release_eligible": "boolean",
    "notes": "string",
}
REQUIRED_MANIFEST_FIELDS = tuple(MANIFEST_FIELDS)
ALLOWED_SPLITS = {"train", "dev", "test", "held-out"}


def stage1_manifest_schema() -> dict[str, Any]:
    return {
        "schema_version": STAGE1_MANIFEST_SCHEMA_VERSION,
        "format": "jsonl",
        "path": "data/stage1/stage1_manifest.jsonl",
        "required": list(REQUIRED_MANIFEST_FIELDS),
        "field_order": list(MANIFEST_FIELDS),
        "fields": [
            {"name": name, "type": FIELD_TYPES[name]}
            for name in MANIFEST_FIELDS
        ],
        "payload_excluded": ["text", "title"],
        "trainer_jsonl_fields": ["doc_id", "text", "source", "register", "split", "prototype_only"],
        "notes": (
            "Manifest rows intentionally exclude corpus text. The local "
            "trainer JSONL under data/stage1/stage1.jsonl.gz carries text "
            "and remains gitignored. token_count_est/char_count are cleaned "
            "payload counts; raw_token_count_est/raw_char_count preserve the "
            "pre-clean source-row counts for audit."
        ),
    }


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _looks_sha256(v: Any) -> bool:
    return (
        isinstance(v, str)
        and len(v) == 64
        and all(c in "0123456789abcdef" for c in v.lower())
    )


def _field_type_ok(value: Any, typ: str) -> bool:
    if typ == "string":
        return isinstance(value, str)
    if typ == "string|null":
        return value is None or isinstance(value, str)
    if typ == "integer":
        return _is_int(value)
    if typ == "integer|null":
        return value is None or _is_int(value)
    if typ == "number":
        return _is_num(value)
    if typ == "number|null":
        return value is None or _is_num(value)
    if typ == "boolean":
        return isinstance(value, bool)
    if typ == "object":
        return isinstance(value, dict)
    if typ == "sha256":
        return _looks_sha256(value)
    return False


def validate_manifest_docs(docs: list[dict], max_errors: int = 50) -> list[str]:
    errors: list[str] = []
    for idx, d in enumerate(docs, 1):
        doc_id = d.get("doc_id", f"row{idx}")
        for field in REQUIRED_MANIFEST_FIELDS:
            if field not in d:
                errors.append(f"{doc_id}:missing_field:{field}")
                continue
            value = d.get(field)
            typ = FIELD_TYPES[field]
            if not _field_type_ok(value, typ):
                errors.append(
                    f"{doc_id}:bad_type:{field}:expected={typ}:got={type(value).__name__}"
                )
        if d.get("split") not in ALLOWED_SPLITS:
            errors.append(f"{doc_id}:bad_split:{d.get('split')!r}")
        if _is_int(d.get("token_count_est")) and d["token_count_est"] <= 0:
            errors.append(f"{doc_id}:nonpositive_token_count")
        if _is_int(d.get("char_count")) and d["char_count"] < 0:
            errors.append(f"{doc_id}:negative_char_count")
        if d.get("unicode_normalized") is not True:
            errors.append(f"{doc_id}:unicode_not_normalized")
        if not d.get("license_observed"):
            errors.append(f"{doc_id}:empty_license_observed")
        if len(errors) >= max_errors:
            errors.append(f"truncated_after_{max_errors}_schema_errors")
            return errors
    return errors


def finalize_fineweb2_cleaning_report(
    report: dict[str, Any] | None,
    docs: list[dict],
) -> dict[str, Any] | None:
    if report is None:
        return None
    report["manifest_source_token_summary"] = _token_summary_by_field(docs, "source")
    report["manifest_register_token_summary"] = _token_summary_by_field(docs, "register_tag")
    report["manifest_source_register_token_summary"] = _source_register_token_summary(docs)
    fineweb_docs = [d for d in docs if d.get("source") == "fineweb2_haw"]
    fineweb_train_docs = [
        d for d in fineweb_docs
        if d.get("split") == "train" and d.get("language_id") == "haw"
    ]
    report["fineweb2_docs_after_exact_dedupe"] = len(fineweb_docs)
    report["fineweb2_manifest_tokens"] = {
        "raw_tokens_est": sum(_raw_token_count_for_doc(d) for d in fineweb_docs),
        "clean_tokens_est": sum(int(d.get("token_count_est") or 0) for d in fineweb_docs),
    }
    report["fineweb2_manifest_train_tokens"] = {
        "rows": len(fineweb_train_docs),
        "raw_tokens_est": sum(_raw_token_count_for_doc(d) for d in fineweb_train_docs),
        "clean_tokens_est": sum(int(d.get("token_count_est") or 0) for d in fineweb_train_docs),
    }
    for key in ("row_reject_reasons", "paragraph_reject_reasons", "unicode"):
        if isinstance(report.get(key), Counter):
            report[key] = dict(sorted(report[key].items()))
    return report


def write_outputs(
    docs: list[dict],
    dry_run: bool,
    token_target: str,
    fineweb2_cleaning_report: dict[str, Any] | None = None,
) -> dict[str, str]:
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

    with TOKEN_REPORT_PATH.open("w", encoding="utf-8") as rfh:
        json.dump(token_report_payload(docs, token_target), rfh, ensure_ascii=False, indent=2)
        rfh.write("\n")
    written["token_target_report"] = str(TOKEN_REPORT_PATH)

    finalized_cleaning = finalize_fineweb2_cleaning_report(fineweb2_cleaning_report, docs)
    if finalized_cleaning is not None:
        FINEWEB2_STAGE1_DIR.mkdir(parents=True, exist_ok=True)
        with FINEWEB2_CLEANING_REPORT_PATH.open("w", encoding="utf-8") as cfh:
            json.dump(finalized_cleaning, cfh, ensure_ascii=False, indent=2, default=str)
            cfh.write("\n")
        written["fineweb2_cleaning_report"] = str(FINEWEB2_CLEANING_REPORT_PATH)

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
                    "raw_token_count_est": d["raw_token_count_est"],
                    "token_count_est": d["token_count_est"],
                    "cleaning_method": d["cleaning_method"],
                    "source_url": d["source_url"],
                    "fetch_date": d["fetch_date"],
                }, ensure_ascii=False) + "\n")
        written[f"extracted::{src}/{fd}"] = str(out)
    return written


# ---------- CLI ----------

def _source_selected(sources: list[str] | None, source: str) -> bool:
    return sources is None or source in sources


def _preview_docs_from_local_reports(sources: list[str] | None) -> list[dict]:
    """Cheap token preview from local reports; never opens corpus text."""
    docs: list[dict] = []
    if sources is None and TOKEN_REPORT_PATH.exists():
        try:
            payload = json.loads(TOKEN_REPORT_PATH.read_text(encoding="utf-8"))
            tokens = int(payload.get("train_tokens_est") or 0)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            tokens = 0
        if tokens:
            return [{
                "split": "train",
                "language_id": "haw",
                "token_count_est": tokens,
                "source": "stage1_token_report",
                "sha256_clean": "0" * 64,
            }]
    if _source_selected(sources, "fineweb2_haw"):
        cleaning_report = DATA_STAGE1 / "fineweb2_haw" / "cleaning_report.json"
        if cleaning_report.exists():
            try:
                payload = json.loads(cleaning_report.read_text(encoding="utf-8"))
                train_tokens = payload.get("fineweb2_manifest_train_tokens", {})
                tokens = int(train_tokens.get("clean_tokens_est") or 0)
                raw_tokens = int(train_tokens.get("raw_tokens_est") or tokens)
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                tokens = 0
                raw_tokens = 0
            if tokens:
                docs.append({
                    "split": "train",
                    "language_id": "haw",
                    "token_count_est": tokens,
                    "raw_token_count_est": raw_tokens,
                    "source": "fineweb2_haw",
                    "register_tag": "web",
                    "sha256_clean": "0" * 64,
                })
                return docs
        report = DATA_STAGE1 / "fineweb2_haw" / "split_dedupe_manifest.json"
        if report.exists():
            try:
                payload = json.loads(report.read_text(encoding="utf-8"))
                tokens = int(payload.get("splits", {}).get("train", {}).get("tokens") or 0)
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                tokens = 0
            if tokens:
                docs.append({
                    "split": "train",
                    "language_id": "haw",
                    "token_count_est": tokens,
                    "source": "fineweb2_haw",
                    "sha256_clean": "0" * 64,
                })
    return docs


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
    p.add_argument("--print-schema", action="store_true",
                   help="Print the Stage-1 manifest JSONL schema and exit.")
    args = p.parse_args(argv)

    if args.print_schema:
        json.dump(stage1_manifest_schema(), sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0

    if args.show_targets:
        # Cheap, no-corpus-needed view of where we stand vs targets.
        all_docs_preview: list[dict] = _preview_docs_from_local_reports(args.source)
        try:
            for rec in iter_fetch_records(args.source):
                if rec.source == "fineweb2_haw":
                    continue
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
                "Uses local Stage-1 token reports/split manifests when "
                "present; otherwise token counts only become non-zero after "
                "extraction (run without --show-targets). Conservative "
                f"target = {TOKEN_TARGETS['conservative']:,} train tokens is "
                "the Stage-1 go/no-go gate; below this, --strict exits 2."
            ),
        }
        json.dump(out, sys.stdout, ensure_ascii=False, indent=2, default=str)
        sys.stdout.write("\n")
        return 0

    started = _utcnow_iso()
    all_docs: list[dict] = []
    all_skips: list[Skip] = []
    seen_records = 0
    accepted_source_records_seen = 0
    fineweb2_cleaning_report: dict[str, Any] | None = None

    if _source_selected(args.source, "fineweb2_haw"):
        docs, skips, rows_seen, fineweb2_cleaning_report = process_fineweb2_stage1_jsonl(
            FINEWEB2_STAGE1_TRAIN,
            args.limit,
        )
        all_docs.extend(docs)
        all_skips.extend(skips)
        accepted_source_records_seen += rows_seen

    # FineWeb-2 raw ledgers point at split-level aggregate JSONL files; consume
    # the accepted post-310 Stage-1 train file above instead of treating every
    # provenance row as an independent artefact.
    raw_sources = None if args.source is None else [s for s in args.source if s != "fineweb2_haw"]
    for rec in iter_fetch_records(raw_sources):
        if rec.source == "fineweb2_haw":
            continue
        seen_records += 1
        try:
            docs, skips = process_record(rec, args.limit)
        except Exception as e:  # noqa: BLE001
            all_skips.append(Skip(f"exception:{type(e).__name__}:{e}", rec))
            continue
        all_docs.extend(docs)
        all_skips.extend(skips)

    all_docs, deduped_docs_removed = dedupe_docs(all_docs)
    schema_errors = validate_manifest_docs(all_docs)
    fineweb2_cleaning_report = finalize_fineweb2_cleaning_report(
        fineweb2_cleaning_report,
        all_docs,
    )
    if schema_errors:
        written = {}
    else:
        written = write_outputs(
            all_docs,
            args.dry_run,
            args.token_target,
            fineweb2_cleaning_report,
        )
    failures = quality_gates(all_docs, args.strict, args.token_target)
    tokens_report = token_volume_report(all_docs, args.token_target)

    summary = {
        "started_utc": started,
        "finished_utc": _utcnow_iso(),
        "fetch_records_seen": seen_records,
        "accepted_source_records_seen": accepted_source_records_seen,
        "docs_emitted": len(all_docs),
        "deduped_docs_removed": deduped_docs_removed,
        "docs_skipped": len(all_skips),
        "skip_reasons": Counter(s.reason.split(":", 1)[0] for s in all_skips),
        "skip_reason_details": Counter(skip_detail_key(s.reason) for s in all_skips),
        "split_counts": Counter(d["split"] for d in all_docs),
        "source_counts": Counter(d["source"] for d in all_docs),
        "source_token_summary": _token_summary_by_field(all_docs, "source"),
        "register_token_summary": _token_summary_by_field(all_docs, "register_tag"),
        "manifest_schema_version": STAGE1_MANIFEST_SCHEMA_VERSION,
        "schema_errors": schema_errors,
        "token_volume": tokens_report,
        "fineweb2_cleaning": fineweb2_cleaning_report,
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
        if accepted_source_records_seen == 0:
            print("note: no accepted Stage-1 source rows and no fetch.jsonl found under data/raw/. "
                  "Run source fetchers first. For FineWeb-2: "
                  "scripts/205_fetch_fineweb2_haw_raw.py --execute --split train ...; then "
                  "scripts/310_split_dedupe_fineweb2_haw.py --execute; then rerun 301.", file=sys.stderr)
    if any(s.reason.startswith("fineweb2_raw_train_missing") for s in all_skips):
        print(
            "note: FineWeb-2 raw train rows are missing. Fetch them with "
            "scripts/205_fetch_fineweb2_haw_raw.py --execute --split train --limit <N>, "
            "then run scripts/310_split_dedupe_fineweb2_haw.py --execute before 301.",
            file=sys.stderr,
        )
    if any(s.reason.startswith("fineweb2_stage1_train_missing") for s in all_skips):
        print(
            "note: FineWeb-2 raw rows exist but data/stage1/fineweb2_haw/train.jsonl is missing. "
            "Run scripts/310_split_dedupe_fineweb2_haw.py --execute to create the accepted train slice.",
            file=sys.stderr,
        )
    if schema_errors:
        print(
            f"error: Stage-1 manifest schema validation failed "
            f"({len(schema_errors)} shown/max). Outputs were not written.",
            file=sys.stderr,
        )
        return 1
    if args.strict and failures:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
