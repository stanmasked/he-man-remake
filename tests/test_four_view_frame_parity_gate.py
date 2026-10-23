"""Synthetic-only Stage218 four-view CPU report contract regressions."""
from __future__ import annotations

from copy import deepcopy
import unittest

from heman_tools.four_view_frame_parity_gate import (
    FourViewFrameGateError, summarize_four_view_frame_parity,
)


def _frames():
    return [
        {
            "screen": screen, "direction": direction,
            "source_symbol_count": 2, "resolved_symbol_count": 2,
            "cpu_frame_packet_count": 2,
            "output_width": (93 if screen == "screen-med" else 186),
            "output_height": (119 if screen == "screen-med" else 238),
            "gpu_submission_verified": False,
            "original_runtime_pixel_parity_verified": False,
            "source_local_transform_counts": {
                "negative_scale_x": 2 if direction == "west" else 0
            },
        }
        for screen in ("screen-med", "screen-xlarge")
        for direction in ("east", "west")
    ]


class FourViewFrameParityTests(unittest.TestCase):
    def test_complete_synthetic_four_views_can_show_exact_two_to_one_extent(self):
        result = summarize_four_view_frame_parity(_frames())
        self.assertEqual(result["frame_count"], 4)
        self.assertEqual(result["paired_resolution_directions_checked"], 2)
        self.assertTrue(result["all_resolution_packet_counts_match"])
        self.assertTrue(result["all_cropped_dimensions_exactly_doubled"])
        self.assertFalse(result["original_runtime_pixel_parity_verified"])
        self.assertFalse(result["runtime_player_transform_recovered"])
        self.assertFalse(result["camera_coordinates_recovered"])
        self.assertFalse(result["pixel_arrays_examined"])
        self.assertFalse(result["source_identifiers_exported"])
        self.assertTrue(all(c["negative_x_scale_count_match"] for c in result["comparisons"]))

    def test_input_order_does_not_change_aggregate(self):
        frames = _frames()
        self.assertEqual(summarize_four_view_frame_parity(frames),
                         summarize_four_view_frame_parity(list(reversed(frames))))

    def test_nonmatching_size_is_reported_not_invented(self):
        frames = _frames()
        frames[2]["output_width"] += 1
        result = summarize_four_view_frame_parity(frames)
        self.assertFalse(result["all_cropped_dimensions_exactly_doubled"])
        self.assertFalse(result["comparisons"][0]["cropped_width_exactly_doubled"])
        self.assertTrue(result["comparisons"][1]["cropped_width_exactly_doubled"])

    def test_nonmatching_symbol_counts_are_not_hidden(self):
        frames = _frames()
        frames[2]["source_symbol_count"] = 3
        result = summarize_four_view_frame_parity(frames)
        self.assertFalse(result["comparisons"][0]["source_symbol_count_match"])
        self.assertTrue(result["all_resolution_packet_counts_match"])

    def test_duplicate_or_missing_view_fails_closed(self):
        frames = _frames()
        frames[3] = deepcopy(frames[0])
        with self.assertRaisesRegex(FourViewFrameGateError, "Duplicate"):
            summarize_four_view_frame_parity(frames)
        with self.assertRaisesRegex(FourViewFrameGateError, "Exactly four"):
            summarize_four_view_frame_parity(frames[:3])

    def test_false_runtime_parity_claim_is_rejected(self):
        frames = _frames()
        frames[0]["original_runtime_pixel_parity_verified"] = True
        with self.assertRaisesRegex(FourViewFrameGateError, "runtime/GPU parity"):
            summarize_four_view_frame_parity(frames)
        frames[0]["original_runtime_pixel_parity_verified"] = False
        frames[0]["gpu_submission_verified"] = True
        with self.assertRaisesRegex(FourViewFrameGateError, "runtime/GPU parity"):
            summarize_four_view_frame_parity(frames)

    def test_bad_numeric_counts_and_packet_counts_are_rejected(self):
        cases = (
            ("output_width", True, "bounded integer"),
            ("output_height", 0, "bounded integer"),
            ("source_symbol_count", 1025, "bounded integer"),
            ("resolved_symbol_count", 3, "inconsistent"),
            ("cpu_frame_packet_count", -1, "bounded integer"),
        )
        for field, value, error in cases:
            with self.subTest(field=field):
                frames = _frames()
                frames[0][field] = value
                with self.assertRaisesRegex(FourViewFrameGateError, error):
                    summarize_four_view_frame_parity(frames)

    def test_cropped_pixel_budget_bound(self):
        frames = _frames()
        frames[0]["output_width"] = 2049
        frames[0]["output_height"] = 2049
        with self.assertRaisesRegex(FourViewFrameGateError, "pixel budget"):
            summarize_four_view_frame_parity(frames)

    def test_unknown_pair_rejected(self):
        frames = _frames()
        frames[0]["direction"] = "north"
        with self.assertRaisesRegex(FourViewFrameGateError, "Unknown"):
            summarize_four_view_frame_parity(frames)

    def test_local_mirroring_optional_and_never_infers_scene(self):
        frames = _frames()
        frames[0].pop("source_local_transform_counts")
        result = summarize_four_view_frame_parity(frames)
        self.assertIsNone(result["comparisons"][0]["negative_x_scale_count_match"])
        self.assertFalse(result["camera_coordinates_recovered"])
        self.assertFalse(result["original_runtime_pixel_parity_verified"])


if __name__ == "__main__":
    unittest.main()
