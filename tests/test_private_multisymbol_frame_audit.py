"""Synthetic-only tests for the Stage204 multi-Symbol audit CLI helpers."""
from __future__ import annotations

import argparse
import io
import struct
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from PIL import Image

from heman_tools.physics_shape_census import PREFIX, SCREENS
from heman_tools.private_multisymbol_frame_audit import (
    _checked_png_dimensions,
    _parse_active_mask,
    _parse_region,
    _require_rectangle_in_bounds,
    audit_private_multisymbol_frame,
    main,
)
from heman_tools.private_single_symbol_frame_decoder import PrivateFrameDecodeError


def png_bytes(size=(8, 8)):
    image = Image.new("RGBA", size, (12, 34, 56, 255))
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def _string(value):
    raw = value.encode("utf-16le")
    return struct.pack("<H", len(raw) // 2) + raw


def _indexed_repo(label, rows, target):
    out = bytearray(_string(label) + struct.pack("<HI", 0, len(rows)))
    for key, offset in rows:
        out += _string(key) + struct.pack("<I", 0) + _string(target) + struct.pack("<I", offset)
    return bytes(out)


def _sequence_record(key, symbols):
    out = bytearray(_string(key) + struct.pack("<iii", 0, 1, 0))
    out += struct.pack("<4i", 0, 100, 0, 0) + b"\x00" + struct.pack("<i", len(symbols))
    for name, offset_x, mask in symbols:
        out += struct.pack("<ii", 0, 0) + _string(name)
        out += struct.pack("<4i", 0, 0, offset_x, 12)
        out += struct.pack("<6f", 1, 1, 1, 1, 1, 1)
        out += struct.pack("<7i", 0, 0, 0, 0, -1, -1, mask)
    return bytes(out)


def _cut_record(name, texture, rectangle):
    return (_string(name) + _string(texture) + struct.pack("<I", 1)
            + struct.pack("<5i", 0, *rectangle))


def _image_repo():
    return (_string("ImageData") + struct.pack("<HI", 0, 1)
            + _string("SyntheticImage") + struct.pack("<I", 1)
            + _string("/textures/synthetic.png") + struct.pack("<I", 0))


def _synthetic_multisymbol_ipa(path, *, symbols=(("SyntheticCutA", 10, 0),
                                                  ("SyntheticCutB", 30, 0)),
                               rectangles=((0, 0, 8, 8), (8, 0, 8, 8))):
    east_key, west_key = "syntheticIdle.e", "syntheticIdle.w"
    east_record = _sequence_record(east_key, symbols)
    west_record = _sequence_record(west_key, symbols)
    sequence_wad = east_record + west_record
    sequence_repo = _indexed_repo(
        "SpriteSeqData",
        ((east_key, 0), (west_key, len(east_record))),
        "sprite/SpriteSeqData.wad",
    )

    cut_records = tuple(_cut_record(name, "SyntheticTexture", rect)
                        for (name, _, _), rect in zip(symbols, rectangles))
    cut_wad = b"".join(cut_records)
    cut_offsets = []
    at = 0
    for record in cut_records:
        cut_offsets.append(at)
        at += len(record)
    cut_repo = _indexed_repo(
        "SpriteCutData",
        tuple((symbols[i][0], cut_offsets[i]) for i in range(len(symbols))),
        "sprite/SpriteResData.wad",
    )

    scalar = bytearray(13)
    scalar[10] = 0
    scalar[11] = 0
    texture_record = (_string("SyntheticTexture") + bytes(scalar)
                      + _string("") + _string("SyntheticImage"))
    texture_repo = _indexed_repo(
        "TextureData", (("SyntheticTexture", 0),), "textureData/TextureData.wad"
    )
    image_repo = _image_repo()
    go = (_string("syntheticIdle") + _string(east_key) + _string(west_key)
          + _string("syntheticOther") + _string(east_key) + _string(west_key))
    split = len(_string("syntheticIdle") + _string(east_key) + _string(west_key))
    image = png_bytes((16, 16))
    with ZipFile(path, "w") as archive:
        for screen in SCREENS:
            root = PREFIX + screen + "/"
            archive.writestr(root + "go/default", go)
            archive.writestr(root + "meta/SpriteSeqData.repo", sequence_repo)
            archive.writestr(root + "sprite/SpriteSeqData.wad", sequence_wad)
            archive.writestr(root + "meta/SpriteCutData.repo", cut_repo)
            archive.writestr(root + "sprite/SpriteResData.wad", cut_wad)
            archive.writestr(root + "meta/TextureData.repo", texture_repo)
            archive.writestr(root + "textureData/TextureData.wad", texture_record)
            archive.writestr(root + "meta/ImageData.repo", image_repo)
            archive.writestr(root + "textures/synthetic.png", image)
    return ((0, split), (split, len(go)))


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

    def test_region_and_mask_parsers_reject_malformed_text(self):
        for value in ("", "10", "a:b", "10:20:30"):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                _parse_region(value)
        for value in ("", "mask", "0xzz"):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                _parse_active_mask(value)

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

    def test_original_ipa_cli_path_resolves_and_assembles_synthetic_multisymbol_frame(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "synthetic.ipa"
            regions = _synthetic_multisymbol_ipa(ipa)
            report_path = Path.cwd() / "local_reports" / "stage204-multisymbol-integration-test.json"
            try:
                result = audit_private_multisymbol_frame(
                    ipa, regions, "syntheticIdle", 0, "east", 0, active_mask=0
                )
                self.assertEqual(result["source_symbol_count"], 2)
                self.assertEqual(result["resolved_symbol_count"], 2)
                self.assertEqual(result["cpu_frame_packet_count"], 2)
                self.assertEqual(result["cpu_frame_packet_vertex_count"], 8)
                self.assertEqual(result["cpu_frame_packet_uv_pair_count"], 8)
                self.assertTrue(result["cpu_frame_packet_source_order_preserved"])
                self.assertTrue(result["all_source_pngs_validated"])
                self.assertFalse(result["runtime_active_mask_verified"])
                self.assertFalse(result["original_runtime_pixel_parity_verified"])
                self.assertNotIn("SyntheticCut", str(result))
                self.assertNotIn("/textures/", str(result))

                self.assertEqual(main([
                    "--ipa", str(ipa),
                    "--region", f"{regions[0][0]}:{regions[0][1]}",
                    "--region", f"{regions[1][0]}:{regions[1][1]}",
                    "--alias", "syntheticIdle", "--variant", "0",
                    "--direction", "east", "--frame", "0",
                    "--active-mask", "0", "--report-out", str(report_path),
                ]), 0)
                import json
                saved = json.loads(report_path.read_text(encoding="utf-8"))
                self.assertEqual(saved["cpu_frame_packet_count"], 2)
                self.assertNotIn("SyntheticCut", json.dumps(saved))
            finally:
                report_path.unlink(missing_ok=True)

    def test_multisymbol_cli_applies_explicit_mask_without_renumbering(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "masked.ipa"
            regions = _synthetic_multisymbol_ipa(
                ipa, symbols=(("SyntheticCutA", 10, 0), ("SyntheticCutB", 30, 4))
            )
            report = audit_private_multisymbol_frame(
                ipa, regions, "syntheticIdle", 0, "west", 0, active_mask=4
            )
            self.assertEqual(report["source_symbol_count"], 2)
            self.assertEqual(report["cpu_frame_packet_count"], 1)
            self.assertEqual(report["masked_symbol_count"], 1)
            self.assertTrue(report["cpu_frame_packet_source_order_preserved"])

    def test_multisymbol_cli_rejects_out_of_bounds_late_symbol(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "out-of-bounds.ipa"
            regions = _synthetic_multisymbol_ipa(
                ipa, rectangles=((0, 0, 8, 8), (15, 15, 8, 8))
            )
            with self.assertRaises(PrivateFrameDecodeError):
                audit_private_multisymbol_frame(
                    ipa, regions, "syntheticIdle", 0, "east", 0
                )



if __name__ == "__main__":
    unittest.main()
