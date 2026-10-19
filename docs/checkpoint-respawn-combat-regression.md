# Stage 048 — checkpoint recovery preserves a live combat session

This source-only regression uses the **same independently authored C99 physics,
combat, session and RGBA8888 raster code** linked into the synthetic Switch NRO.
It proves checkpoint behavior without modifying HP directly and without using
original iOS game assets.

## End-to-end host scenario

1. Start at world x=50 with 3/3 HP; checkpoint at x=90 is initially yellow
   and not activated (checkpoint index -1).
2. Walk to x=90; the ordinary physics event system activates checkpoint 0.
   The renderer's checkpoint flag turns green while enemy HP remains 2/2.
3. Walk onward to x=110, inside the enemy's patrol x=106..114, then wait
   for *three real contact hits* with a 30-frame immunity cooldown.
   At zero player HP, the hero is still at x=110 and respawns=0.
4. Before recovery, pass invalid combat settings. The session update must
   reject the step with **byte-for-byte rollback**, retaining checkpoint 0.
5. Attempt recovery while holding Left + Jump + Sword. The next native frame
   must suppress those inputs, restore full HP and the enemy encounter, and
   respawn at the **activated checkpoint x=90**, not at initial spawn x=50.
6. Move from x=90 to x=104 using actual physics. Inflict two ordinary
   C99 sword hits after the standard cooldown and defeat the enemy 2→1→0.
7. Walk toward a world hazard at x=150. Its event initiates a *second*
   native respawn and resets the enemy while preserving checkpoint 0,
   again returning the hero to world x=90.

The test inspects the **actual portable raster output** after each major
transition: checkpoint flag pixel yellow→green, every player and enemy HP
HUD tick, the world-space magenta X indicator, and the native green
respawn counter indicator.

## Run

Run the existing native matrix using both compilers:

    sh native/run_tests.sh gcc
    sh native/run_tests.sh clang

`raster/tests/test_checkpoint_respawn_combat_raster.c` is included in the
standard `native/run_tests.sh` script on every GCC/Clang CI run.

## Important scope

Stage 048 is a **host native C99 gameplay + raster** regression, not yet
a NeXium guest-HID checkpoint capture, original iOS-game reconstruction,
or a physical Switch test. Previous stages prove separate emulator input
scenarios; this stage extends gameplay state coverage without claiming
a new emulator result. No original IPA, extracted textures/sound, Nintendo
keys, firmware or private-derived game files are committed.
