"""Synthetic regressions for Stage199 native quad geometry."""
import math
import unittest
from dataclasses import replace

from heman_tools.native_sprite_cut_uv import NativeSpriteCutUV
from heman_tools.symbol_frame_render_plan import SymbolDrawCommand, PlayerTransform
from heman_tools.symbol_render_contract import SymbolTweenSelectors
from heman_tools.symbol_mesh_geometry import (
    SymbolMeshGeometryError, build_symbol_quad_geometry, expand_native_uv_corners,
)


def command(*, rotation=0, offset_x=0, offset_y=0, scale_x=1.0, scale_y=1.0):
    uv = NativeSpriteCutUV(-0.25, 0.0, 1.25, 1.0, 8, 8, 0, 0,
                           "GL_CLAMP_TO_EDGE", "GL_CLAMP_TO_EDGE")
    return SymbolDrawCommand(
        source_order=3,
        cut_handle=17,
        uv=uv,
        vertex_rgba=(1.0, 0.5, 0.25, 1.0),
        draw_enabled=True,
        blend_override=None,
        rotation_degrees=rotation,
        offset_x=offset_x,
        offset_y=offset_y,
        scale_x=scale_x,
        scale_y=scale_y,
        tween_selectors=SymbolTweenSelectors(1, 1, 1, 1),
        symbol_mask=0,
    )


def close_pair(actual, expected, tol=2e-5):
    return all(abs(a - b) <= tol for a, b in zip(actual, expected))


class SymbolMeshGeometryTests(unittest.TestCase):
    def test_native_vertex_order_and_centered_quad(self):
        result = build_symbol_quad_geometry(command(), 8, 4)
        self.assertEqual(result.vertices, ((0.0, 0.0), (0.0, 4.0),
                                           (8.0, 4.0), (8.0, 0.0)))
        self.assertTrue(result.front_face_flip)

    def test_local_scale_then_offset(self):
        result = build_symbol_quad_geometry(
            command(offset_x=10, offset_y=20, scale_x=2.0, scale_y=3.0), 4, 2
        )
        self.assertEqual(result.vertices, ((8.0, 18.0), (8.0, 24.0),
                                           (16.0, 24.0), (16.0, 18.0)))

    def test_local_rotation_then_offset(self):
        result = build_symbol_quad_geometry(
            command(rotation=90, offset_x=3, offset_y=4), 2, 2
        )
        self.assertTrue(close_pair(result.vertices[0], (5.0, 4.0)))
        self.assertTrue(close_pair(result.vertices[1], (3.0, 4.0)))
        self.assertTrue(close_pair(result.vertices[2], (3.0, 6.0)))
        self.assertTrue(close_pair(result.vertices[3], (5.0, 6.0)))

    def test_player_transform_order_and_independent_pivots(self):
        player = PlayerTransform(
            rotation_degrees=90.0,
            rotation_pivot_x=1.0,
            rotation_pivot_y=1.0,
            scale_x=2.0,
            scale_y=0.5,
            scale_pivot_x=0.0,
            scale_pivot_y=0.0,
            translation_x=5.0,
            translation_y=7.0,
        )
        result = build_symbol_quad_geometry(command(), 2, 2, player)
        self.assertTrue(close_pair(result.vertices[0], (9.0, 7.0)))

    def test_negative_scale_mirrors_and_flips_winding(self):
        normal = build_symbol_quad_geometry(command(), 4, 2)
        mirrored = build_symbol_quad_geometry(command(scale_x=-1.0), 4, 2)
        self.assertTrue(normal.front_face_flip)
        self.assertFalse(mirrored.front_face_flip)
        self.assertEqual(mirrored.vertices[0], (4.0, 0.0))

    def test_player_negative_scale_does_not_recompute_native_winding_flag(self):
        player = PlayerTransform(scale_x=-1.0)
        result = build_symbol_quad_geometry(command(offset_x=2), 4, 2, player)
        self.assertTrue(result.front_face_flip)
        self.assertEqual(result.vertices[0], (-2.0, 0.0))

    def test_zero_and_negative_dimensions_are_preserved(self):
        zero = build_symbol_quad_geometry(command(), 0, 4)
        negative = build_symbol_quad_geometry(command(), -4, 2)
        self.assertEqual(zero.vertices[0][0], 0.0)
        self.assertEqual(zero.vertices[2][0], 0.0)
        self.assertEqual(negative.vertices[0], (0.0, 0.0))
        self.assertEqual(negative.vertices[2], (-4.0, 2.0))

    def test_native_uv_corner_order_matches_sprite_cut_array(self):
        item = replace(
            command(),
            uv=NativeSpriteCutUV(-0.25, 0.125, 1.25, 0.875, 8, 8, 0, 0,
                                 "GL_CLAMP_TO_EDGE", "GL_CLAMP_TO_EDGE"),
        )
        self.assertEqual(
            expand_native_uv_corners(item),
            ((-0.25, 0.125), (-0.25, 0.875),
             (1.25, 0.875), (1.25, 0.125)),
        )

    def test_uv_expansion_rejects_invalid_command(self):
        item = replace(command(), vertex_rgba=(1.0, 1.0, float("nan"), 1.0))
        with self.assertRaises(SymbolMeshGeometryError):
            expand_native_uv_corners(item)

    def test_out_of_range_uvs_are_not_modified(self):
        item = command()
        before = (item.uv.u0, item.uv.v0, item.uv.u1, item.uv.v1)
        build_symbol_quad_geometry(item, 3, 5)
        self.assertEqual((item.uv.u0, item.uv.v0, item.uv.u1, item.uv.v1), before)
        self.assertEqual(before, (-0.25, 0.0, 1.25, 1.0))

    def test_player_transform_nonfinite_rejected(self):
        with self.assertRaises(ValueError):
            PlayerTransform(scale_x=float("nan"))

    def test_cut_dimensions_require_signed_32_bit_integers(self):
        with self.assertRaisesRegex(SymbolMeshGeometryError, "signed 32-bit"):
            build_symbol_quad_geometry(command(), True, 2)
        with self.assertRaisesRegex(SymbolMeshGeometryError, "signed 32-bit"):
            build_symbol_quad_geometry(command(), 1 << 31, 2)

    def test_large_transform_overflow_fails_closed(self):
        item = command(scale_x=3.0e38)
        with self.assertRaises(SymbolMeshGeometryError):
            build_symbol_quad_geometry(item, 2_000_000_000, 2)

    def test_command_not_mutated(self):
        item = command(rotation=30, offset_x=-4, scale_y=-2.0)
        before = item
        build_symbol_quad_geometry(item, 9, 7)
        self.assertIs(item, before)
        self.assertEqual(item.offset_x, -4)
        self.assertEqual(item.scale_y, -2.0)


if __name__ == "__main__":
    unittest.main()
