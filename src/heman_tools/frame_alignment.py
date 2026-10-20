"""Bounded single-frame, *hypothetical* coordinate calibration from private anchors.

Does not read original IPA/images, infer shape ownership or modify game physics.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


MAX_ANCHORS = 128
MAX_JSON = 256_000


def _pair(value: object, label: str) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{label} must have exactly two coordinates")
    if any(isinstance(x, bool) or not isinstance(x, (float, int)) for x in value):
        raise ValueError(f"{label} must have numeric coordinates")
    x, y = map(float, value)
    if not all(math.isfinite(v) and abs(v) <= 1e8 for v in (x, y)):
        raise ValueError(f"{label} must contain bounded finite coordinates")
    return x, y


def _line_fit(xs: list[float], ys: list[float]) -> tuple[float, float]:
    n = len(xs)
    mx = math.fsum(xs) / n
    my = math.fsum(ys) / n
    cx = [x - mx for x in xs]
    cy = [y - my for y in ys]
    spread = math.fsum(v * v for v in cx)
    if max(xs) - min(xs) < 1e-3 or spread < 1e-8:
        raise ValueError("insufficient distinct level anchor coordinates")
    scale = math.fsum(a * b for a, b in zip(cx, cy)) / spread
    offset = my - scale * mx
    if (not math.isfinite(scale) or not math.isfinite(offset)
            or abs(scale) < 1e-9 or abs(scale) > 1e6):
        raise ValueError("implausible axis scale or offset")
    return scale, offset


def fit_single_frame(data: dict, *, max_residual_px: float = 2.0) -> dict:
    """Fit x'=sx*x+tx, y'=sy*y+ty from 4+ distinct, same-frame anchors.

    This axis-aligned hypothesis is intentionally rejected for rotation,
    shear, camera motion, mismatched anchors and high residuals.
    """
    if (isinstance(max_residual_px, bool)
            or not isinstance(max_residual_px, (int, float))
            or not math.isfinite(max_residual_px) or not 0 < max_residual_px <= 100):
        raise ValueError("max_residual_px must be finite, positive, at most 100")
    if not isinstance(data, dict):
        raise ValueError("expected an anchor JSON object")
    frame = data.get("frame_id")
    if (not isinstance(frame, str) or not 1 <= len(frame) <= 128
            or not frame.isprintable()):
        raise ValueError("frame_id must identify one captured frame")
    anchors = data.get("anchors")
    if not isinstance(anchors, list) or not 4 <= len(anchors) <= MAX_ANCHORS:
        raise ValueError("expected between 4 and 128 explicit anchors")
    names = set()
    level_points = []
    pixels = []
    for entry in anchors:
        if not isinstance(entry, dict):
            raise ValueError("anchor must be an object")
        ident = entry.get("id")
        if (not isinstance(ident, str) or not 1 <= len(ident) <= 128
                or not ident.isprintable() or ident in names):
            raise ValueError("anchor id must be a unique printable string")
        if entry.get("frame_id", frame) != frame:
            raise ValueError("anchor from a different screenshot frame")
        names.add(ident)
        level_points.append(_pair(entry.get("level_xy"), "level_xy"))
        pixels.append(_pair(entry.get("screen_xy"), "screen_xy"))
    sx, tx = _line_fit([p[0] for p in level_points], [p[0] for p in pixels])
    sy, ty = _line_fit([p[1] for p in level_points], [p[1] for p in pixels])
    errors = [math.hypot(sx * x + tx - u, sy * y + ty - v)
              for (x, y), (u, v) in zip(level_points, pixels)]
    worst = max(errors)
    rms = math.sqrt(math.fsum(e * e for e in errors) / len(errors))
    if not math.isfinite(worst) or worst > max_residual_px or rms > max_residual_px:
        raise ValueError("anchor residual exceeds tolerance; frame mapping unverified")
    return {
        "frame_id": frame,
        "model": "uncalibrated_axis_aligned_single_frame",
        "level_to_screen_scale": [sx, sy],
        "level_to_screen_offset_px": [tx, ty],
        "anchor_count": len(anchors),
        "rms_residual_px": rms,
        "max_residual_px": worst,
        "tolerance_px": float(max_residual_px),
        "physical_units_verified": False,
        "source_shape_ownership_verified": False,
        "valid_across_frames": False,
        "interpretation": (
            "Private single-frame math fit only; neither actual iOS camera rules "
            "nor gameplay collision, hitboxes or authentic physics are proven."
        ),
    }


def _private_path(path: Path) -> Path:
    root = Path.cwd() / "local_reports"
    if root.is_symlink():
        raise ValueError("local_reports must not be a symbolic link")
    resolved = root.resolve()
    target = path.resolve()
    if target == resolved or not target.is_relative_to(resolved) or target.suffix != ".json":
        raise ValueError("JSON input and output must be under local_reports/")
    return target


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--anchors", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-residual-px", type=float, default=2.0)
    args = parser.parse_args(argv)
    source = _private_path(args.anchors)
    destination = _private_path(args.out)
    if destination == source:
        raise ValueError("input and output cannot be the same file")
    if source.stat().st_size > MAX_JSON:
        raise ValueError("private anchor JSON exceeds size bound")
    data = json.loads(source.read_text(encoding="utf-8"))
    report = fit_single_frame(data, max_residual_px=args.max_residual_px)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print("Evaluated single-frame hypothetical alignment; private report saved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
