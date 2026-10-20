"""Conservative, read-only comparison of privately observed contact traces.

Inputs may be manually measured or synthetic. Exact provenance is not
authenticated here; no result from this tool proves original iOS gameplay.
Original screenshots, recorded frames and coordinates stay outside GitHub.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path

from .frame_alignment import _private_path

CONTACTS = frozenset(("airborne", "floor", "wall", "ceiling",
                      "one_way", "hazard", "unknown"))
CAPTURE_TYPES = frozenset(("synthetic", "manual_observation"))
MAX_FRAMES = 600
MAX_BYTES = 1_000_000


def _positive_number(value: object, label: str, *, upper: float) -> float:
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or not 0 < value <= upper):
        raise ValueError(f"{label} must be finite, positive and bounded")
    return float(value)


def _xy(value: object, label: str) -> tuple[float, float]:
    if (not isinstance(value, list) or len(value) != 2
            or any(isinstance(v, bool) or not isinstance(v, (int, float))
                   or not math.isfinite(v) or abs(v) > 1_000_000
                   for v in value)):
        raise ValueError(f"{label} must contain two bounded finite numbers")
    return float(value[0]), float(value[1])


def _identity(value: object, label: str) -> str:
    if (not isinstance(value, str) or not 1 <= len(value) <= 128
            or not value.isprintable() or any(ord(c) < 32 for c in value)):
        raise ValueError(f"invalid {label}")
    return value


def _parse_capture(capture: object, platform: str) -> dict:
    if not isinstance(capture, dict) or capture.get("platform") != platform:
        raise ValueError(f"expected a {platform} capture")
    identity = _identity(capture.get("capture_id"), "capture_id")
    anchor = _identity(capture.get("stationary_anchor_id"), "anchor ID")
    method = capture.get("evidence_kind")
    if method not in CAPTURE_TYPES:
        raise ValueError("capture evidence_kind must be explicitly labeled")
    scale = _positive_number(capture.get("pixels_per_unit"),
                             "pixels_per_unit", upper=10_000)
    observations = capture.get("observations")
    if not isinstance(observations, list) or not 8 <= len(observations) <= MAX_FRAMES:
        raise ValueError("expected 8 to 600 sampled frames")
    result = []
    for i, record in enumerate(observations):
        if not isinstance(record, dict):
            raise ValueError("frame must be an object")
        frame = record.get("frame")
        if type(frame) is not int or frame != i:
            raise ValueError("frames must be contiguous, starting at zero")
        control = record.get("control")
        if not isinstance(control, dict):
            raise ValueError("missing recorded controller state")
        direction = control.get("horizontal")
        jump = control.get("jump")
        if type(direction) is not int or direction not in (-1, 0, 1):
            raise ValueError("horizontal input must be -1, 0 or 1")
        if type(jump) is not bool:
            raise ValueError("jump input must be an explicit boolean")
        contact = record.get("contact")
        if contact not in CONTACTS:
            raise ValueError("unsupported contact observation")
        feet = _xy(record.get("feet_screen_xy"), "feet_screen_xy")
        anchor_pos = _xy(record.get("anchor_screen_xy"), "anchor_screen_xy")
        world_relative = tuple(
            (a - b) / scale for a, b in zip(feet, anchor_pos))
        result.append((direction, jump, contact, world_relative))
    return {"id": identity, "anchor": anchor, "evidence": method,
            "scale": scale, "records": result}


def compare_contact_traces(data: dict, *, max_position_error_units: float = 1.0,
                           max_contact_mismatches: int = 0) -> dict:
    """Evaluate 1:1 input/frame/contact agreement under supplied calibration.

    Subtracts a common stationary *screen* anchor within each capture
    before dividing by explicitly supplied pixels/unit. Identity and scale
    remain hypothetical until independently verified.
    """
    if not isinstance(data, dict):
        raise ValueError("trace input must be a JSON object")
    scenario = _identity(data.get("scenario_id"), "scenario_id")
    fps = data.get("fps")
    if type(fps) is not int or not 1 <= fps <= 240:
        raise ValueError("fps must be a positive bounded integer")
    tolerance = _positive_number(max_position_error_units,
                                 "max_position_error_units", upper=1000)
    if (type(max_contact_mismatches) is not int
            or not 0 <= max_contact_mismatches <= MAX_FRAMES):
        raise ValueError("max_contact_mismatches must be a bounded integer")
    ios = _parse_capture(data.get("reference"), "ios")
    switch = _parse_capture(data.get("candidate"), "switch")
    if ios["id"] == switch["id"]:
        raise ValueError("captures must have distinct identifiers")
    if ios["anchor"] != switch["anchor"]:
        raise ValueError("stationary anchor identities differ")
    if len(ios["records"]) != len(switch["records"]):
        raise ValueError("capture frame counts differ")
    errors = []
    contact_mismatches = Counter()
    unknown = 0
    transition_mismatch_count = 0
    last_a = last_b = None
    for (control_a, jump_a, contact_a, xy_a), (
            control_b, jump_b, contact_b, xy_b) in zip(
                ios["records"], switch["records"]):
        if (control_a, jump_a) != (control_b, jump_b):
            raise ValueError("the two captures used different inputs")
        delta = math.hypot(xy_a[0] - xy_b[0], xy_a[1] - xy_b[1])
        if not math.isfinite(delta):
            raise ValueError("coordinate normalization overflow")
        errors.append(delta)
        if contact_a != contact_b:
            contact_mismatches[contact_a + "->" + contact_b] += 1
        if "unknown" in (contact_a, contact_b):
            unknown += 1
        if last_a is not None and ((contact_a != last_a) !=
                                   (contact_b != last_b)):
            transition_mismatch_count += 1
        last_a, last_b = contact_a, contact_b
    mismatch_total = sum(contact_mismatches.values())
    worst = max(errors)
    rms = math.sqrt(math.fsum(e * e for e in errors) / len(errors))
    numeric_pass = (worst <= tolerance
                    and mismatch_total <= max_contact_mismatches
                    and unknown == 0)
    return {
        "schema_version": 1,
        "scenario_id": scenario,
        "sample_count": len(errors),
        "fps": fps,
        "reference_evidence_kind": ios["evidence"],
        "candidate_evidence_kind": switch["evidence"],
        "maximum_relative_position_error_units": round(worst, 6),
        "rms_relative_position_error_units": round(rms, 6),
        "allowed_position_error_units": tolerance,
        "contact_mismatch_frames": mismatch_total,
        "contact_mismatch_categories": dict(sorted(contact_mismatches.items())),
        "contact_transition_mismatch_count": transition_mismatch_count,
        "unknown_contact_frames": unknown,
        "numeric_agreement_under_supplied_scale": numeric_pass,
        "source_capture_authenticated": False,
        "stationary_landmark_identity_authenticated": False,
        "original_ios_physics_verified": False,
        "automatic_collision_export_permitted": False,
        "interpretation": (
            "Frame/input/contact comparison under supplied, unauthenticated "
            "anchors and scales; agreement is not independent iOS gameplay "
            "proof and cannot authorize native collision geometry."
        ),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--traces", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--max-position-error-units", type=float, default=1.0)
    parser.add_argument("--max-contact-mismatches", type=int, default=0)
    args = parser.parse_args(argv)
    source = _private_path(args.traces)
    target = _private_path(args.out)
    if source == target:
        raise ValueError("input and output must be different local reports")
    if source.stat().st_size > MAX_BYTES:
        raise ValueError("trace input exceeds size limit")
    report = compare_contact_traces(
        json.loads(source.read_text(encoding="utf-8")),
        max_position_error_units=args.max_position_error_units,
        max_contact_mismatches=args.max_contact_mismatches)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    print("Compared private traces; original iOS gameplay remains unverified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
