"""Private-only audit of used collision tiles and their explicit Shape2D links.

The report joins serialized tile metadata to exact .shape resource stems.
An empty shape reference is recorded as the engine's separate fallback case;
it is not inferred to be solid terrain.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import math
import struct
import zipfile

from .lvl import LevelFormatError
from .shapes import parse_shape
from .tilemap import MAX_FILE as MAX_MAP_BYTES, TileMapFormatError, parse_tilemap

MAX_TILESET_BYTES = 1_000_000
MAX_TILE_RECORDS = 4096
MAX_TEXTURE_REFS = 32
MAX_STRING_UNITS = 512
MAX_SHAPE_BYTES = 1_048_576


def _valid_map_name(name: str) -> bool:
    return (
        isinstance(name, str) and 1 < len(name) <= 128
        and name.endswith(".map") and "/" not in name and "\\" not in name
        and all(ch not in name for ch in ("\x00", "\n", "\r"))
        and name not in (".map", "..map")
    )


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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def private_output_path(path: Path) -> Path:
    """Require ignored local_reports JSON output and reject symlink escapes."""
    root_path = Path.cwd() / "local_reports"
    if root_path.is_symlink():
        raise ValueError("local_reports must not be a symbolic link")
    root = root_path.resolve()
    destination = path.resolve()
    if destination == root or not destination.is_relative_to(root) or destination.suffix != ".json":
        raise ValueError("output must be a .json file beneath local_reports/")
    if path.exists() and path.is_symlink():
        raise ValueError("output must not be a symbolic link")
    return destination


class TilesetFormatError(ValueError):
    """Malformed serialized runtime tileset."""


def _read_u16_string(data: bytes, offset: int, *, allow_empty: bool) -> tuple[str, int]:
    if offset < 0 or offset + 2 > len(data):
        raise TilesetFormatError("truncated UTF-16 string length")
    units = struct.unpack_from("<H", data, offset)[0]
    offset += 2
    if units > MAX_STRING_UNITS or (not allow_empty and units == 0):
        raise TilesetFormatError("invalid UTF-16 string length")
    end = offset + units * 2
    if end > len(data):
        raise TilesetFormatError("truncated UTF-16 string")
    try:
        value = data[offset:end].decode("utf-16le", errors="strict")
    except UnicodeDecodeError as exc:
        raise TilesetFormatError("invalid UTF-16 string") from exc
    if any(ord(ch) < 32 for ch in value):
        raise TilesetFormatError("control character in UTF-16 string")
    return value, end


def parse_runtime_tileset(data: bytes) -> dict:
    """Decode the Tileset::customLoad / Tile::fileIn record layout.

    Header: six signed 32-bit integers, one float32, a texture-reference count,
    that many length-prefixed UTF-16 strings, then the tile-record count.
    Each tile: seven signed integers, one boolean byte, one float32 damage
    value, and a length-prefixed UTF-16 collision-shape reference.
    """
    if len(data) < 36 or len(data) > MAX_TILESET_BYTES:
        raise TilesetFormatError("invalid runtime tileset byte length")
    header_ints = struct.unpack_from("<6i", data, 0)
    header_float = struct.unpack_from("<f", data, 24)[0]
    texture_ref_count = struct.unpack_from("<i", data, 28)[0]
    if not all(1 <= value <= 8192 for value in header_ints[:4]):
        raise TilesetFormatError("invalid runtime tileset dimensions")
    if not math.isfinite(header_float):
        raise TilesetFormatError("non-finite runtime tileset header float")
    if not 1 <= texture_ref_count <= MAX_TEXTURE_REFS:
        raise TilesetFormatError("invalid texture-reference count")

    offset = 32
    texture_refs = []
    for _ in range(texture_ref_count):
        value, offset = _read_u16_string(data, offset, allow_empty=False)
        texture_refs.append(value)
    if offset + 4 > len(data):
        raise TilesetFormatError("missing tile-record count")
    tile_count = struct.unpack_from("<i", data, offset)[0]
    offset += 4
    if not 1 <= tile_count <= MAX_TILE_RECORDS:
        raise TilesetFormatError("invalid tile-record count")

    entries = []
    for tile_id in range(tile_count):
        if offset + 33 > len(data):
            raise TilesetFormatError("truncated tile record")
        values = struct.unpack_from("<7i", data, offset)
        opacity_flag = data[offset + 28]
        damage = struct.unpack_from("<f", data, offset + 29)[0]
        if opacity_flag not in (0, 1):
            raise TilesetFormatError("invalid tile opacity flag")
        if not math.isfinite(damage):
            raise TilesetFormatError("non-finite tile damage value")
        offset += 33
        shape_ref, offset = _read_u16_string(data, offset, allow_empty=True)
        x, y, width, height, collision_id, s32_data, s32_alt1_data = values
        if x < 0 or y < 0 or not 1 <= width <= 8192 or not 1 <= height <= 8192:
            raise TilesetFormatError("invalid tile atlas rectangle")
        entries.append({
            "tile_id": tile_id,
            "atlas_x": x,
            "atlas_y": y,
            "width": width,
            "height": height,
            "collision_id": collision_id,
            "s32_data": s32_data,
            "s32_alt1_data": s32_alt1_data,
            "opacity_flag": bool(opacity_flag),
            "damage": damage,
            "collision_shape_reference": shape_ref,
        })
    if offset != len(data):
        raise TilesetFormatError("trailing bytes after runtime tileset")
    return {
        "header_ints": list(header_ints),
        "header_float": header_float,
        "texture_refs": texture_refs,
        "entries": entries,
    }


def _valid_shape_reference(value: str) -> bool:
    return (
        isinstance(value, str)
        and 1 <= len(value) <= 128
        and value not in (".", "..")
        and "/" not in value
        and "\\" not in value
        and all(ord(ch) >= 33 for ch in value)
        and not value.endswith(".shape")
    )


def _shape_path(archive: zipfile.ZipFile, screen: str, reference: str) -> str:
    if not _valid_shape_reference(reference):
        raise ValueError("unsafe or invalid collision-shape reference")
    prefix = f"Payload/MOTU.app/{screen}/geometry/"
    matches = [
        info.filename for info in archive.infolist()
        if info.filename.startswith(prefix)
        and info.filename.endswith(".shape")
        and PurePosixPath(info.filename).stem == reference
    ]
    if len(matches) != 1:
        raise ValueError("collision-shape reference must resolve to exactly one .shape resource")
    return matches[0]


def _shape_summary(data: bytes) -> dict:
    if not data or len(data) > MAX_SHAPE_BYTES:
        raise ValueError("shape resource size outside permitted bounds")
    shape = parse_shape(data)
    return {
        "kind": shape.kind,
        "flags": shape.flags,
        "reference": shape.reference,
        "vertex_count": len(shape.vertices) if shape.kind == "polygon" else None,
        "bounds": list(shape.bounds()),
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _screen_scan(archive: zipfile.ZipFile, screen: str, map_name: str) -> dict:
    prefix = f"Payload/MOTU.app/{screen}"
    map_path = f"{prefix}/maps/{map_name}"
    tileset_path = f"{prefix}/tilesets/collision.tileset"
    map_raw = _read_archive_entry(archive, map_path, MAX_MAP_BYTES)
    tileset_raw = _read_archive_entry(archive, tileset_path, MAX_TILESET_BYTES)
    tilemap = parse_tilemap(map_raw)
    layer = tilemap.layer("collision")
    atlas_matches = [i for i, name in enumerate(layer.atlases) if name == "collision"]
    if len(atlas_matches) != 1:
        raise ValueError("collision layer must reference exactly one collision atlas")
    collision_atlas = atlas_matches[0]

    frequencies = {}
    other_atlas_cells = 0
    for tile_id, atlas_id in zip(layer.tile_ids, layer.atlas_ids):
        if tile_id == 0xffff:
            continue
        if atlas_id == collision_atlas:
            frequencies[tile_id] = frequencies.get(tile_id, 0) + 1
        else:
            other_atlas_cells += 1

    tileset = parse_runtime_tileset(tileset_raw)
    if max(frequencies, default=-1) >= len(tileset["entries"]):
        raise TilesetFormatError("used collision tile ID exceeds tile-record count")

    used_tiles = []
    for tile_id, cells in sorted(frequencies.items()):
        tile = tileset["entries"][tile_id]
        reference = tile["collision_shape_reference"]
        item = {
            "tile_id": tile_id,
            "occupied_cells": cells,
            "collision_id": tile["collision_id"],
            "s32_data": tile["s32_data"],
            "s32_alt1_data": tile["s32_alt1_data"],
            "opacity_flag": tile["opacity_flag"],
            "damage": tile["damage"],
            "atlas_rect": [tile["atlas_x"], tile["atlas_y"], tile["width"], tile["height"]],
            "collision_shape_reference": reference or None,
            "shape_resource": None,
        }
        if reference:
            shape_path = _shape_path(archive, screen, reference)
            shape_raw = _read_archive_entry(archive, shape_path, MAX_SHAPE_BYTES)
            item["shape_resource"] = {
                "entry": shape_path,
                **_shape_summary(shape_raw),
            }
        used_tiles.append(item)

    return {
        "screen": screen,
        "map_bytes": map_raw,
        "tileset_bytes": tileset_raw,
        "tileset": tileset,
        "map_size_bytes": len(map_raw),
        "tileset_size_bytes": len(tileset_raw),
        "map_sha256": hashlib.sha256(map_raw).hexdigest(),
        "tileset_sha256": hashlib.sha256(tileset_raw).hexdigest(),
        "map_dimensions": [layer.columns, layer.rows],
        "occupied_cells": layer.occupied_count,
        "other_atlas_cells": other_atlas_cells,
        "tile_frequencies": {str(k): v for k, v in sorted(frequencies.items())},
        "used_tiles": used_tiles,
    }


def _rect_scale(med: dict, large: dict) -> int:
    a, b = med["tileset"], large["tileset"]
    if len(a["entries"]) != len(b["entries"]):
        raise ValueError("resolution packs have different tile-record counts")
    if a["texture_refs"] != b["texture_refs"]:
        raise ValueError("resolution packs have different texture references")
    if a["header_ints"][4:] != b["header_ints"][4:] or a["header_float"] != b["header_float"]:
        raise ValueError("resolution packs have different collision metadata")
    if a["header_ints"][0] <= 0 or b["header_ints"][0] % a["header_ints"][0]:
        raise ValueError("tileset header dimensions have no integer scale")
    scale = b["header_ints"][0] // a["header_ints"][0]
    if (
        scale < 1
        or b["header_ints"][:2] != [v * scale for v in a["header_ints"][:2]]
        or b["header_ints"][2:4] != a["header_ints"][2:4]
    ):
        raise ValueError("atlas dimensions do not scale while logical tile dimensions remain stable")
    for left, right in zip(a["entries"], b["entries"]):
        if (right["atlas_x"], right["atlas_y"], right["width"], right["height"]) != (
            left["atlas_x"] * scale, left["atlas_y"] * scale,
            left["width"] * scale, left["height"] * scale
        ):
            raise ValueError("tile atlas rectangles do not share one uniform scale")
        for field in ("collision_id", "s32_data", "s32_alt1_data", "opacity_flag", "damage", "collision_shape_reference"):
            if left[field] != right[field]:
                raise ValueError("tile collision metadata differs across resolution packs")
    return scale


def compare_screen_pair(ipa: Path, map_name: str) -> dict:
    if not ipa.is_file() or ipa.is_symlink():
        raise ValueError("IPA must be an existing regular non-symlink file")
    with zipfile.ZipFile(ipa, "r") as archive:
        med = _screen_scan(archive, "screen-med", map_name)
        large = _screen_scan(archive, "screen-xlarge", map_name)

    scale = _rect_scale(med, large)
    if med["map_bytes"] != large["map_bytes"]:
        map_equal = False
    else:
        map_equal = True
    if med["tile_frequencies"] != large["tile_frequencies"]:
        raise ValueError("used collision tile frequencies differ across resolution packs")
    if len(med["used_tiles"]) != len(large["used_tiles"]):
        raise ValueError("used collision tile count differs across resolution packs")

    med_by_id = {tile["tile_id"]: tile for tile in med["used_tiles"]}
    large_by_id = {tile["tile_id"]: tile for tile in large["used_tiles"]}
    explicit_refs = [t for t in med["used_tiles"] if t["collision_shape_reference"]]
    exact_matches = sum(
        t["shape_resource"] is not None and
        t["shape_resource"]["sha256"] == large_by_id[t["tile_id"]]["shape_resource"]["sha256"]
        for t in explicit_refs
    )
    shape_resource_bytes_equal = all(
        t["shape_resource"]["sha256"] == large_by_id[t["tile_id"]]["shape_resource"]["sha256"]
        for t in explicit_refs
    )
    metadata_parity = all(
        med_by_id[tile_id]["collision_id"] == large_by_id[tile_id]["collision_id"]
        and med_by_id[tile_id]["collision_shape_reference"] == large_by_id[tile_id]["collision_shape_reference"]
        for tile_id in med_by_id
    )
    complete = map_equal and metadata_parity and shape_resource_bytes_equal
    return {
        "schema": "heman-collision-shape-link-audit-v1",
        "source_ipa": {
            "name": ipa.name,
            "size_bytes": ipa.stat().st_size,
            "sha256": _sha256_file(ipa),
        },
        "screen_med": {
            "map_size_bytes": med["map_size_bytes"],
            "tileset_size_bytes": med["tileset_size_bytes"],
            "map_sha256": med["map_sha256"],
            "tileset_sha256": med["tileset_sha256"],
            "map_dimensions": med["map_dimensions"],
            "occupied_cells": med["occupied_cells"],
            "other_atlas_cells": med["other_atlas_cells"],
            "tile_frequencies": med["tile_frequencies"],
            "used_tiles": med["used_tiles"],
            "tileset_header": {
                "dimensions": med["tileset"]["header_ints"][:4],
                "collision_category": med["tileset"]["header_ints"][4],
                "collision_bitmask": med["tileset"]["header_ints"][5],
                "header_float": med["tileset"]["header_float"],
                "texture_refs": med["tileset"]["texture_refs"],
                "tile_record_count": len(med["tileset"]["entries"]),
            },
        },
        "screen_xlarge": {
            "map_size_bytes": large["map_size_bytes"],
            "tileset_size_bytes": large["tileset_size_bytes"],
            "map_sha256": large["map_sha256"],
            "tileset_sha256": large["tileset_sha256"],
            "map_dimensions": large["map_dimensions"],
            "occupied_cells": large["occupied_cells"],
            "other_atlas_cells": large["other_atlas_cells"],
            "tile_frequencies": large["tile_frequencies"],
            "used_tiles": large["used_tiles"],
            "tileset_header": {
                "dimensions": large["tileset"]["header_ints"][:4],
                "collision_category": large["tileset"]["header_ints"][4],
                "collision_bitmask": large["tileset"]["header_ints"][5],
                "header_float": large["tileset"]["header_float"],
                "texture_refs": large["tileset"]["texture_refs"],
                "tile_record_count": len(large["tileset"]["entries"]),
            },
        },
        "cross_screen": {
            "map_bytes_exactly_equal": map_equal,
            "tile_rect_scale_factor": scale,
            "used_tile_frequencies_match": med["tile_frequencies"] == large["tile_frequencies"],
            "tile_collision_metadata_match": metadata_parity,
            "used_tile_count": len(med["used_tiles"]),
            "explicit_shape_reference_count": len(explicit_refs),
            "no_explicit_shape_reference_count": len(med["used_tiles"]) - len(explicit_refs),
            "exact_shape_resource_matches": exact_matches,
            "all_referenced_shape_resources_byte_equal": shape_resource_bytes_equal,
        },
        "result": "cross_screen_shape_link_audit_complete" if complete else "partial_or_divergent_shape_links",
        "resource_links_verified": complete,
        "macho_call_path_disassembly_included_in_this_tool": False,
        "original_collision_semantics_verified": False,
        "original_ios_gameplay_trace_compared": False,
        "native_switch_collision_import_authorized": False,
        "interpretation_boundary": (
            "Exact tile-record strings and paired .shape resources establish a source-resource link. "
            "They do not by themselves establish physical meaning, collision category semantics, "
            "world transform or gameplay response. Empty references use the separately audited "
            "fallback code path; they are not assumed to be solid."
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
    except (OSError, zipfile.BadZipFile, TileMapFormatError, LevelFormatError, TilesetFormatError, ValueError, KeyError) as exc:
        parser.error(f"collision shape-link audit failed: {type(exc).__name__}: {exc}")
    print(f"Stage260 result={report['result']}; private shape-link report saved under local_reports/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
