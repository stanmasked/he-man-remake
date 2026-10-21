#!/usr/bin/env python3
"""Stage122: real cold guest must prioritize a *valid newer, different-progress* record.

Synthetic modification is restricted to the fictional Bio collectible in a
fresh isolated CI emulator SD fixture. It is NOT a genuine second gameplay save,
an iOS save, physical power-loss proof, or cryptographically trusted content.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import struct
from pathlib import Path

from audit_switch_sd_journal import RECORD_SIZE, decode_record, fnv64
from instrument_nexium_lore_lab import COLD_RESTORE_EVENTS, FRAMES
from verify_nexium_cold_restart import load_guest_frame
from verify_nexium_sd_disk_receipt import (
    audit_confined_sd, read_confined_sd_slot_bytes,
)

ART_EVENT_INDEX = 2  # The exclusively synthetic source-authored test world.


def lab(root: Path) -> Path:
    return root / "sdmc" / "switch" / "heman_lore_lab"


def prepare_divergent_slots(source_root: Path, target_root: Path, first: dict) -> dict:
    if not source_root.is_absolute() or not target_root.is_absolute():
        raise ValueError("CI SD data roots must be absolute")
    if ".." in source_root.parts or ".." in target_root.parts:
        raise ValueError("Parent traversal in SD data root")
    if source_root.resolve() == target_root.resolve():
        raise ValueError("Cannot mutate original guest SD root")
    if target_root.exists() or target_root.is_symlink():
        raise ValueError("Divergent fixture target must not already exist")
    if (first.get("classification") !=
            "guest_optical_round_trip_with_structural_emulator_sd_bytes" or
            first.get("actual_emulator_file_bytes_examined") is not True):
        raise ValueError("Missing independently proven original SD receipt")
    disk, issue = audit_confined_sd(source_root)
    if (issue or disk["slots"] != first.get("emulator_sd_slots") or
            disk["latest_structural_candidate_slot"] is None):
        raise ValueError("Original virtual SD no longer matches first-process receipt")
    slot = disk["latest_structural_candidate_slot"]
    entry = disk["slots"][slot]
    if (entry["status"] != "structurally_valid" or
            entry["collected_mask"] != 3 or entry["collected_count"] != 2):
        raise ValueError("A completed two-collectible guest record is required")
    previous = read_confined_sd_slot_bytes(source_root, slot, entry["sha256"])
    # A cleared pickup would otherwise immediately re-collect on the first
    # native frame after restore. Art is at x=56 in this fictional level.
    # Require a generous safety gap beyond actor half-width 5 + radius 4.
    old_player_x = struct.unpack_from("<f", previous, 16 + 28)[0]
    if not math.isfinite(old_player_x) or abs(old_player_x - 56.0) <= 12.0:
        raise ValueError("Source saved hero overlaps synthetic Art pickup; fixture would auto-recollect")
    generation = entry["generation"]
    if not (0 < generation < (1 << 64) - 1):
        raise ValueError("Cannot generate newer journal without wraparound")

    # Preserve all other world/player fields. Make a structurally valid but
    # visibly DIFFERENT synthetic snapshot: Art is uncollected, Bio remains.
    newer = bytearray(previous)
    picked = struct.unpack_from("<I", newer, 16 + 64)[0]
    if picked & (1 << ART_EVENT_INDEX) == 0 or (
        struct.unpack_from("<I", newer, 16 + 68)[0] & 1
    ) == 0:
        raise ValueError("Expected actual earned Bio and broken gate bits")
    struct.pack_into("<I", newer, 16 + 64, picked & ~(1 << ART_EVENT_INDEX))
    newer[16 + 82] = 1  # Bio only; distant Art item bit cleared.
    newer[16 + 83] = 1
    struct.pack_into("<Q", newer, 16 + 88, fnv64(newer[16:16 + 88]))
    struct.pack_into("<Q", newer, 8, generation + 1)
    struct.pack_into("<Q", newer, 112, fnv64(newer[:112]))

    old_meta = decode_record(previous)
    new_meta = decode_record(newer)
    if (old_meta.get("status") != "structurally_valid" or
            new_meta.get("status") != "structurally_valid" or
            old_meta["collected_count"] != 2 or
            new_meta["collected_count"] != 1 or
            new_meta["collected_mask"] != 1 or
            new_meta["generation"] != old_meta["generation"] + 1 or
            new_meta["world_seal"] != old_meta["world_seal"] or
            new_meta["bindings"] != old_meta["bindings"]):
        raise ValueError("Divergent record did not preserve a valid bound world")

    target = lab(target_root)
    target.mkdir(parents=True, exist_ok=False)
    (target / "progress0.bin").write_bytes(previous)
    (target / "progress1.bin").write_bytes(newer)
    verified, issue = audit_confined_sd(target_root)
    if (issue or verified["structurally_valid_slot_count"] != 2 or
            verified["latest_structural_candidate_slot"] != 1 or
            verified["ambiguous_world_binding"] or
            verified["slots"][0]["collected_count"] != 2 or
            verified["slots"][1]["collected_count"] != 1):
        raise ValueError("Fixture does not contain two distinct valid ranked saves")
    return {
        "classification": "synthetic_two_valid_divergent_progress_sd_fixture",
        "source_guest_snapshot_slot": slot,
        "older_generation": generation,
        "newer_generation": generation + 1,
        "older_sha256": hashlib.sha256(previous).hexdigest(),
        "newer_sha256": hashlib.sha256(newer).hexdigest(),
        "older_collected_mask": 3,
        "newer_collected_mask": 1,
        "older_collected_count": 2,
        "newer_collected_count": 1,
        "synthetically_modified_collectible": "fictional_concept_art",
        "actual_second_gameplay_save_observed": False,
        "real_guest_execution_verified": False,
        "hardware_sd_power_loss_verified": False,
        "original_ios_save_fidelity_verified": False,
    }


def masked_common_scene_digest(image_path: Path) -> str:
    """Only exempt the *known* Art HUD, pickup sprite and count bar rectangles.

    Do not alter guest PNGs; compare raw RGB guest pixels outside the precise
    regions which are legitimately affected by uncollecting Art in this
    fictional, source-authored world.
    """
    from PIL import Image
    if image_path.is_symlink() or not image_path.is_file():
        raise ValueError("Missing or linked source guest PNG")
    with Image.open(image_path) as file:
        if file.format != "PNG":
            raise ValueError("Not a real guest PNG")
        rgb = file.convert("RGB")
        if rgb.size != (640, 360):
            raise ValueError("Incorrect source guest PNG dimensions")
        raw = bytearray(rgb.tobytes())
    if len(raw) != 640 * 360 * 3:
        raise ValueError("Invalid guest pixel storage length")
    rects = (
        (186, 22, 228, 37),  # Art HUD lamp (42x15)
        (350, 22, 384, 37),  # variable-sized earned count indicator
        (420, 22, 456, 37),  # save/load diagnostic status, not game state
        (115, 183, 126, 194),  # fictional Art event2: ORIGIN_X 64 + 56 - 5
    )
    for x0, y0, x1, y1 in rects:
        for y in range(y0, y1):
            start = (y * 640 + x0) * 3
            raw[start:start + (x1-x0)*3] = b"\0" * ((x1-x0)*3)
    return hashlib.sha256(raw).hexdigest()


def verify_divergent_restore(first: Path, second: Path, root: Path,
                             manifest: dict) -> dict:
    if not all(p.is_absolute() for p in (first, second, root)):
        raise ValueError("All guest evidence paths must be absolute")
    if first.resolve() == second.resolve():
        raise ValueError("Guest runs must use distinct host processes")
    if manifest.get("classification") != "synthetic_two_valid_divergent_progress_sd_fixture":
        raise ValueError("Invalid divergent SD fixture receipt")
    for folder in (first, second):
        if (folder / "raster-exit-status.txt").read_text().strip() != "0":
            raise ValueError("Guest host process did not exit cleanly")
    log = (second / "raster-runner.log").read_text()
    if "Production runner complete" not in log:
        raise ValueError("New-process NeXium runner did not finish")
    cycles = re.findall(r"cycles=(\d+) svcs=(\d+) frames=(\d+)", log)
    if not cycles or max(int(a) for a, _, _ in cycles) <= 0 or (
            max(int(b) for _, b, _ in cycles) <= 0):
        raise ValueError("Missing new guest CPU/SVC progress")
    expected_hid = [
        f"HEMAN_LORE_HID frame={f} {packet}"
        for f, packet in COLD_RESTORE_EVENTS
    ]
    actual_hid = [line for line in log.splitlines()
                  if line.startswith("HEMAN_LORE_HID frame=")]
    if actual_hid != expected_hid:
        raise ValueError("Unexpected gameplay/save action in cold restore run")
    expected_pngs = [
        f"HEMAN_GUEST_FRAME_PNG frame={f} dimensions=640x360 "
        f"path={second / f'raster-frame-{f:04}.png'}"
        for f in FRAMES
    ]
    actual_pngs = [line for line in log.splitlines()
                   if line.startswith("HEMAN_GUEST_FRAME_PNG frame=")]
    if actual_pngs != expected_pngs:
        raise ValueError("Missing, reordered or aliased genuine guest frame_rx PNGs")

    saved, source_digest = load_guest_frame(first, 485)
    new, before_digest = load_guest_frame(second, 30)
    pre_load, pre_load_digest = load_guest_frame(second, 518)
    restored, restored_digest = load_guest_frame(second, 540)
    if saved["lights"] != (1, 1, 1, 1, 1) or (
            saved["collected_count"] != 2 or saved["sd_status"] != 1):
        raise ValueError("Original successful complete-collection scene missing")
    if new["lights"] != (0, 0, 0, 0, 0) or (
            new["collected_count"] != 0 or new["sd_status"] != 0):
        raise ValueError("Second OS process was not a fresh game")
    if new != pre_load or before_digest != pre_load_digest:
        raise ValueError("Cold game mutated before the only restore command")
    if restored["lights"] != (1, 1, 1, 0, 1) or (
            restored["collected_count"] != 1 or restored["sd_status"] != 1):
        raise ValueError("Native loader did not select the NEWER partial-progress slot")
    if restored["native_player_x"] != saved["native_player_x"]:
        raise ValueError("Changed progress unexpectedly teleported saved player")
    if source_digest == restored_digest:
        raise ValueError("Newer partial-progress state indistinguishable from older full state")
    if masked_common_scene_digest(first / "raster-frame-0485.png") != (
            masked_common_scene_digest(second / "raster-frame-0540.png")):
        raise ValueError("Divergent slot changed pixels outside legitimate Art/count regions")

    disk, issue = audit_confined_sd(root)
    if (issue or disk["structurally_valid_slot_count"] != 2 or
            disk["latest_structural_candidate_slot"] != 1 or
            disk["slots"][0].get("sha256") != manifest["older_sha256"] or
            disk["slots"][1].get("sha256") != manifest["newer_sha256"] or
            disk["slots"][0].get("collected_count") != 2 or
            disk["slots"][1].get("collected_count") != 1 or
            disk["slots"][1].get("generation") != manifest["newer_generation"]):
        raise ValueError("Guest altered/ignored the two independently ranked SD journals")
    return {
        "classification": "real_nexium_newer_divergent_progress_slot_selected",
        "two_structurally_valid_divergent_slots": True,
        "newer_generation_selected_in_guest_pixels": True,
        "original_completed_guest_scene_different": True,
        "unchanged_world_pixels_outside_art_and_count": True,
        "original_and_modified_journal_sha256_unchanged": True,
        "fresh_guest_process_and_real_npad_required": True,
        "synthetic_second_snapshot_not_a_genuine_gameplay_save": True,
        "nintendo_switch_hardware_sd_verified": False,
        "real_power_loss_verified": False,
        "original_ios_fidelity_verified": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="action", required=True)
    prep = subs.add_parser("prepare")
    prep.add_argument("--source-root", type=Path, required=True)
    prep.add_argument("--target-root", type=Path, required=True)
    prep.add_argument("--first-receipt", type=Path, required=True)
    prep.add_argument("--out", type=Path, required=True)
    check = subs.add_parser("verify")
    check.add_argument("--first-evidence", type=Path, required=True)
    check.add_argument("--cold-evidence", type=Path, required=True)
    check.add_argument("--target-root", type=Path, required=True)
    check.add_argument("--manifest", type=Path, required=True)
    check.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.action == "prepare":
        result = prepare_divergent_slots(
            args.source_root, args.target_root, json.loads(args.first_receipt.read_text())
        )
    else:
        result = verify_divergent_restore(
            args.first_evidence, args.cold_evidence, args.target_root,
            json.loads(args.manifest.read_text())
        )
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
