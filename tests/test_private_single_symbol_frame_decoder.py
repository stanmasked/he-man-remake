"""Synthetic-only tests for the Stage189 private single-symbol crop decoder."""
from __future__ import annotations

import io
import struct
import unittest

from PIL import Image

from heman_tools.private_single_symbol_frame_decoder import (
    PrivateFrameDecodeError,
    crop_png_bytes,
    parse_single_symbol_frame,
    resolve_alias_pair,
    select_cut_rectangle,
    parse_symbol_frame,
    _assemble_private_symbol_packet_summary,
    _assemble_private_symbol_frame_packet_summary,
)


def field(value: str) -> bytes:
    encoded = value.encode("utf-16le")
    return len(value).to_bytes(2, "little") + encoded


def sequence_record(symbols, frame_time=100):
    out = bytearray(field("SyntheticSequence") + struct.pack("<iii", 0, 1, 0))
    out += struct.pack("<4i", 0, frame_time, 0, 0) + b"\x00" + struct.pack("<i", len(symbols))
    for name, handle in symbols:
        out += struct.pack("<ii", 0, 0) + field(name)
        out += struct.pack("<4i", handle, 0, 0, 0)
        out += struct.pack("<6f", 1, 1, 1, 1, 1, 1)
        out += struct.pack("<7i", 0, 0, 0, 0, 0, 0, 0)
    return bytes(out)


def cut_record(name, texture, tuples):
    out = bytearray(field(name) + field(texture) + struct.pack("<I", len(tuples)))
    for item in tuples:
        out += struct.pack("<iiiii", *item)
    return bytes(out)


def png_bytes(size=(8, 8)):
    image = Image.new("RGBA", size, (12, 34, 56, 255))
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


class PrivateSingleSymbolFrameDecoderTests(unittest.TestCase):
    def test_multi_symbol_parser_preserves_every_symbol_in_source_order(self):
        record = sequence_record((("SyntheticCutA", 7), ("SyntheticCutB", 8),
                                  ("SyntheticCutC", 9)))
        parsed = parse_symbol_frame(record, 0)
        self.assertEqual(parsed["symbol_count"], 3)
        self.assertEqual([item["name"] for item in parsed["symbols"]],
                         ["SyntheticCutA", "SyntheticCutB", "SyntheticCutC"])
        self.assertEqual([item["cut_handle"] for item in parsed["symbols"]], [7, 8, 9])
        self.assertEqual(parsed["frame_index"], 0)

    def test_multi_symbol_packet_summary_preserves_order_and_mask_skips(self):
        symbols = (
            {"name": "SyntheticA", "serialized_fields": (7, 0, 10, 20),
             "transform_values": (1, 1, 1, 1, 1, 1),
             "serialized_tail": (0, 0, 0, 0, -1, -1, 0)},
            {"name": "SyntheticB", "serialized_fields": (8, 0, 30, 40),
             "transform_values": (1, 1, 1, 1, 1, 1),
             "serialized_tail": (0, 0, 0, 0, -1, -1, 0)},
            {"name": "SyntheticC", "serialized_fields": (9, 0, 50, 60),
             "transform_values": (1, 1, 1, 1, 1, 1),
             "serialized_tail": (0, 0, 0, 0, -1, -1, 4)},
        )
        report = _assemble_private_symbol_frame_packet_summary(
            symbols,
            ((0, 0, 8, 4), (2, 1, 4, 2), (1, 2, 3, 3)),
            ((16, 16), (16, 16), (16, 16)),
            ((0, 0), (0, 0), (0, 0)),
            active_mask=4,
        )
        self.assertEqual(report["frame_symbol_count"], 3)
        self.assertEqual(report["cpu_frame_packet_count"], 2)
        self.assertEqual(report["cpu_frame_packet_vertex_count"], 8)
        self.assertEqual(report["cpu_frame_packet_uv_pair_count"], 8)
        self.assertEqual(report["cpu_frame_packet_color_channel_count"], 8)
        self.assertEqual(report["masked_symbol_count"], 1)
        self.assertTrue(report["cpu_frame_packet_source_order_preserved"])
        self.assertTrue(report["cpu_frame_packet_finite"])
        self.assertFalse(report["full_frame_composition_verified"])
        self.assertNotIn("SyntheticA", str(report))

    def test_multi_symbol_packet_summary_fails_closed_on_late_unsupported_tween(self):
        good = {"name": "SyntheticA", "serialized_fields": (7, 0, 0, 0),
                "transform_values": (1, 1, 1, 1, 1, 1),
                "serialized_tail": (0, 0, 0, 0, -1, -1, 0)}
        bad = {"name": "SyntheticB", "serialized_fields": (8, 0, 0, 0),
               "transform_values": (1, 1, 1, 1, 1, 1),
               "serialized_tail": (99, 0, 0, 0, -1, -1, 0)}
        with self.assertRaisesRegex(PrivateFrameDecodeError, "without guessing"):
            _assemble_private_symbol_frame_packet_summary(
                (good, bad), ((0, 0, 8, 4), (0, 0, 8, 4)),
                ((16, 16), (16, 16)), ((0, 0), (0, 0)), active_mask=0,
            )

    def test_multi_symbol_packet_summary_requires_parallel_metadata(self):
        symbol = {"name": "SyntheticA", "serialized_fields": (7, 0, 0, 0),
                  "transform_values": (1, 1, 1, 1, 1, 1),
                  "serialized_tail": (0, 0, 0, 0, -1, -1, 0)}
        with self.assertRaisesRegex(PrivateFrameDecodeError, "parallel every Symbol"):
            _assemble_private_symbol_frame_packet_summary(
                (symbol, symbol), ((0, 0, 8, 4),),
                ((16, 16), (16, 16)), ((0, 0), (0, 0)), active_mask=0,
            )

    def test_sequence_frame_resolves_single_symbol_and_handle(self):
        parsed = parse_single_symbol_frame(sequence_record((("SyntheticCut", 7),)), 0)
        self.assertEqual(parsed["symbol_count"], 1)
        self.assertEqual(parsed["symbols"][0]["name"], "SyntheticCut")
        self.assertEqual(parsed["symbols"][0]["cut_handle"], 7)
        self.assertTrue(all(v == 1.0 for v in parsed["symbols"][0]["transform_values"]))

    def test_parser_retains_exact_serialized_symbol_fields_for_private_assembly(self):
        parsed = parse_single_symbol_frame(sequence_record((("SyntheticCut", 7),)), 0)
        symbol = parsed["symbols"][0]
        self.assertEqual(symbol["serialized_fields"], (7, 0, 0, 0))
        self.assertEqual(symbol["serialized_tail"], (0, 0, 0, 0, 0, 0, 0))

    def test_private_packet_summary_contains_only_aggregate_evidence(self):
        symbol = {
            "name": "SyntheticCut",
            "cut_handle": 7,
            "serialized_fields": (7, 0, -3, -5),
            "transform_values": (1.0, 1.0, 1.0, 1.0, 1.0, 1.0),
            "serialized_tail": (1, 1, 1, 1, -1, -1, 0),
        }
        report = _assemble_private_symbol_packet_summary(
            symbol, (0, 0, 8, 4), (16, 16), (0, 0)
        )
        self.assertTrue(report["cpu_frame_packet_assembled"])
        self.assertEqual(report["cpu_frame_packet_count"], 1)
        self.assertEqual(report["cpu_frame_packet_vertex_count"], 4)
        self.assertEqual(report["cpu_frame_packet_uv_pair_count"], 4)
        self.assertTrue(report["cpu_frame_packet_source_order_preserved"])
        self.assertTrue(report["cpu_frame_packet_finite"])
        self.assertFalse(report["full_frame_composition_verified"])
        self.assertFalse(report["original_runtime_pixel_parity_verified"])
        self.assertNotIn("SyntheticCut", str(report))

    def test_private_packet_summary_rejects_unsupported_tween_without_guessing(self):
        symbol = {
            "name": "SyntheticCut",
            "cut_handle": 7,
            "serialized_fields": (7, 0, 0, 0),
            "transform_values": (1.0, 1.0, 1.0, 1.0, 1.0, 1.0),
            "serialized_tail": (99, 1, 1, 1, -1, -1, 0),
        }
        with self.assertRaisesRegex(PrivateFrameDecodeError, "without guessing"):
            _assemble_private_symbol_packet_summary(
                symbol, (0, 0, 8, 4), (16, 16), (0, 0)
            )

    def test_out_of_range_frame_fails_closed(self):
        with self.assertRaisesRegex(PrivateFrameDecodeError, "outside the sequence"):
            parse_single_symbol_frame(sequence_record((("SyntheticCut", 0),)), 1)

    def test_multi_symbol_frame_is_not_misrendered_as_single_crop(self):
        record = sequence_record((("SyntheticCutA", 0), ("SyntheticCutB", 1)))
        with self.assertRaisesRegex(PrivateFrameDecodeError, "single-symbol frame"):
            parse_single_symbol_frame(record, 0)

    def test_alias_pair_requires_exact_east_west_resources(self):
        data = field("syntheticIdle") + field("synthetic.idle.e") + field("synthetic.idle.w")
        pair = resolve_alias_pair(data, {"synthetic.idle.e", "synthetic.idle.w"},
                                  (0, len(data)), "syntheticIdle")
        self.assertEqual(pair, ("synthetic.idle.e", "synthetic.idle.w"))

    def test_ambiguous_alias_pair_fails_closed(self):
        data = (field("syntheticIdle") + field("one.e") + field("one.w")
                + field("syntheticIdle") + field("two.e") + field("two.w"))
        with self.assertRaisesRegex(PrivateFrameDecodeError, "missing or ambiguous"):
            resolve_alias_pair(data, {"one.e", "one.w", "two.e", "two.w"},
                               (0, len(data)), "syntheticIdle")

    def test_missing_alias_fails_closed(self):
        data = field("syntheticOther") + field("other.e") + field("other.w")
        with self.assertRaisesRegex(PrivateFrameDecodeError, "missing or ambiguous"):
            resolve_alias_pair(data, {"other.e", "other.w"}, (0, len(data)), "syntheticIdle")

    def test_cut_handle_selects_exact_rectangle(self):
        raw = cut_record("SyntheticCut", "SyntheticTexture",
                         ((0, 1, 2, 3, 4), (1, 2, 1, 4, 5)))
        texture, rect = select_cut_rectangle(raw, "SyntheticCut", "SyntheticCut", 1)
        self.assertEqual(texture, "SyntheticTexture")
        self.assertEqual(rect, (2, 1, 4, 5))

    def test_missing_cut_handle_fails_closed(self):
        raw = cut_record("SyntheticCut", "SyntheticTexture", ((0, 1, 2, 3, 4),))
        with self.assertRaisesRegex(PrivateFrameDecodeError, "missing or ambiguous"):
            select_cut_rectangle(raw, "SyntheticCut", "SyntheticCut", 7)

    def test_duplicate_cut_handle_fails_closed(self):
        raw = cut_record("SyntheticCut", "SyntheticTexture",
                         ((7, 1, 2, 3, 4), (7, 2, 3, 4, 5)))
        # The indexed record parser also enforces handle ordinals, so malformed
        # duplicate handles are rejected before selection.
        with self.assertRaises(ValueError):
            select_cut_rectangle(raw, "SyntheticCut", "SyntheticCut", 7)

    def test_in_bounds_crop_is_written_as_png_bytes(self):
        cropped, source_size = crop_png_bytes(png_bytes(), (2, 1, 3, 4))
        self.assertEqual(source_size, (8, 8))
        with Image.open(io.BytesIO(cropped)) as image:
            self.assertEqual(image.size, (3, 4))
            self.assertEqual(image.format, "PNG")

    def test_out_of_bounds_crop_is_not_clipped(self):
        with self.assertRaisesRegex(PrivateFrameDecodeError, "exceeds PNG bounds"):
            crop_png_bytes(png_bytes(), (7, 7, 2, 2))

    def test_invalid_rectangle_fails_closed(self):
        with self.assertRaisesRegex(PrivateFrameDecodeError, "invalid dimensions"):
            crop_png_bytes(png_bytes(), (-1, 0, 2, 2))

    def test_non_png_payload_is_rejected(self):
        with self.assertRaisesRegex(PrivateFrameDecodeError, "not PNG"):
            crop_png_bytes(b"not png", (0, 0, 1, 1))


if __name__ == "__main__":
    unittest.main()
