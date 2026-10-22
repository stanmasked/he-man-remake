"""Synthetic-only regression tests for Stage188 alias resolution."""
from __future__ import annotations

import unittest

from heman_tools.directional_sequence_resolver import (
    DirectionalSequenceEntry,
    resolve_directional_sequence,
)


BASE = DirectionalSequenceEntry(
    alias="syntheticIdle", variant=0,
    east_key="synthetic.base.idle.e", west_key="synthetic.base.idle.w",
)
ARMOR = DirectionalSequenceEntry(
    alias="syntheticIdle", variant=1,
    east_key="synthetic.armor.idle.e", west_key="synthetic.armor.idle.w",
)


class DirectionalSequenceResolverTests(unittest.TestCase):
    def test_east_selects_east_key(self):
        result = resolve_directional_sequence((BASE,), "syntheticIdle", 0, "east")
        self.assertEqual(result.status, "resolved")
        self.assertEqual(result.resource_key, BASE.east_key)

    def test_west_selects_west_key(self):
        result = resolve_directional_sequence((BASE,), "syntheticIdle", 0, "west")
        self.assertEqual(result.status, "resolved")
        self.assertEqual(result.resource_key, BASE.west_key)

    def test_variant_selects_its_own_pair(self):
        result = resolve_directional_sequence((BASE, ARMOR), "syntheticIdle", 1, "east")
        self.assertEqual(result.resource_key, ARMOR.east_key)

    def test_missing_alias_returns_missing(self):
        result = resolve_directional_sequence((BASE,), "syntheticJump", 0, "east")
        self.assertEqual((result.status, result.resource_key), ("missing", None))

    def test_missing_variant_does_not_fall_back(self):
        result = resolve_directional_sequence((BASE,), "syntheticIdle", 1, "west")
        self.assertEqual((result.status, result.resource_key), ("missing", None))

    def test_explicitly_ambiguous_alias_fails_closed(self):
        result = resolve_directional_sequence(
            (BASE,), "syntheticIdle", 0, "east",
            ambiguous_aliases={(0, "syntheticIdle")},
        )
        self.assertEqual((result.status, result.resource_key), ("ambiguous", None))

    def test_ambiguous_alias_can_be_rejected_even_without_a_candidate_entry(self):
        result = resolve_directional_sequence(
            (), "syntheticWalk", 0, "west",
            ambiguous_aliases={(0, "syntheticWalk")},
        )
        self.assertEqual((result.status, result.resource_key), ("ambiguous", None))

    def test_duplicate_alias_variant_entries_are_not_silently_collapsed(self):
        duplicate = DirectionalSequenceEntry(
            alias=BASE.alias, variant=BASE.variant,
            east_key=BASE.east_key, west_key=BASE.west_key,
        )
        result = resolve_directional_sequence((BASE, duplicate), BASE.alias, 0, "east")
        self.assertEqual((result.status, result.resource_key), ("ambiguous", None))

    def test_invalid_direction_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Direction must"):
            resolve_directional_sequence((BASE,), BASE.alias, 0, "north")

    def test_boolean_variant_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Variant must"):
            resolve_directional_sequence((BASE,), BASE.alias, True, "east")

    def test_empty_alias_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Alias must"):
            resolve_directional_sequence((BASE,), "", 0, "east")

    def test_empty_resource_key_is_rejected(self):
        malformed = DirectionalSequenceEntry("syntheticIdle", 0, "", "synthetic.w")
        with self.assertRaisesRegex(ValueError, "East resource keys"):
            resolve_directional_sequence((malformed,), "syntheticIdle", 0, "east")

    def test_malformed_ambiguous_alias_tuple_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Ambiguous alias entries"):
            resolve_directional_sequence((BASE,), BASE.alias, 0, "east",
                                         ambiguous_aliases=((True, BASE.alias),))


if __name__ == "__main__":
    unittest.main()
