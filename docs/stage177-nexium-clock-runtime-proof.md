# Stage177 — run the synthetic sprite clock inside NeXium

Stage177 moves beyond cross-compilation: a dedicated workflow builds the
existing asset-free sprite-clock NRO, starts it with the pinned patched
NeXium guest runner, captures actual guest framebuffer PNGs, and checks
the rendered state transitions. The workflow is evidence-gathering only;
it does not patch the NRO or modify the production game.

## Captured checkpoints

The temporary NeXium runner captures guest frames 6, 12, 18, 30, 36,
120 and 300. Under the NRO's fabricated 16/17/17-ms callback pattern,
the expected source-model checkpoints are:

- Frame 6: synthetic frame 1 at its right boundary.
- Frame 12: synthetic frame 2.
- Frame 18: finite replay wraps to synthetic frame 0 and the progress bar resets.
- Frame 30: synthetic frame 2 after the second play has advanced.
- Frame 36: the 37th player update crosses the strict finish edge.
- Frames 120 and 300: the finished frame, full progress bar and finished-state strip remain stable.

The Stage177 verifier checks 640×360 guest PNG dimensions, center-swatch
transitions, progress-bar reset and completion, the finished-state strip,
and the per-callback update indicator (one update at frame 30 versus two at
frame 120). Stage178 strengthens this to exact RGB values for the center
swatch, progress bar, finish strip and update HUD, based on retained real
NeXium guest captures. Both verifiers fail closed when a required checkpoint
is missing or sampled pixels do not match the expected state.

A native C99 timeline test independently runs the exact 16/17/17-ms callback
sequence through the production scheduler and sprite-clock sources for 300
guest callbacks. It locks expected cumulative update counts and states at all
seven capture checkpoints: 6, 12, 18, 30, 36, 120 and 300. This prevents the
pixel verifier's expected timeline from drifting away from the C implementation.

## Isolation and privacy

- NRO is built from the already existing synthetic C99 clock and scheduler.
- NeXium is checked out at the same pinned upstream revision and patched
  only in a temporary CI workspace for guest frame capture.
- The owner-private IPA, original textures, record timing values and
  binary are not involved in this workflow.
- Captures and logs are uploaded as a seven-day CI artifact, including
  diagnostic evidence on failure.

The shared Python CI exercises the frame instrumentation against a pinned-shape
synthetic Rust fixture and tests the pixel verifier with fabricated 640×360 PNG
checkpoints. Negative controls remove a required frame, corrupt the update
indicator, and corrupt a center-swatch pixel; each must fail closed. These are
host-side test-fixture checks, not captured emulator evidence.

## What this can prove

A passing run proves that the isolated synthetic NRO executes under the
patched NeXium CPU/runner and that its actual guest pixels match the
deterministic synthetic clock model at the selected checkpoints. It does
not prove the original iOS binary's runtime timing, nor validate authentic
He-Man art or production actor animation.

## Next gate

Four earlier NeXium runs passed all seven guest PNG checkpoints, including
frame 300: [run A](https://github.com/stanmasked/he-man-remake/actions/runs/39839123724),
[run B](https://github.com/stanmasked/he-man-remake/actions/runs/39839405439),
[run C](https://github.com/stanmasked/he-man-remake/actions/runs/39842453357),
and [run D](https://github.com/stanmasked/he-man-remake/actions/runs/39842587365).
A separate run exposed nondeterministic startup latency: the first frame
arrived late and the 16-second capture budget ended before frame 300. The
workflow now allows 40 seconds, with a host regression guarding that budget.
The current PR-head rerun must still finish successfully before this gate is
checked. If it fails, use retained logs/PNGs to correct the runner or pixel
assertions before connecting original graphics. Production integration remains
blocked on resolving the original timer/callback discrepancy.

## Host CI dependency

The first full Python-suite run discovered that the new PNG fixture tests
import Pillow, while the generic test workflow did not install it. Pillow is
now installed before test discovery. The corrected run passed all 1,809 tests
on Python 3.10, 3.12 and 3.13; native C99 core and focused sprite-clock host
checks also passed under GCC and Clang. These host results are distinct from
the latest NeXium runtime rerun.
