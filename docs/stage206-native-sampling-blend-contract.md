# Stage206 — native texture sampling and blend-state contract

## Goal

Determine the source-confirmed texture filtering, wrap and blend behavior required by a future textured-quad renderer. The reverse-engineered executable and the owner's IPA remain local; this document records behavior, not disassembly bytes or resource identifiers.

## Texture filter selector

The serialized TextureData record contains a 13-byte scalar block. Its final byte is a boolean filter selector consumed by the native TextureDefinition/texture loader path.

| Serialized selector | Native min filter | Native mag filter | Mipmaps |
|---|---|---|---|
| 0 | GL_NEAREST | GL_NEAREST | disabled |
| 1 | GL_LINEAR | GL_LINEAR | disabled |

The loader also contains a mode-2 path (GL_LINEAR_MIPMAP_NEAREST minification with GL_LINEAR magnification and mipmap generation), but that value is not representable by the serialized boolean field used by TextureData. A global force-nearest gate is modeled explicitly by the reference contract rather than inferred from live runtime state.

## Full original-IPA census — 23 October 2026

Both screen packs contain 1,645 indexed TextureData records. Every record has filter selector 0, so the original resource metadata selects nearest minification and magnification with mipmap generation disabled.

| Per-axis wrap mode | screen-med | screen-xlarge |
|---|---:|---:|
| S: clamp-to-edge | 1,638 | 1,638 |
| S: repeat | 7 | 7 |
| T: clamp-to-edge | 1,632 | 1,632 |
| T: repeat | 13 | 13 |

The TextureData repository indexes and WAD bytes match across the two packs. The local census also verified that all filter selector values are boolean and that the wrap-mode distributions match. The aggregate report does not include texture names, paths, offsets, source bytes or hashes.

## Native blend state

- SpritePlayer initializes its default source factor to GL_ONE and destination factor to GL_ONE_MINUS_SRC_ALPHA, i.e. premultiplied-alpha blending.
- SpritePlayer paint enables blending while drawing the frame and disables it afterward.
- When the frame enables Symbol-specific blending and both Symbol factors are not the `-1` sentinel, the native path applies that Symbol override. Otherwise it falls back to the current SpritePlayer blend factors, which may have been changed through the custom-blend setter.
- The renderer adapter must therefore carry a frame-level blend state and retain per-Symbol overrides; hardcoding the default as the only possible state would be incorrect.

## Implementation boundary

`native_render_state_contract.py` provides an asset-free, tested mapping from serialized filter selectors to native sampling state. Stage205 now compares the filter selectors in both packs alongside resource identity, wrap modes, normalized UVs and CPU geometry.

This closes the sampling-state discovery gate for the current original IPA. It does not establish GPU submission, coordinate projection, scene placement, live blend overrides, animation timing or original-runtime pixel parity. Stage207 will use this contract to build a synthetic-tested textured-quad reference renderer before connecting it to the Switch framebuffer path.
