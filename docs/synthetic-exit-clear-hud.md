# Stage 055 — visible native course completion (synthetic Switch NRO)

The independent raster Switch prototype already includes an `HM_EXIT`
world event. `native/src/heman_core.c` makes contact with that
event set `hm_state.completed=1` and keeps it set. Until now the
graphical `switch_raster` application ignored that established result:
a player could reach the exit arch without a visible success signal.

This small gameplay/UI integration draws a deterministic **CLEAR**
badge in the upper-right section of the 640×360 RGBA8888 framebuffer
whenever `view->game->player.completed` is nonzero.

The badge is rendered using **five newly authored 3×5 bitmap
letterforms** (C, L, E, A, R) and flat geometric fills. It loads no
image, font, sprite, texture, sound, proprietary level or network asset.
Its location, pixels and palette do not overlap the original QA
fingerprint or player/enemy health bars. Existing checkpoint and combat
logic are unchanged.

## Exact host-side regression

The existing `raster/tests/test_raster_scene.c` checks:

1. No amber CLEAR glyph or green completion border while the native
   completion flag is zero.
2. A visible amber glyph at framebuffer pixel **(553,53)** and green
   border at **(547,47)** only when completion becomes true.
3. Restoring the completion flag to zero reproduces the exact prior
   framebuffer checksum (no permanent stamp).
4. Original guarded framebuffer prefix/suffix and padding columns
   remain unchanged on the completed frame.
5. All previous invalid-render fail-closed checks continue to pass.

CI's existing `native/run_tests.sh` executes this renderer under
both **GCC** and **Clang**, and the existing devkitPro NRO build validates
the same raster source cross-compiles on Nintendo Switch.

The current normal synthetic `switch_raster` stage has an exit event
near world x=728; no original iOS maps, artwork, dialogue, mechanics,
level progression or complete game is implemented. A future real
guest-NeXium input scenario can prove reaching the exit and seeing the
CLEAR indicator. Until that happens, **do not claim guest visual proof
or console hardware verification of this new feature**.

This source-only change does not publish the user's privately held iOS
IPA or any extracted proprietary game resources.
