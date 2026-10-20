"""Fail-closed NeXium ZL air attack evidence on *real* guest framebuffer PNGs.

A host-only fake PNG test is never evidence of guest execution. The strict
production checker sees the guest ROM framebuffer and exact HID transcript.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from instrument_nexium_air_smash import FRAMES, HID_EVENTS
from verify_nexium_guest_pngs import describe

# NRO renderer packs color as little-endian 0xAABBGGRR; these are RGBA RGB.
READY = (216, 224, 110)    # 0xff6ee0d8
ACTIVE = (85, 170, 255)    # 0xffffaa55
IMPACT = (138, 213, 66)   # 0xff42d58a
COOLDOWN = (120, 101, 86) # 0xff566578
BORDER = (73, 52, 32)     # 0xff203449
STAGE_ONE = (103, 73, 53)
STAGE_TWO = (191, 230, 241)
FIRST_CLEAR_BORDER = (80, 105, 33)
FIRST_CLEAR_TEXT = (134, 212, 240)
CYAN_Y_MARK = (0, 255, 255)
KNOWN = {
    READY: "ready",
    ACTIVE: "active",
    IMPACT: "impact",
    COOLDOWN: "cooldown",
}


def height_marker(rgb) -> int:
    locations = [
        y for y in range(80, 340)
        if rgb.getpixel((476, y)) == CYAN_Y_MARK
    ]
    if len(locations) != 9 or locations[-1] - locations[0] != 8:
        raise ValueError("Missing true guest world-Y marker")
    return locations[0]


def verify(directory: Path) -> dict:
    from PIL import Image

    log = (directory / "raster-runner.log").read_text().splitlines()
    for frame, control in HID_EVENTS:
        exact = f"HEMAN_SMASH_HID frame={frame} {control}"
        if log.count(exact) != 1:
            raise ValueError(f"Missing/duplicate guest controller event at {frame}")
    records = {}
    hashes = {}
    paused_image = {}
    for frame in FRAMES:
        prefix = f"HEMAN_GUEST_FRAME_PNG frame={frame} dimensions=640x360 path="
        found = [line[len(prefix):] for line in log if line.startswith(prefix)]
        if len(found) != 1:
            raise ValueError(f"Missing/duplicated authentic guest PNG attestation at {frame}")
        candidate = directory / f"raster-frame-{frame:04}.png"
        if (not candidate.is_file() or
                Path(found[0]).resolve() != candidate.resolve() or
                not Path(found[0]).is_absolute()):
            raise ValueError(f"Missing/wrong-run guest PNG for {frame}")
        with Image.open(candidate) as img:
            if img.format != "PNG":
                raise ValueError(f"Expected a native frame_rx PNG at {frame}")
            rgb = img.convert("RGB")
        if rgb.size != (640, 360):
            raise ValueError(f"Unexpected guest render dimensions at {frame}")
        count, colors, xpos = describe(rgb)
        if count != 192 or colors < 8:
            raise ValueError(f"No native gameplay HUD/player at {frame}")
        stage = (
            1 if rgb.getpixel((404, 9)) == STAGE_ONE else
            2 if rgb.getpixel((404, 9)) == STAGE_TWO else 0)
        if not stage or rgb.getpixel((408, 9)) != STAGE_TWO:
            raise ValueError(f"Stage badge missing/wrong at {frame}")
        first_clear = (
            rgb.getpixel((547, 47)) == FIRST_CLEAR_BORDER and
            rgb.getpixel((553, 53)) == FIRST_CLEAR_TEXT)
        status = None
        if stage == 2:
            if rgb.getpixel((575, 79)) != BORDER:
                raise ValueError("No actual ZL source HUD border on stage 2")
            status = KNOWN.get(rgb.getpixel((588, 88)))
            if status is None:
                raise ValueError(f"Invalid/invisible guest ZL indicator {frame}")
        payload = rgb.tobytes()
        hashes[frame] = hashlib.sha256(payload).hexdigest()
        if frame in (183, 193):
            paused_image[frame] = payload
        records[frame] = {
            "stage": stage, "status": status, "clear": first_clear,
            "world_x": round(xpos, 2), "height_y": height_marker(rgb),
        }
    if records[75]["stage"] != 1 or not records[75]["clear"]:
        raise ValueError("Stage-1 native CLEAR was not earned by real D-pad")
    if any(records[f]["stage"] != 2 for f in FRAMES if f != 75):
        raise ValueError("No genuine A transition into original synthetic room 2")
    if any(records[f]["clear"] for f in FRAMES if f != 75):
        raise ValueError("Stage-2 FINISH appeared before the opt-in ZL experiment")
    if records[125]["status"] != "ready" or records[143]["status"] != "ready":
        raise ValueError("ZL must be ready before native airborne activation")
    if records[143]["height_y"] >= records[125]["height_y"] - 8:
        raise ValueError("A-button jump did not show a genuine ascent in guest world-Y")
    strike_window = [records[f]["status"] for f in (145, 146, 147, 148)]
    if "active" not in strike_window:
        raise ValueError("Never observed genuine active ZL strike frames")
    if "impact" not in [records[f]["status"] for f in (147, 148, 150, 152)]:
        raise ValueError("Never observed ZL impact from genuine swept landing")
    if records[158]["status"] != "cooldown":
        raise ValueError("Fresh second ZL should not bypass native cooldown")
    if records[183]["status"] != "cooldown" or records[193]["status"] != "cooldown":
        raise ValueError("Pause unexpectedly advanced aerial recovery")
    if paused_image[183] != paused_image[193]:
        raise ValueError("Native Minus pause did not freeze complete guest framebuffer")
    if records[211]["status"] not in ("cooldown", "ready"):
        raise ValueError("No valid ability state after Minus resume")
    if records[231]["status"] != "ready":
        raise ValueError("ZL cooldown never returned to ready after real frames")
    if records[245]["status"] != "ready":
        raise ValueError("Native B respawn did not restore ready ZL")
    if records[231]["world_x"] - records[245]["world_x"] < 70:
        raise ValueError("Actual B edge did not move hero back to room-2 spawn")
    if hashes[231] == hashes[245]:
        raise ValueError("Guest framebuffer did not change on native B retry")
    return {
        "schema_version": 1,
        "frames": list(FRAMES),
        "all_guest_hid_injections_observed": True,
        "real_guest_jump_and_zl_activation": True,
        "genuine_swept_landing_impact_visible": True,
        "second_zl_blocked_by_cooldown": True,
        "pause_retained_identical_guest_pixels": True,
        "native_b_respawn_confirmed": True,
        "original_ios_ability_parity_verified": False,
        "guest_frame_sha256": {str(f): hashes[f] for f in FRAMES},
        "states": {str(f): records[f]["status"] for f in FRAMES},
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("directory", type=Path)
    args = p.parse_args()
    print(json.dumps(verify(args.directory), indent=2, sort_keys=True))
    print("PASS: genuine synthetic Switch ZL jump/impact/cooldown/pause/B guest proof")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
