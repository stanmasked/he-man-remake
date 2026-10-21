"""Stage134 model-only regressions, NOT evidence of real NeXium guest behavior."""
from __future__ import annotations

import hashlib
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from audit_switch_sd_journal import fnv64
from instrument_nexium_lore_lab import COLD_RESTORE_EVENTS, FRAMES
from test_nexium_divergent_journal_priority import synthetic_complete_record
from verify_nexium_real_resave_generations import validate_two_generations
from verify_nexium_sd_disk_receipt import audit_confined_sd
from verify_nexium_real_generation_torn_fallback import (
    lab, prepare_true_generation_fallback, verify_true_generation_fallback,
)


class Stage134TornNewerRealDifferentProgressTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.sd = self.root / "source"
        self.target = self.root / "torn-newest"
        folder = lab(self.sd)
        folder.mkdir(parents=True)
        older = bytearray(synthetic_complete_record(1))
        struct.pack_into("<f", older, 16 + 28, 150.0)
        struct.pack_into("<Q", older, 16 + 88, fnv64(older[16:16+88]))
        struct.pack_into("<Q", older, 112, fnv64(older[:112]))
        (folder / "progress0.bin").write_bytes(older)
        baseline, issue = audit_confined_sd(self.sd)
        self.assertIsNone(issue)
        self.first_receipt = {
            "classification": "guest_optical_round_trip_with_structural_emulator_sd_bytes",
            "actual_emulator_file_bytes_examined": True,
            "emulator_sd_slots": baseline["slots"],
        }
        newer = bytearray(older)
        struct.pack_into("<f", newer, 16 + 28, 195.0)
        struct.pack_into("<Q", newer, 16 + 88, fnv64(newer[16:16+88]))
        struct.pack_into("<Q", newer, 8, 2)
        struct.pack_into("<Q", newer, 112, fnv64(newer[:112]))
        (folder / "progress1.bin").write_bytes(newer)
        self.report = {
            **validate_two_generations(self.sd, self.first_receipt),
            "classification": "real_nexium_two_guest_origin_sd_save_generations",
        }
        self.first = self.root / "first"
        self.second = self.root / "second"
        self.eighth = self.root / "eighth"
        for evidence in (self.first, self.second, self.eighth):
            evidence.mkdir()
            (evidence / "raster-exit-status.txt").write_text("0\n")
        log = [
            "Production runner complete: frames=540",
            "cycles=35000 svcs=3000 frames=530",
            *(f"HEMAN_LORE_HID frame={f} {packet}"
              for f, packet in COLD_RESTORE_EVENTS),
            *(f"HEMAN_GUEST_FRAME_PNG frame={f} dimensions=640x360 "
              f"path={self.eighth / f'raster-frame-{f:04}.png'}"
              for f in FRAMES),
        ]
        (self.eighth / "raster-runner.log").write_text("\n".join(log) + "\n")
        old = {"lights": (1,1,1,1,1), "collected_count": 2,
               "sd_status": 1, "native_player_x": 150}
        new = dict(old, native_player_x=195)
        empty = {"lights": (0,0,0,0,0), "collected_count": 0,
                 "sd_status": 0, "native_player_x": 24}
        self.frames = {
            (self.first, 485): (old, "old-pixels"),
            (self.second, 345): (new, "new-pixels"),
            (self.eighth, 30): (empty, "fresh-pixels"),
            (self.eighth, 518): (empty, "fresh-pixels"),
            (self.eighth, 540): (old, "old-pixels"),
        }

    def prepare(self):
        return prepare_true_generation_fallback(
            self.sd, self.target, self.first_receipt, self.report)

    def verify_mock(self, fixture):
        with patch("verify_nexium_real_generation_torn_fallback.load_guest_frame",
                   side_effect=lambda folder, frame: self.frames[(folder,frame)]):
            return verify_true_generation_fallback(
                self.first, self.second, self.eighth, self.sd, self.target,
                self.first_receipt, self.report, fixture)

    def test_torn_copy_preserves_both_authentic_source_mock_slots(self):
        original = [(lab(self.sd) / f"progress{i}.bin").read_bytes() for i in (0,1)]
        manifest = self.prepare()
        self.assertEqual(manifest["older_native_x"], 150)
        self.assertEqual(manifest["newer_native_x"], 195)
        self.assertFalse(manifest["real_hardware_power_cut_observed"])
        for i in (0,1):
            self.assertEqual((lab(self.sd) / f"progress{i}.bin").read_bytes(), original[i])
        self.assertEqual((lab(self.target) / "progress0.bin").read_bytes(), original[0])
        self.assertEqual(len((lab(self.target) / "progress1.bin").read_bytes()), 64)

    def test_positive_mock_cold_uses_older_distinct_progress(self):
        got = self.verify_mock(self.prepare())
        self.assertTrue(got["old_player_pixels_restored_not_new_player_pixels"])
        self.assertTrue(got["original_two_valid_sd_hashes_unchanged"])
        self.assertFalse(got["real_power_interruption_verified"])

    def test_guest_must_not_restore_torn_newer_save(self):
        manifest = self.prepare()
        self.frames[(self.eighth, 540)] = self.frames[(self.second, 345)]
        with self.assertRaisesRegex(ValueError, "fallback to genuinely older"):
            self.verify_mock(manifest)

    def test_reject_mutated_original_guest_journal(self):
        manifest = self.prepare()
        file = lab(self.sd) / "progress1.bin"
        bits = bytearray(file.read_bytes())
        bits[26] ^= 1
        file.write_bytes(bits)
        with self.assertRaisesRegex(ValueError, "two usable ranked"):
            self.verify_mock(manifest)

    def test_reject_modified_truncated_sd_bytes(self):
        manifest = self.prepare()
        target = lab(self.target) / "progress1.bin"
        target.write_bytes(target.read_bytes()[:-2])
        with self.assertRaisesRegex(ValueError, "modified source or torn SD journal"):
            self.verify_mock(manifest)

    def test_source_sd_cannot_be_overwritten_by_fixture_creator(self):
        with self.assertRaisesRegex(ValueError, "Cannot fault source"):
            prepare_true_generation_fallback(
                self.sd, self.sd, self.first_receipt, self.report)
        self.target.mkdir()
        with self.assertRaisesRegex(ValueError, "must not exist"):
            self.prepare()

    def test_unattested_second_guest_save_cannot_be_source(self):
        self.report["classification"] = "synthetic_two_valid_divergent_progress_sd_fixture"
        with self.assertRaisesRegex(ValueError, "second genuine gameplay"):
            self.prepare()

    def test_cold_process_must_not_inject_movement(self):
        fixture = self.prepare()
        log = self.eighth / "raster-runner.log"
        log.write_text(log.read_text().replace(
            "HEMAN_LORE_HID frame=530 buttons=ZL,R",
            "HEMAN_LORE_HID frame=180 buttons=DRIGHT\n"
            "HEMAN_LORE_HID frame=530 buttons=ZL,R", 1))
        with self.assertRaisesRegex(ValueError, "unexpected save/movement"):
            self.verify_mock(fixture)


if __name__ == "__main__":
    unittest.main()
