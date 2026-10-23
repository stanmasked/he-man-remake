# Stage219 — cross-resolution pixel agreement after the original-source CPU probe

## Why this stage

Stage218 confirmed that one authentic iOS Symbol animation pair has four
successful isolated CPU previews (east and west, medium and extra-large) and
exactly 2x cropped preview dimensions. That **does not imply** that simply
enlarging `screen-med` produces the high-resolution artwork from
`screen-xlarge`.

## Original-source owner-private findings

A privacy-preserving, pixel-by-pixel local comparison was performed between
each **authentic source CPU preview** from `screen-xlarge` and a naive nearest
neighbor 2x enlargement of the corresponding `screen-med` CPU preview.

In the selected original east and west frames, only about **60.26% of all
RGBA pixels** are exactly equal after the naive upscale. Restricting to pixels
visible in either image, about **11.73% of RGBA pixels** match exactly. Alpha
byte agreement is approximately **93.66%**. Values happen to be the same for
the two selected mirrored directions.

This is a comparison between **two reconstructed, source-derived CPU images**,
not between the remake and an actual iOS gameplay screenshot. Causes may
include differing original PNG details, filter behavior, transparent-channel
values and reference raster interpolation. This stage does not isolate those
causes or prove original GPU output.

The complete original-source aggregate report is kept in owner-only Google
Drive under `03_Aggregate_Reports/Stage218_original_frame_probe/`. The
source preview PNGs and private alias selectors remain in
`02_Raw_Traces_and_Captures/Stage218_original_frame_probe/`. Do not publish
the original pixels, resource identifiers, offsets or private digests in
GitHub.

## Public asset-free regression model

`heman_tools.cpu_resolution_pixel_comparator.compare_naive_twofold_resolution_rgba`
accepts two raw RGBA byte buffers with integer dimensions. It requires
exactly 2x dimensions along both axes, bounded pixel count and full RGBA byte
lengths, and computes exact RGBA matches, visible-union matches, matching
alpha bytes and total channel error. It returns only aggregate metrics;
`to_public_safe_summary()` explicitly sets original iOS runtime and GPU
parity flags to false. Synthetic tests cover 100% agreement, incorrect color
and alpha, fully transparent frames, coordinate indexing and malformed/large
buffers.

For this isolated source sequence, relying on a resized medium-resolution
PNG as a substitute for the original extra-large artwork would conceal
material differences. Preserve the actual original resolution pack rather
than assuming its pixels are reproduced by interpolation.

## Still required

An authenticated original iOS runtime frame with known animation state,
viewport/camera and player-wide transforms is required for true game-frame
parity. Comparing two source-resolution CPU reconstructions is not that
oracle, even if their geometry and alpha masks are similar.
