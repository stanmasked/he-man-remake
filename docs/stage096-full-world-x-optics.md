# Stage 096 — real source third-room world-X receipt

The existing magenta HUD intentionally clamps the native player X coordinate
after x=210. That made NeXium screenshots inadequate to independently
distinguish progress across the third training room's authored checkpoint
(x434), hazard (x678), and exit (x842).

This experimental third-room **source-native** overlay adds a small optical
ruler at the bottom of the 640×360 raster. It converts live `game.player.x`
into a fixed-width bright cursor for world x0..900. Its unique RGB value,
(42, 248, 178), occupies exactly 4×10 pixels, with a bounded rail and
static tick marks at x434/x678/x842. It is drawn through
`hm_three_room_progress` **only when `HM_THREE_ROOM_PROBE` and
`stage==2`**. It never changes hero physics, collision detection,
checkpoints, hazards, damage, pickups, or completion events. The regular
two-room NRO and its artwork are left alone.

The actual guest verifier uses `_progress_world_x` to read the cursor
from *real* NeXium `frame_rx` PNGs and requires a native x reset from
near x630 to x460 after the authored hazard, a second traverse past
x700, arrival at the x842 exit, a frozen FINISH and B restart at x48.
The independent host C99 pixel oracle draws the same new native HUD,
and the source RGB→Python bridge uses the identical pixel reader and
bounds. Mock-only tests exercise missing, forged or premature cursors;
they cannot substitute for NeXium evidence.

The original iOS IPA/game data are not published. No success from a host
RGB test can close [Issue #97](https://github.com/stanmasked/he-man-remake/issues/97);
only a real pinned guest-NeXium NRO+HID+PNG run can certify it.
