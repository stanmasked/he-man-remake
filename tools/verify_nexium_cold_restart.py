#!/usr/bin/env python3
"""Stage117: independent *emulated* process cold restore, fail closed.

This requires a real second NeXium debug_boot process with NO save/reset/
upgrade commands, a successful guest optical restore, unchanged actual journal
hashes, and real guest frame_rx PNG identity to the first process' saved scene.
It does NOT claim physical Switch SD durability or power-loss atomicity.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from instrument_nexium_lore_lab import COLD_RESTORE_EVENTS, FRAMES
from verify_nexium_lore_lab_pngs import inspect, normalized_digest, verify


def load_guest_frame(folder: Path, frame: int):
    from PIL import Image
    expected = folder / f"raster-frame-{frame:04}.png"
    if not expected.is_file() or expected.is_symlink():
        raise ValueError(f"Missing or linked real guest PNG {frame}")
    with Image.open(expected) as pic:
        if pic.format != "PNG":
            raise ValueError(f"Non-PNG guest file at frame {frame}")
        rgb = pic.convert("RGB")
        status = inspect(rgb)
        digest = normalized_digest(rgb)
    return status, digest


def attest_reboot(first: Path, second: Path, first_receipt: dict, final_receipt: dict) -> dict:
    if first.resolve() == second.resolve():
        raise ValueError("First and second evidence directories are identical")
    if first_receipt.get("classification") != (
        "guest_optical_round_trip_with_structural_emulator_sd_bytes"
    ):
        raise ValueError("First process lacks a green guest plus physical emulator file receipt")
    if first_receipt.get("actual_emulator_file_bytes_examined") is not True:
        raise ValueError("First process did not independently inspect valid SD bytes")
    if final_receipt.get("actual_emulator_file_bytes_examined") is not True:
        raise ValueError("Second process lost disk evidence")
    if first_receipt.get("emulator_sd_slots") != final_receipt.get("emulator_sd_slots"):
        raise ValueError("SD slot bytes or structural metadata changed during restore-only run")

    if (first / "raster-exit-status.txt").read_text().strip() != "0":
        raise ValueError("First independent runner failed to exit cleanly")
    if (second / "raster-exit-status.txt").read_text().strip() != "0":
        raise ValueError("Second independent runner failed to exit cleanly")
    if not (first / "raster-runner.log").is_file():
        raise ValueError("Missing first process log")
    log = (second / "raster-runner.log").read_text()
    if "Production runner complete" not in log:
        raise ValueError("Second genuine guest process never completed")
    samples = re.findall(r"cycles=(\d+) svcs=(\d+) frames=(\d+)", log)
    if not samples or max(int(row[0]) for row in samples) <= 0 or (
        max(int(row[1]) for row in samples) <= 0
    ):
        raise ValueError("No second-process guest CPU/SVC evidence")
    expected_hid = [
        f"HEMAN_LORE_HID frame={frame} {packet}"
        for frame, packet in COLD_RESTORE_EVENTS
    ]
    observed_hid = [line for line in log.splitlines()
                    if line.startswith("HEMAN_LORE_HID frame=")]
    if observed_hid != expected_hid:
        raise ValueError("Second process performed an unexpected guest HID action")
    expected_frames = [
        f"HEMAN_GUEST_FRAME_PNG frame={frame} dimensions=640x360 path="
        for frame in FRAMES
    ]
    arrivals = [line for line in log.splitlines()
                if line.startswith("HEMAN_GUEST_FRAME_PNG frame=")]
    if len(arrivals) != len(expected_frames):
        raise ValueError("Second process lacks its genuine frame_rx PNG sequence")
    for line, prefix, frame in zip(arrivals, expected_frames, FRAMES):
        expected_path = second / f"raster-frame-{frame:04}.png"
        if not line.startswith(prefix) or (
            Path(line[len(prefix):]) != expected_path.absolute()
        ):
            raise ValueError("Second process PNG log does not match actual frame locations")

    first_state, first_digest = load_guest_frame(first, 485)
    before_state, before_digest = load_guest_frame(second, 30)
    pre_restore_state, pre_restore_digest = load_guest_frame(second, 518)
    restored_state, restored_digest = load_guest_frame(second, 540)
    if (before_state["lights"] != (0, 0, 0, 0, 0) or
        before_state["collected_count"] != 0 or
        before_state["sd_status"] != 0):
        raise ValueError("Second process did not start with a fresh empty game state")
    if before_state != pre_restore_state or before_digest != pre_restore_digest:
        raise ValueError("Second process modified its game state before SD restore")
    if first_state["sd_status"] != 1:
        raise ValueError("First process did not show a successful SD save")
    if restored_state["sd_status"] != 1:
        raise ValueError("Second process did not show a successful SD restore")
    if first_digest != restored_digest or (
        first_state["lights"] != restored_state["lights"]
    ) or first_state["collected_count"] != restored_state["collected_count"]:
        raise ValueError("Cold-process SD restore did not reproduce saved game pixels")
    if restored_digest == before_digest:
        raise ValueError("Restore did not modify the fresh new process scene")
    return {
        "classification": "real_nexium_second_process_sd_restore_pixels_and_disk_bytes",
        "first_process_guest_sd_file_receipt_verified": True,
        "second_process_guest_cpu_and_svc_verified": True,
        "second_process_has_save_commands": False,
        "second_process_real_guest_restore_hid_edges": len(COLD_RESTORE_EVENTS),
        "second_process_fresh_state_confirmed": True,
        "second_process_guest_pngs_inspected": [30, 518, 540],
        "first_process_guest_saved_frame": 485,
        "restored_world_pixels_match_first_process": True,
        "emulator_journal_bytes_unchanged_between_processes": True,
        "independent_emulator_process_cold_restart_verified": True,
        "nintendo_switch_hardware_sd_verified": False,
        "power_loss_durability_verified": False,
        "original_ios_fidelity_verified": False,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("first", type=Path, help="first genuine guest process evidence folder")
    ap.add_argument("second", type=Path, help="separate cold-process guest evidence folder")
    ap.add_argument("--initial-receipt", type=Path, required=True)
    ap.add_argument("--final-receipt", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    result = attest_reboot(
        args.first, args.second,
        json.loads(args.initial_receipt.read_text()),
        json.loads(args.final_receipt.read_text()),
    )
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True, indent=2))
    print("PASS: genuine separate NeXium process restored unchanged SD bytes", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
