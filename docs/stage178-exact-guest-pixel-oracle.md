# Stage178 — exact guest-pixel oracle

Stage178 strengthens the Stage177 NeXium PNG verifier after an audit of a
retained successful guest artifact. The earlier verifier mainly checked
relative differences between sampled pixels; a wrong but internally
consistent palette could therefore pass. Its synthetic host fixture also
used guessed RGB swatches rather than the colors actually observed in NeXium.

## Changes

- Lock the expected RGB value at the center of all seven checkpoints
  (6, 12, 18, 30, 36, 120 and 300), not merely transitions between colors.
- Assert exact fill/background colors for the progress bar at the replay
  boundary, partial-progress checkpoint and finished checkpoints.
- Assert the exact screen-background/finished-strip colors around the strict
  completion boundary.
- Assert exact active/inactive colors at the one-update and two-update HUD
  samples.
- Rebuild host PNG fixtures with the observed framebuffer RGB values and add
  a negative control that corrupts one center-swatch pixel.

The palette was checked against the retained Stage177 NeXium artifact from
run [39842587365](https://github.com/stanmasked/he-man-remake/actions/runs/39842587365).
All seven captured PNGs match the new exact sample oracle. The newer Stage177
PR-head run also completed successfully: [run #39847718995](https://github.com/stanmasked/he-man-remake/actions/runs/39847718995)
captured seven required checkpoints and passed the Stage177 verifier, including
frame 300. The Stage178 exact-pixel assertions are now being checked on their
own PR head.

## Scope and limits

The change is limited to evidence verification and host fixtures. It does not
change the NRO, reconstructed clock/scheduler, production gameplay or main.
A successful exact-pixel check proves the synthetic guest's sampled output
matches the known synthetic state at these checkpoints; it does not establish
the original iOS game's real callback cadence or animation pacing.

## Current verification

The Python suite has passed 1,811 tests on Python 3.12, and the Python 3.10
and 3.13 jobs plus native GCC have passed on the current Stage178 head. The
Clang job and fresh Stage178 NeXium guest run are still queued. The PR remains
Draft until those checks finish; no original IPA or game assets are included.
