#!/usr/bin/env python3
"""Stage118: test-only corrupted journal fixture and cold NeXium rejection oracle.

No original iOS data. Never use personal SD folders. Copies only validated,
CI-generated synthetic 120-byte progress records into a separate isolated
emulator root, mutates their checksum coverage and expects fail-closed restore.
Neither originals nor mutated bytes are published as artifacts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from audit_switch_sd_journal import RECORD_SIZE, decode_record
from instrument_nexium_lore_lab import FRAMES, COLD_RESTORE_EVENTS
from verify_nexium_cold_restart import load_guest_frame
from verify_nexium_sd_disk_receipt import audit_confined_sd


def _lab(root: Path) -> Path:
    return root / "sdmc" / "switch" / "heman_lore_lab"


def prepare_bad_sd(source_root: Path, target_root: Path, first_receipt: dict) -> dict:
    """Make an *isolated new* corrupted fixture, never modify original slots."""
    if not source_root.is_absolute() or not target_root.is_absolute():
        raise ValueError("Both CI data roots must be absolute")
    if source_root.resolve() == target_root.resolve():
        raise ValueError("Refuse to overwrite original emulator SD")
    if target_root.exists() or target_root.is_symlink():
        raise ValueError("Corrupt fixture destination must not exist")
    if first_receipt.get("classification") != (
        "guest_optical_round_trip_with_structural_emulator_sd_bytes"
    ):
        raise ValueError("First run has no independent real guest SD receipt")
    disk, problem = audit_confined_sd(source_root)
    if problem or disk["slots"] != first_receipt.get("emulator_sd_slots") or (
        disk["latest_structural_candidate_slot"] is None
    ):
        raise ValueError("Original journal differs from previously attested slots")
    new_lab = _lab(target_root)
    manifest = {
        "classification": "synthetic_checksum_fault_fixture",
        "slots": [],
        "source_original_bytes_unmodified": True,
        "fixture_contains_original_ios_assets": False,
        "guest_emulator_execution_verified": False,
    }
    new_lab.mkdir(parents=True, exist_ok=False)
    for slot in disk["slots"]:
        if slot["status"] != "structurally_valid":
            continue
        index = slot["slot"]
        src = _lab(source_root) / f"progress{index}.bin"
        raw = src.read_bytes()
        if len(raw) != RECORD_SIZE or hashlib.sha256(raw).hexdigest() != slot["sha256"]:
            raise ValueError("Journal bytes changed after independent receipt")
        broken = bytearray(raw)
        broken[24] ^= 0x40  # Covered by outer FNV; every valid journal must fail.
        if decode_record(broken).get("reason") != "journal_checksum":
            raise ValueError("Injected fault did not invalidate the journal checksum")
        data = bytes(broken)
        (new_lab / f"progress{index}.bin").write_bytes(data)
        manifest["slots"].append({
            "slot": index, "length": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "expected_invalid_reason": "journal_checksum",
        })
    if not manifest["slots"]:
        raise ValueError("Refuse empty corruption fixture")
    fault_disk, fault_problem = audit_confined_sd(target_root)
    if fault_problem or fault_disk["structurally_valid_slot_count"] != 0:
        raise ValueError("Corruption fixture unexpectedly has usable SD records")
    if any(fault_disk["slots"][s["slot"]].get("reason") != "journal_checksum"
           for s in manifest["slots"]):
        raise ValueError("Corruption fixture was not independently rejected")
    return manifest


def verify_failed_restore(folder: Path, data_root: Path, manifest: dict) -> dict:
    if not folder.is_absolute() or not data_root.is_absolute():
        raise ValueError("Cold fault evidence paths must be absolute")
    if manifest.get("classification") != "synthetic_checksum_fault_fixture":
        raise ValueError("Invalid fault manifest")
    if (folder / "raster-exit-status.txt").read_text().strip() != "0":
        raise ValueError("Cold fault guest process did not exit cleanly")
    log = (folder / "raster-runner.log").read_text()
    if "Production runner complete" not in log:
        raise ValueError("Cold fault NeXium guest never completed")
    samples = re.findall(r"cycles=(\d+) svcs=(\d+) frames=(\d+)", log)
    if not samples or max(int(a) for a, _, _ in samples) == 0 or (
        max(int(b) for _, b, _ in samples) == 0
    ):
        raise ValueError("No actual fault-process CPU/SVC execution")
    expected_events = [f"HEMAN_LORE_HID frame={f} {packet}"
                       for f, packet in COLD_RESTORE_EVENTS]
    emitted_events = [line for line in log.splitlines()
                      if line.startswith("HEMAN_LORE_HID frame=")]
    if emitted_events != expected_events:
        raise ValueError("Fault process injected actions other than restore")
    arrivals = [line for line in log.splitlines()
                if line.startswith("HEMAN_GUEST_FRAME_PNG frame=")]
    if len(arrivals) != len(FRAMES):
        raise ValueError("Fault process did not report complete guest frame set")
    for frame, line in zip(FRAMES, arrivals):
        wanted = (f"HEMAN_GUEST_FRAME_PNG frame={frame} dimensions=640x360 "
                  f"path={folder / f'raster-frame-{frame:04}.png'}")
        if line != wanted:
            raise ValueError("Fault PNG path or frame number does not match real guest log")
    before, first_digest = load_guest_frame(folder, 30)
    steady, middle_digest = load_guest_frame(folder, 518)
    after, last_digest = load_guest_frame(folder, 540)
    if before["lights"] != (0, 0, 0, 0, 0) or (
        before["collected_count"] != 0 or before["sd_status"] != 0
    ):
        raise ValueError("Fault process did not start in clean reset state")
    if steady != before or middle_digest != first_digest:
        raise ValueError("Fault process changed the game before load attempt")
    if after["sd_status"] != 2:
        raise ValueError("Corrupted SD was accepted instead of rejected")
    if (after["lights"] != before["lights"] or
        after["collected_count"] != before["collected_count"] or
        last_digest != first_digest):
        raise ValueError("Rejected corrupt SD mutated the guest game session")
    disk, problem = audit_confined_sd(data_root)
    if problem or disk["structurally_valid_slot_count"] != 0:
        raise ValueError("A valid journal unexpectedly exists in faulty sandbox")
    slots = manifest.get("slots", [])
    if not slots:
        raise ValueError("Fault fixture contains no corrupted slots")
    for entry in slots:
        index = entry["slot"]
        path = _lab(data_root) / f"progress{index}.bin"
        if not path.is_file() or path.is_symlink():
            raise ValueError("Corrupted test journal unexpectedly missing or linked")
        data = path.read_bytes()
        if (len(data) != entry["length"] or
            hashlib.sha256(data).hexdigest() != entry["sha256"] or
            disk["slots"][index].get("reason") != "journal_checksum"):
            raise ValueError("Fault fixture bytes mutated during NeXium execution")
    return {
        "classification": "real_nexium_cold_process_corrupted_sd_rejected",
        "corrupted_journal_slots": [entry["slot"] for entry in slots],
        "second_sandbox_separate_from_successful_restore": True,
        "guest_fresh_initial_state_verified": True,
        "guest_restore_only_npad_events": len(COLD_RESTORE_EVENTS),
        "guest_red_sd_status_confirmed": True,
        "failed_restore_preserved_all_game_pixels": True,
        "invalid_journal_bytes_unchanged": True,
        "independent_emulator_process_failure_recovery_verified": True,
        "nintendo_switch_hardware_sd_verified": False,
        "power_loss_durability_verified": False,
        "original_ios_fidelity_verified": False,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="action", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--source-root", required=True, type=Path)
    prep.add_argument("--target-root", required=True, type=Path)
    prep.add_argument("--initial-receipt", required=True, type=Path)
    prep.add_argument("--out", required=True, type=Path)
    verify = sub.add_parser("verify")
    verify.add_argument("--evidence-folder", required=True, type=Path)
    verify.add_argument("--target-root", required=True, type=Path)
    verify.add_argument("--manifest", required=True, type=Path)
    verify.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    if args.action == "prepare":
        result = prepare_bad_sd(
            args.source_root, args.target_root,
            json.loads(args.initial_receipt.read_text()),
        )
    else:
        result = verify_failed_restore(
            args.evidence_folder, args.target_root,
            json.loads(args.manifest.read_text()),
        )
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
