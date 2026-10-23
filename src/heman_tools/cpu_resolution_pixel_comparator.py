"""Stage219: CPU resolution-pair pixel diagnostic, with no runtime parity claim.

Compare a high-resolution RGBA buffer against *naive nearest* 2x enlargement
of a lower-resolution RGBA buffer. Equal canvas geometry alone does not imply
equal source pixels, original texture filters or GPU/iOS runtime parity.

Source PNGs and original asset selectors stay owner-private. This public
module operates on arbitrary bytes and exports aggregate metrics only.
"""
from __future__ import annotations

from dataclasses import dataclass

MAX_COMPARE_PIXELS = 4_194_304


class ResolutionPixelComparisonError(ValueError):
    """Invalid or oversized paired source CPU pixels."""


def _positive_int(value: object, field: str) -> int:
    if type(value) is not int or not 1 <= value <= MAX_COMPARE_PIXELS:
        raise ResolutionPixelComparisonError(f"{field} must be a bounded positive integer")
    return value


@dataclass(frozen=True)
class Naive2xPixelComparison:
    """Aggregate-only diagnostic; no per-pixel or source-resource values."""

    compared_pixels: int
    exact_rgba_pixels: int
    visible_union_pixels: int
    visible_exact_rgba_pixels: int
    alpha_equal_pixels: int
    rgba_channel_abs_diff_sum: int

    def to_public_safe_summary(self) -> dict:
        count = self.compared_pixels
        visible = self.visible_union_pixels
        return {
            "classification": "naive_2x_nearest_cpu_pixel_diagnostic",
            "compared_pixels": count,
            "exact_rgba_pixels": self.exact_rgba_pixels,
            "exact_rgba_fraction": round(self.exact_rgba_pixels / count, 6),
            "visible_union_pixels": visible,
            "visible_exact_rgba_pixels": self.visible_exact_rgba_pixels,
            "visible_exact_rgba_fraction": (
                round(self.visible_exact_rgba_pixels / visible, 6)
                if visible else None
            ),
            "alpha_equal_pixels": self.alpha_equal_pixels,
            "alpha_agreement_fraction": round(self.alpha_equal_pixels / count, 6),
            "mean_channel_absolute_difference": round(
                self.rgba_channel_abs_diff_sum / (4 * count), 6
            ),
            "comparison_filter": "nearest_neighbor_2x_of_low_resolution_reference",
            "input_pixels_or_resource_identifiers_exported": False,
            "native_gpu_sampling_verified": False,
            "original_ios_runtime_frame_parity_verified": False,
        }


def compare_naive_twofold_resolution_rgba(
    low_width: int, low_height: int, low_rgba: bytes,
    high_width: int, high_height: int, high_rgba: bytes,
) -> Naive2xPixelComparison:
    """Compute bounded byte-level agreement without fabricating pixel parity."""
    w = _positive_int(low_width, "low_width")
    h = _positive_int(low_height, "low_height")
    hw = _positive_int(high_width, "high_width")
    hh = _positive_int(high_height, "high_height")
    if hw != 2 * w or hh != 2 * h:
        raise ResolutionPixelComparisonError("High-resolution canvas must be exactly 2x each axis")
    if hw * hh > MAX_COMPARE_PIXELS:
        raise ResolutionPixelComparisonError("High-resolution pixel budget exceeded")
    if type(low_rgba) is not bytes or len(low_rgba) != w * h * 4:
        raise ResolutionPixelComparisonError("Invalid lower-resolution RGBA byte buffer")
    if type(high_rgba) is not bytes or len(high_rgba) != hw * hh * 4:
        raise ResolutionPixelComparisonError("Invalid higher-resolution RGBA byte buffer")

    exact = alpha_equal = visible_union = visible_exact = total_difference = 0
    for y in range(hh):
        low_row = (y // 2) * w
        high_row = y * hw
        for x in range(hw):
            lo = (low_row + x // 2) * 4
            hi = (high_row + x) * 4
            left = low_rgba[lo:lo + 4]
            right = high_rgba[hi:hi + 4]
            match = left == right
            exact += match
            alpha_equal += left[3] == right[3]
            visible = left[3] != 0 or right[3] != 0
            visible_union += visible
            visible_exact += match and visible
            total_difference += sum(abs(a - b) for a, b in zip(left, right))

    return Naive2xPixelComparison(
        compared_pixels=hw * hh,
        exact_rgba_pixels=exact,
        visible_union_pixels=visible_union,
        visible_exact_rgba_pixels=visible_exact,
        alpha_equal_pixels=alpha_equal,
        rgba_channel_abs_diff_sum=total_difference,
    )
