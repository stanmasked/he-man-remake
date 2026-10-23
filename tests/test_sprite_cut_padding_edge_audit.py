"""Synthetic-only tests for native PNG padding and edge-sampling audit."""
from __future__ import annotations

import io
import json
import struct
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from PIL import Image

from heman_tools.sprite_cut_padding_edge_audit import (
    SpritePaddingEdgeAuditError, audit_private_padding_edge_impact,
    classify_native_edge_sampling, pad_decoded_png_rows_zero_fill,
    summarize_padding_edge_impact,
)


def _field(value):
    return struct.pack("<H", len(value)) + value.encode("utf-16le")


def _repo_index(label, key, target):
    return (
        _field(label) + struct.pack("<HI", 0, 1)
        + _field(key) + struct.pack("<I", 0)
        + _field(target) + struct.pack("<I", 0)
    )


def _png_bytes(width, height):
    img = Image.new("RGBA", (width, height), (8, 20, 55, 255))
    output = io.BytesIO()
    img.save(output, format="PNG")
    return output.getvalue()


def _cut_record(x, y, width, height):
    return (_field("fakeCut") + _field("fakeTexture")
            + struct.pack("<I", 1) + struct.pack("<5i", 0, x, y, width, height))


def _synthetic_ipa(path, *, width=30, height=16, xlarge_rect=(31, 0, 2, 1),
                   wrap_s=0, wrap_t=0, omit_xlarge_png=False):
    scalar = bytearray(13)
    scalar[10] = wrap_s
    scalar[11] = wrap_t
    image_repo = (
        _field("ImageData") + struct.pack("<HI", 0, 1)
        + _field("fakeImage") + struct.pack("<I", 1)
        + _field("/textures/fake.png") + struct.pack("<I", 0)
    )
    texture_payload = _field("fakeTexture") + bytes(scalar) + _field("") + _field("fakeImage")
    with ZipFile(path, "w") as archive:
        for screen in ("screen-med", "screen-xlarge"):
            root = "Payload/MOTU.app/" + screen + "/"
            archive.writestr(
                root + "meta/SpriteCutData.repo",
                _repo_index("SpriteCutData", "fakeCut", "sprite/SpriteResData.wad"),
            )
            rectangle = (0, 0, 8, 9) if screen == "screen-med" else xlarge_rect
            archive.writestr(root + "sprite/SpriteResData.wad", _cut_record(*rectangle))
            archive.writestr(
                root + "meta/TextureData.repo",
                _repo_index("TextureData", "fakeTexture", "textureData/TextureData.wad"),
            )
            archive.writestr(root + "textureData/TextureData.wad", texture_payload)
            archive.writestr(root + "meta/ImageData.repo", image_repo)
            if screen != "screen-xlarge" or not omit_xlarge_png:
                archive.writestr(root + "textures/fake.png", _png_bytes(width, height))


class ZeroPaddingModelTests(unittest.TestCase):
    def test_rgb_rows_are_copied_and_right_bottom_padding_stays_zero(self):
        rows = (bytes([1, 2, 3, 4, 5, 6]),
                bytes([7, 8, 9, 10, 11, 12]),
                bytes([13, 14, 15, 16, 17, 18]))
        padded, dimensions = pad_decoded_png_rows_zero_fill(rows, 2, 3, 3)
        self.assertEqual(dimensions, (4, 4))
        stride = 4 * 3
        self.assertEqual(padded[0:6], rows[0])
        self.assertEqual(padded[6:stride], bytes(6))
        self.assertEqual(padded[stride:stride + 6], rows[1])
        self.assertEqual(padded[stride + 6:2 * stride], bytes(6))
        self.assertEqual(padded[2 * stride:2 * stride + 6], rows[2])
        self.assertEqual(padded[2 * stride + 6:3 * stride], bytes(6))
        self.assertEqual(padded[3 * stride:4 * stride], bytes(stride))

    def test_rgba_padding_is_zero_in_all_channels(self):
        padded, dimensions = pad_decoded_png_rows_zero_fill((bytes([1, 2, 3, 4]),), 1, 1, 4)
        self.assertEqual(dimensions, (4, 4))
        self.assertEqual(padded[:4], bytes([1, 2, 3, 4]))
        self.assertEqual(padded[4:], bytes(len(padded) - 4))

    def test_power_of_two_rows_require_no_padding(self):
        rows = (bytes(range(12)), bytes(range(12, 24)))
        padded, dimensions = pad_decoded_png_rows_zero_fill(rows, 4, 2, 3)
        self.assertEqual(dimensions, (4, 2))
        self.assertEqual(padded, b"".join(rows))

    def test_decoded_row_count_must_match_height(self):
        with self.assertRaisesRegex(SpritePaddingEdgeAuditError, "row count"):
            pad_decoded_png_rows_zero_fill((bytes(3),), 1, 2, 3)

    def test_decoded_row_width_must_match_exactly(self):
        with self.assertRaisesRegex(SpritePaddingEdgeAuditError, "exactly width"):
            pad_decoded_png_rows_zero_fill((bytes(5),), 2, 1, 3)

    def test_only_native_three_or_four_byte_rows_are_supported(self):
        with self.assertRaisesRegex(SpritePaddingEdgeAuditError, "3 or 4"):
            pad_decoded_png_rows_zero_fill((bytes(2),), 1, 1, 2)

    def test_padded_buffer_memory_is_bounded(self):
        with self.assertRaisesRegex(SpritePaddingEdgeAuditError, "memory limit"):
            pad_decoded_png_rows_zero_fill((bytes(32768 * 4),), 32768, 1, 4)


class NativeEdgeSamplingTests(unittest.TestCase):
    def test_clamp_edge_on_exact_power_of_two_samples_source_border(self):
        result = classify_native_edge_sampling((31, 0, 2, 1), (32, 16), (0, 0))
        self.assertEqual(result["geometry_status"], "outside_allocated")
        self.assertEqual(result["x_edge_sample"], "source_border_edge")
        self.assertEqual(result["overall_edge_sample"], "source_border_edge")

    def test_clamp_edge_on_padded_width_samples_zero_filled_padding(self):
        result = classify_native_edge_sampling((31, 0, 2, 1), (30, 16), (0, 0))
        self.assertEqual(result["x_edge_sample"], "zero_filled_padding_edge")
        self.assertEqual(result["overall_edge_sample"], "zero_filled_padding_edge")

    def test_clamp_edge_on_padded_height_samples_zero_filled_padding(self):
        result = classify_native_edge_sampling((0, 31, 1, 2), (16, 30), (0, 0))
        self.assertEqual(result["y_edge_sample"], "zero_filled_padding_edge")

    def test_mixed_axis_overrun_reports_padding_and_source_edge_separately(self):
        result = classify_native_edge_sampling((31, 31, 2, 2), (32, 30), (0, 0))
        self.assertEqual(result["x_edge_sample"], "source_border_edge")
        self.assertEqual(result["y_edge_sample"], "zero_filled_padding_edge")
        self.assertEqual(result["overall_edge_sample"], "zero_filled_padding_edge")

    def test_repeat_mode_remains_repeat_not_edge_clamp(self):
        result = classify_native_edge_sampling((31, 0, 2, 1), (30, 16), (1, 0))
        self.assertEqual(result["x_edge_sample"], "repeat_wrap")
        self.assertEqual(result["overall_edge_sample"], "repeat_wrap")

    def test_mixed_repeat_and_padded_clamp_is_reported(self):
        result = classify_native_edge_sampling((31, 31, 2, 2), (30, 30), (1, 0))
        self.assertEqual(result["x_edge_sample"], "repeat_wrap")
        self.assertEqual(result["y_edge_sample"], "zero_filled_padding_edge")
        self.assertEqual(result["overall_edge_sample"], "mixed_axis_sampling")

    def test_negative_uv_is_preserved_and_not_misclassified_as_overflow(self):
        result = classify_native_edge_sampling((0, -1, 1, 2), (16, 16), (0, 0))
        self.assertEqual(result["geometry_status"], "invalid")
        self.assertTrue(result["negative_uv"])
        self.assertFalse(result["uv_above_one"])
        self.assertEqual(result["overall_edge_sample"], "not_outside_allocated")

    def test_padded_only_cut_is_not_an_allocated_edge_overflow(self):
        result = classify_native_edge_sampling((30, 0, 2, 1), (30, 16), (0, 0))
        self.assertEqual(result["geometry_status"], "inside_allocated_only")
        self.assertEqual(result["overall_edge_sample"], "not_outside_allocated")

    def test_unknown_wrap_mode_remains_unresolved(self):
        result = classify_native_edge_sampling((31, 0, 2, 1), (30, 16), (9, 0))
        self.assertEqual(result["x_edge_sample"], "unrecognized_wrap")
        self.assertEqual(result["overall_edge_sample"], "unresolved_wrap")


class PaddingEdgeAggregationTests(unittest.TestCase):
    def test_aggregate_counts_are_redacted(self):
        rows = {
            ("private-A", 0): ((31, 0, 2, 1), (30, 16)),
            ("private-B", 0): ((31, 0, 2, 1), (32, 16)),
            ("private-C", 0): ((0, -1, 1, 2), (16, 16)),
        }
        wraps = {key: (0, 0) for key in rows}
        result = summarize_padding_edge_impact(rows, dict(rows), wraps, dict(wraps))
        med = result["per_pack"]["screen-med"]
        self.assertEqual(med["geometry_categories"]["outside_allocated"], 2)
        self.assertEqual(med["edge_sampling_counts"]["zero_filled_padding_edge"], 1)
        self.assertEqual(med["edge_sampling_counts"]["source_border_edge"], 1)
        self.assertEqual(med["edge_sampling_counts"]["negative_uv_records"], 1)
        self.assertNotIn("private-A", json.dumps(result))
        self.assertTrue(result["native_padding_right_and_bottom_bytes_zeroed"])

    def test_mismatched_wrap_pairs_fail_closed(self):
        rows = {("private-A", 0): ((31, 0, 2, 1), (30, 16))}
        with self.assertRaisesRegex(SpritePaddingEdgeAuditError, "wrap settings differ"):
            summarize_padding_edge_impact(rows, dict(rows), {("private-A", 0): (0, 0)},
                                          {("private-A", 0): (1, 1)})


class SyntheticIpaPaddingEdgeTests(unittest.TestCase):
    def test_fake_ipa_identifies_zero_padding_edge(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "synthetic.ipa"
            _synthetic_ipa(path, width=30, height=16, xlarge_rect=(31, 0, 2, 1))
            report = audit_private_padding_edge_impact(path)
        large = report["per_pack"]["screen-xlarge"]
        self.assertEqual(large["edge_sampling_counts"]["zero_filled_padding_edge"], 1)
        self.assertFalse(report["native_uv_coordinates_clipped_by_model"])
        self.assertNotIn("fakeCut", json.dumps(report))

    def test_fake_ipa_identifies_source_border_edge_for_exact_pow2(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "synthetic.ipa"
            _synthetic_ipa(path, width=32, height=16, xlarge_rect=(31, 0, 2, 1))
            report = audit_private_padding_edge_impact(path)
        large = report["per_pack"]["screen-xlarge"]
        self.assertEqual(large["edge_sampling_counts"]["source_border_edge"], 1)

    def test_missing_png_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "synthetic.ipa"
            _synthetic_ipa(path, omit_xlarge_png=True)
            with self.assertRaises(ValueError):
                audit_private_padding_edge_impact(path)


if __name__ == "__main__":
    unittest.main()
