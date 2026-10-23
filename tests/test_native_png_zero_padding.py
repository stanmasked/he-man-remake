"""Stage223 synthetic-only PNG padding and upload-byte regressions."""
from __future__ import annotations
import unittest
from heman_tools.native_png_zero_padding import reconstruct_native_zero_padded_texture
from heman_tools.native_texture_upload_gate import (
    NativeTextureUploadError, plan_native_texture_upload,
)


class NativePNGZeroPaddingTests(unittest.TestCase):
    def test_rgba_padding_is_transparent_black(self):
        layout = plan_native_texture_upload((3, 2), (0, 0), 0)
        rgba = bytes((3, 7, 11, 128)) * 6
        result = reconstruct_native_zero_padded_texture(
            layout, rgba, native_png_has_alpha=True)
        self.assertEqual((result.width, result.height), (4, 4))
        self.assertEqual(result.rgba[:12], rgba[:12])
        self.assertEqual(result.rgba[12:16], bytes((0, 0, 0, 0)))
        self.assertEqual(result.rgba[16:28], rgba[12:])
        self.assertEqual(result.rgba[32:], bytes(32))

    def test_rgb_padding_is_opaque_black_for_gles_sampling(self):
        layout = plan_native_texture_upload((3, 2), (1, 0), 1)
        rgba = bytes((21, 31, 41, 255)) * 6
        result = reconstruct_native_zero_padded_texture(
            layout, rgba, native_png_has_alpha=False)
        self.assertEqual(result.rgba[12:16], bytes((0, 0, 0, 255)))
        self.assertEqual(result.rgba[32:], bytes((0, 0, 0, 255)) * 8)
        self.assertEqual((result.wrap_s_code, result.filter_mode_code), (1, 1))

    def test_minimum_four_by_four_allocation_from_one_pixel(self):
        layout = plan_native_texture_upload((1, 1), (0, 0), 0)
        result = reconstruct_native_zero_padded_texture(
            layout, bytes((20, 40, 60, 255)), native_png_has_alpha=False)
        self.assertEqual(result.rgba[:4], bytes((20, 40, 60, 255)))
        self.assertEqual(result.rgba[4:], bytes((0, 0, 0, 255)) * 15)

    def test_power_of_two_input_keeps_exact_source(self):
        layout = plan_native_texture_upload((4, 4), (0, 1), 0)
        rgba = bytes(range(64))
        result = reconstruct_native_zero_padded_texture(
            layout, rgba, native_png_has_alpha=True)
        self.assertIs(result.rgba, rgba)

    def test_native_rgb_alpha_cannot_be_fabricated(self):
        layout = plan_native_texture_upload((3, 2), (0, 0), 0)
        with self.assertRaisesRegex(NativeTextureUploadError, "opaque RGBA"):
            reconstruct_native_zero_padded_texture(
                layout, bytes((1, 2, 3, 128)) * 6, native_png_has_alpha=False)

    def test_invalid_alpha_mode_and_source_byte_count_rejected(self):
        layout = plan_native_texture_upload((3, 2), (0, 0), 0)
        with self.assertRaisesRegex(NativeTextureUploadError, "boolean"):
            reconstruct_native_zero_padded_texture(
                layout, bytes(24), native_png_has_alpha=1)
        with self.assertRaisesRegex(NativeTextureUploadError, "byte count"):
            reconstruct_native_zero_padded_texture(
                layout, bytes(23), native_png_has_alpha=True)


if __name__ == "__main__":
    unittest.main()
