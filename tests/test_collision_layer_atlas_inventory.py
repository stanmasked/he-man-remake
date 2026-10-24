"""Synthetic-only tests for global collision-layer atlas routing."""
import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest
import warnings
import zipfile

from heman_tools.collision_layer_atlas_inventory import (
    audit_collision_atlas_routing,
    main,
    private_output_path,
)
from test_tilemap import layer, sample


def text_field(value):
    return struct.pack("<H", len(value)) + value.encode("utf-16le")


def make_repo(label, rows):
    raw = text_field(label) + struct.pack("<HI", 0, len(rows))
    for key, path, value in rows:
        raw += text_field(key) + struct.pack("<I", 0) + text_field(path) + struct.pack("<I", value)
    return raw


def make_tileset(texture_ref):
    return struct.pack("<8I", 32, 32, 32, 32, 49152, 65535, 0, 1) + text_field(texture_ref)


def make_collision_map(*, shown=0, atlas_names=("collision", "cloud")):
    if atlas_names == ("collision", "cloud"):
        return sample(layer(
            "collision", w=2, h=2, ids=(5, 5, 65535, 6),
            atlas=(0, 0, 255, 1), atlases=atlas_names, shown=shown,
        ))
    if atlas_names == ("special",):
        return sample(layer(
            "collision", w=2, h=1, ids=(0, 65535),
            atlas=(0, 255), atlases=atlas_names, shown=shown,
        ))
    return sample(layer(
        "background", w=2, h=1, ids=(1, 65535),
        atlas=(0, 255), atlases=atlas_names, shown=shown,
    ))


def write_synthetic_ipa(path, *, divergent_regular=False, missing_large_map=False,
                        duplicate_med_map=False, missing_special_registry=False):
    fake_med = make_collision_map()
    fake_large = make_collision_map(shown=1 if divergent_regular else 0)
    other = make_collision_map(atlas_names=("special",))
    tile_rows = [
        ("collision", "/tilesets/collision.tileset", 0),
        ("cloud", "/tilesets/cloud.tileset", 0),
    ]
    if not missing_special_registry:
        tile_rows.append(("special", "/tilesets/damage.tileset", 0))
    texture_rows = [
        ("img_collisiontiles", "textureData/TextureData.wad", 0),
        ("Collision.collisionCloudTiles", "textureData/TextureData.wad", 100),
        ("specialTiles", "textureData/TextureData.wad", 200),
    ]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(path, "w") as archive:
            for screen in ("screen-med", "screen-xlarge"):
                prefix = f"Payload/MOTU.app/{screen}"
                archive.writestr(
                    f"{prefix}/maps/Fake.map",
                    fake_med if screen == "screen-med" else fake_large,
                )
                if not (missing_large_map and screen == "screen-xlarge"):
                    archive.writestr(f"{prefix}/maps/Other.map", other)
                archive.writestr(
                    f"{prefix}/maps/gs_background_sky.map",
                    b"med-special-format" if screen == "screen-med" else b"xlarge-special-format",
                )
                archive.writestr(
                    f"{prefix}/meta/TilesetData.repo",
                    make_repo("TilesetData", tile_rows),
                )
                archive.writestr(
                    f"{prefix}/meta/TextureData.repo",
                    make_repo("TextureData", texture_rows),
                )
                archive.writestr(
                    f"{prefix}/tilesets/collision.tileset", make_tileset("img_collisiontiles")
                )
                archive.writestr(
                    f"{prefix}/tilesets/cloud.tileset", make_tileset("Collision.collisionCloudTiles")
                )
                archive.writestr(
                    f"{prefix}/tilesets/damage.tileset", make_tileset("specialTiles")
                )
                if duplicate_med_map and screen == "screen-med":
                    archive.writestr(f"{prefix}/maps/Fake.map", fake_med)


class CollisionLayerAtlasInventoryTests(unittest.TestCase):
    def test_global_aggregate_counts_and_registry_alias_resolution(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "synthetic.ipa"
            write_synthetic_ipa(ipa)
            report = audit_collision_atlas_routing(ipa)
            pairs = report["screen_pack_map_pair_audit"]
            summary = report["collision_layer_summary"]
            self.assertEqual(pairs["paired_map_files"], 3)
            self.assertEqual(pairs["exact_byte_equal_map_pairs"], 2)
            self.assertEqual(pairs["known_special_format_map_pairs_skipped"], 1)
            self.assertFalse(pairs["known_special_format_pair_byte_equal"])
            self.assertEqual(pairs["normal_multilayer_maps_parsed"], 2)
            self.assertTrue(report["resource_registry_summary"]["tileset_registry_exact_bytes_equal_across_packs"])
            self.assertTrue(report["resource_registry_summary"]["texture_registry_exact_bytes_equal_across_packs"])
            self.assertEqual(summary["collision_named_layers"], 2)
            self.assertEqual(summary["occupied_cells"], 4)
            self.assertEqual(summary["cells_on_atlas_named_collision"], 2)
            self.assertEqual(summary["cells_on_other_atlases"], 2)
            by_name = {row["atlas_name"]: row for row in summary["atlas_usage"]}
            self.assertEqual(by_name["collision"]["tile_id_frequencies"], {"5": 2})
            self.assertEqual(by_name["cloud"]["tile_id_frequencies"], {"6": 1})
            self.assertEqual(by_name["special"]["tile_id_frequencies"], {"0": 1})
            self.assertEqual(by_name["special"]["tileset_resource_path"], "/tilesets/damage.tileset")
            self.assertEqual(by_name["special"]["tileset_texture_ref"], "specialTiles")
            self.assertTrue(by_name["special"]["tileset_registry_entry_present"])
            self.assertTrue(by_name["special"]["texture_registry_entry_present"])
            self.assertEqual(report["unresolved_tileset_registry_aliases"], [])
            self.assertFalse(report["original_collision_semantics_verified"])
            serialized = json.dumps(report)
            self.assertNotIn('"tile_ids"', serialized)
            self.assertNotIn('"atlas_ids"', serialized)
            self.assertNotIn("Fake.map", serialized)
            self.assertNotIn("Other.map", serialized)

    def test_missing_registry_alias_is_reported_not_guessed(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "synthetic.ipa"
            write_synthetic_ipa(ipa, missing_special_registry=True)
            report = audit_collision_atlas_routing(ipa)
            self.assertEqual(report["unresolved_tileset_registry_aliases"], ["special"])
            special = next(row for row in report["collision_layer_summary"]["atlas_usage"]
                           if row["atlas_name"] == "special")
            self.assertFalse(special["tileset_registry_entry_present"])
            self.assertIsNone(special["tileset_resource_path"])

    def test_unexpected_regular_map_byte_divergence_fails_closed(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "synthetic.ipa"
            write_synthetic_ipa(ipa, divergent_regular=True)
            with self.assertRaisesRegex(ValueError, "unexpected cross-screen map byte divergence"):
                audit_collision_atlas_routing(ipa)

    def test_missing_screen_pack_map_fails_closed(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "synthetic.ipa"
            write_synthetic_ipa(ipa, missing_large_map=True)
            with self.assertRaisesRegex(ValueError, "different map filename sets"):
                audit_collision_atlas_routing(ipa)

    def test_duplicate_map_entry_fails_closed(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "synthetic.ipa"
            write_synthetic_ipa(ipa, duplicate_med_map=True)
            with self.assertRaisesRegex(ValueError, "duplicate map entry"):
                audit_collision_atlas_routing(ipa)

    def test_no_map_names_or_cell_coordinates_are_exported(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "synthetic.ipa"
            write_synthetic_ipa(ipa)
            report = audit_collision_atlas_routing(ipa)
            self.assertNotIn("map_names", report)
            self.assertNotIn("cell_coordinates", report)
            self.assertNotIn("source_map_hashes", report)

    def test_private_output_path_is_enforced(self):
        for path in ("README.json", "docs/report.json",
                     "local_reports/../report.json", "local_reports/report.txt"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                private_output_path(Path(path))

    def test_dangling_symlink_private_output_is_rejected(self):
        from unittest.mock import patch
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "local_reports").mkdir()
            link = root / "local_reports" / "report.json"
            link.symlink_to(root / "local_reports" / "missing.json")
            with patch("heman_tools.collision_layer_atlas_inventory.Path.cwd", return_value=root):
                with self.assertRaisesRegex(ValueError, "symbolic link"):
                    private_output_path(link)

    def test_cli_writes_private_aggregate_only_report(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "synthetic.ipa"
            write_synthetic_ipa(ipa)
            output = Path.cwd() / "local_reports" / "stage258-synthetic-test.json"
            try:
                self.assertEqual(main(["--ipa", str(ipa), "--out", str(output)]), 0)
                report = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(report["collision_layer_summary"]["occupied_cells"], 4)
                self.assertNotIn("Fake.map", output.read_text(encoding="utf-8"))
            finally:
                output.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
