"""Asset-free, fabricated multi-frame held-out alignment regressions."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from heman_tools.multiframe_heldout import main, validate_multiframe_holdout


_TRAIN = [(0, 0), (10, 5), (40, 25), (90, 55), (20, 50)]
_RESERVED = [(30, 70), (75, 15), (100, 80)]


def synthetic():
    frames = []
    for i, (dx, dy) in enumerate(((20, 100), (50, -15), (-15, 70))):
        def anchors(points, prefix):
            return [
                {"id": f"{prefix}-{index}", "level_xy": [x, y],
                 "screen_xy": [2 * x + dx, -3 * y + dy]}
                for index, (x, y) in enumerate(points)
            ]
        frames.append({
            "frame_id": f"fictional-{i}",
            "anchors": anchors(_TRAIN, "train"),
            "holdout_anchors": anchors(_RESERVED, "reserve"),
        })
    return {"frames": frames}


class MultiFrameHeldoutTests(unittest.TestCase):
    def test_stationary_landmarks_with_moving_camera(self):
        result = validate_multiframe_holdout(synthetic())
        self.assertEqual(result["frame_count"], 3)
        self.assertEqual(result["training_landmarks_per_frame"], 5)
        self.assertEqual(result["heldout_landmarks_per_frame"], 3)
        self.assertEqual(result["reference_scale"], [2, -3])
        self.assertEqual(result["max_relative_scale_drift"], 0)
        self.assertFalse(result["actual_landmark_identity_verified"])
        self.assertFalse(result["collision_geometry_verified"])

    def test_order_of_landmarks_irrelevant(self):
        v = synthetic()
        v["frames"][1]["anchors"].reverse()
        v["frames"][1]["holdout_anchors"].reverse()
        self.assertTrue(validate_multiframe_holdout(v)["crossframe_heldout_numeric_consistency_passed"])

    def test_corrupted_heldout_not_masked_by_perfect_training(self):
        v = synthetic()
        v["frames"][2]["holdout_anchors"][1]["screen_xy"][0] += 30
        with self.assertRaisesRegex(ValueError, "held-out residual"):
            validate_multiframe_holdout(v)

    def test_corrupted_training_rejected(self):
        v = synthetic()
        v["frames"][0]["anchors"][3]["screen_xy"][1] -= 20
        with self.assertRaisesRegex(ValueError, "anchor residual"):
            validate_multiframe_holdout(v)

    def test_full_zoom_rejected_despite_per_frame_perfect_fit(self):
        v = synthetic()
        for p in v["frames"][1]["anchors"] + v["frames"][1]["holdout_anchors"]:
            x, y = p["level_xy"]
            p["screen_xy"] = [3*x+50, -3*y-15]
        with self.assertRaisesRegex(ValueError, "scale drift"):
            validate_multiframe_holdout(v)

    def test_axis_flip_rejected(self):
        v = synthetic()
        for p in v["frames"][1]["anchors"] + v["frames"][1]["holdout_anchors"]:
            x, y = p["level_xy"]
            p["screen_xy"] = [-2*x+50, -3*y-15]
        with self.assertRaisesRegex(ValueError, "scale drift"):
            validate_multiframe_holdout(v)

    def test_changed_training_id_rejected(self):
        v = synthetic()
        v["frames"][1]["anchors"][1]["id"] = "new-id"
        with self.assertRaisesRegex(ValueError, "landmark IDs"):
            validate_multiframe_holdout(v)

    def test_changed_reserved_id_rejected(self):
        v = synthetic()
        v["frames"][1]["holdout_anchors"][1]["id"] = "other"
        with self.assertRaisesRegex(ValueError, "landmark IDs"):
            validate_multiframe_holdout(v)

    def test_changed_heldout_level_coordinate_rejected(self):
        v = synthetic()
        # Preserve the same screen mapping so the local held-out residual is
        # still exactly zero; the cross-frame identity gate must detect it.
        v["frames"][2]["holdout_anchors"][0]["level_xy"][0] += 1
        v["frames"][2]["holdout_anchors"][0]["screen_xy"][0] += 2
        with self.assertRaisesRegex(ValueError, "landmark IDs"):
            validate_multiframe_holdout(v)

    def test_changed_training_coordinate_rejected(self):
        v = synthetic()
        v["frames"][2]["anchors"][1]["level_xy"][1] += 1
        v["frames"][2]["anchors"][1]["screen_xy"][1] -= 3
        with self.assertRaisesRegex(ValueError, "landmark IDs"):
            validate_multiframe_holdout(v)

    def test_duplicate_training_positions_rejected(self):
        v = synthetic()
        v["frames"][0]["anchors"][1]["level_xy"] = v["frames"][0]["anchors"][0]["level_xy"]
        v["frames"][0]["anchors"][1]["screen_xy"] = v["frames"][0]["anchors"][0]["screen_xy"]
        with self.assertRaisesRegex(ValueError, "duplicate training source positions"):
            validate_multiframe_holdout(v)

    def test_duplicate_reserved_positions_rejected(self):
        v = synthetic()
        v["frames"][1]["holdout_anchors"][1]["level_xy"] = (
            v["frames"][1]["holdout_anchors"][0]["level_xy"])
        with self.assertRaises(ValueError):
            validate_multiframe_holdout(v)

    def test_duplicate_frame_id_rejected(self):
        v = synthetic()
        v["frames"][1]["frame_id"] = v["frames"][0]["frame_id"]
        with self.assertRaisesRegex(ValueError, "duplicate frame"):
            validate_multiframe_holdout(v)

    def test_single_frame_rejected(self):
        v = synthetic()
        v["frames"] = v["frames"][:1]
        with self.assertRaisesRegex(ValueError, "2 to 32"):
            validate_multiframe_holdout(v)

    def test_33_frames_rejected(self):
        v = synthetic()
        v["frames"] = v["frames"] * 11
        with self.assertRaisesRegex(ValueError, "2 to 32"):
            validate_multiframe_holdout(v)

    def test_invalid_relative_tolerance_rejected(self):
        for invalid in (0, -0.01, 0.3, True, float("nan")):
            with self.subTest(value=repr(invalid)), self.assertRaises(ValueError):
                validate_multiframe_holdout(synthetic(), max_relative_scale_drift=invalid)

    def test_small_measurement_noise_passes(self):
        v = synthetic()
        v["frames"][1]["holdout_anchors"][0]["screen_xy"][0] += .2
        report = validate_multiframe_holdout(v, max_holdout_residual_px=.5)
        self.assertGreater(report["frame_heldout_max_residual_px"][1], 0)

    def test_cli_writes_only_private_aggregate(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            private = root / "local_reports"
            private.mkdir()
            source, out = private/"observations.json", private/"result.json"
            source.write_text(json.dumps(synthetic()), encoding="utf-8")
            with patch("heman_tools.frame_alignment.Path.cwd", return_value=root):
                self.assertEqual(main(["--frames", str(source), "--out", str(out)]), 0)
            report = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(report["frame_count"], 3)
            self.assertNotIn("level_xy", out.read_text())
            self.assertNotIn("holdout_anchors", out.read_text())

    def test_private_paths_reject_external_output(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            private = root/"local_reports"
            private.mkdir()
            source = private/"input.json"
            source.write_text(json.dumps(synthetic()), encoding="utf-8")
            with patch("heman_tools.frame_alignment.Path.cwd", return_value=root):
                with self.assertRaisesRegex(ValueError, "local_reports"):
                    main(["--frames", str(source), "--out", str(root/"external.json")])

    def test_cli_input_output_alias_rejected(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            private = root/"local_reports"
            private.mkdir()
            source = private/"input.json"
            source.write_text(json.dumps(synthetic()), encoding="utf-8")
            with patch("heman_tools.frame_alignment.Path.cwd", return_value=root):
                with self.assertRaisesRegex(ValueError, "distinct"):
                    main(["--frames", str(source), "--out", str(source)])


if __name__ == "__main__":
    unittest.main()
