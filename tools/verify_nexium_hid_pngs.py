"""Validate actual NeXium guest frames against a timed HID Right press.

A unique magenta HUD marker encodes *player world x*. Moving enemies,
camera movement and graphical animation cannot make this test pass.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from PIL import Image, ImageChops
from verify_nexium_guest_pngs import FRAME_INDICES, describe


def verify(directory: Path) -> dict:
    xs, colors, samples, images = [], [], [], []
    for index in FRAME_INDICES:
        path = directory / f"raster-frame-{index:04}.png"
        if not path.is_file():
            raise FileNotFoundError(f"Guest frame not captured: {path}")
        with Image.open(path) as source:
            if source.format != "PNG":
                raise ValueError(f"Expected guest PNG: {path}")
            image = source.convert("RGB")
            count, diversity, cx = describe(image)
            images.append(image)
            samples.append(count)
            colors.append(diversity)
            xs.append(cx)

    # The pinned debug runner writes "buttons=DRIGHT" at frame 45,
    # "buttons=" at frame 105. Frames 30,120,300 surround the press.
    baseline, post_right, after_release = xs
    right_delta = post_right - baseline
    released_drift = abs(after_release - post_right)
    if not 30.0 <= right_delta <= 340.0:
        raise ValueError(
            f"Controller Right did not move guest player x: delta={right_delta:.2f}"
        )
    if released_drift > 6.0:
        raise ValueError(
            f"Player world x changed after Right was released: {released_drift:.2f}"
        )
    # The track itself only shifts on actual player world-x changes.
    # Require pixel evidence in the fixed 640x360 renderer's HUD strip.
    hud_diff = ImageChops.difference(images[0], images[1])
    changed = sum(1 for row in range(44, 68)
                  for x in range(10, 467)
                  if max(hud_diff.getpixel((x, row))) >= 30)
    if changed < 150:
        raise ValueError(f"Player coordinate HUD did not visibly move: {changed} pixels")
    log = (directory / "raster-runner.log").read_text()
    for marker in (
        "HEMAN_HID_SCHEDULE frame=45 buttons=DRIGHT",
        "HEMAN_HID_SCHEDULE frame=105 buttons=buttons=",
    ):
        if marker not in log:
            raise ValueError(f"Missing observed guest HID schedule event: {marker}")
    return {
        "frames": list(FRAME_INDICES),
        "world_x_centroids": [round(x, 2) for x in xs],
        "right_delta_px": round(right_delta, 2),
        "released_drift_px": round(released_drift, 2),
        "hud_changed_pixels": changed,
        "marker_pixel_counts": samples,
        "sample_colors": colors,
        "input_start_frame": 45,
        "input_release_frame": 105,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    result = verify(args.folder)
    print(json.dumps(result, indent=2, sort_keys=True))
    print("PASS: actual NeXium HID Right input moved the guest player and stayed released")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
