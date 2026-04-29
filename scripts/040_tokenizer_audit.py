#!/usr/bin/env python3
"""Stage-0 Hawaiian tokenizer audit.

Audits Hawaiian tokens/word and byte-fallback/proxy behavior over local,
gitignored samples before serious Llama-3.1-8B Stage-1 spend. Heavy Hugging
Face dependencies are imported only for real audits, so ``--help`` works on a
fresh machine. Missing transformers or gated model access fails with actionable
instructions rather than placeholder results.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_ID = "meta-llama/Llama-3.1-8B"
DEFAULT_TEXT_FIELDS = ("text", "prompt", "reference")
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "tokenizer_audit"
AUDIT_VERSION = "tokenizer-audit-v0.1"

OKINA = "\u02BB"
WRONG_OKINA_CHARS = ("'", "\u2018", "\u2019", "\u02BC")
KAHAKO = "āēīōūĀĒĪŌŪ"
HAWAIIAN_VOWELS = set("aeiouAEIOU" + KAHAKO)
DIACRITIC_CHARS = OKINA + KAHAKO
BYTE_FALLBACK_RE = re.compile(r"^<0x[0-9A-Fa-f]{2}>$")


@dataclass
class Sample:
    text: str
    source: str
    input_path: Path
    locator: str


@dataclass
class SampleMetrics:
    source: str
    input_path: str
    sample_count: int
    char_count: int
    utf8_byte_count: int
    word_count: int
    token_count: int
    okina_count: int
    kahako_count: int
    diacritic_count: int
    explicit_byte_fallback_tokens: int
    replacement_char_proxy_tokens: int
    diacritic_offset_fragment_proxy_tokens: int
    byte_fallback_or_proxy_tokens: int
    nfc_changed: int
    okina_replacements: int
    high_diacritic: bool


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", s).strip("-").lower() or "tokenizer"


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _jsonable(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    return str(obj)


def _sha256_json(obj: Any) -> str:
    payload = json.dumps(_jsonable(obj), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _open_text(path: Path):
    if path.suffix == ".gz" or ".gz" in path.suffixes:
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open("r", encoding="utf-8")


def _split_arg_list(values: Iterable[str] | None, default: Iterable[str]) -> list[str]:
    if not values:
        return list(default)
    out: list[str] = []
    for value in values:
        out.extend(part.strip() for part in value.split(",") if part.strip())
    return out or list(default)


def _extract_text(row: dict[str, Any], fields: list[str]) -> str | None:
    chunks = [str(row[f]).strip() for f in fields if isinstance(row.get(f), str) and str(row[f]).strip()]
    return "\n".join(chunks) if chunks else None


def _source_for(row: dict[str, Any], source_field: str | None, fallback: str) -> str:
    if source_field and isinstance(row.get(source_field), str) and row[source_field].strip():
        return row[source_field].strip()
    for key in ("source_id", "origin", "dataset", "register"):
        if isinstance(row.get(key), str) and row[key].strip():
            return row[key].strip()
    return fallback


def _iter_jsonl(path: Path, text_fields: list[str], source_field: str | None) -> Iterator[Sample]:
    with _open_text(path) as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"Bad JSON at {path}:{line_no}: {e}") from e
            if not isinstance(row, dict):
                raise ValueError(f"Expected JSON object at {path}:{line_no}")
            text = _extract_text(row, text_fields)
            if text:
                fallback = _rel(path)
                yield Sample(text, _source_for(row, source_field, fallback), path, f"{fallback}:{line_no}")


def _iter_json(path: Path, text_fields: list[str], source_field: str | None) -> Iterator[Sample]:
    with _open_text(path) as fh:
        obj = json.load(fh)
    if isinstance(obj, dict):
        records = obj.get("records") if isinstance(obj.get("records"), list) else obj.get("data")
        rows = records if isinstance(records, list) else [obj]
    elif isinstance(obj, list):
        rows = obj
    else:
        raise ValueError(f"Expected object/list JSON in {path}")
    for idx, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue
        text = _extract_text(row, text_fields)
        if text:
            fallback = _rel(path)
            yield Sample(text, _source_for(row, source_field, fallback), path, f"{fallback}:{idx}")


def _iter_delimited(path: Path, text_fields: list[str], source_field: str | None) -> Iterator[Sample]:
    delimiter = "\t" if ".tsv" in path.suffixes else ","
    with _open_text(path) as fh:
        lines = (line for line in fh if line.strip() and not line.lstrip().startswith("#"))
        reader = csv.DictReader(lines, delimiter=delimiter)
        for row_no, row in enumerate(reader, start=2):
            text = _extract_text(row, text_fields)
            if text:
                fallback = _rel(path)
                yield Sample(text, _source_for(row, source_field, fallback), path, f"{fallback}:{row_no}")


def _iter_text(path: Path) -> Iterator[Sample]:
    with _open_text(path) as fh:
        raw = fh.read()
    blocks = [b.strip() for b in re.split(r"\n\s*\n+", raw) if b.strip()] or ([raw.strip()] if raw.strip() else [])
    for idx, block in enumerate(blocks, start=1):
        yield Sample(block, _rel(path), path, f"{_rel(path)}:block-{idx}")


def iter_samples(paths: list[Path], text_fields: list[str], source_field: str | None) -> Iterator[Sample]:
    for p in paths:
        path = p if p.is_absolute() else (REPO_ROOT / p)
        if not path.exists():
            raise FileNotFoundError(f"Input sample file not found: {path}")
        suffixes = set(path.suffixes)
        if ".jsonl" in suffixes or ".ndjson" in suffixes:
            yield from _iter_jsonl(path, text_fields, source_field)
        elif ".json" in suffixes:
            yield from _iter_json(path, text_fields, source_field)
        elif ".tsv" in suffixes or ".csv" in suffixes:
            yield from _iter_delimited(path, text_fields, source_field)
        else:
            yield from _iter_text(path)


def canonicalize_okina_contextual(text: str) -> tuple[str, int]:
    chars = list(text)
    replacements = 0
    for i, ch in enumerate(chars):
        if ch not in WRONG_OKINA_CHARS:
            continue
        prev = chars[i - 1] if i > 0 else ""
        nxt = chars[i + 1] if i + 1 < len(chars) else ""
        prev_is_boundary = not prev or not (prev.isalpha() or prev == OKINA)
        if nxt in HAWAIIAN_VOWELS and (prev in HAWAIIAN_VOWELS or prev_is_boundary):
            chars[i] = OKINA
            replacements += 1
    return "".join(chars), replacements


def normalize_for_audit(text: str, canonicalize_okina: bool) -> tuple[str, bool, int]:
    replacements = 0
    if canonicalize_okina:
        text, replacements = canonicalize_okina_contextual(text)
    normalized = unicodedata.normalize("NFC", text)
    return normalized, normalized != text, replacements


def count_words(text: str) -> int:
    count = 0
    in_word = False
    for ch in text:
        is_word = ch.isalpha() or ch == OKINA
        if is_word and not in_word:
            count += 1
        in_word = is_word
    return count


def count_kahako(text: str) -> int:
    return sum(text.count(ch) for ch in KAHAKO)


def _safe_tokens(tokenizer: Any, ids: list[int]) -> list[str]:
    try:
        return list(tokenizer.convert_ids_to_tokens(ids))
    except Exception:
        return []


def _decode_one(tokenizer: Any, token_id: int) -> str:
    try:
        return tokenizer.decode([token_id], skip_special_tokens=False, clean_up_tokenization_spaces=False)
    except TypeError:
        return tokenizer.decode([token_id], skip_special_tokens=False)
    except Exception:
        return ""


def _encode_with_offsets(tokenizer: Any, text: str) -> tuple[list[int], list[tuple[int, int]] | None]:
    try:
        enc = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True, return_attention_mask=False)
        ids = list(enc["input_ids"])
        offsets = [(int(s), int(e)) for s, e in enc.get("offset_mapping", [])]
        return ids, offsets
    except Exception:
        return list(tokenizer.encode(text, add_special_tokens=False)), None


def _diacritic_offset_fragment_indices(text: str, offsets: list[tuple[int, int]] | None) -> set[int]:
    if not offsets:
        return set()
    by_span: dict[tuple[int, int], list[int]] = defaultdict(list)
    for idx, (start, end) in enumerate(offsets):
        if end - start == 1 and 0 <= start < end <= len(text) and text[start:end] in DIACRITIC_CHARS:
            by_span[(start, end)].append(idx)
    return {idx for indices in by_span.values() if len(indices) > 1 for idx in indices}


def audit_sample(sample: Sample, tokenizer: Any, canonicalize_okina: bool, high_min_count: int, high_min_per_word: float) -> SampleMetrics:
    text, nfc_changed, okina_replacements = normalize_for_audit(sample.text, canonicalize_okina)
    words = count_words(text)
    okina = text.count(OKINA)
    kahako = count_kahako(text)
    diacritics = okina + kahako
    ids, offsets = _encode_with_offsets(tokenizer, text)
    token_strings = _safe_tokens(tokenizer, ids)
    explicit: set[int] = set()
    replacement: set[int] = set()
    for idx, token_id in enumerate(ids):
        token = token_strings[idx] if idx < len(token_strings) else ""
        decoded = _decode_one(tokenizer, token_id)
        if BYTE_FALLBACK_RE.match(token):
            explicit.add(idx)
        if "\ufffd" in token or "\ufffd" in decoded:
            replacement.add(idx)
    offset_fragments = _diacritic_offset_fragment_indices(text, offsets)
    byte_or_proxy = explicit | replacement | offset_fragments
    density = diacritics / words if words else 0.0
    return SampleMetrics(
        source=sample.source,
        input_path=_rel(sample.input_path),
        sample_count=1,
        char_count=len(text),
        utf8_byte_count=len(text.encode("utf-8")),
        word_count=words,
        token_count=len(ids),
        okina_count=okina,
        kahako_count=kahako,
        diacritic_count=diacritics,
        explicit_byte_fallback_tokens=len(explicit),
        replacement_char_proxy_tokens=len(replacement),
        diacritic_offset_fragment_proxy_tokens=len(offset_fragments),
        byte_fallback_or_proxy_tokens=len(byte_or_proxy),
        nfc_changed=int(nfc_changed),
        okina_replacements=okina_replacements,
        high_diacritic=diacritics >= high_min_count and density >= high_min_per_word,
    )


def summarize(metrics: list[SampleMetrics]) -> dict[str, Any]:
    totals: Counter[str] = Counter()
    for m in metrics:
        totals.update({
            "sample_count": m.sample_count,
            "char_count": m.char_count,
            "utf8_byte_count": m.utf8_byte_count,
            "word_count": m.word_count,
            "token_count": m.token_count,
            "okina_count": m.okina_count,
            "kahako_count": m.kahako_count,
            "diacritic_count": m.diacritic_count,
            "explicit_byte_fallback_tokens": m.explicit_byte_fallback_tokens,
            "replacement_char_proxy_tokens": m.replacement_char_proxy_tokens,
            "diacritic_offset_fragment_proxy_tokens": m.diacritic_offset_fragment_proxy_tokens,
            "byte_fallback_or_proxy_tokens": m.byte_fallback_or_proxy_tokens,
            "nfc_changed_samples": m.nfc_changed,
            "okina_replacements": m.okina_replacements,
        })
    words = totals["word_count"]
    tokens = totals["token_count"]
    diacritics = totals["diacritic_count"]
    return {
        "sample_count": totals["sample_count"],
        "char_count": totals["char_count"],
        "utf8_byte_count": totals["utf8_byte_count"],
        "word_count": words,
        "token_count": tokens,
        "tokens_per_word": tokens / words if words else None,
        "okina_count": totals["okina_count"],
        "kahako_count": totals["kahako_count"],
        "diacritic_count": diacritics,
        "diacritics_per_word": diacritics / words if words else None,
        "explicit_byte_fallback_tokens": totals["explicit_byte_fallback_tokens"],
        "explicit_byte_fallback_rate": totals["explicit_byte_fallback_tokens"] / tokens if tokens else None,
        "replacement_char_proxy_tokens": totals["replacement_char_proxy_tokens"],
        "diacritic_offset_fragment_proxy_tokens": totals["diacritic_offset_fragment_proxy_tokens"],
        "byte_fallback_or_proxy_tokens": totals["byte_fallback_or_proxy_tokens"],
        "byte_fallback_or_proxy_rate": totals["byte_fallback_or_proxy_tokens"] / tokens if tokens else None,
        "nfc_changed_samples": totals["nfc_changed_samples"],
        "okina_replacements": totals["okina_replacements"],
    }


def summarize_by_source(metrics: list[SampleMetrics]) -> dict[str, Any]:
    grouped: dict[str, list[SampleMetrics]] = defaultdict(list)
    for m in metrics:
        grouped[m.source].append(m)
    return {source: summarize(rows) for source, rows in sorted(grouped.items())}


def tokenizer_fingerprint(tokenizer: Any) -> str:
    try:
        vocab = tokenizer.get_vocab()
    except Exception:
        vocab = {}
    return _sha256_json({
        "class": tokenizer.__class__.__name__,
        "name_or_path": getattr(tokenizer, "name_or_path", None),
        "vocab": sorted(vocab.items()),
        "special_tokens_map": getattr(tokenizer, "special_tokens_map", {}),
        "model_max_length": getattr(tokenizer, "model_max_length", None),
    })


def diacritic_char_probe(tokenizer: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for ch in DIACRITIC_CHARS:
        ids = list(tokenizer.encode(ch, add_special_tokens=False))
        out[f"U+{ord(ch):04X}"] = {
            "char": ch,
            "token_count": len(ids),
            "token_ids": ids,
            "tokens": _safe_tokens(tokenizer, ids),
            "decoded_pieces": [_decode_one(tokenizer, token_id) for token_id in ids],
        }
    return out


def resolve_hub_model_sha(model_id: str, revision: str | None, local_files_only: bool) -> dict[str, Any]:
    if local_files_only:
        return {"model_repo_sha": None, "note": "--local-files-only set; hub SHA not queried"}
    try:
        from huggingface_hub import HfApi  # type: ignore
        info = HfApi().model_info(model_id, revision=revision)
        return {"model_repo_sha": getattr(info, "sha", None), "error": None}
    except Exception as e:
        return {"model_repo_sha": None, "error": f"{type(e).__name__}: {e}", "note": "Tokenizer loaded, but hub commit SHA could not be resolved."}


def load_tokenizer_or_die(args: argparse.Namespace) -> Any:
    try:
        from transformers import AutoTokenizer  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "Missing optional dependency 'transformers'. Install audit deps with:\n"
            "  python3 -m pip install transformers huggingface_hub sentencepiece tiktoken\n"
            "Then rerun the audit. The root requirements.txt intentionally does not pin ML training dependencies."
        ) from e
    tokenizer_name = args.tokenizer_name or args.model_id
    kwargs: dict[str, Any] = {"use_fast": True, "local_files_only": args.local_files_only, "trust_remote_code": args.trust_remote_code}
    if args.revision:
        kwargs["revision"] = args.revision
    try:
        return AutoTokenizer.from_pretrained(tokenizer_name, **kwargs)
    except Exception as e:
        raise RuntimeError(
            f"Could not load tokenizer '{tokenizer_name}'.\n"
            "Actionable fixes:\n"
            "  1. Install audit deps: python3 -m pip install transformers huggingface_hub sentencepiece tiktoken\n"
            "  2. If this is a gated Llama tokenizer, request access on Hugging Face and authenticate with `huggingface-cli login` or HF_TOKEN.\n"
            "  3. If you already downloaded it, pass --local-files-only and confirm the cache contains the tokenizer files.\n"
            "  4. To audit a fallback, pass --model-id Qwen/Qwen2.5-7B or another candidate explicitly.\n"
            f"Original error: {type(e).__name__}: {e}"
        ) from e


def make_recommendation(report: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    overall = report["overall"]
    high = report["high_diacritic"]
    reasons: list[str] = []
    if overall["sample_count"] == 0:
        reasons.append("no usable text samples loaded")
    if overall["word_count"] < args.min_words:
        reasons.append(f"sample word count {overall['word_count']} < required {args.min_words}; add representative nūpepa, Baibala, and contemporary samples")
    if high["sample_count"] < args.require_high_diacritic_samples:
        reasons.append(f"insufficient high-diacritic samples ({high['sample_count']} < {args.require_high_diacritic_samples})")
    if overall["tokens_per_word"] is not None and overall["tokens_per_word"] > args.go_overall_tokens_per_word:
        reasons.append(f"overall tokens/word {overall['tokens_per_word']:.3f} > {args.go_overall_tokens_per_word:.3f}")
    if high["tokens_per_word"] is not None and high["tokens_per_word"] > args.go_high_diacritic_tokens_per_word:
        reasons.append(f"high-diacritic tokens/word {high['tokens_per_word']:.3f} > {args.go_high_diacritic_tokens_per_word:.3f}")
    explicit_rate = max(overall["explicit_byte_fallback_rate"] or 0.0, high["explicit_byte_fallback_rate"] or 0.0)
    proxy_rate = max(overall["byte_fallback_or_proxy_rate"] or 0.0, high["byte_fallback_or_proxy_rate"] or 0.0)
    if explicit_rate > args.max_explicit_byte_fallback_rate:
        reasons.append(f"explicit byte-fallback token rate {explicit_rate:.6f} > {args.max_explicit_byte_fallback_rate:.6f}")
    if proxy_rate > args.max_byte_proxy_rate:
        reasons.append(f"byte-fallback/proxy token rate {proxy_rate:.6f} > {args.max_byte_proxy_rate:.6f}")
    fragmented = [f"{p['char']}({cp})={p['token_count']} tokens" for cp, p in report["diacritic_char_tokenization"].items() if p["token_count"] > args.max_diacritic_char_tokens]
    if fragmented:
        reasons.append("standalone diacritic chars exceed token budget: " + ", ".join(fragmented))
    decision = "go" if not reasons else "no_go"
    summary = (
        "Tokenizer passes the Stage-0 spend gate under current thresholds. Freeze model/tokenizer SHA in the Stage-1 run manifest before training."
        if decision == "go"
        else "Do not spend serious Stage-1 GPU time on this base/tokenizer yet. Fix sample coverage, audit a fallback tokenizer, or plan vocab/embedding policy first."
    )
    return {"decision": decision, "summary": summary, "blocking_reasons": reasons}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Audit Hawaiian tokenizer tokens/word and byte-fallback/proxy behavior over local JSONL/TSV/text samples.")
    p.add_argument("--model-id", default=DEFAULT_MODEL_ID, help=f"HF model id (default: {DEFAULT_MODEL_ID})")
    p.add_argument("--tokenizer-name", default=None, help="Optional tokenizer id/path if different from --model-id.")
    p.add_argument("--revision", default=None, help="Optional HF revision/commit to load.")
    p.add_argument("--local-files-only", action="store_true", help="Only load tokenizer files already in the HF cache.")
    p.add_argument("--trust-remote-code", action="store_true", help="Forward trust_remote_code=True to AutoTokenizer.")
    p.add_argument("--input", nargs="+", type=Path, required=True, help="Local JSONL/JSON/TSV/CSV/text sample files.")
    p.add_argument("--text-field", action="append", default=None, help=f"JSON/TSV text field to audit. Repeat or comma-separate. Default: {','.join(DEFAULT_TEXT_FIELDS)}")
    p.add_argument("--source-field", default="source", help="Optional JSON/TSV field used for source slice labels.")
    p.add_argument("--limit", type=int, default=None, help="Maximum samples to audit after loading.")
    p.add_argument("--out", type=Path, default=None, help="Output report path. Default: data/tokenizer_audit/<model>-<timestamp>.json")
    p.add_argument("--no-canonicalize-okina", action="store_true", help="Disable conservative U+02BB canonicalization before tokenization.")
    p.add_argument("--high-diacritic-min-count", type=int, default=3, help="Minimum ʻokina+kahakō count for high-diacritic slice.")
    p.add_argument("--high-diacritic-min-per-word", type=float, default=0.25, help="Minimum diacritics/word for high-diacritic slice.")
    p.add_argument("--min-words", type=int, default=1500, help="Minimum sample words for a go decision.")
    p.add_argument("--require-high-diacritic-samples", type=int, default=10, help="Minimum high-diacritic samples for a go decision.")
    p.add_argument("--go-overall-tokens-per-word", type=float, default=2.50, help="Go threshold for overall tokens/word.")
    p.add_argument("--go-high-diacritic-tokens-per-word", type=float, default=3.25, help="Go threshold for high-diacritic tokens/word.")
    p.add_argument("--max-explicit-byte-fallback-rate", type=float, default=0.0, help="Max explicit <0x..> byte-fallback token rate.")
    p.add_argument("--max-byte-proxy-rate", type=float, default=0.01, help="Max combined byte-fallback/proxy token rate.")
    p.add_argument("--max-diacritic-char-tokens", type=int, default=2, help="Max tokens allowed for standalone Hawaiian diacritic chars.")
    p.add_argument("--fail-on-no-go", action="store_true", help="Exit 4 when the report recommendation is no_go.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    text_fields = _split_arg_list(args.text_field, DEFAULT_TEXT_FIELDS)
    try:
        tokenizer = load_tokenizer_or_die(args)
        metrics: list[SampleMetrics] = []
        for idx, sample in enumerate(iter_samples(args.input, text_fields, args.source_field), start=1):
            if args.limit is not None and idx > args.limit:
                break
            metrics.append(audit_sample(sample, tokenizer, not args.no_canonicalize_okina, args.high_diacritic_min_count, args.high_diacritic_min_per_word))
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 3
    if not metrics:
        print("[ERROR] No usable samples found. Check --input and --text-field; JSONL rows need at least one configured text field.", file=sys.stderr)
        return 2

    overall = summarize(metrics)
    high = summarize([m for m in metrics if m.high_diacritic])
    model_sha = resolve_hub_model_sha(args.model_id, args.revision, args.local_files_only)
    tokenizer_sha = tokenizer_fingerprint(tokenizer)
    path_counts = Counter(m.input_path for m in metrics)
    source_counts = Counter(m.source for m in metrics)
    report: dict[str, Any] = {
        "audit_version": AUDIT_VERSION,
        "created_at_utc": _utcnow_iso(),
        "model": {
            "model_id": args.model_id,
            "tokenizer_name": args.tokenizer_name or args.model_id,
            "revision_requested": args.revision,
            "tokenizer_class": tokenizer.__class__.__name__,
            "tokenizer_name_or_path": getattr(tokenizer, "name_or_path", None),
            "tokenizer_vocab_size": getattr(tokenizer, "vocab_size", None),
            "tokenizer_model_max_length": getattr(tokenizer, "model_max_length", None),
            "tokenizer_sha256": tokenizer_sha,
            "tokenizer_fingerprint_sha256": tokenizer_sha,
            **model_sha,
        },
        "input": {"paths": dict(sorted(path_counts.items())), "sources": dict(sorted(source_counts.items())), "text_fields": text_fields, "source_field": args.source_field, "limit": args.limit},
        "normalization": {"unicode": "NFC", "canonicalize_okina_u02bb": not args.no_canonicalize_okina, "nfc_changed_samples": overall["nfc_changed_samples"], "okina_replacements": overall["okina_replacements"]},
        "slice_policy": {"high_diacritic_min_count": args.high_diacritic_min_count, "high_diacritic_min_per_word": args.high_diacritic_min_per_word},
        "gate_policy": {"min_words": args.min_words, "require_high_diacritic_samples": args.require_high_diacritic_samples, "go_overall_tokens_per_word": args.go_overall_tokens_per_word, "go_high_diacritic_tokens_per_word": args.go_high_diacritic_tokens_per_word, "max_explicit_byte_fallback_rate": args.max_explicit_byte_fallback_rate, "max_byte_proxy_rate": args.max_byte_proxy_rate, "max_diacritic_char_tokens": args.max_diacritic_char_tokens},
        "overall": overall,
        "high_diacritic": high,
        "by_source": summarize_by_source(metrics),
        "diacritic_char_tokenization": diacritic_char_probe(tokenizer),
    }
    report["recommendation"] = make_recommendation(report, args)

    out_path = args.out or DEFAULT_OUTPUT_DIR / f"{_slug(args.model_id)}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out_path = out_path if out_path.is_absolute() else (REPO_ROOT / out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "report": _rel(out_path),
        "decision": report["recommendation"]["decision"],
        "blocking_reasons": report["recommendation"]["blocking_reasons"],
        "overall_tokens_per_word": report["overall"]["tokens_per_word"],
        "high_diacritic_tokens_per_word": report["high_diacritic"]["tokens_per_word"],
        "byte_fallback_or_proxy_rate": report["overall"]["byte_fallback_or_proxy_rate"],
    }, ensure_ascii=False, indent=2))
    if args.fail_on_no_go and report["recommendation"]["decision"] != "go":
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
