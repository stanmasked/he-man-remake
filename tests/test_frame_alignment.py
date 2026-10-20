"""Synthetic-only single-frame regression tests, no commercial assets."""
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from heman_tools.frame_alignment import fit_single_frame, _private_path, main


def synthetic():
    pts = [(0, 0), (10, 5), (40, 25), (90, 55), (20, 50)]
    return {"frame_id": "synthetic-frame-01", "anchors": [
        {"id": f"anchor-{i}", "level_xy": [x, y],
         "screen_xy": [2 * x + 20, -3 * y + 100]}
        for i, (x, y) in enumerate(pts)]}


class AlignmentTests(unittest.TestCase):
    def test_exact_known_transform(self):
        r = fit_single_frame(synthetic())
        self.assertEqual(r["level_to_screen_scale"], [2, -3])
        self.assertEqual(r["level_to_screen_offset_px"], [20, 100])
        self.assertEqual(r["max_residual_px"], 0)
        self.assertFalse(r["valid_across_frames"])
        self.assertFalse(r["physical_units_verified"])

    def test_bounded_measurement_noise(self):
        a = synthetic()
        a["anchors"][0]["screen_xy"][0] += .5
        self.assertLess(fit_single_frame(a, max_residual_px=1)["max_residual_px"], 1)

    def test_large_mismatched_anchor_fails(self):
        a = synthetic()
        a["anchors"][2]["screen_xy"][0] += 70
        with self.assertRaisesRegex(ValueError, "residual"):
            fit_single_frame(a)

    def test_insufficient_anchors(self):
        a = synthetic()
        a["anchors"] = a["anchors"][:3]
        with self.assertRaisesRegex(ValueError, "between 4"):
            fit_single_frame(a)

    def test_constant_x_is_not_calibratable(self):
        a = synthetic()
        for p in a["anchors"]:
            p["level_xy"][0] = 5
        with self.assertRaisesRegex(ValueError, "distinct"):
            fit_single_frame(a)

    def test_constant_y_is_not_calibratable(self):
        a = synthetic()
        for p in a["anchors"]:
            p["level_xy"][1] = 5
        with self.assertRaisesRegex(ValueError, "distinct"):
            fit_single_frame(a)

    def test_duplicate_anchor_id_fails(self):
        a = synthetic()
        a["anchors"][1]["id"] = a["anchors"][0]["id"]
        with self.assertRaisesRegex(ValueError, "unique"):
            fit_single_frame(a)

    def test_cross_frame_mixing_fails(self):
        a = synthetic()
        a["anchors"][2]["frame_id"] = "different-frame"
        with self.assertRaisesRegex(ValueError, "different"):
            fit_single_frame(a)

    def test_non_finite_number_rejected(self):
        for bad in (math.nan, math.inf, True):
            a = synthetic()
            a["anchors"][0]["level_xy"][0] = bad
            with self.assertRaises(ValueError):
                fit_single_frame(a)

    def test_bad_tolerance_rejected(self):
        for x in (0, -1, math.nan, 101, True):
            with self.assertRaises(ValueError):
                fit_single_frame(synthetic(), max_residual_px=x)

    def test_non_axis_aligned_rotation_rejected(self):
        a = synthetic()
        for p in a["anchors"]:
            x, y = p["level_xy"]
            p["screen_xy"] = [x - y + 30, x + y + 40]
        with self.assertRaisesRegex(ValueError, "residual"):
            fit_single_frame(a)

    def test_bad_frame_id_rejected(self):
        a = synthetic()
        a["frame_id"] = "\n"
        with self.assertRaises(ValueError):
            fit_single_frame(a)

    def test_private_only_destination(self):
        for p in ("docs/anchors.json", "local_reports/../report.json", "local_reports/data.txt"):
            with self.assertRaises(ValueError):
                _private_path(Path(p))

    def test_symlinked_report_root_rejected(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "other").mkdir()
            (root / "local_reports").symlink_to(root / "other", target_is_directory=True)
            with patch("heman_tools.frame_alignment.Path.cwd", return_value=root):
                with self.assertRaisesRegex(ValueError, "symbolic"):
                    _private_path(root / "local_reports" / "report.json")

    def test_cli_uses_only_ignored_local_json(self):
        root = Path.cwd() / "local_reports"
        root.mkdir(exist_ok=True)
        source = root / "synthetic-frame-alignment-input.json"
        output = root / "synthetic-frame-alignment-output.json"
        try:
            source.write_text(json.dumps(synthetic()), encoding="utf-8")
            self.assertEqual(main(["--anchors", str(source), "--out", str(output)]), 0)
            r = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(r["anchor_count"], 5)
            self.assertNotIn("anchors", r)
        finally:
            source.unlink(missing_ok=True)
            output.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
