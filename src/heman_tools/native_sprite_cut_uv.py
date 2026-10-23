"""Stage195: reproduce native SpriteCut UV generation without clipping.

SpriteCut::buildTextCoord uses allocated Texture::getWidth/Height and signed
x/y/width/height fields directly. Out-of-range UVs are preserved for the
configured OpenGL wrap mode; this module does not crop or synthesize pixels.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import struct
from typing import Sequence

from .sprite_cut_runtime_texture_bounds import allocated_texture_dimensions
from .sprite_cut_wrap_bounds_audit import SpriteCutWrapAuditError, texture_wrap_mode

_S32_MIN = -(1 << 31)
_S32_MAX = (1 << 31) - 1


class NativeSpriteCutUVError(ValueError):
    """Malformed input to the native SpriteCut UV reference model."""


def _signed32(value: object, field: str) -> int:
    if type(value) is not int or not _S32_MIN <= value <= _S32_MAX:
        raise NativeSpriteCutUVError(f"{field} must be a signed 32-bit integer")
    return value


def _add_s32(left: int, right: int) -> int:
    """Model the original ARM signed-int addition at the UV endpoint."""
    value = (left + right) & 0xFFFFFFFF
    return value - 0x100000000 if value & 0x80000000 else value


def _f32(value: int | float) -> float:
    try:
        return struct.unpack("<f", struct.pack("<f", float(value)))[0]
    except (OverflowError, struct.error) as exc:
        raise NativeSpriteCutUVError("Value cannot be represented as a native float") from exc


def _divide_s32_by_dimension(value: int, dimension: int) -> float:
    numerator = _f32(value)
    denominator = _f32(dimension)
    result = _f32(numerator / denominator)
    if not math.isfinite(result):
        raise NativeSpriteCutUVError("Native UV calculation is not finite")
    return result


@dataclass(frozen=True)
class NativeSpriteCutUV:
    """Raw normalized UV endpoints and the native per-axis wrap-mode selection."""

    u0: float
    v0: float
    u1: float
    v1: float
    allocated_width: int
    allocated_height: int
    wrap_s_code: int
    wrap_t_code: int
    wrap_s_mode: str
    wrap_t_mode: str


def compute_native_sprite_cut_uv(
    rectangle: Sequence[int],
    png_dimensions: tuple[int, int],
    wrap_codes: Sequence[int],
) -> NativeSpriteCutUV:
    """Reproduce SpriteCut::buildTextCoord's signed endpoint and UV arithmetic.

    Unlike the safe-crop audit, this native-behavior model deliberately preserves
    negative origins, non-positive extents, and UVs outside [0,1]. It does not
    claim that such source geometry is visually correct.
    """
    if not isinstance(rectangle, (tuple, list)) or len(rectangle) != 4:
        raise NativeSpriteCutUVError("SpriteCut rectangle must contain four integers")
    x, y, width, height = (
        _signed32(value, "SpriteCut rectangle field") for value in rectangle
    )
    if not isinstance(wrap_codes, (tuple, list)) or len(wrap_codes) != 2:
        raise NativeSpriteCutUVError("Wrap codes must contain S and T values")
    wrap_s, wrap_t = wrap_codes
    for value in (wrap_s, wrap_t):
        if type(value) is not int or not 0 <= value <= 255:
            raise NativeSpriteCutUVError("Wrap codes must be unsigned bytes")
    try:
        allocated_width, allocated_height = allocated_texture_dimensions(png_dimensions)
    except Exception as exc:
        raise NativeSpriteCutUVError("PNG dimensions cannot produce a native texture allocation") from exc

    right = _add_s32(x, width)
    bottom = _add_s32(y, height)
    return NativeSpriteCutUV(
        u0=_divide_s32_by_dimension(x, allocated_width),
        v0=_divide_s32_by_dimension(y, allocated_height),
        u1=_divide_s32_by_dimension(right, allocated_width),
        v1=_divide_s32_by_dimension(bottom, allocated_height),
        allocated_width=allocated_width,
        allocated_height=allocated_height,
        wrap_s_code=wrap_s,
        wrap_t_code=wrap_t,
        wrap_s_mode=texture_wrap_mode(wrap_s),
        wrap_t_mode=texture_wrap_mode(wrap_t),
    )
