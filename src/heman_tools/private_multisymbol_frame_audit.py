"""Stage204: owner-local CLI for bounded multi-Symbol CPU frame audits.

The report contains aggregate evidence only. Original resource names, byte
offsets, coordinates, PNG bytes, and IPA hashes remain local and are not
serialized to GitHub or Actions artifacts. This is CPU packet assembly only;
it does not submit GPU work or claim original-runtime pixel parity.
"""
from __future__ import annotations

import argparse
import json
import stat
from pathlib import Path
from zipfile import ZipFile

from .collision_inventory import private_output_path
from .physics_shape_census import PREFIX, SCREENS, MAX_MEMBERS
from .private_single_symbol_frame_decoder import (
    MAX_GO_BYTES,
    MAX_PNG_BYTES,
    PrivateFrameDecodeError,
    _assemble_private_symbol_frame_packet_summary,
    _read_source_member,
    crop_png_bytes,
    parse_symbol_frame,
    resolve_alias_pair,
    select_cut_rectangle,
)
from .sprite_cut_texture_image_graph import (
    MAX_IMAGE_REPO_BYTES,
    _valid_image_path,
    parse_image_repository,
    parse_texture_data_record,
)
from .sprite_cut_wrap_bounds_audit import decode_texture_wrap_codes
from .sprite_repo_wad_index import MAX_REPO_BYTES, MAX_WAD_BYTES, parse_sprite_repository
from .sprite_wad_record_intervals import _intervals
from .symbol_frame_assembler import MAX_SYMBOL_FRAME_COMMANDS

_S32_MIN = -(1 << 31)
_S32_MAX = (1 << 31) - 1


def _parse_region(value: str) -> tuple[int, int]:
    try:
        first, second = value.split(":", 1)
        region = (int(first, 10), int(second, 10))
    except (ValueError, TypeError) as exc:
        raise argparse.ArgumentTypeError("Region must be START:END decimal offsets") from exc
    if not 0 <= region[0] < region[1]:
        raise argparse.ArgumentTypeError("Region must be a positive START:END interval")
    return region


def _parse_active_mask(value: str) -> int:
    try:
        mask = int(value, 0)
    except (ValueError, TypeError) as exc:
        raise argparse.ArgumentTypeError("Active mask must be a decimal or 0x-prefixed integer") from exc
    if not _S32_MIN <= mask <= _S32_MAX:
        raise argparse.ArgumentTypeError("Active mask must fit a signed 32-bit integer")
    return mask


def _checked_png_dimensions(png_bytes: bytes, rectangle: tuple[int, int, int, int]) -> tuple[int, int]:
    """Decode a PNG and reject a rectangle that would require clipping."""
    _, dimensions = crop_png_bytes(png_bytes, rectangle)
    return dimensions


def _require_rectangle_in_bounds(
    rectangle: tuple[int, int, int, int], dimensions: tuple[int, int]
) -> None:
    x, y, width, height = rectangle
    if (x < 0 or y < 0 or width <= 0 or height <= 0
            or x + width > dimensions[0] or y + height > dimensions[1]):
        raise PrivateFrameDecodeError("SpriteCut rectangle exceeds PNG bounds")


def audit_private_multisymbol_frame(
    ipa: Path,
    regions: tuple[tuple[int, int], tuple[int, int]],
    alias: str,
    variant: int,
    direction: str,
    frame_index: int,
    *,
    active_mask: int = 0,
    source_screen_group: str = SCREENS[0],
    _private_details: list | None = None,
) -> dict:
    """Resolve one original frame and assemble aggregate CPU evidence.

    _private_details is an internal local-only out-parameter for paired-pack
    comparisons. Its contents must never be serialized or sent to GitHub.
    """
    if not ipa.is_file():
        raise ValueError("Owner-private original IPA missing")
    if type(variant) is not int or variant not in (0, 1):
        raise PrivateFrameDecodeError("Variant must select one of the two audited regions")
    if direction not in ("east", "west"):
        raise PrivateFrameDecodeError("Direction must be east or west")
    if type(active_mask) is not int or not _S32_MIN <= active_mask <= _S32_MAX:
        raise PrivateFrameDecodeError("Active mask must be a signed 32-bit integer")
    if source_screen_group not in SCREENS:
        raise PrivateFrameDecodeError("Unsupported source screen group")
    if _private_details is not None and type(_private_details) is not list:
        raise PrivateFrameDecodeError("Private detail collector must be a list")
    if not isinstance(regions, tuple) or len(regions) != 2:
        raise PrivateFrameDecodeError("Exactly two component regions are required")
    for region in regions:
        if (not isinstance(region, tuple) or len(region) != 2
                or type(region[0]) is not int or type(region[1]) is not int
                or not 0 <= region[0] < region[1]):
            raise PrivateFrameDecodeError("Component region bounds are invalid")
    if regions[0][1] > regions[1][0]:
        raise PrivateFrameDecodeError("Component regions overlap or are out of order")

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
        source_sequence_repo = {}
        for screen_name in SCREENS:
            root_name = PREFIX + screen_name + "/"
            source_go[screen_name] = _read_source_member(
                archive, index, root_name + "go/default", MAX_GO_BYTES
            )
            source_sequence_repo[screen_name] = _read_source_member(
                archive, index, root_name + "meta/SpriteSeqData.repo", MAX_REPO_BYTES
            )
        if source_go[SCREENS[0]] != source_go[SCREENS[1]]:
            raise PrivateFrameDecodeError("Paired GO default data differ")
        if any(end > len(source_go[SCREENS[0]]) for _, end in regions):
            raise PrivateFrameDecodeError("Component region exceeds the source GO data")
        if source_sequence_repo[SCREENS[0]] != source_sequence_repo[SCREENS[1]]:
            raise PrivateFrameDecodeError("Paired SpriteSequence indexes differ")

        screen = source_screen_group
        root = PREFIX + screen + "/"
        resource_payloads = {}
        for relative, maximum in (
            ("meta/SpriteCutData.repo", MAX_REPO_BYTES),
            ("meta/TextureData.repo", MAX_REPO_BYTES),
            ("meta/ImageData.repo", MAX_IMAGE_REPO_BYTES),
        ):
            first = _read_source_member(archive, index, root + relative, maximum)
            second = _read_source_member(
                archive, index, PREFIX + SCREENS[1] + "/" + relative, maximum
            )
            if first != second:
                raise PrivateFrameDecodeError("Paired resource repository indexes differ")
            resource_payloads[relative] = first

        sequence_repo = source_sequence_repo[screen]
        sequence_wad = _read_source_member(
            archive, index, root + "sprite/SpriteSeqData.wad", MAX_WAD_BYTES
        )
        cut_wad = _read_source_member(
            archive, index, root + "sprite/SpriteResData.wad", MAX_WAD_BYTES
        )
        texture_wad = _read_source_member(
            archive, index, root + "textureData/TextureData.wad", MAX_WAD_BYTES
        )

        sequence_rows = parse_sprite_repository(
            sequence_repo, expected_label="SpriteSeqData",
            expected_wad="sprite/SpriteSeqData.wad",
        )
        sequence_keys = frozenset(row.key for row in sequence_rows)
        east_west_pair = resolve_alias_pair(
            source_go[screen], sequence_keys, regions[variant], alias
        )
        sequence_key = east_west_pair[0] if direction == "east" else east_west_pair[1]
        sequence_records = _intervals(sequence_rows, sequence_wad)
        sequence_by_key = {
            row.key: record for row, record in zip(sequence_rows, sequence_records)
        }
        sequence_record = sequence_by_key.get(sequence_key)
        if sequence_record is None:
            raise PrivateFrameDecodeError("Resolved sequence key is absent from its WAD index")
        frame = parse_symbol_frame(sequence_record, frame_index)
        if frame["sequence_key"] != sequence_key:
            raise PrivateFrameDecodeError("Sequence record key does not match its repository index")
        symbols = frame["symbols"]
        if len(symbols) < 2:
            raise PrivateFrameDecodeError("Stage204 requires a frame containing at least two Symbols")
        if len(symbols) > MAX_SYMBOL_FRAME_COMMANDS:
            raise PrivateFrameDecodeError("Frame exceeds the bounded command limit")

        cut_rows = parse_sprite_repository(
            resource_payloads["meta/SpriteCutData.repo"],
            expected_label="SpriteCutData", expected_wad="sprite/SpriteResData.wad",
        )
        cut_records = _intervals(cut_rows, cut_wad)
        cut_by_key = {row.key: record for row, record in zip(cut_rows, cut_records)}

        texture_rows = parse_sprite_repository(
            resource_payloads["meta/TextureData.repo"],
            expected_label="TextureData", expected_wad="textureData/TextureData.wad",
        )
        texture_records = _intervals(texture_rows, texture_wad)
        texture_by_key = {row.key: record for row, record in zip(texture_rows, texture_records)}

        image_entries = parse_image_repository(resource_payloads["meta/ImageData.repo"])
        image_paths = dict(image_entries)
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

        rectangles = []
        png_dimensions = []
        wrap_codes = []
        dimensions_by_member = {}
        resolved_symbol_count = 0
        for symbol in symbols:
            cut_record = cut_by_key.get(symbol["name"])
            if cut_record is None:
                raise PrivateFrameDecodeError("Frame Symbol is absent from SpriteCut index")
            texture_key, rectangle = select_cut_rectangle(
                cut_record, symbol["name"], symbol["name"], symbol["cut_handle"]
            )
            texture_record = texture_by_key.get(texture_key)
            if texture_record is None:
                raise PrivateFrameDecodeError("SpriteCut texture key is absent from TextureData index")
            record_key, image_key, scalar_block = parse_texture_data_record(texture_record)
            if record_key != texture_key:
                raise PrivateFrameDecodeError("TextureData record key mismatch")
            image_path = image_paths.get(image_key)
            if image_path is None or not _valid_image_path(image_path):
                raise PrivateFrameDecodeError("Texture image key is missing or its path is invalid")

            requested = PREFIX + screen + image_path
            if requested in texture_members:
                actual_name = requested
            else:
                actual_name = folded.get(requested.casefold())
            if actual_name is None:
                raise PrivateFrameDecodeError("ImageData path does not resolve to a PNG member")
            info = texture_members[actual_name]
            if (info.file_size > MAX_PNG_BYTES or info.flag_bits & 1
                    or stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK):
                raise PrivateFrameDecodeError("Resolved PNG member is unsafe or oversized")

            dimensions = dimensions_by_member.get(actual_name)
            if dimensions is None:
                with archive.open(info, "r") as stream:
                    png_bytes = stream.read(MAX_PNG_BYTES + 1)
                if len(png_bytes) > MAX_PNG_BYTES or len(png_bytes) != info.file_size:
                    raise PrivateFrameDecodeError("Resolved PNG member is oversized or incomplete")
                dimensions = _checked_png_dimensions(png_bytes, rectangle)
                dimensions_by_member[actual_name] = dimensions
            else:
                _require_rectangle_in_bounds(rectangle, dimensions)

            rectangles.append(rectangle)
            png_dimensions.append(dimensions)
            wrap_codes.append(decode_texture_wrap_codes(scalar_block))
            resolved_symbol_count += 1

    summary = _assemble_private_symbol_frame_packet_summary(
        symbols, tuple(rectangles), tuple(png_dimensions), tuple(wrap_codes),
        active_mask=active_mask,
    )
    if _private_details is not None:
        # Retain private values only in caller memory for paired-pack comparison.
        # They are deliberately absent from the public aggregate report.
        _private_details.append({
            "symbols": tuple(symbols),
            "rectangles": tuple(rectangles),
            "png_dimensions": tuple(png_dimensions),
            "wrap_codes": tuple(wrap_codes),
        })
    return {
        "classification": "private_multisymbol_frame_packet_audit",
        "source_screen_group": screen,
        "component_variant_index": variant,
        "direction": direction,
        "frame_index": frame_index,
        "frame_has_at_least_two_symbols": True,
        "source_symbol_count": len(symbols),
        "resolved_symbol_count": resolved_symbol_count,
        "all_sprite_rectangles_in_bounds": True,
        "all_resource_links_resolved_uniquely": True,
        "all_source_pngs_validated": True,
        "active_mask_source": "CLI argument or default zero; not recovered from runtime",
        "runtime_active_mask_verified": False,
        "sprite_player_transform_used_identity_for_isolated_test": True,
        "full_frame_composition_verified": False,
        "original_runtime_pixel_parity_verified": False,
        "private_resource_details_exported": False,
        **summary,
    }


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
    parser.add_argument("--active-mask", type=_parse_active_mask, default=0,
                        help="auditor-supplied signed 32-bit mask (decimal or 0x-prefixed)")
    parser.add_argument("--screen", choices=SCREENS, default=SCREENS[0],
                        help="source resolution pack to audit (default: screen-med)")
    parser.add_argument("--report-out", required=True, type=Path)
    args = parser.parse_args(argv)
    if len(args.region) != 2:
        parser.error("exactly two --region values are required")
    destination = private_output_path(args.report_out)
    report = audit_private_multisymbol_frame(
        args.ipa, tuple(args.region), args.alias, args.variant, args.direction,
        args.frame, active_mask=args.active_mask,
        source_screen_group=args.screen,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print("Private multi-Symbol CPU frame packet audit validated; aggregate report saved locally.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
