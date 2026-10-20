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

## Optional two-room prototype (Stage 067)

The standard `heman_raster_probe.nro` retains its verified **single**
synthetic scene. To test one more independently authored area and a real
in-engine completion-to-next-room transition:

```sh
make -C switch_raster clean all TARGET=heman_two_stage_probe CHAIN_PROBE=1
sh native/run_tests.sh gcc
sh native/run_tests.sh clang
```

This variant starts with an opt-in short first room, whose normal C99
`HM_EXIT` event shows **CLEAR** when reached. **Press A after CLEAR**
to load the second room. The transition is not automatic. A simultaneous **Minus + A** input
prioritizes pause instead of changing rooms. It atomically
resets the world, checkpoint, player/monster HP, camera and timers.
Room 2 has a separate source-authored ground/platform layout, own
checkpoints, hazard and exit. Stage 2 is terminal: pressing A there
does not silently restart the course. A small top-right stage marker
reads **1** or **2**. Minus pause, B retry, sword attack and the
other baseline controls remain available.

This feature has its own optional AArch64 NRO CI build in
`.github/workflows/switch-two-stage.yml`, plus independent C99 tests
for earned completion, input gating, failed-stage rollback and a stage
HUD pixel/padding audit. A compiled NRO is **not** proof of emulator
or physical-console execution; real two-room progression still needs
a separate NeXium controller/HUD test.

Both rooms are completely synthetic and bear **no** relationship to
the content, artwork, collision mapping, plot or rules of the original
commercial iOS game. No original IPA or extracted resource is shipped.

## Shared second-room geometry — Stage 068

The optional `CHAIN_PROBE=1` game now sources its **actual**
`48 × 24` tile grid, four event definitions and the second-room enemy
configuration from `native/src/heman_synthetic_room2.c`. This is the same
C99 function invoked by the host tests — **not** a separately invented
test copy. All tile rows (floor 18, raised platforms 13 and 15) and
pickup/checkpoint/hazard/exit coordinates therefore have one authority.

The builder checks arguments and the native physics/combat validators
before committing the world, combat configuration or tile memory.
`native/tests/test_synthetic_room2.c` verifies exact cells and event
types, unchanged output on invalid arguments, deterministic repetition,
and **real native simulation** reaching the pickup, checkpoint, hazard,
and final exit. CI tests this under GCC and Clang, while the existing
actual NeXium PNG progression workflow still validates entrance from
the first room into this scene.

The ordinary one-room NRO, existing controls and the commercial game's
source data are not modified by this internal refactor. Full
original-game content and physics fidelity remain unverified.
