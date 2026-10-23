"""Stage221: aggregate native SpriteCut UV evidence across resolution packs.

The source texture, SpriteCut, paths, keys, rectangles and per-cut UV values
remain owner-private. Public code computes native float32/padded-allocation
UVs in memory and returns only counts, not original records or pixels.

Native UVs divide by allocated (minimum-four, next-power-of-two) texture
dimensions, not by raw PNG dimensions. A cut may lie outside raw PNG or even
outside allocated space: never clip, repair, extrapolate padding, or claim
original gameplay GPU parity here.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence

from .native_sprite_cut_uv import NativeSpriteCutUVError, compute_native_sprite_cut_uv
from .sprite_cut_runtime_texture_bounds import (
    allocated_texture_dimensions, classify_allocated_cut,
)

MAX_NATIVE_CUT_PAIRS = 5_000
UV_TOLERANCE = 1e-7
_SIGNED32_MIN, _SIGNED32_MAX = -(1 << 31), (1 << 31) - 1


class NativeCutUVPairError(ValueError):
    """Source pairs violate the bounded native UV evidence contract."""


def _rectangle(value: object, field: str) -> tuple[int, int, int, int]:
    if not isinstance(value, (tuple, list)) or len(value) != 4:
        raise NativeCutUVPairError(f"{field} needs four signed int32 values")
    if any(type(n) is not int or not _SIGNED32_MIN <= n <= _SIGNED32_MAX
           for n in value):
        raise NativeCutUVPairError(f"{field} needs four signed int32 values")
    return tuple(value)  # type: ignore[return-value]


def _dimensions(value: object, field: str) -> tuple[int, int]:
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise NativeCutUVPairError(f"{field} needs two bounded positive dimensions")
    if any(type(n) is not int or not 1 <= n <= 32768 for n in value):
        raise NativeCutUVPairError(f"{field} needs two bounded positive dimensions")
    return tuple(value)  # type: ignore[return-value]


def _wrap(value: object, field: str) -> tuple[int, int]:
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise NativeCutUVPairError(f"{field} must use two known wrap codes")
    if any(type(n) is not int or n not in (0, 1) for n in value):
        raise NativeCutUVPairError(f"{field} must use two known wrap codes")
    return tuple(value)  # type: ignore[return-value]


def summarize_native_uv_resolution_pairs(pairs: Sequence[Mapping]) -> dict:
    """Compare native UVs using real per-pack allocations, not a global 2x guess.

    Each pair is a mapping containing:
    med_rect, xlarge_rect, med_png, xlarge_png, med_wrap, xlarge_wrap.
    Keys such as texture paths are deliberately ignored and never returned.
    Returns only bounded aggregate counters for private or synthetic input.
    """
    if not isinstance(pairs, (tuple, list)) or not 1 <= len(pairs) <= MAX_NATIVE_CUT_PAIRS:
        raise NativeCutUVPairError("Expected a bounded nonempty list of SpriteCut pairs")

    classes = {"screen-med": Counter(), "screen-xlarge": Counter()}
    class_transitions = Counter()
    doubled_rectangles = doubled_allocations = equal_uvs = 0
    alloc_mismatch_uvs = unexplained_uv_mismatches = 0
    wrap_equal_count = 0

    for pair in pairs:
        if not isinstance(pair, Mapping):
            raise NativeCutUVPairError("Every SpriteCut pair must be a mapping")
        rectangles = (
            _rectangle(pair.get("med_rect"), "med_rect"),
            _rectangle(pair.get("xlarge_rect"), "xlarge_rect"),
        )
        dimensions = (
            _dimensions(pair.get("med_png"), "med_png"),
            _dimensions(pair.get("xlarge_png"), "xlarge_png"),
        )
        wraps = (
            _wrap(pair.get("med_wrap"), "med_wrap"),
            _wrap(pair.get("xlarge_wrap"), "xlarge_wrap"),
        )
        cut_doubled = rectangles[1] == tuple(2 * n for n in rectangles[0])
        doubled_rectangles += cut_doubled
        wraps_equal = wraps[0] == wraps[1]
        wrap_equal_count += wraps_equal

        allocations = (
            allocated_texture_dimensions(dimensions[0]),
            allocated_texture_dimensions(dimensions[1]),
        )
        allocation_doubled = allocations[1] == (
            2 * allocations[0][0], 2 * allocations[0][1],
        )
        doubled_allocations += allocation_doubled
        uv_pairs = []
        pair_statuses = []
        for screen, rect, dims, wrap in zip(
            ("screen-med", "screen-xlarge"), rectangles, dimensions, wraps
        ):
            status, _dx, _dy = classify_allocated_cut(rect, dims)
            classes[screen][status] += 1
            classes[screen]["allocated_differs_from_png"] += (
                allocated_texture_dimensions(dims) != dims
            )
            classes[screen]["repeat_s"] += wrap[0] == 1
            classes[screen]["repeat_t"] += wrap[1] == 1
            pair_statuses.append(status)
            try:
                uv = compute_native_sprite_cut_uv(rect, dims, wrap)
            except (ValueError, OverflowError, ZeroDivisionError) as exc:
                raise NativeCutUVPairError("Native UV could not be resolved safely") from exc
            endpoints = (uv.u0, uv.v0, uv.u1, uv.v1)
            classes[screen]["uv_endpoint_outside_0_to_1"] += any(
                n < 0.0 or n > 1.0 for n in endpoints
            )
            uv_pairs.append(endpoints)
        class_transitions[tuple(pair_statuses)] += 1
        same = all(abs(a - b) <= UV_TOLERANCE for a, b in zip(*uv_pairs))
        equal_uvs += same
        if not same:
            if cut_doubled and not allocation_doubled:
                alloc_mismatch_uvs += 1
            else:
                unexplained_uv_mismatches += 1

    def counts(screen: str) -> dict:
        return {
            "inside_raw_png": classes[screen]["inside_raw"],
            "fits_allocated_only": classes[screen]["inside_allocated_only"],
            "outside_even_allocated": classes[screen]["outside_allocated"],
            "invalid_original_rectangle": classes[screen]["invalid"],
            "allocated_differs_from_png": classes[screen]["allocated_differs_from_png"],
            "uv_endpoint_outside_0_to_1": classes[screen]["uv_endpoint_outside_0_to_1"],
            "wrap_s_repeat_count": classes[screen]["repeat_s"],
            "wrap_t_repeat_count": classes[screen]["repeat_t"],
        }

    return {
        "classification": "paired_native_sprite_cut_allocated_uv_census",
        "paired_cut_count": len(pairs),
        "rectangles_exactly_2x_count": doubled_rectangles,
        "allocated_dimensions_exactly_2x_count": doubled_allocations,
        "uv_endpoints_equal_within_1e_7_count": equal_uvs,
        "uv_mismatch_with_doubled_rect_and_non_doubled_allocation_count": alloc_mismatch_uvs,
        "uv_mismatch_other_count": unexplained_uv_mismatches,
        "wrap_codes_identical_across_packs_count": wrap_equal_count,
        "per_pack": {
            "screen-med": counts("screen-med"),
            "screen-xlarge": counts("screen-xlarge"),
        },
        "paired_bounds_categories": {
            a + "_med__" + b + "_xlarge": number
            for (a, b), number in sorted(class_transitions.items())
        },
        "native_uv_denominator_is_allocated_pow2_texture": True,
        "outside_source_rectangles_clipped_or_repaired": False,
        "allocated_padding_pixels_invented": False,
        "source_path_keys_rectangles_uvs_or_pixels_exported": False,
        "source_runtime_camera_recovered": False,
        "original_ios_gpu_pixel_parity_verified": False,
    }
