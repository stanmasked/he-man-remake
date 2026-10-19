"""Verify that real NeXium X-button input removes exactly two enemy HP.

Evidence is actual guest 640x360 PNG bytes, not a GUI screenshot,
emulator splash, frame count or synthetic log-only combat state.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from PIL import Image
from verify_nexium_guest_pngs import describe

FRAMES = (30, 65, 120)
# Renderer holds uint32_t 0xffe1c86d / 0xff493b51. Framebuffer is
# little-endian RGBA8888, so bytes are RGB (109,200,225) / (81,59,73).
HEALTHY = (109, 200, 225)
DEFEATED = (81, 59, 73)
HEALTH_X = (226, 244)
HEALTH_Y = 18
PLAYER_TICK_COLOR = (101, 121, 231)


def verify(directory: Path) -> dict:
    measured, markers, player = [], [], []
    for index in FRAMES:
        p = directory / f"raster-frame-{index:04}.png"
        if not p.is_file():
            raise FileNotFoundError(f"Missing genuine guest PNG: {p}")
        with Image.open(p) as src:
            if src.format != "PNG":
                raise ValueError(f"Frame {index} is not a PNG image")
            img = src.convert("RGB")
            magenta_count, colors, player_world_x = describe(img)
            if magenta_count != 192 or colors < 8:
                raise ValueError(f"Missing source-authored player marker: {index}")
            markers.append(round(player_world_x, 2))
            measured.append([img.getpixel((x, HEALTH_Y)) for x in HEALTH_X])
            player.append([img.getpixel((x, HEALTH_Y)) for x in (18, 36, 54)])

    expected = [
        [HEALTHY, HEALTHY],    # before real controller input
        [HEALTHY, DEFEATED],   # after X was pressed once
        [DEFEATED, DEFEATED],  # after X was pressed twice
    ]
    if measured != expected:
        raise ValueError(
            f"Guest enemy HP did not fall exactly 2->1->0: "
            f"actual={measured}, expected={expected}"
        )
    if any(abs(x-markers[0]) > 2 for x in markers):
        raise ValueError(f"Player drifted without directional input: {markers}")
    if any(ticks != [PLAYER_TICK_COLOR]*3 for ticks in player):
        raise ValueError(f"Player HP unexpectedly changed: {player}")
    log = (directory / "raster-runner.log").read_text()
    for frame, action in ((45, "buttons=X"), (58, "buttons="),
                          (85, "buttons=X"), (98, "buttons=")):
        msg = f"HEMAN_ATTACK_HID frame={frame} {action}"
        if msg not in log:
            raise ValueError(f"Missing actual NeXium controller event: {msg}")
    return {
        "guest_frames": list(FRAMES),
        "enemy_hp": [2, 1, 0],
        "enemy_hp_pixel_rgb": measured,
        "player_hp_pixel_rgb": player,
        "player_world_x_px": markers,
        "controller_events": ["X pressed @45", "released @58",
                              "X pressed @85", "released @98"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    result = verify(args.folder)
    print(json.dumps(result, indent=2, sort_keys=True))
    print("PASS: actual guest X-button attacks lowered enemy HP 2->1->0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
