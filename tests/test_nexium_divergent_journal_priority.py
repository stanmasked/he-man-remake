"""Stage122 synthetic-only tests; no mocked result attests actual NeXium."""
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
from audit_switch_sd_journal import decode_record, fnv64
from instrument_nexium_lore_lab import FRAMES, COLD_RESTORE_EVENTS
from test_switch_sd_journal_audit import synthetic_record
from verify_nexium_sd_disk_receipt import audit_confined_sd
from verify_nexium_divergent_journal_priority import (
    lab, prepare_divergent_slots, verify_divergent_restore,
)


def synthetic_complete_record(generation=7):
    """A structurally valid toy record, NOT from genuine gameplay."""
    data = bytearray(synthetic_record(generation))
    struct.pack_into("<I", data, 16 + 64, 0b110)  # both pickups
    struct.pack_into("<I", data, 16 + 68, 0b1)  # fictional gate triggered
    data[16 + 80] = 1  # wall crusher upgrade
    data[16 + 81] = 1  # broken gate
    data[16 + 82] = 3  # two lore bits
    data[16 + 83] = 2  # two collectibles
    struct.pack_into("<Q", data, 16 + 88, fnv64(data[16:16 + 88]))
    struct.pack_into("<Q", data, 112, fnv64(data[:112]))
    assert decode_record(data)["status"] == "structurally_valid"
    return bytes(data)


class Stage122DivergentProgressTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / "source"
        self.target = self.root / "divergent"
        lab(self.source).mkdir(parents=True)
        self.original = synthetic_complete_record()
        (lab(self.source) / "progress0.bin").write_bytes(self.original)
        disk, err = audit_confined_sd(self.source)
        self.assertIsNone(err)
        self.receipt = {
            "classification": "guest_optical_round_trip_with_structural_emulator_sd_bytes",
            "actual_emulator_file_bytes_examined": True,
            "emulator_sd_slots": disk["slots"],
        }
        self.first = self.root / "first"
        self.second = self.root / "second"
        self.first.mkdir()
        self.second.mkdir()
        for directory in (self.first, self.second):
            (directory / "raster-exit-status.txt").write_text("0\n")
        lines = [
            "Production runner complete: frames=540",
            "cycles=50000 svcs=2000 frames=530",
            *(f"HEMAN_LORE_HID frame={frame} {packet}"
              for frame, packet in COLD_RESTORE_EVENTS),
            *(f"HEMAN_GUEST_FRAME_PNG frame={frame} dimensions=640x360 "
              f"path={self.second / f'raster-frame-{frame:04}.png'}"
              for frame in FRAMES),
        ]
        (self.second / "raster-runner.log").write_text("\n".join(lines) + "\n")
        complete = {"lights": (1,1,1,1,1), "collected_count": 2,
                    "sd_status": 1, "native_player_x": 160}
        fresh = {"lights": (0,0,0,0,0), "collected_count": 0,
                 "sd_status": 0, "native_player_x": 24}
        partial = {"lights": (1,1,0,1,1), "collected_count": 1,
                   "sd_status": 1, "native_player_x": 160}
        self.frames = {
            (self.first, 485): (complete, "complete-scene"),
            (self.second, 30): (fresh, "empty-scene"),
            (self.second, 518): (fresh, "empty-scene"),
            (self.second, 540): (partial, "partial-scene"),
        }
        self.common_hash = "unchanged-pixels"

    def prepare(self):
        return prepare_divergent_slots(self.source, self.target, self.receipt)

    def verify_mock(self, manifest):
        with patch("verify_nexium_divergent_journal_priority.load_guest_frame",
                   side_effect=lambda folder, frame: self.frames[(folder,frame)]):
            with patch("verify_nexium_divergent_journal_priority.masked_common_scene_digest",
                       return_value=self.common_hash):
                return verify_divergent_restore(
                    self.first, self.second, self.target, manifest
                )

    def test_creates_two_different_structurally_valid_progress_slots(self):
        manifest = self.prepare()
        disk, error = audit_confined_sd(self.target)
        self.assertIsNone(error)
        self.assertEqual(disk["structurally_valid_slot_count"], 2)
        self.assertEqual(disk["latest_structural_candidate_slot"], 1)
        self.assertEqual([s["collected_count"] for s in disk["slots"]], [2, 1])
        self.assertEqual([s["collected_mask"] for s in disk["slots"]], [3, 2])
        self.assertEqual(manifest["newer_generation"], 8)
        self.assertEqual((lab(self.source) / "progress0.bin").read_bytes(), self.original)
        self.assertFalse(manifest["actual_second_gameplay_save_observed"])

    def test_partial_snapshot_removes_only_bio_and_preserves_art_world(self):
        self.prepare()
        prev = (lab(self.target) / "progress0.bin").read_bytes()
        newest = (lab(self.target) / "progress1.bin").read_bytes()
        self.assertEqual(struct.unpack_from("<I", prev, 16+64)[0], 0b110)
        self.assertEqual(struct.unpack_from("<I", newest, 16+64)[0], 0b100)
        self.assertEqual(prev[16+81], newest[16+81])
        self.assertEqual(prev[16+80], newest[16+80])
        self.assertEqual(decode_record(newest)["generation"], 8)

    def test_positive_mock_does_not_count_as_guest_evidence(self):
        result = self.verify_mock(self.prepare())
        self.assertTrue(result["newer_generation_selected_in_guest_pixels"])
        self.assertTrue(result["synthetic_second_snapshot_not_a_genuine_gameplay_save"])
        self.assertFalse(result["nintendo_switch_hardware_sd_verified"])

    def test_refuses_to_modify_source_root_or_existing_destination(self):
        with self.assertRaisesRegex(ValueError, "Cannot mutate original"):
            prepare_divergent_slots(self.source, self.source, self.receipt)
        self.target.mkdir()
        with self.assertRaisesRegex(ValueError, "must not already exist"):
            self.prepare()

    def test_stale_original_sha_receipt_fails(self):
        self.receipt["emulator_sd_slots"] = []
        with self.assertRaisesRegex(ValueError, "no longer matches"):
            self.prepare()

    def test_incomplete_game_cannot_forge_divergent_fixture(self):
        (lab(self.source) / "progress0.bin").write_bytes(synthetic_record(7))
        disk, _ = audit_confined_sd(self.source)
        self.receipt["emulator_sd_slots"] = disk["slots"]
        with self.assertRaisesRegex(ValueError, "two-collectible"):
            self.prepare()

    def test_native_guest_must_prefer_newer_partial_lore(self):
        manifest = self.prepare()
        prior, digest = self.frames[(self.second, 540)]
        self.frames[(self.second, 540)] = (
            dict(prior, lights=(1,1,1,1,1), collected_count=2), digest
        )
        with self.assertRaisesRegex(ValueError, "NEWER partial-progress"):
            self.verify_mock(manifest)

    def test_extraneous_guest_save_input_invalidates_claim(self):
        manifest = self.prepare()
        file = self.second / "raster-runner.log"
        file.write_text(file.read_text().replace(
            "HEMAN_LORE_HID frame=530 buttons=ZL,R",
            "HEMAN_LORE_HID frame=470 buttons=ZL,L\n"
            "HEMAN_LORE_HID frame=530 buttons=ZL,R",
        ))
        with self.assertRaisesRegex(ValueError, "Unexpected gameplay/save"):
            self.verify_mock(manifest)

    def test_guest_must_not_change_either_save_slot(self):
        manifest = self.prepare()
        file = lab(self.target) / "progress1.bin"
        data = bytearray(file.read_bytes())
        data[24] ^= 1
        file.write_bytes(data)
        with self.assertRaisesRegex(ValueError, "altered/ignored"):
            self.verify_mock(manifest)

    def test_old_and_new_must_have_distinct_guest_pixels(self):
        manifest = self.prepare()
        complete, _ = self.frames[(self.first, 485)]
        self.frames[(self.first, 485)] = (complete, "partial-scene")
        with self.assertRaisesRegex(ValueError, "indistinguishable"):
            self.verify_mock(manifest)

    def test_guest_pixels_outside_known_bio_change_are_immutable(self):
        manifest = self.prepare()
        with patch("verify_nexium_divergent_journal_priority.load_guest_frame",
                   side_effect=lambda folder, frame: self.frames[(folder,frame)]):
            with patch("verify_nexium_divergent_journal_priority.masked_common_scene_digest",
                       side_effect=("source-world", "changed-world")):
                with self.assertRaisesRegex(ValueError, "outside legitimate"):
                    verify_divergent_restore(
                        self.first, self.second, self.target, manifest
                    )


if __name__ == "__main__":
    unittest.main()
