"""Asset-free regressions for Stage191 paired PNG/SpriteCut bounds census."""
from __future__ import annotations

import io
import json
import struct
import unittest
from zipfile import ZipFile

from PIL import Image

from heman_tools.sprite_cut_png_bounds_census import (
    SpriteCutBoundsError, _png_ihdr_dimensions, classify_rectangle,
    summarize_paired_cut_bounds,
)


def fixture_png() -> bytes:
    img = Image.new("RGBA", (17, 19), (8, 20, 55, 255))
    output = io.BytesIO()
    img.save(output, format="PNG")
    return output.getvalue()


class SpriteCutPngBoundsTests(unittest.TestCase):
    def test_cut_exactly_touching_bottom_right_edge_is_inside(self):
        self.assertEqual(classify_rectangle((3, 4, 7, 6), (10, 10)), ("inside", 0, 0))

    def test_one_pixel_horizontal_overrun_is_not_clipped(self):
        self.assertEqual(classify_rectangle((3, 4, 8, 6), (10, 10)), ("outside", 1, 0))

    def test_large_vertical_overrun_is_reported_not_repaired(self):
        self.assertEqual(classify_rectangle((0, 2, 1, 513), (10, 3)), ("outside", 0, 512))

    def test_negative_origin_fails_closed_as_invalid_geometry(self):
        self.assertEqual(classify_rectangle((-1, 0, 2, 2), (8, 8)), ("invalid", 0, 0))

    def test_zero_width_fails_closed_as_invalid_geometry(self):
        self.assertEqual(classify_rectangle((0, 0, 0, 2), (8, 8)), ("invalid", 0, 0))

    def test_boolean_rectangle_coordinate_rejected(self):
        with self.assertRaisesRegex(SpriteCutBoundsError, "four integer fields"):
            classify_rectangle((False, 0, 1, 1), (10, 10))

    def test_invalid_png_dimensions_rejected(self):
        with self.assertRaisesRegex(SpriteCutBoundsError, "positive integers"):
            classify_rectangle((0, 0, 2, 2), (0, 10))

    def test_pair_census_tracks_resolution_specific_exceptions_without_names(self):
        cases = {
            ("synthetic-key-A", 0): ((0, 0, 1, 1), (10, 10)),
            ("synthetic-key-B", 0): ((9, 0, 1, 1), (10, 10)),
            ("synthetic-key-C", 0): ((0, 9, 1, 2), (10, 10)),
            ("synthetic-key-D", 0): ((9, 9, 18, 18), (10, 10)),
            ("synthetic-key-E", 0): ((0, 0, -1, 1), (10, 10)),
            ("synthetic-key-F", 0): ((0, 0, 1, 1), (10, 10)),
        }
        extra = dict(cases)
        extra[("synthetic-key-B", 0)] = ((9, 0, 2, 1), (10, 10))
        extra[("synthetic-key-C", 0)] = ((0, 9, 1, 3), (10, 10))
        result = summarize_paired_cut_bounds(cases, extra)
        med = result["per_pack"]["screen-med"]
        large = result["per_pack"]["screen-xlarge"]
        self.assertEqual((med["inside_png"], med["outside_png"],
                          med["invalid_rectangle"]), (3, 2, 1))
        self.assertEqual((large["inside_png"], large["outside_png"],
                          large["invalid_rectangle"]), (2, 3, 1))
        self.assertEqual(result["paired_category_counts"]["inside_med__outside_xlarge"], 1)
        self.assertEqual(result["paired_category_counts"]["outside_med__outside_xlarge"], 2)
        self.assertEqual(med["overrun_magnitude"]["one_pixel"], 1)
        self.assertEqual(med["overrun_magnitude"]["above_sixteen"], 1)
        self.assertFalse(result["padding_or_atlas_repair_inferred"])
        self.assertFalse(result["outside_or_invalid_cuts_may_be_cropped_or_rendered"])
        serialized = json.dumps(result)
        self.assertNotIn("synthetic-key-A", serialized)
        self.assertNotIn("synthetic-key-E", serialized)

    def test_paired_cut_keys_must_match(self):
        a = {("fake", 0): ((0, 0, 1, 1), (3, 3))}
        b = {("other", 0): ((0, 0, 1, 1), (3, 3))}
        with self.assertRaisesRegex(SpriteCutBoundsError, "inventories differ"):
            summarize_paired_cut_bounds(a, b)

    def test_valid_png_header_is_recognized_without_full_image_decode(self):
        buf = io.BytesIO()
        with ZipFile(buf, "w") as z:
            z.writestr("synthetic.png", fixture_png())
        buf.seek(0)
        with ZipFile(buf, "r") as z:
            self.assertEqual(
                _png_ihdr_dimensions(z, z.getinfo("synthetic.png")), (17, 19)
            )

    def test_tampered_ihdr_fails_crc_gate(self):
        image = bytearray(fixture_png())
        struct.pack_into(">I", image, 16, 18)
        buf = io.BytesIO()
        with ZipFile(buf, "w") as z:
            z.writestr("synthetic.png", image)
        buf.seek(0)
        with ZipFile(buf, "r") as z:
            with self.assertRaisesRegex(SpriteCutBoundsError, "checksum"):
                _png_ihdr_dimensions(z, z.getinfo("synthetic.png"))


if __name__ == "__main__":
    unittest.main()
