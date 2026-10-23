"""Stage194: correlate residual SpriteCut bounds with native TextureData wrap modes.

The original ARMv7 TextureData loader maps one-byte wrap IDs 0/1 to
GL_CLAMP_TO_EDGE/GL_REPEAT. This private audit emits aggregate counts only;
it does not repair, clip, render, or export any original resource records.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from zipfile import ZipFile

from .collision_inventory import private_output_path
from .physics_shape_census import MAX_MEMBERS, PREFIX, SCREENS, _safe_read
from .sprite_cut_png_bounds_census import _load_private_cut_rows
from .sprite_cut_texture_image_graph import (
    parse_sprite_cut_record, parse_texture_data_record,
)
from .sprite_repo_wad_index import (
    MAX_REPO_BYTES, MAX_WAD_BYTES,
    parse_sprite_repository,
)
from .sprite_wad_record_intervals import _intervals
from .sprite_cut_runtime_texture_bounds import classify_allocated_cut

_TEXTURE_WRAP_CODES = {0: "clamp_to_edge", 1: "repeat"}


class SpriteCutWrapAuditError(ValueError):
    """A texture wrap code or cut-to-texture relationship is unresolved."""


def decode_texture_wrap_codes(scalar_block: bytes) -> tuple[int, int]:
    """Read the two native wrap IDs at byte offsets 10 and 11 of the 13-byte block."""
    if type(scalar_block) is not bytes or len(scalar_block) != 13:
        raise SpriteCutWrapAuditError("TextureData scalar block must contain exactly 13 bytes")
    return scalar_block[10], scalar_block[11]


def texture_wrap_mode(code: int) -> str:
    """Name only the two wrap IDs confirmed by native TextureData::customLoad."""
    if type(code) is not int or not 0 <= code <= 255:
        raise SpriteCutWrapAuditError("Texture wrap code must be an unsigned byte")
    return _TEXTURE_WRAP_CODES.get(code, "unrecognized")


def _load_private_cut_wrap_codes(ipa: Path) -> dict[str, dict[tuple[str, int], tuple[int, int]]]:
    """Resolve each indexed cut tuple to its TextureData wrap pair in memory only."""
    if not ipa.is_file():
        raise SpriteCutWrapAuditError("Original owner-private IPA not found")
    with ZipFile(ipa, "r") as archive:
        infos = archive.infolist()
        if len(infos) > MAX_MEMBERS:
            raise SpriteCutWrapAuditError("IPA member count exceeds safety limit")
        members = {}
        for info in infos:
            if info.filename in members:
                raise SpriteCutWrapAuditError("Duplicate IPA member name")
            members[info.filename] = info
        result = {}
        shared_repositories = {}
        for screen in SCREENS:
            base = PREFIX + screen + "/"
            cut_repo = _safe_read(archive, members.get(base + "meta/SpriteCutData.repo"),
                                  MAX_REPO_BYTES)
            cut_wad = _safe_read(archive, members.get(base + "sprite/SpriteResData.wad"),
                                 MAX_WAD_BYTES)
            texture_repo = _safe_read(archive, members.get(base + "meta/TextureData.repo"),
                                      MAX_REPO_BYTES)
            texture_wad = _safe_read(archive, members.get(base + "textureData/TextureData.wad"),
                                     MAX_WAD_BYTES)
            for label, blob in (("cut_repo", cut_repo), ("texture_repo", texture_repo)):
                if label in shared_repositories and shared_repositories[label] != blob:
                    raise SpriteCutWrapAuditError("Paired resource indexes differ")
                shared_repositories[label] = blob
            cut_entries = parse_sprite_repository(
                cut_repo, expected_label="SpriteCutData",
                expected_wad="sprite/SpriteResData.wad",
            )
            texture_entries = parse_sprite_repository(
                texture_repo, expected_label="TextureData",
                expected_wad="textureData/TextureData.wad",
            )
            texture_records = _intervals(texture_entries, texture_wad)
            wrap_by_texture = {}
            for entry, record in zip(texture_entries, texture_records):
                key, image_key, scalar_block = parse_texture_data_record(record)
                if key != entry.key or not image_key:
                    raise SpriteCutWrapAuditError("Invalid indexed TextureData record")
                wrap_by_texture[key] = decode_texture_wrap_codes(scalar_block)
            cut_records = _intervals(cut_entries, cut_wad)
            wrap_by_cut_handle = {}
            for entry, record in zip(cut_entries, cut_records):
                key, texture_key, tuples = parse_sprite_cut_record(record)
                if key != entry.key or texture_key not in wrap_by_texture:
                    raise SpriteCutWrapAuditError("SpriteCut texture link is missing or mismatched")
                for handle, _x, _y, _width, _height in tuples:
                    ref = (key, handle)
                    if ref in wrap_by_cut_handle:
                        raise SpriteCutWrapAuditError("Duplicate cut-handle identity")
                    wrap_by_cut_handle[ref] = wrap_by_texture[texture_key]
            result[screen] = wrap_by_cut_handle
        if result[SCREENS[0]] != result[SCREENS[1]]:
            raise SpriteCutWrapAuditError("Cut-handle wrap settings differ between resolution packs")
        return result


def summarize_wrap_bounds(
    med_rows: dict,
    xlarge_rows: dict,
    med_wraps: dict[tuple[str, int], tuple[int, int]],
    xlarge_wraps: dict[tuple[str, int], tuple[int, int]],
) -> dict:
    """Aggregate bounds classes by native wrap pair; private identities never escape."""
    if (not isinstance(med_rows, dict) or not isinstance(xlarge_rows, dict)
            or set(med_rows) != set(xlarge_rows)
            or set(med_rows) != set(med_wraps)
            or set(xlarge_rows) != set(xlarge_wraps)):
        raise SpriteCutWrapAuditError("Paired cut rows and wrap maps do not match")
    if med_wraps != xlarge_wraps:
        raise SpriteCutWrapAuditError("Cut-handle wrap settings differ between resolution packs")
    reports = {}
    for screen, rows, wraps in (
        ("screen-med", med_rows, med_wraps),
        ("screen-xlarge", xlarge_rows, xlarge_wraps),
    ):
        groups = defaultdict(Counter)
        for ref, (rectangle, png_dims) in rows.items():
            mode_pair = tuple(texture_wrap_mode(code) for code in wraps[ref])
            group = groups[mode_pair]
            status, _dx, _dy = classify_allocated_cut(rectangle, png_dims)
            group[status] += 1
        by_wrap = {}
        for pair, counts in sorted(groups.items()):
            key = pair[0] + "__" + pair[1]
            by_wrap[key] = {
                "inside_raw_png": counts["inside_raw"],
                "fits_allocated_only": counts["inside_allocated_only"],
                "outside_allocated": counts["outside_allocated"],
                "invalid_rectangle": counts["invalid"],
                "cut_tuple_count": sum(counts.values()),
            }
        reports[screen] = {
            "cut_tuples_by_texture_wrap_pair": by_wrap,
            "texture_wrap_pairs_by_cut_handle_count": {
                pair[0] + "__" + pair[1]: count
                for pair, count in sorted(Counter(
                    tuple(texture_wrap_mode(code) for code in pair)
                    for pair in wraps.values()
                ).items())
            },
            "outside_allocated_tuples_use_repeat_on_any_axis": any(
                count["outside_allocated"] > 0
                and (pair[0] == "repeat" or pair[1] == "repeat")
                for pair, count in groups.items()
            ),
            "outside_allocated_tuples_use_clamp_to_edge_on_both_axes": all(
                pair == ("clamp_to_edge", "clamp_to_edge")
                for pair, count in groups.items() if count["outside_allocated"] > 0
            ),
        }
    return {
        "classification": "private_sprite_cut_bounds_by_native_texture_wrap_mode",
        "cut_tuple_count_per_pack": len(med_rows),
        "native_wrap_code_0": "GL_CLAMP_TO_EDGE",
        "native_wrap_code_1": "GL_REPEAT",
        "other_native_wrap_codes": "unrecognized; not assigned a guessed mode",
        "paired_cut_handle_wrap_settings_identical": True,
        "per_pack": reports,
        "outside_cuts_clipped_or_repaired": False,
        "private_resource_keys_paths_offsets_or_per_record_data_exported": False,
    }


def audit_private_wrap_bounds(ipa: Path) -> dict:
    rows_med, rows_xlarge = _load_private_cut_rows(ipa)
    wraps = _load_private_cut_wrap_codes(ipa)
    return summarize_wrap_bounds(
        rows_med, rows_xlarge, wraps[SCREENS[0]], wraps[SCREENS[1]]
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    destination = private_output_path(args.out)
    report = audit_private_wrap_bounds(args.ipa)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Private SpriteCut/native wrap correlation complete (aggregate-only).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
