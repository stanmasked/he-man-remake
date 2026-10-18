"""Entirely synthetic fixtures: no original game files or bytes are included."""
from pathlib import Path
from tempfile import TemporaryDirectory
import math
import struct
import unittest
import zipfile

from heman_tools.lvl import LevelFormatError
from heman_tools.objects import parse_level_objects
from heman_tools.objects_cli import audit_objects


def s(text: str) -> bytes:
    return struct.pack("<H", len(text)) + text.encode("utf-16le")


def example_object(*, group="group-one", name="fixture", x=100.0, y=50.0,
                   extra=b"", props=()):
    matrix = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, x, y, 1.0)
    out = bytearray(s("DemoObject") + s(group) + s(name))
    out += b"\x00" * 25 + b"\x01" + s("idle")
    out += struct.pack("<5I", 2, 1, 0, 0, 0) + extra
    out += struct.pack("<I9fB", 9, *matrix, len(props))
    for key, kind, value in props:
        out += s(key)
        if kind == "bool":
            out += struct.pack("<BB", 0, int(value))
        elif kind == "int":
            out += struct.pack("<Bi", 1, value)
        elif kind == "float":
            out += struct.pack("<Bf", 2, value)
        elif kind == "string":
            out += b"\x03" + s(value)
        elif kind == "bad":
            out += b"\xfa"
        else:
            raise AssertionError(kind)
    return bytes(out)


def example_level(objects=None, *, name="Synthetic.lvl", trailer=b"\x00\x00\x00\x00"):
    if objects is None:
        objects = [example_object()]
    return (struct.pack("<I6f", 1, 0, 0, 1500, 600, 0, 0)
            + s(name) + struct.pack("<I", len(objects))
            + b"".join(objects) + trailer)


class TestObjectParser(unittest.TestCase):
    def test_single_object_with_coordinate(self):
        p = parse_level_objects(example_level())
        self.assertEqual(len(p.objects), 1)
        self.assertEqual(p.objects[0].class_name, "DemoObject")
        self.assertEqual(p.objects[0].group_name, "group-one")
        self.assertEqual(p.objects[0].instance_name, "fixture")
        self.assertEqual((p.objects[0].x, p.objects[0].y), (100, 50))
        self.assertEqual(p.trailer_record_count_hint, 0)

    def test_all_property_types(self):
        sample = example_object(props=[("active", "bool", True), ("count", "int", -3),
                                       ("speed", "float", 2.5), ("label", "string", "hello")])
        props = parse_level_objects(example_level([sample])).objects[0].properties
        self.assertEqual([(v.name, v.kind, v.value) for v in props], [
            ("active", "bool", True), ("count", "int", -3),
            ("speed", "float", 2.5), ("label", "string", "hello")])

    def test_two_objects_and_variable_metadata(self):
        objects = [example_object(), example_object(extra=s("SyntheticAnimation"), x=-7)]
        rows = parse_level_objects(example_level(objects)).objects
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1].x, -7)
        self.assertGreater(rows[1].opaque_after_state_bytes, rows[0].opaque_after_state_bytes)
        self.assertEqual(rows[0].end_offset, rows[1].offset)

    def test_detect_truncated_payload(self):
        with self.assertRaises(LevelFormatError):
            parse_level_objects(example_level()[:-2])

    def test_invalid_property_tag(self):
        with self.assertRaises(LevelFormatError):
            parse_level_objects(example_level([example_object(props=[("broken", "bad", None)])]))

    def test_invalid_object_utf16(self):
        data = bytearray(example_level())
        start = 30 + len("Synthetic.lvl") * 2 + 4
        data[start + 2:start + 4] = b"\x00\xd8"
        with self.assertRaises(LevelFormatError):
            parse_level_objects(bytes(data))

    def test_bad_matrix(self):
        obj = bytearray(example_object())
        marker = obj.find(struct.pack("<I", 9))
        self.assertGreater(marker, 0)
        struct.pack_into("<f", obj, marker + 4 + 8 * 4, 9.0)
        with self.assertRaises(LevelFormatError):
            parse_level_objects(example_level([bytes(obj)]))

    def test_nonfinite_property(self):
        with self.assertRaises(LevelFormatError):
            parse_level_objects(example_level([example_object(props=[("bad", "float", math.inf)])]))

    def test_missing_trailer(self):
        with self.assertRaises(LevelFormatError):
            parse_level_objects(example_level(trailer=b""))

    def test_archive_audit(self):
        with TemporaryDirectory() as d:
            ipa = Path(d) / "demo.ipa"
            with zipfile.ZipFile(ipa, "w") as archive:
                archive.writestr("Payload/MOTU.app/screen-med/levels/Synthetic.lvl", example_level())
            report = audit_objects(ipa, "Synthetic.lvl")
            self.assertEqual(report["object_count"], 1)
            self.assertFalse(report["trailer_decoded"])
            self.assertEqual(report["objects"][0]["x"], 100)

    def test_reject_archive_path_traversal(self):
        with self.assertRaises(ValueError):
            audit_objects(Path("does-not-matter"), "../some.lvl")


if __name__ == "__main__":
    unittest.main()
