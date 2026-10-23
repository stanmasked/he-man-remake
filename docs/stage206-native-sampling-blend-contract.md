# Stage206 — native texture sampling and blend-state contract

## Goal

Determine the source-confirmed texture filtering, wrap and blend behavior required by a future textured-quad renderer. The reverse-engineered executable and the owner's IPA remain local; this document records behavior, not disassembly bytes or resource identifiers.

## Corrected TextureData field map

The original loader's field offsets were rechecked against both TextureData::customLoad and Texture::loadTexture. The 13-byte scalar block is not a sequence of thirteen independent booleans:

| Scalar-block bytes | Native meaning | Values in the current IPA |
|---|---|---|
| 5 | PNGData RGB-by-alpha transform flag | 0 for all 1,645 records |
| 6–9 | signed little-endian 32-bit texture filter mode | 0 or 1 |
| 10 | S wrap selector | 0 or 1 |
| 11 | T wrap selector | 0 or 1 |
| 12 | image payload path selector | 0 for all 1,645 records; the loader takes its PNGData path |

The earlier Stage206 interpretation of byte 12 as the filter selector was incorrect. Byte 12 chooses the payload path; the actual filter mode is the 32-bit field at bytes 6–9. Stage211's first aggregate flag count likewise counted the 292 mode-1 filter records as if they were alpha-transform enablement. Stage212 corrects both mappings and retains only aggregate counts.

## Filter modes

| Filter mode | Native min/mag behavior | Mipmap generation | screen-med | screen-xlarge |
|---|---|---|---:|---:|
| 0 | GL_NEAREST / GL_NEAREST | disabled | 1,353 | 1,353 |
| 1 | GL_LINEAR / GL_LINEAR | disabled | 292 | 292 |
| 2 | loader mipmap path exists; current IPA does not use it | not observed in current IPA | 0 | 0 |

Both packs contain 1,645 indexed TextureData records. The repository indexes, WAD bytes, record identities and sampling metadata match exactly. This means the current source set includes 292 linear-filter textures; a nearest-only CPU oracle must not be presented as a complete renderer for authentic assets.

## Alpha-transform flag

The callback flag is scalar-block byte 5, not the filter-mode field. The loader registers the RGB-by-alpha row transform only when this byte is 1 and the decoded PNG row contains alpha. The original IPA has this flag disabled in all 1,645 records in each screen pack. The callback implementation remains relevant as a source-level contract, but the current TextureData census does not show any original texture enabling it.

## Wrap modes

| Per-axis wrap mode | screen-med | screen-xlarge |
|---|---:|---:|
| S: clamp-to-edge | 1,638 | 1,638 |
| S: repeat | 7 | 7 |
| T: clamp-to-edge | 1,632 | 1,632 |
| T: repeat | 13 | 13 |

The TextureData repository indexes and WAD bytes match across the two packs. No resource names, paths, byte offsets, source bytes or hashes are exported by the local census.

## Native blend state

- SpritePlayer initializes its default source factor to GL_ONE and destination factor to GL_ONE_MINUS_SRC_ALPHA.
- SpritePlayer paint enables blending while drawing the frame and disables it afterward.
- When the frame enables Symbol-specific blending and both Symbol factors are not the -1 sentinel, the native path applies that Symbol override. Otherwise it falls back to the current SpritePlayer blend factors, which may have been changed through the custom-blend setter.
- The renderer adapter must therefore carry a frame-level blend state and retain per-Symbol overrides; hardcoding the default as the only possible state would be incorrect.

## Implementation boundary

The native render-state contract now decodes the signed 32-bit filter mode at bytes 6–9, the alpha-transform flag at byte 5, and the payload selector at byte 12. The local census reports 1,353 nearest, 292 linear, zero mode-2, and zero enabled alpha-transform records per pack. It does not establish GPU submission, coordinate projection, scene placement, live blend overrides, animation timing or original-runtime pixel parity.
