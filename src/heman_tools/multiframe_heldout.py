"""Private numerical gate: independent held-out landmarks across multiple frames.

A successful fit does not establish iOS landmark identity, camera behavior,
shape ownership or collision physics. No IPA or image is ever read.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from .frame_alignment import _pair, _private_path
from .heldout_alignment import validate_holdout

_MAX_FRAMES = 32
_MAX_JSON = 1_000_000


def _stationary_id_map(entries: list[dict], label: str) -> dict[str, tuple[float, float]]:
    """Canonicalize landmark IDs/positions; fail on duplicate source positions."""
    positions = {}
    for item in entries:
        identifier = item["id"]
        if identifier in positions:
            raise ValueError(f"duplicate {label} landmark ID")
        positions[identifier] = _pair(item["level_xy"], f"{label} level_xy")
    if len(set(positions.values())) != len(positions):
        raise ValueError(f"duplicate {label} source positions cannot establish independent anchors")
    return positions


def validate_multiframe_holdout(
    data: dict, *, max_fit_residual_px: float = 2.0,
    max_holdout_residual_px: float = 2.0,
    max_relative_scale_drift: float = 0.02,
) -> dict:
    """Test held-out landmark predictions independently on 2-32 captures.

    Each capture fits its own training anchors. The same stationary training
    and reserved landmark IDs/local positions must recur in all frames.
    Camera translation is allowed, but zoom/axis flips and bad holdouts fail.
    """
    if not isinstance(data, dict):
        raise ValueError("expected an object with frame observations")
    frames = data.get("frames")
    if not isinstance(frames, list) or not 2 <= len(frames) <= _MAX_FRAMES:
        raise ValueError("expected 2 to 32 frame observations")
    if (isinstance(max_relative_scale_drift, bool) or
            not isinstance(max_relative_scale_drift, (int, float)) or
            not math.isfinite(max_relative_scale_drift) or
            not 0 < max_relative_scale_drift <= 0.2):
        raise ValueError("invalid cross-frame relative scale tolerance")

    frame_ids = set()
    reference_training = None
    reference_heldout = None
    individual = []
    for frame in frames:
        # The single-frame validator enforces within-frame separation,
        # residual bounds, exact IDs and finite/limited input coordinates.
        result = validate_holdout(
            frame, max_fit_residual_px=max_fit_residual_px,
            max_holdout_residual_px=max_holdout_residual_px)
        fid = result["frame_id"]
        if fid in frame_ids:
            raise ValueError("duplicate frame identifier")
        frame_ids.add(fid)
        train = _stationary_id_map(frame["anchors"], "training")
        reserved = _stationary_id_map(frame["holdout_anchors"], "held-out")
        if set(train).intersection(reserved) or set(train.values()).intersection(reserved.values()):
            raise ValueError("training/held-out data overlap")
        if reference_training is None:
            reference_training, reference_heldout = train, reserved
        elif train != reference_training or reserved != reference_heldout:
            raise ValueError("stationary landmark IDs or level coordinates changed between frames")
        individual.append(result)

    original = individual[0]["fitted_scale"]
    drifts = []
    for result in individual:
        scales = result["fitted_scale"]
        relative = [abs((current - base) / base)
                    for current, base in zip(scales, original)]
        if not all(math.isfinite(n) for n in relative):
            raise ValueError("non-finite fitted scale drift")
        if max(relative) > max_relative_scale_drift:
            raise ValueError("cross-frame scale drift exceeds tolerance")
        drifts.append(max(relative))

    return {
        "frame_ids": [x["frame_id"] for x in individual],
        "frame_count": len(individual),
        "training_landmarks_per_frame": len(reference_training),
        "heldout_landmarks_per_frame": len(reference_heldout),
        "reference_scale": original,
        "frame_offsets_px": [x["fitted_offset_px"] for x in individual],
        "frame_training_max_residual_px": [x["training_max_residual_px"] for x in individual],
        "frame_heldout_max_residual_px": [x["heldout_max_residual_px"] for x in individual],
        "max_relative_scale_drift": max(drifts),
        "allowed_relative_scale_drift": float(max_relative_scale_drift),
        "crossframe_heldout_numeric_consistency_passed": True,
        "actual_landmark_identity_verified": False,
        "original_camera_model_verified": False,
        "physical_units_verified": False,
        "collision_geometry_verified": False,
        "interpretation": (
            "Numerical held-out and scale agreement across privately supplied "
            "frames, not proof of authentic game landmarks, camera, or physics."
        ),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--max-fit-residual-px", type=float, default=2.0)
    parser.add_argument("--max-holdout-residual-px", type=float, default=2.0)
    parser.add_argument("--max-relative-scale-drift", type=float, default=0.02)
    args = parser.parse_args(argv)
    inp = _private_path(args.frames)
    out = _private_path(args.out)
    if inp == out:
        raise ValueError("input/output must be distinct private files")
    if inp.stat().st_size > _MAX_JSON:
        raise ValueError("private frame file exceeds size limit")
    report = validate_multiframe_holdout(
        json.loads(inp.read_text(encoding="utf-8")),
        max_fit_residual_px=args.max_fit_residual_px,
        max_holdout_residual_px=args.max_holdout_residual_px,
        max_relative_scale_drift=args.max_relative_scale_drift)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print("Multi-frame withheld numeric checks completed; aggregate report saved privately.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
