"""Synthetic-only tests for the Stage197 Symbol frame render-plan model."""
from __future__ import annotations

import math
import unittest

from heman_tools.symbol_frame_render_plan import (
    PlayerTransform, SymbolFrameRenderPlan, SymbolLayerInput,
    SymbolRenderPlanError, build_symbol_frame_render_plan,
)
from heman_tools.symbol_render_contract import SymbolRenderContract


def _contract(*, mask=0, blend=(-1, -1), color=(1.0, 1.0, 1.0, 1.0),
              scale=(1.0, 1.0), rotation=0, offset=(0, 0), handle=0):
    alpha, red, green, blue = color
    scale_x, scale_y = scale
    src, dst = blend
    return SymbolRenderContract.from_serialized_fields(
        (handle, rotation, offset[0], offset[1]),
        (alpha, red, green, blue, scale_x, scale_y),
        (1, 2, 1, 5, src, dst, mask),
    )


def _layer(order, *, contract=None, rect=(0, 0, 8, 8), dimensions=(16, 16),
           wraps=(0, 0)):
    return SymbolLayerInput(
        source_order=order,
        contract=contract or _contract(handle=order),
        cut_rectangle=rect,
        png_dimensions=dimensions,
        wrap_codes=wraps,
    )


class SymbolRenderPlanTests(unittest.TestCase):
    def test_single_layer_produces_native_uv_and_color(self):
        layer = _layer(
            0, contract=_contract(color=(0.5, 0.5, 0.25, 1.0), handle=42),
            rect=(0, 0, 8, 8), dimensions=(16, 16),
        )
        plan = build_symbol_frame_render_plan(
            [layer], active_mask=0, user_rgba=(0.8, 0.6, 0.4, 0.9)
        )
        self.assertEqual(plan.command_count, 1)
        self.assertEqual(plan.draw_enabled_count, 1)
        self.assertEqual(plan.commands[0].cut_handle, 42)
        self.assertEqual(plan.commands[0].uv.u1, 0.5)
        self.assertAlmostEqual(plan.commands[0].vertex_rgba[0], 0.2, places=7)
        self.assertAlmostEqual(plan.commands[0].vertex_rgba[1], 0.075, places=7)
        self.assertAlmostEqual(plan.commands[0].vertex_rgba[2], 0.1, places=7)

    def test_source_draw_order_is_preserved_exactly(self):
        layers = [_layer(i) for i in range(4)]
        plan = build_symbol_frame_render_plan(layers, active_mask=0,
                                              user_rgba=(1, 1, 1, 1))
        self.assertEqual(plan.source_order, (0, 1, 2, 3))
        self.assertEqual(tuple(c.cut_handle for c in plan.commands), (0, 1, 2, 3))

    def test_masked_symbols_remain_in_plan_but_are_not_draw_enabled(self):
        layers = [
            _layer(0, contract=_contract(mask=0, handle=0)),
            _layer(1, contract=_contract(mask=4, handle=1)),
            _layer(2, contract=_contract(mask=8, handle=2)),
        ]
        plan = build_symbol_frame_render_plan(layers, active_mask=4,
                                              user_rgba=(1, 1, 1, 1))
        self.assertEqual(plan.command_count, 3)
        self.assertEqual(plan.draw_enabled_count, 2)
        self.assertEqual(plan.mask_suppressed_count, 1)
        self.assertEqual(tuple(c.draw_enabled for c in plan.commands),
                         (True, False, True))

    def test_active_blend_override_is_attached_to_its_layer(self):
        layer = _layer(0, contract=_contract(blend=(1, 1)))
        plan = build_symbol_frame_render_plan([layer], active_mask=0,
                                              user_rgba=(1, 1, 1, 1))
        self.assertEqual(plan.commands[0].blend_override, (1, 1))

    def test_partial_sentinel_blend_is_not_applied(self):
        layer = _layer(0, contract=_contract(blend=(-1, 1)))
        plan = build_symbol_frame_render_plan([layer], active_mask=0,
                                              user_rgba=(1, 1, 1, 1))
        self.assertIsNone(plan.commands[0].blend_override)

    def test_native_uv_outside_allocated_texture_is_not_clipped(self):
        layer = _layer(0, rect=(31, 0, 2, 1), dimensions=(32, 16), wraps=(0, 0))
        plan = build_symbol_frame_render_plan([layer], active_mask=0,
                                              user_rgba=(1, 1, 1, 1))
        self.assertGreater(plan.commands[0].uv.u1, 1.0)

    def test_zero_filled_padding_uvs_are_preserved(self):
        layer = _layer(0, rect=(31, 0, 2, 1), dimensions=(30, 16), wraps=(0, 0))
        plan = build_symbol_frame_render_plan([layer], active_mask=0,
                                              user_rgba=(1, 1, 1, 1))
        self.assertEqual(plan.commands[0].uv.wrap_s_mode, "clamp_to_edge")
        self.assertGreater(plan.commands[0].uv.u1, 1.0)

    def test_local_transform_fields_and_easing_groups_are_retained(self):
        layer = _layer(0, contract=_contract(rotation=-90, offset=(7, -3),
                                             scale=(2.0, -0.5)))
        command = build_symbol_frame_render_plan([layer], active_mask=0,
                                                 user_rgba=(1, 1, 1, 1)).commands[0]
        self.assertEqual((command.rotation_degrees, command.offset_x, command.offset_y),
                         (-90, 7, -3))
        self.assertEqual((command.scale_x, command.scale_y), (2.0, -0.5))
        self.assertEqual(command.tween_selectors.by_group["x_y_offset"], 1)
        self.assertEqual(command.tween_selectors.by_group["alpha_red_green_blue"], 5)

    def test_non_contiguous_source_order_fails_closed(self):
        with self.assertRaisesRegex(SymbolRenderPlanError, "contiguous"):
            build_symbol_frame_render_plan([_layer(1)], active_mask=0,
                                           user_rgba=(1, 1, 1, 1))

    def test_reordered_source_symbols_fail_closed(self):
        with self.assertRaisesRegex(SymbolRenderPlanError, "contiguous"):
            build_symbol_frame_render_plan([_layer(1), _layer(0)], active_mask=0,
                                           user_rgba=(1, 1, 1, 1))

    def test_invalid_active_mask_fails_closed(self):
        with self.assertRaisesRegex(SymbolRenderPlanError, "signed 32-bit"):
            build_symbol_frame_render_plan([], active_mask=True,
                                           user_rgba=(1, 1, 1, 1))

    def test_invalid_user_rgba_fails_even_for_empty_frame(self):
        with self.assertRaisesRegex(SymbolRenderPlanError, "user_rgba"):
            build_symbol_frame_render_plan([], active_mask=0,
                                           user_rgba=(1, 1, float("nan"), 1))

    def test_bad_layer_type_fails_closed(self):
        with self.assertRaisesRegex(SymbolRenderPlanError, "SymbolLayerInput"):
            build_symbol_frame_render_plan([object()], active_mask=0,
                                           user_rgba=(1, 1, 1, 1))

    def test_player_transform_identity(self):
        transform = PlayerTransform()
        self.assertEqual(transform.apply((12.0, -7.0)), (12.0, -7.0))

    def test_player_rotation_uses_degrees_about_its_pivot(self):
        transform = PlayerTransform(
            rotation_degrees=90.0, rotation_pivot_x=1.0, rotation_pivot_y=1.0
        )
        x, y = transform.apply((3.0, 2.0))
        self.assertAlmostEqual(x, 0.0, places=5)
        self.assertAlmostEqual(y, 3.0, places=5)

    def test_player_scale_uses_independent_axes_about_pivot(self):
        transform = PlayerTransform(
            scale_x=2.0, scale_y=0.5, scale_pivot_x=1.0, scale_pivot_y=1.0
        )
        self.assertEqual(transform.apply((3.0, 2.0)), (5.0, 1.5))

    def test_player_transform_order_is_rotate_then_scale_then_translate(self):
        transform = PlayerTransform(
            rotation_degrees=90.0, scale_x=2.0, scale_y=3.0,
            translation_x=5.0, translation_y=-1.0,
        )
        x, y = transform.apply((2.0, 1.0))
        self.assertAlmostEqual(x, 3.0, places=5)
        self.assertAlmostEqual(y, 5.0, places=5)

    def test_negative_player_scale_preserves_mirroring(self):
        transform = PlayerTransform(scale_x=-1.0, scale_y=1.0)
        self.assertEqual(transform.apply((3.0, 2.0)), (-3.0, 2.0))

    def test_non_finite_player_transform_is_rejected(self):
        with self.assertRaisesRegex(SymbolRenderPlanError, "finite number"):
            PlayerTransform(scale_x=math.inf)

    def test_invalid_point_is_rejected(self):
        with self.assertRaisesRegex(SymbolRenderPlanError, "two coordinates"):
            PlayerTransform().apply((1.0,))


if __name__ == "__main__":
    unittest.main()
