"""Synthetic-only tests for Stage190's confirmed per-axis scale subset."""
from __future__ import annotations

import math
import unittest

from heman_tools.symbol_axis_scale import SymbolAxisScale


class SymbolAxisScaleTests(unittest.TestCase):
    def test_unit_scale_is_identity(self):
        self.assertEqual(SymbolAxisScale(1.0, 1.0).apply(12.0, -7.0), (12.0, -7.0))

    def test_nonuniform_scale_applies_per_axis(self):
        self.assertEqual(SymbolAxisScale(2.0, 0.5).apply(3.0, 8.0), (6.0, 4.0))

    def test_negative_scale_preserves_mirroring_sign(self):
        self.assertEqual(SymbolAxisScale(-1.0, 1.0).apply(5.0, -4.0), (-5.0, -4.0))

    def test_zero_scale_collapses_only_selected_axis(self):
        self.assertEqual(SymbolAxisScale(0.0, 2.0).apply(99.0, 3.0), (0.0, 6.0))

    def test_large_scale_is_not_clipped(self):
        self.assertEqual(SymbolAxisScale(130.0, 64.0).apply(1.0, -2.0), (130.0, -128.0))

    def test_non_finite_scale_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "finite numeric"):
            SymbolAxisScale(float("nan"), 1.0)

    def test_boolean_scale_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "finite numeric"):
            SymbolAxisScale(True, 1.0)

    def test_non_finite_coordinate_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "finite numeric"):
            SymbolAxisScale(1.0, 1.0).apply(float("inf"), 0.0)

    def test_overflow_after_scaling_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "remain finite"):
            SymbolAxisScale(1e308, 1.0).apply(1e308, 0.0)


if __name__ == "__main__":
    unittest.main()
