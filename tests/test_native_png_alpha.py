"""Synthetic-only tests for the native PNGData alpha-transform contract."""
from __future__ import annotations
import unittest

from heman_tools.native_png_alpha import (
    NativePNGAlphaError, transform_native_png_alpha,
)


class NativePNGAlphaTests(unittest.TestCase):
    def test_flag_disabled_preserves_straight_rgba(self):
        rgba = bytes((240, 120, 60, 128, 255, 255, 255, 255))
        self.assertIs(transform_native_png_alpha(
            rgba, 2, 1, has_alpha=True, premultiply_alpha=False), rgba)

    def test_no_alpha_channel_skips_transform_even_if_flag_is_set(self):
        rgba = bytes((240, 120, 60, 255))
        self.assertIs(transform_native_png_alpha(
            rgba, 1, 1, has_alpha=False, premultiply_alpha=True), rgba)

    def test_native_transform_uses_rounding_then_shift_by_eight(self):
        rgba = bytes((255, 128, 64, 255, 200, 100, 50, 128))
        result = transform_native_png_alpha(
            rgba, 2, 1, has_alpha=True, premultiply_alpha=True)
        self.assertEqual(result, bytes((254, 127, 64, 255, 100, 50, 25, 128)))

    def test_zero_alpha_clears_rgb_and_preserves_alpha(self):
        rgba = bytes((255, 128, 64, 0))
        result = transform_native_png_alpha(
            rgba, 1, 1, has_alpha=True, premultiply_alpha=True)
        self.assertEqual(result, bytes((0, 0, 0, 0)))

    def test_each_pixel_is_transformed_independently(self):
        rgba = bytes((10, 20, 30, 64, 40, 50, 60, 192))
        result = transform_native_png_alpha(
            rgba, 2, 1, has_alpha=True, premultiply_alpha=True)
        self.assertEqual(result, bytes((2, 5, 7, 64, 30, 37, 45, 192)))

    def test_rejects_non_bytes(self):
        with self.assertRaisesRegex(NativePNGAlphaError, "immutable bytes"):
            transform_native_png_alpha(bytearray(4), 1, 1,
                                       has_alpha=True, premultiply_alpha=True)

    def test_rejects_invalid_dimensions_and_booleans(self):
        with self.assertRaisesRegex(NativePNGAlphaError, "positive integers"):
            transform_native_png_alpha(bytes(4), True, 1,
                                       has_alpha=True, premultiply_alpha=True)
        with self.assertRaisesRegex(NativePNGAlphaError, "booleans"):
            transform_native_png_alpha(bytes(4), 1, 1,
                                       has_alpha=1, premultiply_alpha=True)

    def test_rejects_mismatched_buffer_length(self):
        with self.assertRaisesRegex(NativePNGAlphaError, "byte length"):
            transform_native_png_alpha(bytes(3), 1, 1,
                                       has_alpha=True, premultiply_alpha=True)

    def test_rejects_oversized_texture_before_processing(self):
        with self.assertRaisesRegex(NativePNGAlphaError, "byte limit"):
            transform_native_png_alpha(b"", 4097, 4097,
                                       has_alpha=True, premultiply_alpha=True)


if __name__ == "__main__":
    unittest.main()
