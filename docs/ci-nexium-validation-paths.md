# NeXium validation paths in He-Man iOS -> Switch

There are two different NeXium execution routes in this repository:

- **Patched headless NeXium** (CI: `nexium-patched-headless.yml`,
  `nexium-patched-hid.yml`, `nexium-patched-jump.yml`): builds pinned
  upstream NeXium from Rust source with the verified segment-origin
  loader patch, runs original source-only devkitPro homebrew NRO files,
  captures **guest framebuffer PNGs**, and checks gameplay and input
  effects. This is the meaningful reproducible, PR-triggered runtime
  verification route. A passing cross-compile is not enough.
- **Legacy unpatched nightly NeXium** (CI:
  `switch-raster-nexium.yml`): retains the original Xvfb smoke test
  for explicit manual comparisons of upstream NeXium releases.
  Its loader is known to reject the valid devkitPro NRO header with
  `Data segment out of bounds`. Earlier screenshot comparisons
  misidentified an animated **emulator loading splash** as gameplay.
  Strict marker checks correctly fail this legacy job. It is now
  available only via `workflow_dispatch` to avoid unrelated,
  predictably red jobs on source changes.

This change does **not** hide a failing guest test: the actual
Patched-NeXium CPU/PNG/HID experiments remain PR-triggered and strict.
The legacy job still fails visibly if invoked manually against a
nightly without a loader fix. As soon as the official nightly accepts
normal libnx NRO files, the manual probe can be revalidated and
considered for reactivation in PR CI.

The user-owned original iOS IPA, all proprietary source assets, Switch
keys, firmware and patched emulator executable files stay outside
public GitHub; only independently authored synthetic homebrew code
is used in these public tests.
