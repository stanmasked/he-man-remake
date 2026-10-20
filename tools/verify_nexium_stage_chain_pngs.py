"""Fail-closed actual NeXium guest proof for synthetic CLEAR -> A -> room 2.

Only original 640x360 guest PNGs and exact emulator HID/frame logs qualify.
No emulator RAM or screenshot manipulation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from instrument_nexium_stage_chain import FRAMES, HID_EVENTS

STAGE_FACE = (103, 73, 53)      # little-endian 0xff354967
STAGE_TEXT = (191, 230, 241)    # little-endian 0xfff1e6bf
CLEAR_BORDER = (80, 105, 33)    # 0xff216950
CLEAR_LETTER = (134, 212, 240)  # 0xfff0d486


def verify(directory: Path) -> dict:
    from PIL import Image
    from verify_nexium_guest_pngs import describe

    logs = set((directory / "raster-runner.log").read_text().splitlines())
    for frame, event in HID_EVENTS:
        if f"HEMAN_CHAIN_HID frame={frame} {event}" not in logs:
            raise ValueError(f"Missing exact native Right/A HID event at {frame}")

    positions = {}
    stages = {}
    clear = {}
    hashes = {}
    for frame in FRAMES:
        prefix = f"HEMAN_GUEST_FRAME_PNG frame={frame} dimensions=640x360 path="
        if not any(line.startswith(prefix) for line in logs):
            raise ValueError(f"Missing original emulator PNG log at {frame}")
        file = directory / f"raster-frame-{frame:04}.png"
        if not file.is_file():
            raise FileNotFoundError(file)
        with Image.open(file) as raw:
            if raw.format != "PNG":
                raise ValueError(f"Frame {frame}: not original PNG")
            rgb = raw.convert("RGB")
        if rgb.size != (640, 360):
            raise ValueError(f"Frame {frame}: invalid guest framebuffer size")
        count, colors, world_x = describe(rgb)
        if count != 192 or colors < 8:
            raise ValueError(f"Frame {frame}: no authentic world-X marker")

        # The original synthetic renderer's tiny stage marker is located
        # in unused top-HUD space. Top-left digit cell differentiates 1/2.
        face = rgb.getpixel((404, 9))
        center = rgb.getpixel((408, 9))
        if center != STAGE_TEXT or face not in (STAGE_FACE, STAGE_TEXT):
            raise ValueError(f"Frame {frame}: source-authored stage badge absent")
        stages[frame] = 1 if face == STAGE_FACE else 2
        border = rgb.getpixel((547, 47))
        letter = rgb.getpixel((553, 53))
        if (border == CLEAR_BORDER) != (letter == CLEAR_LETTER):
            raise ValueError(f"Frame {frame}: partial CLEAR indicator")
        clear[frame] = border == CLEAR_BORDER and letter == CLEAR_LETTER
        positions[frame] = round(world_x, 2)
        hashes[frame] = hashlib.sha256(rgb.tobytes()).hexdigest()

    if [stages[f] for f in FRAMES] != [1, 1, 2, 2, 2, 2]:
        raise ValueError("Guest did not transition from stage 1 to 2 after A")
    if clear[30] or not clear[75]:
        raise ValueError("First room CLEAR not earned by native Right movement")
    if any(clear[f] for f in (105, 140, 180, 240)):
        raise ValueError("Stage 1 completion leaked into the second room")
    if positions[75] - positions[30] < 50:
        raise ValueError("First-room Right motion insufficient")
    if positions[75] - positions[105] < 50:
        raise ValueError("Second room did not reset native player position")
    if positions[140] - positions[105] < 30:
        raise ValueError("Second-room Right input did not move the player")
    if abs(positions[180] - positions[240]) > 6:
        raise ValueError("Second-room world motion persisted after release")

    return {
        "frames": list(FRAMES),
        "hid_events": [list(e) for e in HID_EVENTS],
        "stages": [stages[f] for f in FRAMES],
        "clear_visible": [f for f in FRAMES if clear[f]],
        "guest_world_x": [positions[f] for f in FRAMES],
        "stage_1_clear_confirmed": True,
        "explicit_A_transition_confirmed": True,
        "stage_2_movement_and_release_confirmed": True,
        "frame_sha256": {str(f): hashes[f] for f in FRAMES},
        "original_ios_content_verified": False,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("folder", type=Path)
    args = p.parse_args()
    print(json.dumps(verify(args.folder), sort_keys=True, indent=2))
    print("PASS: real guest completed first room, pressed A, and entered second")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
