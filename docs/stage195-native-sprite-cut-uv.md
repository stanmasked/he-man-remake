# Stage195 — native SpriteCut UV arithmetic and transform order

Stage195 distinguishes two different requirements that must not be conflated:

- a **safe image crop** must fit inside source pixels; and
- the **original renderer's UV calculation** preserves signed SpriteCut coordinates and relies on the texture's configured OpenGL wrap mode.

The strict crop/geometry gates in Stages191–192 remain useful for validating and extracting a standalone image. They are not a faithful model of the original runtime's UV behavior.

## Native UV formula

The original `SpriteCut::buildTextCoord` reads the allocated dimensions through `Texture::getWidth/Height` (not the unpadded PNG dimensions), converts signed integer coordinates to 32-bit floats, and divides:

```text
u0 = float32(x) / float32(allocated_width)
v0 = float32(y) / float32(allocated_height)
u1 = float32(int32_add(x, width)) / float32(allocated_width)
v1 = float32(int32_add(y, height)) / float32(allocated_height)
```

The endpoint additions use native 32-bit integer arithmetic. The method does **not** clip UVs to [0,1] and does not reject negative origins, zero/negative extents, or endpoints beyond the allocated texture. The generated coordinates are passed onward to the sprite mesh.

The selected wrap pair then determines sampling:

- TextureData code 0 sets `GL_CLAMP_TO_EDGE`.
- TextureData code 1 sets `GL_REPEAT`.
- Unknown codes remain unresolved in this model; no behavior is guessed.

Stage194 found that all 5 medium and 16 extra-large rectangles outside allocated texture bounds use `GL_CLAMP_TO_EDGE` on both axes. This means the native path samples edge texels for out-of-range coordinates rather than intentionally wrapping those residual cuts to the opposite side. The audit still does not decide whether the original rectangles were deliberate or anomalous.

## Confirmed transform ordering

Read-only native method tracing establishes two separate levels:

1. **Per-Symbol mesh creation:** the Symbol's independent X/Y scales are applied while generating local geometry; the Symbol rotation is then applied to the local vertices; X/Y Symbol offsets are added afterward.
2. **SpritePlayer-wide transform:** `SpritePlayer::tween` calls `applyRotation`, then `applyScale`, then `applyTranslation` in that order.

This describes operation order only. The complete GPU mesh/vertex layout and authentic visual parity remain to be validated.

## Implementation

Added `src/heman_tools/native_sprite_cut_uv.py`:

- computes UV endpoints using the native allocated-size denominator and single-precision float rounding;
- reproduces signed 32-bit endpoint addition;
- deliberately preserves UV values outside [0,1] and reversed/zero extents instead of silently clipping them;
- attaches the known S/T wrap-mode names without pretending to emulate the GPU sampler;
- rejects malformed field types and impossible texture dimensions.

Added 14 synthetic-only tests for power-of-two denominators, out-of-range UVs, negative origins, reversed/zero extents, signed overflow, wrap-code handling, and single-precision arithmetic. No original IPA, identifiers, texture pixels or per-record values are included.

## Next step

Build a synthetic multi-Symbol mesh reference that combines the now-confirmed per-Symbol color/easing/scale fields, local transform order, SpriteCut UV endpoints, source draw order, and SpritePlayer-wide transform order. Keep source-resource resolution and unresolved cut geometry fail-closed in the audit; the renderer must preserve native UV/wrap behavior rather than replacing it with crop rules. Then privately compare one complete frame against an authentic source render before claiming visual parity.
