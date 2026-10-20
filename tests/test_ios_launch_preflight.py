"""Synthetic IPA + fictional Mach-O test fixtures; no commercial source bytes."""
from __future__ import annotations

import json
from pathlib import Path
import plistlib
import stat
import struct
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import warnings
import zipfile

from heman_tools.ios_launch_preflight import (
    inspect_macho_header, inspect_private_ipa_launch, main,
)


def fake_macho(*, cpu=12, subtype=9, filetype=2,
               min_ios=0x00040300, sdk=0x00060100,
               cryptid=0, signature=True, big_endian=False):
    fmt = ">" if big_endian else "<"
    commands = [
        struct.pack(fmt + "IIII", 0x25, 16, min_ios, sdk),
        struct.pack(fmt + "IIIII", 0x21, 20, 80, 8, cryptid),
    ]
    if signature:
        commands.append(struct.pack(fmt + "IIII", 0x1d, 16, 88, 8))
    sizeofcmds = sum(map(len, commands))
    magic = 0xfeedface
    header = struct.pack(fmt + "IiiIIII", magic, cpu, subtype, filetype,
                         len(commands), sizeofcmds, 0)
    return header + b"".join(commands) + b"\0" * (96 - len(header) - sizeofcmds)


def fake_plist(*, exe="MOTU", minimum="4.3"):
    return plistlib.dumps({
        "CFBundleIdentifier": "example.synthetic.private",
        "CFBundleVersion": "0.0.0",
        "CFBundleExecutable": exe,
        "MinimumOSVersion": minimum,
        "UIDeviceFamily": [2, 1],
        "UIRequiredDeviceCapabilities": ["opengles-2"],
        "UISupportedInterfaceOrientations": ["UIInterfaceOrientationLandscapeLeft"],
    })


def write_fixture(path, *, binary=None, plist=None, extras=None):
    files = {
        "Payload/Fiction.app/Info.plist": fake_plist() if plist is None else plist,
        "Payload/Fiction.app/MOTU": fake_macho() if binary is None else binary,
    }
    files.update(extras or {})
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for key, value in files.items():
            z.writestr(key, value)


class PrivateIOSLaunchTests(unittest.TestCase):
    def test_valid_synthetic_arch_and_runtime_evidence_is_false(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "invented.ipa"
            write_fixture(path)
            report = inspect_private_ipa_launch(path)
        self.assertEqual(report["macho_metadata"]["architecture"], "armv7")
        self.assertEqual(report["macho_metadata"]["minimum_ios_from_macho"], "4.3.0")
        self.assertEqual(report["macho_metadata"]["sdk_from_macho"], "6.1.0")
        self.assertEqual(report["macho_metadata"]["encryption_cryptid"], 0)
        self.assertEqual(report["metadata_consistency_blockers"], [])
        self.assertTrue(report["compatibility_hypotheses"][
            "opengles2_required_by_plist"])
        for key in ("real_ios_app_started", "ios_gameplay_frames_recorded",
                    "ios_touch_input_mapping_verified",
                    "original_ios_frame_rate_measured",
                    "code_signature_validity_verified",
                    "original_gameplay_physics_verified",
                    "automatic_collision_export_permitted"):
            self.assertIs(report[key], False)

    def test_thin_big_endian_fixture(self):
        result = inspect_macho_header(fake_macho(big_endian=True))
        self.assertEqual(result["architecture"], "armv7")
        self.assertEqual(result["encryption_cryptid"], 0)

    def test_cryptid_one_reports_blocker_but_never_evidence(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.ipa"
            write_fixture(p, binary=fake_macho(cryptid=1))
            report = inspect_private_ipa_launch(p)
        self.assertIn("binary_reports_encrypted_executable",
                      report["metadata_consistency_blockers"])
        self.assertFalse(report["real_ios_app_started"])

    def test_other_cpu_architecture_blocked(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.ipa"
            write_fixture(p, binary=fake_macho(cpu=7, subtype=3))
            report = inspect_private_ipa_launch(p)
        self.assertIn("executable_architecture_not_armv7",
                      report["metadata_consistency_blockers"])

    def test_non_executable_macho_filetype_blocked(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.ipa"
            write_fixture(p, binary=fake_macho(filetype=1))
            report = inspect_private_ipa_launch(p)
        self.assertIn("macho_filetype_not_executable",
                      report["metadata_consistency_blockers"])

    def test_minimum_ios_mismatch_is_blocker(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.ipa"
            write_fixture(p, plist=fake_plist(minimum="5.0"))
            report = inspect_private_ipa_launch(p)
        self.assertIn("plist_macho_minimum_version_unreconciled",
                      report["metadata_consistency_blockers"])

    def test_nonnumeric_minimum_ios_is_a_blocker_not_crash(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.ipa"
            write_fixture(p, plist=fake_plist(minimum="invalid"))
            report = inspect_private_ipa_launch(p)
        self.assertIn("plist_macho_minimum_version_unreconciled",
                      report["metadata_consistency_blockers"])

    def test_executable_name_with_path_rejected(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.ipa"
            write_fixture(p, plist=fake_plist(exe="../../evil"))
            with self.assertRaisesRegex(ValueError, "unsafe executable"):
                inspect_private_ipa_launch(p)

    def test_info_plist_executable_must_be_present(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.ipa"
            write_fixture(p, plist=fake_plist(exe="Absent"))
            with self.assertRaisesRegex(ValueError, "missing"):
                inspect_private_ipa_launch(p)

    def test_missing_info_plist_rejected(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.ipa"
            with zipfile.ZipFile(p, "w") as z:
                z.writestr("Payload/Fiction.app/MOTU", fake_macho())
            with self.assertRaises(ValueError):
                inspect_private_ipa_launch(p)

    def test_two_distinct_apps_rejected(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.ipa"
            write_fixture(p, extras={
                "Payload/Other.app/Info.plist": fake_plist()})
            with self.assertRaisesRegex(ValueError, "exactly one"):
                inspect_private_ipa_launch(p)

    def test_duplicate_zip_entry_rejected(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.ipa"
            write_fixture(p)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(p, "a") as z:
                    z.writestr("Payload/Fiction.app/MOTU", fake_macho())
            with self.assertRaisesRegex(ValueError, "ZIP entry"):
                inspect_private_ipa_launch(p)

    def test_symlink_and_traversal_zip_rejected(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.ipa"
            write_fixture(p, extras={
                "Payload/Fiction.app/../../escape": b"wrong"})
            with self.assertRaisesRegex(ValueError, "ZIP entry"):
                inspect_private_ipa_launch(p)
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.ipa"
            write_fixture(p)
            symlink = zipfile.ZipInfo("Payload/Fiction.app/link")
            symlink.create_system = 3
            symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
            with zipfile.ZipFile(p, "a") as z:
                z.writestr(symlink, b"../../outside")
            with self.assertRaisesRegex(ValueError, "ZIP entry"):
                inspect_private_ipa_launch(p)

    def test_truncated_command_header_rejected(self):
        raw = bytearray(fake_macho())
        struct.pack_into("<I", raw, 16, 512)
        with self.assertRaisesRegex(ValueError, "load commands"):
            inspect_macho_header(bytes(raw))

    def test_out_of_bounds_load_command_size_rejected(self):
        raw = bytearray(fake_macho())
        struct.pack_into("<I", raw, 32, 500)
        with self.assertRaisesRegex(ValueError, "load command size"):
            inspect_macho_header(bytes(raw))

    def test_fat_and_64bit_headers_fail_explicitly(self):
        for data in (b"\xca\xfe\xba\xbe" + b"\0" * 80,
                     b"\xcf\xfa\xed\xfe" + b"\0" * 80):
            with self.subTest(magic=data[:4]), self.assertRaises(ValueError):
                inspect_macho_header(data)

    def test_invalid_signature_region_fails(self):
        raw = bytearray(fake_macho())
        # Code signature 16-byte command begins at 28 + 16 + 20 = 64.
        struct.pack_into("<I", raw, 64 + 8, 1000000)
        with self.assertRaisesRegex(ValueError, "code-signature region"):
            inspect_macho_header(bytes(raw))

    def test_missing_signature_command_is_not_validity_attestation(self):
        result = inspect_macho_header(fake_macho(signature=False))
        self.assertFalse(result["code_signature_command_present"])
        self.assertFalse(result["code_signature_validity_verified"])

    def test_synthetic_report_excludes_binary_payload_and_paths(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "invented.ipa"
            write_fixture(p)
            result = inspect_private_ipa_launch(p)
        serial = json.dumps(result)
        self.assertNotIn("Payload/Fiction.app/", serial)
        self.assertNotIn("abcdefgh", serial)
        self.assertNotIn("executable_base64", serial)

    def test_private_cli_writes_only_under_ignored_directory(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            private = root / "local_reports"
            private.mkdir()
            ipa = root / "fictional.ipa"
            dest = private / "ios-exec-preflight.json"
            write_fixture(ipa)
            with patch("heman_tools.frame_alignment.Path.cwd",
                       return_value=root):
                self.assertEqual(main([
                    "--ipa", str(ipa), "--out", str(dest)]), 0)
                report = json.loads(dest.read_text())
                self.assertFalse(report["original_gameplay_physics_verified"])
                with self.assertRaises(ValueError):
                    main(["--ipa", str(ipa),
                          "--out", str(root / "public.json")])


if __name__ == "__main__":
    unittest.main()
