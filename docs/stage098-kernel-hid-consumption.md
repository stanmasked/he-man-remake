# Stage 098 — true kernel consumption of NeXium Right/A/B controller presses

Pinned upstream `nexium-kernel/src/hid_state.rs` reads
`NEXIUM_HID_INJECT` only after a **25 ms polling interval**, and the
`debug_boot` visual receiver counts independent `frame_rx` deliveries.
The previous `HEMAN_THREE_HID` log guaranteed only that the debug
runner wrote a controller packet, not that the guest actually received
every short A/B press. That was a material proof gap.

This stage adds `tools/verify_nexium_hid_publication.py`, which reads
**authentic kernel-generated** `[hid-publish]` trace lines in the same
`raster-stdout.log` that the real patched NeXium binary emits when
`NEXIUM_HID_TRACE=1`. Each required source `HID_EVENTS` state
transition must occur in order, including both A room transitions,
room-two/three A jumps, complete button releases, and B replay.
Every sample must report `exclusive=true`, nonzero mapped shared
memory and NPAD layout values containing exactly the injected button
mask. Trace events with identical successive masks are deduplicated;
initial neutral state is permitted, but missing or additional
controller transitions fail closed.

This validation is now a mandatory **additional separate step** in the
real guest workflow, before any PNG verification. The complete
`guest-hid-publication-report.json` is retained with other native
NeXium evidence. If a short button press is lost in kernel polling,
the optical test **must fail rather than quietly certify a file write**.
No source NeXium emulator, gameplay logic, physics, maps, native NRO
pixels, iOS IPA or other confidential assets are changed.

The Python 3.10/3.13 unit tests use manufactured kernel-like traces
only to demonstrate rejection of missed/extra A/B presses, NPAD
mismatches, bad sampling numbers and nonexclusive input. Passing those
mocks is **never** evidence of NeXium execution. Only actual pinned
kernel trace plus genuine guest frame_rx PNGs can close
[Issue #97](https://github.com/stanmasked/he-man-remake/issues/97).
