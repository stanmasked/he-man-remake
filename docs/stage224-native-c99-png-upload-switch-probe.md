# Stage224 — portable native PNG upload and Switch framebuffer probe

## Objective

Carry Stage223's source-audited PNG zero-fill behavior into a **real C99**
texture preparation routine, then compare its outputs with the Python
reference and exercise the same routine inside a Nintendo Switch homebrew
probe. Source of evidence: the original iOS ARMv7 PNG callbacks examined in
Stage223, not an inferred graphics-library default.

## Implementation

`native/src/heman_native_png_upload.c` prepares an explicitly provided,
already-decoded and already-alpha-transformed PNG RGBA buffer for the
allocated native min-four/next-power-of-two texture surface. It writes
each visible PNG row at its true allocated row stride and zero-fills all
right/bottom space. Native three-channel RGB maps to sampled opaque black
padding; four-channel RGBA maps to transparent black padding. Source
alpha, wrap/filter modes and texture-slot identity are strictly validated.

The function returns a `hm_texture_reference_binding` consumed **directly
by the existing C99 textured-quad CPU renderer**. The 64 MiB texture limit
and supported wrap/filter boundaries match the prior Stage222 gate. Invalid
inputs, insufficient capacity or allocation failure leave output bytes and
binding untouched: a bounded temporary buffer is committed only on
success, including when source and destination overlap.

There are two independent test layers:
1. `native/tests/test_native_png_upload.c` runs under GCC and Clang,
   validating RGB/RGBA right/bottom zero pads, minimum-four, direct
   power-of-two/overlapping storage, invalid argument rollback and the
   same C99 textured-quad sampling result.
2. `tests/test_c99_native_png_padding_parity.py` compiles the real native
   C99 module and compares its complete output buffer byte-for-byte to
   `native_png_zero_padding.reconstruct_native_zero_padded_texture`
   over invented sizes and alpha/wrap/filter combinations. This exposes
   differences in row stride and alpha treatment without any IPA in CI.

## Separate Switch test

`make -C switch_raster clean all TEXTURE_PROBE=1 PNG_PADDING_PROBE=1`
creates `heman_png_padding_probe.nro`, separate from the normal raster
prototype and the Stage209 checker. The opt-in guest runs the exact
portable C99 uploader on a synthetic RGB image, submits its resulting
allocated texture to the C99 reference renderer, verifies the expected
4x4 pixels, then paints a visible **synthetic 64x64 panel** into the
ordinary 640x360 libnx software framebuffer. A dedicated public Actions
workflow cross-compiles the AArch64 ELF/NRO using devkitPro, validates
the ELF architecture and NRO0 header, and preserves the NRO artifact.

The guest uses libnx's **software framebuffer**, NOT a native deko3d
texture upload or GPU shader. An NRO build alone is not a successful
emulator or physical Switch launch. No original image, IPA or commercial
code is included in this NRO or any public CI job.

## Still unverified

- GPU texture-format/channel/layout and sampler equivalence in actual
  Switch hardware or NeXium GPU traces
- Source iOS GL driver filtering, upload orientation and screen output
- Source SpritePlayer transform, camera and timestamp-aligned gameplay
  pixel parity

Next: run the Stage224 opt-in guest in NeXium, verify actual guest pixels
and controller-independent rendering, and only then research a proper
deko3d GPU upload path. Do not confuse the software framebuffer with GPU
texture sampling.
