# Stage217 — synthetic SpritePlayer transform diagnostics (no runtime parity)

## Motivation

The owner-local Stage214 CPU preview used a fixed identity `SpritePlayer` transform. Stage215 established that serialized Symbol records include local rotation, offsets, scales, tint and masks, but **not** the live SpritePlayer transform, camera, pivot state or runtime animation interpolation. Treating synthetic geometry as the game's true on-screen placement would be misleading.

## Implementation

`render_private_cpu_frame_preview(..., player_transform=None)` preserves the existing isolated identity reference by default. Passing an explicitly constructed `PlayerTransform` (nine validated binary32 parameters with independent rotation/scale pivots) allows bounded **synthetic CPU-only** geometry diagnostics. Values must be supplied by the local caller; this does not recover or guess any original runtime transform. The private CLI deliberately has no flags to imply that such values came from the iOS game.

New aggregate-only flags:
- `synthetic_player_transform_applied`: true only when a non-identity transform was supplied.
- `runtime_player_transform_grounded`: always false in this stage.
- `player_transform_values_exported`: always false; the aggregate report never lists private pivots or transform numbers.
- `source_translation_canceled_by_bounds_projection`: true. The CPU preview computes bounds of transformed geometry, recenters it on a transparent canvas, and crops padding; a translation of the entire frame can disappear from the resulting PNG.

The `player_transform` prose label says either `identity assumption` or `synthetic nonidentity geometry diagnostic; not from original runtime`. The existing GPU/runtime/scene parity booleans stay false.

## Synthetic regressions

1. The baseline and a caller-supplied X scale show a changed preview geometry width without changing the original source Symbol count or texture bindings.
2. A whole-frame integer translation produces the same cropped RGBA image as the identity reference, demonstrating **why cropped sprite art cannot prove original scene position or camera motion**.
3. A non-`PlayerTransform` object is rejected before opening any private IPA file.

These tests contain only invented synthetic sprites, PNGs and WAD records. Do not upload the owner's source files, textures, captures or private per-resource data into public GitHub Actions.

## Next original-game evidence needed

Only an independently verified original runtime trace or captured frame can establish SpritePlayer-wide pivots, translation, rotation, masks and camera placement. A frame-by-frame comparison also requires consistent timestamps/animation state and documented screen coordinates. Until those are available, Stage217 is **diagnostic**, not a claim of original iOS pixel parity or a playable remake.

## Backup dependency

Stage216's owner-private ZIP backups remain **incomplete** until the original 137,274,848-byte IPA is locally validated, the three resource bundles and manifest are uploaded to Drive, and an independently pinned checksum is verified by readback. Stage217 code does not alter that requirement.
