# Stage 106 — detect borrowed Level 1-1 world changes after event binding

The existing Stage 105 opt-in session owns player, lore and a 0→1
attack-button latch, while borrowing a caller-owned `hm_world` and
its event, tile and optional pixel-mask arrays. The native physics
and contact verifier replay genuine C99 movement, but a caller
could accidentally re-use the same session with a changed map,
different lore coordinates, or altered movement coefficients.
A `HM_TRIGGER` bit is sticky, making *silent in-place changes*
especially risky.

This stage now pins **native fixture pointer identities and original
array bounds** during `hm_level11_session_init()`. It records a
deterministic, **non-cryptographic** FNV-1a content fingerprint over
every event kind and position, the full solid grid or optional
pixel-mask grid, and all world geometry/movement parameters. It
rechecks those borrow constraints **before** processing a frame or
granting Wall Crusher. Dimension and element-count comparisons happen
*before* reading borrowed content, protecting against a common
metadata-overread risk. Any mismatch returns `HM_LORE_INVALID`
and leaves player, inventory and attack latch byte-for-byte unchanged.

The negative tests deliberately mutate, then restore:

- A lore item's coordinates and a gate sensor's radius;
- One solid tile, even with the original tile pointer retained;
- Running speed or world dimensions;
- The event-array pointer, even with identical object content;
- A pixel-mask tile ID, a `mask_rows` bit, mask count and a
  substitute tile-array pointer;
- Invalid initiation metadata.

A restored valid fixture allows normal native `hm_step()` execution,
without forcing a new gameplay state or forging a new reward. Both
GCC and Clang run the C99 tests under ASan + UBSan in an isolated
Ubuntu 24.04 job. This is **not** an emulator run, original iOS map
import or source provenance attestation.

## Critical limitations

- The checksum is **not cryptographically secure** and does not prove
  the source came from the original IPA. It detects accidental
  mutation, not a malicious caller able to forge a state or hash.
- The caller must retain valid allocated storage for all borrowed
  arrays throughout the session. A dangling pointer cannot be
  made safe merely by a fingerprint.
- This is an **O(total world cells + mask rows + event count)**
  verification before each step. It is appropriate for an
  experimental, strict research adapter; it may need an explicitly
  verified faster path before a production Switch framerate.
- No private commercial geometry, map bytes, screenshots or original
  IPA data are included. All test geometry is fictional, and the
  stable Switch NRO and genuine three-room NeXium route are unchanged.
- Source identity and the original Level 1-1 scene remain pending in
  [Issue #110](https://github.com/stanmasked/he-man-remake/issues/110).

## Local tests

```sh
sh native/run_tests.sh gcc
sh native/run_tests.sh clang
```
