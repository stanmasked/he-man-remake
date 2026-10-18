# Stage 037 — verify actual D-pad Right inside patched NeXium guest

Stage 036 proved that patched NeXium executes the independently authored
He-Man homebrew and outputs genuine 640x360 guest scene PNGs, not splash
screenshots. The next critical question is **whether the guest reacts to
controller input**.

## Test procedure

NeXium's pinned upstream `nexium-kernel/src/hid_state.rs` already
supports an input file through `NEXIUM_HID_INJECT`. With the option
`NEXIUM_HID_INJECT_EXCLUSIVE=1`, input defaults to neutral when the file
contains no active buttons. The parser recognizes `buttons=DRIGHT`.

The dedicated workflow `.github/workflows/nexium-patched-hid.yml`
uses NeXium's **real existing HID injection implementation**, rather
than changing game state or directly modifying the synthetic renderer:

- At received guest frame 30, capture the player's pre-input HUD marker.
- At frame 45, write `buttons=DRIGHT` into the injection file.
- At frame 105, write `buttons=` to release all buttons.
- Capture guest framebuffer frames 120 and 300, after press and release.
- In `tools/verify_nexium_hid_pngs.py`, require the magenta marker's
  world-x centroid to move **at least 30 pixels right** and remain
  stable (within 6 pixels) after release.
- Require at least 150 visibly changed pixels in the fixed HUD track,
  full 640×360 guest PNG dimensions and the timed input change events
  in the patched NeXium runner log.

The control signal is injected into the emulator's **actual virtual
controller state**; a moving enemy, game camera, animated NeXium splash,
or changed background alone cannot satisfy the unique world-x check.

## Honest acceptance boundaries

Passing this test establishes real guest reaction to **simulated D-pad
Right** in the NeXium headless runner. It does not yet establish
physical controller handling, A/X/B/Y buttons, touchscreen, audio,
proper window presentation, accuracy to original iOS gameplay, or a
production-quality Nintendo Switch port.

All game mechanics and graphics in the test are independently authored,
not copied from the original iOS IPA. No original assets, keys, firmware,
or patched emulator executables are published.
