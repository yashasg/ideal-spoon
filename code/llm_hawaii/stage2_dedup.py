"""Stage-2 cross-source exact-pair dedup preference policy.

The manifest builder calls this module after candidate rows have been scored and
schema-normalized, but before cap math.  It only collapses exact ``sha256_pair``
collisions; near-duplicate and source-cap policy remains elsewhere.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

POLICY_VERSION = "stage2-cross-source-dedup-v0.1"

BIBLE_FAMILIES = {
    "bible-1868",
    "bible-1839",
    "gospel-john-1854",
    "bible-other",
}

# Ordered rules: first matching rule chooses the retained source family.
# Keep these data-first so policy review can audit preference changes without
# reverse-engineering branches.
PREFERENCE_RULES: list[dict[str, Any]] = [
    {
        "id": "hooilina-over-bible",
        "prefer": ["hooilina"],
        "when_also_present": sorted(BIBLE_FAMILIES),
        "rationale": "Hoʻoilina newspaper/periodical translations are preferred over Bible text on exact overlap per Stage-2 register diversity policy.",
    },
    {
        "id": "wikimedia-cx-over-opus-wikimedia",
        "prefer": ["wikimedia-cx"],
        "when_also_present": ["opus-wikimedia"],
        "rationale": "Canonical Wikimedia CX rows retain source revision/article provenance; OPUS-Wikimedia is a mirrored derivative.",
    },
    {
        "id": "tatoeba-over-opus-tatoeba",
        "prefer": ["tatoeba"],
        "when_also_present": ["opus-tatoeba"],
        "rationale": "Canonical Tatoeba rows retain native sentence/link IDs; OPUS-Tatoeba is a mirrored derivative.",
    },
    {
        "id": "bible-1868-over-other-bible-editions",
        "prefer": ["bible-1868"],
        "when_also_present": ["bible-1839", "gospel-john-1854", "bible-other"],
        "rationale": "Exact Bible cross-edition overlaps keep the later 1868 edition as the more standardized orthography while edition-level caps still allow non-duplicate rows.",
    },
]


def source_family(row: dict[str, Any]) -> str:
    """Return the policy family used for cross-source dedup preference."""
    source = str(row.get("source") or row.get("source_id") or "")
    pair_id = str(row.get("pair_id") or row.get("source_pair_id") or "")

    if source == "hooilina":
        return "hooilina"
    if source == "wikimedia-cx-en-haw":
        return "wikimedia-cx"
    if source == "tatoeba":
        return "tatoeba"
    if source == "opus-haw-subsets":
        if pair_id.startswith("opus-tatoeba-"):
            return "opus-tatoeba"
        if pair_id.startswith("opus-wikimedia-"):
            return "opus-wikimedia"
        return "opus-other"
    if source == "baibala-hemolele-1868":
        return "bible-1868"
    if source == "baibala-hemolele-1839":
        return "bible-1839"
    if source == "gospel_john_1854":
        return "gospel-john-1854"
    if source.startswith("bible") or source.startswith("baibala"):
        return "bible-other"
    return source or "<missing>"


def _stable_row_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("source") or row.get("source_id") or ""),
        str(row.get("pair_id") or row.get("source_pair_id") or ""),
        str(row.get("record_id_haw") or ""),
    )


def select_preferred(rows: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    """Choose one row from an exact-pair collision group.

    Returns ``(kept_row, dropped_rows, reason)``. If no preference rule applies,
    a deterministic source/pair-id fallback keeps output stable.
    """
    if not rows:
        raise ValueError("select_preferred requires at least one row")
    if len(rows) == 1:
        return rows[0], [], "unique_pair_hash"

    families = {source_family(row) for row in rows}
    for rule in PREFERENCE_RULES:
        preferred = set(rule["prefer"])
        others = set(rule["when_also_present"])
        if families & preferred and families & others:
            candidates = [row for row in rows if source_family(row) in preferred]
            kept = sorted(candidates, key=_stable_row_key)[0]
            dropped = [row for row in rows if row is not kept]
            return kept, dropped, str(rule["id"])

    kept = sorted(rows, key=_stable_row_key)[0]
    dropped = [row for row in rows if row is not kept]
    return kept, dropped, "deterministic_fallback_no_policy_rule"


def collapse_pair_hash_duplicates(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Collapse exact ``sha256_pair`` duplicate groups and return stats."""
    groups: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    passthrough: list[tuple[int, dict[str, Any]]] = []
    for idx, row in enumerate(rows):
        pair_hash = row.get("sha256_pair")
        if isinstance(pair_hash, str) and pair_hash:
            groups[pair_hash].append((idx, row))
        else:
            passthrough.append((idx, row))

    kept_by_index: dict[int, dict[str, Any]] = {idx: row for idx, row in passthrough}
    reason_counts: Counter[str] = Counter()
    source_pair_counts: Counter[str] = Counter()
    dropped_examples: list[dict[str, Any]] = []
    duplicate_groups = 0
    dropped_total = 0

    for pair_hash, indexed in groups.items():
        group_rows = [row for _, row in indexed]
        group_sources = {str(row.get("source") or row.get("source_id") or "<missing>") for row in group_rows}
        if len(indexed) == 1 or len(group_sources) == 1:
            for idx, row in indexed:
                kept_by_index[idx] = row
            continue

        duplicate_groups += 1
        kept, dropped, reason = select_preferred(group_rows)
        kept_idx = next(idx for idx, row in indexed if row is kept)
        kept_by_index[kept_idx] = kept
        reason_counts[reason] += len(dropped)
        dropped_total += len(dropped)

        kept_source = str(kept.get("source") or kept.get("source_id") or "<missing>")
        for row in dropped:
            dropped_source = str(row.get("source") or row.get("source_id") or "<missing>")
            source_pair_counts[f"{kept_source} <- {dropped_source}"] += 1
            reasons = row.setdefault("manual_review_reasons", [])
            if isinstance(reasons, list):
                reasons.append(f"cross_source_exact_pair_dedup_drop:{reason}")
            if len(dropped_examples) < 12:
                dropped_examples.append({
                    "sha256_pair": pair_hash,
                    "reason": reason,
                    "kept_source": kept_source,
                    "kept_pair_id": kept.get("pair_id") or kept.get("source_pair_id"),
                    "dropped_source": dropped_source,
                    "dropped_pair_id": row.get("pair_id") or row.get("source_pair_id"),
                })

    kept_rows = [kept_by_index[idx] for idx in sorted(kept_by_index)]
    stats = {
        "policy_version": POLICY_VERSION,
        "rules": PREFERENCE_RULES,
        "input_rows": len(rows),
        "output_rows": len(kept_rows),
        "duplicate_groups": duplicate_groups,
        "dropped_rows": dropped_total,
        "drop_reasons": dict(reason_counts),
        "drop_source_pairs": dict(source_pair_counts),
        "dropped_examples": dropped_examples,
    }
    return kept_rows, stats
