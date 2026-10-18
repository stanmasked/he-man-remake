# Stage 034 — Real Rust loader vs real devkitPro NRO regression

Earlier stages isolated the fact that NeXium's existing NRO parser fails
before starting a legitimate libnx homebrew. Stage 033 produced a
source-only candidate fix, confirmed that it applies to a pinned upstream
commit, and checked the normal NRO file layout in Python.

**This stage goes one step further**: it executes the **actual NeXium Rust
loader**, not a reimplementation, against the original unchanged .nro
outputs of devkitPro.

## Independent evidence

Workflow: `.github/workflows/nexium-loader-real-nro.yml`.

The workflow compiles both synthetic projects from this repository:

- `heman_minimal_guest_probe.nro`: no He-Man gameplay code, tiny libnx
  framebuffer program with a magenta input-dependent rectangle.
- `heman_raster_probe.nro`: graphical synthetic terrain and player built
  from the independently authored C99 gameplay engine.

It then checks out NeXium source at commit
`b6149f647f1b0824e450555beb6cfc16b6f0e075`, copies an isolated
Rust integration test into the upstream `nexium-loader` crate, and runs
two controlled experiments:

1. **Unpatched upstream:** attempt loading both NRO files and verify the
   expected `Data segment out of bounds` error is reproduced.
2. **Patched loader:** apply our previously verified source-only
   `nexium-nro-segment-file-origin.patch` in the temporary checkout and
   rerun the same Rust integration test. Require both NRO files to load
   successfully, including byte-for-byte matching of full-file text,
   read-only and data segments and exact NRO0 image origin.

This does not modify the NRO files, copy original iOS assets or install
a new NeXium binary on the user's device. Both generated test NROs are
independent synthetic programs.

## Acceptance criterion and boundary

A successful CI run proves that the **Rust loader module** now interprets
both real, unmodified devkitPro NRO files as expected. It does *not* prove
the NeXium kernel, JIT, graphics backend, controller mapping or emulator
GUI runs the guest successfully. A full patched NeXium build and a
separately verified guest framebuffer will still be necessary to close
[Issue #30](https://github.com/stanmasked/he-man-remake/issues/30).

The test is deliberately version-pinned and uses no firmware, title
keys, commercial ROMs, original IPA or other protected media.
