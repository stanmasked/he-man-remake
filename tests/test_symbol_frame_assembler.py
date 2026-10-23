"""Synthetic regressions for Stage201 bounded frame packet assembly."""
from dataclasses import replace
import unittest

from heman_tools.symbol_frame_render_plan import (
    PlayerTransform, SymbolFrameRenderPlan, SymbolLayerInput,
    build_symbol_frame_render_plan,
)
from heman_tools.symbol_render_contract import SymbolRenderContract
from heman_tools.symbol_frame_assembler import (
    MAX_SYMBOL_FRAME_COMMANDS, SymbolFrameAssemblyError,
    assemble_symbol_frame,
)


def _contract(*, mask=0, blend=(-1, -1), color=(1.0, 1.0, 1.0, 1.0),
              scale=(1.0, 1.0), rotation=0, offset=(10, 20), handle=0):
    alpha, red, green, blue = color
    scale_x, scale_y = scale
    src, dst = blend
    return SymbolRenderContract.from_serialized_fields(
        (handle, rotation, offset[0], offset[1]),
        (alpha, red, green, blue, scale_x, scale_y),
        (1, 2, 1, 5, src, dst, mask),
    )


def _plan(*, active_mask=0, count=3, masked_index=None):
    layers = []
    for index in range(count):
        layers.append(SymbolLayerInput(
            source_order=index,
            contract=_contract(mask=4 if index == masked_index else 0,
                               handle=17 + index),
            cut_rectangle=(0, 0, 8, 4),
            png_dimensions=(16, 16),
            wrap_codes=(0, 0),
        ))
    return build_symbol_frame_render_plan(
        layers, active_mask=active_mask, user_rgba=(1, 1, 1, 1)
    )


class SymbolFrameAssemblerTests(unittest.TestCase):
    def test_assembles_ordered_geometry_uv_color_and_blend_packets(self):
        plan = _plan(active_mask=4, masked_index=1)
        result = assemble_symbol_frame(
            plan, [(8, 4), (4, 2), (3, 5)], active_mask=4
        )
        self.assertEqual(result.packet_count, 2)
        self.assertEqual(result.source_order, (0, 2))
        first = result.packets[0]
        self.assertEqual(first.cut_handle, 17)
        self.assertEqual(first.xy, (10.0, 20.0, 10.0, 24.0,
                                   18.0, 24.0, 18.0, 20.0))
        self.assertEqual(first.uv, (0.0, 0.0, 0.0, 0.25,
                                    0.5, 0.25, 0.5, 0.0))
        self.assertEqual(first.rgba, (1.0, 1.0, 1.0, 1.0))
        self.assertIsNone(first.blend_override)
        self.assertTrue(first.front_face_flip)

    def test_active_mask_must_match_the_plan_mask_state(self):
        plan = _plan(active_mask=0, masked_index=1)
        with self.assertRaisesRegex(SymbolFrameAssemblyError, "mask state"):
            assemble_symbol_frame(plan, [(8, 4)] * 3, active_mask=4)

    def test_cut_extents_must_cover_masked_and_visible_symbols(self):
        plan = _plan(active_mask=4, masked_index=1)
        with self.assertRaisesRegex(SymbolFrameAssemblyError, "parallel"):
            assemble_symbol_frame(plan, [(8, 4), (3, 5)], active_mask=4)

    def test_malformed_late_command_fails_before_any_frame_is_returned(self):
        plan = _plan(count=2)
        invalid = replace(plan.commands[1], vertex_rgba=(1.0, float("nan"), 1.0, 1.0))
        malformed_plan = SymbolFrameRenderPlan((plan.commands[0], invalid))
        with self.assertRaisesRegex(SymbolFrameAssemblyError, "command failed validation"):
            assemble_symbol_frame(malformed_plan, [(8, 4), (8, 4)], active_mask=0)

    def test_player_transform_and_native_pre_player_winding_are_preserved(self):
        plan = _plan(count=1)
        result = assemble_symbol_frame(
            plan, [(8, 4)], active_mask=0,
            player_transform=PlayerTransform(scale_x=-1.0),
        )
        self.assertTrue(result.packets[0].front_face_flip)
        self.assertEqual(result.packets[0].xy[0], -10.0)
        self.assertEqual(result.packets[0].xy[2], -10.0)

    def test_bounded_command_limit_is_checked_before_entries(self):
        oversized = SymbolFrameRenderPlan(
            tuple(object() for _ in range(MAX_SYMBOL_FRAME_COMMANDS + 1))
        )
        with self.assertRaisesRegex(SymbolFrameAssemblyError, "bounded command limit"):
            assemble_symbol_frame(oversized, [], active_mask=0)

    def test_empty_frame_is_valid(self):
        plan = _plan(count=0)
        result = assemble_symbol_frame(plan, [], active_mask=0)
        self.assertEqual(result.packets, ())
        self.assertEqual(result.packet_count, 0)

    def test_cut_extents_require_signed_32_bit_integers(self):
        plan = _plan(count=1)
        with self.assertRaisesRegex(SymbolFrameAssemblyError, "signed 32-bit"):
            assemble_symbol_frame(plan, [(True, 4)], active_mask=0)
        with self.assertRaisesRegex(SymbolFrameAssemblyError, "signed 32-bit"):
            assemble_symbol_frame(plan, [(1 << 31, 4)], active_mask=0)


if __name__ == "__main__":
    unittest.main()
