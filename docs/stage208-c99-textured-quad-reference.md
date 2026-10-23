# Stage208 — portable C99 textured-quad reference

## Goal

Implement the Stage207 CPU reference contract in portable C99 so synthetic pixel vectors can be exercised under GCC and Clang before Switch integration.

## Contract

- Consumes Stage201 frame packets wrapped with an explicit texture slot. A slot-to-RGBA binding table is caller-owned; cut_handle identifies SpriteCut geometry and is not texture identity.
- Uses explicit affine projection, top-left-origin RGBA output, nearest normalized sampling, independent S/T clamp-or-repeat, source-order blending, frame-level factors and per-Symbol overrides. This reference currently supports only filter mode 0; Stage212 found 292 mode-1 linear textures in the original IPA, so linear sampling must be added before this oracle can render the complete authentic texture set.
- Preserves texture bytes as supplied. Default blend is GL_ONE / GL_ONE_MINUS_SRC_ALPHA. No extra RGB premultiplication, row flip, hidden player transform or inferred camera is applied.
- Validates packets, texture descriptors, state and work bounds before committing output. On error, destination pixels, row padding and result counters remain unchanged.
- Uses deterministic half-open affine coverage. It does not claim exact GLES edge coverage, culling, upload orientation or original-runtime pixel parity.

## Synthetic validation

The C99 suite covers nearest sampling, negative-UV repeat, RGBA8 row-padding preservation, default premultiplied-alpha blending, per-Symbol override, explicit projection, missing texture slot and transactional failure. native/run_tests.sh compiles the same source under strict C99 with GCC and Clang. These synthetic tests do not yet cover linear sampling.
