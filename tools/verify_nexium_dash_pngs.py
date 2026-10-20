"""Validate genuine guest ZR dash frames and ability HUD, fail-closed."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from instrument_nexium_dash import FRAMES, HID_EVENTS

# Guest capture is RGBA byte-order little endian, e.g. 0xff6ee0d8.
READY = (216, 224, 110)
ACTIVE = (85, 170, 255)
COOLING = (120, 101, 86)
STAGE_ONE = (103, 73, 53)
STAGE_TWO = (191, 230, 241)


def verify(folder: Path) -> dict:
    from PIL import Image
    from verify_nexium_guest_pngs import describe

    logs = set((folder / "raster-runner.log").read_text().splitlines())
    for frame, event in HID_EVENTS:
        if f"HEMAN_DASH_HID frame={frame} {event}" not in logs:
            raise ValueError(f"Missing real ZR/Right HID event at frame {frame}")
    xs = {}
    stages = {}
    gauges = {}
    hashes = {}
    for frame in FRAMES:
        prefix = f"HEMAN_GUEST_FRAME_PNG frame={frame} dimensions=640x360 path="
        if not any(line.startswith(prefix) for line in logs):
            raise ValueError(f"Missing authentic NeXium frame {frame}")
        filename = folder / f"raster-frame-{frame:04}.png"
        if not filename.is_file():
            raise FileNotFoundError(filename)
        with Image.open(filename) as opened:
            if opened.format != "PNG":
                raise ValueError(f"Guest frame {frame} is not PNG")
            rgb = opened.convert("RGB")
        if rgb.size != (640, 360):
            raise ValueError(f"Guest frame {frame} wrong framebuffer size")
        marker_count, diversity, world_x = describe(rgb)
        if marker_count != 192 or diversity < 8:
            raise ValueError(f"Guest frame {frame} lacks native player X marker")
        stages[frame] = 1 if rgb.getpixel((404, 9)) == STAGE_ONE else 2
        if rgb.getpixel((408, 9)) != STAGE_TWO:
            raise ValueError(f"Guest frame {frame} lost source-only stage indicator")
        xs[frame] = round(world_x, 2)
        if frame != 75:
            gauges[frame] = rgb.getpixel((437, 16))
            if gauges[frame] not in (READY, ACTIVE, COOLING):
                raise ValueError(f"Guest frame {frame} lacks native dash HUD")
        hashes[frame] = hashlib.sha256(rgb.tobytes()).hexdigest()

    if [stages[f] for f in FRAMES] != [1, 2, 2, 2, 2, 2, 2]:
        raise ValueError("Stage 1 CLEAR -> A -> room 2 not observed")
    expected = {
        105: READY, 115: READY, 125: ACTIVE,
        140: COOLING, 180: COOLING, 240: READY,
    }
    if any(gauges.get(frame) != color for frame, color in expected.items()):
        raise ValueError("Guest ZR dash ready/active/recharge HUD sequence incorrect")
    if xs[125] - xs[115] <= xs[115] - xs[105] + 16:
        raise ValueError("No independently measured speed burst after ZR")
    if xs[140] <= xs[125] or xs[180] <= xs[140]:
        raise ValueError("Room 2 movement did not continue after dash")
    if abs(xs[240] - xs[180]) > 6:
        raise ValueError("Second-room Right release did not stop player")
    return {
        "frames": list(FRAMES),
        "stage_ids": [stages[f] for f in FRAMES],
        "hid_events": [list(x) for x in HID_EVENTS],
        "guest_world_x": [xs[f] for f in FRAMES],
        "dash_hud": {
            str(f): "active" if gauges[f] == ACTIVE else
                    "cooling" if gauges[f] == COOLING else "ready"
            for f in FRAMES if f != 75
        },
        "dash_real_guest_confirmed": True,
        "commercial_ios_fidelity_verified": False,
        "frame_sha256": {str(f): hashes[f] for f in FRAMES},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.directory), sort_keys=True, indent=2))
    print("PASS: genuine guest ZR increased room-2 movement with HUD recharge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
