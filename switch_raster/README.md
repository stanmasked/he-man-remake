# He-Man independent raster prototype

This is a **second, separate** homebrew build. It keeps the proven
`switch/heman_core_probe.nro` text-console program intact and adds
`switch_raster/heman_raster_probe.nro`, a native RGBA8888 visual test.

## What actually exists

- 640 x 360 software framebuffer via `framebufferCreate`,
  `framebufferMakeLinear`, `framebufferBegin` and `framebufferEnd`.
- Source-only geometric artwork: color-banded sky, layered hills,
  stone/grass blocks, a minimal humanoid silhouette, patrolling enemy,
  pickup circles, checkpoint flag, hazard and exit arch.
- Shared `hm_session` C99 physics/combat state from the text probe.
- Left/Right moves, A jumps, X attacks, B resets, Y runs the same
  180-frame reproducible synthetic replay, **Minus toggles PAUSED**,
  Plus exits. While paused, actual C99 player/enemy simulation and all
  timers, hazards and checkpoints are frozen; toggling consumes the
  button-edge frame to avoid accidental moves or attacks on resume.
- Red HP bars, gold enemy HP bars and an 8-hex-digit QA fingerprint on
  the upper right. The QA indicator is blue when idle, green after PASS,
  and red after FAIL.
- Existing physics and combined-session boot self-checks execute before
  opening the framebuffer. No proprietary media is required.

This contains no sprites, geometry, engine files or animation sequences
from the original iOS game. The humanoid is a new debugging placeholder.

## Build and verification

Using devkitPro `devkita64` and libnx:

```sh
export DEVKITPRO=/opt/devkitpro
make -C switch_raster clean all
```

The build creates `switch_raster/heman_raster_probe.nro`. The separate
**He-Man synthetic Switch raster build** GitHub Actions workflow checks
its AArch64 ELF and NRO header and publishes an NRO artifact.

GCC and Clang additionally run `native/tests/test_pause.c` and
`raster/tests/test_pause_overlay.c` to verify the actual state freeze,
strict input rejection, PAUSED source pixels and stride padding.

GCC and Clang run `raster/tests/test_raster_scene.c` on the host. The
test verifies pixel determinism, actor movement changing rendered pixels,
QA fingerprint changing the HUD, fail-closed invalid arguments and
untouched stride padding/sentinels. These are software tests, **not
emulator or hardware launch evidence**.

For a real compatible homebrew runtime, record (1) the exact NRO SHA256,
(2) a screenshot of the rendered scene, (3) the Y-button fingerprint,
and (4) how controller input and animation reacted. The original test
NRO remains the baseline if a graphics regression is found.

This is a development prototype: there is no original He-Man level
reconstruction, character sprites, soundtrack, UI or verified framerate.
