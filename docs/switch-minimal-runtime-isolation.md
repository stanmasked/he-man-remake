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

## Exact loader incompatibility diagnosed

The original NeXium smoke captured only its **terminal stderr** (mostly ALSA
messages). Capturing its real `NEXIUM_DATA_ROOT/logs/nexium-*.log` revealed:

```text
Auto-loaded NRO: .../heman_minimal_guest_probe.nro
Booting NRO: .../heman_minimal_guest_probe.nro
Detected homebrew wrapper, NRO body starts at offset 16
NRO: text=[0x80, 0x14080), ro=[0x14000, 0x18000), data=[0x18000, 0x1a000)
Boot failed: Data segment out of bounds
```

The genuine devkitPro artifact has exactly `0x1a000` bytes. Its NRO header
magic is at offset 16; the data segment ends at `0x1a000` in the full
file. Current upstream NeXium `nexium-loader/src/nro.rs` subtracts the
16-byte wrapper by passing `mmap[16..]` to its segment validator,
creating a `0x19ff0`-byte limit. The declared end appears out of bounds
by exactly **16 bytes**, before any guest instruction can execute.
There is also a separate suspicious 128-byte adjustment to small text
offsets in that same loader.

`python3 tools/nro_layout_diagnostic.py path/to/file.nro` now reports
both full-file layout bounds and the current NeXium loader interpretation
without altering a single original NRO byte. The same diagnosis has
asset-free unit tests and runs automatically at CI build time.

**Do not fix by padding published NRO files or deleting the original
homebrew wrapper.** Such transformations can change code addresses and
create incorrect success claims. Resolve the loader incompatibility
upstream or use an emulator that correctly supports normal devkitPro NRO.
