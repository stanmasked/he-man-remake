# Stage 011 — keyboard-controlled host scene

**Status:** a functional **desktop test scene**, not a port or a complete Nintendo Switch game. It uses independently drawn placeholders and our experimental masked-collision physics. No original He-Man artwork, music, animations or level bytes are contained in this public repository.

## Start on a desktop with Python 3.10+ and Tkinter

From the repository root:

```sh
PYTHONPATH=src python -m heman_tools.host_demo
```

A standalone 800×480 window opens showing a simple, **synthetic 100×30-tile exercise course**. The warm-colored rectangle/circle represents the player. Solid ground, ramps, raised platforms and a pit are hand-built fixtures; they are not extracted from iOS.

Controls:

| Key | Function |
|---|---|
| Left arrow or A | Walk left |
| Right arrow or D | Walk right |
| Space / W / Up arrow | Jump (new keypress) |
| R | Reset to the test spawn |
| Esc | Quit |

The scene advances at a fixed 60Hz simulation step with bounded catch-up, horizontal/vertical scrolling camera, foot/body collision masks, provisional slope adhesion, jump, gravity and respawn after falling below the map. Camera coordinates are clamped to level extents.

## Reproducible tests without display

```sh
PYTHONPATH=src python -m heman_tools.host_demo --headless --ticks 240
PYTHONPATH=src python -m unittest discover -s tests -v
```

Headless replays require **no Tkinter display and no Pillow**, and are suitable for GitHub Actions. The synthetic full test suite is **156 tests** (21 new tests this stage). The scripted input trace settles, walks right, jumps at a fixed frame, and stops. Repeat executions with the same inputs yield identical state.

## Optional private first-level collision import

Users possessing the original iOS v2.0.0 IPA can examine its tile-level collision **locally**, without uploading any source game files:

```sh
python -m pip install Pillow
PYTHONPATH=src python -m heman_tools.host_demo --ipa /private/He-Man-v2.0.0.ipa
```

The optional `--ipa` mode reads `MUMap1-1.map` and `collisionTiles.png` from the local archive, decodes in memory, and renders only temporary flat shapes. It defaults to a **synthetic diagnostic starting point** X=50, feet Y=0, rather than claiming to reproduce the genuine player spawn.

To run a deterministic private replay instead of a window:

```sh
PYTHONPATH=src python -m heman_tools.host_demo --ipa /private/He-Man-v2.0.0.ipa \
  --headless --ticks 240 --out local_reports/host_replay.json
```

The original IPA stays unchanged. Keep `local_reports/` private and Git-ignored. Never commit purchased media or regenerated game art.

## Boundaries and unknowns

- No original iOS application code is executed.
- Pixel alpha of the collision texture is only a **working approximation**, not verified physics semantics.
- Character hitbox size and movement speeds are invented for experimentation.
- Stage 011 has no enemy AI, combat, animated sprites, sound, real graphics, one-way platforms or original camera state logic.
- The Tk desktop window has not been interactively tested in CI because CI has no graphical display; CI verifies its headless simulation path and model behavior.
- A Switch-targeted homebrew NRO build, controller mapping and emulator smoke tests remain future work.

Next: host gameplay loop refinements, validate original behavior from private play footage if available, then separate a platform-independent C core suitable for devkitPro builds.
