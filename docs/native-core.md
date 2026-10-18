# Stage 014 — portable, independently authored C99 core

This module is the first **platform-neutral game-loop experiment**, intended as groundwork for a later Nintendo Switch homebrew adaptation. It is **not** a translation of the original He-Man iOS executable and is **not** a playable Switch port.

## Interfaces

- `native/include/heman_core.h`: public structs for borrowed collision-grid and event arrays, immutable world settings, controller-like input and mutable scene state.
- `native/src/heman_core.c`: deterministic step and validation with no graphics, sound, OS service, memory allocation or file access.
- `native/tests/test_core.c`: eight scenario groups using a hand-written 64×24 cell test course.
- `native/run_tests.sh`: one-command GCC/Clang build and test using a disposable temporary directory.

The C library accepts a **binary occupancy grid** (0 empty, 1 solid) of *axis-aligned rectangular cells*, not image-based slopes. It updates gravity, feet grounding, static left/right wall contact, head contact, jumping, camera following and event flags. Checkpoints, pickups, triggers, hazards, exits and manual resets use synthetic rules. Event progress is stored in bitfields for at most 32 entries. It does not draw anything, process keyboard input, implement SDL2, load the original IPA, or include licensed resources.

The caller retains all world pointers for the entire simulation. The native API has bounded sizes: at most 200,000 cells, 32 events, tile sizes 1–64, body dimensions up to 128 and swept travel at most 512 units per step. World validation rejects malformed spawn positions, event coordinates and overlapping checkpoint spawns. Invalid step inputs leave the supplied state unchanged.

## Build on Linux/macOS (host only)

```sh
sh native/run_tests.sh gcc
sh native/run_tests.sh clang
```

CI also runs these two compilers in separate jobs alongside the existing Python matrix. A local additional GCC AddressSanitizer/UndefinedBehaviorSanitizer test passed. These are **eight native scenario groups**, not full parity tests with the 190 Python scenarios.

## Architectural gap

Stage 011–013 Python logic remains the current functional desktop demo. The C library is a **separate proof-of-portability**, not yet used by the Tkinter app. It intentionally lacks pixel masks, slopes, one-way ledges, animation, health, combat, original camera scripting, input backends and original data import. Exact equality between Python and C trajectories is not claimed.

Before attempting an NRO, the next work should implement slope/alpha-mask parity with existing Python fixtures, add trace comparison between languages, define a platform input/render adapter and then introduce an optional devkitPro compilation job. A compiler passing GCC/Clang alone is **not evidence of Switch compatibility**.
