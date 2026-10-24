"""Private aggregate inventory of atlas routing inside collision-named map layers.

The output contains aggregate counts only. Layer names and nonempty cells do
not establish solidity or any other original gameplay behavior.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import struct
import zipfile

from .tilemap import MAX_FILE as MAX_MAP_BYTES, TileMapFormatError, parse_tilemap

MAX_MAPS = 1000
MAX_REPO_BYTES = 1_000_000
MAX_REPO_ENTRIES = 5000
MAX_TILESET_BYTES = 1_000_000
MAX_WAD_BYTES = 64_000_000
SPECIAL_FORMAT_MAP = "gs_background_sky.map"


class ResourceRepoFormatError(ValueError):
    """Malformed resource repository index."""


def _read_text(data: bytes, offset: int, *, allow_empty: bool = False) -> tuple[str, int]:
    if offset < 0 or offset + 2 > len(data):
        raise ResourceRepoFormatError("truncated UTF-16 length")
    units = struct.unpack_from("<H", data, offset)[0]
    offset += 2
    if units > 512 or (units == 0 and not allow_empty) or offset + units * 2 > len(data):
        raise ResourceRepoFormatError("invalid UTF-16 length")
    try:
        value = data[offset:offset + units * 2].decode("utf-16le", "strict")
    except UnicodeDecodeError as exc:
        raise ResourceRepoFormatError("invalid UTF-16 value") from exc
    if any(ord(char) < 32 for char in value):
        raise ResourceRepoFormatError("control character in resource repository")
    return value, offset + units * 2


def parse_resource_repo(data: bytes, *, expected_label: str) -> dict:
    """Parse the observed key -> resource path/value repository envelope."""
    if not 12 <= len(data) <= MAX_REPO_BYTES:
        raise ResourceRepoFormatError("resource repository byte length outside bounds")
    label, offset = _read_text(data, 0)
    if label != expected_label:
        raise ResourceRepoFormatError("unexpected resource repository label")
    if offset + 6 > len(data):
        raise ResourceRepoFormatError("truncated resource repository header")
    reserved = struct.unpack_from("<H", data, offset)[0]
    count = struct.unpack_from("<I", data, offset + 2)[0]
    offset += 6
    if reserved != 0 or not 1 <= count <= MAX_REPO_ENTRIES:
        raise ResourceRepoFormatError("invalid resource repository header")
    entries = {}
    for _ in range(count):
        key, offset = _read_text(data, offset)
        if offset + 4 > len(data):
            raise ResourceRepoFormatError("truncated resource key marker")
        marker = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        path, offset = _read_text(data, offset)
        if offset + 4 > len(data):
            raise ResourceRepoFormatError("truncated resource value")
        value = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        if marker != 0 or key in entries:
            raise ResourceRepoFormatError("nonzero marker or duplicate resource key")
        parts = PurePosixPath(path.lstrip("/")).parts
        if not parts or any(part in ("", ".", "..") for part in parts):
            raise ResourceRepoFormatError("unsafe resource path")
        entries[key] = {"path": path, "value": value}
    if offset != len(data):
        raise ResourceRepoFormatError("trailing bytes after resource repository")
    return {"label": label, "entry_count": count, "entries": entries}


def _tileset_texture_ref(data: bytes) -> str:
    """Read the common tileset header's texture key; leave other fields opaque."""
    if len(data) < 34 or len(data) > MAX_TILESET_BYTES:
        raise ResourceRepoFormatError("tileset byte length outside bounds")
    dimensions = struct.unpack_from("<4I", data, 0)
    if not all(1 <= value <= 8192 for value in dimensions):
        raise ResourceRepoFormatError("invalid tileset dimensions")
    texture_ref, _offset = _read_text(data, 32)
    return texture_ref


def parse_texture_wad_record(data: bytes, offset: int, *, expected_key: str,
                            next_offset: int) -> dict:
    """Validate the indexed texture metadata record at its repo-provided offset."""
    if offset < 0 or offset >= len(data) or next_offset <= offset or next_offset > len(data):
        raise ResourceRepoFormatError("texture WAD record offset outside bounds")
    key, pos = _read_text(data, offset)
    if key != expected_key:
        raise ResourceRepoFormatError("texture WAD key does not match TextureData.repo")
    if pos + 15 > len(data):
        raise ResourceRepoFormatError("truncated texture WAD metadata")
    marker = struct.unpack_from("<I", data, pos)[0]
    pos += 4
    reserved = data[pos:pos + 11]
    pos += 11
    if marker != 1 or any(reserved):
        raise ResourceRepoFormatError("unsupported texture WAD metadata header")
    texture_name, pos = _read_text(data, pos)
    if pos != next_offset:
        raise ResourceRepoFormatError("texture WAD record length disagrees with repository offsets")
    return {
        "key": key,
        "marker": marker,
        "texture_name": texture_name,
        "record_length": pos - offset,
    }


def _next_texture_offset(texture_repo: dict, path: str, offset: int, wad_size: int) -> int:
    offsets = sorted({
        entry["value"] for entry in texture_repo["entries"].values()
        if entry["path"] == path
    })
    for candidate in offsets:
        if candidate > offset:
            return candidate
    return wad_size


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


def _read_archive_entry(archive: zipfile.ZipFile, path: str, max_bytes: int) -> bytes:
    matches = [info for info in archive.infolist() if info.filename == path]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one IPA entry: {path}")
    info = matches[0]
    mode = (info.external_attr >> 16) & 0xffff
    if stat.S_ISLNK(mode):
        raise ValueError("symbolic-link resource entry is not accepted")
    if info.file_size < 1 or info.file_size > max_bytes:
        raise ValueError("resource entry size outside permitted bounds")
    raw = archive.read(info)
    if len(raw) != info.file_size:
        raise ValueError("resource entry size mismatch")
    return raw


def _registry_paths(archive: zipfile.ZipFile, screen: str) -> tuple[dict, dict, dict, bytes]:
    prefix = f"Payload/MOTU.app/{screen}/meta/"
    tile_raw = _read_archive_entry(archive, prefix + "TilesetData.repo", MAX_REPO_BYTES)
    texture_raw = _read_archive_entry(archive, prefix + "TextureData.repo", MAX_REPO_BYTES)
    tile_repo = parse_resource_repo(tile_raw, expected_label="TilesetData")
    texture_repo = parse_resource_repo(texture_raw, expected_label="TextureData")
    wad_paths = {entry["path"] for entry in texture_repo["entries"].values()}
    if len(wad_paths) != 1:
        raise ResourceRepoFormatError("TextureData.repo does not use one WAD path")
    wad_relative = next(iter(wad_paths)).lstrip("/")
    parts = PurePosixPath(wad_relative).parts
    if not parts or parts[0] != "textureData" or any(p in ("", ".", "..") for p in parts):
        raise ResourceRepoFormatError("TextureData WAD path is outside the expected directory")
    wad_raw = _read_archive_entry(
        archive, f"Payload/MOTU.app/{screen}/{wad_relative}", MAX_WAD_BYTES
    )
    return tile_repo, texture_repo, {
        "tileset_repo_size_bytes": len(tile_raw),
        "tileset_repo_sha256": hashlib.sha256(tile_raw).hexdigest(),
        "texture_repo_size_bytes": len(texture_raw),
        "texture_repo_sha256": hashlib.sha256(texture_raw).hexdigest(),
        "texture_wad_size_bytes": len(wad_raw),
        "texture_wad_sha256": hashlib.sha256(wad_raw).hexdigest(),
        "texture_wad_path": wad_relative,
    }, wad_raw


def audit_collision_atlas_routing(ipa: Path) -> dict:
    """Compare both screen packs and count aggregate atlas usage in collision layers."""
    with zipfile.ZipFile(ipa, "r") as archive:
        if len(archive.infolist()) > 10000:
            raise ValueError("IPA has too many entries")
        med_entries = _map_entry_index(archive, "screen-med")
        large_entries = _map_entry_index(archive, "screen-xlarge")
        if set(med_entries) != set(large_entries):
            raise ValueError("screen packs have different map filename sets")

        med_tiles, med_textures, med_repo_meta, med_wad = _registry_paths(archive, "screen-med")
        large_tiles, large_textures, large_repo_meta, large_wad = _registry_paths(archive, "screen-xlarge")
        tileset_registry_equal = (
            med_tiles["entry_count"] == large_tiles["entry_count"]
            and med_tiles["entries"] == large_tiles["entries"]
            and med_repo_meta["tileset_repo_sha256"] == large_repo_meta["tileset_repo_sha256"]
        )
        texture_registry_equal = (
            med_textures["entry_count"] == large_textures["entry_count"]
            and med_textures["entries"] == large_textures["entries"]
            and med_repo_meta["texture_repo_sha256"] == large_repo_meta["texture_repo_sha256"]
        )
        texture_wad_equal = med_wad == large_wad
        if not tileset_registry_equal or not texture_registry_equal:
            raise ValueError("resource registries differ between screen packs")

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
            med_raw = _read_archive_entry(archive, med_entries[name].filename, MAX_MAP_BYTES)
            large_raw = _read_archive_entry(archive, large_entries[name].filename, MAX_MAP_BYTES)
            exact = med_raw == large_raw
            if exact:
                exact_pairs += 1
            if name == SPECIAL_FORMAT_MAP:
                special_present += 1
                special_equal = exact
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
        unresolved_aliases = []
        for atlas_name, cells in sorted(atlas_cells.items(), key=lambda item: (-item[1], item[0])):
            tile_counts = atlas_tile_counts[atlas_name]
            registry_entry = med_tiles["entries"].get(atlas_name)
            resource_path = registry_entry["path"] if registry_entry else None
            file_present_both = False
            texture_ref = None
            texture_key_present = None
            texture_ref_parseable = False
            texture_wad_record_verified = None
            texture_wad_texture_name = None
            texture_wad_record_length = None
            texture_png_present_both_packs = None
            if registry_entry:
                normalized = resource_path.lstrip("/")
                parts = PurePosixPath(normalized).parts
                if not parts or parts[0] != "tilesets" or any(p in ("", ".", "..") for p in parts):
                    raise ValueError("tileset registry path is outside the tilesets directory")
                med_path = f"Payload/MOTU.app/screen-med/{normalized}"
                large_path = f"Payload/MOTU.app/screen-xlarge/{normalized}"
                med_tileset = _read_archive_entry(archive, med_path, MAX_TILESET_BYTES)
                large_tileset = _read_archive_entry(archive, large_path, MAX_TILESET_BYTES)
                file_present_both = True
                try:
                    med_ref = _tileset_texture_ref(med_tileset)
                    large_ref = _tileset_texture_ref(large_tileset)
                    if med_ref != large_ref:
                        raise ValueError("tileset texture reference differs across screen packs")
                    texture_ref = med_ref
                    texture_ref_parseable = True
                    texture_key_present = texture_ref in med_textures["entries"]
                except ResourceRepoFormatError:
                    # Some legacy tilesets use a different binary envelope. Their
                    # registry path is still authoritative; texture lookup stays unknown.
                    texture_ref_parseable = False
                    texture_key_present = None
                if texture_key_present:
                    texture_entry = med_textures["entries"][texture_ref]
                    texture_offset = texture_entry["value"]
                    next_offset = _next_texture_offset(
                        med_textures, texture_entry["path"], texture_offset, len(med_wad)
                    )
                    large_entry = large_textures["entries"][texture_ref]
                    large_next = _next_texture_offset(
                        large_textures, large_entry["path"], large_entry["value"], len(large_wad)
                    )
                    try:
                        med_record = parse_texture_wad_record(
                            med_wad, texture_offset, expected_key=texture_ref, next_offset=next_offset
                        )
                        large_record = parse_texture_wad_record(
                            large_wad, large_entry["value"], expected_key=texture_ref, next_offset=large_next
                        )
                        texture_wad_record_verified = (
                            med_record == large_record
                            and texture_wad_equal
                            and texture_offset == large_entry["value"]
                        )
                        texture_wad_texture_name = med_record["texture_name"]
                        texture_wad_record_length = med_record["record_length"]
                        if "/" not in texture_wad_texture_name and chr(92) not in texture_wad_texture_name:
                            med_png = f"Payload/MOTU.app/screen-med/textures/{texture_wad_texture_name}.png"
                            large_png = f"Payload/MOTU.app/screen-xlarge/textures/{texture_wad_texture_name}.png"
                            texture_png_present_both_packs = (
                                med_png in archive.namelist() and large_png in archive.namelist()
                            )
                    except ResourceRepoFormatError:
                        texture_wad_record_verified = False
            else:
                unresolved_aliases.append(atlas_name)

            atlas_usage.append({
                "atlas_name": atlas_name,
                "occupied_cells": cells,
                "maps_using_atlas": len(atlas_maps[atlas_name]),
                "distinct_tile_ids": len(tile_counts),
                "tile_id_frequencies": {str(tile_id): count for tile_id, count in sorted(tile_counts.items())},
                "tileset_registry_entry_present": registry_entry is not None,
                "tileset_resource_path": resource_path,
                "tileset_resource_file_present_both_packs": file_present_both,
                "tileset_texture_ref_parseable": texture_ref_parseable,
                "tileset_texture_ref": texture_ref,
                "texture_registry_entry_present": texture_key_present,
                "texture_wad_record_verified": texture_wad_record_verified,
                "texture_wad_texture_name": texture_wad_texture_name,
                "texture_wad_record_length": texture_wad_record_length,
                "texture_png_present_both_packs": texture_png_present_both_packs,
            })

    report = {
        "schema": "heman-collision-layer-atlas-routing-v2",
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
        "resource_registry_summary": {
            "tileset_registry_entries": med_tiles["entry_count"],
            "texture_registry_entries": med_textures["entry_count"],
            "tileset_registry_exact_bytes_equal_across_packs": tileset_registry_equal,
            "texture_registry_exact_bytes_equal_across_packs": texture_registry_equal,
            "texture_wad_exact_bytes_equal_across_packs": texture_wad_equal,
            "texture_wad_size_bytes": med_repo_meta["texture_wad_size_bytes"],
            "texture_wad_sha256": med_repo_meta["texture_wad_sha256"],
            "tileset_registry_sha256": med_repo_meta["tileset_repo_sha256"],
            "texture_registry_sha256": med_repo_meta["texture_repo_sha256"],
        },
        "collision_layer_summary": {
            "collision_named_layers": collision_layers,
            "occupied_cells": total_occupied,
            "cells_on_atlas_named_collision": atlas_cells.get("collision", 0),
            "cells_on_other_atlases": total_occupied - atlas_cells.get("collision", 0),
            "distinct_atlas_names": len(atlas_usage),
            "atlas_usage": atlas_usage,
        },
        "unresolved_tileset_registry_aliases": unresolved_aliases,
        "original_collision_semantics_verified": False,
        "original_ios_gameplay_trace_compared": False,
        "native_switch_collision_import_authorized": False,
        "interpretation_boundary": (
            "This inventory measures source-map parity, resource-registry resolution and "
            "aggregate atlas/tile-ID frequency only. A collision-named layer may reference "
            "multiple atlases. Registry resolution does not prove solidity, slopes, one-way "
            "behavior, hazards, sensor behavior, object ownership or original runtime semantics."
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
    except (OSError, zipfile.BadZipFile, TileMapFormatError, ResourceRepoFormatError, ValueError, KeyError) as exc:
        parser.error(f"collision atlas routing audit failed: {type(exc).__name__}: {exc}")
    print(
        f"Stage258 parsed {report['screen_pack_map_pair_audit']['normal_multilayer_maps_parsed']} "
        f"normal maps and {report['collision_layer_summary']['collision_named_layers']} "
        "collision layers; private aggregate saved under local_reports/"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
