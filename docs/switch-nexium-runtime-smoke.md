# NeXium experimental raster NRO runtime smoke test

This workflow takes the **newly built, independently authored synthetic
He-Man raster NRO** and tries to launch it in NeXium on a Linux CI worker.
The original iOS IPA is not involved, nor are original game graphics,
decrypted Switch firmware, title keys or external copyrighted assets.

Workflow file: `.github/workflows/switch-raster-nexium.yml`.

## What the workflow actually proves when green

1. The devkitPro build produced an AArch64 `.nro` with an NRO0 header.
2. The NeXium process stayed alive long enough to capture a window.
3. A screenshot of that emulator window had a sufficiently varied color
   palette to be consistent with the independent graphical probe.
4. Holding the emulated Right control changed at least 600 gameplay-area
   pixels between two captured frames.
5. The run uploaded `before.png`, `after-right.png`,
   `nexium.log`, `visual-check.txt` and the precise NRO SHA256 under
   `heman-nexium-raster-runtime-evidence`.

A green CI job is stronger evidence than a cross-compiled NRO alone,
but it does **not** establish authentic iOS He-Man behaviour, hardware
performance, correct button mapping for every controller, or original
graphics/audio parity. The first successful captured frames need manual
inspection to rule out surprising emulator/window artifacts.

## Failure interpretations

- Cannot download nightly: external service or asset availability, not
  necessarily a game code failure.
- No emulator window or immediate exit: potential emulator/runtime
  dependency, NRO boot or application initialization failure. Inspect
  `nexium.log` and runner logs.
- Screenshots exist but palette test fails: the synthetic framebuffer
  may not be displaying, or the emulator may be showing only its UI.
- Palette exists but the Right-key delta is too small: the keyboard
  mapping or input focus may differ, or movement may be broken. The
  report alone cannot distinguish these cases.

All screenshots are transient GitHub Actions artifacts, not original
assets. This test does not use local user-specific keys, devices or IPA.

## Stage 031: direct controller movement evidence

After a successful initial NeXium smoke test, a separate regression adds
a bright magenta rectangle to the **fixed HUD**. Its horizontal position
comes exclusively from the player's world-space x coordinate, not the
camera, moving scenery, enemies, or the QA fingerprint.

The workflow now captures three screenshots: `before.png`,
`idle.png` (after a period without any keys) and
`after-right.png` (after holding Right). The separate
`player-input-check.txt` report checks:

- the magenta marker can be located in all three frames;
- it drifts no more than 10 screen pixels while no input is applied;
- after Right is held, its centroid moves right at least 30 pixels.

A failure cannot automatically distinguish controller mapping, window
focus or guest gameplay bugs; it retains screenshot and emulator logs
for diagnosis. This specifically strengthens the evidence of
**directional input being handled**, without asserting fidelity to the
original iOS game.
