"""Stage207: deterministic CPU reference for native textured Symbol quads."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math

from .native_render_state_contract import (
    GL_ONE, GL_ONE_MINUS_SRC_ALPHA, GL_SRC_COLOR, GL_ONE_MINUS_SRC_COLOR,
    GL_SRC_ALPHA, GL_DST_ALPHA, GL_ONE_MINUS_DST_ALPHA, GL_ZERO,
)
from .symbol_frame_assembler import NativeFramePacket

GL_DST_COLOR = 0x0306
GL_ONE_MINUS_DST_COLOR = 0x0307
GL_SRC_ALPHA_SATURATE = 0x0308
MAX_TEXTURE_BYTES = 64 * 1024 * 1024
MAX_FRAME_PIXELS = 4_194_304
MAX_SAMPLE_ATTEMPTS = 16_777_216
MAX_PACKETS = 1024
MAX_ABS_COORDINATE = 10_000_000.0
_S32_MIN, _S32_MAX = -(1 << 31), (1 << 31) - 1
_BLEND_FACTORS = {
    GL_ZERO, GL_ONE, GL_SRC_COLOR, GL_ONE_MINUS_SRC_COLOR, GL_DST_COLOR,
    GL_ONE_MINUS_DST_COLOR, GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA,
    GL_DST_ALPHA, GL_ONE_MINUS_DST_ALPHA, GL_SRC_ALPHA_SATURATE,
}


class TexturedQuadRenderError(ValueError):
    """Invalid source packet, texture state, projection, or bounded render."""


def _finite(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TexturedQuadRenderError(f"{field} must be a finite number")
    try:
        finite = math.isfinite(value)
        result = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise TexturedQuadRenderError(f"{field} must be finite and representable") from exc
    if not finite or not math.isfinite(result):
        raise TexturedQuadRenderError(f"{field} must be a finite number")
    if abs(result) > MAX_ABS_COORDINATE:
        raise TexturedQuadRenderError(f"{field} exceeds the bounded coordinate range")
    return result


def _validate_factor(value: object, field: str, *, source: bool) -> int:
    if type(value) is not int or value not in _BLEND_FACTORS:
        raise TexturedQuadRenderError(f"{field} is not a supported GLES blend factor")
    if value == GL_SRC_ALPHA_SATURATE and not source:
        raise TexturedQuadRenderError("GL_SRC_ALPHA_SATURATE is valid only as a source factor")
    return value


@dataclass(frozen=True)
class TexturePixels:
    """RGBA texels in native-upload row order; row zero is addressed by v=0.

    Wrap codes are 0=clamp-to-edge and 1=repeat. Only filter selector 0 is
    accepted because every TextureData record in the inspected IPA uses nearest
    sampling. Bytes must already match native upload representation; this class
    does not decode PNGs, flip rows, pad dimensions or premultiply RGB. When
    source alpha is present, rgba must already use the native premultiplied
    representation produced by PNGData before texture upload.
    """
    width: int
    height: int
    rgba: bytes
    wrap_s_code: int
    wrap_t_code: int
    filter_mode_code: int = 0

    def __post_init__(self) -> None:
        if (type(self.width) is not int or type(self.height) is not int
                or self.width <= 0 or self.height <= 0):
            raise TexturedQuadRenderError("texture dimensions must be positive integers")
        expected = self.width * self.height * 4
        if expected > MAX_TEXTURE_BYTES:
            raise TexturedQuadRenderError("texture exceeds the byte-size limit")
        if type(self.rgba) is not bytes or len(self.rgba) != expected:
            raise TexturedQuadRenderError("texture must contain exactly width*height*4 RGBA bytes")
        if type(self.wrap_s_code) is not int or self.wrap_s_code not in (0, 1):
            raise TexturedQuadRenderError("S wrap code must be 0 (clamp) or 1 (repeat)")
        if type(self.wrap_t_code) is not int or self.wrap_t_code not in (0, 1):
            raise TexturedQuadRenderError("T wrap code must be 0 (clamp) or 1 (repeat)")
        if type(self.filter_mode_code) is not int or self.filter_mode_code != 0:
            raise TexturedQuadRenderError("Stage207 supports nearest filter selector 0 only")


@dataclass(frozen=True)
class FrameBlendState:
    """Explicit frame-level GLES blend factors; packet overrides take precedence."""
    source_factor: int = GL_ONE
    destination_factor: int = GL_ONE_MINUS_SRC_ALPHA

    def __post_init__(self) -> None:
        _validate_factor(self.source_factor, "frame source factor", source=True)
        _validate_factor(self.destination_factor, "frame destination factor", source=False)


@dataclass(frozen=True)
class RasterProjection:
    """Explicit affine map from native XY to top-left-origin pixel coordinates.

    x' = m00*x + m01*y + tx; y' = m10*x + m11*y + ty.
    """
    m00: float = 1.0
    m01: float = 0.0
    tx: float = 0.0
    m10: float = 0.0
    m11: float = 1.0
    ty: float = 0.0

    def __post_init__(self) -> None:
        for name in ("m00", "m01", "tx", "m10", "m11", "ty"):
            object.__setattr__(self, name, _finite(getattr(self, name), name))

    def apply(self, point: Sequence[float]) -> tuple[float, float]:
        if not isinstance(point, (tuple, list)) or len(point) != 2:
            raise TexturedQuadRenderError("projected point must contain exactly two coordinates")
        x, y = _finite(point[0], "vertex x"), _finite(point[1], "vertex y")
        return (_finite(self.m00*x + self.m01*y + self.tx, "projected x"),
                _finite(self.m10*x + self.m11*y + self.ty, "projected y"))


@dataclass(frozen=True)
class SoftwareFrameResult:
    """Rendered RGBA bytes and aggregate CPU-only counters."""
    width: int
    height: int
    rgba: bytes
    packets_considered: int
    packets_with_coverage: int
    pixel_samples: int


def _validate_packet(packet: object, previous_order: int) -> NativeFramePacket:
    if not isinstance(packet, NativeFramePacket):
        raise TexturedQuadRenderError("every packet must be a NativeFramePacket")
    if (type(packet.source_order) is not int or packet.source_order < 0
            or packet.source_order <= previous_order):
        raise TexturedQuadRenderError("packet source_order values must be strictly increasing")
    if type(packet.cut_handle) is not int or not _S32_MIN <= packet.cut_handle <= _S32_MAX:
        raise TexturedQuadRenderError("cut_handle must be a signed 32-bit integer")
    if type(packet.texture_slot) is not int or not 0 <= packet.texture_slot <= _S32_MAX:
        raise TexturedQuadRenderError("texture_slot must be a non-negative signed 32-bit integer")
    if type(packet.front_face_flip) is not bool:
        raise TexturedQuadRenderError("front_face_flip must be boolean")
    if not isinstance(packet.xy, tuple) or len(packet.xy) != 8:
        raise TexturedQuadRenderError("packet XY must contain four ordered vertices")
    if not isinstance(packet.uv, tuple) or len(packet.uv) != 8:
        raise TexturedQuadRenderError("packet UV must contain four ordered coordinate pairs")
    if not isinstance(packet.rgba, tuple) or len(packet.rgba) != 4:
        raise TexturedQuadRenderError("packet RGBA must contain four channels")
    for value in packet.xy:
        _finite(value, "packet XY")
    uv = tuple(_finite(value, "packet UV") for value in packet.uv)
    rgba = tuple(_finite(value, "packet RGBA") for value in packet.rgba)
    if any(value < 0.0 or value > 1.0 for value in rgba):
        raise TexturedQuadRenderError("packet RGBA channels must be in [0,1]")
    # Native UV corner order: (u0,v0), (u0,v1), (u1,v1), (u1,v0).
    if not (uv[0] == uv[2] and uv[1] == uv[7]
            and uv[3] == uv[5] and uv[4] == uv[6]):
        raise TexturedQuadRenderError("UV corners do not match the native affine quad layout")
    if packet.blend_override is not None:
        if not isinstance(packet.blend_override, tuple) or len(packet.blend_override) != 2:
            raise TexturedQuadRenderError("blend_override must be None or a factor pair")
        _validate_factor(packet.blend_override[0], "Symbol source factor", source=True)
        _validate_factor(packet.blend_override[1], "Symbol destination factor", source=False)
    return packet


def _nearest_index(coord: float, size: int, wrap_code: int) -> int:
    index = math.floor(coord * size)
    return min(size - 1, max(0, index)) if wrap_code == 0 else index % size


def _sample_nearest(texture: TexturePixels, u: float, v: float) -> tuple[int, int, int, int]:
    x = _nearest_index(u, texture.width, texture.wrap_s_code)
    y = _nearest_index(v, texture.height, texture.wrap_t_code)
    at = (y * texture.width + x) * 4
    return (texture.rgba[at], texture.rgba[at+1],
            texture.rgba[at+2], texture.rgba[at+3])


def _factor_value(factor: int, source: tuple[float, ...],
                  destination: tuple[float, ...], channel: int) -> float:
    if factor == GL_ZERO: return 0.0
    if factor == GL_ONE: return 1.0
    if factor == GL_SRC_COLOR: return source[channel]
    if factor == GL_ONE_MINUS_SRC_COLOR: return 1.0 - source[channel]
    if factor == GL_DST_COLOR: return destination[channel]
    if factor == GL_ONE_MINUS_DST_COLOR: return 1.0 - destination[channel]
    if factor == GL_SRC_ALPHA: return source[3]
    if factor == GL_ONE_MINUS_SRC_ALPHA: return 1.0 - source[3]
    if factor == GL_DST_ALPHA: return destination[3]
    if factor == GL_ONE_MINUS_DST_ALPHA: return 1.0 - destination[3]
    if factor == GL_SRC_ALPHA_SATURATE:
        return 1.0 if channel == 3 else min(source[3], 1.0 - destination[3])
    raise TexturedQuadRenderError("unsupported blend factor reached raster stage")


def _byte(value: float) -> int:
    return int(math.floor(min(1.0, max(0.0, value)) * 255.0 + 0.5))


def _blend_pixel(source: tuple[float, float, float, float],
                 destination_bytes: tuple[int, int, int, int],
                 state: FrameBlendState) -> tuple[int, int, int, int]:
    destination = tuple(channel / 255.0 for channel in destination_bytes)
    result = []
    for channel in range(4):
        sf = _factor_value(state.source_factor, source, destination, channel)
        df = _factor_value(state.destination_factor, source, destination, channel)
        result.append(_byte(source[channel] * sf + destination[channel] * df))
    return tuple(result)  # type: ignore[return-value]


def render_textured_frame(
    packets: Sequence[NativeFramePacket],
    textures_by_slot: Mapping[int, TexturePixels],
    *,
    width: int,
    height: int,
    projection: RasterProjection,
    frame_blend: FrameBlendState,
    clear_rgba: tuple[int, int, int, int] = (0, 0, 0, 0),
) -> SoftwareFrameResult:
    """Rasterize ordered packets with nearest sampling and GLES blend factors.

    Packet XY already includes Symbol-local and explicit SpritePlayer transforms
    from Stage201 assembly. Projection is a separate caller-supplied mapping to
    output pixels. All input and work-budget validation occurs before rendering.
    """
    if not isinstance(packets, (tuple, list)):
        raise TexturedQuadRenderError("packets must be a tuple or list")
    if len(packets) > MAX_PACKETS:
        raise TexturedQuadRenderError("frame exceeds the bounded packet limit")
    if type(width) is not int or type(height) is not int or width <= 0 or height <= 0:
        raise TexturedQuadRenderError("frame dimensions must be positive integers")
    if width * height > MAX_FRAME_PIXELS:
        raise TexturedQuadRenderError("frame exceeds the pixel-count limit")
    if not isinstance(projection, RasterProjection):
        raise TexturedQuadRenderError("projection must be explicit RasterProjection state")
    if not isinstance(frame_blend, FrameBlendState):
        raise TexturedQuadRenderError("frame_blend must be explicit FrameBlendState")
    if (not isinstance(clear_rgba, (tuple, list)) or len(clear_rgba) != 4
            or any(type(c) is not int or not 0 <= c <= 255 for c in clear_rgba)):
        raise TexturedQuadRenderError("clear_rgba must contain four byte channels")
    if not isinstance(textures_by_cut_handle, Mapping):
        raise TexturedQuadRenderError("textures_by_cut_handle must be a mapping")
    for key, value in textures_by_cut_handle.items():
        if type(key) is not int or not _S32_MIN <= key <= _S32_MAX:
            raise TexturedQuadRenderError("texture mapping keys must be non-negative signed 32-bit texture slots")
        if not isinstance(value, TexturePixels):
            raise TexturedQuadRenderError("every texture mapping value must be TexturePixels")

    prepared = []
    previous_order = -1
    sample_budget = 0
    for raw_packet in packets:
        packet = _validate_packet(raw_packet, previous_order)
        previous_order = packet.source_order
        try:
            texture = textures_by_cut_handle[packet.cut_handle]
        except KeyError as exc:
            raise TexturedQuadRenderError("packet texture_slot has no resolved texture") from exc
        points = tuple(projection.apply(
            (packet.xy[index*2], packet.xy[index*2+1])
        ) for index in range(4))
        p0, p1, p2, p3 = points
        expected_p2 = (p3[0] + p1[0] - p0[0], p3[1] + p1[1] - p0[1])
        tolerance = 1e-5 + 2e-6 * max(
            1.0, *(abs(v) for point in points for v in point)
        )
        if (abs(p2[0]-expected_p2[0]) > tolerance
                or abs(p2[1]-expected_p2[1]) > tolerance):
            raise TexturedQuadRenderError("projected quad is not an affine parallelogram")
        min_x = max(0, math.floor(min(point[0] for point in points)))
        max_x = min(width, math.ceil(max(point[0] for point in points)))
        min_y = max(0, math.floor(min(point[1] for point in points)))
        max_y = min(height, math.ceil(max(point[1] for point in points)))
        area = max(0, max_x-min_x) * max(0, max_y-min_y)
        ex_x, ex_y = p3[0]-p0[0], p3[1]-p0[1]
        ey_x, ey_y = p1[0]-p0[0], p1[1]-p0[1]
        determinant = ex_x*ey_y - ex_y*ey_x
        if determinant != 0.0:
            sample_budget += area
            if sample_budget > MAX_SAMPLE_ATTEMPTS:
                raise TexturedQuadRenderError("frame exceeds the bounded sample-attempt budget")
        blend = FrameBlendState(*packet.blend_override) if packet.blend_override is not None else frame_blend
        prepared.append((packet, texture, points, min_x, max_x, min_y, max_y,
                         ex_x, ex_y, ey_x, ey_y, determinant, blend))

    pixels = bytearray(bytes(clear_rgba) * (width * height))
    packets_with_coverage = pixel_samples = 0
    for (packet, texture, points, min_x, max_x, min_y, max_y,
         ex_x, ex_y, ey_x, ey_y, determinant, blend) in prepared:
        if determinant == 0.0 or min_x >= max_x or min_y >= max_y:
            continue
        p0 = points[0]
        packet_samples = 0
        for py in range(min_y, max_y):
            dy = py + 0.5 - p0[1]
            for px in range(min_x, max_x):
                dx = px + 0.5 - p0[0]
                s = (dx*ey_y - dy*ey_x) / determinant
                t = (ex_x*dy - ex_y*dx) / determinant
                if s < 0.0 or s >= 1.0 or t < 0.0 or t >= 1.0:
                    continue
                u = packet.uv[0] + s * (packet.uv[6] - packet.uv[0])
                v = packet.uv[1] + t * (packet.uv[3] - packet.uv[1])
                texel = _sample_nearest(texture, u, v)
                source = tuple(min(1.0, max(0.0,
                    (texel[i] / 255.0) * packet.rgba[i])) for i in range(4))
                at = (py * width + px) * 4
                destination = (pixels[at], pixels[at+1], pixels[at+2], pixels[at+3])
                pixels[at:at+4] = bytes(_blend_pixel(source, destination, blend))
                packet_samples += 1
        if packet_samples:
            packets_with_coverage += 1
            pixel_samples += packet_samples
    return SoftwareFrameResult(
        width, height, bytes(pixels), len(packets), packets_with_coverage, pixel_samples
    )
