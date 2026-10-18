"""Synthetic fixtures only: no copyrighted shape bytes or assets."""
import math
import struct
import unittest

from heman_tools.lvl import LevelFormatError
from heman_tools.shapes import parse_shape, affine_point


def polygon(points=((0,0), (2,0), (2,3), (0,3)), reference='', flags=0):
    return (struct.pack('<IIH', 0, flags, len(reference)) + reference.encode('utf-16le')
            + struct.pack('<I', len(points))
            + b''.join(struct.pack('<ff', *p) for p in points))


def circle(radius=5, x=3, y=-1, reference='', flags=0):
    return (struct.pack('<IIH', 1, flags, len(reference)) + reference.encode('utf-16le')
            + struct.pack('<fff', radius, x, y))


class ShapeTests(unittest.TestCase):
    def test_polygon_decode(self):
        parsed = parse_shape(polygon())
        self.assertEqual(parsed.vertices, ((0,0), (2,0), (2,3), (0,3)))
        self.assertEqual(parsed.bounds(), (0,0,2,3))
        self.assertIsNone(parsed.reference)

    def test_linked_polygon(self):
        s = parse_shape(polygon(reference='TestMapA', flags=4))
        self.assertEqual(s.reference, 'TestMapA')
        self.assertEqual(s.flags, 4)

    def test_circle(self):
        s = parse_shape(circle())
        self.assertEqual(s.radius, 5)
        self.assertEqual(s.center, (3,-1))
        self.assertEqual(s.bounds(), (-2,-6,8,4))

    def test_linked_circle(self):
        s = parse_shape(circle(reference='MapB',flags=1))
        self.assertEqual((s.reference, s.flags), ('MapB', 1))

    def test_invalid_kind(self):
        with self.assertRaises(LevelFormatError):
            parse_shape(struct.pack('<IIH', 2, 0, 0))

    def test_truncated(self):
        with self.assertRaises(LevelFormatError):
            parse_shape(polygon()[:-4])

    def test_trailing_bytes(self):
        with self.assertRaises(LevelFormatError):
            parse_shape(circle() + b'garbage')

    def test_bad_circle_radius(self):
        with self.assertRaises(LevelFormatError):
            parse_shape(circle(0))

    def test_nan_vertex(self):
        with self.assertRaises(LevelFormatError):
            parse_shape(polygon(points=((0,0), (1,0), (0,math.nan))))

    def test_invalid_utf16(self):
        b = bytearray(polygon(reference='A'))
        b[10:12] = b'\x00\xd8'
        with self.assertRaises(LevelFormatError):
            parse_shape(bytes(b))

    def test_too_many_vertices(self):
        b = polygon()[:10] + struct.pack('<I', 5000)
        with self.assertRaises(LevelFormatError):
            parse_shape(b)

    def test_transform(self):
        self.assertEqual(affine_point((2,3),(2,0,0,0,4,0,10,-5,1)), (14,7))

    def test_reject_projective(self):
        with self.assertRaises(ValueError):
            affine_point((2,3),(1,0,1,0,1,0,0,0,1))

    def test_reject_nonfinite_transform(self):
        with self.assertRaises(ValueError):
            affine_point((math.nan,0),(1,0,0,0,1,0,0,0,1))

if __name__ == '__main__':
    unittest.main()
