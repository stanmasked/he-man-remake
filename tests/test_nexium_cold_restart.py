"""Stage117 mock-only tests: no synthetic frame is a guest attestation."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from instrument_nexium_lore_lab import COLD_RESTORE_EVENTS, HID_EVENTS, FRAMES, instrument
from verify_nexium_cold_restart import attest_reboot
from verify_nexium_lore_lab_hid import expected_masks
from test_nexium_hid_instrument import SOURCE


class Stage117ColdRestartTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.first = self.root / "first"
        self.second = self.root / "second"
        self.first.mkdir()
        self.second.mkdir()
        for folder in (self.first, self.second):
            (folder / "raster-exit-status.txt").write_text("0\n")
        (self.first / "raster-runner.log").write_text(
            "Production runner complete: frames=540\n"
        )
        lines = [
            "Production runner complete: frames=540",
            "cycles=50000 svcs=2500 frames=530",
            *(f"HEMAN_LORE_HID frame={frame} {packet}"
              for frame, packet in COLD_RESTORE_EVENTS),
            *(f"HEMAN_GUEST_FRAME_PNG frame={frame} dimensions=640x360 "
              f"path={self.second / f'raster-frame-{frame:04}.png'}"
              for frame in FRAMES),
        ]
        (self.second / "raster-runner.log").write_text("\n".join(lines)+"\n")
        self.slots = [{"slot": 0, "status": "structurally_valid",
                       "generation": 1, "sha256": "a" * 64},
                      {"slot": 1, "status": "missing"}]
        self.first_receipt = {
            "classification": "guest_optical_round_trip_with_structural_emulator_sd_bytes",
            "actual_emulator_file_bytes_examined": True,
            "emulator_sd_slots": self.slots,
        }
        self.final_receipt = dict(self.first_receipt)
        empty = {"lights": (0,0,0,0,0), "collected_count": 0,
                 "sd_status": 0}
        saved = {"lights": (1,1,1,1,1), "collected_count": 2,
                 "sd_status": 1}
        self.snapshots = {
            (self.first, 485): (saved, "saved-image"),
            (self.second, 30): (empty, "new-process-empty-image"),
            (self.second, 518): (empty, "new-process-empty-image"),
            (self.second, 540): (saved, "saved-image"),
        }

    def run_oracle(self):
        with patch("verify_nexium_cold_restart.load_guest_frame",
                   side_effect=lambda folder, frame: self.snapshots[(folder, frame)]):
            return attest_reboot(self.first, self.second,
                                 self.first_receipt, self.final_receipt)

    def test_mock_positive_does_not_imply_hardware_or_ios_fidelity(self):
        receipt = self.run_oracle()
        self.assertTrue(receipt["independent_emulator_process_cold_restart_verified"])
        self.assertTrue(receipt["emulator_journal_bytes_unchanged_between_processes"])
        self.assertFalse(receipt["nintendo_switch_hardware_sd_verified"])
        self.assertFalse(receipt["power_loss_durability_verified"])
        self.assertFalse(receipt["original_ios_fidelity_verified"])

    def test_instrumentation_restores_only_in_separate_phase(self):
        output = instrument(SOURCE)
        self.assertIn("HEMAN_LORE_RESTART_PHASE", output)
        self.assertIn('145 => "buttons=L"', output)
        self.assertIn('470 => "buttons=ZL,L"', output)
        self.assertEqual(tuple(frame for frame, _ in COLD_RESTORE_EVENTS),
                         (520, 530, 535, 538))
        self.assertEqual(len(expected_masks(COLD_RESTORE_EVENTS)), 4)
        self.assertEqual(len(expected_masks(HID_EVENTS)), 26)

    def test_second_run_with_extra_save_command_rejected(self):
        log = self.second / "raster-runner.log"
        log.write_text(log.read_text().replace(
            "HEMAN_LORE_HID frame=520 buttons=ZL",
            "HEMAN_LORE_HID frame=470 buttons=ZL,L\n"
            "HEMAN_LORE_HID frame=520 buttons=ZL", 1))
        with self.assertRaisesRegex(ValueError, "unexpected guest HID action"):
            self.run_oracle()

    def test_missing_second_process_hid_event_rejected(self):
        log = self.second / "raster-runner.log"
        log.write_text(log.read_text().replace(
            "HEMAN_LORE_HID frame=530 buttons=ZL,R\n", ""))
        with self.assertRaisesRegex(ValueError, "unexpected guest HID action"):
            self.run_oracle()

    def test_changed_disk_bytes_rejected(self):
        self.final_receipt = dict(self.final_receipt, emulator_sd_slots=[
            {"slot": 0, "status": "structurally_valid", "generation": 1,
             "sha256": "b" * 64}, {"slot": 1, "status": "missing"}
        ])
        with self.assertRaisesRegex(ValueError, "changed during restore-only"):
            self.run_oracle()

    def test_no_green_second_restore_rejected(self):
        status, digest = self.snapshots[(self.second, 540)]
        self.snapshots[(self.second, 540)] = (
            dict(status, sd_status=2), digest
        )
        with self.assertRaisesRegex(ValueError, "successful SD restore"):
            self.run_oracle()

    def test_second_process_starts_with_no_earned_state(self):
        status, digest = self.snapshots[(self.second, 30)]
        self.snapshots[(self.second, 30)] = (
            dict(status, collected_count=1), digest
        )
        with self.assertRaisesRegex(ValueError, "fresh empty"):
            self.run_oracle()

    def test_second_process_must_have_completed_before_report(self):
        (self.second / "raster-exit-status.txt").write_text("124\n")
        with self.assertRaisesRegex(ValueError, "cleanly"):
            self.run_oracle()

    def test_first_and_second_cannot_be_same_folder(self):
        with self.assertRaisesRegex(ValueError, "identical"):
            attest_reboot(self.first, self.first,
                          self.first_receipt, self.final_receipt)

    def test_late_game_pixels_must_match_first_process(self):
        status, _ = self.snapshots[(self.second, 540)]
        self.snapshots[(self.second, 540)] = (status, "wrong-scene")
        with self.assertRaisesRegex(ValueError, "saved game pixels"):
            self.run_oracle()


if __name__ == "__main__":
    unittest.main()
