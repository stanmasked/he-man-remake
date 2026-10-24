"""Synthetic-only tests for the Stage259 runtime-grounded tileset parser."""
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest
import warnings
import zipfile

from heman_tools.tileset_collision_field_census import (
    audit_tileset_collision_fields,
    parse_tileset_collision_fields,
)
from test_collision_layer_atlas_inventory import (
    make_collision_map,
    make_repo,
    make_texture_wad,
    text_field,
)


def make_runtime_tileset(texture_ref, *, scale=1, divergent_semantics=False):
    tile_count = 7
    raw = struct.pack(
        "<8I",
        32 * scale, 32 * scale, 32 * scale, 32 * scale,
        49152, 65535, 0, 1,
    )
    raw += text_field(texture_ref) + struct.pack("<I", tile_count)
    for tile_id in range(tile_count):
        collision_id = 5 if (
            (texture_ref == "specialTiles" and tile_id == 0)
            or (texture_ref != "specialTiles" and tile_id == 5)
        ) else 0
        s32_data = 1 if texture_ref == "Collision.collisionCloudTiles" and tile_id == 5 else 0
        if divergent_semantics and texture_ref == "Collision.collisionCloudTiles" and tile_id == 6:
            s32_data = 9
        s32_alt1_data = 0
        opacity_flag = 1 if texture_ref != "specialTiles" and tile_id == 5 else 0
        shape_marker = 63 if texture_ref == "specialTiles" and tile_id == 0 else 0
        shape_ref = ""
        if texture_ref != "specialTiles" and tile_id == 0:
            shape_ref = "stub_0"
        elif texture_ref != "specialTiles" and tile_id == 6:
            shape_ref = "slant_18_0"
        fields = (
            tile_id * 32 * scale, 0, 32 * scale, 32 * scale,
            collision_id, s32_data, s32_alt1_data, opacity_flag,
        )
        raw += struct.pack("<8I", *fields) + bytes([shape_marker]) + text_field(shape_ref)
    return raw


def write_runtime_ipa(path, *, divergent_cloud_semantics=False):
    fake = make_collision_map()
    other = make_collision_map(atlas_names=("special",))
    texture_wad, texture_rows = make_texture_wad()
    tile_rows = [
        ("collision", "/tilesets/collision.tileset", 0),
        ("cloud", "/tilesets/cloud.tileset", 0),
        ("special", "/tilesets/damage.tileset", 0),
    ]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(path, "w") as archive:
            for screen, scale in (("screen-med", 1), ("screen-xlarge", 2)):
                prefix = f"Payload/MOTU.app/{screen}"
                archive.writestr(f"{prefix}/maps/Fake.map", fake)
                archive.writestr(f"{prefix}/maps/Other.map", other)
                archive.writestr(
                    f"{prefix}/maps/gs_background_sky.map",
                    b"med-special-format" if screen == "screen-med" else b"xlarge-special-format",
                )
                archive.writestr(f"{prefix}/meta/TilesetData.repo", make_repo("TilesetData", tile_rows))
                archive.writestr(f"{prefix}/meta/TextureData.repo", make_repo("TextureData", texture_rows))
                archive.writestr(f"{prefix}/textureData/TextureData.wad", texture_wad)
                archive.writestr(f"{prefix}/textures/collisionTiles.png", b"synthetic-png-collision")
                archive.writestr(f"{prefix}/textures/collisionCloudTiles.png", b"synthetic-png-cloud")
                archive.writestr(f"{prefix}/textures/specialTiles.png", b"synthetic-png-special")
                archive.writestr(
                    f"{prefix}/tilesets/collision.tileset",
                    make_runtime_tileset("img_collisiontiles", scale=scale),
                )
                archive.writestr(
                    f"{prefix}/tilesets/cloud.tileset",
                    make_runtime_tileset(
                        "Collision.collisionCloudTiles", scale=scale,
                        divergent_semantics=divergent_cloud_semantics and screen == "screen-xlarge",
                    ),
                )
                archive.writestr(
                    f"{prefix}/tilesets/damage.tileset",
                    make_runtime_tileset("specialTiles", scale=scale),
                )


class TilesetCollisionFieldCensusTests(unittest.TestCase):
    def test_runtime_header_and_collision_fields_are_named(self):
        raw = make_runtime_tileset("img_collisiontiles")
        parsed = parse_tileset_collision_fields(raw)
        self.assertEqual(parsed["collision_category"], 49152)
        self.assertEqual(parsed["collision_bitmask"], 65535)
        self.assertEqual(parsed["layer_count"], 1)
        self.assertEqual(parsed["layers"][0]["texture_ref"], "img_collisiontiles")
        tile5 = parsed["layers"][0]["tiles"][5]
        self.assertEqual(tile5["collision_id"], 5)
        self.assertEqual(tile5["opacity_flag_low_byte"], 1)
        tile6 = parsed["layers"][0]["tiles"][6]
        self.assertEqual(tile6["collision_id"], 0)
        self.assertEqual(tile6["collision_shape_ref"], "slant_18_0")

    def test_special_record_preserves_marker_and_does_not_infer_behavior(self):
        parsed = parse_tileset_collision_fields(make_runtime_tileset("specialTiles"))
        tile0 = parsed["layers"][0]["tiles"][0]
        self.assertEqual(tile0["collision_id"], 5)
        self.assertEqual(tile0["shape_marker"], 63)
        self.assertEqual(tile0["opacity_flag_low_byte"], 0)
        self.assertFalse(parsed.get("original_collision_semantics_verified", False))

    def test_nonempty_optional_name_is_rejected_not_guessed(self):
        raw = bytearray(make_runtime_tileset("img_collisiontiles"))
        struct.pack_into("<I", raw, 24, 1)
        with self.assertRaisesRegex(ValueError, "optional tileset name"):
            parse_tileset_collision_fields(bytes(raw))

    def test_truncated_tile_record_is_rejected(self):
        raw = make_runtime_tileset("img_collisiontiles")
        with self.assertRaises(ValueError):
            parse_tileset_collision_fields(raw[:-1])

    def test_original_style_synthetic_ipa_joins_tile_ids_to_metadata(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "synthetic.ipa"
            write_runtime_ipa(ipa)
            report = audit_tileset_collision_fields(ipa)
            rows = {row["atlas_name"]: row for row in report["tilesets"]}
            self.assertEqual(report["collision_layer_summary"]["tilesets_parsed"], 3)
            self.assertEqual(report["collision_layer_summary"]["tilesets_not_parsed"], 0)
            self.assertTrue(rows["collision"]["cross_pack_semantic_metadata_equal"])
            collision5 = next(row for row in rows["collision"]["used_tile_records"] if row["tile_id"] == 5)
            self.assertEqual(collision5["frequency"], 2)
            self.assertEqual(collision5["collision_id"], 5)
            self.assertEqual(collision5["opacity_flag_low_byte"], 1)
            cloud6 = next(row for row in rows["cloud"]["used_tile_records"] if row["tile_id"] == 6)
            self.assertEqual(cloud6["collision_shape_ref"], "slant_18_0")
            special0 = next(row for row in rows["special"]["used_tile_records"] if row["tile_id"] == 0)
            self.assertEqual(special0["shape_marker"], 63)
            self.assertFalse(report["original_collision_semantics_verified"])
            serialized = str(report)
            self.assertNotIn("Fake.map", serialized)
            self.assertNotIn("Other.map", serialized)
            self.assertNotIn("cell_coordinates", serialized)

    def test_cross_pack_semantic_difference_is_reported(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "synthetic.ipa"
            write_runtime_ipa(ipa, divergent_cloud_semantics=True)
            report = audit_tileset_collision_fields(ipa)
            cloud = next(row for row in report["tilesets"] if row["atlas_name"] == "cloud")
            self.assertFalse(cloud["cross_pack_semantic_metadata_equal"])
            self.assertEqual(report["collision_layer_summary"]["cross_pack_semantic_parity_failures"], 1)


if __name__ == "__main__":
    unittest.main()
