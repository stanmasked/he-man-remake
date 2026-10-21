# Stage 105 — scene-owned C99 player/input session for Level 1-1

Stage 104's physics-contact receipt validated a real source `hm_step()`
transition, but accepted a separately supplied `attack_fresh_press`
boolean. A caller could mistake an attack button held for several frames
for multiple fresh sword commands.

Stage 105 adds an opt-in `hm_level11_native_session` owning:

- The existing C99 `hm_state` player + `hm_lore_state`
- Three independently bound native event indices
- The previous attack-button level, initially released
- A borrowed immutable `hm_world` reference

`hm_level11_session_step()` now accepts only a button **level**
(`attack_down=0` or `1`), motion input and timestep.
The session computes the fresh edge **only on 0→1**, advances the
actual `hm_step()` and asks the existing Stage 104 contact verifier
to independently replay the exact physics step before any lore
state can change. An invalid input/world binding/step cannot commit
player motion, lore awards or the button latch. A held attack
through the gate cannot open it; the player must release and attack
again, while legitimately touching its active native sensor and
already owning Wall Crusher.

The session also supports receiving Wall Crusher after having
previously touched the gate. Acquiring the upgrade while still
holding attack cannot retroactively trigger destruction. A new
button press is needed. A stale sensor flag combined with an attack
at a distant position cannot break the obstacle. A reset does not
mint a reward or re-arm a held attack.

The caller **still owns the world and the physical input level**;
the code does not authenticate a physical Joy-Con, assert original
attack animation data or verify proprietary `MULevel1-1.lvl`
geometry. The 32×12 test world is fictional. This is a safe
integration seam, not a gameplay-accurate original iOS port.

### Tests

```sh
sh native/run_tests.sh gcc
sh native/run_tests.sh clang
```

Dedicated GCC/Clang ASan/UBSan jobs run the same source-native
session test. The stable two-room NRO, three-room demonstrated
NeXium route, original IPA and public asset archive are untouched.

Source identity, exact gate/sensor locations, tile collision
categories and original behavior remain tracked in
[Issue #110](https://github.com/stanmasked/he-man-remake/issues/110).
