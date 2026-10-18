# Stage 036 — actual raster pixels, not splash or frame counts

In the successful headless NeXium Actions run #39172231085, patched
upstream NeXium executed the guest and delivered 658 frames at 640x360.
The previous CI only counted frames; it did not check their pixels.

This stage records and validates actual guest framebuffer packet contents.

## Method

- tools/instrument_nexium_frames.py instruments the upstream Rust
  debug_boot.rs file only in a temporary pinned checkout.
- At guest frames 30, 120 and 300, the production runner saves frame_rx
  packet contents to PNG. No emulator GUI splash screenshot is used.
- tools/verify_nexium_guest_pngs.py requires 640x360 dimensions,
  a diverse color palette, and at least 100 magenta pixels of the
  source-authored player world-x HUD marker in rows 44–67.
- Without controller input the world-x marker must remain stable to
  within 4 pixels, while graphics should change visibly (at least
  90 pixels from frame 30 to frame 300) due to moving synthetic actors.
- CI retains three PNGs, the verification report, SHA256 values,
  and the execution logs as short-lived workflow artifacts.

A moving NeXium splash or a nonzero frame count alone cannot pass this
test. It requires unique geometry rendered by our actual guest.

## Boundaries

Passing validates rendered guest pixels from the patched runner, but
not user controller input, GUI display, audio, or fidelity to the
original iOS He-Man. The original IPA, Switch firmware and encrypted
keys are never published. DevkitPro NROs are left unchanged.
