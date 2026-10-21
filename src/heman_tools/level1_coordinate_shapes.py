"""Private Level1-1 coordinate-envelope and shape-library evidence.

Candidate tile/object coordinate envelopes are *hypotheses*, NOT verified
physics or screen transforms. Do not export individual original object
positions, shapes, vertex arrays, source filenames, or resource links.
"""
from __future__ import annotations

import argparse
import json
import math
import stat
from pathlib import Path, PurePosixPath
from zipfile import ZipFile, ZipInfo

from .collision_inventory import private_output_path
from .objects import ParsedLevel, parse_level_objects
from .shapes import parse_shape
from .tilemap import TileMap, parse_tilemap

LEVEL_PATH = "levels/MULevel1-1.lvl"
MAP_PATH = "maps/MUMap1-1.map"
SCREEN = ("screen-med", "screen-xlarge")
PREFIX = "Payload/MOTU.app/"
MAX_LEVEL = 8_000_000
MAX_MAP = 16_000_000
MAX_SHAPE = 1_000_000
MAX_SHAPES = 2048
MAX_SHAPE_TOTAL = 32_000_000


def candidate_object_envelopes(level: ParsedLevel, source: TileMap) -> dict:
    """Numerical *containment* only; not proof of object-to-map alignment."""
    grid = source.layer("collision")
    if grid.columns <= 0 or grid.rows <= 0 or (
        not 1 <= grid.tile_width <= 4096 or not 1 <= grid.tile_height <= 4096
    ):
        raise ValueError("Invalid candidate collision grid")
    if not 0 < len(level.objects) <= 100000:
        raise ValueError("Object table cannot be empty or excessive")
    points = [(o.x, o.y) for o in level.objects]
    if any(not math.isfinite(x) or not math.isfinite(y) for x,y in points):
        raise ValueError("Nonfinite original object transform")
    def within(xextent, yextent):
        return sum(0 <= x < xextent and 0 <= y < yextent for x,y in points)
    pixel_extent = within(grid.columns*grid.tile_width,
                          grid.rows*grid.tile_height)
    index_extent = within(grid.columns, grid.rows)
    out_x = sum(not 0 <= x < grid.columns*grid.tile_width for x,y in points)
    out_y = sum(not 0 <= y < grid.rows*grid.tile_height for x,y in points)
    return {
        "candidate_pixel_units_origin_zero": {
            "objects_within_candidate_extent": pixel_extent,
            "objects_outside_candidate_extent": len(points)-pixel_extent,
            "outside_x_extent": out_x,
            "outside_y_extent": out_y,
        },
        "candidate_direct_cell_indices_origin_zero": {
            "objects_within_candidate_extent": index_extent,
            "objects_outside_candidate_extent": len(points)-index_extent,
        },
        "level_object_count": len(points),
        "tile_grid_columns": grid.columns,
        "tile_grid_rows": grid.rows,
        "cell_width_units_as_serialized": grid.tile_width,
        "cell_height_units_as_serialized": grid.tile_height,
        "object_to_collision_scale_verified": False,
        "map_coordinate_origin_verified": False,
        "camera_projection_verified": False,
        "automatically_usable_collision_geometry": False,
    }


def aggregate_shape_links(
    level: ParsedLevel,
    matched_shapes: list[tuple[str, bytes]],
    ) -> dict:
    """Purely lexical candidate counts; does not bind shapes to object hitboxes."""
    if len(matched_shapes) > MAX_SHAPES:
        raise ValueError("Too many shape files")
    if len({name for name,_ in matched_shapes}) != len(matched_shapes):
        raise ValueError("Duplicate shape basenames")
    identifiers = set()
    text_properties = set()
    for obj in level.objects:
        identifiers.update((obj.class_name, obj.group_name, obj.instance_name))
        for prop in obj.properties:
            if prop.kind == "string" and isinstance(prop.value, str):
                text_properties.add(prop.value)
    identifiers.discard("")
    text_properties.discard("")
    references = 0
    names_matching = 0
    refs_matching = 0
    props_matching = 0
    kinds = {"polygon": 0, "circle": 0}
    for name, raw in matched_shapes:
        if not isinstance(name, str) or not name.endswith(".shape") or (
            len(name) <= 6 or "/" in name or "\\" in name
        ):
            raise ValueError("Invalid shape basename")
        if not isinstance(raw, bytes) or len(raw) > MAX_SHAPE:
            raise ValueError("Unsafe shape payload")
        parsed = parse_shape(raw)
        kinds[parsed.kind] += 1
        stem = name[:-6]
        names_matching += stem in identifiers
        props_matching += stem in text_properties
        if parsed.reference:
            references += 1
            refs_matching += parsed.reference in identifiers
    return {
        "paired_shape_library_entries": len(matched_shapes),
        "decoded_polygons": kinds["polygon"],
        "decoded_circles": kinds["circle"],
        "shape_entries_with_embedded_reference": references,
        "filename_stem_matching_level_object_identity": names_matching,
        "filename_stem_matching_level_text_property": props_matching,
        "embedded_reference_matching_level_object_identity": refs_matching,
        "original_shape_to_level_object_owner_verified": False,
        "original_player_hitbox_verified": False,
        "original_collision_shape_usage_verified": False,
    }


def _read(z: ZipFile, by_name: dict[str, ZipInfo], entry: str,
          max_size: int) -> bytes:
    info = by_name.get(entry)
    if (info is None or info.is_dir() or info.flag_bits & 1
            or not 1 <= info.file_size <= max_size
            or stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK):
        raise ValueError("Missing or unsafe required ZIP resource")
    result = z.read(info)
    if len(result) != info.file_size:
        raise ValueError("Truncated ZIP source member")
    return result


def audit_private_level1_geometry(ipa: Path) -> dict:
    """Read owned IPA privately, never extracting bytes or original geometry."""
    if not ipa.is_file():
        raise ValueError("Missing original local IPA")
    with ZipFile(ipa, "r") as z:
        entries = z.infolist()
        if len(entries) > 100000 or len({e.filename for e in entries}) != len(entries):
            raise ValueError("Duplicate/oversized ZIP index")
        by_name = {e.filename:e for e in entries}
        levels = [_read(z,by_name,PREFIX+s+"/"+LEVEL_PATH,MAX_LEVEL) for s in SCREEN]
        maps = [_read(z,by_name,PREFIX+s+"/"+MAP_PATH,MAX_MAP) for s in SCREEN]
        if levels[0] != levels[1] or maps[0] != maps[1]:
            raise ValueError("Source screen pack level/map bytes differ")
        parsed = parse_level_objects(levels[0])
        grid = parse_tilemap(maps[0])
        if parsed.level_name != "MULevel1-1.lvl":
            raise ValueError("Original Level1-1 name mismatch")
        scores = candidate_object_envelopes(parsed, grid)
        shapes = {}
        for s in SCREEN:
            prefix = PREFIX+s+"/geometry/"
            candidates = {
                PurePosixPath(n).name: n for n in by_name
                if n.startswith(prefix) and n.endswith(".shape") and
                   "/" not in n[len(prefix):]
            }
            if len(candidates) > MAX_SHAPES or not candidates:
                raise ValueError("Missing or excessive original shape library")
            size = sum(by_name[path].file_size for path in candidates.values())
            if size > MAX_SHAPE_TOTAL:
                raise ValueError("Shape library exceeds aggregate size bound")
            shapes[s] = {
                leaf: _read(z, by_name, path, MAX_SHAPE)
                for leaf,path in candidates.items()
            }
        if set(shapes[SCREEN[0]]) != set(shapes[SCREEN[1]]):
            raise ValueError("Original screen shape libraries have different members")
        if any(shapes[SCREEN[0]][name] != shapes[SCREEN[1]][name]
               for name in shapes[SCREEN[0]]):
            raise ValueError("Original screen shape libraries differ in bytes")
        links = aggregate_shape_links(parsed, sorted(shapes[SCREEN[0]].items()))
    return {
        "classification": "owner_private_level1_coordinate_and_shape_evidence",
        "source_screen_level_and_map_pairs_identical": True,
        "shape_library_both_screens_byte_identical": True,
        "object_coordinate_envelopes": scores,
        "shape_to_object_textual_candidates": links,
        "all_source_asset_bytes_remain_local": True,
        "original_game_coordinate_system_proven": False,
        "native_switch_world_geometry_import_authorized": False,
        "original_gameplay_parity_verified": False,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ipa", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)
    out = private_output_path(args.out)
    report = audit_private_level1_geometry(args.ipa)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report, sort_keys=True, indent=2)+"\n",
                   encoding="utf-8")
    print("Source-local coordinate and shape hypothesis counts recorded under ignored local_reports.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
