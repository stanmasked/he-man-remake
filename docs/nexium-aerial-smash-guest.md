# Stage 087 — genuine NeXium guest aerial ZL test

This experimental and independently authored gameplay test uses **real
controller input through a patched, pinned NeXium guest** rather than
mocked PNGs or artificially setting actor state.

It follows Stage 086's opt-in C99 AIR_SMASH_PROBE=1 CHAIN_PROBE=1 Switch
NRO, which maps fresh ZL while airborne to a provisional downward strike
and uses genuine swept collision to detect impact.

The 260-frame experimental script completes stage 1 with D-pad Right
and presses A to enter stage 2. It walks, jumps A and presses ZL in the
air. True guest PNGs sample the source HUD at x588,y88 and must show
ready, active, impact and cooldown. A second ZL must not defeat
recovery. The script also toggles Minus, checks two identical paused
guest frames, resumes and finally presses B to return to room-2 spawn.

The RGB samples are decoded from little-endian packed C99 RGBA:

| State | RGB |
| --- | --- |
| Ready | 216,224,110 |
| Active | 85,170,255 |
| Impact | 138,213,66 |
| Cooldown | 120,101,86 |

The schedule is an EXPERIMENT. If a guest jump or impact misses selected
frame windows, this is a genuine test failure. Inspect original NeXium
guest PNGs and adjust controller timing only. Never modify the native
map, source collision, guest RAM, or screenshot to force success.

CI compiles the exact opt-in NRO with devkitA64, builds pinned NeXium,
executes guest instructions and retains short-lived PNG/log artifacts.
The 17 synthetic checker tests are not, alone, emulator evidence.

No real iOS v2.0.0 physics parity or native framerate is claimed. The
privately held original IPA stays off public GitHub, and a vintage iOS
device is NOT required.
