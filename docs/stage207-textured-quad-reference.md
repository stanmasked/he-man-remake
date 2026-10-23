# Stage207 — state-aware textured-quad CPU reference

## Goal

Turn Stage201's CPU packet list into a deterministic RGBA reference image while keeping native render-state and coordinate assumptions explicit. This is a CPU oracle for synthetic fixtures, not a Switch GPU backend.

## Contract

- Input is an ordered sequence of NativeFramePacket records. Packet XY already contains Symbol-local and caller-selected SpritePlayer transforms supplied to Stage201 assembly. The renderer never applies an implicit player transform.
- RasterProjection is mandatory and maps native XY to top-left-origin output pixel coordinates with an explicit affine matrix. No original game viewport, aspect ratio or camera transform is inferred.
- A cut-handle-to-TexturePixels mapping is supplied by the caller. Texture bytes are RGBA in the row order expected by native upload; row zero is addressed by normalized v=0. This stage does not decode PNGs, flip rows or alter source texels.
- Only filter selector 0 is accepted: nearest sampling selects floor(u*width) and floor(v*height), then applies clamp-to-edge or modulo repeat independently on S and T. Out-of-range UVs are preserved and sampled through the selected wrap mode.
- Packets are blended in strictly increasing native source order. A packet's per-Symbol blend override takes precedence over explicit frame-level FrameBlendState; otherwise frame factors are used. Default factors are GL_ONE / GL_ONE_MINUS_SRC_ALPHA.
- The blend equation applies GLES glBlendFunc factors per RGBA channel and clamps/quantizes after each packet to model an RGBA8 target. Input texture RGB is not premultiplied a second time; the actual decoded/uploaded alpha representation still needs separate source-path confirmation before visual-parity claims.
- Invalid packet layout, missing textures, unsupported filters/factors, non-finite values, non-affine quads and sample-budget overflow fail closed before a result image is returned.

## Synthetic verification

tests/test_textured_quad_reference.py covers normalized nearest sampling, independent S/T wrap modes, out-of-range UVs, premultiplied-alpha blending, per-Symbol and frame-level blend states, source ordering, explicit projection, malformed packets, missing resources and strict unsupported-state rejection.

## Evidence boundary

This stage supplies an asset-free software reference renderer only. It does not load the original IPA, prove PNG row orientation or premultiplication, infer live projection/player state, submit GPU commands, test the Switch framebuffer, or establish original-runtime pixel parity. Stage208 can compare this reference with a small native C99 implementation over shared synthetic vectors before connecting output to the Switch framebuffer path.
