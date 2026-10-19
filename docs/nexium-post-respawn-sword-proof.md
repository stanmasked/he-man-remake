# Stage 046 — genuine X-button sword combat after native respawn

This is a **new guest-emulated integration test**, distinct from the host-only
stage 043 controls test and the stage 044 guest post-respawn movement proof.

The opt-in `DAMAGE_PROBE=1` graphical devkitPro NRO uses the original shared,
independently authored C99 gameplay/rendering sources. Its synthetic enemy
touches the player on frames 1, 31 and 61; native recovery occurs on frame 62.
No copyrighted iOS game data is present.

## Genuine NeXium inputs and screen captures

The instrumentation changes only NeXium's **temporary pinned debug_boot Rust
checkout**. The game NRO's C engine and all state remain unchanged.

| Guest frame | Event | Expected player HP | Expected enemy HP |
| --- | --- | --- | --- |
| 62 | Capture after native respawn | 3/3 | 2/2 |
| 65 | Inject X press through NeXium HID file | — | — |
| 74 | Release X | — | — |
| 79 | Capture after first real sword press | 2/3 | 1/2 |
| 84 | Inject second X press | — | — |
| 93 | Release X | — | — |
| 115 | Capture after second real sword press | 2/3 | 0/2 |
| 170 | Capture stable defeated enemy | 2/3 | 0/2 |

The expected stable player HP requires the second attack to defeat the
enemy *before* the second post-respawn contact can connect. That timing
is a hypothesis checked by CI, not a claim of emulator success.

The Python verifier requires authentic 640×360 guest frame_rx PNGs,
exact player and enemy health-bar RGB ticks from the same C renderer,
a persistent native green respawn-counter marker, 192 magenta
world-x marker pixels at world x=50, and unchanged player position.
It also requires all genuine frame captures and four precise HID events
in the NeXium runner log.

The separate `.github/workflows/nexium-patched-post-respawn-sword.yml`
runs a genuine devkitPro NRO in a patched, pinned NeXium execution
backend and uploads guest PNGs and logs even if verification fails.

`tests/test_nexium_post_respawn_sword_instrument.py` locks both pinned
frame-receiver hooks, capture and input schedules, the inability to
double-instrument upstream Rust code, and the original little-endian
RGBA renderer color contract.

## Boundaries

A successful experiment would prove just this synthetic encounter and
the guest-emulated HID-to-renderer path, **not original iOS game fidelity**
or execution on physical Nintendo Switch. No original user IPA, extracted
proprietary assets, firmware, keys or emulator binaries enter the
public Git repository.
