"""Stage193: confirmed serialized Symbol visual-field semantics.

The private original ARMv7 Symbol::fileIn and SpritePlayer::tween/updateMesh
paths establish the field order below. This is an asset-free reference model,
not a production renderer and not a source-resource decoder.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

MAX_TWEEN_FUNCTION_ID = 17
_GL_BLEND_FACTOR_BY_CODE = {
    0: 0,       # GL_ZERO
    1: 1,       # GL_ONE
    2: 0x0300,  # GL_SRC_COLOR
    3: 0x0301,  # GL_ONE_MINUS_SRC_COLOR
    4: 0x0302,  # GL_SRC_ALPHA
    5: 0x0303,  # GL_ONE_MINUS_SRC_ALPHA
    6: 0x0304,  # GL_DST_ALPHA
    7: 0x0305,  # GL_ONE_MINUS_DST_ALPHA
}
_S32_MIN = -(1 << 31)
_S32_MAX = (1 << 31) - 1


class SymbolRenderContractError(ValueError):
    """Malformed or unsupported Symbol visual parameters."""


def _s32(value: object, field: str) -> int:
    if type(value) is not int or not _S32_MIN <= value <= _S32_MAX:
        raise SymbolRenderContractError(f"{field} must be a signed 32-bit integer")
    return value


def _finite_number(value: object, field: str) -> float:
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value)):
        raise SymbolRenderContractError(f"{field} must be a finite number")
    return float(value)


def _rgba_tuple(values: Sequence[float], field: str) -> tuple[float, float, float, float]:
    if not isinstance(values, (tuple, list)) or len(values) != 4:
        raise SymbolRenderContractError(f"{field} must contain exactly four channels")
    return tuple(_finite_number(value, field) for value in values)  # type: ignore[return-value]


def _clamp_channel(value: float) -> float:
    return min(1.0, max(0.0, value))


@dataclass(frozen=True)
class SymbolColorMultipliers:
    """Serialized color order is alpha, red, green, blue (not conventional RGBA)."""

    alpha: float
    red: float
    green: float
    blue: float

    def __post_init__(self) -> None:
        for name in ("alpha", "red", "green", "blue"):
            object.__setattr__(self, name, _finite_number(getattr(self, name), name))

    def apply_user_rgba(
        self, user_rgba: Sequence[float],
    ) -> tuple[float, float, float, float]:
        """Apply native A*R/G/B/A multipliers and clamp each output channel."""
        user_r, user_g, user_b, user_a = _rgba_tuple(user_rgba, "user RGBA")
        return (
            _clamp_channel(user_r * self.alpha * self.red),
            _clamp_channel(user_g * self.alpha * self.green),
            _clamp_channel(user_b * self.alpha * self.blue),
            _clamp_channel(user_a * self.alpha),
        )


@dataclass(frozen=True)
class SymbolTweenSelectors:
    """Four serialized easing IDs and the native field groups each controls."""

    offset_xy: int
    rotation: int
    scale_xy: int
    color_alpha_rgb: int

    def __post_init__(self) -> None:
        for name in ("offset_xy", "rotation", "scale_xy", "color_alpha_rgb"):
            value = _s32(getattr(self, name), name)
            if not 0 <= value <= MAX_TWEEN_FUNCTION_ID:
                raise SymbolRenderContractError(
                    f"{name} must select a native tween function in 0..{MAX_TWEEN_FUNCTION_ID}"
                )

    @property
    def by_group(self) -> dict[str, int]:
        return {
            "x_y_offset": self.offset_xy,
            "rotation": self.rotation,
            "scale_x_y": self.scale_xy,
            "alpha_red_green_blue": self.color_alpha_rgb,
        }


@dataclass(frozen=True)
class SymbolBlendOverride:
    """Native asymmetry: source factor is stored raw; destination is an encoded ID."""

    source_factor_raw: int
    destination_factor_code: int

    def __post_init__(self) -> None:
        _s32(self.source_factor_raw, "source_factor_raw")
        _s32(self.destination_factor_code, "destination_factor_code")

    def resolve(self) -> tuple[int, int] | None:
        """Return (raw source GL factor, mapped destination GL factor), or no override."""
        if self.source_factor_raw == -1 or self.destination_factor_code == -1:
            return None
        destination = _GL_BLEND_FACTOR_BY_CODE.get(self.destination_factor_code)
        if destination is None:
            return None
        return self.source_factor_raw, destination


@dataclass(frozen=True)
class SymbolRenderContract:
    """Confirmed Symbol field contract after its resource name."""

    cut_handle: int
    rotation_degrees: int
    offset_x: int
    offset_y: int
    color: SymbolColorMultipliers
    scale_x: float
    scale_y: float
    tween: SymbolTweenSelectors
    blend: SymbolBlendOverride
    symbol_mask: int

    def __post_init__(self) -> None:
        for name in ("cut_handle", "rotation_degrees", "offset_x", "offset_y", "symbol_mask"):
            _s32(getattr(self, name), name)
        object.__setattr__(self, "scale_x", _finite_number(self.scale_x, "scale_x"))
        object.__setattr__(self, "scale_y", _finite_number(self.scale_y, "scale_y"))
        if not isinstance(self.color, SymbolColorMultipliers):
            raise SymbolRenderContractError("color must be SymbolColorMultipliers")
        if not isinstance(self.tween, SymbolTweenSelectors):
            raise SymbolRenderContractError("tween must be SymbolTweenSelectors")
        if not isinstance(self.blend, SymbolBlendOverride):
            raise SymbolRenderContractError("blend must be SymbolBlendOverride")

    @classmethod
    def from_serialized_fields(
        cls,
        four_ints: Sequence[int],
        six_floats: Sequence[float],
        seven_ints: Sequence[int],
    ) -> "SymbolRenderContract":
        """Decode the confirmed four-int / six-float / seven-int Symbol tail."""
        if not isinstance(four_ints, (tuple, list)) or len(four_ints) != 4:
            raise SymbolRenderContractError("Symbol prefix must contain exactly four integers")
        if not isinstance(six_floats, (tuple, list)) or len(six_floats) != 6:
            raise SymbolRenderContractError("Symbol float block must contain exactly six values")
        if not isinstance(seven_ints, (tuple, list)) or len(seven_ints) != 7:
            raise SymbolRenderContractError("Symbol scalar tail must contain exactly seven integers")
        cut_handle, rotation, offset_x, offset_y = (
            _s32(value, "Symbol integer prefix") for value in four_ints
        )
        alpha, red, green, blue, scale_x, scale_y = (
            _finite_number(value, "Symbol float block") for value in six_floats
        )
        ease_offset, ease_rotation, ease_scale, ease_color, blend_src, blend_dst, mask = (
            _s32(value, "Symbol scalar tail") for value in seven_ints
        )
        return cls(
            cut_handle=cut_handle,
            rotation_degrees=rotation,
            offset_x=offset_x,
            offset_y=offset_y,
            color=SymbolColorMultipliers(alpha, red, green, blue),
            scale_x=scale_x,
            scale_y=scale_y,
            tween=SymbolTweenSelectors(ease_offset, ease_rotation, ease_scale, ease_color),
            blend=SymbolBlendOverride(blend_src, blend_dst),
            symbol_mask=mask,
        )

    def is_suppressed_by_mask(self, active_mask: int) -> bool:
        """Native paint skips this Symbol when its mask intersects the active mask."""
        active_mask = _s32(active_mask, "active_mask")
        return (self.symbol_mask & active_mask) != 0
