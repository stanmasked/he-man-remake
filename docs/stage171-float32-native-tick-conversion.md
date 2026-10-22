# Stage171 — original float32 tick conversion and normal active-player integration

This stage builds on the verified original SpriteSequence/Frame/Symbol
loader (Stages167–168), cumulative timestamp boundaries (Stage169)
and replay decisions (Stage170). Only the NORMAL finite, nonnegative
elapsed-time path is covered. It is not an original Switch animation
renderer and does not import proprietary assets.

## Original ARMv7 evidence

The owner's private original executable contains the SpritePlayer
constructor, setCustomAnimationRate, tick(float) and calc(int).

Independent instruction-level checks establish:

- The constructor initializes the float32 custom animation rate to
  exactly **1.0**.
- setCustomAnimationRate directly stores the supplied float32 value.
- SpritePlayer::tick(float) checks that its playback mode field equals
  **1** before invoking calc(int).
- For active playback, the tick input is multiplied by the saved
  float32 animation rate, then by an embedded float32 constant
  **1000.0**, in that order.
- The result is converted using ARM VCVT.S32.F32 (truncation toward
  zero) and passed as a signed 32-bit integer to calc(int).
- calc(int) first checks isFinished; if not finished it adds the
  quantized integer tick to the elapsed counter and advances through
  the Stage170 native replay logic.

No original disassembly, code bytes, game-owned names or traces are
committed. These rules can be represented with source-free
binary32 operations on fabricated test values.

## Reference implementation

The new module
src/heman_tools/sprite_player_native_tick_conversion.py provides:

- native_tick_delta_as_i32(delta_input, rate=1.0): round both
  arguments to IEEE binary32, perform **two separately rounded**
  float32 multiplies, then truncate to signed integer toward zero.
- step_native_player_from_float_tick(boundaries, loop, state, input,
  rate=1.0, playback_active=True): models the normal calc path,
  including inactive mode, finished-before-increment, signed elapsed
  range protection and Stage170 frame/replay transitions.
- Finite/valid input checks reject undefined or unsupported
  out-of-range values. No claim is made about the original hardware's
  saturation policy on NaN/infinite input, negative playback, signed
  elapsed overflow or graphics changes.

### A useful synthetic consequence

Assuming **one second per unit of tick(float) input**, a fabricated
delta of 1/60 is converted into **16** integer time ticks at the
default animation rate, not 17. Sixty separate identical calls
therefore give 960 integer time ticks; one single 1.0 input yields
1000. This illustrates **quantization at each tick call**, not
proof that the original game actually uses fixed 60-Hz tick input.
The upstream caller time unit, actual cadence and whether other
callers adjust elapsed time separately remain to be established.

The original SpritePlayer tick also maintains fade/highlighting
fields; Stage171 intentionally models only the normal animation
clock/calc path. The surrounding transitions, time source and
hardware playback can differ.

## Tests and privacy

Tests at tests/test_sprite_player_native_tick_conversion.py use
fabricated numeric time values only. They cover:

- Rate 0, half, default, double and negative conversion, binary32
  mantissa boundaries, submillisecond rounding to zero, truncation
  toward zero for positive and negative values
- Nonfinite/boolean/huge arguments, overflow, inactive mode
- Exact frame edges, finite and infinite replay, empty and
  zero-duration frames, already-finished frames and excessive work
- Quantization of 60 separate hypothetical 1/60 tick calls versus a
  single hypothetical 1.0 input

The original IPA, native executable and sprites remain solely in
the owner's private working environment. No native data or private
analysis reports are consumed by public CI.

## Next implementation gate

Inspect how the original gameplay update passes delta time to
SpritePlayer::tick and calibrate actual input units and frame cadence.
After that, port the bounded behavior to a separately tested Switch
host-side animation clock, followed by graphics mapping and replay
validation in a Switch emulator. The existing synthetic NRO, original
asset import and main branch are unchanged in this stage.
