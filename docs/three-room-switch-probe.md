# Stage 089 — optional third room in the synthetic Switch course

This opt-in variant extends the two-room original-content-free Switch
prototype to **three training rooms**. It is based on the standalone
third-room map from Draft PR #95. Existing one- and two-room builds,
including the earlier NeXium FINISH/B verification, are unchanged.

## Build

Use the devkitPro devkitA64 environment and run from repository root:

    make -C switch_raster clean all \
      TARGET=heman_three_room_probe CHAIN_PROBE=1 \
      THREE_ROOM_PROBE=1 AIR_SMASH_PROBE=1

In the independent new course, stage 1 earns CLEAR, then a fresh **A**
edge advances to stage 2; the real stage-2 native exit similarly needs
a new A edge to enter stage 3. A is not a hidden jump on transition.
**Minus** takes priority over simultaneous A while paused, B handles
ordinary respawn, and Plus exits the NRO.

The FINISH panel and B retry are displayed **only** when stage 3 earns
its own real C99 HM_EXIT. No source-to-engine completion flag or fake
guest screenshot is injected. On stages 1 and 2, the renderer continues
showing the ordinary CLEAR badge when the current native exit fires.

Stage-3 HUD badge is drawn separately from the legacy stage 1/2
implementation, retaining the established 640×360 raster dimensions,
framebuffer stride checks and pixel positions. The optional **ZL**
air-strike training is available in the final third room when
AIR_SMASH_PROBE=1, not in the unchanged stage-2 experimental NRO.

## Test boundaries

- native/tests/test_three_room_chain.c uses actual native C99 HM_EXIT
  events in a **small invented** test world to verify two atomic
  transitions, Minus precedence, no early skips, invalid next-world
  rollback, fresh enemy/player HP, and final-stage lock.
- raster/tests/test_third_room_marker.c checks 1/2/3 bitmap colors,
  strict dimensions and framebuffer row-padding canaries.
- native/tests/test_synthetic_room3.c independently checks the authored
  56×24 map and its event types (Stage 088).
- .github/workflows/switch-three-room.yml cross-compiles a real AArch64
  NRO under devkitA64, checks its NRO0 marker and publishes only a
  short-lived **synthetic** binary.

These tests and an NRO cross-compilation are **NOT** a real NeXium
end-to-end third-level victory confirmation. Full traversal of the
actual third-room obstacles, second-room hazard and the new A transition
still needs true guest HID/PNG evidence, with stage indicators 1,2,3
and authentic native final FINISH/B restart.

The third map is original source-authored training geometry. No
original IPA, proprietary level data, extracted sprites, old iOS
screenshots or unverified iOS physics enter public GitHub.
