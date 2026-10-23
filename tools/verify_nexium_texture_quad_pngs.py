"""Validate genuine NeXium guest PNGs from the Stage209 texture probe.

The probe draws only a newly-authored 8x4 RGBA test texture through the
portable C99 CPU reference. These checks do not claim GPU texture sampling.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

FRAME_INDICES = (30, 120, 300)
WIDTH, HEIGHT = 640, 360
QUAD_LEFT, QUAD_TOP = 128, 64
CELL_WIDTH, CELL_HEIGHT = 32, 32
COLORS = (
    (255, 0, 255),    # magenta
    (0, 255, 0),      # green
    (0, 255, 255),    # cyan
    (255, 128, 0),    # orange
)
BACKGROUND = (17, 19, 23)


def check_frame(path: Path, frame_index: int) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"Missing genuine guest frame {frame_index}: {path}")
    with Image.open(path) as source:
        if source.format != "PNG":
            raise ValueError(f"Guest frame {frame_index} is not PNG")
        image = source.convert("RGB")
    if image.size != (WIDTH, HEIGHT):
        raise ValueError(
            f"Unexpected guest frame {frame_index} dimensions: {image.size}"
        )

    checked = 0
    for y in range(4):
        for x in range(8):
            sample_x = QUAD_LEFT + x * CELL_WIDTH + CELL_WIDTH // 2
            sample_y = QUAD_TOP + y * CELL_HEIGHT + CELL_HEIGHT // 2
            expected = COLORS[(x & 1) | ((y & 1) << 1)]
            actual = image.getpixel((sample_x, sample_y))
            if actual != expected:
                raise ValueError(
                    f"Frame {frame_index} sample ({sample_x},{sample_y}) "
                    f"expected {expected}, got {actual}"
                )
            checked += 1

    for x, y in ((10, 10), (QUAD_LEFT + 272, QUAD_TOP + 144), (639, 359)):
        actual = image.getpixel((x, y))
        if actual != BACKGROUND:
            raise ValueError(
                f"Frame {frame_index} background ({x},{y}) "
                f"expected {BACKGROUND}, got {actual}"
            )

    return {"frame": frame_index, "dimensions": [WIDTH, HEIGHT],
            "checker_samples": checked, "background_samples": 3}


def check_frames(folder: Path) -> dict:
    details = [
        check_frame(folder / f"raster-frame-{index:04}.png", index)
        for index in FRAME_INDICES
    ]
    return {
        "frames": details,
        "texture": {"dimensions": [8, 4], "filter": "nearest",
                    "wrap_s": "clamp-to-edge", "wrap_t": "clamp-to-edge"},
        "quad": {"left": QUAD_LEFT, "top": QUAD_TOP,
                 "width": 256, "height": 128},
        "validation": "32 exact checkerboard samples and 3 background samples per guest frame",
        "evidence_boundary": "CPU reference framebuffer path; not GPU texture sampling",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    report = check_frames(args.folder)
    print(json.dumps(report, sort_keys=True, indent=2))
    print("PASS: genuine NeXium guest frames match Stage209 texture-reference pixels")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
