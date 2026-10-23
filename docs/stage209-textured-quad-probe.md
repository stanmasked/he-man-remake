# Stage209 — synthetic Switch textured-quad probe

## Purpose

Run the Stage208 portable C99 reference in a standalone devkitPro/libnx NRO, then validate its output from actual NeXium guest framebuffer captures. This is an isolated CPU-reference integration test, not a GPU texture-upload implementation.

## Guest contract

- A newly authored 8×4 RGBA texture uses four opaque colors in a repeating 2×2 checker pattern.
- One explicit source-ordered frame packet is paired with texture slot 23 while its SpriteCut handle is 9001, guarding against accidental use of the handle as texture identity.
- The packet is projected explicitly to a 256×128 rectangle at (128,64) in a 640×360 top-left-origin RGBA framebuffer.
- The NRO checks 32 interior texel-center samples, three background samples, one covered packet and exactly 32,768 sampled pixels before opening the framebuffer.
- The guest writes the generated RGBA image row-by-row using the actual libnx framebuffer stride. It contains no original IPA resources.

## NeXium evidence

The patched-NeXium workflow builds the dedicated `heman_texture_probe.nro`, captures frames 30, 120 and 300 from the guest `frame_rx` path, and validates exact expected colors at all 32 texel centers plus untouched background points in each frame. It records the NRO and PNG hashes and guest CPU/SVC progress.

## Limitations

This verifies the C99 CPU reference and Switch framebuffer path in NeXium. It does not test GLES/GPU texture upload, authentic original-game projection, original pixel parity, or physical hardware. CI evidence is pending until the workflow completes successfully.
