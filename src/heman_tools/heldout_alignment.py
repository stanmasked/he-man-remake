"""Validate a single-frame coordinate hypothesis against independently held-out anchors.

Original IPA, screenshot pixels, camera rules and collision semantics are NOT
read or inferred. Data remain local; only aggregated numerical errors export.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from .frame_alignment import MAX_ANCHORS, MAX_JSON, _pair, _private_path, fit_single_frame


def validate_holdout(data: dict, *, max_fit_residual_px: float = 2.0,
                     max_holdout_residual_px: float = 2.0) -> dict:
    """Fit using training anchors ONLY, then test different held-out landmarks.

    This catches coincidental/overfit training data while preserving the prior
    axis-aligned single-frame model; it never proves original-game mapping.
    """
    if not isinstance(data, dict):
        raise ValueError("expected one private anchor report object")
    if (isinstance(max_holdout_residual_px, bool) or
            not isinstance(max_holdout_residual_px, (float, int)) or
            not math.isfinite(max_holdout_residual_px) or
            not 0 < max_holdout_residual_px <= 100):
        raise ValueError("invalid held-out residual tolerance")
    fit = fit_single_frame(data, max_residual_px=max_fit_residual_px)
    trained = data["anchors"]
    heldout = data.get("holdout_anchors")
    if not isinstance(heldout, list) or not 2 <= len(heldout) <= 32:
        raise ValueError("expected 2 to 32 independent held-out anchors")
    if len(trained) + len(heldout) > MAX_ANCHORS:
        raise ValueError("combined anchor count exceeds safety bound")
    frame = fit["frame_id"]
    names = {anchor["id"] for anchor in trained}
    training_points = {_pair(anchor["level_xy"], "training level_xy")
                       for anchor in trained}
    heldout_points = set()
    errors = []
    scale_x, scale_y = fit["level_to_screen_scale"]
    offset_x, offset_y = fit["level_to_screen_offset_px"]
    for anchor in heldout:
        if not isinstance(anchor, dict):
            raise ValueError("held-out anchor must be an object")
        identifier = anchor.get("id")
        if (not isinstance(identifier, str) or not 1 <= len(identifier) <= 128
                or not identifier.isprintable() or identifier in names):
            raise ValueError("held-out ID must be unique and disjoint from training")
        if anchor.get("frame_id", frame) != frame:
            raise ValueError("held-out anchor belongs to a different frame")
        names.add(identifier)
        level = _pair(anchor.get("level_xy"), "held-out level_xy")
        screen = _pair(anchor.get("screen_xy"), "held-out screen_xy")
        if level in training_points or level in heldout_points:
            raise ValueError("held-out location repeats a training/validation point")
        heldout_points.add(level)
        expected_x = scale_x * level[0] + offset_x
        expected_y = scale_y * level[1] + offset_y
        error = math.hypot(expected_x - screen[0], expected_y - screen[1])
        if not math.isfinite(error):
            raise ValueError("held-out projection overflow")
        errors.append(error)
    worst = max(errors)
    rms = math.sqrt(math.fsum(e*e for e in errors)/len(errors))
    if worst > max_holdout_residual_px:
        raise ValueError("held-out residual exceeds tolerance: mapping unverified")
    return {
        "frame_id": frame,
        "model": fit["model"],
        "training_anchor_count": fit["anchor_count"],
        "heldout_anchor_count": len(errors),
        "fitted_scale": fit["level_to_screen_scale"],
        "fitted_offset_px": fit["level_to_screen_offset_px"],
        "training_max_residual_px": fit["max_residual_px"],
        "heldout_max_residual_px": worst,
        "heldout_rms_residual_px": rms,
        "heldout_tolerance_px": float(max_holdout_residual_px),
        "heldout_numeric_consistency_passed": True,
        "landmark_identity_verified": False,
        "original_camera_model_verified": False,
        "actual_collision_geometry_verified": False,
        "interpretation": (
            "Withheld numerical check on one frame, not proof of source-game "
            "landmark identity, camera calibration, scale or original physics."
        ),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--anchors", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--max-fit-residual-px", default=2.0, type=float)
    parser.add_argument("--max-holdout-residual-px", default=2.0, type=float)
    args = parser.parse_args(argv)
    source = _private_path(args.anchors)
    target = _private_path(args.out)
    if source == target:
        raise ValueError("input and output cannot be the same private file")
    if source.stat().st_size > MAX_JSON:
        raise ValueError("anchor input exceeds size bound")
    report = validate_holdout(
        json.loads(source.read_text(encoding="utf-8")),
        max_fit_residual_px=args.max_fit_residual_px,
        max_holdout_residual_px=args.max_holdout_residual_px,
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False)+"\n",
                      encoding="utf-8")
    print("Held-out coordinate consistency checked; numerical report saved privately.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
