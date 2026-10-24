"""Synthetic-only tests for Stage258 collision-mask morphology profiles."""
import io
import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest
import warnings
import zipfile

from PIL import Image

from heman_tools.collision_mask_morphology import (
    compare_screen_pair,
    main,
    mask_profile,
    private_output_path,
)
from heman_tools.collision_atlas_alpha import TileSetFormatError
from test_tilemap import layer, sample


def text_field(value):
    return struct.pack("<H", len(value)) + value.encode("utf-16le")


def synthetic_tileset(scale=1):
    data = struct.pack("<8I", 32 * scale, 32 * scale, 32, 32,
                       49152, 65535, 0, 1)
    data += text_field("img_collisiontiles") + struct.pack("<I", 2)
    for index, name in enumerate(("half-mask", "full-mask")):
        fields = (index * 32 * scale, 0, 32 * scale, 32 * scale,
                  index, 0, 0, 0)
        data += struct.pack("<8I", *fields) + b"\x00" + text_field(name)
    return data


def synthetic_texture(scale=1, *, edge_difference=False, empty=False):
    image = Image.new("RGBA", (64, 32), (255, 0, 188, 0))
    if not empty:
        for y in range(32):
            for x in range(16):
                image.putpixel((x, y), (255, 0, 188, 255))
            for x in range(32, 64):
                image.putpixel((x, y), (255, 0, 188, 255))
    if scale != 1:
        image = image.resize((image.width * scale, image.height * scale),
                             Image.Resampling.NEAREST)
    if edge_difference and scale > 1:
        for y in range(image.height):
            for x in range(scale):
                image.putpixel((x, y), (255, 0, 188, 0))
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def synthetic_map(*, shown=0, tile_ids=(0, 1, 65535, 1, 0, 1),
                  atlas_ids=(0, 0, 255, 0, 0, 0),
                  atlases=("collision",)):
    return sample(layer(
        "collision", w=3, h=2, ids=tile_ids, atlas=atlas_ids,
        atlases=atlases, shown=shown,
    ))


def write_synthetic_ipa(path, *, large_shown=0, duplicate_map=False,
                        bad_tile_id=False, large_edge_difference=False,
                        empty_texture=False, atlas_names=("collision",)):
    med_map = synthetic_map(atlases=atlas_names)
    large_map = synthetic_map(shown=large_shown, atlases=atlas_names)
    if bad_tile_id:
        med_map = synthetic_map(tile_ids=(0, 1, 65535, 1, 0, 7),
                                atlases=atlas_names)
    with zipfile.ZipFile(path, "w") as archive:
        for screen, scale, map_bytes in (
            ("screen-med", 1, med_map), ("screen-xlarge", 2, large_map)
        ):
            prefix = f"Payload/MOTU.app/{screen}"
            archive.writestr(f"{prefix}/maps/Fake.map", map_bytes)
            archive.writestr(f"{prefix}/tilesets/collision.tileset",
                             synthetic_tileset(scale))
            archive.writestr(
                f"{prefix}/textures/collisionTiles.png",
                synthetic_texture(scale, edge_difference=(
                    large_edge_difference and scale == 2
                ), empty=empty_texture),
            )
            if duplicate_map and screen == "screen-med":
                archive.writestr(f"{prefix}/maps/Fake.map", map_bytes)


class CollisionMaskMorphologyTests(unittest.TestCase):
    def test_half_mask_edge_and_run_profile(self):
        image = Image.new("RGBA", (32, 32), (255, 0, 0, 0))
        for y in range(32):
            for x in range(16):
                image.putpixel((x, y), (255, 0, 0, 255))
        profile, mask = mask_profile(
            image, {"x": 0, "y": 0, "width": 32, "height": 32,
                    "ordinal": 0, "name": "synthetic"},
            atlas_index=0, cells=2,
        )
        self.assertEqual(sum(mask), 512)
        self.assertEqual(profile["edge_coverage_pixels"],
                         {"top": 16, "right": 0, "bottom": 16, "left": 32})
        self.assertEqual(profile["horizontal_runs"], 32)
        self.assertEqual(profile["vertical_runs"], 16)
        self.assertEqual(profile["exposed_four_neighbor_boundary_edges"], 96)
        self.assertEqual(profile["opaque_bbox_xyxy_exclusive"], [0, 0, 16, 32])
        self.assertEqual(profile["cells_using_tile"], 2)

    def test_empty_mask_has_no_bbox_or_boundary(self):
        image = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
        profile, mask = mask_profile(
            image, {"x": 0, "y": 0, "width": 8, "height": 8,
                    "ordinal": 1, "name": ""},
            atlas_index=0, cells=1,
        )
        self.assertEqual(sum(mask), 0)
        self.assertIsNone(profile["opaque_bbox_xyxy_exclusive"])
        self.assertEqual(profile["horizontal_runs"], 0)
        self.assertEqual(profile["vertical_runs"], 0)
        self.assertEqual(profile["exposed_four_neighbor_boundary_edges"], 0)

    def test_tile_pixel_budget_fails_closed(self):
        image = Image.new("RGBA", (1024, 1025), (0, 0, 0, 255))
        with self.assertRaisesRegex(TileSetFormatError, "pixel budget"):
            mask_profile(
                image, {"x": 0, "y": 0, "width": 1024, "height": 1025,
                        "ordinal": 0, "name": ""},
                atlas_index=0, cells=1,
            )

    def test_pair_profiles_and_normalized_masks_match(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "synthetic.ipa"
            write_synthetic_ipa(ipa)
            report = compare_screen_pair(ipa, "Fake.map")
            self.assertEqual(report["result"], "cross_screen_mask_morphology_complete")
            self.assertTrue(report["cross_screen"]["map_bytes_exactly_equal"])
            self.assertEqual(report["cross_screen"]["tile_rect_scale_factor"], 2)
            self.assertEqual(report["cross_screen"]["used_tile_count"], 2)
            self.assertEqual(report["cross_screen"]["exact_normalized_threshold_mask_matches"], 2)
            self.assertEqual(report["cross_screen"]["total_normalized_mask_mismatches"], 0)
            self.assertAlmostEqual(report["cross_screen"]["aggregate_normalized_mask_iou"], 1.0)
            self.assertEqual(report["tiles"][0]["screen_med"]["alpha_ge_128_pixels"], 512)
            self.assertEqual(report["tiles"][0]["screen_med"]["exposed_four_neighbor_boundary_edges"], 96)
            self.assertEqual(report["tiles"][1]["screen_med"]["alpha_ge_128_pixels"], 1024)
            self.assertEqual(report["tiles"][1]["screen_med"]["exposed_four_neighbor_boundary_edges"], 128)
            self.assertFalse(report["native_switch_collision_import_authorized"])
            serialized = json.dumps(report)
            self.assertNotIn('"mask":', serialized)
            self.assertNotIn('"tile_ids":', serialized)
            self.assertNotIn('"atlas_ids":', serialized)

    def test_mask_disagreement_is_reported_not_normalized_away(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "synthetic.ipa"
            write_synthetic_ipa(ipa, large_edge_difference=True)
            report = compare_screen_pair(ipa, "Fake.map")
            self.assertTrue(report["cross_screen"]["map_bytes_exactly_equal"])
            self.assertGreater(report["cross_screen"]["total_normalized_mask_mismatches"], 0)
            self.assertLess(report["cross_screen"]["aggregate_normalized_mask_iou"], 1.0)
            self.assertEqual(report["result"], "cross_screen_mask_morphology_complete")

    def test_equal_occupancy_does_not_hide_map_byte_difference(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "synthetic.ipa"
            write_synthetic_ipa(ipa, large_shown=1)
            report = compare_screen_pair(ipa, "Fake.map")
            self.assertFalse(report["cross_screen"]["map_bytes_exactly_equal"])
            self.assertEqual(report["screen_med"]["occupied_cells"], 5)
            self.assertEqual(report["screen_xlarge"]["occupied_cells"], 5)
            self.assertEqual(report["result"], "partial_or_divergent_morphology")

    def test_out_of_range_tile_id_fails_closed(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "synthetic.ipa"
            write_synthetic_ipa(ipa, bad_tile_id=True)
            with self.assertRaisesRegex(TileSetFormatError, "exceeds tileset"):
                compare_screen_pair(ipa, "Fake.map")

    def test_duplicate_selected_archive_entry_is_rejected(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "duplicate.ipa"
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                write_synthetic_ipa(ipa, duplicate_map=True)
            with self.assertRaisesRegex(ValueError, "exactly one IPA entry"):
                compare_screen_pair(ipa, "Fake.map")

    def test_missing_collision_atlas_is_rejected(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "synthetic.ipa"
            write_synthetic_ipa(ipa, atlas_names=("background",))
            with self.assertRaisesRegex(ValueError, "exactly one collision atlas"):
                compare_screen_pair(ipa, "Fake.map")

    def test_empty_textures_remain_a_valid_measured_mask(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "synthetic.ipa"
            write_synthetic_ipa(ipa, empty_texture=True)
            report = compare_screen_pair(ipa, "Fake.map")
            self.assertEqual(report["cross_screen"]["total_normalized_mask_mismatches"], 0)
            self.assertEqual(report["cross_screen"]["aggregate_normalized_mask_iou"], 1.0)
            self.assertTrue(all(tile["screen_med"]["alpha_ge_128_pixels"] == 0
                                for tile in report["tiles"]))

    def test_private_output_path_is_enforced(self):
        for path in ("README.json", "docs/report.json",
                     "local_reports/../report.json", "local_reports/report.txt"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                private_output_path(Path(path))

    def test_cli_writes_only_private_report(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "synthetic.ipa"
            write_synthetic_ipa(ipa)
            output = Path.cwd() / "local_reports" / "stage258-synthetic-test.json"
            try:
                result = main([
                    "--ipa", str(ipa), "--map", "Fake.map",
                    "--out", str(output),
                ])
                self.assertEqual(result, 0)
                report = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(report["result"], "cross_screen_mask_morphology_complete")
                self.assertFalse(report["original_collision_semantics_verified"])
            finally:
                output.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
