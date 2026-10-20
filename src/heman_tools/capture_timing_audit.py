"""Private timing preflight for staged iOS/Switch contact-capture observations.

Observed timestamp *metadata* is supplied manually or from another local
capture tool. No video decoding, footage authentication or gameplay physics.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from .contact_scenarios import FPS, SCENARIOS, scripted_controls
from .frame_alignment import _private_path

MAX_JSON_BYTES = 500_000
MAX_TIMESTAMP_US = 10**15
MAX_SOURCE_FRAME_INDEX = 10**9
CAPTURE_TYPES = frozenset(("synthetic", "manual_observation"))


def _tolerance(value: object, name: str) -> float:
    if (type(value) not in (float, int) or not math.isfinite(value)
            or not 0 < value <= 100):
        raise ValueError(f"invalid {name} tolerance (0,100] ms")
    return float(value)


def _identifier(value: object, name: str) -> str:
    if (not isinstance(value, str) or not 1 <= len(value) <= 128
            or not value.isprintable()
            or any(ord(char) < 32 for char in value)):
        raise ValueError(f"invalid {name}")
    return value


def _read_stream(data: object, platform: str, scenario: str) -> dict:
    if not isinstance(data, dict) or data.get("platform") != platform:
        raise ValueError(f"expected a {platform} capture")
    capture_id = _identifier(data.get("capture_id"), "capture ID")
    kind = data.get("evidence_kind")
    if type(kind) is not str or kind not in CAPTURE_TYPES:
        raise ValueError("unsupported or missing evidence_kind")
    if data.get("clock_kind") != "capture_monotonic":
        raise ValueError("capture clock_kind must be capture_monotonic")
    frames = data.get("frames")
    expected = scripted_controls(scenario)
    if not isinstance(frames, list) or len(frames) != len(expected):
        raise ValueError("capture frame count differs from scripted scenario")
    timestamps = []
    source_indices = []
    for tick, (frame, (axis, jump)) in enumerate(zip(frames, expected)):
        if not isinstance(frame, dict):
            raise ValueError("invalid timing frame record")
        if type(frame.get("script_tick")) is not int or frame["script_tick"] != tick:
            raise ValueError("missing, repeated or reordered script tick")
        source_index = frame.get("source_frame_index")
        if (type(source_index) is not int
                or not 0 <= source_index <= MAX_SOURCE_FRAME_INDEX):
            raise ValueError("invalid source frame index")
        timestamp = frame.get("timestamp_us")
        if (type(timestamp) is not int
                or not 0 <= timestamp <= MAX_TIMESTAMP_US):
            raise ValueError("invalid monotonic timestamp")
        control = frame.get("control")
        if (not isinstance(control, dict)
                or type(control.get("horizontal")) is not int
                or type(control.get("jump")) is not bool
                or control["horizontal"] != axis
                or control["jump"] != jump):
            raise ValueError(f"{platform} control differs at script tick {tick}")
        if timestamps and timestamp <= timestamps[-1]:
            raise ValueError("non-increasing capture timestamp")
        if source_indices and source_index < source_indices[-1]:
            raise ValueError("source frame counter moved backward")
        timestamps.append(timestamp)
        source_indices.append(source_index)

    gaps = sum(max(index - previous - 1, 0)
               for previous, index in zip(source_indices, source_indices[1:]))
    repeats = sum(index == previous for previous, index
                  in zip(source_indices, source_indices[1:]))
    base_interval = 1_000_000 / FPS
    intervals = [b - a for a, b in zip(timestamps, timestamps[1:])]
    jitter_ms = max(abs(dt - base_interval) for dt in intervals) / 1000
    duration_error_ms = abs(
        timestamps[-1] - timestamps[0] - (len(timestamps) - 1) * base_interval
    ) / 1000
    return {
        "capture_id": capture_id, "evidence_kind": kind,
        "times_us": timestamps, "source_frame_gaps": gaps,
        "repeated_source_frames": repeats,
        "max_interval_jitter_ms": jitter_ms,
        "duration_error_ms": duration_error_ms,
    }


def audit_timing(data: object, *, max_interval_jitter_ms: float = 3.0,
                 max_elapsed_skew_ms: float = 4.0,
                 max_duration_error_ms: float = 6.0) -> dict:
    """Check relative capture timestamps against a provisional 60 Hz schedule.

    Comparing elapsed times after each capture's first frame cannot detect
    *constant* cross-device offsets: independent synchronization is required.
    """
    jitter_limit = _tolerance(max_interval_jitter_ms, "interval jitter")
    skew_limit = _tolerance(max_elapsed_skew_ms, "elapsed skew")
    duration_limit = _tolerance(max_duration_error_ms, "duration error")
    if not isinstance(data, dict):
        raise ValueError("timing input must be an object")
    scenario = data.get("scenario_id")
    if type(scenario) is not str or scenario not in SCENARIOS:
        raise ValueError("unsupported contact observation scenario")
    if type(data.get("nominal_fps")) is not int or data["nominal_fps"] != FPS:
        raise ValueError("the provisional capture protocol requires 60 Hz")
    ios = _read_stream(data.get("reference"), "ios", scenario)
    switch = _read_stream(data.get("candidate"), "switch", scenario)
    if ios["capture_id"] == switch["capture_id"]:
        raise ValueError("both captures share the same identifier")

    ref = ios["times_us"]
    other = switch["times_us"]
    elapsed_skew_ms = max(
        abs((r - ref[0]) - (s - other[0])) / 1000
        for r, s in zip(ref, other))
    blockers = []
    for label, capture in (("ios", ios), ("switch", switch)):
        if capture["source_frame_gaps"]:
            blockers.append(label + ":missing_source_frames")
        if capture["repeated_source_frames"]:
            blockers.append(label + ":duplicated_source_frames")
        if capture["max_interval_jitter_ms"] > jitter_limit:
            blockers.append(label + ":frame_interval_jitter")
        if capture["duration_error_ms"] > duration_limit:
            blockers.append(label + ":capture_duration_drift")
        if capture["evidence_kind"] == "synthetic":
            blockers.append(label + ":synthetic_not_original_recording")
    if elapsed_skew_ms > skew_limit:
        blockers.append("cross_capture_relative_elapsed_skew")

    return {
        "schema_version": 1,
        "scenario_id": scenario,
        "nominal_fps": FPS,
        "sample_count_per_capture": len(ref),
        "reference_evidence_kind": ios["evidence_kind"],
        "candidate_evidence_kind": switch["evidence_kind"],
        "max_frame_interval_jitter_ms": {
            "ios": round(ios["max_interval_jitter_ms"], 6),
            "switch": round(switch["max_interval_jitter_ms"], 6),
        },
        "capture_duration_error_ms": {
            "ios": round(ios["duration_error_ms"], 6),
            "switch": round(switch["duration_error_ms"], 6),
        },
        "missing_source_frame_count": {
            "ios": ios["source_frame_gaps"],
            "switch": switch["source_frame_gaps"],
        },
        "duplicate_source_frame_count": {
            "ios": ios["repeated_source_frames"],
            "switch": switch["repeated_source_frames"],
        },
        "max_relative_elapsed_skew_ms": round(elapsed_skew_ms, 6),
        "limits_ms": {
            "interval_jitter": jitter_limit, "relative_elapsed_skew": skew_limit,
            "duration_error": duration_limit,
        },
        "timing_consistent_under_supplied_metadata": not blockers,
        "structural_blockers": sorted(blockers),
        "source_video_decoding_performed": False,
        "absolute_cross_device_time_offset_verified": False,
        "source_frame_timestamps_authenticated": False,
        "ios_gameplay_recording_authenticated": False,
        "original_gameplay_physics_verified": False,
        "automatic_collision_export_permitted": False,
        "interpretation": (
            "Only relative timing and input-schedule consistency of supplied "
            "metadata. First-frame alignment is assumed; constant clock offsets, "
            "real video frame validity, original FPS and physics are unverified."
        ),
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--timing", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--max-interval-jitter-ms", type=float, default=3.0)
    p.add_argument("--max-elapsed-skew-ms", type=float, default=4.0)
    p.add_argument("--max-duration-error-ms", type=float, default=6.0)
    args = p.parse_args(argv)
    source, target = _private_path(args.timing), _private_path(args.out)
    if source == target:
        raise ValueError("timing input and output must be different files")
    if source.stat().st_size > MAX_JSON_BYTES:
        raise ValueError("private timing metadata exceeds size limit")
    report = audit_timing(
        json.loads(source.read_text(encoding="utf-8")),
        max_interval_jitter_ms=args.max_interval_jitter_ms,
        max_elapsed_skew_ms=args.max_elapsed_skew_ms,
        max_duration_error_ms=args.max_duration_error_ms)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    print("Audited private relative timing; source video and iOS physics remain unverified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
