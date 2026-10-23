"""Stage222 synthetic tests: native allocation is not raw PNG-size sampling."""
from __future__ import annotations

import unittest

from heman_tools.native_texture_upload_gate import (
    NativeTextureUploadError, NativeUploadLayout,
    plan_native_texture_upload, prepare_native_cpu_texture,
)


class NativeTextureUploadTests(unittest.TestCase):
    def test_power_two_png_has_direct_usable_rgba(self):
        layout = plan_native_texture_upload((4, 4), (0, 0), 0)
        rgba = bytes(range(64))
        texture = prepare_native_cpu_texture(layout, rgba)
        self.assertEqual((texture.width, texture.height), (4, 4))
        self.assertIs(texture.rgba, rgba)
        self.assertFalse(layout.needs_native_padding)
        summary = layout.aggregate_only()
        self.assertTrue(summary["raw_png_buffer_directly_usable"])
        self.assertFalse(summary["original_ios_gpu_pixel_parity_verified"])
        self.assertFalse(summary["switch_hardware_gpu_parity_verified"])

    def test_nonpow2_png_fails_before_sampling_unknown_padding(self):
        layout = plan_native_texture_upload((3, 2), (0, 1), 1)
        self.assertEqual((layout.allocated_width, layout.allocated_height), (4, 4))
        self.assertEqual(layout.allocated_rgba_size, 64)
        self.assertTrue(layout.aggregate_only()["padding_texels_required"])
        with self.assertRaisesRegex(NativeTextureUploadError, "padding texels are unverified"):
            prepare_native_cpu_texture(layout, bytes(range(24)))

    def test_explicit_complete_allocated_buffer_preserves_source_rows(self):
        layout = plan_native_texture_upload((3, 2), (1, 0), 0)
        row0 = bytes(range(12))
        row1 = bytes(range(12, 24))
        padding = bytes((55, 66, 77, 88))
        entire = row0 + padding + row1 + padding + padding*8
        self.assertEqual(len(entire), 64)
        texture = prepare_native_cpu_texture(layout, row0+row1, complete_allocated_rgba=entire)
        self.assertEqual((texture.width, texture.height), (4, 4))
        self.assertEqual(texture.rgba, entire)
        self.assertEqual((texture.wrap_s_code, texture.wrap_t_code), (1, 0))
        self.assertEqual(texture.filter_mode_code, 0)

    def test_cannot_pretend_padded_bytes_match_source_png(self):
        layout = plan_native_texture_upload((3, 2), (0, 0), 0)
        rgba = bytes(range(24))
        complete = bytearray(64)
        complete[:12] = rgba[:12]
        complete[16:28] = rgba[12:]
        complete[18] ^= 1
        with self.assertRaisesRegex(NativeTextureUploadError, "visible PNG rows"):
            prepare_native_cpu_texture(layout, rgba, complete_allocated_rgba=bytes(complete))

    def test_complete_allocated_bytes_must_match_declared_size(self):
        layout = plan_native_texture_upload((3, 2), (0, 0), 0)
        with self.assertRaisesRegex(NativeTextureUploadError, "allocated RGBA byte length"):
            prepare_native_cpu_texture(layout, bytes(24), complete_allocated_rgba=bytes(24))

    def test_incomplete_source_bytes_fail_closed(self):
        layout = plan_native_texture_upload((4, 4), (0, 0), 0)
        with self.assertRaisesRegex(NativeTextureUploadError, "byte length"):
            prepare_native_cpu_texture(layout, bytes(63))

    def test_minimum_four_allocation_is_not_raw_png_footprint(self):
        layout = plan_native_texture_upload((1, 1), (0, 0), 0)
        self.assertEqual((layout.allocated_width, layout.allocated_height), (4, 4))
        with self.assertRaises(NativeTextureUploadError):
            prepare_native_cpu_texture(layout, bytes(4))

    def test_explicit_linear_clamp_repeat_codes_are_preserved(self):
        layout = plan_native_texture_upload((4, 8), (0, 1), 1)
        texture = prepare_native_cpu_texture(layout, bytes(4*8*4))
        self.assertEqual((texture.filter_mode_code, texture.wrap_t_code), (1, 1))
        self.assertTrue(layout.aggregate_only()["wrap_t_repeat"])

    def test_mipmaps_or_unknown_wrap_codes_are_rejected(self):
        for wrap, mode in (((0, 0), 2), ((2, 0), 0), ((True, 0), 0), ((0, 0), True)):
            with self.subTest(wrap=wrap, mode=mode):
                with self.assertRaises(NativeTextureUploadError):
                    plan_native_texture_upload((4, 4), wrap, mode)

    def test_bool_shape_and_oversize_allocation_rejected(self):
        for dimensions in ((True, 4), (0, 4), (32769, 1), [4, 4]):
            with self.subTest(dimensions=dimensions):
                with self.assertRaises(NativeTextureUploadError):
                    plan_native_texture_upload(dimensions, (0, 0), 0)
        with self.assertRaisesRegex(NativeTextureUploadError, "RGBA byte budget"):
            plan_native_texture_upload((8192, 8192), (0, 0), 0)

    def test_forged_layout_allocation_mismatch_rejected(self):
        forged = NativeUploadLayout(3, 2, 3, 2, 0, 0, 0)
        with self.assertRaisesRegex(NativeTextureUploadError, "disagree"):
            prepare_native_cpu_texture(forged, bytes(24))

    def test_does_not_export_source_pixels_in_aggregate(self):
        layout = plan_native_texture_upload((4, 4), (0, 0), 0)
        summary = layout.aggregate_only()
        self.assertNotIn("rgba", str(summary).lower())
        self.assertFalse(summary["source_texture_pixels_exported"])
        self.assertFalse(summary["original_native_padding_pixels_recovered"])


if __name__ == "__main__":
    unittest.main()
