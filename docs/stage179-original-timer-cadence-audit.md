# Stage179 — original timer path and fixed-delta cadence audit

Stage179 revisits the original iOS v2.0.0 timing path using the owner-held
IPA fetched privately from Google Drive. The executable was inspected locally
as an ARMv7 Mach-O with its symbol table available. No IPA bytes, executable
bytes, raw disassembly, code offsets, original assets, or private reports are
committed or uploaded.

## Static call path established from the original executable

1. `GSAppDelegate::onCreate` calls `HeloApp::setTimer(60)`.
2. `HeloApp::setTimer(int)` converts the frequency argument to float and
   calls `HeloTimeDelegate::setTimer(float)`.
3. `HeloTimeDelegate::setTimer` calculates `1000.0f / frequency`, then
   scales by `0.001f`, and registers a repeating `NSTimer` callback to
   `HeloTimeDelegateObjc::tick:`. At frequency 60, the requested interval is
   nominally (1/60) second, approximately 16.667 ms.
4. `HeloTimeDelegateObjc::tick:` calls `HeloApp::_tick`.
5. `HeloApp::_tick` records the current reference-date timestamp and passes
   the exact float32 constant `0.04f` to its application-handler callback.
6. `GSAppDelegate::onTick` independently samples `gettimeofday`, converts
   the difference to integer milliseconds, adds it to a persistent accumulator,
   caps the accumulator at 66 ms, then repeatedly calls `Kernel::tick(0.04f)`
   while consuming complete 16 ms quanta. It subtracts 16 ms per update and
   stops when the remainder is below 16 ms.
7. `SpritePlayer::tick(float)` applies its animation-rate factor, multiplies
   by `1000.0f`, and truncates to signed integer time. At rate 1.0, each
   fixed `0.04f` input advances the player clock by 40 integer units.

These facts come from static control flow in the private original executable.
The requested NSTimer interval is not a measurement of delivered callbacks:
actual iOS scheduling jitter, suspension, callback delays and device behavior
are still unmeasured.

## New regression: keep the animation active for the full modeled second

Stage175's one-second integration fixture used a short finite animation, which
finished after 37 player updates. That was correct for the end-state test but
could obscure the cumulative time offered to an animation that remains active.

The updated `native/tests/test_tick_animation_integration.c` adds a separate
long-duration infinite synthetic animation. Under the existing fabricated
callback deltas (20 × 16 ms and 40 × 17 ms = 1000 ms), the test asserts:

- 60 outer callbacks;
- 62 scheduler/player updates;
- 8 ms remaining in the accumulator;
- 40 integer animation-time units per active player update;
- 2,480 cumulative integer time units after the modeled second; and
- the long synthetic animation remains unfinished.

This is a deterministic consequence of the recovered code path and the
existing source-free C99 model, not a claim that a real device delivers this
exact callback sequence or that the original animation was observed running
at 2.48× speed. The 66 ms accumulator cap continues to discard excess wall
time after long stalls; it is not replaced by unbounded catch-up.

## Interpretation and next gate

The code contains two distinct time inputs: measured wall-clock elapsed time
controls how many 16 ms updates run, while each update receives a fixed 40-unit
player-clock increment at the default animation rate. This explains the
*modeled* 2.48× ratio under the chosen one-second schedule. It does not resolve
whether the original runtime intentionally used this ratio, how often callbacks
were actually delivered, or whether another state/pause path changes effective
pacing.

The host test uses only fabricated boundaries and deltas and compiles with the
same scheduler and sprite-clock sources used by the synthetic Switch probe.
Original-device timing parity remains an explicit production-integration gate.
No authentic textures or actor animations are connected by this stage.
