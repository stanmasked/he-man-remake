"""Synthetic-only tests for Stage193 native Symbol visual-field semantics."""
from __future__ import annotations

import math
import unittest

from heman_tools.symbol_render_contract import (
    SymbolBlendOverride, SymbolColorMultipliers, SymbolRenderContract,
    SymbolRenderContractError, SymbolTweenSelectors,
)


class SymbolRenderContractTests(unittest.TestCase):
    def test_serialized_field_order_is_decoded_explicitly(self):
        value = SymbolRenderContract.from_serialized_fields(
            (12, -90, 17, -21),
            (0.5, 0.8, 0.6, 0.4, 2.0, -0.5),
            (1, 2, 1, 5, -1, -1, 12),
        )
        self.assertEqual((value.cut_handle, value.rotation_degrees,
                          value.offset_x, value.offset_y), (12, -90, 17, -21))
        self.assertEqual(
            (value.color.alpha, value.color.red, value.color.green, value.color.blue),
            (0.5, 0.8, 0.6, 0.4),
        )
        self.assertEqual((value.scale_x, value.scale_y), (2.0, -0.5))
        self.assertEqual(value.tween.by_group, {
            "x_y_offset": 1, "rotation": 2, "scale_x_y": 1,
            "alpha_red_green_blue": 5,
        })
        self.assertEqual((value.blend.source_factor_raw,
                          value.blend.destination_factor_code), (-1, -1))
        self.assertEqual(value.symbol_mask, 12)

    def test_alpha_is_shared_multiplier_and_color_serialization_is_argb(self):
        color = SymbolColorMultipliers(alpha=0.5, red=0.5, green=0.2, blue=0.4)
        actual = color.apply_user_rgba((0.8, 0.7, 0.6, 0.9))
        expected = (0.2, 0.07, 0.12, 0.45)
        for actual_channel, expected_channel in zip(actual, expected):
            self.assertAlmostEqual(actual_channel, expected_channel, places=7)

    def test_zero_symbol_alpha_suppresses_all_rgba_channels(self):
        color = SymbolColorMultipliers(0.0, 1.0, 0.5, 0.25)
        self.assertEqual(color.apply_user_rgba((1.0, 0.5, 0.25, 0.75)),
                         (0.0, 0.0, 0.0, 0.0))

    def test_native_color_clamp_handles_above_one_and_negative_inputs(self):
        color = SymbolColorMultipliers(1.5, 1.1, -0.2, 0.8)
        actual = color.apply_user_rgba((1.0, 0.9, 0.5, 1.0))
        expected = (1.0, 0.0, 0.6, 1.0)
        for actual_channel, expected_channel in zip(actual, expected):
            self.assertAlmostEqual(actual_channel, expected_channel, places=7)

    def test_user_rgba_must_have_four_finite_numeric_channels(self):
        color = SymbolColorMultipliers(1, 1, 1, 1)
        for value in ((1, 1, 1), (1, 1, float("nan"), 1), (1, True, 1, 1)):
            with self.subTest(value=value):
                with self.assertRaises(SymbolRenderContractError):
                    color.apply_user_rgba(value)

    def test_non_finite_symbol_color_is_rejected(self):
        with self.assertRaisesRegex(SymbolRenderContractError, "finite number"):
            SymbolColorMultipliers(1.0, math.inf, 1.0, 1.0)

    def test_tween_groups_match_native_interpolation_calls(self):
        selectors = SymbolTweenSelectors(1, 2, 4, 5)
        self.assertEqual(selectors.by_group, {
            "x_y_offset": 1,
            "rotation": 2,
            "scale_x_y": 4,
            "alpha_red_green_blue": 5,
        })

    def test_tween_selector_outside_native_enum_range_fails_closed(self):
        with self.assertRaisesRegex(SymbolRenderContractError, "0..17"):
            SymbolTweenSelectors(1, 2, 18, 5)
        with self.assertRaises(SymbolRenderContractError):
            SymbolTweenSelectors(True, 1, 1, 1)

    def test_scale_fields_are_independent_and_may_preserve_mirroring(self):
        value = SymbolRenderContract.from_serialized_fields(
            (0, 0, 0, 0), (1, 1, 1, 1, 2.5, -1.25), (1, 1, 1, 1, -1, -1, 0)
        )
        self.assertEqual((value.scale_x, value.scale_y), (2.5, -1.25))

    def test_blend_destination_ids_map_to_native_gl_constants(self):
        expected = {
            0: 0, 1: 1, 2: 0x0300, 3: 0x0301,
            4: 0x0302, 5: 0x0303, 6: 0x0304, 7: 0x0305,
        }
        for code, gl_constant in expected.items():
            with self.subTest(code=code):
                self.assertEqual(SymbolBlendOverride(1, code).resolve(), (1, gl_constant))

    def test_blend_source_is_preserved_as_raw_gl_value(self):
        self.assertEqual(SymbolBlendOverride(0x0302, 1).resolve(), (0x0302, 1))

    def test_blend_override_is_disabled_when_either_field_is_sentinel(self):
        self.assertIsNone(SymbolBlendOverride(-1, 1).resolve())
        self.assertIsNone(SymbolBlendOverride(1, -1).resolve())
        self.assertIsNone(SymbolBlendOverride(-1, -1).resolve())

    def test_unknown_blend_destination_fails_closed(self):
        self.assertIsNone(SymbolBlendOverride(1, 8).resolve())
        self.assertIsNone(SymbolBlendOverride(1, -2).resolve())

    def test_mask_overlap_suppresses_symbol(self):
        value = SymbolRenderContract.from_serialized_fields(
            (0, 0, 0, 0), (1, 1, 1, 1, 1, 1), (1, 1, 1, 1, -1, -1, 12)
        )
        self.assertTrue(value.is_suppressed_by_mask(4))
        self.assertTrue(value.is_suppressed_by_mask(8))
        self.assertFalse(value.is_suppressed_by_mask(3))

    def test_zero_mask_never_suppresses_symbol(self):
        value = SymbolRenderContract.from_serialized_fields(
            (0, 0, 0, 0), (1, 1, 1, 1, 1, 1), (1, 1, 1, 1, -1, -1, 0)
        )
        for active in (0, 1, 12, 0x7FFFFFFF):
            self.assertFalse(value.is_suppressed_by_mask(active))

    def test_mask_uses_signed_integer_validation(self):
        value = SymbolRenderContract.from_serialized_fields(
            (0, 0, 0, 0), (1, 1, 1, 1, 1, 1), (1, 1, 1, 1, -1, -1, 1)
        )
        with self.assertRaisesRegex(SymbolRenderContractError, "signed 32-bit"):
            value.is_suppressed_by_mask(True)

    def test_symbol_integer_prefix_rejects_boolean(self):
        with self.assertRaisesRegex(SymbolRenderContractError, "signed 32-bit"):
            SymbolRenderContract.from_serialized_fields(
                (False, 0, 0, 0), (1, 1, 1, 1, 1, 1), (1, 1, 1, 1, -1, -1, 0)
            )

    def test_symbol_float_block_requires_exact_length(self):
        with self.assertRaisesRegex(SymbolRenderContractError, "exactly six"):
            SymbolRenderContract.from_serialized_fields(
                (0, 0, 0, 0), (1, 1, 1, 1, 1), (1, 1, 1, 1, -1, -1, 0)
            )

    def test_symbol_scalar_tail_requires_exact_length(self):
        with self.assertRaisesRegex(SymbolRenderContractError, "exactly seven"):
            SymbolRenderContract.from_serialized_fields(
                (0, 0, 0, 0), (1, 1, 1, 1, 1, 1), (1, 1, 1, 1, -1, -1)
            )

    def test_non_finite_scale_is_rejected(self):
        with self.assertRaisesRegex(SymbolRenderContractError, "finite number"):
            SymbolRenderContract.from_serialized_fields(
                (0, 0, 0, 0), (1, 1, 1, 1, float("nan"), 1),
                (1, 1, 1, 1, -1, -1, 0),
            )


if __name__ == "__main__":
    unittest.main()
