# Stage222 — fail-closed native texture upload readiness

## Correction identified after Stage221

Stage221 established that original SpriteCut UV coordinates are normalized
against the native allocated width and height, not raw PNG dimensions.
The earlier owner-local CPU preview passed the original PNG width/height
directly to its CPU sampler. For non-power-of-two PNGs, this makes the
sampler's coordinate denominator inconsistent with the source UV geometry.
Consequently, earlier Stage218/219 source-derived cropped CPU previews
cannot be treated as evidence of native texture sampling parity whenever
their sampled texture needed padding. Their archival source-data provenance
is intact, but full CPU pixel parity must be **re-evaluated** for any frame
whose texture bindings used padded allocations.

**Independent original-source check:** the four Stage218 selected east/west
views from both packs were re-decoded from the pinned owner-only IPA.
All **8 of 8 actual source frame texture bindings** (two per frame)
had raw PNG dimensions exactly equal to the native allocated dimensions,
with nearest sampling and clamp-to-edge in both axes. Therefore the specific
Stage218/219 selected CPU frames are **not affected by this missing-padding
error**. This does not establish camera placement or original iOS runtime
screen parity. A private aggregate report records the four preflights
without exporting the source sequence selector or texture identities. Stage220's comparison of standalone original
PNG source files is not affected by the CPU sampler denominator.

In the owner-private Stage221 original-source inventory, 1,296 medium
cut bindings and 1,293 extra-large cut bindings refer to PNGs whose
allocated dimensions differ from the raw PNG. These are cut **bindings**,
not necessarily unique textures. They cannot be assumed equivalent to
uploading raw PNG bytes in a row-major `TexturePixels` sampler.

## Public implementation

`native_texture_upload_gate.py` now validates the original
minimum-four/next-power-of-two allocation, known S/T clamp/repeat selectors,
known nearest/linear CPU filters and the bounded 64-MiB allocation budget.

`prepare_native_cpu_texture` returns a `TexturePixels` binding only when:
- the raw PNG occupies the entire native allocated surface, with validated
  RGBA byte length, **or**
- a complete allocated RGBA buffer is explicitly supplied, with the original
  visible PNG rows proven byte-identical in their correct upload-row slots.

The second case permits independent synthetic experiments with supplied
padding, but **does not authenticate** padding bytes as original iOS game
content. Unknown original padding is never filled with zeros, extended by
edge-copy, clipped or silently ignored. Unsupported mipmap filters fail
closed.

The private source CPU-preview path now enforces this guard by default.
For a padded original PNG, it fails with a specific missing-native-padding
error rather than producing a misleading preview using wrong dimensions.
No original resource or original source selector has been committed to the
public repository.

## Tests

Asset-free tests validate direct power-of-two uploads, minimum-four
allocations, explicit full-surface buffers, visible-row consistency,
missing/wrong-size padding, wrapped and filtered samplers, malformed
dimensions, memory caps and falsified allocation metadata.

These tests run under the repository's existing Python and native CI.
They exercise a **CPU reference** and not the Nintendo Switch GPU upload
path; no DKSH shader or GX2 GPU test is implied.

## Pending original/native evidence

1. Inspect the actual original iOS texture allocation and upload path,
   especially what initializes the right/bottom padded rows and any
   image-mode, stride, orientation and alpha transformations.
2. Add an independently verified full allocated texture buffer, native
   texture sampler and a traceable CPU rendering reference for at least
   one original frame.
3. Only then compare the authentic, timestamp-aligned original iOS
   gameplay frame, SpritePlayer/camera position and Switch output.
   A passing synthetic CI never establishes original runtime pixel parity.
