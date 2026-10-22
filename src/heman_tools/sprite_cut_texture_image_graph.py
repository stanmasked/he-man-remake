"""Stage185: private, aggregate-only SpriteSequence -> cut -> texture -> image audit.

This module validates the resource-reference chain without exporting original
resource identifiers, paths, image bytes, per-record fields, or private reports.
The five-u32 SpriteCut tuples are preserved as opaque fields except that their
first value is checked against the tuple's zero-based position. Their other
field semantics are deliberately not inferred.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
import stat
import struct
from zipfile import ZipFile

from .collision_inventory import private_output_path
from .physics_shape_census import PREFIX, SCREENS, MAX_MEMBERS, _safe_read
from .sprite_repo_wad_index import (
    MAX_REPO_BYTES, MAX_WAD_BYTES, SpriteIndexFormatError,
    parse_sprite_repository, _text,
)
from .sprite_sequence_native_loader_structure import _parse_native_sequence
from .sprite_wad_record_intervals import _intervals

MAX_IMAGE_ENTRIES = 5000
MAX_IMAGE_REPO_BYTES = 1_000_000
MAX_CUT_TUPLES = 2048
TEXTURE_OPAQUE_HEADER_BYTES = 15
_U16 = struct.Struct("<H")
_U32 = struct.Struct("<I")
_TUPLE5 = struct.Struct("<IIIII")
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class SpriteResourceGraphError(ValueError):
    """An invalid or incomplete source resource-reference graph."""


def _valid_image_path(path: str) -> bool:
    if (not isinstance(path, str) or not path.startswith("/textures/")
            or not path.endswith(".png") or "\\" in path or "\x00" in path):
        return False
    parts = path[1:].split("/")
    return all(part not in ("", ".", "..") for part in parts)


def parse_image_repository(raw: bytes) -> tuple[tuple[str, str], ...]:
    """Parse ImageData.repo, whose entry marker/path envelope differs from .repo WAD indexes."""
    if type(raw) is not bytes or not 12 <= len(raw) <= MAX_IMAGE_REPO_BYTES:
        raise SpriteResourceGraphError("Invalid ImageData repository size")
    label, at = _text(raw, 0)
    if label != "ImageData" or at + 6 > len(raw):
        raise SpriteResourceGraphError("Invalid ImageData repository header")
    reserved = _U16.unpack_from(raw, at)[0]
    count = _U32.unpack_from(raw, at + 2)[0]
    at += 6
    if reserved != 0 or not 1 <= count <= MAX_IMAGE_ENTRIES:
        raise SpriteResourceGraphError("Invalid ImageData repository count")
    result = []
    seen = set()
    for _ in range(count):
        key, at = _text(raw, at)
        if at + 4 > len(raw):
            raise SpriteResourceGraphError("Truncated ImageData entry marker")
        marker = _U32.unpack_from(raw, at)[0]
        at += 4
        path, at = _text(raw, at)
        if at + 4 > len(raw):
            raise SpriteResourceGraphError("Truncated ImageData entry offset")
        offset = _U32.unpack_from(raw, at)[0]
        at += 4
        if key in seen or marker != 1 or offset != 0 or not _valid_image_path(path):
            raise SpriteResourceGraphError("Invalid ImageData entry")
        seen.add(key)
        result.append((key, path))
    if at != len(raw):
        raise SpriteResourceGraphError("ImageData repository has trailing bytes")
    return tuple(result)


def parse_sprite_cut_record(record: bytes) -> tuple[str, str, tuple[tuple[int, int, int, int, int], ...]]:
    """Parse a cut key, texture key, count, and exact sequence of five-u32 tuples."""
    if type(record) is not bytes or len(record) > MAX_WAD_BYTES:
        raise SpriteResourceGraphError("Invalid SpriteCut record")
    key, at = _text(record, 0)
    texture_key, at = _text(record, at)
    if at + _U32.size > len(record):
        raise SpriteResourceGraphError("Missing SpriteCut tuple count")
    count = _U32.unpack_from(record, at)[0]
    at += _U32.size
    if (not 1 <= count <= MAX_CUT_TUPLES
            or len(record) - at != count * _TUPLE5.size):
        raise SpriteResourceGraphError("SpriteCut tuple count does not match exact record length")
    tuples = tuple(_TUPLE5.unpack_from(record, at + i * _TUPLE5.size)
                   for i in range(count))
    if any(item[0] != ordinal for ordinal, item in enumerate(tuples)):
        raise SpriteResourceGraphError("SpriteCut first tuple field is not its zero-based ordinal")
    return key, texture_key, tuples


def parse_texture_data_record(record: bytes) -> tuple[str, str, bytes]:
    """Parse the texture key, opaque 15-byte block, and image key with exact EOF."""
    if type(record) is not bytes or len(record) > MAX_WAD_BYTES:
        raise SpriteResourceGraphError("Invalid TextureData record")
    key, at = _text(record, 0)
    if at + TEXTURE_OPAQUE_HEADER_BYTES > len(record):
        raise SpriteResourceGraphError("Truncated TextureData opaque block")
    opaque = record[at:at + TEXTURE_OPAQUE_HEADER_BYTES]
    at += TEXTURE_OPAQUE_HEADER_BYTES
    image_key, at = _text(record, at)
    if at != len(record):
        raise SpriteResourceGraphError("TextureData record has trailing bytes")
    return key, image_key, opaque


def _require_screen_pair(groups: tuple[dict[str, bytes], ...]) -> None:
    if any(not isinstance(group, dict) or set(group) != set(SCREENS) for group in groups):
        raise SpriteResourceGraphError("Both original screen-resolution packs are required")
    for group in groups:
        if any(type(value) is not bytes for value in group.values()):
            raise SpriteResourceGraphError("Resource pack entries must be bytes")


def _parse_sequence_pack(repository: bytes, wad: bytes):
    rows = parse_sprite_repository(
        repository, expected_label="SpriteSeqData", expected_wad="sprite/SpriteSeqData.wad")
    records = _intervals(rows, wad)
    result = []
    for row, record in zip(rows, records):
        item = _parse_native_sequence(record)
        if item.key != row.key:
            raise SpriteIndexFormatError("SpriteSequence record key mismatch")
        result.append(item)
    return tuple(result)


def _parse_cut_pack(repository: bytes, wad: bytes):
    rows = parse_sprite_repository(
        repository, expected_label="SpriteCutData", expected_wad="sprite/SpriteResData.wad")
    records = _intervals(rows, wad)
    result = []
    for row, record in zip(rows, records):
        key, texture_key, tuples = parse_sprite_cut_record(record)
        if key != row.key:
            raise SpriteIndexFormatError("SpriteCut record key mismatch")
        result.append((key, texture_key, tuples))
    return tuple(result)


def _parse_texture_pack(repository: bytes, wad: bytes):
    rows = parse_sprite_repository(
        repository, expected_label="TextureData", expected_wad="textureData/TextureData.wad")
    records = _intervals(rows, wad)
    result = []
    for row, record in zip(rows, records):
        key, image_key, opaque = parse_texture_data_record(record)
        if key != row.key:
            raise SpriteIndexFormatError("TextureData record key mismatch")
        result.append((key, image_key, opaque))
    return tuple(result)


def _resolve_image_paths(screen: str, entries: tuple[tuple[str, str], ...],
                         member_headers: dict[str, bytes]) -> dict:
    """Resolve case-sensitive bundle paths, allowing unique case-only source aliases."""
    texture_prefix = f"{PREFIX}{screen}/textures/"
    files = {name: header for name, header in member_headers.items()
             if name.startswith(texture_prefix)}
    folded: dict[str, str] = {}
    for name in files:
        key = name.casefold()
        if key in folded and folded[key] != name:
            raise SpriteResourceGraphError("Ambiguous case-insensitive texture member path")
        folded[key] = name
    exact = 0
    fallback = 0
    resolved = set()
    alias_groups: dict[str, list[str]] = defaultdict(list)
    for key, path in entries:
        requested = f"{PREFIX}{screen}{path}"
        alias_groups[path.casefold()].append(path)
        if requested in files:
            actual = requested
            exact += 1
        else:
            actual = folded.get(requested.casefold())
            if actual is None:
                raise SpriteResourceGraphError("ImageData path does not resolve to a texture member")
            fallback += 1
        header = files[actual]
        if (len(header) < 24 or header[:8] != _PNG_SIGNATURE
                or header[12:16] != b"IHDR"):
            raise SpriteResourceGraphError("Resolved ImageData member is not a valid PNG header")
        width, height = struct.unpack_from(">II", header, 16)
        if width == 0 or height == 0:
            raise SpriteResourceGraphError("Resolved PNG has an empty dimension")
        resolved.add(actual)
    duplicates = [paths for paths in alias_groups.values() if len(paths) > 1]
    return {
        "image_data_entries": len(entries),
        "image_data_paths_resolved": len(entries),
        "unique_png_members_verified": len(resolved),
        "exact_case_path_entries": exact,
        "casefold_only_path_entries": fallback,
        "casefold_alias_groups": len(duplicates),
        "casefold_alias_extra_entries": sum(len(paths) - 1 for paths in duplicates),
    }


def summarize_sprite_cut_texture_image_graph(
    sequence_repositories: dict[str, bytes],
    sequence_wads: dict[str, bytes],
    cut_repositories: dict[str, bytes],
    cut_wads: dict[str, bytes],
    texture_repositories: dict[str, bytes],
    texture_wads: dict[str, bytes],
    image_repositories: dict[str, bytes],
    image_member_headers: dict[str, dict[str, bytes]],
) -> dict:
    """Validate the cross-resource graph and return aggregate-only evidence."""
    groups = (sequence_repositories, sequence_wads, cut_repositories, cut_wads,
              texture_repositories, texture_wads, image_repositories)
    _require_screen_pair(groups)
    if not isinstance(image_member_headers, dict) or set(image_member_headers) != set(SCREENS):
        raise SpriteResourceGraphError("Both screen packs need image member headers")
    for screen in SCREENS:
        if not isinstance(image_member_headers[screen], dict):
            raise SpriteResourceGraphError("Image member header map is invalid")
        if any(not isinstance(name, str) or type(header) is not bytes
               for name, header in image_member_headers[screen].items()):
            raise SpriteResourceGraphError("Image member header entries are invalid")

    repo_groups = (sequence_repositories, cut_repositories,
                   texture_repositories, image_repositories)
    if any(group[SCREENS[0]] != group[SCREENS[1]] for group in repo_groups):
        raise SpriteResourceGraphError("Paired resource repository indexes differ")

    per_screen = {}
    private_sequences = {}
    private_cuts = {}
    private_textures = {}
    private_images = {}
    for screen in SCREENS:
        sequences = _parse_sequence_pack(sequence_repositories[screen], sequence_wads[screen])
        cuts = _parse_cut_pack(cut_repositories[screen], cut_wads[screen])
        textures = _parse_texture_pack(texture_repositories[screen], texture_wads[screen])
        images = parse_image_repository(image_repositories[screen])
        cut_keys = {item[0] for item in cuts}
        texture_keys = {item[0] for item in textures}
        image_keys = {item[0] for item in images}
        if len(cut_keys) != len(cuts) or len(texture_keys) != len(textures):
            raise SpriteResourceGraphError("Duplicate cut or texture key")
        cut_to_texture = sum(texture_key in texture_keys for _, texture_key, _ in cuts)
        texture_to_image = sum(image_key in image_keys for _, image_key, _ in textures)
        if cut_to_texture != len(cuts):
            raise SpriteResourceGraphError("SpriteCut references a missing TextureData key")
        if texture_to_image != len(textures):
            raise SpriteResourceGraphError("TextureData references a missing ImageData key")

        symbol_names = [name for sequence in sequences for frame in sequence.frames
                        for name in frame.symbol_names]
        indexed_symbols = sum(name in cut_keys for name in symbol_names)
        tuple_count = sum(len(tuples) for _, _, tuples in cuts)
        cut_summary = _resolve_image_paths(screen, images, image_member_headers[screen])
        per_screen[screen] = {
            "sequence_records": len(sequences),
            "sequence_frames": sum(len(item.frames) for item in sequences),
            "symbol_references": len(symbol_names),
            "symbol_references_matching_cut_index": indexed_symbols,
            "symbol_references_without_cut_index_match": len(symbol_names) - indexed_symbols,
            "cut_records": len(cuts),
            "cut_to_texture_links": cut_to_texture,
            "cut_tuple_entries": tuple_count,
            "cut_tuple_first_fields_matching_ordinals": tuple_count,
            "texture_records": len(textures),
            "texture_to_image_links": texture_to_image,
            **cut_summary,
        }
        private_sequences[screen] = sequences
        private_cuts[screen] = cuts
        private_textures[screen] = textures
        private_images[screen] = images

    left, right = SCREENS
    left_seq, right_seq = private_sequences[left], private_sequences[right]
    if len(left_seq) != len(right_seq):
        raise SpriteResourceGraphError("Paired sequence counts differ")
    for first, second in zip(left_seq, right_seq):
        if first.key != second.key or len(first.frames) != len(second.frames):
            raise SpriteResourceGraphError("Paired sequence identity/frame counts differ")
        if any(a.symbol_names != b.symbol_names for a, b in zip(first.frames, second.frames)):
            raise SpriteResourceGraphError("Paired symbol references differ")

    left_cuts, right_cuts = private_cuts[left], private_cuts[right]
    if len(left_cuts) != len(right_cuts):
        raise SpriteResourceGraphError("Paired SpriteCut counts differ")
    for first, second in zip(left_cuts, right_cuts):
        if (first[0] != second[0] or first[1] != second[1]
                or len(first[2]) != len(second[2])
                or tuple(x[0] for x in first[2]) != tuple(x[0] for x in second[2])):
            raise SpriteResourceGraphError("Paired SpriteCut reference or tuple structure differs")
    left_textures, right_textures = private_textures[left], private_textures[right]
    if [(k, image) for k, image, _ in left_textures] != [
            (k, image) for k, image, _ in right_textures]:
        raise SpriteResourceGraphError("Paired TextureData image links differ")
    if private_images[left] != private_images[right]:
        raise SpriteResourceGraphError("Paired ImageData repositories differ")

    return {
        "classification": "private_sprite_sequence_cut_texture_image_reference_graph",
        "per_resolution_pack": per_screen,
        "paired_pack_checks": {
            "sequence_keys_frame_counts_and_symbol_references_match": True,
            "cut_keys_texture_links_and_tuple_counts_match": True,
            "texture_to_image_key_links_match": True,
            "image_repository_entries_match": True,
        },
        "texture_opaque_header_bytes": TEXTURE_OPAQUE_HEADER_BYTES,
        "sprite_cut_tuple_first_field_is_zero_based_ordinal": True,
        "sprite_cut_tuple_remaining_field_semantics_verified": False,
        "sprite_cut_tuples_confirmed_as_texture_rectangles": False,
        "original_actor_state_to_sequence_binding_verified": False,
        "original_animation_transform_and_render_order_verified": False,
        "original_animation_timebase_calibrated": False,
        "original_resource_names_paths_values_offsets_or_bytes_exported": False,
        "source_art_or_private_reports_included": False,
    }


def audit_private_sprite_cut_texture_image_graph(ipa: Path) -> dict:
    """Read only bounded index/WAD members and PNG headers from the owner-private IPA."""
    if not ipa.is_file():
        raise ValueError("Owner-private original IPA missing")
    with ZipFile(ipa, "r") as archive:
        infos = archive.infolist()
        if len(infos) > MAX_MEMBERS:
            raise ValueError("Excessive original ZIP member count")
        lookup = {}
        for info in infos:
            if info.filename in lookup:
                raise ValueError("Duplicate original ZIP member")
            lookup[info.filename] = info
        sequence_repositories = {}
        sequence_wads = {}
        cut_repositories = {}
        cut_wads = {}
        texture_repositories = {}
        texture_wads = {}
        image_repositories = {}
        image_member_headers = {}
        for screen in SCREENS:
            root = f"{PREFIX}{screen}/"
            sequence_repositories[screen] = _safe_read(
                archive, lookup.get(root + "meta/SpriteSeqData.repo"), MAX_REPO_BYTES)
            sequence_wads[screen] = _safe_read(
                archive, lookup.get(root + "sprite/SpriteSeqData.wad"), MAX_WAD_BYTES)
            cut_repositories[screen] = _safe_read(
                archive, lookup.get(root + "meta/SpriteCutData.repo"), MAX_REPO_BYTES)
            cut_wads[screen] = _safe_read(
                archive, lookup.get(root + "sprite/SpriteResData.wad"), MAX_WAD_BYTES)
            texture_repositories[screen] = _safe_read(
                archive, lookup.get(root + "meta/TextureData.repo"), MAX_REPO_BYTES)
            texture_wads[screen] = _safe_read(
                archive, lookup.get(root + "textureData/TextureData.wad"), MAX_WAD_BYTES)
            image_repositories[screen] = _safe_read(
                archive, lookup.get(root + "meta/ImageData.repo"), MAX_IMAGE_REPO_BYTES)
            headers = {}
            texture_root = root + "textures/"
            for info in infos:
                if not info.is_dir() and info.filename.startswith(texture_root):
                    is_link = stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK
                    if is_link or info.flag_bits & 1:
                        headers[info.filename] = b""
                    else:
                        with archive.open(info, "r") as stream:
                            headers[info.filename] = stream.read(24)
            image_member_headers[screen] = headers
    return summarize_sprite_cut_texture_image_graph(
        sequence_repositories, sequence_wads, cut_repositories, cut_wads,
        texture_repositories, texture_wads, image_repositories, image_member_headers,
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    destination = private_output_path(args.out)
    report = audit_private_sprite_cut_texture_image_graph(args.ipa)
    destination.parent.mkdir(parents=True, exist_ok=True)
    import json
    destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Private sprite resource graph validated; aggregate-only report saved locally.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
