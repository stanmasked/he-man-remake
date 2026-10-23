"""Stage218: privacy-preserving paired-resolution CPU frame evidence gate.

Accept only aggregate metrics from four locally rendered original/source or
synthetic frames. This cannot establish real iOS runtime placement or pixel
parity; it merely checks packet counts and measured cropped-canvas extents.
No IPA, PNG, identifiers, byte offsets, transform values or resource paths
are read or written by this module.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping, Sequence

from .collision_inventory import private_output_path
from .physics_shape_census import SCREENS


class FourViewFrameGateError(ValueError):
    """Invalid or incomplete four-view CPU preview evidence."""


_DIRECTIONS = ("east", "west")
_MAX_SYMBOLS = 1024
_MAX_DIMENSION = 4_194_304
_REQUIRED = (
    "screen", "direction", "source_symbol_count",
    "resolved_symbol_count", "cpu_frame_packet_count",
    "output_width", "output_height", "gpu_submission_verified",
    "original_runtime_pixel_parity_verified",
)


def _bounded_count(record: Mapping, field: str, *, minimum: int, maximum: int) -> int:
    value = record.get(field)
    if type(value) is not int or not minimum <= value <= maximum:
        raise FourViewFrameGateError(f"{field} must be a bounded integer")
    return value


def summarize_four_view_frame_parity(frames: Sequence[Mapping]) -> dict:
    """Report symmetric directional resolution evidence without inferred transforms.

    Input order is irrelevant. All four (resolution, direction) pairs must
    occur exactly once. Invalid source flags, extra derived parity claims, and
    non-finite/oversized metrics fail closed before any result is returned.
    """
    if not isinstance(frames, (tuple, list)) or len(frames) != 4:
        raise FourViewFrameGateError("Exactly four CPU frame reports are required")
    indexed: dict[tuple[str, str], dict] = {}
    for source in frames:
        if not isinstance(source, Mapping):
            raise FourViewFrameGateError("Every CPU frame report must be an object")
        if any(field not in source for field in _REQUIRED):
            raise FourViewFrameGateError("CPU frame is missing required aggregate fields")
        screen, direction = source["screen"], source["direction"]
        if screen not in SCREENS or direction not in _DIRECTIONS:
            raise FourViewFrameGateError("Unknown resolution or direction")
        key = (screen, direction)
        if key in indexed:
            raise FourViewFrameGateError("Duplicate resolution/direction report")
        for flag in ("gpu_submission_verified", "original_runtime_pixel_parity_verified"):
            if source[flag] is not False:
                raise FourViewFrameGateError("Synthetic CPU source cannot claim runtime/GPU parity")
        counts = {
            field: _bounded_count(source, field, minimum=0, maximum=_MAX_SYMBOLS)
            for field in ("source_symbol_count", "resolved_symbol_count",
                          "cpu_frame_packet_count")
        }
        width = _bounded_count(source, "output_width", minimum=1,
                               maximum=_MAX_DIMENSION)
        height = _bounded_count(source, "output_height", minimum=1,
                                maximum=_MAX_DIMENSION)
        if width * height > _MAX_DIMENSION:
            raise FourViewFrameGateError("CPU frame exceeds the bounded pixel budget")
        if (counts["resolved_symbol_count"] > counts["source_symbol_count"]
                or counts["cpu_frame_packet_count"] > counts["resolved_symbol_count"]):
            raise FourViewFrameGateError("CPU frame packet counts are inconsistent")
        local = source.get("source_local_transform_counts")
        negative_x = None
        if local is not None:
            if not isinstance(local, Mapping):
                raise FourViewFrameGateError("Local transform counts must be aggregate objects")
            negative_x = _bounded_count(local, "negative_scale_x",
                                        minimum=0, maximum=counts["source_symbol_count"])
        indexed[key] = {
            **counts, "width": width, "height": height,
            "negative_scale_x": negative_x,
        }

    expected = {(screen, direction) for screen in SCREENS for direction in _DIRECTIONS}
    if set(indexed) != expected:
        raise FourViewFrameGateError("Missing resolution/direction pair")

    comparisons = []
    for direction in _DIRECTIONS:
        medium = indexed[SCREENS[0], direction]
        large = indexed[SCREENS[1], direction]
        comparisons.append({
            "direction": direction,
            "source_symbol_count_match": medium["source_symbol_count"] == large["source_symbol_count"],
            "resolved_symbol_count_match": medium["resolved_symbol_count"] == large["resolved_symbol_count"],
            "packet_count_match": medium["cpu_frame_packet_count"] == large["cpu_frame_packet_count"],
            "cropped_width_exactly_doubled": large["width"] == 2 * medium["width"],
            "cropped_height_exactly_doubled": large["height"] == 2 * medium["height"],
            "negative_x_scale_count_match": (
                medium["negative_scale_x"] == large["negative_scale_x"]
                if medium["negative_scale_x"] is not None and large["negative_scale_x"] is not None
                else None
            ),
        })

    return {
        "classification": "four_view_cpu_source_metric_comparison",
        "frame_count": 4,
        "paired_resolution_directions_checked": 2,
        "comparisons": comparisons,
        "all_resolution_packet_counts_match": all(c["packet_count_match"] for c in comparisons),
        "all_cropped_dimensions_exactly_doubled": all(
            c["cropped_width_exactly_doubled"] and c["cropped_height_exactly_doubled"]
            for c in comparisons
        ),
        "camera_coordinates_recovered": False,
        "runtime_player_transform_recovered": False,
        "original_runtime_pixel_parity_verified": False,
        "gpu_submission_verified": False,
        "pixel_arrays_examined": False,
        "source_identifiers_exported": False,
        "interpretation": (
            "Cropped CPU preview extents and Symbol packet counts only; "
            "not evidence of source camera, full-scene position or iOS runtime frame parity"
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-report", type=Path, required=True,
                        help="Owner-local Stage218 four-frame aggregate JSON beneath local_reports/")
    parser.add_argument("--out", type=Path, required=True,
                        help="Owner-local aggregate parity JSON beneath local_reports/")
    args = parser.parse_args(argv)
    source = private_output_path(args.source_report)
    destination = private_output_path(args.out)
    if source == destination or source.suffix != ".json" or destination.suffix != ".json":
        parser.error("Source and destination must be separate .json paths")
    if destination.exists() or destination.is_symlink():
        raise FourViewFrameGateError("Refusing to overwrite an existing private parity report")
    raw = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise FourViewFrameGateError("Source summary must be an object")
    result = summarize_four_view_frame_parity(raw.get("frames"))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n",
                           encoding="utf-8")
    print("Four CPU frame metrics checked; original runtime and camera parity remain unverified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
