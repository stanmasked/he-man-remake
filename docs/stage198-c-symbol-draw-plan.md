# Stage198 — portable C99 Symbol draw-plan ABI

Stage198 carries the validated Python command-plan contract into a small C99 interface that a future Switch graphics adapter can consume. It does not connect the command list to the current synthetic renderer or claim to draw original game assets.

## C command ABI

Added `native/include/heman_symbol_draw_plan.h` and `native/src/heman_symbol_draw_plan.c`.

Each `hm_symbol_draw_command` contains:

- contiguous source-order index and resolved cut handle;
- raw normalized UV endpoints (negative or greater than 1 is allowed);
- already-clamped vertex RGBA values;
- explicit blend-override enabled/sentinel fields;
- Symbol mask;
- rotation, X/Y offset and independent X/Y scale values.

The validator rejects missing command storage, missing/reordered indices, non-finite UV/color/transform fields, color channels outside [0,1], and inconsistent blend sentinels. It does not clamp UVs or reject negative/zero scales.

`hm_symbol_draw_plan_visit` validates the **entire** command list before invoking any callback, then visits drawable symbols in original order and skips a command only when `symbol_mask & active_mask` is nonzero. Callback errors stop iteration and report the number of successfully completed callbacks. Input commands are never modified.

## Validation

Added `native/tests/test_symbol_draw_plan.c` and connected it to `native/run_tests.sh`, so the existing strict GCC/Clang C99 workflow compiles it with `-Wall -Wextra -Werror -pedantic`.

The new synthetic tests cover empty/null plans, source order, unclipped UVs, non-finite values, RGBA range, negative scales, blend sentinel rules, mask filtering, whole-plan validation before callbacks, early callback failure and input immutability. No IPA, original assets or private per-record data is used.

## Scope boundary and next step

This establishes a C ABI and a fail-closed dispatch boundary, but no code yet serializes the Python plan into C structs or connects it to GPU calls. The next graphics step remains resolving exact native quad construction and the per-Symbol vertex buffer layout, then adding a small synthetic geometry bridge and tests before private source-frame comparison.
