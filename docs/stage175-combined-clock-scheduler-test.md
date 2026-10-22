# Stage175 — combined scheduler and animation-clock integration

Stage175 closes a test gap between Stages172–174: the outer wall-clock
scheduler and the per-player animation clock were previously tested
separately. The new host scenario links the same production C99 source
files together, without graphics, assets or Nintendo SDK dependencies.

## Integrated scenarios

1. **One fabricated second:** feed 60 wall-clock callbacks using a
   repeatable 16,17,17-ms pattern. The accumulator returns 62 gameplay
   updates and an 8-ms remainder. Each update passes the observed 0.04f
   input to a finite three-frame, one-extra-replay animation. The combined
   result is frame 2, elapsed 760, no replays remaining, and the strict
   finished predicate set. The remaining scheduler updates do not add
   time once the finite animation is finished.
2. **Long stall:** a fabricated 500-ms wall-clock delta is capped to
   66 ms, resulting in four player updates and a 2-ms remainder. The
   infinite synthetic animation accumulates 160 integer time units.
3. **Pause/resume:** the outer scheduler continues to emit updates while
   the player clock is paused, but the player state remains unchanged.
   After resume, one subsequent 16-ms scheduler update advances the
   player clock by 40 units.

These are source-level deterministic test vectors. They do not establish
the original iOS app's exact timer delivery pattern, operating-system
scheduling, or observed animation speed.

## Implementation

- native/tests/test_tick_animation_integration.c
- native/run_tests.sh

The new binary compiles heman_app_tick_scheduler.c and
heman_sprite_clock.c together with strict C99 warnings. Because the
runner is shared by GCC and Clang jobs, both toolchains run the same
combined assertions. No production game NRO, actor behavior, or original
assets are modified.

## Next step

The timing model is internally integrated and deterministic. The next
gate is executing the synthetic Switch NRO under NeXium and recording
the actual update count and frame-state transitions. Original-device
runtime comparison remains necessary before adopting these timing rules
in production gameplay.
