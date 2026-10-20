# Stage 091 — real NeXium three-room optical regression (experimental)

The pinned emulator's **two actual guest frame_rx loops** write genuine
640×360 PNG frames and receive ordinary HID button commands. Neither NRO
pixels nor RAM, physics, map, collision masks or native completion flags are
patched. In particular, this test is NOT a game screenshot generator.

## Source of truth and proof boundary

- The opt-in NRO is built with `CHAIN_PROBE=1 THREE_ROOM_PROBE=1
  AIR_SMASH_PROBE=1` and SHA-256 compared before and after running.
- **Stage 1:** D-pad Right earns real C99 x90 exit, A90 advances to stage 2.
- **Stage 2:** D-pad Right, fresh A350 jump past real x570 hazard, native
  x735 CLEAR; fresh A510 advances to stage 3. No premature FINISH allowed.
- **Stage 3:** D-pad Right from x48, trigger authored x434 checkpoint and
  x678 hazard; verify source-native respawn badge, try real A952 jump to
  avoid the hazard, and earn native x842 CLEAR/FINISH. Final B1140 must
  reset the *third* room and clear the on-screen FINISH and respawn badge.
- The script samples stage digits 1/2/3 via **all 15 native glyph cells**,
  authentic world-X and world-Y HUD, CLEAR border and glyph, FINISH+B
  optical pixels, and stable full-image bytes at terminal freeze.
- All HID receipt lines, PNG absolute paths, sizes and SHA-256 are checked
  against the current run. Guest source is pinned; test refuses repeated
  or missing frames. Synthetic mocks only verify checker strictness.

**Warning:** All frame numbers for the third-room path are tentative
controller timing hypotheses. A red guest test is a failed experiment, not
permission to alter the map, game code, AArch64 NRO, original IPA, emulator
RAM or PNG content. Inspect the authentic guest evidence and adjust input
timings, then rerun the *unchanged* NRO. Its success must not be claimed
until real guest jobs are green.

### World-X marker limitation

The debug renderer's magenta x-indicator clamps at player world x210. It
cannot alone show crossing room-3 x678 or reaching x842. The verifier
instead requires the native hazard/respawn indicator, fresh A jump on the
world-Y ruler, genuine stage-3 CLEAR and FINISH, and subsequent native B
restart, all independently derived from source C99 game state **only at
rendering time**. The third-room collision is never changed to make the
optical receipt green.

Stage 090 host C99 traversal proof in Draft PR #98 independently earned
CLEAR in 505 fixed-step frames. It is NOT a substitute for this guest
workflow.

Original He-Man iOS v2.0.0 mechanics and graphics parity remain unverified.
Private original IPA/assets stay local and are never checked into GitHub.
The existing one- and two-room prototype NROs stay untouched.
