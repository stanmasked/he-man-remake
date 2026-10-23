# Stage193 — residual SpriteCut UV exception triage

Stage192 established the original iOS power-of-two texture allocation rule and explained most raw PNG-bound overruns. Stage193 isolates only the remaining cases instead of inventing missing texture content.

## Known private aggregate baseline

Per 2,334 original cut entries in each resolution pack:

- screen-med: 5 rectangles exceed even the allocated texture bounds; 1 rectangle has invalid signed geometry.
- screen-xlarge: 16 rectangles exceed allocated bounds; 1 rectangle has invalid signed geometry.
- Most earlier overruns are explained by native texture allocation and should **not** be treated as corrupt original PNGs.
- No evidence yet establishes that these remaining cuts are rendered, wrapped, clamped, clipped or unused in original gameplay.

## Added code

`src/heman_tools/sprite_cut_residual_triage.py` provides an asset-free classifier that receives an in-memory paired inventory and counts:

- safe extents;
- outside-allocated cases split into horizontal, vertical or both-axis overruns;
- maximum per-axis overflow in pixels;
- invalid rectangles;
- paired category transitions.

It never exports private resource keys, source offsets, individual rectangles, graphics or original IPA bytes; output is aggregate counts and explicit unresolved-evidence flags only.

`tests/test_sprite_cut_residual_triage.py` has four synthetic regressions for axis classification, cross-pack differences, missing keys and malformed image bounds.

The module does not claim to know the original GL wrap/clamp mode, texture upload padding pixels, or whether an out-of-range rectangle was actually displayed. It never returns guessed UVs or changes rendering.

## Next checks

1. Verify original Texture/SpriteCut GL state and texture upload behavior against native ARMv7 code.
2. Determine whether residual entries occur in reachable character animation frames using the existing private Symbol→SpriteCut graph.
3. Separately test the first four unknown Symbol floats and complete draw order before assembling multi-symbol output.
4. Preserve the current synthetic Switch/NeXium runtime proof as a separate evidence category.
