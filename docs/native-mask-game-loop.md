# Stage 017 — packed collision masks in the native C99 game loop

This stage extends independently authored C99 host gameplay to use synthetic per-pixel collision geometry, while keeping the purchased iOS IPA private.

## Implementation

- Optional borrowed world pointer **mask_grid**; NULL keeps original rectangular-tile stepping.
- At initialization the grid structure, dimensions and spawn are checked.
- Whole-body collision tests use packed tile mask bits.
- Grounded movement sweeps horizontally and tests short vertical lifts before stepping up, then checks nearby support when descending.
- Jumps, gravity, walls, ceilings, event flags and camera updates remain in the existing native step function.
- Malformed mask references and mismatched map dimensions are rejected; invalid steps preserve the original actor state.
- Configurable rise/drop limits between 0 and 32 units.

## Verification

- Three native synthetic gameplay test groups: uphill/downhill motion, wall/head clearance and jumping/input rollback.
- Integrated 26-frame C99 upward/downward wedge trace compared against Python slope physics. Identical ground/wall/ceiling flags, numeric tolerance **0.001** for X, feet Y and velocity.
- Earlier 720-frame rectangular-cell parity and 32-position packed-mask geometry tests remain in the CI suite.
- Local GCC/Clang compilations and the new Python comparison passed; full GitHub Actions is required before merging.

## Known limitations

Per-pixel queries currently revalidate the borrowed mask arrays on each overlap operation. That fail-closed approach has a potentially high CPU cost on large maps and must be profiled and optimized before a Nintendo Switch game build.

This is an experimental C99 host engine. The Tkinter preview is still driven by Python, and the C core does not implement the original movement parameters, animation, enemies, music, damage, one-way ledges, or original script behavior. No Nintendo Switch NRO or Switch emulator smoke test has been created.

## Commands

    sh native/run_tests.sh gcc
    sh native/run_tests.sh clang
    PYTHONPATH=src python -m unittest discover -s tests -v

All public fixtures are independently created. No original IPA, maps, sprites, extracted collision pixel arrays, sound, or private forensic reports are uploaded.
