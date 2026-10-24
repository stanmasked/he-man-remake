"""Fabricated-only Stage263 inbound Thumb-2 call-site regression suite."""
from __future__ import annotations

import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from heman_tools.thumb_inbound_census import (
    _classify_caller, inspect_private_ipa_inbound, main,
    summarize_thumb_inbound_references,
)
from test_thumb_bl_call_census import fake_macho, encode_thumb_bl
from test_ios_launch_preflight import write_fixture


def fictional_inbound_macho():
    data = bytearray(fake_macho())
    # __TEXT,__text: virtual 0x1000, file offset 192 in fabricated fixture.
    text_offset = 28 + 16 + (56 + 68) + 24
    for source, target in (
        (0xA0, 0x00),  # synthetic shape accessor -> bridge
        (0xC0, 0x60),  # synthetic shape API -> tile query
        (0xE0, 0x60),  # synthetic dispatcher -> tile query
        (0x100, 0x20), # synthetic file reader -> collision handler
    ):
        at = text_offset + source
        data[at:at + 4] = encode_thumb_bl(0x1000 + source, 0x1000 + target)
    return bytes(data)


class InboundCensusTests(unittest.TestCase):
    def test_named_synthetic_caller_groups(self):
        self.assertEqual(
            _classify_caller(["__ZN8CTileMap19initializeCollisionEv"]),
            "tilemap_collision_initializer")
        self.assertEqual(
            _classify_caller(["__ZN12CollisionMapC2EP9TileLayerii"]),
            "collision_map_constructor")
        self.assertEqual(
            _classify_caller(["__ZN25CPlayerStateComboAttackEv"]),
            "combat_attack_related")
        self.assertEqual(
            _classify_caller(["__ZN4helo7Shape2D8getVertsEv"]),
            "shape_geometry_related")

    def test_exact_inbound_targets_only_and_redacted_output(self):
        report = summarize_thumb_inbound_references(fictional_inbound_macho())
        self.assertEqual(report["total_selected_inbound_bl_candidates"], 4)
        roles = {x["target_role"]: x for x in report["selected_targets"]}
        self.assertEqual(roles["shape_to_physics_bridge"]["candidate_bl_inbound_sites"], 1)
        self.assertEqual(roles["tile_shape_query"]["candidate_bl_inbound_sites"], 2)
        self.assertEqual(roles["collision_event_handler"]["candidate_bl_inbound_sites"], 1)
        self.assertEqual(roles["world_entity_shape_query"]["candidate_bl_inbound_sites"], 0)
        self.assertEqual(roles["shape_resource_loader"]["candidate_bl_inbound_sites"], 0)
        self.assertEqual(roles["tile_shape_query"]["distinct_nearest_named_caller_entries"], 2)
        self.assertFalse(report["tilemap_to_tile_shape_static_candidate"])
        self.assertFalse(report["original_collision_alpha_usage_verified"])
        self.assertFalse(report["native_switch_collision_import_authorized"])
        dumped = json.dumps(report)
        for text in ("CTileMap", "Shape2D8getVerts", "CollisionMapC2",
                     "0x1000", "b2PolygonShape"):
            self.assertNotIn(text, dumped)

    def test_no_fabricated_inbound_branches(self):
        report = summarize_thumb_inbound_references(fake_macho())
        self.assertEqual(report["total_selected_inbound_bl_candidates"], 0)

    def test_nonmacho_and_corrupt_section(self):
        with self.assertRaises(ValueError):
            summarize_thumb_inbound_references(bytes(300))
        with self.assertRaisesRegex(ValueError, "text section exceeds file bounds"):
            summarize_thumb_inbound_references(fake_macho(corrupt_text=True))

    def test_private_ipa_read_only(self):
        with TemporaryDirectory() as temp:
            ipa = Path(temp) / "fiction.ipa"
            write_fixture(ipa, binary=fictional_inbound_macho())
            report = inspect_private_ipa_inbound(ipa)
        self.assertEqual(report["total_selected_inbound_bl_candidates"], 4)
        self.assertFalse(report["private_source"]["source_executable_extracted"])

    def test_private_cli_report_only(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "local_reports").mkdir()
            ipa = root / "fiction.ipa"
            write_fixture(ipa, binary=fictional_inbound_macho())
            dest = root / "local_reports" / "inbound.json"
            with patch("heman_tools.collision_inventory.Path.cwd", return_value=root):
                self.assertEqual(main(["--ipa", str(ipa), "--out", str(dest)]), 0)
            report = json.loads(dest.read_text(encoding="utf-8"))
            self.assertTrue(report["static_bl_candidate_not_reachable_control_flow"])
            self.assertFalse(report["original_runtime_resource_binding_verified"])


if __name__ == "__main__":
    unittest.main()
