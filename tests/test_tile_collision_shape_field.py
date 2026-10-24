"""Only fictional Mach-O symbols and fabricated Thumb halfwords for Stage264."""
from __future__ import annotations

import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from heman_tools.tile_collision_shape_field import (
    thumb_imm_word_transfer,
    thumb_movs_zero,
    summarize_tile_shape_field_chain,
    inspect_private_ipa_tile_shape_field,
    main,
)
from test_thumb_bl_call_census import encode_thumb_bl
from test_ios_launch_preflight import write_fixture


def mem_word(operation: str, rt: int, rn: int, offset_bytes: int) -> int:
    if operation not in ("ldr", "str") or offset_bytes % 4 or not 0 <= offset_bytes <= 124:
        raise ValueError("fixture transfer outside 16-bit Thumb encoding")
    return ((0x6800 if operation == "ldr" else 0x6000)
            | ((offset_bytes // 4) << 6) | (rn << 3) | rt)


def synthetic_tile_macho(*, omit_call=False, omit_initialization=False,
                         bad_setter_field=False, missing_getter=False):
    # Entirely invented symbol names, addresses, and instructions.
    names = [
        ("__ZN4Tile6fileInEP12_helo_file_tP7Tileset", 0),
        ("__ZN4Tile17setCollisionShapeEPKc", 0x80),
        ("__ZN4Tile17getCollisionShapeEv", 0x100),
        ("__ZN4Tile9anotherEv", 0x120),
    ]
    if missing_getter:
        names = [x for x in names if "getCollisionShape" not in x[0]]
    raw_text = bytearray(0x160)

    def put(offset, halfword):
        struct.pack_into("<H", raw_text, offset, halfword)

    if not omit_initialization:
        put(0x00, 0x2000)  # MOVS r0,#0
    else:
        put(0x00, 0x2001)  # MOVS r0,#1
    put(0x02, mem_word("str", 0, 4, 40))
    put(0x04, mem_word("str", 0, 4, 44))
    if not omit_call:
        raw_text[0x06:0x0A] = encode_thumb_bl(0x1006, 0x1080)
    put(0x80, mem_word("str", 0, 1, 40 if bad_setter_field else 44))
    put(0x82, 0x4770)  # BX lr

    put(0x100, mem_word("ldr", 1, 0, 44))
    put(0x102, 0x2000)  # MOVS r0,#0
    put(0x104, 0x2900)  # CMP r1,#0
    put(0x106, 0xBF18)  # IT NE
    put(0x108, mem_word("ldr", 0, 1, 4))
    put(0x10A, 0x4770)  # BX lr
    put(0x120, 0x4770)  # Sentinel function

    strtab = bytearray(b"\x00")
    nlist = []
    for label, offset in names:
        index = len(strtab)
        strtab.extend(label.encode("ascii") + b"\x00")
        nlist.append((index, offset))

    version = struct.pack("<IIII", 0x25, 16, 0x00040300, 0x00060100)
    segment_size = 56 + 68
    command_size = len(version) + segment_size + 24
    text_offset = 28 + command_size
    symoff = text_offset + len(raw_text)
    stroff = symoff + len(nlist) * 12
    end = stroff + len(strtab)
    section = struct.pack(
        "<16s16sIIIIIIIII", b"__text", b"__TEXT", 0x1000,
        len(raw_text), text_offset, 2, 0, 0, 0, 0, 0
    )
    segment = struct.pack(
        "<II16sIIIIIIII", 1, segment_size, b"__TEXT",
        0x1000, 0x2000, 0, end, 7, 5, 1, 0
    ) + section
    symcommand = struct.pack("<IIIIII", 2, 24, symoff, len(nlist),
                             stroff, len(strtab))
    header = struct.pack("<IiiIIII", 0xfeedface, 12, 9, 2, 3, command_size, 0)
    entries = b"".join(
        struct.pack("<IBBHI", index, 0x0F, 1, 8, 0x1000 + addr)
        for index, addr in nlist
    )
    return header + version + segment + symcommand + raw_text + entries + strtab


class TileCollisionShapeFieldTests(unittest.TestCase):
    def test_thumb_immediate_load_store_decoding(self):
        encoded = mem_word("str", 0, 4, 44)
        self.assertEqual(thumb_imm_word_transfer(encoded), {
            "operation": "str", "source_or_dest": 0, "base": 4, "offset_bytes": 44
        })
        self.assertEqual(thumb_imm_word_transfer(
            mem_word("ldr", 1, 0, 44))["operation"], "ldr")
        self.assertIsNone(thumb_imm_word_transfer(0x4770))
        self.assertTrue(thumb_movs_zero(0x2000, 0))
        self.assertFalse(thumb_movs_zero(0x2001, 0))
        self.assertFalse(thumb_movs_zero(0x2000, 1))

    def test_join_from_filein_setter_and_getter(self):
        report = summarize_tile_shape_field_chain(synthetic_tile_macho())
        self.assertEqual(report["selected_thumb_methods"], 3)
        self.assertEqual(report["deserializer_to_setter_direct_bl_candidates"], 1)
        self.assertEqual(report["candidate_member_offset_bytes"], 44)
        self.assertEqual(report["deserializer_zero_initialization_candidates"], 1)
        self.assertEqual(report["setter_field_write_candidates"], 1)
        self.assertEqual(report["getter_field_read_candidates"], 1)
        self.assertEqual(report["getter_nested_pointer_read_candidates"], 1)
        self.assertTrue(report["structural_chain_complete"])
        self.assertFalse(report["collision_shape_resource_type_verified"])
        self.assertFalse(report["original_tile_alpha_used_for_collision_verified"])
        self.assertFalse(report["native_switch_collision_import_authorized"])
        dumped = json.dumps(report)
        for token in ("__ZN4Tile", "getCollisionShape", "0x1080", "Tileset"):
            self.assertNotIn(token, dumped)

    def test_no_direct_call_does_not_get_invented(self):
        report = summarize_tile_shape_field_chain(
            synthetic_tile_macho(omit_call=True)
        )
        self.assertEqual(report["deserializer_to_setter_direct_bl_candidates"], 0)
        self.assertFalse(report["structural_chain_complete"])

    def test_missing_zero_propagation_is_not_proven(self):
        report = summarize_tile_shape_field_chain(
            synthetic_tile_macho(omit_initialization=True)
        )
        self.assertEqual(report["deserializer_zero_initialization_candidates"], 0)
        self.assertFalse(report["structural_chain_complete"])

    def test_wrong_setter_offset_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "field-access join"):
            summarize_tile_shape_field_chain(
                synthetic_tile_macho(bad_setter_field=True)
            )

    def test_missing_getter_symbol_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "uniquely defined"):
            summarize_tile_shape_field_chain(
                synthetic_tile_macho(missing_getter=True)
            )

    def test_invalid_macho_input_rejected(self):
        with self.assertRaises(ValueError):
            summarize_tile_shape_field_chain(bytes(400))

    def test_owner_ipa_access_contract_synthetic_only(self):
        with TemporaryDirectory() as temp:
            ipa = Path(temp) / "fiction.ipa"
            write_fixture(ipa, binary=synthetic_tile_macho())
            report = inspect_private_ipa_tile_shape_field(ipa)
        self.assertFalse(report["private_source"]["private_executable_extracted_to_disk"])
        self.assertTrue(report["structural_chain_complete"])

    def test_private_path_and_report(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "local_reports").mkdir()
            ipa = root / "fiction.ipa"
            write_fixture(ipa, binary=synthetic_tile_macho())
            out = root / "local_reports" / "stage264-test.json"
            with patch("heman_tools.collision_inventory.Path.cwd", return_value=root):
                self.assertEqual(main(["--ipa", str(ipa), "--out", str(out)]), 0)
            report = json.loads(out.read_text(encoding="utf-8"))
            self.assertTrue(report["static_instruction_patterns_not_proven_runtime_aliases"])


if __name__ == "__main__":
    unittest.main()
