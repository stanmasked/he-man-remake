"""Stage189: private, fail-closed single-symbol sprite-frame crop.

The tool reads the owner-held IPA locally and writes only to ignored
local_reports/. It never serializes original resource names, paths, offsets,
image bytes, or per-record values into its JSON report or public repository.
"""
from __future__ import annotations

import argparse
import io
import json
import math
from pathlib import Path
import stat
import struct
from zipfile import ZipFile

from .collision_inventory import private_output_path
from .physics_shape_census import PREFIX, SCREENS, MAX_MEMBERS, _safe_read
from .player_sequence_alias_census import (
    _ALIAS, _IGNORED_TOKENS, _find_sequence_references,
    _length_prefixed_ascii_tokens,
)
from .sprite_cut_texture_image_graph import (
    MAX_IMAGE_REPO_BYTES, _valid_image_path, parse_image_repository,
    parse_sprite_cut_record, parse_texture_data_record,
)
from .sprite_repo_wad_index import (
    MAX_REPO_BYTES, MAX_WAD_BYTES, parse_sprite_repository,
)
from .sprite_sequence_native_loader_structure import (
    MAX_SEQUENCE_BYTES, _RecordReader, _parse_native_sequence,
)
from .sprite_wad_record_intervals import _intervals
from .sprite_cut_wrap_bounds_audit import decode_texture_wrap_codes
from .symbol_frame_assembler import (
    SymbolFrameAssemblyError, assemble_symbol_frame,
)
from .symbol_frame_render_plan import (
    PlayerTransform, SymbolLayerInput, build_symbol_frame_render_plan,
)
from .symbol_render_contract import SymbolRenderContract

MAX_GO_BYTES = 8_000_000
MAX_PNG_BYTES = 32_000_000
_U32 = struct.Struct("<I")
_I32 = struct.Struct("<i")
_F32 = struct.Struct("<f")
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class PrivateFrameDecodeError(ValueError):
    """A single-symbol crop cannot be resolved without guessing."""


def parse_single_symbol_frame(record: bytes, frame_index: int) -> dict:
    """Strictly parse a sequence record and return one frame's sole symbol."""
    sequence = _parse_native_sequence(record)
    if type(frame_index) is not int or not 0 <= frame_index < len(sequence.frames):
        raise PrivateFrameDecodeError("Frame index is outside the sequence")
    reader = _RecordReader(record)
    sequence_key = reader.utf16()
    reader.s32()  # loop field
    frame_count = reader.s32()
    reader.s32()  # third sequence field
    selected = None
    for index in range(frame_count):
        header = tuple(reader.s32() for _ in range(4))
        reader.u8()
        symbol_count = reader.s32()
        symbols = []
        for _ in range(symbol_count):
            reader.s32()
            reader.s32()
            name = reader.utf16(allow_empty=True)
            fields = tuple(reader.s32() for _ in range(4))
            transforms = tuple(_F32.unpack(reader.take(4))[0] for _ in range(6))
            serialized_tail = tuple(reader.s32() for _ in range(7))
            symbols.append({
                "name": name,
                "cut_handle": fields[0],
                "serialized_fields": fields,
                "transform_values": transforms,
                "serialized_tail": serialized_tail,
            })
        if index == frame_index:
            selected = {"sequence_key": sequence_key, "frame_index": index,
                        "frame_time_field": header[1], "symbol_count": symbol_count,
                        "symbols": symbols}
    if reader.pos != len(record):
        raise PrivateFrameDecodeError("Sequence parser did not reach exact EOF")
    if selected is None or selected["symbol_count"] != 1:
        raise PrivateFrameDecodeError("Only a single-symbol frame is supported")
    symbol = selected["symbols"][0]
    if not symbol["name"]:
        raise PrivateFrameDecodeError("Frame symbol has an empty resource name")
    if not all(math.isfinite(value) for value in symbol["transform_values"]):
        raise PrivateFrameDecodeError("Frame symbol has non-finite transform fields")
    return selected


def resolve_alias_pair(
    go_data: bytes, sequence_keys: set[str] | frozenset[str],
    region: tuple[int, int], alias: str,
) -> tuple[str, str]:
    """Resolve exactly one east/west pair for one alias in one bounded region."""
    if not isinstance(alias, str) or not _ALIAS.fullmatch(alias):
        raise PrivateFrameDecodeError("Alias is not a valid short identifier")
    if (not isinstance(region, tuple) or len(region) != 2
            or type(region[0]) is not int or type(region[1]) is not int
            or not 0 <= region[0] < region[1] <= len(go_data)):
        raise PrivateFrameDecodeError("Alias region bounds are invalid")
    start, end = region
    tokens = _length_prefixed_ascii_tokens(go_data, start, end)
    aliases = [(pos, value) for pos, value in tokens
               if value not in sequence_keys and value not in _IGNORED_TOKENS
               and _ALIAS.fullmatch(value)]
    refs = _find_sequence_references(go_data, frozenset(sequence_keys), start, end)
    matches = []
    ambiguous = False
    for index, (pos, value) in enumerate(aliases):
        next_pos = aliases[index + 1][0] if index + 1 < len(aliases) else end
        group_refs = [(ref_pos, key) for ref_pos, key in refs
                      if pos < ref_pos < next_pos]
        if value != alias or not group_refs:
            continue
        if len(group_refs) == 2 and {key[-2:] for _, key in group_refs} == {".e", ".w"}:
            east = next(key for _, key in group_refs if key.endswith(".e"))
            west = next(key for _, key in group_refs if key.endswith(".w"))
            matches.append((east, west))
        else:
            ambiguous = True
    if ambiguous or len(matches) != 1:
        raise PrivateFrameDecodeError("Alias pair is missing or ambiguous")
    return matches[0]


def select_cut_rectangle(
    cut_record: bytes, expected_cut_key: str, symbol_name: str, cut_handle: int,
) -> tuple[str, tuple[int, int, int, int]]:
    key, texture_key, tuples = parse_sprite_cut_record(cut_record)
    if key != expected_cut_key or key != symbol_name:
        raise PrivateFrameDecodeError("Symbol does not match the indexed SpriteCut key")
    matches = [item for item in tuples if item[0] == cut_handle]
    if len(matches) != 1:
        raise PrivateFrameDecodeError("SpriteCut handle is missing or ambiguous")
    _, x, y, width, height = matches[0]
    if x < 0 or y < 0 or width <= 0 or height <= 0:
        raise PrivateFrameDecodeError("SpriteCut rectangle has invalid dimensions")
    return texture_key, (x, y, width, height)


def crop_png_bytes(png_bytes: bytes, rectangle: tuple[int, int, int, int]) -> tuple[bytes, tuple[int, int]]:
    """Crop a PNG only when the entire rectangle is in bounds; never clip."""
    if type(png_bytes) is not bytes or len(png_bytes) > MAX_PNG_BYTES:
        raise PrivateFrameDecodeError("Invalid or oversized PNG input")
    if not png_bytes.startswith(_PNG_SIGNATURE):
        raise PrivateFrameDecodeError("Source image is not PNG")
    if (not isinstance(rectangle, tuple) or len(rectangle) != 4
            or any(type(value) is not int for value in rectangle)):
        raise PrivateFrameDecodeError("Rectangle must contain four integers")
    x, y, width, height = rectangle
    if x < 0 or y < 0 or width <= 0 or height <= 0:
        raise PrivateFrameDecodeError("Rectangle has invalid dimensions")
    try:
        from PIL import Image
        source = Image.open(io.BytesIO(png_bytes))
        if source.format != "PNG":
            raise PrivateFrameDecodeError("Decoded source image is not PNG")
        source.load()
        source_size = source.size
        if x + width > source.width or y + height > source.height:
            raise PrivateFrameDecodeError("SpriteCut rectangle exceeds PNG bounds")
        crop = source.convert("RGBA").crop((x, y, x + width, y + height))
        output = io.BytesIO()
        crop.save(output, format="PNG")
    except PrivateFrameDecodeError:
        raise
    except Exception as exc:
        raise PrivateFrameDecodeError("PNG decode failed") from exc
    return output.getvalue(), source_size


def _private_png_output_path(path: Path) -> Path:
    root_path = Path.cwd() / "local_reports"
    if root_path.is_symlink():
        raise ValueError("local_reports must not be a symbolic link")
    root = root_path.resolve()
    destination = path.resolve()
    if (destination == root or not destination.is_relative_to(root)
            or destination.suffix.lower() != ".png"):
        raise ValueError("PNG output must be beneath local_reports/ with a .png suffix")
    parent = destination.parent
    while parent != root and parent.is_relative_to(root):
        if parent.exists() and parent.is_symlink():
            raise ValueError("Private PNG output path must not traverse symbolic links")
        parent = parent.parent
    return destination


def _read_source_member(archive: ZipFile, index: dict, path: str, max_size: int) -> bytes:
    return _safe_read(archive, index.get(path), max_size)


def _assemble_private_symbol_packet_summary(
    symbol: dict,
    rectangle: tuple[int, int, int, int],
    png_dimensions: tuple[int, int],
    wrap_codes: tuple[int, int],
) -> dict:
    """Assemble one isolated CPU packet and return aggregate-only evidence."""
    try:
        contract = SymbolRenderContract.from_serialized_fields(
            symbol["serialized_fields"],
            symbol["transform_values"],
            symbol["serialized_tail"],
        )
        layer = SymbolLayerInput(
            source_order=0,
            contract=contract,
            cut_rectangle=rectangle,
            png_dimensions=png_dimensions,
            wrap_codes=wrap_codes,
        )
        plan = build_symbol_frame_render_plan(
            (layer,), active_mask=0, user_rgba=(1.0, 1.0, 1.0, 1.0)
        )
        assembly = assemble_symbol_frame(
            plan,
            ((rectangle[2], rectangle[3]),),
            active_mask=0,
            player_transform=PlayerTransform(),
        )
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise PrivateFrameDecodeError(
            "Resolved source Symbol could not be assembled without guessing"
        ) from exc

    if assembly.packet_count != 1 or assembly.source_order != (0,):
        raise PrivateFrameDecodeError("Isolated frame did not produce exactly one ordered packet")
    packet = assembly.packets[0]
    if (len(packet.xy) != 8 or len(packet.uv) != 8
            or len(packet.rgba) != 4
            or not all(math.isfinite(value) for value in packet.xy + packet.uv + packet.rgba)):
        raise PrivateFrameDecodeError("Isolated frame packet is incomplete or non-finite")
    return {
        "cpu_frame_packet_assembled": True,
        "cpu_frame_packet_count": assembly.packet_count,
        "cpu_frame_packet_vertex_count": len(packet.xy) // 2,
        "cpu_frame_packet_uv_pair_count": len(packet.uv) // 2,
        "cpu_frame_packet_source_order_preserved": packet.source_order == 0,
        "cpu_frame_packet_finite": True,
        "native_winding_flag_computed": True,
        "native_uv_out_of_unit_interval_preserved": any(
            value < 0.0 or value > 1.0 for value in packet.uv
        ),
        "sprite_player_transform_used_identity_for_isolated_test": True,
        "full_frame_composition_verified": False,
        "original_runtime_pixel_parity_verified": False,
    }


def audit_private_single_symbol_crop(
    ipa: Path, regions: tuple[tuple[int, int], tuple[int, int]], alias: str,
    variant: int, direction: str, frame_index: int, png_output: Path,
    *, assemble_packet: bool = False,
) -> dict:
    if type(assemble_packet) is not bool:
        raise PrivateFrameDecodeError("assemble_packet must be boolean")
    if not ipa.is_file():
        raise ValueError("Owner-private original IPA missing")
    if type(variant) is not int or variant not in (0, 1):
        raise PrivateFrameDecodeError("Variant must select one of the two audited regions")
    if direction not in ("east", "west"):
        raise PrivateFrameDecodeError("Direction must be east or west")
    if not isinstance(regions, tuple) or len(regions) != 2:
        raise PrivateFrameDecodeError("Exactly two component regions are required")
    normalized = []
    for region in regions:
        if (not isinstance(region, tuple) or len(region) != 2
                or type(region[0]) is not int or type(region[1]) is not int
                or not 0 <= region[0] < region[1]):
            raise PrivateFrameDecodeError("Component region bounds are invalid")
        normalized.append(region)
    if normalized[0][1] > normalized[1][0]:
        raise PrivateFrameDecodeError("Component regions overlap or are out of order")
    png_output = _private_png_output_path(png_output)

    with ZipFile(ipa, "r") as archive:
        infos = archive.infolist()
        if len(infos) > MAX_MEMBERS:
            raise ValueError("Excessive original ZIP member count")
        index = {}
        for info in infos:
            if info.filename in index:
                raise ValueError("Duplicate original ZIP member")
            index[info.filename] = info

        source_go = {}
        source_seq_repo = {}
        for screen in SCREENS:
            root = PREFIX + screen + "/"
            source_go[screen] = _read_source_member(
                archive, index, root + "go/default", MAX_GO_BYTES)
            source_seq_repo[screen] = _read_source_member(
                archive, index, root + "meta/SpriteSeqData.repo", MAX_REPO_BYTES)
        if source_go[SCREENS[0]] != source_go[SCREENS[1]]:
            raise PrivateFrameDecodeError("Paired GO default data differ")
        if source_seq_repo[SCREENS[0]] != source_seq_repo[SCREENS[1]]:
            raise PrivateFrameDecodeError("Paired SpriteSequence indexes differ")

        screen = SCREENS[0]
        root = PREFIX + screen + "/"
        sequence_repo_raw = source_seq_repo[screen]
        sequence_wad = _read_source_member(
            archive, index, root + "sprite/SpriteSeqData.wad", MAX_WAD_BYTES)
        cut_repo_raw = _read_source_member(
            archive, index, root + "meta/SpriteCutData.repo", MAX_REPO_BYTES)
        cut_wad = _read_source_member(
            archive, index, root + "sprite/SpriteResData.wad", MAX_WAD_BYTES)
        texture_repo_raw = _read_source_member(
            archive, index, root + "meta/TextureData.repo", MAX_REPO_BYTES)
        texture_wad = _read_source_member(
            archive, index, root + "textureData/TextureData.wad", MAX_WAD_BYTES)
        image_repo_raw = _read_source_member(
            archive, index, root + "meta/ImageData.repo", MAX_IMAGE_REPO_BYTES)

        # Cross-resolution repository equality is a separate integrity gate.
        for relative, raw in (
            ("meta/SpriteCutData.repo", cut_repo_raw),
            ("meta/TextureData.repo", texture_repo_raw),
            ("meta/ImageData.repo", image_repo_raw),
        ):
            other = _read_source_member(
                archive, index, PREFIX + SCREENS[1] + "/" + relative,
                MAX_IMAGE_REPO_BYTES if relative.endswith("ImageData.repo") else MAX_REPO_BYTES)
            if raw != other:
                raise PrivateFrameDecodeError("Paired resource repository indexes differ")

        sequence_rows = parse_sprite_repository(
            sequence_repo_raw, expected_label="SpriteSeqData",
            expected_wad="sprite/SpriteSeqData.wad")
        sequence_keys = frozenset(row.key for row in sequence_rows)
        pair = resolve_alias_pair(source_go[screen], sequence_keys, regions[variant], alias)
        sequence_key = pair[0] if direction == "east" else pair[1]
        sequence_records = _intervals(sequence_rows, sequence_wad)
        sequence_record_by_key = {row.key: record for row, record in zip(sequence_rows, sequence_records)}
        sequence_record = sequence_record_by_key.get(sequence_key)
        if sequence_record is None:
            raise PrivateFrameDecodeError("Resolved sequence key is absent from its WAD index")
        frame = parse_single_symbol_frame(sequence_record, frame_index)
        symbol = frame["symbols"][0]

        cut_rows = parse_sprite_repository(
            cut_repo_raw, expected_label="SpriteCutData",
            expected_wad="sprite/SpriteResData.wad")
        cut_records = _intervals(cut_rows, cut_wad)
        cut_record_by_key = {row.key: record for row, record in zip(cut_rows, cut_records)}
        cut_record = cut_record_by_key.get(symbol["name"])
        if cut_record is None:
            raise PrivateFrameDecodeError("Frame symbol is absent from SpriteCut index")
        texture_key, rectangle = select_cut_rectangle(
            cut_record, symbol["name"], symbol["name"], symbol["cut_handle"])

        texture_rows = parse_sprite_repository(
            texture_repo_raw, expected_label="TextureData",
            expected_wad="textureData/TextureData.wad")
        texture_records = _intervals(texture_rows, texture_wad)
        texture_record_by_key = {row.key: record for row, record in zip(texture_rows, texture_records)}
        texture_record = texture_record_by_key.get(texture_key)
        if texture_record is None:
            raise PrivateFrameDecodeError("SpriteCut texture key is absent from TextureData index")
        texture_record_key, image_key, scalar_block = parse_texture_data_record(texture_record)
        wrap_codes = decode_texture_wrap_codes(scalar_block)
        if texture_record_key != texture_key:
            raise PrivateFrameDecodeError("TextureData record key mismatch")

        image_entries = parse_image_repository(image_repo_raw)
        image_paths = dict(image_entries)
        image_path = image_paths.get(image_key)
        if image_path is None or not _valid_image_path(image_path):
            raise PrivateFrameDecodeError("Texture image key is missing or its path is invalid")

        texture_root = root + "textures/"
        texture_members = {
            info.filename: info for info in infos
            if not info.is_dir() and info.filename.startswith(texture_root)
        }
        folded = {}
        for name in texture_members:
            key = name.casefold()
            if key in folded and folded[key] != name:
                raise PrivateFrameDecodeError("Ambiguous case-insensitive texture member path")
            folded[key] = name
        requested = PREFIX + screen + image_path
        casefold_fallback = False
        if requested in texture_members:
            actual_name = requested
        else:
            actual_name = folded.get(requested.casefold())
            casefold_fallback = actual_name is not None
        if actual_name is None:
            raise PrivateFrameDecodeError("ImageData path does not resolve to a PNG member")
        info = texture_members[actual_name]
        if (info.file_size > MAX_PNG_BYTES or info.flag_bits & 1
                or stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK):
            raise PrivateFrameDecodeError("Resolved PNG member is unsafe or oversized")
        with archive.open(info, "r") as stream:
            png_bytes = stream.read(MAX_PNG_BYTES + 1)
        if len(png_bytes) > MAX_PNG_BYTES:
            raise PrivateFrameDecodeError("Resolved PNG member exceeds size limit")

    crop_bytes, source_size = crop_png_bytes(png_bytes, rectangle)
    packet_summary = None
    if assemble_packet:
        packet_summary = _assemble_private_symbol_packet_summary(
            symbol, rectangle, source_size, wrap_codes
        )
    png_output.parent.mkdir(parents=True, exist_ok=True)
    png_output.write_bytes(crop_bytes)
    crop_width, crop_height = rectangle[2], rectangle[3]
    report = {
        "classification": "private_single_symbol_sprite_crop",
        "source_screen_group": screen,
        "component_variant_index": variant,
        "direction": direction,
        "frame_index": frame_index,
        "frame_symbol_count": frame["symbol_count"],
        "source_png_dimensions": list(source_size),
        "crop_dimensions": [crop_width, crop_height],
        "sprite_rectangle_in_bounds": True,
        "sequence_record_exact_eof_validated": True,
        "sprite_cut_handle_resolved_uniquely": True,
        "texture_to_image_link_resolved": True,
        "image_member_resolved": True,
        "casefold_path_fallback_used": casefold_fallback,
        "symbol_transform_fields_finite": True,
        "symbol_transform_semantics_applied": bool(assemble_packet),
        "full_frame_composition_verified": False,
        "private_crop_written_locally": True,
        "original_resource_keys_paths_offsets_or_bytes_exported": False,
    }
    if packet_summary is not None:
        report.update(packet_summary)
    return report


def _parse_region(value: str) -> tuple[int, int]:
    try:
        first, second = value.split(":", 1)
        return int(first, 10), int(second, 10)
    except (ValueError, TypeError) as exc:
        raise argparse.ArgumentTypeError("Region must be START:END decimal offsets") from exc


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", required=True, type=Path)
    parser.add_argument("--region", action="append", required=True, type=_parse_region,
                        help="private byte window START:END; provide exactly two")
    parser.add_argument("--alias", required=True,
                        help="private short alias from the local source data")
    parser.add_argument("--variant", required=True, type=int, choices=(0, 1))
    parser.add_argument("--direction", required=True, choices=("east", "west"))
    parser.add_argument("--frame", type=int, default=0)
    parser.add_argument(
        "--assemble-packet", action="store_true",
        help="also assemble one bounded CPU packet; report aggregate evidence only",
    )
    parser.add_argument("--png-out", required=True, type=Path)
    parser.add_argument("--report-out", required=True, type=Path)
    args = parser.parse_args(argv)
    if len(args.region) != 2:
        parser.error("exactly two --region values are required")
    destination = private_output_path(args.report_out)
    report = audit_private_single_symbol_crop(
        args.ipa, tuple(args.region), args.alias, args.variant, args.direction,
        args.frame, args.png_out, assemble_packet=args.assemble_packet,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.assemble_packet:
        print("Private single-symbol crop and CPU packet validated; aggregate report saved locally.")
    else:
        print("Private single-symbol frame crop validated and saved locally.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
