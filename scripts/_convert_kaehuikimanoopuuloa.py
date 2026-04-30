#!/usr/bin/env python3
"""Convert He moʻolelo kaʻao no Kaʻehuikimanōopuʻuloa human-paste pages
into an additive tokenizer-audit candidate artifact.

Local one-shot, idempotent. Not committed. See:
- .squad/decisions.md (Rusty/Basher tokenizer-audit gate, Issue #8)
- data/tokenizer_audit/ulukau_nupepa/README.md (prior landing-copy artifact)
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "data" / "raw" / "ulukau_nupepa" / "human_fetch_book_pages.txt"
OUT_DIR = REPO / "data" / "tokenizer_audit" / "ulukau_nupepa" / "kaehuikimanoopuuloa"

OKINA = "\u02bb"
OKINA_VARIANTS = ["\u2018", "\u2019", "\u02bc", "\u0060"]
KAHAKO_CHARS = "āēīōūĀĒĪŌŪ"
DIACRITIC_SET = set(KAHAKO_CHARS) | {OKINA}


def fold_okina(s: str) -> str:
    for v in OKINA_VARIANTS:
        s = s.replace(v, OKINA)
    return s


def clean(text: str) -> str:
    # NFC, then fold ʻokina variants.
    text = unicodedata.normalize("NFC", text)
    text = fold_okina(text)
    # Drop BOM / zero-width / NBSP normalize.
    text = text.replace("\ufeff", "").replace("\u200b", "").replace("\u00a0", " ")
    # Normalize line endings.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Per-line cleanup: strip trailing/leading spaces; collapse runs of spaces/tabs.
    lines = []
    for ln in text.split("\n"):
        ln = ln.strip()
        ln = re.sub(r"[ \t]+", " ", ln)
        lines.append(ln)
    text = "\n".join(lines)
    # Collapse 2+ blank lines (page-boundary scaffolding) to single blank line.
    text = re.sub(r"\n{2,}", "\n\n", text)
    return text.strip() + "\n"


def stats(text: str) -> dict:
    body = text.strip()
    paragraphs = [p for p in re.split(r"\n{2,}", body) if p.strip()]
    rough_words = len(re.findall(r"\S+", body))
    okina_n = body.count(OKINA)
    kahako_n = sum(body.count(c) for c in KAHAKO_CHARS)
    diacritic_n = sum(1 for ch in body if ch in DIACRITIC_SET)
    letters = sum(1 for ch in body if ch.isalpha())
    density = round(diacritic_n / letters, 4) if letters else 0.0
    return {
        "chars": len(body),
        "rough_words": rough_words,
        "paragraphs": len(paragraphs),
        "lines": body.count("\n") + 1,
        "okina_count": okina_n,
        "kahako_count": kahako_n,
        "diacritic_letters": diacritic_n,
        "letters": letters,
        "diacritic_density": density,
    }


def main() -> None:
    raw = SRC.read_text(encoding="utf-8")
    raw_sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    cleaned = clean(raw)
    cleaned_sha = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()
    st = stats(cleaned)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    haw_txt = OUT_DIR / "kaehuikimanoopuuloa.haw.txt"
    haw_txt.write_text(cleaned, encoding="utf-8")

    record = {
        "id": "ulukau_nupepa.kaehuikimanoopuuloa.haw.0001",
        "lang": "haw",
        "title": "He moʻolelo kaʻao no Kaʻehuikimanōopuʻuloa (book pages, manual paste)",
        "text": cleaned,
        "source": "ulukau_nupepa",
        "source_path": "data/raw/ulukau_nupepa/human_fetch_book_pages.txt",
        "provenance": {
            "site": "Ulukau / Nupepa Hawaiian newspapers/book collection",
            "work": "He moʻolelo kaʻao no Kaʻehuikimanōopuʻuloa",
            "fetch_method": "human_fetch (manual page-by-page paste)",
            "fetched_by": "user",
            "license_status": "unverified",
            "rights_cleared": False,
        },
        "quality_note": (
            "User-pasted Hawaiian moʻolelo text. Surface form is high quality "
            "(NFC, U+02BB ʻokina present, kahakō preserved). Treat as plausible-"
            "quality probe text only; not a verified W1 / eval / training row."
        ),
        "audit_use": "tokenizer_audit_candidate",
        "policy": {
            "audit_only": True,
            "stage1_eligible": False,
            "eval_eligible": False,
            "training_eligible": False,
            "w1_eligible": False,
        },
        "normalization": {
            "form": "NFC",
            "okina_codepoint": "U+02BB",
            "okina_variants_folded": ["U+2018", "U+2019", "U+02BC", "U+0060"],
            "whitespace": (
                "lines stripped; internal runs of spaces/tabs collapsed; "
                "blank-line runs (page-paste scaffolding) collapsed to a "
                "single blank line; paragraph boundaries preserved"
            ),
            "scaffolding_removed": "page-boundary multi-blank runs only",
        },
        "hash": {
            "algo": "sha256",
            "raw": raw_sha,
            "normalized": cleaned_sha,
        },
        "stats": st,
    }

    jsonl = OUT_DIR / "kaehuikimanoopuuloa.jsonl"
    with jsonl.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    manifest = {
        "artifact": "ulukau_nupepa/kaehuikimanoopuuloa",
        "audit_use": "tokenizer_audit_candidate",
        "policy": record["policy"],
        "files": {
            "jsonl": str(jsonl.relative_to(REPO)),
            "haw_txt": str(haw_txt.relative_to(REPO)),
            "readme": str((OUT_DIR / "README.md").relative_to(REPO)),
        },
        "source": {
            "path": "data/raw/ulukau_nupepa/human_fetch_book_pages.txt",
            "sha256": raw_sha,
            "modified": False,
        },
        "stats": st,
        "hash_normalized": cleaned_sha,
    }
    (OUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({"ok": True, "stats": st, "out_dir": str(OUT_DIR.relative_to(REPO))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
