"""Stage121: synthetic-only descriptor-relative SD fixture source regression."""
from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from test_switch_sd_journal_audit import synthetic_record
from verify_nexium_sd_disk_receipt import (
    audit_confined_sd, read_confined_sd_slot_bytes,
)
from verify_nexium_corrupt_cold_restore import prepare_bad_sd
from verify_nexium_torn_slot_fallback import prepare_torn_newest


class Stage121ConfinedFixtureReads(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / "sd-source"
        self.lab = self.source / "sdmc" / "switch" / "heman_lore_lab"
        self.lab.mkdir(parents=True)
        self.raw = synthetic_record(7)
        (self.lab / "progress0.bin").write_bytes(self.raw)
        disk, issue = audit_confined_sd(self.source)
        self.assertIsNone(issue)
        self.receipt = {
            "classification": "guest_optical_round_trip_with_structural_emulator_sd_bytes",
            "actual_emulator_file_bytes_examined": True,
            "emulator_sd_slots": disk["slots"],
        }
        self.digest = hashlib.sha256(self.raw).hexdigest()

    def test_exact_bytes_read_from_unique_regular_slot(self):
        self.assertEqual(read_confined_sd_slot_bytes(self.source, 0, self.digest),
                         self.raw)

    def test_checksum_binding_rejects_stale_receipt(self):
        with self.assertRaisesRegex(ValueError, "no longer matches"):
            read_confined_sd_slot_bytes(self.source, 0, "0" * 64)

    def test_relative_path_and_parent_traversal_rejected(self):
        for root in (Path("relative-source"), self.root / ".." / "sd-source"):
            with self.subTest(root=str(root)):
                with self.assertRaisesRegex(ValueError, "Unsafe fixture"):
                    read_confined_sd_slot_bytes(root, 0, self.digest)

    def test_symlink_parent_rejected_without_reading_external_data(self):
        alias = self.root / "aliased-source"
        alias.symlink_to(self.source, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Unsafe or inaccessible"):
            read_confined_sd_slot_bytes(alias, 0, self.digest)

    def test_symlinked_leaf_rejected(self):
        original = self.lab / "progress0.bin"
        original.rename(self.lab / "backing.bin")
        original.symlink_to(self.lab / "backing.bin")
        with self.assertRaisesRegex(ValueError, "Unsafe or inaccessible"):
            read_confined_sd_slot_bytes(self.source, 0, self.digest)

    def test_hardlinked_leaf_rejected(self):
        path = self.lab / "progress0.bin"
        os.link(path, self.lab / "hardlink.bin")
        with self.assertRaisesRegex(ValueError, "not a unique regular"):
            read_confined_sd_slot_bytes(self.source, 0, self.digest)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "Requires FIFO")
    def test_fifo_slot_cannot_block_or_be_accepted(self):
        slot = self.lab / "progress0.bin"
        slot.unlink()
        os.mkfifo(slot)
        with self.assertRaisesRegex(ValueError, "not a unique regular"):
            read_confined_sd_slot_bytes(self.source, 0, self.digest)

    def test_ancestor_rename_and_symlink_swap_do_not_redirect_open_slot(self):
        original_open = os.open
        shifted = self.lab.with_name("retained-lab-folder")
        external = self.root / "external"
        external.mkdir()
        outside_record = synthetic_record(19)
        (external / "progress0.bin").write_bytes(outside_record)
        triggered = [False]

        def race_open(name, flags, *args, **kwargs):
            fd = original_open(name, flags, *args, **kwargs)
            if name == "heman_lore_lab" and not triggered[0]:
                triggered[0] = True
                self.lab.rename(shifted)
                self.lab.symlink_to(external, target_is_directory=True)
            return fd

        with patch("verify_nexium_sd_disk_receipt.os.open", side_effect=race_open):
            actual = read_confined_sd_slot_bytes(self.source, 0, self.digest)
        self.assertTrue(triggered[0])
        self.assertEqual(actual, self.raw)
        self.assertEqual((external / "progress0.bin").read_bytes(), outside_record)

    def test_both_fixture_generators_avoid_path_based_source_reads(self):
        with patch.object(Path, "read_bytes",
                          side_effect=AssertionError("Path.read_bytes is unsafe")):
            corrupt = prepare_bad_sd(
                self.source, self.root / "corrupt-fixture", self.receipt
            )
            torn = prepare_torn_newest(
                self.source, self.root / "torn-fixture", self.receipt
            )
        self.assertEqual(len(corrupt["slots"]), 1)
        self.assertEqual(torn["survivor_sha256"], self.digest)

    def test_input_slot_and_checksum_format_fail_closed(self):
        for slot, digest in ((2, self.digest), (-1, self.digest),
                             (0, self.digest.upper()), (0, "bad")):
            with self.subTest(slot=slot, digest=digest):
                with self.assertRaisesRegex(ValueError, "fixed slot"):
                    read_confined_sd_slot_bytes(self.source, slot, digest)


if __name__ == "__main__":
    unittest.main()
