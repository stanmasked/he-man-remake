"""Stage211: exact native PNG row alpha-transform reference.

Models the original PNGData user-transform callback only. PNG decoding,
libpng palette/tRNS expansion, texture allocation, padding, and GPU upload are
separate operations. Input is decoded RGBA pixels for the actual image extent.
"""
from __future__ import annotations

_MAX_RGBA_BYTES = 64 * 1024 * 1024


class NativePNGAlphaError(ValueError):
    """Invalid decoded RGBA pixels or native PNG alpha-transform parameters."""


def transform_native_png_alpha(
    rgba: bytes,
    width: int,
    height: int,
    *,
    has_alpha: bool,
    premultiply_alpha: bool,
) -> bytes:
    """Apply the native per-texture alpha transform when its flag is enabled.

    RGB uses the exact source expression (channel * alpha + 127) >> 8;
    alpha is unchanged. This preserves native divide-by-256 behavior (255*255
    maps to 254), rather than substituting a conventional divide-by-255 formula.
    """
    if type(rgba) is not bytes:
        raise NativePNGAlphaError("rgba must be immutable bytes")
    if (type(width) is not int or type(height) is not int
            or width <= 0 or height <= 0):
        raise NativePNGAlphaError("width and height must be positive integers")
    if type(has_alpha) is not bool or type(premultiply_alpha) is not bool:
        raise NativePNGAlphaError("alpha flags must be booleans")
    expected = width * height * 4
    if expected > _MAX_RGBA_BYTES:
        raise NativePNGAlphaError("decoded RGBA texture exceeds the byte limit")
    if len(rgba) != expected:
        raise NativePNGAlphaError("decoded RGBA byte length does not match dimensions")
    if not has_alpha or not premultiply_alpha:
        return rgba

    output = bytearray(rgba)
    for at in range(0, expected, 4):
        alpha = output[at + 3]
        output[at] = (output[at] * alpha + 127) >> 8
        output[at + 1] = (output[at + 1] * alpha + 127) >> 8
        output[at + 2] = (output[at + 2] * alpha + 127) >> 8
    return bytes(output)
