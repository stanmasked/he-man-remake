# Stage169 — native SpritePlayer timestamp boundaries and frame selection

Stage167 recovered original `SpriteSequence` → `SpriteFrame` →
`Symbol` loading. Stage168 measured verified per-frame time fields.
Stage169 adds a **minimal source-free reference** for the original
player's cumulative boundaries and lookup for **nonnegative elapsed
integer time**, grounded in separate inspected ARMv7 executable code.

## Two independent original methods

A private examination of the original ARMv7 executable found:

**`SpritePlayer::buildKeyFrameTimeStamps()`** stores a table of
`frame_count + 1` signed integer boundaries, starting with zero.
Each successive boundary adds `SpriteFrame::getTime()` from the
corresponding frame.

**`SpritePlayer::computeCurrentFrameIndex(elapsed)`** uses that
table to choose the interval whose **right endpoint is strictly
greater** than a nonnegative elapsed value. An elapsed value at an
internal boundary selects the **next** frame. At/after total time,
it returns the last frame. An empty sequence returns `-1`.

Zero-duration frames have duplicate boundaries and are skipped when
time moves through that boundary; no minimum 1-unit duration is
invented. This behavior is based on original index lookup, not
guessed based on popular platform game animations.

## Deliberately scoped reference implementation

- `src/heman_tools/sprite_sequence_native_frame_boundaries.py`
  provides two pure bounded functions:
  `build_keyframe_boundaries((durations...))` and
  `frame_index_at_elapsed_ticks(boundaries, nonnegative_time)`.
- Rejects negative frame times, malformed values and signed 32-bit
  total overflow rather than silently wrapping or assuming a recovery
  strategy. The original owner IPA contains no negative frame time
  values or cumulative signed 32-bit overflow, so this covers observed
  original data.
- A strict owner-private source audit applies these controls to the
  real nested sequence structures of both original resolution packs
  and reconciles aggregate counts with the Stage168 native ledger.
- Returns **anonymous aggregate counters only**, without original
  identifiers, individual duration arrays, offsets, images, frame
  traces or timing arrays.

## Runtime time conversion: strong evidence, bounded claim

The original `SpritePlayer::tick(float)` code includes a floating
point multiplication by a saved animation-rate factor and **1000.0**
before converting to a signed integer and invoking player calculation.
This connects the native integer frame times with a timebase scaled
by 1000 per input time unit, consistent with milliseconds if upstream
delta time is in seconds. The upstream call chain/units have *not*
yet been independently established; neither the exact rounding
behavior nor custom playback-rate defaults is claimed here.

The original `SpritePlayer::advancedFrameIndex` and
`isFinished` handle separate finite/infinite loop counters and
end-of-playback behavior. **Do not reuse the clamped pure lookup as a
complete looping player**. The oracle intentionally does not simulate
negative elapsed values, wraparound, replay counters or collision
animation state.

## Tests, IPA boundaries and next gate

- `tests/test_sprite_sequence_native_frame_boundaries.py`
- **25 completely fabricated tests**: zero/one/multi-frame sequences,
  strict boundaries, zero-duration skips, clamping, bad inputs,
  nonmonotonic/overflow rejection, cross-resolution drift, secure
  fabricated IPA and ZIP controls, and source privacy.

Private owner-only run:

```sh
PYTHONPATH=src python -m heman_tools.sprite_sequence_native_frame_boundaries \
  --ipa /secure/private/He-Man-v2.0.0.ipa \
  --out local_reports/sprite_sequence_native_frame_boundaries.json
```

All original IPA assets, machine code, source identifiers and any
private report stay off public GitHub/Actions. Synthetic Switch NRO
and `main` are unchanged.

**Next gate:** confirm upstream tick delta units/rounding and model
`advancedFrameIndex` replay and end-of-animation rules with
independent machine-code control-flow evidence before integrating
actual animation state and textures.
