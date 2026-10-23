"""Stage220: safe statistics for paired iOS source texture packs.

The caller keeps all original PNGs, paths and per-asset metrics private.
This module only returns aggregate counters and never outputs resource IDs,
paths, source images, or real iOS runtime-parity claims.  Synthetic tests can
exercise it in public CI without mounting the original IPA.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence

MAX_PAIRS = 4_096
MAX_DIMENSION = 16_384
MAX_PIXELS = 200_000_000


class PairedTextureCensusError(ValueError):
    """Invalid or inconsistent source texture pair metrics."""


def _int(value: object, label: str, maximum: int, *, min_value: int = 0) -> int:
    if type(value) is not int or not min_value <= value <= maximum:
        raise PairedTextureCensusError(f"{label} must be a bounded integer")
    return value


def _shape(record: Mapping, key: str) -> tuple[int, int]:
    value = record.get(key)
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise PairedTextureCensusError(f"{key} must contain two dimensions")
    return (
        _int(value[0], key + " width", MAX_DIMENSION, min_value=1),
        _int(value[1], key + " height", MAX_DIMENSION, min_value=1),
    )


def summarize_texture_resolution_pairs(pairs: Sequence[Mapping]) -> dict:
    """Cross-check source-pair dimension/pixel metrics; keep results aggregate-only.

    Exact-2x pairs require all six pixel census counters. Non-2x pairs can
    only contribute dimension observations; no pixel alignment is invented.
    """
    if not isinstance(pairs, (list, tuple)) or not 1 <= len(pairs) <= MAX_PAIRS:
        raise PairedTextureCensusError("Pair inventory must be a bounded nonempty sequence")

    deltas = Counter()
    counts = Counter()
    exact_pairs = nonexact_pairs = full_matches = different_pairs = 0
    for pair in pairs:
        if not isinstance(pair, Mapping):
            raise PairedTextureCensusError("Each pair must be a mapping")
        low_w, low_h = _shape(pair, "med_dimensions")
        high_w, high_h = _shape(pair, "xlarge_dimensions")
        dx, dy = high_w - low_w * 2, high_h - low_h * 2
        deltas[(dx, dy)] += 1
        if dx or dy:
            nonexact_pairs += 1
            # Do not invent pixel alignment when the original dimensions differ.
            if any(field in pair for field in (
                "compared_pixels", "exact_pixels", "visible_union_pixels",
                "visible_exact_pixels", "alpha_equal_pixels")):
                raise PairedTextureCensusError(
                    "Non-2x source pair must not claim aligned pixel comparison"
                )
            continue

        exact_pairs += 1
        pixels = high_w * high_h
        if counts["compared_pixels"] + pixels > MAX_PIXELS:
            raise PairedTextureCensusError("Total compared pixel budget exceeded")
        compared = _int(pair.get("compared_pixels"), "compared_pixels", MAX_PIXELS)
        exact = _int(pair.get("exact_pixels"), "exact_pixels", pixels)
        visible = _int(pair.get("visible_union_pixels"), "visible_union_pixels", pixels)
        visible_exact = _int(pair.get("visible_exact_pixels"), "visible_exact_pixels", pixels)
        alpha_equal = _int(pair.get("alpha_equal_pixels"), "alpha_equal_pixels", pixels)
        if compared != pixels:
            raise PairedTextureCensusError("Compared pixel count disagrees with source dimensions")
        if visible_exact > min(visible, exact):
            raise PairedTextureCensusError("Visible exact pixels exceed overall exact or visible")
        counts["compared_pixels"] += pixels
        counts["exact_rgba_pixels"] += exact
        counts["visible_union_pixels"] += visible
        counts["visible_exact_rgba_pixels"] += visible_exact
        counts["alpha_equal_pixels"] += alpha_equal
        if exact == pixels:
            full_matches += 1
        else:
            different_pairs += 1

    total = counts["compared_pixels"]
    visible = counts["visible_union_pixels"]
    result = {
        "classification": "source_texture_resolution_pair_aggregate",
        "paired_texture_count": len(pairs),
        "exact_2x_dimension_pairs": exact_pairs,
        "non_2x_dimension_pairs": nonexact_pairs,
        "exact_2x_pixel_identical_texture_pairs": full_matches,
        "exact_2x_pixel_different_texture_pairs": different_pairs,
        "source_dimension_delta_histogram": [
            {"x_from_2x": dx, "y_from_2x": dy, "count": n}
            for (dx, dy), n in sorted(deltas.items())
        ],
        "pixel_count_compared": total,
        "exact_rgba_fraction": round(counts["exact_rgba_pixels"] / total, 6)
        if total else None,
        "visible_union_count": visible,
        "visible_exact_rgba_fraction": round(
            counts["visible_exact_rgba_pixels"] / visible, 6
        ) if visible else None,
        "alpha_agreement_fraction": round(
            counts["alpha_equal_pixels"] / total, 6
        ) if total else None,
        "per_asset_details_exported": False,
        "original_source_images_exported": False,
        "native_gpu_output_verified": False,
        "original_ios_runtime_frame_parity_verified": False,
        "assumption": (
            "Input pixel counts compare original high-resolution PNGs to naive "
            "2x nearest-neighbor enlargement of original low-resolution PNGs"
        ),
    }
    return result
