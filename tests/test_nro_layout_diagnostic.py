"""Synthetic regression for the NRO0 loader boundary diagnostic."""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from nro_layout_diagnostic import inspect_nro


def fixture(wrapper: bool = True, trailing_padding: int = 0) -> bytes:
    length = 0x1A000
    data = bytearray(length + trailing_padding)
    pos = 16 if wrapper else 0
    data[pos:pos + 4] = b"NRO0"
    struct.pack_into("<I", data, pos + 8, length)
    for at, offset, size in (
        (0x10, 0, 0x14000),
        (0x18, 0x14000, 0x4000),
        (0x20, 0x18000, 0x2000),
    ):
        struct.pack_into("<II", data, pos + at, offset, size)
    return bytes(data)


class NroLayoutDiagnosticTests(unittest.TestCase):
    def test_devkitpro_wrapper_reproduces_loader_off_by_16(self) -> None:
        result = inspect_nro(fixture())
        self.assertEqual(result.magic_offset, 16)
        self.assertEqual(result.file_bytes, 0x1A000)
        self.assertEqual(result.emulator_slice_bytes, 0x19FF0)
        self.assertEqual(result.data_end, 0x1A000)
        self.assertEqual(result.loader_shortfall, 16)
        self.assertTrue(result.original_bounds_ok)
        self.assertFalse(result.nexium_bounds_ok)

    def test_no_wrapper_has_no_subtraction(self) -> None:
        result = inspect_nro(fixture(wrapper=False))
        self.assertTrue(result.original_bounds_ok)
        self.assertTrue(result.nexium_bounds_ok)

    def test_padding_changes_bounds_not_loader_semantics(self) -> None:
        result = inspect_nro(fixture(trailing_padding=16))
        self.assertTrue(result.nexium_bounds_ok)
        self.assertEqual(result.loader_shortfall, 0)
        self.assertEqual(result.magic_offset, 16)

    def test_invalid_magic_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing NRO0"):
            inspect_nro(b"X" * 256)

    def test_truncated_original_segment_is_detected(self) -> None:
        result = inspect_nro(fixture()[:-17])
        self.assertFalse(result.original_bounds_ok)
        self.assertFalse(result.nexium_bounds_ok)


if __name__ == "__main__":
    unittest.main()
