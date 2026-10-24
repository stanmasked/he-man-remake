"""Synthetic Mach-O string fixtures only; never original executable bytes."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from heman_tools.runtime_physics_string_census import (
    inspect_private_ipa_runtime_strings,
    main,
    summarize_runtime_strings,
)
from test_ios_launch_preflight import fake_macho, write_fixture


def fake_binary(strings=()):
    suffix = b"\x00" + b"\x00".join(s.encode("ascii") for s in strings) + b"\x00"
    return fake_macho() + suffix


class RuntimePhysicsStringCensusTests(unittest.TestCase):
    def test_candidate_groups_are_counted_without_exporting_strings(self):
        binary = fake_binary([
            "CPhysics",
            "CEntityPhysicsObject",
            "CSensor",
            "CLineSensor",
            "CStaticPlatform",
            "CInfiniteTileMapLayer",
            "PhysicsStruct2D",
            "Shape2D",
            "EntityCollisionManager",
            "CMSG_HGE_COLLISION_OCCURED",
            "CMSG_HGE_SENSOR_ENTERED",
            "CMSG_PP_AABB_COLLISION",
            "ordinary synthetic label",
            "CPhysics",
        ])
        report = summarize_runtime_strings(binary)
        self.assertEqual(report["macho"]["architecture"], "armv7")
        self.assertEqual(report["candidate_identifier_counts"]["physics_type_names"], 2)
        self.assertEqual(report["candidate_identifier_counts"]["sensor_type_names"], 2)
        self.assertEqual(report["candidate_identifier_counts"]["platform_type_names"], 1)
        self.assertEqual(report["candidate_identifier_counts"]["tilemap_type_names"], 1)
        self.assertEqual(report["candidate_identifier_counts"]["physics_format_type_names"], 2)
        self.assertEqual(report["candidate_identifier_counts"]["collision_manager_type_names"], 1)
        self.assertEqual(report["candidate_identifier_counts"]["message_identifiers"], 3)
        self.assertEqual(report["candidate_identifier_counts"]["collision_or_sensor_message_identifiers"], 3)
        serialized = json.dumps(report)
        for source_value in ("CPhysics", "CEntityPhysicsObject",
                             "CMSG_HGE_COLLISION_OCCURED", "ordinary synthetic label"):
            self.assertNotIn(source_value, serialized)
        self.assertFalse(report["static_strings_are_runtime_call_evidence"])
        self.assertFalse(report["original_collision_response_verified"])
        self.assertFalse(report["native_switch_collision_import_authorized"])

    def test_duplicate_string_values_count_once(self):
        report = summarize_runtime_strings(fake_binary([
            "CPhysics", "CPhysics", "CPhysics", "CMSG_HGE_SENSOR_ENTERED",
            "CMSG_HGE_SENSOR_ENTERED",
        ]))
        self.assertEqual(report["distinct_printable_ascii_strings"], 2)
        self.assertEqual(report["candidate_identifier_counts"]["physics_type_names"], 1)
        self.assertEqual(report["candidate_identifier_counts"]["message_identifiers"], 1)

    def test_overlong_printable_runs_are_ignored(self):
        report = summarize_runtime_strings(fake_binary(["physics" + "x" * 600]))
        self.assertEqual(report["substring_candidate_counts"]["physics"], 0)
        self.assertEqual(report["candidate_identifier_counts"]["physics_type_names"], 0)

    def test_non_macho_input_rejected(self):
        with self.assertRaisesRegex(ValueError, "Mach-O"):
            summarize_runtime_strings(b"not a Mach-O executable " + bytes(80))

    def test_synthetic_ipa_read_in_memory_and_reported_as_static_only(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "fictional.ipa"
            write_fixture(path, binary=fake_binary([
                "CPhysics", "CMSG_HGE_COLLISION_OCCURED",
                "CSensor", "PhysicsStruct2D", "Shape2D",
            ]))
            report = inspect_private_ipa_runtime_strings(path)
        self.assertEqual(report["private_source"]["executable_size_bytes"],
                         len(fake_binary([
                             "CPhysics", "CMSG_HGE_COLLISION_OCCURED",
                             "CSensor", "PhysicsStruct2D", "Shape2D",
                         ])))
        self.assertFalse(report["private_source"]["ipa_member_extracted_to_disk"])
        self.assertTrue(report["candidate_groups_present"]["physics_type_names"])
        self.assertTrue(report["candidate_groups_present"]["collision_or_sensor_message_identifiers"])
        self.assertFalse(report["original_physics_resource_binding_verified"])
        self.assertNotIn("CMSG_HGE_COLLISION_OCCURED", json.dumps(report))

    def test_symlink_ipa_rejected(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            real = root / "real.ipa"
            write_fixture(real, binary=fake_binary(["CPhysics"]))
            link = root / "linked.ipa"
            link.symlink_to(real)
            with self.assertRaisesRegex(ValueError, "non-symlink"):
                inspect_private_ipa_runtime_strings(link)

    def test_cli_writes_only_private_json_report(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "local_reports").mkdir()
            ipa = root / "fictional.ipa"
            write_fixture(ipa, binary=fake_binary(["CPhysics", "CSensor"]))
            output = root / "local_reports" / "runtime-string-census.json"
            with patch("heman_tools.collision_inventory.Path.cwd", return_value=root):
                self.assertEqual(main(["--ipa", str(ipa), "--out", str(output)]), 0)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(report["private_source"]["raw_executable_bytes_in_report"] is False)
            self.assertFalse(report["original_collision_alpha_usage_verified"])


if __name__ == "__main__":
    unittest.main()
