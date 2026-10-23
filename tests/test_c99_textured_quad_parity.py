"""Stage210: compare the C99 textured-quad oracle with the Python reference."""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

from heman_tools.native_render_state_contract import GL_ONE
from heman_tools.symbol_frame_assembler import NativeFramePacket
from heman_tools.textured_quad_reference import (
    FrameBlendState, RasterProjection, TexturePixels, render_textured_frame,
)


class CPacket(ctypes.Structure):
    _fields_ = [
        ("source_order", ctypes.c_uint32),
        ("cut_handle", ctypes.c_int32),
        ("front_face_flip", ctypes.c_int32),
        ("xy", ctypes.c_float * 8),
        ("uv", ctypes.c_float * 8),
        ("rgba", ctypes.c_float * 4),
        ("blend_override_enabled", ctypes.c_int32),
        ("blend_source", ctypes.c_int32),
        ("blend_destination", ctypes.c_int32),
    ]


class CDraw(ctypes.Structure):
    _fields_ = [("packet", ctypes.POINTER(CPacket)),
                ("texture_slot", ctypes.c_int32)]


class CBinding(ctypes.Structure):
    _fields_ = [
        ("texture_slot", ctypes.c_int32),
        ("width", ctypes.c_uint32),
        ("height", ctypes.c_uint32),
        ("rgba", ctypes.POINTER(ctypes.c_uint8)),
        ("rgba_size", ctypes.c_size_t),
        ("wrap_s_code", ctypes.c_int32),
        ("wrap_t_code", ctypes.c_int32),
        ("filter_mode_code", ctypes.c_int32),
    ]


class CProjection(ctypes.Structure):
    _fields_ = [("m00", ctypes.c_double), ("m01", ctypes.c_double),
                ("tx", ctypes.c_double), ("m10", ctypes.c_double),
                ("m11", ctypes.c_double), ("ty", ctypes.c_double)]


class CBlend(ctypes.Structure):
    _fields_ = [("source_factor", ctypes.c_uint32),
                ("destination_factor", ctypes.c_uint32)]


class CStats(ctypes.Structure):
    _fields_ = [("packets_with_coverage", ctypes.c_size_t),
                ("pixel_samples", ctypes.c_size_t)]


def _c_packet(packet: NativeFramePacket) -> CPacket:
    result = CPacket()
    result.source_order = packet.source_order
    result.cut_handle = packet.cut_handle
    result.front_face_flip = int(packet.front_face_flip)
    result.xy = (ctypes.c_float * 8)(*packet.xy)
    result.uv = (ctypes.c_float * 8)(*packet.uv)
    result.rgba = (ctypes.c_float * 4)(*packet.rgba)
    if packet.blend_override is None:
        result.blend_override_enabled = 0
        result.blend_source = -1
        result.blend_destination = -1
    else:
        result.blend_override_enabled = 1
        result.blend_source = packet.blend_override[0]
        result.blend_destination = packet.blend_override[1]
    return result


class C99TexturedQuadParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._temporary = tempfile.TemporaryDirectory(prefix="heman-c99-parity-")
        root = Path(__file__).resolve().parents[1]
        library_path = Path(cls._temporary.name) / "libheman_textured_quad_reference.so"
        compiler = shlex.split(os.environ.get("CC", "cc"))
        command = compiler + [
            "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror", "-pedantic",
            "-shared", "-fPIC",
            "-I", str(root / "native" / "include"),
            str(root / "native" / "src" / "heman_textured_quad_reference.c"),
            "-lm", "-o", str(library_path),
        ]
        subprocess.run(command, check=True, capture_output=True, text=True)
        cls._library = ctypes.CDLL(str(library_path))
        cls._library.hm_textured_quad_reference_render.argtypes = [
            ctypes.POINTER(CDraw), ctypes.c_size_t,
            ctypes.POINTER(CBinding), ctypes.c_size_t,
            ctypes.c_uint32, ctypes.c_uint32, ctypes.c_size_t,
            ctypes.POINTER(CProjection), ctypes.POINTER(CBlend),
            ctypes.POINTER(ctypes.c_uint8), ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_size_t, ctypes.POINTER(CStats),
        ]
        cls._library.hm_textured_quad_reference_render.restype = ctypes.c_int

    @classmethod
    def tearDownClass(cls):
        cls._temporary.cleanup()

    def test_multitexture_clipping_and_blend_match_byte_for_byte(self):
        texture_a = TexturePixels(
            2, 2,
            bytes((255, 0, 0, 255, 0, 255, 0, 255,
                   0, 0, 255, 128, 255, 255, 255, 128)),
            0, 0,
        )
        texture_b = TexturePixels(
            2, 2,
            bytes((128, 64, 0, 128, 0, 128, 255, 255,
                   255, 0, 128, 64, 16, 32, 48, 128)),
            1, 0,
        )
        packets = [
            NativeFramePacket(
                0, 41, False,
                (0., 0., 0., 4., 4., 4., 4., 0.),
                (0., 0., 0., 1., 1., 1., 1., 0.),
                (1., 1., 1., 1.), None, 4,
            ),
            NativeFramePacket(
                2, 42, False,
                (1., 0., 1., 4., 5., 4., 5., 0.),
                (-0.5, -0.5, -0.5, 1.5, 1.5, 1.5, 1.5, -0.5),
                (0.5, 1., 0.75, 0.5), (GL_ONE, GL_ONE), 9,
            ),
        ]
        textures = {4: texture_a, 9: texture_b}
        projection = RasterProjection(tx=0.25)
        blend = FrameBlendState()
        clear = (11, 13, 17, 19)
        width, height = 5, 4
        expected = render_textured_frame(
            packets, textures, width=width, height=height,
            projection=projection, frame_blend=blend, clear_rgba=clear,
        )

        c_packets = (CPacket * len(packets))(*[_c_packet(p) for p in packets])
        c_draws = (CDraw * len(packets))()
        for i, packet in enumerate(packets):
            pointer = ctypes.cast(
                ctypes.byref(c_packets, i * ctypes.sizeof(CPacket)),
                ctypes.POINTER(CPacket),
            )
            c_draws[i] = CDraw(pointer, packet.texture_slot)

        backing_buffers = []
        c_bindings = (CBinding * len(textures))()
        for i, (slot, texture) in enumerate(sorted(textures.items())):
            storage = (ctypes.c_uint8 * len(texture.rgba)).from_buffer_copy(texture.rgba)
            backing_buffers.append(storage)
            c_bindings[i] = CBinding(
                slot, texture.width, texture.height,
                ctypes.cast(storage, ctypes.POINTER(ctypes.c_uint8)),
                len(texture.rgba), texture.wrap_s_code, texture.wrap_t_code,
                texture.filter_mode_code,
            )

        c_projection = CProjection(
            projection.m00, projection.m01, projection.tx,
            projection.m10, projection.m11, projection.ty,
        )
        c_blend = CBlend(blend.source_factor, blend.destination_factor)
        c_clear = (ctypes.c_uint8 * 4)(*clear)
        stride = width * 4 + 8
        capacity = stride * height
        output = (ctypes.c_uint8 * capacity)()
        ctypes.memset(ctypes.addressof(output), 0xA5, capacity)
        stats = CStats(123, 456)

        status = self._library.hm_textured_quad_reference_render(
            c_draws, len(packets), c_bindings, len(textures),
            width, height, stride, ctypes.byref(c_projection),
            ctypes.byref(c_blend), c_clear, output, capacity,
            ctypes.byref(stats),
        )
        self.assertEqual(status, 0, f"C99 renderer status {status}")

        active_rows = b"".join(
            bytes(output[y * stride:y * stride + width * 4])
            for y in range(height)
        )
        self.assertEqual(active_rows, expected.rgba)
        self.assertEqual(stats.packets_with_coverage, expected.packets_with_coverage)
        self.assertEqual(stats.pixel_samples, expected.pixel_samples)
        for y in range(height):
            padding = bytes(output[y * stride + width * 4:(y + 1) * stride])
            self.assertEqual(padding, b"\xA5" * 8, f"row {y} padding changed")


if __name__ == "__main__":
    unittest.main()
