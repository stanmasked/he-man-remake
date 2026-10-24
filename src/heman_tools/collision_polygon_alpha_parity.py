"""Read-only polygon-vs-atlas-alpha comparison for linked collision tiles.

Static source-image similarity is not proof of an original gameplay collider.
The original polygons and image pixels are never exported; the report contains
only numeric overlap metrics and evidence-boundary flags.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import zipfile

from .collision_atlas_alpha import (
    MAX_TEXTURE_BYTES, MAX_TILESET_BYTES, _load_rgba_png,
    _read_archive_entry, parse_tileset, private_output_path,
)
from .collision_geometry_name_link import _screen_inventory, SCREENS, PREFIX
from .shapes import parse_shape

ALPHA_THRESHOLD = 128
MAX_PER_TILE_PIXELS = 1_048_576
MAX_ANALYZED_SHAPES = 128
EPS = 1e-6


def _polygon_area(vertices: tuple[tuple[float, float], ...]) -> float:
    area2 = sum(
        vertices[i][0] * vertices[(i + 1) % len(vertices)][1]
        - vertices[(i + 1) % len(vertices)][0] * vertices[i][1]
        for i in range(len(vertices))
    )
    return abs(area2) / 2


def _inside_polygon(px: float, py: float,
                    vertices: tuple[tuple[float, float], ...]) -> bool:
    """Even-odd fill rule evaluated at pixel centers, no boundary sampling."""
    inside = False
    for index, (ax, ay) in enumerate(vertices):
        bx, by = vertices[(index + 1) % len(vertices)]
        if (ay > py) != (by > py):
            xcut = ax + (py - ay) * (bx - ax) / (by - ay)
            if px < xcut:
                inside = not inside
    return inside


def _compare_polygon_to_alpha(image, rectangle: dict, shape, scale: int) -> dict:
    if shape.kind != "polygon":
        raise ValueError("only polygonal linked shape can be raster-compared")
    vertices = shape.vertices
    if not 3 <= len(vertices) <= 128:
        raise ValueError("polygon vertex count outside bounded raster audit")
    if not all(math.isfinite(value) for vertex in vertices for value in vertex):
        raise ValueError("non-finite polygon coordinates")
    area = _polygon_area(vertices)
    if area <= EPS:
        raise ValueError("degenerate polygon: zero area")
    if not isinstance(scale, int) or not 1 <= scale <= 8:
        raise ValueError("unsupported integer resolution scale")

    x, y, width, height = (rectangle[k] for k in ("x", "y", "width", "height"))
    if (width < 1 or height < 1 or width * height > MAX_PER_TILE_PIXELS
            or x + width > image.width or y + height > image.height):
        raise ValueError("tile rectangle exceeds decoded PNG budget")
    pixels = image.crop((x, y, x + width, y + height)).getchannel("A").tobytes()
    alpha_count = geometry_count = intersection = union = 0
    for i, alpha in enumerate(pixels):
        ix, iy = i % width, i // width
        hit_alpha = alpha >= ALPHA_THRESHOLD
        hit_geometry = _inside_polygon((ix + 0.5) / scale,
                                       (iy + 0.5) / scale, vertices)
        alpha_count += hit_alpha
        geometry_count += hit_geometry
        intersection += hit_alpha and hit_geometry
        union += hit_alpha or hit_geometry
    mismatched = union - intersection
    return {
        "geometry_kind": "polygon",
        "polygon_vertex_count": len(vertices),
        "polygon_area_local_units_squared": area,
        "atlas_pixels": width * height,
        "png_alpha_ge_128_pixels": alpha_count,
        "polygon_center_raster_pixels": geometry_count,
        "intersection_pixels": intersection,
        "union_pixels": union,
        "pixel_mismatches": mismatched,
        "intersection_over_union": (1.0 if union == 0 else intersection / union),
        "resolution_scale": scale,
        "source_geometry_vertices_in_report": False,
        "source_png_alpha_array_in_report": False,
    }


def _screen(archive: zipfile.ZipFile, screen: str, map_name: str,
            medium_reference_widths: dict[int, int] | None) -> dict:
    inventory = _screen_inventory(archive, screen, map_name)
    root = PREFIX + screen + "/"
    raw_tileset = _read_archive_entry(
        archive, root + "tilesets/collision.tileset", MAX_TILESET_BYTES
    )
    texture = _read_archive_entry(
        archive, root + "textures/collisionTiles.png", MAX_TEXTURE_BYTES
    )
    tileset = parse_tileset(raw_tileset)
    image = _load_rgba_png(texture)
    if len(tileset["entries"]) != len(inventory["tileset_names"]):
        raise ValueError("tileset record count changed within read")
    selected = inventory["used_frequencies"]
    if len(selected) > MAX_ANALYZED_SHAPES:
        raise ValueError("too many distinct used collision tiles")

    rows = []
    incomplete = 0
    total = {"intersection": 0, "union": 0, "mismatch": 0, "pixels": 0}
    ref_widths = {}
    for tile_id, cells in sorted(selected.items()):
        record = tileset["entries"][tile_id]
        if not record["name"]:
            continue
        if tile_id not in inventory["geometry_bytes"]:
            incomplete += 1
            continue
        raw_shape = inventory["geometry_bytes"][tile_id]
        shape = parse_shape(raw_shape)
        if shape.kind != "polygon":
            incomplete += 1
            continue
        rect_width = record["width"]
        if medium_reference_widths is None:
            scale = 1
            ref_widths[tile_id] = rect_width
        else:
            medium_width = medium_reference_widths.get(tile_id)
            if not medium_width or rect_width % medium_width:
                raise ValueError("collision tile rectangles lack integer resolution scale")
            scale = rect_width // medium_width
        row = _compare_polygon_to_alpha(image, record, shape, scale)
        row["tile_id"] = tile_id
        row["cells_using_tile_in_selected_map"] = cells
        rows.append(row)
        total["intersection"] += row["intersection_pixels"]
        total["union"] += row["union_pixels"]
        total["mismatch"] += row["pixel_mismatches"]
        total["pixels"] += row["atlas_pixels"]

    return {
        "screen": screen,
        "tiles": rows,
        "used_tile_frequencies": dict(sorted(selected.items())),
        "tileset_names": inventory["tileset_names"],
        "shape_content_sha256_by_id": {
            i: hashlib.sha256(raw).hexdigest()
            for i, raw in inventory["geometry_bytes"].items()
            if i in selected
        },
        "medium_reference_widths": ref_widths,
        "incomplete_or_nonaligned_used_shape_count": incomplete,
        "used_named_shape_count": inventory["shape_reference_counts"][
            "used_named_tile_ids"
        ],
        "atlas_pixels_compared": total["pixels"],
        "intersection_pixels": total["intersection"],
        "union_pixels": total["union"],
        "mismatched_pixels": total["mismatch"],
        "aggregate_polygon_alpha_iou": (
            1.0 if not total["union"] else total["intersection"] / total["union"]
        ),
    }


def inspect_private_geometry_alpha_parity(ipa: Path, map_name: str) -> dict:
    if not ipa.is_file() or ipa.is_symlink():
        raise ValueError("IPA must be an existing regular non-symlink file")
    from .collision_geometry_name_link import inspect_private_collision_geometry_names
    # Reuse the Stage265 structural/name/byte-parity contract.
    lineage = inspect_private_collision_geometry_names(ipa, map_name)
    if lineage["result"] != "cross_screen_shape_reference_census_complete":
        raise ValueError("collision geometry reference packs fail Stage265 parity")
    with zipfile.ZipFile(ipa, "r") as archive:
        medium = _screen(archive, SCREENS[0], map_name, None)
        large = _screen(
            archive, SCREENS[1], map_name, medium["medium_reference_widths"]
        )
    if medium["tileset_names"] != large["tileset_names"]:
        raise ValueError("medium/xlarge serialized shape names differ")
    if medium["used_tile_frequencies"] != large["used_tile_frequencies"]:
        raise ValueError("collision tile frequencies differ across screen packs")
    if medium["shape_content_sha256_by_id"] != large["shape_content_sha256_by_id"]:
        raise ValueError("linked shape resources differ across screen packs")
    a, b = medium["tiles"], large["tiles"]
    if [t["tile_id"] for t in a] != [t["tile_id"] for t in b]:
        raise ValueError("raster-compared shape IDs diverge across packs")

    def sanitize(screen: dict) -> dict:
        return {
            "screen": screen["screen"],
            "linked_used_shapes": screen["used_named_shape_count"],
            "raster_compared_polygon_count": len(screen["tiles"]),
            "unresolved_used_shape_count": screen[
                "incomplete_or_nonaligned_used_shape_count"
            ],
            "atlas_pixels_compared": screen["atlas_pixels_compared"],
            "intersection_pixels": screen["intersection_pixels"],
            "union_pixels": screen["union_pixels"],
            "mismatched_pixels": screen["mismatched_pixels"],
            "aggregate_polygon_alpha_iou": screen["aggregate_polygon_alpha_iou"],
            "polygons": screen["tiles"],
        }

    return {
        "schema": "heman-stage266-polygon-atlas-alpha-comparison-v1",
        "map_name": map_name,
        "source_ipa": {
            "size_bytes": ipa.stat().st_size,
            "sha256": lineage["source_ipa"]["sha256"],
        },
        "screen_med": sanitize(medium),
        "screen_xlarge": sanitize(large),
        "cross_screen": {
            "map_bytes_equal": lineage["cross_screen"]["map_bytes_exactly_equal"],
            "tileset_names_equal": True,
            "linked_used_geometry_bytes_equal": True,
            "same_used_polygon_ids": True,
        },
        "result": "polygon_alpha_comparison_complete",
        "original_geometry_vertices_or_bitmap_exported": False,
        "polygon_and_image_overlap_is_runtime_collisions_proof": False,
        "original_collision_material_or_one_way_rules_verified": False,
        "original_runtime_geometry_loader_path_verified": False,
        "original_ios_gameplay_trace_compared": False,
        "native_switch_collision_import_authorized": False,
        "interpretation_boundary": (
            "Even high polygon/alpha IoU is visual alignment evidence, not proof "
            "of the original runtime collider, object placement or one-way/solid "
            "collision semantics. Polygon raster fill uses pixel centers and a "
            "128/255 alpha threshold; no inferred physics rule is imported."
        ),
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ipa", type=Path, required=True)
    p.add_argument("--map", default="MUMap1-1.map")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    report_path = private_output_path(args.out)
    report = inspect_private_geometry_alpha_parity(args.ipa, args.map)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("Stage266 polygon/alpha metrics saved privately; collision rules remain unverified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
