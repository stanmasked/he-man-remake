# Stage172 — portable C99 sprite clock and isolated Switch NRO

Stage172 translates the source-free timing decisions established in
Stages169–171 into a bounded C99 module. It also adds a **separate
synthetic Nintendo Switch NRO** that visualizes three fabricated frame
states with flat color swatches. It does not modify the existing game
prototype NRO or claim to display original He-Man animation assets.

## Portable native module

- native/include/heman_sprite_clock.h
- native/src/heman_sprite_clock.c
- native/tests/test_sprite_clock.c

The module has no heap allocation, file I/O, game assets or graphics
dependencies. It provides:
- float32 delta × rate, followed by a separate float32 multiply by
  1000.0f, then safe in-range truncation toward zero to signed i32;
- bounded frame-boundary validation, strict right-edge frame lookup,
  zero-duration frame skipping and last-frame hold;
- finite extra replays and negative infinite-replay settings;
- finished-before-time-addition semantics, inactive/pause no-op and
  state rollback on invalid input or overflow;
- a capped transition budget to prevent pathological zero-duration
  loops from hanging the process.

C99 has undefined behavior for an out-of-range floating-to-integer
conversion. The module checks the float32 result against the signed
32-bit range **before** casting. It refuses NaN/Inf and unsupported
negative player deltas. Volatile float intermediates force each
multiplication to be stored/rounded separately, avoiding accidental
fusion or excess precision in the supported toolchains.

## Timebase boundary

The original executable confirms the multiplication by 1000, but the
upstream caller's units/cadence have not yet been independently
calibrated. Consequently the API calls its integer value
elapsed_ticks, not milliseconds, and does not assume 60-Hz gameplay.
The Switch demo deliberately uses a **fabricated** 1/60 input to expose
per-call quantization; it is a deterministic test signal, not a wall
clock. The synthetic timeline uses three frames with cumulative
boundaries (0, 240, 480, 720) and one extra replay.

## Isolated Switch guest

- switch_sprite_clock/Makefile
- switch_sprite_clock/source/main.c
- CI: .github/workflows/switch-sprite-clock-probe.yml

The NRO shows the currently selected abstract frame as a large color
swatch, the active/paused state, the selected rate and elapsed progress.
Controller controls:
- **A** — pause/resume;
- **B** — reset to the first synthetic frame and replay count;
- **Y** — cycle the synthetic rate through 0.5×, 1× and 2×;
- **Plus** — exit.

The NRO build job checks the AArch64 ELF and NRO0 header and uploads
only the generated asset-free NRO as a short-lived CI artifact. This
is cross-compilation evidence, not yet emulator or physical-hardware
playback proof.

## Validation and privacy

The host C99 runner now compiles and runs test_sprite_clock.c with
both GCC and Clang under -Wall -Wextra -Werror -pedantic. Tests use
only invented boundary arrays and scalar values. The dedicated Switch
workflow rejects tracked proprietary assets, compiles the NRO and
validates its container header. No original IPA, executable, sprite
texture, per-record timing, disassembly or private report is uploaded.

## Next proof obligation

1. Calibrate actual delta input units and call cadence at the original
   gameplay call site.
2. Run the isolated NRO in NeXium and compare pause/resume, rate changes,
   replay and reset against the C99 host trace.
3. Only then design the production graphics adapter and map decoded
   Symbols to atlas regions. Actor animation and collision/hitbox
   changes remain unimplemented and unverified.
