"""Stage212: synthetic tests for the corrected native TextureData field map."""
from __future__ import annotations

import struct
import unittest

from heman_tools.native_render_state_contract import (
    GL_LINEAR,
    GL_NEAREST,
    NativeRenderStateError,
    decode_texture_alpha_transform_flag,
    decode_texture_filter_mode,
    decode_texture_payload_selector,
    resolve_texture_sampling_state,
)


class NativeRenderStateContractTests(unittest.TestCase):
    def test_filter_mode_is_signed_int32_at_scalar_bytes_six_through_nine(self):
        scalar = bytearray(13)
        scalar[6:10] = struct.pack("<i", 1)
        scalar[12] = 0
        self.assertEqual(decode_texture_filter_mode(bytes(scalar)), 1)
        self.assertEqual(resolve_texture_sampling_state(1).min_filter, GL_LINEAR)

    def test_final_byte_is_not_the_filter_mode(self):
        scalar = bytearray(13)
        scalar[12] = 1
        self.assertEqual(decode_texture_filter_mode(bytes(scalar)), 0)
        self.assertEqual(decode_texture_payload_selector(bytes(scalar)), 1)

    def test_filter_mode_zero_means_nearest(self):
        scalar = bytearray(13)
        self.assertEqual(decode_texture_filter_mode(bytes(scalar)), 0)
        state = resolve_texture_sampling_state(0)
        self.assertEqual((state.min_filter, state.mag_filter), (GL_NEAREST, GL_NEAREST))
        self.assertFalse(state.generate_mipmaps)

    def test_filter_mode_two_is_recognized_as_mipmap_mode(self):
        scalar = bytearray(13)
        scalar[6:10] = struct.pack("<i", 2)
        self.assertEqual(decode_texture_filter_mode(bytes(scalar)), 2)
        self.assertTrue(resolve_texture_sampling_state(2).generate_mipmaps)

    def test_unsupported_filter_mode_fails_closed(self):
        scalar = bytearray(13)
        scalar[6:10] = struct.pack("<i", 3)
        with self.assertRaisesRegex(NativeRenderStateError, "0, 1, or 2"):
            decode_texture_filter_mode(bytes(scalar))

    def test_alpha_transform_flag_is_byte_five_not_filter_mode(self):
        scalar = bytearray(13)
        scalar[5] = 1
        scalar[6:10] = struct.pack("<i", 0)
        self.assertEqual(decode_texture_alpha_transform_flag(bytes(scalar)), 1)
        self.assertEqual(decode_texture_filter_mode(bytes(scalar)), 0)

    def test_zero_alpha_flag_is_independent_of_linear_filtering(self):
        scalar = bytearray(13)
        scalar[5] = 0
        scalar[6:10] = struct.pack("<i", 1)
        self.assertEqual(decode_texture_alpha_transform_flag(bytes(scalar)), 0)
        self.assertEqual(decode_texture_filter_mode(bytes(scalar)), 1)

    def test_alpha_transform_flag_must_be_boolean(self):
        scalar = bytearray(13)
        scalar[5] = 2
        with self.assertRaisesRegex(NativeRenderStateError, "alpha-transform flag"):
            decode_texture_alpha_transform_flag(bytes(scalar))

    def test_payload_selector_is_byte_twelve(self):
        scalar = bytearray(13)
        scalar[12] = 1
        self.assertEqual(decode_texture_payload_selector(bytes(scalar)), 1)

    def test_all_decoders_require_exact_scalar_length(self):
        for decoder in (decode_texture_filter_mode, decode_texture_alpha_transform_flag,
                        decode_texture_payload_selector):
            with self.subTest(decoder=decoder.__name__):
                with self.assertRaisesRegex(NativeRenderStateError, "exactly 13"):
                    decoder(bytes(12))

    def test_non_bytes_scalar_is_rejected(self):
        with self.assertRaisesRegex(NativeRenderStateError, "exactly 13"):
            decode_texture_filter_mode(bytearray(13))


if __name__ == "__main__":
    unittest.main()
