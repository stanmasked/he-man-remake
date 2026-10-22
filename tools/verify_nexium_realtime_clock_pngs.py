"""Fail-closed OCR verification for the real-time clock guest's PASS screen."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageOps

FRAME_INDICES = (30, 120, 300)
LATE_FRAMES = (120, 300)
SUPPORTED_SIZES = {(640, 360), (1280, 720)}
REQUIRED_TOKENS = ("STARTUP", "COUNTER", "RESUME", "PASS")


def normalize(text: str) -> str:
    return re.sub(r"[^A-Z0-9]+", " ", text.upper()).strip()


def has_pass_marker(text: str) -> bool:
    tokens = set(normalize(text).split())
    return all(token in tokens for token in REQUIRED_TOKENS) and "FAIL" not in tokens


def read_and_ocr(path: Path, scratch: Path, index: int) -> tuple[Image.Image, str]:
    if not path.is_file():
        raise FileNotFoundError(f"NeXium did not capture guest frame {index}: {path}")
    with Image.open(path) as source:
        if source.format != "PNG":
            raise ValueError(f"Guest frame {index} is not PNG")
        image = source.convert("RGB")
    if image.size not in SUPPORTED_SIZES:
        raise ValueError(
            f"Unexpected guest frame {index} dimensions: {image.size}; "
            f"expected one of {sorted(SUPPORTED_SIZES)}"
        )

    # libnx console output may be captured at 640x360 or native 1280x720.
    # Crop the same upper 250/360 of the screen and normalize to 2560x1000.
    crop_height = image.height * 250 // 360
    crop = image.crop((0, 0, image.width, crop_height)).convert("L")
    # Tesseract is more reliable with dark glyphs on a light background.
    crop = ImageOps.invert(ImageOps.autocontrast(crop))
    crop = crop.resize((2560, 1000), Image.Resampling.NEAREST)
    enlarged = scratch / f"clock-frame-{index:04}-ocr.png"
    crop.save(enlarged)
    result = subprocess.run(
        ["tesseract", str(enlarged), "stdout", "--psm", "6", "-l", "eng"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Tesseract failed for frame {index}: {result.stderr.strip()}"
        )
    return image, result.stdout


def verify(folder: Path) -> dict:
    captures: dict[int, str] = {}
    details = []
    with tempfile.TemporaryDirectory(prefix="heman-stage183-ocr-") as temp:
        scratch = Path(temp)
        for index in FRAME_INDICES:
            image, text = read_and_ocr(
                folder / f"raster-frame-{index:04}.png", scratch, index
            )
            captures[index] = text
            gray = image.convert("L")
            ink_pixels = sum(1 for value in gray.getdata() if value > 48)
            if ink_pixels < 250:
                raise ValueError(
                    f"Guest frame {index} has too little visible console output: {ink_pixels} ink pixels"
                )
            details.append(
                {
                    "frame": index,
                    "dimensions": list(image.size),
                    "visible_ink_pixels": ink_pixels,
                    "pass_marker_detected": has_pass_marker(text),
                    "ocr_text": text.strip(),
                }
            )

    successful_frames = [
        index for index in LATE_FRAMES if has_pass_marker(captures[index])
    ]
    if not successful_frames:
        rendered = {str(index): normalize(captures[index]) for index in LATE_FRAMES}
        raise ValueError(
            "No late guest frame OCR contains STARTUP, COUNTER, RESUME and PASS "
            f"without FAIL; normalized OCR={rendered}"
        )

    return {
        "captured_frames": list(FRAME_INDICES),
        "dimensions": [WIDTH, HEIGHT],
        "required_tokens": list(REQUIRED_TOKENS),
        "pass_marker_frames": successful_frames,
        "frame_results": details,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    result = verify(args.folder)
    print(json.dumps(result, indent=2, sort_keys=True))
    print(
        "PASS: NeXium guest framebuffer visibly reports the real-counter "
        "pause/resume self-check"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
