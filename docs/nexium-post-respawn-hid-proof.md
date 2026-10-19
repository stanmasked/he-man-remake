# Stage 044 — real D-pad Right after defeat and native respawn (NeXium)

This experiment is deliberately separate from the host-only C99 Stage 043.
It runs the existing source-only `heman_damage_probe.nro` in **actual patched,
pinned-upstream NeXium guest execution** and does not modify its gameplay code.

## Guest session

The opt-in encounter places a synthetic enemy at contact range. With no input,
the real gameplay loop causes three hits (frames 1, 31, 61), then uses its
normal next-frame recovery (frame 62).

The instrumenter modifies only the *temporary upstream Rust runner* to:

- Capture guest `frame_rx` RGBA PNGs at frames **62, 90, 160, 220**.
- Write `buttons=DRIGHT` through NeXium's existing
  `NEXIUM_HID_INJECT` mechanism after receiving frame **80**.
- Release Right with `buttons=` after receiving frame **120**.
- Log both injected HID actions and all four real guest screenshot events.

The synthetic course contains a health pickup at x=170. Releasing Right at frame 120 keeps the player short of that pickup, so the test isolates movement/stop behavior without incidental healing.

The production guest NRO, combat mechanics, native death/respawn logic and
raster HUD have **no special-case input or state overrides**.

## Independent fail-closed guest verifier

`tools/verify_nexium_post_respawn_pngs.py` requires:

| Guest frame | Hero HP | Respawn marker | World-x marker |
| --- | --- | --- | --- |
| 62 | 3/3 | Green (counter ≥ 1) | Spawn ~125.5 px |
| 90 | 2/3 | Green | At least 12 px beyond frame 62 |
| 160 | 2/3 | Green | At least 36 px beyond frame 90 |
| 220 | 2/3 | Green | Stable within 8 px of frame 160 |

All four frames must retain complete **2/2 enemy HP**, exactly three authentic
player HUD tick colors, 192 magenta marker pixels, ≥8 scene colors, and an
unchanged native respawn indicator. The runner log must record frame captures
and both controller actions at frames 80 and 120.

This is more evidence than a frame count, guessed character position or
synthetic desktop screenshot. The verifier rejects missing/incorrect guest
pixels and log records. Independent Python tests lock the dual pinned Rust
receive paths, exact frame schedule, re-instrumentation rejection and the
original renderer's little-endian RGBA pixel values.

## CI

Use the dedicated
`.github/workflows/nexium-patched-post-respawn.yml` workflow: it builds a
real devkitPro test NRO, applies the pinned NeXium loader patch in a temporary
checkout, executes actual emulated CPU instructions, captures guest frame
bytes and uploads logs/PNGs, including on failure.

The expected movement thresholds are a **test hypothesis**, not a verified
performance or controller-latency claim until this exact CI run succeeds.

## Privacy and scope

No original user-owned iOS IPA, original sprites/levels/music, game assets,
private derived reports, Nintendo firmware/keys or patched emulator binaries
are committed to this public repository. Passing this synthetic guest proof
would still not establish original iOS He-Man gameplay fidelity or running on
physical Nintendo Switch hardware.
