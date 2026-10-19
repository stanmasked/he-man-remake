# Stage 053 — checkpoint B-retry after post-defeat sword victory

This additive regression extends the existing **source-only C99 raster
test** introduced by Stage 052. The complete Stage 052 sequence remains
unchanged: move by real simulated input to a synthetic checkpoint, survive
three enemy contacts until 0 HP, automatically recover on the next
simulation frame, and defeat the enemy with two genuine native sword
presses. The test uses the same native C99 code and 640×360 RGBA8888
rasterizer linked into the Nintendo Switch homebrew NRO.

## What the new continuation verifies

After the first sword victory, simulate an ordinary **B/manual reset**.
The native physics, session and combat modules must:

- keep the activated checkpoint at **world x=90** rather than returning
  to the original x=50 spawn;
- increment the true native respawn counter from 1 to 2;
- restore player health to **3 HP** and enemy health to **2 HP**;
- restore enemy patrol start and direction, and clear combat frame,
  sword hits, player hits, sword cooldown and contact immunity;
- ignore a sword press **on** the reset tick, so no ghost attack is
  counted, while still accepting new player input on subsequent ticks.

Run another full two-X attack sequence against the reset enemy. Verify
the actual C99 renderer displays successive **enemy HP 2 → 1 → 0**
and **hero HP 3 → 2 → 2**. A second manual reset after this victory
must increment the respawn counter to 3 and restore both combat actors
without forgetting the active checkpoint. Also exercise the second
manual reset with Left + Jump + X held to ensure the *reset* itself does
not move the character or register a sword attack.

This supplements Stage 048's earlier **hazard**-induced reset and
Stage 052's genuine guest **auto-recovery + X victory**. The new
continuation specifically covers **manual retry after victory** and
the idempotent encounter reinitialization path. The test is built
and executed by the existing `native/run_tests.sh` CI jobs under
both GCC and Clang without adding any emulator build cost.

## Evidence limits

This change only extends the host-side C99 test. It does **not**
establish that the new post-victory B sequence has been run inside
NeXium or on physical Nintendo Switch hardware. Do not claim
guest-controller proof from this source-only test. Stage 052's
existing independent genuine NeXium proofs remain unchanged.

The public repository contains no proprietary He-Man IPA, game assets,
Nintendo firmware or keys.
