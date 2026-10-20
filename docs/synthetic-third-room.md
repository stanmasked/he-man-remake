# Stage 088 — standalone third synthetic training room

Stage 088 adds a third **independently authored** C99 map but does **not**
enable it in the existing Switch gameplay, NeXium proofs or two-room
completion logic. Its purpose is to test a new room's world data and
atomic setup before extending the main course.

- 56×24 tiles, 16 world units each; solid floor on row 18
- Three isolated elevated platform runs, all written from scratch
- World spawn at (48,288), pickup at x158, checkpoint at x434,
  hazard at x678, and goal trigger x842
- A separate authored enemy patrol between x292 and x370 with 3 HP
- Existing C99 walking, jump, gravity, combat and hazard rules; no
  proprietary level resources, exact native iOS coordinates or images

The exported initializer validates both the proposed physics world
and combat config **before any caller state is changed**. Invalid
pointers or wrong-sized tile buffers do not modify caller-owned memory.
Valid output points to the caller's persistent tile buffer, never the
function's private stack.

The corresponding host test verifies all exact cells, sentinel and
padding guards, output determinism, authentic native movement from
spawn through the pickup/checkpoint/hazard, plus separate goal-event
reachability from a near-goal test state. The latter is explicitly
**not a full human/controller route proof**.

Run:

    native/run_tests.sh gcc
    native/run_tests.sh clang

## Next integration step

After PR #94 proves the second-room ZL strike through actual NeXium
frames, implement a separate opt-in three-room stage selector and
continue on A after room-2 completion; update FINISH so it is earned
only on the true final room, with testable transitions, fresh input
edges and native atomic session initialization. The present two-room
NRO and its confirmed B retry must remain unchanged.

Then require a real third-room guest traversal, not just host
`hm_step` event checks or an NRO cross-compile.

This file is source-authored training content. The owner's original
iOS IPA and all extracted game assets remain private and never enter
GitHub or CI.
