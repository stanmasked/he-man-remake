# Stage 016 — pixel masks integrated into the native C99 game loop

The platform-neutral C99 `hm_step()` now accepts **optional borrowed pixel masks** from Stage 015. The existing rectangular-tile path remains the default, so earlier host scenarios still run unchanged. No original He-Man iOS executable code, artwork, extracted `.map` data or proprietary collision bytes are included.

## How to enable the new path

In `hm_world` (see `native/include/heman_core.h`):

- `mask_grid` points to a caller-owned, previously constructed `hm_mask_grid` containing 16-bit tile IDs and 64-bit mask rows. Set it to `NULL` to keep the legacy rectangular collision path.
- `max_rise` and `max_drop` control bounded grounded slope stepping, each from 0 to 32 synthetic pixel units.
- When masks are enabled, `hm_init()` verifies grid dimensions, tile size, per-tile mask IDs and row bit bounds; `hm_step()` revalidates the borrowed mask grid and rejects corruption without mutating `hm_state`.

The simulation tests the **full actor rectangle** against pixel-level occupancy. If a grounded horizontal step collides with a rising slope, it attempts a short vertical lift while checking head clearance, then confirms a nearby supporting surface. For unobstructed movement, it follows a descending slope within the configured drop limit. Airborne motion, gravity and jumps still use the ordinary swept collision path, now against pixel masks. Over-high walls and low ceilings block movement; unsupported motion resumes gravity.

This is an independently written approximation of Python's `step_body_slopes`, **not a recovered iOS physics engine**. No one-way platforms, tile hazard semantics, dynamic geometry, sprite animation, enemies or game audio are implemented.

## Evidence and tests

All integration fixtures are original synthetic inputs:

- Existing **8 native rectangular-collision scenario groups** pass GCC and Clang; this regression guards the legacy path.
- Existing C99 packed-mask geometry tests pass.
- New native mask gameplay integration covers up/down slopes, high walls, low ceilings, jumping, bad tile IDs and rollback on invalid grids. GCC, Clang and local GCC ASan/UBSan builds pass.
- New 26-frame native C-vs-Python sloped-ground replay compares actor position, feet Y, velocity, grounded, wall and ceiling flags. All 26 frames agree; numeric position/velocity tolerance is 0.001 in these fixtures. Local observed maximum position discrepancy was under 0.000001, and all flags matched exactly.
- The prior four 180-frame C-vs-Python rectangular scenarios and 32 mask geometry checks still pass locally.

The checked-out local collection has 174 host-side Python test methods (not the complete public GitHub suite). Full matrix testing on the current branch remains subject to GitHub Actions.

## Run on host (not Nintendo Switch)

```sh
sh native/run_tests.sh gcc
sh native/run_tests.sh clang
PYTHONPATH=src python -m unittest discover -s tests -v
```

When embedding the C99 core, link **both** `native/src/heman_core.c` and `native/src/heman_mask.c` with your input/render adapter. `hm_mask_grid` data and `hm_world` must remain alive while the simulation runs. The collision code does not allocate memory, load files or depend on iOS/Switch SDKs.

## Remaining limitations before NRO

No Nintendo Switch target, controller adapter, display backend, devkitPro compilation or emulator smoke test exists yet. The C99 engine still lacks camera scripting from the original title and authentic collision parameters. The pixel-mask validation currently rechecks borrowed arrays during gameplay queries; benchmark and streamline validation before using large real-world scenes on constrained hardware. The original iOS assets must continue to remain local/private.
