"""Fail-closed checks for synthetic sprite-clock guest frames captured by NeXium."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from PIL import Image

FRAME_INDICES = (6, 12, 18, 30, 36, 120, 300)
WIDTH, HEIGHT = 640, 360

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

    # The synthetic NRO's center swatch must traverse frame 1 -> frame 2 ->
    # frame 0 at the known scheduler boundaries, then hold frame 2 after finish.
    center = {index: pixel[index][320, 180] for index in FRAME_INDICES}
    if center[6] == center[12]:
        raise ValueError("Frame 6 to 12 did not change the synthetic frame swatch")
    if center[12] == center[18]:
        raise ValueError("Frame 12 to 18 did not wrap to the first synthetic frame")
    if center[18] == center[30]:
        raise ValueError("Frame 18 to 30 did not advance back to the third frame")
    for index in (36, 120, 300):
        if center[index] != center[30]:
            raise ValueError(f"Finished animation did not hold frame 2 at guest frame {index}")

    # At frame 18 elapsed time has just wrapped to zero; by frame 12 the
    # elapsed bar is filled partway. At frame 30 it is not yet full; frame
    # 36 has passed the strict finish edge and clamps the progress bar to full.
    progress_left = {index: pixel[index][140, 292] for index in FRAME_INDICES}
    progress_far = {index: pixel[index][450, 292] for index in FRAME_INDICES}
    if progress_left[12] == progress_left[18]:
        raise ValueError("Progress bar did not reset at the finite replay boundary")
    if progress_far[30] == progress_far[36]:
        raise ValueError("Progress bar did not reach full width at animation finish")
    if not (progress_far[36] == progress_far[120] == progress_far[300]):
        raise ValueError("Progress bar changed after the animation had finished")

    # A white strip is rendered only when the native strict-end predicate
    # reports finished. Sample away from the other HUD elements.
    finish_strip = {index: pixel[index][100, 352] for index in FRAME_INDICES}
    if finish_strip[18] == finish_strip[36]:
        raise ValueError("Native finished-state strip did not appear after the strict end edge")
    if not (finish_strip[36] == finish_strip[120] == finish_strip[300]):
        raise ValueError("Finished-state strip was not stable in later guest frames")

    # The per-callback update bar is one quantum wide at frame 30, two at
    # frame 120 for the synthetic 16/17/17-ms pattern.
    update_one = pixel[30][100, 80]
    update_two_edge_30 = pixel[30][190, 80]
    update_two_edge_120 = pixel[120][190, 80]
    if update_one == update_two_edge_30:
        raise ValueError("Frame 30 update bar unexpectedly shows two catch-up updates")
    if update_one != update_two_edge_120:
        raise ValueError("Frame 120 update bar did not show two catch-up updates")

    result = {
        "captured_frames": list(FRAME_INDICES),
        "dimensions": [WIDTH, HEIGHT],
        "center_swatch_transitions": {
            "frame_6": list(center[6]),
            "frame_12": list(center[12]),
            "frame_18": list(center[18]),
            "frame_30": list(center[30]),
            "finished_frames_hold": [36, 120, 300],
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
