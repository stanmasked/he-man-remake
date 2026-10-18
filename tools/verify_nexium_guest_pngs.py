"""Fail-closed validation for PNGs exported from NeXium's guest frame_rx.

Validates 640x360 real guest framebuffer content using a unique synthetic
magenta world-x HUD marker, rather than relying on a changing emulator splash.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageChops


FRAME_INDICES = (30, 120, 300)
WIDTH, HEIGHT = 640, 360


def describe(image: Image.Image) -> tuple[int, int, float]:
    rgb = image.convert("RGB")
    if rgb.size != (WIDTH, HEIGHT):
        raise ValueError(f"Unexpected guest frame dimensions: {rgb.size}")
    # Our own C renderer draws a *unique solid-magenta marker* at
    # world_x->HUD x. No external NeXium UI is in the guest frame_rx.
    pixel = rgb.load()
    magenta = []
    for y in range(44, 68):
        for x in range(10, 467):
            r, g, b = pixel[x, y]
            if r >= 210 and g <= 55 and b >= 210:
                magenta.append(x)
    if len(magenta) < 100:
        raise ValueError(
            f"Missing original synthetic player-world-x marker: {len(magenta)} pixels"
        )
    colors = len(set(rgb.resize((128, 72)).getdata()))
    if colors < 8:
        raise ValueError(f"Guest frame lacks world color diversity: {colors}")
    return len(magenta), colors, sum(magenta) / len(magenta)


def check_frames(folder: Path) -> dict:
    imgs = []
    details = []
    for i in FRAME_INDICES:
        path = folder / f"raster-frame-{i:04}.png"
        if not path.is_file():
            raise FileNotFoundError(f"NeXium did not export guest frame {i}: {path}")
        with Image.open(path) as img:
            if img.format != "PNG":
                raise ValueError(f"NeXium frame {i} is not PNG")
            rgb = img.convert("RGB")
            details.append(describe(rgb))
            imgs.append(rgb)
    xs = [x[2] for x in details]
    if max(xs)-min(xs) > 4:
        raise ValueError(
            f"Player x unexpectedly changed without controller input: {xs}"
        )
    moved_pixels = 0
    diff = ImageChops.difference(imgs[0], imgs[2])
    # Count an RGB pixel only if one channel changed by >=20.
    for delta in diff.getdata():
        if max(delta) >= 20:
            moved_pixels += 1
    if moved_pixels < 90:
        raise ValueError(
            f"Guest frames did not evolve across 270 frames: {moved_pixels} changed"
        )
    result = {
        "frames": list(FRAME_INDICES),
        "dimensions": [WIDTH, HEIGHT],
        "magenta_pixels": [x[0] for x in details],
        "sample_colors": [x[1] for x in details],
        "world_x_marker_center": [round(x, 2) for x in xs],
        "world_animation_changed_pixels": moved_pixels,
    }
    return result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("folder", type=Path)
    args = p.parse_args()
    import json
    outcome = check_frames(args.folder)
    print(json.dumps(outcome, sort_keys=True, indent=2))
    print("PASS: NeXium delivered synthetic He-Man guest pixels, including player HUD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
