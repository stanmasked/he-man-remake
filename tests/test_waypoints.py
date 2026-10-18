"""Synthetic fixtures only; no original game files or asset bytes."""
from pathlib import Path
from tempfile import TemporaryDirectory
import math
import struct
import unittest
import zipfile

from heman_tools.lvl import LevelFormatError
from heman_tools.waypoints import parse_waypoints
from heman_tools.waypoints_cli import audit_waypoints
from test_objects import example_level, s


def point(x, y, z=0.0, marker=0, short_field=0, links=()):
    return struct.pack("<IfffHI", marker, x, y, z, short_field, len(links)) + b"".join(
        struct.pack("<I", link) for link in links)


def named_group(name="synthetic_path", points=None):
    if points is None:
        points = [point(10, 20), point(30, 40, links=(0,))]
    return s(name) + struct.pack("<I", len(points)) + b"".join(points)


def synthetic_level(groups=None):
    if groups is None:
        groups = [named_group()]
    return example_level(trailer=struct.pack("<I", len(groups)) + b"".join(groups))


class TestNamedPoints(unittest.TestCase):
    def test_valid_route_and_link(self):
        result = parse_waypoints(synthetic_level())
        self.assertEqual(result.level_name, "Synthetic.lvl")
        self.assertEqual(result.total_points, 2)
        self.assertEqual(result.total_links, 1)
        self.assertEqual(result.groups[0].points[1].link_indices, (0,))
        self.assertEqual(result.groups[0].points[0].x, 10)
        self.assertEqual(result.trailing_unparsed_bytes, 0)

    def test_multiple_groups_and_fields(self):
        a = named_group("Group A", [point(-2, 4, 8, marker=19, short_field=5)])
        b = named_group("Group B", [point(3, 6)])
        result = parse_waypoints(synthetic_level([a, b]))
        self.assertEqual(len(result.groups), 2)
        self.assertEqual(result.groups[0].points[0].marker, 19)
        self.assertEqual(result.groups[0].points[0].short_field, 5)

    def test_zero_groups(self):
        result = parse_waypoints(synthetic_level([]))
        self.assertEqual(result.total_points, 0)

    def test_empty_named_group(self):
        result = parse_waypoints(synthetic_level([named_group("Empty", [])]))
        self.assertEqual(result.total_points, 0)

    def test_duplicate_edges_preserved(self):
        result = parse_waypoints(synthetic_level([
            named_group(points=[point(0, 0, links=(1, 1)), point(2, 0)])
        ]))
        self.assertEqual(result.groups[0].points[0].link_indices, (1, 1))

    def test_invalid_link_index(self):
        with self.assertRaises(LevelFormatError):
            parse_waypoints(synthetic_level([named_group(points=[point(1, 2, links=(1,))])]))

    def test_invalid_large_link_count(self):
        corrupt = bytearray(point(10, 20))
        struct.pack_into("<I", corrupt, 18, 99999)
        with self.assertRaises(LevelFormatError):
            parse_waypoints(synthetic_level([named_group(points=[bytes(corrupt)])]))

    def test_nonfinite_coordinates(self):
        with self.assertRaises(LevelFormatError):
            parse_waypoints(synthetic_level([named_group(points=[point(math.inf, 2)])]))

    def test_truncated_point(self):
        with self.assertRaises(LevelFormatError):
            parse_waypoints(synthetic_level()[:-4])

    def test_reject_unparsed_bytes(self):
        with self.assertRaises(LevelFormatError):
            parse_waypoints(synthetic_level() + b"JUNK")

    def test_invalid_group_count(self):
        with self.assertRaises(LevelFormatError):
            parse_waypoints(example_level(trailer=struct.pack("<I", 99999)))

    def test_local_ipa_loader(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "fixture.ipa"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("Payload/MOTU.app/screen-med/levels/Synthetic.lvl", synthetic_level())
            report = audit_waypoints(path, "Synthetic.lvl")
            self.assertEqual(report["points_count"], 2)
            self.assertEqual(report["groups_count"], 1)

    def test_reject_level_traversal(self):
        with self.assertRaises(ValueError):
            audit_waypoints(Path("not-opened"), "../private.lvl")


if __name__ == "__main__":
    unittest.main()
