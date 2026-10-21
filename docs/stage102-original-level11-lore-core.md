# Stage 102 — first original-game level 1-1 objectives (evidence-driven C99 core)

## What is actually known

The original game is a 2-D side-scrolling action/platform game. A public
2013 guide, authored after playing **Android 1.0.3**, describes two
distinct collectible lore fragments in its first level, *Dungeons 1-1*:

| Objective | Reported reward | Reported accessibility |
| --- | --- | --- |
| L001, hidden left near the level start | Bio Skeletor | Reach a hidden passage behind destructible blocks and a Horde obstacle; **Wall Crusher** is needed |
| L002, midway along the path | Game Concept Art 09 | No special ability required; reachable across a block floor under a low ceiling |

Source:
https://jtquisenberry.github.io/Video-Game-Documents/Android/MOTU_He-Man_The_Most_Powerful_Game/MOTU_He-Man_TMPGITU_Walkthrough.html

The guide documents both classic directional/jump/attack controls and
gesture controls. It **does not** provide exact object coordinates,
collision polygons, sprite frames, animation rates, movement speed,
camera origin or iOS 2.0.0 physics. It explicitly says it was authored
while running Android 1.0.3, with iOS parity only *believed* by its author.
Nothing here is claimed to be measured iOS gameplay.

## Implemented in source

`native/include/heman_level11_lore.h` and
`native/src/heman_level11_lore.c` introduce a portable,
allocation-free **objective/progression subsystem** for the two lore
rewards, without hardcoding hypothetical physical placements.

It supports independent grant of the Wall Crusher ability, a gate that
cannot be broken by a normal attack before the unlock, and pickups
that require caller-confirmed physical overlap. The freely accessible
mid-level collectible is not falsely gated by the unlock. Both rewards
are collected only once. Invalid, fabricated or out-of-range input and
inconsistent states are rejected **without mutating state**.

The subsystem deliberately does **not** decide where the hero is,
interpret tilemap collision bits, grant unlocks, choose iOS save/persist
semantics, load original images, or modify any currently working NRO.
Those responsibilities require actual private source data and further
independent evidence from genuine iOS gameplay. The caller remains
responsible for real collision/contact verification.

The standalone C99 regression uses synthetic contacts and reward IDs;
it checks both collection orders, gating, duplicate pickups, bad
`wall_crusher` values, unearned hidden rewards, stale flags and explicit
initialization without assuming unknown original save data semantics.

## Why this matters

This is the first **documented original level 1-1 mechanic**, rather
than a fourth invented synthetic training room. It creates a concrete
integration point for genuine, privately processed source-level map
and animation data. It does not pretend the original level is already
playable or that public walkthrough descriptions substitute for the
user's lawful IPA archive.

The user's `He-Man-v2.0.0.ipa` is **not available in the current
runtime**; only previously recorded private inspection metadata is
known. The public repository receives no original IPA, maps, assets,
screenshots or derived level coordinates. More exact geometry must pass
the existing eight-category gate in `docs/first-level-evidence-gate.md`
before implementation.

## Test

    sh native/run_tests.sh gcc
    sh native/run_tests.sh clang

Both compilers use the same source C99 rules that can later be
linked into a strictly opt-in, source-backed level 1-1 Switch build.
No existing game build selects these rules yet.
