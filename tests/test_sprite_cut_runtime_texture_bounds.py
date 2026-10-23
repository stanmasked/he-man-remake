"""Synthetic-only regressions for the native padded-PNG SpriteCut contract."""
from __future__ import annotations

import json
import unittest

from heman_tools.sprite_cut_png_bounds_census import SpriteCutBoundsError
from heman_tools.sprite_cut_runtime_texture_bounds import (
    allocated_texture_dimensions, classify_allocated_cut,
    summarize_paired_allocated_bounds, verified_uv_coordinates,
)


class NativePaddedPngContractTests(unittest.TestCase):
    def test_minimum_allocation_is_four_by_four(self):
        self.assertEqual(allocated_texture_dimensions((1, 3)), (4, 4))

    def test_exact_powers_are_not_doubled(self):
        self.assertEqual(allocated_texture_dimensions((128, 256)), (128, 256))

    def test_independent_next_power_of_two_dimensions(self):
        self.assertEqual(allocated_texture_dimensions((250, 93)), (256, 128))

    def test_non_power_of_two_png_dimensions(self):
        self.assertEqual(allocated_texture_dimensions((5, 9)), (8, 16))

    def test_boolean_png_dimensions_are_rejected(self):
        with self.assertRaisesRegex(SpriteCutBoundsError, "bounded positive integers"):
            allocated_texture_dimensions((True, 8))

    def test_raw_png_cut_remains_inside_raw(self):
        self.assertEqual(
            classify_allocated_cut((3, 3, 7, 7), (10, 10)),
            ("inside_raw", 0, 0),
        )

    def test_cut_outside_raw_png_can_fit_padded_allocation(self):
        self.assertEqual(
            classify_allocated_cut((9, 9, 5, 5), (10, 10)),
            ("inside_allocated_only", 0, 0),
        )

    def test_cut_beyond_native_allocation_remains_unresolved(self):
        self.assertEqual(
            classify_allocated_cut((15, 15, 2, 3), (10, 10)),
            ("outside_allocated", 1, 2),
        )

    def test_negative_cut_y_remains_invalid_even_with_padding(self):
        self.assertEqual(
            classify_allocated_cut((0, -1, 2, 2), (10, 10)),
            ("invalid", 0, 0),
        )

    def test_uv_uses_padded_denominator_not_raw_png_size(self):
        self.assertEqual(
            verified_uv_coordinates((8, 8, 4, 4), (10, 10)),
            (0.5, 0.5, 0.75, 0.75),
        )

    def test_exact_png_cut_uv_still_uses_allocated_denominator(self):
        self.assertEqual(
            verified_uv_coordinates((2, 2, 3, 3), (10, 10)),
            (0.125, 0.125, 0.3125, 0.3125),
        )

    def test_uv_rejects_unresolved_cut_instead_of_clipping(self):
        with self.assertRaisesRegex(SpriteCutBoundsError, "Cannot normalize"):
            verified_uv_coordinates((15, 0, 2, 1), (10, 10))

    def test_uv_rejects_invalid_negative_cut(self):
        with self.assertRaisesRegex(SpriteCutBoundsError, "Cannot normalize"):
            verified_uv_coordinates((0, -1, 1, 2), (10, 10))

    def test_cross_pack_aggregate_only_and_unresolved_categories(self):
        medium = {
            ("synthetic-private-A", 0): ((0, 0, 2, 2), (10, 10)),
            ("synthetic-private-B", 0): ((9, 9, 5, 5), (10, 10)),
            ("synthetic-private-C", 0): ((15, 2, 3, 1), (10, 10)),
            ("synthetic-private-D", 0): ((0, -1, 2, 2), (10, 10)),
        }
        extra = dict(medium)
        extra[("synthetic-private-A", 0)] = ((10, 2, 4, 1), (10, 10))
        result = summarize_paired_allocated_bounds(medium, extra)
        med = result["per_pack"]["screen-med"]
        large = result["per_pack"]["screen-xlarge"]
        self.assertEqual(
            (med["inside_raw_png"], med["fits_allocated_only"],
             med["outside_even_allocated"], med["invalid_rectangle"]),
            (1, 1, 1, 1),
        )
        self.assertEqual(
            (large["inside_raw_png"], large["fits_allocated_only"],
             large["outside_even_allocated"], large["invalid_rectangle"]),
            (0, 2, 1, 1),
        )
        self.assertEqual(
            result["paired_category_counts"]["inside_raw_med__inside_allocated_only_xlarge"],
            1,
        )
        self.assertFalse(result["padding_pixel_content_verified"])
        self.assertFalse(result["unresolved_cuts_repaired_or_rendered"])
        self.assertNotIn("synthetic-private", json.dumps(result))

    def test_missing_cross_pack_cut_is_rejected(self):
        a = {("sample", 0): ((0, 0, 2, 2), (8, 8))}
        b = {("sample", 1): ((0, 0, 2, 2), (8, 8))}
        with self.assertRaisesRegex(SpriteCutBoundsError, "Paired source cut sets differ"):
            summarize_paired_allocated_bounds(a, b)


if __name__ == "__main__":
    unittest.main()
