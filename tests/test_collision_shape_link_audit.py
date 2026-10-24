"""Synthetic-only regressions for Stage260 tile-to-Shape2D resource links."""
import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest
import warnings
import zipfile

from heman_tools.collision_shape_link_audit import (
    TilesetFormatError,
    compare_screen_pair,
    main,
    parse_runtime_tileset,
    private_output_path,
)
from test_tilemap import layer, sample


def text_field(value):
    return struct.pack("<H", len(value)) + value.encode("utf-16le")


def shape_polygon(vertices, *, flags=0):
    payload = struct.pack("<IIH", 0, flags, 0) + struct.pack("<I", len(vertices))
    payload += struct.pack("<" + "f" * (2 * len(vertices)),
                           *(coord for point in vertices for coord in point))
    return payload


def synthetic_tileset(scale=1, *, shape_ref="ramp_a", collision_id_1=5,
                      texture_ref_count=1, trailing=b""):
    data = struct.pack("<6ifi", 32*scale, 32*scale, 32*scale, 32*scale,
                       0xC000, 0xFFFF, 0.0, texture_ref_count)
    if texture_ref_count:
        data += text_field("img_collisiontiles")
    data += struct.pack("<i", 2)
    records = (
        (0, 0, 32*scale, 32*scale, 0, 0, 0, 0, 0.0, shape_ref),
        (32*scale, 0, 32*scale, 32*scale, collision_id_1, 0, 0, 1, 0.0, ""),
    )
    for x, y, w, h, collision_id, s32_data, s32_alt1, opacity, damage, ref in records:
        data += struct.pack("<7iBf", x, y, w, h, collision_id,
                            s32_data, s32_alt1, opacity, damage)
        data += text_field(ref)
    return data + trailing


def synthetic_map(*, tile_ids=(0, 1, 65535, 1, 0, 1),
                  atlas_ids=(0, 0, 255, 0, 0, 0),
                  atlases=("collision",), shown=0):
    return sample(layer("collision", w=3, h=2, ids=tile_ids,
                        atlas=atlas_ids, atlases=atlases, shown=shown))


def write_synthetic_ipa(path, *, shape_med=None, shape_large=None,
                        omit_large_shape=False, collision_id_large=5,
                        invalid_ref=None, duplicate_shape=False):
    med_map = synthetic_map()
    large_map = synthetic_map()
    if invalid_ref is not None:
        # Replace only the shape-reference field while preserving all other records.
        med_tileset = synthetic_tileset(shape_ref=invalid_ref)
    else:
        med_tileset = synthetic_tileset()
    large_tileset = synthetic_tileset(scale=2, collision_id_1=collision_id_large, shape_ref=invalid_ref or "ramp_a")
    if shape_med is None:
        shape_med = shape_polygon(((32, 22), (32, 32), (0, 32)))
    if shape_large is None:
        shape_large = shape_med
    with zipfile.ZipFile(path, "w") as archive:
        for screen, tileset, map_bytes in (
            ("screen-med", med_tileset, med_map),
            ("screen-xlarge", large_tileset, large_map),
        ):
            prefix = f"Payload/MOTU.app/{screen}"
            archive.writestr(f"{prefix}/maps/Fake.map", map_bytes)
            archive.writestr(f"{prefix}/tilesets/collision.tileset", tileset)
        med_shape_path = "Payload/MOTU.app/screen-med/geometry/ramp_a.shape"
        large_shape_path = "Payload/MOTU.app/screen-xlarge/geometry/ramp_a.shape"
        archive.writestr(med_shape_path, shape_med)
        if not omit_large_shape:
            archive.writestr(large_shape_path, shape_large)
        if duplicate_shape:
            archive.writestr(med_shape_path, shape_med)


class CollisionShapeLinkAuditTests(unittest.TestCase):
    def test_runtime_tileset_parser_reads_shape_reference_and_metadata(self):
        parsed = parse_runtime_tileset(synthetic_tileset())
        self.assertEqual(parsed["texture_refs"], ["img_collisiontiles"])
        self.assertEqual(parsed["header_ints"][4:], [0xC000, 0xFFFF])
        self.assertEqual(len(parsed["entries"]), 2)
        self.assertEqual(parsed["entries"][0]["collision_shape_reference"], "ramp_a")
        self.assertEqual(parsed["entries"][0]["collision_id"], 0)
        self.assertEqual(parsed["entries"][1]["collision_id"], 5)
        self.assertTrue(parsed["entries"][1]["opacity_flag"])
        self.assertEqual(parsed["entries"][1]["collision_shape_reference"], "")

    def test_pair_links_explicit_shape_and_preserves_fallback_case(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "synthetic.ipa"
            write_synthetic_ipa(ipa)
            report = compare_screen_pair(ipa, "Fake.map")
            self.assertEqual(report["result"], "cross_screen_shape_link_audit_complete")
            self.assertTrue(report["cross_screen"]["map_bytes_exactly_equal"])
            self.assertEqual(report["cross_screen"]["tile_rect_scale_factor"], 2)
            self.assertEqual(report["cross_screen"]["used_tile_count"], 2)
            self.assertEqual(report["cross_screen"]["explicit_shape_reference_count"], 1)
            self.assertEqual(report["cross_screen"]["no_explicit_shape_reference_count"], 1)
            self.assertEqual(report["cross_screen"]["exact_shape_resource_matches"], 1)
            self.assertTrue(report["cross_screen"]["all_referenced_shape_resources_byte_equal"])
            tile0 = report["screen_med"]["used_tiles"][0]
            self.assertEqual(tile0["collision_shape_reference"], "ramp_a")
            self.assertEqual(tile0["shape_resource"]["kind"], "polygon")
            self.assertEqual(tile0["shape_resource"]["vertex_count"], 3)
            tile1 = report["screen_med"]["used_tiles"][1]
            self.assertIsNone(tile1["collision_shape_reference"])
            self.assertIsNone(tile1["shape_resource"])
            self.assertFalse(report["native_switch_collision_import_authorized"])
            serialized = json.dumps(report)
            self.assertNotIn('"vertices":', serialized)
            self.assertNotIn('"tile_ids":', serialized)
            self.assertNotIn('"atlas_ids":', serialized)

    def test_shape_byte_divergence_is_reported(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "synthetic.ipa"
            changed = shape_polygon(((32, 22), (32, 32), (0, 31)))
            write_synthetic_ipa(ipa, shape_large=changed)
            report = compare_screen_pair(ipa, "Fake.map")
            self.assertEqual(report["result"], "partial_or_divergent_shape_links")
            self.assertFalse(report["cross_screen"]["all_referenced_shape_resources_byte_equal"])
            self.assertEqual(report["cross_screen"]["exact_shape_resource_matches"], 0)

    def test_missing_shape_peer_fails_closed(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "synthetic.ipa"
            write_synthetic_ipa(ipa, omit_large_shape=True)
            with self.assertRaisesRegex(ValueError, "exactly one .shape resource"):
                compare_screen_pair(ipa, "Fake.map")

    def test_path_like_shape_reference_is_rejected(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "synthetic.ipa"
            write_synthetic_ipa(ipa, invalid_ref="../ramp_a")
            with self.assertRaisesRegex(ValueError, "unsafe or invalid"):
                compare_screen_pair(ipa, "Fake.map")

    def test_tile_collision_metadata_divergence_fails_closed(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "synthetic.ipa"
            write_synthetic_ipa(ipa, collision_id_large=99)
            with self.assertRaisesRegex(ValueError, "collision metadata differs"):
                compare_screen_pair(ipa, "Fake.map")

    def test_duplicate_shape_entry_is_rejected(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "synthetic.ipa"
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                write_synthetic_ipa(ipa, duplicate_shape=True)
            with self.assertRaisesRegex(ValueError, "exactly one .shape resource"):
                compare_screen_pair(ipa, "Fake.map")

    def test_out_of_range_tile_id_is_rejected(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "synthetic.ipa"
            write_synthetic_ipa(ipa)
            # The synthetic tileset has two records, so tile ID 2 must fail.
            with zipfile.ZipFile(ipa, "a") as archive:
                archive.writestr(
                    "Payload/MOTU.app/screen-med/maps/Bad.map",
                    synthetic_map(tile_ids=(0, 2, 65535, 1, 0, 1)),
                )
                archive.writestr(
                    "Payload/MOTU.app/screen-xlarge/maps/Bad.map",
                    synthetic_map(tile_ids=(0, 2, 65535, 1, 0, 1)),
                )
            with self.assertRaisesRegex(TilesetFormatError, "exceeds tile-record count"):
                compare_screen_pair(ipa, "Bad.map")

    def test_invalid_texture_reference_count_is_rejected(self):
        with self.assertRaisesRegex(TilesetFormatError, "texture-reference count"):
            parse_runtime_tileset(synthetic_tileset(texture_ref_count=0))

    def test_trailing_tileset_bytes_are_rejected(self):
        with self.assertRaisesRegex(TilesetFormatError, "trailing bytes"):
            parse_runtime_tileset(synthetic_tileset(trailing=b"extra"))

    def test_private_output_path_is_enforced(self):
        for path in ("README.json", "docs/report.json",
                     "local_reports/../report.json", "local_reports/report.txt"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                private_output_path(Path(path))

    def test_cli_writes_only_private_report(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "synthetic.ipa"
            write_synthetic_ipa(ipa)
            output = Path.cwd() / "local_reports" / "stage260-synthetic-test.json"
            try:
                result = main(["--ipa", str(ipa), "--map", "Fake.map", "--out", str(output)])
                self.assertEqual(result, 0)
                report = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(report["result"], "cross_screen_shape_link_audit_complete")
                self.assertFalse(report["original_collision_semantics_verified"])
            finally:
                output.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
