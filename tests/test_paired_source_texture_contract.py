"""Stage220 public synthetic-only texture-pair census regression tests."""
from __future__ import annotations

from copy import deepcopy
import unittest

from heman_tools.paired_source_texture_contract import (
    PairedTextureCensusError, summarize_texture_resolution_pairs,
)


def _pair(*, low=(2, 1), high=(4, 2), same=True, visible=5):
    record = {
        "path": "invented/source/path/should-never-export.png",
        "med_dimensions": list(low),
        "xlarge_dimensions": list(high),
    }
    if high == (low[0] * 2, low[1] * 2):
        pixels = high[0] * high[1]
        exact = pixels if same else pixels - 1
        record.update({
            "compared_pixels": pixels,
            "exact_pixels": exact,
            "visible_union_pixels": min(visible, pixels),
            "visible_exact_pixels": max(0, min(visible, exact) - (0 if same else 1)),
            "alpha_equal_pixels": pixels - (0 if same else 1),
        })
    return record


class TexturePairContractTests(unittest.TestCase):
    def test_valid_mixed_dimensions_are_summarized_without_source_paths(self):
        records = [_pair(), _pair(same=False), _pair(high=(3, 2))]
        report = summarize_texture_resolution_pairs(records)
        self.assertEqual(report["paired_texture_count"], 3)
        self.assertEqual(report["exact_2x_dimension_pairs"], 2)
        self.assertEqual(report["non_2x_dimension_pairs"], 1)
        self.assertEqual(report["exact_2x_pixel_identical_texture_pairs"], 1)
        self.assertEqual(report["exact_2x_pixel_different_texture_pairs"], 1)
        self.assertEqual(report["pixel_count_compared"], 16)
        self.assertEqual(report["exact_rgba_fraction"], 0.9375)
        self.assertEqual(report["visible_exact_rgba_fraction"], 0.9)
        self.assertEqual(report["alpha_agreement_fraction"], 0.9375)
        self.assertFalse(report["per_asset_details_exported"])
        self.assertFalse(report["original_ios_runtime_frame_parity_verified"])
        self.assertNotIn("invented/source/path", str(report))

    def test_order_independent_histogram_and_weighted_fraction(self):
        records = [
            _pair(low=(1, 1), high=(2, 2), same=True),
            _pair(low=(4, 4), high=(8, 8), same=False),
            _pair(low=(3, 4), high=(6, 7)),
        ]
        self.assertEqual(
            summarize_texture_resolution_pairs(records),
            summarize_texture_resolution_pairs(list(reversed(records))),
        )
        report = summarize_texture_resolution_pairs(records)
        self.assertEqual(report["pixel_count_compared"], 68)
        self.assertEqual(report["exact_rgba_fraction"], round(67 / 68, 6))

    def test_only_non_double_pairs_have_no_claimed_pixels(self):
        report = summarize_texture_resolution_pairs([_pair(high=(5, 3))])
        self.assertEqual(report["non_2x_dimension_pairs"], 1)
        self.assertEqual(report["pixel_count_compared"], 0)
        self.assertIsNone(report["exact_rgba_fraction"])
        self.assertIsNone(report["alpha_agreement_fraction"])

    def test_empty_visible_union_has_no_invented_agreement(self):
        report = summarize_texture_resolution_pairs([_pair(visible=0)])
        self.assertIsNone(report["visible_exact_rgba_fraction"])

    def test_inconsistent_comparison_counts_fail_closed(self):
        record = _pair()
        record["compared_pixels"] = 7
        with self.assertRaisesRegex(PairedTextureCensusError, "source dimensions"):
            summarize_texture_resolution_pairs([record])

    def test_invalid_visible_exact_counts_fail_closed(self):
        record = _pair(same=False)
        record["visible_exact_pixels"] = 8
        with self.assertRaisesRegex(PairedTextureCensusError, "Visible exact"):
            summarize_texture_resolution_pairs([record])

    def test_bool_dimension_and_negative_counts_are_rejected(self):
        wrong = _pair()
        wrong["med_dimensions"] = [True, 1]
        with self.assertRaisesRegex(PairedTextureCensusError, "bounded integer"):
            summarize_texture_resolution_pairs([wrong])
        wrong = _pair()
        wrong["alpha_equal_pixels"] = -1
        with self.assertRaisesRegex(PairedTextureCensusError, "bounded integer"):
            summarize_texture_resolution_pairs([wrong])

    def test_pixel_claims_on_non_double_dimensions_rejected(self):
        record = _pair(high=(3, 2))
        record["compared_pixels"] = 6
        with self.assertRaisesRegex(PairedTextureCensusError, "must not claim"):
            summarize_texture_resolution_pairs([record])

    def test_invalid_shape_and_record_types_rejected(self):
        for values in ([], [{}], [None], [{"med_dimensions": [2, 3]}]):
            with self.subTest(value=str(values)):
                with self.assertRaises(PairedTextureCensusError):
                    summarize_texture_resolution_pairs(values)

    def test_large_pair_count_is_bounded(self):
        with self.assertRaisesRegex(PairedTextureCensusError, "bounded nonempty"):
            summarize_texture_resolution_pairs([_pair(high=(3, 2))] * 4097)


if __name__ == "__main__":
    unittest.main()
