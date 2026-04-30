"""One-shot local converter: ulukau_nupepa/human_fetch.md -> tokenizer-audit candidate.

Additive, audit-only. Does NOT produce W1/eval/training data. Output paths live
under ignored data/tokenizer_audit/. Run from repo root:

    python3 scripts/_convert_ulukau_human_fetch.py
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "data/raw/ulukau_nupepa/human_fetch.md"
OUT_DIR = REPO / "data/tokenizer_audit/ulukau_nupepa"
JSONL = OUT_DIR / "human_fetch.jsonl"
HAW_TXT = OUT_DIR / "human_fetch.haw.txt"
ALL_TXT = OUT_DIR / "human_fetch.txt"

OKINA = "\u02bb"
OKINA_VARIANTS = ["\u2018", "\u2019", "\u02bc", "`"]
KAHAKO_VOWELS = set("āēīōūĀĒĪŌŪ")
DIACRITIC_CHARS = KAHAKO_VOWELS | {OKINA}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    for v in OKINA_VARIANTS:
        text = text.replace(v, OKINA)
    text = unicodedata.normalize("NFC", text)
    return text.strip()


def parse_sections(raw: str) -> list[dict]:
    blocks = re.split(r"^# ", raw, flags=re.MULTILINE)
    out = []
    for blk in blocks:
        blk = blk.strip()
        if not blk:
            continue
        head, _, body = blk.partition("\n")
        lang_label = head.strip().lower()
        body = body.strip()
        if not body:
            continue
        lang = "haw" if "hawaii" in lang_label and "english" not in lang_label else (
            "en" if lang_label.startswith("english") else lang_label
        )
        lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
        out.append({"lang": lang, "lines": lines})
    return out


def diacritic_stats(text: str) -> dict:
    okina_count = text.count(OKINA)
    kahako_count = sum(1 for c in text if c in KAHAKO_VOWELS)
    chars = len(text)
    rough_words = len(re.findall(r"\S+", text))
    return {
        "chars": chars,
        "rough_words": rough_words,
        "okina_count": okina_count,
        "kahako_count": kahako_count,
        "diacritic_density": round((okina_count + kahako_count) / chars, 5) if chars else 0.0,
    }


def main() -> None:
    raw = SRC.read_text(encoding="utf-8")
    sections = parse_sections(raw)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    records = []
    haw_text_blocks = []
    all_text_blocks = []
    for sec in sections:
        normed_lines = [normalize(ln) for ln in sec["lines"]]
        text = "\n".join(normed_lines)
        sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        stats = diacritic_stats(text)
        rec = {
            "id": f"ulukau_nupepa.human_fetch.{sec['lang']}.0001",
            "lang": sec["lang"],
            "text": text,
            "source": "ulukau_nupepa",
            "source_path": "data/raw/ulukau_nupepa/human_fetch.md",
            "provenance": {
                "site": "Ulukau / Nupepa Hawaiian newspapers collection landing copy",
                "fetch_method": "human_fetch (manual paste)",
                "fetched_by": "user",
                "license_status": "unverified_landing_copy",
                "rights_cleared": False,
            },
            "quality_note": (
                "User believes the Hawaiian paragraph is written/translated by native "
                "speakers (institutional landing page); treat as plausible-quality, "
                "NOT verified. English paragraph is parallel context only."
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
                "markdown_scaffolding_removed": True,
            },
            "hash": {"algo": "sha256", "value": sha},
            "stats": stats,
        }
        records.append(rec)
        all_text_blocks.append(text)
        if sec["lang"] == "haw":
            haw_text_blocks.append(text)

    with JSONL.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    HAW_TXT.write_text("\n\n".join(haw_text_blocks) + "\n", encoding="utf-8")
    ALL_TXT.write_text("\n\n".join(all_text_blocks) + "\n", encoding="utf-8")

    summary = {
        "records": len(records),
        "by_lang": {r["lang"]: r["stats"] for r in records},
        "outputs": {
            "jsonl": str(JSONL.relative_to(REPO)),
            "haw_txt": str(HAW_TXT.relative_to(REPO)),
            "all_txt": str(ALL_TXT.relative_to(REPO)),
        },
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
