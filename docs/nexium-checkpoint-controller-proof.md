# Stage 049 — genuine NeXium checkpoint activation and B-button respawn

This test extends the **real-emulator evidence** to world checkpoints.
Stage 048 already verifies natural combat defeat and recovery at checkpoints
in portable C99. Stage 049 independently proves activation and use of a
checkpoint through genuine NeXium controller events and framebuffer bytes.

## Asset-free guest, unchanged game mechanics

The normal Switch homebrew NRO, core physics/combat engine and original
synthetic artwork remain unchanged. A separate opt-in build uses
\`make -C switch_raster TARGET=heman_checkpoint_probe CHECKPOINT_PROBE=1\`
to select a nearby event table: the checkpoint is at world (90, 272),
a distant hazard is at (210, 262). The ordinary enemy is far away,
so HP remains 3/3. The normal build keeps its existing event layout.

In a temporary pinned upstream NeXium Rust debug runner,
\`tools/instrument_nexium_checkpoint.py\` adds frame_rx PNG captures at
frames 30, 95, 145, 195 and 230. Input is injected only through NeXium's
existing \`NEXIUM_HID_INJECT\` controller file:

| Frame | Controller action |
| --- | --- |
| 45 | Hold D-pad Right, pass checkpoint x=90 |
| 78 | Release Right |
| 107 | Press B (native game reset/respawn) |
| 117 | Release B |
| 160 | Hold Right after checkpoint respawn |
| 174 | Release Right |

The verifier requires **real 640×360 guest PNG bytes** showing:

- Frame 30 starts near spawn x=50; checkpoint flag yellow; no respawn.
- Frame 95 shows moved world-x marker and green checkpoint flag.
- Frame 145 shows native green respawn counter and hero at checkpoint x=90,
  rather than initial x=50 or the position before B.
- Frame 195 shows fresh movement to the right after B reset.
- Frame 230 confirms motion stops after D-pad release.

All frames must have unchanged player 3/3 HP, enemy 2/2 HP, 192 magenta
world-x HUD marker pixels, and a diverse synthetic scene. Actual HID and
framebuffer capture log events are mandatory. Unmatched HUD pixels or missing
logs must fail the test.

The checkpoint flag sample uses the normal renderer colors at guest pixel
(190, 250). No game object is modified by the instrumenter; game-side B
button handling is the same logic used by ordinary players.

## CI

\`.github/workflows/nexium-patched-checkpoint.yml\` builds a real
asset-free devkitPro NRO, applies the established NeXium loader patch to
a temporary upstream checkout and runs the original guest CPU/graphics
path. It saves PNGs and logs even if the evidence verifier fails.

\`tests/test_nexium_checkpoint_instrument.py\` locks dual guest receive paths,
exact HID/capture schedules and the original little-endian RGBA8888 HUD
colors independently of NeXium.

All frame timing and pixel expectations are test hypotheses until the
corresponding **current-head GitHub Actions job reports success**.
A passing synthetic guest checkpoint does not establish original
iOS He-Man game fidelity or physical Nintendo Switch hardware operation.
No copyrighted IPA resources, original user assets, keys, firmware,
or patched emulator binaries are committed.
