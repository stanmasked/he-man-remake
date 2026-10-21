"""Stage133 mock-only contract tests. Not proof of guest execution."""
from __future__ import annotations

import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from audit_switch_sd_journal import fnv64
from instrument_nexium_lore_lab import RESAVE_EVENTS, COLD_RESTORE_EVENTS, FRAMES, instrument
from test_nexium_divergent_journal_priority import synthetic_complete_record
from test_nexium_hid_instrument import SOURCE
from verify_nexium_lore_lab_hid import expected_masks, LAB_BITS
from verify_nexium_sd_disk_receipt import audit_confined_sd
from verify_nexium_real_resave_generations import (
    validate_two_generations, verify_resave, verify_final_cold
)


class Stage133TwoActualGuestSaves(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        self.sd = self.root / "nexium-data"
        self.lab = self.sd / "sdmc" / "switch" / "heman_lore_lab"
        self.lab.mkdir(parents=True)
        self.first = self.root / "first"
        self.second = self.root / "second"
        self.third = self.root / "third"
        for folder in (self.first, self.second, self.third):
            folder.mkdir()
            (folder / "raster-exit-status.txt").write_text("0\n")
        original = bytearray(synthetic_complete_record(1))
        struct.pack_into("<f", original, 16 + 28, 24.0)
        struct.pack_into("<Q", original, 16 + 88, fnv64(original[16:16 + 88]))
        struct.pack_into("<Q", original, 112, fnv64(original[:112]))
        self.original = bytes(original)
        (self.lab / "progress0.bin").write_bytes(self.original)
        disk, problem = audit_confined_sd(self.sd)
        self.assertIsNone(problem)
        self.first_receipt = {
            "classification": "guest_optical_round_trip_with_structural_emulator_sd_bytes",
            "actual_emulator_file_bytes_examined": True,
            "emulator_sd_slots": disk["slots"],
        }
        second = bytearray(original)
        struct.pack_into("<f", second, 16 + 28, 50.0)
        struct.pack_into("<Q", second, 16 + 88, fnv64(second[16:16 + 88]))
        struct.pack_into("<Q", second, 8, 2)
        struct.pack_into("<Q", second, 112, fnv64(second[:112]))
        (self.lab / "progress1.bin").write_bytes(second)
        for folder, events in ((self.second, RESAVE_EVENTS),
                               (self.third, COLD_RESTORE_EVENTS)):
            log = [
                "Production runner complete: frames=540",
                "cycles=40000 svcs=5000 frames=525",
                *(f"HEMAN_LORE_HID frame={frame} {command}"
                  for frame, command in events),
                *(f"HEMAN_GUEST_FRAME_PNG frame={frame} dimensions=640x360 "
                  f"path={folder / f'raster-frame-{frame:04}.png'}"
                  for frame in FRAMES),
            ]
            (folder / "raster-runner.log").write_text("\n".join(log) + "\n")
        saved = {"lights": (1,1,1,1,1), "collected_count": 2,
                 "sd_status": 1, "native_player_x": 24}
        moved = dict(saved, native_player_x=50)
        fresh = {"lights": (0,0,0,0,0), "collected_count": 0,
                 "sd_status": 0, "native_player_x": 24}
        self.frames = {
            (self.first, 485): (saved, "older-pixels"),
            (self.second, 30): (fresh, "fresh-pixels"),
            (self.second, 130): (saved, "older-pixels"),
            (self.second, 265): (moved, "newer-pixels"),
            (self.second, 345): (moved, "newer-pixels"),
            (self.second, 445): (moved, "newer-pixels"),
            (self.third, 30): (fresh, "fresh-pixels"),
            (self.third, 518): (fresh, "fresh-pixels"),
            (self.third, 540): (moved, "newer-pixels"),
        }

    def resave(self):
        with patch("verify_nexium_real_resave_generations.load_guest_frame",
                   side_effect=lambda folder, frame: self.frames[(folder,frame)]):
            return verify_resave(
                self.first, self.second, self.sd, self.first_receipt)

    def cold(self, first_result):
        with patch("verify_nexium_real_resave_generations.load_guest_frame",
                   side_effect=lambda folder, frame: self.frames[(folder,frame)]):
            return verify_final_cold(
                self.first, self.second, self.third, self.sd,
                self.first_receipt, first_result)

    def test_never_edit_guest_nro_for_resave_schedule(self):
        rust = instrument(SOURCE)
        self.assertIn('phase == "resave"', rust)
        self.assertIn('phase == "restore"', rust)
        self.assertIn('90 => "buttons=ZL,R"', rust)
        self.assertIn('300 => "buttons=ZL,L"', rust)
        self.assertEqual(len(RESAVE_EVENTS), 10)
        self.assertEqual(expected_masks(RESAVE_EVENTS)[-3], LAB_BITS["ZL"] | LAB_BITS["L"])

    def test_distinct_second_guest_origin_journal_contract(self):
        result = self.resave()
        self.assertEqual(result["classification"],
                         "real_nexium_two_guest_origin_sd_save_generations")
        self.assertTrue(result["real_second_process_save_of_different_progress"])
        self.assertFalse(result["nintendo_switch_hardware_sd_verified"])

    def test_real_cold_latest_of_two_generations_contract(self):
        result = self.cold(self.resave())
        self.assertTrue(result["third_process_restored_newest_pixels_not_older"])
        self.assertTrue(result["both_original_guest_written_slot_hashes_unchanged"])
        self.assertFalse(result["real_power_loss_verified"])

    def test_second_generation_must_have_actual_different_player_x(self):
        (self.lab / "progress1.bin").write_bytes(self.original)
        with self.assertRaisesRegex(ValueError, "two usable ranked|differ unexpectedly"):
            self.resave()

    def test_first_guest_slot_cannot_be_mutated(self):
        old = self.lab / "progress0.bin"
        data = bytearray(old.read_bytes())
        data[40] ^= 1
        old.write_bytes(data)
        with self.assertRaisesRegex(ValueError, "two usable ranked|differ unexpectedly"):
            self.resave()

    def test_second_gameplay_input_cannot_be_forged_by_runner_schedule(self):
        path = self.second / "raster-runner.log"
        path.write_text(path.read_text().replace(
            "HEMAN_LORE_HID frame=300 buttons=ZL,L",
            "HEMAN_LORE_HID frame=300 buttons=ZL,R", 1))
        with self.assertRaisesRegex(ValueError, "unexpected save/movement"):
            self.resave()

    def test_guest_must_move_in_real_pixels_before_resaving(self):
        frame, digest = self.frames[(self.second, 265)]
        self.frames[(self.second, 265)] = (dict(frame, native_player_x=24), digest)
        with self.assertRaisesRegex(ValueError, "D-pad player move"):
            self.resave()

    def test_resave_must_preserve_second_scene_pixels(self):
        frame, _ = self.frames[(self.second, 345)]
        self.frames[(self.second, 345)] = (frame, "unsaved-pixels")
        with self.assertRaisesRegex(ValueError, "did not preserve moved"):
            self.resave()

    def test_older_first_process_missing_receipt_is_rejected(self):
        self.first_receipt["actual_emulator_file_bytes_examined"] = False
        with self.assertRaisesRegex(ValueError, "never proven"):
            self.resave()

    def test_cold_process_must_restore_newer_not_older_pixels(self):
        report = self.resave()
        old, digest = self.frames[(self.first, 485)]
        self.frames[(self.third, 540)] = (old, digest)
        with self.assertRaisesRegex(ValueError, "choose NEWEST"):
            self.cold(report)

    def test_cold_process_fails_if_guest_overwrites_second_slot(self):
        report = self.resave()
        slot = self.lab / "progress1.bin"
        raw = bytearray(slot.read_bytes())
        raw[24] ^= 1
        slot.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, "two usable ranked|modified"):
            self.cold(report)

    def test_cold_runner_must_not_inject_unexpected_move(self):
        report = self.resave()
        path = self.third / "raster-runner.log"
        path.write_text(path.read_text().replace(
            "HEMAN_LORE_HID frame=530 buttons=ZL,R",
            "HEMAN_LORE_HID frame=200 buttons=DRIGHT\n"
            "HEMAN_LORE_HID frame=530 buttons=ZL,R", 1))
        with self.assertRaisesRegex(ValueError, "unexpected save/movement"):
            self.cold(report)


if __name__ == "__main__":
    unittest.main()
