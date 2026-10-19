"""Fail-closed original NeXium guest PNG proof of actual HM_EXIT CLEAR.

Checks source-authored guest frame_rx screenshots and exact HID records;
never reads emulated RAM, edits frames or mutates the native game state.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from instrument_nexium_exit_clear import FRAMES, INPUT_EVENTS

# The C99 RGBA8888 constants are little-endian when read from true PNG RGB.
CLEAR_BORDER = (80, 105, 33)   # 0xff216950
CLEAR_LETTER = (134, 212, 240)  # 0xfff0d486


def verify(folder: Path) -> dict:
    from PIL import Image
    from verify_nexium_guest_pngs import describe

    states = {}
    for frame in FRAMES:
        file = folder / f"raster-frame-{frame:04}.png"
        if not file.is_file():
            raise FileNotFoundError(f"Missing original NeXium guest PNG frame {frame}")
        with Image.open(file) as original:
            if original.format != "PNG":
                raise ValueError(f"Frame {frame}: not a true PNG")
            rgb = original.convert("RGB")
        if rgb.size != (640, 360):
            raise ValueError(f"Frame {frame}: guest resolution mismatch")
        count, variety, position = describe(rgb)
        if count != 192 or variety < 8:
            raise ValueError(f"Frame {frame}: genuine player position marker missing")
        border = rgb.getpixel((547, 47))
        letter = rgb.getpixel((553, 53))
        clear = border == CLEAR_BORDER and letter == CLEAR_LETTER
        if (border == CLEAR_BORDER) != (letter == CLEAR_LETTER):
            raise ValueError(f"Frame {frame}: partial or forged CLEAR badge")
        states[frame] = (round(position, 2), clear, count, variety)

    if states[30][1]:
        raise ValueError("CLEAR appeared before any right-input or exit contact")
    for frame in (80, 120, 300):
        if not states[frame][1]:
            raise ValueError(f"Frame {frame}: native HM_EXIT CLEAR not visible")
    if states[80][0] - states[30][0] < 50:
        raise ValueError("D-pad did not move player far enough to reach exit")
    if states[120][0] - states[30][0] < 50:
        raise ValueError("Player position did not persist through exit")
    if abs(states[300][0] - states[120][0]) > 6:
        raise ValueError("Player moved after releasing D-pad Right")

    log_lines = set((folder / "raster-runner.log").read_text().splitlines())
    for frame in FRAMES:
        prefix = f"HEMAN_GUEST_FRAME_PNG frame={frame} dimensions=640x360 path="
        if not any(line.startswith(prefix) for line in log_lines):
            raise ValueError(f"Missing genuine guest frame_rx PNG log for {frame}")
    for frame, action in INPUT_EVENTS:
        exact = f"HEMAN_HID_SCHEDULE frame={frame} {action}"
        if exact not in log_lines:
            raise ValueError(f"Missing exact real NeXium HID event {frame}")

    return {
        "frames": list(FRAMES),
        "exit_visible": [frame for frame in FRAMES if states[frame][1]],
        "exit_hidden_before_input": not states[30][1],
        "player_world_x_markers": [states[frame][0] for frame in FRAMES],
        "release_stops_world_motion": True,
        "genuine_controller_events": [list(e) for e in INPUT_EVENTS],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("folder", type=Path)
    args = ap.parse_args()
    print(json.dumps(verify(args.folder), indent=2, sort_keys=True))
    print("PASS: genuine NeXium D-pad activated native HM_EXIT and rendered CLEAR")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
