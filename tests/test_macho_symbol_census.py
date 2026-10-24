"""Synthetic Mach-O symbol tables only; never original executable bytes."""
from __future__ import annotations

import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from heman_tools.macho_symbol_census import (
    inspect_private_ipa_symbol_table,
    main,
    summarize_macho_symbols,
)
from test_ios_launch_preflight import write_fixture


def fake_symbol_macho(symbols):
    """Build a thin ARMv7 Mach-O with one __TEXT,__text section and nlist32 table."""
    string_table = bytearray(b"\x00")
    nlist = []
    for name, n_type, n_sect in symbols:
        raw = name.encode("ascii")
        strx = len(string_table)
        string_table.extend(raw + b"\x00")
        nlist.append(struct.pack("<IBBHI", strx, n_type, n_sect, 0, 0x1000))

    version_command = struct.pack("<IIII", 0x25, 16, 0x00040300, 0x00060100)
    segment_size = 56 + 68
    symtab_command = struct.pack("<IIIIII", 0x2, 24, 0, len(nlist), 0, len(string_table))
    sizeofcmds = len(version_command) + segment_size + len(symtab_command)
    text_offset = 28 + sizeofcmds
    text_bytes = bytes(16)
    symoff = text_offset + len(text_bytes)
    symbol_bytes = b"".join(nlist)
    stroff = symoff + len(symbol_bytes)
    final_size = stroff + len(string_table)

    segment_header = struct.pack(
        "<II16sIIIIIIII",
        0x1, segment_size, b"__TEXT",
        0x1000, final_size, 0, final_size, 7, 5, 1, 0,
    )
    section = struct.pack(
        "<16s16sIIIIIIIII",
        b"__text", b"__TEXT", 0x1000, len(text_bytes), text_offset,
        2, 0, 0, 0, 0, 0,
    )
    segment_command = segment_header + section
    symtab_command = struct.pack(
        "<IIIIII", 0x2, 24, symoff, len(nlist), stroff, len(string_table)
    )
    header = struct.pack(
        "<IiiIIII", 0xfeedface, 12, 9, 2, 3, sizeofcmds, 0
    )
    return (header + version_command + segment_command + symtab_command
            + text_bytes + symbol_bytes + bytes(string_table))


class MachOSymbolCensusTests(unittest.TestCase):
    def test_counts_text_defined_categories_without_exporting_names(self):
        symbols = [
            ("__ZN22EntityCollisionManager18onAABBIntersectionEv", 0x1E, 1),
            ("__ZN4helo7Shape2D10customLoadEv", 0x1E, 1),
            ("__ZN4helo2rt13ClassTypeImplI11CPhysicsSetE11newInstanceEv", 0x1E, 1),
            ("__ZN11CLineSensor9handleMsgEv", 0x1E, 1),
            ("__ZN15CStaticPlatformC1Ev", 0x1E, 1),
            ("__ZN21CInfiniteTileMapLayerC1Ev", 0x1E, 1),
            ("_external_physics_stub", 0x01, 0),
        ]
        report = summarize_macho_symbols(fake_symbol_macho(symbols))
        self.assertEqual(report["macho"]["architecture"], "armv7")
        self.assertEqual(report["macho"]["text_section_ordinal"], 1)
        self.assertEqual(report["symbol_table_entries"], 7)
        self.assertEqual(report["named_non_debug_symbol_entries"], 7)
        self.assertEqual(report["text_section_defined_symbol_entries"], 6)
        self.assertEqual(report["category_symbol_entry_counts"]["physics"], 2)
        self.assertEqual(report["text_section_category_symbol_entry_counts"]["physics"], 1)
        self.assertEqual(report["category_symbol_entry_counts"]["collision"], 1)
        self.assertEqual(report["text_section_category_symbol_entry_counts"]["collision"], 1)
        self.assertEqual(report["text_section_category_symbol_entry_counts"]["shape2d"], 1)
        self.assertEqual(report["text_section_category_symbol_entry_counts"]["sensor"], 1)
        self.assertEqual(report["text_section_category_symbol_entry_counts"]["platform"], 1)
        self.assertEqual(report["text_section_category_symbol_entry_counts"]["tilemap"], 1)
        serialized = json.dumps(report)
        for name, _, _ in symbols:
            self.assertNotIn(name, serialized)
        self.assertFalse(report["static_symbol_presence_proves_call_path"])
        self.assertFalse(report["original_collision_response_verified"])
        self.assertFalse(report["native_switch_collision_import_authorized"])

    def test_duplicate_symbol_entries_are_counted_as_entries(self):
        symbols = [
            ("__ZN4helo7Shape2D10customLoadEv", 0x1E, 1),
            ("__ZN4helo7Shape2D10customLoadEv", 0x1E, 1),
        ]
        report = summarize_macho_symbols(fake_symbol_macho(symbols))
        self.assertEqual(report["symbol_table_entries"], 2)
        self.assertEqual(report["distinct_symbol_names"], 1)
        self.assertEqual(report["category_symbol_entry_counts"]["shape2d"], 2)
        self.assertEqual(report["text_section_category_symbol_entry_counts"]["shape2d"], 2)

    def test_bad_symbol_string_index_rejected(self):
        binary = bytearray(fake_symbol_macho([
            ("__ZN4helo7Shape2D10customLoadEv", 0x1E, 1)
        ]))
        # Locate LC_SYMTAB and corrupt its first nlist string index.
        cursor = 28
        symoff = None
        for _ in range(3):
            cmd, cmdsize = struct.unpack_from("<II", binary, cursor)
            if cmd == 0x2:
                symoff = struct.unpack_from("<I", binary, cursor + 8)[0]
                break
            cursor += cmdsize
        self.assertIsNotNone(symoff)
        struct.pack_into("<I", binary, symoff, 0xFFFFFFFF)
        with self.assertRaisesRegex(ValueError, "string table"):
            summarize_macho_symbols(bytes(binary))

    def test_symbol_table_absent_rejected(self):
        version_command = struct.pack("<IIII", 0x25, 16, 0x00040300, 0x00060100)
        segment_size = 56 + 68
        text_offset = 28 + 16 + segment_size
        text_bytes = bytes(16)
        segment_header = struct.pack(
            "<II16sIIIIIIII",
            0x1, segment_size, b"__TEXT",
            0x1000, 256, 0, text_offset + len(text_bytes), 7, 5, 1, 0,
        )
        section = struct.pack(
            "<16s16sIIIIIIIII",
            b"__text", b"__TEXT", 0x1000, len(text_bytes), text_offset,
            2, 0, 0, 0, 0, 0,
        )
        segment_command = segment_header + section
        commands = version_command + segment_command
        header = struct.pack(
            "<IiiIIII", 0xfeedface, 12, 9, 2, 2, len(commands), 0
        )
        without_symtab = header + commands + text_bytes
        with self.assertRaisesRegex(ValueError, "symbol table is absent"):
            summarize_macho_symbols(without_symtab)

    def test_non_macho_rejected(self):
        with self.assertRaisesRegex(ValueError, "Mach-O"):
            summarize_macho_symbols(b"not Mach-O" + bytes(100))

    def test_synthetic_ipa_source_member_stays_in_memory(self):
        symbols = [
            ("__ZN22EntityCollisionManager18onAABBIntersectionEv", 0x1E, 1),
            ("__ZN4helo7Shape2D10customLoadEv", 0x1E, 1),
        ]
        binary = fake_symbol_macho(symbols)
        with TemporaryDirectory() as tmp:
            ipa = Path(tmp) / "fictional.ipa"
            write_fixture(ipa, binary=binary)
            report = inspect_private_ipa_symbol_table(ipa)
        self.assertEqual(report["private_source"]["executable_size_bytes"], len(binary))
        self.assertFalse(report["private_source"]["ipa_member_extracted_to_disk"])
        self.assertFalse(report["private_source"]["raw_executable_bytes_in_report"])
        self.assertEqual(report["text_section_category_symbol_entry_counts"]["collision"], 1)
        self.assertNotIn("EntityCollisionManager", json.dumps(report))

    def test_cli_writes_only_private_json_report(self):
        symbols = [("__ZN4helo7Shape2D10customLoadEv", 0x1E, 1)]
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "local_reports").mkdir()
            ipa = root / "fictional.ipa"
            write_fixture(ipa, binary=fake_symbol_macho(symbols))
            output = root / "local_reports" / "symbol-census.json"
            with patch("heman_tools.collision_inventory.Path.cwd", return_value=root):
                self.assertEqual(main(["--ipa", str(ipa), "--out", str(output)]), 0)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertFalse(report["raw_symbol_names_in_report"])
            self.assertFalse(report["original_runtime_resource_binding_verified"])


if __name__ == "__main__":
    unittest.main()
