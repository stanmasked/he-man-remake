"""Stage118 synthetic-only failure injection. NEVER certifies a guest run."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from audit_switch_sd_journal import decode_record
from instrument_nexium_lore_lab import FRAMES, COLD_RESTORE_EVENTS
from test_switch_sd_journal_audit import synthetic_record
from verify_nexium_corrupt_cold_restore import prepare_bad_sd, verify_failed_restore
from verify_nexium_sd_disk_receipt import audit_confined_sd


class Stage118FaultTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.source = self.base / "source"
        self.target = self.base / "fault-target"
        self.source_lab = self.source / "sdmc" / "switch" / "heman_lore_lab"
        self.source_lab.mkdir(parents=True)
        self.original = synthetic_record(1)
        (self.source_lab / "progress0.bin").write_bytes(self.original)
        disk, problem = audit_confined_sd(self.source)
        self.assertIsNone(problem)
        self.receipt = {
            "classification": "guest_optical_round_trip_with_structural_emulator_sd_bytes",
            "actual_emulator_file_bytes_examined": True,
            "emulator_sd_slots": disk["slots"],
        }
        self.folder = self.base / "fault-evidence"
        self.folder.mkdir()
        (self.folder / "raster-exit-status.txt").write_text("0\n")
        lines = [
            "Production runner complete: frames=540",
            "cycles=50000 svcs=2000 frames=530",
            *(f"HEMAN_LORE_HID frame={f} {packet}"
              for f, packet in COLD_RESTORE_EVENTS),
            *(f"HEMAN_GUEST_FRAME_PNG frame={f} dimensions=640x360 "
              f"path={self.folder / f'raster-frame-{f:04}.png'}"
              for f in FRAMES),
        ]
        (self.folder / "raster-runner.log").write_text("\n".join(lines)+"\n")
        empty = {"lights": (0, 0, 0, 0, 0), "collected_count": 0,
                 "sd_status": 0}
        red = dict(empty, sd_status=2)
        self.frames = {
            30: (empty, "empty-scene"),
            518: (empty, "empty-scene"),
            540: (red, "empty-scene"),
        }

    def make_fixture(self):
        return prepare_bad_sd(self.source, self.target, self.receipt)

    def verify_mock(self, manifest):
        with patch("verify_nexium_corrupt_cold_restore.load_guest_frame",
                   side_effect=lambda folder, frame: self.frames[frame]):
            return verify_failed_restore(self.folder, self.target, manifest)

    def test_corrupt_exact_generated_journal_without_touching_original(self):
        manifest = self.make_fixture()
        self.assertEqual(manifest["slots"][0]["slot"], 0)
        self.assertEqual((self.source_lab / "progress0.bin").read_bytes(), self.original)
        bad = (self.target / "sdmc" / "switch" / "heman_lore_lab" /
               "progress0.bin").read_bytes()
        self.assertNotEqual(bad, self.original)
        self.assertEqual(decode_record(bad)["reason"], "journal_checksum")
        self.assertFalse(manifest["guest_emulator_execution_verified"])

    def test_positive_mock_fault_receipt_is_not_hardware_proof(self):
        manifest = self.make_fixture()
        result = self.verify_mock(manifest)
        self.assertEqual(result["classification"],
                         "real_nexium_cold_process_corrupted_sd_rejected")
        self.assertTrue(result["failed_restore_preserved_all_game_pixels"])
        self.assertFalse(result["nintendo_switch_hardware_sd_verified"])

    def test_never_modify_source_root(self):
        with self.assertRaisesRegex(ValueError, "Refuse to overwrite"):
            prepare_bad_sd(self.source, self.source, self.receipt)
        self.assertEqual((self.source_lab / "progress0.bin").read_bytes(), self.original)

    def test_never_overwrite_existing_fault_target(self):
        self.target.mkdir()
        with self.assertRaisesRegex(ValueError, "must not exist"):
            self.make_fixture()

    def test_reject_stale_first_receipt(self):
        self.receipt["emulator_sd_slots"] = []
        with self.assertRaisesRegex(ValueError, "differs"):
            self.make_fixture()

    def test_reject_unconfirmed_initial_sd(self):
        self.receipt["classification"] = "no_guest_sd_success_claim"
        with self.assertRaisesRegex(ValueError, "no independent"):
            self.make_fixture()

    def test_guest_accepting_bad_sd_is_a_failure(self):
        manifest = self.make_fixture()
        self.frames[540] = (dict(self.frames[540][0], sd_status=1), "empty-scene")
        with self.assertRaisesRegex(ValueError, "accepted instead of rejected"):
            self.verify_mock(manifest)

    def test_rejected_sd_must_not_mutate_game_pixels(self):
        manifest = self.make_fixture()
        self.frames[540] = (self.frames[540][0], "corrupted-restored-scene")
        with self.assertRaisesRegex(ValueError, "mutated the guest"):
            self.verify_mock(manifest)

    def test_actual_corrupt_file_must_survive_guest_process_unchanged(self):
        manifest = self.make_fixture()
        slot = self.target / "sdmc" / "switch" / "heman_lore_lab" / "progress0.bin"
        raw = bytearray(slot.read_bytes())
        raw[25] ^= 0x08
        slot.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, "fixture bytes mutated"):
            self.verify_mock(manifest)

    def test_no_spurious_save_command_in_fault_process(self):
        manifest = self.make_fixture()
        path = self.folder / "raster-runner.log"
        log = path.read_text()
        path.write_text(log.replace(
            "HEMAN_LORE_HID frame=530 buttons=ZL,R",
            "HEMAN_LORE_HID frame=470 buttons=ZL,L\n"
            "HEMAN_LORE_HID frame=530 buttons=ZL,R", 1))
        with self.assertRaisesRegex(ValueError, "other than restore"):
            self.verify_mock(manifest)

    def test_fault_process_must_fully_exit(self):
        manifest = self.make_fixture()
        (self.folder / "raster-exit-status.txt").write_text("124\n")
        with self.assertRaisesRegex(ValueError, "did not exit cleanly"):
            self.verify_mock(manifest)

    def test_missing_real_guest_frame_receipt_rejected(self):
        manifest = self.make_fixture()
        path = self.folder / "raster-runner.log"
        path.write_text(path.read_text().replace(
            "HEMAN_GUEST_FRAME_PNG frame=540 dimensions", "LOST frame=540 dimensions"
        ))
        with self.assertRaisesRegex(ValueError, "complete guest frame"):
            self.verify_mock(manifest)


if __name__ == "__main__":
    unittest.main()
