# Stage 104 — C99 physics-bound lore contact adapter for Level 1-1

The independent lore progression rules from Stage 102 did not know
whether a genuine gameplay movement step overlapped the selected item.
This stage adds a separate **opt-in native C99 adapter** that takes
the existing core's `hm_world`, consecutive `hm_state` values, exact
movement input and fixed timestep, plus three explicit event bindings.

## Contact evidence, not guessed coordinates

The bindings must identify three distinct in-bounds indices of already
validated native `hm_world.events`:

- `HM_TRIGGER`: the destructible left barrier's sensor.
- `HM_PICKUP`: Bio Skeletor, requiring Wall Crusher and opened barrier.
- `HM_PICKUP`: Game Concept Art 09, open without the Wall Crusher.

Before granting ANY reward, `hm_level11_accept_native_frame()`
copies the old player state, calls the existing **production
`hm_step()`**, and demands byte-for-byte identity with the supplied
new state. An arbitrary manual "overlap = true" or edited
`hm_state.picked`/`triggered` flag fails. The adapter accepts
only newly earned pickup/trigger bits on an actual consecutive native
simulation step. It refuses teleport/reset or death/respawn rewards.
For the gate, the trigger crossing **must coincide with a declared
fresh attack button press**, and the Wall Crusher must already have
been granted. The gate opens BEFORE processing pickup bits from the
same frame. Duplicate input receipts are idempotent. Failure to
validate an entire receipt leaves lore state unchanged.

This contracts **source-native movement contact with a separately
supplied attack edge**. The edge comes from the caller, not independent
emulator proof. It does not authenticate the original game model,
recognize attack animations, check collision geometry sourced from the
IPA, assert original iOS object IDs or infer camera coordinates.

## Test and integration boundary

`native/tests/test_level11_native_contacts.c` constructs a tiny
**fictional**, asset-free world and uses the ACTUAL core
`hm_step()` to approach pickups and a gate. Tests ensure ordinary
movement cannot break the gate, acquiring Wall Crusher without the
correct simultaneous attack/trigger does not break it, the open
collectible is independent, gated lore cannot be reached by bypass,
forged frame/pickup/trigger/position flags fail, bindings must have
correct roles, reset fails closed and replay cannot duplicate rewards.

Run:
```sh
sh native/run_tests.sh gcc
sh native/run_tests.sh clang
```
A dedicated GitHub Actions job runs strict C99 builds under
ASan/UBSan for GCC and Clang.

The project must **not** treat the fictional positions in this test as
the original iOS level's geometry. Original `MULevel1-1.lvl`,
`.map`, `.shape`, ownership, control timing and contact semantics
still require the private, source-evidence requirements in
[Issue #110](https://github.com/stanmasked/he-man-remake/issues/110).
The private IPA is not imported into GitHub or CI. No current Switch
NRO selects this adapter, and the stable two-room / proven
three-room guest runs remain unchanged.
