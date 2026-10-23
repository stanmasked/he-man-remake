"""Stage222: source-safe native texture allocation and CPU upload readiness.

SpriteCut native UVs use minimum-four/next-power-of-two allocation dimensions.
Do *not* pass raw PNG-size RGBA as a texture whose UV denominator is its
padded allocation. Padded texel values in the original iOS upload are not
recovered by the asset census; copying edge pixels, zero-filling or remapping
UVs would invent evidence.

This contract requires complete externally supplied allocated RGBA for
padded textures and verifies its visible PNG subrectangle byte-for-byte.
It does not authenticate the external padding itself, nor claim GPU,
Switch DKSH, or original runtime pixel parity.
"""
from __future__ import annotations

from dataclasses import dataclass

from .sprite_cut_runtime_texture_bounds import allocated_texture_dimensions
from .textured_quad_reference import (
    MAX_TEXTURE_BYTES, TexturePixels, TexturedQuadRenderError,
)


class NativeTextureUploadError(ValueError):
    """Cannot prepare a bounded native-allocation texture without assumptions."""


@dataclass(frozen=True)
class NativeUploadLayout:
    png_width: int
    png_height: int
    allocated_width: int
    allocated_height: int
    wrap_s_code: int
    wrap_t_code: int
    filter_mode_code: int

    @property
    def needs_native_padding(self) -> bool:
        return (self.png_width != self.allocated_width
                or self.png_height != self.allocated_height)

    @property
    def allocated_rgba_size(self) -> int:
        return self.allocated_width * self.allocated_height * 4

    def aggregate_only(self) -> dict:
        """No raw pixels, source resource names or padding values are exported."""
        return {
            "classification": "native_texture_upload_readiness_gate",
            "png_dimensions": [self.png_width, self.png_height],
            "allocated_dimensions": [self.allocated_width, self.allocated_height],
            "padding_texels_required": self.needs_native_padding,
            "raw_png_buffer_directly_usable": not self.needs_native_padding,
            "wrap_s_repeat": self.wrap_s_code == 1,
            "wrap_t_repeat": self.wrap_t_code == 1,
            "sampler_filter": "nearest" if self.filter_mode_code == 0 else "linear",
            "original_native_padding_pixels_recovered": False,
            "source_texture_pixels_exported": False,
            "original_ios_gpu_pixel_parity_verified": False,
            "switch_hardware_gpu_parity_verified": False,
        }


def plan_native_texture_upload(
    png_dimensions: tuple[int, int],
    wrap_codes: tuple[int, int],
    filter_mode_code: int,
) -> NativeUploadLayout:
    """Check genuine allocation geometry and only supported CPU sample modes."""
    if not isinstance(png_dimensions, tuple) or len(png_dimensions) != 2:
        raise NativeTextureUploadError("PNG dimensions must be a two-item tuple")
    try:
        aw, ah = allocated_texture_dimensions(png_dimensions)
    except (ValueError, TypeError, OverflowError) as exc:
        raise NativeTextureUploadError("PNG dimensions cannot be allocated safely") from exc
    if (not isinstance(wrap_codes, tuple) or len(wrap_codes) != 2
            or any(type(code) is not int or code not in (0, 1)
                   for code in wrap_codes)):
        raise NativeTextureUploadError("Wrap codes must be explicit clamp/repeat integers")
    if type(filter_mode_code) is not int or filter_mode_code not in (0, 1):
        raise NativeTextureUploadError("Only verified nearest/linear CPU filters are supported")
    if aw * ah * 4 > MAX_TEXTURE_BYTES:
        raise NativeTextureUploadError("Allocated texture exceeds the bounded RGBA byte budget")
    return NativeUploadLayout(
        png_dimensions[0], png_dimensions[1], aw, ah,
        wrap_codes[0], wrap_codes[1], filter_mode_code,
    )


def prepare_native_cpu_texture(
    layout: NativeUploadLayout,
    transformed_png_rgba: bytes,
    *,
    complete_allocated_rgba: bytes | None = None,
) -> TexturePixels:
    """Bind only a correctly sized native-layout buffer for CPU diagnostics.

    Caller must supply upload-row-ordered RGBA (already alpha transformed).
    For any padded PNG, a complete caller-provided allocated buffer is
    required, with its visible PNG rows identical to the source. The method
    does not assert that the padding came from the original game.
    """
    if not isinstance(layout, NativeUploadLayout):
        raise NativeTextureUploadError("A validated native upload layout is required")
    # Do not trust a manually instantiated dataclass without revalidation.
    verified_layout = plan_native_texture_upload(
        (layout.png_width, layout.png_height),
        (layout.wrap_s_code, layout.wrap_t_code),
        layout.filter_mode_code,
    )
    if verified_layout != layout:
        raise NativeTextureUploadError("Native upload allocation fields disagree with PNG metadata")
    expected_source_bytes = layout.png_width * layout.png_height * 4
    if type(transformed_png_rgba) is not bytes or len(transformed_png_rgba) != expected_source_bytes:
        raise NativeTextureUploadError("Native PNG RGBA byte length does not match source dimensions")
    if complete_allocated_rgba is None:
        if layout.needs_native_padding:
            raise NativeTextureUploadError(
                "Native padding texels are unverified: refuse raw PNG-size texture upload"
            )
        source = transformed_png_rgba
    else:
        if type(complete_allocated_rgba) is not bytes or len(complete_allocated_rgba) != layout.allocated_rgba_size:
            raise NativeTextureUploadError("Complete allocated RGBA byte length is invalid")
        for row in range(layout.png_height):
            start = row * layout.png_width * 4
            upload_start = row * layout.allocated_width * 4
            count = layout.png_width * 4
            if complete_allocated_rgba[upload_start:upload_start+count] != transformed_png_rgba[start:start+count]:
                raise NativeTextureUploadError(
                    "Complete allocated RGBA does not preserve visible PNG rows"
                )
        source = complete_allocated_rgba
    try:
        return TexturePixels(
            width=layout.allocated_width, height=layout.allocated_height,
            rgba=source,
            wrap_s_code=layout.wrap_s_code, wrap_t_code=layout.wrap_t_code,
            filter_mode_code=layout.filter_mode_code,
        )
    except TexturedQuadRenderError as exc:
        raise NativeTextureUploadError("Texture binding is incompatible with CPU sampler") from exc
