"""Synthetic held-out landmark tests; no real iOS coordinates or game assets."""
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from heman_tools.heldout_alignment import main, validate_holdout


def mock_sample():
    training = [(0, 0), (10, 5), (40, 25), (90, 55), (20, 50)]
    reserved = [(30, 70), (75, 15), (100, 80)]
    def point(prefix, i, x, y):
        return {"id": f"{prefix}-{i}", "level_xy": [x, y],
                "screen_xy": [2*x + 20, -3*y + 100]}
    return {
        "frame_id": "mock-frame-12",
        "anchors": [point("train", i, x, y)
                    for i, (x, y) in enumerate(training)],
        "holdout_anchors": [point("reserve", i, x, y)
                            for i, (x, y) in enumerate(reserved)],
    }


class HeldoutTests(unittest.TestCase):
    def test_independent_exact_consistency(self):
        result = validate_holdout(mock_sample())
        self.assertEqual(result["training_anchor_count"], 5)
        self.assertEqual(result["heldout_anchor_count"], 3)
        self.assertEqual(result["heldout_max_residual_px"], 0)
        self.assertEqual(result["fitted_scale"], [2, -3])
        self.assertTrue(result["heldout_numeric_consistency_passed"])
        self.assertFalse(result["landmark_identity_verified"])
        self.assertFalse(result["actual_collision_geometry_verified"])

    def test_corrupted_holdout_rejected_despite_perfect_fit(self):
        sample = mock_sample()
        sample["holdout_anchors"][1]["screen_xy"][0] += 20
        with self.assertRaisesRegex(ValueError, "held-out residual"):
            validate_holdout(sample)

    def test_noisy_heldout_within_tolerance(self):
        sample = mock_sample()
        sample["holdout_anchors"][0]["screen_xy"][1] += 0.5
        out = validate_holdout(sample, max_holdout_residual_px=0.6)
        self.assertAlmostEqual(out["heldout_max_residual_px"], 0.5)

    def test_corrupted_training_fails_even_if_holdout_exact(self):
        sample = mock_sample()
        sample["anchors"][0]["screen_xy"][0] += 20
        with self.assertRaisesRegex(ValueError, "anchor residual"):
            validate_holdout(sample)

    def test_heldout_optional_input_not_treated_as_training(self):
        sample = mock_sample()
        sample["holdout_anchors"] = sample["holdout_anchors"][:2]
        out = validate_holdout(sample)
        self.assertEqual(out["training_anchor_count"], 5)
        self.assertEqual(out["heldout_anchor_count"], 2)

    def test_must_have_two_heldout_points(self):
        sample = mock_sample()
        sample["holdout_anchors"] = sample["holdout_anchors"][:1]
        with self.assertRaisesRegex(ValueError, "2 to 32"):
            validate_holdout(sample)

    def test_duplicate_training_id_rejected(self):
        sample = mock_sample()
        sample["holdout_anchors"][0]["id"] = sample["anchors"][1]["id"]
        with self.assertRaisesRegex(ValueError, "disjoint"):
            validate_holdout(sample)

    def test_duplicate_heldout_id_rejected(self):
        sample = mock_sample()
        sample["holdout_anchors"][1]["id"] = sample["holdout_anchors"][0]["id"]
        with self.assertRaisesRegex(ValueError, "disjoint"):
            validate_holdout(sample)

    def test_heldout_location_cannot_repeat_training(self):
        sample = mock_sample()
        sample["holdout_anchors"][0]["level_xy"] = sample["anchors"][1]["level_xy"]
        with self.assertRaisesRegex(ValueError, "repeats"):
            validate_holdout(sample)

    def test_heldout_location_cannot_repeat_other_holdout(self):
        sample = mock_sample()
        sample["holdout_anchors"][1]["level_xy"] = sample["holdout_anchors"][0]["level_xy"]
        with self.assertRaisesRegex(ValueError, "repeats"):
            validate_holdout(sample)

    def test_frame_mismatch_rejected(self):
        sample = mock_sample()
        sample["holdout_anchors"][1]["frame_id"] = "different-frame"
        with self.assertRaisesRegex(ValueError, "different frame"):
            validate_holdout(sample)

    def test_nonfinite_and_bool_coordinates_rejected(self):
        for bad in (math.nan, math.inf, True):
            sample = mock_sample()
            sample["holdout_anchors"][0]["screen_xy"][0] = bad
            with self.subTest(bad=repr(bad)), self.assertRaises(ValueError):
                validate_holdout(sample)

    def test_bad_threshold_rejected(self):
        for bad in (-1, 0, math.nan, True, 110):
            with self.subTest(value=repr(bad)), self.assertRaises(ValueError):
                validate_holdout(mock_sample(), max_holdout_residual_px=bad)

    def test_oversized_heldout_set_rejected(self):
        sample = mock_sample()
        sample["holdout_anchors"] *= 12
        with self.assertRaisesRegex(ValueError, "2 to 32"):
            validate_holdout(sample)

    def test_missing_or_nonlist_heldout_rejected(self):
        for bad in (None, {}, "", 3):
            sample = mock_sample()
            sample["holdout_anchors"] = bad
            with self.subTest(bad=repr(bad)), self.assertRaises(ValueError):
                validate_holdout(sample)

    def test_private_cli_does_not_emit_raw_anchors(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            private = root/"local_reports"
            private.mkdir()
            inp, out = private/"anchors.json", private/"result.json"
            inp.write_text(json.dumps(mock_sample()), encoding="utf-8")
            with patch("heman_tools.frame_alignment.Path.cwd", return_value=root):
                self.assertEqual(main(["--anchors", str(inp), "--out", str(out)]), 0)
            result = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(result["heldout_anchor_count"], 3)
            self.assertNotIn("holdout_anchors", result)
            self.assertNotIn("level_xy", out.read_text())

    def test_private_cli_no_overwrite_input(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            private = root/"local_reports"
            private.mkdir()
            inp = private/"anchors.json"
            inp.write_text(json.dumps(mock_sample()), encoding="utf-8")
            with patch("heman_tools.frame_alignment.Path.cwd", return_value=root):
                with self.assertRaisesRegex(ValueError, "same private"):
                    main(["--anchors", str(inp), "--out", str(inp)])

    def test_cli_rejects_public_report_path(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            private = root/"local_reports"
            private.mkdir()
            inp = private/"anchors.json"
            inp.write_text(json.dumps(mock_sample()), encoding="utf-8")
            with patch("heman_tools.frame_alignment.Path.cwd", return_value=root):
                with self.assertRaisesRegex(ValueError, "local_reports"):
                    main(["--anchors", str(inp),
                          "--out", str(root/"public-report.json")])


if __name__ == "__main__":
    unittest.main()
