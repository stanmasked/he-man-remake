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
