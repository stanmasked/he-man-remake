# Stage221 — verified paired SpriteCut UV and allocated-texture geometry

## Original resource evidence (owner-private)

The original `He-Man-v2.0.0.ipa` (137,274,848 bytes) was checked against
the separately pinned Stage216 SHA-256 before examining indexed SpriteCut
records from both screen packs. This stage reuses the already documented
ARMv7 `SpriteCut::buildTextCoord` contract: signed 32-bit cut endpoints
are converted to binary32, then **divided by allocated texture dimensions**,
which are at least 4 pixels and rounded up to powers of two. They are *not*
divided directly by the PNG's unpadded IHDR dimensions.

The paired inventory contains **2,334** original cut-handle identities.
Every extra-large cut rectangle has all four integer fields exactly twice
the corresponding medium-resolution rectangle. But only **2,321** pairs
also have allocated texture dimensions exactly double. Exactly those
2,321 pairs have equivalent normalized native UV endpoints (absolute
difference at most 1e-7). In the remaining **13** pairs, normalized UVs
differ, and every mismatch coincides with a non-2x relationship between
allocated texture dimensions. Those differences cannot be resolved by
copying medium UVs to extra-large textures.

The complete per-pack bounds classification:

| Category | medium | extra-large |
|---|---:|---:|
| Cut fits raw PNG | 2,291 | 2,254 |
| Cut fits allocated surface only | 37 | 63 |
| Cut outside even allocated surface | 5 | 16 |
| Invalid original rectangle | 1 | 1 |
| Normalized UV endpoint outside [0,1] | 6 | 17 |

The cross-pack transitions include 26 cuts moving from inside-raw to
allocated-only and 11 from inside-raw to outside-allocated, with one
invalid cut present in both packs. All source wrap codes in these rows
are preserved, not guessed. Source index keys, per-cut coordinates,
texture IDs, and archive offsets remain in owner-only private reports.

## Public synthetic-only verification

`summarize_native_uv_resolution_pairs()` accepts bounded paired
rectangles, actual PNG dimensions, and per-axis wrap codes (0 for
clamp, 1 for repeat) supplied by an owner-local caller. It reuses the
existing native binary32 UV model and native padded allocation rule,
returning *only aggregate counts* and the classification of UV
mismatches. It preserves invalid/out-of-range source rectangles as
observations: it never clips the cut or synthesizes padding pixels.

Tests use deliberately invented cuts to cover raw and padded-only
bounds, UVs beyond allocated edges, native wrap, 2x cut coordinates
with **non-2x allocation**, malformed types, source-key privacy, and
large/invalid inputs.

## Correctness boundary

The current source-derived CPU reference does not reconstruct native
padding texels or an authentic iOS runtime camera. The observed
out-of-PNG and out-of-allocated records cannot be rendered as if
clipping were faithful to the iOS GPU. Different wrap modes further
change how an out-of-range UV samples texture pixels. This audit is a
**source-data/native-math parity check**, not a gameplay screen or
Nintendo Switch GPU parity certificate.

Next: connect explicit texture allocation dimensions, verified padding
behavior and sampler/wrap state to the actual Nintendo Switch texture
upload path; compare selected source sprite frames and original
iOS runtime captures before claiming end-to-end pixel parity.
