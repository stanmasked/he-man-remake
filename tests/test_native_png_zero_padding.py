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

