"""Synthetic residual texture exception triage tests."""
import json
import unittest
from heman_tools.sprite_cut_png_bounds_census import SpriteCutBoundsError
from heman_tools.sprite_cut_residual_triage import triage_residuals


class ResidualTriageTests(unittest.TestCase):
    def test_separates_axes_and_preserves_unresolved_cases(self):
        med = {
            ("private-a", 0): ((16, 0, 1, 2), (10, 10)),
            ("private-b", 0): ((0, 16, 2, 1), (10, 10)),
            ("private-c", 0): ((16, 16, 1, 1), (10, 10)),
            ("private-d", 0): ((0, -1, 1, 1), (10, 10)),
            ("private-e", 0): ((0, 0, 1, 1), (10, 10)),
        }
        large = dict(med)
        result = triage_residuals(med, large)
        pack = result["per_pack"]["screen-med"]
        self.assertEqual((pack["outside_horizontal_only"],
                          pack["outside_vertical_only"],
                          pack["outside_both_axes"], pack["invalid"]), (1, 1, 1, 1))
        self.assertFalse(result["unresolved_cuts_renderable"])
        self.assertNotIn("private-a", json.dumps(result))

    def test_cross_pack_transition_counts(self):
        med = {("demo", 0): ((0, 0, 2, 2), (10, 10))}
        large = {("demo", 0): ((16, 0, 1, 1), (10, 10))}
        r = triage_residuals(med, large)
        self.assertEqual(r["paired_status_counts"]["inside_raw_med__outside_allocated_xlarge"], 1)

    def test_missing_paired_key_rejected(self):
        with self.assertRaisesRegex(SpriteCutBoundsError, "must match"):
            triage_residuals({("a", 0): ((0, 0, 1, 1), (4, 4))},
                             {("b", 0): ((0, 0, 1, 1), (4, 4))})

    def test_invalid_dimensions_rejected(self):
        with self.assertRaisesRegex(SpriteCutBoundsError, "PNG dimensions"):
            triage_residuals({("a", 0): ((0, 0, 1, 1), (0, 0))},
                             {("a", 0): ((0, 0, 1, 1), (0, 0))})


if __name__ == "__main__":
    unittest.main()
