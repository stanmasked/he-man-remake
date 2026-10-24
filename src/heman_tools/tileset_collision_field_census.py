"""Private-only parser for collision-related fields in registered tileset resources.

The JSON output belongs under ignored local_reports/. It records metadata
fields, not verified gameplay behavior.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import struct
import zipfile

from .collision_layer_atlas_inventory import (
    MAX_TILESET_BYTES,
    audit_collision_atlas_routing,
    private_output_path,
)

MAX_TILE_COUNT = 4096
MAX_LAYER_COUNT = 128


class TilesetFormatError(ValueError):
    """Unsupported or malformed tileset structure."""


def _read_text16(data: bytes, offset: int, *, allow_empty: bool = False) -> tuple[str, int]:
    if offset < 0 or offset + 2 > len(data):
        raise TilesetFormatError("truncated UTF-16 string length")
    units = struct.unpack_from("<H", data, offset)[0]
    offset += 2
    if units > 512 or (units == 0 and not allow_empty) or offset + units * 2 > len(data):
        raise TilesetFormatError("invalid UTF-16 string length")
    try:
        value = data[offset:offset + units * 2].decode("utf-16le", "strict")
    except UnicodeDecodeError as exc:
        raise TilesetFormatError("invalid UTF-16 string") from exc
    if any(ord(char) < 32 for char in value):
        raise TilesetFormatError("control character in tileset string")
    return value, offset + units * 2


def parse_tileset_collision_fields(data: bytes) -> dict:
    """Parse the common runtime tileset envelope and keep unverified fields explicit."""
    if not 36 <= len(data) <= MAX_TILESET_BYTES:
        raise TilesetFormatError("tileset size outside bounds")
    header = struct.unpack_from("<6I", data, 0)
    tile_width, tile_height, atlas_tile_width, atlas_tile_height, category, bitmask = header
    if not all(1 <= value <= 8192 for value in (tile_width, tile_height, atlas_tile_width, atlas_tile_height)):
        raise TilesetFormatError("invalid tile dimensions")
    optional_name_length = struct.unpack_from("<I", data, 24)[0]
    layer_count = struct.unpack_from("<I", data, 28)[0]
    if optional_name_length != 0:
        raise TilesetFormatError("nonempty optional tileset name is not yet supported")
    if not 1 <= layer_count <= MAX_LAYER_COUNT:
        raise TilesetFormatError("layer count outside bounds")
    offset = 32
    layers = []
    for layer_index in range(layer_count):
        texture_ref, offset = _read_text16(data, offset)
        if offset + 4 > len(data):
            raise TilesetFormatError("missing tile count")
        tile_count = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        if not 1 <= tile_count <= MAX_TILE_COUNT:
            raise TilesetFormatError("tile count outside bounds")
        tiles = []
        for ordinal in range(tile_count):
            if offset + 33 > len(data):
                raise TilesetFormatError("truncated tile record")
            fields = struct.unpack_from("<8I", data, offset)
            offset += 32
            shape_marker = data[offset]
            offset += 1
            shape_ref, offset = _read_text16(data, offset, allow_empty=True)
            x, y, width, height = fields[:4]
            if not (1 <= width <= 8192 and 1 <= height <= 8192):
                raise TilesetFormatError("invalid tile rectangle")
            tiles.append({
                "ordinal": ordinal,
                "x": x,
                "y": y,
                "width": width,
                "height": height,
                "collision_id": fields[4],
                "s32_data": fields[5],
                "s32_alt1_data": fields[6],
                "opacity_flag_raw": fields[7],
                "opacity_flag_low_byte": fields[7] & 0xff,
                "shape_marker": shape_marker,
                "collision_shape_ref": shape_ref,
            })
        layers.append({
            "layer_index": layer_index,
            "texture_ref": texture_ref,
            "tile_count": tile_count,
            "tiles": tiles,
        })
    if offset != len(data):
        raise TilesetFormatError("trailing bytes after tileset records")
    return {
        "tile_width": tile_width,
        "tile_height": tile_height,
        "atlas_tile_width": atlas_tile_width,
        "atlas_tile_height": atlas_tile_height,
        "collision_category": category,
        "collision_bitmask": bitmask,
        "optional_name_length": optional_name_length,
        "layer_count": layer_count,
        "layers": layers,
    }


def _read_registered_tileset(archive: zipfile.ZipFile, screen: str, resource_path: str) -> bytes:
    normalized = resource_path.lstrip("/")
    parts = PurePosixPath(normalized).parts
    if not parts or parts[0] != "tilesets" or any(part in ("", ".", "..") for part in parts):
        raise ValueError("registered tileset path is outside the tilesets directory")
    path = f"Payload/MOTU.app/{screen}/{normalized}"
    matches = [info for info in archive.infolist() if info.filename == path]
    if len(matches) != 1:
        raise ValueError("registered tileset resource is missing or duplicated")
    info = matches[0]
    if info.file_size < 1 or info.file_size > MAX_TILESET_BYTES:
        raise ValueError("registered tileset resource size outside bounds")
    raw = archive.read(info)
    if len(raw) != info.file_size:
        raise ValueError("registered tileset resource size mismatch")
    return raw


def _semantic_signature(tileset: dict) -> tuple:
    return (
        tileset["collision_category"],
        tileset["collision_bitmask"],
        tileset["layer_count"],
        tuple(
            (
                layer["texture_ref"],
                layer["tile_count"],
                tuple(
                    (
                        tile["collision_id"],
                        tile["s32_data"],
                        tile["s32_alt1_data"],
                        tile["opacity_flag_low_byte"],
                        tile["shape_marker"],
                        tile["collision_shape_ref"],
                    )
                    for tile in layer["tiles"]
                ),
            )
            for layer in tileset["layers"]
        ),
    )


def _field_distribution(used_records: list[dict]) -> dict:
    fields = {
        "collision_id_cell_counts": Counter(),
        "s32_data_cell_counts": Counter(),
        "s32_alt1_data_cell_counts": Counter(),
        "opacity_flag_low_byte_cell_counts": Counter(),
        "shape_marker_cell_counts": Counter(),
        "collision_shape_ref_cell_counts": Counter(),
    }
    for row in used_records:
        frequency = row["frequency"]
        fields["collision_id_cell_counts"][str(row["collision_id"])] += frequency
        fields["s32_data_cell_counts"][str(row["s32_data"])] += frequency
        fields["s32_alt1_data_cell_counts"][str(row["s32_alt1_data"])] += frequency
        fields["opacity_flag_low_byte_cell_counts"][str(row["opacity_flag_low_byte"])] += frequency
        fields["shape_marker_cell_counts"][str(row["shape_marker"])] += frequency
        fields["collision_shape_ref_cell_counts"][row["collision_shape_ref"] or "(empty)"] += frequency
    return {key: dict(sorted(counter.items())) for key, counter in fields.items()}


def audit_tileset_collision_fields(ipa: Path) -> dict:
    """Join aggregate collision-layer tile-ID frequencies to registered tile records."""
    routing = audit_collision_atlas_routing(ipa)
    atlas_usage = routing["collision_layer_summary"]["atlas_usage"]
    details = []
    with zipfile.ZipFile(ipa, "r") as archive:
        for atlas_row in atlas_usage:
            atlas_name = atlas_row["atlas_name"]
            resource_path = atlas_row["tileset_resource_path"]
            row = {
                "atlas_name": atlas_name,
                "occupied_cells": atlas_row["occupied_cells"],
                "maps_using_atlas": atlas_row["maps_using_atlas"],
                "tileset_resource_path": resource_path,
                "parse_status": "unsupported_tileset_format",
                "parse_error_type": None,
                "cross_pack_semantic_metadata_equal": None,
                "header": None,
                "layers": [],
                "used_tile_records": [],
                "tile_id_out_of_range": [],
                "field_distribution": {},
            }
            if not resource_path or not atlas_row["tileset_registry_entry_present"]:
                row["parse_status"] = "unresolved_tileset_registry_alias"
                details.append(row)
                continue
            try:
                med_raw = _read_registered_tileset(archive, "screen-med", resource_path)
                large_raw = _read_registered_tileset(archive, "screen-xlarge", resource_path)
                med = parse_tileset_collision_fields(med_raw)
                large = parse_tileset_collision_fields(large_raw)
            except (TilesetFormatError, ValueError, UnicodeDecodeError, struct.error) as exc:
                row["parse_error_type"] = type(exc).__name__
                details.append(row)
                continue

            row["parse_status"] = "parsed"
            row["cross_pack_semantic_metadata_equal"] = _semantic_signature(med) == _semantic_signature(large)
            row["header"] = {
                "tile_width": med["tile_width"],
                "tile_height": med["tile_height"],
                "atlas_tile_width": med["atlas_tile_width"],
                "atlas_tile_height": med["atlas_tile_height"],
                "collision_category": med["collision_category"],
                "collision_bitmask": med["collision_bitmask"],
                "layer_count": med["layer_count"],
            }
            row["layers"] = [
                {
                    "layer_index": layer["layer_index"],
                    "texture_ref": layer["texture_ref"],
                    "tile_count": layer["tile_count"],
                }
                for layer in med["layers"]
            ]
            if med["layer_count"] == 1:
                entries = med["layers"][0]["tiles"]
                for tile_id_text, frequency in sorted(
                    atlas_row["tile_id_frequencies"].items(), key=lambda item: int(item[0])
                ):
                    tile_id = int(tile_id_text)
                    if tile_id >= len(entries):
                        row["tile_id_out_of_range"].append({"tile_id": tile_id, "frequency": frequency})
                        continue
                    tile = entries[tile_id]
                    row["used_tile_records"].append({
                        "tile_id": tile_id,
                        "frequency": frequency,
                        "collision_id": tile["collision_id"],
                        "s32_data": tile["s32_data"],
                        "s32_alt1_data": tile["s32_alt1_data"],
                        "opacity_flag_raw": tile["opacity_flag_raw"],
                        "opacity_flag_low_byte": tile["opacity_flag_low_byte"],
                        "shape_marker": tile["shape_marker"],
                        "collision_shape_ref": tile["collision_shape_ref"],
                    })
                row["field_distribution"] = _field_distribution(row["used_tile_records"])
            else:
                row["tile_join_status"] = "not_joined_multiple_layers"
            details.append(row)

    return {
        "schema": "heman-tileset-collision-field-census-v1",
        "source_ipa": routing["source_ipa"],
        "map_pair_audit": routing["screen_pack_map_pair_audit"],
        "resource_registry_summary": routing["resource_registry_summary"],
        "collision_layer_summary": routing["collision_layer_summary"] | {
            "tilesets_parsed": sum(row["parse_status"] == "parsed" for row in details),
            "tilesets_not_parsed": sum(row["parse_status"] != "parsed" for row in details),
            "cross_pack_semantic_parity_failures": sum(
                row["cross_pack_semantic_metadata_equal"] is False for row in details
            ),
        },
        "tilesets": details,
        "original_collision_semantics_verified": False,
        "original_ios_gameplay_trace_compared": False,
        "native_switch_collision_import_authorized": False,
        "interpretation_boundary": (
            "Field names are grounded by the original runtime accessors and loader path, but "
            "this census does not establish what collision IDs, S32 fields, categories, bitmasks, "
            "shape markers or opacity flags do during gameplay. It contains aggregate cell "
            "frequencies, not map names or per-cell coordinates."
        ),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", required=True, type=Path, help="owner-held IPA; read in memory only")
    parser.add_argument("--out", required=True, type=Path, help="JSON output beneath ignored local_reports/")
    args = parser.parse_args(argv)
    if not args.ipa.is_file() or args.ipa.is_symlink():
        parser.error("--ipa must be an existing regular non-symlink file")
    try:
        output = private_output_path(args.out)
        report = audit_tileset_collision_fields(args.ipa)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                          encoding="utf-8")
    except (OSError, zipfile.BadZipFile, ValueError, KeyError, struct.error) as exc:
        parser.error(f"tileset collision-field census failed: {type(exc).__name__}: {exc}")
    print(
        f"Stage259 parsed {report['collision_layer_summary']['tilesets_parsed']} registered "
        "tilesets; private aggregate saved under local_reports/"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
