"""Synthetic-only Stage216 private backup and recovery verification tests."""
from __future__ import annotations

import hashlib
import json
import stat
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import warnings
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED, ZipInfo

from heman_tools.physics_shape_census import PREFIX, SCREENS
from heman_tools.private_asset_backup import (
    MANIFEST_NAME,
    OUTPUT_FILENAMES,
    SHARED,
    PrivateBackupError,
    build_private_backup,
    verify_private_backup,
)


def make_synthetic_ipa(path: Path, *, omit_xlarge=False, duplicate=False) -> None:
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as source:
        for screen in SCREENS:
            if screen == SCREENS[1] and omit_xlarge:
                continue
            root = PREFIX + screen + "/"
            source.writestr(root + "textures/synthetic.png", b"PNG-fixture-only:" + screen.encode())
            source.writestr(root + "sprite/SpriteSeqData.wad", b"synthetic-sequence:" + screen.encode())
            if duplicate and screen == SCREENS[0]:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    source.writestr(root + "textures/synthetic.png", b"duplicate")
        source.writestr("Payload/MOTU.app/Info.plist", b"synthetic-non-screen-member")


class PrivateAssetBackupTests(unittest.TestCase):
    def setUp(self) -> None:
        root = Path.cwd() / "local_reports"
        root.mkdir(exist_ok=True)
        self.scope = TemporaryDirectory(prefix="stage216-synthetic-", dir=root)
        self.addCleanup(self.scope.cleanup)
        self.base = Path(self.scope.name)
        self.ipa = self.base / "fake-original.ipa"
        self.output = self.base / "backups"

    def _backup(self, **kwargs):
        return build_private_backup(
            self.ipa,
            self.output,
            expected_source_bytes=self.ipa.stat().st_size,
            canonical_source_url="https://drive.google.com/file/d/SYNTHETIC/view",
            **kwargs,
        )

    def test_two_packs_archive_losslessly_with_deterministic_sha256(self):
        make_synthetic_ipa(self.ipa)
        source_sha = hashlib.sha256(self.ipa.read_bytes()).hexdigest()
        manifest = self._backup(expected_source_sha256=source_sha)
        self.assertEqual(manifest["source"]["sha256"], source_sha)
        self.assertTrue(manifest["source"]["zip_crc_verified"])
        self.assertFalse(manifest["backed_up_to_drive"])
        self.assertFalse(manifest["drive_readback_verified"])
        self.assertFalse(manifest["original_runtime_pixel_parity_verified"])
        self.assertEqual(set(manifest["screen_packs"]), set(SCREENS))
        self.assertEqual(manifest["shared_resources"]["file_count"], 1)
        self.assertEqual(manifest["application_file_count"], 5)
        self.assertEqual(manifest["shared_resources"]["files"][0]["path"], "Info.plist")
        with ZipFile(self.output / OUTPUT_FILENAMES[SHARED], "r") as shared_zip:
            self.assertEqual(shared_zip.read("Info.plist"), b"synthetic-non-screen-member")
        for screen in SCREENS:
            pack = manifest["screen_packs"][screen]
            self.assertEqual(pack["file_count"], 2)
            self.assertEqual(len(pack["files"]), 2)
            self.assertNotIn("Info.plist", json.dumps(pack))
            with ZipFile(self.output / OUTPUT_FILENAMES[screen], "r") as zf:
                self.assertEqual(
                    zf.read("textures/synthetic.png"),
                    b"PNG-fixture-only:" + screen.encode(),
                )
        expected_manifest_sha = hashlib.sha256(
            (self.output / MANIFEST_NAME).read_bytes()
        ).hexdigest()
        self.assertEqual(
            set(verify_private_backup(
                self.output / MANIFEST_NAME, self.output,
                expected_manifest_sha256=expected_manifest_sha,
            )),
            set(SCREENS) | {SHARED},
        )
        self.assertEqual(
            {v["verified"] for v in verify_private_backup(self.output / MANIFEST_NAME, self.output).values()},
            {True},
        )
        second = self.base / "backups-copy"
        again = build_private_backup(
            self.ipa,
            second,
            expected_source_bytes=self.ipa.stat().st_size,
            expected_source_sha256=source_sha,
        )
        for screen in SCREENS:
            self.assertEqual(
                again["screen_packs"][screen]["archive_sha256"],
                manifest["screen_packs"][screen]["archive_sha256"],
            )
        self.assertEqual(
            again["shared_resources"]["archive_sha256"],
            manifest["shared_resources"]["archive_sha256"],
        )

    def test_wrong_byte_size_blocks_backup_before_output(self):
        make_synthetic_ipa(self.ipa)
        with self.assertRaisesRegex(PrivateBackupError, "Drive byte size"):
            build_private_backup(self.ipa, self.output, expected_source_bytes=self.ipa.stat().st_size + 1)
        self.assertFalse(self.output.exists())

    def test_wrong_source_hash_rejected(self):
        make_synthetic_ipa(self.ipa)
        with self.assertRaisesRegex(PrivateBackupError, "canonical source"):
            self._backup(expected_source_sha256="0" * 64)

    def test_missing_resolution_pack_refused(self):
        make_synthetic_ipa(self.ipa, omit_xlarge=True)
        with self.assertRaisesRegex(PrivateBackupError, "Both original resolution packs"):
            self._backup()
        self.assertFalse((self.output / MANIFEST_NAME).exists())

    def test_duplicate_source_path_rejected(self):
        make_synthetic_ipa(self.ipa, duplicate=True)
        with self.assertRaisesRegex(PrivateBackupError, "duplicate"):
            self._backup()

    def test_corrupted_source_member_crc_refuses_backup(self):
        with ZipFile(self.ipa, "w", compression=ZIP_STORED) as source:
            source.writestr(
                PREFIX + SCREENS[0] + "/textures/synthetic.png",
                b"original-good-bytes-0000",
            )
            source.writestr(
                PREFIX + SCREENS[1] + "/textures/synthetic.png",
                b"original-good-bytes-0000",
            )
        with ZipFile(self.ipa, "r") as source:
            info = source.getinfo(PREFIX + SCREENS[0] + "/textures/synthetic.png")
            local_data_offset = (
                info.header_offset + 30 + len(info.filename.encode("utf-8"))
                + len(info.extra)
            )
        with self.ipa.open("r+b") as damaged:
            damaged.seek(local_data_offset)
            byte = damaged.read(1)
            damaged.seek(local_data_offset)
            damaged.write(bytes([byte[0] ^ 1]))
        with self.assertRaisesRegex(PrivateBackupError, "integrity test failed"):
            self._backup()
        self.assertFalse((self.output / MANIFEST_NAME).exists())

    def test_unsafe_path_refused_even_with_complete_resolution_packs(self):
        make_synthetic_ipa(self.ipa)
        with ZipFile(self.ipa, "a") as source:
            source.writestr(
                PREFIX + SCREENS[0] + "/../escape.txt",
                b"synthetic-unsafe-traversal",
            )
        with self.assertRaisesRegex(PrivateBackupError, "unsafe ZIP member paths"):
            self._backup()
        self.assertFalse((self.output / MANIFEST_NAME).exists())

    def test_unix_symlink_member_refused(self):
        make_synthetic_ipa(self.ipa)
        with ZipFile(self.ipa, "a") as source:
            link = ZipInfo(PREFIX + "LinkToOriginal")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            source.writestr(link, b"../../outside")
        with self.assertRaisesRegex(PrivateBackupError, "Encrypted or symlink"):
            self._backup()
        self.assertFalse((self.output / MANIFEST_NAME).exists())

    def test_missing_shared_files_still_yields_valid_empty_archive(self):
        with ZipFile(self.ipa, "w", compression=ZIP_DEFLATED) as source:
            for screen in SCREENS:
                source.writestr(
                    PREFIX + screen + "/sprite/synthetic.wad",
                    b"fake-test-data",
                )
        manifest = self._backup()
        self.assertEqual(manifest["shared_resources"]["file_count"], 0)
        with ZipFile(self.output / OUTPUT_FILENAMES[SHARED], "r") as shared:
            self.assertEqual(shared.namelist(), [])
        self.assertEqual(len(verify_private_backup(
            self.output / MANIFEST_NAME, self.output,
        )), 3)

    def test_non_zip_source_rejected(self):
        self.ipa.write_bytes(b"not-a-valid-IPA")
        with self.assertRaises(PrivateBackupError):
            self._backup()

    def test_existing_checkpoint_cannot_be_overwritten(self):
        make_synthetic_ipa(self.ipa)
        self._backup()
        with self.assertRaisesRegex(PrivateBackupError, "already exists"):
            self._backup()

    def test_modified_archive_detected_during_readback(self):
        make_synthetic_ipa(self.ipa)
        self._backup()
        with (self.output / OUTPUT_FILENAMES[SCREENS[0]]).open("ab") as f:
            f.write(b"unexpected-extra-data")
        with self.assertRaisesRegex(PrivateBackupError, "SHA-256 mismatch"):
            verify_private_backup(self.output / MANIFEST_NAME, self.output)

    def test_wrong_trusted_manifest_checksum_refused(self):
        make_synthetic_ipa(self.ipa)
        self._backup()
        with self.assertRaisesRegex(PrivateBackupError, "trusted checkpoint"):
            verify_private_backup(
                self.output / MANIFEST_NAME,
                self.output,
                expected_manifest_sha256="0" * 64,
            )

    def test_repacked_member_not_counted_as_shared_twice(self):
        make_synthetic_ipa(self.ipa)
        result = self._backup()
        self.assertEqual(
            sum(result["screen_packs"][screen]["file_count"] for screen in SCREENS)
            + result["shared_resources"]["file_count"],
            result["application_file_count"],
        )

    def test_corrupt_shared_archive_is_detected(self):
        make_synthetic_ipa(self.ipa)
        self._backup()
        with (self.output / OUTPUT_FILENAMES[SHARED]).open("ab") as f:
            f.write(b"tamper shared bundle")
        with self.assertRaisesRegex(PrivateBackupError, "SHA-256 mismatch"):
            verify_private_backup(self.output / MANIFEST_NAME, self.output)

    def test_outside_ignored_worktree_is_rejected(self):
        make_synthetic_ipa(self.ipa)
        with TemporaryDirectory() as outside:
            with self.assertRaisesRegex(PrivateBackupError, "local_reports"):
                build_private_backup(
                    self.ipa,
                    Path(outside) / "backup",
                    expected_source_bytes=self.ipa.stat().st_size,
                )

    def test_malformed_sha_rejected(self):
        make_synthetic_ipa(self.ipa)
        with self.assertRaisesRegex(PrivateBackupError, "64 lowercase"):
            self._backup(expected_source_sha256="not-a-hash")

    def test_readback_missing_archive_rejected(self):
        make_synthetic_ipa(self.ipa)
        self._backup()
        (self.output / OUTPUT_FILENAMES[SCREENS[1]]).unlink()
        with self.assertRaisesRegex(PrivateBackupError, "Missing"):
            verify_private_backup(self.output / MANIFEST_NAME, self.output)


if __name__ == "__main__":
    unittest.main()
