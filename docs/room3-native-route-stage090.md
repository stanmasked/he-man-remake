# Stage 090 — independent full room-3 C99 gameplay route

This **stacked draft** adds a genuine source-native controller-style
traversal to prepare Issue #97's still-unverified NeXium proof.
It depends on Draft PR #96, itself stacked on room fixture PR #95.

## What the test genuinely does

`native/tests/test_room3_full_route.c` constructs the *actual* authored
56×24 room-3 fixture, launches the unmodified C99 game session at x=48
and feeds ordinary fixed-step rightward input at 60 Hz. It must:

1. Collect the native x158 pickup and activate the native x434 checkpoint.
2. Walk into the x678 hazard, recording **one real hazard**, and observe
   ordinary native respawn at the checkpoint (x434) with recovered HP.
3. Walk right again. Send one fresh A jump at x≥660 and avoid **any**
   further hazard with the real swept platform collision.
4. Earn native HM_EXIT at x842 without moving the player, manipulating
   completion flags, editing the map or directly teleporting near goal.
5. Keep the final native session exactly frozen for three adapter frames,
   then use actual B-reset input to restart the final room from its spawn.

The test fails on a second hazard, missing exit, unwanted mutating FINISH,
incorrect checkpoint or broken replay, with limited printed diagnostics.
A GitHub Actions matrix builds and runs it under both GCC and Clang.

## Critical evidence boundary

**This is not a NeXium/emulator pass.** It establishes only that the
same authored C99 game logic can reach the end of the third room using
normal controller-style input. Stage 1/2 guest progress and stage-3 HUD
pixels have not been proven by this test. A successful native run cannot
confirm real guest timing, guest HID edge delivery or recorded 640×360 PNG
evidence. Issue #97 remains open until the unchanged opt-in three-room
NRO actually completes in pinned NeXium with genuine frame-receiver proof.

The original iOS IPA remains private; the maps, routes and provisional
ability timing are original synthetic training content, not recovered
iOS game behavior.
