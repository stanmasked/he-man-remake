"""Synthetic-only tests for private multi-part backup transfer and restore."""
from __future__ import annotations

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile, ZIP_DEFLATED

from heman_tools.physics_shape_census import PREFIX, SCREENS
from heman_tools.private_asset_backup import (
    MANIFEST_NAME, OUTPUT_FILENAMES, PrivateBackupError, build_private_backup,
)
from heman_tools.private_archive_transfer import (
    TRANSFER_INDEX_NAME, prepare_private_transfer, restore_private_transfer,
)


class Stage216PrivateTransferTests(unittest.TestCase):
    def setUp(self):
        local = Path.cwd() / "local_reports"
        local.mkdir(exist_ok=True)
        temp = TemporaryDirectory(prefix="stage216-part-fixture-", dir=local)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.ipa = self.root / "synthetic.ipa"
        self.backup = self.root / "backup"
        self.parts = self.root / "upload-parts"
        self.restored = self.root / "downloaded-restore"
        with ZipFile(self.ipa, "w", compression=ZIP_DEFLATED) as zf:
            for screen in SCREENS:
                zf.writestr(
                    PREFIX + screen + "/textures/fake.png",
                    bytes(range(256)) * 5 + screen.encode(),
                )
                zf.writestr(
                    PREFIX + screen + "/sprites/fake.wad",
                    ("synthetic sprites only " + screen).encode(),
                )
            zf.writestr(PREFIX + "Audio/fake.caf", b"synthetic audio only")
            zf.writestr("Payload/MOTU.app/Info.plist", b"synthetic metadata")

    def _build_and_stage(self):
        build_private_backup(
            self.ipa, self.backup,
            expected_source_bytes=self.ipa.stat().st_size,
        )
        return prepare_private_transfer(self.backup, self.parts, part_bytes=256)

    def _restore(self, sha):
        return restore_private_transfer(
            self.parts, self.restored, expected_index_sha256=sha,
        )

    def test_roundtrip_with_independent_index_sha(self):
        result = self._build_and_stage()
        self.assertGreater(result["part_count"], 4)
        self.assertEqual(result["max_part_bytes"], 256)
        self.assertEqual(
            result["transfer_index_sha256"],
            hashlib.sha256((self.parts / TRANSFER_INDEX_NAME).read_bytes()).hexdigest(),
        )
        restored = self._restore(result["transfer_index_sha256"])
        self.assertEqual(restored["verified_archive_groups"], 3)
        self.assertEqual(restored["verified_file_groups"], 4)
        self.assertEqual(restored["verified_part_count"], result["part_count"])
        for file_name in (*OUTPUT_FILENAMES.values(), MANIFEST_NAME):
            self.assertEqual((self.backup / file_name).read_bytes(),
                             (self.restored / file_name).read_bytes())

    def test_tampered_index_sha_blocks_restore(self):
        self._build_and_stage()
        with self.assertRaisesRegex(PrivateBackupError, "trusted private SHA-256"):
            self._restore("0" * 64)
        self.assertFalse(self.restored.exists())

    def test_tampered_part_blocks_restore_and_publishes_nothing(self):
        result = self._build_and_stage()
        part_files = sorted(self.parts.glob("*.part*"))
        self.assertTrue(part_files)
        selected = part_files[0]
        blob = bytearray(selected.read_bytes())
        blob[0] ^= 1
        selected.write_bytes(blob)
        with self.assertRaisesRegex(PrivateBackupError, "Transfer part SHA-256 mismatch"):
            self._restore(result["transfer_index_sha256"])
        self.assertFalse(self.restored.exists())

    def test_missing_part_blocks_restore(self):
        result = self._build_and_stage()
        part_files = sorted(self.parts.glob("*.part*"))
        part_files[-1].unlink()
        with self.assertRaisesRegex(PrivateBackupError, "Missing or invalid transfer part size"):
            self._restore(result["transfer_index_sha256"])
        self.assertFalse(self.restored.exists())

    def test_no_overwrite_existing_checkpoint_or_restoration(self):
        result = self._build_and_stage()
        with self.assertRaisesRegex(PrivateBackupError, "already exists"):
            prepare_private_transfer(self.backup, self.parts, part_bytes=256)
        self._restore(result["transfer_index_sha256"])
        with self.assertRaisesRegex(PrivateBackupError, "already exists"):
            self._restore(result["transfer_index_sha256"])

    def test_invalid_chunk_sizes_fail_before_output(self):
        build_private_backup(self.ipa, self.backup, expected_source_bytes=self.ipa.stat().st_size)
        for n in (0, -1, 255, 32 * 1024 * 1024 + 1):
            with self.subTest(size=n):
                with self.assertRaisesRegex(PrivateBackupError, "between 256 bytes"):
                    prepare_private_transfer(self.backup, self.parts, part_bytes=n)
                self.assertFalse(self.parts.exists())


if __name__ == "__main__":
    unittest.main()
