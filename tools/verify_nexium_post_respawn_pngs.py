"""Require genuine NeXium guest HUD pixels proving movement after respawn.

Input is supplied through NeXium's existing HID file interface. This verifier
never reads internal emulator/guest memory and never generates substitute PNGs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

FRAMES = (62, 90, 160, 220)
EXPECTED_HP = (3, 2, 2, 2)
PLAYER_ALIVE = (101, 121, 231)
PLAYER_EMPTY = (81, 59, 73)
ENEMY_ALIVE = (109, 200, 225)
RESPAWN_GREEN = (138, 213, 66)


def verify(folder: Path) -> dict:
    from PIL import Image
    from verify_nexium_guest_pngs import describe

    world_x = []
    values = []
    for frame, hp in zip(FRAMES, EXPECTED_HP):
        file = folder / f"raster-frame-{frame:04}.png"
        if not file.is_file():
            raise FileNotFoundError(f"Missing real guest frame {frame}: {file}")
        with Image.open(file) as raw:
            if raw.format != "PNG":
                raise ValueError(f"Guest frame {frame} is not PNG")
            rgb = raw.convert("RGB")
        count, colors, x = describe(rgb)
        if count != 192 or colors < 8:
            raise ValueError(f"Frame {frame}: no genuine source HUD world marker")
        ticks = [rgb.getpixel((px, 18)) for px in (18, 36, 54)]
        expected = [PLAYER_ALIVE if i < hp else PLAYER_EMPTY for i in range(3)]
        if ticks != expected:
            raise ValueError(f"Frame {frame}: player HP differs: {ticks}")
        enemy = [rgb.getpixel((px, 18)) for px in (226, 244)]
        if enemy != [ENEMY_ALIVE, ENEMY_ALIVE]:
            raise ValueError(f"Frame {frame}: enemy HP changed: {enemy}")
        if rgb.getpixel((522, 62)) != RESPAWN_GREEN:
            raise ValueError(f"Frame {frame}: missing native respawn counter marker")
        world_x.append(x)
        values.append({"frame": frame, "player_hp": hp,
                       "world_x_marker": round(x, 2), "colors": colors})
    if abs(world_x[0] - 125.5) > 2:
        raise ValueError("Hero did not naturally respawn at world x=50")
    if world_x[1] - world_x[0] < 12:
        raise ValueError("Real D-pad Right did not move player by frame 90")
    if world_x[2] - world_x[1] < 36:
        raise ValueError("Sustained Right input failed to continue player movement")
    if abs(world_x[3] - world_x[2]) > 8:
        raise ValueError("Hero kept moving after the real D-pad release")
    log = (folder / "raster-runner.log").read_text()
    for frame in FRAMES:
        if f"HEMAN_GUEST_FRAME_PNG frame={frame} " not in log:
            raise ValueError(f"Missing genuine guest frame capture log {frame}")
    for frame, action in ((80, "buttons=DRIGHT"), (145, "buttons=")):
        if f"HEMAN_RESPAWN_HID frame={frame} {action}" not in log:
            raise ValueError(f"Missing genuine NeXium HID event {frame} {action}")
    return {"frames": values, "respawn_marker_present": True,
            "real_hid_right_after_respawn": True,
            "right_release_stops_movement": True}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("folder", type=Path)
    args = p.parse_args()
    print(json.dumps(verify(args.folder), indent=2, sort_keys=True))
    print("PASS: genuine NeXium guest Right input and release after native respawn")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
