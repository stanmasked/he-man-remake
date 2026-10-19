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

## Diagnosis of the first live failure

First real patched-NeXium input run
[#39176583738](https://github.com/stanmasked/he-man-remake/actions/runs/39176583738)
successfully executed the 640x360 synthetic guest and recorded the
A-button press at frame 45 and release at frame 58. The three saved
guest PNGs showed that the unique height marker **really did move**:

| Guest frame | Marker range in screen Y (pixels) | Meaning |
| --- | --- | --- |
| 30 | 298–306 | Ground |
| 65 | 228–236 | Jump in progress, 70 pixels higher |
| 120 | 298–306 | Returned to ground |

The initial verifier rejected the frame because it expected a
`cyan RGB(0,255,255)` marker, while the source had mistakenly used
C RGBA8888 word `0xff00ffff`, which becomes **yellow** when stored as
little-endian RGBA bytes. The corrected word `0xffffff00` produces
true cyan bytes `00 ff ff ff`. The C renderer and its native tests are
both corrected, and `tests/test_native_rgba_markers.py` locks down
the actual RGBA byte meaning so this error cannot recur unnoticed.

This was a **marker color mismatch**, not evidence of broken jump
physics or failed NeXium A-button delivery. Nevertheless, the stage
will only be merged once the corrected end-to-end CI validates the
real cyan PNGs and the full jump/landing scenario.
