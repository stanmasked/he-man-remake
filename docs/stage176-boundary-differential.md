# Stage176 — sprite-clock boundary differential and exhaustive small-state test

Stage176 adds two complementary checks for the reconstructed frame
transition algorithm. The original iOS IPA remains owner-private; no
original sequence names, frame durations, resource identifiers, binaries,
or traces are included in this repository.

## Public, source-free regression test

native/tests/test_sprite_clock_exhaustive.c enumerates monotonic
synthetic boundary arrays of one to four frames, each frame duration
chosen from 0, 1, or 2 units (excluding all-zero total sequences). It
sweeps valid current frame indices, elapsed values through three complete
sequence durations plus two units, and loop/replay settings for finite
and infinite playback.

The test compares the C99 implementation to a separate reference state
machine and checks result codes, selected frame, elapsed time, and replay
counter. It executes **41,874 cases**. A focused workflow compiles and runs
this test alongside the existing clock/scheduler integration checks under
both GCC and Clang, without adding it to the broad gameplay test runner.

## Owner-private boundary differential

A local, aggregate-only analysis parsed the timing fields from all
2,354 indexed animation sequences in each original resolution pack. It
then compared the local C99 transition implementation with an independent
Python translation of the recovered transition rules at initial state
and around each cumulative frame boundary (one unit before, exact, and
one unit after), including both the immediately preceding frame and a
stale frame-zero starting state, plus valid replay-counter settings.

- screen-med: **43,403 cases, 0 mismatches**
- screen-xlarge: **43,403 cases, 0 mismatches**
- Non-empty sequences exercised per pack: 2,351; empty sequences: 3

Only aggregate counts were retained. This is a cross-check of the C port
against the reconstructed reference over the original timing-table
shapes; it is **not** execution of the original binary and does not prove
runtime animation-speed parity. The original assets and per-record values
were not added to public CI.

## Next gate

The clock model now has broad synthetic state-space coverage and a
private sweep over the original timing tables. Next, run the isolated
Switch NRO in NeXium and record the NRO's own frame/update transitions.
Before changing production gameplay, reconcile those results with the
original callback/accumulator behavior. Runtime evidence from the original
iOS app is still unavailable in this session.
