"""Synthetic-only Stage265 tile name-to-geometry resource linkage tests."""
from __future__ import annotations

import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import zipfile

from heman_tools.collision_geometry_name_link import (
    inspect_private_collision_geometry_names, main
)
from test_tilemap import sample, layer


def text_field(s):
    return struct.pack("<H", len(s)) + s.encode("utf-16le")


def fictional_tileset(scale):
    names = ("synth_ramp_A", "", "synth_badref", "synth_ramp_B")
    data = struct.pack("<8I", 32 * scale, 32 * scale, 32, 32,
                       0, 65535, 0, 1)
    data += text_field("img_synthetic")
    data += struct.pack("<I", len(names))
    for i, name in enumerate(names):
        data += struct.pack("<8I", i * 32 * scale, 0,
                            32 * scale, 32 * scale, i, 0, 0, 0)
        data += b"\x00" + text_field(name)
    return data


def fictional_map(shown=0):
    return sample(layer(
        "collision", w=3, h=2,
        ids=(0, 1, 65535, 3, 1, 0),
        atlas=(0, 0, 255, 0, 0, 0),
        atlases=("collision",), shown=shown
    ))


def write_zip(ipa, *, mismatch_geometry=False,
              alternate_typo=True, different_map=False):
    with zipfile.ZipFile(ipa, "w") as archive:
        for screen, scale in (("screen-med", 1), ("screen-xlarge", 2)):
            root = f"Payload/MOTU.app/{screen}/"
            archive.writestr(root + "maps/Fiction.map",
                             fictional_map(1 if different_map and scale == 2 else 0))
            archive.writestr(root + "tilesets/collision.tileset",
                             fictional_tileset(scale))
            archive.writestr(root + "geometry/synth_ramp_A.shape",
                             b"entirely fabricated geometry A")
            archive.writestr(root + "geometry/synth_ramp_B.shape",
                             b"changed on larger pack" if mismatch_geometry and scale == 2
                             else b"entirely fabricated geometry B")
            if alternate_typo:
                archive.writestr(root + "geometry/synth_badrefshape",
                                 b"near miss must not auto-resolve")


class CollisionGeometryNamesTests(unittest.TestCase):
    def test_lexical_join_reports_only_counts(self):
        with TemporaryDirectory() as tmp:
            ipa = Path(tmp) / "fiction.ipa"
            write_zip(ipa)
            report = inspect_private_collision_geometry_names(ipa, "Fiction.map")
        self.assertEqual(report["result"], "cross_screen_shape_reference_census_complete")
        expected = report["screen_med"]
        self.assertEqual(expected["tileset_records"], 4)
        self.assertEqual(expected["named_records"], 3)
        self.assertEqual(expected["named_with_exact_geometry_member"], 2)
        self.assertEqual(expected["named_without_exact_geometry_member"], 1)
        self.assertEqual(expected["missing_named_with_dot_before_extension_anomaly"], 1)
        self.assertEqual(expected["distinct_used_collision_tile_ids"], 3)
        self.assertEqual(expected["used_named_tile_ids"], 2)
        self.assertEqual(expected["used_unnamed_tile_ids"], 1)
        self.assertEqual(expected["used_named_with_exact_geometry_member"], 2)
        self.assertEqual(expected["used_named_without_exact_geometry_member"], 0)
        self.assertEqual(expected["occupied_cells_in_selected_collision_atlas"], 5)
        self.assertTrue(report["cross_screen"]["exactly_named_shape_bytes_identical"])
        self.assertTrue(report["cross_screen"]["map_bytes_exactly_equal"])
        self.assertFalse(report["native_switch_collision_import_authorized"])
        dumped = json.dumps(report)
        for val in ("synth_ramp_A", "synth_badref",
                    "geometry/synth_", "entirely fabricated"):
            self.assertNotIn(val, dumped)

    def test_same_names_but_shape_bytes_differ(self):
        with TemporaryDirectory() as tmp:
            ipa = Path(tmp) / "fiction.ipa"
            write_zip(ipa, mismatch_geometry=True)
            report = inspect_private_collision_geometry_names(ipa, "Fiction.map")
        self.assertFalse(report["cross_screen"]["exactly_named_shape_bytes_identical"])
        self.assertEqual(report["result"], "cross_screen_shape_reference_divergence")

    def test_same_occupancy_but_map_bytes_differ(self):
        with TemporaryDirectory() as tmp:
            ipa = Path(tmp) / "fiction.ipa"
            write_zip(ipa, different_map=True)
            report = inspect_private_collision_geometry_names(ipa, "Fiction.map")
        self.assertEqual(report["result"], "cross_screen_shape_reference_divergence")
        self.assertFalse(report["cross_screen"]["map_bytes_exactly_equal"])

    def test_typo_candidate_does_not_count_as_exact_match(self):
        with TemporaryDirectory() as tmp:
            ipa = Path(tmp) / "fiction.ipa"
            write_zip(ipa, alternate_typo=False)
            report = inspect_private_collision_geometry_names(ipa, "Fiction.map")
        self.assertEqual(report["screen_med"]["named_with_exact_geometry_member"], 2)
        self.assertEqual(
            report["screen_med"]["missing_named_with_dot_before_extension_anomaly"], 0
        )

    def test_malicious_map_name_rejected(self):
        with TemporaryDirectory() as tmp:
            ipa = Path(tmp) / "fiction.ipa"
            write_zip(ipa)
            for name in ("../Fiction.map", "/Fiction.map", "Fiction.png",
                         "Fiction.map/../a", "Fiction\n.map"):
                with self.subTest(name=name), self.assertRaisesRegex(ValueError, "basename"):
                    inspect_private_collision_geometry_names(ipa, name)

    def test_private_json_output(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "local_reports").mkdir()
            ipa = root / "fiction.ipa"
            write_zip(ipa)
            out = root / "local_reports" / "stage265-synthetic.json"
            with patch("heman_tools.collision_atlas_alpha.Path.cwd", return_value=root):
                self.assertEqual(main(["--ipa", str(ipa), "--map", "Fiction.map",
                                       "--out", str(out)]), 0)
            report = json.loads(out.read_text(encoding="utf-8"))
            self.assertFalse(report["named_resource_exact_match_is_runtime_binding_proof"])


if __name__ == "__main__":
    unittest.main()
