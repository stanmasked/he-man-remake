"""Private lexical join: collision tileset names to geometry resource members.

An exact resource-name match is direct serialization evidence, not proof of
runtime object binding, collision response or pixel-alpha use.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import zipfile

from .collision_atlas_alpha import (
    MAX_TILESET_BYTES, _read_archive_entry, parse_tileset, private_output_path
)
from .tilemap import MAX_FILE as MAX_MAP_BYTES, parse_tilemap

SCREENS = ("screen-med", "screen-xlarge")
PREFIX = "Payload/MOTU.app/"
MAX_MEMBERS = 100_000
MAX_GEOMETRY_BYTES = 1_000_000
MAX_SELECTED_GEOMETRY_BYTES = 16_000_000
SHAPE_NAME = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")


def _screen_inventory(archive: zipfile.ZipFile, screen: str, map_name: str) -> dict:
    root = PREFIX + screen + "/"
    map_bytes = _read_archive_entry(
        archive, root + "maps/" + map_name, MAX_MAP_BYTES
    )
    tileset_bytes = _read_archive_entry(
        archive, root + "tilesets/collision.tileset", MAX_TILESET_BYTES
    )
    tilemap = parse_tilemap(map_bytes)
    collision = tilemap.layer("collision")
    indexes = [i for i, name in enumerate(collision.atlases)
               if name == "collision"]
    if len(indexes) != 1:
        raise ValueError("expected one collision atlas in the selected layer")
    atlas_id = indexes[0]
    metadata = parse_tileset(tileset_bytes)
    tiles = metadata["entries"]
    counts = Counter()
    noncollision = 0
    for tile_id, atlas in zip(collision.tile_ids, collision.atlas_ids):
        if tile_id == 65535:
            continue
        if atlas == atlas_id:
            if tile_id >= len(tiles):
                raise ValueError("occupied collision tile ID exceeds tileset records")
            counts[tile_id] += 1
        else:
            noncollision += 1

    exact = {}
    missing = []
    near = []
    named = 0
    total_geometry_bytes = 0
    for entry in tiles:
        name = entry["name"]
        if not name:
            continue
        named += 1
        if not SHAPE_NAME.fullmatch(name):
            raise ValueError("unsafe or malformed geometry reference in tileset")
        expected = root + "geometry/" + name + ".shape"
        members = [info for info in archive.infolist() if info.filename == expected]
        if len(members) > 1:
            raise ValueError("duplicate geometry archive member")
        if members:
            raw = _read_archive_entry(archive, expected, MAX_GEOMETRY_BYTES)
            total_geometry_bytes += len(raw)
            if total_geometry_bytes > MAX_SELECTED_GEOMETRY_BYTES:
                raise ValueError("selected geometry exceeds read-only byte budget")
            exact[entry["ordinal"]] = raw
        else:
            missing.append(entry["ordinal"])
            # Diagnostic only: a malformed filename cannot be silently
            # normalized into a valid resource reference.
            alternative = root + "geometry/" + name + "shape"
            if any(info.filename == alternative for info in archive.infolist()):
                near.append(entry["ordinal"])

    used_ids = set(counts)
    named_ids = {x["ordinal"] for x in tiles if x["name"]}
    return {
        "map_bytes": map_bytes,
        "tileset_names": tuple(e["name"] for e in tiles),
        "geometry_bytes": exact,
        "used_frequencies": dict(sorted(counts.items())),
        "shape_reference_counts": {
            "tileset_records": len(tiles),
            "named_records": named,
            "unnamed_records": len(tiles) - named,
            "named_with_exact_geometry_member": len(exact),
            "named_without_exact_geometry_member": len(missing),
            "missing_named_with_dot_before_extension_anomaly": len(near),
            "distinct_used_collision_tile_ids": len(used_ids),
            "used_named_tile_ids": len(used_ids & named_ids),
            "used_unnamed_tile_ids": len(used_ids - named_ids),
            "used_named_with_exact_geometry_member": len(used_ids & set(exact)),
            "used_named_without_exact_geometry_member": len(
                (used_ids & named_ids) - set(exact)
            ),
            "occupied_cells_in_selected_collision_atlas": sum(counts.values()),
            "occupied_cells_on_other_atlases": noncollision,
        },
    }


def inspect_private_collision_geometry_names(ipa: Path, map_name: str) -> dict:
    if not ipa.is_file() or ipa.is_symlink():
        raise ValueError("expected existing regular owner-held IPA")
    if not isinstance(map_name, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,120}\.map", map_name):
        raise ValueError("expected simple map basename")
    with zipfile.ZipFile(ipa, "r") as archive:
        members = archive.infolist()
        if len(members) > MAX_MEMBERS:
            raise ValueError("IPA has too many archive members")
        if len({x.filename for x in members}) != len(members):
            raise ValueError("duplicate archive entries")
        inventories = {screen: _screen_inventory(archive, screen, map_name)
                       for screen in SCREENS}

    med, large = [inventories[s] for s in SCREENS]
    names_match = med["tileset_names"] == large["tileset_names"]
    map_equal = med["map_bytes"] == large["map_bytes"]
    exact_ids_match = med["geometry_bytes"].keys() == large["geometry_bytes"].keys()
    geometry_equal = exact_ids_match and all(
        med["geometry_bytes"][tile_id] == large["geometry_bytes"][tile_id]
        for tile_id in med["geometry_bytes"]
    )
    frequency_equal = med["used_frequencies"] == large["used_frequencies"]
    metrics_equal = med["shape_reference_counts"] == large["shape_reference_counts"]
    result = ("cross_screen_shape_reference_census_complete"
              if names_match and map_equal and exact_ids_match
              and geometry_equal and frequency_equal and metrics_equal
              else "cross_screen_shape_reference_divergence")
    return {
        "schema": "heman-stage265-collision-tile-to-geometry-name-v1",
        "map_name": map_name,
        "source_ipa": {
            "size_bytes": ipa.stat().st_size,
            "sha256": _sha256_file(ipa),
        },
        "screen_med": med["shape_reference_counts"],
        "screen_xlarge": large["shape_reference_counts"],
        "cross_screen": {
            "map_bytes_exactly_equal": map_equal,
            "tileset_name_order_equal": names_match,
            "used_tile_id_frequencies_equal": frequency_equal,
            "exact_geometry_member_id_sets_equal": exact_ids_match,
            "exactly_named_shape_bytes_identical": geometry_equal,
            "summary_counts_equal": metrics_equal,
        },
        "result": result,
        "source_shape_names_paths_and_raw_bytes_in_report": False,
        "named_resource_exact_match_is_runtime_binding_proof": False,
        "collision_shape_object_type_verified": False,
        "original_collision_alpha_usage_verified": False,
        "original_collision_response_verified": False,
        "original_ios_gameplay_trace_compared": False,
        "native_switch_collision_import_authorized": False,
        "interpretation_boundary": (
            "Exact file-name matching between serialized tiles and geometry resources "
            "establishes only a static lexical link. It does not establish runtime "
            "loading, collider types, slope behavior, one-way collision or source "
            "pixel-alpha use. Missing extension-dot candidates remain unresolved."
        ),
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ipa", required=True, type=Path)
    p.add_argument("--map", default="MUMap1-1.map")
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args(argv)
    dest = private_output_path(args.out)
    report = inspect_private_collision_geometry_names(args.ipa, args.map)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print("Stage265 collision geometry-name audit saved privately; runtime loading remains unverified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
