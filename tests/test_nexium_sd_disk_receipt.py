"""Stage114: distinguish guest HUD success from independently found SD bytes."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
from verify_nexium_sd_disk_receipt import verify_runtime_receipt
from test_switch_sd_journal_audit import synthetic_record


class Stage114DiskReceiptTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.lab = self.root / "sdmc" / "switch" / "heman_lore_lab"
        self.lab.mkdir(parents=True)

    def claim(self, save=True, load=True, round_trip=True):
        return {
            "guest_sd_save_succeeded": save,
            "guest_sd_load_succeeded": load,
            "guest_sd_round_trip_verified": round_trip,
        }

    def test_green_hud_without_any_file_must_fail(self):
        receipt, okay = verify_runtime_receipt(self.root, self.claim())
        self.assertFalse(okay)
        self.assertEqual(receipt["classification"],
                         "green_guest_hud_without_structurally_valid_sd_file")
        self.assertFalse(receipt["independent_process_cold_restart_verified"])

    def test_valid_synthetic_first_generation_provides_disk_evidence(self):
        slot = self.lab / "progress0.bin"
        raw = synthetic_record(generation=1)
        slot.write_bytes(raw)
        receipt, okay = verify_runtime_receipt(self.root, self.claim())
        self.assertTrue(okay)
        self.assertTrue(receipt["actual_emulator_file_bytes_examined"])
        self.assertEqual(receipt["emulator_sd_latest_structural_candidate_slot"], 0)
        self.assertEqual(slot.read_bytes(), raw)
        self.assertFalse(receipt["nintendo_switch_hardware_sd_verified"])

    def test_newer_corrupt_slot_does_not_cancel_older_valid_record(self):
        (self.lab / "progress0.bin").write_bytes(synthetic_record(1))
        bad = bytearray(synthetic_record(2))
        bad[24] ^= 0x40
        (self.lab / "progress1.bin").write_bytes(bad)
        receipt, okay = verify_runtime_receipt(self.root, self.claim())
        self.assertTrue(okay)
        self.assertEqual(receipt["emulator_sd_latest_structural_candidate_slot"], 0)
        self.assertEqual(receipt["emulator_sd_slots"][1]["reason"], "journal_checksum")

    def test_two_conflicting_world_bindings_reject_green_hud(self):
        (self.lab / "progress0.bin").write_bytes(synthetic_record(1, seal=123))
        (self.lab / "progress1.bin").write_bytes(synthetic_record(2, seal=456))
        receipt, okay = verify_runtime_receipt(self.root, self.claim())
        self.assertFalse(okay)
        self.assertTrue(receipt["emulator_sd_world_ambiguous"])

    def test_without_guest_success_claim_missing_files_is_not_disk_proof(self):
        receipt, okay = verify_runtime_receipt(
            self.root, self.claim(False, False, False)
        )
        self.assertTrue(okay)
        self.assertFalse(receipt["actual_emulator_file_bytes_examined"])
        self.assertEqual(receipt["classification"], "no_guest_sd_success_claim")

    def test_optical_round_trip_without_claimed_save_is_inconsistent(self):
        (self.lab / "progress0.bin").write_bytes(synthetic_record(1))
        receipt, okay = verify_runtime_receipt(
            self.root, self.claim(False, True, True)
        )
        self.assertFalse(okay)
        self.assertEqual(receipt["classification"], "inconsistent_guest_optical_claim")

    def test_truncated_only_file_rejects_green_hud(self):
        (self.lab / "progress0.bin").write_bytes(synthetic_record(1)[:60])
        receipt, okay = verify_runtime_receipt(self.root, self.claim())
        self.assertFalse(okay)
        self.assertEqual(receipt["emulator_sd_slots"][0]["reason"], "wrong_length")


if __name__ == "__main__":
    unittest.main()
