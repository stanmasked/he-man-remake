#!/usr/bin/env python3
"""Stage134: cold recover REAL older saved progress after REAL newer save is torn.

Source slots MUST both be written by the unchanged guest NRO in preceding
independent host processes. Truncation is synthetic, in a new CI-only copy:
never modify source SD or claim physical power-loss durability.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from audit_switch_sd_journal import decode_record
from instrument_nexium_lore_lab import COLD_RESTORE_EVENTS
from verify_nexium_cold_restart import load_guest_frame
from verify_nexium_real_resave_generations import (
    require_process, validate_two_generations,
)
from verify_nexium_sd_disk_receipt import audit_confined_sd, read_confined_sd_slot_bytes

TRUNCATED_LENGTH = 64


def lab(root: Path) -> Path:
    return root / "sdmc" / "switch" / "heman_lore_lab"


def prepare_true_generation_fallback(source_root: Path, destination_root: Path,
                                     first_receipt: dict, resave_report: dict) -> dict:
    if (not source_root.is_absolute() or not destination_root.is_absolute() or
        ".." in source_root.parts or ".." in destination_root.parts):
        raise ValueError("Require absolute CI virtual SD roots without traversal")
    if source_root.resolve() == destination_root.resolve():
        raise ValueError("Cannot fault source live guest SD root")
    if destination_root.exists() or destination_root.is_symlink():
        raise ValueError("Fault destination must not exist")
    if resave_report.get("classification") != (
        "real_nexium_two_guest_origin_sd_save_generations"
    ):
        raise ValueError("Missing attestation of second genuine gameplay-origin save")
    expected = validate_two_generations(source_root, first_receipt)
    for field in ("older_sha256", "newer_sha256", "older_generation",
                  "newer_generation", "older_native_x", "newer_native_x"):
        if expected[field] != resave_report.get(field):
            raise ValueError("Original guest-written records changed since two-save attestation")

    older = read_confined_sd_slot_bytes(source_root, 0, expected["older_sha256"])
    newer = read_confined_sd_slot_bytes(source_root, 1, expected["newer_sha256"])
    if (decode_record(older).get("status") != "structurally_valid" or
        decode_record(newer).get("status") != "structurally_valid"):
        raise ValueError("Two source guest records are no longer structurally valid")
    truncated = newer[:TRUNCATED_LENGTH]
    if decode_record(truncated).get("reason") != "wrong_length":
        raise ValueError("Newer truncated record did not fail checksum/length validation")

    destination = lab(destination_root)
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "progress0.bin").write_bytes(older)
    (destination / "progress1.bin").write_bytes(truncated)
    check, error = audit_confined_sd(destination_root)
    if (error or check["structurally_valid_slot_count"] != 1 or
        check["latest_structural_candidate_slot"] != 0 or
        check["slots"][0].get("sha256") != expected["older_sha256"] or
        check["slots"][1].get("reason") != "wrong_length"):
        raise ValueError("Synthetic torn-newer fixture failed independent SD audit")

    return {
        "classification": "synthetic_truncation_of_newer_genuinely_guest_written_save",
        "two_preexisting_genuine_gameplay_written_records_verified": True,
        "older_generation": expected["older_generation"],
        "newer_generation": expected["newer_generation"],
        "older_native_x": expected["older_native_x"],
        "newer_native_x": expected["newer_native_x"],
        "older_sha256": expected["older_sha256"],
        "newer_source_sha256": expected["newer_sha256"],
        "torn_newer_sha256": hashlib.sha256(truncated).hexdigest(),
        "torn_newer_length": len(truncated),
        "real_hardware_power_cut_observed": False,
        "original_guest_sd_root_modified": False,
        "original_ios_content_used": False,
    }


def verify_true_generation_fallback(first: Path, second: Path, eighth: Path,
                                    original_root: Path, damaged_root: Path,
                                    first_receipt: dict, resave_report: dict,
                                    fixture: dict) -> dict:
    if len({first.resolve(), second.resolve(), eighth.resolve()}) != 3:
        raise ValueError("Must use a separate eighth host guest process")
    if (fixture.get("classification") !=
        "synthetic_truncation_of_newer_genuinely_guest_written_save" or
        fixture.get("two_preexisting_genuine_gameplay_written_records_verified") is not True):
        raise ValueError("Missing genuine two-save source fixture attestation")
    require_process(eighth, COLD_RESTORE_EVENTS, "older genuine slot fallback")
    original_saved, original_pixels = load_guest_frame(first, 485)
    real_newer, newer_pixels = load_guest_frame(second, 345)
    fresh, fresh_pixels = load_guest_frame(eighth, 30)
    before, before_pixels = load_guest_frame(eighth, 518)
    restored, restored_pixels = load_guest_frame(eighth, 540)
    if (original_saved["sd_status"] != 1 or real_newer["sd_status"] != 1 or
        original_saved["collected_count"] != 2 or real_newer["collected_count"] != 2 or
        real_newer["native_player_x"] - original_saved["native_player_x"] < 8):
        raise ValueError("Two genuinely saved source gameplay states not distinguishable")
    if (fresh["lights"] != (0, 0, 0, 0, 0) or
        fresh["collected_count"] != 0 or fresh["sd_status"] != 0 or
        fresh != before or fresh_pixels != before_pixels):
        raise ValueError("Eighth real guest was not an untouched fresh process")
    if (restored != original_saved or restored_pixels != original_pixels or
        restored_pixels == newer_pixels):
        raise ValueError("Cold guest did not fallback to genuinely older saved progress")

    current = validate_two_generations(original_root, first_receipt)
    for field in ("older_sha256", "newer_sha256", "older_generation",
                  "newer_generation", "older_native_x", "newer_native_x"):
        if current[field] != resave_report.get(field) or (
            field in fixture and fixture[field] != current[field]
        ):
            raise ValueError("Original unmodified guest SD records changed after fault experiment")
    damaged, error = audit_confined_sd(damaged_root)
    if (error or damaged["structurally_valid_slot_count"] != 1 or
        damaged["latest_structural_candidate_slot"] != 0 or
        damaged["slots"][0].get("sha256") != fixture["older_sha256"] or
        damaged["slots"][1].get("reason") != "wrong_length"):
        raise ValueError("Eighth process changed damaged virtual SD journal structure")
    prior = read_confined_sd_slot_bytes(damaged_root, 0, fixture["older_sha256"])
    torn = lab(damaged_root) / "progress1.bin"
    if not torn.is_file() or torn.is_symlink():
        raise ValueError("Truncated newer SD record disappeared or was replaced")
    torn_bytes = torn.read_bytes()
    if (len(torn_bytes) != fixture["torn_newer_length"] or
        hashlib.sha256(torn_bytes).hexdigest() != fixture["torn_newer_sha256"] or
        len(prior) != 120):
        raise ValueError("Guest modified source or torn SD journal bytes")
    return {
        "classification": "real_nexium_cold_recovered_different_older_gameplay_save_after_newer_torn",
        "both_original_source_save_slots_written_by_real_guest": True,
        "older_and_newer_gameplay_x_distinguishable": True,
        "eighth_independent_guest_kernel_inputs_only_restore": len(COLD_RESTORE_EVENTS),
        "old_player_pixels_restored_not_new_player_pixels": True,
        "torn_newer_rejected": True,
        "original_two_valid_sd_hashes_unchanged": True,
        "torn_fixture_both_slot_hashes_unchanged": True,
        "physical_nintendo_switch_sd_tested": False,
        "real_power_interruption_verified": False,
        "original_ios_fidelity_verified": False,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    modes = ap.add_subparsers(dest="action", required=True)
    prep = modes.add_parser("prepare")
    prep.add_argument("--source-root", required=True, type=Path)
    prep.add_argument("--target-root", required=True, type=Path)
    prep.add_argument("--first-receipt", required=True, type=Path)
    prep.add_argument("--resave-report", required=True, type=Path)
    prep.add_argument("--out", required=True, type=Path)
    chk = modes.add_parser("verify")
    chk.add_argument("--first", required=True, type=Path)
    chk.add_argument("--second", required=True, type=Path)
    chk.add_argument("--eighth", required=True, type=Path)
    chk.add_argument("--source-root", required=True, type=Path)
    chk.add_argument("--target-root", required=True, type=Path)
    chk.add_argument("--first-receipt", required=True, type=Path)
    chk.add_argument("--resave-report", required=True, type=Path)
    chk.add_argument("--fixture", required=True, type=Path)
    chk.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)
    first_receipt = json.loads(args.first_receipt.read_text())
    report = json.loads(args.resave_report.read_text())
    if args.action == "prepare":
        result = prepare_true_generation_fallback(
            args.source_root, args.target_root, first_receipt, report)
    else:
        result = verify_true_generation_fallback(
            args.first, args.second, args.eighth, args.source_root,
            args.target_root, first_receipt, report,
            json.loads(args.fixture.read_text()))
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2)+"\n")
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
