# Stage213 — linear texture sampling in the CPU reference renderers

## Why this stage is required

Stage212 corrected the original TextureData field map and found 292 mode-1 linear textures in each screen-resolution pack. A nearest-only oracle cannot represent those textures without silently changing their appearance.

## Sampling contract

- Filter selector 0 remains nearest: select `floor(u * width)` and `floor(v * height)`, then apply each axis's clamp-to-edge or repeat mode.
- Filter selector 1 uses bilinear filtering in normalized coordinates. Texel centers are at `(i + 0.5) / size`; the continuous texel coordinate is `coord * size - 0.5`.
- The four neighboring texels are wrapped independently per axis, then interpolated horizontally and vertically in normalized RGBA space.
- Clamp-to-edge duplicates the edge texel when a neighbor falls outside the texture. Repeat wraps each neighbor modulo the dimension, including interpolation across the seam.
- Filter selector 2 is rejected. The original loader has a mipmap path, but the current private IPA census contains zero mode-2 records and the reference does not build mipmaps.
- Texture bytes remain caller-supplied native-upload RGBA. This stage does not decode PNG, change alpha representation, flip rows, pad textures, infer camera/player transforms or submit GPU commands.

## Verification

The Python and C99 references use matching double-precision arithmetic and byte quantization. Synthetic tests verify texel-center behavior, interpolation between contrasting texels, clamp edges, repeat seams, independent S/T modes, and explicit rejection of mode 2. The Python/C differential test compares the entire rendered RGBA output and pixel counters for both S clamp and S repeat.

The interpolation is a deterministic CPU oracle. GLES implementations may use implementation-defined internal interpolation precision, and this test does not prove exact GPU output or original-runtime pixel parity.
