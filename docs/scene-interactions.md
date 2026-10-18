# Stage 012 - independent scene interactions

This is a **source-only prototype** for the desktop test scene. Events are entirely synthetic, not copied from the original iOS game.

## Interactions

| Kind | Behavior |
|---|---|
| pickup | Collect once, keep after reset |
| checkpoint | Update the respawn location |
| trigger | Record a single activation |
| hazard | Respawn and increment hazard hit count |
| exit | Mark the synthetic scene completed |

Events are identified by unique IDs and world-coordinate circles. The actor's full rectangular collision body is considered, including its head and sides. Between-frame movement is also sampled to avoid skipping over small event regions. Checkpoints are rejected if the player-sized body would overlap solid terrain at the saved respawn point.

## Asset-free headless verification

    PYTHONPATH=src python -m heman_tools.events_demo --ticks 240
    PYTHONPATH=src python -m unittest discover -s tests -v

The CLI prints JSON with the final position, collected IDs, active checkpoint, activated triggers, hazard contacts and completion flag. It uses neither Pillow, Tkinter nor purchased media.

The stage adds 19 synthetic test methods (15 scene interactions, 4 replay/validation), bringing the cumulative total to 175 if all earlier stages are present.

## Important limitations

- All event rules here are **invented gameplay approximations**. They do not reproduce the original iOS game scripts, combat, checkpoints or objectives.
- The first version provides event-state logic and headless replay. Graphical pickup/trigger icons are not yet implemented.
- A real Nintendo Switch NRO and original visual/audio presentation remain unfinished.
- The purchased IPA, original maps, images and generated private reports stay outside GitHub.

Next: integrate a user-visible event HUD into the desktop host scene, then investigate a platform-independent game loop suitable for future devkitPro builds.
