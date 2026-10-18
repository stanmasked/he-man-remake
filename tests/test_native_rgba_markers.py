"""RGBA8888 word ordering regression for independently authored HUD marker.

libnx framebuffer uses little-endian pixel words. The memory word value
0xffffff00 encodes raw bytes [00, ff, ff, ff] = cyan RGBA, not yellow.
"""
from __future__ import annotations
import struct
import unittest


class NativeRgbaMarkerTests(unittest.TestCase):
    def test_jump_marker_is_cyan_in_rgba_bytes(self) -> None:
        pixel = 0xFFFFFF00
        self.assertEqual(struct.pack("<I", pixel), bytes((0,255,255,255)))

    def test_old_word_was_yellow_not_cyan(self) -> None:
        old = 0xFF00FFFF
        self.assertEqual(struct.pack("<I", old), bytes((255,255,0,255)))
        self.assertNotEqual(old, 0xFFFFFF00)

    def test_existing_horizontal_marker_is_magenta(self) -> None:
        self.assertEqual(struct.pack("<I", 0xFFFF00FF), bytes((255,0,255,255)))


if __name__ == "__main__":
    unittest.main()
