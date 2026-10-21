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

    def test_symlinked_lab_directory_does_not_read_external_records(self):
        outside = self.root / "outside"
        outside.mkdir()
        record = synthetic_record(generation=2)
        (outside / "progress0.bin").write_bytes(record)
        self.lab.rmdir()
        self.lab.symlink_to(outside, target_is_directory=True)
        report, okay = verify_runtime_receipt(self.root, self.claim())
        self.assertFalse(okay)
        self.assertEqual(report["classification"], "unsafe_emulator_sd_directory")
        self.assertEqual(report["emulator_sd_directory_validation"],
                         "symlinked_sd_directory_disallowed")
        self.assertFalse(report["actual_emulator_file_bytes_examined"])
        self.assertEqual((outside / "progress0.bin").read_bytes(), record)

    def test_symlinked_sdmc_parent_rejected(self):
        import shutil
        shutil.rmtree(self.root / "sdmc")
        outsider = self.root / "outside"
        outsider.mkdir()
        (self.root / "sdmc").symlink_to(outsider, target_is_directory=True)
        report, okay = verify_runtime_receipt(self.root, self.claim())
        self.assertFalse(okay)
        self.assertEqual(report["emulator_sd_directory_validation"],
                         "symlinked_sd_directory_disallowed")

    def test_data_root_itself_cannot_be_a_symlink(self):
        alias = self.root / "linked-data"
        alias.symlink_to(self.root, target_is_directory=True)
        report, okay = verify_runtime_receipt(alias, self.claim())
        self.assertFalse(okay)
        self.assertEqual(report["classification"], "unsafe_emulator_sd_directory")

    def test_non_directory_lab_component_rejected(self):
        self.lab.rmdir()
        self.lab.write_bytes(b"not a directory")
        report, okay = verify_runtime_receipt(self.root, self.claim())
        self.assertFalse(okay)
        self.assertEqual(report["emulator_sd_directory_validation"],
                         "non_directory_sd_component")

    def test_guest_ci_uses_explicit_absolute_isolated_sd_root(self):
        workflow = (
            ROOT / ".github/workflows/nexium-patched-lore-lab.yml"
        ).read_text(encoding="utf-8")
        self.assertIn('--data-root "$PWD/boot-evidence/nexium-data"', workflow)

    def test_relative_data_root_rejected_without_reading(self):
        report, okay = verify_runtime_receipt(Path("relative-guest-data"), self.claim())
        self.assertFalse(okay)
        self.assertEqual(report["emulator_sd_directory_validation"],
                         "relative_data_root_disallowed")

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

    def test_symlinked_ancestor_of_data_root_is_rejected(self):
        original = self.root / "parent"
        (original / "data" / "sdmc" / "switch" / "heman_lore_lab").mkdir(parents=True)
        (original / "data" / "sdmc" / "switch" / "heman_lore_lab" /
         "progress0.bin").write_bytes(synthetic_record(9))
        alias = self.root / "parent-alias"
        alias.symlink_to(original, target_is_directory=True)
        receipt, okay = verify_runtime_receipt(alias / "data", self.claim())
        self.assertFalse(okay)
        self.assertEqual(receipt["emulator_sd_directory_validation"],
                         "symlinked_sd_directory_disallowed")
        self.assertFalse(receipt["actual_emulator_file_bytes_examined"])

    def test_parent_traversal_not_allowed_even_for_equivalent_absolute_path(self):
        alias = Path(str(self.root) + "/../" + self.root.name)
        receipt, okay = verify_runtime_receipt(alias, self.claim())
        self.assertFalse(okay)
        self.assertEqual(receipt["emulator_sd_directory_validation"],
                         "parent_traversal_disallowed")

    def test_audit_uses_no_path_open_when_reading_journal(self):
        from unittest.mock import patch
        (self.lab / "progress0.bin").write_bytes(synthetic_record(4))
        # Original audit_directory used Path.open after a separate lstat;
        # descriptor-relative reads must never call that vulnerable API.
        with patch.object(Path, "open", side_effect=AssertionError("Path.open used")):
            receipt, okay = verify_runtime_receipt(self.root, self.claim())
        self.assertTrue(okay)
        self.assertEqual(receipt["emulator_sd_directory_validation"],
                         "secure_fd_relative_inspection")

    def test_fifo_slot_rejected_without_blocking(self):
        import os
        if not hasattr(os, "mkfifo"):
            self.skipTest("FIFO requires POSIX")
        os.mkfifo(self.lab / "progress0.bin")
        receipt, okay = verify_runtime_receipt(self.root, self.claim())
        self.assertFalse(okay)
        self.assertEqual(receipt["emulator_sd_slots"][0]["reason"], "non_regular_file")

    def test_hardlink_aliases_are_not_valid_independent_disk_evidence(self):
        import os
        source = self.lab / "progress0.bin"
        source.write_bytes(synthetic_record(5))
        os.link(source, self.lab / "progress1.bin")
        receipt, okay = verify_runtime_receipt(self.root, self.claim())
        self.assertFalse(okay)
        self.assertEqual(receipt["emulator_sd_slots"][0]["reason"],
                         "hardlinked_file_disallowed")
        self.assertEqual(receipt["emulator_sd_slots"][1]["reason"],
                         "hardlinked_file_disallowed")

    def test_replaced_directory_name_cannot_redirect_open_slot(self):
        import os
        from unittest.mock import patch
        original = synthetic_record(3)
        external = synthetic_record(9)
        (self.lab / "progress0.bin").write_bytes(original)
        outsider = self.root / "outside"
        outsider.mkdir()
        (outsider / "progress0.bin").write_bytes(external)
        actual_open = os.open
        swapped = [False]

        def switch_after_directory_open(name, flags, *args, **kwargs):
            fd = actual_open(name, flags, *args, **kwargs)
            if name == "heman_lore_lab" and not swapped[0]:
                swapped[0] = True
                self.lab.rename(self.lab.with_name("moved_lab"))
                self.lab.symlink_to(outsider, target_is_directory=True)
            return fd

        with patch("verify_nexium_sd_disk_receipt.os.open",
                   side_effect=switch_after_directory_open):
            receipt, okay = verify_runtime_receipt(self.root, self.claim())
        self.assertTrue(swapped[0])
        self.assertTrue(okay)
        self.assertEqual(receipt["emulator_sd_slots"][0]["generation"], 3)
        self.assertEqual(outsider.joinpath("progress0.bin").read_bytes(), external)


if __name__ == "__main__":
    unittest.main()
