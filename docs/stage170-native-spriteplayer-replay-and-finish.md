# Stage170 — original SpritePlayer replay and finish decisions

**Scope:** nonnegative native elapsed integers, frame boundaries independently
validated by Stage169, and the native SpriteSequence::getLoop field.
This is an owner-private source-research reference, not a finished Switch
animation controller or a replacement for original game execution.

## Findings from original ARMv7 control flow

Inspected these original methods separately without publishing any
machine-code bytes or disassembly:

- SpritePlayer::reset sets elapsed time and current frame index to
  zero and copies SpriteSequence::getLoop into its **remaining replay**
  counter.
- advancedFrameIndex(elapsed) increments the current frame index,
  wrapping modulo the sequence frame count. At the total timestamp,
  a completed cycle can either leave the final frame in place (no
  remaining finite replays) or subtract one full duration and restart.
- With a **negative loop setting** the original branch does **not**
  decrement the remaining counter. With a nonnegative setting and
  positive remaining counter, the counter decrements once per
  completed wrap. Thus positive values encode additional repeats,
  not numbers of frames.
- isFinished handles missing/empty resources or an available next
  frame first. On the last frame it requires elapsed to be **strictly
  greater** than that frame's final time boundary **and** the remaining
  replay counter to be zero. Equality is **not** finished.
- calc checks isFinished before applying a new elapsed-time increment
  and then calls advancedFrameIndex. The pure oracle models the
  latter and the finish gate independently.

The owner's original iOS v2.0.0 IPA contains 2,354 sequences per
resolution, including 1,689 with zero replay setting, 642 negative,
and 23 positive. No individual identifiers or original numeric
values are exposed in repository tests.

## Implementation

- Source: src/heman_tools/sprite_player_native_loop_controls.py
  exports immutable NativePlayerState, bounded advance_native_player
  and is_native_finished functions using Stage169 boundaries.
- Tests: tests/test_sprite_player_native_loop_controls.py contains
  **27 synthetic-only tests**, including boundary equality, multiple
  finite cycles in one update, no-repeat finish, negative infinite
  policy, empty/single/multiple frames, zero-time skips and archive
  safety and report redaction.
- Owner-private source audit checks loop sign groups against validated
  Stage169 structural totals in both original source resolutions.
- Inconsistent counters, out-of-range time/frame values, zero-total
  infinite replay and excessive transition work fail closed instead
  of hanging or inventing a recovery.

### Fabricated examples

With hypothetical boundaries (0, 40, 100):

- No repeats: at elapsed 99 select the last frame. At time 100 it
  remains selected but is not finished; at 101 with no replay remaining
  the finished gate becomes true.
- One finite repeat left: at time 100 decrement it to zero, subtract
  100 time units and restart from the first frame.
- Infinite setting -1: elapsed 245 becomes elapsed 45 after two full
  cycles; the negative loop setting remains unchanged.

These are fabricated duration values, not original game data.

## Owner-only execution

    PYTHONPATH=src python -m heman_tools.sprite_player_native_loop_controls \
      --ipa /secure/private/He-Man-v2.0.0.ipa \
      --out local_reports/sprite_player_native_loop_controls.json

Only anonymous aggregates are emitted. Never publish the original
IPA, executable, reverse-engineering trace, WAD, resource identifiers,
individual frame timings, artwork or private results to GitHub/Actions.

## Still unresolved

SpritePlayer::tick(float) multiplies by a rate factor and 1000, but
upstream clock units and precise float rounding are not yet calibrated
against original execution. This oracle does not cover the complete
tick pipeline, pause and sequence replacement, atlas textures, mesh
animation, collision changes or genuine hardware Switch parity.
