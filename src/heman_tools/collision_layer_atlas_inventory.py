"""Private aggregate inventory of atlas routing inside collision-named map layers.

The output contains aggregate counts only. Layer names and nonempty cells do
not establish solidity or any other original gameplay behavior.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import stat
import zipfile

from .tilemap import MAX_FILE as MAX_MAP_BYTES, TileMapFormatError, parse_tilemap

MAX_MAPS = 1000
SPECIAL_FORMAT_MAP = "gs_background_sky.map"


def _safe_map_name(name: str) -> bool:
    return (
        isinstance(name, str) and 1 < len(name) <= 256
        and name.endswith(".map") and "/" not in name and "\\" not in name
        and all(char not in name for char in ("\x00", "\n", "\r"))
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _map_entry_index(archive: zipfile.ZipFile, screen: str) -> dict[str, zipfile.ZipInfo]:
    prefix = f"Payload/MOTU.app/{screen}/maps/"
    result = {}
    for info in archive.infolist():
        if not info.filename.startswith(prefix) or not info.filename.endswith(".map"):
            continue
        name = info.filename[len(prefix):]
        if not _safe_map_name(name):
            raise ValueError("map entry is not a simple basename")
        if name in result:
            raise ValueError("duplicate map entry")
        mode = (info.external_attr >> 16) & 0xffff
        if stat.S_ISLNK(mode):
            raise ValueError("symbolic-link map entry is not accepted")
        if info.file_size < 1 or info.file_size > MAX_MAP_BYTES:
            raise ValueError("map entry size outside permitted bounds")
        result[name] = info
        if len(result) > MAX_MAPS:
            raise ValueError("too many map entries")
    if not result:
        raise ValueError(f"no map entries found for {screen}")
    return result


def _read_info(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes:
    raw = archive.read(info)
    if len(raw) != info.file_size:
        raise ValueError("map entry size mismatch")
    return raw


def audit_collision_atlas_routing(ipa: Path) -> dict:
    """Compare both screen packs and count aggregate atlas usage in collision layers."""
    with zipfile.ZipFile(ipa, "r") as archive:
        med_entries = _map_entry_index(archive, "screen-med")
        large_entries = _map_entry_index(archive, "screen-xlarge")
        if set(med_entries) != set(large_entries):
            raise ValueError("screen packs have different map filename sets")

        tileset_prefix = "Payload/MOTU.app/screen-med/tilesets/"
        tileset_stems = set()
        for info in archive.infolist():
            if not info.filename.startswith(tileset_prefix) or not info.filename.endswith(".tileset"):
                continue
            stem = info.filename[len(tileset_prefix):-len(".tileset")]
            if "/" in stem or not stem:
                raise ValueError("unexpected nested tileset path")
            if stem in tileset_stems:
                raise ValueError("duplicate tileset entry")
            tileset_stems.add(stem)

        atlas_cells = Counter()
        atlas_tile_counts = defaultdict(Counter)
        atlas_maps = defaultdict(set)
        total_occupied = 0
        collision_layers = 0
        normal_maps_parsed = 0
        exact_pairs = 0
        special_present = 0
        special_equal = None

        for name in sorted(med_entries):
            med_raw = _read_info(archive, med_entries[name])
            large_raw = _read_info(archive, large_entries[name])
            exact = med_raw == large_raw
            if exact:
                exact_pairs += 1
            if name == SPECIAL_FORMAT_MAP:
                special_present += 1
                special_equal = exact
                # This one known resource uses a different format and is excluded
                # from the normal multilayer parser in both screen packs.
                continue
            if not exact:
                raise ValueError("unexpected cross-screen map byte divergence")
            try:
                parsed = parse_tilemap(med_raw)
            except (TileMapFormatError, UnicodeDecodeError) as exc:
                raise ValueError(f"unsupported non-special map format: {type(exc).__name__}") from exc
            normal_maps_parsed += 1
            found = [layer for layer in parsed.layers if layer.name.casefold() == "collision"]
            if len(found) > 1:
                raise ValueError("duplicate collision-named layer in map")
            if not found:
                continue
            collision_layers += 1
            layer = found[0]
            occupied_in_layer = 0
            for tile_id, atlas_id in zip(layer.tile_ids, layer.atlas_ids):
                if tile_id == 0xffff:
                    continue
                occupied_in_layer += 1
                atlas_name = layer.atlases[atlas_id]
                atlas_cells[atlas_name] += 1
                atlas_tile_counts[atlas_name][tile_id] += 1
                atlas_maps[atlas_name].add(name)
            total_occupied += occupied_in_layer

    if special_present not in (0, 1):
        raise ValueError("expected at most one known special-format map pair")
    if normal_maps_parsed != len(med_entries) - special_present:
        raise ValueError("normal map count does not reconcile")

    atlas_usage = []
    for atlas_name, cells in sorted(atlas_cells.items(), key=lambda item: (-item[1], item[0])):
        tile_counts = atlas_tile_counts[atlas_name]
        atlas_usage.append({
            "atlas_name": atlas_name,
            "occupied_cells": cells,
            "maps_using_atlas": len(atlas_maps[atlas_name]),
            "distinct_tile_ids": len(tile_counts),
            "tile_id_frequencies": {str(tile_id): count for tile_id, count in sorted(tile_counts.items())},
            "same_stem_tileset_present": atlas_name in tileset_stems,
        })

    cells_on_collision_named_atlas = atlas_cells.get("collision", 0)
    report = {
        "schema": "heman-collision-layer-atlas-routing-v1",
        "source_ipa": {
            "name": ipa.name,
            "size_bytes": ipa.stat().st_size,
            "sha256": _sha256_file(ipa),
        },
        "screen_pack_map_pair_audit": {
            "screen_med_map_files": len(med_entries),
            "screen_xlarge_map_files": len(large_entries),
            "paired_map_files": len(set(med_entries) & set(large_entries)),
            "exact_byte_equal_map_pairs": exact_pairs,
            "known_special_format_map_pairs_skipped": special_present,
            "known_special_format_pair_byte_equal": special_equal,
            "normal_multilayer_maps_parsed": normal_maps_parsed,
        },
        "collision_layer_summary": {
            "collision_named_layers": collision_layers,
            "occupied_cells": total_occupied,
            "cells_on_atlas_named_collision": cells_on_collision_named_atlas,
            "cells_on_other_atlases": total_occupied - cells_on_collision_named_atlas,
            "distinct_atlas_names": len(atlas_usage),
            "atlas_usage": atlas_usage,
        },
        "unresolved_direct_tileset_stem_aliases": [
            row["atlas_name"] for row in atlas_usage if not row["same_stem_tileset_present"]
        ],
        "original_collision_semantics_verified": False,
        "original_ios_gameplay_trace_compared": False,
        "native_switch_collision_import_authorized": False,
        "interpretation_boundary": (
            "This inventory measures atlas routing and tile-ID frequency only. "
            "A layer named collision may reference other atlas names; neither occupancy "
            "nor an atlas name proves solidity, slopes, one-way behavior, hazards, "
            "sensor behavior, object ownership or original runtime collision semantics."
        ),
    }
    return report


def private_output_path(path: Path) -> Path:
    """Require ignored local_reports JSON output; reject symlinked paths."""
    root_path = Path.cwd() / "local_reports"
    if root_path.is_symlink():
        raise ValueError("local_reports must not be a symbolic link")
    root = root_path.resolve()
    destination = path.resolve()
    if destination == root or not destination.is_relative_to(root) or destination.suffix != ".json":
        raise ValueError("output must be a .json file beneath local_reports/")
    if path.is_symlink():
        raise ValueError("output must not be a symbolic link")
    return destination


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", required=True, type=Path, help="owner-held IPA; read in memory only")
    parser.add_argument("--out", required=True, type=Path, help="JSON output beneath ignored local_reports/")
    args = parser.parse_args(argv)
    if not args.ipa.is_file() or args.ipa.is_symlink():
        parser.error("--ipa must be an existing regular non-symlink file")
    try:
        output = private_output_path(args.out)
        report = audit_collision_atlas_routing(args.ipa)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                          encoding="utf-8")
    except (OSError, zipfile.BadZipFile, TileMapFormatError, ValueError, KeyError) as exc:
        parser.error(f"collision atlas routing audit failed: {type(exc).__name__}: {exc}")
    print(
        f"Stage258 parsed {report['screen_pack_map_audit']['normal_multilayer_maps_parsed']} "
        f"normal maps and {report['collision_layer_summary']['collision_named_layers']} "
        "collision layers; private aggregate saved under local_reports/"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
