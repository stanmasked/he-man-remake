"""Cross-check unmodified C99 renderer RGB output against NeXium pixel readers.

Reads ONLY "source-frame-XXXX.rgb" from a HOST GCC/Clang C99 simulation.
Deliberately does not produce PNGs, HID attestations, guest-runner logs or
any claim that NeXium has run. This is a source-to-parser contract check.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from instrument_nexium_three_room import FRAMES
from verify_nexium_guest_pngs import describe
from verify_nexium_three_room_pngs import (
    _digit, _overlay, _world_y,
    CLEAR_BORDER, CLEAR_LETTER,
    EXPECTED_CLEAR, EXPECTED_FINISH, EXPECTED_STAGES,
    RETRY_GREEN,
)

WIDTH = 640
HEIGHT = 360
RGB_BYTES = WIDTH * HEIGHT * 3


def read_source_rgb(directory: Path, frame: int):
    from PIL import Image

    name = directory / f"source-frame-{frame:04}.rgb"
    data = name.read_bytes()
    if len(data) != RGB_BYTES:
        raise ValueError(
            f"Host C99 source frame {frame}: expected {RGB_BYTES} RGB bytes, "
            f"received {len(data)}"
        )
    return Image.frombytes("RGB", (WIDTH, HEIGHT), data)


def verify(directory: Path) -> dict:
    observed = sorted(p.name for p in directory.glob("source-frame-*.rgb"))
    wanted = [f"source-frame-{frame:04}.rgb" for frame in FRAMES]
    if observed != wanted:
        raise ValueError("Missing, duplicate or unexpected host-only RGB frames")

    values = {}
    freeze = {}
    for frame in FRAMES:
        img = read_source_rgb(directory, frame)
        marker_count, colors, world_x = describe(img)
        if marker_count != 192 or colors < 8:
            raise ValueError(f"Host framebuffer marker/color diversity invalid at {frame}")
        clear_border = img.getpixel((547, 47)) == CLEAR_BORDER
        clear_letter = img.getpixel((553, 53)) == CLEAR_LETTER
        if clear_border != clear_letter:
            raise ValueError(f"Partial C99-rendered CLEAR at {frame}")
        values[frame] = {
            "stage": _digit(img),
            "clear": clear_border,
            "finish": _overlay(img),
            "world_x": round(world_x, 2),
            "world_y": _world_y(img),
            "respawn": img.getpixel((522, 62)) == RETRY_GREEN,
            "sha256": hashlib.sha256(img.tobytes()).hexdigest(),
        }
        if frame in (1080, 1120):
            freeze[frame] = img.tobytes()

    if tuple(values[f]["stage"] for f in FRAMES) != EXPECTED_STAGES:
        raise ValueError("Host stage badge glyphs disagree with optical parser")
    if {f for f in FRAMES if values[f]["clear"]} != EXPECTED_CLEAR:
        raise ValueError("Host real source CLEAR samples disagree with optical parser")
    if {f for f in FRAMES if values[f]["finish"]} != EXPECTED_FINISH:
        raise ValueError("Host source FINISH/B glyphs disagree with optical parser")
    for frame in FRAMES:
        expected_respawn = 850 <= frame <= 1120
        if values[frame]["respawn"] != expected_respawn:
            raise ValueError(f"Host source respawn indicator wrong at frame {frame}")
    if values[75]["world_x"] - values[105]["world_x"] < 90:
        raise ValueError("Host native first room restart marker absent")
    if values[505]["world_x"] - values[535]["world_x"] < 170:
        raise ValueError("Host native third room spawn reset absent")
    if values[650]["world_x"] - values[535]["world_x"] < 150:
        raise ValueError("Host native third room D-pad movement absent")
    if values[970]["world_y"] > values[945]["world_y"] - 25:
        raise ValueError("Host source renderer cannot depict third room A jump")
    if freeze[1080] != freeze[1120]:
        raise ValueError("Host real RGB source pixels changed after FINISH")
    if abs(values[1190]["world_x"] - values[1170]["world_x"]) > 6:
        raise ValueError("Host source player drift after B")
    if values[1170]["world_x"] > 150 or values[1170]["respawn"]:
        raise ValueError("Host third-room B restart marker absent")
    if values[1120]["sha256"] == values[1170]["sha256"]:
        raise ValueError("B did not change the frozen host framebuffer")

    return {
        "source_only": True,
        "neXium_guest_test_executed": False,
        "authentic_guest_frame_rx_pngs": False,
        "stage_labels": [values[f]["stage"] for f in FRAMES],
        "source_clear_frames": sorted(EXPECTED_CLEAR),
        "source_finish_frames": sorted(EXPECTED_FINISH),
        "native_B_replay_visible_to_python_pixel_parser": True,
        "host_source_rgb_sha256": {
            str(f): values[f]["sha256"] for f in FRAMES
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_rgb_directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.source_rgb_directory), indent=2, sort_keys=True))
    print("PASS: C99 host framebuffer pixels agree with the exact Python guest "
          "optical reader; authentic NeXium guest execution remains untested")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
