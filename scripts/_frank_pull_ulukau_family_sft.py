#!/usr/bin/env python3
"""
One-off Frank pull script: Ulukau-family SFT candidates (Round 4 discovery).
Outputs to data/raw/ulukau-family-sft-candidates/20260501/.
Run from repo root.
"""
import hashlib
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DATE = "20260501"
OUT_ROOT = REPO_ROOT / "data" / "raw" / "ulukau-family-sft-candidates" / OUT_DATE
HK_ROOT = REPO_ROOT / "data" / "raw" / "hawaiian-kingdom-statutes-paired-imprints" / OUT_DATE

RATE_LIMIT_S = 2.0        # polite IA rate limit
PDF_MAX_BYTES = 50_000_000  # skip PDFs larger than 50 MB

IA_META_URL = "https://archive.org/metadata/{item_id}"
IA_DL_URL   = "https://archive.org/download/{item_id}/{filename}"

UA = "FrankDataCollector/1.0 (ideal-spoon; hawaiian-llm-prototype; provenance-only; contact=yashasg)"

# ---------------------------------------------------------------------------
# New items to pull (all public IA, PD pre-1925)
# ---------------------------------------------------------------------------
NEW_ITEMS = [
    {
        "source_id": "ia-hawaiian-phrase-book-1881",
        "title": "Hawaiian Phrase Book (4th ed., revised, 1881)",
        "item_id": "hawaiianphrasebo00bishrich",
        "pull": ["djvu.txt", "pdf", "meta.xml", "marc.xml", "ia_metadata.json"],
        "rights_status": "PD_pre1925",
        "rights_note": "1881 US imprint. Pre-1925. Public domain. No scraping prohibition on IA.",
        "status": "full",
        "alignment_type": "dictionary-example",
        "alignment_method": "column-position",
        "register": "educational",
        "notes": "Explicit ENGLISH|HAWAIIAN two-column layout; rank-1 candidate; ~800-2000 phrase pairs.",
    },
    {
        "source_id": "ia-hk-constitution-1852-en",
        "title": "Constitution and Laws of HM Kamehameha III (1852) — English",
        "item_id": "constitutionand00hawagoog",
        "pull": ["djvu.txt", "pdf", "meta.xml", "marc.xml", "ia_metadata.json"],
        "rights_status": "PD_pre1925_sovereign_edicts",
        "rights_note": "1852 Hawaiian Kingdom publication (Honolulu). PD by age + sovereign-edicts.",
        "status": "full",
        "alignment_type": "parallel-doc",
        "alignment_method": "section-id",
        "register": "legal",
        "notes": "EN pair for hekumukanawaiam00hawagoog (already in HK statutes dir). ~200-600 section pairs.",
    },
    {
        "source_id": "ia-gospel-john-parallel-columns-1854",
        "title": "The Gospel According to John in Parallel Columns: English and Hawaiian (1854)",
        "item_id": "gospelaccordingt00hawarich",
        "pull": ["djvu.txt", "pdf", "meta.xml", "marc.xml", "ia_metadata.json"],
        "rights_status": "PD_pre1925",
        "rights_note": "1854 Mission Press (Honolulu). PD by age. No scraping restriction on IA.",
        "status": "raw",
        "alignment_type": "parallel-verse",
        "alignment_method": "verse-id",
        "register": "religious",
        "notes": "Parallel-column EN|HAW, all 21 chapters of John ~880 verses. Bible cap risk; dedupe vs Baibala.",
    },
    {
        "source_id": "ia-sanitary-instructions-1881",
        "title": "Sanitary Instructions for Hawaiians (English and Hawaiian, 1881)",
        "item_id": "63140380R.nlm.nih.gov",
        "pull": ["djvu.txt", "pdf", "meta.xml", "ia_metadata.json"],
        "rights_status": "PD_pre1925",
        "rights_note": "1881 Hawaiian Board of Education publication. PD. No scraping restriction.",
        "status": "raw",
        "alignment_type": "comparable-aligned",
        "alignment_method": "labse",
        "register": "educational",
        "notes": "EN volume first, HAW volume second (not interleaved). LaBSE needed. Unique health/medical register.",
    },
]

# Inventory-only items (metadata only, no bulk text pull)
INVENTORY_ITEMS = [
    {
        "source_id": "ia-diglot-nt-1859",
        "title": "Hawaiian-English (1859) Diglot New Testament",
        "item_id": "HAWPDF_DBS_HS",
        "pull": ["ia_metadata.json"],
        "rights_status": "PD_pre1925",
        "rights_note": "1859 American Bible Society publication. PD. OCR two-column garbled.",
        "status": "inventory_only",
        "alignment_type": "parallel-verse",
        "alignment_method": "verse-id",
        "register": "religious",
        "notes": "2.4 MB djvu.txt but OCR garbled from two-column layout. hOCR extraction needed. Overlaps Baibala plan.",
        "blocker": "OCR quality BLOCKED for djvu.txt approach. Defer to hOCR/djvu.xml column extraction.",
    },
]

# Reused items already in HK statutes paired imprints dir
REUSED_ITEMS = [
    {
        "source_id": "ia-hk-constitution-1852-haw",
        "title": "He Kumukanawai a me na Kanawai o ka Moi Kamehameha III (1852) — Hawaiian",
        "item_id": "hekumukanawaiam00hawagoog",
        "reused_from": str(HK_ROOT),
        "rights_status": "PD_pre1925_sovereign_edicts",
        "rights_note": "1852 Hawaiian Kingdom publication. PD by age + sovereign-edicts.",
        "status": "reused",
        "alignment_type": "parallel-doc",
        "alignment_method": "section-id",
        "register": "legal",
        "notes": "HAW pair for constitutionand00hawagoog. Already in HK statutes dir. Some W→AV OCR substitutions.",
    },
    {
        "source_id": "ia-hk-statute-laws-1847-haw",
        "title": "Kanawai i kauia e ka Moi Kamehameha III (1847) — Hawaiian",
        "item_id": "kanawaiikauiaek00ricogoog",
        "reused_from": str(HK_ROOT),
        "rights_status": "PD_pre1925_sovereign_edicts",
        "rights_note": "1847 Hawaiian Kingdom publication. PD.",
        "status": "reused",
        "alignment_type": "parallel-doc",
        "alignment_method": "section-id",
        "register": "legal",
        "notes": "HAW pair. Year-range verification required vs EN 1846 item.",
    },
    {
        "source_id": "ia-hk-statute-laws-1847-en",
        "title": "Statute Laws of His Majesty Kamehameha III (1846/47) — English",
        "item_id": "statutelawshism00ricogoog",
        "reused_from": str(HK_ROOT),
        "rights_status": "PD_pre1925_sovereign_edicts",
        "rights_note": "1846/47 Hawaiian Kingdom publication. PD.",
        "status": "reused",
        "alignment_type": "parallel-doc",
        "alignment_method": "section-id",
        "register": "legal",
        "notes": "EN pair. 1.5 MB djvu.txt. Also may contain interleaved EN+HAW columns per earlier probe.",
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def ia_url_safe_get(url: str, dest: Path, label: str, max_bytes: int | None = None) -> dict:
    """Download url to dest. Returns asset record dict."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as resp:
            if max_bytes is not None:
                content_length = int(resp.headers.get("Content-Length", 0))
                if content_length > max_bytes:
                    print(f"  SKIP {label}: {content_length:,} bytes > {max_bytes:,} limit")
                    return {"kind": label, "source_url": url, "local_path": None,
                            "sha256": None, "bytes": content_length,
                            "status": "skipped_too_large"}
            data = resp.read()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        sha = hashlib.sha256(data).hexdigest()
        print(f"  OK {label}: {len(data):,} bytes → {dest.name}")
        return {"kind": label, "source_url": url, "local_path": str(dest),
                "sha256": sha, "bytes": len(data), "status": "downloaded"}
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} {label}: {url}")
        return {"kind": label, "source_url": url, "local_path": None,
                "sha256": None, "bytes": 0, "status": f"http_error_{e.code}"}
    except Exception as e:
        print(f"  ERROR {label}: {e}")
        return {"kind": label, "source_url": url, "local_path": None,
                "sha256": None, "bytes": 0, "status": f"error_{type(e).__name__}"}


def fetch_ia_metadata(item_id: str, dest: Path) -> tuple[dict, dict]:
    """Fetch IA metadata JSON; return (ia_files_dict, asset_record)."""
    url = IA_META_URL.format(item_id=item_id)
    asset = ia_url_safe_get(url, dest, "ia_metadata.json")
    ia_files = {}
    if asset["status"] == "downloaded":
        try:
            meta = json.loads(dest.read_text())
            ia_files = {f["name"]: f for f in meta.get("files", [])}
        except Exception:
            pass
    return ia_files, asset


def find_ia_file(ia_files: dict, suffixes: list[str]) -> str | None:
    """Find first filename matching any of the given suffixes."""
    for suf in suffixes:
        for fname in ia_files:
            if fname.endswith(suf):
                return fname
    return None


def get_file_size(ia_files: dict, filename: str) -> int:
    if filename in ia_files:
        try:
            return int(ia_files[filename].get("size", 0))
        except (ValueError, TypeError):
            return 0
    return 0


def pull_item(item_spec: dict, out_dir: Path) -> list[dict]:
    """Pull all requested assets for one IA item. Returns list of asset records."""
    item_id = item_spec["item_id"]
    pull_kinds = set(item_spec.get("pull", []))
    item_dir = out_dir / item_id
    item_dir.mkdir(parents=True, exist_ok=True)

    records = []

    # Always fetch IA metadata first (needed to discover filenames)
    meta_dest = item_dir / "ia_metadata.json"
    ia_files, meta_asset = fetch_ia_metadata(item_id, meta_dest)
    records.append(meta_asset)
    time.sleep(RATE_LIMIT_S)

    # djvu.txt
    if "djvu.txt" in pull_kinds:
        fname = find_ia_file(ia_files, ["_djvu.txt"])
        if fname:
            url = IA_DL_URL.format(item_id=item_id, filename=fname)
            dest = item_dir / fname
            records.append(ia_url_safe_get(url, dest, "djvu.txt"))
            time.sleep(RATE_LIMIT_S)
        else:
            print(f"  WARN: no djvu.txt found in IA files for {item_id}")
            records.append({"kind": "djvu.txt", "status": "not_found_in_ia"})

    # meta.xml
    if "meta.xml" in pull_kinds:
        fname = find_ia_file(ia_files, ["_meta.xml"])
        if fname:
            url = IA_DL_URL.format(item_id=item_id, filename=fname)
            dest = item_dir / fname
            records.append(ia_url_safe_get(url, dest, "meta.xml"))
            time.sleep(RATE_LIMIT_S)
        else:
            print(f"  WARN: no meta.xml found for {item_id}")
            records.append({"kind": "meta.xml", "status": "not_found_in_ia"})

    # marc.xml
    if "marc.xml" in pull_kinds:
        fname = find_ia_file(ia_files, ["_marc.xml"])
        if fname:
            url = IA_DL_URL.format(item_id=item_id, filename=fname)
            dest = item_dir / fname
            records.append(ia_url_safe_get(url, dest, "marc.xml"))
            time.sleep(RATE_LIMIT_S)
        else:
            print(f"  INFO: no marc.xml for {item_id} (Google scans often lack it)")
            records.append({"kind": "marc.xml", "status": "not_in_ia"})

    # PDF: check size first
    if "pdf" in pull_kinds:
        fname = find_ia_file(ia_files, [".pdf"])
        if fname:
            size = get_file_size(ia_files, fname)
            url = IA_DL_URL.format(item_id=item_id, filename=fname)
            dest = item_dir / fname
            records.append(ia_url_safe_get(url, dest, "pdf", max_bytes=PDF_MAX_BYTES))
            time.sleep(RATE_LIMIT_S)
        else:
            print(f"  INFO: no PDF found for {item_id}")
            records.append({"kind": "pdf", "status": "not_in_ia"})

    return records


def build_reuse_records(item_spec: dict) -> list[dict]:
    """Build asset records for items already on disk in HK statutes dir."""
    item_id = item_spec["item_id"]
    hk = Path(item_spec["reused_from"])
    records = []
    for fname in (hk).glob(f"{item_id}__*"):
        sha = sha256_file(fname)
        records.append({
            "kind": fname.suffix.lstrip(".") or fname.name.split(".")[-1],
            "source_url": f"https://archive.org/download/{item_id}/{fname.name.split('__', 1)[1]}",
            "local_path": str(fname),
            "sha256": sha,
            "bytes": fname.stat().st_size,
            "status": "reused",
        })
    if not records:
        records.append({"kind": "all", "status": "reused_dir_not_found"})
    return records


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    now_utc = datetime.now(timezone.utc).isoformat()
    print(f"\n{'='*70}")
    print(f"Frank — Ulukau-family SFT candidates pull")
    print(f"Output: {OUT_ROOT}")
    print(f"Started: {now_utc}")
    print(f"{'='*70}\n")

    manifest_rows = []

    # 1. Pull new items
    for spec in NEW_ITEMS:
        print(f"\n>>> [{spec['source_id']}] {spec['title']}")
        assets = pull_item(spec, OUT_ROOT)
        row = {
            "source_id": spec["source_id"],
            "source_title": spec["title"],
            "item_id": spec["item_id"],
            "rights_status": spec["rights_status"],
            "rights_note": spec["rights_note"],
            "status": spec["status"],
            "alignment_type": spec["alignment_type"],
            "alignment_method": spec["alignment_method"],
            "register": spec["register"],
            "notes": spec["notes"],
            "prototype_only": True,
            "release_eligible": spec["rights_status"] == "PD_pre1925",
            "fetch_date_utc": now_utc,
            "assets": assets,
        }
        manifest_rows.append(row)

    # 2. Pull inventory-only items (metadata only)
    for spec in INVENTORY_ITEMS:
        print(f"\n>>> [INVENTORY ONLY] [{spec['source_id']}] {spec['title']}")
        assets = pull_item(spec, OUT_ROOT)
        row = {
            "source_id": spec["source_id"],
            "source_title": spec["title"],
            "item_id": spec["item_id"],
            "rights_status": spec["rights_status"],
            "rights_note": spec["rights_note"],
            "status": spec["status"],
            "alignment_type": spec["alignment_type"],
            "alignment_method": spec["alignment_method"],
            "register": spec["register"],
            "notes": spec["notes"],
            "blocker": spec.get("blocker", ""),
            "prototype_only": True,
            "release_eligible": False,
            "fetch_date_utc": now_utc,
            "assets": assets,
        }
        manifest_rows.append(row)

    # 3. Register reused items
    for spec in REUSED_ITEMS:
        print(f"\n>>> [REUSE] [{spec['source_id']}] {spec['title']}")
        assets = build_reuse_records(spec)
        print(f"  Reused {len(assets)} file(s) from {spec['reused_from']}")
        row = {
            "source_id": spec["source_id"],
            "source_title": spec["title"],
            "item_id": spec["item_id"],
            "reused_from": spec["reused_from"],
            "rights_status": spec["rights_status"],
            "rights_note": spec["rights_note"],
            "status": spec["status"],
            "alignment_type": spec["alignment_type"],
            "alignment_method": spec["alignment_method"],
            "register": spec["register"],
            "notes": spec["notes"],
            "prototype_only": True,
            "release_eligible": False,
            "fetch_date_utc": now_utc,
            "assets": assets,
        }
        manifest_rows.append(row)

    # -----------------------------------------------------------------------
    # Write manifest.jsonl
    # -----------------------------------------------------------------------
    manifest_path = OUT_ROOT / "manifest.jsonl"
    with open(manifest_path, "w") as f:
        for row in manifest_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"\nWrote {len(manifest_rows)} rows → {manifest_path}")

    # -----------------------------------------------------------------------
    # Write manifest_summary.json
    # -----------------------------------------------------------------------
    total_bytes_new = sum(
        a.get("bytes", 0)
        for row in manifest_rows if row["status"] != "reused"
        for a in row.get("assets", [])
        if a.get("bytes")
    )
    total_bytes_reused = sum(
        a.get("bytes", 0)
        for row in manifest_rows if row["status"] == "reused"
        for a in row.get("assets", [])
        if a.get("bytes")
    )
    ok_assets = sum(
        1 for row in manifest_rows
        for a in row.get("assets", [])
        if a.get("status") in ("downloaded", "reused")
    )
    summary = {
        "session": "ulukau-family-sft-candidates-round4",
        "fetch_date_utc": now_utc,
        "agent": "frank",
        "source_items_new": len(NEW_ITEMS) + len(INVENTORY_ITEMS),
        "source_items_reused": len(REUSED_ITEMS),
        "source_items_total": len(manifest_rows),
        "assets_ok": ok_assets,
        "bytes_new_downloaded": total_bytes_new,
        "bytes_reused_registered": total_bytes_reused,
        "manifest_rows": len(manifest_rows),
        "notes": (
            "New pulls: Hawaiian Phrase Book 1881, 1852 Constitution EN, "
            "Gospel of John 1854 (Bible cap risk), Sanitary Instructions 1881. "
            "Inventory only: Diglot NT 1859 (OCR blocked). "
            "Reused from HK statutes dir: 1852 HAW constitution, 1847 HAW/EN statute laws."
        ),
    }
    summary_path = OUT_ROOT / "manifest_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote summary → {summary_path}")

    # -----------------------------------------------------------------------
    # Write CLEANUP_NOTES.json
    # -----------------------------------------------------------------------
    cleanup = {
        "session": "ulukau-family-sft-candidates-round4",
        "notes_by_source": [
            {
                "source_id": "ia-hawaiian-phrase-book-1881",
                "classification": "full",
                "adapter_readiness": "adapter_needed",
                "adapter_approach": "Column-detection on djvu.txt: split lines on whitespace gap between EN/HAW halves; filter entries where HAW side < 3 chars.",
                "blocker": "None — ready for 325_build_phrase_book_candidates.py adapter.",
                "estimated_rows": "800-2000",
            },
            {
                "source_id": "ia-hk-constitution-1852-en",
                "classification": "full",
                "adapter_readiness": "adapter_needed",
                "adapter_approach": "Extend hawaiian-kingdom-statutes adapter: add 1852 pair hekumukanawaiam00hawagoog (HAW) + constitutionand00hawagoog (EN). Section-id alignment. Check W→AV OCR on HAW side.",
                "blocker": "Linus: confirm 1852 pair is in register cap (<=15% combined legal tokens).",
                "estimated_rows": "200-600",
            },
            {
                "source_id": "ia-hk-constitution-1852-haw",
                "classification": "reused",
                "adapter_readiness": "adapter_needed",
                "adapter_approach": "Same as ia-hk-constitution-1852-en above.",
                "blocker": "Same as EN pair above.",
                "estimated_rows": "200-600 (combined with EN pair)",
            },
            {
                "source_id": "ia-hk-statute-laws-1847-haw",
                "classification": "reused",
                "adapter_readiness": "inventory_only",
                "adapter_approach": "Year-range verification first: does EN 1846 cover exactly the same laws as HAW 1847?",
                "blocker": "Linus: year-range verification required before pairing.",
                "estimated_rows": "100-400",
            },
            {
                "source_id": "ia-hk-statute-laws-1847-en",
                "classification": "reused",
                "adapter_readiness": "inventory_only",
                "adapter_approach": "Same as HAW 1847 above. Also note: may contain interleaved EN+HAW columns per earlier probe.",
                "blocker": "Year-range verification + interleaved-column check.",
                "estimated_rows": "100-400",
            },
            {
                "source_id": "ia-gospel-john-parallel-columns-1854",
                "classification": "raw",
                "adapter_readiness": "adapter_needed_bible_cap_risk",
                "adapter_approach": "Verse-id alignment using chapter.verse numbers in djvu.txt. BUT: parallel-column OCR may interleave EN+HAW lines. Linus: confirm whether 1854 parallel-column djvu.txt is cleanly split or interleaved.",
                "blocker": "Bible cap risk (<=30% total parallel train tokens); confirm OCR column quality; dedupe against Baibala 1839.",
                "estimated_rows": "700-880 verses (John only)",
            },
            {
                "source_id": "ia-sanitary-instructions-1881",
                "classification": "raw",
                "adapter_readiness": "adapter_needed_labse_blocked",
                "adapter_approach": "Two-phase: (1) Detect EN/HAW volume boundary in djvu.txt; (2) Align chapters by number; (3) LaBSE paragraph-level scoring >= 0.75.",
                "blocker": "Requires LaBSE infrastructure (Rusty). No deterministic alignment.",
                "estimated_rows": "200-800",
            },
            {
                "source_id": "ia-diglot-nt-1859",
                "classification": "inventory_only",
                "adapter_readiness": "blocked_ocr",
                "adapter_approach": "hOCR/djvu.xml bounding-box column extraction needed for two-column OCR recovery.",
                "blocker": "OCR quality BLOCKED. djvu.txt two-column garbled. Overlaps Baibala plan.",
                "estimated_rows": "0 until hOCR extraction",
            },
        ],
        "global_notes": [
            "Do NOT delete or modify HK statutes paired imprints root. Reused files are registered by path only.",
            "Phrase Book (1881) is highest-priority new adapter — no blockers, PD-clear, deterministic column alignment.",
            "Sanitary Instructions (1881) is unique health/medical register — high value once LaBSE infra is available.",
            "Gospel of John (1854) needs Bible cap accounting before emitting candidates.",
            "Diglot NT (1859) deferred indefinitely until hOCR column extraction is feasible.",
        ],
    }
    cleanup_path = OUT_ROOT / "CLEANUP_NOTES.json"
    cleanup_path.write_text(json.dumps(cleanup, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote CLEANUP_NOTES → {cleanup_path}")

    # -----------------------------------------------------------------------
    # Count structured rows across all stage2 candidates
    # -----------------------------------------------------------------------
    cands_dir = REPO_ROOT / "data" / "stage2" / "candidates"
    print(f"\n{'='*70}")
    print("Structured row counts in data/stage2/candidates/")
    print(f"{'='*70}")
    total_rows = 0
    row_counts = {}
    if cands_dir.exists():
        for jl in sorted(cands_dir.glob("*.jsonl")):
            count = sum(1 for line in jl.read_text().splitlines() if line.strip())
            row_counts[jl.name] = count
            total_rows += count
            print(f"  {jl.name}: {count:,} rows")
    print(f"  {'─'*40}")
    print(f"  TOTAL: {total_rows:,} structured rows")

    # Append row counts to summary
    summary["stage2_candidate_row_counts"] = row_counts
    summary["stage2_candidate_total_rows"] = total_rows
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")

    print(f"\n{'='*70}")
    print("DONE.")
    print(f"{'='*70}")
    return total_rows


if __name__ == "__main__":
    main()
