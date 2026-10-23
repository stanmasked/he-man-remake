# Stage212 — correction of native TextureData scalar-field offsets

## Why this correction was required

The first Stage206/Stage211 aggregate pass assigned the filter-mode field and the alpha-transform flag to the wrong scalar-block positions. A direct trace through the original ARMv7 TextureData::customLoad and Texture::loadTexture corrected the mapping.

The 13-byte TextureData scalar block uses:

- byte 5 for the alpha-transform flag passed to the PNGData reader;
- bytes 6–9 as a signed little-endian 32-bit filter mode;
- bytes 10 and 11 for S/T wrap selectors;
- byte 12 for the PNG-versus-alternate payload path selector.

The final byte is not the filter mode. The 32-bit integer at bytes 6–9 is not the alpha-transform flag.

## Paired original-IPA audit

Both screen-med and screen-xlarge contain 1,645 indexed TextureData records. The corrected local census found, in each pack:

- filter mode 0 (nearest): 1,353;
- filter mode 1 (linear): 292;
- filter mode 2 (mipmap path): 0;
- alpha-transform flag enabled: 0;
- PNG payload selector: 1,645;
- paired TextureData repository index and WAD equality: exact.

Wrap counts are unchanged: S clamp/repeat = 1,638/7 and T clamp/repeat = 1,632/13 in each pack. Per-record metadata also matches across the two packs. The report exports only aggregate counts and booleans; original resource names, paths, offsets, bytes and hashes remain local.

## Code and test changes

- decode_texture_filter_mode now reads the signed 32-bit field at bytes 6–9 and accepts native mode codes 0, 1 or 2.
- decode_texture_alpha_transform_flag reads byte 5 and validates the boolean contract.
- decode_texture_payload_selector reads byte 12 separately.
- The aggregate census now reports filter-mode, alpha-flag and payload-selector counts independently.
- Added synthetic tests proving that changing byte 12 cannot change the filter mode, and that the alpha flag is independent of the filter mode.

The Python and C99 raster references still intentionally support nearest mode only. Stage213 will add linear sampling before authentic texture metadata can be fed through the CPU render path.
