"""Fictional tile grids only; never use commercial .map bytes in CI."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import stat
from tempfile import TemporaryDirectory
import unittest
import warnings
import zipfile

from heman_tools.collision_components import (
    inspect_private_pair, main, summarize_topology,
)
from heman_tools.tilemap import TileMap, parse_tilemap
from test_tilemap import layer, sample


def fixture():
    # L-shaped group with 3 cells; separate single cell in lower right.
    return parse_tilemap(sample(layer(w=3, h=2,
        ids=(1, 1, 65535, 1, 65535, 2),
        atlas=(0, 0, 255, 0, 15, 0))))


class CollisionComponentTests(unittest.TestCase):
    def test_four_connected_l_shape_and_island(self):
        report = summarize_topology(fixture())
        self.assertEqual(report["occupied_cells"], 4)
        self.assertEqual(report["empty_cells"], 2)
        self.assertEqual(report["component_count_4_connected"], 2)
        self.assertEqual(report["largest_component_cells"], 3)
        self.assertEqual(report["singleton_components"], 1)
        self.assertEqual(report["adjacent_occupied_edge_pairs"], 2)
        self.assertEqual(report["exposed_grid_edges_total"], 12)
        self.assertEqual(report["components"][0]["bbox_inclusive_xyxy"],
                         [0, 0, 1, 1])
        self.assertEqual(report["components"][1]["bbox_inclusive_xyxy"],
                         [2, 1, 2, 1])
        self.assertEqual(report["tile_id_counts"], {"1": 3, "2": 1})
        self.assertFalse(report["runtime_collision_type_verified"]
                         if "runtime_collision_type_verified" in report else
                         report["original_gameplay_physics_verified"])
        self.assertFalse(report["automatic_collision_export_permitted"])

    def test_full_square_counts_shared_edges_once(self):
        report = summarize_topology(parse_tilemap(sample(
            layer(w=2, h=2, ids=(5,) * 4, atlas=(0,) * 4))))
        self.assertEqual(report["component_count_4_connected"], 1)
        self.assertEqual(report["adjacent_occupied_edge_pairs"], 4)
        self.assertEqual(report["exposed_grid_edges_total"], 8)
        self.assertEqual(report["components"][0]["bbox_inclusive_xyxy"],
                         [0, 0, 1, 1])

    def test_diagonal_touching_remains_disconnected(self):
        report = summarize_topology(parse_tilemap(sample(
            layer(w=2, h=2, ids=(7, 65535, 65535, 7),
                  atlas=(0, 255, 255, 0)))))
        self.assertEqual(report["component_count_4_connected"], 2)
        self.assertEqual(report["exposed_grid_edges_total"], 8)

    def test_empty_grid_ignores_stale_atlas_ids(self):
        report = summarize_topology(parse_tilemap(sample(
            layer(ids=(65535,) * 6, atlas=(255, 14, 6, 32, 1, 0)))))
        self.assertEqual(report["component_count_4_connected"], 0)
        self.assertEqual(report["largest_component_cells"], 0)
        self.assertEqual(report["exposed_grid_edges_total"], 0)
        self.assertEqual(report["components"], [])

    def test_different_atlases_connect_by_occupancy(self):
        source = parse_tilemap(sample(layer(w=2, h=1,
            ids=(3, 4), atlas=(0, 1), atlases=("A", "B"))))
        report = summarize_topology(source)
        self.assertEqual(report["component_count_4_connected"], 1)
        self.assertEqual(report["atlas_id_counts"], {"0": 1, "1": 1})
        self.assertEqual(report["components"][0]["distinct_tile_ids"], 2)
        self.assertEqual(report["components"][0]["distinct_atlas_ids"], 2)

    def test_corrupt_array_length_rejected(self):
        source = fixture()
        broken = TileMap((replace(source.layers[0], atlas_ids=b""),))
        with self.assertRaisesRegex(ValueError, "inconsistent"):
            summarize_topology(broken)

    def test_nonexistent_and_duplicate_collision_layer_rejected(self):
        with self.assertRaises(KeyError):
            summarize_topology(parse_tilemap(sample(layer(name="map"))))
        with self.assertRaises(KeyError):
            summarize_topology(parse_tilemap(
                sample(layer(name="collision"), layer(name="collision"))))

    def test_many_disconnected_regions_rejected(self):
        w = h = 100
        indices = tuple(3 if (x + y) % 2 == 0 else 65535
                        for y in range(h) for x in range(w))
        atlases = bytes(0 if v == 3 else 255 for v in indices)
        source = parse_tilemap(sample(layer(
            w=w, h=h, ids=indices, atlas=atlases)))
        with self.assertRaisesRegex(ValueError, "too many isolated"):
            summarize_topology(source)

    def _ipa(self, directory, med=None, large=None):
        destination = Path(directory) / "fabricated.ipa"
        with zipfile.ZipFile(destination, "w") as archive:
            if med is not None:
                archive.writestr("Payload/MOTU.app/screen-med/maps/Fake.map", med)
            if large is not None:
                archive.writestr("Payload/MOTU.app/screen-xlarge/maps/Fake.map", large)
        return destination

    def test_identical_synthetic_screen_maps(self):
        with TemporaryDirectory() as directory:
            content = sample()
            result = inspect_private_pair(
                self._ipa(directory, content, content), "Fake.map")
        self.assertTrue(result["source_map_bytes_identical"])
        self.assertTrue(result["derived_topology_identical"])
        self.assertEqual(result["screens"]["screen-med"]["occupied_cells"], 5)
        self.assertFalse(result["runtime_collision_type_verified"])

    def test_equal_topology_does_not_claim_equal_bytes(self):
        with TemporaryDirectory() as directory:
            a = sample(layer(shown=0))
            b = sample(layer(shown=1))
            result = inspect_private_pair(self._ipa(directory, a, b), "Fake.map")
        self.assertFalse(result["source_map_bytes_identical"])
        self.assertTrue(result["derived_topology_identical"])

    def test_missing_second_pack_rejected(self):
        with TemporaryDirectory() as directory:
            p = self._ipa(directory, sample())
            with self.assertRaisesRegex(ValueError, "exactly one"):
                inspect_private_pair(p, "Fake.map")

    def test_bad_basename_rejected(self):
        with self.assertRaises(ValueError):
            inspect_private_pair(Path("missing.ipa"), "../Fake.map")
        with self.assertRaises(ValueError):
            inspect_private_pair(Path("missing.ipa"), "x\\Fake.map")

    def test_duplicate_selected_zip_name_rejected(self):
        with TemporaryDirectory() as directory:
            p = self._ipa(directory, sample(), sample())
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(p, "a") as archive:
                    archive.writestr(
                        "Payload/MOTU.app/screen-med/maps/Fake.map", sample())
            with self.assertRaisesRegex(ValueError, "exactly one"):
                inspect_private_pair(p, "Fake.map")

    def test_symlink_selected_map_rejected(self):
        with TemporaryDirectory() as directory:
            p = Path(directory) / "fabricated.ipa"
            with zipfile.ZipFile(p, "w") as archive:
                item = zipfile.ZipInfo(
                    "Payload/MOTU.app/screen-med/maps/Fake.map")
                item.create_system = 3
                item.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(item, b"wrong")
                archive.writestr(
                    "Payload/MOTU.app/screen-xlarge/maps/Fake.map",
                    sample())
            with self.assertRaisesRegex(ValueError, "invalid"):
                inspect_private_pair(p, "Fake.map")

    def test_private_cli_generates_only_ignored_json(self):
        with TemporaryDirectory() as directory:
            p = self._ipa(directory, sample(), sample())
            destination = (Path.cwd() / "local_reports" /
                           "synthetic-topology-stage74.json")
            try:
                self.assertEqual(main([
                    "--ipa", str(p), "--map", "Fake.map",
                    "--out", str(destination)]), 0)
                report = json.loads(destination.read_text())
                self.assertEqual(report["screens"]["screen-med"]["occupied_cells"], 5)
                self.assertNotIn("atlas_ids", report)
                self.assertNotIn("tile_ids", report)
                self.assertFalse(report["automatic_collision_export_permitted"])
            finally:
                destination.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
