# Stage 018 — validated-once native mask collision fast path

## Problem

Before this change, the native C99 gameplay loop called the fully checked packed-mask body collision function for **every pixel sweep sample**. Each call walked the entire mask grid and mask-row table again. This was safe but repeatedly performed O(cells + mask rows) work inside a pixel-level movement loop.

## Change

- At the start of each C99 gameplay tick, `hm_step` still validates the entire borrowed mask-grid structure with `hm_mask_valid`.
- The internal sweep, ground-support and initial actor-overlap checks then use the **prevalidated** collision helper for that same tick, testing only body-local mask pixels.
- Public `hm_mask_body_overlap` remains fully checked and still returns an error for invalid geometry.
- A new C99 test checks that corrupt tile IDs or out-of-range mask rows **between ticks** are rejected at the next step and do not alter the previous actor state.
- This optimization assumes the caller does not concurrently mutate the borrowed mask arrays while one step executes. An immutable or externally synchronized world is required.

## Reproducible synthetic benchmark

`native/tests/bench_mask_step.c` creates a synthetic **300x19 grid** with 32-unit tiles and one horizontal solid layer. It simulates 900 frames with no game art or source data. The benchmark uses standard C `clock()` CPU time and produces a final-state fingerprint.

One local GCC -O2 Linux run on the same host reported:

| Version | 900 simulation frames, CPU time |
|---|---:|
| Before the optimisation | 0.074808 seconds |
| After the optimisation | 0.017046 seconds |

Ratio: **approximately 4.39x faster** in this single local experiment. Both versions produced the same printed final X, feet Y, camera X and respawn count. This is **not** a Nintendo Switch performance claim and not a stable CI timing guarantee.

The CI records benchmark results without rejecting builds on timing alone; hosted CPU speed varies. Run locally:

    sh native/bench_mask_step.sh gcc
    sh native/bench_mask_step.sh clang
    sh native/run_tests.sh gcc
    sh native/run_tests.sh clang

## Switch development

The optional `switch/` directory contains a minimal devkitA64/libnx *console probe* that passes controller buttons into `hm_step` on a synthetic solid-cell world. No original level assets are included. The SDK is **not installed in this environment**, so its NRO build has not been attempted or verified. See `switch/README.md`.

## Scope limits

The Python Tk window still has its own simulation implementation. The C99 probe does not offer original iOS graphics, audio, sprites, enemies, actual player constants or an original-data level loader. Its packed-mask slopes are a synthetic approximation, and this performance optimisation does not validate original gameplay behavior.
