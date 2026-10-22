# Stage182 — monotonic app-clock bridge

Stage182 introduces a portable boundary between a platform monotonic timestamp and the existing bounded app-tick scheduler. It is deliberately separate from the deterministic NeXium probe: the current guest PNG oracle continues to use fabricated callback deltas and is not made timing-sensitive.

## Contract

- The platform supplies a monotonic timestamp in nanoseconds; this module performs no OS or libnx calls.
- The first sample establishes a baseline and returns zero elapsed milliseconds.
- Subsequent elapsed deltas truncate sub-millisecond fractions and are capped at 66 ms before narrowing to a signed integer. The scheduler already clamps the accumulated budget to 66 ms, so this bound preserves its catch-up semantics while preventing integer overflow on very long pauses.
- The sample baseline is committed only after timestamp validation. A regressing timestamp fails closed without modifying state or output.
- The caller invokes this bridge only when the application-state gate dispatches the tick handler. It must not sample while dispatch is skipped; therefore the first resumed sample includes the pause interval and is bounded by the same 66-ms policy.
- The existing player-level pause remains separate: the app clock may schedule updates while the sprite clock is inactive.

## Tests

Six synthetic C99 scenarios cover first-sample behavior, integer-millisecond conversion, the 66-ms edge, two pause/resume cycles with a carried accumulator remainder, timestamp regression, extreme uint64 deltas and invalid state. The repeated-pause integration case yields 11 bounded updates, a 3-ms accumulator remainder and 440 offered player-clock units from fabricated timestamps.

The focused host workflow compiles this adapter under GCC and Clang with strict C99 warnings. The full native/run_tests.sh suite also includes it. No guest NRO or production loop is changed in this stage.

## Evidence boundary and next step

This is a portable time-source bridge, not proof of original iOS callback delivery or a hardware Switch frame rate. It does not choose a libnx API, perform rendering, or change player timing. The next step is to wire a verified libnx monotonic source into an isolated real-time guest probe while keeping the deterministic frame oracle separate.

No IPA bytes, disassembly, original game art, extracted resources or private reports are included.
