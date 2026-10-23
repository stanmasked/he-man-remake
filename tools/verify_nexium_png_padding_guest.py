"""Stage225: verify *actual* NeXium guest PNG pixels of synthetic padded textures.

Not an original game capture. The source is Stage224's synthetic RGB CPU
texture upload drawn via libnx software framebuffer, not deko3d GPU sampling.
Three separate runner frame captures are required; runner progress is
validated independently by the workflow. No file is silently synthesized.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

from verify_nexium_texture_quad_pngs import check_frames as check_base_frames

FRAMES = (30, 120, 300)
PANEL_LEFT, PANEL_TOP, CELL = 16, 16, 16
EXPECTED_ROWS = (
    ((255, 0, 0), (0, 255, 0), (0, 0, 255), (0, 0, 0)),
    ((255, 128, 0), (128, 0, 255), (0, 255, 255), (0, 0, 0)),
    ((0, 0, 0),) * 4,
    ((0, 0, 0),) * 4,
)


def check_padding_frame(path: Path, frame: int) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"Missing captured NeXium guest frame {frame}: {path}")
    with Image.open(path) as source:
        if source.format != "PNG":
            raise ValueError(f"Guest frame {frame} must be PNG")
        pixels = source.convert("RGB")
    if pixels.size != (640, 360):
        raise ValueError(f"Guest frame {frame} unexpected size {pixels.size}")
    verified = 0
    for y, row in enumerate(EXPECTED_ROWS):
        for x, expected in enumerate(row):
            point = (PANEL_LEFT + x * CELL + CELL // 2,
                     PANEL_TOP + y * CELL + CELL // 2)
            actual = pixels.getpixel(point)
            if actual != expected:
                raise ValueError(
                    f"Guest frame {frame} padded PNG sample at {point}: "
                    f"expected {expected}, got {actual}"
                )
            verified += 1
    return {
        "frame": frame,
        "panel_sample_count": verified,
        "native_zero_padding_rgb_black_verified": True,
        "original_source_pixels_examined": False,
        "hardware_gpu_texture_upload_verified": False,
    }


def check_padding_frames(directory: Path) -> dict:
    base = check_base_frames(directory)
    frames = [
        check_padding_frame(directory / f"raster-frame-{index:04}.png", index)
        for index in FRAMES
    ]
    return {
        "classification": "stage225_actual_guest_software_framebuffer_png_checks",
        "guest_frame_count": len(frames),
        "guest_frames": frames,
        "previous_stage209_checker_verified": True,
        "stage224_padded_rgb_opaque_black_verified": True,
        "verified_samples_per_frame": 16,
        "native_gpu_texture_submission_verified": False,
        "original_ios_runtime_pixel_parity_verified": False,
        "source_game_assets_used": False,
        "previous_reference": base["validation"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    report = check_padding_frames(args.directory)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
