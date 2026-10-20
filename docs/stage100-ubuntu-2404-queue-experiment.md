# Stage 100 — test the GitHub runner-image queue bottleneck

For the last experimental three-room PR series, the 18-sample host-renderer
oracle, RGB→Python optical bridge, NPAD parser, HID-parity and sanitizer
jobs have repeatedly completed successfully with
`runs-on: ubuntu-24.04`. Meanwhile, core Python/C99 jobs, the
devkitPro cross-compile and the genuine three-room NeXium NRO build have
remained queued without a test result on `ubuntu-latest`.

This stage changes the **runner host selection only** from
`ubuntu-latest` to explicit `ubuntu-24.04`, covering:

- `.github/workflows/validate.yml`: both Python 3.10/3.12/3.13
  and GCC/Clang native C99 regression jobs
- `.github/workflows/switch-three-room.yml`: the existing
  isolated `devkitpro/devkita64:latest` container and existing
  three-room asset-free AArch64 NRO build (unchanged container image)
- `.github/workflows/nexium-patched-three-room.yml`: only the
  devkitPro container-based guest-NRO production job; its existing
  pinned NeXium execution already uses `ubuntu-24.04`

No game C/C99/Rust code, maps, game physics, framebuffer, private
commercial IPA, source-input controller events or guest optical
checker is altered. Using an explicitly versioned Ubuntu host runner
does not itself prove that the NRO builds or runs; all conclusions
require real completed CI jobs and authentic NeXium frame_rx PNGs.
This is an isolated CI queue-remediation experiment, not a declaration
that the GitHub-hosted runner capacity issue is definitively solved.

Related: [Issue #97](https://github.com/stanmasked/he-man-remake/issues/97).
