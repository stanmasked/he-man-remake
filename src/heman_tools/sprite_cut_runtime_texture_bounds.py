"""Stage192: reproduce original PNG power-of-two texture extents and UV gate.

Private records remain in-memory. Public reports contain counts only, and no
padding pixels, source files or gameplay textures are exported.
Native evidence: pngInfoCallback stores IHDR actual width/height separately,
allocates next-power-of-two width/height starting at 4, and SpriteCut UVs
divide by Texture::getWidth/getHeight (allocated sizes, not unpadded sizes).
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from .collision_inventory import private_output_path
from .sprite_cut_png_bounds_census import (
    MAX_CUTS, SpriteCutBoundsError, _load_private_cut_rows,
    classify_rectangle,
)


def allocated_texture_dimensions(png_dimensions: tuple[int, int]) -> tuple[int, int]:
    """Replicate the observed ARMv7 PNG allocation rule (minimum 4, pow2)."""
    if (not isinstance(png_dimensions, tuple) or len(png_dimensions) != 2
            or any(type(value) is not int or not 0 < value <= 32768
                   for value in png_dimensions)):
        raise SpriteCutBoundsError("PNG dimensions must be bounded positive integers")
    return tuple(max(4, 1 << (value - 1).bit_length()) for value in png_dimensions)


def classify_allocated_cut(
    rectangle: tuple[int, int, int, int],
    png_dimensions: tuple[int, int],
) -> tuple[str, int, int]:
    """Distinguish raw-PNG fits, padded-only fits and still-unresolved cuts."""
    raw_class, _, _ = classify_rectangle(rectangle, png_dimensions)
    if raw_class == "invalid":
        return "invalid", 0, 0
    if raw_class == "inside":
        return "inside_raw", 0, 0
    width, height = allocated_texture_dimensions(png_dimensions)
    x, y, cut_width, cut_height = rectangle
    overflow_x = max(0, x + cut_width - width)
    overflow_y = max(0, y + cut_height - height)
    if overflow_x or overflow_y:
        return "outside_allocated", overflow_x, overflow_y
    return "inside_allocated_only", 0, 0


def verified_uv_coordinates(
    rectangle: tuple[int, int, int, int],
    png_dimensions: tuple[int, int],
) -> tuple[float, float, float, float]:
    """Return normalized UVs only when the original cut fits allocated extents.

    This establishes UV geometry, NOT the PNG pixel content in padded areas.
    Actual padding pixels must not be synthesized without separate evidence.
    """
    status, _, _ = classify_allocated_cut(rectangle, png_dimensions)
    if status not in ("inside_raw", "inside_allocated_only"):
        raise SpriteCutBoundsError("Cannot normalize invalid or outside-allocated SpriteCut")
    x, y, cut_width, cut_height = rectangle
    width, height = allocated_texture_dimensions(png_dimensions)
    return (x / width, y / height,
            (x + cut_width) / width, (y + cut_height) / height)


def summarize_paired_allocated_bounds(
    med: dict[tuple[str, int], tuple[tuple[int, int, int, int], tuple[int, int]]],
    xlarge: dict[tuple[str, int], tuple[tuple[int, int, int, int], tuple[int, int]]],
) -> dict:
    """Count categories and cross-pack transitions; never emit private names."""
    if (not isinstance(med, dict) or not isinstance(xlarge, dict)
            or not 1 <= len(med) <= MAX_CUTS or set(med) != set(xlarge)):
        raise SpriteCutBoundsError("Paired source cut sets differ or are excessive")
    statuses = {}
    by_pack = {}
    for label, rows in (("screen-med", med), ("screen-xlarge", xlarge)):
        bucket = Counter()
        records = {}
        max_horizontal = max_vertical = 0
        for key, (rectangle, png_dims) in rows.items():
            status, excess_x, excess_y = classify_allocated_cut(rectangle, png_dims)
            records[key] = status
            bucket[status] += 1
            max_horizontal = max(max_horizontal, excess_x)
            max_vertical = max(max_vertical, excess_y)
        statuses[label] = records
        by_pack[label] = {
            "inside_raw_png": bucket["inside_raw"],
            "fits_allocated_only": bucket["inside_allocated_only"],
            "outside_even_allocated": bucket["outside_allocated"],
            "invalid_rectangle": bucket["invalid"],
            "largest_unresolved_horizontal_excess_pixels": max_horizontal,
            "largest_unresolved_vertical_excess_pixels": max_vertical,
        }
    transitions = Counter(
        (statuses["screen-med"][key], statuses["screen-xlarge"][key])
        for key in med
    )
    return {
        "classification": "private_native_png_allocation_sprite_cut_census",
        "indexed_cut_count_per_pack": len(med),
        "per_pack": by_pack,
        "paired_category_counts": {
            a + "_med__" + b + "_xlarge": count
            for (a, b), count in sorted(transitions.items())
        },
        "native_png_allocation_minimum_edge_pixels": 4,
        "native_allocation_per_axis_next_power_of_two": True,
        "sprite_cut_uv_denominator_is_allocated_texture_size": True,
        "unresolved_cuts_repaired_or_rendered": False,
        "padding_pixel_content_verified": False,
        "original_records_names_bytes_offsets_or_images_exported": False,
    }


def audit_private_allocated_bounds(ipa: Path) -> dict:
    medium, extra_large = _load_private_cut_rows(ipa)
    return summarize_paired_allocated_bounds(medium, extra_large)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    destination = private_output_path(args.out)
    report = audit_private_allocated_bounds(args.ipa)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Private padded-texture SpriteCut census complete (aggregate-only).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
