"""Artificial ZIP fixtures only; never uses original iOS game data in CI."""
from __future__ import annotations

import stat
import struct
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path

from heman_tools.first_level_pair_audit import compare_pair


class FirstLevelPairAuditTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "fake.ipa"
        base = "Payload/MOTU.app/"
        self.files = {
            base + screen + "/levels/MULevel1-1.lvl":
                struct.pack("<I", 1) + b"synthetic-level"
            for screen in ("screen-med", "screen-xlarge")
        }
        self.files.update({
            base + screen + "/maps/MUMap1-1.map":
                struct.pack("<I", 3) + b"synthetic-map"
            for screen in ("screen-med", "screen-xlarge")
        })

    def create_zip(self, resources=None):
        with zipfile.ZipFile(self.path, "w") as archive:
            for name, data in (self.files if resources is None else resources).items():
                archive.writestr(name, data)

    def test_matching_pairs_and_unverified_collision(self):
        self.create_zip()
        result = compare_pair(self.path)
        self.assertTrue(result["cross_pack_bytes_identical"])
        self.assertEqual(result["selected_pairs"]["level"]["bytes_per_screen"]["screen-med"],
                         len(struct.pack("<I", 1) + b"synthetic-level"))
        self.assertTrue(result["selected_pairs"]["map"]["standard_header_observed"])
        for key in ("level_to_map_binding_verified", "collision_type_verified",
                    "original_gameplay_trace_verified",
                    "automatic_collision_export_permitted"):
            self.assertIs(result[key], False)
        self.assertNotIn("synthetic-map", str(result))

    def test_changed_map_pair_is_reported(self):
        files = dict(self.files)
        key = "Payload/MOTU.app/screen-xlarge/maps/MUMap1-1.map"
        files[key] += b"change"
        self.create_zip(files)
        result = compare_pair(self.path)
        self.assertFalse(result["cross_pack_bytes_identical"])
        self.assertTrue(result["selected_pairs"]["level"]["exact_bytes_equal"])
        self.assertFalse(result["selected_pairs"]["map"]["exact_bytes_equal"])

    def test_changed_level_pair_is_reported(self):
        files = dict(self.files)
        files["Payload/MOTU.app/screen-med/levels/MULevel1-1.lvl"] += b"change"
        self.create_zip(files)
        self.assertFalse(compare_pair(self.path)["selected_pairs"]["level"]["exact_bytes_equal"])

    def test_missing_map_rejected(self):
        files = dict(self.files)
        del files["Payload/MOTU.app/screen-med/maps/MUMap1-1.map"]
        self.create_zip(files)
        with self.assertRaisesRegex(ValueError, "missing"):
            compare_pair(self.path)

    def test_invalid_resource_paths_rejected(self):
        self.create_zip()
        for filename in ("../MULevel1-1.lvl", "sub/MULevel1-1.lvl",
                         "MULevel1-1.lvl\\other", "elsewhere.png"):
            with self.subTest(filename=filename), self.assertRaises(ValueError):
                compare_pair(self.path, level=filename)

    def test_duplicate_zip_entry_rejected(self):
        self.create_zip()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(self.path, "a") as archive:
                archive.writestr("Payload/MOTU.app/screen-med/maps/MUMap1-1.map", b"x")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            compare_pair(self.path)

    def test_selected_symlink_rejected(self):
        path = "Payload/MOTU.app/screen-med/maps/MUMap1-1.map"
        with zipfile.ZipFile(self.path, "w") as archive:
            for name, data in self.files.items():
                if name == path:
                    link = zipfile.ZipInfo(name)
                    link.create_system = 3
                    link.external_attr = (stat.S_IFLNK | 0o777) << 16
                    archive.writestr(link, b"fake-target")
                else:
                    archive.writestr(name, data)
        with self.assertRaises(ValueError):
            compare_pair(self.path)

    def test_nonstandard_header_remains_unverified(self):
        files = dict(self.files)
        for screen in ("screen-med", "screen-xlarge"):
            files[f"Payload/MOTU.app/{screen}/maps/MUMap1-1.map"] = (
                struct.pack("<I", 255) + b"fake-map")
        self.create_zip(files)
        result = compare_pair(self.path)
        self.assertTrue(result["selected_pairs"]["map"]["exact_bytes_equal"])
        self.assertFalse(result["selected_pairs"]["map"]["standard_header_observed"])

    def test_invalid_archive_rejected(self):
        self.path.write_bytes(b"fabricated nonzip")
        with self.assertRaises(ValueError):
            compare_pair(self.path)

    def test_invalid_map_filename_rejected(self):
        self.create_zip()
        with self.assertRaises(ValueError):
            compare_pair(self.path, map_name="other.zip")


if __name__ == "__main__":
    unittest.main()
