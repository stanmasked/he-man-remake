# Stage 018 — first optional devkitPro target (synthetic core probe)

This directory is a small **text-console test program**, not a playable He-Man remake. It contains no original level files, game graphics, scripts, music, or purchased iOS resources.

## Requirements

Install the devkitPro Switch development packages (devkitA64, libnx, elf2nro) and set **DEVKITPRO** to the installed SDK location. The source refers to the standard libnx controller and console APIs in the maintained [switchbrew application example](https://github.com/switchbrew/switch-examples/tree/master/templates/application).

After installation, from the repository root:

    make -C switch

Expected output (when the SDK is installed and compatible): `switch/heman_core_probe.nro`. The executable prints native C99 simulation coordinates on an ordinary text console, accepts Left/Right to move, A to jump, B to reset and Plus to quit.

The C99 core operates on a **hand-written 48x24 solid-cell exercise world**, not any game data. No external asset extraction or original IPA is used. It does not load iOS level files or render sprites.

### What has actually been tested

- Host GCC and Clang builds of the C99 engine and synthetic simulation tests: completed locally.
- The first 900-frame 300x19 masked-world CPU benchmark: completed locally.
- **First real cross-compilation passed** in GitHub Actions with devkitA64 15.2.0, libnx and elf2nro: [run #39157351301](https://github.com/stanmasked/he-man-remake/actions/runs/39157351301). The resulting synthetic-only NRO is 196,608 bytes, verified as an AArch64-derived NRO (`NRO0` signature at offset 0x10), SHA-256 `89d54933e481008e6d28c41abe09a2c3877a73e54634cf2567a2f779db2b4fdd`. The build artifact is downloadable from that Actions run (retention: seven days).

### SDK conventions

The Makefile follows the devkitA64 compiler and libnx console conventions. For production homebrew, the maintained [application template](https://github.com/switchbrew/switch-examples/blob/master/templates/application/Makefile) is the supported reference for NRO packaging and app metadata. Before shipping anything, move to a verified template-based production build, add applet lifecycle checks, graphics and controller timing, and test on an emulator or console that can legally run homebrew.

This target is now built in a separate GitHub Actions job using the official `devkitpro/devkita64` container. The normal Python/GCC/Clang jobs remain independent. Successful cross-compilation is **not** proof that the homebrew launches or operates correctly in a Switch emulator or on hardware; runtime tests remain pending.
