# Stage 040 — contact damage, invulnerability, defeat, recovery

This stage tests the **already implemented** independently authored C99
combat/session logic with a deterministic synthetic contact encounter.

A stationary player stands at x=50, y=272. A two-HP enemy patrols
only from x=46 to 54, remaining inside the existing 9-unit contact
range. The test deliberately supplies **no player button input** and
retains the original battle rules, avoiding any special-case damage
or forced health modification.

At exactly 60 Hz and hurt_cooldown_frames=45 the expected timeline is:

| Simulation frame | Player HP | Player hits | Expected |
| --- | --- | --- | --- |
| 0 | 3 | 0 | Spawn |
| 1 | 2 | 1 | First enemy contact |
| 45 | 2 | 1 | Still invulnerable |
| 46 | 1 | 2 | Second contact after 45 frames |
| 90 | 1 | 2 | Still invulnerable |
| 91 | 0 | 3 | Third contact, defeated |
| 92 | 3 | 0 | Next-frame respawn resets combat |
| 93 | 2 | 1 | Contact damage works after respawn |

The standalone `raster/tests/test_contact_recovery_raster.c` compiles
the **same** `heman_core.c`, `heman_combat.c`,
`heman_session.c` and `raster_scene.c` sources linked into the
devkitPro Switch executable. At every checkpoint it also samples all
three actual player HP tick pixels from the 640×360 RGBA renderer and
checks that the magenta player-X and cyan player-world-Y indicators do
not move. The test is run on both **GCC and Clang** by
`native/run_tests.sh`.

This validates engine and renderer state deterministically on the host.
It is **not yet** evidence that receiving damage or respawning occurs
in an emulated NeXium guest; a dedicated opt-in devkitPro encounter
and actual guest PNGs would be needed for that stronger conclusion.

Only original asset-free prototype code is tracked in GitHub. The
user-owned iOS IPA and proprietary assets remain private.
