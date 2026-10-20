"""Offline alpha parity of two private iOS collision tile atlases.

Reports only aggregate threshold counts; alpha pixels or binary tile masks are
never exported. This is not a claim about original-game physics or solidity.
"""
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import stat
import zipfile

THRESHOLDS = (64, 128, 192)
SCREENS = ("screen-med", "screen-xlarge")
MAX_PIXELS = 16_000_000
MAX_SELECTED_BYTES = 16_000_000
MAX_USED_TILES = 64


def _alpha_image(width: int, height: int, alpha: bytes, label: str) -> None:
    if (type(width) is not int or type(height) is not int
            or not 1 <= width <= 8192 or not 1 <= height <= 8192
            or width * height > MAX_PIXELS
            or not isinstance(alpha, bytes) or len(alpha) != width * height):
        raise ValueError(f"invalid bounded {label} alpha plane")


def compare_alpha_planes(medium: tuple[int, int, bytes],
                         xlarge: tuple[int, int, bytes],
                         tile_size: int, tile_ids: list[int]) -> dict:
    """Threshold the same row-major tile indices after medium's exact 2x zoom.

    Metrics refer to source *art alpha*, not to original collision hitboxes.
    """
    if type(tile_size) is not int or not 1 <= tile_size <= 64:
        raise ValueError("invalid base tile size")
    if (not isinstance(medium, tuple) or not isinstance(xlarge, tuple)
            or len(medium) != 3 or len(xlarge) != 3):
        raise ValueError("expected two (width, height, alpha) planes")
    mw, mh, ma = medium
    lw, lh, la = xlarge
    _alpha_image(mw, mh, ma, "medium")
    _alpha_image(lw, lh, la, "xlarge")
    if lw != 2 * mw or lh != 2 * mh or mw % tile_size or mh % tile_size:
        raise ValueError("atlases must have corresponding 2x row-major tiles")
    columns = mw // tile_size
    atlas_count = columns * (mh // tile_size)
    if (not isinstance(tile_ids, list)
            or not 1 <= len(tile_ids) <= MAX_USED_TILES
            or any(type(i) is not int or not 0 <= i < atlas_count
                   for i in tile_ids)
            or len(set(tile_ids)) != len(tile_ids)):
        raise ValueError("invalid, duplicate or out-of-range tile IDs")

    results = {}
    for idx in sorted(tile_ids):
        bx = (idx % columns) * tile_size
        by = (idx // columns) * tile_size
        metrics = {}
        for threshold in THRESHOLDS:
            intersection = high_only = medium_only = 0
            medium_count = high_count = 0
            for y in range(tile_size):
                for x in range(tile_size):
                    low = ma[(by + y) * mw + bx + x] >= threshold
                    medium_count += low
                    offset = (2 * (by + y)) * lw + 2 * (bx + x)
                    for k in (offset, offset + 1,
                              offset + lw, offset + lw + 1):
                        high = la[k] >= threshold
                        high_count += high
                        intersection += bool(low and high)
                        high_only += bool(high and not low)
                        medium_only += bool(low and not high)
            union = intersection + high_only + medium_only
            metrics[str(threshold)] = {
                "medium_opaque_pixels": medium_count,
                "xlarge_opaque_pixels": high_count,
                "intersection_pixels": intersection,
                "xlarge_only_pixels": high_only,
                "medium_only_pixels": medium_only,
                "mismatching_pixels": high_only + medium_only,
                "intersection_over_union": (
                    round(intersection / union, 6) if union else 1.0),
            }
        results[str(idx)] = metrics
    return {
        "schema_version": 1,
        "source_tile_size": tile_size,
        "xlarge_tile_size": 2 * tile_size,
        "atlas_tiles_per_row": columns,
        "compared_tile_ids": sorted(tile_ids),
        "thresholds": list(THRESHOLDS),
        "tile_metrics": results,
        "all_threshold_128_masks_identical": all(
            t["128"]["mismatching_pixels"] == 0 for t in results.values()),
        "alpha_mask_means_solid_terrain": False,
        "source_game_collision_semantics_verified": False,
        "camera_or_scale_calibrated": False,
        "automatic_collision_export_permitted": False,
    }


def _archive_bytes(archive: zipfile.ZipFile, entries: list[zipfile.ZipInfo],
                   path: str) -> bytes:
    selected = [item for item in entries if item.filename == path]
    if len(selected) != 1:
        raise ValueError("missing or duplicate selected IPA member")
    item = selected[0]
    if (item.is_dir() or item.flag_bits & 1 or item.file_size < 4
            or item.file_size > MAX_SELECTED_BYTES
            or stat.S_IFMT(item.external_attr >> 16) == stat.S_IFLNK):
        raise ValueError("invalid, encrypted or oversized IPA member")
    return archive.read(item)


def inspect_private_ipa(ipa: Path, map_name: str = "MUMap1-1.map") -> dict:
    """Read two maps and private PNG alpha planes directly from user's IPA."""
    if (not isinstance(map_name, str) or len(map_name) <= 4
            or len(map_name) > 255 or not map_name.endswith(".map")
            or "/" in map_name or "\\" in map_name
            or not map_name.isprintable()):
        raise ValueError("map_name must be a simple .map basename")
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Install Pillow locally for private PNG decoding") from exc
    from .tilemap import parse_tilemap

    images = {}
    maps = {}
    layers = {}
    with zipfile.ZipFile(ipa) as archive:
        entries = archive.infolist()
        if len(entries) > 100000:
            raise ValueError("excessive number of archive entries")
        for screen in SCREENS:
            base = f"Payload/MOTU.app/{screen}/"
            maps[screen] = _archive_bytes(
                archive, entries, base + "maps/" + map_name)
            layers[screen] = parse_tilemap(maps[screen]).layer("collision")
            raw = _archive_bytes(
                archive, entries, base + "textures/collisionTiles.png")
            with Image.open(io.BytesIO(raw)) as image:
                if (image.format != "PNG" or "A" not in image.getbands()
                        or not 0 < image.width * image.height <= MAX_PIXELS):
                    raise ValueError("expected bounded PNG with alpha channel")
                images[screen] = (
                    image.width, image.height, image.getchannel("A").tobytes())

    if maps[SCREENS[0]] != maps[SCREENS[1]]:
        raise ValueError("original screen-pack map bytes differ")
    layer = layers[SCREENS[0]]
    if (layer.tile_width != layer.tile_height
            or layer.atlases.count("collision") != 1):
        raise ValueError("unsupported collision tile or atlas")
    atlas_index = layer.atlases.index("collision")
    used_ids = set()
    for tile, atlas in zip(layer.tile_ids, layer.atlas_ids):
        if tile == 65535:
            continue
        if atlas != atlas_index:
            raise ValueError("unexpected atlas in collision candidate cell")
        used_ids.add(tile)
    report = compare_alpha_planes(
        images[SCREENS[0]], images[SCREENS[1]], layer.tile_width,
        sorted(used_ids))
    report.update({
        "map": map_name,
        "map_bytes_identical_between_screens": True,
        "occupied_candidate_cells": layer.occupied_count,
        "source_art_embedded_in_report": False,
    })
    return report


def main(argv=None) -> int:
    from .collision_inventory import private_output_path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", required=True, type=Path)
    parser.add_argument("--map", dest="map_name", default="MUMap1-1.map")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    output = private_output_path(args.out)
    report = inspect_private_ipa(args.ipa, args.map_name)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print("Private alpha parity audit completed. No masks exported.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
