"""Private-only alpha census for collision-tile atlas candidates.

The tool reads original IPA entries in memory and writes only to ignored
local_reports/. Atlas alpha is image evidence, not proof of game physics.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import struct
import zipfile

from PIL import Image

from .tilemap import MAX_FILE as MAX_MAP_BYTES, TileMapFormatError, parse_tilemap

MAX_TILESET_BYTES = 1_000_000
MAX_TEXTURE_BYTES = 64_000_000
MAX_TEXTURE_PIXELS = 64_000_000
MAX_TILE_RECORDS = 4096
MAX_UTF16_UNITS = 512
MAX_MAP_NAME = 128
ALPHA_THRESHOLD = 128
CROSS_PACK_ALPHA_TOLERANCE = 0.02


class TileSetFormatError(ValueError):
    """Malformed or unsupported serialized .tileset resource."""


def _need(data: bytes, offset: int, size: int) -> None:
    if offset < 0 or size < 0 or offset + size > len(data):
        raise TileSetFormatError(f"truncated tileset at byte {offset}")


def _read_u32(data: bytes, offset: int) -> tuple[int, int]:
    _need(data, offset, 4)
    return struct.unpack_from("<I", data, offset)[0], offset + 4


def _read_text(data: bytes, offset: int, *, allow_empty: bool) -> tuple[str, int]:
    _need(data, offset, 2)
    units = struct.unpack_from("<H", data, offset)[0]
    offset += 2
    if units > MAX_UTF16_UNITS or (not allow_empty and units == 0):
        raise TileSetFormatError("invalid UTF-16 string length")
    size = units * 2
    _need(data, offset, size)
    try:
        value = data[offset:offset + size].decode("utf-16le", errors="strict")
    except UnicodeDecodeError as exc:
        raise TileSetFormatError("invalid UTF-16 string") from exc
    if any(ord(char) < 32 for char in value):
        raise TileSetFormatError("control character in tileset string")
    return value, offset + size


def parse_tileset(data: bytes) -> dict:
    """Parse the observed tile-rectangle envelope; opaque fields stay opaque.

    Each tile record begins with eight little-endian u32 fields, then one byte,
    then a length-prefixed UTF-16LE name. The first four u32 values are the
    atlas rectangle x/y/width/height. Other fields are retained as opaque
    metadata and are not assigned gameplay semantics.
    """
    if len(data) < 38 or len(data) > MAX_TILESET_BYTES:
        raise TileSetFormatError("invalid tileset byte length")
    header = struct.unpack_from("<8I", data, 0)
    tile_width, tile_height, atlas_tile_width, atlas_tile_height = header[:4]
    if not all(1 <= value <= 8192 for value in
               (tile_width, tile_height, atlas_tile_width, atlas_tile_height)):
        raise TileSetFormatError("invalid tileset dimensions")
    texture_ref, offset = _read_text(data, 32, allow_empty=False)
    count, offset = _read_u32(data, offset)
    if not 1 <= count <= MAX_TILE_RECORDS:
        raise TileSetFormatError("invalid tileset record count")

    entries = []
    for ordinal in range(count):
        _need(data, offset, 33)
        fields = struct.unpack_from("<8I", data, offset)
        offset += 32
        marker = data[offset]
        offset += 1
        name, offset = _read_text(data, offset, allow_empty=True)
        x, y, width, height = fields[:4]
        if width == 0 or height == 0 or width > 8192 or height > 8192:
            raise TileSetFormatError("invalid tile rectangle dimensions")
        entries.append({
            "ordinal": ordinal,
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "opaque_fields": list(fields[4:]),
            "marker": marker,
            "name": name,
        })
    if offset != len(data):
        raise TileSetFormatError("trailing bytes after tileset records")
    return {
        "tile_width": tile_width,
        "tile_height": tile_height,
        "atlas_tile_width": atlas_tile_width,
        "atlas_tile_height": atlas_tile_height,
        "opaque_header_fields": list(header[4:]),
        "texture_ref": texture_ref,
        "entries": entries,
    }


def _read_archive_entry(archive: zipfile.ZipFile, path: str, max_bytes: int) -> bytes:
    matches = [info for info in archive.infolist() if info.filename == path]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one IPA entry: {path}")
    info = matches[0]
    if info.file_size < 1 or info.file_size > max_bytes:
        raise ValueError(f"IPA entry size outside permitted bounds: {path}")
    raw = archive.read(info)
    if len(raw) != info.file_size:
        raise ValueError(f"IPA entry size mismatch: {path}")
    return raw


def _load_rgba_png(data: bytes) -> Image.Image:
    if not data or len(data) > MAX_TEXTURE_BYTES:
        raise ValueError("invalid texture PNG byte length")
    try:
        with Image.open(io.BytesIO(data)) as probe:
            if probe.format != "PNG":
                raise ValueError("collision texture is not PNG")
            if probe.width < 1 or probe.height < 1 or probe.width * probe.height > MAX_TEXTURE_PIXELS:
                raise ValueError("texture dimensions outside permitted bounds")
            probe.verify()
        with Image.open(io.BytesIO(data)) as source:
            image = source.convert("RGBA")
            image.load()
    except (OSError, Image.DecompressionBombError) as exc:
        raise ValueError("invalid or unsafe texture PNG") from exc
    return image


def _alpha_metrics(image: Image.Image, entry: dict, cells: int, atlas_index: int) -> dict:
    x, y = entry["x"], entry["y"]
    width, height = entry["width"], entry["height"]
    if x + width > image.width or y + height > image.height:
        raise TileSetFormatError("tile rectangle exceeds texture bounds")
    alpha = list(image.crop((x, y, x + width, y + height)).getchannel("A").getdata())
    pixel_count = len(alpha)
    nonzero = sum(value > 0 for value in alpha)
    thresholded = sum(value >= ALPHA_THRESHOLD for value in alpha)
    opaque = sum(value == 255 for value in alpha)
    alpha_sum = sum(alpha)
    return {
        "tile_id": entry["ordinal"],
        "atlas_index": atlas_index,
        "cells": cells,
        "atlas_rect": [x, y, width, height],
        "alpha_nonzero_pixels": nonzero,
        "alpha_at_least_128_pixels": thresholded,
        "alpha_fully_opaque_pixels": opaque,
        "pixel_count": pixel_count,
        "alpha_nonzero_fraction": nonzero / pixel_count,
        "alpha_at_least_128_fraction": thresholded / pixel_count,
        "mean_alpha_fraction": alpha_sum / (255 * pixel_count),
        "tile_name": entry["name"] or None,
    }


def _analyze_screen(archive: zipfile.ZipFile, screen: str, map_name: str) -> tuple[dict, bytes, dict]:
    prefix = f"Payload/MOTU.app/{screen}"
    map_path = f"{prefix}/maps/{map_name}"
    tileset_path = f"{prefix}/tilesets/collision.tileset"
    texture_path = f"{prefix}/textures/collisionTiles.png"
    map_raw = _read_archive_entry(archive, map_path, MAX_MAP_BYTES)
    tileset_raw = _read_archive_entry(archive, tileset_path, MAX_TILESET_BYTES)
    texture_raw = _read_archive_entry(archive, texture_path, MAX_TEXTURE_BYTES)

    tilemap = parse_tilemap(map_raw)
    layer = tilemap.layer("collision")
    matching_atlases = [index for index, name in enumerate(layer.atlases) if name == "collision"]
    if len(matching_atlases) != 1:
        raise ValueError("collision layer must reference exactly one 'collision' atlas")
    target_atlas = matching_atlases[0]
    tileset = parse_tileset(tileset_raw)
    image = _load_rgba_png(texture_raw)
    expected_ref = Path(texture_path).stem.casefold()
    texture_ref = tileset["texture_ref"].casefold()
    if texture_ref.startswith("img_"):
        texture_ref = texture_ref[4:]
    if texture_ref != expected_ref:
        raise ValueError("tileset texture reference does not match selected PNG basename")

    for entry in tileset["entries"]:
        if entry["x"] + entry["width"] > image.width or entry["y"] + entry["height"] > image.height:
            raise TileSetFormatError("tileset rectangle exceeds texture bounds")

    counts = Counter()
    other_atlas_counts = Counter()
    for tile_id, atlas_id in zip(layer.tile_ids, layer.atlas_ids):
        if tile_id == 0xffff:
            continue
        if atlas_id == target_atlas:
            counts[tile_id] += 1
        else:
            other_atlas_counts[(atlas_id, layer.atlases[atlas_id])] += 1

    tile_results = []
    for tile_id, cells in sorted(counts.items()):
        if tile_id >= len(tileset["entries"]):
            raise TileSetFormatError("occupied tile ID exceeds tileset record count")
        tile_results.append(_alpha_metrics(image, tileset["entries"][tile_id], cells, target_atlas))

    occupied = layer.occupied_count
    resolved = sum(counts.values())
    report = {
        "screen": screen,
        "map_entry": map_path,
        "tileset_entry": tileset_path,
        "texture_entry": texture_path,
        "source_entries": {
            "map": {"size_bytes": len(map_raw), "sha256": hashlib.sha256(map_raw).hexdigest()},
            "tileset": {"size_bytes": len(tileset_raw), "sha256": hashlib.sha256(tileset_raw).hexdigest()},
            "texture": {"size_bytes": len(texture_raw), "sha256": hashlib.sha256(texture_raw).hexdigest()},
        },
        "map_layer": {
            "name": layer.name,
            "columns": layer.columns,
            "rows": layer.rows,
            "occupied_cells": occupied,
            "empty_cells": layer.columns * layer.rows - occupied,
            "occupied_cells_resolved_by_selected_atlas": resolved,
            "occupied_cells_on_other_atlases": sum(other_atlas_counts.values()),
            "other_atlas_cell_counts": [
                {"atlas_index": atlas, "atlas_name": name, "cells": count}
                for (atlas, name), count in sorted(other_atlas_counts.items())
            ],
            "distinct_used_tile_ids": len(counts),
            "tile_id_frequencies": {str(tile_id): cells for tile_id, cells in sorted(counts.items())},
        },
        "tileset": {
            "texture_ref": tileset["texture_ref"],
            "tile_record_count": len(tileset["entries"]),
            "tile_rectangles_within_texture": True,
            "texture_size": [image.width, image.height],
            "tile_rect_size_set": sorted({
                (entry["width"], entry["height"]) for entry in tileset["entries"]
            }),
        },
        "tiles": tile_results,
        "result": "alpha_census_complete" if resolved == occupied else "partial_alpha_census",
        "original_collision_semantics_verified": False,
        "original_ios_gameplay_trace_compared": False,
        "native_switch_collision_import_authorized": False,
        "interpretation_boundary": (
            "Atlas alpha coverage is image-data evidence only. It does not prove "
            "solidness, slope response, one-way behavior, hazards, object ownership, "
            "world scale, or original runtime collision behavior."
        ),
    }
    return report, map_raw, tileset


def compare_screen_pair(ipa: Path, map_name: str) -> dict:
    """Compare original medium/xlarge collision atlas masks without extraction."""
    with zipfile.ZipFile(ipa, "r") as archive:
        med, med_map, med_tileset = _analyze_screen(archive, "screen-med", map_name)
        large, large_map, large_tileset = _analyze_screen(archive, "screen-xlarge", map_name)

    med_entries = med_tileset["entries"]
    large_entries = large_tileset["entries"]
    names_match = [entry["name"] for entry in med_entries] == [entry["name"] for entry in large_entries]
    rects_scale_consistent = len(med_entries) == len(large_entries)
    scale = None
    if rects_scale_consistent and med_entries:
        mw, lw = med_entries[0]["width"], large_entries[0]["width"]
        if mw and lw % mw == 0:
            scale = lw // mw
        else:
            rects_scale_consistent = False
    if rects_scale_consistent and scale:
        for left, right in zip(med_entries, large_entries):
            if (right["x"], right["y"], right["width"], right["height"]) != (
                left["x"] * scale, left["y"] * scale,
                left["width"] * scale, left["height"] * scale
            ):
                rects_scale_consistent = False
                break

    med_by_id = {entry["tile_id"]: entry for entry in med["tiles"]}
    large_by_id = {entry["tile_id"]: entry for entry in large["tiles"]}
    alpha_diffs = {}
    for tile_id in sorted(set(med_by_id) & set(large_by_id)):
        alpha_diffs[str(tile_id)] = abs(
            med_by_id[tile_id]["alpha_at_least_128_fraction"]
            - large_by_id[tile_id]["alpha_at_least_128_fraction"]
        )
    max_diff = max(alpha_diffs.values()) if alpha_diffs else None
    map_bytes_match = med_map == large_map
    texture_ref_match = med_tileset["texture_ref"] == large_tileset["texture_ref"]
    counts_match = med["map_layer"]["tile_id_frequencies"] == large["map_layer"]["tile_id_frequencies"]
    alpha_agrees = max_diff is not None and max_diff <= CROSS_PACK_ALPHA_TOLERANCE
    complete = (
        med["result"] == "alpha_census_complete"
        and large["result"] == "alpha_census_complete"
        and map_bytes_match and names_match and rects_scale_consistent
        and texture_ref_match and counts_match and alpha_agrees
    )
    return {
        "schema": "heman-collision-atlas-alpha-census-v1",
        "map_name": map_name,
        "source_ipa": {
            "name": ipa.name,
            "size_bytes": ipa.stat().st_size,
            "sha256": _sha256_file(ipa),
        },
        "screen_med": med,
        "screen_xlarge": large,
        "cross_screen": {
            "map_bytes_exactly_equal": map_bytes_match,
            "tile_record_names_match": names_match,
            "tile_rectangles_match_after_uniform_scaling": rects_scale_consistent,
            "tile_rect_scale_factor": scale,
            "texture_reference_matches": texture_ref_match,
            "tile_id_frequency_match": counts_match,
            "alpha_ge_128_fraction_absolute_differences": alpha_diffs,
            "maximum_alpha_ge_128_fraction_absolute_difference": max_diff,
            "alpha_coverage_agrees_within_tolerance": alpha_agrees,
        },
        "result": "cross_screen_alpha_census_complete" if complete else "partial_or_divergent_alpha_census",
        "original_collision_semantics_verified": False,
        "original_ios_gameplay_trace_compared": False,
        "native_switch_collision_import_authorized": False,
        "interpretation_boundary": (
            "The census correlates occupied collision-layer tile IDs with alpha coverage "
            "in a named atlas candidate. It is not a collision-engine reconstruction and "
            "does not authorize importing any original collision rule into Switch gameplay."
        ),
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def private_output_path(path: Path) -> Path:
    """Require ignored local_reports JSON output; reject symlinked roots."""
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


def _valid_map_name(name: str) -> bool:
    return (
        isinstance(name, str) and 1 < len(name) <= MAX_MAP_NAME
        and name.endswith(".map") and "/" not in name and "\\" not in name
        and all(char not in name for char in ("\x00", "\n", "\r"))
        and name not in (".map", "..map")
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", required=True, type=Path, help="owner-held IPA; read in memory only")
    parser.add_argument("--map", dest="map_name", default="MUMap1-1.map")
    parser.add_argument("--screen", choices=("screen-med", "screen-xlarge"), default="screen-med")
    parser.add_argument("--compare-screens", action="store_true")
    parser.add_argument("--out", required=True, type=Path, help="JSON output beneath ignored local_reports/")
    args = parser.parse_args(argv)
    if not _valid_map_name(args.map_name):
        parser.error("--map must be a simple .map basename")
    if args.compare_screens and args.screen != "screen-med":
        parser.error("--screen is not used with --compare-screens")
    if not args.ipa.is_file() or args.ipa.is_symlink():
        parser.error("--ipa must be an existing regular non-symlink file")
    try:
        output = private_output_path(args.out)
        if args.compare_screens:
            report = compare_screen_pair(args.ipa, args.map_name)
        else:
            with zipfile.ZipFile(args.ipa, "r") as archive:
                report, _, _ = _analyze_screen(archive, args.screen, args.map_name)
            report = {
                "schema": "heman-collision-atlas-alpha-census-v1",
                "map_name": args.map_name,
                "source_ipa": {
                    "name": args.ipa.name,
                    "size_bytes": args.ipa.stat().st_size,
                    "sha256": _sha256_file(args.ipa),
                },
                "screen": report,
                "result": report["result"],
                "original_collision_semantics_verified": False,
                "original_ios_gameplay_trace_compared": False,
                "native_switch_collision_import_authorized": False,
            }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except (OSError, zipfile.BadZipFile, TileMapFormatError, TileSetFormatError, ValueError, KeyError) as exc:
        parser.error(f"collision atlas alpha census failed: {type(exc).__name__}: {exc}")
    print(f"Stage257 result={report['result']}; private report saved under local_reports/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
