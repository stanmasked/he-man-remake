"""Read-only connected-component topology of a private iOS collision layer.

Occupied != solid. Grid adjacency does NOT establish slopes, one-way
platforms, spikes, hazards, hitboxes, or source-game movement physics.
Private component bounds must never be added to public source fixtures.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import stat
import zipfile

from .collision_inventory import private_output_path
from .tilemap import MAX_FILE, TileMap, parse_tilemap

SCREENS = ("screen-med", "screen-xlarge")
DIRECTIONS = (("N", 0, -1), ("E", 1, 0),
              ("S", 0, 1), ("W", -1, 0))
MAX_COMPONENTS = 4096


def summarize_topology(source: TileMap) -> dict:
    """Four-connected occupancy only, with private per-component bounds."""
    layer = source.layer("collision")  # fail if missing or duplicated
    width, height = layer.columns, layer.rows
    count = width * height
    if not (0 < count <= 100000
            and len(layer.tile_ids) == count and len(layer.atlas_ids) == count):
        raise ValueError("inconsistent collision grid")
    occupied = bytearray(int(tile != 65535) for tile in layer.tile_ids)
    for pos, filled in enumerate(occupied):
        if filled and (layer.atlas_ids[pos] >= len(layer.atlases)
                       or not 0 <= layer.tile_ids[pos] <= 65534):
            raise ValueError("occupied cell has invalid atlas or tile ID")
    visited = bytearray(count)
    components = []
    edges_total = Counter({key: 0 for key, _, _ in DIRECTIONS})
    tile_total = Counter()
    atlas_total = Counter()
    for start, present in enumerate(occupied):
        if not present or visited[start]:
            continue
        if len(components) >= MAX_COMPONENTS:
            raise ValueError("too many isolated occupancy components")
        visited[start] = 1
        stack = [start]
        component_edges = Counter({key: 0 for key, _, _ in DIRECTIONS})
        component_tile_ids = Counter()
        component_atlases = Counter()
        component_cells = 0
        min_x, max_x = width, -1
        min_y, max_y = height, -1
        while stack:
            pos = stack.pop()
            x, y = pos % width, pos // width
            component_cells += 1
            min_x, max_x = min(min_x, x), max(max_x, x)
            min_y, max_y = min(min_y, y), max(max_y, y)
            tile_id = layer.tile_ids[pos]
            atlas_id = layer.atlas_ids[pos]
            component_tile_ids[tile_id] += 1
            component_atlases[atlas_id] += 1
            tile_total[tile_id] += 1
            atlas_total[atlas_id] += 1
            for side, dx, dy in DIRECTIONS:
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    other = ny * width + nx
                    if occupied[other]:
                        if not visited[other]:
                            visited[other] = 1
                            stack.append(other)
                        continue
                component_edges[side] += 1
                edges_total[side] += 1
        components.append({
            "component_index": len(components),
            "occupied_cells": component_cells,
            "bbox_inclusive_xyxy": [min_x, min_y, max_x, max_y],
            "exposed_grid_edges": {side: component_edges[side]
                                   for side, _, _ in DIRECTIONS},
            "distinct_tile_ids": len(component_tile_ids),
            "distinct_atlas_ids": len(component_atlases),
            "tile_counts": {str(key): n
                            for key, n in sorted(component_tile_ids.items())},
        })

    n_occupied = sum(occupied)
    exposed = sum(edges_total.values())
    # Every shared cardinal edge subtracts two from the four-edge total.
    neighbor_pairs = 0
    for pos, filled in enumerate(occupied):
        if not filled:
            continue
        x, y = pos % width, pos // width
        if x + 1 < width and occupied[pos + 1]:
            neighbor_pairs += 1
        if y + 1 < height and occupied[pos + width]:
            neighbor_pairs += 1
    if (sum(c["occupied_cells"] for c in components) != n_occupied
            or exposed != 4 * n_occupied - 2 * neighbor_pairs):
        raise ValueError("inconsistent connected-component accounting")

    return {
        "columns": width,
        "rows": height,
        "tile_size": [layer.tile_width, layer.tile_height],
        "occupied_cells": n_occupied,
        "empty_cells": count - n_occupied,
        "component_count_4_connected": len(components),
        "largest_component_cells": max(
            (c["occupied_cells"] for c in components), default=0),
        "singleton_components": sum(
            c["occupied_cells"] == 1 for c in components),
        "adjacent_occupied_edge_pairs": neighbor_pairs,
        "exposed_grid_edges_total": exposed,
        "exposed_grid_edges_by_side": {
            side: edges_total[side] for side, _, _ in DIRECTIONS},
        "tile_id_counts": {str(key): n for key, n in sorted(tile_total.items())},
        "atlas_id_counts": {str(key): n for key, n in sorted(atlas_total.items())},
        "components": components,
        "collision_categories_verified": False,
        "coordinate_alignment_verified": False,
        "original_gameplay_physics_verified": False,
        "automatic_collision_export_permitted": False,
        "interpretation": (
            "Four-connected nonempty tile topology only. This is not "
            "proof of solidity, slopes, one-way platforms or hazards."
        ),
    }


def inspect_private_pair(ipa: Path, map_name: str = "MUMap1-1.map") -> dict:
    """Read only two selected map files from a local, personally held IPA."""
    if (not isinstance(map_name, str) or len(map_name) <= 4
            or len(map_name) > 255 or not map_name.endswith(".map")
            or "/" in map_name or "\\" in map_name
            or not map_name.isprintable()):
        raise ValueError("expected a simple .map basename")
    reports = {}
    binaries = {}
    with zipfile.ZipFile(ipa) as archive:
        entries = archive.infolist()
        if len(entries) > 100000:
            raise ValueError("excessive ZIP member count")
        for screen in SCREENS:
            name = f"Payload/MOTU.app/{screen}/maps/{map_name}"
            found = [member for member in entries if member.filename == name]
            if len(found) != 1:
                raise ValueError("expected exactly one map in each screen pack")
            entry = found[0]
            if (entry.is_dir() or entry.flag_bits & 1
                    or stat.S_IFMT(entry.external_attr >> 16) == stat.S_IFLNK
                    or not 4 <= entry.file_size <= MAX_FILE):
                raise ValueError("invalid, encrypted or oversized selected map")
            data = archive.read(entry)  # validates CRC without extraction
            binaries[screen] = data
            reports[screen] = summarize_topology(parse_tilemap(data))
    same = binaries[SCREENS[0]] == binaries[SCREENS[1]]
    consistent = reports[SCREENS[0]] == reports[SCREENS[1]]
    return {
        "map": map_name,
        "screen_packs": list(SCREENS),
        "source_map_bytes_identical": same,
        "derived_topology_identical": consistent,
        "screens": reports,
        "runtime_collision_type_verified": False,
        "automatic_collision_export_permitted": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", required=True, type=Path)
    parser.add_argument("--map", dest="map_name", default="MUMap1-1.map")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    destination = private_output_path(args.out)
    report = inspect_private_pair(args.ipa, args.map_name)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print("Saved private occupancy-topology report; no collision mask exported.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
