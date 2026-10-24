"""Only fabricated polygons, tilesets and PNGs are used in Stage266 CI."""
from __future__ import annotations

import io
import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import zipfile

from PIL import Image

from heman_tools.collision_polygon_alpha_parity import (
    _inside_polygon,
    _compare_polygon_to_alpha,
    inspect_private_geometry_alpha_parity,
    main,
)
from heman_tools.shapes import Shape
from test_collision_geometry_name_link import fictional_tileset, fictional_map


def fictional_polygon(points):
    out = struct.pack("<IIHI", 0, 0, 0, len(points))
    for x, y in points:
        out += struct.pack("<ff", x, y)
    return out


TRIANGLE = ((0., 0.), (32., 0.), (0., 32.))
BOX = ((0., 0.), (32., 0.), (32., 32.), (0., 32.))


def fictional_png(scale, *, introduce_error=False):
    image = Image.new("RGBA", (4 * 32 * scale, 32 * scale), (255, 0, 0, 0))
    for y in range(32 * scale):
        for x in range(32 * scale):
            if _inside_polygon((x + 0.5) / scale, (y + 0.5) / scale, TRIANGLE):
                image.putpixel((x, y), (255, 0, 0, 255))
            image.putpixel((3 * 32 * scale + x, y), (255, 0, 0, 255))
    if introduce_error:
        image.putpixel((0, 0), (255, 0, 0, 0))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def write_fictional_ipa(path, *, corrupt_one_pixel=False,
                        omit_used_shape=False, change_shape_bytes=False,
                        change_map=False):
    with zipfile.ZipFile(path, "w") as archive:
        for screen, scale in (("screen-med", 1), ("screen-xlarge", 2)):
            root = f"Payload/MOTU.app/{screen}/"
            archive.writestr(root + "maps/Fiction.map",
                             fictional_map(1 if change_map and scale == 2 else 0))
            archive.writestr(root + "tilesets/collision.tileset",
                             fictional_tileset(scale))
            archive.writestr(
                root + "textures/collisionTiles.png",
                fictional_png(scale, introduce_error=corrupt_one_pixel and scale == 2)
            )
            archive.writestr(root + "geometry/synth_ramp_A.shape",
                             fictional_polygon(TRIANGLE))
            if not omit_used_shape:
                points = BOX if not(change_shape_bytes and scale == 2) else (
                    (0., 0.), (32., 0.), (32., 31.), (0., 31.))
                archive.writestr(root + "geometry/synth_ramp_B.shape",
                                 fictional_polygon(points))
            archive.writestr(root + "geometry/synth_badrefshape",
                             b"fabricated near-name mismatch only")


class CollisionPolygonAlphaTests(unittest.TestCase):
    def test_evenodd_polygon_center_rule(self):
        self.assertTrue(_inside_polygon(0.5, 0.5, TRIANGLE))
        self.assertFalse(_inside_polygon(31.5, 31.5, TRIANGLE))
        self.assertTrue(_inside_polygon(16, 16, BOX))

    def test_fabricated_image_and_polygon_match(self):
        with TemporaryDirectory() as tmp:
            ipa = Path(tmp) / "fabricated.ipa"
            write_fictional_ipa(ipa)
            report = inspect_private_geometry_alpha_parity(ipa, "Fiction.map")
        self.assertEqual(report["result"], "polygon_alpha_comparison_complete")
        self.assertEqual(report["screen_med"]["linked_used_shapes"], 2)
        self.assertEqual(report["screen_med"]["raster_compared_polygon_count"], 2)
        self.assertEqual(report["screen_med"]["unresolved_used_shape_count"], 0)
        self.assertEqual(report["screen_med"]["aggregate_polygon_alpha_iou"], 1)
        self.assertEqual(report["screen_xlarge"]["aggregate_polygon_alpha_iou"], 1)
        self.assertEqual(report["screen_med"]["mismatched_pixels"], 0)
        self.assertTrue(report["cross_screen"]["linked_used_geometry_bytes_equal"])
        self.assertFalse(report["native_switch_collision_import_authorized"])
        data = json.dumps(report)
        for token in ("synth_ramp", "fabricated near-name", "vertices", "pixels_array"):
            # JSON keys never include source geometry vertices or bitmap arrays.
            if token == "vertices":
                self.assertNotIn('"vertices":', data)
            else:
                self.assertNotIn(token, data)

    def test_alpha_difference_is_reported_without_claiming_parity(self):
        with TemporaryDirectory() as tmp:
            ipa = Path(tmp) / "fabricated.ipa"
            write_fictional_ipa(ipa, corrupt_one_pixel=True)
            report = inspect_private_geometry_alpha_parity(ipa, "Fiction.map")
        self.assertEqual(report["screen_med"]["mismatched_pixels"], 0)
        self.assertGreater(report["screen_xlarge"]["mismatched_pixels"], 0)
        self.assertLess(report["screen_xlarge"]["aggregate_polygon_alpha_iou"], 1)
        self.assertFalse(report["polygon_and_image_overlap_is_runtime_collisions_proof"])

    def test_differing_shape_source_is_rejected(self):
        with TemporaryDirectory() as tmp:
            ipa = Path(tmp) / "fabricated.ipa"
            write_fictional_ipa(ipa, change_shape_bytes=True)
            with self.assertRaisesRegex(ValueError, "Stage265 parity"):
                inspect_private_geometry_alpha_parity(ipa, "Fiction.map")

    def test_missing_used_shape_is_not_called_complete(self):
        with TemporaryDirectory() as tmp:
            ipa = Path(tmp) / "fabricated.ipa"
            write_fictional_ipa(ipa, omit_used_shape=True)
            report = inspect_private_geometry_alpha_parity(ipa, "Fiction.map")
        self.assertEqual(report["result"], "partial_used_geometry_unresolved")
        self.assertEqual(report["screen_med"]["unresolved_used_shape_count"], 1)

    def test_changed_map_bytes_fail_closed(self):
        with TemporaryDirectory() as tmp:
            ipa = Path(tmp) / "fabricated.ipa"
            write_fictional_ipa(ipa, change_map=True)
            with self.assertRaisesRegex(ValueError, "Stage265 parity"):
                inspect_private_geometry_alpha_parity(ipa, "Fiction.map")

    def test_direct_geometry_comparison_budget(self):
        picture = Image.new("RGBA", (16, 16), (0, 0, 0, 255))
        shape = Shape("polygon", 0, None,
                      ((0, 0), (16, 0), (16, 16), (0, 16)), None, None)
        with self.assertRaisesRegex(ValueError, "decoded PNG budget"):
            _compare_polygon_to_alpha(
                picture,
                {"x": 0, "y": 0, "width": 100000, "height": 100000},
                shape, 1
            )

    def test_private_cli_is_bounded_and_redacted(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "local_reports").mkdir()
            ipa = root / "fiction.ipa"
            write_fictional_ipa(ipa)
            target = root / "local_reports" / "stage266-synthetic.json"
            with patch("heman_tools.collision_atlas_alpha.Path.cwd", return_value=root):
                self.assertEqual(main([
                    "--ipa", str(ipa), "--map", "Fiction.map",
                    "--out", str(target)
                ]), 0)
            result = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(result["result"], "polygon_alpha_comparison_complete")
            self.assertFalse(result["original_runtime_geometry_loader_path_verified"])


if __name__ == "__main__":
    unittest.main()
