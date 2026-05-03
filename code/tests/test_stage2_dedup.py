from __future__ import annotations

import unittest

from llm_hawaii.stage2_dedup import (
    collapse_pair_hash_duplicates,
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


if __name__ == "__main__":
    unittest.main()
