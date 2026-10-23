"""Synthetic-only tests for Stage190's confirmed Symbol transform subset."""
from __future__ import annotations

import math
import unittest

from heman_tools.symbol_rotation_translation import SymbolRotationTranslation


class SymbolRotationTranslationTests(unittest.TestCase):
    def assertPointAlmostEqual(self, actual, expected, places=6):
        self.assertAlmostEqual(actual[0], expected[0], places=places)
        self.assertAlmostEqual(actual[1], expected[1], places=places)

    def test_zero_rotation_applies_offsets(self):
        transform = SymbolRotationTranslation(0, -30, -90)
        self.assertPointAlmostEqual(transform.apply(5.0, 7.0), (-25.0, -83.0))

    def test_ninety_degrees_rotates_then_translates(self):
        transform = SymbolRotationTranslation(90, 10, -4)
        self.assertPointAlmostEqual(transform.apply(1.0, 0.0), (10.0, -3.0))

    def test_negative_ninety_degrees(self):
        transform = SymbolRotationTranslation(-90, 2, 3)
        self.assertPointAlmostEqual(transform.apply(0.0, 1.0), (3.0, 3.0))

    def test_one_eighty_degrees(self):
        transform = SymbolRotationTranslation(180, 0, 0)
        self.assertPointAlmostEqual(transform.apply(2.0, -3.0), (-2.0, 3.0))

    def test_thirty_degrees_uses_degrees_not_radians(self):
        transform = SymbolRotationTranslation(30, 0, 0)
        self.assertPointAlmostEqual(
            transform.apply(2.0, 0.0), (math.sqrt(3.0), 1.0)
        )

    def test_rotation_radians_uses_pi_over_180(self):
        self.assertAlmostEqual(
            SymbolRotationTranslation(90, 0, 0).rotation_radians, math.pi / 2
        )

    def test_boolean_rotation_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Rotation must"):
            SymbolRotationTranslation(True, 0, 0)

    def test_boolean_offsets_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "offsets must be integers"):
            SymbolRotationTranslation(0, False, 0)

    def test_non_finite_local_point_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "must be finite"):
            SymbolRotationTranslation(0, 0, 0).apply(float("nan"), 0.0)

    def test_extreme_rotation_stays_finite(self):
        point = SymbolRotationTranslation(585, -256, 576).apply(61.0, 91.0)
        self.assertTrue(all(math.isfinite(value) for value in point))


if __name__ == "__main__":
    unittest.main()
