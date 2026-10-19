# Stage 040: real contact damage, invulnerability and respawn in NeXium

This stage verifies the existing synthetic gameplay, not original
iOS He-Man behavior or proprietary media.

## Source-only isolated encounter

An opt-in devkitPro NRO is compiled via

```sh
make -C switch_raster clean all TARGET=heman_damage_probe DAMAGE_PROBE=1
```

The default `heman_raster_probe.nro` scene is untouched. The
damage probe places a tiny patrolling synthetic enemy directly beside
the original player's x=50, both with feet y=272. The *existing*
`hm_combat_step` module decrements player HP on contact with a
30-frame hurt cooldown. `hm_session_step` uses the original
next-frame defeat reset when HP reaches zero.

No guest game state or enemy/player HP is forged from the emulator
test instrumentation. No controller input is injected.

At 60 Hz, independent host execution of this native scene should
produce the following simulated frames:

| Guest frame | Player HP | Respawns | Interpretation |
|---|---|---|---|
| 10 | 2/3 | 0 | First contact already caused one hit |
| 25 | 2/3 | 0 | Still immune during hurt cooldown |
| 40 | 1/3 | 0 | Second real contact after immunity ends |
| 61 | 0/3 | 0 | Third contact defeats player |
| 62 | 3/3 | 1 | Native encounter+player reset on next frame |

The independently authored original raster HUD shows three player
health ticks as actual RGBA8888 pixels at x=18/36/54,y=18.
The enemy health ticks remain 2/2. A new static HUD marker, derived
**only** from `hm_state.respawns`, is dark at (522,62) when zero and
green after any native respawn. The marker is not controlled by the
harness and cannot change from moving background or emulator splash.

## Verification

The host regression `raster/tests/test_damage_respawn_raster.c`
advances the same C99 session, checks immunity, defeat, exact native
respawn counter and actual original renderer pixels under GCC/Clang.

The dedicated workflow
`.github/workflows/nexium-patched-damage.yml` builds the opt-in NRO,
compiles patched original NeXium debug_boot with the unchanged guest
code and captures **real guest frame_rx PNGs** at frames
10/25/40/61/62 (not GUI splash screenshots). The fail-closed verifier
`tools/verify_nexium_damage_pngs.py` requires those exact HP bar
pixel states, the green native respawn marker, unchanged player x,
original enemy full health and guest-frame logging.

Even if this passes, it does not establish that the original iOS
He-Man game was ported, nor GUI presentation, audio, touchscreen,
physical Switch controller, real console execution or game fidelity.
No IPA assets, firmware, crypto keys or patched NeXium executable
are committed.
