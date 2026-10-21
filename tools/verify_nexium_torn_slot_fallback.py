#!/usr/bin/env python3
"""Stage119: emulate torn *newest* journal and require older valid cold recovery.

Read-only source, new CI-only fixture, unchanged synthetic guest NRO. This is
NOT an actual power interruption or Nintendo Switch flash durability test.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

from audit_switch_sd_journal import RECORD_SIZE, decode_record, fnv64
from instrument_nexium_lore_lab import FRAMES, COLD_RESTORE_EVENTS
from verify_nexium_cold_restart import load_guest_frame
from verify_nexium_sd_disk_receipt import audit_confined_sd, read_confined_sd_slot_bytes

TRUNCATION_BYTES = 64


def lab(root: Path) -> Path:
    return root / "sdmc" / "switch" / "heman_lore_lab"


def prepare_torn_newest(source_root: Path, target_root: Path, initial: dict) -> dict:
    """Preserve the authentic valid journal while making a truncated newer slot."""
    if not source_root.is_absolute() or not target_root.is_absolute():
        raise ValueError("Both isolated CI roots must be absolute")
    if source_root.resolve() == target_root.resolve():
        raise ValueError("Refuse to overwrite first-process SD")
    if target_root.exists() or target_root.is_symlink():
        raise ValueError("Torn-slot fixture destination must not exist")
    if (initial.get("classification") !=
        "guest_optical_round_trip_with_structural_emulator_sd_bytes" or
        initial.get("actual_emulator_file_bytes_examined") is not True):
        raise ValueError("First process lacks independently confirmed SD save")
    previous, problem = audit_confined_sd(source_root)
    if (problem or previous["slots"] != initial.get("emulator_sd_slots") or
        previous["latest_structural_candidate_slot"] is None):
        raise ValueError("First-process journal changed or has no usable record")

    selected = previous["latest_structural_candidate_slot"]
    entry = previous["slots"][selected]
    if entry["status"] != "structurally_valid":
        raise ValueError("Source journal structural candidate is not valid")
    # This path is in the dedicated CI run's private SD fixture, not a user SD.
    original = read_confined_sd_slot_bytes(source_root, selected, entry["sha256"])
    generation = entry["generation"]
    if not (0 < generation < (1 << 64) - 1):
        raise ValueError("No safe generation for torn newer slot")

    newer = bytearray(original)
    struct.pack_into("<Q", newer, 8, generation + 1)
    struct.pack_into("<Q", newer, 112, fnv64(newer[:112]))
    if (decode_record(newer).get("status") != "structurally_valid" or
        decode_record(newer)["generation"] != generation + 1):
        raise ValueError("Synthetic newer journal construction failed")
    torn = bytes(newer[:TRUNCATION_BYTES])
    if decode_record(torn).get("reason") != "wrong_length":
        raise ValueError("Truncation did not invalidate newest slot")

    destination = lab(target_root)
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "progress0.bin").write_bytes(original)
    (destination / "progress1.bin").write_bytes(torn)
    disk, problem = audit_confined_sd(target_root)
    if (problem or disk["structurally_valid_slot_count"] != 1 or
        disk["latest_structural_candidate_slot"] != 0 or
        disk["slots"][1].get("reason") != "wrong_length" or
        disk["slots"][0].get("sha256") != entry["sha256"]):
        raise ValueError("Fixture must have exactly one older valid candidate")

    return {
        "classification": "synthetic_newest_journal_truncation_fixture",
        "source_initial_valid_generation": generation,
        "source_initial_slot": selected,
        "survivor_slot": 0,
        "survivor_sha256": hashlib.sha256(original).hexdigest(),
        "survivor_length": len(original),
        "torn_newer_slot": 1,
        "torn_newer_expected_generation": generation + 1,
        "torn_newer_sha256": hashlib.sha256(torn).hexdigest(),
        "torn_newer_length": len(torn),
        "torn_newer_expected_invalid_reason": "wrong_length",
        "real_power_interruption_observed": False,
        "original_ios_data_used": False,
        "actual_neXium_execution_verified": False,
    }


def verify_fallback(first: Path, evidence: Path, target_root: Path, manifest: dict) -> dict:
    if not all(p.is_absolute() for p in (first, evidence, target_root)):
        raise ValueError("All guest evidence paths must be absolute")
    if manifest.get("classification") != "synthetic_newest_journal_truncation_fixture":
        raise ValueError("Missing newest-slot corruption manifest")
    if (first / "raster-exit-status.txt").read_text().strip() != "0":
        raise ValueError("Original SD guest run did not complete")
    if (evidence / "raster-exit-status.txt").read_text().strip() != "0":
        raise ValueError("Cold torn-slot guest runner did not complete")
    log = (evidence / "raster-runner.log").read_text()
    if "Production runner complete" not in log:
        raise ValueError("Cold torn-slot NeXium runner did not finish")
    progress = re.findall(r"cycles=(\d+) svcs=(\d+) frames=(\d+)", log)
    if not progress or max(int(x) for x, _, _ in progress) == 0 or (
        max(int(y) for _, y, _ in progress) == 0
    ):
        raise ValueError("No real cold-process CPU and SVC evidence")
    expected = [f"HEMAN_LORE_HID frame={f} {buttons}"
                for f, buttons in COLD_RESTORE_EVENTS]
    events = [line for line in log.splitlines()
              if line.startswith("HEMAN_LORE_HID frame=")]
    if events != expected:
        raise ValueError("Cold torn-slot guest has unexpected HID actions")
    actual = [line for line in log.splitlines()
              if line.startswith("HEMAN_GUEST_FRAME_PNG frame=")]
    if len(actual) != len(FRAMES):
        raise ValueError("Missing guest frame_rx receipts")
    for frame, line in zip(FRAMES, actual):
        expected_line = (
            f"HEMAN_GUEST_FRAME_PNG frame={frame} dimensions=640x360 "
            f"path={evidence / f'raster-frame-{frame:04}.png'}"
        )
        if line != expected_line:
            raise ValueError("Incorrect frame_rx path or frame chronology")

    saved_state, saved_digest = load_guest_frame(first, 485)
    new_state, new_digest = load_guest_frame(evidence, 30)
    before, before_digest = load_guest_frame(evidence, 518)
    restored, restored_digest = load_guest_frame(evidence, 540)
    if (saved_state["sd_status"] != 1 or
        new_state["lights"] != (0, 0, 0, 0, 0) or
        new_state["collected_count"] != 0 or new_state["sd_status"] != 0):
        raise ValueError("Incorrect baseline save or fresh cold process")
    if new_state != before or new_digest != before_digest:
        raise ValueError("Guest changed its game state before cold restore")
    if restored["sd_status"] != 1:
        raise ValueError("Guest refused older valid slot after torn newer record")
    if (restored_digest != saved_digest or restored["lights"] != saved_state["lights"] or
        restored["collected_count"] != saved_state["collected_count"]):
        raise ValueError("Older-slot recovery did not reproduce genuine saved pixels")
    if restored_digest == new_digest:
        raise ValueError("Cold restore left untouched empty session")

    disk, problem = audit_confined_sd(target_root)
    if (problem or disk["structurally_valid_slot_count"] != 1 or
        disk["latest_structural_candidate_slot"] != 0 or
        disk["slots"][1].get("reason") != "wrong_length"):
        raise ValueError("Older valid and newer torn slot state changed")
    for slot, size_key, hash_key in (
        (0, "survivor_length", "survivor_sha256"),
        (1, "torn_newer_length", "torn_newer_sha256"),
    ):
        path = lab(target_root) / f"progress{slot}.bin"
        if path.is_symlink() or not path.is_file():
            raise ValueError("Slot unexpectedly missing or linked")
        raw = path.read_bytes()
        if len(raw) != manifest[size_key] or (
            hashlib.sha256(raw).hexdigest() != manifest[hash_key]
        ):
            raise ValueError("Guest modified SD slots in restore-only phase")
    return {
        "classification": "real_nexium_cold_restore_older_slot_after_synthetic_newest_truncation",
        "fresh_guest_process_and_real_kernel_input_required": True,
        "older_slot_native_recovery_verified": True,
        "torn_newest_journal_not_accepted": True,
        "restored_guest_frame_matches_first_process": True,
        "both_slots_unchanged_in_restore_only_process": True,
        "torn_newest_slot_generation": manifest["torn_newer_expected_generation"],
        "actual_power_interruption_verified": False,
        "nintendo_switch_hardware_sd_verified": False,
        "original_ios_fidelity_verified": False,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    subs = ap.add_subparsers(dest="action", required=True)
    prep = subs.add_parser("prepare")
    prep.add_argument("--source-root", required=True, type=Path)
    prep.add_argument("--target-root", required=True, type=Path)
    prep.add_argument("--first-receipt", required=True, type=Path)
    prep.add_argument("--out", required=True, type=Path)
    chk = subs.add_parser("verify")
    chk.add_argument("--first-evidence", required=True, type=Path)
    chk.add_argument("--cold-evidence", required=True, type=Path)
    chk.add_argument("--target-root", required=True, type=Path)
    chk.add_argument("--manifest", required=True, type=Path)
    chk.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)
    if args.action == "prepare":
        result = prepare_torn_newest(args.source_root, args.target_root,
                                      json.loads(args.first_receipt.read_text()))
    else:
        result = verify_fallback(args.first_evidence, args.cold_evidence,
                                 args.target_root,
                                 json.loads(args.manifest.read_text()))
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
