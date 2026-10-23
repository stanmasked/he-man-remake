"""Stage219 asset-free nearest-neighbor resolution comparison tests."""
import unittest

from heman_tools.cpu_resolution_pixel_comparator import (
    ResolutionPixelComparisonError,
    compare_naive_twofold_resolution_rgba,
)


class CPUResolutionPixelComparatorTests(unittest.TestCase):
    def test_exact_twofold_pixels_yield_full_agreement(self):
        low = bytes([8, 16, 24, 255])
        high = low * 4
        data = compare_naive_twofold_resolution_rgba(1, 1, low, 2, 2, high)
        result = data.to_public_safe_summary()
        self.assertEqual(result["compared_pixels"], 4)
        self.assertEqual(result["exact_rgba_pixels"], 4)
        self.assertEqual(result["visible_exact_rgba_fraction"], 1.0)
        self.assertEqual(result["alpha_agreement_fraction"], 1.0)
        self.assertEqual(result["mean_channel_absolute_difference"], 0.0)
        self.assertFalse(result["native_gpu_sampling_verified"])
        self.assertFalse(result["original_ios_runtime_frame_parity_verified"])

    def test_pixel_value_differs_without_geometry_diff(self):
        low = bytes([8, 16, 24, 255])
        high = low * 3 + bytes([9, 16, 24, 0])
        report = compare_naive_twofold_resolution_rgba(
            1, 1, low, 2, 2, high
        ).to_public_safe_summary()
        self.assertEqual(report["compared_pixels"], 4)
        self.assertEqual(report["exact_rgba_pixels"], 3)
        self.assertEqual(report["alpha_equal_pixels"], 3)
        self.assertEqual(report["visible_union_pixels"], 4)
        self.assertEqual(report["visible_exact_rgba_fraction"], 0.75)
        self.assertEqual(report["mean_channel_absolute_difference"], 16.0)

    def test_transparent_pairs_do_not_fabricate_visible_evidence(self):
        low = bytes([0, 0, 0, 0])
        result = compare_naive_twofold_resolution_rgba(
            1, 1, low, 2, 2, low * 4
        ).to_public_safe_summary()
        self.assertIsNone(result["visible_exact_rgba_fraction"])
        self.assertEqual(result["visible_union_pixels"], 0)
        self.assertEqual(result["exact_rgba_fraction"], 1.0)

    def test_strict_x_and_y_double_requirements(self):
        low = bytes([0, 0, 0, 0])
        with self.assertRaisesRegex(ResolutionPixelComparisonError, "exactly 2x"):
            compare_naive_twofold_resolution_rgba(1, 1, low, 3, 2, low * 6)
        with self.assertRaisesRegex(ResolutionPixelComparisonError, "exactly 2x"):
            compare_naive_twofold_resolution_rgba(1, 1, low, 2, 3, low * 6)

    def test_rejects_bool_dimensions_and_incomplete_buffers(self):
        low = bytes([0, 0, 0, 0])
        with self.assertRaisesRegex(ResolutionPixelComparisonError, "bounded positive"):
            compare_naive_twofold_resolution_rgba(True, 1, low, 2, 2, low * 4)
        with self.assertRaisesRegex(ResolutionPixelComparisonError, "lower-resolution"):
            compare_naive_twofold_resolution_rgba(1, 1, low[:3], 2, 2, low * 4)
        with self.assertRaisesRegex(ResolutionPixelComparisonError, "higher-resolution"):
            compare_naive_twofold_resolution_rgba(1, 1, low, 2, 2, low * 3)

    def test_bounded_pixel_budget(self):
        with self.assertRaisesRegex(ResolutionPixelComparisonError, "budget exceeded"):
            compare_naive_twofold_resolution_rgba(
                2049, 1024, b"", 4098, 2048, b""
            )

    def test_nearest_mapping_uses_correct_row_and_column(self):
        # A 2x2 palette with four distinct pixels must upscale as 2x2 blocks.
        colors = (
            bytes([11, 0, 0, 255]),
            bytes([22, 0, 0, 255]),
            bytes([33, 0, 0, 255]),
            bytes([44, 0, 0, 255]),
        )
        low = b"".join(colors)
        high = b"".join(
            colors[(y // 2) * 2 + x // 2]
            for y in range(4) for x in range(4)
        )
        result = compare_naive_twofold_resolution_rgba(
            2, 2, low, 4, 4, high
        ).to_public_safe_summary()
        self.assertEqual(result["exact_rgba_pixels"], 16)


if __name__ == "__main__":
    unittest.main()
