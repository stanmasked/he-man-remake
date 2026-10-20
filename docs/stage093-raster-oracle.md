# Stage 093 — native raster oracle at NeXium proof checkpoints

This **host C99 renderer** check uses the exact existing source-authored C99
physics, three independently-authored training rooms, native collision and
completion flags, and the same Right/A/B HID frames as Draft PR #99. It
reproduces all **18 planned guest screenshot sampling points** while running
1190 genuine C99 gameplay frames.

It renders the actual 640×360 raster scene and source HUD composition used by
`switch_raster/source/main.c`, including `hm_three_room_marker`,
`hm_dash_hud`, `hm_finale_overlay` and `hm_air_smash_hud`.
At each sampled frame, the GCC/Clang test checks the **full 3×5 stage digit**,
exact CLEAR border/glyph colors, six separate FINISH + B prompt pixels,
native checkpoint/hazard respawn indicator, precisely 192 magenta world-X HUD
pixels and nine cyan world-Y ruler pixels. The two terminal source raster
framebuffers must also match byte-for-byte.

This catches cases where a Python optical verifier expects a pixel pattern
that the *actual C renderer* does not produce. It is a test of the **source
code and sample timings**, not of the AArch64 build, guest controller
transport, NeXium emulation or screenshot bytes. The original game assets
and private iOS IPA remain off GitHub, and no playable level is modified.

Required next receipt remains unchanged: a successful authentic pinned
NeXium `frame_rx` PNG/HID run for [Draft PR #99](https://github.com/stanmasked/he-man-remake/pull/99)
at the exact head commit being certified. Source renderer success alone
cannot close [Issue #97](https://github.com/stanmasked/he-man-remake/issues/97).
