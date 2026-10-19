"""Asset-free adversarial tests for candidate collision-tile statistics."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import zipfile

from heman_tools.collision_inventory import (
    main, private_output_path, scan_local_ipa, summarize_collision_layer,
)
from heman_tools.tilemap import TileMapFormatError, parse_tilemap
from test_tilemap import layer, sample


class CollisionInventoryTests(unittest.TestCase):
    def test_pairs_and_exposed_faces(self):
        source = sample(layer(
            w=3, h=2, ids=(7, 7, 65535, 7, 9, 65535),
            atlas=(0, 1, 255, 0, 1, 0), atlases=("alpha", "beta")))
        report = summarize_collision_layer(parse_tilemap(source))
        self.assertEqual((report["occupied_cells"], report["empty_cells"]), (4, 2))
        self.assertEqual(report["distinct_atlas_tile_pairs"], 3)
        self.assertEqual([x["cells"] for x in report["tiles"]], [2, 1, 1])
        first = report["tiles"][0]
        self.assertEqual(first["occupied_neighbor_counts"], [0, 0, 2, 0, 0])
        self.assertEqual(first["sides_next_to_empty_or_boundary"],
                         {"N": 1, "E": 0, "S": 1, "W": 2})
        self.assertEqual(report["tiles"][1]["atlas_name"], "beta")
        self.assertEqual(report["tiles"][1]["tile_id"], 7)

    def test_full_square_is_not_called_solid(self):
        report = summarize_collision_layer(parse_tilemap(
            sample(layer(w=3, h=3, ids=(4,)*9, atlas=(0,)*9))))
        entry = report["tiles"][0]
        self.assertEqual(entry["occupied_neighbor_counts"], [0, 0, 4, 4, 1])
        self.assertEqual(entry["sides_next_to_empty_or_boundary"],
                         {"N": 3, "E": 3, "S": 3, "W": 3})
        self.assertIn("solidness", report["interpretation"])

    def test_empty_stale_atlas_not_used(self):
        report = summarize_collision_layer(parse_tilemap(
            sample(layer(ids=(65535,)*6, atlas=(255, 3, 11, 0, 255, 23)))))
        self.assertEqual(report["tiles"], [])
        self.assertEqual(report["empty_cells"], 6)

    def test_single_tile_four_faces(self):
        report = summarize_collision_layer(parse_tilemap(
            sample(layer(w=1, h=1, ids=(3,), atlas=(0,)))))
        entry = report["tiles"][0]
        self.assertEqual(entry["occupied_neighbor_counts"], [1, 0, 0, 0, 0])
        self.assertEqual(sum(entry["sides_next_to_empty_or_boundary"].values()), 4)

    def test_absent_or_duplicate_collision_layer_fails(self):
        with self.assertRaises(KeyError):
            summarize_collision_layer(parse_tilemap(
                sample(layer(name="background"))))
        with self.assertRaises(KeyError):
            summarize_collision_layer(parse_tilemap(
                sample(layer(name="collision"), layer(name="collision"))))

    def test_temporary_synthetic_ipa(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "synthetic.ipa"
            with zipfile.ZipFile(ipa, "w") as archive:
                archive.writestr("Payload/MOTU.app/screen-med/maps/Fake.map", sample())
            report = scan_local_ipa(ipa, "Fake.map")
            self.assertEqual(report["occupied_cells"], 5)
            self.assertEqual(report["map"], "Fake.map")
            self.assertNotIn("tile_ids", report)
            self.assertNotIn("atlas_ids", report)

    def test_duplicate_entry_rejected(self):
        import warnings
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "duplicate.ipa"
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(ipa, "w") as archive:
                    name = "Payload/MOTU.app/screen-med/maps/Fake.map"
                    archive.writestr(name, sample())
                    archive.writestr(name, sample())
            with self.assertRaises(ValueError):
                scan_local_ipa(ipa, "Fake.map")

    def test_reject_traversal_and_wrong_screen(self):
        for name in ("../Fake.map", "..\\Fake.map", "d/Fake.map",
                     "Fake.map\n", "", ".map"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                scan_local_ipa(Path("missing"), name)
        with self.assertRaises(ValueError):
            scan_local_ipa(Path("missing"), "Fake.map", "../screen")

    def test_corrupt_map_rejected(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "bad.ipa"
            with zipfile.ZipFile(ipa, "w") as archive:
                archive.writestr("Payload/MOTU.app/screen-med/maps/Fake.map",
                                 b"not a valid multilayer map")
            with self.assertRaises(TileMapFormatError):
                scan_local_ipa(ipa, "Fake.map")

    def test_private_output_only(self):
        for name in ("README.json", "docs/report.json",
                     "local_reports/../report.json",
                     "local_reports/report.txt"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                private_output_path(Path(name))

    def test_symlinked_private_root_rejected(self):
        from unittest.mock import patch
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "public").mkdir()
            (root / "local_reports").symlink_to(root / "public", target_is_directory=True)
            with patch("heman_tools.collision_inventory.Path.cwd", return_value=root):
                with self.assertRaisesRegex(ValueError, "symbolic link"):
                    private_output_path(root / "local_reports" / "report.json")

    def test_cli_writes_private_json(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "mock.ipa"
            with zipfile.ZipFile(ipa, "w") as archive:
                archive.writestr("Payload/MOTU.app/screen-med/maps/Fake.map", sample())
            out = Path.cwd() / "local_reports" / "synthetic-inventory-test.json"
            try:
                self.assertEqual(main(["--ipa", str(ipa), "--map", "Fake.map",
                                       "--out", str(out)]), 0)
                result = json.loads(out.read_text())
                self.assertEqual(result["occupied_cells"], 5)
                self.assertEqual(result["distinct_atlas_tile_pairs"], 5)
            finally:
                out.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
