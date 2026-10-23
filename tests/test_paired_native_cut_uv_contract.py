"""Stage221 synthetic native UV/power-of-two allocation regression tests."""
from copy import deepcopy
import unittest

from heman_tools.paired_native_cut_uv_contract import (
    NativeCutUVPairError, summarize_native_uv_resolution_pairs,
)


def _pair(
    rect=(2, 2, 4, 4), medium=(12, 12), xlarge=(24, 24),
    med_wrap=(0, 0), xlarge_wrap=(0, 0),
):
    return {
        "private_source_name": "do-not-export/invented-secret-image.png",
        "med_rect": list(rect),
        "xlarge_rect": [2 * v for v in rect],
        "med_png": list(medium),
        "xlarge_png": list(xlarge),
        "med_wrap": list(med_wrap),
        "xlarge_wrap": list(xlarge_wrap),
    }


class NativeCutUVResolutionPairTests(unittest.TestCase):
    def test_exactly_doubled_rect_and_allocations_have_matching_native_uv(self):
        result = summarize_native_uv_resolution_pairs([_pair()])
        self.assertEqual(result["paired_cut_count"], 1)
        self.assertEqual(result["rectangles_exactly_2x_count"], 1)
        self.assertEqual(result["allocated_dimensions_exactly_2x_count"], 1)
        self.assertEqual(result["uv_endpoints_equal_within_1e_7_count"], 1)
        self.assertEqual(result["per_pack"]["screen-med"]["inside_raw_png"], 1)
        self.assertFalse(result["source_path_keys_rectangles_uvs_or_pixels_exported"])
        self.assertFalse(result["original_ios_gpu_pixel_parity_verified"])
        self.assertNotIn("do-not-export", str(result))
        self.assertNotIn("med_rect", str(result))

    def test_cut_can_fit_only_allocated_pow2_padding_without_inventing_pixels(self):
        result = summarize_native_uv_resolution_pairs([
            _pair(rect=(2, 2, 2, 2), medium=(3, 3), xlarge=(6, 6))
        ])
        for screen in ("screen-med", "screen-xlarge"):
            self.assertEqual(result["per_pack"][screen]["fits_allocated_only"], 1)
            self.assertEqual(result["per_pack"][screen]["allocated_differs_from_png"], 1)
        self.assertEqual(result["uv_endpoints_equal_within_1e_7_count"], 1)
        self.assertFalse(result["allocated_padding_pixels_invented"])
        self.assertFalse(result["outside_source_rectangles_clipped_or_repaired"])

    def test_non_doubled_allocation_changes_uv_even_when_cut_rectangles_double(self):
        # 65 -> allocated 128, but 128 -> allocated 128 on the larger pack.
        result = summarize_native_uv_resolution_pairs([
            _pair(medium=(65, 64), xlarge=(128, 128))
        ])
        self.assertEqual(result["rectangles_exactly_2x_count"], 1)
        self.assertEqual(result["allocated_dimensions_exactly_2x_count"], 0)
        self.assertEqual(result["uv_endpoints_equal_within_1e_7_count"], 0)
        self.assertEqual(
            result["uv_mismatch_with_doubled_rect_and_non_doubled_allocation_count"], 1
        )
        self.assertEqual(result["uv_mismatch_other_count"], 0)

    def test_outside_even_allocated_is_reported_not_clipped(self):
        result = summarize_native_uv_resolution_pairs([
            _pair(rect=(3, 1, 2, 2), medium=(4, 4), xlarge=(8, 8),
                  med_wrap=(1, 0), xlarge_wrap=(1, 0))
        ])
        for screen in ("screen-med", "screen-xlarge"):
            self.assertEqual(result["per_pack"][screen]["outside_even_allocated"], 1)
            self.assertEqual(result["per_pack"][screen]["uv_endpoint_outside_0_to_1"], 1)
            self.assertEqual(result["per_pack"][screen]["wrap_s_repeat_count"], 1)
        self.assertEqual(result["uv_endpoints_equal_within_1e_7_count"], 1)

    def test_invalid_original_source_rectangle_is_counted_not_repaired(self):
        result = summarize_native_uv_resolution_pairs([
            _pair(rect=(-1, 0, 2, 2), medium=(4, 4), xlarge=(8, 8))
        ])
        self.assertEqual(result["per_pack"]["screen-med"]["invalid_original_rectangle"], 1)
        self.assertEqual(result["per_pack"]["screen-xlarge"]["invalid_original_rectangle"], 1)
        self.assertFalse(result["outside_source_rectangles_clipped_or_repaired"])

    def test_nondoubled_cut_rectangles_are_explicitly_reported(self):
        pair = _pair()
        pair["xlarge_rect"][2] += 1
        result = summarize_native_uv_resolution_pairs([pair])
        self.assertEqual(result["rectangles_exactly_2x_count"], 0)
        self.assertEqual(result["uv_endpoints_equal_within_1e_7_count"], 0)
        self.assertEqual(result["uv_mismatch_other_count"], 1)

    def test_pair_order_independent_and_wrap_difference_not_hidden(self):
        one = _pair()
        two = _pair(rect=(0, 0, 2, 2), xlarge_wrap=(1, 0))
        result = summarize_native_uv_resolution_pairs([one, two])
        self.assertEqual(result, summarize_native_uv_resolution_pairs([two, one]))
        self.assertEqual(result["wrap_codes_identical_across_packs_count"], 1)

    def test_source_names_are_discarded_from_aggregate(self):
        pair = _pair()
        pair["key"] = "private serial key"
        pair["original_byte_offset"] = 12345
        report = summarize_native_uv_resolution_pairs([pair])
        self.assertNotIn("private serial", str(report))
        self.assertNotIn("12345", str(report))
        self.assertNotIn("key", str(report))

    def test_bools_or_bad_shapes_rejected_before_native_uv(self):
        cases = (
            ("med_rect", [True, 2, 4, 4]),
            ("xlarge_rect", [4, 4, 8]),
            ("med_png", [False, 12]),
            ("xlarge_png", [0, 1]),
            ("med_wrap", [2, 0]),
            ("xlarge_wrap", [0, True]),
        )
        for field, value in cases:
            with self.subTest(field=field):
                pair = _pair()
                pair[field] = value
                with self.assertRaises(NativeCutUVPairError):
                    summarize_native_uv_resolution_pairs([pair])

    def test_empty_duplicate_large_or_nonmapping_inputs_rejected(self):
        for pairs in ([], [_pair()] * 5001, [None], "source"):
            with self.subTest(size=len(pairs)):
                with self.assertRaises(NativeCutUVPairError):
                    summarize_native_uv_resolution_pairs(pairs)

    def test_large_source_cut_bounds_are_float32_and_never_extrapolated(self):
        pair = _pair(rect=(20, 20, 40, 40), medium=(127, 127),
                     xlarge=(255, 255))
        result = summarize_native_uv_resolution_pairs([pair])
        self.assertEqual(result["allocated_dimensions_exactly_2x_count"], 1)
        self.assertEqual(result["uv_endpoints_equal_within_1e_7_count"], 1)


if __name__ == "__main__":
    unittest.main()
