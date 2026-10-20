# Stage 084 — genuine NeXium FINISH / B guest proof

This is a **new, opt-in diagnostic** for the independently authored two-room
He-Man Switch homebrew prototype. It never launches the original iOS game
and never claims to measure original game's physics or hitboxes.

## What the NeXium job actually runs

The workflow `.github/workflows/nexium-patched-finale.yml`:

1. Builds the source-authored two-stage `heman_two_stage_probe.nro` with
   devkitA64/libnx and a separate minimal NRO for boot diagnosis.
2. Clones an exact pinned NeXium commit and applies the public homebrew
   loader patch. It patches **only a temporary emulator frame receiver**
   to send actual HID button inputs and capture true guest-frame PNGs.
3. Reproduces the existing stage-1 Right -> native CLEAR -> A stage transition.
4. In stage 2, moves Right, presses A for a genuine native jump near the
   synthetic hazard, then keeps moving toward the second-room C99 exit.
5. Captures genuine 640x360 guest frames before, during, and after terminal
   FINISH, followed by a B-button restart. The job uses a longer experimental
   runner duration than earlier 240-frame NeXium checks.
6. Validates **actual PNG bytes and actual HID logs**, not predicted states.
   Captures are uploaded as short-lived GitHub Actions diagnostic artifacts.

The synthetic room-2 geometry is **unchanged**: checkpoint x330, hazard
x570 and exit x735. The controller schedule is an *experimental attempt*
at traversal; the actual guest test must fail when the hero cannot cross
the hazard or does not reach the real exit. No exit flag, actor position,
guest memory or screenshot content may be patched to manufacture success.

## Optical and temporal acceptance

The verifier requires:

- Real first-room CLEAR at guest frame 75, stage marker **2** after A.
- A world-space cyan ruler rise after native jump near guest frame 365.
- The source-authored FINISH panel at guest frames 465, 490 and 515:
  border RGB (109,200,225), glyph RGB (191,230,241), underline RGB
  (138,213,66).
- **Identical complete rendered RGB guest pixels** at frames 490 and 515
  while the synthetic finished session is frozen; image hashes may
  legitimately match because the image is static.
- A true B edge at frame 540, FINISH absent by 565, stage remains 2,
  world-x HUD marker returns from its saturated endpoint to spawn, and
  player world-x remains stable without new movement input at 590.
- Exact frame logs and paths, no duplicate injection or PNG attestation,
  no missing files, and the expected 640x360 guest framebuffer size.

A native host C99 regression from Stage 083 separately validates pause,
atomic restart and frame freeze, while this stage targets actual NeXium
guest execution. A green cross-compile alone is **not** a passing guest run.

`tests/test_nexium_finale.py` constructs only fake `FakeRGB`/PNG proxy
objects for 18 failure-mode checks. Those tests cannot replace the
production NeXium guest job.

## Current limitations

This diagnostic uses public, wholly invented geometry, actor graphics and
controller actions. It does not contain extracted iOS assets, original IPA
bytes, source derived collision maps or copied YouTube video frames. The
user does **not** need an old iOS device. Original iOS v2.0.0 mechanics,
native framerate and exact controller-to-frame timing remain unverified.
