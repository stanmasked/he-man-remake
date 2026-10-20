"""Only constructed polygon/circle buffers; no commercial game assets."""
import math
import struct
import unittest

from heman_tools.affine_shape_geometry import (
    affine_diagnostics, hypothetical_geometry_report, hypothetical_shape_aabb,
)
from heman_tools.shapes import Shape, parse_shape


def matrix(a=1., b=0., c=0., d=1., tx=0., ty=0.):
    return (a, b, 0., c, d, 0., tx, ty, 1.)


def polygon(*points):
    if not points:
        points = ((0., 0.), (2., 0.), (2., 3.), (0., 3.))
    data = struct.pack('<IIHI', 0, 0, 0, len(points))
    data += b''.join(struct.pack('<ff', *p) for p in points)
    return parse_shape(data)


def circle(radius=2., x=0., y=0.):
    return parse_shape(struct.pack('<IIHfff', 1, 0, 0, radius, x, y))


class AffineShapeGeometryTests(unittest.TestCase):
    def test_identity_polygon(self):
        self.assertEqual(hypothetical_shape_aabb(polygon(), matrix()), (0, 0, 2, 3))

    def test_translated_polygon(self):
        self.assertEqual(hypothetical_shape_aabb(polygon(), matrix(tx=10, ty=-4)),
                         (10, -4, 12, -1))

    def test_rotated_polygon(self):
        self.assertEqual(hypothetical_shape_aabb(polygon(), matrix(0, 1, -1, 0)),
                         (-3, 0, 0, 2))

    def test_sheared_polygon(self):
        self.assertEqual(hypothetical_shape_aabb(polygon(), matrix(1, 0, 2, 1)),
                         (0, 0, 8, 3))

    def test_reflected_polygon(self):
        self.assertEqual(hypothetical_shape_aabb(polygon(), matrix(-1, 0, 0, 1)),
                         (-2, 0, 0, 3))
        self.assertTrue(affine_diagnostics(matrix(-1, 0, 0, 1))['reflected'])

    def test_circle_translation(self):
        self.assertEqual(hypothetical_shape_aabb(circle(2, 3, -1), matrix(tx=5, ty=7)),
                         (6, 4, 10, 8))

    def test_circle_anisotropic_ellipse(self):
        self.assertEqual(hypothetical_shape_aabb(circle(2), matrix(3, 0, 0, .5)),
                         (-6, -1, 6, 1))

    def test_circle_rotated(self):
        self.assertEqual(hypothetical_shape_aabb(circle(2), matrix(0, 1, -1, 0)),
                         (-2, -2, 2, 2))

    def test_circle_sheared_uses_row_norm(self):
        bound = hypothetical_shape_aabb(circle(2), matrix(1, 0, 2, 1))
        self.assertAlmostEqual(bound[0], -2 * math.sqrt(5))
        self.assertAlmostEqual(bound[2], 2 * math.sqrt(5))
        self.assertEqual((bound[1], bound[3]), (-2, 2))

    def test_zero_linear_matrix(self):
        m = matrix(0, 0, 0, 0, 5, -7)
        self.assertEqual(hypothetical_shape_aabb(circle(2), m), (5, -7, 5, -7))
        report = affine_diagnostics(m)
        self.assertTrue(report['near_degenerate'])
        self.assertIsNone(report['axis_cosine'])

    def test_determinant_and_axes(self):
        d = affine_diagnostics(matrix(3, 0, 0, 4))
        self.assertEqual((d['determinant'], d['local_x_axis_length'],
                          d['local_y_axis_length']), (12, 3, 4))
        self.assertFalse(d['near_degenerate'])
        self.assertEqual(d['axis_cosine'], 0)

    def test_shear_detected_by_cosine(self):
        d = affine_diagnostics(matrix(1, 0, 2, 1))
        self.assertGreater(d['axis_cosine'], 0.8)
        self.assertEqual(d['determinant'], 1)

    def test_projective_rejected(self):
        bad = (1, 0, .5, 0, 1, 0, 0, 0, 1)
        with self.assertRaises(ValueError):
            hypothetical_shape_aabb(circle(), bad)

    def test_nonfinite_matrix_rejected(self):
        with self.assertRaises(ValueError):
            affine_diagnostics(matrix(tx=math.inf))

    def test_too_short_matrix_rejected(self):
        with self.assertRaises(ValueError):
            hypothetical_shape_aabb(circle(), (1.,)*8)

    def test_invalid_polygon_rejected(self):
        bad = Shape('polygon', 0, None, ((0, 0), (1, 1)), None, None)
        with self.assertRaises(ValueError):
            hypothetical_shape_aabb(bad, matrix())

    def test_invalid_circle_rejected(self):
        bad = Shape('circle', 0, None, (), -1., (0, 0))
        with self.assertRaises(ValueError):
            hypothetical_shape_aabb(bad, matrix())

    def test_unknown_shape_rejected(self):
        bad = Shape('unknown', 0, None, (), None, None)
        with self.assertRaises(ValueError):
            hypothetical_shape_aabb(bad, matrix())

    def test_unverified_geometry_explicit(self):
        value = hypothetical_geometry_report(circle(), matrix(2, 0, 0, 3))
        self.assertEqual(value['hypothetical_aabb'], (-4, -6, 4, 6))
        self.assertFalse(value['association_confirmed'])
        self.assertFalse(value['physical_collision_confirmed'])
        self.assertFalse(value['units_verified'])
        self.assertIn('not a collidable', value['interpretation'])

    def test_circle_bounds_exact_after_rotation_shear(self):
        m = matrix(.8, .6, -1.4, .3, 10, -5)
        bounds = hypothetical_shape_aabb(circle(3), m)
        self.assertAlmostEqual(bounds[0], 10 - 3*math.hypot(.8, -1.4))
        self.assertAlmostEqual(bounds[1], -5 - 3*math.hypot(.6, .3))


if __name__ == '__main__':
    unittest.main()
