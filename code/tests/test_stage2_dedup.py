from __future__ import annotations

import sys
import unittest
from pathlib import Path

_CODE_DIR = Path(__file__).resolve().parents[1]
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

from llm_hawaii.stage2_dedup import (
    annotate_paraphrase_groups,
    cap_exact_en,
    cap_exact_haw,
    collapse_near_dupes,
    collapse_pair_hash_duplicates,
    near_duplicate_groups,
    select_preferred,
    source_family,
)


def row(source: str, pair_id: str, pair_hash: str = "same") -> dict:
    return {
        "source": source,
        "pair_id": pair_id,
        "sha256_pair": pair_hash,
        "manual_review_reasons": [],
    }


class TestStage2CrossSourceDedupPolicy(unittest.TestCase):
    def test_canonical_tatoeba_preferred_over_opus_tatoeba(self):
        kept, dropped, reason = select_preferred([
            row("opus-haw-subsets", "opus-tatoeba-v2023-04-12-000001-abc"),
            row("tatoeba", "tatoeba-haw1-en1"),
        ])
        self.assertEqual(kept["source"], "tatoeba")
        self.assertEqual(dropped[0]["source"], "opus-haw-subsets")
        self.assertEqual(reason, "tatoeba-over-opus-tatoeba")

    def test_wikimedia_cx_preferred_over_opus_wikimedia(self):
        kept, dropped, reason = select_preferred([
            row("opus-haw-subsets", "opus-wikimedia-v20230407-000001-abc"),
            row("wikimedia-cx-en-haw", "wikimedia-cx-en-haw-1-p0"),
        ])
        self.assertEqual(kept["source"], "wikimedia-cx-en-haw")
        self.assertEqual(reason, "wikimedia-cx-over-opus-wikimedia")

    def test_bible_exact_overlap_prefers_1868(self):
        kept, dropped, reason = select_preferred([
            row("gospel_john_1854", "gospel_john_1854-JHN.1.16"),
            row("baibala-hemolele-1868", "bible:JHN:1:16"),
        ])
        self.assertEqual(kept["source"], "baibala-hemolele-1868")
        self.assertEqual(reason, "bible-1868-over-other-bible-editions")

    def test_hooilina_preferred_over_bible(self):
        kept, dropped, reason = select_preferred([
            row("baibala-hemolele-1868", "bible:GEN:1:1"),
            row("hooilina", "hooilina-section-1"),
        ])
        self.assertEqual(kept["source"], "hooilina")
        self.assertEqual(reason, "hooilina-over-bible")

    def test_collapse_drops_one_per_exact_pair_group(self):
        rows = [
            row("opus-haw-subsets", "opus-tatoeba-v2023-04-12-000001-abc", "h1"),
            row("tatoeba", "tatoeba-haw1-en1", "h1"),
            row("wikimedia-cx-en-haw", "wikimedia-cx-1", "h2"),
        ]
        kept, stats = collapse_pair_hash_duplicates(rows)
        self.assertEqual(len(kept), 2)
        self.assertEqual(stats["duplicate_groups"], 1)
        self.assertEqual(stats["dropped_rows"], 1)
        self.assertEqual(stats["drop_reasons"], {"tatoeba-over-opus-tatoeba": 1})
        self.assertEqual(source_family(kept[0]), "tatoeba")

    def test_cap_exact_en_keeps_three_best_variants(self):
        rows = [
            {**row("opus-haw-subsets", "opus", "p1"), "sha256_en_clean": "same-en", "sha256_haw_clean": "h1", "text_en": "This English phrase is longer", "text_haw": "A"},
            {**row("ia-hawaiian-phrase-book-1881", "phrase", "p2"), "sha256_en_clean": "same-en", "sha256_haw_clean": "h2", "text_en": "This English phrase is longer", "text_haw": "Aloha kakahiaka"},
            {**row("hooilina", "hoo", "p3"), "sha256_en_clean": "same-en", "sha256_haw_clean": "h3", "text_en": "This English phrase is longer", "text_haw": "Aloha nui loa"},
            {**row("tatoeba", "tat", "p4"), "sha256_en_clean": "same-en", "sha256_haw_clean": "h4", "text_en": "This English phrase is longer", "text_haw": "Aloha"},
        ]
        kept, stats = cap_exact_en(rows, max_per_key=3)
        kept_sources = {r["source"] for r in kept}
        self.assertEqual(len(kept), 3)
        self.assertEqual(stats["capped_groups"], 1)
        self.assertEqual(stats["dropped_rows"], 1)
        self.assertIn("hooilina", kept_sources)
        self.assertNotIn("opus-haw-subsets", kept_sources)

    def test_cap_exact_haw_keeps_three_best_variants(self):
        rows = [
            {**row("opus-haw-subsets", "opus", "p1"), "sha256_en_clean": "e1", "sha256_haw_clean": "same-haw", "text_en": "Hi", "text_haw": "Aloha nui i kēia kakahiaka"},
            {**row("ia-hawaiian-phrase-book-1881", "phrase", "p2"), "sha256_en_clean": "e2", "sha256_haw_clean": "same-haw", "text_en": "Greetings", "text_haw": "Aloha nui i kēia kakahiaka"},
            {**row("hooilina", "hoo", "p3"), "sha256_en_clean": "e3", "sha256_haw_clean": "same-haw", "text_en": "A warm greeting", "text_haw": "Aloha nui i kēia kakahiaka"},
            {**row("tatoeba", "tat", "p4"), "sha256_en_clean": "e4", "sha256_haw_clean": "same-haw", "text_en": "Hello", "text_haw": "Aloha nui i kēia kakahiaka"},
        ]
        kept, stats = cap_exact_haw(rows, max_per_key=3)
        self.assertEqual(len(kept), 3)
        self.assertEqual(stats["capped_groups"], 1)
        self.assertEqual(stats["dropped_rows"], 1)
        self.assertNotIn("opus-haw-subsets", {r["source"] for r in kept})

    def test_short_exact_en_requires_long_other_side_and_caps_at_two(self):
        rows = [
            {**row("ia-hawaiian-phrase-book-1881", "short", "p1"), "sha256_en_clean": "same-en", "sha256_haw_clean": "h1", "text_en": "good house", "text_haw": "Hale"},
            {**row("andrews-1865-en-haw-vocab-appendix", "edge", "p2"), "sha256_en_clean": "same-en", "sha256_haw_clean": "h2", "text_en": "good house", "text_haw": "He hale maikaʻi kēia"},
            {**row("tatoeba", "long", "p3"), "sha256_en_clean": "same-en", "sha256_haw_clean": "h3", "text_en": "good house", "text_haw": "He hale nui maikaʻi loa"},
        ]
        kept, stats = cap_exact_en(rows)
        self.assertEqual([r["pair_id"] for r in kept], ["edge", "long"])
        self.assertEqual(stats["short_policy_groups"], 1)
        self.assertEqual(stats["short_other_too_short_dropped_rows"], 1)
        self.assertEqual(stats["dropped_rows"], 1)

    def test_short_exact_haw_drops_empty_other_side(self):
        rows = [
            {**row("ia-hawaiian-phrase-book-1881", "empty", "p1"), "sha256_en_clean": "e1", "sha256_haw_clean": "same-haw", "text_en": "", "text_haw": "ʻAe"},
            {**row("andrews-1865-en-haw-vocab-appendix", "threshold", "p2"), "sha256_en_clean": "e2", "sha256_haw_clean": "same-haw", "text_en": "This has four tokens", "text_haw": "ʻAe"},
            {**row("tatoeba", "also-threshold", "p3"), "sha256_en_clean": "e3", "sha256_haw_clean": "same-haw", "text_en": "That also has four", "text_haw": "ʻAe"},
            {**row("kaikki", "over-cap", "p4"), "sha256_en_clean": "e4", "sha256_haw_clean": "same-haw", "text_en": "Another valid long gloss", "text_haw": "ʻAe"},
        ]
        kept, stats = cap_exact_haw(rows)
        self.assertEqual(len(kept), 2)
        self.assertNotIn("empty", {r["pair_id"] for r in kept})
        self.assertEqual(stats["drop_reasons"], {"short_other_min_4": 1, "max_2": 1})

    def test_empty_duplicate_side_uses_generic_cap(self):
        rows = [
            {**row("hooilina", "a", "p1"), "sha256_en_clean": "same-en", "sha256_haw_clean": "h1", "text_en": "", "text_haw": "Ekahi"},
            {**row("tatoeba", "b", "p2"), "sha256_en_clean": "same-en", "sha256_haw_clean": "h2", "text_en": "", "text_haw": "Elua"},
            {**row("ia-hawaiian-phrase-book-1881", "c", "p3"), "sha256_en_clean": "same-en", "sha256_haw_clean": "h3", "text_en": "", "text_haw": "Ekolu"},
            {**row("opus-haw-subsets", "d", "p4"), "sha256_en_clean": "same-en", "sha256_haw_clean": "h4", "text_en": "", "text_haw": "Eha"},
        ]
        kept, stats = cap_exact_en(rows)
        self.assertEqual(len(kept), 3)
        self.assertEqual(stats["short_policy_groups"], 0)
        self.assertEqual(stats["drop_reasons"], {"max_3": 1})

    def test_collapse_near_dupes_prefers_richer_source(self):
        rows = [
            {**row("ia-hawaiian-phrase-book-1881", "phrase", "p1"), "text_en": "In the beginning God made the heaven", "text_haw": "I kinohi hana ke Akua i ka lani"},
            {**row("hooilina", "hoo", "p2"), "text_en": "In the beginning God made the heavens", "text_haw": "I kinohi hana ke Akua i ka lani"},
            {**row("tatoeba", "tat", "p3"), "text_en": "This is different", "text_haw": "He ʻokoʻa kēia"},
        ]
        kept, stats = collapse_near_dupes(rows, threshold=0.92)
        self.assertEqual(len(kept), 2)
        self.assertEqual(stats["near_duplicate_groups"], 1)
        self.assertEqual(stats["dropped_rows"], 1)
        self.assertIn("hooilina", {r["source"] for r in kept})
        self.assertNotIn("ia-hawaiian-phrase-book-1881", {r["source"] for r in kept})

    def test_weblate_orders_below_tatoeba_and_uses_short_variant_cap(self):
        kept, dropped, reason = select_preferred([
            row("weblate", "weblate:hosted:demo:app:menu.open"),
            row("tatoeba", "tatoeba-haw1-en1"),
        ])
        self.assertEqual(kept["source"], "tatoeba")
        self.assertEqual(dropped[0]["source"], "weblate")
        self.assertEqual(reason, "tatoeba-over-weblate")

        rows = [
            {**row("weblate", "w", "p1"), "sha256_en_clean": "same-en", "sha256_haw_clean": "h1", "text_en": "Open settings now", "text_haw": "E wehe"},
            {**row("tatoeba", "t", "p2"), "sha256_en_clean": "same-en", "sha256_haw_clean": "h2", "text_en": "Open settings now", "text_haw": "E wehe i nā hoʻonohonoho"},
            {**row("kaikki", "k", "p3"), "sha256_en_clean": "same-en", "sha256_haw_clean": "h3", "text_en": "Open settings now", "text_haw": "E wehe i kēia papa hoʻonohonoho"},
        ]
        capped, stats = cap_exact_en(rows)
        self.assertEqual(len(capped), 2)
        self.assertEqual(stats["short_policy_groups"], 1)
        self.assertNotIn("weblate", {r["source"] for r in capped})

    def test_unruled_exact_pair_fallback_uses_source_priority_not_source_id(self):
        kept, dropped, reason = select_preferred([
            {**row("andrews-1865-en-haw-vocab-appendix", "andrews", "same"), "text_en": "Short", "text_haw": "Pōkole"},
            {**row("hooilina", "hooilina", "same"), "text_en": "Short", "text_haw": "Pōkole"},
        ])
        self.assertEqual(kept["source"], "hooilina")
        self.assertEqual(dropped[0]["source"], "andrews-1865-en-haw-vocab-appendix")
        self.assertEqual(reason, "deterministic_fallback_no_policy_rule")

    def test_near_duplicate_matching_ignores_invisible_format_controls(self):
        rows = [
            {**row("hooilina", "plain", "p1"), "text_en": "abcdef", "text_haw": "hooponopono"},
            {**row("andrews-1865-en-haw-vocab-appendix", "hidden", "p2"), "text_en": "abc\u200bdef", "text_haw": "hoo\u00adponopono"},
        ]
        self.assertEqual(near_duplicate_groups(rows, threshold=1.0), [[0, 1]])
        kept, stats = collapse_near_dupes(rows, threshold=1.0)
        self.assertEqual([r["pair_id"] for r in kept], ["plain"])
        self.assertEqual(stats["dropped_rows"], 1)

    def test_english_okina_and_apostrophe_are_not_folded_for_dedup(self):
        rows = [
            {**row("hooilina", "apostrophe", "p1"), "text_en": "Hawai'i", "text_haw": "hawaiʻi"},
            {**row("tatoeba", "okina", "p2"), "text_en": "Hawaiʻi", "text_haw": "hawaiʻi"},
        ]
        self.assertEqual(near_duplicate_groups(rows, threshold=1.0), [])

    def test_trailing_punctuation_only_variants_are_near_duplicates(self):
        rows = [
            {**row("andrews-1865-en-haw-vocab-appendix", "bare", "p1"), "text_en": "Blue", "text_haw": "uliuli"},
            {**row("ia-hawaiian-phrase-book-1881", "punct", "p2"), "text_en": "Blue.", "text_haw": "Uliuli."},
        ]
        self.assertEqual(near_duplicate_groups(rows, threshold=1.0), [[0, 1]])

    def test_annotate_paraphrase_groups_marks_remaining_one_sided_groups(self):
        rows = [
            {**row("baibala-hemolele-1868", "a", "p1"), "sha256_en_clean": "same-en", "sha256_haw_clean": "h1"},
            {**row("baibala-hemolele-1868", "b", "p2"), "sha256_en_clean": "same-en", "sha256_haw_clean": "h2"},
            {**row("tatoeba", "c", "p3"), "sha256_en_clean": "e3", "sha256_haw_clean": "same-haw"},
            {**row("tatoeba", "d", "p4"), "sha256_en_clean": "e4", "sha256_haw_clean": "same-haw"},
            {**row("kaikki", "unique", "p5"), "sha256_en_clean": "e5", "sha256_haw_clean": "h5", "paraphrase_group_id": "stale"},
        ]
        stats = annotate_paraphrase_groups(rows)
        self.assertEqual(stats["exact_en_groups"], 1)
        self.assertEqual(stats["exact_haw_groups"], 1)
        self.assertEqual(stats["paraphrase_components"], 2)
        self.assertEqual(stats["annotated_rows"], 4)
        self.assertEqual(rows[0]["paraphrase_group_id"], rows[1]["paraphrase_group_id"])
        self.assertEqual(rows[2]["paraphrase_group_id"], rows[3]["paraphrase_group_id"])
        self.assertNotEqual(rows[0]["paraphrase_group_id"], rows[2]["paraphrase_group_id"])
        self.assertNotIn("paraphrase_group_id", rows[4])


if __name__ == "__main__":
    unittest.main()
