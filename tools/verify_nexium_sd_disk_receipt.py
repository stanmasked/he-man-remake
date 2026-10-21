#!/usr/bin/env python3
"""Verify actual *emulator sandbox* SD bytes after a green guest HUD.

This read-only structural check never claims physical Switch durability or
cross-process persistence. A green HUD without independently found 120-byte
files fails closed rather than being misrepresented as disk evidence.
"""
import argparse
import json
from pathlib import Path

from audit_switch_sd_journal import audit_directory


def verify_runtime_receipt(data_root: Path, guest_report: dict) -> tuple[dict, bool]:
    lab = data_root / "sdmc" / "switch" / "heman_lore_lab"
    disk = audit_directory(lab)
    save_claim = guest_report.get("guest_sd_save_succeeded") is True
    load_claim = guest_report.get("guest_sd_load_succeeded") is True
    round_trip = guest_report.get("guest_sd_round_trip_verified") is True
    valid = disk["structurally_valid_slot_count"] > 0
    candidate = disk["latest_structural_candidate_slot"]
    has_usable_record = valid and candidate is not None
    inconsistent_claim = round_trip and not (save_claim and load_claim)
    missing_disk_proof = (save_claim or load_claim or round_trip) and not has_usable_record
    success = not (inconsistent_claim or missing_disk_proof)
    if inconsistent_claim:
        classification = "inconsistent_guest_optical_claim"
    elif missing_disk_proof:
        classification = "green_guest_hud_without_structurally_valid_sd_file"
    elif round_trip:
        classification = "guest_optical_round_trip_with_structural_emulator_sd_bytes"
    elif save_claim or load_claim:
        classification = "some_guest_sd_operation_with_structural_emulator_sd_bytes"
    else:
        classification = "no_guest_sd_success_claim"
    # Do not emit emulator host paths or raw private bytes.
    receipt = {
        "classification": classification,
        "guest_sd_save_succeeded": save_claim,
        "guest_sd_load_succeeded": load_claim,
        "guest_sd_round_trip_verified": round_trip,
        "emulator_sd_slots": disk["slots"],
        "emulator_sd_structurally_valid_slot_count": disk["structurally_valid_slot_count"],
        "emulator_sd_latest_structural_candidate_slot": candidate,
        "emulator_sd_world_ambiguous": disk["ambiguous_world_binding"],
        "actual_emulator_file_bytes_examined": has_usable_record,
        "independent_process_cold_restart_verified": False,
        "nintendo_switch_hardware_sd_verified": False,
        "physical_power_loss_atomicity_verified": False,
    }
    return receipt, success


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", required=True, type=Path,
                        help="isolated NEXIUM_DATA_ROOT for this CI run")
    parser.add_argument("--guest-report", required=True, type=Path,
                        help="real guest PNG oracle JSON")
    parser.add_argument("--out", required=True, type=Path,
                        help="metadata-only JSON receipt, not raw files")
    args = parser.parse_args(argv)
    with args.guest_report.open(encoding="utf-8") as file:
        guest = json.load(file)
    receipt, okay = verify_runtime_receipt(args.data_root, guest)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
    print(f"STAGE114_EMULATED_DISK_RECEIPT_{'PASS' if okay else 'FAIL'}: "
          f"{receipt['classification']}")
    return 0 if okay else 2


if __name__ == "__main__":
    raise SystemExit(main())
