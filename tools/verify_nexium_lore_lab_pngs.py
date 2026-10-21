"""Fail-closed optical verification of REAL pinned NeXium lab guest frames.

The source-authored NRO draws 640x360 fixed-color rectangles only.
Read ONLY frame_rx PNG files and their logged absolute paths; do not
paint/construct replacement screenshots or trust mock CI as guest proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from instrument_nexium_lore_lab import FRAMES, HID_EVENTS

# BGRA integer constants stored as little-endian RGBA8 framebuffer bytes,
# from the exact Stage111 source-authored switch_lore/source/main.c.
BG = (39, 28, 18)
GREY = (88, 72, 64)
GREEN = (124, 223, 85)
BIO = (205, 121, 224)
ART = (219, 232, 105)
SAVE = (255, 140, 104)
HERO = (144, 220, 255)

# Expected independent visual milestones (not asserted iOS positions):
# format: (upgrade, opened_gate, bio, art, saved, earned_count, x_min, x_max)
STATES = {
    30:  (0, 0, 0, 0, 0, 0, 15, 33),
    60:  (0, 0, 0, 1, 0, 1, 36, 86),
    130: (0, 0, 0, 1, 0, 1, 150, 195),
    165: (0, 0, 0, 1, 1, 1, 150, 195),
    215: (0, 0, 0, 0, 1, 0, 15, 38),
    265: (0, 0, 0, 1, 1, 1, 150, 195),
    305: (1, 0, 0, 1, 1, 1, 150, 195),
    345: (1, 0, 0, 1, 1, 1, 95, 118),
    395: (1, 1, 0, 1, 1, 1, 95, 112),
    445: (1, 1, 1, 1, 1, 2, 140, 192),
    485: (1, 1, 1, 1, 1, 2, 140, 192),
    530: (1, 1, 1, 1, 1, 2, 140, 192),
}
LIGHT_POINTS = ((30, 30), (84, 30), (138, 30), (192, 30), (246, 30))
ACTIVE_COLORS = (GREEN, GREEN, BIO, ART, SAVE)
BARS = ((360, 30), (372, 30))


def inspect(rgb) -> dict:
    if rgb.size != (640, 360):
        raise ValueError("Real guest framebuffer is not 640x360")
    if rgb.getpixel((600, 20)) != BG:
        raise ValueError("Guest PNG lacks source NRO background color")
    lights = []
    for point, active in zip(LIGHT_POINTS, ACTIVE_COLORS):
        color = rgb.getpixel(point)
        if color == active:
            lights.append(1)
        elif color == GREY:
            lights.append(0)
        else:
            raise ValueError("Guest lore/upgrade/save HUD is malformed")
    progress = [rgb.getpixel(point) for point in BARS]
    if any(color not in (BG, GREEN) for color in progress):
        raise ValueError("Guest lore counter bar has unknown source pixels")
    count = (1 if progress[0] == GREEN else 0) + (
        1 if progress[1] == GREEN else 0
    )
    hero = [x for x in range(64, 590)
            if rgb.getpixel((x, 188)) == HERO]
    if (len(hero) != 10 or hero[-1] - hero[0] != 9):
        raise ValueError("Missing unique 10-pixel native player")
    native_x = hero[0] + 5 - 64
    return {
        "lights": tuple(lights),
        "collected_count": count,
        "native_player_x": native_x,
    }


def verify(folder: Path) -> dict:
    from PIL import Image
    log = (folder / "raster-runner.log").read_text()
    lines = log.splitlines()
    if "Production runner complete" not in log:
        raise ValueError("NeXium genuine production runner did not complete")
    cycles = re.findall(r"cycles=(\d+) svcs=(\d+) frames=(\d+)", log)
    if not cycles or max(int(c[0]) for c in cycles) <= 0 or (
        max(int(c[1]) for c in cycles) <= 0
    ):
        raise ValueError("No authentic guest CPU/SVC execution receipts")
    scheduled = [line for line in lines if line.startswith("HEMAN_LORE_HID frame=")]
    expected = [
        f"HEMAN_LORE_HID frame={frame} {packet}"
        for frame, packet in HID_EVENTS
    ]
    if scheduled != expected:
        raise ValueError("Guest runner HID transcript differs from pinned schedule")

    arrivals = [line for line in lines
                if line.startswith("HEMAN_GUEST_FRAME_PNG frame=")]
    if len(arrivals) != len(FRAMES):
        raise ValueError("Missing, extra or duplicated frame_rx PNG receipt")
    snapshots = {}
    digests = {}
    for line, frame in zip(arrivals, FRAMES):
        prefix = f"HEMAN_GUEST_FRAME_PNG frame={frame} dimensions=640x360 path="
        if not line.startswith(prefix):
            raise ValueError("Unexpected frame_rx or PNG geometry receipt")
        png = folder / f"raster-frame-{frame:04}.png"
        logged_path = Path(line[len(prefix):])
        if (not logged_path.is_absolute() or
                logged_path.resolve() != png.resolve() or not png.is_file()):
            raise ValueError("Real NeXium PNG path does not match runner log")
        with Image.open(png) as file:
            if file.format != "PNG":
                raise ValueError("NeXium guest capture is not a PNG")
            rgb = file.convert("RGB")
            found = inspect(rgb)
            digest = hashlib.sha256(rgb.tobytes()).hexdigest()
        status = STATES[frame]
        if found["lights"] != status[:5]:
            raise ValueError(
                f"Actual guest HUD did not follow expected save/lore route "
                f"at frame {frame}: {found['lights']} != {status[:5]}"
            )
        if found["collected_count"] != status[5]:
            raise ValueError(f"Native two-lore counter mismatched at {frame}")
        if not status[6] <= found["native_player_x"] <= status[7]:
            raise ValueError(
                f"Native in-game player location failed at frame {frame}"
            )
        snapshots[frame] = found
        digests[frame] = digest

    # Save slot remains alive across B reset, and load returns to same
    # earned player progress. Endgame repeats to show no phantom extra
    # rewards; final RAM save followed by RAM load renders same source
    # scene with identical pixels rather than a mock verifier redraw.
    if digests[165] != digests[265]:
        raise ValueError("Guest snapshot restore did not reproduce saved scene")
    if digests[485] != digests[530]:
        raise ValueError("Guest completed lore save/load was not pixel-stable")
    if digests[30] == digests[215]:
        # Save light turns blue after B restart: reset does not destroy RAM.
        raise ValueError("Guest reset incorrectly discarded local RAM save")
    if digests[345] == digests[395] or digests[395] == digests[445]:
        raise ValueError("Native attack/return did not affect guest pixels")
    return {
        "authentic_pinned_nexium_frame_rx_pngs_validated": len(FRAMES),
        "guest_cpu_and_svc_execution_recorded": True,
        "real_native_wall_crusher_attack_and_two_collectibles": True,
        "guest_ram_save_reset_load_pixels_confirmed": True,
        "real_frame_milestones": list(FRAMES),
        "original_ios_source_fidelity_verified": False,
        "hardware_nintendo_switch_execution_verified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("guest_folder", type=Path)
    args = parser.parse_args()
    result = verify(args.guest_folder)
    print(json.dumps(result, sort_keys=True, indent=2))
    print("PASS: genuine pinned NeXium guest lore/saves route and PNG receipt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
