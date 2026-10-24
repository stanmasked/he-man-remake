"""Stage227: invented DKSH byte fixtures, never proprietary shader bytes."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import struct
import unittest

from tools.verify_stage227_dksh_bundle import (
    DKSHValidationError, HEADER, MAGIC, check_pair, inspect_dksh,
    inspect_embedded_nro_shaders,
)


def invented_shader(seed: int = 0, *, control_size: int = 64, code_size: int = 48) -> bytes:
    header = HEADER.pack(MAGIC, HEADER.size, control_size, code_size, HEADER.size, 1)
    return header + bytes(control_size - HEADER.size) + bytes((seed+i) % 256 for i in range(code_size))


class DKSHBundleTests(unittest.TestCase):
    def test_valid_vertex_and_fragment_fixtures(self):
        for stage in ("vertex", "fragment"):
            report = inspect_dksh(invented_shader(), shader_stage=stage)
            self.assertEqual(report["code_size"], 48)
            self.assertEqual(report["program_count"], 1)
            self.assertFalse(report["gpu_shader_executed"])
            self.assertFalse(report["gpu_texture_sampling_verified"])
            self.assertFalse(report["original_ios_runtime_pixel_parity_verified"])

    def test_distinct_stage_files(self):
        with TemporaryDirectory() as folder:
            vertex = Path(folder) / "v.dksh"
            fragment = Path(folder) / "f.dksh"
            vertex.write_bytes(invented_shader(0))
            fragment.write_bytes(invented_shader(77))
            report = check_pair(vertex, fragment)
            self.assertEqual(report["shader_count"], 2)
            self.assertEqual([x["shader_stage"] for x in report["stages"]], ["vertex", "fragment"])
            self.assertFalse(report["hardware_gpu_sampling_verified"])

    def test_identical_files_fail_closed(self):
        with TemporaryDirectory() as folder:
            vertex = Path(folder) / "v.dksh"
            fragment = Path(folder) / "f.dksh"
            vertex.write_bytes(invented_shader(10))
            fragment.write_bytes(invented_shader(10))
            with self.assertRaisesRegex(DKSHValidationError, "identical"):
                check_pair(vertex, fragment)

    def test_corrupted_magic(self):
        invalid = b"BAD!" + invented_shader()[4:]
        with self.assertRaisesRegex(DKSHValidationError, "magic"):
            inspect_dksh(invalid, shader_stage="vertex")

    def test_missing_code(self):
        fixture = bytearray(invented_shader())
        struct.pack_into("<I", fixture, 12, 0)
        with self.assertRaisesRegex(DKSHValidationError, "machine-code"):
            inspect_dksh(bytes(fixture), shader_stage="fragment")

    def test_shortened_binary(self):
        fixture = invented_shader()
        with self.assertRaisesRegex(DKSHValidationError, "truncated"):
            inspect_dksh(fixture[:-1], shader_stage="vertex")

    def test_control_and_program_offset_invalid(self):
        for new_control, new_offset in ((20, 24), (64, 64), (70, 24)):
            fixture = bytearray(invented_shader())
            struct.pack_into("<I", fixture, 8, new_control)
            struct.pack_into("<I", fixture, 16, new_offset)
            with self.subTest(control=new_control, offset=new_offset):
                with self.assertRaises(DKSHValidationError):
                    inspect_dksh(bytes(fixture), shader_stage="fragment")

    def test_unsupported_stage_and_program_count(self):
        with self.assertRaisesRegex(DKSHValidationError, "known"):
            inspect_dksh(invented_shader(), shader_stage="geometry")
        fixture = bytearray(invented_shader())
        struct.pack_into("<I", fixture, 20, 0)
        with self.assertRaisesRegex(DKSHValidationError, "program count"):
            inspect_dksh(bytes(fixture), shader_stage="vertex")

    @staticmethod
    def invented_nro(vertex: bytes, fragment: bytes, *, aset: bool = True) -> bytes:
        base = bytearray(0x70)
        base[16:20] = b"NRO0"
        struct.pack_into("<I", base, 0x18, 0x70)
        if not aset:
            return bytes(base)
        section = bytearray(56)
        section[:4] = b"ASET"
        payload = b"synthetic-romfs-prefix" + vertex + b"separator" + fragment
        struct.pack_into("<QQ", section, 40, 56, len(payload))
        return bytes(base + section + payload)

    def test_embedded_romfs_must_contain_both_actual_shaders(self):
        vertex, fragment = invented_shader(0), invented_shader(77)
        report = inspect_embedded_nro_shaders(
            self.invented_nro(vertex, fragment), vertex, fragment,
        )
        self.assertEqual(report["embedded_compiled_shader_count"], 2)
        self.assertFalse(report["gpu_fragment_sampling_verified"])

    def test_romfsdir_only_missing_aset_must_fail(self):
        vertex, fragment = invented_shader(0), invented_shader(77)
        with self.assertRaisesRegex(DKSHValidationError, "ASET/RomFS"):
            inspect_embedded_nro_shaders(
                self.invented_nro(vertex, fragment, aset=False), vertex, fragment,
            )

    def test_romfs_missing_fragment_must_fail(self):
        vertex, fragment = invented_shader(0), invented_shader(77)
        with self.assertRaisesRegex(DKSHValidationError, "missing exact"):
            inspect_embedded_nro_shaders(
                self.invented_nro(vertex, invented_shader(11)), vertex, fragment,
            )

    def test_romfs_extent_cannot_escape_nro(self):
        vertex, fragment = invented_shader(0), invented_shader(77)
        invalid = bytearray(self.invented_nro(vertex, fragment))
        struct.pack_into("<Q", invalid, 0x70+48, 0xFFFFFFFF)
        with self.assertRaisesRegex(DKSHValidationError, "beyond NRO"):
            inspect_embedded_nro_shaders(bytes(invalid), vertex, fragment)

    def test_does_not_export_shader_bytes_or_resource_path(self):
        report = inspect_dksh(invented_shader(44), shader_stage="vertex")
        self.assertNotIn("image", str(report))
        self.assertFalse(report["source_game_assets_included"])


if __name__ == "__main__":
    unittest.main()
