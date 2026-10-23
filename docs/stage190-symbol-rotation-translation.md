# Stage190 — confirmed Symbol rotation and translation subset

Stage190 uses the original ARMv7 rendering path to resolve the Symbol cut handle, rotation, X/Y offsets, and the final two per-axis scale fields. This is a partial transform contract, not a full sprite renderer.

## Native evidence

For each Symbol record, the four signed integers after the resource name are:

1. the SpriteCut handle;
2. rotation in degrees;
3. local X offset;
4. local Y offset.

The caller passes the rotation and offsets into `SpritePlayer::updateMesh`. The native implementation multiplies the rotation value by the floating-point constant **0.0174532924** (π/180) before calling sine and cosine, then applies the standard rotation matrix and adds the X/Y translation.

A private aggregate census across 14,971 Symbols found 13,664 zero rotations; rotation ranges from -585 to 585, X offsets from -256 to 576, and Y offsets from -512 to 384. The final two serialized floats are used by native SpriteFrame::computeFrameArea to scale both the local X/Y offsets and the cut width/height, confirming independent X/Y scale multipliers. Their aggregate ranges are -12..130 and -5..64. These are aggregate counts/ranges only; no resource labels, keys, or per-record values are exported.

## Changes

- Added `src/heman_tools/symbol_rotation_translation.py`, which models the confirmed rotation/translation subset.
- Added `src/heman_tools/symbol_axis_scale.py`, which models the confirmed final two float fields as independent X/Y scales without clipping negative or large values.
- Added 19 synthetic-only tests across rotation/translation and axis scaling.
- The first four serialized float fields remain uninterpreted. The partial helpers are not yet wired into the private crop decoder or production NRO.

## Next step

Resolve the first four float fields and the remaining Symbol scalar tail from the native rendering code. Then confirm the full operation order and use the complete transform contract to compose multi-symbol frames, preserving draw order and failing closed on any unresolved or out-of-bounds cut.
