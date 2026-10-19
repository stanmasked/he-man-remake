"""Local-only statistics for candidate .map collision tiles.

Occupancy is NOT evidence of solidity, slope geometry or gameplay behavior.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import zipfile

from .tilemap import MAX_FILE, TileMap, TileMapFormatError, parse_tilemap

SIDES = ("N", "E", "S", "W")


def summarize_collision_layer(tilemap: TileMap) -> dict:
    """Count atlas/tile pairs and occupancy-only four-neighbor relationships."""
    layer = tilemap.layer("collision")
    width, height = layer.columns, layer.rows
    cells = width * height
    if len(layer.tile_ids) != cells or len(layer.atlas_ids) != cells:
        raise ValueError("inconsistent tile and atlas grids")
    occupied = [tile != 0xffff for tile in layer.tile_ids]
    counts = Counter()
    histograms = defaultdict(Counter)
    exposed = defaultdict(Counter)
    for pos, tile in enumerate(layer.tile_ids):
        if not occupied[pos]:
            continue  # stale atlas indices in empty cells are permitted
        atlas = layer.atlas_ids[pos]
        if atlas >= len(layer.atlases):
            raise TileMapFormatError("occupied tile has invalid atlas")
        key = (atlas, tile)
        counts[key] += 1
        x, y = pos % width, pos // width
        neighbors = (
            y > 0 and occupied[pos-width],
            x + 1 < width and occupied[pos+1],
            y + 1 < height and occupied[pos+width],
            x > 0 and occupied[pos-1],
        )
        histograms[key][sum(neighbors)] += 1
        for side, filled in zip(SIDES, neighbors):
            if not filled:
                exposed[key][side] += 1

    results = []
    for atlas, tile in sorted(counts):
        key = (atlas, tile)
        results.append({
            "atlas_index": atlas,
            "atlas_name": layer.atlases[atlas],
            "tile_id": tile,
            "cells": counts[key],
            "occupied_neighbor_counts": [histograms[key][i] for i in range(5)],
            "sides_next_to_empty_or_boundary": {
                side: exposed[key][side] for side in SIDES
            },
        })
    filled = sum(counts.values())
    return {
        "layer": "collision",
        "columns": width,
        "rows": height,
        "tile_width": layer.tile_width,
        "tile_height": layer.tile_height,
        "occupied_cells": filled,
        "empty_cells": cells - filled,
        "distinct_atlas_tile_pairs": len(results),
        "tiles": results,
        "interpretation": (
            "Occupancy-only statistics: solidness, slopes, one-way behavior, "
            "hazards, object ownership and collision hitboxes NOT established."
        ),
    }


def scan_local_ipa(ipa: Path, name: str, screen: str = "screen-med") -> dict:
    """Read a single map entry from a private local IPA without extraction."""
    if (not isinstance(name, str) or not name.endswith(".map") or
            len(name) <= 4 or "/" in name or "\\" in name or
            "\x00" in name or "\n" in name or "\r" in name):
        raise ValueError("expected a simple .map basename")
    if screen not in ("screen-med", "screen-xlarge"):
        raise ValueError("unsupported screen group")
    entry = f"Payload/MOTU.app/{screen}/maps/{name}"
    with zipfile.ZipFile(ipa, "r") as archive:
        matches = [v for v in archive.infolist() if v.filename == entry]
        if len(matches) != 1:
            raise ValueError("expected exactly one map entry")
        info = matches[0]
        if info.file_size > MAX_FILE:
            raise TileMapFormatError("oversized input map")
        parsed = parse_tilemap(archive.read(info))
    return {"map": name, "screen": screen, **summarize_collision_layer(parsed)}



def compare_screen_pair(ipa: Path, name: str) -> dict:
    """Check exact screen-med versus screen-xlarge .map bytes, privately.

    Matching aggregate statistics alone can hide different cell placement,
    so exact source-byte equality is an independent, stricter gate.
    """
    med = scan_local_ipa(ipa, name, "screen-med")
    large = scan_local_ipa(ipa, name, "screen-xlarge")
    with zipfile.ZipFile(ipa, "r") as archive:
        paths = (
            f"Payload/MOTU.app/screen-med/maps/{name}",
            f"Payload/MOTU.app/screen-xlarge/maps/{name}",
        )
        a, b = (archive.read(filename) for filename in paths)
    same_inventory = ({k: v for k, v in med.items() if k != "screen"} ==
                      {k: v for k, v in large.items() if k != "screen"})
    return {
        "map": name,
        "screen_pair": ["screen-med", "screen-xlarge"],
        "exact_map_bytes_match": a == b,
        "collision_inventory_match": same_inventory,
        "screen_med_occupied_cells": med["occupied_cells"],
        "screen_xlarge_occupied_cells": large["occupied_cells"],
        "interpretation": (
            "Byte equality and occupancy summary agreement are structural "
            "checks only; neither establishes original collision semantics."
        ),
    }


def private_output_path(path: Path) -> Path:
    """Require an ignored local_reports JSON path, not a tracked repository file."""
    local_root = Path.cwd() / "local_reports"
    if local_root.is_symlink():
        raise ValueError("local_reports must not be a symbolic link")
    root = local_root.resolve()
    dest = path.resolve()
    if dest == root or not dest.is_relative_to(root) or dest.suffix != ".json":
        raise ValueError("output must be .json beneath local_reports/")
    return dest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", required=True, type=Path)
    parser.add_argument("--map", dest="name", required=True)
    parser.add_argument("--screen", choices=("screen-med", "screen-xlarge"),
                        default="screen-med")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--compare-screens", action="store_true",
                        help="check same map in both iOS screen resource packs")
    args = parser.parse_args(argv)
    out = private_output_path(args.out)
    if args.compare_screens:
        if args.screen != "screen-med":
            parser.error("--screen is not used with --compare-screens")
        report = compare_screen_pair(args.ipa, args.name)
    else:
        report = scan_local_ipa(args.ipa, args.name, args.screen)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    if args.compare_screens:
        print("Compared both private screen map packs; "
              "structural result saved under local_reports/")
    else:
        print(f"Analysed {report['occupied_cells']} candidate cells; "
              "details saved privately under local_reports/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
