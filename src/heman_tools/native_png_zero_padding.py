"""Stage223 native texture padding CPU reference."""
from __future__ import annotations

from .native_texture_upload_gate import (
    NativeTextureUploadError, NativeUploadLayout,
    plan_native_texture_upload, prepare_native_cpu_texture,
)


def reconstruct_native_zero_padded_texture(
    layout: NativeUploadLayout,
    transformed_png_rgba: bytes,
    *,
    native_png_has_alpha: bool,
):
    """Model zero-filled extra rows and columns in the original PNG reader."""
    if type(native_png_has_alpha) is not bool:
        raise NativeTextureUploadError("Native alpha flag must be boolean")
    if not isinstance(layout, NativeUploadLayout):
        raise NativeTextureUploadError("Native upload layout is required")
    verified = plan_native_texture_upload(
        (layout.png_width, layout.png_height),
        (layout.wrap_s_code, layout.wrap_t_code), layout.filter_mode_code,
    )
    if verified != layout:
        raise NativeTextureUploadError("Allocated dimensions disagree")
    width, height = layout.png_width, layout.png_height
    if type(transformed_png_rgba) is not bytes or len(transformed_png_rgba) != width * height * 4:
        raise NativeTextureUploadError("Source PNG RGBA byte count is invalid")
    if not native_png_has_alpha and any(
        transformed_png_rgba[i] != 255 for i in range(3, len(transformed_png_rgba), 4)
    ):
        raise NativeTextureUploadError("Native RGB PNG must decode as opaque RGBA")
    if not layout.needs_native_padding:
        return prepare_native_cpu_texture(layout, transformed_png_rgba)

    # The verified ARMv7 reader memset(0) writes each missing native byte.
    # In GLES, missing alpha in a three-channel RGB texture samples as 1.0.
    pixel = bytes((0, 0, 0, 0 if native_png_has_alpha else 255))
    complete = bytearray(pixel * (layout.allocated_width * layout.allocated_height))
    for row in range(height):
        start = row * width * 4
        destination = row * layout.allocated_width * 4
        complete[destination:destination + width * 4] = (
            transformed_png_rgba[start:start + width * 4]
        )
    return prepare_native_cpu_texture(
        layout, transformed_png_rgba,
        complete_allocated_rgba=bytes(complete),
    )
