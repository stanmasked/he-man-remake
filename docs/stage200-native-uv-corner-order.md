# Stage200 — exact native SpriteCut UV corner order

Stage200 closes the UV-corner-order question left open by Stage199 using the original ARMv7 `SpriteCut::buildTextCoord` store sequence and the already traced four-vertex `GL_TRIANGLE_FAN` order. The original IPA remains private; no image pixels, resource keys, offsets or per-record data are committed.

## Native UV store sequence

The original method computes:

- (u_0 = x / mathrm{Texture::getWidth}())
- (v_0 = y / mathrm{Texture::getHeight}())
- (u_1 = (x+w) / mathrm{Texture::getWidth}())
- (v_1 = (y+h) / mathrm{Texture::getHeight}())

The denominator is the allocated power-of-two texture extent established in Stage192. The method then writes the eight floats in this exact order:

| SpriteCut byte offset | Value | Vertex |
|---|---|---|
| `+0x14` | `u0` | 0 |
| `+0x18` | `v0` | 0 |
| `+0x1C` | `u0` | 1 |
| `+0x20` | `v1` | 1 |
| `+0x24` | `u1` | 2 |
| `+0x28` | `v1` | 2 |
| `+0x2C` | `u1` | 3 |
| `+0x30` | `v0` | 3 |

Thus the UV pairs are exactly **(u0,v0), (u0,v1), (u1,v1), (u1,v0)**, matching the four vertex pairs stored by `SpritePlayer::updateMesh` and consumed by `GL_TRIANGLE_FAN`. Negative or above-one coordinates remain unchanged; native texture wrap behavior controls sampling.

## Implementation

- Adds `hm_symbol_mesh_expand_uvs` to the portable C99 mesh geometry interface.
- Adds Python `expand_native_uv_corners` returning the same four pairs with binary32 endpoints.
- Shares command validation with the geometry builder, rejects malformed/non-finite commands, and writes C output only on success.
- Adds two C99 and two Python synthetic tests for exact corner order, out-of-range UV preservation and fail-closed validation.

This establishes coordinate ordering, not final pixel parity. Texture filtering, blend state, mask state, rasterization edge rules and private full-frame comparison still require integration evidence.
