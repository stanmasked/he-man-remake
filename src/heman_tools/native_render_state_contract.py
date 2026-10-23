"""Stage206: source-confirmed native texture sampling and default blend state.

The serialized TextureData filter selector is a boolean byte. Loader modes 0
and 1 map to nearest and linear min/mag filtering respectively; the loader's
mipmap mode 2 exists but is not representable by this TextureData field.
The default SpritePlayer blend factors are GL_ONE / GL_ONE_MINUS_SRC_ALPHA,
but runtime custom factors and per-Symbol overrides must remain supported.
"""
from __future__ import annotations

from dataclasses import dataclass

GL_ZERO = 0
GL_ONE = 1
GL_SRC_COLOR = 0x0300
GL_ONE_MINUS_SRC_COLOR = 0x0301
GL_SRC_ALPHA = 0x0302
GL_ONE_MINUS_SRC_ALPHA = 0x0303
GL_DST_ALPHA = 0x0304
GL_ONE_MINUS_DST_ALPHA = 0x0305
GL_NEAREST = 0x2600
GL_LINEAR = 0x2601
GL_LINEAR_MIPMAP_NEAREST = 0x2701
GL_TEXTURE_MAG_FILTER = 0x2800
GL_TEXTURE_MIN_FILTER = 0x2801
GL_GENERATE_MIPMAP = 0x8191
GL_CLAMP_TO_EDGE = 0x812F
GL_REPEAT = 0x2901

NATIVE_DEFAULT_PLAYER_BLEND = (GL_ONE, GL_ONE_MINUS_SRC_ALPHA)


class NativeRenderStateError(ValueError):
    """Invalid serialized texture filter selector or unsupported loader mode."""


@dataclass(frozen=True)
class NativeTextureSamplingState:
    filter_mode_code: int
    filter_mode_name: str
    min_filter: int
    mag_filter: int
    generate_mipmaps: bool


def decode_texture_filter_mode(scalar_block: bytes) -> int:
    """Decode the final boolean byte of the 13-byte native TextureData scalar block."""
    if type(scalar_block) is not bytes or len(scalar_block) != 13:
        raise NativeRenderStateError("TextureData scalar block must contain exactly 13 bytes")
    code = scalar_block[12]
    if code not in (0, 1):
        raise NativeRenderStateError("Serialized TextureData filter selector must be boolean 0 or 1")
    return code


def resolve_texture_sampling_state(filter_mode_code: int, *, force_nearest: bool = False) -> NativeTextureSamplingState:
    """Resolve the observed loader state; force_nearest models its global override gate."""
    if type(force_nearest) is not bool:
        raise NativeRenderStateError("force_nearest must be boolean")
    if type(filter_mode_code) is not int or filter_mode_code not in (0, 1, 2):
        raise NativeRenderStateError("Native loader filter mode must be 0, 1, or 2")
    effective = 0 if force_nearest else filter_mode_code
    if effective == 0:
        return NativeTextureSamplingState(0, "nearest", GL_NEAREST, GL_NEAREST, False)
    if effective == 1:
        return NativeTextureSamplingState(1, "linear", GL_LINEAR, GL_LINEAR, False)
    return NativeTextureSamplingState(2, "linear_mipmap_nearest", GL_LINEAR_MIPMAP_NEAREST,
                                      GL_LINEAR, True)
