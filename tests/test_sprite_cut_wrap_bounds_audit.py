"""Synthetic-only tests for Stage194 TextureData wrap and cut-bound correlation."""
from __future__ import annotations

import io
import json
import struct
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from PIL import Image

from heman_tools.sprite_cut_png_bounds_census import SpriteCutBoundsError
from heman_tools.sprite_cut_wrap_bounds_audit import (
    SpriteCutWrapAuditError, audit_private_wrap_bounds, decode_texture_wrap_codes,
    summarize_wrap_bounds, texture_wrap_mode,
)


def _field(value):
    return struct.pack("<H", len(value)) + value.encode("utf-16le")


def _repo_index(label, key, target):
    return (
        _field(label) + struct.pack("<HI", 0, 1)
        + _field(key) + struct.pack("<I", 0)
        + _field(target) + struct.pack("<I", 0)
    )


def _png_bytes(width=17, height=19):
    img = Image.new("RGBA", (width, height), (8, 20, 55, 255))
    output = io.BytesIO()
    img.save(output, format="PNG")
    return output.getvalue()


def _cut_record(x, y, width, height):
    return (_field("fakeCut") + _field("fakeTexture")
            + struct.pack("<I", 1) + struct.pack("<5i", 0, x, y, width, height))


def _synthetic_ipa(path, *, wrap_s=0, wrap_t=0, xlarge_rect=(0, 0, 8, 9),
                   xlarge_wrap_s=None, omit_png=False):
    scalar = bytearray(13)
    scalar[10] = wrap_s
    scalar[11] = wrap_t
    large_scalar = bytearray(scalar)
    if xlarge_wrap_s is not None:
        large_scalar[10] = xlarge_wrap_s
    image_repo = (
        _field("ImageData") + struct.pack("<HI", 0, 1)
        + _field("fakeImage") + struct.pack("<I", 1)
        + _field("/textures/fake.png") + struct.pack("<I", 0)
    )
    texture_payload = _field("fakeTexture") + bytes(scalar) + _field("") + _field("fakeImage")
    large_texture_payload = _field("fakeTexture") + bytes(large_scalar) + _field("") + _field("fakeImage")
    with ZipFile(path, "w") as archive:
        for screen in ("screen-med", "screen-xlarge"):
            root = "Payload/MOTU.app/" + screen + "/"
            archive.writestr(
                root + "meta/SpriteCutData.repo",
                _repo_index("SpriteCutData", "fakeCut", "sprite/SpriteResData.wad"),
            )
            rectangle = (0, 0, 8, 9) if screen == "screen-med" else xlarge_rect
            archive.writestr(root + "sprite/SpriteResData.wad",
                             _cut_record(*rectangle))
            archive.writestr(
                root + "meta/TextureData.repo",
                _repo_index("TextureData", "fakeTexture", "textureData/TextureData.wad"),
            )
            archive.writestr(
                root + "textureData/TextureData.wad",
                texture_payload if screen == "screen-med" else large_texture_payload,
            )
            archive.writestr(root + "meta/ImageData.repo", image_repo)
            if screen != "screen-xlarge" or not omit_png:
                archive.writestr(root + "textures/fake.png", _png_bytes())


class TextureWrapCodeTests(unittest.TestCase):
    def test_wrap_codes_are_read_from_native_scalar_offsets_ten_and_eleven(self):
        scalar = bytearray(13)
        scalar[0] = 7
        scalar[10] = 1
        scalar[11] = 0
        self.assertEqual(decode_texture_wrap_codes(bytes(scalar)), (1, 0))

    def test_scalar_block_must_have_exactly_thirteen_bytes(self):
        with self.assertRaisesRegex(SpriteCutWrapAuditError, "exactly 13"):
            decode_texture_wrap_codes(bytes(12))

    def test_native_code_zero_means_clamp_to_edge(self):
        self.assertEqual(texture_wrap_mode(0), "clamp_to_edge")

    def test_native_code_one_means_repeat(self):
        self.assertEqual(texture_wrap_mode(1), "repeat")

    def test_unknown_wrap_code_is_not_guessed(self):
        self.assertEqual(texture_wrap_mode(2), "unrecognized")

    def test_boolean_wrap_code_is_rejected(self):
        with self.assertRaisesRegex(SpriteCutWrapAuditError, "unsigned byte"):
            texture_wrap_mode(True)

    def test_out_of_range_wrap_code_is_rejected(self):
        with self.assertRaisesRegex(SpriteCutWrapAuditError, "unsigned byte"):
            texture_wrap_mode(256)


class WrapBoundsAggregationTests(unittest.TestCase):
    def setUp(self):
        self.med = {
            ("synthetic-A", 0): ((0, 0, 2, 2), (17, 19)),
            ("synthetic-B", 0): ((31, 0, 2, 1), (17, 19)),
            ("synthetic-C", 0): ((0, -1, 2, 2), (17, 19)),
        }
        self.large = dict(self.med)
        self.large[("synthetic-A", 0)] = ((17, 0, 2, 2), (17, 19))
        self.wraps = {
            ("synthetic-A", 0): (0, 0),
            ("synthetic-B", 0): (0, 0),
            ("synthetic-C", 0): (0, 0),
        }

    def test_bounds_are_grouped_by_clamp_to_edge(self):
        result = summarize_wrap_bounds(self.med, self.large, self.wraps, dict(self.wraps))
        med = result["per_pack"]["screen-med"]["cut_tuples_by_texture_wrap_pair"]["clamp_to_edge__clamp_to_edge"]
        large = result["per_pack"]["screen-xlarge"]["cut_tuples_by_texture_wrap_pair"]["clamp_to_edge__clamp_to_edge"]
        self.assertEqual(med["outside_allocated"], 1)
        self.assertEqual(med["invalid_rectangle"], 1)
        self.assertEqual(large["fits_allocated_only"], 1)
        self.assertEqual(large["outside_allocated"], 1)
        self.assertFalse(result["per_pack"]["screen-med"]["outside_allocated_tuples_use_repeat_on_any_axis"])
        self.assertTrue(result["per_pack"]["screen-med"]["outside_allocated_tuples_use_clamp_to_edge_on_both_axes"])
        self.assertNotIn("synthetic-A", json.dumps(result))

    def test_repeat_pair_is_reported_separately(self):
        wraps = dict(self.wraps)
        wraps[("synthetic-B", 0)] = (1, 1)
        result = summarize_wrap_bounds(self.med, self.large, wraps, dict(wraps))
        group = result["per_pack"]["screen-med"]["cut_tuples_by_texture_wrap_pair"]["repeat__repeat"]
        self.assertEqual(group["outside_allocated"], 1)
        self.assertTrue(result["per_pack"]["screen-med"]["outside_allocated_tuples_use_repeat_on_any_axis"])
        self.assertFalse(result["per_pack"]["screen-med"]["outside_allocated_tuples_use_clamp_to_edge_on_both_axes"])

    def test_unknown_wrap_codes_remain_unknown(self):
        wraps = dict(self.wraps)
        wraps[("synthetic-B", 0)] = (9, 0)
        result = summarize_wrap_bounds(self.med, self.large, wraps, dict(wraps))
        self.assertIn("unrecognized__clamp_to_edge",
                      result["per_pack"]["screen-med"]["cut_tuples_by_texture_wrap_pair"])

    def test_mismatched_paired_cut_identity_fails_closed(self):
        with self.assertRaisesRegex(SpriteCutWrapAuditError, "do not match"):
            summarize_wrap_bounds(self.med, {("other", 0): self.med[("synthetic-A", 0)],
                                             ("synthetic-B", 0): self.med[("synthetic-B", 0)],
                                             ("synthetic-C", 0): self.med[("synthetic-C", 0)]},
                                  self.wraps, self.wraps)

    def test_resolution_specific_wrap_change_fails_closed(self):
        changed = dict(self.wraps)
        changed[("synthetic-A", 0)] = (1, 1)
        with self.assertRaisesRegex(SpriteCutWrapAuditError, "differ"):
            summarize_wrap_bounds(self.med, self.large, self.wraps, changed)


class SyntheticIpaWrapAuditTests(unittest.TestCase):
    def test_complete_fake_ipa_finds_outside_cut_on_clamp_wrap(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "synthetic.ipa"
            _synthetic_ipa(path, wrap_s=0, wrap_t=0, xlarge_rect=(31, 0, 2, 1))
            report = audit_private_wrap_bounds(path)
        large = report["per_pack"]["screen-xlarge"]
        clamp = large["cut_tuples_by_texture_wrap_pair"]["clamp_to_edge__clamp_to_edge"]
        self.assertEqual(clamp["outside_allocated"], 1)
        self.assertFalse(large["outside_allocated_tuples_use_repeat_on_any_axis"])
        self.assertTrue(large["outside_allocated_tuples_use_clamp_to_edge_on_both_axes"])
        self.assertNotIn("fakeCut", json.dumps(report))

    def test_complete_fake_ipa_preserves_repeat_mode(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "synthetic.ipa"
            _synthetic_ipa(path, wrap_s=1, wrap_t=1, xlarge_rect=(31, 0, 2, 1))
            report = audit_private_wrap_bounds(path)
        large = report["per_pack"]["screen-xlarge"]
        self.assertEqual(
            large["cut_tuples_by_texture_wrap_pair"]["repeat__repeat"]["outside_allocated"], 1
        )
        self.assertTrue(large["outside_allocated_tuples_use_repeat_on_any_axis"])

    def test_inconsistent_wrap_settings_between_packs_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "synthetic.ipa"
            _synthetic_ipa(path, wrap_s=0, wrap_t=0, xlarge_wrap_s=1)
            with self.assertRaisesRegex(SpriteCutWrapAuditError, "differ between resolution packs"):
                audit_private_wrap_bounds(path)

    def test_missing_png_fails_closed_before_wrap_report(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "synthetic.ipa"
            _synthetic_ipa(path, omit_png=True)
            with self.assertRaises(SpriteCutBoundsError):
                audit_private_wrap_bounds(path)


if __name__ == "__main__":
    unittest.main()
