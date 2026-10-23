"""Synthetic-only Stage207 tests for the CPU textured-quad reference renderer."""
from __future__ import annotations
import unittest

from heman_tools.native_render_state_contract import GL_ONE, GL_ZERO
from heman_tools.symbol_frame_assembler import NativeFramePacket
from heman_tools.textured_quad_reference import (
    FrameBlendState, RasterProjection, TexturePixels, TexturedQuadRenderError,
    render_textured_frame,
)


def _packet(*, order=0, handle=7, slot=0,
            xy=(0., 0., 0., 2., 2., 2., 2., 0.),
            uv=(0., 0., 0., 1., 1., 1., 1., 0.),
            rgba=(1., 1., 1., 1.), blend=None):
    return NativeFramePacket(order, handle, False, tuple(xy), tuple(uv), tuple(rgba), blend, slot)


def _render(packet, texture, *, width=2, height=2, projection=None, blend=None,
            clear=(0, 0, 0, 0)):
    return render_textured_frame(
        [packet], {packet.texture_slot: texture}, width=width, height=height,
        projection=projection or RasterProjection(),
        frame_blend=blend or FrameBlendState(), clear_rgba=clear,
    )


class TexturedQuadReferenceTests(unittest.TestCase):
    def test_nearest_sampling_and_native_corner_order(self):
        texture = TexturePixels(2, 2, bytes((
            255,0,0,255, 0,255,0,255, 0,0,255,255, 255,255,255,255
        )), 0, 0)
        result = _render(_packet(), texture)
        self.assertEqual(result.rgba, texture.rgba)
        self.assertEqual((result.packets_considered, result.packets_with_coverage,
                          result.pixel_samples), (1, 1, 4))

    def test_s_clamp_and_repeat_are_independent(self):
        texels = bytes((255,0,0,255, 0,255,0,255))
        packet = _packet(xy=(0,0,0,1,2,1,2,0),
                         uv=(-.5,0,-.5,1,.5,1,.5,0))
        a = _render(packet, TexturePixels(2,1,texels,0,0), width=2, height=1)
        b = _render(packet, TexturePixels(2,1,texels,1,0), width=2, height=1)
        self.assertEqual(a.rgba, bytes((255,0,0,255, 255,0,0,255)))
        self.assertEqual(b.rgba, bytes((0,255,0,255, 255,0,0,255)))

    def test_t_repeat_does_not_change_s_clamp(self):
        texture = TexturePixels(1,2,bytes((255,0,0,255, 0,255,0,255)),0,1)
        packet = _packet(uv=(0,-.5,0,.5,1,.5,1,-.5))
        result = _render(packet, texture)
        self.assertEqual(result.rgba, bytes((
            0,255,0,255, 0,255,0,255, 255,0,0,255, 255,0,0,255
        )))

    def test_default_premultiplied_blend_does_not_multiply_texel_twice(self):
        texture = TexturePixels(1,1,bytes((128,0,0,128)),0,0)
        packet = _packet(xy=(0,0,0,1,1,1,1,0), uv=(0,0,0,1,1,1,1,0))
        result = _render(packet, texture, width=1, height=1, clear=(0,0,255,255))
        self.assertEqual(result.rgba, bytes((128,0,127,255)))

    def test_symbol_blend_override_precedes_frame_default(self):
        texture = TexturePixels(1,1,bytes((128,0,0,128)),0,0)
        packet = _packet(xy=(0,0,0,1,1,1,1,0), uv=(0,0,0,1,1,1,1,0),
                         blend=(GL_ONE,GL_ONE))
        result = _render(packet, texture, width=1, height=1, clear=(0,0,255,255))
        self.assertEqual(result.rgba, bytes((128,0,255,255)))

    def test_frame_level_custom_blend_is_used_without_override(self):
        texture = TexturePixels(1,1,bytes((64,0,0,64)),0,0)
        packet = _packet(xy=(0,0,0,1,1,1,1,0), uv=(0,0,0,1,1,1,1,0))
        result = _render(packet, texture, width=1, height=1, clear=(0,0,0,0),
                         blend=FrameBlendState(GL_ZERO,GL_ONE))
        self.assertEqual(result.rgba, bytes((0,0,0,0)))

    def test_source_order_controls_alpha_composition(self):
        red = TexturePixels(1,1,bytes((128,0,0,128)),0,0)
        green = TexturePixels(1,1,bytes((0,128,0,128)),0,0)
        packets = [_packet(order=0, handle=7, slot=0, xy=(0,0,0,1,1,1,1,0),
                           uv=(0,0,0,1,1,1,1,0)),
                   _packet(order=2, handle=8, slot=1, xy=(0,0,0,1,1,1,1,0),
                           uv=(0,0,0,1,1,1,1,0))]
        result = render_textured_frame(
            packets, {0:red,1:green}, width=1, height=1,
            projection=RasterProjection(), frame_blend=FrameBlendState())
        self.assertEqual(result.rgba, bytes((64,128,0,192)))

    def test_explicit_projection_controls_placement(self):
        texture = TexturePixels(1,1,bytes((255,255,255,255)),0,0)
        packet = _packet(xy=(0,0,0,1,1,1,1,0), uv=(0,0,0,1,1,1,1,0))
        result = _render(packet, texture, width=2, height=1,
                         projection=RasterProjection(tx=1.0))
        self.assertEqual(result.rgba, bytes((0,0,0,0, 255,255,255,255)))

    def test_empty_frame_returns_clear_color(self):
        result = render_textured_frame([], {}, width=2, height=1,
            projection=RasterProjection(), frame_blend=FrameBlendState(),
            clear_rgba=(1,2,3,4))
        self.assertEqual(result.rgba, bytes((1,2,3,4,1,2,3,4)))
        self.assertEqual(result.pixel_samples, 0)

    def test_missing_texture_fails_closed(self):
        with self.assertRaisesRegex(TexturedQuadRenderError, "no resolved texture"):
            render_textured_frame([_packet()], {}, width=2, height=2,
                projection=RasterProjection(), frame_blend=FrameBlendState())

    def test_linear_filter_is_not_silently_approximated(self):
        with self.assertRaisesRegex(TexturedQuadRenderError, "nearest filter selector"):
            TexturePixels(1,1,bytes(4),0,0,filter_mode_code=1)

    def test_invalid_wrap_code_fails_closed(self):
        with self.assertRaisesRegex(TexturedQuadRenderError, "S wrap code"):
            TexturePixels(1,1,bytes(4),2,0)

    def test_malformed_uv_corner_order_fails_closed(self):
        packet = _packet(uv=(0,0,.1,1,1,1,1,0))
        texture = TexturePixels(1,1,bytes((255,255,255,255)),0,0)
        with self.assertRaisesRegex(TexturedQuadRenderError, "UV corners"):
            _render(packet, texture)

    def test_non_parallelogram_fails_closed(self):
        packet = _packet(xy=(0,0,0,2,3,2,2,0))
        texture = TexturePixels(1,1,bytes((255,255,255,255)),0,0)
        with self.assertRaisesRegex(TexturedQuadRenderError, "not an affine parallelogram"):
            _render(packet, texture)

    def test_unsorted_source_order_fails_closed(self):
        texture = TexturePixels(1,1,bytes((255,255,255,255)),0,0)
        with self.assertRaisesRegex(TexturedQuadRenderError, "strictly increasing"):
            render_textured_frame([_packet(order=2),_packet(order=1)], {0:texture},
                width=2,height=2,projection=RasterProjection(),frame_blend=FrameBlendState())

    def test_invalid_symbol_blend_factor_fails_closed(self):
        packet = _packet(blend=(0xDEAD,GL_ONE))
        texture = TexturePixels(1,1,bytes((255,255,255,255)),0,0)
        with self.assertRaisesRegex(TexturedQuadRenderError, "source factor"):
            _render(packet, texture)

    def test_src_alpha_saturate_cannot_be_destination_factor(self):
        packet = _packet(blend=(GL_ONE,0x0308))
        texture = TexturePixels(1,1,bytes((255,255,255,255)),0,0)
        with self.assertRaisesRegex(TexturedQuadRenderError, "only as a source"):
            _render(packet, texture)

    def test_degenerate_quad_has_no_coverage(self):
        packet = _packet(xy=(0,0,0,0,0,0,0,0))
        texture = TexturePixels(1,1,bytes((255,255,255,255)),0,0)
        result = _render(packet, texture)
        self.assertEqual(result.rgba, bytes(16))
        self.assertEqual(result.packets_with_coverage, 0)

    def test_source_order_gap_from_masked_symbol_is_allowed(self):
        texture = TexturePixels(1,1,bytes((255,255,255,255)),0,0)
        result = render_textured_frame([_packet(order=0),_packet(order=2,handle=8,slot=1)],
            {0:texture,1:texture},width=2,height=2,
            projection=RasterProjection(),frame_blend=FrameBlendState())
        self.assertEqual((result.packets_considered,result.packets_with_coverage),(2,2))

    def test_two_cut_handles_can_share_one_texture_slot(self):
        texture = TexturePixels(1,1,bytes((255,255,255,255)),0,0)
        packets = [
            _packet(order=0, handle=7, slot=4, xy=(0,0,0,1,1,1,1,0),
                    uv=(0,0,0,1,1,1,1,0)),
            _packet(order=2, handle=8, slot=4, xy=(0,0,0,1,1,1,1,0),
                    uv=(0,0,0,1,1,1,1,0)),
        ]
        result = render_textured_frame(packets, {4:texture}, width=1, height=1,
            projection=RasterProjection(), frame_blend=FrameBlendState())
        self.assertEqual((result.packets_considered, result.pixel_samples), (2,2))

    def test_missing_texture_slot_fails_closed(self):
        packet = NativeFramePacket(0, 7, False, (0.,0.,0.,1.,1.,1.,1.,0.),
                                   (0.,0.,0.,1.,1.,1.,1.,0.),
                                   (1.,1.,1.,1.), None, None)
        texture = TexturePixels(1,1,bytes((255,255,255,255)),0,0)
        with self.assertRaisesRegex(TexturedQuadRenderError, "texture_slot"):
            render_textured_frame([packet], {0:texture}, width=1, height=1,
                projection=RasterProjection(), frame_blend=FrameBlendState())

    def test_unrepresentably_large_integer_fails_closed(self):
        packet = _packet(xy=(10**1000, 0, 0, 1, 1, 1, 1, 0))
        texture = TexturePixels(1,1,bytes((255,255,255,255)),0,0)
        with self.assertRaisesRegex(TexturedQuadRenderError, "finite and representable"):
            _render(packet, texture)

    def test_clear_color_requires_byte_channels(self):
        with self.assertRaisesRegex(TexturedQuadRenderError, "four byte channels"):
            render_textured_frame([],{},width=1,height=1,projection=RasterProjection(),
                frame_blend=FrameBlendState(),clear_rgba=(0,0,0,256))


if __name__ == "__main__":
    unittest.main()
