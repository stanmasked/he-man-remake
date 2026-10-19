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
| 133 | X pressed — first sword attack after natural respawn |
| 140 | X released |
| 149 | X pressed — second sword attack after cooldown |
| 156 | X released |

Both X presses deliberately occur **after** the 116–130 dense death-window
captures. The previous first press at frame 129 risked damaging the enemy
before frame 130, contradicting the verifier's full enemy-HP invariant
through natural death/recovery even if guest combat worked correctly.
The revised presses are at frames 133 and 149 (16 frames apart, beyond
the 15-frame sword cooldown). The second attack is intentionally before
roughly frame 153–154, when 30-frame contact immunity can end after
the new hit at frame 123–124. This avoids an input-versus-contact
ordering race without changing the game engine.

Guest PNG captures are scheduled at 30, 80, 105, every frame 116–130,
140, 160, and 185. The verifier *discovers* the death frame within
the 116–130 window, requires immediate recovery, the original green
checkpoint flag, stable world-x=90 or 92 before death, but exact world-x=90
**after recovery**, and native green respawn counter, and
inspects each rendered HP tick. Expected enemy progression: 2 HP
through frame 130 → 1 HP by frame 140 → 0 HP by frame 160, remaining
defeated at frame 185. Player HP remains 2 after the enemy is defeated.

The timing is a **test hypothesis** until the pinned patched NeXium
workflow provides real guest framebuffer evidence. Three genuine NeXium Stage 050 runs have shown 20, 21 or 22 D-pad
movement ticks (world x=90, 92 or 94) before defeat. They recover exactly
at checkpoint world x=90, but the observed death/recovery frame can
differ by one (122→123 or 121→122). The verifier accepts only a bounded,
physically quantized rightward approach and requires exact recovery.
The post-recovery X-button victory remains a test hypothesis until the
stage's own genuine NeXium workflow passes.

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
