# Stage 099 — verify the REAL pinned NeXium kernel HID source contract

The Stage 098 guest HID publication reader is not allowed to infer that an
input reached the guest merely because a debug_boot Rust process wrote
`buttons=A` to disk. It requires actual `[hid-publish]` lines emitted by
the `nexium-kernel/src/hid_state.rs` implementation.

To avoid trusting a Python parser whose button bits or receipt format might
silently diverge from upstream, Stage 099 adds a second fail-closed source
contract gate. **After checkout of the exact upstream NeXium commit and
before cargo build**, `check_pinned_nexium_hid_source.py` inspects the
temporary **real Rust source** and verifies:

- Full 7-layout NPAD shared-memory publication
- The literal NeXium button-bit mappings for A/B/D-pad and relevant controls
- The actual `buttons=DRIGHT/A/B` string parser bindings
- The 25ms kernel injected-input polling code
- Exclusive controller input, actual shared-memory mapping and publication
- The exact `[hid-publish]` format consumed by Stage 098's parser

Malformed or changed upstream symbols abort the real NeXium CI before
building the emulator. A separate Python 3.10/3.13 job runs mutation tests
using constructed Rust fragments; those tests **do not** inspect the pinned
upstream repo and are never guest execution proof. The real guest step
produces `pinned-kernel-hid-source.json` in its CI artifacts, alongside
the kernel publication report and authentic NeXium frame_rx screenshots.

No gameplay changes, emulator patches, physics modifications, native
NRO pixels, private iOS IPA or stable 2-room content were made.
Issue #97 remains open until actual Switch AArch64 guest frames, HID
receipts and CLEAR/FINISH/B evidence pass in NeXium.
