"""Stage262 regression tests: only fictional ARMv7 Mach-O and synthetic calls."""
from __future__ import annotations

import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from heman_tools.thumb_bl_call_census import (
    decode_thumb_bl,
    inspect_private_ipa_thumb_calls,
    main,
    summarize_thumb_bl_references,
)
from test_ios_launch_preflight import write_fixture


def encode_thumb_bl(source: int, target: int) -> bytes:
    displacement = target - (source + 4)
    if displacement & 1 or not -(1 << 24) <= displacement < (1 << 24):
        raise ValueError("synthetic displacement outside Thumb BL range")
    bits = displacement & ((1 << 25) - 1)
    sign = (bits >> 24) & 1
    i1 = (bits >> 23) & 1
    i2 = (bits >> 22) & 1
    j1 = 1 - (i1 ^ sign)
    j2 = 1 - (i2 ^ sign)
    first = 0xF000 | (sign << 10) | ((bits >> 12) & 0x3FF)
    second = 0xD000 | (j1 << 13) | (j2 << 11) | ((bits >> 1) & 0x7FF)
    return struct.pack("<HH", first, second)


def fake_macho(*, extra_unknown=False, missing_anchor=False, corrupt_text=False):
    # The names and instruction bytes are wholly synthetic, never sourced
    # from the original game's executable or its stored asset names.
    symbols = [
        ("__ZN15BodyOwnerHelper22createB2ShapeFromShapeEPKN4helo7Shape2DE", 0x00),
        ("__ZN22EntityCollisionManager18onAABBIntersectionEPN4helo4AABBES2_", 0x20),
        ("__ZN12CWorldEntity17getCollisionShapeERN4helo4AABBE", 0x40),
        ("__ZN4Tile17getCollisionShapeEv", 0x60),
        ("__ZN4helo7Shape2D10customLoadEP12_helo_file_t", 0x80),
        ("__ZNK4helo7Shape2D8getVertsEv", 0xA0),
        ("__ZN14b2PolygonShape3SetEPK6b2Vec2i", 0xC0),
        ("__ZN4helo12GoGameObject22sendMessageImmediatelyEPNS_5GoMsgEPv", 0xE0),
        ("__Z18helo_file_read_f32P12_helo_file_t", 0x100),
    ]
    if missing_anchor:
        symbols = [s for s in symbols if "CWorldEntity" not in s[0]]
    string_table = bytearray(b"\x00")
    nlist = []
    for name, rel in symbols:
        offset = len(string_table)
        string_table.extend(name.encode("ascii") + b"\x00")
        nlist.append(struct.pack("<IBBHI", offset, 0x0F, 1, 8, 0x1000 + rel))
    text = bytearray(0x140)
    calls = [
        (0x00, 0xA0),
        (0x04, 0xC0),
        (0x20, 0xE0),
        (0x40, 0xA0),
        (0x80, 0x100),
    ]
    if extra_unknown:
        calls.append((0x84, 0x20E0))
    for relative_source, relative_target in calls:
        text[relative_source:relative_source + 4] = encode_thumb_bl(
            0x1000 + relative_source, 0x1000 + relative_target
        )
    version = struct.pack("<IIII", 0x25, 16, 0x00040300, 0x00060100)
    segment_size = 56 + 68
    command_size = len(version) + segment_size + 24
    text_file_offset = 28 + command_size
    symoff = text_file_offset + len(text)
    stroff = symoff + len(nlist) * 12
    total_file_size = stroff + len(string_table)
    segment = struct.pack(
        "<II16sIIIIIIII", 1, segment_size, b"__TEXT",
        0x1000, 0x2000, 0, total_file_size, 7, 5, 1, 0,
    )
    section = struct.pack(
        "<16s16sIIIIIIIII",
        b"__text", b"__TEXT", 0x1000, len(text),
        text_file_offset if not corrupt_text else total_file_size + 1,
        2, 0, 0, 0, 0, 0,
    )
    symtab = struct.pack("<IIIIII", 2, 24, symoff, len(nlist),
                         stroff, len(string_table))
    header = struct.pack("<IiiIIII", 0xfeedface, 12, 9, 2, 3, command_size, 0)
    return (header + version + segment + section + symtab
            + text + b"".join(nlist) + bytes(string_table))


class ThumbBLCallCensusTests(unittest.TestCase):
    def test_thumb_bl_forward_and_backward_encoding(self):
        for source, dest in (
            (0x1000, 0x1100), (0x1200, 0x1080),
            (0x1f000, 0x3000), (0x4000, 0x4004)
        ):
            first, second = struct.unpack("<HH", encode_thumb_bl(source, dest))
            self.assertEqual(decode_thumb_bl(first, second, source), dest)
        self.assertIsNone(decode_thumb_bl(0xBF00, 0xBF00, 0x1000))
        # BLX differs at bit 12; do not classify as Thumb BL.
        first, second = struct.unpack("<HH", encode_thumb_bl(0x1000, 0x2000))
        self.assertIsNone(decode_thumb_bl(first, second & ~0x1000, 0x1000))

    def test_selected_static_targets_and_redaction(self):
        report = summarize_thumb_bl_references(fake_macho())
        self.assertEqual(report["selected_anchor_count"], 5)
        self.assertEqual(report["selected_anchor_thumb_bl_candidate_sites"], 5)
        self.assertEqual(report["selected_anchor_exact_defined_target_sites"], 5)
        anchors = {a["anchor"]: a for a in report["selected_anchors"]}
        bridge = anchors["shape_to_physics_bridge"]
        self.assertEqual(bridge["thumb_bl_candidate_sites"], 2)
        self.assertEqual(bridge["resolved_target_groups"]["shape2d_api"], 1)
        self.assertEqual(bridge["resolved_target_groups"]["physics_shape_api"], 1)
        self.assertEqual(
            anchors["collision_event_handler"]["resolved_target_groups"]["game_message_api"], 1
        )
        self.assertEqual(anchors["tile_shape_query"]["thumb_bl_candidate_sites"], 0)
        self.assertEqual(
            anchors["shape_resource_loader"]["resolved_target_groups"]["resource_read_api"], 1
        )
        self.assertTrue(report["original_shape2d_to_physics_bridge_static_evidence"])
        self.assertFalse(report["original_runtime_resource_binding_verified"])
        self.assertFalse(report["native_switch_collision_import_authorized"])
        serialized = json.dumps(report)
        for raw in ("BodyOwnerHelper", "b2PolygonShape", "sendMessageImmediately",
                    "Shape2D10customLoad", "0x1000"):
            self.assertNotIn(raw, serialized)

    def test_nonexact_target_is_reported_not_assigned(self):
        report = summarize_thumb_bl_references(fake_macho(extra_unknown=True))
        self.assertEqual(report["selected_anchor_thumb_bl_candidate_sites"], 6)
        self.assertEqual(report["selected_anchor_exact_defined_target_sites"], 5)
        loader = next(a for a in report["selected_anchors"]
                      if a["anchor"] == "shape_resource_loader")
        self.assertEqual(loader["unresolved_or_nonexact_site_count"], 1)

    def test_missing_anchor_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "one defined text symbol"):
            summarize_thumb_bl_references(fake_macho(missing_anchor=True))

    def test_broken_text_range_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "text section exceeds bounds"):
            summarize_thumb_bl_references(fake_macho(corrupt_text=True))

    def test_not_macho_fails_closed(self):
        with self.assertRaises(ValueError):
            summarize_thumb_bl_references(bytes(300))

    def test_fake_ipa_read_only(self):
        with TemporaryDirectory() as folder:
            ipa = Path(folder) / "fabricated.ipa"
            write_fixture(ipa, binary=fake_macho())
            report = inspect_private_ipa_thumb_calls(ipa)
        self.assertEqual(report["selected_anchor_exact_defined_target_sites"], 5)
        self.assertFalse(report["private_source"]["executable_extracted_to_disk"])
        self.assertNotIn("BodyOwnerHelper", json.dumps(report))

    def test_cli_private_report(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "local_reports").mkdir()
            ipa = root / "fabricated.ipa"
            write_fixture(ipa, binary=fake_macho())
            out = root / "local_reports" / "thumb-bl-census.json"
            with patch("heman_tools.collision_inventory.Path.cwd", return_value=root):
                self.assertEqual(main(["--ipa", str(ipa), "--out", str(out)]), 0)
            report = json.loads(out.read_text(encoding="utf-8"))
            self.assertTrue(report["static_instruction_candidate_not_verified_control_flow"])
            self.assertFalse(report["original_collision_alpha_usage_verified"])


if __name__ == "__main__":
    unittest.main()
