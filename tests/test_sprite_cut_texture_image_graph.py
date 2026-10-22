"""Stage185: synthetic-only resource graph and path-resolution regressions."""
from __future__ import annotations

import json
import struct
import unittest

from heman_tools import sprite_cut_texture_image_graph as graph

SCREENS = ("screen-med", "screen-xlarge")
PNG_HEADER = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", 16, 16)


def name(value):
    encoded = value.encode("utf-16le")
    return struct.pack("<H", len(encoded) // 2) + encoded


def indexed_repo(label, rows, target):
    out = bytearray(name(label) + struct.pack("<HI", 0, len(rows)))
    for key, offset in rows:
        out += name(key) + struct.pack("<I", 0) + name(target) + struct.pack("<I", offset)
    return bytes(out)


def image_repo(rows):
    out = bytearray(name("ImageData") + struct.pack("<HI", 0, len(rows)))
    for key, path in rows:
        out += name(key) + struct.pack("<I", 1) + name(path) + struct.pack("<I", 0)
    return bytes(out)


def sequence_record(symbol="SyntheticCut"):
    out = bytearray(name("SyntheticSequence") + struct.pack("<iii", 0, 1, 0))
    out += struct.pack("<iiii", 0, 10, 0, 0) + b"\x00" + struct.pack("<i", 1)
    out += struct.pack("<ii", 0, 0) + name(symbol)
    out += struct.pack("<4i", 0, 0, 0, 0) + struct.pack("<6f", 0, 0, 0, 0, 0, 0)
    out += struct.pack("<7i", 0, 0, 0, 0, 0, 0, 0)
    return bytes(out)


def cut_record(texture="SyntheticTexture", tuple_index=0, trailing=b"", xywh=(0, 0, 16, 16)):
    return (name("SyntheticCut") + name(texture) + struct.pack("<I", 1)
            + struct.pack("<iiiii", tuple_index, *xywh) + trailing)


def texture_record(image="SyntheticImage", trailing=b""):
    return name("SyntheticTexture") + bytes([1]) + bytes(14) + name(image) + trailing


def fixture(symbol="SyntheticCut", cut_texture="SyntheticTexture", texture_image="SyntheticImage",
            paths=(("SyntheticImage", "/textures/synthetic.png"),), member_headers=None):
    seq = sequence_record(symbol)
    cut = cut_record(cut_texture)
    tex = texture_record(texture_image)
    repos = {
        "seq": indexed_repo("SpriteSeqData", [("SyntheticSequence", 0)], "sprite/SpriteSeqData.wad"),
        "cut": indexed_repo("SpriteCutData", [("SyntheticCut", 0)], "sprite/SpriteResData.wad"),
        "tex": indexed_repo("TextureData", [("SyntheticTexture", 0)], "textureData/TextureData.wad"),
        "img": image_repo(paths),
    }
    default_headers = {
        f"Payload/MOTU.app/{screen}/textures/synthetic.png": PNG_HEADER for screen in SCREENS
    }
    if member_headers is not None:
        default_headers = member_headers
    args = (
        {s: repos["seq"] for s in SCREENS}, {s: seq for s in SCREENS},
        {s: repos["cut"] for s in SCREENS}, {s: cut for s in SCREENS},
        {s: repos["tex"] for s in SCREENS}, {s: tex for s in SCREENS},
        {s: repos["img"] for s in SCREENS},
        {s: {k: v for k, v in default_headers.items() if f"/{s}/" in k} for s in SCREENS},
    )
    return args


class SpriteResourceGraphTests(unittest.TestCase):
    def test_complete_graph_counts_and_redacts_identifiers(self):
        report = graph.summarize_sprite_cut_texture_image_graph(*fixture())
        med = report["per_resolution_pack"]["screen-med"]
        self.assertEqual(med["sequence_records"], 1)
        self.assertEqual(med["symbol_references_matching_cut_index"], 1)
        self.assertEqual(med["cut_to_texture_links"], 1)
        self.assertEqual(med["texture_to_image_links"], 1)
        self.assertEqual(med["unique_png_members_verified"], 1)
        self.assertNotIn("Synthetic", json.dumps(report))
        self.assertNotIn("/textures/", json.dumps(report))

    def test_unindexed_symbol_is_counted_not_rejected(self):
        report = graph.summarize_sprite_cut_texture_image_graph(*fixture(symbol="UnindexedSymbol"))
        med = report["per_resolution_pack"]["screen-med"]
        self.assertEqual(med["symbol_references_matching_cut_index"], 0)
        self.assertEqual(med["symbol_references_without_cut_index_match"], 1)

    def test_missing_cut_texture_link_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing TextureData key"):
            graph.summarize_sprite_cut_texture_image_graph(*fixture(cut_texture="MissingTexture"))

    def test_missing_texture_image_link_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing ImageData key"):
            graph.summarize_sprite_cut_texture_image_graph(*fixture(texture_image="MissingImage"))

    def test_cut_tuple_count_requires_exact_eof(self):
        with self.assertRaisesRegex(ValueError, "tuple count does not match"):
            graph.parse_sprite_cut_record(cut_record(trailing=b"\x00"))

    def test_cut_handle_must_match_zero_based_position(self):
        with self.assertRaisesRegex(ValueError, "zero-based position"):
            graph.parse_sprite_cut_record(cut_record(tuple_index=1))

    def test_texture_record_requires_exact_eof(self):
        with self.assertRaisesRegex(ValueError, "trailing bytes"):
            graph.parse_texture_data_record(texture_record(trailing=b"\x00"))

    def test_texture_record_requires_empty_auxiliary_string(self):
        malformed = name("SyntheticTexture") + bytes([1]) + bytes(12) + name("not-empty") + name("SyntheticImage")
        with self.assertRaisesRegex(ValueError, "auxiliary string is not empty"):
            graph.parse_texture_data_record(malformed)

    def test_cut_xywh_fields_are_signed(self):
        record = cut_record(xywh=(12, -256, 214, 512))
        key, texture, tuples = graph.parse_sprite_cut_record(record)
        self.assertEqual(tuples, ((0, 12, -256, 214, 512),))

    def test_case_only_image_path_aliases_resolve_to_one_png(self):
        args = list(fixture(paths=(
            ("SyntheticImage", "/textures/synthetic.png"),
            ("SyntheticAlias", "/textures/Synthetic.png"),
        )))
        report = graph.summarize_sprite_cut_texture_image_graph(*args)
        med = report["per_resolution_pack"]["screen-med"]
        self.assertEqual(med["image_data_entries"], 2)
        self.assertEqual(med["unique_png_members_verified"], 1)
        self.assertEqual(med["casefold_alias_groups"], 1)
        self.assertEqual(med["casefold_alias_extra_entries"], 1)
        self.assertEqual(med["casefold_only_path_entries"], 1)

    def test_missing_image_path_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "does not resolve"):
            graph.summarize_sprite_cut_texture_image_graph(
                *fixture(paths=(("SyntheticImage", "/textures/missing.png"),)))

    def test_invalid_png_header_is_rejected(self):
        headers = {}
        for screen in SCREENS:
            headers[f"Payload/MOTU.app/{screen}/textures/synthetic.png"] = b"not a png header"
        with self.assertRaisesRegex(ValueError, "not a valid PNG header"):
            graph.summarize_sprite_cut_texture_image_graph(*fixture(member_headers=headers))

    def test_casefold_duplicate_archive_members_are_rejected(self):
        headers = {}
        for screen in SCREENS:
            headers[f"Payload/MOTU.app/{screen}/textures/synthetic.png"] = PNG_HEADER
            headers[f"Payload/MOTU.app/{screen}/textures/Synthetic.png"] = PNG_HEADER
        with self.assertRaisesRegex(ValueError, "Ambiguous case-insensitive"):
            graph.summarize_sprite_cut_texture_image_graph(*fixture(member_headers=headers))

    def test_image_repository_rejects_parent_traversal(self):
        with self.assertRaisesRegex(ValueError, "Invalid ImageData entry"):
            graph.parse_image_repository(image_repo((("SyntheticImage", "/textures/../escape.png"),)))

    def test_paired_symbol_references_must_match(self):
        args = list(fixture())
        seq_wads = dict(args[1])
        seq_wads["screen-xlarge"] = sequence_record("DifferentSymbol")
        args[1] = seq_wads
        with self.assertRaisesRegex(ValueError, "Paired symbol references differ"):
            graph.summarize_sprite_cut_texture_image_graph(*args)


if __name__ == "__main__":
    unittest.main()
