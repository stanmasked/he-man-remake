# Stage 013 — synthetic event markers and gameplay HUD

This stage makes the Stage 012 fictional event state visible in the existing desktop Tkinter demo. It **does not reproduce or contain original He-Man artwork, scripts, collision materials or objective logic**.

## Start the desktop event course

```sh
PYTHONPATH=src python -m heman_tools.host_demo --interactions
```

The flag selects a hand-authored test level with synthetic items, checkpoint, trigger, hazard, and exit. All markers use basic Canvas shapes and text. In this mode:

- Gold circles with **+** are pickups; they disappear when collected.
- Green squares marked **C** are checkpoints; the current checkpoint is highlighted.
- Pink triangular **!** icons represent hazards that reset the player.
- Blue **T** icons are triggers; activated triggers become dim.
- Purple **E** icons mark the exit and become dim on completion.

The overlay moves with the camera and filters out icons beyond the viewport. A compact HUD shows collected/total pickups, checkpoint active/inactive state, hazard hit count, respawn count, triggered events, and exit state. The original arrow/A/D movement, jump, reset and escape keys continue to work.

## Test without a window or game assets

```sh
PYTHONPATH=src python -m heman_tools.host_demo --headless --interactions --ticks 180
PYTHONPATH=src python -m unittest discover -s tests -v
```

The new event view is factored into a pure presentation model (no Tkinter import) and a small Canvas drawing adapter. Automated tests validate clipping, camera offsets, pickup disappearance, activated state highlights, all five marker kinds, HUD counters and draw calls on a fake Canvas. Four additional tests exercise the headless CLI switch, backward compatibility, deterministic replay and refusal to mix synthetic scripted events with purchased IPA input.

This stage adds **15 synthetic tests** (11 view tests plus 4 CLI tests), bringing the stacked branch to **190 tests** assuming the existing 175-test Stage 012 branch. GitHub Actions will confirm the full matrix independently.

## Limits

- `--interactions` intentionally accepts synthetic scenes only. Combining it with `--ipa` is rejected, because original iOS event semantics are unknown.
- The plain `--ipa` mode remains available separately for local physics research.
- The original gameplay logic, animation states, enemy AI, health, voice/audio and Nintendo Switch binary are not implemented.
- The window needs desktop Tkinter and a graphical display; the deterministic no-window version runs under standard-library Python.

No original game asset is included or uploaded.
