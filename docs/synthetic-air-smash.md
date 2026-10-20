# Stage 086 — optional source-authored ZL aerial strike

No legacy iOS device is required. The original owned He-Man IPA remains
private; the 2013 Android guide's Aerial Smash is only a **qualitative
reference**. All durations, enemy hit-distance and landing effects here
are NEW, provisional native C99 rules, not recovered iOS mechanics.

To build the **independent** second-room gameplay variant:

    make -C switch_raster clean all \
      TARGET=heman_air_smash_probe CHAIN_PROBE=1 AIR_SMASH_PROBE=1

The standard one-room NRO and existing two-room `CHAIN_PROBE=1` use their
existing action mappings. Only `AIR_SMASH_PROBE=1` assigns ZL to a new
air action in the synthetic second room. The other mappings are unchanged:
D-pad Left/Right move, A jumps, X attacks, ZR dashes, Minus pauses, B
restarts and Plus exits.

### Experimental skill rules

- Grounded ZL is ignored. A fresh ZL DOWN edge while airborne, while
  alive/not completed, and off cooldown arms one descending strike.
- The attack uses the REAL collision and swept landing engine; it raises
  downward vertical velocity to a provisional 520 world units/second.
- A genuine landing triggers an 8-frame feedback state, one impact count
  and at most one damage point on a nearby independently-authored enemy.
- The attack has a 50-frame recovery, not spent during pause/frozen FINISH.
- Respawn cancels an active strike and its recovery; completing the final
  room freezes all ability state, and B starts a new session.
- Calls use copy-then-commit, so rejected physics/combat/input leaves
  game, dash, pause and air-strike state byte-for-byte unchanged.

The ability cannot modify solid cells, extract assets, replace hazard
collision or fabricate original gameplay. The second-room geometry and
enemy placement remain the source-authored fixtures already tested.

### Verification levels

`native/tests/test_air_smash.c` exercises actual C99 physics, native
landing, cooldown, pause precedence, one enemy HP impact, B respawn,
terminal B replay, and rollback. GCC and Clang run the identical source.

The optional NRO's **cross-compilation** is a separate gate from
actual NeXium guest-controller optical proof. Until a new real guest
test is green, do not claim that NeXium has confirmed ZL activation.
No iOS engine parity or original-game frame timing has been measured.
