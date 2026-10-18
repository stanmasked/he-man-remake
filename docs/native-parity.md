# Stage 015 — C99 / Python trace parity and packed slope masks

This is a **synthetic, source-only regression harness**. It contains no iOS game assets, extracted physics tables, textures, ROMs or copied script data.

## Rectangular-cell physics parity

The new `native/tests/trace_core.c` writes a simple CSV trace for a fully synthetic 40×20 game grid (16-unit solid cells) with four independent cases: `flat`, `wall`, `ceiling` and `ledge`.

`tests/test_native_trace.py` compiles the native C99 trace reporter locally and compares every frame with the existing Python `heman_tools.body_physics.step_body` reference. Camera follow and scene respawn calculations follow the previously implemented Python scene rule. Each scenario has 180 frames: **720 frame-by-frame comparisons**, with exact equality required for frame counters, grounded/wall/ceiling contacts and respawn counts. The tolerance for X, feet Y, vertical velocity and camera positions is **0.035 synthetic coordinate units** to account for native float32 versus Python float64 arithmetic.

This explicitly compares the **shared rectangular-mask subset only**; it is not a proof that Python's slope adhesive gameplay or the original iOS movement logic matches the C99 simulation.

## First packed pixel-mask primitive in C99

`native/include/heman_mask.h` and `native/src/heman_mask.c` expose a separate, read-only, borrowed-array geometry model. The grid stores `uint16_t` tile IDs and each geometry mask uses `uint64_t` row bits. Zero-based bit X marks an occupied pixel; `0xffff` marks an empty tile. It supports tile sizes 1–64 and bounds checks for tile IDs, mask rows, actor dimensions and scan distance.

Capabilities:
- Occupancy checks at integer pixel coordinates.
- Whole-body half-open rectangle overlap.
- Vertical feet sampling at center and both actor edges, with bounded downward scan.
- Fail-closed validation on malformed mask arrays or numerical inputs.
- No dynamic allocation, graphics or file I/O.

Native synthetic tests verify a one-sided wedge, a full tile, out-of-map emptiness, invalid tile IDs, oversized scans and illegal packed rows.

The C mask trace fixture, `native/tests/trace_mask.c`, is compared against Python `MaskedGrid.solid_at`, `MaskedGrid.first_feet_contact` and `body_physics.overlaps_body` across 32 synthetic tile columns. All occupancy/contact observations are compared exactly.

**Important:** the new mask geometry module is **not yet wired into** `hm_step`; gameplay in the C core continues using rectangular solid/empty tiles. This stage establishes geometry parity ahead of a later integration rather than claiming complete slope physics.

## Commands

```sh
sh native/run_tests.sh gcc
sh native/run_tests.sh clang
PYTHONPATH=src python -m unittest discover -s tests -v
```

The GitHub CI matrix includes Python 3.10/3.12/3.13, and native GCC/Clang builds. It also checks the new C-vs-Python comparisons in the Python test job (a C99 `cc` compiler is required and available on standard Ubuntu Actions runners).

## Unresolved before Nintendo Switch

Still needed: integrate pixel-mask collision into the native `hm_step` game loop, compare slope traversal, portable input/render abstraction, devkitPro compilation, emulator test, original-game behavior validation and legal asset handling. No Switch `.nro` is built by this stage.
