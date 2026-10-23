"""Stage212: corrected native TextureData sampling and alpha-transform field map.

The 13-byte scalar block stores the alpha-transform flag at byte 5, the
signed little-endian filter mode at bytes 6..9, S/T wrap codes at 10/11,
and the image-payload path selector at byte 12. The owner's current IPA has
1353 nearest and 292 linear textures per screen pack; every alpha-transform
flag and payload selector is zero.
"""
from __future__ import annotations

from dataclasses import dataclass
import struct

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
    """Invalid TextureData scalar field or unsupported native loader mode."""


@dataclass(frozen=True)
class NativeTextureSamplingState:
    filter_mode_code: int
    filter_mode_name: str
    min_filter: int
    mag_filter: int
    generate_mipmaps: bool


def _validate_scalar_block(scalar_block: bytes) -> None:
    if type(scalar_block) is not bytes or len(scalar_block) != 13:
        raise NativeRenderStateError("TextureData scalar block must contain exactly 13 bytes")


def decode_texture_filter_mode(scalar_block: bytes) -> int:
    """Read the signed 32-bit loader filter mode from scalar bytes 6..9."""
    _validate_scalar_block(scalar_block)
    code = struct.unpack_from("<i", scalar_block, 6)[0]
    if code not in (0, 1, 2):
        raise NativeRenderStateError("Serialized TextureData filter mode must be 0, 1, or 2")
    return code


def decode_texture_alpha_transform_flag(scalar_block: bytes) -> int:
    """Read the PNGData RGB-by-alpha callback flag from scalar byte 5."""
    _validate_scalar_block(scalar_block)
    code = scalar_block[5]
    if code not in (0, 1):
        raise NativeRenderStateError("TextureData alpha-transform flag must be boolean 0 or 1")
    return code


def decode_texture_payload_selector(scalar_block: bytes) -> int:
    """Read the loader's PNG-versus-alternate payload selector at scalar byte 12."""
    _validate_scalar_block(scalar_block)
    code = scalar_block[12]
    if code not in (0, 1):
        raise NativeRenderStateError("TextureData payload selector must be boolean 0 or 1")
    return code


def resolve_texture_sampling_state(filter_mode_code: int, *, force_nearest: bool = False) -> NativeTextureSamplingState:
    """Resolve supported loader modes; force_nearest models its global override gate."""
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
