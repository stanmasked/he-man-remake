# Stage 108 — C99 lore save receipts and correct later Bio collection

The source-authored opt-in Level 1-1 research session can now export
and restore a **fixed, versioned, canonical little-endian 96-byte
receipt**. The receipt includes player position, physics state,
checkpoint/event flags, native frame/counters, the attack button
latch, and the two collectible rewards. It stores neither pointers
nor original IPA pixels, map arrays or proprietary asset names.
Restoration succeeds only against an independently initialized
session whose native world-content fingerprint and exact gate/Bio/
Concept Art role indices agree. It does not copy world pointers
from an untrusted file.

The receipt has a magic and schema version, reserved bytes, and a
64-bit FNV-1a checksum over its first 88 bytes. **FNV-1a detects
accidental corruption, not deliberate tampering or save authenticity.**
After a successful checksum, restoration additionally checks
boolean flags, finite coordinates and velocities, valid event kinds,
checkpoint membership, reward-count consistency and whether lore
rewards are reflected by native picked/triggered flags. A malformed
or incompatible receipt leaves the session byte-for-byte unchanged.

## Important gameplay bug also fixed

The native C99 `HM_PICKUP` flag is sticky. Previously, physically
touching the hidden Bio collectible **before** Wall Crusher would
mark it picked in the core yet correctly block the lore reward.
After opening the gate, this same sticky flag meant the item could
never be earned, even upon returning.

Stage 108 makes the Bio reward available through a **new valid
sweep pickup OR current verified hero-body contact** with that
event when the gate has been opened. An old, distant native flag
alone cannot mint a reward; the complete `hm_step()` still has
to match the real provided frame, and rewards remain idempotent.
This is the same principle already used for revisiting the
`HM_TRIGGER` barrier with an earned upgrade.

New regression tests drive actual source-native C99 movement from
a fictional 32×12 level, deliberately touch the hidden collectible
too early, save progress, reinitialize, restore, earn Wall Crusher,
return to the gate, attack once, return to the hidden collectible
and receive exactly one reward. Additional tests mutate the
receipt magic, version, size, reserved bytes, checksum, role IDs,
non-binary flags, collected-mask consistency and NaN position.
Both GCC and Clang run strict C99 ASan + UBSan coverage.

## Scope and limitations

- This is **not** the original iOS save format. It makes no claim
  about the original game's persistence, paid ability unlocks,
  upgrade acquisition sequence or replay checkpoints.
- No filesystem read/write is added. The caller owns 96 bytes
  and any eventual Nintendo Switch save-directory transaction.
- Restoring a signed/verified original IPA or authentic iOS
  gameplay is out of scope; original level geometry and contacts
  are still tracked in [Issue #110](https://github.com/stanmasked/he-man-remake/issues/110).
- This research feature is opt-in C99 only. Stable two-room and
  separately proven NeXium three-room NROs remain unchanged.

Local native checks:

```sh
sh native/run_tests.sh gcc
sh native/run_tests.sh clang
```
