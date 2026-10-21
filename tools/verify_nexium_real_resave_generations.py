#!/usr/bin/env python3
"""Stage133: verify TWO genuinely guest-written SD generations and cold newest restore.

Only original guest NRO actions count: SD-load, real D-pad movement, SD-save.
The host never edits a saved record or presents mock frames as guest evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import struct
from pathlib import Path

from instrument_nexium_lore_lab import FRAMES, RESAVE_EVENTS, COLD_RESTORE_EVENTS
from verify_nexium_cold_restart import load_guest_frame
from verify_nexium_sd_disk_receipt import audit_confined_sd, read_confined_sd_slot_bytes


def require_process(folder: Path, events: tuple, label: str) -> None:
    if not folder.is_absolute():
        raise ValueError(f"{label}: evidence folder must be absolute")
    if (folder / "raster-exit-status.txt").read_text().strip() != "0":
        raise ValueError(f"{label}: genuine emulator process did not exit cleanly")
    log = (folder / "raster-runner.log").read_text()
    if "Production runner complete" not in log:
        raise ValueError(f"{label}: no completed production guest runner")
    samples = re.findall(r"cycles=(\d+) svcs=(\d+) frames=(\d+)", log)
    if not samples or max(int(a) for a, _, _ in samples) <= 0 or (
        max(int(b) for _, b, _ in samples) <= 0
    ):
        raise ValueError(f"{label}: no genuine guest CPU/SVC progress")
    desired = [
        f"HEMAN_LORE_HID frame={frame} {packet}"
        for frame, packet in events
    ]
    published = [s for s in log.splitlines()
                 if s.startswith("HEMAN_LORE_HID frame=")]
    if published != desired:
        raise ValueError(f"{label}: unexpected save/movement/injection transcript")
    desired_png = [
        f"HEMAN_GUEST_FRAME_PNG frame={frame} dimensions=640x360 "
        f"path={folder / f'raster-frame-{frame:04}.png'}"
        for frame in FRAMES
    ]
    published_png = [s for s in log.splitlines()
                     if s.startswith("HEMAN_GUEST_FRAME_PNG frame=")]
    if published_png != desired_png:
        raise ValueError(f"{label}: missing, reordered, or spoofed frame_rx PNG receipts")


def validate_two_generations(root: Path, first_receipt: dict) -> dict:
    if not root.is_absolute() or ".." in root.parts:
        raise ValueError("Invalid isolated guest SD root")
    if (first_receipt.get("classification") !=
        "guest_optical_round_trip_with_structural_emulator_sd_bytes" or
        first_receipt.get("actual_emulator_file_bytes_examined") is not True):
        raise ValueError("First genuine saved state was never proven")
    origin = first_receipt["emulator_sd_slots"]
    valid_origin = [s for s in origin if s["status"] == "structurally_valid"]
    if len(valid_origin) != 1 or valid_origin[0]["slot"] != 0:
        raise ValueError("First process must have created exactly one first-generation slot")
    initial = valid_origin[0]
    disk, problem = audit_confined_sd(root)
    if (problem or disk["structurally_valid_slot_count"] != 2 or
        disk["latest_structural_candidate_slot"] != 1 or
        disk["ambiguous_world_binding"]):
        raise ValueError("Second actual guest save did not create two usable ranked slots")
    older, newer = disk["slots"]
    if (older != initial or
        newer.get("status") != "structurally_valid" or
        newer.get("generation") != older["generation"] + 1 or
        older["collected_mask"] != 3 or
        newer["collected_mask"] != 3 or
        older["collected_count"] != 2 or
        newer["collected_count"] != 2 or
        older["world_seal"] != newer["world_seal"] or
        older["bindings"] != newer["bindings"] or
        older["sha256"] == newer["sha256"]):
        raise ValueError("Two real journal generations differ unexpectedly or were modified")
    old_bytes = read_confined_sd_slot_bytes(root, 0, older["sha256"])
    new_bytes = read_confined_sd_slot_bytes(root, 1, newer["sha256"])
    old_x = struct.unpack_from("<f", old_bytes, 16 + 28)[0]
    new_x = struct.unpack_from("<f", new_bytes, 16 + 28)[0]
    if (not math.isfinite(old_x) or not math.isfinite(new_x) or
        new_x - old_x < 8.0 or new_x - old_x > 150.0):
        raise ValueError("Second game-origin journal has no plausible earned D-pad position change")
    if old_bytes[16:112] == new_bytes[16:112]:
        raise ValueError("Second gameplay-origin snapshot unexpectedly identical")
    return {
        "classification": "two_genuine_guest_written_generation_snapshots",
        "older_slot": 0, "newer_slot": 1,
        "older_generation": older["generation"],
        "newer_generation": newer["generation"],
        "older_sha256": older["sha256"],
        "newer_sha256": newer["sha256"],
        "older_native_x": old_x, "newer_native_x": new_x,
        "collectible_count_in_both": 2,
        "world_and_binding_same": True,
        "nintendo_switch_hardware_sd_verified": False,
        "real_flash_power_loss_verified": False,
    }


def verify_resave(first: Path, second: Path, root: Path,
                  first_receipt: dict) -> dict:
    if first.resolve() == second.resolve():
        raise ValueError("First and second genuine guest folders are identical")
    if (first / "raster-exit-status.txt").read_text().strip() != "0":
        raise ValueError("Original save process did not exit cleanly")
    require_process(second, RESAVE_EVENTS, "second actual SD-save process")
    base, digest_base = load_guest_frame(first, 485)
    fresh, fresh_digest = load_guest_frame(second, 30)
    loaded, loaded_digest = load_guest_frame(second, 130)
    moved, moved_digest = load_guest_frame(second, 265)
    saved, saved_digest = load_guest_frame(second, 345)
    stable, stable_digest = load_guest_frame(second, 445)
    if (base["sd_status"] != 1 or
        base["lights"] != (1, 1, 1, 1, 1) or
        base["collected_count"] != 2):
        raise ValueError("First guest process lacks original earned full-progress scene")
    if (fresh["lights"] != (0, 0, 0, 0, 0) or
        fresh["collected_count"] != 0 or fresh["sd_status"] != 0):
        raise ValueError("Second guest process did not start from empty RAM")
    if (loaded != base or loaded_digest != digest_base):
        raise ValueError("Second actual guest process did not restore original SD saved scene")
    for state in (moved, saved, stable):
        if (state["lights"] != base["lights"] or
            state["collected_count"] != 2 or state["sd_status"] != 1):
            raise ValueError("Movement/save unexpectedly changed earned quest or SD indicators")
    if (moved["native_player_x"] - loaded["native_player_x"] < 8 or
        saved["native_player_x"] != moved["native_player_x"] or
        stable["native_player_x"] != saved["native_player_x"]):
        raise ValueError("Genuine D-pad player move failed or was unstable before save")
    if (moved_digest == digest_base or
        saved_digest != moved_digest or stable_digest != saved_digest):
        raise ValueError("Second actual save did not preserve moved in-game world pixels")
    journal = validate_two_generations(root, first_receipt)
    if (abs(journal["older_native_x"] - base["native_player_x"]) > 1.1 or
        abs(journal["newer_native_x"] - saved["native_player_x"]) > 1.1):
        raise ValueError("Real second SD journal bytes disagree with guest player pixels")
    return {
        **journal,
        "classification": "real_nexium_two_guest_origin_sd_save_generations",
        "second_process_real_load_move_resave_npad_events": len(RESAVE_EVENTS),
        "newer_world_pixels_differ_from_older": True,
        "independent_second_process_guest_pngs": [30, 130, 265, 345, 445],
        "real_second_process_save_of_different_progress": True,
        "actual_second_save_file_bytes_verified": True,
    }


def verify_final_cold(first: Path, second: Path, third: Path, root: Path,
                      first_receipt: dict, resave_report: dict) -> dict:
    if len({first.resolve(), second.resolve(), third.resolve()}) != 3:
        raise ValueError("Three separate actual host guest processes required")
    if (resave_report.get("classification") !=
        "real_nexium_two_guest_origin_sd_save_generations"):
        raise ValueError("Second genuine SD-save receipt is untrusted")
    require_process(third, COLD_RESTORE_EVENTS, "third cold newest-load process")
    fresh, fresh_digest = load_guest_frame(third, 30)
    before, before_digest = load_guest_frame(third, 518)
    restored, restored_digest = load_guest_frame(third, 540)
    older, older_digest = load_guest_frame(first, 485)
    newest, newest_digest = load_guest_frame(second, 345)
    if (fresh["lights"] != (0, 0, 0, 0, 0) or
        fresh["collected_count"] != 0 or fresh["sd_status"] != 0 or
        fresh != before or fresh_digest != before_digest):
        raise ValueError("Final cold process was not a fresh empty game")
    if (restored != newest or restored_digest != newest_digest or
        restored_digest == older_digest or
        restored["native_player_x"] - older["native_player_x"] < 8):
        raise ValueError("Third genuine host process did not choose NEWEST gameplay-written SD slot")
    latest = validate_two_generations(root, first_receipt)
    for attr in ("older_sha256", "newer_sha256", "older_generation",
                 "newer_generation"):
        if resave_report.get(attr) != latest[attr]:
            raise ValueError("Guest cold load modified one of the real SD saves")
    return {
        "classification": "real_nexium_cold_latest_of_two_genuine_guest_saved_generations",
        "real_first_gameplay_written_save": True,
        "real_second_gameplay_written_save": True,
        "real_second_save_contains_different_player_position": True,
        "third_new_process_kernel_npad_only_restore_events": len(COLD_RESTORE_EVENTS),
        "third_process_restored_newest_pixels_not_older": True,
        "both_original_guest_written_slot_hashes_unchanged": True,
        "nintendo_switch_hardware_sd_verified": False,
        "real_power_loss_verified": False,
        "original_ios_fidelity_verified": False,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    subs = ap.add_subparsers(dest="action", required=True)
    a = subs.add_parser("resave")
    a.add_argument("--first-evidence", required=True, type=Path)
    a.add_argument("--second-evidence", required=True, type=Path)
    a.add_argument("--root", required=True, type=Path)
    a.add_argument("--first-receipt", required=True, type=Path)
    a.add_argument("--out", required=True, type=Path)
    b = subs.add_parser("cold")
    b.add_argument("--first-evidence", required=True, type=Path)
    b.add_argument("--second-evidence", required=True, type=Path)
    b.add_argument("--third-evidence", required=True, type=Path)
    b.add_argument("--root", required=True, type=Path)
    b.add_argument("--first-receipt", required=True, type=Path)
    b.add_argument("--resave-report", required=True, type=Path)
    b.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)
    first_receipt = json.loads(args.first_receipt.read_text())
    if args.action == "resave":
        result = verify_resave(args.first_evidence, args.second_evidence,
                               args.root, first_receipt)
    else:
        result = verify_final_cold(
            args.first_evidence, args.second_evidence, args.third_evidence,
            args.root, first_receipt, json.loads(args.resave_report.read_text()))
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
