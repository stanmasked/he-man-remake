# Stage 020 — Switch synthetic core probe with text-map visualization

This directory is a small **text-console test program**, not a playable He-Man remake. It contains no original level files, game graphics, scripts, music, or purchased iOS resources.

## Requirements

Install the devkitPro Switch development packages (devkitA64, libnx, elf2nro) and set **DEVKITPRO** to the installed SDK location. The source refers to the standard libnx controller and console APIs in the maintained [switchbrew application example](https://github.com/switchbrew/switch-examples/tree/master/templates/application).

After installation, from the repository root:

    make -C switch

Expected output (when the SDK is installed and compatible): `switch/heman_core_probe.nro`. The executable draws a 40×20 text-tile viewport using the independent C99 simulation, accepts Left/Right to move, A to jump, B to reset and Plus to quit. It shows a player marker (`@`), platforms (`#`), pickups (`*`), checkpoints (`C`), hazards (`!`) and exit (`>`), plus a numerical HUD. These are *invented test events*, not original iOS mechanics.

The C99 core operates on a **hand-written 48x24 solid-cell exercise world**, not any game data. No external asset extraction or original IPA is used. It does not load iOS level files or render sprites. Viewport logic is pure C99 (`switch/source/probe_view.c`) and is regression-tested on GCC and Clang by `switch/tests/test_probe_view.c`; the console program reuses this exact code. Physics uses a nominal 1/60-second fixed step with approximate sleeping, not measured hardware-accurate frame pacing.

### What has actually been tested

- Host GCC and Clang builds of the C99 engine and synthetic simulation tests: completed locally.
- The first 900-frame 300x19 masked-world CPU benchmark: completed locally.
- **First real cross-compilation passed** in GitHub Actions with devkitA64 15.2.0, libnx and elf2nro: [run #39157351301](https://github.com/stanmasked/he-man-remake/actions/runs/39157351301). The resulting synthetic-only NRO is 196,608 bytes, verified as an AArch64-derived NRO (`NRO0` signature at offset 0x10), SHA-256 `89d54933e481008e6d28c41abe09a2c3877a73e54634cf2567a2f779db2b4fdd`. The build artifact is downloadable from that Actions run (retention: seven days).

### SDK conventions

The Makefile follows the devkitA64 compiler and libnx console conventions. For production homebrew, the maintained [application template](https://github.com/switchbrew/switch-examples/blob/master/templates/application/Makefile) is the supported reference for NRO packaging and app metadata. Before shipping anything, move to a verified template-based production build, add applet lifecycle checks, graphics and controller timing, and test on an emulator or console that can legally run homebrew.

This target is now built in a separate GitHub Actions job using the official `devkitpro/devkita64` container. The normal Python/GCC/Clang jobs remain independent. Successful cross-compilation is **not** proof that the homebrew launches or operates correctly in a Switch emulator or on hardware; runtime tests remain pending.

### Stage 020 scope

This is a visibly navigable *console test map* with scrolling text tiles and synthetic event markers. It is not original He-Man gameplay, a texture renderer, or a demonstration of Switch emulator/hardware boot. The private IPA remains outside GitHub. Native host tests check tile placement, HUD marker state, scrolling offset, NUL row bounds, and fail-closed handling of invalid input.

### Stage 021 boot self-check

On startup, the NRO executes an independent 180-frame, fixed-step synthetic
course using the same `hm_step` engine and `hm_probe_render` text viewport
that the interactive console uses. It verifies movement, one jump and landing,
pickup, checkpoint, exit, scrolling, and one visible player glyph. The
program **refuses to start** if this self-check fails and shows an error code;
otherwise the HUD prints `Synthetic boot self-check: PASS`.

The same diagnostic is run twice by an asset-free host test compiled with both
GCC and Clang in the existing native CI. PASS indicates **C99 simulation
self-consistency**, not a Switch emulator boot or original iOS behaviour.
A photograph/screenshot of this status after a real emulator or homebrew
launch would be separate evidence of execution, and must not be conflated
with the build-only CI evidence.
