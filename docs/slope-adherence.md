# Stage 010 — experimental full-body slope adhesion

This module extends the independent Python host physics harness. It is **not**
the original game's physics engine and is not a playable Nintendo Switch build.

## Algorithm

The new opt-in function `step_body_slopes` wraps the static two-way mask
collider with bounded grounded movement. When the player is grounded:

1. Sweep the entire character rectangle horizontally at the current height.
2. If a short obstacle blocks travel, try lifting the entire body 1 through
   `max_rise` pixels, checking upward clearance including the head.
3. Retry horizontal sweep at each safe lifted position.
4. Require a real supporting surface after the move. Snap down by no more
   than `max_rise + max_drop` pixels, preventing step-up into empty air.
5. For an unobstructed move, descend at most `max_drop` to follow gradual
   down-slopes; if support ends, resume gravity.

Jumping and airborne motion continue through the previously tested
`step_body` function, without an automatic slope magnet. Wall and ceiling
blocking remain active. The older API is unchanged.

## Evidence

- **13 new synthetic unit tests**, **135 total** in the local Python suite.
- Tests cover uphill/downhill motion, high wall rejection, small step-up,
  low ceiling clearance, cliff fall, airborne/jump bypass, numeric safety
  bounds and repeatability.
- Private user-owned iOS v2.0.0 input `MUMap1-1.map` was used only locally.
  All six occupied collision tile types were decoded from the original
  collision alpha atlas.
- Among privately inspected slope areas in the first level, multiple
  short left/right probes remained grounded while changing foot height.
  No original graphics, collision masks, map bytes or per-level reports
  appear in the public source repository.

## Run synthetic host tests

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
```

To opt in to slope walking when calling the host physics API:

```python
from heman_tools.slope_physics import step_body_slopes, SlopeConfig
from heman_tools.body_physics import Body, BodyConfig

settings = SlopeConfig(max_rise=6, max_drop=6)
actor = Body(x=10, feet_y=32, grounded=True)
# grid must be a MaskedGrid constructed locally from independent masks.
actor = step_body_slopes(actor, grid, axis=1, jump=False,
                         dt=1/60, config=BodyConfig(), slope=settings)
```

## What is not yet verified

Real He-Man hitbox dimensions, gravity/jump values, one-way platforms, damage
zones, slope flags, map-to-world scaling, animation, combat and camera logic.
Pixel transparency is only a proxy for possible collision geometry. The
current algorithm is an experimental support-following model, not proof that
the original game computes collisions this way.

The next practical step is a host-controlled playable test scene with
independent placeholder rendering and keyboard/controller input, followed
by private comparisons with the purchased iOS game and eventual Switch
homebrew build integration.
