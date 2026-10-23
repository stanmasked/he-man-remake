"""Stage196: explain native clamp-to-edge sampling at zero-filled PNG padding.

Original PNGData::pngInfoCallback explicitly zeroes right-side padding bytes
and complete bottom padding rows. This audit joins private cut bounds to the
native wrap map and reports aggregate sampling-edge categories only.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from .collision_inventory import private_output_path
from .sprite_cut_png_bounds_census import _load_private_cut_rows
from .sprite_cut_runtime_texture_bounds import (
    MAX_CUTS, allocated_texture_dimensions, classify_allocated_cut,
)
from .sprite_cut_wrap_bounds_audit import _load_private_cut_wrap_codes
from .native_sprite_cut_uv import compute_native_sprite_cut_uv


MAX_PADDED_TEXTURE_BYTES = 64_000_000


class SpritePaddingEdgeAuditError(ValueError):
    """Paired geometry, wrap modes, or UV edge classification is unresolved."""


def pad_decoded_png_rows_zero_fill(
    rows: tuple[bytes, ...] | list[bytes],
    width: int,
    height: int,
    bytes_per_pixel: int,
) -> tuple[bytes, tuple[int, int]]:
    """Model PNGData's post-transform row layout and zero-filled right/bottom padding."""
    if (type(width) is not int or type(height) is not int
            or not 0 < width <= 32768 or not 0 < height <= 32768):
        raise SpritePaddingEdgeAuditError("Decoded PNG dimensions must be bounded positive integers")
    if type(bytes_per_pixel) is not int or bytes_per_pixel not in (3, 4):
        raise SpritePaddingEdgeAuditError("Native decoded rows must use 3 or 4 bytes per pixel")
    if not isinstance(rows, (tuple, list)) or len(rows) != height:
        raise SpritePaddingEdgeAuditError("Decoded row count must match PNG height")
    row_bytes = width * bytes_per_pixel
    if any(type(row) is not bytes or len(row) != row_bytes for row in rows):
        raise SpritePaddingEdgeAuditError("Every decoded row must contain exactly width × BPP bytes")
    allocated_width, allocated_height = allocated_texture_dimensions((width, height))
    total = allocated_width * allocated_height * bytes_per_pixel
    if total > MAX_PADDED_TEXTURE_BYTES:
        raise SpritePaddingEdgeAuditError("Padded texture exceeds the reference-model memory limit")
    output = bytearray(total)
    stride = allocated_width * bytes_per_pixel
    for y, row in enumerate(rows):
        start = y * stride
        output[start:start + row_bytes] = row
    return bytes(output), (allocated_width, allocated_height)


def _axis_edge_sample(
    overrun: bool, wrap_mode: str, raw_dimension: int, allocated_dimension: int,
) -> str:
    if not overrun:
        return "not_overrun"
    if wrap_mode == "repeat":
        return "repeat_wrap"
    if wrap_mode == "clamp_to_edge":
        return ("zero_filled_padding_edge" if raw_dimension < allocated_dimension
                else "source_border_edge")
    return "unrecognized_wrap"


def classify_native_edge_sampling(
    rectangle: tuple[int, int, int, int],
    png_dimensions: tuple[int, int],
    wrap_codes: tuple[int, int],
) -> dict:
    """Classify safe-crop status separately from the original runtime sampling edge."""
    status, _excess_x, _excess_y = classify_allocated_cut(rectangle, png_dimensions)
    uv = compute_native_sprite_cut_uv(rectangle, png_dimensions, wrap_codes)
    alloc_w, alloc_h = allocated_texture_dimensions(png_dimensions)
    over_x = uv.u0 > 1.0 or uv.u1 > 1.0
    over_y = uv.v0 > 1.0 or uv.v1 > 1.0
    sample_x = _axis_edge_sample(over_x, uv.wrap_s_mode, png_dimensions[0], alloc_w)
    sample_y = _axis_edge_sample(over_y, uv.wrap_t_mode, png_dimensions[1], alloc_h)
    active = [value for value in (sample_x, sample_y) if value != "not_overrun"]
    if not active:
        overall = "not_outside_allocated"
    elif "repeat_wrap" in active and any(
        value in ("zero_filled_padding_edge", "source_border_edge") for value in active
    ):
        overall = "mixed_axis_sampling"
    elif "repeat_wrap" in active:
        overall = "repeat_wrap"
    elif "unrecognized_wrap" in active:
        overall = "unresolved_wrap"
    elif "zero_filled_padding_edge" in active:
        overall = "zero_filled_padding_edge"
    else:
        overall = "source_border_edge"
    return {
        "geometry_status": status,
        "x_overrun": over_x,
        "y_overrun": over_y,
        "x_edge_sample": sample_x,
        "y_edge_sample": sample_y,
        "overall_edge_sample": overall,
        "negative_uv": min(uv.u0, uv.v0, uv.u1, uv.v1) < 0.0,
        "uv_above_one": max(uv.u0, uv.v0, uv.u1, uv.v1) > 1.0,
    }


def summarize_padding_edge_impact(
    med_rows: dict,
    xlarge_rows: dict,
    med_wraps: dict[tuple[str, int], tuple[int, int]],
    xlarge_wraps: dict[tuple[str, int], tuple[int, int]],
) -> dict:
    """Summarize source-edge versus zero-padding samples without retaining identities."""
    if (not isinstance(med_rows, dict) or not isinstance(xlarge_rows, dict)
            or not 1 <= len(med_rows) <= MAX_CUTS
            or set(med_rows) != set(xlarge_rows)
            or set(med_rows) != set(med_wraps)
            or set(xlarge_rows) != set(xlarge_wraps)):
        raise SpritePaddingEdgeAuditError("Paired cut inventories and wrap maps do not match")
    if med_wraps != xlarge_wraps:
        raise SpritePaddingEdgeAuditError("Paired native wrap settings differ")
    reports = {}
    for label, rows, wraps in (
        ("screen-med", med_rows, med_wraps),
        ("screen-xlarge", xlarge_rows, xlarge_wraps),
    ):
        geometry = Counter()
        edge = Counter()
        axes = Counter()
        for ref, (rectangle, png_dims) in rows.items():
            result = classify_native_edge_sampling(rectangle, png_dims, wraps[ref])
            geometry[result["geometry_status"]] += 1
            edge[result["overall_edge_sample"]] += 1
            if result["x_overrun"] and result["y_overrun"]:
                axes["both_axes"] += 1
            elif result["x_overrun"]:
                axes["x_only"] += 1
            elif result["y_overrun"]:
                axes["y_only"] += 1
            if result["x_edge_sample"] != "not_overrun":
                edge["x_" + result["x_edge_sample"]] += 1
            if result["y_edge_sample"] != "not_overrun":
                edge["y_" + result["y_edge_sample"]] += 1
            if result["negative_uv"]:
                edge["negative_uv_records"] += 1
            if result["uv_above_one"]:
                edge["uv_above_one_records"] += 1
        reports[label] = {
            "geometry_categories": {
                name: geometry[name]
                for name in ("inside_raw", "inside_allocated_only", "outside_allocated", "invalid")
            },
            "outside_allocated_axis_counts": {
                name: axes[name] for name in ("x_only", "y_only", "both_axes")
            },
            "edge_sampling_counts": {
                name: edge[name] for name in (
                    "zero_filled_padding_edge", "source_border_edge", "repeat_wrap",
                    "mixed_axis_sampling", "unresolved_wrap", "not_outside_allocated",
                    "x_zero_filled_padding_edge", "x_source_border_edge", "x_repeat_wrap",
                    "y_zero_filled_padding_edge", "y_source_border_edge", "y_repeat_wrap",
                    "negative_uv_records", "uv_above_one_records",
                )
            },
        }
    return {
        "classification": "private_native_png_padding_edge_impact",
        "cut_tuple_count_per_pack": len(med_rows),
        "native_padding_right_and_bottom_bytes_zeroed": True,
        "native_uv_coordinates_clipped_by_model": False,
        "paired_cut_handle_wrap_settings_identical": True,
        "per_pack": reports,
        "original_resource_keys_paths_offsets_or_per_record_data_exported": False,
    }


def audit_private_padding_edge_impact(ipa: Path) -> dict:
    rows_med, rows_xlarge = _load_private_cut_rows(ipa)
    wraps = _load_private_cut_wrap_codes(ipa)
    return summarize_padding_edge_impact(
        rows_med, rows_xlarge, wraps["screen-med"], wraps["screen-xlarge"]
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    destination = private_output_path(args.out)
    report = audit_private_padding_edge_impact(args.ipa)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Private native PNG-padding edge census complete (aggregate-only).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
