"""Require actual NeXium game HUD proof of checkpoint + native B respawn.

Reads original asset-free RGBA framebuffer bytes captured from guest frame_rx,
not screenshots of the emulator GUI, inferred coordinates or host-only tests.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

FRAMES = (30, 95, 145, 195, 230)
PLAYER_HP = (101, 121, 231)
ENEMY_HP = (109, 200, 225)
COUNTER_OFF = (81, 61, 40)
COUNTER_ON = (138, 213, 66)
FLAG_OFF = (119, 205, 255)
FLAG_ON = (166, 228, 119)
HID_EVENTS = (
    (45, "buttons=DRIGHT"),
    (78, "buttons="),
    (107, "buttons=B"),
    (117, "buttons="),
    (160, "buttons=DRIGHT"),
    (174, "buttons="),
)


def verify(folder: Path) -> dict:
    from PIL import Image
    from verify_nexium_guest_pngs import describe

    world_x = []
    frames = []
    for n, frame in enumerate(FRAMES):
        file = folder / f"raster-frame-{frame:04}.png"
        if not file.is_file():
            raise FileNotFoundError(f"Missing real guest checkpoint frame {frame}")
        with Image.open(file) as raw:
            if raw.format != "PNG":
                raise ValueError(f"Guest checkpoint frame {frame} is not a PNG")
            rgb = raw.convert("RGB")
        marker_pixels, colors, x = describe(rgb)
        if marker_pixels != 192 or colors < 8:
            raise ValueError(f"Frame {frame}: missing source-authored x marker")
        if [rgb.getpixel((px, 18)) for px in (18, 36, 54)] != [PLAYER_HP]*3:
            raise ValueError(f"Frame {frame}: hero HP changed unexpectedly")
        if [rgb.getpixel((px, 18)) for px in (226, 244)] != [ENEMY_HP]*2:
            raise ValueError(f"Frame {frame}: enemy HP changed unexpectedly")
        flag = rgb.getpixel((190, 250))
        expected_flag = FLAG_OFF if n == 0 else FLAG_ON
        if flag != expected_flag:
            raise ValueError(
                f"Frame {frame}: checkpoint flag activation mismatch: {flag}"
            )
        counter = rgb.getpixel((522, 62))
        expected_counter = COUNTER_OFF if n < 2 else COUNTER_ON
        if counter != expected_counter:
            raise ValueError(
                f"Frame {frame}: native respawn counter mismatch: {counter}"
            )
        frames.append({"frame": frame, "checkpoint_activated": n > 0,
                       "native_respawns": 0 if n < 2 else 1,
                       "world_x_marker": round(x, 2), "sample_colors": colors})
        world_x.append(x)

    if abs(world_x[0] - 125.5) > 2:
        raise ValueError(f"Hero did not start at initial x=50: {world_x[0]}")
    if world_x[1] - world_x[0] < 70:
        raise ValueError(f"Real D-pad did not activate distant checkpoint: {world_x}")
    if abs(world_x[2] - 205.5) > 4:
        raise ValueError(f"B button did not respawn at checkpoint x=90: {world_x}")
    if world_x[1] - world_x[2] < 20:
        raise ValueError(f"Reset returned to same location, not checkpoint: {world_x}")
    if world_x[3] - world_x[2] < 14:
        raise ValueError(f"Player cannot move after native checkpoint reset: {world_x}")
    if abs(world_x[4] - world_x[3]) > 8:
        raise ValueError(f"Hero kept moving after Right release: {world_x}")

    log = (folder / "raster-runner.log").read_text()
    for frame in FRAMES:
        if f"HEMAN_GUEST_FRAME_PNG frame={frame} " not in log:
            raise ValueError(f"Missing true guest framebuffer event at {frame}")
    for frame, action in HID_EVENTS:
        marker = f"HEMAN_CHECKPOINT_HID frame={frame} {action}"
        if marker not in log:
            raise ValueError(f"Missing real NeXium checkpoint HID: {marker}")

    return {"guest_frame_evidence": frames,
            "checkpoint_activation_by_right": True,
            "b_reset_to_activated_checkpoint": True,
            "control_resumed_after_respawn": True,
            "release_stops_movement": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.folder), indent=2, sort_keys=True))
    print("PASS: real NeXium D-pad checkpoint activation, B recovery and movement")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
