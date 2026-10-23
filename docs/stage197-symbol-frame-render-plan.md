# Stage197 — ordered multi-Symbol render-command reference

Stage197 connects the independently verified field contracts from Stages193–196 into one asset-free frame plan. This is an integration boundary for the future renderer, not yet a pixel renderer.

## What one command contains

For every source Symbol, in original serialized order, the plan combines:

- the resolved SpriteCut handle and native UV endpoints from Stage195, including UVs outside [0,1];
- native wrap-mode names, preserving clamp/repeat semantics;
- the four Symbol color multipliers applied to the caller's RGBA color and clamped per channel;
- rotation, X/Y offsets and independent scales;
- the four easing selectors, blend override (only when its source/destination fields resolve), and Symbol mask;
- a draw-enabled flag derived from the intersection of Symbol and active masks.

Masked symbols remain in the command list, but are marked non-drawable. This preserves source identity and ordering for diagnostics without pretending that a suppressed layer was drawn. The command builder rejects reordered or missing source-order indices instead of sorting them.

## SpritePlayer-wide transform

`PlayerTransform` models the native `SpritePlayer::tween` order:

1. rotate each point around the configured rotation pivot;
2. scale X and Y independently around the configured scale pivot;
3. add the translation.

The rotation uses the original degrees-to-radians constant and 32-bit float rounding. The local Symbol transform order is retained as Stage195 established it: scale, rotation, then offset. The command plan deliberately does not invent quad vertices; the exact vertex layout and final GPU parity remain the next graphics milestone.

## Implementation and tests

Added `src/heman_tools/symbol_frame_render_plan.py`:

- builds an ordered command stream from already-resolved layer metadata;
- uses the Stage193 color, tween, blend and mask contract, Stage195 native UV arithmetic, and Stage194 wrap names;
- applies strict type and finite-number checks;
- preserves out-of-range UVs, negative scale values and source draw order;
- does not read the original IPA, export original resource names, synthesize textures, or draw pixels.

Added 20 synthetic-only tests covering command ordering, masks, color channels, blend sentinels, native UV preservation, transform pivots/order, negative scale, and fail-closed inputs.

## Remaining steps

1. Resolve the original mesh vertex buffer layout and exact local coordinate construction from `SpritePlayer::updateMesh`.
2. Build the four quad vertices from the cut dimensions and Symbol transforms without reinterpreting UVs as crop bounds.
3. Privately render one complete multi-Symbol frame and compare it with a trustworthy original-runtime frame or source footage.
4. Only after that parity gate, connect the validated command plan to the Switch graphics adapter. A successful plan test alone is not evidence of gameplay readiness.
