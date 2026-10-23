# Stage220 — complete owner-original cross-resolution PNG texture census

## Goal and provenance

Stage219 showed that naive 2x enlargement of one isolated medium
source-derived CPU sprite frame is not pixel-equivalent to the matching
extra-large source-derived CPU frame. Stage220 checks **all original PNG
texture paths** in both Stage216 owner-private archive packs rather than
extrapolating from one frame.

Original archives were independently anchored to the Stage216 stored
SHA-256 identities and each complete ZIP passed CRC verification.
The per-resource file paths, source images, image hashes and pixel-level
comparisons remain **owner-private**, not GitHub Actions artifacts.

## Original IPA source census — completed 2026-10-24

* Both screen packs contain 1,644 PNG texture records with exactly matching
  relative resource paths; 1,644 PNG pairs were individually decoded with
  Pillow. No unmatched PNG paths were observed.
* 1,563 pairs have high-resolution dimensions of exactly 2x both axes.
  **81 pairs do not**: including 25 pairs with extra-large width one pixel
  less than exact doubling and 24 pairs with extra-large height one pixel
  more. The remaining exceptions are not all small rounding differences;
  arbitrary 2x assumptions are unsound.
* Within the 1,563 exact-dimension pairs, 16 are exactly pixel-identical
  after nearest-neighbor enlargement of the medium RGBA source.
  The other 1,547 have pixel differences.
* Across 106,490,684 compared pixels, the exact RGBA agreement fraction
  is **0.418062**, visible-union exact RGBA agreement **0.326875**,
  and alpha-byte agreement **0.923504**.
* Source decoded image modes vary: RGBA, RGB and palette-encoded textures
  occur, with some pairs differing in native mode. The comparison normalized
  both images to RGBA before evaluating equality.

These are *weighted source-image comparison metrics*, not the pixel
agreement fraction of a rendered gameplay frame. Different image detail,
fully transparent RGB channel values, source modes, filtering and
rasterization must be investigated separately before attributing causality.

Private owner-only evidence:

* Detailed path-indexed original texture census (private, 936,027 bytes):
  `02_Raw_Traces_and_Captures/Stage220_original_texture_census/`
  `private-original-texture-census.json`
* Aggregate-only report (4,145 bytes):
  `03_Aggregate_Reports/Stage220_original_texture_census/`
  `stage220-aggregate-texture-census.json`

Both were uploaded to Google Drive and fetched back independently.
Downloaded SHA-256 digests match the local source copies. The detailed
record is **not public-safe**; do not copy its contents to a pull request.

## Public reproducible gate

`paired_source_texture_contract.summarize_texture_resolution_pairs()`
summarizes strictly bounded, anonymized pair metrics: dimensions, explicit
2x exceptions, matched/different pixel texture counts and weighted RGBA,
visible-union and alpha agreement. It refuses impossible pixel counts
or an alignment claim for a texture whose dimensions are not exactly 2x.
It never serializes texture names, paths or actual pixel buffers, and
always reports original iOS runtime pixel parity as false.

The public CI tests invented records only. They validate a mixed
2x/non-2x inventory, weighted metrics, ordering invariance, transparent
pixel edge cases, malformed counts and safe non-disclosure.

## Engineering consequence

Do not replace the original extra-large PNG pack with naive resized
medium assets. A resolution-aware loader must use the actual asset for
the requested screen pack, check the actual texture dimensions, and
validate SpriteCut UVs against that concrete texture. Source texture
mismatch **does not** establish native GPU sampling or whole-game pixel
parity. An original runtime capture and associated camera/animation
state remain necessary for that.
