# Stage 054 — genuine NeXium B retry after checkpoint sword victory

Stage 053 already verified the **manual B retry after victory** in the
real C99 session, combat and RGBA8888 renderer under GCC and Clang.
That evidence is host-side: it does **not** prove that the NeXium guest
controller and display handle the entire second encounter.

This experimental branch adds that missing, genuinely emulated sequence
to the existing Stage 052 **unchanged source-only devkitPro Switch NRO**:

| NeXium guest frame | Event |
| --- | --- |
| 45 / 66 | D-pad Right pressed/released; activate x=90 checkpoint |
| 116–130 | Inspect native 0-HP defeat and next-frame x=90 recovery |
| 133 / 140 | First original X attack / release |
| 149 / 156 | Second original X attack / release |
| 185 | Original enemy defeated (0 HP), hero alive (2 HP) |
| 194 / 201 | **New B manual reset / release** |
| 190–211 | Dense real guest PNG captures around B and first retry |
| 205 / 212 | **New first X attack / release** |
| 221 / 228 | **New second X attack / release** |
| 220 | Expect enemy HP 1, hero HP 2 |
| 242 / 270 | Expect enemy HP 0, hero HP 2, world x=90 |

Both X presses occur after the B release and are 16 guest frames
apart (the C99 sword has a 15-frame cooldown). The second X is also
scheduled before the next potential 30-frame contact hit after B,
avoiding a false defeat due to guest input-delivery jitter. Genuine input edge
delivery can shift by a frame; the PNG verifier discovers the exact
first **3 hero / 2 enemy HP** reset frame in the 195–204 capture
window instead of assuming one HID/guest scheduling identity.

## Fail-closed evidence contract

The new `tools/verify_nexium_postvictory_b_pngs.py` **first runs
the established Stage 052 verifier** on the original frames and exact
D-pad/X HID logs. It then requires all new source-authored guest
frame_rx PNGs (including 190–211), their genuine frame log records,
and exact complete B/X press-and-release log lines.

After victory, the enemy may not restore before the B press. An
actual reset must visibly restore the combat HUD to hero/enemy HP
3/2, then fresh sword attacks must produce enemy HP **2→1→0**.
All sampled frames must preserve world x=90, active green checkpoint,
and native respawn HUD marker; the hero must stay alive after the
second victory. Wrong/forged HID releases, fake logs, missing PNGs,
premature enemy damage, and incorrect HP fail closed.

The real NeXium proof is the workflow
`.github/workflows/nexium-patched-postvictory-b.yml`, which checks
out the pinned temporary upstream runner, modifies only *that
checkout's* two real frame receivers, builds the actual existing
devkitPro NRO, and uploads real guest PNG/log evidence even if the
verifier fails.

`tests/test_nexium_postvictory_b.py` is a *host-side mock* unit
suite, **not evidence of successful emulation**. The draft PR must
not merge before current-head Python CI and the authentic NeXium
workflow both succeed. The experiment can expose a real scheduling
difference that requires adjusting only the *test* event timing, not
overriding game RAM or fabricating frames.

No proprietary original iOS IPA, commercial art/audio, Nintendo
firmware, keys or console-exclusive data is included in GitHub.
