# Minimal NeXium guest isolation (Stage 032)

The earlier NeXium raster smoke workflow gave a false-positive result:
the screenshots were an animated **NeXium loading splash**, not the
synthetic He-Man guest framebuffer. See [Issue #30](https://github.com/stanmasked/he-man-remake/issues/30).

This experiment builds **an entirely separate libnx NRO** with no
He-Man engine, collision system, file assets, original iOS material,
game keys, or external firmware.

`switch_minimal/heman_minimal_guest_probe.nro` performs only:

1. Create a 640x360 RGBA8888 framebuffer using libnx.
2. Draw a contrasting checkerboard background.
3. Draw a fixed 110x100 magenta rectangle.
4. Change the rectangle's x-coordinate only when the D-pad Right or
   Left button is held.
5. Exit on Plus.

The `Isolated minimal libnx guest NeXium probe` workflow tests the
same program on the nightly emulator under Xvfb + Lavapipe and uploads
screenshots and logs. It requires **thousands of solid magenta pixels**
in the window and a stable marker without input. The actual Right-key
test must move the marker. An animated emulator splash cannot meet
this requirement.

## Interpreting results

- **Pass:** minimal libnx framebuffer and basic controller input work
  in the CI NeXium environment. Investigate the full raster game's
  pre-framebuffer self-checks, memory use, and services separately.
- **Screenshot failure / loading splash:** the problem also happens
  without the He-Man game engine. Investigate NeXium guest startup,
  headless graphics, application loading, and environment before
  changing game logic.
- **No screenshot / runtime crash:** inspect captured `nexium.log` and
  the runner failure; this alone does not diagnose root cause.

Passing the minimalist test would NOT by itself establish that the
actual He-Man raster NRO boots or functions correctly.
