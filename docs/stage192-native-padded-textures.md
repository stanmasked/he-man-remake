# Stage192 — native padded texture extents and SpriteCut UV denominators

Stage192 resolves **most**, but not all, of the raw-PNG bounds exceptions from Stage191 using evidence from the original iOS ARMv7 executable. The owner's IPA and all disassembly remain private; only aggregate findings and an independently testable model are committed.

## Native load path, confirmed

Read-only analysis of the original compiled methods establishes:

1. `PNGData::pngInfoCallback` calls `png_get_IHDR` and stores the source width and height as the **actual** dimensions.
2. The callback independently initializes both allocated dimensions to **4** and doubles each one until it is at least the corresponding actual dimension. This is a per-axis next-power-of-two rule with minimum 4.
3. `PNGData::getActualWidth/Height` and `PNGData::getImageWidth/Height` read **different fields**.
4. `Texture::loadTexture` copies the actual dimensions to its unpadded width/height fields, while it copies the PNGData image (allocated) dimensions to its regular width/height fields.
5. `Texture::getUnpaddedWidth/Height` and `Texture::getWidth/Height` are separate accessors.
6. `SpriteCut::buildTextCoord` divides cut coordinates by `Texture::getWidth/Height`, **not** by the unpadded dimensions.

Therefore, using raw PNG IHDR dimensions as the UV denominator was incorrect for non-power-of-two images. The model now uses exactly the native allocation rule, without guessing a padding amount.

## Original-data result

On the same 2,334 private SpriteCut rectangles in each pack:

| Allocation-relative category | screen-med | screen-xlarge |
|---|---:|---:|
| Inside both PNG and allocated texture | 2,291 | 2,254 |
| Outside raw PNG but inside allocated texture | **37** | **63** |
| Outside even the allocated texture | **5** | **16** |
| Invalid rectangle (negative Y) | 1 | 1 |
| **Total** | **2,334** | **2,334** |

Paired across identical private cut identities:

- 2,254 inside raw bounds in both packs.
- 37 fit only padded bounds in both packs.
- 26 fit raw bounds in medium but only padded bounds in xlarge.
- 11 fit raw bounds in medium but exceed even allocated xlarge bounds.
- 5 exceed allocated bounds in both packs.
- 1 has invalid negative-Y geometry in both packs.

**Interpretation:** power-of-two allocation explains 37/42 medium and 63/79 xlarge originally out-of-raw-bounds rectangles. It does not explain every case. The 5 and 16 residual overflows, and one negative-Y tuple per pack, remain explicit exceptions; nothing is silently clipped or repaired. Padding **pixels** are not inferred from this dimension audit.

## Implementation

`src/heman_tools/sprite_cut_runtime_texture_bounds.py`:

- reproduces the native per-axis minimum-4 next-power-of-two allocation;
- distinguishes `inside_raw`, `inside_allocated_only`, `outside_allocated`, and `invalid`;
- returns normalized UV endpoints only when a cut lies inside the known allocated extents, using the allocated denominator;
- produces aggregate-only paired-pack reports and no labels, private offsets, per-record values or graphics;
- refuses to calculate UVs for a cut outside allocated extents or an invalid cut.

Stage191's private index loader is factored into an in-memory helper so Stage192 can reuse exactly the same strict repository/WAD/ImageData parsing without duplicate source-asset logic.

15 synthetic-only regression tests validate power-of-two edges, native UV normalization, missing/invalid geometry, cross-pack categories, fail-closed behavior and report redaction. The existing Stage191 synthetic paired-IPA integration tests remain applicable.

Owner-private command:

```sh
PYTHONPATH=src python -m heman_tools.sprite_cut_runtime_texture_bounds \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --out local_reports/stage192_native_texture_bounds.json
```

## Remaining proof gates

- Determine whether the residual 5/16 overflows are intentional effects, malformed cut definitions or use another texture transform/wrap mode. No default action is assumed.
- Interpret the first four Symbol float fields and remaining scalar tail before composing multi-symbol frames.
- Test the eventual GPU UV mapping against a genuine source-game render, not merely the synthetic NeXium probe. The original iOS gameplay and full visual parity remain unverified.
