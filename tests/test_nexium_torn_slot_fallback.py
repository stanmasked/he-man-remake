"""Stage119 mock-only test suite, never runtime/hardware proof."""
from __future__ import annotations
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from audit_switch_sd_journal import decode_record
from instrument_nexium_lore_lab import COLD_RESTORE_EVENTS, FRAMES
from test_switch_sd_journal_audit import synthetic_record
from verify_nexium_sd_disk_receipt import audit_confined_sd
from verify_nexium_torn_slot_fallback import (
    prepare_torn_newest, verify_fallback, lab,
)


class Stage119TornNewestFallbackTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / "source"
        self.target = self.root / "torn"
        lab(self.source).mkdir(parents=True)
        self.original = synthetic_record(7)
        (lab(self.source) / "progress0.bin").write_bytes(self.original)
        disk, err = audit_confined_sd(self.source)
        self.assertIsNone(err)
        self.initial = {
            "classification": "guest_optical_round_trip_with_structural_emulator_sd_bytes",
            "actual_emulator_file_bytes_examined": True,
            "emulator_sd_slots": disk["slots"],
        }
        self.first = self.root / "first"
        self.cold = self.root / "cold"
        self.first.mkdir()
        self.cold.mkdir()
        for folder in (self.first, self.cold):
            (folder / "raster-exit-status.txt").write_text("0\n")
        lines = [
            "Production runner complete: frames=540",
            "cycles=50000 svcs=2000 frames=530",
            *(f"HEMAN_LORE_HID frame={f} {button}"
              for f, button in COLD_RESTORE_EVENTS),
            *(f"HEMAN_GUEST_FRAME_PNG frame={f} dimensions=640x360 "
              f"path={self.cold / f'raster-frame-{f:04}.png'}"
              for f in FRAMES),
        ]
        (self.cold / "raster-runner.log").write_text("\n".join(lines)+"\n")
        saved = {"lights": (1,1,1,1,1), "collected_count": 2, "sd_status": 1}
        fresh = {"lights": (0,0,0,0,0), "collected_count": 0, "sd_status": 0}
        self.frames = {
            (self.first, 485): (saved, "saved-pixels"),
            (self.cold, 30): (fresh, "empty-pixels"),
            (self.cold, 518): (fresh, "empty-pixels"),
            (self.cold, 540): (saved, "saved-pixels"),
        }

    def prepare(self):
        return prepare_torn_newest(self.source, self.target, self.initial)

    def oracle(self, manifest):
        with patch("verify_nexium_torn_slot_fallback.load_guest_frame",
                   side_effect=lambda folder, frame: self.frames[(folder,frame)]):
            return verify_fallback(self.first, self.cold, self.target, manifest)

    def test_create_torn_newest_from_valid_guest_snapshot(self):
        manifest = self.prepare()
        self.assertEqual(manifest["source_initial_valid_generation"], 7)
        self.assertEqual(manifest["torn_newer_expected_generation"], 8)
        self.assertEqual((lab(self.target) / "progress0.bin").read_bytes(),
                         self.original)
        newest = (lab(self.target) / "progress1.bin").read_bytes()
        self.assertEqual(len(newest), 64)
        self.assertEqual(decode_record(newest)["reason"], "wrong_length")
        self.assertEqual((lab(self.source) / "progress0.bin").read_bytes(),
                         self.original)
        self.assertFalse(manifest["real_power_interruption_observed"])

    def test_positive_synthetic_guest_oracle_never_claims_hardware(self):
        manifest = self.prepare()
        result = self.oracle(manifest)
        self.assertTrue(result["older_slot_native_recovery_verified"])
        self.assertTrue(result["both_slots_unchanged_in_restore_only_process"])
        self.assertFalse(result["actual_power_interruption_verified"])

    def test_torn_newest_must_not_be_accepted(self):
        manifest = self.prepare()
        old, digest = self.frames[(self.cold, 540)]
        self.frames[(self.cold, 540)] = (dict(old, sd_status=2), digest)
        with self.assertRaisesRegex(ValueError, "refused older valid slot"):
            self.oracle(manifest)

    def test_torn_slot_load_must_match_original_guest_scene(self):
        manifest = self.prepare()
        old, _ = self.frames[(self.cold, 540)]
        self.frames[(self.cold, 540)] = (old, "unrelated-pixels")
        with self.assertRaisesRegex(ValueError, "reproduce genuine saved pixels"):
            self.oracle(manifest)

    def test_torn_slot_must_remain_unchanged(self):
        manifest = self.prepare()
        target = lab(self.target) / "progress1.bin"
        target.write_bytes(target.read_bytes()[:-1])
        with self.assertRaisesRegex(ValueError, "modified SD slots"):
            self.oracle(manifest)

    def test_surviving_slot_must_remain_unchanged(self):
        manifest = self.prepare()
        target = lab(self.target) / "progress0.bin"
        raw = bytearray(target.read_bytes())
        raw[24] ^= 1
        target.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, "Older valid and newer torn"):
            self.oracle(manifest)

    def test_source_root_refuses_to_be_mutated(self):
        with self.assertRaisesRegex(ValueError, "Refuse to overwrite"):
            prepare_torn_newest(self.source, self.source, self.initial)

    def test_refuse_to_overwrite_an_existing_destination(self):
        self.target.mkdir()
        with self.assertRaisesRegex(ValueError, "must not exist"):
            self.prepare()

    def test_reject_stale_source_receipt(self):
        self.initial["emulator_sd_slots"] = []
        with self.assertRaisesRegex(ValueError, "First-process journal changed"):
            self.prepare()

    def test_reject_generation_rollover(self):
        target = lab(self.source) / "progress0.bin"
        target.write_bytes(synthetic_record((1 << 64) - 1))
        disk, _ = audit_confined_sd(self.source)
        self.initial["emulator_sd_slots"] = disk["slots"]
        with self.assertRaisesRegex(ValueError, "No safe generation"):
            self.prepare()

    def test_fault_oracle_requires_only_restore_button_edges(self):
        manifest = self.prepare()
        log = self.cold / "raster-runner.log"
        log.write_text(log.read_text().replace(
            "HEMAN_LORE_HID frame=530 buttons=ZL,R",
            "HEMAN_LORE_HID frame=470 buttons=ZL,L\n"
            "HEMAN_LORE_HID frame=530 buttons=ZL,R", 1))
        with self.assertRaisesRegex(ValueError, "unexpected HID actions"):
            self.oracle(manifest)

    def test_fresh_game_state_must_not_change_before_restore(self):
        manifest = self.prepare()
        state, digest = self.frames[(self.cold, 518)]
        self.frames[(self.cold, 518)] = (state, "changed-before-restore")
        with self.assertRaisesRegex(ValueError, "before cold restore"):
            self.oracle(manifest)


if __name__ == "__main__":
    unittest.main()
