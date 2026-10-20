# Stage 095 — guard identical real guest/native controller frames

Three independently authored tests previously copied the same Right/A/B
script manually. They had already diverged once when the second-room
post-CLEAR Right-release was corrected from frame 500 to frame 470.

This stage adds a **fail-closed static parser**:
`tools/verify_three_room_hid_parity.py` imports the canonical Python
`HID_EVENTS` and `FRAMES` from the real NeXium injector and parses
both C99 `buttons_at()` switch tables. Every one of **16 distinct
button edges** must match exactly. It also checks the complete array of
**18 sampled frame numbers** in the source C99 raster oracle against
the genuine NeXium capture configuration.

The checker rejects any unrecognized C expression, duplicated source
frame, missing/extra input, changed transition A/B edge, malformed
frame list, or workflow that stops injecting exclusive real HID packets.
It also verifies a pinned, real guest PNG collection workflow is
still present. Python 3.10 and 3.13 run independently with mutation
tests demonstrating how drift is rejected.

This test does not run an emulator, validate original iOS assets, or
make any claim about guest screenshots. Original iOS IPA is never
published. No gameplay, event positions, damage, NRO, emulator or HUD
source is modified. Genuine guest proof under Issue #97 remains open.
