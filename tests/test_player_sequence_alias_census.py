"""Synthetic-only tests for Stage187 alias-to-directional-sequence census."""
from __future__ import annotations

import json
import unittest

from heman_tools.player_sequence_alias_census import (
    SequenceAliasCensusError,
    summarize_directional_alias_regions,
)


def field(value: str) -> bytes:
    encoded = value.encode("utf-16le")
    return len(value).to_bytes(2, "little") + encoded


def pair(alias: str, east: str, west: str) -> bytes:
    return field(alias) + field(east) + field(west)


class PlayerSequenceAliasCensusTests(unittest.TestCase):
    def test_single_alias_pair_is_counted_without_exporting_labels(self):
        data = pair("syntheticIdle", "synthetic.idle.e", "synthetic.idle.w")
        report = summarize_directional_alias_regions(
            data, ("synthetic.idle.e", "synthetic.idle.w"), ((0, len(data)), (0, len(data)))
        )
        region = report["regions"][0]
        self.assertEqual(region["sequence_reference_occurrences"], 2)
        self.assertEqual(region["unique_sequence_keys"], 2)
        self.assertEqual(region["paired_alias_entry_occurrences"], 1)
        self.assertEqual(region["ambiguous_alias_groups"], 0)
        self.assertNotIn("syntheticIdle", json.dumps(report))
        self.assertNotIn("synthetic.idle.e", json.dumps(report))

    def test_shared_alias_with_different_resource_pairs_is_reported_aggregate_only(self):
        left = pair("syntheticIdle", "base.idle.e", "base.idle.w")
        right = pair("syntheticIdle", "armor.idle.e", "armor.idle.w")
        data = left + right
        split = len(left)
        report = summarize_directional_alias_regions(
            data,
            ("base.idle.e", "base.idle.w", "armor.idle.e", "armor.idle.w"),
            ((0, split), (split, len(data))),
        )
        self.assertEqual(report["cross_region"]["shared_paired_aliases"], 1)
        self.assertEqual(report["cross_region"]["comparable_unique_aliases"], 1)
        self.assertEqual(report["cross_region"]["same_resource_pair_count"], 0)
        self.assertEqual(report["cross_region"]["different_resource_pair_count"], 1)

    def test_identical_pair_across_regions_is_counted_as_same(self):
        left = pair("syntheticIdle", "base.idle.e", "base.idle.w")
        right = pair("syntheticIdle", "base.idle.e", "base.idle.w")
        data = left + right
        split = len(left)
        report = summarize_directional_alias_regions(
            data, ("base.idle.e", "base.idle.w"), ((0, split), (split, len(data)))
        )
        self.assertEqual(report["cross_region"]["same_resource_pair_count"], 1)
        self.assertEqual(report["cross_region"]["different_resource_pair_count"], 0)

    def test_four_references_under_one_alias_are_ambiguous_not_guessed(self):
        data = (field("syntheticWalk")
                + field("walk-a.e") + field("walk-a.w")
                + field("walk-b.e") + field("walk-b.w"))
        report = summarize_directional_alias_regions(
            data,
            ("walk-a.e", "walk-a.w", "walk-b.e", "walk-b.w"),
            ((0, len(data)), (0, len(data))),
        )
        self.assertEqual(report["regions"][0]["paired_alias_entry_occurrences"], 0)
        self.assertEqual(report["regions"][0]["ambiguous_alias_groups"], 1)
        self.assertEqual(report["regions"][0]["ambiguous_sequence_reference_occurrences"], 4)

    def test_unassigned_reference_is_reported(self):
        data = field("orphan.e") + pair("syntheticIdle", "idle.e", "idle.w")
        report = summarize_directional_alias_regions(
            data, ("orphan.e", "idle.e", "idle.w"), ((0, len(data)), (0, len(data)))
        )
        self.assertEqual(report["regions"][0]["unassigned_sequence_reference_occurrences"], 1)

    def test_resource_like_token_missing_from_index_is_reported(self):
        data = pair("syntheticIdle", "idle.e", "idle.w") + field("missing.e")
        report = summarize_directional_alias_regions(
            data, ("idle.e", "idle.w"), ((0, len(data)), (0, len(data)))
        )
        self.assertFalse(report["all_resource_like_tokens_match_sequence_index"])
        self.assertEqual(report["regions"][0]["unmatched_resource_like_token_count"], 1)

    def test_duplicate_alias_entries_are_not_silently_collapsed(self):
        data = pair("syntheticIdle", "idle.e", "idle.w") + pair(
            "syntheticIdle", "idle.e", "idle.w"
        )
        report = summarize_directional_alias_regions(
            data, ("idle.e", "idle.w"), ((0, len(data)), (0, len(data)))
        )
        self.assertEqual(report["regions"][0]["paired_alias_entry_occurrences"], 2)
        self.assertEqual(report["regions"][0]["unique_paired_aliases"], 1)
        self.assertEqual(report["cross_region"]["shared_aliases_with_duplicate_pair_entries"], 1)

    def test_invalid_regions_fail_closed(self):
        data = pair("syntheticIdle", "idle.e", "idle.w")
        with self.assertRaisesRegex(SequenceAliasCensusError, "overlap or are out of order"):
            summarize_directional_alias_regions(data, ("idle.e", "idle.w"), ((0, len(data)), (1, len(data))))

    def test_duplicate_sequence_keys_fail_closed(self):
        data = pair("syntheticIdle", "idle.e", "idle.w")
        with self.assertRaisesRegex(SequenceAliasCensusError, "duplicated"):
            summarize_directional_alias_regions(data, ("idle.e", "idle.e"), ((0, len(data)), (0, len(data))))

    def test_exactly_two_regions_are_required(self):
        data = pair("syntheticIdle", "idle.e", "idle.w")
        with self.assertRaisesRegex(SequenceAliasCensusError, "Exactly two"):
            summarize_directional_alias_regions(data, ("idle.e", "idle.w"), ((0, len(data)),))


if __name__ == "__main__":
    unittest.main()
