"""Stage224: byte-for-byte portable C99 vs Python synthetic PNG padding parity."""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

from heman_tools.native_png_zero_padding import reconstruct_native_zero_padded_texture
from heman_tools.native_texture_upload_gate import plan_native_texture_upload


class CBinding(ctypes.Structure):
    _fields_ = [
        ("texture_slot", ctypes.c_int32),
        ("width", ctypes.c_uint32), ("height", ctypes.c_uint32),
        ("rgba", ctypes.POINTER(ctypes.c_uint8)),
        ("rgba_size", ctypes.c_size_t),
        ("wrap_s_code", ctypes.c_int32), ("wrap_t_code", ctypes.c_int32),
        ("filter_mode_code", ctypes.c_int32),
    ]


class C99NativePNGUploadParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._temp = tempfile.TemporaryDirectory(prefix="heman-stage224-parity-")
        root = Path(__file__).resolve().parents[1]
        library = Path(cls._temp.name) / "native_png_upload.so"
        compiler = shlex.split(os.environ.get("CC", "cc"))
        command = compiler + [
            "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror", "-pedantic",
            "-shared", "-fPIC", "-I", str(root / "native" / "include"),
            str(root / "native" / "src" / "heman_native_png_upload.c"),
            "-o", str(library),
        ]
        try:
            subprocess.run(command, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as exc:
            raise AssertionError("Stage224 C99 library compile failed: " +
                                 (exc.stderr or exc.stdout)) from exc
        cls.lib = ctypes.CDLL(str(library))
        cls.lib.hm_native_png_prepare_rgba.argtypes = [
            ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t,
            ctypes.c_uint32, ctypes.c_uint32,
            ctypes.c_int32, ctypes.c_int32, ctypes.c_int32, ctypes.c_int32,
            ctypes.c_int32,
            ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t,
            ctypes.POINTER(CBinding),
        ]
        cls.lib.hm_native_png_prepare_rgba.restype = ctypes.c_int

    @classmethod
    def tearDownClass(cls):
        cls._temp.cleanup()

    def test_native_upload_matches_python_for_rgb_rgba_and_pow2_edges(self):
        for w, h in ((1, 1), (3, 2), (4, 4), (5, 7), (17, 4), (8, 5)):
            for has_alpha in (False, True):
                for wrap_s, wrap_t, filter_code in ((0, 0, 0), (1, 0, 1)):
                    with self.subTest(dimensions=(w, h), alpha=has_alpha, wrap=wrap_s):
                        rgba = bytes(
                            byte
                            for y in range(h) for x in range(w)
                            for byte in (
                                (11 * x + y) % 256, (17 * y + x) % 256,
                                (23 * x + y) % 256,
                                (x * 13 + y * 19) % 256 if has_alpha else 255,
                            )
                        )
                        layout = plan_native_texture_upload((w, h), (wrap_s, wrap_t), filter_code)
                        expected = reconstruct_native_zero_padded_texture(
                            layout, rgba, native_png_has_alpha=has_alpha,
                        )
                        src = (ctypes.c_uint8 * len(rgba)).from_buffer_copy(rgba)
                        out = (ctypes.c_uint8 * layout.allocated_rgba_size)()
                        binding = CBinding()
                        status = self.lib.hm_native_png_prepare_rgba(
                            src, len(rgba), w, h, int(has_alpha),
                            wrap_s, wrap_t, filter_code, 19,
                            out, len(out), ctypes.byref(binding),
                        )
                        self.assertEqual(status, 0)
                        self.assertEqual(bytes(out), expected.rgba)
                        self.assertEqual((binding.width, binding.height),
                                         (expected.width, expected.height))
                        self.assertEqual(binding.rgba_size, len(out))
                        self.assertEqual((binding.wrap_s_code, binding.wrap_t_code,
                                          binding.filter_mode_code), (wrap_s, wrap_t, filter_code))

    def test_failed_rgb_alpha_preserves_output_bytes_and_binding(self):
        src = (ctypes.c_uint8 * 4)(7, 8, 9, 12)
        out = (ctypes.c_uint8 * 64)(*([0xA5] * 64))
        binding = CBinding()
        binding.texture_slot = 77
        binding.width = 999
        status = self.lib.hm_native_png_prepare_rgba(
            src, 4, 1, 1, 0, 0, 0, 0, 2,
            out, 64, ctypes.byref(binding),
        )
        self.assertEqual(status, 1)
        self.assertEqual(bytes(out), bytes([0xA5]) * 64)
        self.assertEqual((binding.texture_slot, binding.width), (77, 999))


if __name__ == "__main__":
    unittest.main()
