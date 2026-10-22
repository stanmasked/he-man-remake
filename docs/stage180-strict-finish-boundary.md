# Stage180 — strict finish-boundary negative control

Stage180 is a verifier-only follow-up to Stage178, stacked on Stage179. A focused review found that the exact-RGB oracle checked the finished-state strip was absent at frame 18 and present at frames 36, 120 and 300, but did not assert absence at frame 30. The recovered synthetic timeline says frame 30 is still active (elapsed 520); the strict finish edge is crossed at frame 36 (elapsed 760).

## Changes

- Require the exact screen-background RGB at the finish-strip sample for all pre-finish checkpoints: 6, 12, 18 and 30.
- Keep exact finished-strip RGB checks at frames 36, 120 and 300.
- Add negative-control host cases that inject a white finished strip at each pre-finish checkpoint (frames 6, 12, 18 and 30); each must fail closed and identify the offending frame.
- No guest NRO, production game logic, sprite-clock, or input behavior is modified.

## Verification

The existing Stage178 host CI passed 1,811 tests across Python 3.10, 3.12 and 3.13, and native C99 under GCC/Clang. Stage180 adds one more Python regression and must be re-run on the new head. The fresh actual-NeXium exact-pixel run for Stage178 remains queued, so this host fix does not substitute for that guest evidence.

## Limits and privacy

All PNGs in host tests are fabricated 640×360 fixtures; actual guest PNG verification remains a separate NeXium gate. The test uses no original IPA, art, extracted textures, or private reports. No production NRO or `main` changes are included.