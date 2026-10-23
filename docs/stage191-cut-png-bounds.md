# Stage191 — paired original SpriteCut rectangles versus PNG IHDR

Stage191 makes the unresolved raw-PNG bounds finding from Stage185 reproducible. A private read-only scan of the owner-held iOS v2.0.0 IPA evaluates all 2,334 indexed SpriteCut rectangles in both resolution packs, follows the exact SpriteCut → TextureData → ImageData resource chain, and compares each rectangle against its source PNG IHDR dimensions.

## New owner-private findings

| Category | screen-med | screen-xlarge |
|---|---:|---:|
| Rectangles wholly inside raw PNG dimensions | 2,291 | 2,254 |
| Nonempty rectangles beyond raw PNG dimensions | 42 | 79 |
| Rectangles with invalid signed coordinates or dimensions | 1 | 1 |
| **Total indexed rectangles** | **2,334** | **2,334** |

The previous Stage185 totals of 43 and 80 source rectangles that could not be safely cropped against their raw PNG bounds comprised the outside cases **plus one invalid rectangle in each pack**. Distinguishing these cases prevents a single malformed tuple from being misdiagnosed as a texture-padding problem.

**Cross-pack comparison (same private record/handle, no labels exported):**

- 2,254 rectangles are inside both packs.
- 42 are beyond PNG IHDR bounds in both packs.
- 37 are inside screen-med yet outside screen-xlarge.
- One geometry-invalid tuple occurs in both packs.

**Magnitude of overflow (maximum of horizontal and vertical excess):**

| Overflow extent | screen-med | screen-xlarge |
|---|---:|---:|
| Exactly one pixel | 34 | 53 |
| Two or three pixels | 1 | 6 |
| Four to sixteen pixels | 6 | 6 |
| More than sixteen pixels | 1 | 14 |
| **Total outside** | **42** | **79** |

These data reject a blanket 1-pixel padding assumption: both packs contain substantially larger mismatches. The PNG IHDR is not necessarily the runtime texture allocation size. A PNG-bound failure **does not prove** the native iOS renderer clips the cut, and an inside-PNG result does not establish visual equivalence.

## Implemented audit

Added `src/heman_tools/sprite_cut_png_bounds_census.py`:

- Reads only bounded indexed cut/texture/image metadata and the 33-byte PNG signature/IHDR with checked CRC, without extracting PNG image pixels.
- Resolves uniquely matching archive member paths; rejects duplicate or ambiguous case-insensitive entries, unsafe symlinks, and malformed resource links.
- Requires the resource indexes and cut identities to agree between medium and extra-large screen packs.
- Classifies cuts as `inside`, `outside`, or `invalid`; counts axis and magnitude of overruns and cross-pack transitions without exporting resource names, keys, original bytes, offsets, or per-record values.
- Never clips, pads, repairs, normalizes UVs, or renders any out-of-bounds or invalid cut. Runtime texture dimensions and potential padding still need separate native evidence.

Run privately (do not commit the IPA or local report):

```sh
PYTHONPATH=src python -m heman_tools.sprite_cut_png_bounds_census \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --out local_reports/stage191_cut_png_bounds.json
```

Added 12 asset-free synthetic unit tests for exact-edge rectangles, one-pixel and large overflows, malformed dimensions, booleans, cross-pack classification, redacted reports, mismatched keys, valid PNG IHDR, and CRC tampering.

## Next evidence gates

1. Trace the original texture construction path to learn whether native GL image dimensions, allocation dimensions, and SpriteCut normalized UV denominators differ.
2. Keep one-pixel and large mismatches in separate categories until independently explained. Do not infer power-of-two expansion or silently crop.
3. Only after runtime texture dimensions and remaining Symbol float fields are resolved, assemble a multi-symbol frame using verified transform order.
4. Validate an original full frame privately against reliable source footage or an actual iOS runtime capture. A successful synthetic NRO in NeXium does not establish source-game visual parity.
