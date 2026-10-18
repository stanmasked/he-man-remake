"""Asset-free, byte-accurate tests for correct NRO segment origin."""
from __future__ import annotations
import struct
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from nro_loader_reference import parse_standard_nro


def make_image() -> bytes:
    image = bytearray(0x1A000)
    image[0:4] = b"\x20\x00\x00\x14"  # native AArch64 entry branch stub
    struct.pack_into("<I", image, 4, 0xF0)
    image[0x10:0x14] = b"NRO0"
    struct.pack_into("<I", image, 0x18, 0x1A000)
    for header, off, length in (
        (0x20, 0, 0x14000),
        (0x28, 0x14000, 0x4000),
        (0x30, 0x18000, 0x2000),
    ):
        struct.pack_into("<II", image, header, off, length)
    struct.pack_into("<I", image, 0x38, 0x5000)
    image[0x14000:0x14004] = b"READ"
    image[0x18000:0x18004] = b"DATA"
    return bytes(image)


class CanonicalNroLoaderTests(unittest.TestCase):
    def test_realistic_standard_devkitpro_file(self) -> None:
        data = make_image()
        parsed = parse_standard_nro(data)
        self.assertEqual(parsed.size, len(data))
        self.assertEqual(parsed.mod0_offset, 0xF0)
        self.assertEqual(parsed.bss_size, 0x5000)
        self.assertEqual(parsed.text.offset, 0)
        self.assertEqual(parsed.text.end, 0x14000)
        self.assertEqual(parsed.ro.offset, 0x14000)
        self.assertEqual(parsed.data.end, len(data))
        self.assertEqual(parsed.bytes_for(data, "text")[:4],
                         b"\x20\x00\x00\x14")
        self.assertEqual(parsed.bytes_for(data, "ro")[:4], b"READ")
        self.assertEqual(parsed.bytes_for(data, "data")[:4], b"DATA")

    def test_missing_header_at_plus_16_rejected(self) -> None:
        data = bytearray(make_image())
        data[0x10:0x14] = b"BAD0"
        with self.assertRaisesRegex(ValueError, "NRO0"):
            parse_standard_nro(bytes(data))

    def test_truncated_final_data_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid NRO image size"):
            parse_standard_nro(make_image()[:-16])

    def test_segment_outside_declared_size_rejected(self) -> None:
        data = bytearray(make_image())
        struct.pack_into("<I", data, 0x34, 0x2001)
        with self.assertRaisesRegex(ValueError, "segment exceeds"):
            parse_standard_nro(bytes(data))

    def test_adjacent_ro_and_data_not_shifted_by_header(self) -> None:
        image = make_image()
        parsed = parse_standard_nro(image)
        self.assertEqual(parsed.ro.end, parsed.data.offset)
        self.assertEqual(parsed.ro.size, 0x4000)

    def test_overlapping_segments_rejected(self) -> None:
        data = bytearray(make_image())
        struct.pack_into("<I", data, 0x28, 0x13000)
        with self.assertRaisesRegex(ValueError, "overlapping"):
            parse_standard_nro(bytes(data))

    def test_text_start_must_be_file_start(self) -> None:
        data = bytearray(make_image())
        struct.pack_into("<I", data, 0x20, 128)
        with self.assertRaisesRegex(ValueError, "offset zero"):
            parse_standard_nro(bytes(data))

    def test_optional_aset_after_image_does_not_affect_segments(self) -> None:
        data = make_image() + b"ASET" + bytes(56)
        parsed = parse_standard_nro(data)
        self.assertEqual(parsed.size, len(data)-60)
        self.assertEqual(parsed.data.end, parsed.size)

    def test_reject_unknown_segment_name(self) -> None:
        data = make_image()
        with self.assertRaisesRegex(ValueError, "unknown"):
            parse_standard_nro(data).bytes_for(data, "oops")


if __name__ == "__main__":
    unittest.main()
