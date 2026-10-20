"""Fabricated alpha arrays and ZIPs only. No original game assets in CI."""
from pathlib import Path
import stat
import tempfile
import unittest
import warnings
import zipfile

from heman_tools.alpha_pack_parity import (
    _archive_bytes, compare_alpha_planes,
)


def nearest_2x(alpha, width, height):
    return bytes(alpha[(y // 2) * width + (x // 2)]
                 for y in range(2 * height) for x in range(2 * width))


class AlphaParityTests(unittest.TestCase):
    def sample(self):
        low = bytes([255, 0, 0, 255, 0, 255, 255, 0])
        return ((4, 2, low), (8, 4, nearest_2x(low, 4, 2)))

    def test_identical_2x_binary_masks(self):
        a, b = self.sample()
        report = compare_alpha_planes(a, b, 2, [0, 1])
        self.assertTrue(report["all_threshold_128_masks_identical"])
        self.assertEqual(report["tile_metrics"]["0"]["128"]["intersection_over_union"], 1.0)
        self.assertEqual(report["tile_metrics"]["1"]["128"]["mismatching_pixels"], 0)
        self.assertFalse(report["automatic_collision_export_permitted"])

    def test_changed_high_resolution_pixel_detected(self):
        a, (w, h, pixels) = self.sample()
        changed = bytearray(pixels)
        changed[0] = 0
        report = compare_alpha_planes(a, (w, h, bytes(changed)), 2, [0])
        self.assertEqual(report["tile_metrics"]["0"]["128"]["medium_only_pixels"], 1)
        self.assertFalse(report["all_threshold_128_masks_identical"])

    def test_new_high_resolution_opaque_pixel_detected(self):
        a, (w, h, pixels) = self.sample()
        changed = bytearray(pixels)
        changed[2] = 255
        report = compare_alpha_planes(a, (w, h, bytes(changed)), 2, [0])
        self.assertEqual(report["tile_metrics"]["0"]["128"]["xlarge_only_pixels"], 1)

    def test_threshold_sensitivity_explicit(self):
        report = compare_alpha_planes(
            (1, 1, bytes([128])), (2, 2, bytes([64, 127, 128, 192])),
            1, [0])
        self.assertEqual(report["tile_metrics"]["0"]["64"]["xlarge_opaque_pixels"], 4)
        self.assertEqual(report["tile_metrics"]["0"]["128"]["xlarge_opaque_pixels"], 2)
        self.assertEqual(report["tile_metrics"]["0"]["192"]["medium_opaque_pixels"], 0)
        self.assertEqual(report["tile_metrics"]["0"]["128"]["intersection_over_union"], 0.5)

    def test_both_empty_tiles_are_equal_without_divzero(self):
        report = compare_alpha_planes(
            (1, 1, bytes([0])), (2, 2, bytes(4)), 1, [0])
        self.assertEqual(report["tile_metrics"]["0"]["128"]["intersection_over_union"], 1.0)

    def test_fully_opaque_tiles(self):
        report = compare_alpha_planes(
            (2, 2, bytes([255] * 4)), (4, 4, bytes([255] * 16)),
            2, [0])
        self.assertTrue(report["all_threshold_128_masks_identical"])
        self.assertEqual(report["tile_metrics"]["0"]["128"]["intersection_pixels"], 16)

    def test_sorted_tile_ids_and_row_major(self):
        a = (2, 4, bytes([0, 0, 0, 0, 255, 255, 255, 255]))
        b = (4, 8, nearest_2x(a[2], 2, 4))
        report = compare_alpha_planes(a, b, 2, [1, 0])
        self.assertEqual(report["compared_tile_ids"], [0, 1])
        self.assertEqual(report["tile_metrics"]["0"]["128"]["medium_opaque_pixels"], 0)
        self.assertEqual(report["tile_metrics"]["1"]["128"]["medium_opaque_pixels"], 4)

    def test_invalid_alpha_bytes_length_rejected(self):
        _, b = self.sample()
        with self.assertRaises(ValueError):
            compare_alpha_planes((4, 2, b"bad"), b, 2, [0])

    def test_not_two_times_image_dimensions_rejected(self):
        a, _ = self.sample()
        with self.assertRaises(ValueError):
            compare_alpha_planes(a, (7, 4, bytes(28)), 2, [0])

    def test_invalid_non_divisible_medium_image_rejected(self):
        with self.assertRaises(ValueError):
            compare_alpha_planes((3, 2, bytes(6)), (6, 4, bytes(24)), 2, [0])

    def test_out_of_range_or_duplicate_tile_ids_rejected(self):
        a, b = self.sample()
        for ids in ([], [2], [0, 0], [-1], [True], [0.0]):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                compare_alpha_planes(a, b, 2, ids)

    def test_oversized_image_dimensions_rejected_before_processing(self):
        with self.assertRaises(ValueError):
            compare_alpha_planes((8193, 1, b"x"), (16386, 2, b"x"), 1, [0])

    def test_input_thresholds_never_claim_terrain_solidity(self):
        a, b = self.sample()
        report = compare_alpha_planes(a, b, 2, [0])
        self.assertIs(report["alpha_mask_means_solid_terrain"], False)
        self.assertIs(report["source_game_collision_semantics_verified"], False)
        self.assertIs(report["camera_or_scale_calibrated"], False)
        self.assertNotIn("mask_rows", str(report))
        self.assertNotIn("raw_alpha", str(report))

    def test_read_zip_selected_duplicate_name_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fabricated.zip"
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(path, "w") as z:
                    z.writestr("selected.png", b"alpha")
                    z.writestr("selected.png", b"other")
            with zipfile.ZipFile(path) as z:
                with self.assertRaisesRegex(ValueError, "duplicate"):
                    _archive_bytes(z, z.infolist(), "selected.png")

    def test_read_zip_selected_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fabricated.zip"
            with zipfile.ZipFile(path, "w") as z:
                item = zipfile.ZipInfo("selected.png")
                item.create_system = 3
                item.external_attr = (stat.S_IFLNK | 0o777) << 16
                z.writestr(item, b"fake-target")
            with zipfile.ZipFile(path) as z:
                with self.assertRaisesRegex(ValueError, "invalid"):
                    _archive_bytes(z, z.infolist(), "selected.png")

    def test_read_zip_selected_missing_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fabricated.zip"
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("another.map", b"fiction")
            with zipfile.ZipFile(path) as z:
                with self.assertRaisesRegex(ValueError, "missing"):
                    _archive_bytes(z, z.infolist(), "selected.png")


if __name__ == "__main__":
    unittest.main()
