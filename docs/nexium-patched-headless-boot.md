# Stage 035 — patched NeXium guest CPU boot, without a GUI

The previous staged PR proves only whether the actual Rust `nexium-loader`
accepts genuine devkitPro NRO data segments byte-for-byte. An accepted
binary is not yet a running guest application.

This experiment takes the next verifiable step using NeXium's own
`debug_boot` command-line binary. It compiles the pinned NeXium Rust
source with the stage-033 loader patch, then attempts to execute **our
independently authored minimal libnx NRO** and the source-only He-Man
raster NRO.

Workflow: `.github/workflows/nexium-patched-headless.yml`.

- The build runs `cargo build -p nexium-gui --bin debug_boot
  --no-default-features --features backend-rustarmic`, avoiding the
  Dynarmic backend. It uses the upstream built-in debugging entrypoint.
- The minimal NRO first uses the debug CPU path. Evidence requires
  `Boot context initialized`, an actual initial program counter
  and guest execution/SVC diagnostics.
- The graphical NRO is then tested using the production runner path,
  which reports retired CPU cycles, SVC counts and captured guest frames.
  Evidence requires nonzero guest CPU work. **Frame count is reported
  separately; a nonzero cycle count is not a verified rendered frame.**
- Standard logs and NRO SHA256 are retained as GitHub Actions artifacts
  even on crashes or timeouts.

All inputs are built in CI from source with devkitPro. No original iOS
IPA, commercial ROMs, cryptographic keys or firmware dumps are used.
No patched upstream executable is distributed as a downloadable
artifact. Only diagnostic log text is uploaded.

This experimental CI job is deliberately strict. An error during
NeXium's native compilation, an unsupported emulated system service,
guest CPU exception or lack of actual guest execution must produce a
**failure**, rather than a misleading claim that the game works. A
passing headless test will still need real pixel/color and controller
validation with the GUI before confirming an interactive Switch port.

Tracked root issue:
https://github.com/stanmasked/he-man-remake/issues/30
