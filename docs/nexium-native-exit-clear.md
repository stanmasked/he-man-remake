# Stage 056 — genuine NeXium controller → native exit → visible CLEAR

The **Stage 055** host raster test renders a CLEAR badge only when the
existing native C99 physics engine sets `player.completed` in response
to `HM_EXIT`. This draft extends that evidence into a genuine
Nintendo Switch NRO running in the pinned NeXium emulator.

## Controlled guest experiment

The ordinary NRO course is unchanged. An opt-in `EXIT_PROBE=1` build
compiles the **same** physics, `hm_session_step`, framebuffer renderer
and controller adapter, with the synthetic exit placed at x=90, 40
world units from the player spawn (x=50). The only `HM_EXIT_PROBE`
code changes the *test event list*. An existing enemy remains far away,
so contact damage does not interfere.

| Guest frame | Input / evidence |
| --- | --- |
| 30 | Capture before input; CLEAR must be absent |
| 45 | Genuine injected D-pad Right press |
| 60 | Intermediate original guest frame |
| 80 | Player reached native HM_EXIT; CLEAR badge must be present |
| 105 | Release D-pad Right |
| 120 | Capture after release; CLEAR persists |
| 300 | Persistent native completion, stable position after release |

`tools/instrument_nexium_exit_clear.py` extends the existing pinned
NeXium guest-frame receiver instrumentation and **does not modify
guest NRO bytes, guest RAM or framebuffer contents**.

The fail-closed verifier checks:

- All five original 640×360 RGBA PNGs and matching genuine `frame_rx`
  log records.
- Exact real HID press/release lines at frames 45 and 105.
- The genuine magenta *player world-x marker* moves by at least 50
  pixel units; the marker stops moving after release.
- The CLEAR border and first letter are both absent at frame 30,
  both present at frames 80, 120 and 300; a partial badge fails.
- Source-authored RGBA8888 is stored as little-endian pixel words, so
  the actual PNG RGB byte triples at **(547,47)** and **(553,53)**
  are **(80,105,33)** and **(134,212,240)** respectively.

The independently authored synthetic art and 3×5 glyphs are **not**
original copyrighted game graphics. No commercial He-Man gameplay,
physics or progression is claimed. The diagnostic proves a small
self-contained course is *completable* in the emulator; it does not
prove it is an accurate remake or that it works on physical Switch
hardware.

`tests/test_nexium_exit_clear.py` includes 14 mocked host-side
positive/hostile tests. Those mocks themselves are **not** guest
evidence; only the separate `nexium-patched-exit-clear.yml` job's
real NRO, frame captures and exact input trace can prove the result.

This is stacked on Stage 055 while that stage's full regression suite
runs. Merge the parent only after all of its CI checks pass, and merge
this experimental stage only after its own current-head authentic
NeXium proof and Python/native tests are successful. Original user IPA,
extracted commercial game files, keys and firmware remain private.
