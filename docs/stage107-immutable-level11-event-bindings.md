# Stage 107 — immutable lore-event identities in the native session

In Stage 106, the experimental C99 session pinned every event coordinate
and world collision array, but **did not pin the three lore role indices
themselves**. Both original-game-described rewards have native event
kind `HM_PICKUP`, so swapping their indices would still pass ordinary
event-type validation while assigning the wrong lore reward.

This stage adds two independent, zero-allocation session invariants:

1. Save `sealed_bindings` at session initialization. Before each frame
   and each Wall Crusher grant, compare the actual gate/Bio/Concept Art
   event indices with the saved indices. A swap of *two valid*
   `HM_PICKUP` objects is now rejected even if its type checks succeed.
2. Save `sealed_world` pointer identity. Replacing the session's world
   descriptor with a copied struct that happens to point to identical
   arrays is rejected, even though the Stage 106 content fingerprint
   would have remained equal.

The existing `hm_step()` physics replay, frame/lore atomic rollback
and attack 0→1 edge latch are unchanged. The additions only run in
the isolated optional Level 1-1 source-research session; no stable
two-room Switch NRO, proven three-room NeXium NRO or production map
geometry was changed.

The C99 tests intentionally swap two same-kind pickup roles, then
verify that both the frame step and upgrade grant reject the swap
without mutating player, attack state or rewards. A test also replaces
the world descriptor with an identical copy and demonstrates the
same fail-closed result. Restoring the original role assignment or
world descriptor permits normal C99 play again, including only the
free Concept Art pickup on the synthetic test route.

The session field copies are an **accidental integration mistake
detector**, not an anti-cheat system or evidence of original iOS
source provenance. The structs are C99-memory writable by their
caller, so malicious code can alter both the active and sealed fields.
All test map coordinates are fictional. Genuine level identity,
source-derived object ownership and original collision timing are
still blocked in [Issue #110](https://github.com/stanmasked/he-man-remake/issues/110).

Verification reuses the existing GCC/Clang native test suite and
ASan/UBSan workflows, avoiding a redundant new compiler pipeline.
