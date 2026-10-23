"""Stage191: private PNG-IHDR vs SpriteCut rectangle paired-pack census.

No original resource identifiers, source offsets, PNG bytes, or record-level
findings are ever returned by the public census or written to GitHub.
Outside-PNG rectangles remain unresolved: padding is NOT inferred and no
texture coordinates or crops are generated for those records.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import stat
import struct
from zipfile import ZipFile
import zlib

from .collision_inventory import private_output_path
from .physics_shape_census import MAX_MEMBERS, PREFIX, SCREENS, _safe_read
from .sprite_cut_texture_image_graph import (
    MAX_IMAGE_REPO_BYTES, parse_image_repository,
    parse_sprite_cut_record, parse_texture_data_record,
)
from .sprite_repo_wad_index import (
    MAX_REPO_BYTES, MAX_WAD_BYTES, parse_sprite_repository,
)
from .sprite_wad_record_intervals import _intervals

MAX_CUTS = 5000
MAX_PNG_BYTES = 32_000_000
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class SpriteCutBoundsError(ValueError):
    """Missing, ambiguous, malformed or unverified original texture geometry."""


def classify_rectangle(
    rectangle: tuple[int, int, int, int],
    png_dimensions: tuple[int, int],
) -> tuple[str, int, int]:
    """Classify one cut against raw IHDR bounds without clipping or padding."""
    if (not isinstance(rectangle, tuple) or len(rectangle) != 4
            or any(type(v) is not int for v in rectangle)):
        raise SpriteCutBoundsError("Cut rectangle must have four integer fields")
    if (not isinstance(png_dimensions, tuple) or len(png_dimensions) != 2
            or any(type(v) is not int for v in png_dimensions)
            or not all(0 < v <= 32768 for v in png_dimensions)):
        raise SpriteCutBoundsError("PNG dimensions must be positive integers")
    x, y, width, height = rectangle
    image_width, image_height = png_dimensions
    if x < 0 or y < 0 or width <= 0 or height <= 0:
        return "invalid", 0, 0
    excess_x = max(0, x + width - image_width)
    excess_y = max(0, y + height - image_height)
    return ("outside" if excess_x or excess_y else "inside",
            excess_x, excess_y)


def summarize_paired_cut_bounds(
    med: dict[tuple[str, int], tuple[tuple[int, int, int, int], tuple[int, int]]],
    xlarge: dict[tuple[str, int], tuple[tuple[int, int, int, int], tuple[int, int]]],
) -> dict:
    """Return counts only. Stable private keys are never copied to the report."""
    if (not isinstance(med, dict) or not isinstance(xlarge, dict)
            or not 1 <= len(med) <= MAX_CUTS
            or set(med) != set(xlarge)):
        raise SpriteCutBoundsError("Paired cut inventories differ or are excessive")
    per_pack = {}
    categories_by_pack = {}
    for label, rows in (("screen-med", med), ("screen-xlarge", xlarge)):
        cats = {}
        counts = Counter()
        excess_bands = Counter()
        max_x = max_y = 0
        for key, (rectangle, png_dimensions) in rows.items():
            status, dx, dy = classify_rectangle(rectangle, png_dimensions)
            cats[key] = status
            counts[status] += 1
            if status == "outside":
                counts[("horizontal" if dx and not dy else
                        "vertical" if dy and not dx else "both") + "_overrun"] += 1
                excess = max(dx, dy)
                band = ("one_pixel" if excess == 1 else
                        "two_to_three" if excess <= 3 else
                        "four_to_sixteen" if excess <= 16 else "above_sixteen")
                excess_bands[band] += 1
                max_x = max(max_x, dx)
                max_y = max(max_y, dy)
        per_pack[label] = {
            "inside_png": counts["inside"],
            "outside_png": counts["outside"],
            "invalid_rectangle": counts["invalid"],
            "overrun_axes": {
                name: counts[name + "_overrun"] for name in ("horizontal", "vertical", "both")
            },
            "overrun_magnitude": {
                name: excess_bands[name]
                for name in ("one_pixel", "two_to_three", "four_to_sixteen", "above_sixteen")
            },
            "max_horizontal_excess_pixels": max_x,
            "max_vertical_excess_pixels": max_y,
        }
        categories_by_pack[label] = cats
    paired = Counter(
        (categories_by_pack["screen-med"][key], categories_by_pack["screen-xlarge"][key])
        for key in med
    )
    return {
        "classification": "private_paired_sprite_cut_raw_png_bounds_census",
        "indexed_cut_count_per_pack": len(med),
        "per_pack": per_pack,
        "paired_category_counts": {
            f"{a}_med__{b}_xlarge": count
            for (a, b), count in sorted(paired.items())
        },
        "raw_png_bounds_are_runtime_texture_dimensions": False,
        "padding_or_atlas_repair_inferred": False,
        "outside_or_invalid_cuts_may_be_cropped_or_rendered": False,
        "private_keys_offsets_pixels_and_record_data_exported": False,
    }


def _png_ihdr_dimensions(archive: ZipFile, info) -> tuple[int, int]:
    """Read only PNG signature and IHDR; do not extract PNG data."""
    if (info is None or info.is_dir() or info.file_size < 33
            or info.file_size > MAX_PNG_BYTES or info.flag_bits & 1
            or stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK):
        raise SpriteCutBoundsError("Unsafe or missing PNG archive member")
    with archive.open(info, "r") as member:
        header = member.read(33)
    if (len(header) != 33 or header[:8] != _PNG_SIGNATURE
            or struct.unpack_from(">I", header, 8)[0] != 13
            or header[12:16] != b"IHDR"
            or zlib.crc32(header[12:29]) & 0xFFFFFFFF !=
            struct.unpack_from(">I", header, 29)[0]):
        raise SpriteCutBoundsError("Invalid PNG signature or IHDR checksum")
    width, height = struct.unpack_from(">II", header, 16)
    if not 0 < width <= 32768 or not 0 < height <= 32768:
        raise SpriteCutBoundsError("PNG IHDR dimensions out of bounds")
    return width, height


def audit_private_cut_bounds(ipa: Path) -> dict:
    """Inspect both owner-private iOS resolution packs; report aggregates."""
    if not ipa.is_file():
        raise SpriteCutBoundsError("Original IPA not available locally")
    paths = (
        ("meta/SpriteCutData.repo", MAX_REPO_BYTES),
        ("sprite/SpriteResData.wad", MAX_WAD_BYTES),
        ("meta/TextureData.repo", MAX_REPO_BYTES),
        ("textureData/TextureData.wad", MAX_WAD_BYTES),
        ("meta/ImageData.repo", MAX_IMAGE_REPO_BYTES),
    )
    with ZipFile(ipa, "r") as archive:
        members = archive.infolist()
        if len(members) > MAX_MEMBERS:
            raise SpriteCutBoundsError("IPA member count exceeds safety limit")
        by_name = {}
        for info in members:
            if info.filename in by_name:
                raise SpriteCutBoundsError("Duplicate IPA member name")
            by_name[info.filename] = info
        paired = {}
        repositories = []
        for screen in SCREENS:
            base = PREFIX + screen + "/"
            sources = {
                path: _safe_read(archive, by_name.get(base + path), cap)
                for path, cap in paths
            }
            repositories.append(tuple(sources[path] for path, _ in paths if path.endswith(".repo")))
            cuts = parse_sprite_repository(
                sources["meta/SpriteCutData.repo"],
                expected_label="SpriteCutData",
                expected_wad="sprite/SpriteResData.wad",
            )
            textures = parse_sprite_repository(
                sources["meta/TextureData.repo"],
                expected_label="TextureData",
                expected_wad="textureData/TextureData.wad",
            )
            cut_records = dict(zip(
                (entry.key for entry in cuts),
                _intervals(cuts, sources["sprite/SpriteResData.wad"]),
            ))
            texture_records = dict(zip(
                (entry.key for entry in textures),
                _intervals(textures, sources["textureData/TextureData.wad"]),
            ))
            images = dict(parse_image_repository(sources["meta/ImageData.repo"]))
            texture_members = {
                info.filename: info for info in members
                if info.filename.startswith(base + "textures/") and not info.is_dir()
            }
            folded = {}
            for name in texture_members:
                alias = name.casefold()
                if alias in folded and folded[alias] != name:
                    raise SpriteCutBoundsError("Ambiguous casefolded PNG members")
                folded[alias] = name
            dimensions_cache = {}
            census = {}
            for cut_key, cut_record in cut_records.items():
                texture_key, tuples = parse_sprite_cut_record(cut_record)
                if texture_key not in texture_records:
                    raise SpriteCutBoundsError("Missing TextureData resource link")
                parsed_texture, image_key, _ = parse_texture_data_record(
                    texture_records[texture_key])
                if parsed_texture != texture_key or image_key not in images:
                    raise SpriteCutBoundsError("Invalid TextureData-to-ImageData link")
                requested = base + images[image_key].lstrip("/")
                actual = folded.get(requested.casefold())
                if actual is None:
                    raise SpriteCutBoundsError("Unresolved image member")
                if actual not in dimensions_cache:
                    dimensions_cache[actual] = _png_ihdr_dimensions(
                        archive, texture_members[actual])
                png_dims = dimensions_cache[actual]
                for handle, x, y, width, height in tuples:
                    census[(cut_key, handle)] = ((x, y, width, height), png_dims)
            paired[screen] = census
        if repositories[0] != repositories[1]:
            raise SpriteCutBoundsError("Original paired resource indexes differ")
        return summarize_paired_cut_bounds(paired[SCREENS[0]], paired[SCREENS[1]])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    destination = private_output_path(args.out)
    result = audit_private_cut_bounds(args.ipa)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Private paired SpriteCut/PNG bounds census complete (aggregate-only).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
