# Stage 039 — verify real X-button sword hits and opponent HP in NeXium

The previous steps proved simulated D-pad Right motion and A-button
jumping/landing using actual PNGs from **guest 640x360 frame_rx** in
patched NeXium. This stage tests a third Nintendo Switch control:
**X for a melee sword attack**, including real gameplay state changes.

## Deliberately separate test encounter

The ordinary game binary `heman_raster_probe.nro` and its world remain
unchanged. CI **additionally** compiles `heman_attack_probe.nro` by
invoking:

```sh
make -C switch_raster clean all TARGET=heman_attack_probe ATTACK_PROBE=1
```

The opt-in `HM_ATTACK_PROBE` flag configures a short enemy patrol
(x=66..74 instead of the ordinary x=220..355). The actual melee-hit
logic, player movement, enemy health state and shared renderer are
identical to production. The player's spawn remains x=50 and feet
y=272, within the sword's 30-unit reach but outside the enemy's
9-unit contact radius. This isolates the attack button rather than
mixing it with navigation or contact damage.

The C99 host test `raster/tests/test_attack_raster.c` independently
confirms that two genuine calls through `hm_session_step()` reduce
enemy HP from 2 to 1 then to 0, and that the real renderer updates
the two health pixels without harming the stationary player.

## Real virtual controller experiment

The pinned NeXium `debug_boot` running with the verified NRO loader
fix receives `buttons=X` using NeXium's existing
`NEXIUM_HID_INJECT` interface (not a guest memory override). A Rust
test-only source instrumenter in the temporary checkout schedules:

| Received guest frame | Controller | Evidence |
| --- | --- | --- |
| 30 | No button | Enemy health is 2/2 |
| 45 | X pressed | First strike |
| 58 | X released | Allows a new edge-triggered strike |
| 65 | No button | Enemy health is 1/2 |
| 85 | X pressed again | Second strike |
| 98 | X released | All controls neutral |
| 120 | No button | Enemy health is 0/2 |

The guest output itself is saved as PNG at frames 30/65/120. The
independent verifier `tools/verify_nexium_attack_pngs.py` samples both
top-HUD enemy health ticks at pixels (226,18) and (244,18). On the
actual little-endian RGBA8888 framebuffer, live tick color is RGB
(109,200,225) and empty tick color is RGB (81,59,73). It requires
both-live -> one-live -> both-empty, plus unchanged player HP and
world-space x and four precisely observed controller events.

Success verifies **two real virtual-controller X attacks were processed
by independently authored Switch homebrew gameplay and rendered**.
It does not prove physical Switch input, genuine iOS He-Man combat,
original sound/art, GUI compatibility or release readiness.

No original user-owned IPA, private game assets, Switch keys/firmware or
patched NeXium executables are published to public GitHub.
