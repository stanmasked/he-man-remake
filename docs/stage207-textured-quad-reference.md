# Stage207 — state-aware textured-quad CPU reference

## Goal

Turn Stage201's CPU packet list into a deterministic RGBA reference image while keeping native render-state and coordinate assumptions explicit. This is a CPU oracle for synthetic fixtures, not a Switch GPU backend.

## Contract

- Input is an ordered sequence of NativeFramePacket records. Packet XY already contains Symbol-local and caller-selected SpritePlayer transforms supplied to Stage201 assembly. The renderer never applies an implicit player transform.
- RasterProjection is mandatory and maps native XY to top-left-origin output pixel coordinates with an explicit affine matrix. No original game viewport, aspect ratio or camera transform is inferred.
- A non-negative texture-slot-to-TexturePixels mapping is supplied by the caller. Each packet must carry a resolved texture_slot; cut_handle identifies SpriteCut geometry and is not used as texture identity. Texture bytes are RGBA in the row order expected by native upload; row zero is addressed by normalized v=0. This stage does not decode PNGs, flip rows or alter source texels.
- Stage207 currently accepts filter mode 0 only: nearest sampling selects floor(u*width) and floor(v*height), then applies clamp-to-edge or modulo repeat independently on S and T. The corrected Stage212 census finds 292 mode-1 linear textures in the original IPA, so this nearest-only oracle is not yet sufficient for authentic texture integration; callers must fail closed for mode 1 until the linear sampler is implemented.
- Packets are blended in strictly increasing native source order. A packet's per-Symbol blend override takes precedence over explicit frame-level FrameBlendState; otherwise frame factors are used. Default factors are GL_ONE / GL_ONE_MINUS_SRC_ALPHA.
- The blend equation applies GLES glBlendFunc factors per RGBA channel and clamps/quantizes after each packet to model an RGBA8 target. Input texture RGB is not premultiplied a second time; Stage211 subsequently confirmed the source path: PNGData registers a per-row RGB-by-alpha transform only when the per-texture flag is enabled and the decoded row has an alpha channel. See [Stage211](stage211-native-png-alpha-contract.md). The CPU renderer still consumes already-prepared upload bytes; it does not perform PNG decoding or this transform itself.
- Invalid packet layout, missing textures, unsupported filters/factors, non-finite or unrepresentably large values, non-affine quads and sample-budget overflow fail closed before a result image is returned. Quad coverage uses a deterministic half-open affine rule; exact GLES triangle-edge ownership and face-culling state are not modeled.

## Synthetic verification

tests/test_textured_quad_reference.py covers normalized nearest sampling, independent S/T wrap modes, out-of-range UVs, premultiplied-alpha blending, per-Symbol and frame-level blend states, source ordering, explicit projection, malformed packets, missing resources and strict unsupported-state rejection.

## Evidence boundary

This stage supplies an asset-free software reference renderer only. It does not load the original IPA, prove PNG row orientation or premultiplication, infer live projection/player state, submit GPU commands, test the Switch framebuffer, or establish original-runtime pixel parity. Stage212 corrected the metadata offsets: the alpha-transform flag is byte 5 and filter mode is the signed 32-bit value at bytes 6–9. Linear sampling remains a required follow-up. Stage208 can compare this reference with a small native C99 implementation over shared synthetic vectors before connecting output to the Switch framebuffer path.
