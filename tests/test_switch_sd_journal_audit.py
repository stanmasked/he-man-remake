"""Synthetic-only tests for a read-only local SD-journal structural audit."""
from __future__ import annotations

import contextlib
import io
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_switch_sd_journal import audit_directory, decode_record, fnv64, main


def synthetic_record(generation=1, seal=1234, binding=(0, 1, 2)):
    """Construct test bytes only; no original game contents or asset sources."""
    snap = bytearray(96)
    snap[:4] = b"H1S1"
    snap[4:8] = b"\x01\x00\x60\x00"
    struct.pack_into("<Q", snap, 8, seal)
    struct.pack_into("<III", snap, 16, *binding)
    struct.pack_into("<5f", snap, 28, 24.0, 32.0, 0.0, 0.0, 0.0)
    struct.pack_into("<I", snap, 48, 30)
    snap[76] = 1
    snap[82] = 2
    snap[83] = 1
    struct.pack_into("<Q", snap, 88, fnv64(snap[:88]))
    raw = bytearray(120)
    raw[:4] = b"H1J1"
    raw[4] = 1
    struct.pack_into("<Q", raw, 8, generation)
    raw[16:112] = snap
    struct.pack_into("<Q", raw, 112, fnv64(raw[:112]))
    return bytes(raw)


class ReadOnlyJournalAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def put(self, slot, data):
        path = self.directory / f"progress{slot}.bin"
        path.write_bytes(data)
        return path

    def test_empty_directory_is_not_success(self):
        report = audit_directory(self.directory)
        self.assertEqual([s["status"] for s in report["slots"]],
                         ["missing", "missing"])
        self.assertIsNone(report["latest_structural_candidate_slot"])
        self.assertFalse(report["real_sd_commit_or_cold_boot_verified"])

    def test_two_valid_slots_prefer_latest_generation(self):
        older = synthetic_record(1)
        newer = synthetic_record(2)
        self.put(0, older)
        self.put(1, newer)
        report = audit_directory(self.directory)
        self.assertEqual(report["latest_structural_candidate_slot"], 1)
        self.assertEqual(report["structurally_valid_slot_count"], 2)
        self.assertEqual(report["slots"][1]["generation"], 2)
        self.assertFalse(report["runtime_world_compatibility_verified"])
        self.assertEqual((self.directory / "progress0.bin").read_bytes(), older)
        self.assertEqual((self.directory / "progress1.bin").read_bytes(), newer)

    def test_corrupt_newest_falls_back_to_older(self):
        self.put(0, synthetic_record(1))
        broken = bytearray(synthetic_record(2))
        broken[24] ^= 0x40
        self.put(1, broken)
        report = audit_directory(self.directory)
        self.assertEqual(report["latest_structural_candidate_slot"], 0)
        self.assertEqual(report["slots"][1]["reason"], "journal_checksum")

    def test_truncation_and_extra_byte_are_rejected(self):
        for data in (synthetic_record()[:60], synthetic_record() + b"\xff"):
            with self.subTest(length=len(data)):
                self.put(0, data)
                report = audit_directory(self.directory)
                self.assertEqual(report["slots"][0]["reason"], "wrong_length")
                self.assertIsNone(report["latest_structural_candidate_slot"])

    def test_unsupported_schema_with_recalculated_outer_checksum_rejected(self):
        raw = bytearray(synthetic_record())
        raw[4] = 2
        struct.pack_into("<Q", raw, 112, fnv64(raw[:112]))
        self.assertEqual(decode_record(raw)["reason"], "unsupported_journal_version")

    def test_invalid_inner_digest_with_valid_outer_digest_rejected(self):
        raw = bytearray(synthetic_record())
        raw[44] ^= 0x20
        struct.pack_into("<Q", raw, 112, fnv64(raw[:112]))
        self.assertEqual(decode_record(raw)["reason"], "snapshot_checksum")

    def test_two_structural_worlds_cannot_choose_compatible_candidate(self):
        self.put(0, synthetic_record(1, seal=1234))
        self.put(1, synthetic_record(2, seal=5678))
        report = audit_directory(self.directory)
        self.assertTrue(report["ambiguous_world_binding"])
        self.assertIsNone(report["latest_structural_candidate_slot"])

    def test_reject_symlink_without_reading_target(self):
        target = self.directory / "private-unrelated-file"
        target.write_bytes(synthetic_record())
        (self.directory / "progress0.bin").symlink_to(target)
        report = audit_directory(self.directory)
        self.assertEqual(report["slots"][0]["reason"], "symlink_disallowed")
        self.assertEqual(target.read_bytes(), synthetic_record())

    def test_cli_prints_metadata_not_record_bytes_and_exit_code(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main([str(self.directory)]), 2)
        self.assertEqual(json.loads(out.getvalue())["structurally_valid_slot_count"], 0)
        raw = synthetic_record()
        self.put(0, raw)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main([str(self.directory)]), 0)
        report = json.loads(out.getvalue())
        self.assertEqual(report["latest_structural_candidate_slot"], 0)
        self.assertNotIn("raw_bytes", out.getvalue())
        self.assertNotIn(str(self.directory), out.getvalue())
        self.assertEqual((self.directory / "progress0.bin").read_bytes(), raw)


if __name__ == "__main__":
    unittest.main()
