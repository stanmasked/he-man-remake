# Stage 016 — masked character movement experiment

This adds a standalone C99 actor-step function over the packed per-pixel geometry introduced in Stage 015. It does not replace the rectangular map-based `hm_step` game loop.

## Additions

- `native/include/heman_mask_motion.h`: C99 motion/state/configuration interface.
- `native/src/heman_mask_motion.c`: fixed-timestep horizontal and vertical sweeps over the entire body; short up-steps and down-slope support when grounded; gravity and jumping when airborne.
- `native/tests/test_mask_motion.c`: entirely synthetic slope-walking, return-down-slope, jumping and invalid-time-step tests.
- `native/run_tests.sh`: builds the extra native C99 executable using both GCC and Clang via the existing GitHub matrix.

The packed tile data are passed as caller-owned arrays; the library does not allocate, open files, draw pixels or contain game artwork.

## Limitations

This is a bounded host physics experiment, not the original He-Man engine. It does not support one-way ledges, enemies, health, real player hitbox calibration or source scripts. It does not have a devkitPro build yet. The existing high-level `hm_step` still uses binary occupancy cells instead of the mask-motion API. A future platform adapter must choose and integrate the actual native movement implementation deliberately.

## CI

Run:

    sh native/run_tests.sh gcc
    sh native/run_tests.sh clang

Both are added to GitHub Actions. The new tests need to pass independently before the branch can be merged. No original IPA or private diagnostics are published.
