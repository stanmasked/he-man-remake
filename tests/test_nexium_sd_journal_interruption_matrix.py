"""Stage135 structural fault matrix for EVERY byte of a fictional 120-byte SD record.

Asset-free host-only failure-injection tests: these DO NOT emulate an actual
fsdevCommitDevice(), Switch NAND/SD power cut, or the runtime C99 loader.
The tests independently check that the older valid journal remains the only
structurally eligible candidate across every truncation boundary and every
one-bit perturbation of a newer record.
"""
from __future__ import annotations

import hashlib
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from audit_switch_sd_journal import (
    RECORD_SIZE, audit_directory, decode_record, fnv64,
)
from test_switch_sd_journal_audit import synthetic_record


class Stage135CompleteJournalInterruptionMatrix(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.older = synthetic_record(generation=17)
        self.newer = bytearray(synthetic_record(generation=18))
        # Deliberately DIFFERENT, structurally valid synthetic player
        # position so that choosing the wrong generation is observable.
        struct.pack_into("<f", self.newer, 16 + 28, 51.0)
        struct.pack_into("<Q", self.newer, 16 + 88,
                         fnv64(self.newer[16:16 + 88]))
        struct.pack_into("<Q", self.newer, 112, fnv64(self.newer[:112]))
        self.newer = bytes(self.newer)
        self.old_slot = self.root / "progress0.bin"
        self.new_slot = self.root / "progress1.bin"
        self.old_slot.write_bytes(self.older)
        self.old_sha256 = hashlib.sha256(self.older).hexdigest()
        self.assertEqual(len(self.older), RECORD_SIZE)
        self.assertEqual(len(self.newer), RECORD_SIZE)
        self.assertEqual(decode_record(self.older)["status"], "structurally_valid")
        self.assertEqual(decode_record(self.newer)["status"], "structurally_valid")
        self.assertNotEqual(self.older, self.newer)

    def assert_only_old_candidate(self, reason=None):
        report = audit_directory(self.root)
        self.assertEqual(report["structurally_valid_slot_count"], 1)
        self.assertEqual(report["latest_structural_candidate_slot"], 0)
        self.assertEqual(report["slots"][0]["sha256"], self.old_sha256)
        self.assertEqual(report["slots"][0]["generation"], 17)
        self.assertEqual(report["slots"][1]["status"], "invalid")
        if reason:
            self.assertEqual(report["slots"][1]["reason"], reason)
        self.assertEqual(self.old_slot.read_bytes(), self.older)

    def test_every_incomplete_write_boundary_falls_back_to_old(self):
        for length in range(RECORD_SIZE):
            with self.subTest(new_record_length=length):
                self.new_slot.write_bytes(self.newer[:length])
                self.assert_only_old_candidate("wrong_length")

    def test_every_single_bit_flip_in_full_new_record_falls_back(self):
        for offset in range(RECORD_SIZE):
            with self.subTest(byte_offset=offset):
                bad = bytearray(self.newer)
                bad[offset] ^= 0x01
                self.new_slot.write_bytes(bad)
                self.assert_only_old_candidate()

    def test_complete_newer_generation_supersedes_older(self):
        self.new_slot.write_bytes(self.newer)
        report = audit_directory(self.root)
        self.assertEqual(report["structurally_valid_slot_count"], 2)
        self.assertEqual(report["latest_structural_candidate_slot"], 1)
        self.assertEqual(report["slots"][0]["generation"], 17)
        self.assertEqual(report["slots"][1]["generation"], 18)
        self.assertNotEqual(report["slots"][0]["sha256"],
                            report["slots"][1]["sha256"])
        self.assertEqual(self.old_slot.read_bytes(), self.older)

    def test_extra_postrecord_bytes_never_count_as_atomic_commit(self):
        for n in (1, 8, 120):
            with self.subTest(extra_bytes=n):
                self.new_slot.write_bytes(self.newer + bytes([0xA5]) * n)
                self.assert_only_old_candidate("wrong_length")

    def test_second_slot_inner_checksum_mismatch_even_if_outer_repaired(self):
        for offset in (16 + 28, 16 + 48, 16 + 82):
            with self.subTest(snapshot_corruption_byte=offset):
                bad = bytearray(self.newer)
                bad[offset] ^= 1
                struct.pack_into("<Q", bad, 112, fnv64(bad[:112]))
                self.new_slot.write_bytes(bad)
                self.assert_only_old_candidate("snapshot_checksum")

    def test_world_seal_mismatch_refuses_false_binding_consensus(self):
        bad_world = bytearray(self.newer)
        struct.pack_into("<Q", bad_world, 16 + 8, 123456)
        struct.pack_into("<Q", bad_world, 16 + 88,
                         fnv64(bad_world[16:16 + 88]))
        struct.pack_into("<Q", bad_world, 112,
                         fnv64(bad_world[:112]))
        self.new_slot.write_bytes(bad_world)
        report = audit_directory(self.root)
        # An offline verifier lacks the live world. It must not assert a
        # latest compatible snapshot when two valid records disagree.
        self.assertTrue(report["ambiguous_world_binding"])
        self.assertIsNone(report["latest_structural_candidate_slot"])
        self.assertEqual(report["structurally_valid_slot_count"], 2)
        self.assertEqual(self.old_slot.read_bytes(), self.older)


if __name__ == "__main__":
    unittest.main()
