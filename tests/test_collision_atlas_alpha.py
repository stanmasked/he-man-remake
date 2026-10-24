"""Synthetic-only tests for Stage257 collision atlas alpha census."""
import io
import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest
import warnings
import zipfile

from PIL import Image

from heman_tools.collision_atlas_alpha import (
    TileSetFormatError,
    compare_screen_pair,
    main,
    parse_tileset,
    private_output_path,
)
from test_tilemap import layer, sample


def text_field(value):
    return struct.pack("<H", len(value)) + value.encode("utf-16le")


def synthetic_tileset(scale=1, *, trailing=b""):
    header = struct.pack("<8I", 32 * scale, 32 * scale, 32, 32,
                         49152, 65535, 0, 1)
    result = header + text_field("img_collisiontiles") + struct.pack("<I", 2)
    for index, name in enumerate(("solid-candidate", "")):
        fields = (index * 32 * scale, 0, 32 * scale, 32 * scale,
                  index, 0, 0, 0)
        result += struct.pack("<8I", *fields) + b"\x00" + text_field(name)
    return result + trailing


def synthetic_texture(scale=1):
    image = Image.new("RGBA", (64, 32), (255, 0, 188, 0))
    for y in range(32):
        for x in range(16):
            image.putpixel((x, y), (255, 0, 188, 255))
    for y in range(32):
        for x in range(32, 64):
            image.putpixel((x, y), (255, 0, 188, 255))
    if scale != 1:
        image = image.resize((image.width * scale, image.height * scale),
                             Image.Resampling.NEAREST)
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
                        bad_tile_id=False):
    med_map = synthetic_map()
    large_map = synthetic_map(shown=large_shown)
    if bad_tile_id:
        med_map = synthetic_map(tile_ids=(0, 1, 65535, 1, 0, 7))
    with zipfile.ZipFile(path, "w") as archive:
        for screen, scale, map_bytes in (
            ("screen-med", 1, med_map), ("screen-xlarge", 2, large_map)
        ):
            prefix = f"Payload/MOTU.app/{screen}"
            archive.writestr(f"{prefix}/maps/Fake.map", map_bytes)
            archive.writestr(f"{prefix}/tilesets/collision.tileset",
                             synthetic_tileset(scale))
            archive.writestr(f"{prefix}/textures/collisionTiles.png",
                             synthetic_texture(scale))
            if duplicate_map and screen == "screen-med":
                archive.writestr(f"{prefix}/maps/Fake.map", map_bytes)


class CollisionAtlasAlphaTests(unittest.TestCase):
    def test_tileset_rectangles_are_parsed_in_record_order(self):
        parsed = parse_tileset(synthetic_tileset())
        self.assertEqual(parsed["texture_ref"], "img_collisiontiles")
        self.assertEqual(len(parsed["entries"]), 2)
        self.assertEqual(parsed["entries"][0]["name"], "solid-candidate")
        self.assertEqual(parsed["entries"][1]["name"], "")
        self.assertEqual(
            [parsed["entries"][1][key] for key in ("x", "y", "width", "height")],
            [32, 0, 32, 32],
        )

    def test_trailing_tileset_bytes_fail_closed(self):
        with self.assertRaises(TileSetFormatError):
            parse_tileset(synthetic_tileset(trailing=b"unexpected"))

    def test_real_screen_pair_contract_on_synthetic_assets(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "synthetic.ipa"
            write_synthetic_ipa(ipa)
            report = compare_screen_pair(ipa, "Fake.map")
            self.assertEqual(report["result"], "cross_screen_alpha_census_complete")
            self.assertTrue(report["cross_screen"]["map_bytes_exactly_equal"])
            self.assertTrue(report["cross_screen"]["tile_rectangles_match_after_uniform_scaling"])
            self.assertTrue(report["cross_screen"]["alpha_coverage_agrees_within_tolerance"])
            self.assertEqual(report["screen_med"]["map_layer"]["occupied_cells"], 5)
            self.assertEqual(report["screen_med"]["map_layer"]["tile_id_frequencies"],
                             {"0": 2, "1": 3})
            self.assertAlmostEqual(
                report["screen_med"]["tiles"][0]["alpha_at_least_128_fraction"],
                0.5,
            )
            self.assertEqual(
                report["screen_med"]["tiles"][1]["alpha_at_least_128_fraction"],
                1.0,
            )
            self.assertFalse(report["original_collision_semantics_verified"])
            serialized = json.dumps(report)
            self.assertNotIn('"tile_ids"', serialized)
            self.assertNotIn('"atlas_ids"', serialized)

    def test_equal_occupancy_does_not_hide_source_byte_difference(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "synthetic.ipa"
            write_synthetic_ipa(ipa, large_shown=1)
            report = compare_screen_pair(ipa, "Fake.map")
            self.assertFalse(report["cross_screen"]["map_bytes_exactly_equal"])
            self.assertEqual(report["screen_med"]["map_layer"]["occupied_cells"],
                             report["screen_xlarge"]["map_layer"]["occupied_cells"])
            self.assertEqual(report["result"], "partial_or_divergent_alpha_census")

    def test_out_of_range_tile_id_is_rejected(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "synthetic.ipa"
            write_synthetic_ipa(ipa, bad_tile_id=True)
            with self.assertRaises(TileSetFormatError):
                compare_screen_pair(ipa, "Fake.map")

    def test_duplicate_map_entry_is_rejected(self):
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
            med_map = synthetic_map(atlases=("not-collision",))
            with zipfile.ZipFile(ipa, "w") as archive:
                for screen, scale in (("screen-med", 1), ("screen-xlarge", 2)):
                    prefix = f"Payload/MOTU.app/{screen}"
                    archive.writestr(f"{prefix}/maps/Fake.map", med_map)
                    archive.writestr(f"{prefix}/tilesets/collision.tileset",
                                     synthetic_tileset(scale))
                    archive.writestr(f"{prefix}/textures/collisionTiles.png",
                                     synthetic_texture(scale))
            with self.assertRaisesRegex(ValueError, "exactly one"):
                compare_screen_pair(ipa, "Fake.map")

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
            with patch("heman_tools.collision_atlas_alpha.Path.cwd", return_value=root):
                with self.assertRaisesRegex(ValueError, "symbolic link"):
                    private_output_path(link)

    def test_cli_writes_only_private_report(self):
        with TemporaryDirectory() as directory:
            ipa = Path(directory) / "synthetic.ipa"
            write_synthetic_ipa(ipa)
            output = Path.cwd() / "local_reports" / "stage257-synthetic-test.json"
            try:
                result = main([
                    "--ipa", str(ipa), "--map", "Fake.map",
                    "--compare-screens", "--out", str(output),
                ])
                self.assertEqual(result, 0)
                report = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(report["result"], "cross_screen_alpha_census_complete")
            finally:
                output.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
