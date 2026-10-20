# Stage 097 — source-native framebuffer guardrails for experimental stage 3

This stage introduces a new **standalone test**, not a gameplay change:
`qa/heman_three_room_progress_sentinels.c`. It links the real
`raster/third_room_marker.c` and original `stage_marker.c`.

The test exercises exact full-width third-room optical HUD pixels at x0,
x48, x210, x434 (checkpoint), x678 (hazard), x828/x842 (goal) and x900
for 640, 641, 777 and 4096-pixel framebuffer strides. Every pixel
outside the expected 510×22 progress panel must retain its sentinel,
including padding between logical width 640 and actual stride.

It also checks zero mutations on failed source calls (invalid
dimensions, stride, null pointer, NaN/Inf/negative/world-x overflow),
before/after-frame allocation canaries, the exact stage-3 digit at
all source pixels, and **byte-for-byte equivalence** of stage 1 and
stage 2 badges between the new 3-room compositor and preexisting
2-room renderer.

GitHub Actions compiles and runs the test with GCC and Clang, strict
C99 warnings, AddressSanitizer and UndefinedBehaviorSanitizer. A green
result confirms only **source C99 memory and drawing contracts**.
This check never runs NeXium, captures guest `frame_rx` PNGs or
modifies the source IPA, authored gameplay geometry, movement, or
any Switch production NRO. It cannot close [Issue #97](https://github.com/stanmasked/he-man-remake/issues/97).
