import math
from pathlib import Path
import struct
import unittest
import zipfile
from tempfile import TemporaryDirectory

from heman_tools.lvl import LevelFormatError, parse_level_header
from heman_tools.cli import audit_ipa

def synthetic_level(name="Synthetic1.lvl", count=3, first_label="ObjectA", version=1):
    first = name.encode("utf-16le")
    return (struct.pack("<I6fH", version, 0.0, 0.0, 1500.0, 576.0, 0.0, 100.0, len(name))
            + first + struct.pack("<I", count)
            + (struct.pack("<H", len(first_label)) + first_label.encode("utf-16le") if count else b""))

class TestHeader(unittest.TestCase):
    def test_happy_path(self):
        h = parse_level_header(synthetic_level())
        self.assertEqual(h.embedded_name, "Synthetic1.lvl")
        self.assertEqual(h.record_count_hint, 3)
        self.assertEqual(h.first_record_label_hint, "ObjectA")
        self.assertEqual(h.raw_floats[2], 1500.0)

    def test_zero_records(self):
        self.assertIsNone(parse_level_header(synthetic_level(count=0)).first_record_label_hint)

    def test_short_file(self):
        with self.assertRaises(LevelFormatError):
            parse_level_header(b"\x00")

    def test_truncated_utf16(self):
        with self.assertRaises(LevelFormatError):
            parse_level_header(synthetic_level()[:35])

    def test_truncated_record_count(self):
        d = synthetic_level()
        n = len("Synthetic1.lvl")
        with self.assertRaises(LevelFormatError):
            parse_level_header(d[:30 + 2 * n + 1])

    def test_bad_version(self):
        with self.assertRaises(LevelFormatError):
            parse_level_header(synthetic_level(version=2))

    def test_nonfinite_field(self):
        data = bytearray(synthetic_level())
        struct.pack_into("<f", data, 12, math.nan)
        with self.assertRaises(LevelFormatError):
            parse_level_header(bytes(data))

    def test_bad_embedded_name(self):
        with self.assertRaises(LevelFormatError):
            parse_level_header(synthetic_level("other.dat"))

    def test_optional_label_malformed_is_not_fatal(self):
        d = synthetic_level()[:-4]
        self.assertIsNone(parse_level_header(d).first_record_label_hint)

    def test_archive_scan(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "sample.ipa"
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("Payload/MOTU.app/screen-med/levels/Synthetic1.lvl", synthetic_level())
                z.writestr("Payload/MOTU.app/screen-med/levels/ignored.txt", "test")
            r = audit_ipa(path)
            self.assertEqual(r["level_files"], 1)
            self.assertEqual(r["levels"][0]["header"]["record_count_hint"], 3)

    def test_archive_name_mismatch(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "sample.ipa"
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("Payload/MOTU.app/screen-med/levels/Other.lvl", synthetic_level())
            with self.assertRaises(LevelFormatError):
                audit_ipa(path)

if __name__ == "__main__":
    unittest.main()
