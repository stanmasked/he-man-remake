"""Stage197: build an asset-free ordered Symbol render-command reference.

This creates a validated command plan from already-resolved Symbol, SpriteCut,
PNG dimensions and native wrap metadata. It does not draw pixels or claim a
complete renderer. The plan retains source order and native out-of-range UVs.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import struct
from typing import Sequence

from .native_sprite_cut_uv import NativeSpriteCutUV, compute_native_sprite_cut_uv
from .symbol_render_contract import (
    SymbolRenderContract, SymbolRenderContractError, SymbolTweenSelectors,
    _S32_MAX, _S32_MIN,
)


class SymbolRenderPlanError(ValueError):
    """Invalid, reordered, or incomplete source-symbol render plan."""


def _f32(value: int | float, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise SymbolRenderPlanError(f"{field} must be a finite number")
    try:
        return struct.unpack("<f", struct.pack("<f", float(value)))[0]
    except (OverflowError, struct.error) as exc:
        raise SymbolRenderPlanError(f"{field} cannot be represented as a native float") from exc


def _point(point: Sequence[float], field: str) -> tuple[float, float]:
    if not isinstance(point, (tuple, list)) or len(point) != 2:
        raise SymbolRenderPlanError(f"{field} must contain exactly two coordinates")
    return _f32(point[0], field), _f32(point[1], field)


@dataclass(frozen=True)
class PlayerTransform:
    """Native SpritePlayer-wide transform and its independent rotation/scale pivots."""

    rotation_degrees: float = 0.0
    rotation_pivot_x: float = 0.0
    rotation_pivot_y: float = 0.0
    scale_x: float = 1.0
    scale_y: float = 1.0
    scale_pivot_x: float = 0.0
    scale_pivot_y: float = 0.0
    translation_x: float = 0.0
    translation_y: float = 0.0

    def __post_init__(self) -> None:
        for name in (
            "rotation_degrees", "rotation_pivot_x", "rotation_pivot_y",
            "scale_x", "scale_y", "scale_pivot_x", "scale_pivot_y",
            "translation_x", "translation_y",
        ):
            object.__setattr__(self, name, _f32(getattr(self, name), name))

    def apply(self, point: Sequence[float]) -> tuple[float, float]:
        """Apply native order: rotate about pivot, scale about pivot, then translate."""
        x, y = _point(point, "point")
        theta = _f32(_f32(self.rotation_degrees, "rotation_degrees")
                      * _f32(0.0174532924, "degrees_to_radians"), "rotation_radians")
        cosine = _f32(math.cos(theta), "rotation_cosine")
        sine = _f32(math.sin(theta), "rotation_sine")

        dx = _f32(x - self.rotation_pivot_x, "rotation_dx")
        dy = _f32(y - self.rotation_pivot_y, "rotation_dy")
        rotated_x = _f32(
            self.rotation_pivot_x + _f32(_f32(cosine * dx, "cos_dx")
                                         - _f32(sine * dy, "sin_dy"), "rotated_x_delta"),
            "rotated_x",
        )
        rotated_y = _f32(
            self.rotation_pivot_y + _f32(_f32(sine * dx, "sin_dx")
                                         + _f32(cosine * dy, "cos_dy"), "rotated_y_delta"),
            "rotated_y",
        )

        scaled_x = _f32(
            self.scale_pivot_x + _f32(
                _f32(rotated_x - self.scale_pivot_x, "scale_dx") * self.scale_x,
                "scaled_dx",
            ),
            "scaled_x",
        )
        scaled_y = _f32(
            self.scale_pivot_y + _f32(
                _f32(rotated_y - self.scale_pivot_y, "scale_dy") * self.scale_y,
                "scaled_dy",
            ),
            "scaled_y",
        )
        return (
            _f32(scaled_x + self.translation_x, "translated_x"),
            _f32(scaled_y + self.translation_y, "translated_y"),
        )


@dataclass(frozen=True)
class SymbolLayerInput:
    """One source-ordered Symbol with its resolved cut rectangle and texture metadata."""

    source_order: int
    contract: SymbolRenderContract
    cut_rectangle: tuple[int, int, int, int]
    png_dimensions: tuple[int, int]
    wrap_codes: tuple[int, int]
    texture_slot: int | None = None

    def __post_init__(self) -> None:
        if type(self.source_order) is not int or self.source_order < 0:
            raise SymbolRenderPlanError("source_order must be a non-negative integer")
        if not isinstance(self.contract, SymbolRenderContract):
            raise SymbolRenderPlanError("contract must be a SymbolRenderContract")
        if (self.texture_slot is not None
                and (type(self.texture_slot) is not int or not 0 <= self.texture_slot <= _S32_MAX)):
            raise SymbolRenderPlanError("texture_slot must be a non-negative signed 32-bit integer or None")


@dataclass(frozen=True)
class SymbolDrawCommand:
    """Resolved, ordered metadata for one possible native Symbol draw."""

    source_order: int
    cut_handle: int
    uv: NativeSpriteCutUV
    vertex_rgba: tuple[float, float, float, float]
    draw_enabled: bool
    blend_override: tuple[int, int] | None
    rotation_degrees: int
    offset_x: int
    offset_y: int
    scale_x: float
    scale_y: float
    tween_selectors: SymbolTweenSelectors
    symbol_mask: int
    texture_slot: int | None = None


@dataclass(frozen=True)
class SymbolFrameRenderPlan:
    """Ordered command stream; no pixels or mesh vertices are generated here."""

    commands: tuple[SymbolDrawCommand, ...]
    player_transform_order: tuple[str, str, str] = ("rotation", "scale", "translation")
    symbol_local_transform_order: tuple[str, str, str] = ("scale", "rotation", "offset")

    @property
    def command_count(self) -> int:
        return len(self.commands)

    @property
    def draw_enabled_count(self) -> int:
        return sum(command.draw_enabled for command in self.commands)

    @property
    def mask_suppressed_count(self) -> int:
        return self.command_count - self.draw_enabled_count

    @property
    def source_order(self) -> tuple[int, ...]:
        return tuple(command.source_order for command in self.commands)


def build_symbol_frame_render_plan(
    layers: Sequence[SymbolLayerInput],
    *,
    active_mask: int,
    user_rgba: Sequence[float],
) -> SymbolFrameRenderPlan:
    """Build a source-order command plan; preserve UVs and never synthesize geometry."""
    if not isinstance(layers, (tuple, list)):
        raise SymbolRenderPlanError("layers must be a sequence")
    if type(active_mask) is not int or not _S32_MIN <= active_mask <= _S32_MAX:
        raise SymbolRenderPlanError("active_mask must be a signed 32-bit integer")
    # Validate the user color even for an empty frame.
    try:
        from .symbol_render_contract import SymbolColorMultipliers
        SymbolColorMultipliers(1.0, 1.0, 1.0, 1.0).apply_user_rgba(user_rgba)
    except SymbolRenderContractError as exc:
        raise SymbolRenderPlanError("user_rgba is invalid") from exc

    commands = []
    for expected_order, layer in enumerate(layers):
        if not isinstance(layer, SymbolLayerInput):
            raise SymbolRenderPlanError("Every layer must be a SymbolLayerInput")
        if layer.source_order != expected_order:
            raise SymbolRenderPlanError("Source symbols must remain contiguous and in native draw order")
        try:
            uv = compute_native_sprite_cut_uv(
                layer.cut_rectangle, layer.png_dimensions, layer.wrap_codes
            )
            color = layer.contract.color.apply_user_rgba(user_rgba)
            draw_enabled = not layer.contract.is_suppressed_by_mask(active_mask)
            blend = layer.contract.blend.resolve()
        except (ValueError, TypeError, OverflowError) as exc:
            raise SymbolRenderPlanError("Layer could not be resolved without guessing") from exc
        commands.append(SymbolDrawCommand(
            source_order=layer.source_order,
            cut_handle=layer.contract.cut_handle,
            texture_slot=layer.texture_slot,
            uv=uv,
            vertex_rgba=color,
            draw_enabled=draw_enabled,
            blend_override=blend,
            rotation_degrees=layer.contract.rotation_degrees,
            offset_x=layer.contract.offset_x,
            offset_y=layer.contract.offset_y,
            scale_x=layer.contract.scale_x,
            scale_y=layer.contract.scale_y,
            tween_selectors=layer.contract.tween,
            symbol_mask=layer.contract.symbol_mask,
        ))
    return SymbolFrameRenderPlan(tuple(commands))
