# Stage 052 — two true sword hits after natural checkpoint defeat in NeXium

This experimental **source-only Nintendo Switch homebrew** integration stage
extends Stage 050 (checkpoint activated via genuine D-pad input, natural
defeat on three enemy contacts, next-frame native respawn at x=90) with
two genuine X-button presses to defeat the enemy **after** respawn.

No gameplay code changes, private IPA assets, emulator-memory overrides
or game-state injections are introduced. The opt-in Stage 050 NRO builds
from exactly the same C99 physics, combat, session and raster sources.

## Guest controller and capture schedule

| Guest receiver frame | Action |
| --- | --- |
| 45 | D-pad Right begins movement toward world checkpoint x=90 |
| 66 | D-pad released, hero remains at x=90 in enemy contact range |
| 122 | Captured native 0-HP defeat in previous genuine NeXium run |
| 123 | Captured native 3-HP automatic checkpoint respawn in prior run |
| 129 | X pressed — first sword attack after natural respawn |
| 136 | X released |
| 148 | X pressed — second sword attack after cooldown |
| 155 | X released |

Guest PNG captures are scheduled at 30, 80, 105, every frame 116–130,
140, 160, and 185. The verifier *discovers* the death frame within
the 116–130 window, requires immediate recovery, the original green
checkpoint flag, stable world-x=90 or 92 before death, but exact world-x=90
**after recovery**, and native green respawn counter, and
inspects each rendered HP tick. Expected enemy progression: 2 HP
through frame 130 → 1 HP by frame 140 → 0 HP by frame 160, remaining
defeated at frame 185. Player HP remains 2 after the enemy is defeated.

The timing is a **test hypothesis** until the pinned patched NeXium
workflow provides real guest framebuffer evidence. Two genuine NeXium Stage 050 runs have shown 20 or 21 D-pad steps
before release (world-x=90 or 92); both return exactly to world-x=90 on
recovery at frame 123. The original checkpoint death→recovery transition
on frames 122→123 is confirmed in both saved guest captures, but a new
X-button attack victory is not confirmed until this stage's CI passes.

`.github/workflows/nexium-patched-checkpoint-sword.yml` cross-builds
a genuine devkitPro NRO and runs the pinned NeXium Rust AArch64 backend,
with controller events through its existing HID file. Both Rust frame
receiver paths are pinned; authentic frame logs, exact full HID lines,
and actual PNGs are mandatory. Artifacts are saved even if verification
fails.

A new portable native test, `raster/tests/test_checkpoint_postdefeat_sword_raster.c`,
replays the unchanged checkpoint encounter using actual C99 movement,
three contact hits, native recovery and two sword presses. It checks
checkpoint flag and player/enemy HP pixels in the original 640×360
renderer. `native/run_tests.sh` runs it on both GCC and Clang. This
is independent host evidence, NOT guest HID proof.

`tests/test_nexium_checkpoint_sword.py` provides ten fast host-side
regression tests for the original renderer colors, dual NeXium Rust
receiver patches, exact events and fail-closed rejection of missing
frames, incorrect HP and fake X releases. These use mocked image
decoders, NOT real emulator results.

This proves only the new independently authored synthetic gameplay
prototype in an emulator if CI passes — it does not prove fidelity to
the original iOS He-Man game or compatibility with real Switch hardware.
The proprietary user IPA, Nintendo keys, firmware and copyrighted art
remain outside the public repository.
