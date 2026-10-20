"""Verify *original* NeXium guest PNGs show controller-driven pause.

No RAM patching, guest-state injection, synthetic screenshot generation or
rewriting of emulator output is permitted by this verifier.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from instrument_nexium_pause import FRAMES, HID_EVENTS

# Raw portable uint32_t RGBA framebuffer is saved as little-endian PNG RGB.
PAUSE_BORDER = (109, 200, 225)  # 0xffe1c86d
PAUSE_TEXT = (191, 230, 241)    # 0xfff1e6bf


def verify(directory: Path) -> dict:
    from PIL import Image
    from verify_nexium_guest_pngs import describe

    log_lines = set((directory / "raster-runner.log").read_text().splitlines())
    for frame, action in HID_EVENTS:
        if f"HEMAN_PAUSE_HID frame={frame} {action}" not in log_lines:
            raise ValueError(f"Missing exact NeXium Minus/Right edge {frame}")
    positions = {}
    pixels = {}
    for frame in FRAMES:
        prefix = f"HEMAN_GUEST_FRAME_PNG frame={frame} dimensions=640x360 path="
        if not any(x.startswith(prefix) for x in log_lines):
            raise ValueError(f"Missing real guest PNG capture log at {frame}")
        filename = directory / f"raster-frame-{frame:04}.png"
        if not filename.is_file():
            raise FileNotFoundError(filename)
        with Image.open(filename) as raw:
            if raw.format != "PNG":
                raise ValueError(f"Frame {frame}: expected original PNG")
            image = raw.convert("RGB")
        if image.size != (640, 360):
            raise ValueError(f"Frame {frame}: unexpected guest framebuffer")
        count, diversity, world_x = describe(image)
        if count != 192 or diversity < 8:
            raise ValueError(f"Frame {frame}: true world-X HUD marker missing")
        paused = (image.getpixel((224, 131)) == PAUSE_BORDER
                  and image.getpixel((270, 162)) == PAUSE_TEXT)
        if (image.getpixel((224, 131)) == PAUSE_BORDER) != (
                image.getpixel((270, 162)) == PAUSE_TEXT):
            raise ValueError(f"Frame {frame}: partial PAUSED badge")
        expected_pause = frame in (110, 135)
        if paused != expected_pause:
            raise ValueError(f"Frame {frame}: PAUSED visibility mismatch")
        positions[frame] = round(world_x, 2)
        # Full-frame equality during the freeze proves that not even the
        # independent patrol/enemy animation advanced in the pause interval.
        pixels[frame] = hashlib.sha256(image.tobytes()).hexdigest()

    if positions[70] - positions[30] < 20:
        raise ValueError("Right did not advance player before pause")
    if abs(positions[135] - positions[110]) > 2:
        raise ValueError("World player moved while Minus pause active")
    if pixels[110] != pixels[135]:
        raise ValueError("Guest framebuffer changed during held pause")
    if positions[175] - positions[135] < 15:
        raise ValueError("Player did not resume after Minus toggle")
    if abs(positions[300] - positions[220]) > 6:
        raise ValueError("World player moved after final Right release")

    return {
        "frames": list(FRAMES),
        "controller_events": [list(x) for x in HID_EVENTS],
        "guest_world_x": [positions[f] for f in FRAMES],
        "pause_visible_at_frames": [110, 135],
        "paused_guest_frames_identical": True,
        "right_motion_before_pause": True,
        "right_motion_after_resume": True,
        "still_after_release": True,
        "frame_sha256": {str(f): pixels[f] for f in FRAMES},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.folder), indent=2, sort_keys=True))
    print("PASS: genuine guest Minus froze gameplay and resumed on second press")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
