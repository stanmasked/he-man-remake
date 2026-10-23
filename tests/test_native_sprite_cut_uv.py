"""Synthetic-only tests for native SpriteCut UV arithmetic and wrap semantics."""
from __future__ import annotations

import math
import unittest

from heman_tools.native_sprite_cut_uv import (
    NativeSpriteCutUVError, compute_native_sprite_cut_uv,
)


class NativeSpriteCutUvTests(unittest.TestCase):
    def test_non_power_of_two_png_uses_allocated_uv_denominator(self):
        uv = compute_native_sprite_cut_uv((0, 0, 250, 93), (250, 93), (0, 0))
        self.assertEqual((uv.allocated_width, uv.allocated_height), (256, 128))
        self.assertAlmostEqual(uv.u1, 250 / 256, places=7)
        self.assertAlmostEqual(uv.v1, 93 / 128, places=7)

    def test_uv_end_at_allocated_edge_is_exactly_one(self):
        uv = compute_native_sprite_cut_uv((250, 93, 6, 35), (250, 93), (0, 0))
        self.assertEqual((uv.u1, uv.v1), (1.0, 1.0))

    def test_uv_outside_allocation_is_preserved_without_clipping(self):
        uv = compute_native_sprite_cut_uv((257, 0, 4, 1), (250, 93), (0, 0))
        self.assertGreater(uv.u0, 1.0)
        self.assertGreater(uv.u1, 1.0)
        self.assertEqual(uv.u0, 257 / 256)
        self.assertEqual(uv.u1, 261 / 256)

    def test_negative_origin_preserves_negative_uv(self):
        uv = compute_native_sprite_cut_uv((0, -1, 8, 10), (17, 19), (0, 0))
        self.assertLess(uv.v0, 0.0)
        self.assertAlmostEqual(uv.v1, 9 / 32, places=7)

    def test_negative_width_preserves_reversed_u_endpoints(self):
        uv = compute_native_sprite_cut_uv((8, 0, -4, 4), (17, 19), (0, 0))
        self.assertGreater(uv.u0, uv.u1)
        self.assertEqual((uv.u0, uv.u1), (0.25, 0.125))

    def test_zero_width_preserves_equal_u_endpoints(self):
        uv = compute_native_sprite_cut_uv((4, 2, 0, 3), (17, 19), (0, 0))
        self.assertEqual(uv.u0, uv.u1)

    def test_signed_endpoint_addition_matches_32_bit_arm_wrap(self):
        uv = compute_native_sprite_cut_uv((0x7FFFFFFF, 0, 1, 1), (4, 4), (0, 0))
        self.assertGreater(uv.u0, 1.0e8)
        self.assertLess(uv.u1, -1.0e8)

    def test_wrap_codes_are_returned_with_native_mode_names(self):
        uv = compute_native_sprite_cut_uv((0, 0, 2, 2), (8, 8), (0, 1))
        self.assertEqual((uv.wrap_s_mode, uv.wrap_t_mode), ("clamp_to_edge", "repeat"))

    def test_unknown_wrap_code_is_not_guessed(self):
        uv = compute_native_sprite_cut_uv((0, 0, 2, 2), (8, 8), (9, 0))
        self.assertEqual((uv.wrap_s_mode, uv.wrap_t_mode), ("unrecognized", "clamp_to_edge"))

    def test_rectangle_requires_four_signed_integers(self):
        with self.assertRaisesRegex(NativeSpriteCutUVError, "four integers"):
            compute_native_sprite_cut_uv((0, 1, 2), (8, 8), (0, 0))
        with self.assertRaisesRegex(NativeSpriteCutUVError, "signed 32-bit"):
            compute_native_sprite_cut_uv((False, 0, 1, 1), (8, 8), (0, 0))

    def test_rectangle_integer_overflow_is_rejected_before_native_add(self):
        with self.assertRaisesRegex(NativeSpriteCutUVError, "signed 32-bit"):
            compute_native_sprite_cut_uv((1 << 31, 0, 1, 1), (8, 8), (0, 0))

    def test_wrap_codes_require_two_unsigned_bytes(self):
        with self.assertRaisesRegex(NativeSpriteCutUVError, "S and T"):
            compute_native_sprite_cut_uv((0, 0, 1, 1), (8, 8), (0,))
        with self.assertRaisesRegex(NativeSpriteCutUVError, "unsigned bytes"):
            compute_native_sprite_cut_uv((0, 0, 1, 1), (8, 8), (True, 0))

    def test_invalid_png_dimensions_are_rejected(self):
        with self.assertRaisesRegex(NativeSpriteCutUVError, "texture allocation"):
            compute_native_sprite_cut_uv((0, 0, 1, 1), (0, 8), (0, 0))

    def test_uv_results_are_native_single_precision_values(self):
        uv = compute_native_sprite_cut_uv((1, 3, 7, 9), (10, 10), (0, 0))
        self.assertEqual(uv.u0, 0.0625)
        self.assertEqual(uv.v0, 0.1875)
        self.assertTrue(math.isfinite(uv.u1) and math.isfinite(uv.v1))


if __name__ == "__main__":
    unittest.main()
