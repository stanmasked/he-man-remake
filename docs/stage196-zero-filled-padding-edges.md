# Stage196 — zero-filled PNG padding and residual edge samples

Stage196 traces the original PNG buffer construction and joins that evidence to the remaining out-of-allocation SpriteCut rectangles. This closes the last ambiguity about what a clamp-to-edge sampler sees when the texture has power-of-two padding.

## Native buffer initialization

In the original ARMv7 `PNGData::pngInfoCallback`:

1. The image buffer uses the allocated power-of-two width and height, with the native decoded bytes-per-pixel stride.
2. For every actual image row, the callback explicitly zeroes the bytes between the actual PNG width and allocated texture width.
3. It then zeroes every full row between the actual PNG height and allocated height.
4. `pngRowCallback` writes decoded source-row pixels using the allocated-width stride, leaving those padding regions zero.

Therefore right-side and bottom padding bytes are zero after decoding. They are transparent black when the decoded texture format includes alpha, or black in a three-byte RGB texture. This conclusion comes from native buffer writes; the audit does not extract or publish padding pixels.

## Private residual-edge census

Every remaining cut outside allocated texture bounds uses `GL_CLAMP_TO_EDGE` on both axes. The native UV formula does not clip it; the GPU clamps out-of-range sampling to the edge of the allocated texture.

| Resolution | Outside allocated | Clamps to source-image border | Reaches zero-filled padding edge |
|---|---:|---:|---:|
| screen-med | 5 | 4 | **1** |
| screen-xlarge | 16 | 12 | **4** |

The distinction depends on the dimension of the overrun axis, not merely whether the image has padding somewhere:

- When the overrun axis has an exact power-of-two source dimension, the allocated edge is also the source image's edge.
- When the overrun axis has a smaller non-power-of-two source dimension, the allocated edge lies in the zero-filled padding.
- For a cut exceeding both axes, each axis is classified separately; if either clamp reaches padding, the overall sample category records that padding edge.

The single negative-Y rectangle per pack remains a separate source-geometry exception. Native UV arithmetic preserves its negative coordinate, and its clamp mode handles sampling; it is not silently rewritten.

These findings do **not** prove that the original cut rectangles were intentional. They explain the native sampling result without inventing clipping, texture pixels or repaired geometry.

## Implementation

Added `src/heman_tools/sprite_cut_padding_edge_audit.py`:

- includes a bounded reference helper that reproduces native decoded-row stride and zero-filled right/bottom padding;
- correlates private SpriteCut bounds with native S/T wrap codes and Stage195's un-clipped UV calculation;
- separates source-border samples from zero-filled-padding samples and reports per-axis overruns;
- keeps invalid/negative UVs distinct from rectangles extending beyond allocated dimensions;
- emits aggregate counts only and never extracts image pixels or exports resource keys, paths, offsets or per-record data.

Added 21 synthetic-only tests for RGB/RGBA row padding, exact power-of-two dimensions, memory limits, clamp/repeat behavior, negative UVs, paired aggregation and end-to-end fabricated two-resolution IPA audits.

Owner-private command:

```sh
PYTHONPATH=src python -m heman_tools.sprite_cut_padding_edge_audit \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --out local_reports/stage196_padding_edges.json
```

## Next step

Use the verified texture allocation, UV, color, easing, blend and mask contracts in a private multi-Symbol mesh reference. Keep draw order and native transforms intact, then compare a full composed frame against an authentic source render. This stage still does not claim full-game rendering or visual parity.
