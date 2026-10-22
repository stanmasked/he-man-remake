"""Fail-closed checks for synthetic sprite-clock guest frames captured by NeXium."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

FRAME_INDICES = (6, 12, 18, 30, 36, 120, 300)
WIDTH, HEIGHT = 640, 360

# Exact RGB values sampled from a successful real NeXium guest-frame artifact.
# libnx's packed uint32 framebuffer values appear byte-reversed in the PNG's
# RGB channel order, so these are intentionally the observed PNG values.
EXPECTED_CENTER_RGB = {
    6: (209, 185, 71),    # synthetic frame 1
    12: (91, 196, 122),   # synthetic frame 2
    18: (72, 91, 216),    # replay wraps to synthetic frame 0
    30: (91, 196, 122),   # synthetic frame 2
    36: (91, 196, 122),
    120: (91, 196, 122),
    300: (91, 196, 122),
}
SCREEN_BACKGROUND_RGB = (55, 35, 24)
BAR_BACKGROUND_RGB = (93, 70, 57)
BAR_FILL_RGB = (102, 209, 255)
FINISHED_STRIP_RGB = (240, 240, 240)


def load_frame(folder: Path, index: int) -> Image.Image:
    path = folder / f"raster-frame-{index:04}.png"
    if not path.is_file():
        raise FileNotFoundError(f"NeXium did not capture guest frame {index}: {path}")
    with Image.open(path) as source:
        if source.format != "PNG":
            raise ValueError(f"Guest frame {index} is not PNG")
        image = source.convert("RGB")
    if image.size != (WIDTH, HEIGHT):
        raise ValueError(f"Unexpected frame {index} dimensions: {image.size}")
    return image


def verify(folder: Path) -> dict:
    frames = {index: load_frame(folder, index) for index in FRAME_INDICES}
    pixel = {index: frames[index].load() for index in FRAME_INDICES}

    # Check exact state colors, not merely that neighboring frames differ.
    center = {index: pixel[index][320, 180] for index in FRAME_INDICES}
    for index, expected in EXPECTED_CENTER_RGB.items():
        if center[index] != expected:
            raise ValueError(
                f"Unexpected synthetic swatch at frame {index}: "
                f"got {center[index]}, expected {expected}"
            )

    # At frame 18 elapsed time has wrapped to zero; at frame 30 the progress
    # bar is partial; frame 36 crosses the strict finish edge and fills it.
    progress_left = {index: pixel[index][140, 292] for index in FRAME_INDICES}
    progress_far = {index: pixel[index][450, 292] for index in FRAME_INDICES}
    if progress_left[12] != BAR_FILL_RGB:
        raise ValueError("Progress bar is not filled at the frame-12 checkpoint")
    if progress_left[18] != BAR_BACKGROUND_RGB:
        raise ValueError("Progress bar did not reset at the finite replay boundary")
    if progress_far[30] != BAR_BACKGROUND_RGB:
        raise ValueError("Progress bar should still be partial at guest frame 30")
    for index in (36, 120, 300):
        if progress_far[index] != BAR_FILL_RGB:
            raise ValueError(
                f"Progress bar is not full and stable at guest frame {index}"
            )

    # The screen background persists until the native strict-end predicate
    # emits the finished-state strip.
    finish_strip = {index: pixel[index][100, 352] for index in FRAME_INDICES}
    if finish_strip[18] != SCREEN_BACKGROUND_RGB:
        raise ValueError("Finished-state strip appeared before the strict end edge")
    for index in (36, 120, 300):
        if finish_strip[index] != FINISHED_STRIP_RGB:
            raise ValueError(
                f"Finished-state strip is absent or unstable at guest frame {index}"
            )

    # The callback HUD shows one 80-pixel update quantum at frame 30 and two
    # at frame 120. Verify exact fill/background colors at both edges.
    update_one = pixel[30][100, 80]
    update_two_edge_30 = pixel[30][190, 80]
    update_one_edge_120 = pixel[120][100, 80]
    update_two_edge_120 = pixel[120][190, 80]
    if update_one != BAR_FILL_RGB or update_one_edge_120 != BAR_FILL_RGB:
        raise ValueError("First update-bar quantum has an unexpected pixel color")
    if update_two_edge_30 != BAR_BACKGROUND_RGB:
        raise ValueError("Frame 30 update bar unexpectedly shows two catch-up updates")
    if update_two_edge_120 != BAR_FILL_RGB:
        raise ValueError("Frame 120 update bar did not show two catch-up updates")

    result = {
        "captured_frames": list(FRAME_INDICES),
        "dimensions": [WIDTH, HEIGHT],
        "center_swatch_rgb": {
            str(index): list(center[index]) for index in FRAME_INDICES
        },
        "progress_bar_reset_at_frame_18": True,
        "progress_bar_full_by_frame_36": True,
        "finished_strip_stable_after_frame_36": True,
        "two_update_catchup_visible_at_frame_120": True,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    result = verify(args.folder)
    print(json.dumps(result, indent=2, sort_keys=True))
    print("PASS: NeXium guest pixels match the synthetic sprite-clock timeline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
