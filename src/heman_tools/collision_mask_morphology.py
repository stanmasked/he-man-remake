"""Private-only morphology profiles for collision-atlas alpha masks.

This describes serialized image masks and their cross-resolution agreement.
It does not infer collision response or gameplay semantics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

from PIL import Image

from .collision_atlas_alpha import (
    MAX_TEXTURE_BYTES,
    MAX_TILESET_BYTES,
    TileSetFormatError,
    _load_rgba_png,
    _read_archive_entry,
    _sha256_file,
    _valid_map_name,
    parse_tileset,
    private_output_path,
)
from .tilemap import MAX_FILE as MAX_MAP_BYTES, TileMapFormatError, parse_tilemap

MAX_MASK_PIXELS = 1_048_576
ALPHA_THRESHOLD = 128


def mask_profile(image: Image.Image, entry: dict, atlas_index: int, cells: int) -> tuple[dict, bytearray]:
    """Return local morphology counters and a threshold mask held in memory."""
    x, y = entry["x"], entry["y"]
    width, height = entry["width"], entry["height"]
    pixels = width * height
    if pixels < 1 or pixels > MAX_MASK_PIXELS:
        raise TileSetFormatError("tile mask exceeds bounded morphology pixel budget")
    if x + width > image.width or y + height > image.height:
        raise TileSetFormatError("tile rectangle exceeds texture bounds")

    crop = image.crop((x, y, x + width, y + height)).convert("RGBA")
    alpha = list(crop.getchannel("A").getdata())
    mask = bytearray(1 if value >= ALPHA_THRESHOLD else 0 for value in alpha)
    occupied = sum(mask)
    row_counts = []
    row_first = []
    row_last = []
    horizontal_runs = 0
    for row_index in range(height):
        start = row_index * width
        row = mask[start:start + width]
        row_counts.append(sum(row))
        first = next((i for i, value in enumerate(row) if value), None)
        last = next((i for i in range(width - 1, -1, -1) if row[i]), None)
        row_first.append(first)
        row_last.append(last)
        horizontal_runs += sum(
            value and (i == 0 or not row[i - 1])
            for i, value in enumerate(row)
        )

    column_counts = []
    column_first = []
    column_last = []
    vertical_runs = 0
    for column in range(width):
        values = [mask[row * width + column] for row in range(height)]
        column_counts.append(sum(values))
        first = next((i for i, value in enumerate(values) if value), None)
        last = next((i for i in range(height - 1, -1, -1) if values[i]), None)
        column_first.append(first)
        column_last.append(last)
        vertical_runs += sum(
            value and (i == 0 or not values[i - 1])
            for i, value in enumerate(values)
        )

    if occupied:
        min_x, min_y = width, height
        max_x = max_y = -1
        for pos, value in enumerate(mask):
            if value:
                px, py = pos % width, pos // width
                min_x = min(min_x, px)
                min_y = min(min_y, py)
                max_x = max(max_x, px)
                max_y = max(max_y, py)
        bbox = [min_x, min_y, max_x + 1, max_y + 1]
    else:
        bbox = None

    edge_coverage = {
        "top": sum(mask[:width]),
        "right": sum(mask[row * width + width - 1] for row in range(height)),
        "bottom": sum(mask[(height - 1) * width:(height * width)]),
        "left": sum(mask[row * width] for row in range(height)),
    }
    boundary_edges = 0
    for pos, value in enumerate(mask):
        if not value:
            continue
        row, column = divmod(pos, width)
        if row == 0 or not mask[pos - width]:
            boundary_edges += 1
        if row + 1 == height or not mask[pos + width]:
            boundary_edges += 1
        if column == 0 or not mask[pos - 1]:
            boundary_edges += 1
        if column + 1 == width or not mask[pos + 1]:
            boundary_edges += 1

    profile = {
        "tile_id": entry["ordinal"],
        "atlas_index": atlas_index,
        "cells_using_tile": cells,
        "tile_name": entry["name"] or None,
        "mask_dimensions": [width, height],
        "alpha_nonzero_pixels": sum(value > 0 for value in alpha),
        "alpha_ge_128_pixels": occupied,
        "alpha_ge_128_fraction": occupied / pixels,
        "opaque_bbox_xyxy_exclusive": bbox,
        "edge_coverage_pixels": edge_coverage,
        "edge_coverage_fraction": {
            "top": edge_coverage["top"] / width,
            "right": edge_coverage["right"] / height,
            "bottom": edge_coverage["bottom"] / width,
            "left": edge_coverage["left"] / height,
        },
        "horizontal_runs": horizontal_runs,
        "vertical_runs": vertical_runs,
        "exposed_four_neighbor_boundary_edges": boundary_edges,
        "nonempty_rows": sum(count > 0 for count in row_counts),
        "nonempty_columns": sum(count > 0 for count in column_counts),
        "min_max_opaque_pixels_per_row": [
            min(row_counts), max(row_counts)
        ],
        "min_max_opaque_pixels_per_column": [
            min(column_counts), max(column_counts)
        ],
        # Full one-dimensional profiles are retained only in the local report.
        "row_alpha_ge_128_counts": row_counts,
        "column_alpha_ge_128_counts": column_counts,
        "row_first_opaque_x": row_first,
        "row_last_opaque_x": row_last,
        "column_first_opaque_y": column_first,
        "column_last_opaque_y": column_last,
    }
    return profile, mask


def _screen_data(archive: zipfile.ZipFile, screen: str, map_name: str) -> dict:
    prefix = f"Payload/MOTU.app/{screen}"
    map_path = f"{prefix}/maps/{map_name}"
    tileset_path = f"{prefix}/tilesets/collision.tileset"
    texture_path = f"{prefix}/textures/collisionTiles.png"
    map_raw = _read_archive_entry(archive, map_path, MAX_MAP_BYTES)
    tileset_raw = _read_archive_entry(archive, tileset_path, MAX_TILESET_BYTES)
    texture_raw = _read_archive_entry(archive, texture_path, MAX_TEXTURE_BYTES)
    tilemap = parse_tilemap(map_raw)
    layer = tilemap.layer("collision")
    atlas_matches = [i for i, name in enumerate(layer.atlases) if name == "collision"]
    if len(atlas_matches) != 1:
        raise ValueError("collision layer must reference exactly one collision atlas")
    atlas_index = atlas_matches[0]
    tileset = parse_tileset(tileset_raw)
    image = _load_rgba_png(texture_raw)
    texture_ref = tileset["texture_ref"].casefold()
    if texture_ref.startswith("img_"):
        texture_ref = texture_ref[4:]
    if texture_ref != Path(texture_path).stem.casefold():
        raise ValueError("tileset texture reference does not match selected PNG")

    frequencies = {}
    for tile_id, atlas_id in zip(layer.tile_ids, layer.atlas_ids):
        if tile_id == 0xffff:
            continue
        if atlas_id == atlas_index:
            frequencies[tile_id] = frequencies.get(tile_id, 0) + 1
        elif atlas_id >= len(layer.atlases):
            raise TileMapFormatError("occupied tile has invalid atlas")

    profiles = {}
    for tile_id, cells in sorted(frequencies.items()):
        if tile_id >= len(tileset["entries"]):
            raise TileSetFormatError("occupied tile ID exceeds tileset record count")
        profile, mask = mask_profile(image, tileset["entries"][tile_id], atlas_index, cells)
        profiles[tile_id] = {"profile": profile, "mask": mask}

    return {
        "screen": screen,
        "map_bytes": map_raw,
        "tileset": tileset,
        "profiles": profiles,
        "tile_frequencies": {str(k): v for k, v in sorted(frequencies.items())},
        "map_dimensions": [layer.columns, layer.rows],
        "occupied_cells": layer.occupied_count,
        "source_entries": {
            "map": {"size_bytes": len(map_raw), "sha256": hashlib.sha256(map_raw).hexdigest()},
            "tileset": {"size_bytes": len(tileset_raw), "sha256": hashlib.sha256(tileset_raw).hexdigest()},
            "texture": {"size_bytes": len(texture_raw), "sha256": hashlib.sha256(texture_raw).hexdigest()},
        },
        "texture_dimensions": [image.width, image.height],
    }


def _rectangle_scale(med: dict, large: dict) -> int:
    a = med["tileset"]["entries"]
    b = large["tileset"]["entries"]
    if len(a) != len(b) or not a:
        raise ValueError("resolution packs have different tileset record counts")
    if [e["name"] for e in a] != [e["name"] for e in b]:
        raise ValueError("resolution packs have different tileset record names")
    if a[0]["width"] < 1 or b[0]["width"] % a[0]["width"]:
        raise ValueError("tileset rectangle scale is not an integer")
    scale = b[0]["width"] // a[0]["width"]
    if scale < 1:
        raise ValueError("invalid tileset rectangle scale")
    for left, right in zip(a, b):
        if (right["x"], right["y"], right["width"], right["height"]) != (
            left["x"] * scale, left["y"] * scale,
            left["width"] * scale, left["height"] * scale
        ):
            raise ValueError("tileset rectangles do not share one uniform scale")
    return scale


def _downsample_mask(mask: bytearray, width: int, height: int, scale: int) -> bytearray:
    if width % scale or height % scale:
        raise ValueError("high-resolution tile dimensions do not divide by scale")
    out_width, out_height = width // scale, height // scale
    required = (scale * scale + 1) // 2
    result = bytearray(out_width * out_height)
    for y in range(out_height):
        for x in range(out_width):
            total = 0
            for dy in range(scale):
                start = (y * scale + dy) * width + x * scale
                total += sum(mask[start:start + scale])
            result[y * out_width + x] = int(total >= required)
    return result


def compare_screen_pair(ipa: Path, map_name: str) -> dict:
    if not ipa.is_file() or ipa.is_symlink():
        raise ValueError("IPA must be an existing regular non-symlink file")
    with zipfile.ZipFile(ipa, "r") as archive:
        med = _screen_data(archive, "screen-med", map_name)
        large = _screen_data(archive, "screen-xlarge", map_name)

    scale = _rectangle_scale(med, large)
    ids_med = set(med["profiles"])
    ids_large = set(large["profiles"])
    if ids_med != ids_large:
        raise ValueError("used collision tile IDs differ between resolution packs")
    if med["tile_frequencies"] != large["tile_frequencies"]:
        raise ValueError("used collision tile frequencies differ between resolution packs")

    per_tile = []
    normalized_exact = 0
    all_mismatch = 0
    all_union = 0
    for tile_id in sorted(ids_med):
        left = med["profiles"][tile_id]
        right = large["profiles"][tile_id]
        lm = left["mask"]
        rm = right["mask"]
        rw, rh = right["profile"]["mask_dimensions"]
        normalized = _downsample_mask(rm, rw, rh, scale)
        if len(lm) != len(normalized):
            raise ValueError("normalized high-resolution mask dimensions differ")
        intersection = sum(a and b for a, b in zip(lm, normalized))
        union = sum(a or b for a, b in zip(lm, normalized))
        mismatches = sum(a != b for a, b in zip(lm, normalized))
        iou = 1.0 if union == 0 else intersection / union
        normalized_exact += mismatches == 0
        all_mismatch += mismatches
        all_union += union
        per_tile.append({
            "tile_id": tile_id,
            "cells_using_tile": left["profile"]["cells_using_tile"],
            "screen_med": left["profile"],
            "screen_xlarge": right["profile"],
            "normalized_mask_comparison": {
                "downsample_scale": scale,
                "screen_med_pixels": len(lm),
                "intersection_pixels": intersection,
                "union_pixels": union,
                "mismatched_pixels": mismatches,
                "intersection_over_union": iou,
                "exact_threshold_mask_match": mismatches == 0,
            },
        })

    complete = (
        med["map_bytes"] == large["map_bytes"]
        and med["map_dimensions"] == large["map_dimensions"]
        and med["tile_frequencies"] == large["tile_frequencies"]
    )
    public_med = {k: v for k, v in med.items() if k not in ("map_bytes", "tileset", "profiles")}
    public_large = {k: v for k, v in large.items() if k not in ("map_bytes", "tileset", "profiles")}
    return {
        "schema": "heman-collision-mask-morphology-v1",
        "map_name": map_name,
        "source_ipa": {
            "name": ipa.name,
            "size_bytes": ipa.stat().st_size,
            "sha256": _sha256_file(ipa),
        },
        "screen_med": public_med,
        "screen_xlarge": public_large,
        "cross_screen": {
            "map_bytes_exactly_equal": med["map_bytes"] == large["map_bytes"],
            "tile_record_names_and_rectangles_match_after_uniform_scale": True,
            "tile_rect_scale_factor": scale,
            "used_tile_ids_match": ids_med == ids_large,
            "tile_frequencies_match": med["tile_frequencies"] == large["tile_frequencies"],
            "used_tile_count": len(per_tile),
            "exact_normalized_threshold_mask_matches": normalized_exact,
            "total_normalized_mask_pixels_compared": sum(
                item["normalized_mask_comparison"]["screen_med_pixels"] for item in per_tile
            ),
            "total_normalized_mask_mismatches": all_mismatch,
            "aggregate_normalized_mask_iou": (
                1.0 if all_union == 0 else
                sum(item["normalized_mask_comparison"]["intersection_pixels"] for item in per_tile)
                / all_union
            ),
        },
        "tiles": per_tile,
        "result": "cross_screen_mask_morphology_complete" if complete else "partial_or_divergent_morphology",
        "original_collision_semantics_verified": False,
        "original_ios_gameplay_trace_compared": False,
        "native_switch_collision_import_authorized": False,
        "interpretation_boundary": (
            "Alpha-mask morphology and normalized mask agreement are source-image "
            "observations only. They do not establish solidity, slopes, one-way behavior, "
            "hazards, object ownership, world transforms or runtime collision behavior."
        ),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", required=True, type=Path)
    parser.add_argument("--map", dest="map_name", default="MUMap1-1.map")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    if not _valid_map_name(args.map_name):
        parser.error("--map must be a simple .map basename")
    try:
        output = private_output_path(args.out)
        report = compare_screen_pair(args.ipa, args.map_name)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except (OSError, zipfile.BadZipFile, TileMapFormatError, TileSetFormatError, ValueError, KeyError) as exc:
        parser.error(f"collision mask morphology failed: {type(exc).__name__}: {exc}")
    print(f"Stage258 result={report['result']}; private morphology report saved under local_reports/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
