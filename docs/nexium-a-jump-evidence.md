# Stage 038 — verify actual guest A-button jump and landing

The synthetic Nintendo Switch game in `switch_raster` already includes
jump physics. Its camera tracks the player vertically, so a screenshot
of the hero's **screen** Y coordinate is not sufficient to prove jump
input affected the actual world simulation.

This stage adds a fixed cyan HUD ruler whose marker is computed only
from the player's **world-space foot Y**. It is independent of the
camera, autonomous enemy, background and NeXium GUI.

## Experiment

The isolated NeXium CI workflow
`.github/workflows/nexium-patched-jump.yml` uses the pinned upstream
NeXium's built-in `NEXIUM_HID_INJECT` mechanism, not a game-state
override. The only input is a simulated Nintendo Switch **A button**.

- Capture guest frame 30 at the normal grounded Y position.
- Inject `buttons=A` at received guest frame 45.
- Release the button at frame 58 using `buttons=`.
- Capture frame 65 near the apex of the jump and frame 120 after landing.
- Verify the cyan marker rose by at least 20 pixels by frame 65 and
  returned within 5 pixels of the original Y by frame 120.
- Require horizontal magenta player-x position to stay within 5 pixels
  throughout, and verify a real cyan HUD pixel difference.
- Check actual NeXium logs for both scheduled A press and release.

The C99 raster host regression separately verifies the cyan marker
tracks world-foot-Y and is reversible while live gameplay logic remains
unchanged. Synthetic instrumentation gets Python unit coverage.

Passing would prove the emulated Switch A-button reached our source-only
jump gameplay and a complete ballistic jump/landing was seen in real
guest framebuffer pixels. It would **not** yet establish performance on
physical hardware, original iOS gameplay/art/sound reproduction,
controller compatibility outside the emulated injected control, or
production readiness.

The original user-owned IPA, proprietary game assets, keys and firmware
remain outside the public GitHub repository.
