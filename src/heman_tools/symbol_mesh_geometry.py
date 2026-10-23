"""Stage199: source-ordered native Symbol quad geometry reference.

This models the centered four-vertex fan and transform order identified in the
original ARMv7 SpritePlayer::updateMesh/applyRotation/applyScale/
applyTranslation path. It is not a GPU renderer and does not resolve assets.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import struct

from .symbol_frame_render_plan import PlayerTransform, SymbolDrawCommand


class SymbolMeshGeometryError(ValueError):
    """Malformed or non-finite Symbol quad geometry."""


def _f32(value: int | float, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise SymbolMeshGeometryError(f"{field} must be finite")
    try:
        result = struct.unpack("<f", struct.pack("<f", float(value)))[0]
    except (OverflowError, struct.error) as exc:
        raise SymbolMeshGeometryError(f"{field} is not representable as binary32") from exc
    if not math.isfinite(result):
        raise SymbolMeshGeometryError(f"{field} is not representable as binary32")
    return result


def _add(a: float, b: float) -> float:
    return _f32(a + b, "coordinate sum")


def _sub(a: float, b: float) -> float:
    return _f32(a - b, "coordinate difference")


def _mul(a: float, b: float) -> float:
    return _f32(a * b, "coordinate product")


@dataclass(frozen=True)
class SymbolQuadGeometry:
    """Four XY vertices in native GL_TRIANGLE_FAN order and winding metadata."""

    vertices: tuple[tuple[float, float], tuple[float, float],
                    tuple[float, float], tuple[float, float]]
    front_face_flip: bool

    @property
    def flat_xy(self) -> tuple[float, ...]:
        return tuple(value for point in self.vertices for value in point)


def build_symbol_quad_geometry(
    command: SymbolDrawCommand,
    cut_width: int,
    cut_height: int,
    player_transform: PlayerTransform | None = None,
) -> SymbolQuadGeometry:
    """Build a centered quad and apply native local then player transforms.

    Signed zero/negative SpriteCut dimensions and scales are preserved. UV
    endpoints remain on the command and are not clipped or synthesized here.
    """
    if not isinstance(command, SymbolDrawCommand):
        raise SymbolMeshGeometryError("command must be a SymbolDrawCommand")
    if type(command.source_order) is not int or not 0 <= command.source_order <= (1 << 32) - 1:
        raise SymbolMeshGeometryError("source_order must be an unsigned 32-bit integer")
    if type(command.cut_handle) is not int or not -(1 << 31) <= command.cut_handle <= (1 << 31) - 1:
        raise SymbolMeshGeometryError("cut_handle must be a signed 32-bit integer")
    if not isinstance(command.uv, object):
        raise SymbolMeshGeometryError("uv metadata is missing")
    for field in ("u0", "v0", "u1", "v1"):
        _f32(getattr(command.uv, field), "uv " + field)
    if not isinstance(command.vertex_rgba, (tuple, list)) or len(command.vertex_rgba) != 4:
        raise SymbolMeshGeometryError("vertex_rgba must contain four channels")
    for channel in command.vertex_rgba:
        value = _f32(channel, "vertex_rgba")
        if value < 0.0 or value > 1.0:
            raise SymbolMeshGeometryError("vertex_rgba channel must be in [0, 1]")
    if type(command.draw_enabled) is not bool:
        raise SymbolMeshGeometryError("draw_enabled must be boolean")
    if command.blend_override is not None:
        if (not isinstance(command.blend_override, tuple)
                or len(command.blend_override) != 2
                or any(type(value) is not int or not 0 <= value <= (1 << 31) - 1
                       for value in command.blend_override)):
            raise SymbolMeshGeometryError("blend_override must be a pair of non-negative int32 values")
    if type(command.symbol_mask) is not int or not -(1 << 31) <= command.symbol_mask <= (1 << 31) - 1:
        raise SymbolMeshGeometryError("symbol_mask must be a signed 32-bit integer")
    for name, value in (("cut_width", cut_width), ("cut_height", cut_height)):
        if type(value) is not int or not -(1 << 31) <= value <= (1 << 31) - 1:
            raise SymbolMeshGeometryError(f"{name} must be a signed 32-bit integer")
    if player_transform is None:
        player_transform = PlayerTransform()
    if not isinstance(player_transform, PlayerTransform):
        raise SymbolMeshGeometryError("player_transform must be a PlayerTransform")

    try:
        rotation = _f32(command.rotation_degrees, "rotation_degrees")
        offset_x = _f32(command.offset_x, "offset_x")
        offset_y = _f32(command.offset_y, "offset_y")
        scale_x = _f32(command.scale_x, "scale_x")
        scale_y = _f32(command.scale_y, "scale_y")
        half_width = _mul(_f32(cut_width, "cut_width"), 0.5)
        half_height = _mul(_f32(cut_height, "cut_height"), 0.5)
        theta = _mul(rotation, _f32(0.0174532924, "degrees_to_radians"))
        cosine = _f32(math.cos(theta), "local cosine")
        sine = _f32(math.sin(theta), "local sine")
        corners = (
            (-half_width, -half_height),
            (-half_width, half_height),
            (half_width, half_height),
            (half_width, -half_height),
        )
        transformed = []
        for base_x, base_y in corners:
            x = _mul(_mul(base_x, scale_x), 1.0)
            y = _mul(_mul(base_y, scale_y), 1.0)
            if command.rotation_degrees != 0:
                rotated_x = _sub(_mul(cosine, x), _mul(sine, y))
                rotated_y = _add(_mul(sine, x), _mul(cosine, y))
                x, y = rotated_x, rotated_y
            x = _add(x, offset_x)
            y = _add(y, offset_y)
            x, y = player_transform.apply((x, y))
            transformed.append((_f32(x, "vertex x"), _f32(y, "vertex y")))
    except (OverflowError, TypeError, ValueError) as exc:
        if isinstance(exc, SymbolMeshGeometryError):
            raise
        raise SymbolMeshGeometryError("Quad could not be transformed without guessing") from exc

    x0, y0 = transformed[0]
    x1, y1 = transformed[1]
    x2, y2 = transformed[2]
    area = _sub(
        _mul(_sub(x1, x0), _sub(y2, y0)),
        _mul(_sub(y1, y0), _sub(x2, x0)),
    )
    return SymbolQuadGeometry(tuple(transformed), area <= 0.0)  # type: ignore[arg-type]
