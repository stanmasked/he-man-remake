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

## Experimental second-room ZR dash — Stage 069

In the optional two-room build only, **ZR + Left/Right** starts a
12-game-frame speed burst if the character is grounded, alive and
the ability has recovered. The existing native full-body collision
checks still determine the actual movement: dashing cannot pass through
solid tiles. The burst uses a copy of the same C99 world with double
horizontal speed (240 px/s vs 120 px/s) and **never changes the stored
world or enemy configuration**. The action has an 80-frame lockout
counted from its initial press, so it cannot be spammed. A fresh ZR
press is needed after recovery. An orange ZR HUD meter indicates an
active burst; cyan is ready and grey is recovering.

**Minus** toggles pause with priority over simultaneous ZR, freezing
both the simulated gameplay and dash/recovery counters. Resuming
consumes the button edge without a phantom dash. B resets the character
and cancels an active dash. Stage 1, the single-scene NRO, and all
original baseline controls are unchanged.

`native/tests/test_dash.c` compares actual native C99 movement at
60 Hz against non-dashing movement and checks cooldown, pause and
input-error rollback. `raster/tests/test_dash_hud.c` checks
deterministic UI pixels and stride padding under both host compilers.

This is a new synthetic ability, **not** part of the iOS game's
confirmed rules. Guest-level verification still requires a dedicated
NeXium ZR press/capture run; host tests and NRO compilation alone do
not prove controller behavior in the emulator or on hardware.


## Stage 083: two-room synthetic victory and deliberate restart

The optional `CHAIN_PROBE=1` Nintendo Switch graphical NRO now has a
terminal **FINISH** state once room 2 earns its own genuine C99 `HM_EXIT`.
A center-panel source-authored bitmap glyph overlay is displayed only
after that event. It is not shown merely because the player reached room 2.

At final completion, directional movement, A jump, X attack and ZR dash no
longer advance the portable physics, combat, cooldowns or camera.
**Minus** still toggles pause, taking precedence over simultaneous B.
After resuming, pressing **B** explicitly retries the second room,
resetting the player, HP, enemy and dash timers in one accepted transition.
The first room's CLEAR to second-room A transition and the standard
single-room NRO remain unchanged.

The same native function used by the two-stage NRO is compiled and
executed on host GCC/Clang. The test reaches final completion through
a real native C99 `HM_EXIT` event, then verifies 90 frozen frames,
pause precedence, invalid-input rollback, B restart, restored HP and
genuine simulation progress after retry. The overlay has an independent
pixel/color test including rejection-before-write and padding canaries.

Source assets and original iOS physics are **not** represented. A host
pass and NRO cross-compilation do not by themselves prove a real NeXium
controller or screen capture.

### Video reference research (not source-faithfulness proof)

Public reference footage available as of October 2026:

- iGamesView, 2012 iPhone/iPad gameplay:
  https://www.youtube.com/watch?v=veD5dGUZ7cs
- Publisher Chillingo, 2012 gameplay/promo:
  https://www.youtube.com/watch?v=5ieLgWos3Fo
- Independent guide (based on Android 1.0.3, possibly variant gameplay):
  https://gamefaqs.gamespot.com/android/733964-he-man-the-most-powerful-game-in-the-universe/faqs/68021

Use these for qualitative visual/level/ability references, not for
fabricated original iOS input traces, proven collision hitboxes,
original game timing or a video-copyright asset export. Our owned
source IPA remains private and can differ from early published footage.


## Stage209 — isolated textured-quad reference NRO

Build the standalone synthetic checkerboard probe with devkitPro:

```sh
make -C switch_raster clean all TEXTURE_PROBE=1
```

This creates `switch_raster/heman_texture_probe.nro` without replacing the ordinary `heman_raster_probe.nro` source or gameplay. The probe runs the portable Stage208 C99 CPU reference against a newly authored 8×4 RGBA texture, writes the result to the 640×360 libnx software framebuffer, and checks its own expected sample points before startup. The patched NeXium workflow captures guest frames 30, 120 and 300 and validates checker colors plus clear-background pixels. This verifies the CPU reference and framebuffer path only; it is not a GPU texture-upload path, original-game rendering or hardware proof. No original IPA or extracted resources are used.


## Stage224 — synthetic native allocated-PNG CPU upload guest

A separate opt-in NRO checks the original iOS source-audited zero-padding
**algorithm**, implemented as portable C99 over invented RGB/RGBA buffers.
It is not shipped with, or sourced from, original commercial textures.

```sh
make -C switch_raster clean all TEXTURE_PROBE=1 PNG_PADDING_PROBE=1
# output: switch_raster/heman_png_padding_probe.nro
```

The guest fills a 4×4 allocated texture from a 3×2 synthetic RGB PNG
sample using `hm_native_png_prepare_rgba`, validates allocated stride,
right/bottom black pixels, the exact C99 textured-quad CPU render and
draws a separate visible 64×64 panel into the libnx 640×360 framebuffer.
The existing Stage209 checker remains independent. The standalone Stage224
GitHub Actions workflow validates the AArch64/NRO0 build and keeps a short
lived NRO artifact. The native host C99 checks run under GCC and Clang;
Python/C99 tests compare 48 invented RGB/RGBA/wrap/filter combinations
byte-for-byte. A passing host test or NRO compile is **not** proof of
NeXium execution or GPU texture upload: this still uses the software
framebuffer, not native deko3d sampling.
