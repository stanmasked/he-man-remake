# Stage 043 — controls and sword combat after native respawn

This host-only test exercises the same independently authored C99 physics, combat and 640×360 RGBA renderer linked into the synthetic Nintendo Switch NRO. No original iOS game content is used.

## Deterministic sequence

With the hero at x=50 and an enemy patrolling x=46..54, contact damage uses the existing 30-frame immunity and eventually causes native defeat.

| Frame | Action | Expected outcome |
| --- | --- | --- |
| 61 | Third contact | Hero HP 0/3 |
| 62 | Recovery while holding Left, Jump and Sword | HP 3/3, respawns=1, encounter restored; held controls suppressed |
| 63 | Right input | Player x=52, fresh contact HP 2/3 |
| 74 | Right input over twelve frames | Player x=74, facing right |
| 76 | Two frames of left input | Player x=70, facing left |
| 77 | Sword press facing opponent | Enemy HP 1/2 |
| 95 | Second sword press after cooldown | Enemy HP 0/2 |
| 110 | Idle after defeat of enemy | Player HP 2/3, enemy HP 0, respawns=1 |

The native reset clears the grounded flag on frame 62; grounding returns on the following step. The test deliberately submits Left, Jump, and Sword during recovery and asserts no leaked motion, facing change, or sword hit. The test checks player and enemy HP pixels, world-x magenta marker, grounded world-y yellow marker and genuine respawn counter marker.

Host checks are part of both existing commands:

    sh native/run_tests.sh gcc
    sh native/run_tests.sh clang

The new file is raster/tests/test_post_respawn_controls_raster.c, exercising the unchanged core and raster renderer without private files or Nintendo SDK.

## Limitations

These are host C99 and framebuffer assertions, not real NeXium controller events. The opt-in emulator contact-damage PNG proof is separately tracked in PR #40. No physical Switch test or faithful iOS port is claimed. The privately owned IPA, media assets, keys and firmware stay off GitHub.
