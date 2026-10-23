"""Synthetic-only tests for the Stage204 multi-Symbol audit CLI helpers."""
from __future__ import annotations

import argparse
import io
import unittest

from PIL import Image

from heman_tools.private_multisymbol_frame_audit import (
    _checked_png_dimensions,
    _parse_active_mask,
    _parse_region,
    _require_rectangle_in_bounds,
)
from heman_tools.private_single_symbol_frame_decoder import PrivateFrameDecodeError


def png_bytes(size=(8, 8)):
    image = Image.new("RGBA", size, (12, 34, 56, 255))
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


class PrivateMultiSymbolFrameAuditTests(unittest.TestCase):
    def test_region_parser_requires_positive_interval(self):
        self.assertEqual(_parse_region("10:20"), (10, 20))
        with self.assertRaises(argparse.ArgumentTypeError):
            _parse_region("20:20")
        with self.assertRaises(argparse.ArgumentTypeError):
            _parse_region("20:10")

    def test_active_mask_parser_accepts_decimal_and_hex(self):
        self.assertEqual(_parse_active_mask("4"), 4)
        self.assertEqual(_parse_active_mask("0x10"), 16)
        with self.assertRaises(argparse.ArgumentTypeError):
            _parse_active_mask("0x100000000")

    def test_png_dimensions_helper_validates_full_png_and_rectangle(self):
        dims = _checked_png_dimensions(png_bytes((16, 8)), (2, 1, 3, 4))
        self.assertEqual(dims, (16, 8))
        with self.assertRaises(PrivateFrameDecodeError):
            _checked_png_dimensions(png_bytes((8, 8)), (7, 7, 2, 2))
        with self.assertRaises(PrivateFrameDecodeError):
            _checked_png_dimensions(b"not png", (0, 0, 1, 1))

    def test_cached_dimensions_still_validate_each_rectangle(self):
        _require_rectangle_in_bounds((1, 2, 3, 4), (8, 8))
        with self.assertRaisesRegex(PrivateFrameDecodeError, "PNG bounds"):
            _require_rectangle_in_bounds((7, 7, 2, 2), (8, 8))

    def test_zero_width_and_negative_origin_fail_closed(self):
        for rectangle in ((0, 0, 0, 1), (-1, 0, 1, 1), (0, -1, 1, 1)):
            with self.subTest(rectangle=rectangle), self.assertRaises(PrivateFrameDecodeError):
                _require_rectangle_in_bounds(rectangle, (8, 8))


if __name__ == "__main__":
    unittest.main()
