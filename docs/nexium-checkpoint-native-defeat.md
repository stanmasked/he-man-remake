# Stage 050 — real NeXium natural combat defeat at activated checkpoint

## Goal

Extend Stage 049's genuine controller-driven checkpoint activation and
manual B-button reset to **automatic respawn after real enemy contact**.

The new opt-in `CHECKPOINT_DEFEAT_PROBE=1` chooses the same asset-free
checkpoint event at world (90, 272), with the enemy patrolling x=86..94
and 30-frame native contact immunity. The normal Switch NRO's world,
combat configuration, game logic and artwork are unchanged.

## Guest event sequence

NeXium's existing HID input file sends **D-pad Right at guest frame 45**
and releases it after guest frame 66. The synthetic hero moves from world
x=50 to x=90, activating the checkpoint before sustained
enemy contact. No further controller input or game-state modifications
occur. The C99 combat loop reduces health via repeated collisions:

| Guest frame | Expected evidence |
| --- | --- |
| 30 | Initial world x=50; 3 HP; yellow checkpoint |
| 80 | Checkpoint green, world x=90; 2 HP; respawns=0 |
| 105 | 1 HP, same checkpoint position |
| 116–130 | Dense real guest PNGs; exactly one 0-HP frame followed immediately by 3 HP and a persistent green native respawn marker |
| 145 | World x=90 (checkpoint, not x=50); 2 HP from a later new contact, one or more respawns indicated |

The test deliberately collects **every frame from 116 through 130**,
rather than inventing an exact death frame based on emulator scheduling.
The strict verifier requires the actual zero-HP frame, next-frame native
recovery, checkpoint world-x location and complete original RGBA8888 HUD.
Enemy health must remain 2/2 throughout.

A fixed (207,250) guest pixel samples the checkpoint flag, to the right
of the hero and enemy sprites. Additional actual game HUD evidence
includes the world-space magenta 192-pixel marker, health ticks, native
respawn counter and color diversity. The original guest captures and
both D-pad HID events must exist in the NeXium runner log.

The original gameplay engine is neither injected nor modified, and all
instrumentation is confined to a temporary pinned upstream Rust runner.

## Continuous integration

`.github/workflows/nexium-patched-checkpoint-defeat.yml` compiles a
real devkitPro source-only NRO, runs patched upstream NeXium CPU/guest
rendering, invokes the fail-closed Python verifier and uploads authentic
guest PNGs/logs even on failure. The ordinary PR CI also compiles Python
source tests; `tests/test_nexium_checkpoint_defeat_instrument.py`
checks both pinned Rust frame receiver paths, the precise HID schedule
and renderer endianness.

A further `tests/test_nexium_checkpoint_defeat_verifier_negative.py` suite
executes the unchanged production verifier on 19 source-only scenarios:
one valid transition and 18 intentionally corrupted outcomes. The fake
image decoder is never a substitute for real NeXium guest evidence.

Two independent pinned NeXium guest runs (39299874720 and
39303499444) captured **world x=90 or x=92 before death**, depending on
whether 20 or 21 actual D-pad ticks were delivered. Both produced
**native recovery at exactly world x=90**. The verifier permits only
those two predeath positions, requires the player to remain stationary
before defeat, and enforces the checkpoint's exact recovery position. Frame 122 displays 0 HP, frame 123 shows 3 HP
and the native respawn counter, and frame 124 displays 2 HP after a
new contact. The first observed failure was the too-strict old x=92 expectation;
the corrected current-head CI must pass independently.

The exact HP timeline above remains a **test hypothesis until current-head
NeXium CI passes**. This is not a recreation of the original proprietary
iOS game's assets or behavior, and does not establish operation on real
Switch hardware. No original IPA, private ROM files, keys, firmware,
commercial art or sound, or patched emulator binaries are published.
