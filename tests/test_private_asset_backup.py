"""Synthetic-only Stage216 private backup and recovery verification tests."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import warnings
from zipfile import ZipFile, ZIP_DEFLATED

from heman_tools.physics_shape_census import PREFIX, SCREENS
from heman_tools.private_asset_backup import (
    MANIFEST_NAME,
    OUTPUT_FILENAMES,
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
