#!/usr/bin/env python3
"""Stage-2 parallel source collection plan (100-phase).

Reads ``data-sources/stage2-parallel-fetch-plan.json`` and emits the
numbered 100-phase plan consumed by ``scripts/207_fetch_stage2_parallel_raw.py``.
The source inventory remains the policy/source-of-truth artifact; this script
turns it into a local execution plan with explicit target math and per-source
fetch gates.

Safety posture:

* No network calls. This is a planner only.
* Writes only under ``data/local/stage2_parallel/`` (gitignored).
* Keeps excluded sources out of the executable plan. Eval-only sources are
  excluded by default unless ``--include-eval`` is passed.
* Records the Stage-2 target as 80k bidirectional SFT rows == 40k canonical
  pairs before retention rows.

Usage::

    python scripts/107_collect_stage2_parallel.py --dry-run
    python scripts/107_collect_stage2_parallel.py
    python scripts/107_collect_stage2_parallel.py --include-eval --print

Exit codes: 0 success, 2 I/O / malformed inventory.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INVENTORY = REPO_ROOT / "data-sources" / "stage2-parallel-fetch-plan.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "local" / "stage2_parallel"
TATOEBA_PINNED_DUMP = REPO_ROOT / "data-sources" / "tatoeba" / "PINNED_DUMP.json"

SFT_ROW_TARGET = 80_000
DIRECTIONS_PER_PAIR = 2

FETCHER_SCRIPT = "scripts/207_fetch_stage2_parallel_raw.py"

# Existing source-specific paths that should not be hidden by the generic
# static downloader. The generic 207 script may still fetch raw bytes for
# sources with concrete URLs; these adapter hints tell the operator where the
# candidate-row conversion or specialized fetch path lives.
SOURCE_SPECIFIC_ADAPTERS: dict[str, str] = {
    "bible-haw-baibala-pinned-edition": "scripts/206_fetch_baibala_raw.py --side haw",
    "bible-eng-pd-anchor": "scripts/206_fetch_baibala_raw.py --side eng",
    "bible-haw-archive-org-pre1925": "scripts/206_fetch_baibala_raw.py --side haw",
    "tatoeba-haw-eng": "data-sources/tatoeba/fetch.py",
}


def _utcnow_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _relative_display(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _safe_filename_from_url(url: str, fallback: str) -> str:
    parsed = urlparse(url)
    name = Path(parsed.path).name or fallback
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return name or fallback


def _dedupe_filename(filename: str, index: int, seen: set[str]) -> str:
    if filename not in seen:
        seen.add(filename)
        return filename
    path = Path(filename)
    suffix = "".join(path.suffixes)
    stem = filename[: -len(suffix)] if suffix else filename
    candidate = f"{stem}-{index}{suffix}"
    while candidate in seen:
        candidate = f"{stem}-{index}-{len(seen)}{suffix}"
    seen.add(candidate)
    return candidate


def load_inventory(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as fh:
            inv = json.load(fh)
    except OSError as exc:
        raise RuntimeError(f"failed to read inventory {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"inventory is not valid JSON: {path}: {exc}") from exc
    if not isinstance(inv.get("sources"), list):
        raise RuntimeError(f"inventory missing list field `sources`: {path}")
    return inv


def source_gates(src: dict[str, Any]) -> list[str]:
    """Return conservative gates that must be acknowledged before fetching."""
    gates: list[str] = []
    rights = str(src.get("rights_status_hint") or "")
    status = str(src.get("verification_status") or "")
    acquisition = src.get("acquisition_plan") or {}

    if rights == "eval_only":
        gates.append("eval_only")
    if rights in {"rights_review_required", "unknown_review_required"}:
        gates.append("rights_review_required")
    if status == "pending_rights_review" and "rights_review_required" not in gates:
        gates.append("rights_review_required")
    if status == "pending_endpoint_check":
        gates.append("endpoint_check_required")

    for blocker in acquisition.get("do_not_invoke_until") or []:
        gates.append(f"blocked_until:{blocker}")
    return gates


def source_fetch_kind(src: dict[str, Any]) -> str:
    """Classify the fetch shape for operator routing."""
    if source_concrete_urls(src):
        return "static-download"
    if src.get("source_id") in SOURCE_SPECIFIC_ADAPTERS:
        return "source-specific-adapter"
    if src.get("url_templates"):
        return "template-or-api-adapter-needed"
    return "adapter-needed"


def source_concrete_urls(src: dict[str, Any]) -> list[str]:
    """Return concrete raw URLs, including source-specific pinned supplements."""
    source_id = str(src.get("source_id") or "")
    if source_id == "tatoeba-haw-eng" and TATOEBA_PINNED_DUMP.exists():
        try:
            pinned = json.loads(TATOEBA_PINNED_DUMP.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return list(src.get("concrete_urls") or [])
        urls = [
            pinned.get("haw_sentences_url"),
            pinned.get("haw_eng_links_url"),
            pinned.get("eng_sentences_url"),
        ]
        return [str(u) for u in urls if u]
    return list(src.get("concrete_urls") or [])


def build_source_entry(src: dict[str, Any]) -> dict[str, Any]:
    source_id = str(src["source_id"])
    urls = source_concrete_urls(src)
    seen_filenames: set[str] = set()
    artifacts = []
    for i, url in enumerate(urls, start=1):
        filename = _safe_filename_from_url(url, f"{source_id}-{i}.raw")
        filename = _dedupe_filename(filename, i, seen_filenames)
        artifacts.append({
            "artifact_id": f"{source_id}:{i}",
            "url": url,
            "filename": filename,
        })

    kind = source_fetch_kind(src)
    gates = source_gates(src)
    if kind == "static-download":
        fetch_state = "ready-static-download" if not gates else "gated-static-download"
    else:
        fetch_state = kind

    return {
        "source_id": source_id,
        "name": src.get("name"),
        "tier": src.get("tier"),
        "alignment_type": src.get("alignment_type"),
        "rights_status_hint": src.get("rights_status_hint"),
        "verification_status": src.get("verification_status"),
        "license_observed": src.get("license_observed"),
        "tos_or_license_url": src.get("tos_or_license_url"),
        "homepage_or_access": src.get("homepage_or_access"),
        "fetch_kind": kind,
        "fetch_state": fetch_state,
        "fetch_gates": gates,
        "raw_storage_root": f"data/raw/{source_id}/",
        "download_artifacts": artifacts,
        "source_specific_adapter": SOURCE_SPECIFIC_ADAPTERS.get(source_id),
        "generic_fetcher_script": FETCHER_SCRIPT if kind == "static-download" else None,
        "candidate_output_hint": f"data/stage2/candidates/{source_id}.jsonl",
        "prototype_notes": src.get("prototype_notes") or [],
        "exclusions_or_risks": src.get("exclusions_or_risks") or [],
    }


def build_plan(
    inventory: dict[str, Any],
    *,
    inventory_path: Path,
    include_eval: bool,
    sft_row_target: int = SFT_ROW_TARGET,
) -> dict[str, Any]:
    pair_target = sft_row_target // DIRECTIONS_PER_PAIR
    sources: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    for src in inventory["sources"]:
        source_id = str(src.get("source_id") or "")
        alignment_type = str(src.get("alignment_type") or "")
        verification = str(src.get("verification_status") or "")
        rights = str(src.get("rights_status_hint") or "")

        if alignment_type == "excluded" or verification == "excluded_pending_verification":
            skipped.append({"source_id": source_id, "reason": "excluded"})
            continue
        if rights == "eval_only" and not include_eval:
            skipped.append({"source_id": source_id, "reason": "eval_only"})
            continue
        sources.append(build_source_entry(src))

    return {
        "schema_version": "stage2-parallel-collect-plan.v1",
        "generated_by": "scripts/107_collect_stage2_parallel.py",
        "generated_at_utc": _utcnow_iso(),
        "source_inventory": {
            "path": _relative_display(inventory_path),
            "sha256": _sha256_file(inventory_path),
            "artifact_id": inventory.get("artifact_id"),
            "schema_version": inventory.get("schema_version"),
        },
        "stage2_target": {
            "sft_rows": sft_row_target,
            "canonical_pair_target": pair_target,
            "directions_per_pair": DIRECTIONS_PER_PAIR,
            "retention_slice": (
                "10-20% by token, merged later; retention rows are not counted "
                "inside the 80k directional-row target."
            ),
        },
        "policy": {
            "dry_run_default": True,
            "execute_flag_required": True,
            "raw_storage_root": "data/raw/<source_id>/<YYYYMMDD>/",
            "stage2_storage_root": "data/stage2/",
            "no_public_artifacts": True,
        },
        "fetcher_script": FETCHER_SCRIPT,
        "include_eval": include_eval,
        "sources": sources,
        "skipped_sources": skipped,
        "summary": {
            "source_count": len(sources),
            "static_download_sources": sum(
                1 for s in sources if s["fetch_kind"] == "static-download"
            ),
            "gated_static_download_sources": sum(
                1 for s in sources if s["fetch_state"] == "gated-static-download"
            ),
            "source_specific_adapter_sources": sum(
                1 for s in sources if s["source_specific_adapter"]
            ),
        },
    }


def write_plan(plan: dict[str, Any], out_dir: Path, *, dry_run: bool) -> Path:
    out_path = out_dir / "collect_plan.json"
    if dry_run:
        print(f"[DRY-RUN] would write {_relative_display(out_path)}")
        return out_path

    out_dir.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(plan, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    readme = out_dir / "README.txt"
    if not readme.exists():
        readme.write_text(
            "This directory is gitignored. It holds the Stage-2 parallel\n"
            "collection plan emitted by scripts/107_collect_stage2_parallel.py\n"
            "and consumed by scripts/207_fetch_stage2_parallel_raw.py.\n"
            "Do not commit anything under data/.\n",
            encoding="utf-8",
        )
    return out_path


def print_summary(plan: dict[str, Any]) -> None:
    target = plan["stage2_target"]
    summary = plan["summary"]
    print("Stage-2 parallel collect plan")
    print(f"  target_sft_rows       : {target['sft_rows']:,}")
    print(f"  canonical_pair_target : {target['canonical_pair_target']:,}")
    print(f"  source_count          : {summary['source_count']}")
    print(f"  static_download       : {summary['static_download_sources']}")
    print(f"  gated_static_download : {summary['gated_static_download_sources']}")
    print(f"  source_specific       : {summary['source_specific_adapter_sources']}")
    if plan["skipped_sources"]:
        skipped = ", ".join(
            f"{s['source_id']}({s['reason']})" for s in plan["skipped_sources"]
        )
        print(f"  skipped               : {skipped}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--include-eval", action="store_true",
                        help="Include eval-only sources in the plan, still gated in 207.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Build and print the plan summary without writing files.")
    parser.add_argument("--print", dest="print_plan", action="store_true",
                        help="Pretty-print the full plan JSON.")
    parser.add_argument("--sft-row-target", type=int, default=SFT_ROW_TARGET,
                        help=f"Directional SFT row target (default {SFT_ROW_TARGET}).")
    args = parser.parse_args(argv)

    if args.sft_row_target < 2 or args.sft_row_target % DIRECTIONS_PER_PAIR:
        print("--sft-row-target must be an even integer >= 2", file=sys.stderr)
        return 2

    try:
        inventory = load_inventory(args.inventory)
        plan = build_plan(
            inventory,
            inventory_path=args.inventory,
            include_eval=args.include_eval,
            sft_row_target=args.sft_row_target,
        )
        out_path = write_plan(plan, args.out, dry_run=args.dry_run)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: failed to write plan: {exc}", file=sys.stderr)
        return 2

    print_summary(plan)
    print(f"  output                : {_relative_display(out_path)}")
    if args.print_plan:
        print()
        print(json.dumps(plan, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
