"""Synthetic Mach-O import records and fabricated ZIPs, never original binaries."""
from __future__ import annotations

import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import zipfile

from heman_tools.ios_runtime_dependencies import (
    inspect_linked_dylibs, inspect_ipa_dependencies, main,
)
from test_ios_launch_preflight import fake_plist


def fixture(libs=(), *, order="<"):
    commands = [struct.pack(order + "IIII", 0x25, 16, 0x00040300, 0x00060100)]
    for name, cmd in libs:
        raw = name if isinstance(name, bytes) else name.encode("utf8")
        size = 24 + len(raw) + 1
        padded = (size + 3) & ~3
        commands.append(
            struct.pack(order + "IIIIII", cmd, padded, 24, 0, 0, 0)
            + raw + b"\x00" + bytes(padded - size))
    header = struct.pack(
        order + "IiiIIII", 0xfeedface, 12, 9, 2, len(commands),
        sum(len(c) for c in commands), 0)
    return header + b"".join(commands) + bytes(32)


def fake_zip(directory, *, libs=(), executable=None):
    path = Path(directory) / "fictional.ipa"
    binary = fixture(libs) if executable is None else executable
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Payload/Fiction.app/Info.plist", fake_plist())
        archive.writestr("Payload/Fiction.app/MOTU", binary)
    return path


class RuntimeDependencyTests(unittest.TestCase):
    def test_empty_import_table(self):
        report = inspect_linked_dylibs(fixture())
        self.assertEqual(report["linked_library_count"], 0)
        self.assertEqual(report["architecture"], "armv7")
        self.assertEqual(report["by_load_kind"]["required"], 0)
        self.assertFalse(report["source_ios_game_launched"])

    def test_strong_and_weak_system_dependencies(self):
        libs = [
            ("/System/Library/Frameworks/UIKit.framework/UIKit", 0xc),
            ("/System/Library/Frameworks/OpenGLES.framework/OpenGLES",
             0x80000018),
            ("/usr/lib/libsqlite3.dylib", 0xc),
        ]
        report = inspect_linked_dylibs(fixture(libs))
        self.assertEqual(report["linked_library_count"], 3)
        self.assertEqual(report["by_load_kind"]["required"], 2)
        self.assertEqual(report["by_load_kind"]["weak"], 1)
        self.assertEqual(report["by_path_category"]["system_framework"], 2)
        self.assertEqual(report["by_path_category"]["system_library"], 1)
        self.assertTrue(report["uikit_linked"])
        self.assertTrue(report["opengles_linked"])
        self.assertFalse(report["openaudio_linked"])
        self.assertFalse(report["runtime_import_resolution_verified"])

    def test_alternative_load_commands_counted(self):
        libs = [("@rpath/libsample.dylib", 0x8000001f),
                ("@loader_path/libdummy.dylib", 0x80000023),
                ("@executable_path/local.dylib", 0x20)]
        report = inspect_linked_dylibs(fixture(libs))
        self.assertEqual(report["linked_library_count"], 3)
        self.assertEqual(report["by_load_kind"]["reexport"], 1)
        self.assertEqual(report["by_load_kind"]["upward"], 1)
        self.assertEqual(report["by_load_kind"]["lazy"], 1)
        self.assertEqual(report["by_path_category"]["runtime_relative"], 3)

    def test_big_endian_32bit_macho(self):
        report = inspect_linked_dylibs(fixture(
            [("/usr/lib/libz.dylib", 0xc)], order=">"))
        self.assertEqual(report["linked_library_count"], 1)

    def test_import_paths_are_not_exported(self):
        report = inspect_linked_dylibs(fixture([
            ("/usr/lib/libprivate_fake.dylib", 0xc)]))
        text = json.dumps(report)
        self.assertNotIn("libprivate_fake.dylib", text)
        self.assertNotIn("/usr/lib/", text)
        self.assertFalse(report["dependency_paths_embedded_in_report"])
        self.assertFalse(report["original_gameplay_physics_verified"])

    def test_duplicate_import_rejected(self):
        libs = [("/usr/lib/test.dylib", 0xc)] * 2
        with self.assertRaisesRegex(ValueError, "duplicated"):
            inspect_linked_dylibs(fixture(libs))

    def test_empty_name_rejected(self):
        with self.assertRaisesRegex(ValueError, "NUL terminated"):
            inspect_linked_dylibs(fixture([(b"", 0xc)]))

    def test_unterminated_name_rejected(self):
        data = bytearray(fixture([("test_name", 0xc)]))
        offset = 28 + 16 + 24
        data[offset:offset + 12] = b"a" * 12
        with self.assertRaisesRegex(ValueError, "NUL terminated"):
            inspect_linked_dylibs(bytes(data))

    def test_invalid_dylib_name_offset_rejected(self):
        data = bytearray(fixture([("test_name", 0xc)]))
        struct.pack_into("<I", data, 28 + 16 + 8, 0)
        with self.assertRaisesRegex(ValueError, "name offset"):
            inspect_linked_dylibs(bytes(data))

    def test_nonutf8_name_rejected(self):
        with self.assertRaisesRegex(ValueError, "UTF-8"):
            inspect_linked_dylibs(fixture([(b"\xff\xfe", 0xc)]))

    def test_control_characters_and_backslashes_rejected(self):
        for name in ("back\\slash.dylib", "new\nline"):
            with self.subTest(name=name), self.assertRaisesRegex(
                    ValueError, "invalid linked-library"):
                inspect_linked_dylibs(fixture([(name, 0xc)]))

    def test_more_than_128_imports_rejected(self):
        libs = [(f"/usr/lib/libdummy{i}.dylib", 0xc)
                for i in range(129)]
        with self.assertRaisesRegex(ValueError, "excessive"):
            inspect_linked_dylibs(fixture(libs))

    def test_malformed_macho_rejected(self):
        with self.assertRaises(ValueError):
            inspect_linked_dylibs(bytes(100))
        with self.assertRaises(ValueError):
            inspect_linked_dylibs(b"\xcf\xfa\xed\xfe" + bytes(100))

    def test_valid_fake_ipa_metadata_and_no_runtime_claims(self):
        with TemporaryDirectory() as tmp:
            p = fake_zip(tmp, libs=[
                ("/System/Library/Frameworks/OpenGLES.framework/OpenGLES",
                 0xc),
                ("/usr/lib/libz.1.dylib", 0xc)])
            report = inspect_ipa_dependencies(p)
        self.assertEqual(report["linked_library_count"], 2)
        self.assertEqual(report["sdk_from_macho"], "6.1.0")
        self.assertEqual(report["minimum_ios_from_plist"], "4.3")
        self.assertTrue(report["opengles_linked"])
        self.assertTrue(report["opengles2_required_by_plist"])
        self.assertFalse(report["touchhle_compatibility_established"])
        self.assertFalse(report["hardware_capture_success_verified"])

    def test_ipa_missing_executable_fails_closed(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "fiction.ipa"
            with zipfile.ZipFile(p, "w") as z:
                z.writestr("Payload/Fiction.app/Info.plist", fake_plist())
            with self.assertRaises(ValueError):
                inspect_ipa_dependencies(p)

    def test_cli_output_only_under_local_reports(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            local = root / "local_reports"
            local.mkdir()
            ipa = fake_zip(tmp, libs=[("/usr/lib/libc_fake.dylib", 0xc)])
            report_path = local / "runtime-deps.json"
            with patch("heman_tools.frame_alignment.Path.cwd",
                       return_value=root):
                self.assertEqual(main([
                    "--ipa", str(ipa), "--out", str(report_path)]), 0)
                report = json.loads(report_path.read_text())
                self.assertEqual(report["linked_library_count"], 1)
                with self.assertRaises(ValueError):
                    main(["--ipa", str(ipa),
                          "--out", str(root / "public.json")])


if __name__ == "__main__":
    unittest.main()
