"""Stage-2 duplicate and near-duplicate preference policy.

The manifest builder calls this module after candidate rows have been scored and
schema-normalized, but before cap math.  Exact ``sha256_pair`` collisions are
collapsed first, then optional one-sided exact-text caps and near-dupe collapse
can be applied with deterministic source preference.
"""

from __future__ import annotations

import difflib
import hashlib
import re
import unicodedata

from llm_hawaii.stage2_canonical import HAW_OKINA_FOLD
from collections import Counter, defaultdict
from typing import Any

POLICY_VERSION = "stage2-cross-source-dedup-v0.6"
EXACT_SIDE_MAX_PER_KEY = 3
SHORT_EXACT_SIDE_MAX_PER_KEY = 2
SHORT_EXACT_SIDE_TOKEN_MAX = 3
SHORT_EXACT_OTHER_SIDE_MIN_TOKENS = 4
SOFTWARE_L10N_SHORT_VARIANT_TOKEN_MAX = 6
NEAR_DUPE_THRESHOLD = 0.92
_TOKEN_RE = re.compile(r"[\wʻ'-]+", re.UNICODE)
_OKINA_FOLD = HAW_OKINA_FOLD
_INVISIBLE_FORMAT_CONTROLS = str.maketrans("", "", "\u00ad\u200b\u200c\u200d\ufeff")
WEBLATE_SOURCES = {"weblate", "weblate-en-haw"}

BIBLE_FAMILIES = {
    "bible-1868",
    "bible-1839",
    "gospel-john-1854",
    "bible-other",
}

SOURCE_PRIORITY: dict[str, int] = {
    "hooilina": 0,
    "baibala-hemolele-1868": 1,
    "baibala-hemolele-1839": 2,
    "gospel_john_1854": 3,
    "hk_statutes_1897": 4,
    "hk-statutes-1897": 4,
    "hk_constitution_1852": 5,
    "wikimedia-cx-en-haw": 6,
    "tatoeba": 7,
    "weblate": 8,
    "weblate-en-haw": 8,
    "kaikki-haw-en-wiktionary": 9,
    "kaikki": 9,
    "andrews-1865-en-haw-vocab-appendix": 10,
    "andrews": 10,
    "ia-hawaiian-phrase-book-1881": 11,
    "opus-haw-subsets": 20,
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
        "id": "tatoeba-over-weblate",
        "prefer": ["tatoeba"],
        "when_also_present": ["weblate"],
        "rationale": "Tatoeba sentence pairs outrank short software-localization strings on exact overlap.",
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
    if source in WEBLATE_SOURCES:
        return "weblate"
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


def _source_priority(row: dict[str, Any]) -> int:
    source = str(row.get("source") or row.get("source_id") or "")
    if source in SOURCE_PRIORITY:
        return SOURCE_PRIORITY[source]
    family = source_family(row)
    if family.startswith("bible") or family == "gospel-john-1854":
        return 2
    return 50


def _text_len(row: dict[str, Any]) -> int:
    return len(str(row.get("text_en") or "")) + len(str(row.get("text_haw") or ""))


def canonical_sort_key(row: dict[str, Any]) -> tuple[int, int, str, str, str]:
    """Deterministic keep-order: richer source, longer text, stable ids."""
    return (*(_source_priority(row), -_text_len(row)), *_stable_row_key(row))


def _append_reason(row: dict[str, Any], reason: str) -> None:
    reasons = row.setdefault("manual_review_reasons", [])
    if isinstance(reasons, list):
        reasons.append(reason)


def _normal_text(text: Any, *, haw: bool) -> str:
    s = unicodedata.normalize("NFC", str(text or "")).translate(_INVISIBLE_FORMAT_CONTROLS)
    if haw:
        s = s.translate(_OKINA_FOLD)
    return " ".join(_TOKEN_RE.findall(s.casefold()))


def _token_list(text: Any, *, haw: bool) -> list[str]:
    return _normal_text(text, haw=haw).split()


def _token_count(text: Any, *, haw: bool) -> int:
    return len(_token_list(text, haw=haw))


def _tokens(text: Any, *, haw: bool) -> set[str]:
    return set(_token_list(text, haw=haw))


def _text_similarity(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def _set_similarity(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


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

    kept = sorted(rows, key=canonical_sort_key)[0]
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
            _append_reason(row, f"cross_source_exact_pair_dedup_drop:{reason}")
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


def _cap_exact_key(
    rows: list[dict[str, Any]],
    *,
    key_name: str,
    other_key_name: str,
    key_text_name: str,
    key_text_haw: bool,
    other_text_name: str,
    other_text_haw: bool,
    max_per_key: int,
    reason_prefix: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if max_per_key < 1:
        raise ValueError("max_per_key must be >= 1")
    groups: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    passthrough: list[tuple[int, dict[str, Any]]] = []
    for idx, row in enumerate(rows):
        key = row.get(key_name)
        if isinstance(key, str) and key:
            groups[key].append((idx, row))
        else:
            passthrough.append((idx, row))

    kept_by_index: dict[int, dict[str, Any]] = {idx: row for idx, row in passthrough}
    capped_groups = 0
    short_policy_groups = 0
    dropped_total = 0
    short_other_too_short = 0
    source_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    group_size_histogram: Counter[str] = Counter()
    examples: list[dict[str, Any]] = []

    for key, indexed in groups.items():
        other_values = {row.get(other_key_name) for _, row in indexed}
        sources = {str(row.get("source") or row.get("source_id") or "") for _, row in indexed}
        if "baibala-hemolele-1839" in sources:
            for idx, row in indexed:
                kept_by_index[idx] = row
            continue
        if len(other_values) <= 1:
            for idx, row in indexed:
                kept_by_index[idx] = row
            continue

        key_lengths = [_token_count(row.get(key_text_name), haw=key_text_haw) for _, row in indexed]
        nonzero_key_lengths = [length for length in key_lengths if length > 0]
        has_weblate = bool(sources & WEBLATE_SOURCES)
        short_token_max = SOFTWARE_L10N_SHORT_VARIANT_TOKEN_MAX if has_weblate else SHORT_EXACT_SIDE_TOKEN_MAX
        is_short_key = bool(nonzero_key_lengths) and max(nonzero_key_lengths) <= short_token_max
        effective_max = SHORT_EXACT_SIDE_MAX_PER_KEY if is_short_key else max_per_key
        eligible = indexed
        if is_short_key:
            short_policy_groups += 1
            filtered: list[tuple[int, dict[str, Any]]] = []
            for idx, row in indexed:
                source = str(row.get("source") or row.get("source_id") or "<missing>")
                other_tokens = _token_count(row.get(other_text_name), haw=other_text_haw)
                if other_tokens >= SHORT_EXACT_OTHER_SIDE_MIN_TOKENS:
                    filtered.append((idx, row))
                else:
                    dropped_total += 1
                    short_other_too_short += 1
                    source_counts[source] += 1
                    reason_counts[f"short_other_min_{SHORT_EXACT_OTHER_SIDE_MIN_TOKENS}"] += 1
                    _append_reason(row, f"{reason_prefix}_short_variant_drop:other_tokens_lt_{SHORT_EXACT_OTHER_SIDE_MIN_TOKENS}")
            eligible = filtered

        if len(eligible) <= effective_max:
            for idx, row in eligible:
                kept_by_index[idx] = row
            continue

        capped_groups += 1
        group_size_histogram[str(len(eligible))] += 1
        ranked = sorted(eligible, key=lambda item: canonical_sort_key(item[1]))
        keep = set(id(row) for _, row in ranked[:effective_max])
        kept_sources = []
        dropped_sources = []
        for idx, row in eligible:
            source = str(row.get("source") or row.get("source_id") or "<missing>")
            if id(row) in keep:
                kept_by_index[idx] = row
                kept_sources.append(source)
            else:
                dropped_total += 1
                source_counts[source] += 1
                reason_counts[f"max_{effective_max}"] += 1
                dropped_sources.append(source)
                _append_reason(row, f"{reason_prefix}_cap_drop:max_{effective_max}")
        if len(examples) < 12:
            examples.append({
                "key": key,
                "group_size": len(indexed),
                "eligible_group_size": len(eligible),
                "effective_max_per_key": effective_max,
                "short_variant_policy_applied": is_short_key,
                "kept_sources": kept_sources,
                "dropped_sources": dropped_sources,
            })

    kept_rows = [kept_by_index[idx] for idx in sorted(kept_by_index)]
    return kept_rows, {
        "input_rows": len(rows),
        "output_rows": len(kept_rows),
        "max_per_key": max_per_key,
        "short_exact_side_max_per_key": SHORT_EXACT_SIDE_MAX_PER_KEY,
        "short_exact_side_token_max": SHORT_EXACT_SIDE_TOKEN_MAX,
        "short_exact_other_side_min_tokens": SHORT_EXACT_OTHER_SIDE_MIN_TOKENS,
        "short_policy_groups": short_policy_groups,
        "capped_groups": capped_groups,
        "dropped_rows": dropped_total,
        "short_other_too_short_dropped_rows": short_other_too_short,
        "drop_reasons": dict(reason_counts),
        "drop_sources": dict(source_counts),
        "capped_group_size_histogram": dict(group_size_histogram),
        "examples": examples,
    }


def cap_exact_en(rows: list[dict[str, Any]], max_per_key: int = EXACT_SIDE_MAX_PER_KEY) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Cap rows sharing one English clean hash but multiple Hawaiian hashes."""
    return _cap_exact_key(
        rows,
        key_name="sha256_en_clean",
        other_key_name="sha256_haw_clean",
        key_text_name="text_en",
        key_text_haw=False,
        other_text_name="text_haw",
        other_text_haw=True,
        max_per_key=max_per_key,
        reason_prefix="exact_en",
    )


def cap_exact_haw(rows: list[dict[str, Any]], max_per_key: int = EXACT_SIDE_MAX_PER_KEY) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Cap rows sharing one Hawaiian clean hash but multiple English hashes."""
    return _cap_exact_key(
        rows,
        key_name="sha256_haw_clean",
        other_key_name="sha256_en_clean",
        key_text_name="text_haw",
        key_text_haw=True,
        other_text_name="text_en",
        other_text_haw=False,
        max_per_key=max_per_key,
        reason_prefix="exact_haw",
    )


def _near_blocks(rows: list[dict[str, Any]]) -> dict[tuple[str, str, str, str], list[int]]:
    blocks: dict[tuple[str, str, str, str], list[int]] = defaultdict(list)
    for idx, row in enumerate(rows):
        en_tokens = _normal_text(row.get("text_en"), haw=False).split()
        haw_tokens = _normal_text(row.get("text_haw"), haw=True).split()
        if not en_tokens or not haw_tokens:
            continue
        key = (en_tokens[0], en_tokens[-1], haw_tokens[0], haw_tokens[-1])
        blocks[key].append(idx)
        blocks[("haw-token-set", " ".join(sorted(set(haw_tokens))), "", "")].append(idx)
        if len(en_tokens) <= 6:
            blocks[("short-en", " ".join(sorted(set(en_tokens))), haw_tokens[0], haw_tokens[-1])].append(idx)
    return blocks


def near_duplicate_groups(rows: list[dict[str, Any]], threshold: float = NEAR_DUPE_THRESHOLD) -> list[list[int]]:
    """Return index groups whose EN and HAW sides are both near-identical."""
    parent = list(range(len(rows)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    prepared = []
    for row in rows:
        en = _normal_text(row.get("text_en"), haw=False)
        haw = _normal_text(row.get("text_haw"), haw=True)
        prepared.append((en, haw, set(en.split()), set(haw.split())))

    seen_pairs: set[tuple[int, int]] = set()
    for idxs in _near_blocks(rows).values():
        unique = sorted(set(idxs))
        if len(unique) < 2 or len(unique) > 400:
            continue
        block_sources = {str(rows[idx].get("source") or rows[idx].get("source_id") or "") for idx in unique}
        if len(block_sources) < 2:
            continue
        for pos, i in enumerate(unique):
            for j in unique[pos + 1:]:
                if (rows[i].get("source") or rows[i].get("source_id")) == (rows[j].get("source") or rows[j].get("source_id")):
                    continue
                pair = (i, j)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                en_i, haw_i, en_tok_i, haw_tok_i = prepared[i]
                en_j, haw_j, en_tok_j, haw_tok_j = prepared[j]
                en_score = max(_text_similarity(en_i, en_j), _set_similarity(en_tok_i, en_tok_j))
                if en_score < threshold:
                    continue
                haw_score = max(_text_similarity(haw_i, haw_j), _set_similarity(haw_tok_i, haw_tok_j))
                if haw_score >= threshold:
                    union(i, j)

    grouped: dict[int, list[int]] = defaultdict(list)
    for idx in range(len(rows)):
        root = find(idx)
        if root != idx:
            grouped[root].append(idx)
            if root not in grouped[root]:
                grouped[root].append(root)
    return [sorted(set(v)) for v in grouped.values() if len(set(v)) > 1]


def collapse_near_dupes(rows: list[dict[str, Any]], threshold: float = NEAR_DUPE_THRESHOLD) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Collapse near-duplicate EN/HAW groups using canonical source preference."""
    groups = near_duplicate_groups(rows, threshold=threshold)
    drop_ids: set[int] = set()
    source_counts: Counter[str] = Counter()
    examples: list[dict[str, Any]] = []
    for group in groups:
        ranked = sorted(group, key=lambda idx: canonical_sort_key(rows[idx]))
        keep_idx = ranked[0]
        for idx in ranked[1:]:
            drop_ids.add(idx)
            source = str(rows[idx].get("source") or rows[idx].get("source_id") or "<missing>")
            source_counts[source] += 1
            _append_reason(rows[idx], f"near_duplicate_drop:threshold_{threshold}")
        if len(examples) < 12:
            examples.append({
                "group_size": len(group),
                "kept_source": rows[keep_idx].get("source") or rows[keep_idx].get("source_id"),
                "kept_pair_id": rows[keep_idx].get("pair_id") or rows[keep_idx].get("source_pair_id"),
                "dropped": [
                    {
                        "source": rows[idx].get("source") or rows[idx].get("source_id"),
                        "pair_id": rows[idx].get("pair_id") or rows[idx].get("source_pair_id"),
                    }
                    for idx in ranked[1:4]
                ],
            })
    kept = [row for idx, row in enumerate(rows) if idx not in drop_ids]
    return kept, {
        "input_rows": len(rows),
        "output_rows": len(kept),
        "threshold": threshold,
        "near_duplicate_groups": len(groups),
        "dropped_rows": len(drop_ids),
        "drop_sources": dict(source_counts),
        "examples": examples,
    }


def annotate_paraphrase_groups(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Annotate remaining one-sided exact-text groups without dropping rows.

    Rows connected by a shared English-clean hash with multiple Hawaiian variants,
    or a shared Hawaiian-clean hash with multiple English variants, receive the
    same deterministic ``paraphrase_group_id``. The field lets SFT sampling see
    retained lexical diversity after hard dedup/cap passes have finished.
    """
    parent = list(range(len(rows)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    def mark_side(key_name: str, other_key_name: str) -> tuple[int, int]:
        groups: dict[str, list[int]] = defaultdict(list)
        for idx, row in enumerate(rows):
            key = row.get(key_name)
            if isinstance(key, str) and key:
                groups[key].append(idx)
        group_count = 0
        row_hits: set[int] = set()
        for idxs in groups.values():
            other_values = {rows[idx].get(other_key_name) for idx in idxs}
            if len(other_values) <= 1:
                continue
            group_count += 1
            first = idxs[0]
            for idx in idxs[1:]:
                union(first, idx)
            row_hits.update(idxs)
        return group_count, len(row_hits)

    exact_en_groups, exact_en_rows = mark_side("sha256_en_clean", "sha256_haw_clean")
    exact_haw_groups, exact_haw_rows = mark_side("sha256_haw_clean", "sha256_en_clean")

    components: dict[int, list[int]] = defaultdict(list)
    for idx in range(len(rows)):
        components[find(idx)].append(idx)

    annotated_rows = 0
    examples: list[dict[str, Any]] = []
    for idxs in components.values():
        if len(idxs) <= 1:
            rows[idxs[0]].pop("paraphrase_group_id", None)
            continue
        identity_parts = []
        for idx in sorted(idxs, key=lambda i: _stable_row_key(rows[i])):
            row = rows[idx]
            identity_parts.append("|".join(_stable_row_key(row)))
        digest = hashlib.sha256("\n".join(identity_parts).encode("utf-8")).hexdigest()[:16]
        group_id = f"stage2-paraphrase-{digest}"
        for idx in idxs:
            rows[idx]["paraphrase_group_id"] = group_id
        annotated_rows += len(idxs)
        if len(examples) < 12:
            examples.append({
                "paraphrase_group_id": group_id,
                "group_size": len(idxs),
                "sources": sorted({str(rows[idx].get("source") or "<missing>") for idx in idxs}),
                "pair_ids": [rows[idx].get("pair_id") for idx in sorted(idxs, key=lambda i: _stable_row_key(rows[i]))[:5]],
            })

    return {
        "policy_version": POLICY_VERSION,
        "input_rows": len(rows),
        "exact_en_groups": exact_en_groups,
        "exact_en_rows": exact_en_rows,
        "exact_haw_groups": exact_haw_groups,
        "exact_haw_rows": exact_haw_rows,
        "paraphrase_components": sum(1 for idxs in components.values() if len(idxs) > 1),
        "annotated_rows": annotated_rows,
        "examples": examples,
    }
